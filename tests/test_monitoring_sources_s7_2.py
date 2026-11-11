from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas.ingest.monitoring.sources import (
    map_sf_bay_sample,
    parse_csv_headers,
    read_bounded,
    tier_a_ready,
)


@pytest.mark.parametrize(
    ("code", "matrix"),
    [
        ("sw", "stormwater"),
        ("sed", "sediment"),
        ("eff", "wastewater effluent"),
        ("fish", "fish"),
        ("unknown", None),
    ],
)
def test_sf_bay_matrix_codes_follow_shared_map(code: str, matrix: str | None) -> None:
    fixture = json.loads(Path("tests/fixtures/monitoring/sf_bay_sample_ccby.json").read_text())
    sample = fixture["sheets"]["manta"]["row"]
    particle = dict(fixture["sheets"]["Particle Data"]["row"], SampleMatrix=code)
    mapped = map_sf_bay_sample(sample, particle, license_cleared=True)
    assert mapped["matrix"] == matrix
    assert mapped["matrix_source_code"] == code


def test_sf_bay_sample_maps_observed_fields_and_requires_cleared_license() -> None:
    fixture = json.loads(Path("tests/fixtures/monitoring/sf_bay_sample_ccby.json").read_text())
    sample_sheet = fixture["sheets"]["manta"]
    particle_sheet = fixture["sheets"]["Particle Data"]
    assert "SampleMatrix" not in sample_sheet["headers"]
    assert "Volume.L" not in particle_sheet["headers"]
    assert (
        fixture["workbook_sha256"]
        == "8fc7c636413e8030d9648d295c3263fe3dbf30a04c64c765e267cb71611d2684"
    )
    mapped = map_sf_bay_sample(sample_sheet["row"], particle_sheet["row"], license_cleared=True)
    assert mapped["sample_id"] == "CB4-Manta-16Nov2017"
    assert mapped["lat"] == pytest.approx(37.92291)
    assert mapped["lon"] == pytest.approx(-122.43303)
    assert mapped["matrix"] == "surface water"
    assert mapped["matrix_source_code"] == "manta"
    assert mapped["particle_count"] == 630
    assert mapped["sample_volume_l"] == pytest.approx(102764.135670286)
    assert mapped["concentration_value"] is None
    assert mapped["concentration_unit"] is None
    assert mapped["particle_length_mm"] == pytest.approx(2.427)
    assert mapped["particle_width_mm"] == pytest.approx(0.037)
    assert mapped["size_class"] is None
    assert mapped["mesh_um"] is None
    with pytest.raises(PermissionError, match="terms are not cleared"):
        map_sf_bay_sample(sample_sheet["row"], particle_sheet["row"], license_cleared=False)


def test_csv_parser_rejects_html_error_page() -> None:
    assert parse_csv_headers(b"SampleID,Latitude,Longitude\n") == [
        "SampleID",
        "Latitude",
        "Longitude",
    ]
    with pytest.raises(ValueError, match="not a CSV"):
        parse_csv_headers(b"<html><title>Access denied</title></html>")


def test_bounded_response_fails_when_payload_exceeds_cap() -> None:
    class Response:
        def iter_content(self, chunk_size: int):
            yield b"1234"

    with pytest.raises(ValueError, match="exceeds 3 byte limit"):
        read_bounded(Response(), limit=3)


def test_tier_a_requires_every_evidence_gate() -> None:
    assert tier_a_ready(
        machine_accessible=True,
        plastic_relevant=True,
        license_cleared=True,
        mapped_fields=True,
    )
    assert not tier_a_ready(
        machine_accessible=True,
        plastic_relevant=True,
        license_cleared=False,
        mapped_fields=True,
    )
