"""Build data/processed/analytics/denominator_series.json (BQ-2.1, BQ-2.2).

Counts the global-denominator series by publication year from stored inputs: A (all types) and
A-article_review, B and B-article_review come from the denominator cache written by
scripts/fetch_denominator_series.py; C and D come from the normalized works, the raw works and the
site index. B2 is listed with its status and not counted. No network calls. The output folder is
gitignored; BQ-2.4 publishes site/data/denominators.json later from this file.

    py -3.14 scripts/build_denominator_series.py            # write the JSON
    py -3.14 scripts/build_denominator_series.py --check    # fail when the JSON is missing or stale

--check exits 0 with a SKIP message when an input is absent (CI has no data/ tree). The as-of
date defaults to today (UTC), so --check also reports stale on a new day; rerun without --check.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.analytics.denominators import (  # noqa: E402
    build_series,
    input_fingerprint,
    load_corpus_records,
    load_denominator_cache,
    load_published_works,
    load_series_config,
    render_payload,
    resolve_cache_entries,
)
from atlas.query import load_query_config  # noqa: E402

CONFIG = ROOT / "config" / "denominator_series.yml"
QUERY_CONFIG = ROOT / "config" / "queries.yml"
CACHE = ROOT / "data" / "interim" / "denominator_series_cache.json"
INDEX = ROOT / "site" / "data" / "index.json"
WORKS = ROOT / "data" / "processed" / "normalized" / "works.parquet"
RAW = ROOT / "data" / "interim" / "works_raw.parquet"
OUTPUT = ROOT / "data" / "processed" / "analytics" / "denominator_series.json"


def _relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _fingerprint(path: Path) -> dict[str, str]:
    fingerprint = input_fingerprint(path)
    fingerprint["path"] = _relative(path)
    return fingerprint


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="fail when the output is missing or stale"
    )
    parser.add_argument(
        "--as-of", type=date.fromisoformat, default=None, help="YYYY-MM-DD; default today (UTC)"
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)

    inputs = {"denominator_cache": CACHE, "index": INDEX, "works": WORKS, "raw": RAW}
    absent = [_relative(path) for path in inputs.values() if not path.exists()]
    if absent:
        if args.check:
            print(f"SKIP: inputs absent ({', '.join(absent)}); nothing checked")
            return 0
        print(f"error: missing inputs: {', '.join(absent)}", file=sys.stderr)
        return 1

    as_of = args.as_of or datetime.now(UTC).date()
    try:
        specs = load_series_config(CONFIG)
        config = load_query_config(QUERY_CONFIG)
        query_version = str(config.get("version") or "")
        payload = build_series(
            specs,
            corpus_records=load_corpus_records(WORKS, RAW),
            published_works=load_published_works(INDEX, WORKS),
            denominator_entries=resolve_cache_entries(
                specs, load_denominator_cache(CACHE), query_config=config
            ),
            as_of=as_of,
            expected_query_version=query_version,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    payload["inputs"] = {name: _fingerprint(path) for name, path in inputs.items()}
    text = render_payload(payload)
    shown = _relative(args.output)

    if args.check:
        if not args.output.exists():
            print(f"FAIL: {shown} is missing; run without --check", file=sys.stderr)
            return 1
        if args.output.read_bytes() != text.encode("utf-8"):
            print(f"FAIL: {shown} is stale; rerun without --check", file=sys.stderr)
            return 1
        print(f"ok: {shown} is current")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    tmp = args.output.with_suffix(args.output.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(args.output)
    last = payload["last_complete_year"]
    summary = []
    for series_id, entry in payload["series"].items():
        row = next((r for r in entry["years"] if r["year"] == last), None)
        if row is not None:
            stale = " (stale)" if entry.get("cache", {}).get("stale") else ""
            summary.append(f"{series_id}={row['count']} in {last}{stale}")
    pending = ", ".join(
        f"{sid} ({info['status']})" for sid, info in payload["not_computed"].items()
    )
    print(f"wrote {shown}: {'; '.join(summary)}; not computed: {pending or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
