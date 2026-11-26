"""Ambassador data per region (AMB-1 step 1): eligible institutions and case queues.

Writes ``site/data/<slug>/ambassador_institutions.json`` (schema amb-v1) and
``site/data/<slug>/ambassador_cases.json`` (schema amb-cases-v1) for every registry region with a
predicate. Inputs are ignored (the global partition, raw OpenAlex pages, normalized tables), the
domain cache under ``data/interim/ambassador_domains/`` and owner overrides in
``regions/<slug>/ambassador_domains.csv``.

``--fetch-domains`` is the only network mode. It fetches, for every eligible institution of every
region, the OpenAlex institution record (batches of up to 100 ids, about 1 credit per call, capped
at 20 credits per run, logged to ``data/logs/api_usage.jsonl``) and the ROR v2 record (free, one
request per second, generic User-Agent). Results are cached per institution with fetch dates, so
reruns reuse them. Without it, the build reads the cache and never touches the network.

``--check`` validates the committed files (schema, eligibility, privacy, caps, override CSV) and
never uses the network. When the ignored inputs and the domain cache exist it also rebuilds each
region and fails if the committed copy is stale (the committed ``generated_at`` is reused for the
comparison); otherwise it prints SKIP for the staleness check.

Usage:
    py -3.14 scripts/build_ambassador_data.py                   # write every region (cache only)
    py -3.14 scripts/build_ambassador_data.py --fetch-domains   # fill the cache, then write
    py -3.14 scripts/build_ambassador_data.py --slug norway     # one region
    py -3.14 scripts/build_ambassador_data.py --check           # validate; exit 1 on problems
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.build.ambassadors import (  # noqa: E402
    ADDITIONS_CSV,
    USAGE_LOG,
    FetchLimitError,
    RegionCorpus,
    additions_problems,
    build_from_corpus,
    encode,
    inputs_present,
    load_corpus,
    missing_domain_cache,
    overrides_problems,
    run_fetch,
    validate_outputs,
)
from atlas.ingest.openalex import load_openalex_key  # noqa: E402
from atlas.regions.registry import Region, load_registry  # noqa: E402
from atlas.regions.scope import region_data_dir  # noqa: E402

INSTITUTIONS_FILE = "ambassador_institutions.json"
CASES_FILE = "ambassador_cases.json"


def eligible_regions() -> list[Region]:
    """Planned or active regions with a predicate (the root tier has none)."""
    return [
        region
        for region in load_registry().regions
        if region.tier != "root"
        and region.predicate is not None
        and region.status in ("planned", "active")
    ]


def _select(regions: list[Region], slug: str | None) -> list[Region]:
    if slug is None:
        return regions
    chosen = [region for region in regions if region.slug == slug]
    if not chosen:
        known = ", ".join(region.slug for region in regions)
        raise SystemExit(f"ERROR: {slug!r} is not an eligible region (eligible: {known})")
    return chosen


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


def _override_path(region: Region) -> Path:
    return ROOT / "regions" / region.slug / "ambassador_domains.csv"


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _fetch(regions: list[Region]) -> dict[str, RegionCorpus]:
    """Load every eligible region, fill the domain cache (network) and return the corpora."""
    corpora = {region.slug: load_corpus(region, ROOT) for region in regions}
    load_openalex_key(ROOT / ".env")
    stats = run_fetch(corpora, ROOT, usage_log=ROOT / USAGE_LOG)
    print(
        f"fetch: {stats['institutions']} eligible institutions; OpenAlex calls "
        f"{stats['openalex_calls']}; ROR requests {stats['ror_requests']}; "
        f"OpenAlex credits {stats['credits']}"
    )
    return corpora


def _write(regions: list[Region], corpora: dict[str, RegionCorpus]) -> int:
    for region in regions:
        corpus = corpora.get(region.slug) or load_corpus(region, ROOT)
        notes: list[str] = []
        try:
            institutions, cases = build_from_corpus(region, corpus, ROOT, notes=notes)
        except ValueError as error:
            print(f"ERROR: {region.slug}: {error}", file=sys.stderr)
            return 1
        for note in notes:
            print(f"note: {note}")
        problems = validate_outputs(institutions, cases, region.slug)
        if problems:
            for problem in problems[:20]:
                print(f"ERROR: {region.slug}: {problem}", file=sys.stderr)
            return 1
        folder = region_data_dir(region)
        _write_atomic(folder / INSTITUTIONS_FILE, encode(institutions))
        _write_atomic(folder / CASES_FILE, encode(cases))
        rows = institutions["institutions"]
        with_domains = sum(1 for row in rows if row["domains"])
        needing = [row for row in rows if row["needs_domain"]]
        print(
            f"{region.slug}: {len(rows)} eligible institutions ({with_domains} with domains, "
            f"{len(needing)} need a domain); cases {cases['counts']}"
        )
        for row in needing[:5]:
            print(f"  needs domain: {row['name']} ({row['id']}, {row['works']} works)")
    return 0


def _check(regions: list[Region]) -> int:
    failed = False
    for problem in additions_problems(ROOT / ADDITIONS_CSV):
        print(f"FAIL: {_rel(ROOT / ADDITIONS_CSV)}: {problem}")
        failed = True
    for region in regions:
        folder = region_data_dir(region)
        label = region.slug
        override_file = _override_path(region)
        if not override_file.is_file():
            print(f"FAIL: {label}: missing {_rel(override_file)}")
            failed = True
        else:
            for problem in overrides_problems(override_file):
                print(f"FAIL: {label}: {problem}")
                failed = True
        committed: dict[str, dict] = {}
        for name in (INSTITUTIONS_FILE, CASES_FILE):
            path = folder / name
            if not path.is_file():
                print(f"FAIL: {label}: missing {_rel(path)}")
                failed = True
                break
            committed[name] = json.loads(path.read_text(encoding="utf-8"))
        if len(committed) != 2:
            continue
        problems = validate_outputs(committed[INSTITUTIONS_FILE], committed[CASES_FILE], label)
        if problems:
            for problem in problems[:20]:
                print(f"FAIL: {label}: {problem}")
            failed = True
            continue
        print(f"PASS: {label}: schema, eligibility, privacy and caps")
        if not inputs_present(region, ROOT):
            print(f"SKIP: {label}: staleness; ignored inputs not present")
            continue
        corpus = load_corpus(region, ROOT)
        missing = missing_domain_cache(ROOT, corpus)
        if missing:
            print(
                f"SKIP: {label}: staleness; domain cache lacks {len(missing)} eligible "
                "institutions (run with --fetch-domains)"
            )
            continue
        stamp = committed[INSTITUTIONS_FILE]["generated_at"]
        if additions_problems(ROOT / ADDITIONS_CSV):
            continue  # reported above; the rebuild would stop on the same rows
        try:
            institutions, cases = build_from_corpus(region, corpus, ROOT, generated_at=stamp)
        except ValueError as error:
            print(f"FAIL: {label}: {error}")
            failed = True
            continue
        stale = [
            name
            for name, payload in ((INSTITUTIONS_FILE, institutions), (CASES_FILE, cases))
            if committed[name] != payload
        ]
        if stale:
            print(
                f"FAIL: {label}: stale {', '.join(stale)}; rerun scripts/build_ambassador_data.py"
            )
            failed = True
        else:
            print(f"PASS: {label}: freshness")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--slug", help="one region slug (default: every eligible region)")
    parser.add_argument("--check", action="store_true", help="validate committed files (offline)")
    parser.add_argument(
        "--fetch-domains",
        action="store_true",
        help="fetch OpenAlex and ROR records for all eligible institutions (network, capped)",
    )
    args = parser.parse_args(argv)
    if args.check and args.fetch_domains:
        parser.error("--check and --fetch-domains cannot be combined")
    regions = _select(eligible_regions(), args.slug)
    if args.check:
        return _check(regions)
    corpora: dict[str, RegionCorpus] = {}
    if args.fetch_domains:
        try:
            corpora = _fetch(eligible_regions())
        except FetchLimitError as error:
            print(f"ERROR: fetch stopped by the budget guard: {error}", file=sys.stderr)
            return 1
    return _write(regions, corpora)


if __name__ == "__main__":
    raise SystemExit(main())
