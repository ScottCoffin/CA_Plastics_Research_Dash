"""Small, bounded source probes and conservative Tier-A readiness checks."""

from __future__ import annotations

import csv
import io
from typing import Any

MAX_REQUESTS = 50
MAX_BYTES_PER_FILE = 10_000_000
# Source-specific codes observed in `Particle Data` (and the matching sample sheet
# names). The SFEI / 5 Gyres study uses: manta = surface-water manta trawl, sw =
# stormwater runoff, sed = sediment, eff = wastewater effluent, fish = fish (gut
# contents). Shared by sfbay.py; a code is only mapped when it equals its sheet.
SF_BAY_MATRIX_MAP = {
    "manta": "surface water",
    "sw": "stormwater",
    "sed": "sediment",
    "eff": "wastewater effluent",
    "fish": "fish",
}


def read_bounded(response: Any, *, limit: int = MAX_BYTES_PER_FILE) -> bytes:
    """Read a streaming response without exceeding the documented per-file cap."""
    chunks = bytearray()
    iterator = (
        response.iter_content(chunk_size=64 * 1024)
        if hasattr(response, "iter_content")
        else iter(lambda: response.read(64 * 1024), b"")
    )
    for chunk in iterator:
        chunks.extend(chunk)
        if len(chunks) > limit:
            raise ValueError(f"response exceeds {limit} byte limit")
    return bytes(chunks)


def map_sf_bay_sample(
    sample_row: dict[str, Any],
    particle_row: dict[str, Any],
    *,
    license_cleared: bool,
) -> dict[str, Any]:
    """Map observed SF Bay source facts without inventing canonical values."""
    if not license_cleared:
        raise PermissionError("source reuse terms are not cleared")
    date = sample_row.get("SampleDate")
    return {
        "sample_id": sample_row.get("SampleID"),
        "dataset_id": "sf_bay_5gyres_microplastics",
        "lat": sample_row.get("ActualLatitude", sample_row.get("Latitude")),
        "lon": sample_row.get("ActualLongitude", sample_row.get("Longitude")),
        "date": date.isoformat() if hasattr(date, "isoformat") else date,
        "matrix": SF_BAY_MATRIX_MAP.get(particle_row.get("SampleMatrix")),
        "matrix_source_code": particle_row.get("SampleMatrix"),
        "particle_count": sample_row.get("Count"),
        "sample_volume_l": sample_row.get("Volume.L"),
        "concentration_value": None,
        "concentration_unit": None,
        "particle_length_mm": particle_row.get("Length.mm"),
        "particle_width_mm": particle_row.get("Width.mm"),
        "size_class": None,
        "mesh_um": None,
        "plastic_type": particle_row.get("PlasticType"),
        "morphology": particle_row.get("MorphologicalCategory"),
        "method": sample_row.get("CollectionDeviceName"),
        "citation": "SFEI and 5 Gyres, SF Bay Microplastics Project (CC BY 4.0)",
    }


def parse_csv_headers(payload: bytes) -> list[str]:
    """Parse actual CSV headers, rejecting HTML/error pages masquerading as data."""
    text = payload.decode("utf-8-sig")
    headers = next(csv.reader(io.StringIO(text)), [])
    if not headers or "<html" in text[:500].casefold():
        raise ValueError("response is not a CSV data file")
    return headers


def tier_a_ready(
    *, machine_accessible: bool, plastic_relevant: bool, license_cleared: bool, mapped_fields: bool
) -> bool:
    """Tier A requires all four independently evidenced readiness conditions."""
    return all((machine_accessible, plastic_relevant, license_cleared, mapped_fields))
