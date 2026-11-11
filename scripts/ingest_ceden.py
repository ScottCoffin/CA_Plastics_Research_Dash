"""Match CEDEN microplastics concentrations onto the SF Bay / 5 Gyres workbook samples (S7.8a).

Default: live fetch from the data.ca.gov CKAN datastore (raw pages saved under data/raw/ceden/api/).
``--from-export PATH`` reads the owner's TSV export instead (offline).
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from atlas.ingest.monitoring.ceden import (
    aggregate_by_sample,
    consistency_report,
    enrich_samples,
    fetch_ceden_microplastics,
    load_owner_export,
    summarize_enrichment,
)

DEFAULT_SAMPLES = Path("data/processed/normalized/sf_bay_5gyres/samples.json")
DEFAULT_RAW_DIR = Path("data/raw/ceden/api")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-export", type=Path, help="owner TSV export (offline)")
    parser.add_argument("--samples", type=Path, default=DEFAULT_SAMPLES)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_SAMPLES.parent)
    parser.add_argument(
        "--rel-tol",
        type=float,
        default=1e-5,
        help="relative tolerance for keeping workbook concentrations; CEDEN Result strings "
        "carry 6-8 significant digits, so exact 1e-9 agreement is not achievable",
    )
    args = parser.parse_args()

    pages: dict[str, dict[str, Any]] = {}
    if args.from_export:
        records = load_owner_export(args.from_export)
        source = f"owner export {args.from_export.name}"
    else:
        args.raw_dir.mkdir(parents=True, exist_ok=True)

        def sink(year: str, offset: int, payload: dict[str, Any]) -> None:
            path = args.raw_dir / f"{year}_offset{offset}.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            pages.setdefault(year, {"total": payload["result"]["total"], "pages": 0})
            pages[year]["pages"] += 1

        records = fetch_ceden_microplastics(page_sink=sink)
        source = "live CKAN datastore_search"

    # The live datastore omits the ISQA QA flag that the owner export carries; QA then
    # falls back to blank sample types and blank names only, so counts will differ.
    isqa_available = any("isqa" in {str(key).lower() for key in record} for record in records)
    if not isqa_available:
        print("warning: records have no ISQA field; QA flags are sample-type and name based only")
    by_sample = aggregate_by_sample(records)
    workbook = json.loads(args.samples.read_text(encoding="utf-8"))
    enriched = enrich_samples(workbook, by_sample, rel_tol=args.rel_tol)
    counts = summarize_enrichment(workbook, enriched, by_sample)
    consistency = consistency_report(workbook, by_sample)
    qc = {
        "source": source,
        "record_count": len(records),
        "unit_counts": dict(Counter(s["concentration_unit"] for s in by_sample.values())),
        "resource_totals": pages,
        "rel_tol": args.rel_tol,
        "isqa_available": isqa_available,
        "summary": counts,
        "consistency": consistency,
        "license": "CC BY 4.0 (owner decision 2026-11-10)",
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_samples = args.output_dir / "samples_enriched.json"
    out_qc = args.output_dir / "ceden_qc.json"
    out_samples.write_text(
        json.dumps(enriched, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    out_qc.write_text(json.dumps(qc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"source: {source}")
    print(f"records: {len(records)}  ceden samples: {len(by_sample)}")
    print(f"summary: {json.dumps(counts, sort_keys=True)}")
    print(f"consistency: {json.dumps(consistency, sort_keys=True)}")
    print(f"wrote {out_samples} and {out_qc}")


if __name__ == "__main__":
    main()
