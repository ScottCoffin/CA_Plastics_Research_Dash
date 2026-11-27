"""Public roster QC candidates (AMB-ROSTER-QC): pairs, suspect names, the builder and the app."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from atlas.groups import roster_qc

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_roster_qc.py"
APP = ROOT / "scripts" / "review_group_roster_app.py"
COMMITTED = ROOT / "site" / "data" / "global" / "groups" / "roster_qc.json"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


script = _load("build_roster_qc", SCRIPT)


def _rec(group_id: str, name: str, url: str | None, country: str = "NO") -> dict:
    return {"group_id": group_id, "name": name, "name_alt": [], "country": country, "url": url}


PAIR_RECORDS = [
    _rec("cg_01", "Example Reef Society", "https://example-reef.no"),
    _rec("cg_02", "Reef Society Trust", "https://www.example-reef.no/forum"),
    _rec("cg_03", "Lagoon Research Alliance", "https://lagoon-a.no"),
    _rec("cg_04", "Lagoon Research Alliance", "https://lagoon-b.no"),
    _rec("cg_05", "Lagoon Research Alliance", "https://lagoon-c.se", country="SE"),
    _rec("cg_06", "Coastal Plastics Forum", "https://www.facebook.com/coastal"),
    _rec("cg_07", "Marine Debris Network", "https://facebook.com/marine"),
]

SUSPECT_RECORDS = [
    _rec("sus_01", "Example Coast ??", "https://example-coast.no"),
    _rec("sus_02", "Broken � Name", "https://broken.no"),
    _rec("sus_03", "Ocean`s Trust", "https://ocean.no"),
    _rec("sus_04", "https://example-tide.org", "https://tide.no"),
    _rec("sus_05", "example-wave.org", "https://wave.no"),
    _rec("sus_06", "USP", "https://usp.no"),
    _rec("sus_07", "Example Harbour Trust", "https://harbour.no"),
    _rec("sus_08", "Example Corrected ??", "https://corrected.no"),
]


def _roster(records: list[dict], **extra: str) -> dict:
    return {"schema": "x", "retrieved_at": "2026-11-20", "records": records, **extra}


def _merge(keep: str, drop: str, decision: str) -> dict[str, str]:
    return {"group_id_keep": keep, "group_id_drop": drop, "decision": decision}


def test_pairs_cover_same_domain_similar_name_and_exclusions() -> None:
    doc = roster_qc.build_roster_qc(_roster(PAIR_RECORDS), [], {})
    assert doc["pairs"] == [
        {"a": "cg_01", "b": "cg_02", "reason": "same_domain"},
        {"a": "cg_03", "b": "cg_04", "reason": "similar_name"},
    ]


def test_pairs_are_ordered_and_sorted_whatever_the_input_order() -> None:
    doc = roster_qc.build_roster_qc(_roster(list(reversed(PAIR_RECORDS))), [], {})
    assert all(p["a"] < p["b"] for p in doc["pairs"])
    assert doc["pairs"] == sorted(doc["pairs"], key=lambda p: (p["a"], p["b"]))


def test_decided_pairs_are_suppressed_for_same_and_different() -> None:
    merges = [_merge("cg_04", "cg_03", "different"), _merge("cg_02", "cg_01", "same")]
    doc = roster_qc.build_roster_qc(_roster(PAIR_RECORDS), merges, {})
    assert doc["pairs"] == []


def test_suspect_codes_one_per_rule() -> None:
    assert roster_qc.suspect_codes("Example Coast ??") == ["double_question_mark"]
    assert roster_qc.suspect_codes("Broken � Name") == ["broken_character"]
    assert roster_qc.suspect_codes("Ocean`s Trust") == ["backtick"]
    assert roster_qc.suspect_codes("https://example-tide.org") == ["web_address"]
    assert roster_qc.suspect_codes("www.example-tide.org") == ["web_address"]
    assert roster_qc.suspect_codes("example-wave.org") == ["domain_only"]
    assert roster_qc.suspect_codes("USP") == ["short_one_case"]
    assert roster_qc.suspect_codes("Example Harbour Trust") == []


def test_suspect_names_list_codes_and_skip_corrected_ids() -> None:
    doc = roster_qc.build_roster_qc(
        _roster(SUSPECT_RECORDS), [], {"sus_08": "Example Coast Corrected"}
    )
    assert doc["suspect_names"] == [
        {"group_id": "sus_01", "reasons": ["double_question_mark"]},
        {"group_id": "sus_02", "reasons": ["broken_character"]},
        {"group_id": "sus_03", "reasons": ["backtick"]},
        {"group_id": "sus_04", "reasons": ["web_address"]},
        {"group_id": "sus_05", "reasons": ["domain_only"]},
        {"group_id": "sus_06", "reasons": ["short_one_case"]},
    ]


def test_output_is_deterministic_and_carries_no_names_or_urls() -> None:
    roster = _roster(PAIR_RECORDS + SUSPECT_RECORDS)
    corrections = {"sus_08": "Example Coast Corrected"}
    first = roster_qc.build_roster_qc(roster, [_merge("cg_04", "cg_03", "different")], corrections)
    second = roster_qc.build_roster_qc(roster, [_merge("cg_04", "cg_03", "different")], corrections)
    assert first == second
    assert set(first) == {"schema", "generated_from", "pairs", "suspect_names"}
    assert first["schema"] == "cg-roster-qc-v1"
    text = json.dumps(first, sort_keys=True)
    for record in PAIR_RECORDS + SUSPECT_RECORDS:
        assert record["name"] not in text
        assert record["url"] not in text
    assert "Example Corrected" not in text


def test_generated_from_uses_generated_at_when_present() -> None:
    doc = roster_qc.build_roster_qc(_roster([]), [], {})
    assert doc["generated_from"] == "2026-11-20"
    doc = roster_qc.build_roster_qc(_roster([], generated_at="2026-11-21"), [], {})
    assert doc["generated_from"] == "2026-11-21"


def _write_roster(path: Path, records: list[dict]) -> Path:
    path.write_text(json.dumps(_roster(records)), encoding="utf-8")
    return path


def test_script_check_fails_then_passes_after_write(tmp_path: Path, monkeypatch) -> None:
    roster = _write_roster(tmp_path / "roster.json", PAIR_RECORDS)
    output = tmp_path / "roster_qc.json"
    curation = tmp_path / "curation"
    curation.mkdir()
    monkeypatch.setattr(script, "ROSTER_PATH", roster)
    monkeypatch.setattr(script, "OUTPUT_PATH", output)

    assert script.main(["--check", "--curation-dir", str(curation)]) == 1
    assert script.main(["--curation-dir", str(curation)]) == 0
    assert script.main(["--check", "--curation-dir", str(curation)]) == 0

    output.write_bytes(output.read_bytes() + b" ")
    assert script.main(["--check", "--curation-dir", str(curation)]) == 1


def test_script_reads_merges_and_corrections_from_curation_dir(tmp_path: Path) -> None:
    curation = tmp_path / "curation"
    curation.mkdir()
    (curation / "group_merges.csv").write_text(
        "group_id_keep,group_id_drop,decided_at,decision\ncg_04,cg_03,2026-11-20,different\n",
        encoding="utf-8",
    )
    (curation / "group_name_corrections.csv").write_text(
        "group_id,name,submitted_at\nsus_01,Example Coast,2026-11-20\n", encoding="utf-8"
    )
    roster = _write_roster(tmp_path / "roster.json", PAIR_RECORDS + SUSPECT_RECORDS)
    doc = json.loads(script.render(curation, roster).decode("utf-8"))
    assert all(p["a"] != "cg_03" for p in doc["pairs"])
    assert "sus_01" not in [s["group_id"] for s in doc["suspect_names"]]


def test_committed_file_passes_check_with_committed_curation(tmp_path: Path) -> None:
    if not COMMITTED.exists():
        pytest.skip("roster_qc.json is not in the worktree")
    curation = tmp_path / "curation"
    curation.mkdir()
    for name in ("group_merges.csv", "group_name_corrections.csv"):
        completed = subprocess.run(
            ["git", "show", f"HEAD:curation/{name}"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            pytest.skip("git HEAD is not available")
        (curation / name).write_bytes(completed.stdout)
    assert script.main(["--check", "--curation-dir", str(curation)]) == 0


def _load_app() -> ModuleType:
    pytest.importorskip("streamlit")
    return _load("review_group_roster_app", APP)


def test_review_app_renders_the_same_sentence_for_each_code() -> None:
    app = _load_app()
    assert set(app.SUSPECT_SENTENCES) == set(roster_qc.SUSPECT_CODES)
    assert app.suspect_reasons("Example Coast ??") == ['the name contains "??"']
    assert app.suspect_reasons("Broken � Name") == ["the name has a broken character (�)"]
    assert app.suspect_reasons("Ocean`s Trust") == ["the name uses a backtick (`) as an apostrophe"]
    assert app.suspect_reasons("https://example-tide.org") == ["a web address is used as the name"]
    assert app.suspect_reasons("example-wave.org") == ["the name is only a domain"]
    assert app.suspect_reasons("USP") == ["a short name in one case"]
    assert app.suspect_reasons("Example Harbour Trust") == []
