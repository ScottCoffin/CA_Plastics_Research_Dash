"""ESCH-CA: add plastics works hosted on eScholarship that carry UC evidence.

Inputs: the latest ``audit_escholarship_openalex.py`` snapshots (OpenAlex works with an
eScholarship location that already match the active plastics query and type filters) and
``data/processed/escholarship_items.parquet`` (``fetch_escholarship_items.py``). A
work is merged into ``data/interim/works_raw.parquet`` when it is not yet in the raw
corpus and its eScholarship record is a UC thesis, a UC open-access-policy deposit or a
campus-unit item (UC-hosted journals and unfetched items are skipped). Normalization
then gives it the ``escholarship`` California basis. No network calls.

    PYTHONPATH=src py -3.14 scripts/ingest_escholarship_works.py [--dry-run]
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import pyarrow.parquet as pq

from atlas.ingest import europepmc_audit as audit
from atlas.ingest import openalex as oa
from atlas.ingest.normalize import ESCHOLARSHIP_PATH, load_escholarship_evidence

RAW = Path("data/interim/works_raw.parquet")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    evidence = load_escholarship_evidence(ESCHOLARSHIP_PATH)
    raw_ids = {
        oa.compact_openalex_id(r["openalex_id"])
        for r in pq.read_table(RAW, columns=["openalex_id"]).to_pylist()
    }
    candidates: dict[str, dict] = {}
    for path in glob.glob("data/raw/openalex_works/escholarship-openalex-audit-*.json"):
        body = json.loads(Path(path).read_text(encoding="utf-8")).get("response") or {}
        for work in body.get("results") or []:
            candidates[oa.compact_openalex_id(work.get("id"))] = work
    missing = {k: w for k, w in candidates.items() if k not in raw_ids}
    kept = [w for k, w in missing.items() if k in evidence]
    print(
        f"audit works: {len(candidates)}; missing from raw: {len(missing)}; "
        f"with UC evidence: {len(kept)}"
    )
    if not args.dry_run and kept:
        added, total = audit.merge_works(kept, run_id="escholarship-ingest", output=RAW)
        print(f"merged {added} new works; raw rows {total}")
    for work in kept:
        print(" ", oa.compact_openalex_id(work.get("id")), str(work.get("title"))[:80])


if __name__ == "__main__":
    main()
