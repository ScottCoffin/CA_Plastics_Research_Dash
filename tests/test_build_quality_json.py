"""Tests for BQ-1.4 (build_quality_json.py) and BQ-1.1b (build_quality_predictions.py).

Synthetic inputs only. The payload tests build from in-memory coverage and reports; the committed
files are checked with ``--check`` (curation files only, no ignored ``data/`` input).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


payload_mod = _load("build_quality_json")
predictions_mod = _load("build_quality_predictions")
NO_ESTIMATE = "No validated estimate yet"
GENERATED = "2026-11-25T00:00:00+00:00"
INCOMPLETE = {
    "ca_labelled": 38,
    "ca_designed": 500,
    "global_labelled": 0,
    "global_drawn": 263,
    "predictions_missing": 0,
}


def _ok_report() -> dict:
    estimand = {
        "status": "ok",
        "point": 0.91,
        "interval": [0.85, 0.95],
        "n": 480,
        "flags": [],
        "design_notes": ["design note"],
    }
    return {"status": "ok", "estimands": {e: dict(estimand) for e in payload_mod.ESTIMAND_TEXT}}


def _walk_numbers(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in {"point", "interval", "se", "upper_bound"} and value is not None:
                yield key
            yield from _walk_numbers(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_numbers(item)


@pytest.mark.parametrize("scope", ["california", "global"])
def test_incomplete_gold_publishes_no_numbers(scope):
    payload = payload_mod.public_payload(scope, INCOMPLETE, generated_at=GENERATED)
    assert payload["status"] == "no_validated_estimate"
    assert payload["checkpoint"] is None
    assert list(_walk_numbers(payload)) == []
    for entry in payload["estimands"].values():
        assert entry["status"] == "no_validated_estimate"
        assert entry["display"] == NO_ESTIMATE
        assert "point" not in entry and "interval" not in entry


def test_labels_so_far_are_stated_in_plain_words():
    ca = payload_mod.public_payload("california", INCOMPLETE, generated_at=GENERATED)
    gl = payload_mod.public_payload("global", INCOMPLETE, generated_at=GENERATED)
    assert ca["labels"]["text"] == "38 of 500 California works labelled"
    assert gl["labels"]["text"] == "0 of 263 global works labelled"


def test_report_with_incomplete_status_still_publishes_no_numbers():
    report = {"status": "incomplete_gold", "estimands": {"E1": {"status": "incomplete_gold"}}}
    payload = payload_mod.public_payload(
        "california", INCOMPLETE, generated_at=GENERATED, report=report
    )
    assert list(_walk_numbers(payload)) == []
    assert payload["estimands"]["E1"]["status"] == "no_validated_estimate"


def test_numbers_appear_only_for_a_final_checkpoint_with_ok_status():
    payload = payload_mod.public_payload(
        "california", INCOMPLETE, generated_at=GENERATED, report=_ok_report()
    )
    entry = payload["estimands"]["E1"]
    assert entry["status"] == "ok"
    assert entry["point"] == 0.91
    assert entry["interval"] == [0.85, 0.95]
    assert entry["note"] == "design note"
    assert payload["status"] == "ok"
    # Global-only estimands are still gated by the scope they belong to.
    assert set(payload["estimands"]) == {"E1", "E1s", "E1l", "E2", "E3", "E4"}


def test_build_payloads_is_silent_without_a_final_checkpoint():
    payloads = payload_mod.build_payloads(GENERATED)
    assert set(payloads) == {"california", "global"}
    for payload in payloads.values():
        assert list(_walk_numbers(payload)) == []
        assert payload["checkpoint"] is None


def test_committed_payloads_are_current():
    assert payload_mod.main(["--check"]) == 0


def test_ca_prediction_rows_prefer_the_published_label_and_fall_back_to_the_rule():
    labels = {
        "W1": {
            "plastic_related": True,
            "plastic_tier": "core",
            "domain_tags": ["a"],
            "label_source": "rule",
        },
        "W2": {
            "plastic_related": True,
            "plastic_tier": "core",
            "domain_tags": [],
            "label_source": "rule",
        },
    }
    published = {
        "W1": {
            "plastic_related": False,
            "plastic_tier": "",
            "domain_tags": ["x", "y"],
            "study_type": "review",
        }
    }
    rows = predictions_mod.ca_prediction_rows(["W1", "W2"], labels, published)
    by_id = {r["work_id"]: r for r in rows}
    assert by_id["W1"]["pred_plastic_related"] == "false"
    assert by_id["W1"]["pred_domain_tags"] == "x|y"
    assert by_id["W1"]["pred_study_type"] == "review"
    assert by_id["W1"]["label_source"] == "rule"
    assert by_id["W2"]["pred_plastic_related"] == "true"
    assert by_id["W2"]["label_source"] == "unpublished_rule"
    assert set(rows[0]) == set(predictions_mod.COLUMNS)


def test_global_prediction_rows_treat_every_query_hit_as_predicted_true():
    frame = [{"work_id": "G1", "band": "low", "theme_group": "other"}]
    rows = predictions_mod.global_prediction_rows(frame, {"G1": "en"})
    assert rows == [
        {
            "work_id": "G1",
            "pred_plastic_related": "true",
            "pred_plastic_tier": "",
            "pred_analytic_lens": "",
            "pred_domain_tags": "",
            "pred_study_type": "",
            "pred_band": "low",
            "label_source": "query",
            "theme_group": "other",
            "language": "en",
        }
    ]


def test_predictions_csv_round_trip(tmp_path):
    path = tmp_path / "p.csv"
    predictions_mod._write_csv(path, [{k: "" for k in predictions_mod.COLUMNS}])
    text = path.read_text(encoding="utf-8").splitlines()
    assert text[0].split(",") == list(predictions_mod.COLUMNS)
    assert len(text) == 2
