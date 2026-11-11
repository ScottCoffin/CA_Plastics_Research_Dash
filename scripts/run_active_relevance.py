"""Headless active-learning run for work relevance (S5.1-AL).

    py -3.14 scripts/run_active_relevance.py [--model BAAI/bge-small-en-v1.5] [--batch 20]

Embeds title + abstract for every corpus work (cached in data/interim/embeddings/),
trains the classifier on the owner's labels, prints metrics and the queue composition,
writes a queue preview to scratch/, and updates curation/work_relevance_al_state.json.
Needs the optional ``ml`` extra (sentence-transformers, scikit-learn). It never writes
curation/work_relevance.csv or curation/work_relevance_model.csv.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.nlp import active_relevance as al  # noqa: E402
from atlas.work_relevance_review import (  # noqa: E402
    REVIEW_CSV,
    WORKS_PARQUET,
    load_work_details,
    load_work_reviews,
)


def load_embedder(model_name: str) -> tuple[al.Embedder, str]:
    """Download/load the model, falling back to MiniLM when the primary one fails."""
    for name in (model_name, al.FALLBACK_MODEL):
        try:
            return al.sentence_transformer_embedder(name), name
        except Exception as error:  # noqa: BLE001 - report and try the fallback
            print(f"could not load {name}: {error}", file=sys.stderr)
    raise SystemExit("no embedding model could be loaded")


def run(model_name: str, batch: int, save: bool = True) -> al.ActiveResult:
    details = load_work_details(ROOT / WORKS_PARQUET)
    texts = al.work_texts(details)
    embedder, used = load_embedder(model_name)
    reviews = load_work_reviews(ROOT / REVIEW_CSV).rows
    prior = al.load_state(ROOT / al.STATE_PATH)
    result = al.run_active_learning(
        texts=texts,
        review_rows=reviews,
        audit_labels=al.load_audit_labels([ROOT / p for p in al.AUDIT_CSVS]),
        test_ids=al.load_test_ids(ROOT / al.SPLITS_CSV),
        embedder=embedder,
        model_name=used,
        cache_dir=ROOT / al.EMBEDDING_DIR,
        batch_size=batch,
        skipped=frozenset(prior.get("skipped", [])),
    )
    if save:
        state = prior
        summary = al.audit_summary(state, result.confident_auto)
        al.append_trend(state, result.model.metrics, summary)
        al.save_state(al.state_snapshot(result, state), ROOT / al.STATE_PATH)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=al.DEFAULT_MODEL)
    parser.add_argument("--batch", type=int, default=al.BATCH_SIZE)
    parser.add_argument("--no-save", action="store_true", help="do not update the state file")
    args = parser.parse_args()
    start = time.perf_counter()
    result = run(args.model, args.batch, save=not args.no_save)
    m = result.model.metrics
    print(f"model: {result.model_name}; embedded {result.n_embedded} new/changed works")
    print(
        f"labels: {m['n_labels']} ({m['n_relevant']} relevant, {m['n_not_relevant']} not); "
        f"sources {dict(Counter(src for _v, src in result.labels.values()))}"
    )
    print(
        f"{m['cv_folds']}-fold CV: AUC {m['cv_roc_auc']:.3f}, accuracy {m['cv_accuracy']:.3f}, "
        f"not-relevant precision {m['cv_not_relevant_precision']:.3f} "
        f"recall {m['cv_not_relevant_recall']:.3f}; calibrated={m['calibrated']}"
    )
    disagreements = sum(1 for s in result.scores if s["disagree"])
    print(
        f"unlabeled scored: {len(result.scores)}; confident auto-labels: {result.confident_auto}; "
        f"model-Haiku disagreements: {disagreements}"
    )
    no_haiku = sum(1 for s in result.scores if s["haiku"] is None)
    print(f"queue-eligible works: {len(result.scores)} ({no_haiku} with no Haiku call)")
    print(f"queue: {dict(Counter(q['reason'] for q in result.queue))}")
    print(f"timings (s): {result.seconds}; total {time.perf_counter() - start:.1f}")
    preview = ROOT / "scratch" / "al_queue_preview.csv"
    preview.parent.mkdir(exist_ok=True)
    with preview.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(["work_id", "reason", "p_relevant", "haiku"])
        for q in result.queue:
            writer.writerow([q["work_id"], q["reason"], f"{q['p_relevant']:.3f}", q["haiku"]])
    print(f"queue preview: {preview}")


if __name__ == "__main__":
    main()
