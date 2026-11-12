from __future__ import annotations

import pytest

from atlas.nlp.eval import evaluate, render_markdown, write_calibration_plot


def _fixture():
    gold, predictions = [], []
    for index, positive in enumerate((True, False, True)):
        work_id = f"w{index}"
        gold.append(
            {
                "work_id": work_id,
                "split": "dev",
                "decision_status": "complete",
                "plastic_related": str(positive).lower(),
                "plastic_tier": "core" if positive else "",
                "ca_sampled": "yes" if positive else "no",
                "study_type": "field" if positive else "review",
                "domain_tags": ["occurrence_and_monitoring"] if positive else [],
            }
        )
        predictions.append(
            {
                "work_id": work_id,
                "plastic_related": str(positive).lower(),
                "plastic_tier": "core" if positive else "none",
                "ca_sampled": "yes" if positive else "no",
                "study_type": "field" if positive else "review",
                "domain_tags": ["occurrence_and_monitoring"] if positive else [],
                "plastic_related_probability": 0.8 if positive else 0.2,
            }
        )
    return gold, predictions


def test_evaluation_and_reliability_plot(tmp_path):
    gold, predictions = _fixture()
    report = evaluate(gold, predictions, split="dev", model_version="m1", data_snapshot="s1")
    assert report["metrics"]["plastic_related"]["f1"] == 1
    assert report["metrics"]["ca_sampled"]["classes"]["partial"]["f1"] is None
    assert report["domain_tags"]["occurrence_and_monitoring"]["f1"] == 1
    assert report["errors"] == []
    plot = tmp_path / "calibration.png"
    write_calibration_plot(report, plot)
    assert plot.stat().st_size > 0
    assert "undefined" in render_markdown(report, plot.name)


def test_held_out_requires_explicit_final_evaluation():
    gold, predictions = _fixture()
    gold = [dict(row, split="test") for row in gold]
    with pytest.raises(ValueError, match="allow_test"):
        evaluate(gold, predictions, split="test", model_version="m1", data_snapshot="s1")
    assert (
        evaluate(
            gold, predictions, split="test", model_version="m1", data_snapshot="s1", allow_test=True
        )["split"]
        == "test"
    )


def test_rejects_unresolved_duplicate_and_mismatched_prediction_rows():
    gold, predictions = _fixture()
    with pytest.raises(ValueError, match="unresolved"):
        evaluate(
            [dict(gold[0], decision_status="adjudication_required")],
            predictions[:1],
            split="dev",
            model_version="m1",
            data_snapshot="s1",
        )
    with pytest.raises(ValueError, match="duplicate canonical"):
        evaluate(gold + [gold[0]], predictions, split="dev", model_version="m1", data_snapshot="s1")
    with pytest.raises(ValueError, match="exactly match"):
        evaluate(gold, predictions[:-1], split="dev", model_version="m1", data_snapshot="s1")


def test_rejects_invalid_probability_and_requires_provenance():
    gold, predictions = _fixture()
    predictions[0]["plastic_related_probability"] = 1.1
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        evaluate(gold, predictions, split="dev", model_version="m1", data_snapshot="s1")
    with pytest.raises(ValueError, match="provenance"):
        evaluate(gold, predictions, split="dev", model_version="", data_snapshot="s1")


def test_error_table_includes_study_type_mismatches():
    gold, predictions = _fixture()
    predictions[0]["study_type"] = "review"
    report = evaluate(gold, predictions, split="dev", model_version="m1", data_snapshot="s1")
    assert report["errors"][0]["fields"] == ["study_type"]


def test_gold_requires_explicit_complete_adjudication_status():
    gold, predictions = _fixture()
    del gold[0]["decision_status"]
    with pytest.raises(ValueError, match="unresolved"):
        evaluate(gold, predictions, split="dev", model_version="m1", data_snapshot="s1")


def test_rejects_duplicate_id_across_splits_before_filtering():
    gold, predictions = _fixture()
    gold.append(dict(gold[0], split="train"))
    with pytest.raises(ValueError, match="multiple splits"):
        evaluate(gold, predictions, split="dev", model_version="m1", data_snapshot="s1")


@pytest.mark.parametrize("work_id", [None, "", "   ", " w0", 12])
def test_rejects_null_blank_and_noncanonical_gold_ids(work_id):
    gold, predictions = _fixture()
    gold[0]["work_id"] = work_id
    with pytest.raises(ValueError, match="gold work_id"):
        evaluate(gold, predictions, split="dev", model_version="m1", data_snapshot="s1")


def test_negative_gold_may_leave_ca_sampled_and_study_type_blank():
    gold, predictions = _fixture()
    gold[1]["ca_sampled"] = gold[1]["study_type"] = ""
    # Predictions on a negative gold work are not scored for these fields.
    predictions[1]["ca_sampled"], predictions[1]["study_type"] = "yes", "anything"
    report = evaluate(gold, predictions, split="dev", model_version="m1", data_snapshot="s1")
    assert report["metrics"]["ca_sampled"]["precision"] == 1
    assert report["metrics"]["ca_sampled"]["classes"]["yes"]["support"] == 2
    assert not report["errors"]


def test_positive_gold_still_requires_study_type():
    gold, predictions = _fixture()
    gold[0]["study_type"] = ""
    with pytest.raises(ValueError, match="missing study_type"):
        evaluate(gold, predictions, split="dev", model_version="m1", data_snapshot="s1")
