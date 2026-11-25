"""BQ-1.1 corpus-quality estimators (A3 section 7, Module 1). Writes the bq1-v1 JSON.

    py -3.14 scripts/bq1_estimate.py --synthetic [--out scratch/bq1/quality.json]
    py -3.14 scripts/bq1_estimate.py [--predictions PATH] [--out PATH]

``--synthetic`` builds a seeded synthetic dataset (strata, weights, labels, predictions) and runs
the same estimators as the real path. The real path reads gold labels only from
``curation/annotations/*.csv`` (decision_status ``complete``), the design from
``curation/gold_design_v1.json`` and ``curation/gold_global_draws_v1.csv``, and predictions from
``--predictions`` (not shipped). Without labels every estimand is ``{"status": "no_gold_yet"}``.
Formulas: ``docs/QUALITY_ESTIMATORS.md``.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.nlp import quality as q  # noqa: E402
from atlas.nlp.annotation import DOMAIN_TAGS  # noqa: E402

SCHEMA = "bq1-v1"
CA_SHEET = ROOT / "curation" / "annotations" / "annotations_SC.csv"
GLOBAL_SHEET = ROOT / "curation" / "annotations" / "annotations_global_SC.csv"
DESIGN = ROOT / "curation" / "gold_design_v1.json"
GLOBAL_DRAWS = ROOT / "curation" / "gold_global_draws_v1.csv"
DEFAULT_OUT = ROOT / "scratch" / "bq1" / "quality.json"
ESTIMANDS = ("E1", "E1g", "E1s", "E1l", "E2", "E2g", "E3", "E4", "E7")
GLOBAL_ESTIMANDS = frozenset({"E1g", "E2g"})
ADAPTIVE_NOTE = (
    "Global strata use adaptive Neyman allocation (A3 4.3 item 3). A simulation on the earlier "
    "32-stratum frame gave a relative bias of -1.18% (ADR-GOLD-GLOBAL-SAMPLER-2026-11-25); the "
    "16-stratum redesign keeps the allocation, and its bias is reported here, not re-simulated."
)
CA_NOTE = (
    "CA pool: 500 works drawn from 873 strata, one work per sampled stratum; Horvitz-Thompson "
    "weights 1/pi (ADR-GOLD-DESIGN-HT). Variance uses between-stratum variation; the cluster "
    "bootstrap over author groups gives the reported interval."
)
PRIMARY_CENTRALITY = frozenset({"primary", "substantial"})


# ---------------------------------------------------------------- estimands


def _count(rows: list[dict[str, Any]], pred) -> int:
    return sum(1 for r in rows if pred(r))


def _ca_headline(
    rows: list[dict[str, Any]], num, den, population_units: int, min_n: int
) -> dict[str, Any]:
    """Two-stage HT ratio over the CA block with a cluster bootstrap over author groups."""
    sampled = [r for r in rows if r["weight"] is not None]
    units = [(float(r["N_h"]), float(num(r)), float(den(r))) for r in sampled]
    res = q.psu_ratio(units, population_units)
    domain = [r for r in sampled if den(r)]
    if res["point"] is None:
        return {
            "status": "no_domain",
            "point": None,
            "n": len(domain),
            "flags": ["insufficient_data"],
        }

    def stat(sample: list[dict[str, Any]]) -> float | None:
        d = sum(r["weight"] * den(r) for r in sample)
        return sum(r["weight"] * num(r) for r in sample) / d if d > 0 else None

    reps = q.cluster_bootstrap_replicates(sampled, lambda r: r["author_group"], stat)
    return {
        "status": "ok",
        "point": res["point"],
        "interval": q.percentile_interval(reps),
        "interval_method": "cluster bootstrap percentile over author groups (B=1000, fixed seed)",
        "linearised_interval": res["interval"],
        "se": res["se"],
        "design_effect": q.design_effect(res["variance"], res["point"], len(domain)),
        "kish": q.kish_design_effect([r["weight"] for r in domain]),
        "n": len(domain),
        "n_sampled": len(sampled),
        "method": "two-stage HT ratio (one work per sampled stratum), linearised variance",
        "flags": ["insufficient_data"] if len(domain) < min_n else [],
        "design_notes": [CA_NOTE],
    }


def _global_headline(rows: list[dict[str, Any]], num, den, min_n: int) -> dict[str, Any]:
    """Stratified ratio over the global block (SRS within strata, adaptive allocation)."""
    strata: dict[str, tuple[float, list[float], list[float]]] = {}
    for r in rows:
        if r["weight"] is None:
            continue
        entry = strata.setdefault(r["stratum"], (float(r["N_h"]), [], []))
        entry[1].append(float(num(r)))
        entry[2].append(float(den(r)))
    res = q.stratified_ratio(list(strata.values()))
    domain = [r for r in rows if r["weight"] is not None and den(r)]
    if res["point"] is None:
        return {
            "status": "no_domain",
            "point": None,
            "n": len(domain),
            "flags": ["insufficient_data"],
        }
    flags = ["insufficient_data"] if len(domain) < min_n else []
    if res["variance"] is None:
        flags.append("unestimable_variance")
    elif res["variance"] == 0:
        flags.append("zero_variance")
    return {
        "status": "ok",
        "point": res["point"],
        "interval": res["interval"],
        "interval_method": "normal approximation on stratified linearised variance",
        "se": res["se"],
        "design_effect": q.design_effect(res["variance"], res["point"], len(domain)),
        "kish": q.kish_design_effect([r["weight"] for r in domain]),
        "n": len(domain),
        "n_sampled": _count(rows, lambda r: r["weight"] is not None),
        "method": "stratified ratio (SRS within strata, adaptive allocation)",
        "flags": flags,
        "design_notes": [ADAPTIVE_NOTE],
    }


def _unweighted(rows: list[dict[str, Any]], num, den, min_n: int, note: str) -> dict[str, Any]:
    n = _count(rows, den)
    k = _count(rows, lambda r: den(r) and num(r))
    if n == 0:
        return {
            "status": "no_domain",
            "point": None,
            "interval": None,
            "n": 0,
            "flags": ["insufficient_data"],
            "design_notes": [note],
        }
    lo, hi = q.clopper_pearson_interval(k, n)
    return {
        "status": "ok",
        "point": k / n,
        "interval": [lo, hi],
        "interval_method": "Clopper-Pearson exact, unweighted counts",
        "n": n,
        "flags": ["insufficient_data"] if n < min_n else [],
        "design_notes": [note],
    }


def _e4(labelled: list[dict[str, Any]]) -> dict[str, Any]:
    plastic = [r for r in labelled if r["gold_pr"]]
    return {
        "status": "ok",
        "per_tag": q.tag_f1(
            [r["gold_tags"] for r in plastic], [r["pred_tags"] for r in plastic], DOMAIN_TAGS
        ),
        "per_study_type": q.study_type_metrics(
            [r["gold_study_type"] for r in plastic], [r["pred_study_type"] for r in plastic]
        ),
        "n": len(plastic),
        "design_notes": [
            "Unweighted, over gold plastic-relevant rows. Experimental if F1 or kappa < 0.70; "
            "insufficient_data below 15 positives; below_target_40 flags values under 40 positives."
        ],
    }


def _breakdowns(rows: list[dict[str, Any]], min_n: int) -> dict[str, Any]:
    """Weighted E1 and E2 within each block, by theme, label source, year, language, abstract."""
    dims = ("theme_group", "label_source", "year", "language", "abstract_present")
    out: dict[str, Any] = {}
    for block in ("ca", "global"):
        block_rows = [r for r in rows if r["block"] == block and r["weight"] is not None]
        out[block] = {}
        for dim in dims:
            levels: dict[str, Any] = {}
            for level in sorted({str(r[dim]) for r in block_rows}):
                subset = [r for r in block_rows if str(r[dim]) == level]
                e1 = q.weighted_share(
                    [
                        (r["weight"], float(r["gold_pr"] and r["pred_pr"]), float(r["pred_pr"]))
                        for r in subset
                    ]
                )
                e2 = q.weighted_share(
                    [
                        (r["weight"], float(r["gold_pr"] and r["pred_pr"]), float(r["gold_pr"]))
                        for r in subset
                    ]
                )
                levels[level] = {
                    "n": len(subset),
                    "E1": {"point": e1["point"], "interval": e1["interval"], "n": e1["n"]},
                    "E2": {"point": e2["point"], "interval": e2["interval"], "n": e2["n"]},
                    "flags": ["insufficient_data"] if len(subset) < min_n else [],
                }
            out[block][dim] = levels
    out["note"] = "Descriptive: weighted within block, Wilson on Kish effective n. " + ADAPTIVE_NOTE
    return out


def estimate_all(
    rows: list[dict[str, Any]], *, ca_population_units: int, min_n: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run every estimand and breakdown on joined rows (synthetic or gold).

    Each row needs: block, weight, N_h, stratum, author_group, split, gold_pr, pred_pr, gold_tier,
    pred_tier, gold_centrality, gold_lens, pred_lens, pred_band, gold_tags, pred_tags,
    gold_study_type, pred_study_type, and the breakdown fields (theme_group, label_source, year,
    language, abstract_present).
    """
    ca = [r for r in rows if r["block"] == "ca"]
    glob = [r for r in rows if r["block"] == "global"]
    labelled = ca + glob

    def gold_pr(r: dict[str, Any]) -> int:
        return int(r["gold_pr"])

    def pred_pr(r: dict[str, Any]) -> int:
        return int(r["pred_pr"])

    def agree(r: dict[str, Any]) -> int:
        """Both gold and predicted plastic-related: the numerator of precision and recall."""
        return int(r["gold_pr"] and r["pred_pr"])

    estimands: dict[str, Any] = {
        "E1": _ca_headline(ca, agree, pred_pr, ca_population_units, min_n),
        "E1g": _global_headline(glob, agree, pred_pr, min_n),
        "E2": _ca_headline(ca, agree, gold_pr, ca_population_units, min_n),
        "E2g": _global_headline(glob, agree, gold_pr, min_n),
        "E1s": _ca_headline(
            ca,
            lambda r: int(
                r["pred_tier"] == "lifecycle_and_society"
                and r["gold_centrality"] in PRIMARY_CENTRALITY
            ),
            lambda r: int(r["pred_tier"] == "lifecycle_and_society"),
            ca_population_units,
            min_n,
        ),
        "E1l": _unweighted(
            labelled,
            lambda r: r["gold_lens"] == r["pred_lens"],
            lambda r: bool(r["pred_lens"]),
            min_n,
            "Lens precision: unweighted and indicative (lens labels are sparse).",
        ),
    }
    held_out = [r for r in labelled if r["split"] == q.HELD_OUT_SPLIT]
    estimands["E3"] = {
        "status": "ok",
        **q.e3_current_model(held_out),
        "design_notes": ["Held-out 'test' split rows only; unweighted."],
    }
    estimands["E4"] = _e4(labelled)
    low = [r for r in labelled if r["pred_band"] == "low"]
    estimands["E7"] = {
        "status": "ok" if low else "no_domain",
        "p3": q.p3_bound(_count(low, gold_pr), len(low)),
        "n": len(low),
        "flags": ["insufficient_data"] if len(low) < min_n else [],
        "design_notes": ["Low band, unweighted P3: zero hits give the 1-0.05^(1/n) bound."],
    }
    return estimands, _breakdowns(rows, min_n)


# ---------------------------------------------------------------- synthetic dataset


def synthetic_rows(seed: int = q.BOOTSTRAP_SEED) -> tuple[list[dict[str, Any]], int]:
    """Seeded synthetic CA strata (30 of 60 sampled) and global strata (4 x 6 draws)."""
    rng = random.Random(seed)
    m_units = 60
    sampled = rng.sample(range(m_units), 30)
    rows: list[dict[str, Any]] = []
    for i, h in enumerate(sampled):
        big_n = rng.randint(2, 40)
        rows.append(
            _synthetic_row(
                rng,
                block="ca",
                work_id=f"CA{i:03d}",
                stratum=f"ca-{h}",
                big_n=big_n,
                weight=m_units / len(sampled) * big_n,
            )
        )
    for g in range(4):
        for j in range(6):
            rows.append(
                _synthetic_row(
                    rng,
                    block="global",
                    work_id=f"GL{g}{j}",
                    stratum=f"global-{g}",
                    big_n=50,
                    weight=50 / 6,
                )
            )
    rows.append(
        _synthetic_row(
            rng, block="leak_test", work_id="LT0", stratum="leak", big_n=None, weight=None
        )
    )
    return rows, m_units


def _synthetic_row(
    rng: random.Random,
    *,
    block: str,
    work_id: str,
    stratum: str,
    big_n: int | None,
    weight: float | None,
) -> dict[str, Any]:
    gold_pr = rng.random() < 0.6
    pred_pr = gold_pr if rng.random() < 0.85 else not gold_pr
    types = ["review", "field-study", "lab-experiment", "model"]
    tiers = ["core", "chemicals-in-plastics", "lifecycle_and_society"]
    tag_pool = DOMAIN_TAGS[:6]
    return {
        "block": block,
        "work_id": work_id,
        "stratum": stratum,
        "N_h": big_n,
        "weight": weight,
        "author_group": f"ag{rng.randrange(12)}",
        "split": rng.choice(["train", "dev", "test"]) if block != "global" else "global",
        "year": str(rng.randint(1990, 2024)),
        "language": rng.choice(["en", "en", "es"]),
        "abstract_present": "yes" if rng.random() < 0.9 else "no",
        "label_source": rng.choice(["owner", "curated", "accepted_al", "assist"]),
        "theme_group": rng.choice(["pollution-core", "lifecycle-and-society", "other"]),
        "gold_pr": gold_pr,
        "pred_pr": pred_pr,
        "gold_tier": rng.choice(tiers) if gold_pr else None,
        "pred_tier": rng.choice(tiers),
        "gold_centrality": rng.choice(["primary", "substantial", "peripheral"])
        if gold_pr
        else None,
        "gold_lens": rng.choice(["lens-a", "lens-b", ""]),
        "pred_lens": rng.choice(["lens-a", "lens-b", ""]),
        "pred_band": rng.choice(["low", "medium", "high"]),
        "gold_tags": frozenset(t for t in tag_pool if rng.random() < 0.3)
        if gold_pr
        else frozenset(),
        "pred_tags": frozenset(t for t in tag_pool if rng.random() < 0.3)
        if pred_pr
        else frozenset(),
        "gold_study_type": rng.choice(types) if gold_pr else None,
        "pred_study_type": rng.choice(types),
    }


# ---------------------------------------------------------------- real gold path


def _labelled(path: Path) -> list[dict[str, str]]:
    """Rows of an owner annotation sheet with decision_status complete and plastic_related set."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        r
        for r in rows
        if r.get("decision_status") == "complete" and r.get("plastic_related") in {"true", "false"}
    ]


def _load_predictions(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {r["work_id"]: r for r in csv.DictReader(handle)}


def load_gold_rows(
    *,
    ca_sheet: Path,
    global_sheet: Path,
    design: Path,
    global_draws: Path,
    predictions: Path | None,
) -> dict[str, Any]:
    """Join labelled rows to the design and predictions.

    A labelled row without a prediction is counted in ``predictions_missing`` and left out, so the
    estimators never see a missing prediction.
    """
    design_json = (
        json.loads(design.read_text(encoding="utf-8")) if design.exists() else {"rows": []}
    )
    design_rows = {r["work_id"]: r for r in design_json["rows"]}
    pool = [r for r in design_rows.values() if r["sample_role"] == "pool"]
    draws: list[dict[str, str]] = []
    if global_draws.exists():
        with global_draws.open(encoding="utf-8", newline="") as handle:
            draws = list(csv.DictReader(handle))
    n_per_stratum: dict[str, int] = {}
    for d in draws:
        n_per_stratum[d["stratum"]] = n_per_stratum.get(d["stratum"], 0) + 1
    global_by_id = {d["work_id"]: d for d in draws}
    preds = _load_predictions(predictions)
    rows: list[dict[str, Any]] = []
    missing = 0
    labelled_ca = 0
    for sheet_row in _labelled(ca_sheet):
        meta = design_rows.get(sheet_row["work_id"])
        if meta is None:
            continue
        is_pool = meta["sample_role"] == "pool"
        labelled_ca += int(is_pool)
        if sheet_row["work_id"] not in preds:
            missing += 1
            continue
        rows.append(
            _gold_row(
                sheet_row,
                preds[sheet_row["work_id"]],
                block="ca" if is_pool else "leak_test",
                weight=meta.get("design_weight") if is_pool else None,
                big_n=meta.get("N_h") if is_pool else None,
                stratum=meta["stratum"]["key"],
                author_group=meta["author_group"],
                split=sheet_row.get("split") or meta["split"],
            )
        )
    labelled_global = 0
    for sheet_row in _labelled(global_sheet):
        draw = global_by_id.get(sheet_row["work_id"])
        if draw is None:
            continue
        labelled_global += 1
        if sheet_row["work_id"] not in preds:
            missing += 1
            continue
        n_h = n_per_stratum[draw["stratum"]]
        rows.append(
            _gold_row(
                sheet_row,
                preds[sheet_row["work_id"]],
                block="global",
                weight=float(draw["N_h"]) / n_h,
                big_n=int(draw["N_h"]),
                stratum=draw["stratum"],
                author_group=sheet_row["work_id"],
                split="global",
            )
        )
    return {
        "rows": rows,
        "coverage": {
            "ca_labelled": labelled_ca,
            "ca_designed": len(pool),
            "global_labelled": labelled_global,
            "global_drawn": len(draws),
            "predictions_missing": missing,
        },
        "predictions_supplied": predictions is not None and predictions.exists(),
        "ca_population_units": int(design_json.get("strata_count") or 0),
    }


def _gold_row(
    sheet: dict[str, str],
    pred: dict[str, str],
    *,
    block: str,
    weight: float | None,
    big_n: int | None,
    stratum: str,
    author_group: str,
    split: str,
) -> dict[str, Any]:
    return {
        "block": block,
        "work_id": sheet["work_id"],
        "stratum": stratum,
        "N_h": big_n,
        "weight": weight,
        "author_group": author_group,
        "split": split,
        "year": sheet.get("year", ""),
        "language": pred.get("language", ""),
        "abstract_present": "yes" if sheet.get("abstract", "").strip() else "no",
        "label_source": pred.get("label_source", ""),
        "theme_group": pred.get("theme_group", ""),
        "gold_pr": sheet["plastic_related"] == "true",
        "pred_pr": pred.get("pred_plastic_related") == "true",
        "gold_tier": sheet.get("plastic_tier") or None,
        "pred_tier": pred.get("pred_plastic_tier") or None,
        "gold_centrality": sheet.get("plastics_centrality") or None,
        "gold_lens": sheet.get("analytic_lens") or "",
        "pred_lens": pred.get("pred_analytic_lens") or "",
        "pred_band": pred.get("pred_band") or None,
        "gold_tags": frozenset(t for t in (sheet.get("domain_tags") or "").split("|") if t),
        "pred_tags": frozenset(t for t in (pred.get("pred_domain_tags") or "").split("|") if t),
        "gold_study_type": sheet.get("study_type") or None,
        "pred_study_type": pred.get("pred_study_type") or None,
    }


# ---------------------------------------------------------------- output


def _gold_gate(estimand: str, real: dict[str, Any]) -> str | None:
    """Why an estimand cannot be reported yet, or None when every gate passes."""
    cov = real["coverage"]
    if estimand in GLOBAL_ESTIMANDS:
        if cov["global_labelled"] == 0:
            return "no_gold_yet"
    elif cov["ca_labelled"] == 0 and cov["global_labelled"] == 0:
        return "no_gold_yet"
    if not real["predictions_supplied"] or cov["predictions_missing"]:
        return "missing_predictions"
    if cov["ca_labelled"] < cov["ca_designed"] or cov["global_labelled"] < cov["global_drawn"]:
        return "incomplete_gold"
    return None


def build_report(
    *, synthetic: bool, real: dict[str, Any] | None, min_n: int, generated_at: str
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "mode": "synthetic" if synthetic else "gold",
        "seed": q.BOOTSTRAP_SEED,
        "bootstrap_B": q.BOOTSTRAP_B,
        "min_n": min_n,
        "adaptive_allocation_note": ADAPTIVE_NOTE,
    }
    if synthetic:
        rows, m_units = synthetic_rows()
        estimands, breakdowns = estimate_all(rows, ca_population_units=m_units, min_n=min_n)
        base.update(
            {
                "status": "ok",
                "synthetic_note": "Seeded synthetic strata; not a corpus estimate.",
                "estimands": estimands,
                "breakdowns": breakdowns,
            }
        )
        return base
    assert real is not None
    gates = {e: _gold_gate(e, real) for e in ESTIMANDS}
    base["coverage"] = real["coverage"]
    if all(v == "no_gold_yet" for v in gates.values()):
        base.update(
            {
                "status": "no_gold_yet",
                "estimands": {e: {"status": "no_gold_yet"} for e in ESTIMANDS},
            }
        )
        return base
    if all(v is None for v in gates.values()):
        estimands, breakdowns = estimate_all(
            real["rows"], ca_population_units=real["ca_population_units"], min_n=min_n
        )
        base.update({"status": "ok", "estimands": estimands, "breakdowns": breakdowns})
        return base
    base.update(
        {
            "status": "incomplete_gold",
            "estimands": {e: {"status": gates[e] or "pending"} for e in ESTIMANDS},
        }
    )
    return base


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--synthetic", action="store_true", help="run on a seeded synthetic dataset"
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--predictions",
        type=Path,
        default=None,
        help="CSV of model predictions keyed by work_id (required before any real estimate)",
    )
    parser.add_argument("--min-n", type=int, default=q.DEFAULT_MIN_N)
    args = parser.parse_args(argv)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    real = None
    if not args.synthetic:
        real = load_gold_rows(
            ca_sheet=CA_SHEET,
            global_sheet=GLOBAL_SHEET,
            design=DESIGN,
            global_draws=GLOBAL_DRAWS,
            predictions=args.predictions,
        )
    report = build_report(
        synthetic=args.synthetic, real=real, min_n=args.min_n, generated_at=generated_at
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"wrote {args.out} (status={report['status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
