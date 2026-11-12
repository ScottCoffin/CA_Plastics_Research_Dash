"""Offline tests for the gold-label review logic (atlas.gold_label_review). No Streamlit."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from atlas import gold_label_review as gl
from atlas.nlp.annotation import (
    _SAMPLING,
    _SOURCES,
    _TIERS,
    ANNOTATION_FIELDS,
    DOMAIN_TAGS,
    LABEL_FIELDS,
    import_annotations,
)

ROOT = Path(__file__).resolve().parent.parent

SPLITS = [
    {"work_id": "W1", "sample_role": "pool", "split": "train"},
    {"work_id": "W2", "sample_role": "pool", "split": "dev"},
    {"work_id": "W3", "sample_role": "leak_test", "split": "test"},
    {"work_id": "W4", "sample_role": "pool", "split": "test"},
    {"work_id": "W5", "sample_role": "pool", "split": "train"},
]
WORKS = {
    row["work_id"]: {
        "work_id": row["work_id"],
        "title": f"Title {row['work_id']}",
        "abstract": f"Abstract for {row['work_id']}",
        "year": 2020,
    }
    for row in SPLITS
}
COMPLETE_FORM: dict[str, Any] = {
    "plastic_related": "true",
    "plastic_tier": "core",
    "ca_sampled": "yes",
    "study_type": "field_occurrence",
    "domain_tags": ["occurrence_and_monitoring", "wastewater_and_treatment"],
    "evidence_snippet": "microplastics were collected",
    "evidence_source": "abstract",
}


def _sheet(tmp_path: Path, name: str = "annotations_SC.csv") -> Path:
    path = tmp_path / "annotations" / name
    assert gl.ensure_sheet(path, SPLITS, WORKS) is True
    return path


def _raw_records(path: Path) -> list[str]:
    """Each data line of the sheet as raw text, to check byte-for-byte preservation."""
    return path.read_bytes().decode("utf-8").splitlines(keepends=True)


def test_sheet_is_created_only_when_missing(tmp_path: Path) -> None:
    path = _sheet(tmp_path)
    before = path.read_bytes()
    assert before.startswith(b"\xef\xbb\xbf")  # export_templates writes a UTF-8 BOM
    rows = gl.read_rows(path)
    assert [row["work_id"] for row in rows] == ["W1", "W2", "W3", "W4", "W5"]  # test included
    assert {row["guide_version"] for row in rows} == {"guide_v2"}
    assert {row["annotator"] for row in rows} == {"SC"}
    assert all(row["abstract"] == "" for row in rows)  # abstracts stay in the parquet
    assert rows[0]["title"] == "Title W1"
    assert gl.ensure_sheet(path, SPLITS, WORKS) is False
    assert path.read_bytes() == before


def test_sheet_creation_fails_loudly_when_metadata_is_missing(tmp_path: Path) -> None:
    works = {key: value for key, value in WORKS.items() if key != "W3"}
    path = tmp_path / "annotations_SC.csv"
    with pytest.raises(ValueError, match="1 split work"):
        gl.ensure_sheet(path, SPLITS, works)
    assert not path.exists()


def test_row_update_leaves_other_rows_byte_identical(tmp_path: Path) -> None:
    path = _sheet(tmp_path)
    before = _raw_records(path)
    gl.update_row(path, "W4", {"plastic_related": "false", "decision_status": "complete"})
    after = _raw_records(path)
    assert len(before) == len(after)
    changed = [i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b]
    assert len(changed) == 1
    assert after[changed[0]].startswith("W4,")
    assert after[changed[0]].endswith("\r\n") or after[changed[0]].endswith("\n")
    assert gl.read_rows(path)[3]["plastic_related"] == "false"


def test_update_rejects_unknown_field_and_unknown_work(tmp_path: Path) -> None:
    path = _sheet(tmp_path)
    with pytest.raises(KeyError):
        gl.update_row(path, "W1", {"not_a_field": "x"})
    with pytest.raises(KeyError):
        gl.update_row(path, "W999", {"plastic_related": "true"})


def test_missing_study_type_is_rejected(tmp_path: Path) -> None:
    path = _sheet(tmp_path)
    form = {**COMPLETE_FORM, "study_type": None}
    with pytest.raises(ValueError, match="missing study_type for W1"):
        gl.save_decision(path, "W1", form, "complete", gl.split_index(SPLITS))
    assert gl.read_rows(path)[0]["decision_status"] == ""


def test_tier_with_plastic_related_false_is_rejected(tmp_path: Path) -> None:
    # The view never sends a tier for a negative work, so the rule is tested on the
    # validator directly with a tier that a hand-edited sheet could contain.
    path = _sheet(tmp_path)
    rows = gl.read_rows(path)
    row = {**rows[0], "plastic_related": "false", "plastic_tier": "core", "ca_sampled": "no"}
    row.update(study_type="policy_social", decision_status="complete")
    with pytest.raises(ValueError, match="cannot have a plastic_tier"):
        gl.validate_row(row, gl.split_index(SPLITS))


def test_form_mapping_clears_tier_and_tags_for_negative_work() -> None:
    form = {**COMPLETE_FORM, "plastic_related": "false"}
    values = gl.values_from_form(form, "complete")
    assert values["plastic_tier"] == ""
    assert values["domain_tags"] == ""
    assert values["plastic_related"] == "false"


def test_adjudication_hold_clears_labels_and_keeps_evidence() -> None:
    values = gl.values_from_form(COMPLETE_FORM, "adjudication_required")
    assert {values[f] for f in LABEL_FIELDS} == {""}
    assert values["domain_tags"] == ""
    assert values["evidence_snippet"] == "microplastics were collected"
    assert values["decision_status"] == "adjudication_required"


def test_adjudication_hold_without_evidence_is_rejected(tmp_path: Path) -> None:
    path = _sheet(tmp_path)
    form = {**COMPLETE_FORM, "evidence_snippet": "", "evidence_source": ""}
    with pytest.raises(ValueError, match="needs evidence or a decision note"):
        gl.save_decision(path, "W1", form, "adjudication_required", gl.split_index(SPLITS))


def test_snippet_longer_than_limit_is_rejected(tmp_path: Path) -> None:
    path = _sheet(tmp_path)
    form = {**COMPLETE_FORM, "evidence_snippet": "x" * (gl.MAX_SNIPPET_CHARS + 1)}
    with pytest.raises(ValueError, match=f"longer than {gl.MAX_SNIPPET_CHARS}"):
        gl.save_decision(path, "W1", form, "complete", gl.split_index(SPLITS))


def test_save_writes_only_the_chosen_row(tmp_path: Path) -> None:
    path = _sheet(tmp_path)
    before = _raw_records(path)
    gl.save_decision(path, "W2", COMPLETE_FORM, "complete", gl.split_index(SPLITS))
    after = _raw_records(path)
    changed = [i for i, (a, b) in enumerate(zip(before, after, strict=True)) if a != b]
    assert len(changed) == 1 and after[changed[0]].startswith("W2,")
    row = gl.read_rows(path)[1]
    assert row["domain_tags"] == "occurrence_and_monitoring|wastewater_and_treatment"
    assert row["decision_status"] == "complete"
    assert row["abstract"] == ""


def test_queue_puts_dev_and_test_before_train(tmp_path: Path) -> None:
    rows = gl.read_rows(_sheet(tmp_path))
    unlabelled = [row["work_id"] for row in gl.queue(rows, "Unlabelled (dev+test first)")]
    assert unlabelled == ["W2", "W3", "W4", "W1", "W5"]
    assert [row["work_id"] for row in gl.queue(rows, "Unlabelled (all)")] == [
        "W1",
        "W2",
        "W3",
        "W4",
        "W5",
    ]
    assert [row["work_id"] for row in gl.queue(rows, "All")][:3] == ["W2", "W3", "W4"]


def test_queue_views_and_progress(tmp_path: Path) -> None:
    path = _sheet(tmp_path)
    gl.save_decision(path, "W2", COMPLETE_FORM, "complete", gl.split_index(SPLITS))
    gl.save_decision(
        path,
        "W3",
        {**COMPLETE_FORM, "evidence_snippet": "x"},
        "adjudication_required",
        gl.split_index(SPLITS),
    )
    rows = gl.read_rows(path)
    assert [r["work_id"] for r in gl.queue(rows, "Needs adjudication")] == ["W3"]
    assert "W2" not in [r["work_id"] for r in gl.queue(rows, "Unlabelled (dev+test first)")]
    assert "W3" not in [r["work_id"] for r in gl.queue(rows, "Unlabelled (all)")]
    assert gl.progress(rows) == {"test": (0, 2), "dev": (1, 1), "train": (0, 2)}
    with pytest.raises(ValueError, match="unknown view"):
        gl.queue(rows, "Nope")


def test_position_after_save_skip_and_search() -> None:
    before = ["W2", "W3", "W4"]
    assert gl.position_after(before, ["W3", "W4"], "W2", 0) == 0  # removed: next slides in
    assert gl.position_after(before, before, "W2", 0) == 1  # skip or adjudication hold
    assert gl.position_after(before, before, "W9", 2) == 2  # searched outside the queue


def test_work_id_search() -> None:
    rows = [{"work_id": "W1234", "split": "dev"}]
    assert gl.normalize_work_id(" 1234 ") == "W1234"
    assert gl.normalize_work_id("w1234") == "W1234"
    assert gl.find_work(rows, "1234") == {"work_id": "W1234", "split": "dev"}
    assert gl.find_work(rows, "") is None
    assert gl.find_work(rows, "W9") is None


def test_header_mismatch_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("work_id,split\nW1,dev\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header mismatch"):
        gl.read_rows(path)


def test_validate_row_agrees_with_import_annotations(tmp_path: Path) -> None:
    one = SPLITS[:1]  # a one-row sheet, so the importer sees no blank rows
    good = gl.values_from_form(COMPLETE_FORM, "complete")
    bad = gl.values_from_form({**COMPLETE_FORM, "study_type": ""}, "complete")
    for name, values in {"good": good, "bad": bad}.items():
        path = tmp_path / name / "annotations_SC.csv"
        gl.ensure_sheet(path, one, WORKS)
        base = gl.read_rows(path)[0]
        validator_ok, importer_ok = True, True
        try:
            gl.validate_row({**base, **values}, gl.split_index(one))
        except ValueError:
            validator_ok = False
        gl.update_row(path, "W1", values)
        try:
            import_annotations([path], one, guide_version="guide_v2")
        except ValueError:
            importer_ok = False
        assert validator_ok == importer_ok, name
        assert validator_ok is (name == "good")


def _complete_all(path: Path) -> None:
    """Fill every row of the five-work sheet so the importer accepts the whole file."""
    splits = gl.split_index(SPLITS)
    gl.save_decision(path, "W1", COMPLETE_FORM, "complete", splits)
    gl.save_decision(path, "W2", COMPLETE_FORM, "complete", splits)
    gl.save_decision(
        path,
        "W3",
        {**COMPLETE_FORM, "plastic_related": "false", "plastic_tier": None, "domain_tags": []},
        "complete",
        splits,
    )
    gl.save_decision(path, "W4", COMPLETE_FORM, "adjudication_required", splits)
    gl.save_decision(path, "W5", COMPLETE_FORM, "complete", splits)


def test_round_trip_through_import_annotations(tmp_path: Path) -> None:
    path = _sheet(tmp_path)
    _complete_all(path)
    imported = import_annotations([path], SPLITS, guide_version="guide_v2", include_test=True)
    by_id = {row["work_id"]: row for row in imported}
    assert set(by_id) == {"W1", "W2", "W3", "W4", "W5"}
    assert by_id["W1"]["decision_status"] == "complete"
    assert by_id["W1"]["domain_tags"] == [
        "occurrence_and_monitoring",
        "wastewater_and_treatment",
    ]
    assert by_id["W3"]["plastic_related"] == "false"
    assert by_id["W4"]["decision_status"] == "adjudication_required"


def test_import_with_full_abstract_metadata_needs_blank_abstract_map(tmp_path: Path) -> None:
    """The sheet keeps abstracts blank, so the importer's metadata check needs the same map."""
    path = _sheet(tmp_path)
    _complete_all(path)
    blank = {k: {**v, "abstract": ""} for k, v in WORKS.items()}
    imported = import_annotations(
        [path], SPLITS, guide_version="guide_v2", works_by_id=blank, include_test=True
    )
    assert len(imported) == 5
    with pytest.raises(ValueError, match="source metadata conflict"):
        import_annotations(
            [path], SPLITS, guide_version="guide_v2", works_by_id=WORKS, include_test=True
        )


def test_choice_lists_match_the_importer_sets() -> None:
    assert set(gl.TIER_OPTIONS) == _TIERS
    assert set(gl.SAMPLING_OPTIONS) == _SAMPLING
    assert set(gl.SOURCE_OPTIONS) == _SOURCES
    assert set(gl.FORM_FIELDS) <= set(ANNOTATION_FIELDS)


def test_study_types_match_guide_v2_and_taxonomy() -> None:
    taxonomy = yaml.safe_load((ROOT / "config" / "taxonomy.yml").read_text(encoding="utf-8"))
    values = taxonomy["add_on_a2"]["study_type"]["values"]
    assert list(gl.STUDY_TYPES) == [v for v in values if v != "unclear_other"]
    guide = (ROOT / "docs" / "LABELING_GUIDE_A2_ADDENDUM.md").read_text(encoding="utf-8")
    for value in gl.STUDY_TYPES:
        assert re.search(rf"^\| {value} \|", guide, re.MULTILINE), value
    assert set(DOMAIN_TAGS) == {
        "occurrence_and_monitoring",
        "analytical_methods",
        "fate_transport_and_sorption",
        "wastewater_and_treatment",
        "ecotoxicology_and_trophic_transfer",
        "soil_and_agriculture",
        "human_exposure_and_health_risk",
        "air",
    }


def test_line_endings_are_kept_for_crlf_and_lf_sheets(tmp_path: Path) -> None:
    path = _sheet(tmp_path)  # csv writes CRLF by default
    assert b"\r\n" in path.read_bytes()
    gl.update_row(path, "W2", {"plastic_related": "true"})
    crlf = path.read_bytes()
    assert crlf.count(b"\n") == crlf.count(b"\r\n")
    path.write_bytes(crlf.replace(b"\r\n", b"\n"))
    gl.update_row(path, "W3", {"plastic_related": "false"})
    assert b"\r" not in path.read_bytes()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        assert len(list(csv.DictReader(stream))) == 5


def test_negative_work_needs_no_other_labels(tmp_path: Path) -> None:
    path = _sheet(tmp_path)
    form = {"plastic_related": "false"}
    values = gl.save_decision(path, "W1", form, "complete", gl.split_index(SPLITS))
    assert values["ca_sampled"] == values["study_type"] == values["domain_tags"] == ""
    # Labels left over from an earlier "true" answer are cleared, not saved.
    full = {**COMPLETE_FORM, "plastic_related": "false"}
    assert gl.values_from_form(full, "complete")["study_type"] == ""
    assert gl.values_from_form(full, "complete")["ca_sampled"] == ""


def test_positive_work_still_needs_ca_sampled(tmp_path: Path) -> None:
    path = _sheet(tmp_path)
    form = {**COMPLETE_FORM, "ca_sampled": None}
    with pytest.raises(ValueError, match="invalid ca_sampled for W1"):
        gl.save_decision(path, "W1", form, "complete", gl.split_index(SPLITS))


def test_new_design_label_is_saved_and_offered_again(tmp_path: Path) -> None:
    path = _sheet(tmp_path)
    form = {**COMPLETE_FORM, "study_type": " Archival specimen-analysis "}
    gl.save_decision(path, "W1", form, "complete", gl.split_index(SPLITS))
    assert gl.read_rows(path)[0]["study_type"] == "archival_specimen_analysis"
    options = gl.study_type_options(gl.read_rows(path))
    assert options[: len(gl.STUDY_TYPES)] == list(gl.STUDY_TYPES)
    assert options[-1] == "archival_specimen_analysis"


def test_paper_link_and_author_line() -> None:
    assert gl.paper_link({"doi": "https://doi.org/10.1/X"}, "W1") == "https://doi.org/10.1/X"
    assert gl.paper_link({"doi": "doi:10.1/x"}, "W1") == "https://doi.org/10.1/x"
    assert gl.paper_link({}, "W9") == "https://openalex.org/W9"
    assert gl.author_line(["A", "B"]) == "A, B"
    many = gl.author_line([f"N{i}" for i in range(12)], limit=4)
    assert many == "N0, N1, N2, ... (12 authors), N11"


def test_load_works_adds_doi_journal_and_authors(tmp_path: Path) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    works = tmp_path / "works.parquet"
    pq.write_table(
        pa.table(
            {
                "work_id": ["W1"],
                "doi": ["https://doi.org/10.1/a"],
                "title": ["T"],
                "abstract": ["A"],
                "year": [2020],
                "journal": ["J"],
            }
        ),
        works,
    )
    pq.write_table(
        pa.table({"work_id": ["W1", "W1"], "author_name": ["First", "Second"]}),
        tmp_path / "authorships.parquet",
    )
    out = gl.load_works(works, ["W1"], fallbacks=())
    assert out["W1"]["authors"] == ["First", "Second"]
    assert out["W1"]["journal"] == "J"
    assert out["W1"]["doi"] == "https://doi.org/10.1/a"


def test_snippet_without_source_gets_one_automatically(tmp_path: Path) -> None:
    path = _sheet(tmp_path)
    title = gl.read_rows(path)[0]["title"]
    splits = gl.split_index(SPLITS)
    form = {**COMPLETE_FORM, "evidence_snippet": "samples were collected", "evidence_source": ""}
    assert gl.save_decision(path, "W1", form, "complete", splits)["evidence_source"] == "abstract"
    form["evidence_snippet"] = f"  {title.upper()} "
    assert gl.save_decision(path, "W1", form, "complete", splits)["evidence_source"] == "title"
    form.update(evidence_snippet="", evidence_source="abstract")
    assert gl.save_decision(path, "W1", form, "complete", splits)["evidence_source"] == ""
