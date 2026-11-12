"""S2.5(c): ingest plastics works listed on CA experts' ORCID records but missing from the corpus.

``data/processed/orcid_profiles.parquet`` (``fetch_orcid_profiles.py``) lists every DOI on
each expert's public ORCID record (``orcid_dois``). DOIs already in the normalized corpus
are dropped. The rest go to OpenAlex as plain DOI filters (1 credit per 50 DOIs, no
title/abstract search, budget-guarded, raw snapshots kept). Each returned work must then
pass, locally:

1. the active query rule on title + abstract (``classify_plastic_text``; exclusions win)
   or the owner's always-relevant rule (micro-nano plastics); OpenAlex type exclusions
   are applied in the request;
2. the California gate used by every supplementary ingest (``keep_for_corpus``: a CA
   raw affiliation or a registry institution on the work itself).

Survivors are merged into ``data/interim/works_raw.parquet``; then run the usual
normalize -> label -> export chain. ``--max-batches`` spreads the work over days.

    PYTHONPATH=src py -3.14 scripts/ingest_orcid_dois.py --dry-run
    PYTHONPATH=src py -3.14 scripts/ingest_orcid_dois.py --max-credits 1500
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pyarrow.parquet as pq

from atlas.ingest import europepmc_audit as audit
from atlas.ingest import openalex as oa
from atlas.ingest.normalize import _abstract_from_inverted_index
from atlas.nlp.labels import always_relevant, classify_plastic_text
from atlas.query import load_query_config

PROFILES = Path("data/processed/orcid_profiles.parquet")
WORKS = Path("data/processed/normalized/works.parquet")
RAW_OUT = Path("data/interim/works_raw.parquet")


def candidate_dois(
    profiles: Path = PROFILES, works: Path = WORKS, dois_file: Path | None = None
) -> list[str]:
    corpus = {
        audit.normalize_doi(row["doi"])
        for row in pq.read_table(works, columns=["doi"]).to_pylist()
        if row.get("doi")
    }
    if dois_file is not None:
        values = dois_file.read_text(encoding="utf-8").split()
    else:
        values = [
            value
            for row in pq.read_table(profiles, columns=["orcid_dois"]).to_pylist()
            for value in row.get("orcid_dois") or []
        ]
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        doi = audit.normalize_doi(value)
        if doi and doi not in corpus and doi not in seen and audit.is_queryable_doi(doi):
            seen.add(doi)
            out.append(doi)
    return sorted(out)


def passes_query(work: dict, config: dict) -> bool:
    text = " ".join(
        part
        for part in (
            str(work.get("title") or ""),
            _abstract_from_inverted_index(work.get("abstract_inverted_index")),
        )
        if part
    )
    return classify_plastic_text(text, config).related or always_relevant(text, config)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="count only; no OpenAlex calls")
    parser.add_argument("--max-credits", type=float, default=1500)
    parser.add_argument("--max-batches", type=int, default=0, help="0 = all")
    parser.add_argument("--out", type=Path, default=Path("scratch/orcid_doi_ingest.json"))
    parser.add_argument(
        "--dois-file",
        type=Path,
        default=None,
        help="one DOI per line (e.g. fetch_ror_researcher_dois.py output) instead of expert ORCIDs",
    )
    args = parser.parse_args()

    config = load_query_config()
    dois = candidate_dois(dois_file=args.dois_file)
    batches = audit.doi_batches(dois)
    if args.max_batches:
        batches = batches[: args.max_batches]
    result: dict = {"candidate_dois": len(dois), "batches": len(batches)}
    print(f"ORCID DOIs not in corpus: {len(dois)}; batches this run: {len(batches)}")
    if not args.dry_run:
        oa.load_openalex_key()
        prefix = "ror-researcher-doi-ingest" if args.dois_file else "orcid-doi-ingest"
        run_id = f"{prefix}-{datetime.now(UTC).date().isoformat()}"
        fetched = audit.fetch_openalex_by_doi(
            batches,
            config=config,
            run_id=run_id,
            max_credits=args.max_credits,
            with_query=False,
        )
        works = fetched["works"]
        plastic = [w for w in works if passes_query(w, config)]
        inst = set(oa.load_institution_ids())
        kept = [w for w in plastic if audit.keep_for_corpus(w, inst)]
        added, total_rows = audit.merge_works(kept, run_id=run_id, output=RAW_OUT)
        result.update(
            {
                "run_id": run_id,
                "openalex_found": len(works),
                "plastic_rule": len(plastic),
                "kept_ca": len(kept),
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
