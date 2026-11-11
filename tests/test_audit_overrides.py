"""AT-1 owner audit labels become work overrides (exclude / plastic_related)."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_audit_overrides.py"
AUDIT_HEADER = "work_id,title,review_label,reviewer\n"


def _runner():
    spec = importlib.util.spec_from_file_location("build_audit_overrides", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_labels_map_to_overrides_and_later_file_wins(tmp_path: Path) -> None:
    runner = _runner()
    v2 = tmp_path / "QUERY_AUDIT_REVIEW.csv"
    v3 = tmp_path / "QUERY_AUDIT_REVIEW_V3.csv"
    v2.write_text(
        AUDIT_HEADER
        + "https://openalex.org/W1,a,relevant,SC\n"
        + "W2,b,not_relevant,SC\n"
        + "W3,c,unsure,SC\n"
        + "W4,d,,\n",
        encoding="utf-8",
    )
    v3.write_text(AUDIT_HEADER + "W1,a,not_relevant,SC\n", encoding="utf-8")
    existing = tmp_path / "overrides.csv"
    existing.write_text(
        "work_id,field,value,reason,reviewed_by,reviewed_at\n"
        "W9,title,Fixed,manual fix,owner,2026-11-01\n",
        encoding="utf-8",
    )
    text = runner.render(existing, (v2, v3))
    rows = list(csv.DictReader(text.splitlines()))
    assert [(r["work_id"], r["field"], r["value"]) for r in rows] == [
        ("W9", "title", "Fixed"),
        ("W1", "exclude", "true"),
        ("W2", "exclude", "true"),
    ]
    assert rows[1]["reason"].startswith(runner.MARKER)
    assert rows[1]["reviewed_at"] == "2026-11-11"
    # Idempotent: regenerating over its own output changes nothing.
    existing.write_text(text, encoding="utf-8")
    assert runner.render(existing, (v2, v3)) == text


def test_committed_overrides_are_current() -> None:
    runner = _runner()
    path = ROOT / "curation" / "overrides_works.csv"
    audit = tuple(ROOT / p for p in runner.AUDIT_FILES)
    assert path.read_text(encoding="utf-8") == runner.render(path, audit)
