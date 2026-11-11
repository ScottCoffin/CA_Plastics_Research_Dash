"""Unit tests for the S8.3 NSF Award Search ingester.  Offline: fake transports only."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
import yaml

from atlas.ingest.grants import GRANT_SCHEMA, validate_grants
from atlas.ingest.grants import nsf_awards as ns

FIXTURE = Path("tests/fixtures/s8_3_nsf_awards.json")
QUERIES = Path("config/queries_v2.yml")  # fixture: request counts pinned to v2 terms
TAXONOMY = Path("config/taxonomy.yml")
TODAY = date(2026, 11, 9)


@pytest.fixture(scope="module")
def records() -> list[dict[str, Any]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["results"]


@pytest.fixture(scope="module")
def query_config() -> dict[str, Any]:
    return yaml.safe_load(QUERIES.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def taxonomy() -> dict[str, Any]:
    return yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))


def fake_transport(records: list[dict[str, Any]], *, page_limit: int | None = None):
    """Filter by state and by the ``date`` field inside the requested window."""

    def transport(params: dict[str, Any]) -> tuple[int, str]:
        start = datetime.strptime(params["dateStart"], "%m/%d/%Y").date()
        end = datetime.strptime(params["dateEnd"], "%m/%d/%Y").date()
        items = []
        for record in records:
            stamp = datetime.strptime(record["date"], "%m/%d/%Y").date()
            if not start <= stamp <= end:
                continue
            if "awardeeStateCode" in params and record["awardeeStateCode"] != "CA":
                continue
            if "perfStateCode" in params and record["perfStateCode"] != "CA":
                continue
            items.append(record)
        total = len(items)
        body: dict[str, Any] = {"metadata": {"totalCount": total, "rpp": params["rpp"]}}
        if total:
            size = params["rpp"] if page_limit is None else min(page_limit, params["rpp"])
            body["award"] = items[params["offset"] : params["offset"] + size]
        return 200, json.dumps({"response": body})

    return transport


def _run(tmp_path, transport, query_config, taxonomy, *, mode="incremental", max_requests=5000):
    return ns.run_ingest(
        mode=mode,
        output=tmp_path / "nsf_awards.parquet",
        state_path=tmp_path / "nsf_awards_state.json",
        query_config=query_config,
        taxonomy=taxonomy,
        transport=transport,
        max_requests=max_requests,
        today=TODAY,
        now=datetime(2026, 11, 9, tzinfo=UTC),
        sleep=lambda _seconds: None,
        clock=lambda: 0.0,
    )


def test_keyword_groups_quote_at_most_one_phrase(query_config):
    groups = ns.keyword_groups(query_config["core_terms"])
    assert groups[0] == "microplastic OR microplastics OR nanoplastic OR nanoplastics"
    for group in groups[1:]:
        assert group.count('"') == 2, group
    for term in query_config["core_terms"]:
        phrases = ns.search_phrases([term])
        for phrase in phrases:
            assert phrase in groups[0] or f'"{phrase}"' in groups, phrase


def test_keyword_groups_reject_embedded_quotes():
    with pytest.raises(ValueError):
        ns.keyword_groups(['plastic "debris"'])


def test_fiscal_window_and_units():
    assert ns.fiscal_window(2027) == ("10/01/2026", "09/30/2027")
    units = ns.plan_units("incremental", TODAY, {})
    assert units == [(2027, "ca"), (2027, "terms"), (2026, "ca"), (2026, "terms")]
    backfill = ns.plan_units("backfill", TODAY, {"2027:ca": "x", "2027:terms": "x"})
    assert len(backfill) == 15 * 2 - 2
    assert backfill[0] == (2026, "ca")


def test_request_params_use_state_filter_only_for_ca(query_config):
    groups = ns.keyword_groups(query_config["core_terms"])
    ca = ns.build_params(
        keyword=groups[0], fiscal_year=2026, state_filter={"awardeeStateCode": "CA"}, offset=0
    )
    terms = ns.build_params(keyword=groups[0], fiscal_year=2026, state_filter={}, offset=0)
    assert ca["awardeeStateCode"] == "CA" and "perfStateCode" not in ca
    assert "awardeeStateCode" not in terms and "perfStateCode" not in terms
    assert ca["dateStart"] == "10/01/2025" and ca["dateEnd"] == "09/30/2026"
    assert ca["rpp"] == ns.PAGE_SIZE


def test_mapping_uses_awardee_state_iso_dates_and_estimated_total(records):
    raw = ns.to_raw_grant(records[0])
    assert raw is not None
    assert raw["source_award_id"] == str(records[0]["id"])
    assert raw["funder"] == "NSF" and raw["funder_chain"] == ["NSF"]
    assert raw["url"].endswith(f"AWD_ID={records[0]['id']}")
    assert raw["start"] == datetime.strptime(records[0]["startDate"], "%m/%d/%Y").date().isoformat()
    assert raw["amount"] == records[0]["estimatedTotalAmt"]
    assert raw["currency"] == "USD"
    assert ns.to_raw_grant({"title": "no id"}) is None


def test_fixture_rows_validate(records, query_config, taxonomy):
    assert 0 < len(records) <= 30
    rows, skipped = ns.normalize_records(records, query_config=query_config, taxonomy=taxonomy)
    assert skipped == 0
    validate_grants(rows.values())
    assert all(row["source"] == "nsf_awards" for row in rows.values())


def test_pagination_collects_every_page(records, query_config):
    groups = ns.keyword_groups(query_config["core_terms"])
    client = ns.NsfClient(fake_transport(records), max_requests=500)
    fetched = ns.fetch_unit(client, fiscal_year=2024, sweep="terms", groups=groups[:1], page_size=2)
    in_window = [r for r in records if _in_fy(r["date"], 2024)]
    assert in_window, "fixture must hold records in the FY2024 window"
    assert len(fetched) == len(in_window)
    assert client.requests == -(-len(in_window) // 2)  # two records per page


def _in_fy(text: str, fiscal_year: int) -> bool:
    stamp = datetime.strptime(text, "%m/%d/%Y").date()
    return date(fiscal_year - 1, 10, 1) <= stamp <= date(fiscal_year, 9, 30)


def test_200_with_service_notification_defers_without_writing(
    tmp_path, records, query_config, taxonomy
):
    def bad(params):
        body = {
            "serviceNotification": [{"notificationType": "ERROR", "notificationMessage": "Invalid"}]
        }
        return 200, json.dumps({"response": body})

    summary = _run(tmp_path, bad, query_config, taxonomy)
    assert summary["status"] == "deferred"
    assert "Invalid" in summary["reason"]
    assert not (tmp_path / "nsf_awards.parquet").exists()


def test_ceiling_defers(tmp_path, query_config, taxonomy):
    def huge(params):
        return 200, json.dumps(
            {"response": {"metadata": {"totalCount": ns.MAX_TOTAL}, "award": []}}
        )

    summary = _run(tmp_path, huge, query_config, taxonomy)
    assert summary["status"] == "deferred"
    assert "ceiling" in summary["reason"]


def test_http_error_preserves_prior_output(tmp_path, records, query_config, taxonomy):
    ok = _run(tmp_path, fake_transport(records), query_config, taxonomy)
    assert ok["status"] == "ok"
    before = (tmp_path / "nsf_awards.parquet").read_bytes()
    state_before = (tmp_path / "nsf_awards_state.json").read_bytes()

    def failing(params):
        return 400, "<html>Bad Request</html>"

    summary = _run(tmp_path, failing, query_config, taxonomy)
    assert summary["status"] == "deferred"
    assert (tmp_path / "nsf_awards.parquet").read_bytes() == before
    assert (tmp_path / "nsf_awards_state.json").read_bytes() == state_before


def test_retry_recovers_from_rate_limit(tmp_path, records, query_config, taxonomy):
    inner = fake_transport(records)
    calls = {"n": 0}

    def flaky(params):
        calls["n"] += 1
        if calls["n"] == 1:
            return 429, "slow down"
        return inner(params)

    summary = _run(tmp_path, flaky, query_config, taxonomy, max_requests=500)
    assert summary["status"] == "ok"
    assert summary["requests"] == calls["n"]


def test_backfill_request_cap_is_enforced_and_resumes(tmp_path, records, query_config, taxonomy):
    first = _run(
        tmp_path, fake_transport(records), query_config, taxonomy, mode="backfill", max_requests=5
    )
    assert first["status"] == "partial"
    assert first["requests"] <= 5
    assert first["units_completed"] == 0
    assert not (tmp_path / "nsf_awards.parquet").exists()

    full = _run(
        tmp_path,
        fake_transport(records),
        query_config,
        taxonomy,
        mode="backfill",
        max_requests=10_000,
    )
    assert full["status"] == "ok"
    assert full["units_completed"] == full["units_planned"] == 30
    state = json.loads((tmp_path / "nsf_awards_state.json").read_text(encoding="utf-8"))
    assert len(state["completed"]) == 30


def test_incremental_uses_current_and_previous_fy(tmp_path, records, query_config, taxonomy):
    summary = _run(tmp_path, fake_transport(records), query_config, taxonomy)
    assert summary["fiscal_years"] == [2027, 2026]
    state = json.loads((tmp_path / "nsf_awards_state.json").read_text(encoding="utf-8"))
    assert set(state["completed"]) == {"2027:ca", "2027:terms", "2026:ca", "2026:terms"}


def test_dry_run_plan_makes_no_requests_or_writes(tmp_path, query_config):
    plan = ns.dry_run_plan(
        mode="incremental",
        today=TODAY,
        query_config=query_config,
        state_path=tmp_path / "missing.json",
        max_requests=3,
    )
    groups = ns.keyword_groups(query_config["core_terms"])
    # Incremental: two fiscal years x (ca: 2 state filters + terms: 1) x keyword queries.
    assert plan["planned_requests_at_least"] == 2 * 3 * len(groups)
    assert plan["units"] == 4
    assert len(plan["requests"]) == 3
    assert not (tmp_path / "missing.json").exists()


def test_output_schema_matches_c3(tmp_path, records, query_config, taxonomy):
    summary = _run(tmp_path, fake_transport(records), query_config, taxonomy)
    table = pq.read_table(tmp_path / "nsf_awards.parquet")
    assert table.schema.equals(GRANT_SCHEMA)
    assert table.num_rows == summary["rows_written"] > 0
