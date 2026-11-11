"""Check CEDEN concentration enrichment (S7.8a) offline.

Always uses tests/fixtures/s7_8_ceden.json. When the ignored owner export and workbook
samples exist locally, also asserts 63 kept and 78 filled concentrations and reports QA counts.
"""

from __future__ import annotations

import json
from pathlib import Path

from atlas.ingest.monitoring.ceden import (
    CEDEN_CITATION_SUFFIX,
    aggregate_by_sample,
    enrich_samples,
    load_owner_export,
    summarize_enrichment,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "s7_8_ceden.json"
EXPORT = ROOT / "data" / "raw" / "ceden" / "export.tsv"
SAMPLES = ROOT / "data" / "processed" / "normalized" / "sf_bay_5gyres" / "samples.json"


def check_fixture() -> None:
    records = json.loads(FIXTURE.read_text(encoding="utf-8"))["records"]
    by_sample = aggregate_by_sample(records)
    assert len(by_sample) == 7, len(by_sample)
    workbook = [
        {
            "sample_id": "TEST-SW-KEEP-01",
            "concentration_value": 0.5,
            "concentration_unit": "particles/L",
            "citation": "base",
        },
        {
            "sample_id": "TEST-SW-FILL-02",
            "concentration_value": None,
            "concentration_unit": "particles/L",
            "citation": "base",
        },
        {
            "sample_id": "TEST-SW-BLANK-04",
            "concentration_value": None,
            "concentration_unit": "particles/L",
            "citation": "base",
        },
    ]
    enriched = enrich_samples(workbook, by_sample)
    assert enriched[0]["concentration_value"] == 0.5
    assert "concentration_source" not in enriched[0]
    assert abs(enriched[1]["concentration_value"] - 0.35) < 1e-12
    assert enriched[1]["citation"].endswith(CEDEN_CITATION_SUFFIX)
    assert enriched[2]["qa_sample"] is True
    print("fixture: ok (3 workbook rows, 7 CEDEN samples)")


def check_local() -> None:
    if not (EXPORT.exists() and SAMPLES.exists()):
        print("local export or workbook samples absent; skipping 63/78 assertions")
        return
    by_sample = aggregate_by_sample(load_owner_export(EXPORT))
    workbook = json.loads(SAMPLES.read_text(encoding="utf-8"))
    enriched = enrich_samples(workbook, by_sample, rel_tol=1e-5)
    counts = summarize_enrichment(workbook, enriched, by_sample)
    assert counts["matched"] == 141, counts
    assert counts["kept_workbook_concentration"] == 63, counts
    assert counts["filled_from_ceden"] == 78, counts
    assert counts["ceden_unmatched"] == 0, counts
    print(
        "local export: ok; kept 63, filled 78; "
        f"qa_samples={counts['qa_samples']} (ceden_qa={counts['ceden_qa_samples']}, "
        f"blank_named={counts['blank_named_workbook_samples']})"
    )


def main() -> None:
    check_fixture()
    check_local()
    print("check_s7_8: PASS")


if __name__ == "__main__":
    main()
