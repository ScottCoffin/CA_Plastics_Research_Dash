"""Conservative normalization of the cleared SF Bay / 5 Gyres workbook."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from atlas.geo.ca_polygons import in_ca

DATASET_ID = "sf_bay_5gyres_microplastics"
EXPECTED_SHA256 = "8fc7c636413e8030d9648d295c3263fe3dbf30a04c64c765e267cb71611d2684"
SOURCE_URL = (
    "https://data.cnra.ca.gov/dataset/78ac95ac-9665-4e53-aea6-ad0762055cce/"
    "resource/4e6aaf6f-7055-484b-84f4-3a66df294f27/download/"
    "2020-09-11_microparticledata.xlsx"
)
LICENSE_EVIDENCE = {
    "name": "Open Data Commons Attribution License",
    "url": "http://www.opendefinition.org/licenses/odc-by",
    "scope": "package metadata; resource-level license field is empty",
    "status": "observed in current official CKAN metadata; differs from S7.2 CC BY 4.0 note",
}
# Owner determination 2026-11-10 (QUESTIONS S7.3-A). The observed package metadata
# (ODC BY) stays in LICENSE_EVIDENCE; both are attribution licenses.
PUBLICATION_LICENSE = {
    "id": "CC-BY-4.0",
    "name": "Creative Commons Attribution 4.0 International",
    "url": "https://creativecommons.org/licenses/by/4.0/",
    "basis": "owner determination 2026-11-10 (QUESTIONS S7.3-A)",
}
ATTRIBUTION = (
    "San Francisco Estuary Institute and 5 Gyres Institute, SF Bay and Adjacent "
    "Sanctuaries Microplastic and Microparticle Project (published by OPC on the "
    "California Natural Resources Agency Open Data portal); CC BY 4.0"
)
MATRIX_MAP = {"manta": "surface water"}
POLYMER_RE = re.compile(
    r"\bpoly(?:ethylene|propylene|ester|amide|styrene|vinyl|urethane|acrylic)\b",
    re.IGNORECASE,
)
NEGATIVE_PLASTIC_LABELS = ("no plastic", "not plastic", "no polymer identified")


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _safe_concentration(count: float | None, volume_l: float | None) -> float | None:
    if count is None or count < 0 or volume_l is None or volume_l <= 0:
        return None
    result = count / volume_l
    return result if math.isfinite(result) else None


def classify_plastic(value: Any) -> bool | None:
    """Classify only explicit negative labels and recognized polymer names."""
    if not isinstance(value, str):
        return None
    label = value.strip().casefold()
    if any(marker in label for marker in NEGATIVE_PLASTIC_LABELS):
        return False
    if POLYMER_RE.search(label):
        return True
    return None


def _iso_date(value: Any) -> str | None:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            try:
                return datetime.fromisoformat(text).isoformat()
            except ValueError:
                return None
    return None


def normalize_rows(
    sample_sheets: dict[str, list[dict[str, Any]]],
    particle_rows: list[dict[str, Any]],
    *,
    source_sha256: str,
    land_path: str | Path | None = None,
    state_waters_path: str | Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Return sample rows, particle rows, and source-level QC."""
    particle_by_id: dict[str, list[dict[str, Any]]] = {}
    qc: Counter[str] = Counter()
    particle_records: list[dict[str, Any]] = []
    source_matrix_counts: Counter[str] = Counter()
    for row in particle_rows:
        key = str(row.get("SampleID") or "").strip()
        if not key:
            qc["particle_rows_missing_sample_id"] += 1
            continue
        particle_by_id.setdefault(key, []).append(row)
        code = str(row.get("SampleMatrix") or "").strip().casefold()
        source_matrix_counts[code or "<missing>"] += 1
        plastic_type = row.get("PlasticType")
        particle_records.append(
            {
                "sample_id": key,
                "dataset_id": DATASET_ID,
                "source_sha256": source_sha256,
                "source_url": SOURCE_URL,
                "source_matrix_code": row.get("SampleMatrix"),
                "length_mm": _number(row.get("Length.mm")),
                "width_mm": _number(row.get("Width.mm")),
                "plastic_type_source": plastic_type,
                "plastic_confirmed": classify_plastic(plastic_type),
                "morphology": row.get("MorphologicalCategory"),
                "color": row.get("Color"),
                "citation": ATTRIBUTION,
                "license": PUBLICATION_LICENSE,
                "license_evidence": LICENSE_EVIDENCE,
            }
        )

    entries_by_id: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    raw_sample_rows = 0
    for sheet, rows in sample_sheets.items():
        for ordinal, sample in enumerate(rows, start=2):
            raw_sample_rows += 1
            sid = str(sample.get("SampleID") or "").strip()
            if not sid:
                qc["samples_missing_id"] += 1
                continue
            sample.setdefault("_source_sheet_row", ordinal)
            entries_by_id.setdefault(sid, []).append((sheet, sample))
            raw_volume = _number(sample.get("Volume.L"))
            if "Volume.L" in sample and (raw_volume is None or raw_volume <= 0):
                qc["raw_rows_invalid_or_missing_volume_l"] += 1

    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    coordinate_counts: Counter[str] = Counter()
    duplicate_conflicts: list[dict[str, Any]] = []
    conflict_fields = (
        "Count",
        "Volume.L",
        "CollectionDeviceName",
        "SampleDate",
        "ActualLatitude",
        "ActualLongitude",
        "Latitude",
        "Longitude",
    )
    for sid, source_entries in entries_by_id.items():
        sheet, sample = source_entries[0]
        seen.add(sid)
        row_sources = [
            {
                "sheet": source_sheet,
                "row": source_row.get("_source_sheet_row"),
                "Count": source_row.get("Count"),
                "Volume.L": source_row.get("Volume.L"),
                "CollectionDeviceName": source_row.get("CollectionDeviceName"),
            }
            for source_sheet, source_row in source_entries
        ]
        field_conflicts = {}
        for field in conflict_fields:
            values = [entry.get(field) for _, entry in source_entries]
            normalized_values = [
                value.isoformat() if hasattr(value, "isoformat") else value for value in values
            ]
            distinct = {
                json.dumps(value, sort_keys=True, default=str) for value in normalized_values
            }
            if len(distinct) > 1:
                field_conflicts[field] = normalized_values
        if len(source_entries) > 1:
            qc["duplicate_sample_ids"] += 1
        if field_conflicts:
            qc["duplicate_sample_id_conflicts"] += 1
            duplicate_conflicts.append(
                {
                    "sample_id": sid,
                    "source_rows": row_sources,
                    "conflicting_fields": field_conflicts,
                    "disposition": (
                        "retain one sample; suppress conflicting canonical fields; "
                        "retain selected raw values and source-row evidence"
                    ),
                }
            )
        count_conflict = "Count" in field_conflicts
        volume_conflict = "Volume.L" in field_conflicts
        method_conflict = "CollectionDeviceName" in field_conflicts
        details = particle_by_id.get(sid, [])
        if not details:
            qc["samples_without_particle_rows"] += 1
        codes = {str(item.get("SampleMatrix") or "").strip().casefold() for item in details}
        code = next(iter(codes)) if len(codes) == 1 else ""
        matrix = MATRIX_MAP.get(code) if code == sheet.casefold() else None
        if len(codes) > 1 or (details and (not matrix or code != sheet.casefold())):
            qc["unknown_or_conflicting_matrix_code"] += 1
            qc[f"unmapped_matrix_sample_{code or 'missing'}"] += 1

        source_count_chosen = sample.get("Count")
        source_count = None if count_conflict else _number(source_count_chosen)
        detail_count = len(details)
        if "Count" in sample and not count_conflict and (source_count is None or source_count < 0):
            qc["invalid_particle_count"] += 1
        count_matches = source_count is not None and source_count == detail_count
        if source_count is not None and not count_matches:
            qc["particle_detail_count_mismatch"] += 1
        source_volume_chosen = sample.get("Volume.L")
        volume = None if volume_conflict else _number(source_volume_chosen)
        if "Volume.L" in sample and not volume_conflict and (volume is None or volume <= 0):
            qc["selected_unique_invalid_or_missing_volume_l"] += 1
        concentration = (
            _safe_concentration(source_count, volume)
            if matrix == "surface water" and count_matches
            else None
        )
        if concentration is None:
            qc["concentration_uncomputed"] += 1
        else:
            qc["concentration_computed"] += 1
        if matrix == "surface water" and source_count is not None and volume and volume > 0:
            if _safe_concentration(source_count, volume) is None:
                qc["concentration_overflow"] += 1

        raw_date = sample.get("SampleDate")
        if "SampleDate" in field_conflicts:
            raw_date = None
        iso_date = _iso_date(raw_date)
        if raw_date not in (None, "") and iso_date is None:
            qc["invalid_sample_date"] += 1
        elif iso_date is None:
            qc["missing_sample_date"] += 1

        lat = _number(sample.get("ActualLatitude"))
        lon = _number(sample.get("ActualLongitude"))
        if "ActualLatitude" in field_conflicts or "Latitude" in field_conflicts:
            lat = None
        if "ActualLongitude" in field_conflicts or "Longitude" in field_conflicts:
            lon = None
        if lat is None:
            lat = _number(sample.get("Latitude"))
        if lon is None:
            lon = _number(sample.get("Longitude"))
        location = None
        if lat is not None and lon is not None:
            try:
                kwargs = {}
                if land_path is not None:
                    kwargs["land_path"] = land_path
                if state_waters_path is not None:
                    kwargs["state_waters_path"] = state_waters_path
                location = in_ca(lat, lon, **kwargs)
                coordinate_counts[location] += 1
            except (ValueError, OSError, FileNotFoundError):
                qc["polygon_classification_failed"] += 1
        else:
            qc["missing_or_invalid_coordinates"] += 1

        particle_labels = [classify_plastic(row.get("PlasticType")) for row in details]
        confirmed_count = sum(label is True for label in particle_labels)
        negative_count = sum(label is False for label in particle_labels)
        unknown_count = sum(label is None for label in particle_labels)
        if confirmed_count:
            sample_plastic = True  # at least one particle has a named polymer
            plastic_basis = "one_or_more_named_polymer"
        elif details and negative_count == len(details):
            sample_plastic = False
            plastic_basis = "all_particle_records_explicitly_negative"
        else:
            sample_plastic = None
            plastic_basis = "ambiguous_or_no_particle_records"

        output.append(
            {
                "sample_id": sid,
                "dataset_id": DATASET_ID,
                "source_sha256": source_sha256,
                "source_url": SOURCE_URL,
                "license": PUBLICATION_LICENSE,
                "license_evidence": LICENSE_EVIDENCE,
                "source_sheet": sheet,
                "lat": lat,
                "lon": lon,
                "date": iso_date,
                "matrix": matrix,
                "matrix_source_code": code or None,
                "particle_count": None if count_conflict else detail_count,
                "particle_count_source": source_count,
                "particle_count_source_chosen_raw": source_count_chosen,
                "particle_count_source_conflict": count_conflict,
                "sample_volume_l": volume,
                "sample_volume_l_chosen_raw": source_volume_chosen,
                "sample_volume_l_source_conflict": volume_conflict,
                "method_source_conflict": method_conflict,
                "method_source_chosen_raw": sample.get("CollectionDeviceName"),
                "source_conflict_fields": sorted(field_conflicts),
                "source_row_provenance": row_sources,
                "concentration_value": concentration,
                "concentration_unit": "particles/L" if concentration is not None else None,
                "size_class": None,
                "method": None if method_conflict else sample.get("CollectionDeviceName"),
                "mesh_um": None,
                "plastic_confirmed": sample_plastic,
                "plastic_confirmation_basis": plastic_basis,
                "confirmed_polymer_particle_count": confirmed_count,
                "explicit_negative_particle_count": negative_count,
                "unclassified_particle_count": unknown_count,
                "particle_detail_rows": detail_count,
                "in_ca_land": location == "land" if location is not None else None,
                "in_ca_state_waters": location == "state_waters" if location is not None else None,
                "contributor": "San Francisco Estuary Institute and 5 Gyres Institute",
                "citation": ATTRIBUTION,
            }
        )

    qc["samples_emitted"] = len(output)
    qc["samples_seen"] = len(seen)
    qc["sample_source_rows_nonblank"] = raw_sample_rows
    qc["duplicate_sample_id_conflict_details"] = duplicate_conflicts
    qc["particle_rows"] = len(particle_rows)
    qc["particle_records_emitted"] = len(particle_records)
    qc["particle_matrix_codes"] = dict(sorted(source_matrix_counts.items()))
    qc["orphan_particle_rows"] = sum(
        len(rows) for sample_id, rows in particle_by_id.items() if sample_id not in seen
    )
    qc["polygon_locations"] = dict(sorted(coordinate_counts.items()))
    qc["sample_sheet_rows"] = {name: len(rows) for name, rows in sample_sheets.items()}
    qc["unit_semantics"] = {
        "manta_volume": "Volume.L",
        "particle_length": "Length.mm",
        "particle_width": "Width.mm",
        "unmapped_denominators": ["Mass.g", "Flow.MLD", "fish tissue/organism basis"],
        "size_class": "unknown",
        "mesh_um": "unknown",
    }
    return (
        output,
        particle_records,
        {
            "dataset_id": DATASET_ID,
            "source_sha256": source_sha256,
            "source_url": SOURCE_URL,
            "license": PUBLICATION_LICENSE,
            "license_evidence": LICENSE_EVIDENCE,
            "citation": ATTRIBUTION,
            "qc": dict(sorted(qc.items())),
        },
    )


def _record_from_row(
    headers: list[Any], values: tuple[Any, ...], *, source_row_number: int
) -> dict[str, Any]:
    """Preserve duplicate source headers by suffixing later occurrences."""
    counts: Counter[str] = Counter()
    record = {}
    for raw_header, value in zip(headers, values, strict=False):
        header = str(raw_header) if raw_header is not None else ""
        counts[header] += 1
        key = header if counts[header] == 1 else f"{header}__{counts[header]}"
        record[key] = value
    record["_source_sheet_row"] = source_row_number
    return record


def ingest_workbook(
    path: str | Path, *, output_dir: str | Path, allow_hash_change: bool = False
) -> dict[str, Any]:
    """Read the pinned workbook and write local normalized JSON/QC outputs."""
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256 and not allow_hash_change:
        raise ValueError(f"workbook SHA-256 changed: {digest}; inspect schema before ingest")
    workbook = load_workbook(path, read_only=True, data_only=True)
    if "Particle Data" not in workbook.sheetnames:
        raise ValueError("workbook lacks required 'Particle Data' sheet")
    sample_sheet_names = [name for name in workbook.sheetnames if name != "Particle Data"]
    if len(sample_sheet_names) != 5:
        raise ValueError(
            f"expected five sample sheets plus Particle Data; found {workbook.sheetnames}"
        )
    sheets: dict[str, list[dict[str, Any]]] = {}
    for name in sample_sheet_names:
        iterator = workbook[name].iter_rows(values_only=True)
        headers = list(next(iterator))
        if "SampleID" not in headers:
            workbook.close()
            raise ValueError(f"sample sheet {name!r} lacks SampleID")
        sheets[name] = [
            _record_from_row(headers, row, source_row_number=row_number)
            for row_number, row in enumerate(iterator, start=2)
            if any(v is not None for v in row)
        ]
    iterator = workbook["Particle Data"].iter_rows(values_only=True)
    headers = list(next(iterator))
    if not {"SampleID", "SampleMatrix"}.issubset(headers):
        workbook.close()
        raise ValueError("Particle Data sheet lacks SampleID or SampleMatrix")
    particles = [
        _record_from_row(headers, row, source_row_number=row_number)
        for row_number, row in enumerate(iterator, start=2)
        if any(v is not None for v in row)
    ]
    workbook.close()
    samples, particle_records, report = normalize_rows(sheets, particles, source_sha256=digest)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("samples.json", samples),
        ("particles.json", particle_records),
        ("qc.json", report),
    ):
        (out / name).write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return report
