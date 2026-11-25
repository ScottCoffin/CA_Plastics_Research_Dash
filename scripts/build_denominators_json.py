"""Build site/data/denominators.json, the public global-denominator file (BQ-2.4).

Reads data/processed/analytics/denominator_series.json (written by
scripts/build_denominator_series.py)
and writes the committed public file: plain-language labels, per-series yearly counts, the allowed
ratio pairs, the metrics block (counts, index, log-linear CAGR with a 95% interval, shares) and a
"what this is and is not" text. Series D is beside-only and is never divided. B2 is listed as not
computed. No network calls.

    py -3.14 scripts/build_denominators_json.py            # write the public file
    py -3.14 scripts/build_denominators_json.py --check    # validate the committed file

--check always validates the committed file. When the ignored input exists it also fails when the
committed file differs from a rebuild from that input (stale). When the input is absent (CI has no
data/ tree) the staleness check prints SKIP and the command exits 0.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "data" / "processed" / "analytics" / "denominator_series.json"
DEFAULT_OUTPUT = ROOT / "site" / "data" / "denominators.json"
SCHEMA_VERSION = "bq2-v1"
INPUT_SCHEMA_VERSION = "denominator_series.v1"

SERIES_ORDER = ["A", "A-article_review", "B", "B-article_review", "C", "D"]
SERIES_LABELS = {
    "A": "All matching records (all OpenAlex types)",
    "A-article_review": "Matching records, article and review types only",
    "B": "Pollution-core records (all OpenAlex types)",
    "B-article_review": "Pollution-core records, article and review types only",
    "C": "California-connected matching records",
    "D": "Published plastic-related works, California (curated; shown beside only)",
}
NOT_COMPUTED_LABELS = {
    "B2": "Lifecycle and society records by labelled centrality (not computed; shown beside only)",
}
# Allowed like-for-like shares as (numerator, denominator). Every other pair is refused.
RATIO_PAIRS = [("B", "A"), ("C", "A"), ("B-article_review", "A-article_review")]
RATIO_LABELS = {
    "B/A": "Pollution-core share of matching records",
    "C/A": "California share of matching records",
    "B-article_review/A-article_review": "Pollution-core share, article and review types only",
}
WHAT_THIS_IS = (
    "Counts of OpenAlex records by publication year. Each record is one OpenAlex work ID, "
    "and duplicate "
    "records are not merged. A is every record that matches the plastics search query. C "
    "is the part of "
    "those matching records that has an author at a California institution, so C/A is the "
    "California share "
    "of matching records. B is a narrower set that also matches the pollution-core terms, "
    "so B/A is the "
    "pollution-core share of matching records."
)
WHAT_THIS_IS_NOT = (
    "It is not a share of all plastics research, and it is not a Web of Science total. "
    "The published "
    "plastic-related works (D) are curated works, so they are shown beside the counts and "
    "never divided. "
    "Retracted-flagged records stay in the all-types counts, because OpenAlex cannot "
    "separate them there."
)
ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
WOS_TOTAL = re.compile(r"Web of Science[^.\n]{0,40}\d", re.IGNORECASE)


def _ratio_id(numerator: str, denominator: str) -> str:
    return f"{numerator}/{denominator}"


def _series_block(sid: str, source: dict[str, Any]) -> dict[str, Any]:
    retractions = str(source.get("retractions", ""))
    return {
        "id": sid,
        "label": SERIES_LABELS[sid],
        "counting_unit": source["counting_unit"],
        "sensitivity": source["sensitivity"],
        "beside_only": bool(source["beside_only"]),
        "comparable_with": sorted(source.get("comparable_with") or []),
        "retraction_split": retractions.startswith("separate"),
        "undated_records": int(source.get("undated") or 0),
        "years": [
            {
                "year": int(row["year"]),
                "count": int(row["count"]),
                "retracted": None if row.get("retracted") is None else int(row["retracted"]),
                "partial_year": bool(row["partial_year"]),
            }
            for row in sorted(source["years"], key=lambda r: r["year"])
        ],
    }


def _check_pairs(series: dict[str, dict[str, Any]], input_pairs: list[list[str]]) -> None:
    allowed = {frozenset((n, d)) for n, d in RATIO_PAIRS}
    listed = {frozenset(pair) for pair in input_pairs}
    if listed != allowed:
        raise ValueError(
            f"ratio_pairs {sorted(map(sorted, listed))} do not match the allowed pairs"
        )
    for numerator, denominator in RATIO_PAIRS:
        n, d = series[numerator], series[denominator]
        if n["counting_unit"] != d["counting_unit"] or n["sensitivity"] != d["sensitivity"]:
            raise ValueError(f"{numerator}/{denominator} mixes counting units or sensitivities")
        if n["beside_only"] or d["beside_only"]:
            raise ValueError(f"{numerator}/{denominator} includes a beside-only series")
        if denominator not in n["comparable_with"] or numerator not in d["comparable_with"]:
            raise ValueError(
                f"{numerator}/{denominator} is not listed in comparable_with on both sides"
            )


def build_payload(
    source: dict[str, Any], *, generated_at: str, input_sha256: str
) -> dict[str, Any]:
    """Return the public payload for a parsed denominator_series.json (no file access)."""
    if source.get("schema_version") != INPUT_SCHEMA_VERSION:
        raise ValueError(f"input schema_version must be {INPUT_SCHEMA_VERSION!r}")
    series_in = source["series"]
    unknown = set(series_in) - set(SERIES_ORDER)
    if unknown:
        raise ValueError(f"unknown input series: {sorted(unknown)}")
    _check_pairs(series_in, source["ratio_pairs"])
    not_computed_in = source.get("not_computed", {})
    if set(not_computed_in) - set(NOT_COMPUTED_LABELS):
        raise ValueError("unknown not_computed series in the input")

    metrics = copy.deepcopy(source["metrics"])
    if set(metrics["series"]) - set(SERIES_ORDER):
        raise ValueError("metrics name an unknown series")
    if set(metrics["shares"]) != {_ratio_id(n, d) for n, d in RATIO_PAIRS}:
        raise ValueError("metrics shares do not match the allowed ratio pairs")

    series = [_series_block(sid, series_in[sid]) for sid in SERIES_ORDER if sid in series_in]
    ratio_pairs = [
        {
            "id": _ratio_id(n, d),
            "numerator": n,
            "denominator": d,
            "label": RATIO_LABELS[_ratio_id(n, d)],
            "sensitivity": series_in[n]["sensitivity"],
        }
        for n, d in RATIO_PAIRS
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "version": {
            "query_version": source["query_version"],
            "as_of": source["as_of"],
            "last_complete_year": source["last_complete_year"],
            "window_start": metrics["window"]["start"],
            "window_end": metrics["window"]["end"],
        },
        "source": {"schema_version": INPUT_SCHEMA_VERSION, "sha256": input_sha256},
        "what_this_is_and_is_not": {"is": WHAT_THIS_IS, "is_not": WHAT_THIS_IS_NOT},
        "series": series,
        "not_computed": [
            {"id": sid, "label": NOT_COMPUTED_LABELS[sid], "status": "not computed"}
            for sid in sorted(not_computed_in)
        ],
        "ratio_pairs": ratio_pairs,
        "metrics": metrics,
    }


def check_payload(payload: dict[str, Any]) -> list[str]:
    """Return problems with a public payload (empty when it is valid)."""
    problems: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version must be {SCHEMA_VERSION!r}")
    if not isinstance(payload.get("generated_at"), str) or not ISO_UTC.match(
        payload["generated_at"]
    ):
        problems.append("generated_at must be an ISO 8601 UTC time")
    version = payload.get("version") or {}
    for key in ("query_version", "as_of", "last_complete_year"):
        if key not in version:
            problems.append(f"version.{key} is missing")
    series = {row["id"]: row for row in payload.get("series", [])}
    if "B2" in series or "D" in {n for n, _ in RATIO_PAIRS} | {d for _, d in RATIO_PAIRS}:
        problems.append("B2 is never a series here and D is never a ratio part")
    if set(series) - set(SERIES_ORDER):
        problems.append(f"unknown series: {sorted(set(series) - set(SERIES_ORDER))}")
    if "D" in series and not series["D"]["beside_only"]:
        problems.append("D must be beside_only")
    allowed = {_ratio_id(n, d): (n, d) for n, d in RATIO_PAIRS}
    listed = payload.get("ratio_pairs", [])
    if sorted(row["id"] for row in listed) != sorted(allowed):
        problems.append("ratio_pairs must list exactly the allowed pairs")
    for row in listed:
        if row["id"] not in allowed or (row["numerator"], row["denominator"]) != allowed[row["id"]]:
            problems.append(f"ratio {row['id']} is not an allowed pair")
            continue
        n, d = series.get(row["numerator"]), series.get(row["denominator"])
        if n is None or d is None:
            problems.append(f"ratio {row['id']} names a missing series")
        elif n["counting_unit"] != d["counting_unit"] or n["sensitivity"] != d["sensitivity"]:
            problems.append(f"ratio {row['id']} mixes counting units or sensitivities")
    metrics = payload.get("metrics") or {}
    if set(metrics.get("shares", {})) != set(allowed):
        problems.append("metrics.shares must list exactly the allowed pairs")
    if not payload.get("what_this_is_and_is_not", {}).get("is_not"):
        problems.append("what_this_is_and_is_not.is_not is missing")
    if WOS_TOTAL.search(json.dumps(payload, ensure_ascii=False)):
        problems.append("a Web of Science total appears in the text")
    return problems


def render(payload: dict[str, Any]) -> bytes:
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    return text.encode("utf-8")


def _rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _rebuild(input_path: Path, generated_at: str) -> dict[str, Any]:
    raw = input_path.read_bytes()
    return build_payload(
        json.loads(raw.decode("utf-8")),
        generated_at=generated_at,
        input_sha256=hashlib.sha256(raw).hexdigest(),
    )


def run_check(input_path: Path, output_path: Path) -> int:
    if not output_path.exists():
        print(f"FAIL: {_rel(output_path)} is missing; run scripts/build_denominators_json.py")
        return 1
    committed = json.loads(output_path.read_text(encoding="utf-8"))
    problems = check_payload(committed)
    if problems:
        print("FAIL: " + "; ".join(problems))
        return 1
    if not input_path.exists():
        print(f"SKIP: staleness not checked; {_rel(input_path)} is absent (ignored input)")
        print(f"OK: {_rel(output_path)} is valid")
        return 0
    if _rebuild(input_path, committed["generated_at"]) != committed:
        print(
            f"STALE: {_rel(output_path)} differs from a rebuild; "
            "run scripts/build_denominators_json.py"
        )
        return 1
    print(f"OK: {_rel(output_path)} is valid and matches {_rel(input_path)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check", action="store_true", help="validate the committed file; write nothing"
    )
    args = parser.parse_args(argv)
    if args.check:
        return run_check(args.input, args.output)
    if not args.input.exists():
        print(
            f"ERROR: {_rel(args.input)} is missing; run scripts/build_denominator_series.py first"
        )
        return 1
    generated_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = _rebuild(args.input, generated_at)
    problems = check_payload(payload)
    if problems:
        print("ERROR: " + "; ".join(problems))
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(render(payload))
    print(f"Wrote {_rel(args.output)} ({len(payload['series'])} series)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
