"""BQ-1.2: the failure taxonomy loads, is well formed and covers the classes the spec names."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_PATH = REPO_ROOT / "config" / "failure_taxonomy.yml"

REQUIRED_KEYS = (
    "id",
    "label",
    "direction",
    "definition",
    "examples",
    "source",
    "detection",
    "stage",
    "status",
)
DIRECTIONS = {"false_positive", "false_negative", "either", "not_an_error"}
STAGES = {"query", "labels", "abstract_qc", "pubmed_qc"}
STATUSES = {"seeded", "pending_bq_s9", "defined_bq_s9"}
SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
# Each ";"-separated source is REL-1 with a section, the A3 Module 1 or A3 §2 text, or a repo file.
SOURCE_PART = re.compile(r"^(?:REL-1 §\S.*|A3 Module 1|A3 §2|A3 §5\.11|repo: \S.*)$")
REPO_PATH = re.compile(r"\b(?:src|config|docs|curation|tests)/[\w./-]+")

SPEC_CLASS_IDS = {
    "plasticity_collision",
    "plastic_surgery",
    "plastic_responses",
    "litter_beetles",
    "upcycling_non_plastic",
    "withheld_abstract",
    "misattached_abstract",
    "non_english_text",
    "public_communication_item",
    "generic_theme_drift",
    "polysemous_framing_word",
    "abbreviation_collision",
    "incidental_plastics",
    "pubmed_only_record",
    "missing_abstract_in_openalex",
}


@pytest.fixture(scope="module")
def taxonomy() -> dict[str, Any]:
    with TAXONOMY_PATH.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    assert isinstance(data, dict)
    return data


@pytest.fixture(scope="module")
def classes(taxonomy: dict[str, Any]) -> list[dict[str, Any]]:
    return taxonomy["classes"]


def test_header_version_and_class_list(taxonomy: dict[str, Any]) -> None:
    assert taxonomy["version"] == "failure-taxonomy-v1"
    assert taxonomy["status"] == "draft"
    assert isinstance(taxonomy["classes"], list)
    assert taxonomy["classes"]


def test_ids_are_unique_and_snake_case(classes: list[dict[str, Any]]) -> None:
    ids = [entry.get("id") for entry in classes]
    assert all(isinstance(i, str) and SNAKE_CASE.match(i) for i in ids), ids
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicates, f"duplicate ids: {duplicates}"


def test_required_keys_and_text_fields(classes: list[dict[str, Any]]) -> None:
    for entry in classes:
        missing = [key for key in REQUIRED_KEYS if key not in entry]
        assert not missing, f"{entry.get('id')}: missing {missing}"
        for key in ("label", "definition", "detection"):
            assert isinstance(entry[key], str) and entry[key].strip(), (entry["id"], key)
        assert entry["definition"].endswith("."), entry["id"]


def test_direction_and_stage_values_are_valid(classes: list[dict[str, Any]]) -> None:
    for entry in classes:
        assert entry["direction"] in DIRECTIONS, entry["id"]
        assert entry["stage"] in STAGES, entry["id"]


def test_status_values_and_pending_placeholders(classes: list[dict[str, Any]]) -> None:
    for entry in classes:
        assert entry["status"] in STATUSES, entry["id"]
        if entry["status"] in {"pending_bq_s9", "defined_bq_s9"}:
            assert entry["stage"] == "pubmed_qc", entry["id"]


def test_every_class_has_examples_and_source(classes: list[dict[str, Any]]) -> None:
    for entry in classes:
        examples = entry["examples"]
        assert isinstance(examples, list) and examples, entry["id"]
        assert all(isinstance(e, str) and e.strip() for e in examples), entry["id"]
        assert isinstance(entry["source"], str) and entry["source"].strip(), entry["id"]


def test_sources_use_allowed_forms(classes: list[dict[str, Any]]) -> None:
    for entry in classes:
        parts = [part.strip() for part in entry["source"].split(";")]
        bad = [part for part in parts if not SOURCE_PART.match(part)]
        assert not bad, f"{entry['id']}: unrecognised source {bad}"


def test_cited_repo_paths_exist(classes: list[dict[str, Any]]) -> None:
    for entry in classes:
        text = f"{entry['source']} {entry['detection']}"
        for match in REPO_PATH.finditer(text):
            path = match.group(0).rstrip(".")
            assert (REPO_ROOT / path).exists(), f"{entry['id']} cites missing {path}"


def test_spec_required_classes_are_present(classes: list[dict[str, Any]]) -> None:
    ids = {entry["id"] for entry in classes}
    missing = sorted(SPEC_CLASS_IDS - ids)
    assert not missing, f"missing spec classes: {missing}"
