"""BQ-G0: guide addendum A3 files agree (guide_v3 fields, calibration cases, CA backfill)."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "LABELING_GUIDE_A3_ADDENDUM.md"
CENTRALITY = {"primary", "substantial", "incidental", "none", "not_assessed"}
LENSES = {
    "waste_colonialism",
    "environmental_justice_and_racism",
    "indigenous_and_community_governance",
    "community_and_participatory_methods",
    "labour_and_informal_economy",
    "circularity_critique_and_greenwashing",
    "political_economy_centre_periphery",
    "responsibility_shifting",
}


def _rows(name: str) -> list[dict[str, str]]:
    with (ROOT / "curation" / name).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_gold_template_has_the_a3_fields_after_the_guide_v2_fields() -> None:
    header = (ROOT / "curation" / "gold_works.csv").read_text(encoding="utf-8").splitlines()[0]
    expected = [
        "analytic_lens",
        "lens_evidence",
        "colonialism_framing",
        "waste_colonialism_type",
        "plastics_centrality",
        "role",
    ]
    assert header.split(",")[-6:] == expected
    assert header.startswith("work_id,plastic_related,plastic_tier,")


def test_guide_lists_every_lens_and_centrality_value() -> None:
    text = GUIDE.read_text(encoding="utf-8")
    for value in LENSES | CENTRALITY | {"lifecycle_and_society", "guide_example"}:
        assert f"`{value}`" in text, value


def test_guide_examples_are_valid_and_carry_evidence_for_every_lens() -> None:
    rows = _rows("a3_guide_examples.csv")
    assert len(rows) == 5
    assert {r["example_id"] for r in rows} == {
        "ashworth_2026",
        "foellmer_2022",
        "peryman_2024",
        "stoett_2024",
        "gutberlet_2023",
    }
    for row in rows:
        assert row["role"] == "guide_example"
        assert row["plastics_centrality"] in CENTRALITY - {"not_assessed"}
        lenses = [v for v in row["analytic_lens"].split(";") if v]
        assert set(lenses) <= LENSES, row["example_id"]
        assert bool(lenses) == bool(row["lens_evidence"].strip()), row["example_id"]
    boundary = {r["example_id"]: r["plastics_centrality"] for r in rows}
    assert boundary["ashworth_2026"] == boundary["foellmer_2022"] == "incidental"


def test_guide_examples_never_enter_the_california_splits() -> None:
    examples = _rows("a3_guide_examples.csv")
    ids = {r["work_id"] for r in examples if r["work_id"]}
    dois = {r["doi"].lower() for r in examples if r["doi"]}
    assert len(ids) == 4 and len(dois) == 4
    split_ids = {r["work_id"] for r in _rows("splits_v2.csv")}
    assert not ids & split_ids
    labelled = _rows("annotations/annotations_SC.csv")
    assert not ids & {r["work_id"] for r in labelled}


def test_backfill_rows_are_labelled_california_works_set_to_not_assessed() -> None:
    labelled = {
        r["work_id"]
        for r in _rows("annotations/annotations_SC.csv")
        if r["decision_status"] == "complete"
    }
    backfill = _rows("a3_lens_backfill.csv")
    covered = {r["work_id"] for r in backfill}
    # Labelling continues after BQ-G0: every backfilled work is labelled, and the backfill
    # covered all labelled works at the time (38 on 2026-11-18).
    assert covered <= labelled
    assert len(covered) == len(backfill) >= 38
    for row in backfill:
        assert row["plastics_centrality"] == row["analytic_lens"] == "not_assessed"
        assert row["a3_conflict"] in {"none", "review_optional", "reopen"}
        assert bool(row["note"]) == (row["a3_conflict"] != "none")
