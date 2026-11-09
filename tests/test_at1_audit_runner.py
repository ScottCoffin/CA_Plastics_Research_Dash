"""Offline acceptance for AT-1 audit preparation and bounded request behavior."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.util.budget import OpenAlexBudget
from atlas.util.cost import ApiCostLogger
from scripts import run_at1_audit as audit


def _fixtures(tmp_path: Path) -> tuple[Path, Path, Path]:
    query_path = tmp_path / "query.txt"
    query_path.write_text(
        'title_and_abstract.search:(microplastic OR "plastic pollution")\n',
        encoding="utf-8",
    )
    review_path = tmp_path / "review.csv"
    registry_path = tmp_path / "institutions.parquet"
    rows = [
        {
            "review_rank": str(index),
            "openalex_id": f"I{index}",
            "display_name": f"Institution {index}",
        }
        for index in range(1, 21)
    ]
    with review_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    pq.write_table(
        pa.Table.from_pylist(
            [
                {"openalex_id": row["openalex_id"], "display_name": row["display_name"]}
                for row in rows
            ]
        ),
        registry_path,
    )
    return query_path, review_path, registry_path


def test_rate_limit_snapshot_parses_usage_aliases_and_rejects_malformed_values():
    body = {
        "rate_limit": {
            "daily_budget_usd": 1,
            "daily_remaining_usd": 0.9,
            "credits_limit": 10000,
            "credits_used": 1000,
            "credits_remaining": 9000,
            "prepaid_remaining_usd": 0,
            "onetime_credits_balance": 0,
            "onetime_credits_remaining": 0,
            "resets_at": "2026-11-10T00:00:00.000Z",
            "resets_in_seconds": 300,
        }
    }
    parsed = audit._rate_limit_state(body, now=datetime(2026, 11, 9, 23, 55, tzinfo=UTC))
    assert parsed["credits_used"] == Decimal(1000)
    assert parsed["onetime_credits_balance"] == Decimal(0)
    assert parsed["resets_at"] == "2026-11-10T00:00:00+00:00"
    assert parsed["resets_in_seconds_at_capture"] == Decimal(300)
    minimal_provider_shape = {"rate_limit": dict(body["rate_limit"])}
    minimal_provider_shape["rate_limit"].pop("resets_in_seconds")
    derived = audit._rate_limit_state(
        minimal_provider_shape, now=datetime(2026, 11, 9, 23, 55, tzinfo=UTC)
    )
    assert derived["resets_in_seconds_at_capture"] == Decimal(300)
    assert derived["reset_seconds_source"] == "derived_from_resets_at_and_observation_time"
    body["rate_limit"]["credits_used"] = "invalid"
    try:
        audit._rate_limit_state(body, now=datetime(2026, 11, 9, 23, 55, tzinfo=UTC))
    except audit.AuditStop as error:
        assert "credits_used" in str(error)
    else:
        raise AssertionError("malformed provider usage must stop the audit")

    diagnostic = audit._status_schema_diagnostics(
        {"api_key": "secret-canary", "rate_limit": {"credits_used": "bad", "private": "secret"}}
    )
    rendered = json.dumps(diagnostic)
    assert "credits_used" in rendered and "secret-canary" not in rendered
    assert "private" not in rendered


def test_status_failure_log_keeps_only_sanitized_schema_evidence(tmp_path: Path):
    path = tmp_path / "usage.jsonl"
    diagnostics = audit._status_schema_diagnostics(
        {
            "api_key": "secret-canary",
            "rate_limit": {"daily_budget_usd": 1, "credits_used": "invalid", "other": "secret"},
        }
    )
    with ApiCostLogger("status-failure", path) as logger:
        logger.record_account_balance_snapshot(
            url=f"{audit.BASE}/rate-limit?api_key=secret-canary",
            status_code=200,
            snapshot=None,
            diagnostics=diagnostics,
        )
    content = path.read_text(encoding="utf-8")
    record = json.loads(content.splitlines()[0])
    assert record["endpoint_type"] == "account_balance_snapshot"
    assert record["account_balance"] == {}
    assert record["schema_diagnostics"]["rate_limit_fields"]["daily_budget_usd"] == {
        "type": "int",
        "value": "1",
    }
    assert "secret-canary" not in content and "other" not in content


def test_resolved_progress_cache_query_alias_rejected_before_request(monkeypatch, tmp_path: Path):
    query_path, review_path, registry_path = _fixtures(tmp_path)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "alias").mkdir()
    original = query_path.read_bytes()
    calls = []

    with pytest.raises(audit.AuditStop, match="artifact path collision"):
        audit.run_audit(
            api_key="secret-sentinel",
            confirmation=audit.FREE_ONLY_CONFIRMATION,
            request_fn=lambda *args: calls.append(args) or pytest.fail("no request expected"),
            query_path=Path("query.txt"),
            review_path=review_path,
            registry_path=registry_path,
            usage_log=tmp_path / "logs/usage.jsonl",
            output_csv=tmp_path / "docs/review.csv",
            output_json=tmp_path / "docs/counts.json",
            progress_cache_path=Path("alias/../query.txt"),
        )
    assert calls == []
    assert query_path.read_bytes() == original


def test_progress_cache_csv_output_alias_rejected_without_overwrite(tmp_path: Path):
    query_path, review_path, registry_path = _fixtures(tmp_path)
    (tmp_path / "alias").mkdir()
    csv_output = tmp_path / "review.csv"
    original = b"owner review artifact must survive collision detection\n"
    csv_output.write_bytes(original)
    calls = []

    with pytest.raises(audit.AuditStop, match="artifact path collision"):
        audit.run_audit(
            api_key="secret-sentinel",
            confirmation=audit.FREE_ONLY_CONFIRMATION,
            request_fn=lambda *args: calls.append(args) or pytest.fail("no request expected"),
            query_path=query_path,
            review_path=review_path,
            registry_path=registry_path,
            usage_log=tmp_path / "logs/usage.jsonl",
            output_csv=csv_output,
            output_json=tmp_path / "counts.json",
            progress_cache_path=tmp_path / "alias/../review.csv",
        )
    assert calls == []
    assert csv_output.read_bytes() == original


def test_rate_limit_reset_must_be_fresh_and_countdown_consistent():
    now = datetime(2026, 11, 9, 23, 55, tzinfo=UTC)
    for reset_at, reset_seconds in (
        ("2026-11-09T23:00:00Z", 300),
        ("2099-01-01T00:00:00Z", 1),
        ("2026-11-10T00:00:00Z", 1e100),
        ("2026-11-10T00:10:00Z", 1),
    ):
        body = {
            "rate_limit": {
                "daily_budget_usd": 1,
                "daily_remaining_usd": 0.9,
                "credits_limit": 10000,
                "credits_used": 1000,
                "credits_remaining": 9000,
                "prepaid_remaining_usd": 0,
                "onetime_credits_remaining": 0,
                "resets_at": reset_at,
                "resets_in_seconds_at_capture": reset_seconds,
            }
        }
        try:
            audit._rate_limit_state(body, now=now)
        except audit.AuditStop as error:
            assert "reset" in str(error)
        else:
            raise AssertionError("stale or inconsistent reset evidence must stop")


def test_undersized_stratum_is_saved_and_remaining_strata_continue(tmp_path):
    query_path, review_path, registry_path = _fixtures(tmp_path)
    seen = []

    def request(url, key, timeout):
        assert key == "secret-sentinel"
        assert timeout == audit.MAX_TIMEOUT_SECONDS
        seen.append(url)
        if url.endswith("/rate-limit"):
            return (
                200,
                {
                    "rate_limit": {
                        "daily_budget_usd": 1,
                        "daily_remaining_usd": 0.97,
                        "credits_limit": 10000,
                        "credits_remaining": 9000,
                        "prepaid_remaining_usd": 0,
                        "onetime_credits_remaining": 0,
                        "credits_used": 1000,
                        "onetime_credits_balance": 0,
                        "resets_at": "2026-11-10T00:00:00.000Z",
                        "resets_in_seconds": 300,
                    }
                },
                {},
            )
        params = parse_qs(urlsplit(url).query)
        raw = urlsplit(url).query
        assert "%28" in raw and "%20" in raw and "%22" in raw
        assert "search" not in params
        if "per_page" in params and params["per_page"] == ["1"]:
            filter_value = params["filter"][0]
            if "institutions.id:" not in filter_value:
                count = 98118
            else:
                institution_id = filter_value.rsplit("institutions.id:", 1)[1]
                count = {
                    audit.BASELINE_IDS["UCSF"]: 25,
                    audit.BASELINE_IDS["SLAC"]: 2,
                    audit.BASELINE_IDS["UC Davis"]: 129,
                }[institution_id]
            return (
                200,
                {"meta": {"count": count, "cost_usd": 0.0001}},
                {"X-RateLimit-Credits-Used": "1"},
            )
        filter_value = params["filter"][0]
        institution_id = filter_value.rsplit("institutions.id:", 1)[1]
        index = int(institution_id[1:])
        works = []
        work_count = 4 if index == 2 else 25
        for row_index in range(work_count):
            work_id = "Wshared" if index in {1, 2} and row_index == 0 else f"W{index}-{row_index}"
            works.append(
                {
                    "id": f"https://openalex.org/{work_id}",
                    "title": f"Title {work_id}",
                    "doi": f"https://doi.org/10.1234/{work_id}",
                    "publication_date": "2026-01-01",
                    "abstract_inverted_index": {"microplastic": [0], "study": [1]},
                }
            )
        return (
            200,
            {"meta": {"count": work_count, "cost_usd": 0.0001}, "results": works},
            {"X-RateLimit-Credits-Used": "1"},
        )

    output_csv = tmp_path / "out" / "sample.csv"
    output_json = tmp_path / "out" / "counts.json"
    progress_cache = tmp_path / "ignored" / "progress.json"
    usage_log = tmp_path / "logs" / "usage.jsonl"
    result = audit.run_audit(
        api_key="secret-sentinel",
        confirmation=audit.FREE_ONLY_CONFIRMATION,
        request_fn=request,
        query_path=query_path,
        review_path=review_path,
        registry_path=registry_path,
        usage_log=usage_log,
        output_csv=output_csv,
        output_json=output_json,
        progress_cache_path=progress_cache,
        budget=OpenAlexBudget(
            max_cost_usd=Decimal("0.10"),
            max_credits=Decimal("1000"),
            cost_per_credit_usd=Decimal("0.0001"),
            reserve_cost_usd=Decimal("0.001"),
            reserve_credits=Decimal("10"),
        ),
        now=lambda: datetime(2026, 11, 9, 23, 55, tzinfo=UTC),
    )
    assert result["request_count_this_run"] == len(seen) == 25
    assert result["sample_rows"] == 479
    assert result["unique_work_ids"] == 478
    assert result["duplicate_work_id_rows"] == 1
    assert result["sample_shortfall_rows"] == 21
    assert result["collection_status"] == "partial_with_shortfalls_or_pending_strata"
    with output_csv.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 479
    assert all(row["review_label"] == "" and row["reviewer"] == "" for row in rows)
    assert rows[0]["source_query"].startswith("title_and_abstract.search:")
    assert any(row["duplicate_across_strata"] == "yes" for row in rows)
    assert result["baselines"] == {
        "global": 98118,
        "UCSF": 25,
        "SLAC": 2,
        "UC Davis": 129,
    }
    assert result["baseline_within_10_percent"] == {
        "global": True,
        "UCSF": True,
        "SLAC": True,
        "UC Davis": True,
    }
    assert progress_cache.exists()
    records = [json.loads(line) for line in usage_log.read_text(encoding="utf-8").splitlines()]
    request_records = [record for record in records if record.get("record_type") == "request"]
    assert len(request_records) == 25
    status_record = next(row for row in request_records if row.get("endpoint_type"))
    assert status_record["endpoint_type"] == "account_balance_snapshot"
    assert status_record["request_cost_known"] is False
    assert status_record["credits_known"] is False
    assert "credits_used" in status_record["account_balance"]
    assert "secret-sentinel" not in usage_log.read_text(encoding="utf-8")
    assert json.loads(output_json.read_text(encoding="utf-8"))["labelled_rows"] == 0


def test_progress_survives_later_error_and_resume_skips_cached_calls(tmp_path):
    query_path, review_path, registry_path = _fixtures(tmp_path)
    output_csv = tmp_path / "docs" / "review.csv"
    output_json = tmp_path / "docs" / "counts.json"
    progress_cache = tmp_path / "ignored" / "progress.json"
    usage_log = tmp_path / "logs" / "usage.jsonl"
    budget = OpenAlexBudget(
        max_cost_usd=Decimal("0.10"),
        max_credits=Decimal("1000"),
        cost_per_credit_usd=Decimal("0.0001"),
        reserve_cost_usd=Decimal("0.001"),
        reserve_credits=Decimal("10"),
    )

    def now():
        return datetime(2026, 11, 9, 23, 55, tzinfo=UTC)

    def status_response():
        return (
            200,
            {
                "rate_limit": {
                    "daily_budget_usd": 1,
                    "daily_remaining_usd": 0.97,
                    "credits_limit": 10000,
                    "credits_remaining": 9000,
                    "credits_used": 1000,
                    "prepaid_remaining_usd": 0,
                    "onetime_credits_remaining": 0,
                    "resets_at": "2026-11-10T00:00:00.000Z",
                    "resets_in_seconds": 300,
                }
            },
            {},
        )

    def baseline_response(url):
        params = parse_qs(urlsplit(url).query)
        filter_value = params["filter"][0]
        if "institutions.id:" not in filter_value:
            count = 98118
        else:
            institution_id = filter_value.rsplit("institutions.id:", 1)[1]
            count = {
                audit.BASELINE_IDS["UCSF"]: 25,
                audit.BASELINE_IDS["SLAC"]: 2,
                audit.BASELINE_IDS["UC Davis"]: 129,
            }[institution_id]
        return (
            200,
            {"meta": {"count": count, "cost_usd": 0.0001}},
            {"X-RateLimit-Credits-Used": "1"},
        )

    def works_response(index: int):
        count = 4 if index == 2 else 25
        records = []
        for position in range(count):
            work_id = "Wshared" if index in {1, 3} and position == 0 else f"W{index}-{position}"
            records.append(
                {
                    "id": f"https://openalex.org/{work_id}",
                    "title": f"Title {work_id}",
                    "doi": f"https://doi.org/10.1234/{work_id}",
                    "publication_date": "2026-01-01",
                    "abstract_inverted_index": {"microplastic": [0]},
                }
            )
        return (
            200,
            {"meta": {"count": count, "cost_usd": 0.0001}, "results": records},
            {"X-RateLimit-Credits-Used": "1"},
        )

    first_calls = []

    def first_request(url, key, timeout):
        first_calls.append(url)
        if url.endswith("/rate-limit"):
            return status_response()
        params = parse_qs(urlsplit(url).query)
        if params.get("per_page") == ["1"]:
            return baseline_response(url)
        institution_id = params["filter"][0].rsplit("institutions.id:", 1)[1]
        if institution_id == "I3":
            return 503, {"message": "temporarily unavailable"}, {"X-RateLimit-Credits-Used": "1"}
        return works_response(int(institution_id[1:]))

    try:
        audit.run_audit(
            api_key="secret-sentinel",
            confirmation=audit.FREE_ONLY_CONFIRMATION,
            request_fn=first_request,
            query_path=query_path,
            review_path=review_path,
            registry_path=registry_path,
            usage_log=usage_log,
            output_csv=output_csv,
            output_json=output_json,
            progress_cache_path=progress_cache,
            budget=budget,
            now=now,
        )
    except audit.AuditStop as error:
        assert "HTTP 503" in str(error)
    else:
        raise AssertionError("the simulated HTTP 503 must stop this run")

    cached = json.loads(progress_cache.read_text(encoding="utf-8"))
    assert set(cached["baselines"]) == {"global", "UCSF", "SLAC", "UC Davis"}
    assert set(cached["samples"]) == {"I1", "I2"}
    with output_csv.open(encoding="utf-8", newline="") as stream:
        partial_rows = list(csv.DictReader(stream))
    assert len(partial_rows) == 29
    assert all(row["review_label"] == "" for row in partial_rows)

    second_calls = []

    def second_request(url, key, timeout):
        second_calls.append(url)
        if url.endswith("/rate-limit"):
            return status_response()
        params = parse_qs(urlsplit(url).query)
        assert params.get("per_page") != ["1"], "valid cached baselines must not be reissued"
        institution_id = params["filter"][0].rsplit("institutions.id:", 1)[1]
        assert institution_id not in {"I1", "I2"}, "valid cached sample strata must not be reissued"
        return works_response(int(institution_id[1:]))

    result = audit.run_audit(
        api_key="secret-sentinel",
        confirmation=audit.FREE_ONLY_CONFIRMATION,
        request_fn=second_request,
        query_path=query_path,
        review_path=review_path,
        registry_path=registry_path,
        usage_log=usage_log,
        output_csv=output_csv,
        output_json=output_json,
        progress_cache_path=progress_cache,
        budget=budget,
        now=now,
    )
    assert len(second_calls) == 19  # fresh status plus the 18 uncached strata
    assert result["sample_rows"] == 479
    assert result["sample_strata_completed"] == 20
    assert result["per_institution"]["I2"]["sampled_rows"] == 4
    assert result["per_institution"]["I2"]["shortfall"] == 21
    assert result["metered_credits_this_run"] == "18"
    assert result["metered_accounted_cost_usd_this_run"] == "0.0018"
    with output_csv.open(encoding="utf-8", newline="") as stream:
        final_rows = list(csv.DictReader(stream))
    assert len(final_rows) == 479
    assert sum(row["duplicate_across_strata"] == "yes" for row in final_rows) == 2


def test_free_only_and_zero_prepaid_gate_fails_closed(tmp_path):
    query_path, review_path, registry_path = _fixtures(tmp_path)

    def request(url, key, timeout):
        return (
            200,
            {
                "rate_limit": {
                    "daily_budget_usd": 1,
                    "daily_remaining_usd": 1,
                    "credits_limit": 10000,
                    "credits_remaining": 10000,
                    "prepaid_remaining_usd": 0.01,
                    "onetime_credits_remaining": 0,
                    "resets_at": "2026-11-10T00:00:00.000Z",
                    "resets_in_seconds": 300,
                }
            },
            {"X-RateLimit-Credits-Used": "1"},
        )

    try:
        audit.run_audit(
            api_key="secret-sentinel",
            confirmation=audit.FREE_ONLY_CONFIRMATION,
            request_fn=request,
            query_path=query_path,
            review_path=review_path,
            registry_path=registry_path,
            usage_log=tmp_path / "logs/usage.jsonl",
            output_csv=tmp_path / "out.csv",
            output_json=tmp_path / "out.json",
            progress_cache_path=tmp_path / "cache/progress.json",
            budget=OpenAlexBudget(
                max_cost_usd=Decimal("0.10"),
                max_credits=Decimal("1000"),
                cost_per_credit_usd=Decimal("0.0001"),
                reserve_cost_usd=Decimal("0.001"),
                reserve_credits=Decimal("10"),
            ),
            now=lambda: datetime(2026, 11, 9, 23, 55, tzinfo=UTC),
        )
    except audit.AuditStop as error:
        assert "nonzero prepaid" in str(error)
    else:
        raise AssertionError("nonzero prepaid balance must block the audit")


def test_status_without_credit_header_is_snapshot_but_unknown_query_stops(tmp_path):
    query_path, review_path, registry_path = _fixtures(tmp_path)
    calls = []

    def request(url, key, timeout):
        calls.append(url)
        if url.endswith("/rate-limit"):
            return (
                200,
                {
                    "rate_limit": {
                        "daily_budget_usd": 1,
                        "daily_remaining_usd": 1,
                        "credits_limit": 10000,
                        "credits_remaining": 10000,
                        "prepaid_remaining_usd": 0,
                        "onetime_credits_remaining": 0,
                        "resets_at": "2026-11-10T00:00:00.000Z",
                        "resets_in_seconds": 300,
                    }
                },
                {},
            )
        return 200, {"meta": {"count": 2}}, {}

    usage_log = tmp_path / "logs/usage.jsonl"
    try:
        audit.run_audit(
            api_key="secret-sentinel",
            confirmation=audit.FREE_ONLY_CONFIRMATION,
            request_fn=request,
            query_path=query_path,
            review_path=review_path,
            registry_path=registry_path,
            usage_log=usage_log,
            output_csv=tmp_path / "out.csv",
            output_json=tmp_path / "out.json",
            progress_cache_path=tmp_path / "cache/progress.json",
            budget=OpenAlexBudget(
                max_cost_usd=Decimal("0.10"),
                max_credits=Decimal("1000"),
                cost_per_credit_usd=Decimal("0.0001"),
                reserve_cost_usd=Decimal("0.001"),
                reserve_credits=Decimal("10"),
            ),
            now=lambda: datetime(2026, 11, 9, 23, 55, tzinfo=UTC),
        )
    except audit.AuditStop as error:
        assert "missing valid credit header" in str(error)
    else:
        raise AssertionError("unknown ordinary request cost must block the audit")
    assert len(calls) == 2 and calls[0] == f"{audit.BASE}/rate-limit"
    assert not calls[1].endswith("/rate-limit")
    records = [json.loads(line) for line in usage_log.read_text(encoding="utf-8").splitlines()]
    request_records = [record for record in records if record.get("record_type") == "request"]
    assert len(request_records) == 2
    assert request_records[0]["endpoint_type"] == "account_balance_snapshot"
    assert request_records[0]["request_cost_known"] is False
    assert request_records[0]["credits_known"] is False
    assert request_records[1]["credits_known"] is False
    assert request_records[1]["cost_known"] is False
    failure_records = [
        json.loads(line)
        for line in (usage_log.parent / "at1_audit_failure.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert failure_records[0]["accounting_known"] is False
    assert failure_records[0]["credits_total"] is None
    assert failure_records[0]["accounted_cost_usd"] is None
    assert not (tmp_path / "out.csv").exists()
