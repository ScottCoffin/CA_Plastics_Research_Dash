from __future__ import annotations

import importlib.util
import json
from decimal import Decimal
from pathlib import Path

import pytest

from atlas.util.budget import OpenAlexBudget

SCRIPT = Path(__file__).parents[1] / "scripts" / "benchmark_openalex_costs.py"
SPEC = importlib.util.spec_from_file_location("benchmark_openalex_costs", SCRIPT)
assert SPEC and SPEC.loader
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


def test_plan_has_exactly_twenty_of_five_endpoint_types() -> None:
    plan = benchmark.benchmark_plan()
    assert len(plan) == 100
    assert [name for name, _ in plan[::20]] == [
        "filter_only_list",
        "search_filter_count",
        "group_by",
        "singleton",
        "page_200",
    ]
    assert all(sum(name == target for name, _ in plan) == 20 for target, _ in plan[::20])
    assert "per-page=200" in plan[-1][1]


def test_dry_run_never_calls_network(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("dry run attempted network access")

    monkeypatch.setattr(benchmark.urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(benchmark, "_request", forbidden)
    assert benchmark.main([]) == 0
    assert json.loads(capsys.readouterr().out)["planned_calls"] == 100


def test_live_requires_acknowledgement_and_preflight_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    with pytest.raises(SystemExit):
        benchmark.main(["--live"])
    proof = tmp_path / "external-proof.txt"
    proof.write_text("verified externally", encoding="utf-8")
    from atlas.ingest import openalex

    monkeypatch.setattr(openalex, "load_openalex_key", lambda path=".env": None)
    monkeypatch.setattr(
        benchmark,
        "run_benchmark",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("test attempted live run")),
    )
    with pytest.raises(SystemExit):
        benchmark.main(["--live", "--ack-zero-paid-credit-policy", "--preflight-proof", str(proof)])


def test_mock_run_captures_latency_cost(tmp_path: Path) -> None:
    calls: list[tuple[str, int]] = []

    def fake(url: str, timeout: int):
        calls.append((url, timeout))
        return 200, {"meta": {"cost_usd": "0.0001"}}, {"X-RateLimit-Credits-Used": "2"}

    class FakeClock:
        now = 0.0

        def __call__(self) -> float:
            return self.now

    fake_clock = FakeClock()

    def timed_fake(url: str, timeout: int):
        fake_clock.now += 0.012
        return fake(url, timeout)

    log = tmp_path / "usage.jsonl"
    result = benchmark.run_benchmark(
        request_fn=timed_fake, max_cost_usd=0.1, log_path=log, clock=fake_clock
    )
    assert len(calls) == result["completed_calls"] == 100
    assert all(timeout == 15 for _, timeout in calls)
    assert result["results"]["page_200"]["requests"] == 20
    assert result["results"]["page_200"]["credits"] == 40
    assert result["results"]["page_200"]["latency_ms_mean"] == 12
    assert result["accounted_cost_usd_total"] == pytest.approx(0.02)
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert records[-1]["record_type"] == "run_summary"
    assert records[-1]["cost_usd_total"] == pytest.approx(0.01)
    call_records = [record for record in records if record["record_type"] == "benchmark_call"]
    assert len(call_records) == 100
    assert call_records[0]["latency_ms"] == 12
    assert call_records[0]["accounted_cost_usd"] == pytest.approx(0.0002)
    assert all("api_key" not in row.get("url", "") for row in records)


def test_secret_canary_url_and_authorization_header_never_reach_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = "OPENALEX_SECRET_CANARY_94f1"
    observed_requests = []

    class Response:
        status = 200
        headers = {"X-RateLimit-Credits-Used": "0"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            return b'{"meta":{"cost_usd":0}}'

    def open_request(request, timeout):
        observed_requests.append(request)
        return Response()

    monkeypatch.setenv("OPENALEX_API_KEY", secret)
    monkeypatch.setattr(benchmark.urllib.request, "urlopen", open_request)
    monkeypatch.setattr(
        benchmark,
        "benchmark_plan",
        lambda: [("filter_only_list", f"{benchmark.BASE}/works?api_key={secret}")],
    )
    log = tmp_path / "canary.jsonl"
    result = benchmark.run_benchmark(request_fn=benchmark._request, max_cost_usd=0.02, log_path=log)
    log_text = log.read_text(encoding="utf-8")
    assert result["completed_calls"] == 1
    assert observed_requests[0].get_header("Authorization") == f"Bearer {secret}"
    assert secret not in log_text
    assert "%5BREDACTED%5D" in log_text


def test_run_rejects_unbounded_timeout_and_stops_at_cost_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timeout"):
        benchmark.run_benchmark(timeout=31, max_cost_usd=1, log_path=tmp_path / "x.jsonl")
    calls = 0

    def expensive(url: str, timeout: int):
        nonlocal calls
        calls += 1
        return (
            200,
            {"meta": {"cost_usd": "0.5"}},
            {"X-RateLimit-Credits-Used": "0"},
        )

    with pytest.raises(RuntimeError, match="cost limit"):
        benchmark.run_benchmark(
            request_fn=expensive,
            max_cost_usd=0.5,
            log_path=tmp_path / "y.jsonl",
            budget=OpenAlexBudget(
                Decimal("0.5"), Decimal("2500"), Decimal("0.0001"), Decimal("0.001"), Decimal("10")
            ),
        )
    assert calls == 1


def test_credit_threshold_and_daily_rerun_history_are_enforced(tmp_path: Path) -> None:
    calls = 0

    def credit_cost(url: str, timeout: int):
        nonlocal calls
        calls += 1
        return 200, {"meta": {"cost_usd": 0}}, {"X-RateLimit-Credits-Used": "1"}

    log = tmp_path / "usage.jsonl"
    with pytest.raises(RuntimeError, match="credit limit"):
        benchmark.run_benchmark(
            request_fn=credit_cost,
            max_cost_usd=1,
            max_credits=0.5,
            log_path=log,
            budget=OpenAlexBudget(
                Decimal("1"), Decimal("0.5"), Decimal("0.0001"), Decimal("0.001"), Decimal("1")
            ),
        )
    assert calls == 0

    with pytest.raises(RuntimeError, match="credit limit"):
        benchmark.run_benchmark(
            request_fn=credit_cost,
            max_cost_usd=1,
            max_credits=1,
            log_path=log,
            budget=OpenAlexBudget(
                Decimal("1"), Decimal("1"), Decimal("0.0001"), Decimal("0"), Decimal("1")
            ),
        )
    assert calls == 1


@pytest.mark.parametrize(
    ("failure", "category", "status"),
    [
        (lambda: TimeoutError("private timeout detail"), "transport_timeout", None),
        (
            lambda: (429, {"meta": {"cost_usd": 0.002}}, {"X-RateLimit-Credits-Used": "3"}),
            "http_error",
            429,
        ),
    ],
)
def test_failed_call_is_sanitized_and_has_no_invented_cost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure,
    category: str,
    status: int | None,
) -> None:
    secret = "FAILURE_SECRET_CANARY"
    monkeypatch.setattr(
        benchmark,
        "benchmark_plan",
        lambda: [("filter_only_list", f"{benchmark.BASE}/works?api_key={secret}")],
    )
    calls = 0

    def request_fn(url: str, timeout: int):
        nonlocal calls
        calls += 1
        result = failure()
        if isinstance(result, BaseException):
            raise result
        return result

    log = tmp_path / f"{category}.jsonl"
    with pytest.raises(RuntimeError, match="call 1/1"):
        benchmark.run_benchmark(request_fn=request_fn, max_cost_usd=0.25, log_path=log)
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    failure_record = next(
        record for record in records if record["record_type"] == "benchmark_failure"
    )
    assert failure_record["endpoint"] == "filter_only_list"
    assert failure_record["call_index"] == 1
    assert failure_record["failure_category"] == category
    if status is not None:
        assert failure_record["status_code"] == status
        request_record = next(record for record in records if record["record_type"] == "request")
        assert request_record["cost_usd"] == 0.002
    else:
        assert "status_code" not in failure_record
        assert not any(record["record_type"] == "request" for record in records)
    assert "cost_usd" not in failure_record
    assert secret not in log.read_text(encoding="utf-8")
    assert "private timeout detail" not in log.read_text(encoding="utf-8")
    assert calls == 1


@pytest.mark.parametrize("credits", [None, "", "not-a-number"])
def test_bad_credit_evidence_stops_and_records_no_fabricated_cost(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    credits: str | None,
) -> None:
    monkeypatch.setattr(
        benchmark,
        "benchmark_plan",
        lambda: [("filter_only_list", f"{benchmark.BASE}/works?api_key=SECRET_CANARY")],
    )
    headers = {} if credits is None else {"X-RateLimit-Credits-Used": credits}
    log = tmp_path / "bad-credit.jsonl"
    with pytest.raises(RuntimeError, match="accounting_metadata_missing"):
        benchmark.run_benchmark(
            request_fn=lambda url, timeout: (200, {"meta": {"cost_usd": 0}}, headers),
            max_cost_usd=0.25,
            max_credits=2500,
            log_path=log,
        )
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    failure = next(record for record in records if record["record_type"] == "benchmark_failure")
    request = next(record for record in records if record["record_type"] == "request")
    assert failure["endpoint"] == "filter_only_list"
    assert failure["failure_category"] == "accounting_metadata_missing"
    assert request["credits_known"] is False
    assert request["cost_usd"] == 0
    assert not any(record["record_type"] == "benchmark_call" for record in records)
    assert "SECRET_CANARY" not in log.read_text(encoding="utf-8")


def test_missing_cost_uses_explicit_credit_based_estimate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        benchmark,
        "benchmark_plan",
        lambda: [("singleton", f"{benchmark.BASE}/works/W1")],
    )
    log = tmp_path / "cost-unknown.jsonl"
    result = benchmark.run_benchmark(
        request_fn=lambda url, timeout: (
            200,
            {"meta": {}},
            {"X-RateLimit-Credits-Used": "1"},
        ),
        max_cost_usd=0.25,
        max_credits=2500,
        log_path=log,
    )
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    call = next(record for record in records if record["record_type"] == "benchmark_call")
    assert call["meta_cost_known"] is False
    assert call["meta_cost_usd"] is None
    assert call["accounted_cost_usd"] == pytest.approx(0.0001)
    assert result["accounted_cost_usd_total"] == pytest.approx(0.0001)
