import csv
import hashlib
from pathlib import Path

import pytest

from atlas.nlp.annotation import (
    ANNOTATION_FIELDS,
    agreement_summary,
    export_templates,
    import_annotations,
    require_frozen_guide,
)

SPLITS = [
    {"work_id": "W1", "sample_role": "pool", "split": "train"},
    {"work_id": "W2", "sample_role": "pool", "split": "train"},
    {"work_id": "W3", "sample_role": "leak_test", "split": "test"},
]


def _annotate(path: Path, annotator: str, ids: list[str] | None = None) -> None:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if ids is not None:
        rows = [row for row in rows if row["work_id"] in ids]
    for i, row in enumerate(rows):
        row.update(
            annotator=annotator,
            plastic_related="true",
            plastic_tier="core",
            ca_sampled="yes" if i == 0 else "no",
            study_type="field study",
            domain_tags="occurrence_and_monitoring",
            evidence_snippet="Synthetic example evidence",
            evidence_source="abstract",
            decision_status="complete",
        )
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ANNOTATION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_template_import_roundtrip_and_kappa(tmp_path: Path) -> None:
    paths = export_templates(SPLITS[:2], ["A", "B"], tmp_path, guide_version="guide_v1")
    _annotate(paths[0], "A")
    _annotate(paths[1], "B")
    with paths[1].open(encoding="utf-8-sig", newline="") as stream:
        rows_b = list(csv.DictReader(stream))
    rows_b[0]["ca_sampled"], rows_b[1]["ca_sampled"] = "no", "yes"
    with paths[1].open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ANNOTATION_FIELDS)
        writer.writeheader()
        writer.writerows(rows_b)
    rows = import_annotations(paths, SPLITS, guide_version="guide_v1")
    assert len(rows) == 4
    assert rows[0]["domain_tags"] == ["occurrence_and_monitoring"]
    report = agreement_summary(rows)
    assert report["double_annotated_works"] == 2
    assert report["labels"]["A__B__plastic_related"]["kappa"] is None
    assert report["labels"]["A__B__ca_sampled"]["n"] == 2
    assert report["labels"]["A__B__ca_sampled"]["kappa"] == -1.0
    assert report["labels"]["A__B__domain:air"]["kappa"] is None
    review_item = report["disagreements"][0]
    assert review_item["work_id"] == "W1"
    assert review_item["fields"]["ca_sampled"] == {"A": "yes", "B": "no"}
    assert review_item["review_status"] == "unresolved"
    assert review_item["annotations"]["A"]["evidence_source"] == "abstract"
    assert review_item["adjudication"] == {"value": None, "rationale": None}


def test_test_split_export_requires_explicit_opt_in(tmp_path: Path) -> None:
    paths = export_templates(SPLITS, ["A"], tmp_path, guide_version="guide_v1")
    assert len(paths) == 1
    with paths[0].open(encoding="utf-8-sig", newline="") as stream:
        assert [row["work_id"] for row in csv.DictReader(stream)] == ["W1", "W2"]
    paths = export_templates(SPLITS, ["A"], tmp_path, guide_version="guide_v1", include_test=True)
    _annotate(paths[0], "A")
    with pytest.raises(ValueError, match="test-label import"):
        import_annotations(paths, SPLITS, guide_version="guide_v1")
    assert len(import_annotations(paths, SPLITS, guide_version="guide_v1", include_test=True)) == 3


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"plastic_related": "maybe"}, "plastic_related"),
        ({"plastic_related": "false", "plastic_tier": "core"}, "negative"),
        ({"plastic_related": "true", "plastic_tier": "bogus"}, "plastic_tier"),
        ({"ca_sampled": "probably"}, "ca_sampled"),
        ({"domain_tags": "unknown_tag"}, "domain_tags"),
        ({"guide_version": "guide_v0"}, "guide version mismatch"),
        ({"split": "test"}, "split metadata conflict"),
        ({"work_id": "W999"}, "unknown work_id"),
    ],
)
def test_import_rejects_invalid_annotations(tmp_path: Path, change: dict, message: str) -> None:
    path = export_templates(SPLITS[:1], ["A"], tmp_path, guide_version="guide_v1")[0]
    _annotate(path, "A")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[0].update(change)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ANNOTATION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match=message):
        import_annotations([path], SPLITS, guide_version="guide_v1")


def test_import_rejects_duplicate_annotator_work_and_unknown_guide(tmp_path: Path) -> None:
    paths = export_templates(SPLITS[:1], ["A"], tmp_path, guide_version="guide_v1")
    _annotate(paths[0], "A")
    with pytest.raises(ValueError, match="duplicate annotation"):
        import_annotations(paths * 2, SPLITS, guide_version="guide_v1")
    with pytest.raises(ValueError, match="guide version mismatch"):
        import_annotations(paths, SPLITS, guide_version="guide_v2")


def test_import_rejects_read_only_source_metadata_conflict(tmp_path: Path) -> None:
    metadata = {"W1": {"year": 2020, "title": "Source title", "abstract": "Source abstract"}}
    path = export_templates(
        SPLITS[:1], ["A"], tmp_path, guide_version="guide_v1", works_by_id=metadata
    )[0]
    _annotate(path, "A")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[0]["title"] = "Edited title"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ANNOTATION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(ValueError, match="source metadata conflict"):
        import_annotations([path], SPLITS, guide_version="guide_v1", works_by_id=metadata)


def test_unresolved_and_kappa_edge_cases(tmp_path: Path) -> None:
    path = export_templates(SPLITS[:1], ["A"], tmp_path, guide_version="guide_v1")[0]
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[0].update(decision_status="adjudication_required", evidence_snippet="uncertain site")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ANNOTATION_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    imported = import_annotations([path], SPLITS, guide_version="guide_v1")
    assert agreement_summary(imported)["labels"] == {}
    review = agreement_summary(imported)["disagreements"][0]
    assert review["review_status"] == "unresolved"
    assert review["fields"] == {}
    assert review["annotations"]["A"]["decision_status"] == "adjudication_required"
    empty = agreement_summary([])
    assert empty["double_annotated_works"] == 0


def test_cli_gate_rejects_pending_guide(tmp_path: Path) -> None:
    guide = tmp_path / "pending_guide.md"
    review = tmp_path / "pending_review.md"
    guide.write_text("**Status:** pending owner review\n", encoding="utf-8")
    review.write_text("- Decision: Pending\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not approved"):
        require_frozen_guide(guide, review)


def _write_approved_pair(tmp_path: Path, owner: str, date: str) -> tuple[Path, Path]:
    guide = tmp_path / "guide.md"
    guide.write_text("**Status:** approved; frozen as `guide_v1`\n", encoding="utf-8")
    digest = hashlib.sha256(guide.read_bytes()).hexdigest().upper()
    review = tmp_path / "review.md"
    review.write_text(
        "\n".join(
            [
                "- Decision: Approve `guide_v1` as written",
                f"- Owner: {owner}",
                f"- Date: {date}",
                f"- Approved guide SHA-256: `{digest}`",
            ]
        ),
        encoding="utf-8",
    )
    return guide, review


def test_guide_gate_requires_real_owner_and_iso_approval_date(tmp_path: Path) -> None:
    guide, review = _write_approved_pair(tmp_path, "Scott Coffin", "2026-11-07")
    assert require_frozen_guide(guide, review) == "guide_v1"
    for owner, date, expected in [
        ("________", "2026-11-07", "name the approving owner"),
        ("TBD", "2026-11-07", "name the approving owner"),
        ("Scott Coffin", "__________", "ISO date"),
        ("Scott Coffin", "2026-11-7", "ISO date"),
    ]:
        guide, review = _write_approved_pair(tmp_path, owner, date)
        with pytest.raises(ValueError, match=expected):
            require_frozen_guide(guide, review)
