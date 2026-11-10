"""Tests for the S8.4 USAspending ingester.  Fakes only; no network calls."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
import yaml

from atlas.ingest.grants import GRANT_SCHEMA, validate_grants
from atlas.ingest.grants import usaspending as us

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/s8_4_usaspending.json"
QUERIES = ROOT / "config/queries.yml"
TAXONOMY = ROOT / "config/taxonomy.yml"
TODAY = date(2026, 11, 9)


@pytest.fixture(scope="module")
def records() -> list[dict[str, Any]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["results"]


@pytest.fixture(scope="module")
def configs() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        yaml.safe_load(QUERIES.read_text(encoding="utf-8")),
        yaml.safe_load(TAXONOMY.read_text(encoding="utf-8")),
    )


def _paged_transport(records, calls=None):
    def transport(path: str, body: dict[str, Any]) -> tuple[int, str]:
        assert path == us.SEARCH_PATH
        if calls is not None:
            calls.append(body)
        page, limit = body["page"], body["limit"]
        items = [dict(r) for r in records[(page - 1) * limit : page * limit]]
        has_next = page * limit < len(records)
        return 200, json.dumps(
            {"results": items, "page_metadata": {"page": page, "hasNext": has_next}}
        )

    return transport


def _no_sleep(_seconds: float) -> None:
    return None


def _run(tmp_path: Path, transport, configs, **overrides):
    query_config, taxonomy = configs
    options: dict[str, Any] = {
        "mode": "incremental",
        "output": tmp_path / "usaspending.parquet",
        "state_path": tmp_path / "usaspending_state.json",
        "query_config": query_config,
        "taxonomy": taxonomy,
        "transport": transport,
        "max_requests": 50,
        "today": TODAY,
        "sleep": _no_sleep,
        "clock": lambda: 0.0,
    }
    options.update(overrides)
    return us.run_ingest(**options)


def test_term_set_is_curated_and_excludes_noisy_substrings() -> None:
    assert "plastic" not in us.USASPENDING_TERMS
    assert "polymer" not in us.USASPENDING_TERMS
    assert {"microplastic", "nanoplastic", "marine debris"} <= set(us.USASPENDING_TERMS)
    assert len(set(us.USASPENDING_TERMS)) == len(us.USASPENDING_TERMS)


def test_filters_carry_award_codes_window_and_location() -> None:
    recipient = us.build_filters("ca_recipient", 2025)
    pop = us.build_filters("ca_pop", 2025)
    assert recipient["award_type_codes"] == ["02", "03", "04", "05"]
    assert recipient["time_period"] == [{"start_date": "2024-10-01", "end_date": "2025-09-30"}]
    assert recipient["recipient_locations"] == [{"country": "USA", "state": "CA"}]
    assert "place_of_performance_locations" not in recipient
    assert pop["place_of_performance_locations"] == [{"country": "USA", "state": "CA"}]
    assert pop["keywords"] == list(us.USASPENDING_TERMS)
    with pytest.raises(ValueError):
        us.build_filters("nationwide", 2025)


def test_fiscal_year_bounds_and_plans() -> None:
    assert us.fiscal_year_bounds(2026) == (date(2025, 10, 1), date(2026, 9, 30))
    assert len(us.plan_units("backfill", TODAY, {})) == 30
    completed = {"2027:ca_recipient": "x"}
    remaining = us.plan_units("backfill", TODAY, completed)
    assert (2027, "ca_recipient") not in remaining
    assert len(remaining) == 29


def test_pagination_follows_has_next(records) -> None:
    calls: list[dict[str, Any]] = []
    client = us.UsaspendingClient(
        _paged_transport(records, calls), max_requests=50, sleep=_no_sleep
    )
    fetched = us.fetch_unit(client, fiscal_year=2025, sweep="ca_recipient", page_size=5)
    assert len(fetched) == len(records)
    assert [call["page"] for call in calls] == [1, 2, 3]


def test_page_cap_raises_and_defers(records, configs, tmp_path) -> None:
    client = us.UsaspendingClient(_paged_transport(records), max_requests=50, sleep=_no_sleep)
    with pytest.raises(us.PageCapExceeded):
        us.fetch_unit(client, fiscal_year=2025, sweep="ca_recipient", page_size=2, max_pages=2)
    summary = _run(tmp_path, _paged_transport(records), configs, max_pages=2, page_size=2)
    assert summary["status"] == "deferred"
    assert not (tmp_path / "usaspending.parquet").exists()


def test_empty_page_with_has_next_is_a_response_error(configs, tmp_path) -> None:
    def transport(path, body):
        return 200, json.dumps({"results": [], "page_metadata": {"page": 1, "hasNext": True}})

    summary = _run(tmp_path, transport, configs)
    assert summary["status"] == "deferred"


def test_normalize_maps_identity_funder_and_url(records, configs) -> None:
    query_config, taxonomy = configs
    raw = us.to_raw_grant(records[0])
    assert raw is not None
    assert raw["source_award_id"] == records[0]["generated_internal_id"]
    assert raw["funder"] == records[0]["Awarding Agency"]
    assert raw["program"] == records[0]["Awarding Sub Agency"]
    assert raw["funder_chain"] == [records[0]["Awarding Agency"], records[0]["Awarding Sub Agency"]]
    assert raw["url"] == f"https://www.usaspending.gov/award/{records[0]['generated_internal_id']}"
    assert len(raw["title"]) <= us.TITLE_CHARS
    rows, skipped = us.normalize_records(records, query_config=query_config, taxonomy=taxonomy)
    assert skipped == 0
    validate_grants(rows.values())


def test_blank_description_falls_back_to_award_id() -> None:
    raw = us.to_raw_grant(
        {"generated_internal_id": "ASST_X_1", "Award ID": "1", "Description": " "}
    )
    assert raw is not None and raw["title"] == "Award 1"
    assert us.to_raw_grant({"Award ID": "1"}) is None


def test_dedupe_across_sweeps_by_generated_internal_id(records, configs, tmp_path) -> None:
    summary = _run(tmp_path, _paged_transport(records), configs)
    assert summary["status"] == "ok"
    assert summary["requests"] == 4
    table = pq.read_table(tmp_path / "usaspending.parquet")
    assert table.schema.equals(GRANT_SCHEMA)
    unique_ids = {r["generated_internal_id"] for r in records}
    assert table.num_rows == len(unique_ids)


def test_budget_exhaustion_is_partial_and_resumable(records, configs, tmp_path) -> None:
    first = _run(tmp_path, _paged_transport(records), configs, mode="backfill", max_requests=2)
    assert first["status"] == "partial"
    assert first["units_completed"] == 2
    state = json.loads((tmp_path / "usaspending_state.json").read_text(encoding="utf-8"))
    assert len(state["completed"]) == 2

    calls: list[dict[str, Any]] = []
    second = _run(
        tmp_path, _paged_transport(records, calls), configs, mode="backfill", max_requests=5
    )
    assert second["units_completed"] == 5
    done_years = {(call["filters"]["time_period"][0]["end_date"]) for call in calls}
    assert len(done_years) >= 1


def test_http_failure_defers_and_preserves_prior_output(records, configs, tmp_path) -> None:
    assert _run(tmp_path, _paged_transport(records), configs)["status"] == "ok"
    before = (tmp_path / "usaspending.parquet").read_bytes()
    state_before = (tmp_path / "usaspending_state.json").read_bytes()

    def failing(path, body):
        return 500, "server error"

    summary = _run(tmp_path, failing, configs)
    assert summary["status"] == "deferred"
    assert (tmp_path / "usaspending.parquet").read_bytes() == before
    assert (tmp_path / "usaspending_state.json").read_bytes() == state_before


def test_retry_then_success_on_429(records, configs, tmp_path) -> None:
    responses = [(429, "slow down")]
    inner = _paged_transport(records)

    def flaky(path, body):
        if responses:
            return responses.pop()
        return inner(path, body)

    summary = _run(tmp_path, flaky, configs, mode="incremental")
    assert summary["status"] == "ok"
    assert summary["requests"] == 5


def test_bad_request_is_not_retried(configs, tmp_path) -> None:
    calls: list[int] = []

    def rejected(path, body):
        calls.append(1)
        return 422, '{"detail": "limit above max"}'

    summary = _run(tmp_path, rejected, configs)
    assert summary["status"] == "deferred"
    assert len(calls) == 1


def test_dry_run_plan_makes_no_calls(tmp_path) -> None:
    plan = us.dry_run_plan(
        mode="incremental", today=TODAY, state_path=tmp_path / "s.json", max_requests=3
    )
    assert plan["units"] == 4
    assert len(plan["requests"]) == 3
    assert plan["requests"][0]["first_page"]["page"] == 1
    assert not (tmp_path / "s.json").exists()


def _bulk_zip(rows: list[dict[str, str]]) -> bytes:
    columns = list(us.BULK_COLUMNS.values())
    buffer = io.StringIO()
    writer_rows = [",".join(columns)]
    for row in rows:
        writer_rows.append(",".join(str(row.get(column, "")) for column in columns))
    buffer.write("\n".join(writer_rows) + "\n")
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as bundle:
        bundle.writestr("award_data.csv", buffer.getvalue())
    return out.getvalue()


def test_bulk_filters_locally_and_applies(tmp_path, configs) -> None:
    rows = [
        {
            "generated_unique_award_id": "ASST_NON_BULK1_068",
            "award_id_fain": "BULK1",
            "recipient_name": "CA Univ",
            "recipient_state_code": "CA",
            "period_of_performance_start_date": "2024-01-01",
            "period_of_performance_current_end_date": "2026-12-31",
            "total_obligated_amount": "1000.5",
            "awarding_agency_name": "National Science Foundation",
            "awarding_sub_agency_name": "NSF",
            "prime_award_base_transaction_description": "Study of Microplastic fibers in estuaries",
        },
        {
            "generated_unique_award_id": "ASST_NON_BULK2_068",
            "recipient_state_code": "TX",
            "prime_award_base_transaction_description": "microplastic work out of state",
        },
        {
            "generated_unique_award_id": "ASST_NON_BULK3_068",
            "recipient_state_code": "CA",
            "prime_award_base_transaction_description": "water quality planning",
        },
    ]
    archive = tmp_path / "bulk.zip"
    archive.write_bytes(_bulk_zip(rows))
    query_config, taxonomy = configs
    posted: list[tuple[str, dict[str, Any]]] = []

    def transport(path, body):
        posted.append((path, body))
        return 200, json.dumps(
            {"status": "ready", "file_url": "https://files.usaspending.gov/x.zip"}
        )

    def download(url, destination: Path):
        assert url == "https://files.usaspending.gov/x.zip"
        destination.write_bytes(archive.read_bytes())

    summary = us.run_bulk_ingest(
        fiscal_years=[2027],
        output=tmp_path / "usaspending.parquet",
        state_path=tmp_path / "state.json",
        query_config=query_config,
        taxonomy=taxonomy,
        transport=transport,
        max_requests=5,
        today=TODAY,
        download=download,
        sleep=_no_sleep,
        clock=lambda: 0.0,
    )
    assert summary["status"] == "ok", summary
    assert summary["requests"] == 2
    assert posted[0][0] == us.BULK_PATH
    assert posted[0][1]["file_format"] == "csv"
    table = pq.read_table(tmp_path / "usaspending.parquet").to_pylist()
    assert [row["source_award_id"] for row in table] == ["ASST_NON_BULK1_068"]
    assert table[0]["source"] == "usaspending"


def test_bulk_rejects_untrusted_download_host() -> None:
    with pytest.raises(us.UsaspendingResponseError):
        us.bulk_file_url({"file_url": "https://evil.example/award.zip"})
    with pytest.raises(us.UsaspendingResponseError):
        us.bulk_file_url({"file_url": "http://files.usaspending.gov/award.zip"})
    assert us.bulk_file_url({"file_url": "https://files.usaspending.gov/a.zip"}).startswith(
        "https://"
    )


def test_bulk_budget_counts_download(tmp_path, configs) -> None:
    query_config, taxonomy = configs

    def transport(path, body):
        return 200, json.dumps({"file_url": "https://files.usaspending.gov/x.zip"})

    summary = us.run_bulk_ingest(
        fiscal_years=[2027, 2026],
        output=tmp_path / "usaspending.parquet",
        state_path=tmp_path / "state.json",
        query_config=query_config,
        taxonomy=taxonomy,
        transport=transport,
        max_requests=3,
        today=TODAY,
        download=lambda url, destination: destination.write_bytes(_bulk_zip([])),
        sleep=_no_sleep,
        clock=lambda: 0.0,
    )
    assert summary["status"] == "partial"
    assert summary["requests"] == 3
