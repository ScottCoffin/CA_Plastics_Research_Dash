"""Offline tests for the S8.8 SWRCB FAAST awarded-proposal adapter (no network)."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
import yaml

from atlas.ingest.grants import GRANT_COLUMNS, validate_grants
from atlas.ingest.grants.faast import (
    KEYWORDS,
    SOURCE,
    FaastDeferred,
    FaastSession,
    FixtureFaast,
    LiveFaast,
    assemble,
    build_raw,
    form_action,
    hidden_fields,
    money,
    pager_targets,
    parse_detail,
    parse_grid,
    run_faast,
)

FIXTURES = Path("tests/fixtures/s8_8_faast")
QUERIES = Path("config/queries.yml")
TAXONOMY = Path("config/taxonomy.yml")
GRID_URL = "https://faast.waterboards.ca.gov/Public_Interface/PublicSearch.aspx"
CONTACT_TOKENS = ("Jane Synthetic", "jane.synthetic", "example.invalid", "555-010-0199", "Contacts")


@pytest.fixture(scope="module")
def configs() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        yaml.safe_load(QUERIES.read_text(encoding="utf-8")),
        yaml.safe_load(TAXONOMY.read_text(encoding="utf-8")),
    )


def _fixture_dir(tmp_path: Path, *, overlap: bool = False) -> Path:
    directory = tmp_path / "fixtures"
    directory.mkdir()
    shutil.copy(FIXTURES / "grid_trash.html", directory / "grid_trash.html")
    shutil.copy(FIXTURES / "detail_24090.html", directory / "detail_24090.html")
    if overlap:
        # A second keyword returning the same awarded PINs must not duplicate them.
        shutil.copy(FIXTURES / "grid_trash.html", directory / "grid_plastic.html")
    return directory


def test_keyword_list_is_the_s8_8_set() -> None:
    assert KEYWORDS == (
        "microplastic",
        "plastic",
        "trash",
        "litter",
        "debris",
        "tire wear",
        "6PPD",
        "polystyrene",
    )


def test_grid_parses_rows_and_detail_urls() -> None:
    page = (FIXTURES / "grid_trash.html").read_text(encoding="utf-8")
    rows = parse_grid(page, GRID_URL)
    assert [row.pin for row in rows] == ["24090", "24184", "99001"]
    first = rows[0]
    assert first.title == "Tracking California's Trash - PHASE1"
    assert first.applicant == "Bay Area Stormwater Management Agencies Association"
    assert first.req_funds == "$870,000"
    assert first.status == "AWARDED"
    assert first.detail_url == (
        "https://faast.waterboards.ca.gov/Public_Interface/PublicProposalDetails.aspx"
        "?Pin=24090&PropId=24090"
    )


def test_money_parses_requested_funds_and_refuses_guesses() -> None:
    assert money("     $870,000") == 870000.0
    assert money("$1,968,850") == 1968850.0
    assert money("") is None
    assert money("TBD") is None
    assert money("nan") is None
    assert money(None) is None


def test_detail_reads_only_four_labelled_fields() -> None:
    fields = parse_detail((FIXTURES / "detail_24090.html").read_text(encoding="utf-8"))
    assert set(fields) == {"rfp_title", "submitting_org", "project_title", "project_description"}
    assert fields["rfp_title"] == "Synthetic Trash Monitoring Grants"
    assert fields["project_title"] == "Tracking California's Trash"
    assert fields["project_description"] is not None
    assert fields["project_description"].startswith("Synthetic description")


def test_build_raw_maps_s8_1_fields() -> None:
    page = (FIXTURES / "grid_trash.html").read_text(encoding="utf-8")
    row = parse_grid(page, GRID_URL)[0]
    detail = parse_detail((FIXTURES / "detail_24090.html").read_text(encoding="utf-8"))
    raw = build_raw(row, detail)
    assert raw["source_award_id"] == "24090"
    assert raw["amount"] == 870000.0
    assert raw["org"] == row.applicant
    assert raw["org_state"] == "CA"
    assert raw["funder"] == "State Water Resources Control Board"
    assert raw["funder_chain"] == [
        "State Water Resources Control Board",
        "Division of Financial Assistance",
    ]
    assert raw["program"] == "FAAST: Synthetic Trash Monitoring Grants (amount = requested funds)"
    assert raw["start"] is None and raw["end"] is None
    assert raw["abstract"] is not None and raw["abstract"].startswith("Agreement No. 12-420-550.")


def test_pager_targets_and_hidden_fields_are_parsed() -> None:
    page = (
        '<input type="hidden" name="__VIEWSTATE" value="A&amp;B" />'
        '<a href="javascript:__doPostBack(&#39;ctl00$ContentPlaceHolder1$'
        "PublicProposalSearchGV&#39;,"
        '&#39;Page$2&#39;)">2</a>'
        "<a href=\"javascript:__doPostBack('ctl00$Other','Page$9')\">9</a>"
    )
    assert pager_targets(page) == {2: "ctl00$ContentPlaceHolder1$PublicProposalSearchGV"}
    assert hidden_fields(page) == {"__VIEWSTATE": "A&B"}
    action = form_action(GRID_URL, '<form method="post" action="./PublicSearch.aspx?x=1&amp;y=2">')
    assert action == "https://faast.waterboards.ca.gov/Public_Interface/PublicSearch.aspx?x=1&y=2"


def test_union_by_pin_across_keywords(tmp_path: Path) -> None:
    provider = FixtureFaast(_fixture_dir(tmp_path, overlap=True))
    raw_rows, counts = assemble(provider, ("trash", "plastic"))
    assert counts["keyword_hits"] == {"trash": 2, "plastic": 2}
    assert counts["unique_awarded"] == 2
    assert counts["non_awarded_skipped"] == 2
    assert [raw["source_award_id"] for raw in raw_rows] == ["24090", "24184"]
    assert provider.missing == 1  # detail_24184 is not in the fixture directory


def test_run_writes_parquet_and_keeps_contacts_out(
    tmp_path: Path, configs: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    query_config, taxonomy = configs
    output = tmp_path / "swrcb_faast.parquet"
    status = tmp_path / "status.json"
    summary = run_faast(
        FixtureFaast(_fixture_dir(tmp_path)),
        query_config=query_config,
        taxonomy=taxonomy,
        output=output,
        status_path=status,
        keywords=("trash",),
    )
    assert summary["status"] == "ok"
    assert summary["output_rows"] == 2
    table = pq.read_table(output)
    assert table.column_names == list(GRANT_COLUMNS)
    rows = table.to_pylist()
    validate_grants(rows)
    assert {row["source"] for row in rows} == {SOURCE}
    trash = next(row for row in rows if row["source_award_id"] == "24090")
    assert trash["amount"] == 870000.0
    assert trash["org_state"] == "CA"
    blob = json.dumps(rows, default=str) + status.read_text(encoding="utf-8")
    for token in CONTACT_TOKENS:
        assert token not in blob
    assert not re.search(r"@|\d{3}-\d{3}-\d{4}", blob)


def test_deferred_run_leaves_existing_output_untouched(
    tmp_path: Path, configs: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    class Broken:
        requests = 3

        def search(self, keyword: str) -> list[Any]:
            raise FaastDeferred("HTTP 503 from FAAST")

        def detail(self, row: object) -> dict[str, Any]:
            raise AssertionError("no detail fetch after a deferral")

    query_config, taxonomy = configs
    output = tmp_path / "swrcb_faast.parquet"
    output.write_bytes(b"previous output")
    status = tmp_path / "status.json"
    summary = run_faast(
        Broken(),
        query_config=query_config,
        taxonomy=taxonomy,
        output=output,
        status_path=status,
    )
    assert summary["status"] == "deferred"
    assert summary["requests"] == 3
    assert output.read_bytes() == b"previous output"


class _Scripted(FaastSession):
    """Session whose network layer replays canned pages, chosen by URL and POST fields."""

    def __init__(self, pages: dict[str, str]) -> None:
        super().__init__(sleep=lambda _seconds: None, clock=lambda: 0.0)
        self.pages = pages
        self.posts: list[dict[str, str]] = []

    def _send(self, url: str, data: Any, referer: str | None) -> tuple[str, str]:  # type: ignore[override]
        self.requests += 1
        if url.endswith("robots.txt"):
            return url, ""
        if "PublicProposalDetails" in url:
            return url, self.pages["detail"]
        if data is None:
            return url, self.pages["home"]
        self.posts.append(dict(data))
        if "PublicTool" in data:
            return url, self.pages["main"]
        if "GotoSearch" in data:
            return url, self.pages["search"]
        if "__EVENTTARGET" in data:
            return url, self.pages["page2"]
        return url, self.pages["results"]


def test_live_flow_follows_pager_and_caches_only_grid(tmp_path: Path) -> None:
    grid = (FIXTURES / "grid_trash.html").read_text(encoding="utf-8")
    pager = (
        "<tr><td><a href=\"javascript:__doPostBack('ctl00$ContentPlaceHolder1$"
        "PublicProposalSearchGV',"
        "'Page$2')\">2</a></td></tr>"
    )
    page1 = grid.replace("</table>", pager + "</table>")
    page2 = grid.replace("24090", "30001").replace("24184", "30002").replace("99001", "30003")
    search_page = (
        '<form method="post" action="./PublicSearch.aspx">'
        '<input type="hidden" name="__VIEWSTATE" value="V" />'
        '<input name="ctl00$ContentPlaceHolder1$PublicSearchBtn" type="submit" value="x" />'
        "</form>"
    )
    session = _Scripted(
        {
            "home": '<form method="post" action="./"></form>',
            "main": '<form method="post" action="./PublicPropSearchMain.aspx"></form>',
            "search": search_page,
            "results": page1,
            "page2": page2,
            "detail": (FIXTURES / "detail_24090.html").read_text(encoding="utf-8"),
        }
    )
    raw_dir = tmp_path / "raw"
    live = LiveFaast(session, raw_dir=raw_dir)
    rows = live.search("trash")
    assert [row.pin for row in rows] == ["24090", "24184", "99001", "30001", "30002", "30003"]
    assert any(
        post.get("__EVENTTARGET", "").endswith("PublicProposalSearchGV") for post in session.posts
    )
    searches = [
        post
        for post in session.posts
        if "ctl00$ContentPlaceHolder1$AccrodianPane2_content$DescriptionText" in post
    ]
    assert searches and all(
        post["ctl00$ContentPlaceHolder1$AccordianPaneMain_content$StatusDDL"] == "AWARDED"
        for post in searches
    )
    assert sorted(path.name for path in raw_dir.iterdir()) == [
        "grid_trash_p1.html",
        "grid_trash_p2.html",
    ]
    detail = live.detail(rows[0])
    assert detail["rfp_title"] == "Synthetic Trash Monitoring Grants"
