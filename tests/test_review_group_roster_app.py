"""Offline tests for scripts/review_group_roster_app.py (CG-ROSTER-QC).

The pure helpers are tested directly. One Streamlit AppTest run covers the one-case-per-screen
saves for both queues. Every file lives in tmp_path; the real curation files are never written.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "scripts" / "review_group_roster_app.py"
MERGE_HEADER = ["group_id_keep", "group_id_drop", "decided_at", "decision"]


def _load_app() -> ModuleType:
    spec = importlib.util.spec_from_file_location("review_group_roster_app", APP)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


app = _load_app()


def _rec(group_id: str, name: str, url: str | None, country: str = "NO") -> dict:
    return {"group_id": group_id, "name": name, "name_alt": [], "country": country, "url": url}


RECORDS = [
    _rec("cg_a", "Example Reef Society", "https://example-reef.no"),
    _rec("cg_b", "Example Lagoon Forum", "https://www.example-reef.no/forum"),
    _rec("cg_c", "Example Shore Group", "https://sites.google.com/view/shore"),
    _rec("cg_d", "Example Bay Club", "https://sites.google.com/view/bay"),
    _rec("cg_e", "USP", None),
    _rec("cg_f", "Example Coast ??", "https://example-coast.no"),
    _rec("cg_g", "https://example-tide.org", "https://example-tide.org"),
    _rec("cg_h", "example-wave.org", "https://example-wave.org"),
    _rec("cg_i", "Example Harbour Trust", "https://example-harbour.no"),
]
DUPES = [
    {
        "country": "NO",
        "reason": "same registrable domain",
        "group_id_a": "cg_a",
        "name_a": "Example Reef Society",
        "group_id_b": "cg_b",
        "name_b": "Example Lagoon Forum",
    },
    {
        "country": "NO",
        "reason": "same registrable domain",
        "group_id_a": "cg_c",
        "name_a": "Example Shore Group",
        "group_id_b": "cg_d",
        "name_b": "Example Bay Club",
    },
]


def _write_inputs(base: Path) -> dict[str, Path]:
    paths = {
        "roster": base / "roster.json",
        "dupes": base / "dupe_review.csv",
        "merges": base / "group_merges.csv",
        "corrections": base / "group_name_corrections.csv",
        "state": base / "state.json",
    }
    paths["roster"].write_text(json.dumps({"records": RECORDS}), encoding="utf-8")
    with paths["dupes"].open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(DUPES[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(DUPES)
    paths["merges"].write_text(",".join(MERGE_HEADER) + "\n", encoding="utf-8")
    paths["corrections"].write_text("group_id,name,submitted_at\n", encoding="utf-8")
    return paths


def _argv(paths: dict[str, Path]) -> list[str]:
    args = [str(APP)]
    for flag in ("roster", "dupes", "merges", "corrections", "state"):
        args += [f"--{flag}", str(paths[flag])]
    return args


def _button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


def test_suspect_reasons_cover_the_four_cases_and_leave_plain_names_alone() -> None:
    assert any("??" in r for r in app.suspect_reasons("Example Coast ??"))
    assert any("web address" in r for r in app.suspect_reasons("https://example-tide.org"))
    assert any("only a domain" in r for r in app.suspect_reasons("example-wave.org"))
    assert any("one case" in r for r in app.suspect_reasons("USP"))
    assert app.suspect_reasons("Example Harbour Trust") == []


def test_duplicate_queue_leaves_out_shared_hosts() -> None:
    cases = app.duplicate_candidates(RECORDS, DUPES)
    assert [c["key"] for c in cases] == ["dup:cg_a|cg_b"]


def test_a_decided_pair_leaves_the_queue_and_a_later_decision_replaces_it(tmp_path: Path) -> None:
    merges = tmp_path / "group_merges.csv"
    merges.write_text(",".join(MERGE_HEADER) + "\n", encoding="utf-8")
    app.record_merge(merges, "cg_a", "cg_b", "same", "2026-11-26T10:00:00Z")
    app.record_merge(merges, "cg_b", "cg_a", "different", "2026-11-26T11:00:00Z")
    rows = list(csv.DictReader(merges.open(encoding="utf-8", newline="")))
    assert len(rows) == 1
    assert rows[0]["decision"] == "different"
    assert list(csv.reader(merges.open(encoding="utf-8")))[0] == MERGE_HEADER
    cases = app.duplicate_candidates(RECORDS, DUPES)
    decided = app.admission.read_merges(merges)
    done = {c["key"] for c in cases if app.is_done(c, decided, set(), set())}
    assert done == {"dup:cg_a|cg_b"}
    assert app.pending_cases(cases, done, []) == []


def test_skipped_cases_move_to_the_end_of_the_queue() -> None:
    cases = app.suspect_candidates(RECORDS)
    first, second = cases[0]["key"], cases[1]["key"]
    pending = app.pending_cases(cases, set(), [first])
    assert pending[0]["key"] == second
    assert pending[-1]["key"] == first


def test_a_correction_is_appended_and_read_back(tmp_path: Path) -> None:
    corrections = tmp_path / "group_name_corrections.csv"
    corrections.write_text("group_id,name,submitted_at\n", encoding="utf-8")
    app.record_correction(corrections, "cg_f", "Example Coast", "2026-11-26T12:00:00Z")
    app.record_correction(corrections, "cg_i", "Example Harbour", "2026-11-26T12:05:00Z")
    assert app.admission.read_name_corrections(corrections) == {
        "cg_f": "Example Coast",
        "cg_i": "Example Harbour",
    }


def test_name_is_ok_is_remembered_in_the_state_file(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    assert app.read_state(state_path) == {"name_ok": [], "skipped": []}
    app.write_state(state_path, {"name_ok": ["cg_e"], "skipped": ["name:cg_f"]})
    assert app.read_state(state_path) == {"name_ok": ["cg_e"], "skipped": ["name:cg_f"]}


def test_duplicates_screen_saves_keep_b_and_then_reports_an_empty_queue(
    tmp_path: Path, monkeypatch
) -> None:
    paths = _write_inputs(tmp_path)
    monkeypatch.setattr(sys, "argv", _argv(paths))
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    _button(at, "Same, keep B").click().run()
    assert not at.exception
    rows = list(csv.DictReader(paths["merges"].open(encoding="utf-8", newline="")))
    assert [(r["group_id_keep"], r["group_id_drop"], r["decision"]) for r in rows] == [
        ("cg_b", "cg_a", "same")
    ]
    assert any("Nothing left" in s.value for s in at.success)


def test_suspect_names_screen_records_ok_and_a_corrected_name(tmp_path: Path, monkeypatch) -> None:
    paths = _write_inputs(tmp_path)
    monkeypatch.setattr(sys, "argv", _argv(paths))
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    at.sidebar.radio[0].set_value("Suspect names").run()
    assert not at.exception
    _button(at, "Name is OK").click().run()
    state = app.read_state(paths["state"])
    assert state["name_ok"] == ["cg_e"]
    at.text_input(key="corrected_name").input("Example Coast").run()
    _button(at, "Save corrected name").click().run()
    assert not at.exception
    assert app.admission.read_name_corrections(paths["corrections"]) == {"cg_f": "Example Coast"}


def test_missing_roster_is_reported_not_raised(tmp_path: Path, monkeypatch) -> None:
    paths = _write_inputs(tmp_path)
    paths["roster"].unlink()
    monkeypatch.setattr(sys, "argv", _argv(paths))
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception
    assert at.error
