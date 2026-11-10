"""Curated monitoring values transcribed from published tables (literature-derived rows).

Each dataset is a committed CSV under ``curation/monitoring/`` whose values were
checked against the source PDF (rendered page and text layer). Rows map onto the
S7.5 display schema; nothing here is fetched from the network.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from atlas.geo.ca_polygons import in_ca

KARAPETROVA_2026_ID = "karapetrova2026_sierra_snow"
KARAPETROVA_2026_CSV = Path("curation/monitoring/karapetrova2026_sierra_snow.csv")
KARAPETROVA_2026_CITATION = (
    "Karapetrova A, Cowger W, Brahney J, et al. Event-Scale Deposition of Atmospheric "
    "Microplastics in Snowfall of the Sierra Nevada in North America. Environ. Sci. "
    "Technol. 2026. doi:10.1021/acs.est.6c02757 (Supporting Information Tables S1-S2)"
)
_MATRIX = {
    "fresh snow": "snow (fresh snowfall)",
    "snow pit layer": "snow (snowpack pit layer)",
    "dry deposition, passive sampler": "atmospheric deposition (dry, passive sampler)",
}


def _number(value: str) -> float | None:
    text = (value or "").strip()
    return float(text) if text else None


def load_karapetrova2026(path: Path = KARAPETROVA_2026_CSV) -> list[dict[str, Any]]:
    """Return display rows for the Sierra Nevada snow and deposition samples.

    ``date`` is the sampling month when the SI names it (CUES fresh snow) and
    otherwise the year: the SI states only that sampling ran January-July 2024.
    """
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            lat, lon = float(record["lat"]), float(record["lon"])
            sample_type = record["sample_type"]
            if sample_type not in _MATRIX:
                raise ValueError(f"unknown sample_type {sample_type!r} in {path}")
            location = in_ca(lat, lon)
            deposition = _number(record["deposition_p_per_m2_day"])
            rows.append(
                {
                    "sample_id": f"{KARAPETROVA_2026_ID}:{record['sample_name']}",
                    "dataset_id": KARAPETROVA_2026_ID,
                    "lat": lat,
                    "lon": lon,
                    "date": record["sample_month"] or "2024",
                    "matrix": _MATRIX[sample_type],
                    "method": f"{sample_type}; site {record['site']} "
                    f"({record['elevation_m']} m elevation)",
                    "concentration_value": _number(record["concentration_p_per_L"]),
                    "concentration_unit": "particles/L",
                    "deposition_rate_value": deposition,
                    "deposition_rate_unit": "particles/m2/day" if deposition is not None else None,
                    "particle_count": None,
                    "in_ca_land": location == "land",
                    "in_ca_state_waters": location == "state_waters",
                    "contributor": "University of California, Riverside (lead author)",
                    "contributor_in_ca": True,
                    "citation": KARAPETROVA_2026_CITATION,
                }
            )
    return rows


CURATED_LOADERS = {KARAPETROVA_2026_ID: load_karapetrova2026}


def load_curated_samples() -> list[dict[str, Any]]:
    """All committed literature-derived rows, in a stable order."""
    return [row for loader in CURATED_LOADERS.values() for row in loader()]
