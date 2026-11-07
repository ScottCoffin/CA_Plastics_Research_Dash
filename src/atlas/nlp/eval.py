"""Reproducible metrics for canonical, adjudicated gold rows and model predictions."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from atlas.nlp.annotation import DOMAIN_TAGS

THRESHOLDS = {
    "ca_sampled_yes_precision": 0.85,
    "ca_sampled_yes_recall": 0.80,
    "plastic_related_f1": 0.90,
    "domain_tag_f1": 0.70,
    "gazetteer_gate_recall": 0.95,
}
CLASSES = {
    "plastic_related": ("false", "true"),
    "plastic_tier": ("core", "chemicals-in-plastics", "none"),
    "ca_sampled": ("yes", "partial", "no", "unclear"),
    # study_type is intentionally open vocabulary in the annotation schema.
}


def _scores(tp: int, fp: int, fn: int, support: int) -> dict[str, Any]:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision and recall
        else (0.0 if precision == 0 or recall == 0 else None)
    )
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "support": support,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def _class_metrics(gold: list[Any], pred: list[Any], classes: tuple[str, ...]) -> dict[str, Any]:
    result = {}
    for label in classes:
        tp = sum(g == label and p == label for g, p in zip(gold, pred, strict=True))
        fp = sum(g != label and p == label for g, p in zip(gold, pred, strict=True))
        fn = sum(g == label and p != label for g, p in zip(gold, pred, strict=True))
        result[label] = _scores(tp, fp, fn, sum(g == label for g in gold))
    return result


def _normalize_gold(rows: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    seen: dict[str, str] = {}
    for row in rows:
        raw_id = row.get("work_id")
        if not isinstance(raw_id, str) or not raw_id or raw_id != raw_id.strip():
            raise ValueError(f"missing, blank, or noncanonical gold work_id: {raw_id!r}")
        if raw_id in seen:
            if seen[raw_id] != row.get("split"):
                raise ValueError(f"gold work_id occurs in multiple splits: {raw_id}")
            raise ValueError(f"duplicate canonical gold work_id: {raw_id!r}")
        seen[raw_id] = row.get("split")

    chosen = [row for row in rows if row.get("split") == split]
    if not chosen:
        raise ValueError(f"no gold rows for split {split!r}")
    normalized = []
    for row in chosen:
        work_id = row["work_id"]
        if row.get("decision_status") != "complete":
            raise ValueError(f"unresolved gold row: {work_id}")
        item = dict(row)
        if item.get("plastic_related") not in {True, False, "true", "false"}:
            raise ValueError(f"invalid plastic_related gold label for {work_id}")
        item["plastic_related"] = str(item["plastic_related"]).lower()
        for field, allowed in CLASSES.items():
            value = item.get(field)
            if (
                field == "plastic_tier"
                and item["plastic_related"] == "false"
                and value in (None, "")
            ):
                item[field] = "none"
                continue
            if value not in allowed:
                raise ValueError(f"invalid {field} gold label for {work_id}: {value!r}")
        if (item["plastic_related"] == "true") == (item["plastic_tier"] == "none"):
            raise ValueError(f"plastic_related and plastic_tier conflict for {work_id}")
        if not isinstance(item.get("study_type"), str) or not item["study_type"].strip():
            raise ValueError(f"missing study_type gold label for {work_id}")
        tags = item.get("domain_tags", [])
        if isinstance(tags, str):
            tags = [tag for tag in tags.split("|") if tag]
        if not isinstance(tags, list) or set(tags) - set(DOMAIN_TAGS):
            raise ValueError(f"invalid domain_tags for {work_id}")
        item["domain_tags"] = sorted(set(tags))
        item["work_id"] = work_id
        normalized.append(item)
    return normalized


def evaluate(
    gold_rows: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    *,
    split: str,
    model_version: str,
    data_snapshot: str,
    allow_test: bool = False,
) -> dict[str, Any]:
    """Evaluate one split; test requires deliberate opt-in and is never tuned here."""
    if split not in {"train", "dev", "test"}:
        raise ValueError("split must be train, dev, or test")
    if split == "test" and not allow_test:
        raise ValueError("test evaluation requires allow_test=True")
    if not model_version.strip() or not data_snapshot.strip():
        raise ValueError("model_version and data_snapshot provenance are required")
    gold = _normalize_gold(gold_rows, split)
    pred_by_id: dict[str, dict[str, Any]] = {}
    for row in predictions:
        work_id = str(row.get("work_id", ""))
        if not work_id or work_id in pred_by_id:
            raise ValueError(f"missing or duplicate prediction work_id: {work_id!r}")
        pred_by_id[work_id] = dict(row)
    gold_ids = {row["work_id"] for row in gold}
    if set(pred_by_id) != gold_ids:
        raise ValueError("prediction IDs must exactly match selected gold split")
    study_types = tuple(sorted({str(row["study_type"]) for row in gold}))
    metric_classes = {**CLASSES, "study_type": study_types}
    for row in pred_by_id.values():
        for field, allowed in metric_classes.items():
            if row.get(field) not in allowed:
                raise ValueError(f"invalid predicted {field} for {row['work_id']}")
        if (row["plastic_related"] == "true") == (row["plastic_tier"] == "none"):
            raise ValueError(f"plastic_related and plastic_tier conflict for {row['work_id']}")
        tags = row.get("domain_tags", [])
        if isinstance(tags, str):
            tags = [tag for tag in tags.split("|") if tag]
        if not isinstance(tags, list) or set(tags) - set(DOMAIN_TAGS):
            raise ValueError(f"invalid predicted domain_tags for {row['work_id']}")
        row["domain_tags"] = sorted(set(tags))
    gold_by_id = {row["work_id"]: row for row in gold}
    ids = sorted(gold_ids)
    metrics: dict[str, Any] = {}
    for field in metric_classes:
        gv = [gold_by_id[i][field] for i in ids]
        pv = [pred_by_id[i][field] for i in ids]
        metrics[field] = {"classes": _class_metrics(gv, pv, metric_classes[field])}
        positive = (
            "true" if field == "plastic_related" else "yes" if field == "ca_sampled" else None
        )
        if positive:
            s = metrics[field]["classes"][positive]
            metrics[field]["positive_class"] = positive
            metrics[field]["precision"] = s["precision"]
            metrics[field]["recall"] = s["recall"]
            metrics[field]["f1"] = s["f1"]
    tags_report = {}
    for tag in DOMAIN_TAGS:
        gv = [tag in gold_by_id[i]["domain_tags"] for i in ids]
        pv = [tag in pred_by_id[i]["domain_tags"] for i in ids]
        tags_report[tag] = _scores(
            sum(g and p for g, p in zip(gv, pv, strict=True)),
            sum(not g and p for g, p in zip(gv, pv, strict=True)),
            sum(g and not p for g, p in zip(gv, pv, strict=True)),
            sum(gv),
        )
    errors = []
    for work_id in ids:
        g, p = gold_by_id[work_id], pred_by_id[work_id]
        fields = [f for f in metric_classes if g[f] != p[f]]
        tag_fp = sorted(set(p["domain_tags"]) - set(g["domain_tags"]))
        tag_fn = sorted(set(g["domain_tags"]) - set(p["domain_tags"]))
        if fields or tag_fp or tag_fn:
            errors.append(
                {
                    "work_id": work_id,
                    "fields": fields,
                    "domain_tag_fp": tag_fp,
                    "domain_tag_fn": tag_fn,
                    "split": split,
                }
            )
    probabilities = [pred_by_id[i].get("plastic_related_probability") for i in ids]
    calibration = None
    if any(value is not None for value in probabilities):
        if any(
            value is None
            or isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 <= value <= 1
            for value in probabilities
        ):
            raise ValueError(
                "plastic_related_probability must be present and in [0, 1] for every row"
            )
        bins = []
        for lower in [i / 10 for i in range(10)]:
            members = [
                i
                for i, value in enumerate(probabilities)
                if lower <= value < lower + 0.1 or (lower == 0.9 and value == 1)
            ]
            if members:
                bins.append(
                    {
                        "mean_probability": sum(probabilities[i] for i in members) / len(members),
                        "observed_rate": sum(
                            gold_by_id[ids[i]]["plastic_related"] == "true" for i in members
                        )
                        / len(members),
                        "count": len(members),
                    }
                )
        calibration = bins
    gate_values = [pred_by_id[i].get("gazetteer_gate") for i in ids]
    gate_recall = None
    if any(value is not None for value in gate_values):
        if any(type(value) is not bool for value in gate_values):
            raise ValueError("gazetteer_gate must be present as a boolean for every prediction")
        positives = [gold_by_id[i]["ca_sampled"] in {"yes", "partial"} for i in ids]
        denominator = sum(positives)
        gate_recall = (
            sum(actual and passed for actual, passed in zip(positives, gate_values, strict=True))
            / denominator
            if denominator
            else None
        )
    return {
        "schema_version": "evaluation_v1",
        "split": split,
        "n": len(ids),
        "model_version": model_version,
        "data_snapshot": data_snapshot,
        "metrics": metrics,
        "domain_tags": tags_report,
        "errors": errors,
        "calibration": calibration,
        "gazetteer_gate_recall": gate_recall,
        "thresholds": THRESHOLDS,
        "interpretation": (
            "Metrics describe the supplied split only. Synthetic metrics are not corpus "
            "performance. Test results are final-only and must not guide development."
        ),
    }


def write_calibration_plot(report: dict[str, Any], destination: str | Path) -> None:
    """Write a reliability diagram when probability estimates were supplied."""
    if report["calibration"] is None:
        raise ValueError("calibration plot requires prediction probabilities")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    points = report["calibration"]
    fig, ax = plt.subplots(figsize=(5.2, 4.2), constrained_layout=True)
    ax.plot([0, 1], [0, 1], linestyle="--", color="#777", label="perfect calibration")
    ax.plot(
        [p["mean_probability"] for p in points],
        [p["observed_rate"] for p in points],
        marker="o",
        color="#176b87",
        label="model",
    )
    ax.set(
        xlim=(0, 1),
        ylim=(0, 1),
        xlabel="Mean predicted probability",
        ylabel="Observed positive fraction",
        title="Plastic relevance reliability diagram",
    )
    ax.grid(alpha=0.2)
    ax.legend(loc="best")
    fig.savefig(destination, dpi=160)
    plt.close(fig)


def render_markdown(report: dict[str, Any], plot_path: str | None = None) -> str:
    def fmt(value: Any) -> str:
        return "undefined" if value is None else f"{value:.3f}"

    lines = [
        f"# Evaluation report: {report['model_version']}",
        "",
        f"- Split: `{report['split']}` ({report['n']} works)",
        f"- Data snapshot: `{report['data_snapshot']}`",
        "",
        "## Per-class results",
        "",
        "| Label | Class | Precision | Recall | F1 | Support |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for field, block in report["metrics"].items():
        for label, value in block["classes"].items():
            lines.append(
                f"| {field} | {label} | {fmt(value['precision'])} | "
                f"{fmt(value['recall'])} | {fmt(value['f1'])} | {value['support']} |"
            )
    lines.extend(
        [
            "",
            "## Domain tag results",
            "",
            "| Tag | Precision | Recall | F1 | Support | Status |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for tag, value in report["domain_tags"].items():
        f1 = value["f1"]
        status = (
            "insufficient positive support"
            if value["support"] == 0
            else (
                "experimental" if f1 is None or f1 < THRESHOLDS["domain_tag_f1"] else "meets target"
            )
        )
        lines.append(
            f"| {tag} | {fmt(value['precision'])} | {fmt(value['recall'])} | "
            f"{fmt(f1)} | {value['support']} | {status} |"
        )
    lines.extend(["", "## Calibration", ""])
    if plot_path and report["calibration"] is not None:
        lines.extend(
            [
                f"![Reliability diagram]({plot_path})",
                "",
                "| Mean probability | Observed rate | Count |",
                "|---:|---:|---:|",
            ]
        )
        for point in report["calibration"]:
            lines.append(
                f"| {point['mean_probability']:.3f} | "
                f"{point['observed_rate']:.3f} | {point['count']} |"
            )
    else:
        lines.append("No probabilities supplied; calibration was not computed.")
    lines.extend(
        [
            "",
            "## Error analysis",
            "",
            "| Work ID | Mismatched labels | Domain false positives | Domain false negatives |",
            "|---|---|---|---|",
        ]
    )
    for error in report["errors"]:
        lines.append(
            f"| {error['work_id']} | {', '.join(error['fields']) or '-'} | "
            f"{', '.join(error['domain_tag_fp']) or '-'} | "
            f"{', '.join(error['domain_tag_fn']) or '-'} |"
        )
    lines.extend(
        [
            "",
            "## Thresholds and interpretation",
            "",
            "G-9 / spec F1 targets: `ca_sampled=yes` precision >=0.85 and recall >=0.80; "
            "plastic relevance F1 >=0.90; domain-tag F1 <0.70 is experimental; "
            "gazetteer gate recall >=0.95. The gate target is not computed unless gate "
            "predictions are supplied.",
            "",
            report["interpretation"],
            "",
            "This harness reports metrics; it does not tune thresholds. Use dev for "
            "development and reserve test for a final, frozen evaluation. Gold rows must "
            "be canonical, adjudicated, and one row per work. Undefined metrics remain explicit.",
            "",
        ]
    )
    return "\n".join(lines)
