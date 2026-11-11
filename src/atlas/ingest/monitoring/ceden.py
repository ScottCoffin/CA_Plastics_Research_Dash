"""CEDEN microplastics concentrations matched onto SF Bay / 5 Gyres workbook samples (S7.8a).

The CEDEN Surface Water - Chemistry Results resources (data.ca.gov CKAN datastore) hold one
row per sample, analyte and size fraction. A workbook sample is matched by ``sample_id``
(CEDEN ``SampleID``). Its concentration is the sum of all analyte results across size
fractions, which reproduces the workbook value for samples where the workbook has one.

Nothing here writes files; the CLI in ``scripts/ingest_ceden.py`` does that.
"""

from __future__ import annotations

import csv
import json
import math
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

CKAN_DATASTORE_URL = "https://data.ca.gov/api/3/action/datastore_search"
USER_AGENT = "ca-plastics-atlas/0.1 (research dashboard)"
PARENT_PROJECT = "Regional Monitoring Program-Microplastics"
UNITS = ["particles/L", "particles/g"]
PAGE_SIZE = 1000
PAGE_DELAY_S = 0.3
RESOURCE_IDS: dict[str, str] = {
    "2018": "f638c764-89d5-4756-ac17-f6b20555d694",
    "2017": "68787549-8a78-4eea-b5b9-ef719e65a05c",
    "2016": "42b906a2-9e30-4e44-92c9-0f94561e47fe",
    "2015": "7d9384fa-70e1-4986-81d6-438ce5565be6",
    "2014": "7abfde16-61b6-425d-9c57-d6bd70700603",
    "pre2000": "158c8ca1-b02f-4665-99d6-2c1c15b6de5a",
}
CEDEN_SOURCE_LABEL = "CEDEN (CC BY 4.0): sum of analyte results across size fractions"
CEDEN_CITATION_SUFFIX = (
    "; concentrations from CEDEN, California Environmental Data Exchange Network (CC BY 4.0)"
)
QA_SAMPLE_TYPES = frozenset({"FieldBlank", "LabBlank"})
MATRIX_FAMILIES = frozenset({"samplewater", "sediment", "effluent", "runoff", "blankwater"})
# Workbook matrix_source_code -> CEDEN matrix families it can correspond to. Blank-water
# samples are compatible with any code, so they are excluded from the comparison.
WORKBOOK_CODE_FAMILIES: dict[str, frozenset[str]] = {
    "manta": frozenset({"samplewater"}),
    "sw": frozenset({"samplewater", "runoff"}),
    "sed": frozenset({"sediment"}),
    "eff": frozenset({"effluent"}),
}
PLACEHOLDER_YEAR = 1950
NEAR_KM = 1.0
EARTH_RADIUS_KM = 6371.0088
_BLANK_NAME = re.compile(r"blank", re.IGNORECASE)

Transport = Callable[[str], dict[str, Any]]
PageSink = Callable[[str, int, dict[str, Any]], None]


def _normalize_keys(record: Mapping[str, Any]) -> dict[str, Any]:
    """Lower-case field names so datastore CamelCase and export UPPERCASE match."""
    return {str(key).lower(): value for key, value in record.items()}


def _text(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    return "" if value is None else str(value).strip()


def _float_or_none(text: str) -> float | None:
    return float(text) if text else None


def _parse_ceden_date(text: str) -> date | None:
    """Parse export ``M/D/YYYY H:MM:SS AM`` or datastore ISO timestamps."""
    text = text.strip()
    if not text:
        return None
    for fmt in ("%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"unparsed CEDEN SampleDate {text!r}") from exc


def _urlopen_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    return payload


def build_search_url(resource_id: str, offset: int, limit: int = PAGE_SIZE) -> str:
    """Return a datastore_search URL with list-valued OR filters (no ``facets``: HTTP 409)."""
    filters = {"Unit": UNITS, "ParentProject": PARENT_PROJECT}
    query = urllib.parse.urlencode(
        {
            "resource_id": resource_id,
            "filters": json.dumps(filters, separators=(",", ":")),
            "limit": limit,
            "offset": offset,
        }
    )
    return f"{CKAN_DATASTORE_URL}?{query}"


def fetch_ceden_microplastics(
    transport: Transport | None = None,
    *,
    resource_ids: Mapping[str, str] = RESOURCE_IDS,
    page_size: int = PAGE_SIZE,
    page_sink: PageSink | None = None,
    delay_s: float = PAGE_DELAY_S,
    sleep: Callable[[float], None] = time.sleep,
) -> list[dict[str, Any]]:
    """Page through every CEDEN resource and return the raw datastore records.

    ``transport`` maps a URL to the parsed JSON payload (default: urllib).
    ``page_sink(year, offset, payload)`` receives each raw page for archiving.
    """
    get = transport or _urlopen_json
    records: list[dict[str, Any]] = []
    first_request = True
    for year, resource_id in resource_ids.items():
        offset = 0
        while True:
            if not first_request:
                sleep(delay_s)
            first_request = False
            payload = get(build_search_url(resource_id, offset, page_size))
            if not payload.get("success", False):
                raise RuntimeError(f"CKAN datastore_search failed for {year} at offset {offset}")
            result = payload["result"]
            page = list(result.get("records", []))
            total = int(result["total"])
            if page_sink is not None:
                page_sink(year, offset, payload)
            records.extend(page)
            offset += len(page)
            if offset >= total:
                break
            if not page:
                raise RuntimeError(f"empty page for {year} at offset {offset} before total {total}")
    return records


def load_owner_export(path: str | Path) -> list[dict[str, Any]]:
    """Read the owner's TSV export (same fields as the datastore, UPPERCASE names)."""
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return [_normalize_keys(row) for row in csv.DictReader(handle, delimiter="\t")]


def aggregate_by_sample(records: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Collapse analyte x size-fraction rows into one concentration per CEDEN SampleID."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in records:
        record = _normalize_keys(raw)
        sample_id = _text(record, "sampleid")
        if not sample_id:
            raise ValueError("CEDEN record without SampleID")
        grouped[sample_id].append(record)

    summaries: dict[str, dict[str, Any]] = {}
    for sample_id, rows in grouped.items():
        units = {_text(row, "unit") for row in rows}
        if len(units) != 1 or "" in units:
            raise ValueError(f"sample {sample_id} has units {sorted(units)}; expected exactly one")
        results = []
        for row in rows:
            value = _float_or_none(_text(row, "result"))
            if value is None:
                raise ValueError(f"sample {sample_id} has an empty Result")
            results.append(value)
        dates = {_parse_ceden_date(_text(row, "sampledate")) for row in rows}
        stations = {_text(row, "stationcode") for row in rows}
        if len(dates) != 1 or len(stations) != 1:
            raise ValueError(f"sample {sample_id} has conflicting date or station")
        sample_date = next(iter(dates))
        latitudes = {_text(row, "latitude") for row in rows} - {""}
        longitudes = {_text(row, "longitude") for row in rows} - {""}
        sample_type_codes = sorted({_text(row, "sampletypecode") for row in rows} - {""})
        summaries[sample_id] = {
            "concentration_value": math.fsum(results),
            "concentration_unit": units.pop(),
            "size_fractions": sorted(
                {_text(row, "matrixname").split(",")[-1].strip() for row in rows}
            ),
            "analyte_count": len({_text(row, "analyte") for row in rows}),
            "is_qa": any(_text(row, "isqa") in {"1", "1.0"} for row in rows)
            or any(code in QA_SAMPLE_TYPES for code in sample_type_codes),
            "sample_type_codes": sample_type_codes,
            "station_code": next(iter(stations)),
            "sample_date": sample_date.isoformat() if sample_date else None,
            "latitude": _float_or_none(next(iter(latitudes), "")),
            "longitude": _float_or_none(next(iter(longitudes), "")),
            "matrix_families": sorted(
                {_text(row, "matrixname").split(",")[0].strip() for row in rows}
            ),
        }
    return summaries


def enrich_samples(
    workbook_rows: Iterable[Mapping[str, Any]],
    ceden_by_sample: Mapping[str, Mapping[str, Any]],
    *,
    rel_tol: float = 1e-5,
) -> list[dict[str, Any]]:
    """Return new workbook rows with CEDEN concentrations kept or filled and QA flags set.

    A non-null workbook concentration is kept only if it equals CEDEN within ``rel_tol``
    (relative); otherwise this raises. Null concentrations are filled from CEDEN and get a
    source label and citation suffix. Rows are never dropped.
    """
    enriched: list[dict[str, Any]] = []
    for row in workbook_rows:
        sample_id = str(row["sample_id"])
        ceden = ceden_by_sample.get(sample_id)
        out = dict(row)
        out["qa_sample"] = bool(ceden and ceden["is_qa"]) or bool(_BLANK_NAME.search(sample_id))
        if ceden is not None:
            value = float(ceden["concentration_value"])
            unit = str(ceden["concentration_unit"])
            existing = row.get("concentration_value")
            if existing is not None:
                if not math.isclose(float(existing), value, rel_tol=rel_tol, abs_tol=0.0):
                    raise ValueError(f"sample {sample_id}: workbook {existing} != CEDEN {value}")
                if row.get("concentration_unit") != unit:
                    raise ValueError(
                        f"sample {sample_id}: workbook unit {row.get('concentration_unit')!r} "
                        f"!= CEDEN unit {unit!r}"
                    )
            else:
                base = row.get("citation") or ""
                out["concentration_value"] = value
                out["concentration_unit"] = unit
                out["concentration_source"] = CEDEN_SOURCE_LABEL
                out["citation"] = (
                    f"{base}{CEDEN_CITATION_SUFFIX}" if base else CEDEN_CITATION_SUFFIX[2:]
                )
        enriched.append(out)
    return enriched


def summarize_enrichment(
    workbook_rows: list[Mapping[str, Any]],
    enriched_rows: list[Mapping[str, Any]],
    ceden_by_sample: Mapping[str, Mapping[str, Any]],
) -> dict[str, int]:
    """Count matched, kept, filled and QA samples."""
    workbook_ids = {str(row["sample_id"]) for row in workbook_rows}
    matched = [row for row in workbook_rows if str(row["sample_id"]) in ceden_by_sample]
    kept = [row for row in matched if row.get("concentration_value") is not None]
    relative = [
        abs(
            float(row["concentration_value"])
            - ceden_by_sample[str(row["sample_id"])]["concentration_value"]
        )
        / max(abs(float(row["concentration_value"])), 1e-300)
        for row in kept
    ]
    return {
        "workbook_rows": len(workbook_rows),
        "ceden_samples": len(ceden_by_sample),
        "matched": len(matched),
        "kept_workbook_concentration": len(kept),
        "filled_from_ceden": len(matched) - len(kept),
        "max_kept_relative_difference": max(relative, default=0.0),
        "ceden_unmatched": len(set(ceden_by_sample) - workbook_ids),
        "qa_samples": sum(1 for row in enriched_rows if row["qa_sample"]),
        "ceden_qa_samples": sum(1 for ceden in ceden_by_sample.values() if ceden["is_qa"]),
        "blank_named_workbook_samples": sum(
            1 for sample_id in workbook_ids if _BLANK_NAME.search(sample_id)
        ),
    }


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlam / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def consistency_report(
    workbook_rows: Iterable[Mapping[str, Any]], ceden_by_sample: Mapping[str, Mapping[str, Any]]
) -> dict[str, int]:
    """Count (never filter) date, location and matrix agreement for matched samples."""
    counts: Counter[str] = Counter()
    for row in workbook_rows:
        ceden = ceden_by_sample.get(str(row["sample_id"]))
        if ceden is None:
            continue
        counts["matched"] += 1

        workbook_date_text = str(row.get("date") or "")[:10]
        ceden_date_text = ceden["sample_date"] or ""
        if not workbook_date_text or not ceden_date_text:
            counts["date_skipped_missing"] += 1
        elif workbook_date_text.startswith(str(PLACEHOLDER_YEAR)) or ceden_date_text.startswith(
            str(PLACEHOLDER_YEAR)
        ):
            counts["date_skipped_placeholder"] += 1
        elif date.fromisoformat(workbook_date_text) == date.fromisoformat(ceden_date_text):
            counts["date_same_day"] += 1
        else:
            counts["date_different_day"] += 1

        lat, lon = row.get("lat"), row.get("lon")
        if lat is None or lon is None or ceden["latitude"] is None or ceden["longitude"] is None:
            counts["location_skipped_missing"] += 1
        elif _distance_km(float(lat), float(lon), ceden["latitude"], ceden["longitude"]) <= NEAR_KM:
            counts["location_within_1km"] += 1
        else:
            counts["location_beyond_1km"] += 1

        families = set(ceden["matrix_families"]) - {"blankwater"}
        expected = WORKBOOK_CODE_FAMILIES.get(str(row.get("matrix_source_code") or ""))
        if expected is None or not families:
            counts["matrix_not_comparable"] += 1
        elif families <= expected:
            counts["matrix_consistent"] += 1
        else:
            counts["matrix_inconsistent"] += 1
    return dict(counts)
