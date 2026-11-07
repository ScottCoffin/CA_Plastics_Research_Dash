"""Deterministic synthetic acceptance check for S4.4 evaluation outputs."""

from __future__ import annotations

import json
from pathlib import Path

from atlas.nlp.eval import evaluate, render_markdown, write_calibration_plot

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    tags = ["occurrence_and_monitoring", "analytical_methods"]
    gold = []
    predictions = []
    for index in range(12):
        positive = index % 2 == 0
        gold.append(
            {
                "work_id": f"synthetic:{index:03d}",
                "split": "dev",
                "decision_status": "complete",
                "plastic_related": str(positive).lower(),
                "plastic_tier": "core" if positive else "",
                "ca_sampled": "yes" if positive else "no",
                "study_type": "field" if positive else "review",
                "domain_tags": [tags[index % 2]] if positive else [],
            }
        )
        # One deterministic relevance miss and one domain omission exercise error output.
        predicted_positive = positive and index != 0
        predictions.append(
            {
                "work_id": f"synthetic:{index:03d}",
                "plastic_related": str(predicted_positive).lower(),
                "plastic_tier": "core" if predicted_positive else "none",
                "ca_sampled": "yes" if positive else "no",
                "study_type": "field" if positive else "review",
                "domain_tags": ([tags[index % 2]] if positive and index != 2 else []),
                "plastic_related_probability": 0.8 if predicted_positive else 0.2,
            }
        )
    report = evaluate(
        gold,
        predictions,
        split="dev",
        model_version="dummy-v1",
        data_snapshot="synthetic-fixture-v1",
    )
    report_path = ROOT / "docs" / "EVAL_synthetic_v1.md"
    plot_path = ROOT / "docs" / "EVAL_synthetic_v1_calibration.png"
    write_calibration_plot(report, plot_path)
    report_path.write_text(render_markdown(report, plot_path.name), encoding="utf-8")
    json_path = ROOT / "docs" / "EVAL_synthetic_v1.json"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert report["n"] == 12 and len(report["errors"]) == 2
    assert report["metrics"]["plastic_related"]["f1"] is not None
    assert report["domain_tags"][tags[0]]["f1"] is not None
    print("S4.4 synthetic evaluation produced per-class metrics, calibration plot, and error table")


if __name__ == "__main__":
    main()
