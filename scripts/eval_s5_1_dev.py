"""S5.1 dev evaluation: plastic-relevance predictors against owner labels (test split excluded).

Owner labels: AT-1 audit labels plus owner decisions in ``curation/work_relevance.csv``
(``atlas.nlp.active_relevance.assemble_labels``; the frozen S4.2 test split is excluded
and never scored). Predictors: the keyword rule (``work_labels.plastic_related``), the
Claude Haiku assist call where one exists, and the active-learning embedding model
(5-fold cross-validated predictions; needs the optional ``ml`` extra). Reports the
relevant-class F1 against the G-9 target (>= 0.90) with a bootstrap 95% interval.

    PYTHONPATH=src py -3.14 scripts/eval_s5_1_dev.py
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

import pyarrow.parquet as pq

from atlas.nlp import active_relevance as al
from atlas.work_relevance_review import load_work_details

TARGET_F1 = 0.90


def f1(pairs: list[tuple[bool, bool]]) -> dict[str, float]:
    tp = sum(1 for y, p in pairs if y and p)
    fp = sum(1 for y, p in pairs if not y and p)
    fn = sum(1 for y, p in pairs if y and not p)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    score = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"n": len(pairs), "precision": precision, "recall": recall, "f1": score}


def bootstrap(pairs: list[tuple[bool, bool]], reps: int = 1000) -> tuple[float, float]:
    rng = random.Random(0)
    values = sorted(f1([rng.choice(pairs) for _ in pairs])["f1"] for _ in range(reps))
    return values[int(0.025 * reps)], values[int(0.975 * reps) - 1]


def summarize(name: str, pairs: list[tuple[bool, bool]]) -> dict:
    out = {"predictor": name, **f1(pairs)}
    out["f1_ci95"] = bootstrap(pairs) if pairs else (0.0, 0.0)
    out["meets_target"] = out["f1_ci95"][0] >= TARGET_F1
    return out


def main() -> None:
    with Path("curation/work_relevance.csv").open(encoding="utf-8", newline="") as handle:
        review_rows = list(csv.DictReader(handle))
    labels = al.assemble_labels(al.load_audit_labels(), review_rows, al.load_test_ids())
    truth = {w: v for w, (v, _src) in labels.items()}
    rule = {
        r["work_id"]: bool(r["plastic_related"])
        for r in pq.read_table(
            "data/processed/work_labels.parquet", columns=["work_id", "plastic_related"]
        ).to_pylist()
    }
    haiku = {
        r["work_id"]: r["assist_plastic_related"] == "true"
        for r in review_rows
        if r.get("assist_plastic_related") in ("true", "false")
    }
    results = [
        summarize("keyword rule", [(truth[w], rule[w]) for w in truth if w in rule]),
        summarize("Claude Haiku assist", [(truth[w], haiku[w]) for w in truth if w in haiku]),
    ]
    try:
        import numpy as np

        texts = al.work_texts(load_work_details())
        ids = [w for w in truth if texts.get(w)]
        embedder = al.sentence_transformer_embedder()
        cache = Path("data/interim/eval_s5_1_embeddings.npz")
        vectors, _computed = al.embed_cached({w: texts[w] for w in ids}, embedder, cache)
        model = al.train(np.asarray([vectors[w] for w in ids]), [truth[w] for w in ids])
        results.append({"predictor": "AL embedding model (CV)", **model.metrics})
    except Exception as error:  # optional ml extra or model download unavailable
        results.append({"predictor": "AL embedding model (CV)", "skipped": str(error)})
    sources: dict[str, int] = {}
    for _v, src in labels.values():
        sources[src] = sources.get(src, 0) + 1
    report = {"labels": len(truth), "label_sources": sources, "results": results}
    Path("scratch").mkdir(exist_ok=True)
    Path("scratch/s5_1_dev_eval.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
