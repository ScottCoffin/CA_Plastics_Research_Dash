"""PLAT-4b: partition the global raw store locally (unpublished).

Writes ``works.parquet``, ``work_regions.parquet``, ``authorships.parquet`` and
``institutions.parquet`` under ``--out-dir`` from the gzip pages in ``--raw-dir``.
``--check`` validates existing outputs and exits 0 with SKIP when no raw store exists.
Nothing here touches the network or the site.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from atlas.ingest.global_partition import (
    DEFAULT_OUT_DIR,
    DEFAULT_RAW_DIR,
    NoRawStoreError,
    build_partition,
    check_outputs,
    raw_page_paths,
    summarize,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument(
        "--check", action="store_true", help="validate existing outputs; SKIP without raw pages"
    )
    args = parser.parse_args(argv)

    if args.check:
        if not raw_page_paths(args.raw_dir):
            print(f"SKIP: no raw store pages under {args.raw_dir / 'pages'}")
            return 0
        problems = check_outputs(args.out_dir)
        if problems:
            for problem in problems:
                print(f"FAIL: {problem}")
            return 1
        print("PASS: partition schema, uniqueness and unscreened labels")
        return 0

    try:
        result = build_partition(args.raw_dir, args.out_dir)
    except NoRawStoreError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    counts = summarize(args.out_dir)
    print(f"skipped records without an OpenAlex id: {result.skipped_records}")
    print(f"works: {counts['works']}")
    print(f"works with pmid: {counts['works_with_pmid']}")
    print("works per top-10 countries:")
    for code, count in counts["top_countries"]:
        print(f"  {code}: {count}")
    print(f"works matching {counts['default_region']}: {counts['default_region_works']}")
    print(f"wrote {result.works_path}")
    print(f"wrote {result.work_regions_path} ({result.work_regions} rows)")
    print(
        f"authorship rows: {counts['authorships']} "
        f"(distinct author ids: {counts['distinct_authors']}, "
        f"null author id share: {counts['null_author_id_share']:.4%})"
    )
    print(f"institutions: {counts['institutions']}")
    print(f"wrote {result.authorships_path} ({result.authorships} rows)")
    print(f"wrote {result.institutions_path} ({result.institutions} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
