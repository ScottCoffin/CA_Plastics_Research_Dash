"""Europe PMC recall audit: benchmark, diff against the corpus, ingest missing DOIs."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq

from atlas.ingest import europepmc_audit as audit
from atlas.ingest import openalex as oa
from atlas.query import load_query_config

WORKS = Path("data/processed/normalized/works.parquet")
SITE_INDEX = Path("site/data/index.json")
RAW_OUT = Path("data/interim/works_raw.parquet")


def corpus_state() -> tuple[dict[str, bool], dict[str, str]]:
    """Return (doi -> ca_any_author, doi -> work_id) from the normalized works table."""

    rows = pq.read_table(WORKS, columns=["work_id", "doi", "ca_any_author"]).to_pylist()
    ca: dict[str, bool] = {}
    ids: dict[str, str] = {}
    for row in rows:
        doi = audit.normalize_doi(row["doi"])
        if doi:
            ca[doi] = ca.get(doi, False) or bool(row["ca_any_author"])
            ids[doi] = row["work_id"]
    return ca, ids


def site_ids() -> set[str]:
    data = json.loads(SITE_INDEX.read_text(encoding="utf-8"))
    return {w["work_id"] for w in data["works"]}


def measure(bench: dict[str, dict]) -> dict[str, int]:
    ca, ids = corpus_state()
    pub = site_ids()
    return {
        "in_corpus": sum(1 for d in bench if d in ca),
        "in_corpus_ca": sum(1 for d in bench if ca.get(d)),
        "published": sum(1 for d in bench if d in ids and ids[d] in pub),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="no OpenAlex calls, no merge")
    parser.add_argument("--measure-only", action="store_true", help="re-measure from the cache")
    parser.add_argument("--max-credits", type=float, default=300.0)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/europepmc"))
    parser.add_argument("--out", type=Path, default=Path("scratch/europepmc_audit.json"))
    parser.add_argument(
        "--extra-dois",
        type=Path,
        help="text file, one DOI per line (e.g. S2.5d DataCite outputs); matched the same way",
    )
    args = parser.parse_args()

    today = datetime.now(UTC).date().isoformat()
    config = load_query_config()
    records = audit.fetch_benchmark(cache_dir=args.cache_dir)
    bench = audit.benchmark_dois(records)
    before = measure(bench)
    ca, _ = corpus_state()
    missing = audit.missing_dois(bench, ca)
    queryable = [d for d in missing if audit.is_queryable_doi(d)]
    extra: list[str] = []
    if args.extra_dois:
        lines = args.extra_dois.read_text(encoding="utf-8").splitlines()
        seen = set(queryable)
        for line in lines:
            doi = audit.normalize_doi(line)
            if doi and doi not in ca and doi not in seen and audit.is_queryable_doi(doi):
                extra.append(doi)
                seen.add(doi)
        queryable += extra
        print(f"extra DOIs not in corpus: {len(extra)}")
    batches = audit.doi_batches(queryable)
    print(f"benchmark {len(records)} records, {len(bench)} with DOI, {len(missing)} missing")
    print(f"measured: {before}; {len(batches)} OpenAlex batches planned")
    result: dict = {
        "measured": before,
        "total": len(records),
        "with_doi": len(bench),
        "missing": len(missing),
        "batches": len(batches),
    }
    if not (args.dry_run or args.measure_only):
        oa.load_openalex_key()
        run_id = f"europepmc-audit-{today}"
        fetched = audit.fetch_openalex_by_doi(
            batches, config=config, run_id=run_id, max_credits=args.max_credits
        )
        works = fetched["works"]
        inst = set(oa.load_institution_ids())
        kept = [w for w in works if audit.keep_for_corpus(w, inst)]
        found = {audit.normalize_doi(w.get("doi")) for w in works}
        added, total_rows = audit.merge_works(kept, run_id=run_id, output=RAW_OUT)
        result.update(
            {
                "run_id": run_id,
                "openalex_matched": len(works),
                "kept": len(kept),
                "rejected_gate": len(works) - len(kept),
                "unmatched_dois": len([d for d in queryable if d not in found]),
                "added_new_ids": added,
                "raw_rows": total_rows,
                "credits": fetched["credits"],
                "requests": fetched["requests"],
                "kept_work_ids": sorted(oa.compact_openalex_id(w.get("id")) for w in kept),
            }
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print({k: v for k, v in result.items() if k != "kept_work_ids"})


if __name__ == "__main__":
    main()
