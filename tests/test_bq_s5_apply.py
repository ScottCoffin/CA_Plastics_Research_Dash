"""BQ-S5 slice 1: owner-approved taxonomy decisions D1-D10 (H40, 2026-11-25).

Covers one topic list (annotation, taxonomy.yml, site topics.js), tiers, the analytic_lens,
plastics_centrality and origin facets, the experimental topic, and the legacy CSV header.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from atlas.nlp import annotation as ann
from atlas.nlp.eval import evaluate

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY = yaml.safe_load((ROOT / "config" / "taxonomy.yml").read_text(encoding="utf-8"))
TOPICS_JS = ROOT / "site" / "assets" / "topics.js"
TAXONOMY_IDS = [entry["id"] for entry in TAXONOMY["domain_tags"]]
LIFECYCLE_TAGS = {
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
SPLIT_INDEX = {"W1": {"split": "train", "sample_role": "pool"}}
SPLITS = [{"work_id": "W1", "sample_role": "pool", "split": "train"}]


def _row(**overrides: str) -> dict[str, str]:
    row = {field: "" for field in ann.ANNOTATION_FIELDS}
    row.update(
        work_id="W1",
        split="train",
        sample_role="pool",
        annotator="Ann A",
        guide_version="guide_v1",
        plastic_related="true",
        plastic_tier="core",
        ca_sampled="yes",
        study_type="field_occurrence",
        domain_tags="occurrence_and_monitoring",
        decision_status="complete",
        plastics_centrality="not_assessed",
    )
    row.update(overrides)
    return row


def _normalize(**overrides: str) -> dict[str, Any]:
    return ann._normalize_row(_row(**overrides), SPLIT_INDEX, "guide_v1")


def _topics_js_keys() -> list[str]:
    text = TOPICS_JS.read_text(encoding="utf-8")
    block = text[text.index("const TOPICS = {") : text.index("// Shown wherever an auxiliary")]
    return re.findall(r"^    ([a-z_]+): \{", block, re.MULTILINE)


def test_one_topic_list_agrees_across_annotation_taxonomy_and_site() -> None:
    assert len(TAXONOMY_IDS) == 21
    assert len(set(TAXONOMY_IDS)) == 21
    assert list(ann.DOMAIN_TAGS) == TAXONOMY_IDS
    keys = _topics_js_keys()
    assert len(keys) == len(set(keys)) == 21
    assert set(keys) == set(TAXONOMY_IDS)


def test_disciplines_mirror_the_eleven_original_tags() -> None:
    assert TAXONOMY["disciplines"] == TAXONOMY_IDS[:11]


def test_experimental_flag_agrees_with_annotation_constant() -> None:
    flagged = {entry["id"] for entry in TAXONOMY["domain_tags"] if entry.get("experimental")}
    assert flagged == {"culture_media_and_discourse"}
    assert set(ann.EXPERIMENTAL_DOMAIN_TAGS) == flagged


def test_lifecycle_tags_are_registered_without_seeds() -> None:
    by_id = {entry["id"]: entry for entry in TAXONOMY["domain_tags"]}
    assert LIFECYCLE_TAGS <= set(by_id)
    for tag in LIFECYCLE_TAGS:
        assert by_id[tag]["seed_concepts"] == [], tag
        assert by_id[tag]["status"] == "approved_no_seeds", tag
    assert by_id["waste_trade_and_global_flows"]["parent"] == "waste_management_and_recycling"


def test_tiers_and_facet_values_agree_with_annotation() -> None:
    facets = TAXONOMY["facets"]
    assert (
        set(TAXONOMY["tiers"])
        == ann._TIERS
        == {
            "core",
            "chemicals-in-plastics",
            "lifecycle_and_society",
        }
    )
    assert set(facets["analytic_lens"]["values"]) == set(ann.LENS_VALUES)
    assert len(ann.LENS_VALUES) == 8
    assert set(facets["plastics_centrality"]["values"]) == set(ann.PLASTICS_CENTRALITY_VALUES)
    assert facets["plastics_centrality"]["default"] == "not_assessed"
    assert set(facets["origin"]["values"]) == set(ann.ORIGIN_VALUES)


def test_review_facets_are_registered_as_planned_only() -> None:
    block = TAXONOMY["review_facets"]
    assert block["status"] == "planned"
    assert block["note"] == "adopt one at a time with a benchmark (SPK-DEET first facet)"
    assert len(block["facets"]) == 18
    assert len(set(block["facets"])) == 18


def test_existing_tiers_and_tags_still_validate() -> None:
    assert _normalize(plastic_tier="chemicals-in-plastics")["plastic_tier"]
    assert _normalize(domain_tags="plastisphere|risk_assessment")["domain_tags"] == [
        "plastisphere",
        "risk_assessment",
    ]


def test_lifecycle_tier_and_new_tags_are_accepted() -> None:
    row = _normalize(
        plastic_tier="lifecycle_and_society",
        domain_tags="lca_and_sustainability|waste_trade_and_global_flows",
    )
    assert row["plastic_tier"] == "lifecycle_and_society"
    assert row["domain_tags"] == ["lca_and_sustainability", "waste_trade_and_global_flows"]


def test_unknown_tag_still_rejected() -> None:
    with pytest.raises(ValueError, match="domain_tags"):
        _normalize(domain_tags="lca_and_sustainability|not_a_tag")


def test_lens_requires_quoted_evidence() -> None:
    with pytest.raises(ValueError, match="lens_evidence"):
        _normalize(analytic_lens="waste_colonialism")


def test_lens_with_evidence_is_accepted_and_sorted() -> None:
    row = _normalize(
        analytic_lens="waste_colonialism|labour_and_informal_economy",
        lens_evidence='"quoted excerpt"',
    )
    assert row["analytic_lens"] == "labour_and_informal_economy|waste_colonialism"


@pytest.mark.parametrize(
    "lens",
    [
        "bogus",
        "waste_colonialism|waste_colonialism",
        # A3-D20: these were folded into existing values, so they are not values of their own.
        "spatial_injustice",
        "decolonial_and_indigenous_research",
        "behavioural_and_psychosocial",
    ],
)
def test_unknown_duplicate_or_folded_lens_rejected(lens: str) -> None:
    with pytest.raises(ValueError, match="analytic_lens"):
        _normalize(analytic_lens=lens, lens_evidence="quote")


def test_blank_centrality_defaults_to_not_assessed() -> None:
    row = _normalize(plastics_centrality="")
    assert row["plastics_centrality"] == "not_assessed"


def test_centrality_is_accepted_for_lifecycle_works() -> None:
    row = _normalize(plastic_tier="lifecycle_and_society", plastics_centrality="primary")
    assert row["plastics_centrality"] == "primary"


def test_centrality_is_rejected_for_other_tiers() -> None:
    with pytest.raises(ValueError, match="lifecycle_and_society"):
        _normalize(plastics_centrality="primary")


def test_centrality_is_rejected_on_negative_works() -> None:
    with pytest.raises(ValueError, match="lifecycle_and_society"):
        _normalize(
            plastic_related="false",
            plastic_tier="",
            ca_sampled="",
            study_type="",
            domain_tags="",
            plastics_centrality="incidental",
        )


def test_invalid_centrality_rejected() -> None:
    with pytest.raises(ValueError, match="plastics_centrality"):
        _normalize(plastic_tier="lifecycle_and_society", plastics_centrality="major")


@pytest.mark.parametrize("value", ["primary", "secondary", "not_stated"])
def test_origin_values_accepted(value: str) -> None:
    assert _normalize(origin=value)["origin"] == value


def test_origin_blank_and_unknown() -> None:
    assert _normalize(origin="")["origin"] == ""
    with pytest.raises(ValueError, match="origin"):
        _normalize(origin="tertiary")


def test_unresolved_row_cannot_carry_lens_or_origin() -> None:
    with pytest.raises(ValueError, match="must not contain labels"):
        ann._normalize_row(
            _row(
                decision_status="adjudication_required",
                plastic_related="",
                plastic_tier="",
                ca_sampled="",
                study_type="",
                domain_tags="",
                evidence_snippet="note",
                analytic_lens="waste_colonialism",
                lens_evidence="quote",
            ),
            SPLIT_INDEX,
            "guide_v1",
        )


def test_template_export_writes_new_columns_with_defaults(tmp_path: Path) -> None:
    paths = ann.export_templates(
        [{"work_id": "W1", "split": "train", "sample_role": "pool"}],
        ["Ann A"],
        tmp_path,
        guide_version="guide_v1",
    )
    with paths[0].open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == list(ann.ANNOTATION_FIELDS)
        row = next(reader)
    assert row["plastics_centrality"] == "not_assessed"
    assert row["analytic_lens"] == row["lens_evidence"] == row["origin"] == ""


def test_legacy_header_still_imports_with_blank_new_columns(tmp_path: Path) -> None:
    legacy = ann.LEGACY_ANNOTATION_FIELDS
    assert "analytic_lens" not in legacy and "origin" not in legacy
    path = tmp_path / "annotations_legacy.csv"
    row = {field: "" for field in legacy}
    row.update(
        work_id="W1",
        split="train",
        sample_role="pool",
        annotator="Ann A",
        guide_version="guide_v1",
        plastic_related="true",
        plastic_tier="core",
        ca_sampled="yes",
        study_type="field_occurrence",
        domain_tags="occurrence_and_monitoring",
        decision_status="complete",
    )
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=legacy)
        writer.writeheader()
        writer.writerow(row)
    imported = ann.import_annotations([path], SPLITS, guide_version="guide_v1")
    assert len(imported) == 1
    assert imported[0]["plastics_centrality"] == "not_assessed"
    assert imported[0]["analytic_lens"] == ""


def test_experimental_tag_is_not_scored_in_per_tag_metrics() -> None:
    gold, predictions = [], []
    for index in range(3):
        tags = ["culture_media_and_discourse"] if index else ["occurrence_and_monitoring"]
        common = {
            "work_id": f"w{index}",
            "plastic_related": "true",
            "plastic_tier": "core",
            "ca_sampled": "yes",
            "study_type": "field_occurrence",
            "domain_tags": tags,
        }
        gold.append({**common, "split": "dev", "decision_status": "complete"})
        predictions.append({**common, "plastic_related_probability": 0.9})
    report = evaluate(gold, predictions, split="dev", model_version="m1", data_snapshot="s1")
    assert "culture_media_and_discourse" not in report["domain_tags"]
    assert "occurrence_and_monitoring" in report["domain_tags"]
