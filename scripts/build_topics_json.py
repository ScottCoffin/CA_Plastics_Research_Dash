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

from atlas.regions.registry import load_registry  # noqa: E402
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


def build_region_payloads(
    index: Mapping[str, Any], region: str, generated_at: str
) -> dict[str, dict[str, Any]]:
    """Build the same chart schema from one region's exported, unscreened works."""
    import json

    region_file = ROOT / "site" / "data" / region / "region.json"
    region_meta = json.loads(region_file.read_text(encoding="utf-8"))
    partial_years = {
        int(row["year"]) for row in region_meta.get("works_by_year", []) if row.get("partial")
    }
    works = index.get("works", [])
    totals: dict[int, int] = {}
    counts: dict[str, dict[int, int]] = {}
    for work in works:
        year = int(work.get("year") or 0)
        if not year:
            continue
        totals[year] = totals.get(year, 0) + 1
        for tag in set(work.get("domain_tags") or []):
            counts.setdefault(str(tag), {})[year] = counts.setdefault(str(tag), {}).get(year, 0) + 1
    years = sorted(totals)
    labels_path = ROOT / "site" / "assets" / "topics.js"
    import yaml

    from atlas.analytics.rising_share import evaluate_tags
    from atlas.analytics.tag_cooccurrence import pair_statistics
    from atlas.analytics.topic_series import CaWork
    from atlas.build.seo import load_topic_labels

    labels = load_topic_labels(labels_path)
    tags = []
    for tag in sorted(counts):
        by_year = [
            {
                "year": year,
                "count": counts[tag].get(year, 0),
                "share": counts[tag].get(year, 0) / totals[year] if totals.get(year) else None,
                "partial": year in partial_years,
            }
            for year in years
        ]
        complete = sum(row["count"] for row in by_year if not row["partial"])
        tags.append(
            {
                "tag": tag,
                "label": labels.get(tag, tag.replace("_", " ").title()),
                "approval": "unscreened",
                "status": "unscreened_query_hit",
                "accuracy_state": INSUFFICIENT if complete < MIN_COMPLETE_WORKS else EXPERIMENTAL,
                "complete_works": complete,
                "by_year": by_year,
                "label_source_totals": {
                    "all_sources": None,
                    "owner_model_only": None,
                    "rule_only": None,
                },
            }
        )
    year_rows = [
        {"year": year, "count": totals[year], "partial": year in partial_years} for year in years
    ]
    last_complete = max((year for year in years if year not in partial_years), default=None)
    complete_works = [
        work
        for work in works
        if int(work.get("year") or 0) and int(work["year"]) not in partial_years
    ]
    taxonomy = yaml.safe_load((ROOT / "config" / "taxonomy.yml").read_text(encoding="utf-8"))
    observed = set(counts)
    region_taxonomy = {
        **taxonomy,
        "domain_tags": [
            entry for entry in taxonomy.get("domain_tags", []) if entry.get("id") in observed
        ],
    }
    complete_tags = sorted(observed)
    pair_result = pair_statistics(
        [frozenset(work.get("domain_tags") or []) for work in complete_works], complete_tags
    )
    pairs = [
        {
            **pair,
            "label_a": labels.get(pair["a"], pair["a"]),
            "label_b": labels.get(pair["b"], pair["b"]),
        }
        for pair in pair_result["pairs"]
    ]
    series = {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "scope": region,
        "region_name": region_meta.get("name", region),
        "as_of": region_meta.get("generated_at"),
        "last_complete_year": last_complete,
        "unit": f"unscreened {region_meta.get('name', region)} work",
        "notice": (
            "These are unscreened OpenAlex query hits. Topic tags are provisional domain labels; "
            "no regional relevance screening has been applied."
        ),
        "page_scope": (
            f"Counts and shares of unscreened {region_meta.get('name', region)} works by "
            "publication year. This is not a measure of importance."
        ),
        "accuracy_rule": (
            "Validated requires human-labelled gold data; no regional gold labels are available. "
            "Small counts are marked insufficient data; other tags are experimental."
        ),
        "plastic_related_by_year": year_rows,
        "tags": tags,
        "tags_excluded": [],
        "lens": {
            "status": "not_available",
            "message": "No regional analytic lens is computed.",
            "caption": "Lens counts are not available for this regional export.",
            "framing_rule": "not computed",
            "series": [],
        },
        "cooccurrence": {
            "window": "complete_years",
            "variant": "unscreened_domain_tags",
            "window_years": {
                "from": min((year for year in years if year not in partial_years), default=None),
                "to": last_complete,
            },
            "min_pair_n": 5,
            "pairs": pairs,
        },
        "version": {
            "schema": SCHEMA,
            "builder": "scripts/build_topics_json.py",
            "file": "topics_timeseries.json",
            "source": "region index domain_tags",
            "region": region,
        },
    }
    ca_works = [
        CaWork(
            work_id=str(work.get("work_id") or ""),
            year=int(work["year"]),
            plastic_related=True,
            topic_sources={str(tag): "rule" for tag in (work.get("domain_tags") or [])},
        )
        for work in works
        if work.get("year") and work.get("work_id")
    ]
    institution_map = {
        str(work.get("work_id")): frozenset(
            str(value) for value in (work.get("institution_ids") or [])
        )
        for work in works
        if work.get("work_id")
    }
    rising = evaluate_tags(
        ca_works,
        region_taxonomy,
        last_complete=last_complete or max(years, default=0),
        institutions=institution_map,
    )
    bursts = {
        "schema": SCHEMA,
        "generated_at": generated_at,
        "scope": region,
        "as_of": region_meta.get("generated_at"),
        "last_complete_year": last_complete,
        "test": rising["test"],
        "alpha": rising["alpha"],
        "window_years": rising["window_years"],
        "min_window_works": rising["min_window_works"],
        "statistical_screen": (
            "Cochran-Armitage screen with a 3-year volume threshold, rule-only tag sensitivity, "
            "and leave-one-institution-out checks. The corpus is unscreened OpenAlex query hits; "
            "owner/model label variants are not available. No correction is made for multiple "
            "testing across tags. Flags are prompts for review, not confirmed findings."
        ),
        "flagged": rising["flagged"],
        "tags": [
            {
                "tag": tag["tag"],
                "label": tag["label"],
                "accuracy_state": next(
                    (row["accuracy_state"] for row in tags if row["tag"] == tag["tag"]),
                    INSUFFICIENT,
                ),
                **{
                    key: tag[key]
                    for key in (
                        "flag",
                        "reasons_failed",
                        "trend",
                        "window_years",
                        "window_count",
                        "total_complete_years",
                        "sensitivity",
                        "loio",
                    )
                },
            }
            for tag in rising["tags"]
        ],
        "tags_excluded": rising["tags_excluded"],
        "bursts": {
            "status": "not_computed",
            "reason": (
                "Kleinberg-style bursts are not implemented; the rising-share test is reported "
                "separately."
            ),
        },
        "version": {
            "schema": SCHEMA,
            "builder": "scripts/build_topics_json.py",
            "file": "topic_bursts.json",
            "source": "region index domain_tags",
            "region": region,
        },
    }
    return {"topics_timeseries.json": series, "topic_bursts.json": bursts}


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
    parser.add_argument("--region", default="california", help="registry slug (default california)")
    args = parser.parse_args(argv)
    generated_at = datetime.now(UTC).isoformat(timespec="seconds")
    if args.region == "california":
        out_dir = out_dir or region_data_dir()
        try:
            inputs = load_inputs(analytics_dir)
        except FileNotFoundError as error:
            print(MISSING_MESSAGE.format(names=error))
            return 1
        payloads = build_payloads(inputs, generated_at)
    else:
        try:
            load_registry().get(args.region)
        except KeyError as error:
            parser.error(str(error.args[0]))
        out_dir = out_dir or ROOT / "site" / "data" / args.region
        index = json.loads((out_dir / "index.json").read_text(encoding="utf-8"))
        payloads = build_region_payloads(index, args.region, generated_at)
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
