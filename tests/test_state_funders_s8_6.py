"""Unit tests for the S8.6 state funder adapters, curation merge, and pass-through dedupe."""

from __future__ import annotations

import urllib.error
from datetime import date
from pathlib import Path

import openpyxl
import pytest
import yaml

from atlas.ingest.grants import (
    GRANT_COLUMNS,
    normalize_grant,
    validate_grants,
)
from atlas.ingest.grants.dedupe import ClusterResult, cluster_rows, compare_rows, render_report
from atlas.ingest.grants.state_funders import (
    OPC_FUNDER,
    BudgetExhausted,
    Fetcher,
    RobotsDisallowed,
    StateFunderHTTPError,
    html_text,
    load_curation,
    merge_curated,
    opc_approvals,
    parse_delta_export,
    parse_opc_council_summary,
    run_state_funders,
)

FIXTURE = Path("tests/fixtures/s8_6/opc_council_summary_excerpt.html")
QUERIES = Path("config/queries.yml")
TAXONOMY = Path("config/taxonomy.yml")
CURATION = Path("curation/grants_manual.csv")
OPC_URL = "https://opc.ca.gov/2026/06/june-16-2026-council-meeting-summary/"


@pytest.fixture(scope="module")
def query_config() -> dict:
    return yaml.safe_load(QUERIES.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def taxonomy() -> dict:
    return yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))


def _row(source: str, award_id: str, title: str, **extra: object) -> dict:
    raw: dict = {"source_award_id": award_id, "title": title}
    raw.update(extra)
    return raw


def _normalized(query_config: dict, taxonomy: dict, source: str, raw: dict) -> dict:
    return normalize_grant(raw, source=source, query_config=query_config, taxonomy=taxonomy)


def test_opc_fixture_yields_plastic_approval_only(query_config: dict) -> None:
    page = FIXTURE.read_text(encoding="utf-8")
    approvals, unparsed = opc_approvals(html_text(page))
    titles = [title for title, _amount, _body in approvals]
    assert titles == [
        "California Sea Grant",
        "Pilot Statewide Plastics Monitoring Program",
        "Coastal Access Grants",
    ]
    assert unparsed == 0
    rows, counts = parse_opc_council_summary(page, OPC_URL, query_config)
    assert counts == {"approvals": 3, "plastic": 1, "unparsed": 0}
    (row,) = rows
    assert row["title"] == "Pilot Statewide Plastics Monitoring Program"
    assert row["amount"] == 2500000.0
    assert row["start"] == "2026-06-16"
    assert row["source_award_id"] == "2026-06-16-pilot-statewide-plastics-monitoring-program"
    assert row["funder_chain"] == [OPC_FUNDER]
    assert row["url"] == OPC_URL


def test_opc_summary_without_meeting_date_is_skipped(query_config: dict) -> None:
    rows, counts = parse_opc_council_summary("<p>No date here</p>", OPC_URL, query_config)
    assert rows == []
    assert counts["no_meeting_date"] == 1


def test_delta_export_joins_plastic_activities_to_awards(
    tmp_path: Path, query_config: dict
) -> None:
    path = tmp_path / "synthetic_export.xlsx"
    book = openpyxl.Workbook()
    activities = book.active
    activities.title = "Science Activities"
    activities.append(
        [
            "Science Activity ID",
            "Title",
            "Description",
            "Science topics",
            "Notes",
            "Lead implementing organization",
            "Permalink",
        ]
    )
    activities.append(
        [
            101,
            "Synthetic microplastics occurrence survey",
            "Sampling for microplastics.",
            "Microplastics",
            None,
            "Synthetic Agency",
            "https://example.invalid/activity/101",
        ]
    )
    activities.append(
        [
            102,
            "Synthetic levee repair",
            "Levee work.",
            "Levees",
            None,
            "Other Agency",
            "https://example.invalid/activity/102",
        ]
    )
    awards = book.create_sheet("Funding Awards")
    awards.append(
        [
            "AwardID",
            "Science Activity ID",
            "Funding organization",
            "Funding program",
            "Total award amount ($)",
            "Date awarded",
        ]
    )
    awards.append([9001, 101, "Synthetic Funder", "Synthetic Program", 150000, "2024-03-01"])
    awards.append([9002, 102, "Synthetic Funder", "Synthetic Program", 5000, "2024-03-01"])
    book.save(path)
    rows, counts = parse_delta_export(path.read_bytes(), query_config)
    assert counts["activities"] == 2
    assert counts["plastic_activities"] == 1
    assert counts["award_rows"] == 1
    (row,) = rows
    assert row["source_award_id"] == "9001"
    assert row["funder_chain"] == ["Synthetic Funder"]
    assert row["amount"] == 150000


def test_curation_rows_win_and_need_evidence(
    tmp_path: Path, query_config: dict, taxonomy: dict
) -> None:
    rows = load_curation(CURATION, query_config, taxonomy)
    assert len(rows) >= 1
    assert all(row["grant_key"] for row in rows)
    validate_grants(rows)
    scraped = [
        _normalized(
            query_config,
            taxonomy,
            "opc_council",
            _row(
                "opc_council",
                "2026-06-16-pilot-statewide-plastics-monitoring-program",
                "Scraped title",
                amount=1.0,
            ),
        )
    ]
    merged, counts = merge_curated(scraped, rows)
    assert counts["curation_overrides"] == len(rows) and len(merged) == 1
    assert merged[0]["title"] == rows[0]["title"]

    bad = tmp_path / "bad.csv"
    header = ",".join((*GRANT_COLUMNS, "curation_note", "evidence_url"))
    empty = ",".join("" for _ in (*GRANT_COLUMNS, "curation_note", "evidence_url"))
    bad.write_text(f"{header}\n{empty}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="evidence_url is required"):
        load_curation(bad, query_config, taxonomy)


def test_fetcher_enforces_robots_and_budget(tmp_path: Path) -> None:
    calls: list[str] = []

    def opener(url: str) -> bytes:
        calls.append(url)
        if url.endswith("/robots.txt"):
            return b"User-agent: *\nDisallow: /private/\n"
        return b"<p>ok</p>"

    fetcher = Fetcher(
        raw_dir=tmp_path, max_requests=2, opener=opener, sleep=lambda _s: None, clock=lambda: 1000.0
    )
    with pytest.raises(RobotsDisallowed):
        fetcher.get("https://example.invalid/private/page")
    assert fetcher.get("https://example.invalid/public/page") == b"<p>ok</p>"
    with pytest.raises(BudgetExhausted):
        fetcher.get("https://example.invalid/public/other")
    assert fetcher.requests == 2
    # Cached pages cost no request.
    assert fetcher.get("https://example.invalid/public/page") == b"<p>ok</p>"


def test_fetcher_spaces_requests_and_reports_http_errors(tmp_path: Path) -> None:
    waits: list[float] = []

    def opener(url: str) -> bytes:
        if url.endswith("/missing"):
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)
        return b"ok"

    fetcher = Fetcher(
        raw_dir=tmp_path, max_requests=10, opener=opener, sleep=waits.append, clock=lambda: 10.0
    )
    fetcher.get("https://example.invalid/a")  # robots fetch, then the page
    assert fetcher.requests == 2
    assert waits and all(wait == pytest.approx(2.0) for wait in waits)
    with pytest.raises(StateFunderHTTPError):
        fetcher.get("https://example.invalid/missing")


def test_run_defers_without_touching_output(
    tmp_path: Path, query_config: dict, taxonomy: dict
) -> None:
    output = tmp_path / "state_funders.parquet"
    output.write_bytes(b"previous")

    def opener(url: str) -> bytes:
        raise urllib.error.HTTPError(url, 503, "Unavailable", None, None)

    fetcher = Fetcher(
        raw_dir=tmp_path / "raw",
        max_requests=5,
        opener=opener,
        sleep=lambda _s: None,
        clock=lambda: 0.0,
    )
    summary = run_state_funders(
        fetcher=fetcher,
        query_config=query_config,
        taxonomy=taxonomy,
        output=output,
        status_path=tmp_path / "status.json",
        curation_path=CURATION,
        months=("2026/06",),
    )
    assert summary["status"] == "deferred"
    assert output.read_bytes() == b"previous"


def _synthetic(source: str, award_id: str, title: str, **extra: object) -> dict:
    raw = _row(source, award_id, title, **extra)
    return raw


def test_dedupe_links_pass_through_record_to_representative(
    query_config: dict, taxonomy: dict
) -> None:
    opc = _normalized(
        query_config,
        taxonomy,
        "opc_council",
        _synthetic(
            "opc_council",
            "OPC-A",
            "Synthetic Microplastics Monitoring Pilot",
            amount=500000,
            start="2026-06-16",
            funder_chain=["Synthetic OPC"],
        ),
    )
    sea_grant = _normalized(
        query_config,
        taxonomy,
        "ca_sea_grant",
        _synthetic(
            "ca_sea_grant",
            "SG-A",
            "Synthetic Microplastics Monitoring Pilot",
            pi_names=["Doe, Jane"],
            amount=500000,
            start="2026-07-01",
            funder_chain=["Synthetic OPC", "Synthetic Sea Grant"],
        ),
    )
    unrelated = _normalized(
        query_config,
        taxonomy,
        "nih_reporter",
        _synthetic(
            "nih_reporter", "NIH-B", "Entirely Different Cardiology Trial", pi_names=["Roe, Sam"]
        ),
    )
    result = cluster_rows([opc, sea_grant, unrelated])
    by_key = {entry["grant_key"]: entry for entry in result.assignments}
    assert len(by_key) == 3
    assert by_key[opc["grant_key"]]["cluster_id"] == sea_grant["grant_key"]
    assert by_key[sea_grant["grant_key"]]["is_representative"] is True
    assert by_key[unrelated["grant_key"]]["cluster_size"] == 1
    assert compare_rows(opc, sea_grant) == ("pi", "funder_chain", "amount", "date") or compare_rows(
        opc, sea_grant
    )


def test_dedupe_rejects_same_title_with_contradictions(query_config: dict, taxonomy: dict) -> None:
    left = _normalized(
        query_config,
        taxonomy,
        "nsf_awards",
        _synthetic(
            "nsf_awards",
            "NSF-1",
            "Synthetic Plastic Debris Survey",
            pi_names=["Alpha, Ann"],
            amount=100000,
            start="2020-01-01",
        ),
    )
    right = _normalized(
        query_config,
        taxonomy,
        "nih_reporter",
        _synthetic(
            "nih_reporter",
            "NIH-1",
            "Synthetic Plastic Debris Survey",
            pi_names=["Beta, Bo"],
            amount=100000,
            start="2020-01-01",
        ),
    )
    assert compare_rows(left, right) is None
    assert len(cluster_rows([left, right]).assignments) == 2
    assert all(entry["cluster_size"] == 1 for entry in cluster_rows([left, right]).assignments)


def test_dedupe_requires_supporting_signal(query_config: dict, taxonomy: dict) -> None:
    left = _normalized(
        query_config,
        taxonomy,
        "nsf_awards",
        _synthetic("nsf_awards", "NSF-2", "Synthetic Plastic Debris Survey"),
    )
    right = _normalized(
        query_config,
        taxonomy,
        "usaspending",
        _synthetic("usaspending", "USA-2", "Synthetic Plastic Debris Survey"),
    )
    assert compare_rows(left, right) is None


def test_representative_prefers_pi_then_deepest_chain(query_config: dict, taxonomy: dict) -> None:
    usa = _normalized(
        query_config,
        taxonomy,
        "usaspending",
        _synthetic(
            "usaspending",
            "U-3",
            "Synthetic Microplastics Study",
            amount=10,
            start="2022-01-01",
            funder_chain=["Synthetic Federal"],
        ),
    )
    nih = _normalized(
        query_config,
        taxonomy,
        "nih_reporter",
        _synthetic(
            "nih_reporter",
            "N-3",
            "Synthetic Microplastics Study",
            amount=10,
            start="2022-01-01",
            pi_names=["Gamma, G"],
            funder_chain=["Synthetic Federal"],
        ),
    )
    result = cluster_rows([usa, nih])
    reps = [entry["grant_key"] for entry in result.assignments if entry["is_representative"]]
    assert reps == [nih["grant_key"]]


def test_report_has_no_titles_and_counts_clusters(query_config: dict, taxonomy: dict) -> None:
    left = _normalized(
        query_config,
        taxonomy,
        "nsf_awards",
        _synthetic(
            "nsf_awards", "NSF-9", "Secret Synthetic Title Words", pi_names=["Alpha, Ann"], amount=5
        ),
    )
    right = _normalized(
        query_config,
        taxonomy,
        "nih_reporter",
        _synthetic(
            "nih_reporter",
            "NIH-9",
            "Secret Synthetic Title Words",
            pi_names=["Alpha, Ann"],
            amount=5,
        ),
    )
    rows = [{**left, "_table": "nsf_awards"}, {**right, "_table": "nih_reporter"}]
    result = cluster_rows(rows)
    report = render_report(rows, result, ["csu_coast: test gap"])
    assert "Secret Synthetic Title Words" not in report
    assert "| nih_reporter | nsf_awards | 1 |" in report
    assert "csu_coast: test gap" in report
    assert isinstance(result, ClusterResult)


def test_grant_columns_unchanged() -> None:
    assert GRANT_COLUMNS[0] == "grant_key" and len(GRANT_COLUMNS) == 21
    assert date(2026, 6, 16).isoformat() == "2026-06-16"
