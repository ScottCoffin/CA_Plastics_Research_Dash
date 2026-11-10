"""Slim grants export for the Funding tab (S8.10).

Reads the S8.6 de-duplicated grants table and the S2.2 institutions table and
writes ``site/data/grants.json``: one row per grant (no abstracts, no contact
details), per-source amount basis captions, and precomputed aggregates. Output is
deterministic for a fixed ``generated_at`` and input.

Amounts are never normalised across sources. Each row carries the basis that
its source reports, and the payload carries the caveat text for every source.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

SCHEMA_VERSION = "s8.10"
PI_LIMIT = 3
UNKNOWN = "unknown"
FEDERAL_SOURCES = frozenset({"nih_reporter", "nsf_awards", "usaspending"})
# California Sea Grant is a NOAA-funded, state-hosted program; it is classed as state.
STATE_SOURCES = frozenset(
    {"ca_sea_grant", "opc_council", "delta_science_tracker", "scc_board", "state_funders"}
)
AMOUNT_BASIS: dict[str, str] = {
    "nih_reporter": (
        "NIH RePORTER award_amount, reported as the fiscal-year total cost. "
        "Not verified as life-of-award."
    ),
    "nsf_awards": (
        "NSF estimatedTotalAmt, the anticipated total award value. Not fundsObligatedAmt. "
        "Life-of-award or current-year basis not verified."
    ),
    "usaspending": (
        "USAspending Award Amount, the obligated total as the award record reports it. "
        "It may cover obligations to date."
    ),
    "ca_sea_grant": ("Sea Grant amount as announced. Most award records report no amount."),
    "opc_council": "Amount as approved by the Ocean Protection Council (staff summary).",
    "swrcb_faast": (
        "FAAST requested funds for an awarded proposal. The executed agreement amount may differ."
    ),
    "delta_science_tracker": "Amount as reported by the Delta Science Tracker.",
    "scc_board": "Amount as reported by the State Coastal Conservancy.",
    "state_funders": "Amount as reported in the state funder export. Some are 'up to' caps.",
}
DEFAULT_AMOUNT_BASIS = "As reported by the source. Amount basis not documented."
CAVEAT = (
    "Awards as reported by each source. This is not a complete record of public funding. "
    "Amounts follow each source's own basis (see amount_basis) and are not comparable "
    "or additive across sources or fiscal years. Each pass-through award appears once, "
    "on its lowest-level record; funder_chain shows the path. Plastic relevance and "
    "topic tags are provisional rule-based labels. An award listed here does not show "
    "that the funded work has been completed or is current."
)
ROW_KEYS: tuple[str, ...] = (
    "grant_key",
    "source",
    "title",
    "pi_names",
    "org",
    "org_state",
    "institution_type",
    "start",
    "end",
    "fiscal_year",
    "amount",
    "currency",
    "amount_basis",
    "funder",
    "funder_type",
    "program",
    "funder_chain",
    "url",
    "plastic_related",
    "domain_tags",
    "ca_led",
)
INSTITUTION_COLUMNS: tuple[str, ...] = ("display_name", "ror_id", "atlas_type")
ROR_PREFIX = "https://ror.org/"


def funder_type(source: str) -> str:
    """Return ``federal``, ``state`` or ``other`` for a grant source name."""

    if source in FEDERAL_SOURCES:
        return "federal"
    if source in STATE_SOURCES:
        return "state"
    return "other"


def _fiscal_year_start_month(source: str) -> int:
    """Return the first month of the fiscal year used for ``fiscal_year``.

    Federal sources and Sea Grant use the October fiscal year; state sources use
    the July fiscal year. Other sources use the calendar year.
    """

    if source in FEDERAL_SOURCES or source == "ca_sea_grant":
        return 10
    if source in STATE_SOURCES:
        return 7
    return 1


def fiscal_year(start: date | None, source: str) -> int | None:
    """Return the fiscal year that contains ``start``, or ``None`` when undated."""

    if start is None:
        return None
    month = _fiscal_year_start_month(source)
    return start.year + 1 if month > 1 and start.month >= month else start.year


def amount_basis(source: str) -> str:
    """Return the caption for what a source's ``amount`` means."""

    return AMOUNT_BASIS.get(source, DEFAULT_AMOUNT_BASIS)


def normalize_name(text: str | None) -> str:
    """Casefold and strip accents and punctuation so names compare exactly."""

    if not text:
        return ""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", folded.casefold()).strip()


def _ror_id(value: str | None) -> str:
    text = (value or "").strip()
    return text[len(ROR_PREFIX) :] if text.startswith(ROR_PREFIX) else text


def _unique_or_unknown(values: dict[str, set[str]]) -> dict[str, str]:
    return {key: next(iter(types)) if len(types) == 1 else UNKNOWN for key, types in values.items()}


def build_institution_index(
    institutions: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, str], dict[str, str]]:
    """Return ``(by_ror, by_name)`` lookups to ``atlas_type``.

    A key with more than one institution type maps to ``unknown``, so the
    lookup never guesses between conflicting records.
    """

    by_ror: dict[str, set[str]] = {}
    by_name: dict[str, set[str]] = {}
    for row in institutions:
        atlas_type = (row.get("atlas_type") or "").strip() or UNKNOWN
        ror = _ror_id(row.get("ror_id"))
        if ror:
            by_ror.setdefault(ror, set()).add(atlas_type)
        name = normalize_name(row.get("display_name"))
        if name:
            by_name.setdefault(name, set()).add(atlas_type)
    return _unique_or_unknown(by_ror), _unique_or_unknown(by_name)


def institution_type(
    org: str | None, org_ror: str | None, by_ror: Mapping[str, str], by_name: Mapping[str, str]
) -> str:
    """Return the institution type for a recipient, joining on ROR then exact name."""

    ror = _ror_id(org_ror)
    if ror and ror in by_ror:
        return by_ror[ror]
    name = normalize_name(org)
    return by_name.get(name, UNKNOWN) if name else UNKNOWN


def _strings(values: Sequence[Any] | None) -> list[str]:
    return [str(value).strip() for value in (values or []) if str(value or "").strip()]


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None


def export_row(
    row: Mapping[str, Any], by_ror: Mapping[str, str], by_name: Mapping[str, str]
) -> dict[str, Any]:
    """Map one merged grants record onto the slim public row.

    Only the fields in ``ROW_KEYS`` are copied, so abstracts never reach the output.
    """

    source = str(row["source"])
    start = row.get("start")
    end = row.get("end")
    amount = row.get("amount")
    return {
        "grant_key": str(row["grant_key"]),
        "source": source,
        "title": str(row["title"]).strip(),
        "pi_names": _strings(row.get("pi_names"))[:PI_LIMIT],
        "org": row.get("org") or None,
        "org_state": row.get("org_state") or None,
        "institution_type": institution_type(row.get("org"), row.get("org_ror"), by_ror, by_name),
        "start": _iso(start),
        "end": _iso(end),
        "fiscal_year": fiscal_year(start, source),
        "amount": round(float(amount), 2) if amount is not None else None,
        "currency": row.get("currency") or None,
        "amount_basis": amount_basis(source),
        "funder": row.get("funder") or None,
        "funder_type": funder_type(source),
        "program": row.get("program") or None,
        "funder_chain": _strings(row.get("funder_chain")),
        "url": row.get("url") or None,
        "plastic_related": row.get("plastic_related"),
        "domain_tags": _strings(row.get("domain_tags")),
        "ca_led": row.get("ca_led"),
    }


def _sort_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return (row["start"] or "9999-12-31", row["grant_key"])


def _aggregate(rows: Sequence[Mapping[str, Any]], keys: Sequence[str]) -> list[dict[str, Any]]:
    buckets: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        key = tuple(row[name] for name in keys)
        bucket = buckets.setdefault(
            key,
            {
                **{name: row[name] for name in keys},
                "count": 0,
                "amount_count": 0,
                "amount_sum": 0.0,
            },
        )
        bucket["count"] += 1
        if row["amount"] is not None:
            bucket["amount_count"] += 1
            bucket["amount_sum"] += row["amount"]
    result = []
    for key in sorted(buckets):
        bucket = buckets[key]
        bucket["amount_sum"] = round(bucket["amount_sum"], 2)
        result.append(bucket)
    return result


def build_payload(
    rows: Sequence[Mapping[str, Any]],
    institutions: Iterable[Mapping[str, Any]] = (),
    *,
    generated_at: str,
    input_rows: int | None = None,
) -> dict[str, Any]:
    """Build the public grants payload from merged grant and institution records."""

    by_ror, by_name = build_institution_index(institutions)
    exported = [export_row(row, by_ror, by_name) for row in rows]
    keys = [row["grant_key"] for row in exported]
    if len(set(keys)) != len(keys):
        raise ValueError("grant_key values must be unique")
    exported.sort(key=_sort_key)

    per_source: dict[str, dict[str, Any]] = {}
    for row in exported:
        entry = per_source.setdefault(
            row["source"],
            {
                "rows": 0,
                "funder_type": row["funder_type"],
                "amount_basis": row["amount_basis"],
                "amount_rows": 0,
            },
        )
        entry["rows"] += 1
        entry["amount_rows"] += row["amount"] is not None

    dated = [row for row in exported if row["fiscal_year"] is not None]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "caveat": CAVEAT,
        "counts": {
            "input_rows": len(rows) if input_rows is None else input_rows,
            "exported_rows": len(exported),
            "undated_rows": len(exported) - len(dated),
        },
        "sources": {name: per_source[name] for name in sorted(per_source)},
        "columns": list(ROW_KEYS),
        "rows": exported,
        "aggregates": {
            "by_year_funder_type": _aggregate(dated, ("fiscal_year", "funder_type")),
            "by_institution_type": _aggregate(exported, ("institution_type",)),
        },
    }


def serialize(payload: Mapping[str, Any]) -> bytes:
    """Return compact, sorted, ASCII JSON bytes with a trailing newline."""

    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return (text + "\n").encode("ascii")


def gzip_size(data: bytes) -> int:
    """Return the gzip size of ``data`` at level 9 with no timestamp (deterministic)."""

    return len(gzip.compress(data, compresslevel=9, mtime=0))


def read_merged(path: Path) -> list[dict[str, Any]]:
    """Read the merged grants Parquet as a list of records."""

    return pq.read_table(path).to_pylist()


def read_institutions(path: Path) -> list[dict[str, Any]]:
    """Read the institution columns needed for the type join."""

    if not path.exists():
        return []
    return pq.read_table(path, columns=list(INSTITUTION_COLUMNS)).to_pylist()


def check_dedupe_map(path: Path, grant_keys: Iterable[str]) -> int:
    """Confirm every exported key is a cluster representative; return map row count."""

    with path.open(newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))
    representatives = {
        record["grant_key"] for record in records if record["is_representative"] == "True"
    }
    missing = sorted(set(grant_keys) - representatives)
    if missing:
        raise ValueError(f"{len(missing)} exported grant_key values are not dedupe representatives")
    return len(records)


def build_from_paths(
    *,
    merged: Path,
    institutions: Path,
    dedupe_map: Path | None,
    output: Path,
    generated_at: str,
) -> dict[str, Any]:
    """Write ``output`` from the Parquet inputs and return a count-only summary."""

    rows = read_merged(merged)
    payload = build_payload(rows, read_institutions(institutions), generated_at=generated_at)
    map_rows = None
    if dedupe_map is not None and dedupe_map.exists():
        map_rows = check_dedupe_map(dedupe_map, [row["grant_key"] for row in payload["rows"]])
    data = serialize(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return {
        "output": str(output),
        "exported_rows": payload["counts"]["exported_rows"],
        "undated_rows": payload["counts"]["undated_rows"],
        "sources": {name: info["rows"] for name, info in payload["sources"].items()},
        "dedupe_map_rows": map_rows,
        "raw_bytes": len(data),
        "gzip_bytes": gzip_size(data),
    }
