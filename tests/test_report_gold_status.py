"""Offline tests for scripts/report_gold_status.py (BQ-G1 gold-label status counts).

Every test writes tiny CSV fixtures under tmp_path. No test reads the real annotation sheet,
touches the network, or depends on the repository's git tags (git is stubbed unless a test
exercises the real call against a fake subprocess result).
"""

from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "report_gold_status.py"

ANNOTATION_FIELDS = (
    "work_id",
    "split",
    "sample_role",
    "year",
    "title",
    "abstract",
    "annotator",
    "guide_version",
    "plastic_related",
    "plastic_tier",
    "ca_sampled",
    "study_type",
    "domain_tags",
    "evidence_snippet",
    "evidence_source",
    "decision_status",
    "adjudicated_value",
    "adjudication_rationale",
)

# (work_id, sample_role, split) as in curation/splits_v2.csv: leak-check works carry split=test.
SPLIT_ROWS = [
    ("W1", "pool", "train"),
    ("W2", "pool", "train"),
    ("W3", "pool", "dev"),
    ("W4", "pool", "dev"),
    ("W5", "pool", "test"),
    ("W7", "pool", "test"),
    ("W6", "leak_test", "test"),
    ("W8", "leak_test", "test"),
]

SHEET_ROWS: list[dict[str, str]] = [
    {"work_id": "W1", "decision_status": "complete", "plastic_related": "true"},
    {"work_id": "W2", "decision_status": "adjudication_required"},
    {"work_id": "W3", "decision_status": "complete", "plastic_related": "false"},
    {"work_id": "W4"},
    {"work_id": "W5", "decision_status": "complete", "plastic_related": "true"},
    {"work_id": "W6", "decision_status": "complete", "plastic_related": "false"},
    {"work_id": "W7"},
    {"work_id": "W8"},
    # Labelled but absent from the split file: counted as labelled, not in any split.
    {"work_id": "W99", "decision_status": "complete", "plastic_related": "true"},
]


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("report_gold_status", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


MODULE = _load()
REAL_GIT_TAGS = MODULE._git_gold_tags


@pytest.fixture()
def mod(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """The script with ROOT pointed at tmp_path and git stubbed to report no tags."""
    monkeypatch.setattr(MODULE, "ROOT", tmp_path)
    monkeypatch.setattr(MODULE, "_git_gold_tags", lambda root: [])
    return MODULE


def _write_csv(
    path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, str]], encoding: str
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, restval="")
        writer.writeheader()
        writer.writerows(rows)


def _write_fixture(
    root: Path,
    sheet_rows: list[dict[str, str]] = SHEET_ROWS,
    split_rows: list[tuple[str, str, str]] = SPLIT_ROWS,
) -> tuple[Path, Path]:
    splits = root / "curation" / "splits_v2.csv"
    _write_csv(
        splits,
        ("work_id", "sample_role", "split"),
        [{"work_id": w, "sample_role": r, "split": s} for w, r, s in split_rows],
        encoding="utf-8",
    )
    annotations = root / "curation" / "annotations" / "annotations_SC.csv"
    # The real sheet is written with a UTF-8 byte-order mark; the fixture matches it.
    _write_csv(annotations, ANNOTATION_FIELDS, sheet_rows, encoding="utf-8-sig")
    return annotations, splits


def _status(mod: Any, tmp_path: Path, **kwargs: Any) -> dict[str, Any]:
    annotations, splits = _write_fixture(tmp_path, **kwargs)
    return mod.compute_status(annotations, splits, tmp_path)


def test_counts_rows_labelled_holds_and_unmatched(mod: Any, tmp_path: Path) -> None:
    status = _status(mod, tmp_path)
    assert status["annotation_rows"] == 9
    assert status["labelled_works"] == 5  # W1, W3, W5, W6, W99
    assert status["adjudication_holds"] == 1  # W2
    assert status["unlabelled_rows"] == 3  # W4, W7, W8
    assert status["rows_without_split_entry"] == 1  # W99


def test_split_join_counts_each_bucket_and_separates_leak_test(mod: Any, tmp_path: Path) -> None:
    status = _status(mod, tmp_path)
    assert status["per_split"] == {
        "train": {"labelled": 1, "total": 2},
        "dev": {"labelled": 1, "total": 2},
        "test": {"labelled": 1, "total": 2},
        "leak-test": {"labelled": 1, "total": 2},
    }


def test_evaluation_set_is_dev_and_test_pool_only(mod: Any, tmp_path: Path) -> None:
    status = _status(mod, tmp_path)
    # W3 (dev pool) and W5 (test pool) count; W6 is a labelled leak-test work and does not.
    assert status["evaluation_set"] == {"labelled": 2, "total": 4, "target": 150, "remaining": 148}


def test_remaining_never_goes_negative(
    mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "EVAL_TARGET", 1)
    assert _status(mod, tmp_path)["evaluation_set"]["remaining"] == 0


def test_plastic_related_counts_labelled_rows_only(mod: Any, tmp_path: Path) -> None:
    # Holds and unlabelled rows have blank plastic_related and are excluded.
    assert _status(mod, tmp_path)["plastic_related"] == {"false": 2, "true": 3}


def test_blank_relevance_on_labelled_row_is_reported(mod: Any, tmp_path: Path) -> None:
    rows = [{"work_id": "W1", "decision_status": "complete"}]
    status = _status(mod, tmp_path, sheet_rows=rows, split_rows=[("W1", "pool", "train")])
    assert status["plastic_related"] == {"(blank)": 1}


def test_empty_sheet_reports_zero_progress(mod: Any, tmp_path: Path, capsys: Any) -> None:
    annotations, splits = _write_fixture(tmp_path, sheet_rows=[{"work_id": "W1"}])
    assert mod.main(["--annotations", str(annotations), "--splits", str(splits)]) == 0
    out = capsys.readouterr().out
    assert "Unique works labelled (decision_status=complete): 0" in out
    assert "Evaluation set (dev+test pool): 0 of 4 labelled" in out
    assert "  (none)" in out


@pytest.mark.parametrize("missing", ["annotations", "splits"])
def test_missing_input_file_is_an_error(
    mod: Any, tmp_path: Path, capsys: Any, missing: str
) -> None:
    annotations, splits = _write_fixture(tmp_path)
    paths = {"annotations": annotations, "splits": splits}
    paths[missing] = tmp_path / "does_not_exist.csv"
    code = mod.main(["--annotations", str(paths["annotations"]), "--splits", str(paths["splits"])])
    assert code == 1
    assert "file not found" in capsys.readouterr().err


def test_duplicate_work_id_is_an_error(mod: Any, tmp_path: Path, capsys: Any) -> None:
    rows = [{"work_id": "W1"}, {"work_id": "W1", "decision_status": "complete"}]
    annotations, splits = _write_fixture(tmp_path, sheet_rows=rows)
    assert mod.main(["--annotations", str(annotations), "--splits", str(splits)]) == 1
    assert "listed more than once" in capsys.readouterr().err


def test_missing_required_column_is_an_error(mod: Any, tmp_path: Path) -> None:
    bad = tmp_path / "bad_splits.csv"
    bad.write_text("work_id,split\nW1,train\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing column"):
        mod.read_table(bad, mod.SPLIT_COLUMNS)


def test_byte_order_mark_is_stripped_from_the_header(mod: Any, tmp_path: Path) -> None:
    path = tmp_path / "splits.csv"
    path.write_text("work_id,sample_role,split\nW1,pool,train\n", encoding="utf-8-sig")
    assert mod.read_table(path, mod.SPLIT_COLUMNS) == [
        {"work_id": "W1", "sample_role": "pool", "split": "train"}
    ]


def test_json_mode_prints_the_counts(mod: Any, tmp_path: Path, capsys: Any) -> None:
    annotations, splits = _write_fixture(tmp_path)
    args = ["--json", "--annotations", str(annotations), "--splits", str(splits)]
    assert mod.main(args) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["annotations"] == "curation/annotations/annotations_SC.csv"
    assert data["labelled_works"] == 5
    assert data["evaluation_set"]["labelled"] == 2
    assert data["per_split"]["leak-test"] == {"labelled": 1, "total": 2}
    assert data["plastic_related"] == {"false": 2, "true": 3}


def test_output_is_deterministic(mod: Any, tmp_path: Path, capsys: Any) -> None:
    annotations, splits = _write_fixture(tmp_path)
    for flags in ([], ["--json"]):
        args = [*flags, "--annotations", str(annotations), "--splits", str(splits)]
        mod.main(args)
        first = capsys.readouterr().out
        mod.main(args)
        assert capsys.readouterr().out == first


def test_text_mode_reports_the_counts(mod: Any, tmp_path: Path, capsys: Any) -> None:
    annotations, splits = _write_fixture(tmp_path)
    assert mod.main(["--annotations", str(annotations), "--splits", str(splits)]) == 0
    out = capsys.readouterr().out
    assert "Unique works labelled (decision_status=complete): 5" in out
    assert "Evaluation set (dev+test pool): 2 of 4 labelled; target 150, remaining 148" in out
    assert "Gold release: no" in out


def test_no_release_without_file_or_tag(mod: Any, tmp_path: Path) -> None:
    release = mod.gold_release(tmp_path)
    assert release == {"status": "no", "files": [], "git_tags": [], "release_tags": []}


def test_gold_v_file_counts_as_release(mod: Any, tmp_path: Path) -> None:
    (tmp_path / "curation").mkdir()
    (tmp_path / "curation" / "gold_v1.csv").write_text("work_id\n", encoding="utf-8")
    release = mod.gold_release(tmp_path)
    assert release["status"] == "yes"
    assert release["files"] == ["gold_v1.csv"]


def test_only_gold_v_tags_count_as_release(
    mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "_git_gold_tags", lambda root: ["gold_notes", "gold_v1"])
    release = mod.gold_release(tmp_path)
    assert release == {
        "status": "yes",
        "files": [],
        "git_tags": ["gold_notes", "gold_v1"],
        "release_tags": ["gold_v1"],
    }


def test_non_release_gold_tag_alone_is_no(
    mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "_git_gold_tags", lambda root: ["gold_notes"])
    assert mod.gold_release(tmp_path)["status"] == "no"


def test_release_is_unknown_when_git_cannot_run(
    mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "_git_gold_tags", REAL_GIT_TAGS)

    def no_git(*args: Any, **kwargs: Any) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(mod.subprocess, "run", no_git)
    release = mod.gold_release(tmp_path)
    assert release["status"] == "unknown"
    assert release["git_tags"] is None
    assert release["release_tags"] is None


def test_release_is_unknown_when_git_fails(
    mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "_git_gold_tags", REAL_GIT_TAGS)
    failed = subprocess.CompletedProcess(args=[], returncode=128, stdout="", stderr="fatal")
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: failed)
    assert mod.gold_release(tmp_path)["status"] == "unknown"


def test_git_tag_output_is_sorted_and_blank_lines_ignored(
    mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(mod, "_git_gold_tags", REAL_GIT_TAGS)
    done = subprocess.CompletedProcess(args=[], returncode=0, stdout="gold_v1\n\ngold_a\n")
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: done)
    assert mod._git_gold_tags(tmp_path) == ["gold_a", "gold_v1"]
