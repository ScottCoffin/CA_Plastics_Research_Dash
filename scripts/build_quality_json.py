"""BQ-1.4: public corpus-quality payloads (schema bq1-v1) for /quality and /california/quality.

    py -3.14 scripts/build_quality_json.py            # write the two quality.json files
    py -3.14 scripts/build_quality_json.py --check    # fail when the committed files are stale

Gold status comes from the committed curation files only (``load_gold_rows`` without
predictions), so the output and ``--check`` do not depend on the ignored ``data/`` tree.

Publication rule (A3 section 7; owner): while gold is incomplete, no numeric estimate, interval,
or breakdown is written. Every estimand reads "No validated estimate yet" with the labels so far.
Numbers are written only when ``FINAL_CHECKPOINT`` names a checkpoint (set by the lead after the
complete gold set has been analysed) and ``scripts/bq1_estimate.py`` reports ``status == ok``
for that estimand. Estimator details are in ``docs/QUALITY_ESTIMATORS.md``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "src"))

import bq1_estimate as bq1  # noqa: E402

SCHEMA = "bq1-v1"
# Set by the lead at the checkpoint where the complete gold set is analysed. None = no numbers.
FINAL_CHECKPOINT: str | None = None
PREDICTIONS_CA = ROOT / "data" / "processed" / "quality" / "predictions_california.csv"
PREDICTIONS_GLOBAL = ROOT / "data" / "processed" / "quality" / "predictions_global.csv"
OUTPUTS = {
    "global": ROOT / "site" / "data" / "global" / "quality.json",
    "california": ROOT / "site" / "data" / "california" / "quality.json",
}
SCOPE_ESTIMANDS = {
    "california": ("E1", "E1s", "E1l", "E2", "E3", "E4"),
    "global": ("E1g", "E2g", "E7"),
}
NO_ESTIMATE = "No validated estimate yet"
# Extra estimator fields shown once an estimand is final (E3 and E4 are nested; E7 has a bound).
DETAIL_KEYS = ("precision", "recall", "f1", "per_tag", "per_study_type", "upper_bound")

# Plain-language estimand descriptions (label, what it measures).
ESTIMAND_TEXT: dict[str, tuple[str, str]] = {
    "E1": (
        "Precision, California",
        "Of the California works the site shows as plastics research, the share that a human "
        "labeller confirms as plastics research.",
    ),
    "E1s": (
        "Precision, lifecycle and society tier",
        "Of the works shown in the lifecycle-and-society tier, the share a human labeller rates "
        "as primary or substantial plastics centrality.",
    ),
    "E1l": (
        "Analytic lens agreement",
        "Of the works shown with an analytic lens, the share where the human label gives the same "
        "lens. Unweighted and indicative only.",
    ),
    "E2": (
        "Recall, California",
        "Of the California works a human labeller confirms as plastics research, the share the "
        "site shows as plastics research.",
    ),
    "E3": (
        "Current model on held-out works",
        "Precision, recall and F1 of the current plastic-relevance model, on held-out test works "
        "only. Training and tuning works are never used.",
    ),
    "E4": (
        "Tag and study-type accuracy",
        "F1 for each domain tag and each study type, against human labels. Results are flagged "
        "when the sample is small or the score is below 0.70.",
    ),
    "E1g": (
        "Precision, global",
        "Of the global works that match the search queries, the share a human labeller confirms "
        "as plastics research. Global works are not screened by the site.",
    ),
    "E2g": (
        "Recall, global",
        "Of the global plastics research a human labeller confirms, the share the query search "
        "finds.",
    ),
    "E7": (
        "Residual relevant works in the low band",
        "An upper bound, at 95% confidence, on the share of low-scoring global works that are "
        "plastics research.",
    ),
}

WHAT_IT_IS = {
    "california": [
        "This page reports how accurate the California research atlas is. It samples works from "
        "the California corpus and asks a human labeller whether each one is plastics research. "
        "The labels are compared with what the site shows.",
        "It is not a final evaluation. No accuracy figure is published until the labelled sample "
        "is complete and analysed.",
    ],
    "global": [
        "This page reports how accurate the global plastics search is. Global works are unscreened "
        "query hits, so a human labeller samples them to estimate how many are plastics research.",
        "It is not a final evaluation. No accuracy figure is published until the labelled sample "
        "is complete and analysed.",
    ],
}

DESIGN_TEXT = {
    "california": (
        "The California sample draws one work from each of 500 of the 873 strata of the corpus. "
        "Each labelled work is weighted by the inverse of its chance of selection, so the labelled "
        "works stand for the whole corpus. Intervals resample author groups, so one prolific group "
        "cannot dominate them. A separate sample of leak-test works is labelled for checks only "
        "and is not weighted."
    ),
    "global": (
        "The global sample draws works from the frozen query frame in strata defined by language "
        "block, theme group and relevance-score band. The allocation adapts to the variance seen "
        "so far (Neyman allocation). Each estimate is weighted by stratum size, and the "
        "ceiling for the low band is an upper bound, not a point estimate."
    ),
}

ESTIMAND_NOTE = (
    "Reported only at a final checkpoint. Interim results are not published (A3 section 7)."
)


def _labels(scope: str, coverage: dict[str, Any]) -> dict[str, Any]:
    if scope == "california":
        labelled, total, unit = coverage["ca_labelled"], coverage["ca_designed"], "California works"
    else:
        labelled, total = coverage["global_labelled"], coverage["global_drawn"]
        unit = "global works"
    return {
        "labelled": labelled,
        "planned": total,
        "unit": unit,
        "text": f"{labelled} of {total} {unit} labelled",
    }


def _design_facts(scope: str, draws_path: Path, coverage: dict[str, Any]) -> dict[str, Any]:
    """Plain design facts from the committed files (sample sizes and strata counts)."""
    if scope == "california":
        design = json.loads(bq1.DESIGN.read_text(encoding="utf-8"))
        return {
            "text": DESIGN_TEXT[scope],
            "strata_in_corpus": int(design.get("strata_count") or 0),
            "strata_sampled": int(design.get("sampled_strata_count") or 0),
            "works_planned": coverage["ca_designed"],
        }
    with draws_path.open(encoding="utf-8", newline="") as handle:
        draws = list(csv.DictReader(handle))
    return {
        "text": DESIGN_TEXT[scope],
        "strata_sampled": len({d["stratum"] for d in draws}),
        "works_planned": coverage["global_drawn"],
    }


def _public_estimand(estimand: str, raw: dict[str, Any] | None, final: bool) -> dict[str, Any]:
    label, what = ESTIMAND_TEXT[estimand]
    entry: dict[str, Any] = {"id": estimand, "label": label, "what": what}
    if final and raw is not None and raw.get("status") == "ok":
        entry.update(
            {
                "status": "ok",
                "point": raw.get("point"),
                "interval": raw.get("interval"),
                "n": raw.get("n"),
                "method": raw.get("method") or raw.get("design_notes", [""])[0],
                "flags": raw.get("flags", []),
                "note": " ".join(raw.get("design_notes", [])),
                **{k: raw[k] for k in DETAIL_KEYS if k in raw},
            }
        )
    else:
        entry.update({"status": "no_validated_estimate", "display": NO_ESTIMATE})
    return entry


def public_payload(
    scope: str,
    coverage: dict[str, Any],
    *,
    generated_at: str,
    draws_path: Path = bq1.GLOBAL_DRAWS,
    report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one scope's payload. ``report`` (a bq1 report) is used only when it is final."""
    final = report is not None
    estimands = {
        e: _public_estimand(e, (report or {}).get("estimands", {}).get(e), final)
        for e in SCOPE_ESTIMANDS[scope]
    }
    published = any(e["status"] == "ok" for e in estimands.values())
    return {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "scope": scope,
        "status": "ok" if published else "no_validated_estimate",
        "status_text": NO_ESTIMATE if not published else "Validated estimates",
        "checkpoint": FINAL_CHECKPOINT if final else None,
        "labels": _labels(scope, coverage),
        "what_this_is_and_is_not": WHAT_IT_IS[scope],
        "design": _design_facts(scope, draws_path, coverage),
        "estimands": estimands,
        "note": ESTIMAND_NOTE,
    }


def build_payloads(generated_at: str) -> dict[str, dict[str, Any]]:
    """Both scopes. Estimators run only when a final checkpoint is set (see module docstring)."""
    real = bq1.load_gold_rows(
        ca_sheet=bq1.CA_SHEET,
        global_sheet=bq1.GLOBAL_SHEET,
        design=bq1.DESIGN,
        global_draws=bq1.GLOBAL_DRAWS,
        predictions=PREDICTIONS_CA if FINAL_CHECKPOINT else None,
        global_predictions=PREDICTIONS_GLOBAL if FINAL_CHECKPOINT else None,
    )
    report = None
    if FINAL_CHECKPOINT:
        report = bq1.build_report(
            synthetic=False, real=real, min_n=bq1.q.DEFAULT_MIN_N, generated_at=generated_at
        )
    coverage = real["coverage"]
    return {
        scope: public_payload(scope, coverage, generated_at=generated_at, report=report)
        for scope in OUTPUTS
    }


def _comparable(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k != "generated_at"}


def _render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="fail when the committed JSON is stale"
    )
    args = parser.parse_args(argv)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    payloads = build_payloads(generated_at)
    if args.check:
        stale = []
        for scope, path in OUTPUTS.items():
            if not path.exists():
                stale.append(f"{path} (missing)")
                continue
            committed = json.loads(path.read_text(encoding="utf-8"))
            if _comparable(committed) != _comparable(payloads[scope]):
                stale.append(f"{path} (stale)")
        if stale:
            print("quality JSON is stale: " + ", ".join(stale))
            return 1
        print("quality JSON is current")
        return 0
    for scope, path in OUTPUTS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_render(payloads[scope]), encoding="utf-8")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
