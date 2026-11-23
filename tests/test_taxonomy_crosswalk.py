"""BQ-S5: the taxonomy crosswalk and owner proposal are well formed and nothing ships.

Offline and read-only: reads config/taxonomy_crosswalk.yml, config/taxonomy.yml and
docs/TAXONOMY_PROPOSAL.md. No code path reads the crosswalk.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CROSSWALK_PATH = REPO_ROOT / "config" / "taxonomy_crosswalk.yml"
TAXONOMY_PATH = REPO_ROOT / "config" / "taxonomy.yml"
PROPOSAL_PATH = REPO_ROOT / "docs" / "TAXONOMY_PROPOSAL.md"

TOP_LEVEL_KEYS = (
    "version",
    "status",
    "approval",
    "owner_summary",
    "spec_sections",
    "guide",
    "scheme_crosswalk",
    "entries",
)
ENTRY_KEYS = (
    "id",
    "kind",
    "item",
    "current_location",
    "proposed_action",
    "maps_to",
    "source",
    "notes",
    "reporting",
    "decision",
)
KINDS = {"topic_tag", "tier", "facet", "facet_value", "field"}
ACTIONS = {"keep", "rename", "merge_into", "split", "add", "add_experimental", "defer"}
REPORTING = {"in_P1_P6", "excluded_from_P1_P6", "not_applicable"}
DECISION_ITEMS = {f"D{number}" for number in range(1, 11)}

# A3 §5.4 candidate topic tags (lifecycle and society), plus the waste-trade sub-topic.
A3_LIFECYCLE_TOPICS = {
    "lca_and_sustainability",
    "waste_management_and_recycling",
    "waste_trade_and_global_flows",
    "policy_law_and_governance",
    "behaviour_and_perception",
    "justice_colonialism_and_power",
    "litter_and_trash",
    "bioplastics_and_alternatives",
    "safe_and_sustainable_by_design",
    "culture_media_and_discourse",
}
# A3 §5.4 item 2 and guide_v3 §6, including the A3-D20 additions.
LENS_VALUES = {
    "waste_colonialism",
    "environmental_justice_and_racism",
    "indigenous_and_community_governance",
    "community_and_participatory_methods",
    "labour_and_informal_economy",
    "circularity_critique_and_greenwashing",
    "political_economy_centre_periphery",
    "responsibility_shifting",
}
CENTRALITY_VALUES = {"primary", "substantial", "incidental", "none", "not_assessed"}
SCHEME_COUNT = 12  # A3 §5.6 table rows


def _load_crosswalk() -> dict[str, Any]:
    data = yaml.safe_load(CROSSWALK_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "crosswalk must be a mapping"
    return data


def _taxonomy_domain_ids() -> list[str]:
    data = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
    return [entry["id"] for entry in data["domain_tags"]]


def _proposal_rows() -> list[list[str]]:
    rows = []
    for line in PROPOSAL_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("| D"):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def test_top_level_keys_and_status() -> None:
    data = _load_crosswalk()
    for key in TOP_LEVEL_KEYS:
        assert key in data, f"missing top-level key {key}"
    assert data["version"] == "taxonomy-crosswalk-v1"
    assert data["status"] == "proposal"
    assert data["approval"] == "A3-D7"
    assert len(data["scheme_crosswalk"]) == SCHEME_COUNT
    for row in data["scheme_crosswalk"]:
        assert isinstance(row["scheme"], str) and row["scheme"]
        assert isinstance(row["atlas_targets"], list) and row["atlas_targets"]


def test_entries_have_required_keys_and_valid_enums() -> None:
    entries = _load_crosswalk()["entries"]
    assert entries, "crosswalk has no entries"
    for entry in entries:
        for key in ENTRY_KEYS:
            assert key in entry, f"{entry.get('id')} is missing {key}"
        assert entry["kind"] in KINDS, f"{entry['id']}: bad kind {entry['kind']}"
        assert entry["proposed_action"] in ACTIONS, f"{entry['id']}: bad action"
        assert entry["reporting"] in REPORTING, f"{entry['id']}: bad reporting"
        assert entry["item"] in DECISION_ITEMS, f"{entry['id']}: bad item {entry['item']}"
        assert isinstance(entry["current_location"], list), entry["id"]
        assert isinstance(entry["maps_to"], list), entry["id"]
        assert isinstance(entry["source"], str) and entry["source"], entry["id"]
        assert isinstance(entry["notes"], str) and entry["notes"], entry["id"]


def test_ids_are_unique_and_every_decision_is_pending() -> None:
    entries = _load_crosswalk()["entries"]
    ids = [entry["id"] for entry in entries]
    assert len(ids) == len(set(ids)), "duplicate crosswalk ids"
    assert {entry["decision"] for entry in entries} == {"pending"}


def test_every_current_domain_tag_is_in_crosswalk() -> None:
    entries = _load_crosswalk()["entries"]
    topic_ids = {entry["id"] for entry in entries if entry["kind"] == "topic_tag"}
    current = _taxonomy_domain_ids()
    assert len(current) == 11
    missing = [tag for tag in current if tag not in topic_ids]
    assert missing == [], f"current tags missing from crosswalk: {missing}"


def test_a3_proposed_tags_lens_values_and_centrality_values_are_listed() -> None:
    entries = _load_crosswalk()["entries"]
    by_id = {entry["id"]: entry for entry in entries}
    for tag in A3_LIFECYCLE_TOPICS:
        assert by_id.get(tag, {}).get("kind") == "topic_tag", f"missing topic {tag}"
    for value in LENS_VALUES:
        assert by_id.get(value, {}).get("kind") == "facet_value", f"missing lens {value}"
    for value in CENTRALITY_VALUES:
        assert by_id.get(value, {}).get("kind") == "facet_value", f"missing value {value}"
    assert by_id["plastics_centrality"]["kind"] == "field"
    assert by_id["analytic_lens"]["kind"] == "facet"


def test_proposed_only_tags_are_not_registered_in_taxonomy() -> None:
    # Nothing ships until approved (A3-D7): an added tag must not be in taxonomy.yml yet.
    entries = _load_crosswalk()["entries"]
    proposed = {
        entry["id"]
        for entry in entries
        if entry["kind"] == "topic_tag" and entry["proposed_action"] in {"add", "add_experimental"}
    }
    registered = set(_taxonomy_domain_ids())
    assert proposed, "expected proposed topic tags"
    assert proposed & registered == set(), "proposed tags are already in taxonomy.yml"


def test_proposal_lists_exactly_the_ten_decision_items() -> None:
    rows = _proposal_rows()
    assert [row[0] for row in rows] == [f"D{number}" for number in range(1, 11)]
    for row in rows:
        assert len(row) == 6, f"{row[0]} should have six columns, found {len(row)}"
        assert row[5] == "", f"{row[0]} must leave the Owner decision cell blank"


def test_every_entry_maps_to_a_proposal_row_and_every_row_is_used() -> None:
    entries = _load_crosswalk()["entries"]
    used = {entry["item"] for entry in entries}
    listed = {row[0] for row in _proposal_rows()}
    assert used <= listed, f"entries cite items not in the proposal: {used - listed}"
    assert used == DECISION_ITEMS


def test_proposal_says_nothing_ships_until_approved() -> None:
    text = PROPOSAL_PATH.read_text(encoding="utf-8")
    assert "Nothing ships until you approve it" in text
    assert "config/taxonomy_crosswalk.yml" in text
