from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "build_methods_flow_json", REPO / "scripts" / "build_methods_flow_json.py"
)
flow_build = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(flow_build)

OUTPUT = REPO / "site" / "data" / "methods_flow.json"


def _card() -> dict:
    return json.loads(flow_build.newest_card_path().read_text(encoding="utf-8"))


def _committed() -> dict:
    return json.loads(OUTPUT.read_text(encoding="utf-8"))


def test_committed_flow_is_not_stale() -> None:
    text = flow_build.build_from_disk()
    assert OUTPUT.read_bytes() == text.encode("utf-8")
    assert text.endswith("\n")


def test_every_numeric_step_matches_methods_card() -> None:
    flow = _card()["flow"]
    steps = [step for stage in _committed()["stages"] for step in stage["steps"]]
    assert steps, "expected numeric steps"
    for step in steps:
        keys = [key for key, entry in flow.items() if entry["value"] == step["value"]]
        assert keys, f"step {step['label']!r} value is not in the methods card"
        assert step["source"] == flow[keys[0]]["source"]
    by_source = {entry["source"]: entry["value"] for entry in flow.values()}
    for step in steps:
        assert by_source[step["source"]] == step["value"]


def test_stage_order_and_not_performed_stages() -> None:
    stages = _committed()["stages"]
    assert [stage["stage"] for stage in stages] == [
        "Searching",
        "Screening",
        "Coding / meta-data extraction",
        "Data extraction",
        "Critical appraisal",
        "Synthesis",
    ]
    not_performed = [stage["stage"] for stage in stages if stage["status"] == "not performed"]
    assert not_performed == ["Data extraction", "Critical appraisal"]
    for stage in stages:
        if stage["status"] == "not performed":
            assert stage["steps"] == []


def test_counts_never_increase_from_searching_through_screening() -> None:
    stages = _committed()["stages"]
    counts = [step["value"] for stage in stages[:2] for step in stage["steps"]]
    assert len(counts) == 5
    assert all(later <= earlier for earlier, later in zip(counts, counts[1:]))


def test_release_metadata_matches_card() -> None:
    card = _card()
    payload = _committed()
    assert payload["schema_version"] == "em6.v1"
    assert payload["release_date"] == card["release_date"]
    assert payload["query_version"] == card["query"]["version"]
    assert payload["template"] == {
        "name": "ROSES flow diagram for systematic maps",
        "licence": "CC BY 4.0",
    }


def test_build_rejects_card_without_flow_counts() -> None:
    card = _card()
    del card["flow"]["raw_records"]
    with pytest.raises(ValueError, match="raw_records"):
        flow_build.build_payload(card)


def test_check_mode_exits_one_when_stale(tmp_path: Path) -> None:
    stale = tmp_path / "methods_flow.json"
    stale.write_text("{}\n", encoding="utf-8")
    assert flow_build.main(["--check", "--output", str(stale)]) == 1
    assert flow_build.main(["--check"]) == 0
