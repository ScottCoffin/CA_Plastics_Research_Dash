from __future__ import annotations

import json
from pathlib import Path

import pytest
from openpyxl import Workbook

from atlas.ingest.monitoring import sfbay, sources


def test_normalize_fixture_sample_preserves_source_and_units(monkeypatch) -> None:
    fixture = json.loads(Path("tests/fixtures/monitoring/sf_bay_sample_ccby.json").read_text())
    sample = fixture["sheets"]["manta"]["row"] | {"Count": 1, "Volume.L": 2.0}
    particle = fixture["sheets"]["Particle Data"]["row"]
    monkeypatch.setattr(sfbay, "in_ca", lambda *_args, **_kwargs: "state_waters")
    rows, particles, report = sfbay.normalize_rows(
        {"manta": [sample]}, [particle], source_sha256=fixture["workbook_sha256"]
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["sample_id"] == "CB4-Manta-16Nov2017"
    assert row["concentration_value"] == 0.5
    assert row["concentration_unit"] == "particles/L"
    assert row["sample_volume_l"] == 2
    assert row["particle_count"] == 1
    assert particles[0]["length_mm"] == 2.427
    assert particles[0]["width_mm"] == 0.037
    assert row["size_class"] is None and row["mesh_um"] is None
    assert row["plastic_confirmed"] is True
    assert row["in_ca_state_waters"] is True
    assert report["qc"]["samples_emitted"] == 1
    assert "particle_detail_count_mismatch" not in report["qc"]


def test_invalid_denominator_and_ambiguous_matrix_are_qc_not_values() -> None:
    sample = {"SampleID": "S1", "Count": 2, "Volume.L": 2}
    particle = {"SampleID": "S1", "SampleMatrix": "unknown", "PlasticType": "microparticle"}
    rows, _, report = sfbay.normalize_rows({"other": [sample]}, [particle], source_sha256="abc")
    assert rows[0]["concentration_value"] is None
    assert rows[0]["concentration_unit"] is None
    assert rows[0]["matrix"] is None
    assert rows[0]["plastic_confirmed"] is None
    assert "invalid_or_missing_volume_l" not in report["qc"]
    assert report["qc"]["concentration_uncomputed"] == 1
    assert report["qc"]["unknown_or_conflicting_matrix_code"] == 1
    assert rows[0]["in_ca_land"] is None

    sample["Volume.L"] = 0
    particle["SampleMatrix"] = "manta"
    rows, _, report = sfbay.normalize_rows({"manta": [sample]}, [particle], source_sha256="abc")
    assert rows[0]["concentration_value"] is None
    assert rows[0]["concentration_unit"] is None
    assert report["qc"]["selected_unique_invalid_or_missing_volume_l"] == 1


EXPECTED_MATRIX = {
    "manta": "surface water",
    "sw": "stormwater",
    "sed": "sediment",
    "eff": "wastewater effluent",
    "fish": "fish",
}


@pytest.mark.parametrize("code", sorted(EXPECTED_MATRIX))
def test_matrix_codes_map_only_when_code_equals_sheet(code: str) -> None:
    assert sfbay.MATRIX_MAP == EXPECTED_MATRIX
    assert sfbay.MATRIX_MAP is sources.SF_BAY_MATRIX_MAP
    sample = {"SampleID": "S1", "Count": 1, "Volume.L": 2.0}
    particle = {"SampleID": "S1", "SampleMatrix": code, "PlasticType": "Polyethylene"}
    rows, _, report = sfbay.normalize_rows({code: [sample]}, [particle], source_sha256="abc")
    assert rows[0]["matrix"] == EXPECTED_MATRIX[code]
    assert "unknown_or_conflicting_matrix_code" not in report["qc"]
    # Concentration stays limited to the surface-water manta trawl.
    expected_concentration = 0.5 if code == "manta" else None
    assert rows[0]["concentration_value"] == expected_concentration

    other = "fish" if code != "fish" else "sed"
    rows, _, report = sfbay.normalize_rows({other: [sample]}, [particle], source_sha256="abc")
    assert rows[0]["matrix"] is None
    assert report["qc"]["unknown_or_conflicting_matrix_code"] == 1


def test_particle_level_confirmation_aggregate_and_matrix_conflict() -> None:
    sample = {"SampleID": "S1", "Count": 2, "Volume.L": 4, "SampleDate": "not a date"}
    particles = [
        {"SampleID": "S1", "SampleMatrix": "sed", "PlasticType": "Polyethylene"},
        {"SampleID": "S1", "SampleMatrix": "sed", "PlasticType": "Not Characterized"},
    ]
    rows, particle_rows, report = sfbay.normalize_rows(
        {"manta": [sample]}, particles, source_sha256="abc"
    )
    assert rows[0]["matrix"] is None
    assert rows[0]["concentration_value"] is None
    assert rows[0]["plastic_confirmed"] is True
    assert rows[0]["confirmed_polymer_particle_count"] == 1
    assert rows[0]["unclassified_particle_count"] == 1
    assert len(particle_rows) == 2
    assert report["qc"]["unknown_or_conflicting_matrix_code"] == 1
    assert report["qc"]["invalid_sample_date"] == 1


def test_concentration_overflow_is_uncomputed() -> None:
    assert sfbay._safe_concentration(1e308, 1e-308) is None


def test_conflicting_duplicate_suppresses_count_and_concentration() -> None:
    first = {
        "SampleID": "DUP",
        "Count": 14,
        "Volume.L": 100.0,
        "CollectionDeviceName": "Manta trawl",
    }
    second = {
        "SampleID": "DUP",
        "Count": 0,
        "Volume.L": 0,
        "CollectionDeviceName": "Unknown device",
    }
    other_invalid = {"SampleID": "S2", "Count": 0, "Volume.L": 0}
    particles = [
        {"SampleID": "DUP", "SampleMatrix": "manta", "PlasticType": "Polyethylene"}
        for _ in range(14)
    ]
    rows, _, report = sfbay.normalize_rows(
        {"manta": [first, second, other_invalid]}, particles, source_sha256="abc"
    )
    duplicate = next(row for row in rows if row["sample_id"] == "DUP")
    assert duplicate["particle_count"] is None
    assert duplicate["particle_detail_rows"] == 14
    assert duplicate["particle_count_source"] is None
    assert duplicate["particle_count_source_chosen_raw"] == 14
    assert duplicate["particle_count_source_conflict"] is True
    assert duplicate["sample_volume_l"] is None
    assert duplicate["sample_volume_l_chosen_raw"] == 100.0
    assert duplicate["sample_volume_l_source_conflict"] is True
    assert duplicate["concentration_value"] is None
    assert duplicate["method"] is None
    assert duplicate["method_source_conflict"] is True
    assert report["qc"]["raw_rows_invalid_or_missing_volume_l"] == 2
    assert report["qc"]["selected_unique_invalid_or_missing_volume_l"] == 1
    conflict = report["qc"]["duplicate_sample_id_conflict_details"][0]
    assert conflict["conflicting_fields"]["Count"] == [14, 0]
    assert conflict["conflicting_fields"]["Volume.L"] == [100.0, 0]
    assert [row["row"] for row in conflict["source_rows"]] == [2, 3]


def test_ingest_small_workbook_preserves_duplicate_headers_and_writes_outputs(tmp_path) -> None:
    workbook_path = tmp_path / "small.xlsx"
    workbook = Workbook()
    particle_sheet = workbook.active
    particle_sheet.title = "Particle Data"
    particle_sheet.append(
        [
            "SampleMatrix",
            "SampleID",
            "PlasticType",
            "MorphologicalCategory",
            "Length.mm",
            "Width.mm",
        ]
    )
    particle_sheet.append(["manta", "S1", "Polyethylene", "fiber", 2.0, 0.2])
    particle_sheet.append(["manta", "S1", "Not Characterized", "fragment", 1.0, 0.3])
    for name in ("manta", "sed", "eff", "sw", "fish"):
        sheet = workbook.create_sheet(name)
        if name == "fish":
            sheet.append(["SampleID", "Count", "SampleID"])
            sheet.append(["F1", 3, None])
        elif name == "manta":
            sheet.append(
                ["SampleID", "SampleDate", "Count", "Volume.L", "ActualLatitude", "ActualLongitude"]
            )
            sheet.append(["S1", "2020-01-02", 2, 4.0, 37.9, -122.4])
        else:
            sheet.append(["SampleID"])
    workbook.save(workbook_path)

    report = sfbay.ingest_workbook(
        workbook_path, output_dir=tmp_path / "normalized", allow_hash_change=True
    )
    samples = json.loads((tmp_path / "normalized" / "samples.json").read_text())
    particles = json.loads((tmp_path / "normalized" / "particles.json").read_text())
    assert report["source_sha256"]
    assert len(samples) == 2
    manta = next(sample for sample in samples if sample["sample_id"] == "S1")
    fish = next(sample for sample in samples if sample["sample_id"] == "F1")
    assert manta["concentration_value"] == 0.5
    assert manta["plastic_confirmed"] is True
    assert manta["confirmed_polymer_particle_count"] == 1
    assert fish["source_sheet"] == "fish"
    assert len(particles) == 2
    samples_bytes = (tmp_path / "normalized" / "samples.json").read_bytes()
    particles_bytes = (tmp_path / "normalized" / "particles.json").read_bytes()
    report_second = sfbay.ingest_workbook(
        workbook_path, output_dir=tmp_path / "normalized", allow_hash_change=True
    )
    assert report_second == report
    assert (tmp_path / "normalized" / "samples.json").read_bytes() == samples_bytes
    assert (tmp_path / "normalized" / "particles.json").read_bytes() == particles_bytes
