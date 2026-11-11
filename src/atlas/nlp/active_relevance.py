"""Active-learning triage of work relevance (S5.1-AL).

The owner cannot review every one of the ~1,000 Haiku calls in
``curation/work_relevance.csv``. This module trains a small classifier on the
owner's labels (AT-1 audit labels plus owner decisions in the works review app)
over sentence embeddings of title + abstract, then picks the next works worth the
owner's time:

* the most uncertain works (labels that improve the model most),
* works where the model and Haiku disagree (likely errors in either),
* a random audit sample of works the model is confident about. Audit outcomes are
  the only data used to estimate auto-label accuracy, so the estimate is unbiased.

Everything except the embedding call is pure and testable: the embedder is injected,
so tests never download a model. S4.2 test-split works are never trained on, scored,
queued or accepted. Heavy imports (numpy, scikit-learn, sentence-transformers) are
lazy, so the module imports without the optional ``ml`` extra.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import random
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
FALLBACK_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIR = Path("data/interim/embeddings")
STATE_PATH = Path("curation/work_relevance_al_state.json")
MODEL_CSV = Path("curation/work_relevance_model.csv")
SPLITS_CSV = Path("curation/splits_v2.csv")
AUDIT_CSVS = (Path("docs/QUERY_AUDIT_REVIEW.csv"), Path("docs/QUERY_AUDIT_REVIEW_V3.csv"))
MODEL_HEADER = ("work_id", "plastic_related", "p_relevant", "model_version", "accepted_at")

CONFIDENT_MARGIN = 0.4  # |p - 0.5| >= 0.4, i.e. p <= 0.1 or p >= 0.9
TARGET_ACCURACY = 0.95
MIN_AUDIT_ITEMS = 30
BATCH_SIZE = 20
MAX_ABSTRACT_CHARS = 2000

Embedder = Callable[[Sequence[str]], Any]  # texts -> (n, d) array of L2-normalized rows


class InsufficientLabels(ValueError):
    """Too few labels of one class to train or cross-validate."""


# --------------------------------------------------------------------------- texts


def work_text(detail: Mapping[str, Any]) -> str:
    """Title plus abstract, truncated; the embedding input."""
    title = str(detail.get("title") or "").strip()
    abstract = " ".join(str(detail.get("abstract") or "").split())[:MAX_ABSTRACT_CHARS]
    return f"{title}. {abstract}".strip(". ").strip() if abstract else title


def work_texts(details: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    return {work_id: work_text(detail) for work_id, detail in details.items()}


def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()  # noqa: S324 - cache key only


def model_slug(model_name: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in model_name.split("/")[-1])


# ----------------------------------------------------------------------- embeddings


def embed_cached(
    texts: Mapping[str, str],
    embedder: Embedder,
    cache_path: Path,
) -> tuple[dict[str, Any], int]:
    """Embeddings per work_id, recomputing only new or changed texts.

    Cache key is ``work_id`` plus the SHA-1 of the text. Returns ``(vectors, n_computed)``.
    """
    import numpy as np

    cached: dict[str, tuple[str, Any]] = {}
    if cache_path.exists():
        with np.load(cache_path, allow_pickle=False) as data:
            for work_id, digest, vector in zip(
                data["ids"].tolist(), data["hashes"].tolist(), data["emb"], strict=True
            ):
                cached[str(work_id)] = (str(digest), vector)
    hashes = {work_id: _sha1(text) for work_id, text in texts.items()}
    todo = [w for w in texts if w not in cached or cached[w][0] != hashes[w]]
    fresh: dict[str, Any] = {}
    if todo:
        matrix = np.asarray(embedder([texts[w] for w in todo]), dtype=np.float32)
        fresh = dict(zip(todo, matrix, strict=True))
    vectors = {w: fresh[w] if w in fresh else cached[w][1] for w in texts}
    if todo:
        ids = list(texts)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=cache_path.parent, suffix=".npz")
        os.close(handle)
        try:
            np.savez_compressed(
                temp,
                ids=np.array(ids),
                hashes=np.array([hashes[w] for w in ids]),
                emb=np.stack([vectors[w] for w in ids]).astype(np.float32),
            )
            os.replace(temp, cache_path)
        except BaseException:
            Path(temp).unlink(missing_ok=True)
            raise
    return vectors, len(todo)


def sentence_transformer_embedder(model_name: str = DEFAULT_MODEL) -> Embedder:
    """Local sentence-transformers encoder (needs the optional ``ml`` extra)."""
    from sentence_transformers import SentenceTransformer  # lazy: optional dependency

    model = SentenceTransformer(model_name, device="cpu")
    model.max_seq_length = min(int(model.max_seq_length or 384), 384)

    def encode(texts: Sequence[str]) -> Any:
        return model.encode(
            list(texts), batch_size=32, normalize_embeddings=True, show_progress_bar=False
        )

    return encode


# ------------------------------------------------------------------------- labels


def load_test_ids(path: Path = SPLITS_CSV) -> frozenset[str]:
    """Works in the frozen S4.2 test split; never trained on, scored or queued."""
    if not path.exists():
        return frozenset()
    with path.open(newline="", encoding="utf-8") as stream:
        return frozenset(r["work_id"] for r in csv.DictReader(stream) if r.get("split") == "test")


def load_audit_labels(paths: Sequence[Path] = AUDIT_CSVS) -> dict[str, bool]:
    """Owner AT-1 labels (relevant/not_relevant); unsure is skipped; later files win."""
    labels: dict[str, bool] = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                label = (row.get("review_label") or "").strip()
                if label in ("relevant", "not_relevant"):
                    labels[row["work_id"]] = label == "relevant"
    return labels


def assemble_labels(
    audit: Mapping[str, bool],
    review_rows: Sequence[Mapping[str, str]],
    test_ids: frozenset[str],
) -> dict[str, tuple[bool, str]]:
    """Human labels ``{work_id: (plastic_related, source)}``, test split excluded.

    An owner decision in ``work_relevance.csv`` (confirmed or changed) overrides an AT-1 label.
    """
    labels: dict[str, tuple[bool, str]] = {
        w: (v, "at1") for w, v in audit.items() if w not in test_ids
    }
    for row in review_rows:
        if row["owner_review"] in ("confirmed", "changed") and row["work_id"] not in test_ids:
            labels[row["work_id"]] = (row["plastic_related"] == "true", "owner")
    return labels


# --------------------------------------------------------------------------- model


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a proportion (95% by default)."""
    if n <= 0:
        return 0.0, 1.0
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


@dataclass
class TrainedModel:
    estimator: Any
    metrics: dict[str, Any]


def train(x: Any, y: Any, seed: int = 0) -> TrainedModel:
    """Logistic regression on embeddings, sigmoid-calibrated when both classes have >= 10."""
    import numpy as np
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
    from sklearn.model_selection import StratifiedKFold, cross_val_predict

    y = np.asarray(y, dtype=int)
    n_pos, n_neg = int(y.sum()), int((1 - y).sum())
    if min(n_pos, n_neg) < 3:
        raise InsufficientLabels(
            f"need at least 3 labels of each class to train (have {n_pos} relevant, {n_neg} not)"
        )
    warnings: list[str] = []
    calibrated = min(n_pos, n_neg) >= 10

    def make() -> Any:
        base = LogisticRegression(class_weight="balanced", max_iter=2000, C=4.0)
        if calibrated:
            return CalibratedClassifierCV(base, method="sigmoid", cv=5)
        return base

    if not calibrated:
        warnings.append("uncalibrated: fewer than 10 labels in one class")
    folds = min(5, n_pos, n_neg)
    cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    proba = cross_val_predict(make(), x, y, cv=cv, method="predict_proba")[:, 1]
    pred = (proba >= 0.5).astype(int)
    metrics: dict[str, Any] = {
        "cv_folds": folds,
        "cv_roc_auc": float(roc_auc_score(y, proba)),
        "cv_accuracy": float(accuracy_score(y, pred)),
        "cv_not_relevant_precision": float(precision_score(y, pred, pos_label=0, zero_division=0)),
        "cv_not_relevant_recall": float(recall_score(y, pred, pos_label=0, zero_division=0)),
        "n_labels": int(len(y)),
        "n_relevant": n_pos,
        "n_not_relevant": n_neg,
        "calibrated": calibrated,
        "warnings": warnings,
    }
    estimator = make().fit(x, y)
    return TrainedModel(estimator=estimator, metrics=metrics)


def score_works(
    model: TrainedModel,
    vectors: Mapping[str, Any],
    population: Mapping[str, bool | None],
) -> list[dict[str, Any]]:
    """Score ``{work_id: haiku_value}``: p_relevant, prediction, disagreement, confidence."""
    import numpy as np

    ids = sorted(w for w in population if w in vectors)
    if not ids:
        return []
    p = model.estimator.predict_proba(np.stack([vectors[w] for w in ids]))[:, 1]
    rows = []
    for work_id, prob in zip(ids, p.tolist(), strict=True):
        haiku = population[work_id]
        rows.append(
            {
                "work_id": work_id,
                "p_relevant": prob,
                "model_pred": prob >= 0.5,
                "haiku": haiku,
                "disagree": haiku is not None and (prob >= 0.5) != haiku,
                "margin": abs(prob - 0.5),
                "confident": abs(prob - 0.5) >= CONFIDENT_MARGIN,
            }
        )
    return rows


# ------------------------------------------------------------------------- queries


def select_queries(
    scores: Sequence[Mapping[str, Any]],
    n: int = BATCH_SIZE,
    seed: int | None = None,
    exclude: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    """Next batch: ~60% uncertain, ~25% model-Haiku disagreements, ~15% random audit.

    The audit sample is drawn first, uniformly from all confident auto-labels, so
    its outcomes estimate auto-label accuracy without selection bias. Short buckets
    are topped up with further uncertain works.
    """
    pool = [dict(s) for s in scores if s["work_id"] not in exclude]
    n_unc = round(0.6 * n)
    n_dis = round(0.25 * n)
    n_aud = max(0, n - n_unc - n_dis)
    rng = random.Random(seed)
    picked: dict[str, dict[str, Any]] = {}

    def take(candidates: list[dict[str, Any]], count: int, reason: str) -> None:
        for s in candidates:
            if count <= 0:
                break
            if s["work_id"] not in picked:
                picked[s["work_id"]] = {**s, "reason": reason}
                count -= 1

    confident = sorted((s for s in pool if s["confident"]), key=lambda s: s["work_id"])
    rng.shuffle(confident)
    take(confident, n_aud, "audit")
    disagree = sorted(
        (s for s in pool if s["disagree"]), key=lambda s: (-s["margin"], s["work_id"])
    )
    take(disagree, n_dis, "disagreement")
    uncertain = sorted(pool, key=lambda s: (s["margin"], s["work_id"]))
    take(uncertain, n_unc, "uncertain")
    take(uncertain, n - len(picked), "uncertain")  # top up
    order = {"uncertain": 0, "disagreement": 1, "audit": 2}
    return sorted(picked.values(), key=lambda s: (order[s["reason"]], s["margin"]))


# ----------------------------------------------------------------- audit & stopping


def record_audit(
    state: dict[str, Any],
    pick: Mapping[str, Any],
    owner_value: bool | None,
    now: datetime | None = None,
) -> None:
    """Append an audit pick's outcome. Only ``reason == "audit"`` picks are logged."""
    if pick.get("reason") != "audit":
        return
    log = state.setdefault("audit_log", [])
    if any(entry["work_id"] == pick["work_id"] for entry in log):
        return
    pred = bool(pick["model_pred"])
    outcome = "unsure" if owner_value is None else ("correct" if pred == owner_value else "wrong")
    log.append(
        {
            "work_id": pick["work_id"],
            "pick_reason": "audit",
            "p_relevant": round(float(pick["p_relevant"]), 4),
            "model_pred": pred,
            "owner": owner_value,
            "outcome": outcome,
            "at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        }
    )


@dataclass
class AuditSummary:
    n: int
    correct: int
    accuracy: float | None
    lower: float
    upper: float
    target: float
    ready_to_accept: bool
    confident_auto: int
    errors_remaining: float | None
    errors_upper: float | None
    more_audits_needed: int | None  # None: target not reachable at the current rate


def audit_summary(
    state: Mapping[str, Any],
    confident_auto: int,
    target: float = TARGET_ACCURACY,
    min_items: int = MIN_AUDIT_ITEMS,
) -> AuditSummary:
    """Auto-label accuracy from audited items only, with a Wilson 95% interval."""
    judged = [e for e in state.get("audit_log", []) if e["outcome"] in ("correct", "wrong")]
    n = len(judged)
    correct = sum(1 for e in judged if e["outcome"] == "correct")
    lower, upper = wilson_interval(correct, n)
    accuracy = correct / n if n else None
    ready = n >= min_items and lower >= target
    needed = 0 if ready else audits_needed(correct, n, target, min_items)
    return AuditSummary(
        n=n,
        correct=correct,
        accuracy=accuracy,
        lower=lower,
        upper=upper,
        target=target,
        ready_to_accept=ready,
        confident_auto=confident_auto,
        errors_remaining=None if accuracy is None else (1 - accuracy) * confident_auto,
        errors_upper=None if n == 0 else (1 - lower) * confident_auto,
        more_audits_needed=needed,
    )


def audits_needed(
    correct: int, n: int, target: float = TARGET_ACCURACY, min_items: int = MIN_AUDIT_ITEMS
) -> int | None:
    """Further audits expected before the Wilson lower bound reaches ``target``.

    Assumes the current audit accuracy continues. ``None`` when that accuracy is at or
    below the target, because the lower bound can then never reach it.
    """
    if n == 0:
        return None
    rate = correct / n
    if rate <= target:
        return None
    for extra in range(0, 5001):
        total = n + extra
        if total >= min_items and wilson_interval(rate * total, total)[0] >= target:
            return extra
    return None


def append_trend(
    state: dict[str, Any],
    metrics: Mapping[str, Any],
    summary: AuditSummary,
    now: datetime | None = None,
) -> None:
    """Record audit accuracy after a retrain, so the owner can see whether tagging helps."""
    trend = state.setdefault("trend", [])
    point = {
        "at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "n_labels": metrics["n_labels"],
        "audit_n": summary.n,
        "audit_accuracy": None if summary.accuracy is None else round(summary.accuracy, 4),
        "audit_lower": round(summary.lower, 4),
        "cv_accuracy": round(metrics["cv_accuracy"], 4),
        "cv_roc_auc": round(metrics["cv_roc_auc"], 4),
    }
    if trend and all(trend[-1][k] == point[k] for k in ("n_labels", "audit_n", "cv_accuracy")):
        return  # nothing changed since the last retrain
    trend.append(point)


# ------------------------------------------------------------------- state & output


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"audit_log": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(text.encode("utf-8"))
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def save_state(state: Mapping[str, Any], path: Path = STATE_PATH) -> None:
    _atomic_write(path, json.dumps(state, indent=2, sort_keys=True) + "\n")


@dataclass
class ActiveResult:
    model_name: str
    labels: dict[str, tuple[bool, str]]
    model: TrainedModel
    scores: list[dict[str, Any]]
    queue: list[dict[str, Any]]
    n_embedded: int = 0
    seconds: dict[str, float] = field(default_factory=dict)

    @property
    def confident_auto(self) -> int:
        return sum(1 for s in self.scores if s["confident"])


def unlabeled_population(
    review_rows: Sequence[Mapping[str, str]],
    labels: Mapping[str, tuple[bool, str]],
    test_ids: frozenset[str],
    corpus_ids: Sequence[str] | None = None,
    skipped: frozenset[str] = frozenset(),
) -> dict[str, bool | None]:
    """``{work_id: haiku_value or None}`` for every corpus work still needing a label.

    Covers works with a pending Haiku row and (when ``corpus_ids`` is given) works with
    no row at all (value None, so no disagreement pick). Owner-decided or owner-unsure
    rows, labelled works, skipped works and S4.2 test works are left out.
    """
    rows = {row["work_id"]: row for row in review_rows}
    pool: list[str] = list(corpus_ids) if corpus_ids is not None else list(rows)
    population: dict[str, bool | None] = {}
    for work_id in pool:
        if work_id in labels or work_id in test_ids or work_id in skipped:
            continue
        row = rows.get(work_id)
        if row is None:
            population[work_id] = None
        elif row["owner_review"] == "pending":
            population[work_id] = (
                row.get("assist_plastic_related") or row["plastic_related"]
            ) == "true"
    return population


def select_audit_round(
    scores: Sequence[Mapping[str, Any]], n: int = BATCH_SIZE, seed: int | None = None
) -> list[dict[str, Any]]:
    """An audit-only batch: random confident auto-labels, proportional across predicted classes."""
    rng = random.Random(seed)
    groups = {
        flag: sorted(
            (s for s in scores if s["confident"] and s["model_pred"] is flag),
            key=lambda s: s["work_id"],
        )
        for flag in (True, False)
    }
    total = sum(len(g) for g in groups.values())
    if total == 0:
        return []
    n = min(n, total)
    quota = {flag: round(n * len(g) / total) for flag, g in groups.items()}
    quota[True] += n - sum(quota.values())  # absorb rounding
    picked: list[dict[str, Any]] = []
    for flag, group in groups.items():
        count = max(0, min(quota[flag], len(group)))
        picked += [{**s, "reason": "audit"} for s in rng.sample(group, count)]
    rng.shuffle(picked)
    return picked


def is_stable(trend: Sequence[Mapping[str, Any]], tolerance: float = 0.01) -> bool:
    """True when the last two retrains each moved CV accuracy by less than ``tolerance``."""
    if len(trend) < 3:
        return False
    a, b, c = (p["cv_accuracy"] for p in trend[-3:])
    return abs(b - a) < tolerance and abs(c - b) < tolerance


def run_active_learning(
    *,
    texts: Mapping[str, str],
    review_rows: Sequence[Mapping[str, str]],
    audit_labels: Mapping[str, bool],
    test_ids: frozenset[str],
    embedder: Embedder,
    model_name: str = DEFAULT_MODEL,
    cache_dir: Path = EMBEDDING_DIR,
    batch_size: int = BATCH_SIZE,
    seed: int = 0,
    skipped: frozenset[str] = frozenset(),
) -> ActiveResult:
    """Embed (cached), assemble labels, train, score unlabeled works and pick the next batch."""
    import time

    import numpy as np

    t0 = time.perf_counter()
    vectors, n_embedded = embed_cached(texts, embedder, cache_dir / f"{model_slug(model_name)}.npz")
    t1 = time.perf_counter()
    labels = {
        w: v
        for w, v in assemble_labels(audit_labels, review_rows, test_ids).items()
        if w in vectors  # labelled works no longer in the corpus cannot be embedded
    }
    train_ids = sorted(w for w in labels if w in vectors)
    x = np.stack([vectors[w] for w in train_ids])
    y = np.array([int(labels[w][0]) for w in train_ids])
    model = train(x, y, seed=seed)
    population = unlabeled_population(review_rows, labels, test_ids, list(vectors), skipped)
    scores = score_works(model, vectors, population)
    queue = select_queries(scores, batch_size, seed=seed)
    t2 = time.perf_counter()
    return ActiveResult(
        model_name=model_name,
        labels=labels,
        model=model,
        scores=scores,
        queue=queue,
        n_embedded=n_embedded,
        seconds={"embed": t1 - t0, "train_score": t2 - t1},
    )


def state_snapshot(
    result: ActiveResult, state: Mapping[str, Any], now: datetime | None = None
) -> dict[str, Any]:
    """The small committed state: model, label counts, CV metrics, audit log, timestamp."""
    sources: dict[str, int] = {}
    for _value, source in result.labels.values():
        sources[source] = sources.get(source, 0) + 1
    return {
        "model": result.model_name,
        "model_slug": model_slug(result.model_name),
        "label_counts": {
            "total": len(result.labels),
            "relevant": result.model.metrics["n_relevant"],
            "not_relevant": result.model.metrics["n_not_relevant"],
            "by_source": sources,
        },
        "cv_metrics": {
            k: v
            for k, v in result.model.metrics.items()
            if k.startswith("cv_") or k == "calibrated"
        },
        "unlabeled_scored": len(result.scores),
        "confident_auto_labels": result.confident_auto,
        "audit_log": list(state.get("audit_log", [])),
        "trend": list(state.get("trend", [])),
        "skipped": list(state.get("skipped", [])),
        "updated_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
    }


def accept_model_labels(
    result: ActiveResult,
    state: Mapping[str, Any],
    review_rows: Sequence[Mapping[str, str]],
    path: Path = MODEL_CSV,
    now: datetime | None = None,
    target: float = TARGET_ACCURACY,
) -> int:
    """Write confident model labels for unlabeled works to ``work_relevance_model.csv``.

    Refuses unless the stopping rule is met. Only works with a pending Haiku row, no
    human label and outside the test split are written, so owner rows are never touched.
    Returns the number of rows written.
    """
    summary = audit_summary(state, result.confident_auto, target)
    if not summary.ready_to_accept:
        raise ValueError("audit accuracy lower bound is below target; not ready to accept")
    protected = {
        row["work_id"] for row in review_rows if row["owner_review"] in ("confirmed", "changed")
    }
    stamp = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    version = f"{model_slug(result.model_name)}-lr-{len(result.labels)}labels"
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(MODEL_HEADER)
    written = 0
    for s in sorted(result.scores, key=lambda s: s["work_id"]):
        if not s["confident"] or s["work_id"] in protected or s["work_id"] in result.labels:
            continue
        writer.writerow(
            [s["work_id"], "true" if s["model_pred"] else "false", f"{s['p_relevant']:.4f}"]
            + [version, stamp]
        )
        written += 1
    _atomic_write(path, buffer.getvalue())
    return written
