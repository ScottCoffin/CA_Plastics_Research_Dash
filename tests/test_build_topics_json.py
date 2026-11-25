"""BQ-4.4: topic JSON files (topics_timeseries, topic_bursts) from synthetic analytics inputs."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "build_topics_json", ROOT / "scripts" / "build_topics_json.py"
)
bt = importlib.util.module_from_spec(SPEC)
sys.modules.setdefault("build_topics_json", bt)
SPEC.loader.exec_module(bt)

VARIANTS = ("all_sources", "owner_model_only", "rule_only")


def _tag(tag: str, complete: int, *, status: str = "labelled", partial: int = 0) -> dict:
    by_year = [
        {"year": 2024, "count": complete, "share": 0.1, "partial": False},
        {"year": 2026, "count": partial, "share": 0.05, "partial": True},
    ]
    return {
        "tag": tag,
        "label": tag.replace("_", " ").capitalize(),
        "approval": "approved",
        "status": status,
        "seed_concepts": 1,
        "total": complete + partial,
        "by_year": by_year,
        "sensitivity": {
            "all_sources": {"total": complete + partial, "by_year": by_year},
            "owner_model_only": {"total": 0, "by_year": []},
            "rule_only": {"total": complete + partial, "by_year": by_year},
        },
    }


def _pair(a: str, b: str, n_ab: int) -> dict:
    status = "sufficient" if n_ab >= 5 else "insufficient_data"
    return {
        "a": a,
        "b": b,
        "N": 100,
        "n_a": 20,
        "n_b": 20,
        "n_ab": n_ab,
        "jaccard": 0.1,
        "lift": 2.0,
        "phi": 0.2,
        "status": status,
    }


def make_inputs(tmp: Path, *, tags: list[dict], pairs: list[dict] | None = None) -> Path:
    analytics = tmp / "analytics"
    analytics.mkdir(parents=True, exist_ok=True)
    series = {
        "schema": "bq4-series-v1",
        "as_of": "2026-11-25",
        "last_complete_year": 2025,
        "labels_snapshot": {"content_sha256": "snap-sha"},
        "ca": {
            "plastic_related_by_year": [{"year": 2024, "count": 100}],
            "tags": tags,
            "tags_excluded": [{"tag": "culture_media_and_discourse", "reason": "experimental"}],
        },
        "lens": {
            "status": "no_lens_labels_yet",
            "message": "no lens labels yet",
            "caption": "A lens is counted only when the work itself uses the frame.",
            "framing_rule": "a lens is counted only when the work itself uses the frame",
            "series": [],
        },
    }
    rising = {
        "schema": "bq4-rising-v1",
        "as_of": "2026-11-25",
        "last_complete_year": 2025,
        "test": "cochran-armitage-normal-approximation",
        "alpha": 0.05,
        "window_years": [2023, 2024, 2025],
        "min_window_works": 10,
        "flagged": [tags[0]["tag"]] if tags else [],
        "tags_excluded": [],
        "tags": [
            {
                "tag": t["tag"],
                "label": t["label"],
                "flag": i == 0,
                "reasons_failed": [] if i == 0 else ["volume"],
                "trend": {"z": 2.5, "p": 0.01, "slope_sign": "positive"},
                "window_years": [2023, 2024, 2025],
                "window_count": 12,
                "total_complete_years": 12,
                "sensitivity": {v: "pass" for v in VARIANTS},
                "loio": {
                    "pass": True,
                    "worst_p": 0.02,
                    "worst_institution": "I1",
                    "institutions_tested": 4,
                },
            }
            for i, t in enumerate(tags)
        ],
    }
    all_pairs = pairs if pairs is not None else []
    cooc = {
        "schema": "bq4-cooc-v1",
        "as_of": "2026-11-25",
        "last_complete_year": 2025,
        "min_pair_n": 5,
        "windows": {"complete_years": {"from": None, "to": 2025}},
        "variants": {
            "all_sources": {
                "status": "testable",
                "windows": {"complete_years": {"N": 100, "pairs": all_pairs}},
            },
            "owner_model_only": {"status": "not_testable", "message": "none"},
            "rule_only": {"status": "testable", "windows": {}},
        },
    }
    for name, payload in (
        ("topic_series.json", series),
        ("rising_share.json", rising),
        ("tag_cooccurrence.json", cooc),
    ):
        (analytics / name).write_text(json.dumps(payload), encoding="utf-8")
    return analytics


def _run(tmp: Path, analytics: Path, *args: str) -> int:
    return bt.main(list(args), analytics_dir=analytics, out_dir=tmp / "out")


def _read(tmp: Path, name: str) -> dict:
    return json.loads((tmp / "out" / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("complete", "status", "expected"),
    [
        (9, "labelled", bt.INSUFFICIENT),
        (10, "labelled", bt.EXPERIMENTAL),
        (0, "labelled", bt.INSUFFICIENT),
        (500, "no_labels_yet", bt.INSUFFICIENT),
    ],
)
def test_accuracy_state_rules(complete: int, status: str, expected: str) -> None:
    assert bt.accuracy_state(_tag("t", complete, status=status)) == expected


def test_partial_years_do_not_count_toward_the_threshold() -> None:
    tag = _tag("t", 9, partial=50)
    assert bt.complete_works(tag) == 9
    assert bt.accuracy_state(tag) == bt.INSUFFICIENT


def test_validated_needs_a_gold_f1_for_the_tag() -> None:
    tag = _tag("t", 50)
    assert bt.accuracy_state(tag) == bt.EXPERIMENTAL
    assert bt.accuracy_state(tag, {"t": 0.9}) == bt.VALIDATED
    assert bt.accuracy_state(tag, {"other": 0.9}) == bt.EXPERIMENTAL


def test_timeseries_payload_carries_states_notice_and_lens(tmp_path: Path) -> None:
    tags = [_tag("alpha", 10), _tag("beta", 9), _tag("gamma", 40, status="no_labels_yet")]
    analytics = make_inputs(tmp_path, tags=tags, pairs=[_pair("alpha", "beta", 5)])
    assert _run(tmp_path, analytics) == 0
    payload = _read(tmp_path, "topics_timeseries.json")
    assert payload["schema"] == "bq4-v1"
    assert payload["notice"] == (
        "Tag labels come from rules; no tag has been validated against gold labels yet."
    )
    states = {t["tag"]: t["accuracy_state"] for t in payload["tags"]}
    assert states == {
        "alpha": "experimental",
        "beta": "insufficient data",
        "gamma": "insufficient data",
    }
    assert payload["lens"]["caption"].startswith("A lens is counted only")
    assert payload["lens"]["framing_rule"]
    pair = payload["cooccurrence"]["pairs"][0]
    assert pair["label_a"] == "Alpha" and pair["status"] == "sufficient"
    assert set(payload["tags"][0]["label_source_totals"]) == set(VARIANTS)


def test_bursts_payload_marks_kleinberg_not_computed(tmp_path: Path) -> None:
    analytics = make_inputs(tmp_path, tags=[_tag("alpha", 10), _tag("beta", 10)])
    assert _run(tmp_path, analytics) == 0
    bursts = _read(tmp_path, "topic_bursts.json")
    assert bursts["bursts"]["status"] == "not_computed"
    assert bursts["bursts"]["reason"]
    assert bursts["flagged"] == ["alpha"]
    flagged = {t["tag"]: t["flag"] for t in bursts["tags"]}
    assert flagged == {"alpha": True, "beta": False}


def test_version_block_records_input_hashes(tmp_path: Path) -> None:
    analytics = make_inputs(tmp_path, tags=[_tag("alpha", 10)])
    assert _run(tmp_path, analytics) == 0
    for name in bt.OUTPUT_FILES:
        version = _read(tmp_path, name)["version"]
        assert version["schema"] == "bq4-v1"
        assert set(version["inputs"]) == set(bt.INPUT_FILES)
        assert all(len(v["sha256"]) == 64 for v in version["inputs"].values())
        assert version["labels_snapshot_content_sha256"] == "snap-sha"


def test_build_is_deterministic_apart_from_generated_at(tmp_path: Path) -> None:
    analytics = make_inputs(tmp_path, tags=[_tag("alpha", 10), _tag("beta", 3)])
    assert _run(tmp_path, analytics) == 0
    first = (tmp_path / "out" / "topics_timeseries.json").read_bytes()
    assert _run(tmp_path, analytics) == 0
    second = (tmp_path / "out" / "topics_timeseries.json").read_bytes()
    assert json.loads(first)["generated_at"] and first.endswith(b"\n")
    assert _comparable(first) == _comparable(second)


def _comparable(raw: bytes) -> dict:
    payload = json.loads(raw)
    payload.pop("generated_at")
    return payload


def test_check_passes_on_fresh_output_and_fails_when_stale(tmp_path: Path) -> None:
    analytics = make_inputs(tmp_path, tags=[_tag("alpha", 10)])
    assert _run(tmp_path, analytics, "--check") == 1  # nothing written yet
    assert _run(tmp_path, analytics) == 0
    assert _run(tmp_path, analytics, "--check") == 0
    tags = [_tag("alpha", 11)]
    stale = make_inputs(tmp_path / "changed", tags=tags)
    assert _run(tmp_path, stale, "--check") == 1


def test_check_fails_when_an_output_file_is_missing(tmp_path: Path) -> None:
    analytics = make_inputs(tmp_path, tags=[_tag("alpha", 10)])
    assert _run(tmp_path, analytics) == 0
    (tmp_path / "out" / "topic_bursts.json").unlink()
    assert _run(tmp_path, analytics, "--check") == 1


def test_missing_analytics_inputs_name_the_build_commands(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "analytics"
    empty.mkdir()
    assert _run(tmp_path, empty) == 1
    message = capsys.readouterr().out
    assert "build_topic_series.py" in message
    assert "build_rising_share.py" in message
    assert "build_tag_cooccurrence.py" in message
    assert not (tmp_path / "out").exists()
