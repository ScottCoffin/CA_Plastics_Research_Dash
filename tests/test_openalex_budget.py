from __future__ import annotations

import io
import json
import urllib.error
from datetime import date
from decimal import Decimal
from email.message import Message
from pathlib import Path

import pytest

from atlas.ingest import openalex
from atlas.ingest.openalex import OpenAlexBudgetError, OpenAlexPaths
from atlas.util.budget import (
    conservative_request_cost,
    daily_logged_usage,
    resolve_openalex_budget,
)
from atlas.util.cost import ApiCostLogger, OpenAlexUsageMetadataError


def write_budget(
    path: Path,
    *,
    abort_usd: str = "0.25",
    abort_credits: str = "2500",
    reserve_usd: str = "0.001",
) -> None:
    path.write_text(
        "\n".join(
            [
                "daily_ceiling_usd: 1.0",
                f"abort_threshold_usd: {abort_usd}",
                "daily_ceiling_credits: 10000",
                f"abort_threshold_credits: {abort_credits}",
                "cost_per_credit_usd: 0.0001",
                f"planned_request_reserve_usd: {reserve_usd}",
                "planned_request_reserve_credits: 10",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_budget_uses_strictest_config_environment_and_caller_values(tmp_path: Path) -> None:
    config = tmp_path / "budget.yml"
    write_budget(config)
    budget = resolve_openalex_budget(
        config,
        max_cost_usd="0.1",
        max_credits="1000",
        environ={"OPENALEX_MAX_COST_USD": "0.05", "OPENALEX_MAX_CREDITS": "500"},
    )
    assert budget.max_cost_usd == Decimal("0.05")
    assert budget.max_credits == Decimal("500")
    assert budget.reserve_error(cost_usd=Decimal("0.0491"), credits=Decimal("490"))
    assert budget.actual_error(cost_usd=Decimal("0.051"), credits=Decimal("501"))


def test_credit_unit_is_conservative_and_validates_config(tmp_path: Path) -> None:
    assert conservative_request_cost("0", "1", Decimal("0.0001")) == Decimal("0.0001")
    assert conservative_request_cost("0.001", "1", Decimal("0.0001")) == Decimal("0.001")
    assert conservative_request_cost(
        None, "1", Decimal("0.0001"), meta_cost_known=False
    ) == Decimal("0.0001")
    with pytest.raises(ValueError, match="credits"):
        conservative_request_cost(None, None, Decimal("0.0001"), meta_cost_known=False)
    config = tmp_path / "bad.yml"
    config.write_text("cost_per_credit_usd: -0.1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="cost_per_credit_usd"):
        resolve_openalex_budget(config, max_cost_usd=1, max_credits=1, environ={})
    config.write_text("cost_per_credit_usd: 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must be positive"):
        resolve_openalex_budget(config, max_cost_usd=1, max_credits=1, environ={})


def test_missing_budget_caps_require_bounded_config_env_or_caller(tmp_path: Path) -> None:
    empty = tmp_path / "empty.yml"
    empty.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="finite OpenAlex USD and credit limits"):
        resolve_openalex_budget(empty, environ={})
    with pytest.raises(ValueError, match="finite OpenAlex USD and credit limits"):
        resolve_openalex_budget(empty, max_cost_usd=0.1, environ={})
    budget = resolve_openalex_budget(
        empty,
        max_cost_usd=0.1,
        max_credits=100,
        environ={},
    )
    assert budget.max_cost_usd == Decimal("0.1")
    assert budget.max_credits == Decimal("100")


def test_daily_log_reconciles_credit_only_cost_across_reruns(tmp_path: Path) -> None:
    usage_log = tmp_path / "api_usage.jsonl"
    with ApiCostLogger("run-1", usage_log) as logger:
        logger.record_openalex_response(
            method="GET",
            url="https://api.openalex.org/works",
            status_code=200,
            headers={"X-RateLimit-Credits-Used": "2"},
            body={"meta": {"cost_usd": 0}},
        )
    costs, credits = daily_logged_usage(usage_log, cost_per_credit_usd=Decimal("0.0001"))
    assert costs == Decimal("0.0002")
    assert credits == Decimal("2.0")


def test_daily_usage_normalizes_timezone_and_ignores_other_event_rows(tmp_path: Path) -> None:
    path = tmp_path / "mixed.jsonl"
    request = {
        "record_type": "request",
        "source": "openalex",
        "run_id": "same-run",
        "timestamp_utc": "2026-11-10T01:00:00+02:00",
        "credits": 1,
        "credits_known": True,
        "cost_usd": 0,
        "cost_known": False,
    }
    benchmark_event = {
        "record_type": "benchmark_call",
        "run_id": "same-run",
        "call_index": 1,
        "credits": 1,
        "accounted_cost_usd": 0.0001,
    }
    summary = {
        "record_type": "run_summary",
        "run_id": "same-run",
        "credits_total": 1,
        "cost_usd_total": 0,
    }
    outside_utc_day = {
        **request,
        "timestamp_utc": "2026-11-09T23:30:00-02:00",
        "credits": 50,
        "cost_usd": 0.005,
        "cost_known": True,
    }
    path.write_text(
        "\n".join(json.dumps(row) for row in (request, benchmark_event, summary, outside_utc_day))
        + "\n",
        encoding="utf-8",
    )
    costs, credits = daily_logged_usage(
        path,
        cost_per_credit_usd=Decimal("0.0001"),
        day=date(2026, 11, 9),
    )
    assert costs == Decimal("0.0001")
    assert credits == Decimal(1)


def test_rate_limit_snapshot_is_preserved_but_excluded_from_request_subtotal(
    tmp_path: Path,
) -> None:
    path = tmp_path / "status-ledger.jsonl"
    historical_unknown = {
        "record_type": "request",
        "source": "openalex",
        "timestamp_utc": "2026-11-09T12:00:00Z",
        "url": "https://api.openalex.org/rate-limit",
        "credits": 0,
        "cost_usd": 0,
        "credits_known": False,
        "cost_known": False,
    }
    metered = {
        **historical_unknown,
        "url": "https://api.openalex.org/works?filter=x",
        "credits": 2,
        "credits_known": True,
        "cost_known": False,
    }
    path.write_text(
        "\n".join(json.dumps(row) for row in (historical_unknown, metered)) + "\n",
        encoding="utf-8",
    )
    costs, credits = daily_logged_usage(
        path,
        cost_per_credit_usd=Decimal("0.0001"),
        day=date(2026, 11, 9),
    )
    assert costs == Decimal("0.0002")
    assert credits == Decimal(2)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


@pytest.mark.parametrize(
    "timestamp",
    ["2026-11-09T12:00:00", "not-a-timestamp"],
)
def test_daily_usage_rejects_malformed_or_timezone_free_timestamp(
    tmp_path: Path, timestamp: str
) -> None:
    row = {
        "record_type": "request",
        "source": "openalex",
        "timestamp_utc": timestamp,
        "credits": 1,
        "cost_usd": 0.0001,
    }
    path = tmp_path / "bad-time.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="timestamp"):
        daily_logged_usage(path, cost_per_credit_usd=Decimal("0.0001"))


@pytest.mark.parametrize(
    "row",
    [
        {
            "record_type": "request",
            "source": "openalex",
            "timestamp_utc": "2026-11-09T12:00:00Z",
            "credits": "",
            "cost_usd": 0,
        },
        {
            "record_type": "request",
            "source": "openalex",
            "timestamp_utc": "2026-11-09T12:00:00Z",
            "credits": 1,
            "cost_known": True,
        },
    ],
)
def test_daily_usage_rejects_missing_or_empty_request_measurement(
    tmp_path: Path, row: dict[str, object]
) -> None:
    path = tmp_path / "missing-metric.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        daily_logged_usage(path, cost_per_credit_usd=Decimal("0.0001"), day=date(2026, 11, 9))


def test_ingest_reserves_before_each_request_and_reruns_count_prior_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENALEX_MAX_COST_USD", raising=False)
    monkeypatch.delenv("OPENALEX_MAX_CREDITS", raising=False)
    budget_path = tmp_path / "budget.yml"
    write_budget(budget_path, abort_usd="0.00015", abort_credits="20", reserve_usd="0.0001")
    paths = OpenAlexPaths(
        raw_dir=tmp_path / "raw",
        output_parquet=tmp_path / "works.parquet",
        high_water_mark=tmp_path / "water.json",
        usage_log=tmp_path / "api_usage.jsonl",
    )
    calls = 0

    def fake_request(url: str, *, logger: ApiCostLogger, **kwargs):
        nonlocal calls
        calls += 1
        body = {
            "meta": {"cost_usd": 0, "next_cursor": None},
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "publication_date": "2024-01-02",
                    "publication_year": 2024,
                }
            ],
        }
        logger.record_openalex_response(
            method="GET",
            url=url,
            status_code=200,
            headers={"X-RateLimit-Credits-Used": "1"},
            body=body,
        )
        return body

    monkeypatch.setattr(openalex, "_request_json", fake_request)
    run_args = {
        "config_path": "config/queries_v2.yml",
        "institution_ids": ["I1"],
        "paths": paths,
        "start_year": 2024,
        "end_year": 2024,
        "allow_candidate": True,
        "budget_path": budget_path,
    }
    openalex.ingest_live(**run_args)
    assert calls == 1
    with pytest.raises(OpenAlexBudgetError, match="reserve.*outputs were not advanced"):
        openalex.ingest_live(**run_args)
    assert calls == 1
    assert json.loads(paths.high_water_mark.read_text(encoding="utf-8"))["requests"] == 1


@pytest.mark.parametrize(
    ("cost", "credits", "error_match"),
    [
        (0.002, "1", "cost budget exceeded"),
        (0, "malformed", "credit usage"),
    ],
)
def test_ingest_budget_or_bad_credit_preserves_outputs_and_high_water(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cost: object,
    credits: str,
    error_match: str,
) -> None:
    monkeypatch.delenv("OPENALEX_MAX_COST_USD", raising=False)
    monkeypatch.delenv("OPENALEX_MAX_CREDITS", raising=False)
    budget_path = tmp_path / "budget.yml"
    write_budget(
        budget_path,
        abort_usd="0.0015",
        abort_credits="20",
        reserve_usd="0.001",
    )
    paths = OpenAlexPaths(
        raw_dir=tmp_path / "raw",
        output_parquet=tmp_path / "works.parquet",
        high_water_mark=tmp_path / "water.json",
        usage_log=tmp_path / "api_usage.jsonl",
    )
    paths.output_parquet.write_bytes(b"prior-output-sentinel")
    prior_high_water = {
        "schema_version": 1,
        "last_publication_date": "2023-12-31",
        "last_run_id": "prior-run",
    }
    paths.high_water_mark.write_text(json.dumps(prior_high_water), encoding="utf-8")

    def fake_request(url: str, *, logger: ApiCostLogger, **kwargs):
        body = {
            "meta": {"cost_usd": cost, "next_cursor": None},
            "results": [{"id": "https://openalex.org/W1", "publication_year": 2024}],
        }
        logger.record_openalex_response(
            method="GET",
            url=url,
            status_code=200,
            headers={"X-RateLimit-Credits-Used": credits},
            body=body,
        )
        return body

    monkeypatch.setattr(openalex, "_request_json", fake_request)
    run_args = {
        "config_path": "config/queries_v2.yml",
        "institution_ids": ["I1"],
        "paths": paths,
        "start_year": 2024,
        "end_year": 2024,
        "allow_candidate": True,
        "budget_path": budget_path,
        "run_id": "budget-stop-test",
    }
    with pytest.raises((OpenAlexBudgetError, ValueError), match=error_match):
        openalex.ingest_live(**run_args)
    assert paths.output_parquet.read_bytes() == b"prior-output-sentinel"
    assert json.loads(paths.high_water_mark.read_text(encoding="utf-8")) == prior_high_water
    assert not list(paths.raw_dir.glob("*.json"))


def test_http_500_without_credit_stops_before_retry_or_output_advancement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENALEX_MAX_COST_USD", raising=False)
    monkeypatch.delenv("OPENALEX_MAX_CREDITS", raising=False)
    monkeypatch.setenv("OPENALEX_API_KEY", "HTTP500_SECRET_CANARY")
    budget_path = tmp_path / "budget.yml"
    write_budget(budget_path)
    paths = OpenAlexPaths(
        raw_dir=tmp_path / "raw",
        output_parquet=tmp_path / "works.parquet",
        high_water_mark=tmp_path / "water.json",
        usage_log=tmp_path / "api_usage.jsonl",
    )
    paths.output_parquet.write_bytes(b"existing-output")
    prior_high_water = {"schema_version": 1, "last_run_id": "prior"}
    paths.high_water_mark.write_text(json.dumps(prior_high_water), encoding="utf-8")
    calls = 0

    class SuccessResponse:
        status = 200
        headers = {"X-RateLimit-Credits-Used": "1"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"meta":{"cost_usd":0},"results":[]}'

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            headers = Message()
            headers["Content-Type"] = "application/json"
            raise urllib.error.HTTPError(
                request.full_url,
                500,
                "server error",
                headers,
                io.BytesIO(b'{"meta":{"cost_usd":0}}'),
            )
        return SuccessResponse()

    monkeypatch.setattr(openalex.urllib.request, "urlopen", fake_urlopen)
    run_args = {
        "config_path": "config/queries_v2.yml",
        "institution_ids": ["I1"],
        "paths": paths,
        "start_year": 2024,
        "end_year": 2024,
        "allow_candidate": True,
        "budget_path": budget_path,
        "run_id": "http500-unknown-test",
    }
    with pytest.raises(OpenAlexUsageMetadataError, match="before retry") as error:
        openalex.ingest_live(**run_args)
    assert calls == 1
    assert "HTTP500_SECRET_CANARY" not in str(error.value)
    assert paths.output_parquet.read_bytes() == b"existing-output"
    assert json.loads(paths.high_water_mark.read_text(encoding="utf-8")) == prior_high_water
    rows = [json.loads(line) for line in paths.usage_log.read_text(encoding="utf-8").splitlines()]
    request = next(row for row in rows if row["record_type"] == "request")
    assert request["status_code"] == 500
    assert request["credits_known"] is False
    assert request["cost_known"] is True
    assert "HTTP500_SECRET_CANARY" not in paths.usage_log.read_text(encoding="utf-8")


def test_http_500_with_known_credits_retries_with_bounded_attempts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    class SuccessResponse:
        status = 200
        headers = {"X-RateLimit-Credits-Used": "1"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"meta":{"cost_usd":0.0001},"results":[]}'

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            headers = Message()
            headers["X-RateLimit-Credits-Used"] = "1"
            raise urllib.error.HTTPError(
                request.full_url,
                500,
                "server error",
                headers,
                io.BytesIO(b'{"meta":{}}'),
            )
        return SuccessResponse()

    monkeypatch.setattr(openalex.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(openalex.time, "sleep", lambda seconds: None)
    log = tmp_path / "known-retry.jsonl"
    with ApiCostLogger("known-retry", log) as logger:
        body = openalex._request_json(
            "https://api.openalex.org/works?filter=type%3Aarticle",
            logger=logger,
            attempts=2,
            timeout=1,
        )
        assert body["results"] == []
        assert calls == 2
        assert logger.request_count == 2
        assert logger.credits_total == Decimal(2)
        assert [row["cost_known"] for row in logger.request_metrics] == [False, True]


def test_http_429_without_credit_defers_as_rate_limit_without_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENALEX_MAX_COST_USD", raising=False)
    monkeypatch.delenv("OPENALEX_MAX_CREDITS", raising=False)
    budget_path = tmp_path / "budget.yml"
    write_budget(budget_path)
    paths = OpenAlexPaths(
        raw_dir=tmp_path / "raw",
        output_parquet=tmp_path / "works.parquet",
        high_water_mark=tmp_path / "water.json",
        usage_log=tmp_path / "api_usage.jsonl",
    )
    paths.output_parquet.write_bytes(b"existing-output")
    prior_high_water = {"schema_version": 1, "last_run_id": "prior"}
    paths.high_water_mark.write_text(json.dumps(prior_high_water), encoding="utf-8")
    calls = 0

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        headers = Message()
        headers["Retry-After"] = "60"
        raise urllib.error.HTTPError(
            request.full_url, 429, "Too Many Requests", headers, io.BytesIO(b"")
        )

    monkeypatch.setattr(openalex.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(openalex.OpenAlexRateLimitError) as error:
        openalex.ingest_live(
            config_path="config/queries_v2.yml",
            institution_ids=["I1"],
            paths=paths,
            start_year=2024,
            end_year=2024,
            allow_candidate=True,
            budget_path=budget_path,
            run_id="http429-unknown-test",
        )
    assert calls == 1
    assert error.value.retry_after == "60"
    assert paths.output_parquet.read_bytes() == b"existing-output"
    assert json.loads(paths.high_water_mark.read_text(encoding="utf-8")) == prior_high_water
    rows = [json.loads(line) for line in paths.usage_log.read_text(encoding="utf-8").splitlines()]
    request = next(row for row in rows if row["record_type"] == "request")
    assert request["status_code"] == 429 and request["credits_known"] is False


def test_burst_rate_limit_429_is_retried_not_deferred(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Boolean-heavy searches are limited to 5 requests/second; that 429 says wait 1s."""
    calls = 0
    burst = (
        b'{"message":"queries with more than 5 operators are limited to 5 requests per'
        b' second per client. Please wait 1s and retry"}'
    )

    class SuccessResponse:
        status = 200
        headers = {"X-RateLimit-Credits-Used": "1"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"meta":{"cost_usd":0.0001},"results":[]}'

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise urllib.error.HTTPError(
                request.full_url, 429, "Too Many Requests", Message(), io.BytesIO(burst)
            )
        return SuccessResponse()

    sleeps: list[float] = []
    monkeypatch.setattr(openalex.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(openalex.time, "sleep", sleeps.append)
    with ApiCostLogger("burst-retry", tmp_path / "burst.jsonl") as logger:
        body = openalex._request_json(
            "https://api.openalex.org/works?filter=type%3Aarticle", logger=logger, timeout=1
        )
    assert body["results"] == [] and calls == 2
    assert any(delay >= 1.0 for delay in sleeps)


def test_unknown_credit_429_is_charged_reserve_not_blocking(tmp_path: Path) -> None:
    path = tmp_path / "usage.jsonl"
    base = {
        "record_type": "request",
        "source": "openalex",
        "timestamp_utc": "2026-11-09T12:00:00Z",
        "url": "https://api.openalex.org/works?filter=x",
    }
    rejected = {**base, "status_code": 429, "credits": 0, "credits_known": False}
    rejected["cost_known"] = False
    metered = {**base, "status_code": 200, "credits": 10, "credits_known": True}
    metered["cost_known"] = True
    metered["cost_usd"] = 0.001
    path.write_text("\n".join(json.dumps(r) for r in (rejected, metered)) + "\n", "utf-8")
    costs, credits = daily_logged_usage(
        path, cost_per_credit_usd=Decimal("0.0001"), day=date(2026, 11, 9)
    )
    assert credits == Decimal(20) and costs == Decimal("0.002")
    unknown_500 = {**rejected, "status_code": 500}
    path.write_text(json.dumps(unknown_500) + "\n", "utf-8")
    with pytest.raises(ValueError, match="unknown credits"):
        daily_logged_usage(path, cost_per_credit_usd=Decimal("0.0001"), day=date(2026, 11, 9))
