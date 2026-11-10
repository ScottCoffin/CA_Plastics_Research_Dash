"""Offline acceptance check for the S8.5 California Sea Grant scraper.

Runs the crawl over the saved fixtures with an in-process fake site, then asserts that
the five OPC-funded microplastics projects (named in the OPC announcement of
2025-11-07, https://opc.ca.gov/2025/11/microplastics-research-public-webinar-and-panel-november-25-2025/)
are captured.  Makes no network calls.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pyarrow.parquet as pq
import yaml

from atlas.ingest.grants import GRANT_SCHEMA, validate_grants
from atlas.ingest.grants import ca_sea_grant as cs

FIXTURES = Path("tests/fixtures/s8_5_ca_sea_grant")
QUERIES = Path("config/queries.yml")
TAXONOMY = Path("config/taxonomy.yml")
# Project number -> PI named in the OPC announcement (speaker list).
OPC_MICROPLASTICS_PROJECTS: dict[str, str] = {
    "R/RCCE-12A": "Sanjay Mohanty",
    "R/RCCE-12B": "Elizabeth Fassman-Beck",
    "R/HCE-40A": "Diana Lin",
    "R/HCE-40B": "William Ludt",
    "R/HCE-40C": "Matthew Savoca",
}


def _transport(site: dict[str, bytes], listing: bytes):
    def transport(url: str) -> tuple[int, bytes]:
        if url.endswith("/robots.txt"):
            return 200, site["robots"]
        if url.startswith(f"{cs.BASE_URL}{cs.LISTING_PATH}?"):
            return 200, listing
        if url in site:
            return 200, site[url]
        return 404, b""

    return transport


def main() -> None:
    robots = (FIXTURES / "robots.txt").read_bytes()
    listing = (FIXTURES / "listing_microplastic.html").read_bytes()
    rows = cs.parse_listing(cs._decode(listing)).rows
    site: dict[str, bytes] = {"robots": robots}
    for path in sorted(FIXTURES.glob("project_*.html")):
        project = cs.parse_project(cs._decode(path.read_bytes()), "fixture")
        for row in rows:
            if row.number == project.number:
                site[row.url] = path.read_bytes()
    assert len(site) == len(OPC_MICROPLASTICS_PROJECTS) + 1, "fixture pages do not match rows"

    query = yaml.safe_load(QUERIES.read_text(encoding="utf-8"))
    taxonomy = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="s8-5-acceptance-") as directory:
        base = Path(directory)
        output = base / "ca_sea_grant.parquet"
        summary = cs.run_ingest(
            output=output,
            cache_dir=base / "cache",
            query_config=query,
            taxonomy=taxonomy,
            transport=_transport(site, listing),
            sleep=lambda seconds: None,
            clock=lambda: 0.0,
        )
        assert summary["status"] == "ok", summary
        assert summary["requests"] == 1 + len(cs.KEYWORDS) + len(OPC_MICROPLASTICS_PROJECTS)
        table = pq.read_table(output)
        assert table.schema.equals(GRANT_SCHEMA)
        captured = {row["source_award_id"]: row for row in table.to_pylist()}
        validate_grants(captured.values())
        for number, pi in OPC_MICROPLASTICS_PROJECTS.items():
            assert number in captured, f"missing OPC microplastics project {number}"
            assert pi in captured[number]["pi_names"], (number, pi)
            assert captured[number]["funder_chain"][-1] == "California Sea Grant"
            assert captured[number]["funder_chain"][0].startswith("California Ocean Protection")

    print("S8.5 check passed: all five OPC microplastics projects captured.")


if __name__ == "__main__":
    main()
