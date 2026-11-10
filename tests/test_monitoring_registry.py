from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from atlas.ingest.monitoring.registry import (
    RegistryValidationError,
    load_registry,
    validate_registry,
)


def test_s7_1_seed_registry_has_at_least_15_verified_distinct_sources() -> None:
    registry = load_registry()
    eligible = [entry for entry in registry["datasets"] if entry["seed_eligible"]]
    assert len(eligible) >= 15
    assert len({entry["id"] for entry in eligible}) == len(eligible)
    assert len({entry["url"] for entry in eligible}) == len(eligible)
    assert len({entry["underlying_dataset_id"] for entry in eligible}) == len(eligible)
    # S7.1 seeds were checked 2026-11-07; later owner-supplied sources carry their own date.
    assert all(entry["last_checked"].isoformat() >= "2026-11-07" for entry in eligible)
    assert all(entry["provenance_url"].startswith("https://") for entry in eligible)
    assert all(entry["verification_url"].startswith("https://") for entry in eligible)
    assert all(entry["evidence_excerpt"] and entry["evidence_identity"] for entry in eligible)
    assert any(entry["provenance_type"] == "literature_secondary" for entry in eligible)


def test_registry_explicitly_excludes_unverified_or_context_only_candidates() -> None:
    registry = load_registry()
    excluded = {entry["id"] for entry in registry["datasets"] if not entry["seed_eligible"]}
    assert {
        "sf_bay_rmp_cd3_microplastics",
        "ceden_microdebris",
        "moore_drinking_water_open_data",
        "statewide_plastics_pilot",
        "swamp_spot_context",
        "california_coastal_cleanup_day",
        "ncei_sf_bay_bivalves_2018",
        "stormwater_collection_method_evaluation",
        "ocean_conservancy_tides_cleanswell",
    } <= excluded


def test_registry_rejects_missing_source_specific_fields() -> None:
    payload = yaml.safe_load(Path("config/datasets.yml").read_text(encoding="utf-8"))
    del payload["datasets"][0]["sample_matrix"]
    with pytest.raises(RegistryValidationError, match="sample_matrix"):
        validate_registry(payload)


def test_registry_rejects_duplicate_ids_and_insufficient_verified_seeds() -> None:
    payload = yaml.safe_load(Path("config/datasets.yml").read_text(encoding="utf-8"))
    duplicate = deepcopy(payload)
    duplicate["datasets"][1]["id"] = duplicate["datasets"][0]["id"]
    with pytest.raises(RegistryValidationError, match="unique"):
        validate_registry(duplicate)

    underfilled = deepcopy(payload)
    for entry in underfilled["datasets"]:
        entry["seed_eligible"] = False
    with pytest.raises(RegistryValidationError, match="verified seed entries"):
        validate_registry(underfilled)


def test_registry_rejects_two_seed_rows_for_the_same_underlying_dataset() -> None:
    payload = yaml.safe_load(Path("config/datasets.yml").read_text(encoding="utf-8"))
    eligible = [entry for entry in payload["datasets"] if entry["seed_eligible"]]
    eligible[1]["underlying_dataset_id"] = eligible[0]["underlying_dataset_id"]
    with pytest.raises(RegistryValidationError, match="distinct underlying datasets"):
        validate_registry(payload)


def test_ncei_accession_child_is_linked_but_not_counted_twice() -> None:
    registry = load_registry()
    by_id = {entry["id"]: entry for entry in registry["datasets"]}
    parent = by_id["noaa_ncei_marine_microplastics"]
    child = by_id["ncei_sf_bay_bivalves_2018"]
    assert parent["seed_eligible"]
    assert not child["seed_eligible"]
    assert child["underlying_dataset_id"] == parent["underlying_dataset_id"]


def test_registry_rejects_unknown_license_without_explanation() -> None:
    payload = yaml.safe_load(Path("config/datasets.yml").read_text(encoding="utf-8"))
    payload["datasets"][0]["license"] = "unknown"
    with pytest.raises(RegistryValidationError, match="explain unknown rights"):
        validate_registry(payload)
