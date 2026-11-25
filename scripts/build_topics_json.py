"""BQ-4.4: public topic-evolution payloads (schema bq4-v1) for /california/topics.

    py -3.14 scripts/build_topics_json.py            # write the two topic JSON files
    py -3.14 scripts/build_topics_json.py --check    # fail when the committed files are stale

Inputs are the gitignored analytics outputs under data/processed/analytics/. Build them first:

    py -3.14 scripts/build_topic_series.py
    py -3.14 scripts/build_rising_share.py
    py -3.14 scripts/build_tag_cooccurrence.py

The builder reads only those JSON files (never the parquet or the live labels), so the payloads
stay on the frozen labels snapshot. Missing inputs fail with a message naming the commands above.
Accuracy rule and file schemas: docs/TOPICS_PAGE.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.regions.scope import region_data_dir  # noqa: E402

SCHEMA = "bq4-v1"
ANALYTICS_DIR = ROOT / "data" / "processed" / "analytics"
INPUT_FILES = {
    "topic_series": "topic_series.json",
    "rising_share": "rising_share.json",
    "tag_cooccurrence": "tag_cooccurrence.json",
}
SOURCE_SCHEMAS = {
    "topic_series": "bq4-series-v1",
    "rising_share": "bq4-rising-v1",
    "tag_cooccurrence": "bq4-cooc-v1",
}
OUTPUT_FILES = ("topics_timeseries.json", "topic_bursts.json")
MISSING_MESSAGE = (
    "analytics inputs missing under data/processed/analytics/ ({names}). Build them first: "
    "py -3.14 scripts/build_topic_series.py; py -3.14 scripts/build_rising_share.py; "
    "py -3.14 scripts/build_tag_cooccurrence.py"
)

# Accuracy states (docs/TOPICS_PAGE.md). The page shows the state as a text badge.
VALIDATED = "validated"
EXPERIMENTAL = "experimental"
INSUFFICIENT = "insufficient data"
MIN_COMPLETE_WORKS = 10
NO_LABELS_STATUS = "no_labels_yet"
ACCURACY_RULE = (
    "validated only when a per-tag F1 from gold labels exists (none do yet); insufficient data "
    "when the tag has fewer than 10 works in complete years or has no labels yet; otherwise "
    "experimental."
)
LABEL_NOTICE = "Tag labels come from rules; no tag has been validated against gold labels yet."
PAGE_SCOPE = (
    "Counts and shares of plastic-related California works by year. This is not a measure of "
    "importance, and the labels are provisional."
)
RISING_RULE = (
    "A rising flag is a statistical screen (Cochran-Armitage trend, volume, label-source and "
    "leave-one-institution-out checks). It has no correction for multiple testing across tags, so "
    "treat each flag as a prompt for review, not a confirmed finding."
)
BURSTS_NOT_COMPUTED = {
    "status": "not_computed",
    "reason": (
        "Kleinberg-style bursts are not implemented (optional in A3). The rising-share trend test "
        "in this file answers the rising question; see docs/RISING_SHARE.md."
    ),
}


def accuracy_state(tag: Mapping[str, Any], gold_f1: Mapping[str, float] | None = None) -> str:
    """Accuracy state for one reported tag. ``gold_f1`` maps tag id to gold F1 (none exist yet)."""
    if gold_f1 and tag["tag"] in gold_f1:
        return VALIDATED
    if tag.get("status") == NO_LABELS_STATUS or complete_works(tag) < MIN_COMPLETE_WORKS:
        return INSUFFICIENT
    return EXPERIMENTAL


def complete_works(tag: Mapping[str, Any]) -> int:
    """Works with the tag in complete years (the year-series counts, partial years excluded)."""
    return sum(int(row["count"]) for row in tag.get("by_year", []) if not row.get("partial"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs(analytics_dir: Path) -> dict[str, Any]:
    """Parse the three analytics outputs and hash their bytes. Raises FileNotFoundError."""
    missing = [name for name in INPUT_FILES.values() if not (analytics_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(", ".join(missing))
    loaded: dict[str, Any] = {}
    for key, name in INPUT_FILES.items():
        path = analytics_dir / name
        loaded[key] = {
            "data": json.loads(path.read_text(encoding="utf-8")),
            "sha256": _sha256(path),
        }
    return loaded


def _version(inputs: Mapping[str, Any], schema_key: str) -> dict[str, Any]:
    series = inputs["topic_series"]["data"]
    return {
        "schema": SCHEMA,
        "source_schemas": dict(SOURCE_SCHEMAS),
        "builder": "scripts/build_topics_json.py",
        "file": schema_key,
        "inputs": {
            key: {"file": INPUT_FILES[key], "sha256": inputs[key]["sha256"]} for key in INPUT_FILES
        },
        "labels_snapshot_content_sha256": series["labels_snapshot"]["content_sha256"],
        "gold_f1_tags": [],
    }


def _labels(series: Mapping[str, Any]) -> dict[str, str]:
    return {tag["tag"]: tag["label"] for tag in series["ca"]["tags"]}


def _tag_entry(tag: Mapping[str, Any], gold_f1: Mapping[str, float] | None) -> dict[str, Any]:
    return {
        "tag": tag["tag"],
        "label": tag["label"],
        "approval": tag["approval"],
        "status": tag["status"],
        "accuracy_state": accuracy_state(tag, gold_f1),
        "complete_works": complete_works(tag),
        "by_year": [
            {
                "year": row["year"],
                "count": row["count"],
                "share": row["share"],
                "partial": row["partial"],
            }
            for row in tag["by_year"]
        ],
        "label_source_totals": {
            variant: tag["sensitivity"][variant]["total"]
            for variant in ("all_sources", "owner_model_only", "rule_only")
        },
    }


def _pairs(cooc: Mapping[str, Any], labels: Mapping[str, str]) -> list[dict[str, Any]]:
    window = cooc["variants"]["all_sources"]["windows"]["complete_years"]
    rows = []
    for pair in window["pairs"]:
        rows.append(
            {
                "a": pair["a"],
                "b": pair["b"],
                "label_a": labels.get(pair["a"], pair["a"]),
                "label_b": labels.get(pair["b"], pair["b"]),
                "n_ab": pair["n_ab"],
                "n_a": pair["n_a"],
                "n_b": pair["n_b"],
                "N": pair["N"],
                "jaccard": pair["jaccard"],
                "lift": pair["lift"],
                "phi": pair["phi"],
                "status": pair["status"],
            }
        )
    return rows


def build_timeseries_payload(
    inputs: Mapping[str, Any], *, generated_at: str, gold_f1: Mapping[str, float] | None = None
) -> dict[str, Any]:
    series = inputs["topic_series"]["data"]
    cooc = inputs["tag_cooccurrence"]["data"]
    ca = series["ca"]
    lens = series["lens"]
    labels = _labels(series)
    tags = [_tag_entry(tag, gold_f1) for tag in ca["tags"]]
    return {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "scope": "california",
        "as_of": series["as_of"],
        "last_complete_year": series["last_complete_year"],
        "unit": "plastic-related California work",
        "notice": LABEL_NOTICE,
        "page_scope": PAGE_SCOPE,
        "accuracy_rule": ACCURACY_RULE,
        "plastic_related_by_year": ca["plastic_related_by_year"],
        "tags": tags,
        "tags_excluded": ca["tags_excluded"],
        "lens": {
            "status": lens["status"],
            "message": lens["message"],
            "caption": lens["caption"],
            "framing_rule": lens["framing_rule"],
            "series": lens["series"],
        },
        "cooccurrence": {
            "window": "complete_years",
            "variant": "all_sources",
            "window_years": {
                "from": cooc["windows"]["complete_years"]["from"],
                "to": cooc["windows"]["complete_years"]["to"],
            },
            "min_pair_n": cooc["min_pair_n"],
            "pairs": _pairs(cooc, labels),
        },
        "version": _version(inputs, "topics_timeseries.json"),
    }


def build_bursts_payload(
    inputs: Mapping[str, Any], *, generated_at: str, gold_f1: Mapping[str, float] | None = None
) -> dict[str, Any]:
    series = inputs["topic_series"]["data"]
    rising = inputs["rising_share"]["data"]
    source_tags = {tag["tag"]: tag for tag in series["ca"]["tags"]}
    tags = []
    for tag in rising["tags"]:
        tags.append(
            {
                "tag": tag["tag"],
                "label": tag["label"],
                "accuracy_state": accuracy_state(
                    source_tags.get(tag["tag"], {"tag": tag["tag"]}), gold_f1
                ),
                "flag": tag["flag"],
                "reasons_failed": tag["reasons_failed"],
                "trend": {key: tag["trend"][key] for key in ("z", "p", "slope_sign")},
                "window_years": tag["window_years"],
                "window_count": tag["window_count"],
                "total_complete_years": tag["total_complete_years"],
                "sensitivity": dict(tag["sensitivity"]),
                "loio": {
                    key: tag["loio"][key]
                    for key in ("pass", "worst_p", "worst_institution", "institutions_tested")
                },
            }
        )
    return {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "scope": "california",
        "as_of": rising["as_of"],
        "last_complete_year": rising["last_complete_year"],
        "test": rising["test"],
        "alpha": rising["alpha"],
        "window_years": rising["window_years"],
        "min_window_works": rising["min_window_works"],
        "statistical_screen": RISING_RULE,
        "flagged": rising["flagged"],
        "tags": tags,
        "tags_excluded": rising["tags_excluded"],
        "bursts": dict(BURSTS_NOT_COMPUTED),
        "version": _version(inputs, "topic_bursts.json"),
    }


def build_payloads(inputs: Mapping[str, Any], generated_at: str) -> dict[str, dict[str, Any]]:
    return {
        "topics_timeseries.json": build_timeseries_payload(inputs, generated_at=generated_at),
        "topic_bursts.json": build_bursts_payload(inputs, generated_at=generated_at),
    }


def _comparable(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k != "generated_at"}


def _render(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(
    argv: list[str] | None = None,
    *,
    analytics_dir: Path = ANALYTICS_DIR,
    out_dir: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="fail when the committed JSON is stale"
    )
    args = parser.parse_args(argv)
    out_dir = out_dir or region_data_dir()
    try:
        inputs = load_inputs(analytics_dir)
    except FileNotFoundError as error:
        print(MISSING_MESSAGE.format(names=error))
        return 1
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    payloads = build_payloads(inputs, generated_at)
    if args.check:
        stale = []
        for name, payload in payloads.items():
            path = out_dir / name
            if not path.exists():
                stale.append(f"{path} (missing)")
                continue
            committed = json.loads(path.read_text(encoding="utf-8"))
            if _comparable(committed) != _comparable(payload):
                stale.append(f"{path} (stale)")
        if stale:
            print("topics JSON is stale: " + ", ".join(stale))
            return 1
        print("topics JSON is current")
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        path = out_dir / name
        path.write_text(_render(payload), encoding="utf-8")
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
