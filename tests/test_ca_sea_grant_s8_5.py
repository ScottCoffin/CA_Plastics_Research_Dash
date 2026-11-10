"""Tests for the S8.5 California Sea Grant scraper.  Offline: fixtures and a fake site only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
import yaml

from atlas.ingest.grants import ca_sea_grant as cs
from atlas.ingest.grants.normalize import normalize_grant
from atlas.ingest.grants.schema import grant_key

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "s8_5_ca_sea_grant"
EXPECTED = {"R/RCCE-12A", "R/RCCE-12B", "R/HCE-40A", "R/HCE-40B", "R/HCE-40C"}
LISTING_PREFIX = f"{cs.BASE_URL}{cs.LISTING_PATH}?"
# Requests for a full crawl of the fixtures: robots, one listing per keyword, five projects.
FULL_CRAWL_REQUESTS = 1 + len(cs.KEYWORDS) + len(EXPECTED)


class FakeSite:
    """Serves the fixture robots, listing, and project pages.  Records every call."""

    def __init__(
        self,
        robots: bytes,
        listing: bytes,
        pages: dict[str, bytes],
        *,
        status: int = 200,
        listings: dict[str, bytes] | None = None,
    ) -> None:
        self.robots = robots
        self.listing = listing
        self.pages = pages
        self.status = status
        self.listings = listings or {}
        self.calls: list[str] = []

    def __call__(self, url: str) -> tuple[int, bytes]:
        self.calls.append(url)
        if self.status != 200:
            return self.status, b""
        if url.endswith("/robots.txt"):
            return 200, self.robots
        if url in self.listings:
            return 200, self.listings[url]
        if url.startswith(LISTING_PREFIX):
            return 200, self.listing
        if url in self.pages:
            return 200, self.pages[url]
        return 404, b""


def _fixture_site(**kwargs: Any) -> FakeSite:
    robots = (FIX / "robots.txt").read_bytes()
    listing = (FIX / "listing_microplastic.html").read_bytes()
    rows = cs.parse_listing(cs._decode(listing)).rows
    pages: dict[str, bytes] = {}
    for path in sorted(FIX.glob("project_*.html")):
        project = cs.parse_project(cs._decode(path.read_bytes()), "fixture")
        for row in rows:
            if row.number == project.number:
                pages[row.url] = path.read_bytes()
    return FakeSite(robots, listing, pages, **kwargs)


def _configs() -> tuple[dict[str, Any], dict[str, Any]]:
    query = yaml.safe_load((ROOT / "config" / "queries.yml").read_text(encoding="utf-8"))
    taxonomy = yaml.safe_load((ROOT / "config" / "taxonomy.yml").read_text(encoding="utf-8"))
    return query, taxonomy


def _fixture_projects() -> list[cs.Project]:
    site = _fixture_site()
    return [cs.parse_project(cs._decode(body), url) for url, body in sorted(site.pages.items())]


def _run(tmp_path: Path, site: FakeSite, output: Path, cache: Path, **kwargs: Any) -> dict:
    query, taxonomy = _configs()
    sleeps: list[float] = kwargs.pop("sleeps", [])
    return cs.run_ingest(
        output=output,
        cache_dir=cache,
        query_config=query,
        taxonomy=taxonomy,
        transport=site,
        sleep=sleeps.append,
        clock=lambda: 0.0,
        **kwargs,
    )


def _inline_project(*, title: str, body: str, funder: str, extra: str = "") -> cs.Project:
    html = (
        '<html><body><h1 class="page-header">'
        + title
        + "</h1><article>"
        + '<div class="field field--name-field-project-number">'
        + '<div class="field--item">R/TEST-1</div></div>'
        + '<div class="field field--name-body"><p>'
        + body
        + "</p></div>"
        + '<div class="field field--name-field-funding-agency"><div class="field--items">'
        + f'<span class="field--item">{funder}</span></div></div>'
        + extra
        + "</article></body></html>"
    )
    return cs.parse_project(html, f"{cs.BASE_URL}/our-work/research-projects/test")


def test_listing_fixture_rows_and_paging_flag() -> None:
    site = _fixture_site()
    parsed = cs.parse_listing(cs._decode(site.listing))
    assert {row.number for row in parsed.rows} == EXPECTED
    assert parsed.has_next is False
    row = next(row for row in parsed.rows if row.number == "R/RCCE-12A")
    assert row.url == (
        f"{cs.BASE_URL}/our-work/research-projects/"
        "design-factors-affecting-microplastic-retention-removal-and-generation"
    )
    assert row.title.startswith("Design factors affecting microplastic")


@pytest.mark.parametrize(
    ("name", "number", "pi", "institution", "start", "end"),
    [
        (
            "project_r_rcce-12a.html",
            "R/RCCE-12A",
            "Sanjay Mohanty",
            "University of California, Los Angeles (UCLA)",
            "2023-10-02",
            "2025-09-30",
        ),
        (
            "project_r_rcce-12b.html",
            "R/RCCE-12B",
            "Elizabeth Fassman-Beck",
            "California State University, Long Beach (Long Beach State)",
            "2023-10-01",
            "2025-09-30",
        ),
        (
            "project_r_hce-40a.html",
            "R/HCE-40A",
            "Diana Lin",
            "San Francisco Estuary Institute",
            "2023-10-01",
            "2026-09-30",
        ),
        (
            "project_r_hce-40b.html",
            "R/HCE-40B",
            "William Ludt",
            "Natural History Museum of Los Angeles",
            "2023-10-01",
            "2026-09-30",
        ),
        (
            "project_r_hce-40c.html",
            "R/HCE-40C",
            "Matthew Savoca",
            "California Marine Sanctuary Foundation",
            "2023-10-01",
            "2026-09-30",
        ),
    ],
)
def test_project_fixture_fields(
    name: str, number: str, pi: str, institution: str, start: str, end: str
) -> None:
    project = cs.parse_project(cs._decode((FIX / name).read_bytes()), "fixture")
    assert project.number == number
    assert pi in project.pi_names
    assert all(
        "University" not in person and "Institute" not in person for person in project.pi_names
    )
    assert project.institution == institution
    assert (project.start, project.end) == (start, end)
    assert any("Ocean Protection Council" in funder for funder in project.funders)
    assert project.focus_areas
    assert cs.is_relevant(project)


def test_relevance_filter_rules() -> None:
    # Plastic term in the title is enough.
    assert cs.is_relevant(
        _inline_project(title="Microplastics in kelp", body="fish", funder="NOAA")
    )
    # Marine litter in the summary is enough.
    assert cs.is_relevant(_inline_project(title="Coasts", body="marine litter", funder="NOAA"))
    # "Plasticity" is not a plastic term.
    assert not cs.is_relevant(
        _inline_project(title="Plasticity in abalone", body="thermal plasticity", funder="NOAA")
    )
    # OPC funder with no plastic term anywhere on the page is not relevant.
    assert not cs.is_relevant(_inline_project(title="Eelgrass", body="fish", funder="OPC"))
    # OPC funder with a plastic term only in an attachment is relevant.
    extra = '<div class="field field--name-field-attachment">plastic summary.pdf</div>'
    assert cs.is_relevant(
        _inline_project(
            title="Eelgrass",
            body="fish",
            funder="California Ocean Protection Council (OPC)",
            extra=extra,
        )
    )


def test_mapping_to_grant_schema_rows() -> None:
    query, taxonomy = _configs()
    projects = _fixture_projects()
    rows, skipped = cs.normalize_projects(projects, query_config=query, taxonomy=taxonomy)
    assert skipped == 0
    assert {row["source_award_id"] for row in rows.values()} == EXPECTED
    for row in rows.values():
        assert row["source"] == "ca_sea_grant"
        assert row["grant_key"] == grant_key("ca_sea_grant", row["source_award_id"])
        assert row["org_state"] == "CA"
        assert row["ca_led"] is True
        assert row["amount"] is None
        assert row["funder_chain"][-1] == "California Sea Grant"
        assert row["funder_chain"][0].startswith("California Ocean Protection Council")
    by_id = {row["source_award_id"]: row for row in rows.values()}
    assert by_id["R/RCCE-12A"]["pi_names"] == ["Sanjay Mohanty"]
    assert by_id["R/RCCE-12A"]["url"].endswith(
        "design-factors-affecting-microplastic-retention-removal-and-generation"
    )


def test_mapping_marks_non_california_institution_unknown() -> None:
    query, taxonomy = _configs()
    project = _inline_project(title="Microplastics", body="x", funder="NOAA")
    row = normalize_grant(
        {**cs.to_raw_grant(project), "org": "University of Hawaii", "org_state": None},
        source="ca_sea_grant",
        query_config=query,
        taxonomy=taxonomy,
    )
    assert row["org_state"] is None and row["ca_led"] is None


def test_cache_reuse_and_pacing(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    sleeps: list[float] = []
    first = _fixture_site()
    summary = _run(tmp_path, first, tmp_path / "out.parquet", cache, sleeps=sleeps)
    assert summary["status"] == "ok"
    assert summary["requests"] == FULL_CRAWL_REQUESTS == len(first.calls)
    assert summary["rows_written"] == 5
    # The first request is not paced; every later one waits the full interval.
    assert len(sleeps) == FULL_CRAWL_REQUESTS - 1
    assert all(abs(seconds - cs.MIN_INTERVAL_SECONDS) < 1e-9 for seconds in sleeps)

    second = _fixture_site()
    rerun = _run(tmp_path, second, tmp_path / "out2.parquet", cache)
    assert rerun["status"] == "ok"
    assert rerun["requests"] == 0
    assert rerun["cache_hits"] == FULL_CRAWL_REQUESTS
    assert second.calls == []
    assert rerun["rows_written"] == 5


def test_request_cap_is_partial_and_keeps_prior_rows(tmp_path: Path) -> None:
    output = tmp_path / "out.parquet"
    _run(tmp_path, _fixture_site(), output, tmp_path / "full_cache")
    site = _fixture_site()
    summary = _run(tmp_path, site, output, tmp_path / "cold_cache", max_requests=3)
    assert summary["status"] == "partial"
    assert "max_requests=3" in summary["reason"]
    assert summary["requests"] == 3 == len(site.calls)
    # Nothing new was reached, so the prior five rows survive the partial run.
    assert summary["rows_written"] == 5
    assert pq.read_table(output).num_rows == 5


def test_fetch_failure_defers_and_preserves_output(tmp_path: Path) -> None:
    output = tmp_path / "out.parquet"
    _run(tmp_path, _fixture_site(), output, tmp_path / "full_cache")
    before = output.read_bytes()
    failing = _run(tmp_path, _fixture_site(status=503), output, tmp_path / "cold_503")
    assert failing["status"] == "deferred"
    assert output.read_bytes() == before

    def broken(url: str) -> tuple[int, bytes]:
        raise OSError("network down")

    network = cs.run_ingest(
        output=output,
        cache_dir=tmp_path / "cold_net",
        query_config=_configs()[0],
        taxonomy=_configs()[1],
        transport=broken,
        sleep=lambda seconds: None,
        clock=lambda: 0.0,
    )
    assert network["status"] == "deferred"
    assert output.read_bytes() == before


def test_robots_disallow_skips_project_pages(tmp_path: Path) -> None:
    site = _fixture_site()
    site.robots = b"User-agent: *\nDisallow: /our-work/research-projects/\n"
    summary = _run(tmp_path, site, tmp_path / "out.parquet", tmp_path / "cache")
    assert summary["status"] == "ok"
    assert summary["robots_skipped"] == 5
    assert summary["rows_written"] == 0


def test_listing_paging_follows_next_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cs, "KEYWORDS", ("microplastic",))
    site = _fixture_site()
    listing_text = cs._decode(site.listing)
    pager = '<ul><li class="pager__item pager__item--next"><a href="?page=1">Next</a></li></ul>'
    page0 = listing_text.replace("</body>", pager + "</body>").encode("utf-8")
    site.listings = {
        cs.listing_url("microplastic", 0): page0,
        cs.listing_url("microplastic", 1): site.listing,
    }
    fetcher = cs.PoliteFetcher(
        tmp_path / "cache", max_requests=50, transport=site, sleep=lambda s: None, clock=lambda: 0.0
    )
    robots = cs.load_robots(fetcher)
    stats = {"listing_pages": 0, "projects_fetched": 0, "robots_skipped": 0, "skipped_invalid": 0}
    projects = cs.crawl(fetcher, robots, stats)
    assert stats["listing_pages"] == 2
    assert {project.number for project in projects} == EXPECTED
    assert cs.listing_url("microplastic", 1) in site.calls
