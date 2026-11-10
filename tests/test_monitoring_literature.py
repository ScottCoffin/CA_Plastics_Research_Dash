from __future__ import annotations

import csv

from atlas.build.monitoring import (
    PRIVATE_SAMPLE_FIELDS,
    build_monitoring_payload,
    load_publication_clearances,
)
from atlas.ingest.monitoring.literature import (
    KARAPETROVA_2026_CSV,
    KARAPETROVA_2026_ID,
    load_curated_samples,
    load_karapetrova2026,
)
from atlas.ingest.monitoring.registry import load_registry


def test_sierra_snow_rows_match_si_table_s2_spot_values() -> None:
    rows = {row["sample_id"].split(":", 1)[1]: row for row in load_karapetrova2026()}
    assert len(rows) == 40
    assert rows["Pear Lake 1A"]["concentration_value"] == 24.4
    assert rows["Pear Lake 1A"]["deposition_rate_value"] == 1010
    assert rows["CUES Fresh Snow February C"]["deposition_rate_value"] == 9250
    assert rows["CUES Fresh Snow February C"]["date"] == "2024-02"
    assert rows["CUES Passive Sampler 4"]["concentration_value"] == 14.4
    assert rows["CUES Pit Layer 4C"]["deposition_rate_value"] is None
    assert rows["CUES Pit Layer 4C"]["deposition_rate_unit"] is None
    assert rows["Yost Meadow C"]["date"] == "2024"


def test_sierra_snow_sites_are_california_land_and_csv_is_complete() -> None:
    rows = load_karapetrova2026()
    assert all(row["in_ca_land"] is True and row["in_ca_state_waters"] is False for row in rows)
    with KARAPETROVA_2026_CSV.open(encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle))
    assert {record["site"] for record in records} == {
        "Earthquake Dome",
        "Yost Meadow",
        "TJ Lake",
        "Pear Lake 1",
        "Pear Lake 2",
        "Pear Lake 3",
        "CUES",
    }


def test_curated_rows_publish_only_display_fields_with_clearance() -> None:
    clearances = load_publication_clearances()
    assert KARAPETROVA_2026_ID in clearances
    rows = load_curated_samples()
    payload = build_monitoring_payload(load_registry(), samples=rows, clearances=clearances)
    assert payload["sample_count"] == 40
    assert all(set(row) <= set(PRIVATE_SAMPLE_FIELDS) for row in payload["samples"])
    dataset = next(d for d in payload["datasets"] if d["id"] == KARAPETROVA_2026_ID)
    assert dataset["measurement_status"] == "published_rights_cleared"
    assert "10.1021/acs.est.6c02757" in dataset["citation"]
