"""S5.1-AL: active-learning triage of work relevance (toy embedder, no model download)."""

from __future__ import annotations

import csv
import hashlib
from collections import Counter
from pathlib import Path

import pytest

pytest.importorskip("sklearn")
np = pytest.importorskip("numpy")

from atlas.nlp import active_relevance as al  # noqa: E402

REL = "plastic microplastic polymer pollution"
NOT = "zinc fishery genetics clover"


def toy_embedder(texts):
    """Deterministic bag-of-keywords embedder: two topic axes plus hashed noise."""
    rows = []
    for text in texts:
        low = text.lower()
        digest = hashlib.sha1(text.encode()).digest()
        noise = [(b - 128) / 1280 for b in digest[:6]]
        vec = np.array(
            [float("plastic" in low) * 2, float("zinc" in low or "clover" in low) * 2, *noise]
        )
        rows.append(vec / np.linalg.norm(vec))
    return np.array(rows)


def make_world(n=80):
    texts, review = {}, []
    for i in range(n):
        wid = f"W{i}"
        relevant = i % 2 == 0
        texts[wid] = f"{REL if relevant else NOT} study {i}"
        review.append(
            {
                "work_id": wid,
                "plastic_related": "true" if relevant else "false",
                "assist_plastic_related": "true" if relevant else "false",
                "confidence": "high",
                "reason": "",
                "reviewer": "claude-haiku-assist",
                "reviewed_at": "2026-11-11",
                "owner_review": "pending",
            }
        )
    return texts, review


def test_assemble_labels_excludes_test_and_owner_wins():
    audit = {"W1": True, "W2": False, "W3": True}
    review = [
        {"work_id": "W2", "plastic_related": "true", "owner_review": "changed"},
        {"work_id": "W4", "plastic_related": "false", "owner_review": "confirmed"},
        {"work_id": "W5", "plastic_related": "true", "owner_review": "pending"},
        {"work_id": "W6", "plastic_related": "true", "owner_review": "unsure"},
    ]
    labels = al.assemble_labels(audit, review, frozenset({"W3", "W4"}))
    assert labels == {"W1": (True, "at1"), "W2": (True, "owner")}


def test_audit_labels_v3_wins_and_unsure_skipped(tmp_path: Path):
    def write(path, rows):
        with path.open("w", newline="", encoding="utf-8") as out:
            w = csv.writer(out)
            w.writerow(["work_id", "review_label"])
            w.writerows(rows)
        return path

    v2 = write(tmp_path / "v2.csv", [("A", "relevant"), ("B", "unsure"), ("C", "relevant")])
    v3 = write(tmp_path / "v3.csv", [("C", "not_relevant"), ("D", "relevant")])
    assert al.load_audit_labels([v2, v3]) == {"A": True, "C": False, "D": True}


def test_unlabeled_population_covers_works_without_haiku_row():
    _texts, review = make_world(10)
    review[1]["owner_review"] = "unsure"
    review[5]["owner_review"] = "confirmed"
    labels = {"W2": (True, "at1")}
    corpus = [f"W{i}" for i in range(12)]  # W10 and W11 have no Haiku row
    pop = al.unlabeled_population(review, labels, frozenset({"W3"}), corpus, frozenset({"W7"}))
    assert set(pop) == {"W0", "W4", "W6", "W8", "W9", "W10", "W11"}
    assert pop["W10"] is None and pop["W0"] is True and pop["W9"] is False


def test_no_haiku_means_no_disagreement():
    class Fixed:
        def predict_proba(self, x):
            return np.array([[0.1, 0.9]] * len(x))

    model = al.TrainedModel(estimator=Fixed(), metrics={})
    vectors = {"A": np.zeros(2), "B": np.zeros(2)}
    rows = {s["work_id"]: s for s in al.score_works(model, vectors, {"A": None, "B": False})}
    assert rows["A"]["disagree"] is False and rows["A"]["haiku"] is None
    assert rows["B"]["disagree"] is True


def test_audit_round_is_stratified_and_confident():
    scores = []
    for i in range(300):
        pred = i % 4 != 0  # 75% predicted relevant
        p = 0.97 if pred else 0.02
        scores.append(
            {
                "work_id": f"W{i}",
                "p_relevant": p,
                "model_pred": pred,
                "haiku": None,
                "disagree": False,
                "margin": abs(p - 0.5),
                "confident": i % 10 != 0,
            }
        )
    batch = al.select_audit_round(scores, 20, seed=3)
    assert len(batch) == 20 and {b["reason"] for b in batch} == {"audit"}
    assert all(b["confident"] for b in batch)
    relevant = sum(1 for b in batch if b["model_pred"])
    assert 13 <= relevant <= 17  # about 75% of 20
    assert al.select_audit_round(scores, 20, seed=3) == batch
    assert al.select_audit_round([], 20) == []


def test_is_stable():
    def trend(*values):
        return [{"cv_accuracy": v} for v in values]

    assert not al.is_stable(trend(0.9, 0.91))
    assert al.is_stable(trend(0.80, 0.905, 0.91, 0.912))
    assert not al.is_stable(trend(0.90, 0.92, 0.921))


def test_embedding_cache_recomputes_only_changes(tmp_path: Path):
    calls = []

    def counting(texts):
        calls.append(len(texts))
        return toy_embedder(texts)

    texts = {"a": "plastic one", "b": "zinc two"}
    path = tmp_path / "m.npz"
    _v, n = al.embed_cached(texts, counting, path)
    assert n == 2
    _v, n = al.embed_cached(texts, counting, path)
    assert n == 0
    _v, n = al.embed_cached({**texts, "b": "zinc changed", "c": "new"}, counting, path)
    assert n == 2 and calls == [2, 2]


def _state(correct, wrong):
    log = [{"work_id": f"c{i}", "outcome": "correct"} for i in range(correct)]
    log += [{"work_id": f"w{i}", "outcome": "wrong"} for i in range(wrong)]
    log.append({"work_id": "u", "outcome": "unsure"})  # ignored
    return {"audit_log": log}


def test_wilson_and_ready_rule():
    lo, hi = al.wilson_interval(30, 30)
    assert 0.88 < lo < 0.89 and hi == 1.0
    assert al.wilson_interval(0, 0) == (0.0, 1.0)

    low = al.audit_summary(_state(30, 0), 100)
    assert not low.ready_to_accept and low.more_audits_needed is not None
    ok = al.audit_summary(_state(80, 0), 100)
    assert ok.ready_to_accept and ok.accuracy == 1.0 and ok.errors_remaining == 0
    assert ok.errors_upper > 0
    few = al.audit_summary(_state(20, 0), 100, target=0.5)
    assert not few.ready_to_accept  # fewer than 30 audit items
    bad = al.audit_summary(_state(80, 20), 50)
    assert not bad.ready_to_accept and bad.more_audits_needed is None
    assert bad.errors_remaining == pytest.approx(10.0)


def test_estimate_uses_audit_items_only():
    state = {"audit_log": []}
    pick_u = {"work_id": "U", "reason": "uncertain", "model_pred": True, "p_relevant": 0.5}
    pick_a = {"work_id": "A", "reason": "audit", "model_pred": True, "p_relevant": 0.95}
    pick_b = {"work_id": "B", "reason": "audit", "model_pred": False, "p_relevant": 0.03}
    al.record_audit(state, pick_u, False)
    al.record_audit(state, pick_a, True)
    al.record_audit(state, pick_b, True)
    al.record_audit(state, pick_a, True)  # duplicate ignored
    assert [e["work_id"] for e in state["audit_log"]] == ["A", "B"]
    summary = al.audit_summary(state, 10)
    assert (summary.n, summary.correct) == (2, 1)


def test_query_mix_proportions():
    scores = []
    for i in range(200):
        p = (i + 0.5) / 200
        scores.append(
            {
                "work_id": f"W{i}",
                "p_relevant": p,
                "model_pred": p >= 0.5,
                "haiku": i % 3 == 0,
                "disagree": (p >= 0.5) != (i % 3 == 0),
                "margin": abs(p - 0.5),
                "confident": abs(p - 0.5) >= al.CONFIDENT_MARGIN,
            }
        )
    queue = al.select_queries(scores, 20, seed=1)
    assert len(queue) == 20 and len({q["work_id"] for q in queue}) == 20
    assert Counter(q["reason"] for q in queue) == {"uncertain": 12, "disagreement": 5, "audit": 3}
    assert all(q["confident"] for q in queue if q["reason"] == "audit")
    assert al.select_queries(scores, 20, seed=1) == queue  # reproducible
    excluded = frozenset(q["work_id"] for q in queue)
    assert not excluded & {q["work_id"] for q in al.select_queries(scores, 20, 1, excluded)}


def _run(tmp_path, review, audit, test_ids=frozenset(), texts=None):
    world_texts, _ = make_world(len(review))
    return al.run_active_learning(
        texts=texts or world_texts,
        review_rows=review,
        audit_labels=audit,
        test_ids=test_ids,
        embedder=toy_embedder,
        model_name="toy/model",
        cache_dir=tmp_path,
    )


def test_end_to_end_excludes_test_and_never_overwrites_owner_rows(tmp_path: Path):
    texts, review = make_world(240)
    audit = {f"W{i}": i % 2 == 0 for i in range(120)}  # first 120 labelled by AT-1
    test_ids = frozenset({"W10", "W11", "W50", "W51"})
    review[200]["owner_review"] = "changed"  # owner-decided rows are not auto-labelled
    review[200]["plastic_related"] = "false"
    result = _run(tmp_path, review, audit, test_ids, texts)
    assert result.model.metrics["cv_roc_auc"] > 0.9
    labelled = set(result.labels)
    assert not labelled & test_ids and "W200" in labelled
    scored = {s["work_id"] for s in result.scores}
    assert not scored & test_ids and not scored & labelled
    assert not {q["work_id"] for q in result.queue} & (test_ids | labelled)

    state = _state(80, 0)
    out = tmp_path / "model.csv"
    written = al.accept_model_labels(result, state, review, out)
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == written > 0
    ids = {r["work_id"] for r in rows}
    assert not ids & (test_ids | labelled) and "W200" not in ids
    assert tuple(rows[0]) == al.MODEL_HEADER
    with pytest.raises(ValueError, match="not ready"):
        al.accept_model_labels(result, {"audit_log": []}, review, tmp_path / "never.csv")
    assert not (tmp_path / "never.csv").exists()


def test_too_few_labels_raises(tmp_path: Path):
    _texts, review = make_world(10)
    with pytest.raises(al.InsufficientLabels):
        _run(tmp_path, review, {"W0": True, "W1": False})


def test_state_trend_and_snapshot(tmp_path: Path):
    _texts, review = make_world(60)
    result = _run(tmp_path, review, {f"W{i}": i % 2 == 0 for i in range(30)})
    state = {"audit_log": []}
    summary = al.audit_summary(state, result.confident_auto)
    al.append_trend(state, result.model.metrics, summary)
    al.append_trend(state, result.model.metrics, summary)  # unchanged: not duplicated
    assert len(state["trend"]) == 1
    snap = al.state_snapshot(result, state)
    path = tmp_path / "state.json"
    al.save_state(snap, path)
    assert al.load_state(path)["label_counts"]["total"] == 30
