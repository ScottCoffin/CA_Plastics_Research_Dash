"""Offline acceptance check for S8.6 (state funders and pass-through dedupe).

No network calls. Checks the adapters against the saved fixture, the curation CSV, the
dedupe rule on synthetic rows, and the presence of the committed documentation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from atlas.ingest.grants import normalize_grant, validate_grants
from atlas.ingest.grants.dedupe import cluster_rows
from atlas.ingest.grants.state_funders import (
    CURATION_PATH,
    html_text,
    load_curation,
    opc_approvals,
    parse_opc_council_summary,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/s8_6/opc_council_summary_excerpt.html"
DOCS = (ROOT / "docs/api_notes/state_funders.md", ROOT / "docs/grants_overlap_report.md")


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def main() -> int:
    queries = yaml.safe_load((ROOT / "config/queries.yml").read_text(encoding="utf-8"))
    taxonomy = yaml.safe_load((ROOT / "config/taxonomy.yml").read_text(encoding="utf-8"))

    approvals, unparsed = opc_approvals(html_text(FIXTURE.read_text(encoding="utf-8")))
    if len(approvals) != 3 or unparsed:
        _fail(f"OPC fixture parse gave {len(approvals)} approvals, {unparsed} unparsed")
    rows, counts = parse_opc_council_summary(
        FIXTURE.read_text(encoding="utf-8"),
        "https://opc.ca.gov/2026/06/june-16-2026-council-meeting-summary/",
        queries,
    )
    if counts["plastic"] != 1 or rows[0]["amount"] != 2500000.0:
        _fail("OPC plastic filter or amount extraction changed")

    curated = load_curation(ROOT / CURATION_PATH, queries, taxonomy)
    if not curated:
        _fail("curation CSV has no rows")
    validate_grants(curated)

    synthetic = [
        normalize_grant(
            {
                "source_award_id": "S8-6-A",
                "title": "Synthetic Microplastics Pilot",
                "amount": 1000,
                "start": "2026-01-01",
                "funder_chain": ["Synthetic OPC"],
            },
            source="opc_council",
            query_config=queries,
            taxonomy=taxonomy,
        ),
        normalize_grant(
            {
                "source_award_id": "S8-6-B",
                "title": "Synthetic Microplastics Pilot",
                "amount": 1000,
                "start": "2026-01-01",
                "pi_names": ["Doe, Jane"],
                "funder_chain": ["Synthetic OPC", "Synthetic Sea Grant"],
            },
            source="ca_sea_grant",
            query_config=queries,
            taxonomy=taxonomy,
        ),
    ]
    result = cluster_rows(synthetic)
    if len({entry["cluster_id"] for entry in result.assignments}) != 1:
        _fail("pass-through pair did not cluster")

    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "data/raw/state_funders/probe.raw"],
        cwd=ROOT,
        check=False,
    )
    if ignored.returncode != 0:
        _fail("data/raw/state_funders is not git-ignored")

    missing = [str(path) for path in DOCS if not path.exists()]
    if missing:
        _fail(f"missing documentation: {missing}")

    print("S8.6 offline checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
