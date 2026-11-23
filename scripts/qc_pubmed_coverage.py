"""PubMed coverage of Atlas works against a reference set (BQ-S9 part A, ADR-A3-PUBMED).

Offline by default. Without ``--live`` the script reads the reference query files, prints the OR
chunks and the request plan, and makes no network call. ``--live`` runs the count-first date
partitioning against NCBI E-utilities and writes a PMID CSV and a manifest JSON under
``--out-dir`` (data/interim, gitignored). Nothing is written to site/data.

Optional environment: ``NCBI_EMAIL`` is sent as the contact ``email`` parameter and
``NCBI_API_KEY`` as ``api_key`` (10 requests per second instead of 3). Neither value is printed
or written to outputs.

Usage:
    py -3.14 scripts/qc_pubmed_coverage.py --reference-set r1 --affiliation California
    py -3.14 scripts/qc_pubmed_coverage.py --reference-set r2 --affiliation California --live
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.qc.pubmed import (  # noqa: E402
    DEFAULT_CAP,
    DEFAULT_MARGIN,
    ROW_FIELDS,
    RPS_WITH_KEY,
    RPS_WITHOUT_KEY,
    EUtilsClient,
    EUtilsError,
    PartitionError,
    QuerySyntaxError,
    build_terms,
    format_day,
    parse_day,
    read_query_file,
    run_reference_set,
)

REFERENCE_FILES = {
    "r1": ("config/pubmed/r1_include.txt", "config/pubmed/r1_exclude.txt"),
    "r2": ("config/pubmed/r2_include.txt", "config/pubmed/r2_exclude.txt"),
}
DEFAULT_START = "1950/01/01"
DEFAULT_OUT_DIR = ROOT / "data" / "interim" / "pubmed"
DEFAULT_CACHE_DIR = ROOT / "data" / "interim" / "pubmed_cache"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PubMed reference-set coverage (BQ-S9 part A).")
    parser.add_argument("--reference-set", required=True, choices=sorted(REFERENCE_FILES))
    parser.add_argument("--affiliation", help="PubMed [ad] restriction, e.g. California")
    parser.add_argument("--start", default=DEFAULT_START, help="first publication date, YYYY/MM/DD")
    parser.add_argument("--end", help="last publication date, YYYY/MM/DD (default: yesterday)")
    parser.add_argument(
        "--rps", type=float, help="requests per second (default 3, or 10 with NCBI_API_KEY)"
    )
    parser.add_argument(
        "--cap", type=int, default=DEFAULT_CAP, help="ESearch retrieval cap (default 10000)"
    )
    parser.add_argument(
        "--margin",
        type=int,
        default=DEFAULT_MARGIN,
        help="safety margin below the cap (default 500)",
    )
    parser.add_argument(
        "--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="output folder (gitignored data/)"
    )
    parser.add_argument(
        "--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="request cache folder"
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="neither read nor write the request cache"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="print the chunks and request plan, no network call (default)",
    )
    mode.add_argument(
        "--live", action="store_true", help="query NCBI E-utilities and write the outputs"
    )
    return parser


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def _file_stem(reference_set: str, affiliation: str | None) -> str:
    if not affiliation:
        return reference_set
    slug = re.sub(r"[^a-z0-9]+", "_", affiliation.lower()).strip("_")
    return f"{reference_set}_{slug}"


def _print_plan(
    *,
    reference_set: str,
    include_path: Path,
    exclude_path: Path | None,
    affiliation: str | None,
    start: str,
    end: str,
    cap: int,
    margin: int,
    client: EUtilsClient,
    chunk_terms: list[str],
) -> None:
    if client.api_key:
        key_note = "API key set (NCBI limit 10 per second)"
    else:
        key_note = "no API key (NCBI limit 3 per second)"
    email_note = (
        "set, sent as the email parameter (value not printed)" if client.email else "not set"
    )
    example = client.build_url(
        "esearch",
        {
            "db": "pubmed",
            "term": chunk_terms[0],
            "datetype": "pdat",
            "mindate": start,
            "maxdate": end,
            "retmode": "json",
            "retmax": 0,
            "retstart": 0,
        },
        redact=True,
    )
    print(f"PubMed coverage plan for reference set {reference_set} (dry run, no network call)")
    print(f"include: {_rel(include_path)}")
    print(f"exclude: {_rel(exclude_path) if exclude_path else 'none (file absent)'}")
    print(f"affiliation: {affiliation or 'none'}")
    print(f"window: {start} to {end} (publication date, datetype pdat)")
    print(f"partition threshold: {cap - margin} records (cap {cap} minus margin {margin})")
    print(f"rate: {client.rps:g} requests per second; {key_note}")
    print(f"contact email: {email_note}")
    print(f"OR chunks: {len(chunk_terms)}")
    for index, term in enumerate(chunk_terms, start=1):
        print(f"  c{index:03d}: {term}")
    print("request plan (live run):")
    print("  1 ESearch for the whole-query translation over the full window")
    print(
        "  per chunk: count-first date bisection (ESearch, retmax=0) until every partition is "
        "under the threshold, then one ESearch per partition for PMIDs"
    )
    print("  ESummary for each unique PMID in batches of 200 (DOI and year)")
    print(
        f"  minimum {1 + 2 * len(chunk_terms)} ESearch calls plus ESummary batches; "
        "bisection adds calls when a window is over the threshold"
    )
    print(f"example request (secrets redacted): {example}")
    print("re-run with --live to query NCBI and write the PMID CSV and manifest")


def _csv_text(rows: Sequence[Mapping[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=ROW_FIELDS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {field: "" if row.get(field) is None else row[field] for field in ROW_FIELDS}
        )
    return buffer.getvalue()


def _assert_no_contact_values(text: str, secrets: Sequence[str]) -> None:
    """Defensive check: the contact email and API key must never reach an output file."""
    for secret in secrets:
        if secret and secret in text:
            raise EUtilsError("internal check failed: a contact value would have been written")


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    opener: Callable[[str], bytes] | None = None,
) -> int:
    args = _parser().parse_args(argv)
    environ = os.environ if env is None else env
    api_key = environ.get("NCBI_API_KEY") or None
    email = environ.get("NCBI_EMAIL") or None
    rps = args.rps if args.rps is not None else (RPS_WITH_KEY if api_key else RPS_WITHOUT_KEY)
    include_path = ROOT / REFERENCE_FILES[args.reference_set][0]
    exclude_candidate = ROOT / REFERENCE_FILES[args.reference_set][1]
    exclude_path = exclude_candidate if exclude_candidate.exists() else None
    try:
        start = format_day(parse_day(args.start))
        end = (
            format_day(parse_day(args.end))
            if args.end
            else format_day(date.today() - timedelta(days=1))
        )
        include = read_query_file(include_path)
        exclude = read_query_file(exclude_path) if exclude_path else ""
        _, chunk_terms = build_terms(include, exclude, args.affiliation)
        client = EUtilsClient(
            opener=opener,
            rps=rps,
            api_key=api_key,
            email=email,
            cache_dir=None if args.no_cache else args.cache_dir,
        )
        if not args.live:
            _print_plan(
                reference_set=args.reference_set,
                include_path=include_path,
                exclude_path=exclude_path,
                affiliation=args.affiliation,
                start=start,
                end=end,
                cap=args.cap,
                margin=args.margin,
                client=client,
                chunk_terms=chunk_terms,
            )
            return 0

        rows, manifest = run_reference_set(
            args.reference_set,
            include_path=include_path,
            exclude_path=exclude_path,
            affiliation=args.affiliation,
            client=client,
            start=start,
            end=end,
            cap=args.cap,
            margin=args.margin,
        )
        csv_text = _csv_text(rows)
        manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        secrets = [value for value in (email, api_key) if value]
        _assert_no_contact_values(csv_text + manifest_text, secrets)

        stem = _file_stem(args.reference_set, args.affiliation)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        csv_path = args.out_dir / f"{stem}_pmids.csv"
        manifest_path = args.out_dir / f"{stem}_manifest.json"
        csv_path.write_text(csv_text, encoding="utf-8", newline="")
        manifest_path.write_text(manifest_text, encoding="utf-8")
        partitions = sum(len(chunk["partitions"]) for chunk in manifest["chunks"])
        print(
            f"{manifest['total_unique_pmids']} unique PMIDs from {len(manifest['chunks'])} chunks "
            f"and {partitions} partitions"
        )
        print(f"wrote {_rel(csv_path)}")
        print(f"wrote {_rel(manifest_path)}")
    except (EUtilsError, PartitionError, QuerySyntaxError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
