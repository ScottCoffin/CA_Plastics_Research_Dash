"""Offline-by-default, bounded OpenAlex cost and latency benchmark."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from atlas.util.budget import (
    OpenAlexBudget,
    conservative_request_cost,
    daily_logged_usage,
    resolve_openalex_budget,
)
from atlas.util.cost import ApiCostLogger, OpenAlexUsageMetadataError

BASE = "https://api.openalex.org"
REPETITIONS = 20
MAX_TIMEOUT = 30
MAX_DURATION = 3600
ZERO_CREDIT_ACK = "I acknowledge that this benchmark is allowed to use zero paid credits."


def benchmark_plan() -> list[tuple[str, str]]:
    """Return the fixed five-endpoint, twenty-repetition plan."""
    params = urllib.parse.urlencode({"filter": "type:article", "per-page": 1})
    search_params = urllib.parse.urlencode(
        {"search": "plastic", "filter": "type:article", "per-page": 1}
    )
    grouped_params = urllib.parse.urlencode(
        {"filter": "type:article", "group_by": "publication_year"}
    )
    page_params = urllib.parse.urlencode({"filter": "type:article", "per-page": 200})
    endpoints = {
        "filter_only_list": f"{BASE}/works?{params}",
        "search_filter_count": f"{BASE}/works?{search_params}",
        "group_by": f"{BASE}/works?{grouped_params}",
        "singleton": f"{BASE}/W2741809807",
        "page_200": f"{BASE}/works?{page_params}",
    }
    return [(name, url) for name, url in endpoints.items() for _ in range(REPETITIONS)]


def _request(url: str, timeout: int) -> tuple[int, Mapping[str, Any], Mapping[str, object]]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "CA-Plastics-OpenAlex-cost-benchmark/1.0"}
    )
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        request.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
            if not isinstance(body, dict):
                raise ValueError("OpenAlex response must be a JSON object")
            return response.status, body, dict(response.headers.items())
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            body = {}
        return error.code, body if isinstance(body, dict) else {}, dict(error.headers.items())


def run_benchmark(
    *,
    request_fn: Callable[
        [str, int], tuple[int, Mapping[str, Any], Mapping[str, object]]
    ] = _request,
    timeout: int = 15,
    max_duration: int = 1800,
    max_cost_usd: float | None = None,
    max_credits: float | None = None,
    log_path: str | Path,
    clock: Callable[[], float] = time.monotonic,
    budget: OpenAlexBudget | None = None,
) -> dict[str, Any]:
    """Run sequentially; abort immediately at the explicit cost or time limit."""
    if not 1 <= timeout <= MAX_TIMEOUT:
        raise ValueError(f"timeout must be between 1 and {MAX_TIMEOUT} seconds")
    if not 1 <= max_duration <= MAX_DURATION:
        raise ValueError(f"max_duration must be between 1 and {MAX_DURATION} seconds")
    budget = budget or resolve_openalex_budget(max_cost_usd=max_cost_usd, max_credits=max_credits)
    effective_cost_limit = budget.max_cost_usd
    effective_credit_limit = budget.max_credits
    if effective_cost_limit is None:
        raise ValueError(
            "a positive maximum cost must be provided by config, environment, or caller"
        )
    if effective_credit_limit is None:
        raise ValueError("a finite maximum credit limit is required for a live benchmark")
    if budget.cost_per_credit_usd <= 0:
        raise ValueError("cost_per_credit_usd must be positive")
    if not math.isfinite(float(effective_cost_limit)) or effective_cost_limit <= 0:
        raise ValueError("max_cost_usd must be positive")
    started = clock()
    plan = benchmark_plan()
    planned_calls = len(plan)
    totals: dict[str, dict[str, Any]] = {}
    conservative_cost_total = budget.cost_per_credit_usd * 0
    credits_total = budget.reserve_credits * 0
    prior_day_cost, prior_day_credits = daily_logged_usage(
        log_path, cost_per_credit_usd=budget.cost_per_credit_usd
    )
    run_id = "openalex-bench-" + uuid.uuid4().hex[:12]
    with ApiCostLogger(run_id, log_path) as logger:
        for call_index, (endpoint, url) in enumerate(plan, start=1):
            if clock() - started >= max_duration:
                _append_failure(
                    log_path,
                    run_id=run_id,
                    endpoint=endpoint,
                    call_index=call_index,
                    failure_category="duration_limit",
                )
                raise RuntimeError("benchmark duration limit reached")
            reserve_error = budget.reserve_error(
                cost_usd=prior_day_cost + conservative_cost_total,
                credits=prior_day_credits + credits_total,
            )
            if reserve_error:
                _append_failure(
                    log_path,
                    run_id=run_id,
                    endpoint=endpoint,
                    call_index=call_index,
                    failure_category="budget_preflight",
                )
                raise RuntimeError(reserve_error)
            before = clock()
            try:
                status, body, headers = request_fn(url, timeout)
            except (TimeoutError, urllib.error.URLError, OSError) as error:
                latency_ms = round((clock() - before) * 1000, 3)
                category = "transport_timeout" if _is_timeout(error) else "transport_error"
                _append_failure(
                    log_path,
                    run_id=run_id,
                    endpoint=endpoint,
                    call_index=call_index,
                    failure_category=category,
                    latency_ms=latency_ms,
                )
                raise RuntimeError(
                    f"benchmark stopped at call {call_index}/{planned_calls} "
                    f"({endpoint}): {category}; "
                    "see sanitized usage log"
                ) from None
            latency_ms = round((clock() - before) * 1000, 3)
            try:
                logger.record_openalex_response(
                    method="GET", url=url, status_code=status, headers=headers, body=body
                )
            except OpenAlexUsageMetadataError:
                _append_failure(
                    log_path,
                    run_id=run_id,
                    endpoint=endpoint,
                    call_index=call_index,
                    failure_category="accounting_metadata_missing",
                    status_code=status,
                    latency_ms=latency_ms,
                )
                raise RuntimeError(
                    f"benchmark stopped at call {call_index}/{planned_calls} ({endpoint}): "
                    "accounting_metadata_missing; see sanitized usage log"
                ) from None
            credit_header = next(
                (v for k, v in headers.items() if k.casefold() == "x-ratelimit-credits-used"),
                None,
            )
            meta = body.get("meta", {})
            meta_cost = (
                meta.get("cost_usd") if isinstance(meta, Mapping) and "cost_usd" in meta else None
            )
            try:
                request_credits = Decimal(str(credit_header))
            except (InvalidOperation, TypeError, ValueError):
                request_credits = None
            if request_credits is None or not request_credits.is_finite() or request_credits < 0:
                _append_failure(
                    log_path,
                    run_id=run_id,
                    endpoint=endpoint,
                    call_index=call_index,
                    failure_category="accounting_metadata_missing",
                    status_code=status,
                    latency_ms=latency_ms,
                )
                raise RuntimeError(
                    f"benchmark stopped at call {call_index}/{planned_calls} ({endpoint}): "
                    "accounting_metadata_missing; see sanitized usage log"
                )
            meta_cost_known = True
            try:
                request_cost = conservative_request_cost(
                    meta_cost, request_credits, budget.cost_per_credit_usd
                )
            except ValueError:
                meta_cost_known = False
                request_cost = conservative_request_cost(
                    None,
                    request_credits,
                    budget.cost_per_credit_usd,
                    meta_cost_known=False,
                )
            _append_call(
                log_path,
                run_id=run_id,
                endpoint=endpoint,
                call_index=call_index,
                status_code=status,
                latency_ms=latency_ms,
                meta_cost_usd=meta_cost if meta_cost_known else None,
                meta_cost_known=meta_cost_known,
                credits=request_credits,
                accounted_cost_usd=request_cost,
            )
            conservative_cost_total += request_cost
            credits_total += request_credits
            if status >= 400:
                _append_failure(
                    log_path,
                    run_id=run_id,
                    endpoint=endpoint,
                    call_index=call_index,
                    failure_category="http_error",
                    status_code=status,
                    latency_ms=latency_ms,
                )
                raise RuntimeError(
                    f"benchmark stopped at call {call_index}/{planned_calls} ({endpoint}): "
                    f"HTTP {status}; see sanitized usage log"
                )
            group = totals.setdefault(
                endpoint,
                {
                    "requests": 0,
                    "latency_ms": [],
                    "credits": 0.0,
                    "cost_usd": 0.0,
                    "accounted_cost_usd": 0.0,
                },
            )
            group["requests"] += 1
            group["latency_ms"].append(round(latency_ms, 3))
            group["credits"] += float(request_credits)
            group["cost_usd"] += float(meta_cost or 0)
            group["accounted_cost_usd"] += float(request_cost)
            overrun_error = budget.actual_error(
                cost_usd=prior_day_cost + conservative_cost_total,
                credits=prior_day_credits + credits_total,
            )
            if overrun_error:
                raise RuntimeError(overrun_error)
    for group in totals.values():
        values = group.pop("latency_ms")
        group["latency_ms_mean"] = round(sum(values) / len(values), 3)
        group["latency_ms_max"] = max(values)
    return {
        "run_id": run_id,
        "planned_calls": planned_calls,
        "completed_calls": sum(g["requests"] for g in totals.values()),
        "credits_total": float(credits_total),
        "meta_cost_usd_total": float(logger.cost_usd_total),
        "accounted_cost_usd_total": float(conservative_cost_total),
        "results": totals,
    }


def _is_timeout(error: BaseException) -> bool:
    reason = error.reason if isinstance(error, urllib.error.URLError) else error
    return isinstance(reason, (TimeoutError,)) or getattr(reason, "errno", None) in {
        110,
        10060,
    }


def _append_failure(
    path: str | Path,
    *,
    run_id: str,
    endpoint: str,
    call_index: int,
    failure_category: str,
    status_code: int | None = None,
    latency_ms: float | None = None,
) -> None:
    record: dict[str, Any] = {
        "record_type": "benchmark_failure",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "endpoint": endpoint,
        "call_index": call_index,
        "failure_category": failure_category,
    }
    if status_code is not None:
        record["status_code"] = status_code
    if latency_ms is not None:
        record["latency_ms"] = latency_ms
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def _append_call(
    path: str | Path,
    *,
    run_id: str,
    endpoint: str,
    call_index: int,
    status_code: int,
    latency_ms: float,
    meta_cost_usd: object | None,
    meta_cost_known: bool,
    credits: object,
    accounted_cost_usd: object,
) -> None:
    record = {
        "record_type": "benchmark_call",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "endpoint": endpoint,
        "call_index": call_index,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "meta_cost_usd": float(meta_cost_usd) if meta_cost_known else None,
        "meta_cost_known": meta_cost_known,
        "credits": float(credits or 0),
        "accounted_cost_usd": float(accounted_cost_usd or 0),
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="execute the 100 OpenAlex requests")
    parser.add_argument(
        "--ack-zero-paid-credit-policy",
        action="store_true",
        help="acknowledge the zero-paid-credit policy",
    )
    parser.add_argument(
        "--preflight-proof",
        type=Path,
        help="path to externally verified account/budget evidence; contents are not read",
    )
    parser.add_argument(
        "--max-cost-usd", type=float, help="optional lower hard-stop threshold in USD"
    )
    parser.add_argument(
        "--max-credits", type=float, help="optional lower hard-stop threshold in credits"
    )
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--max-duration", type=int, default=1800)
    parser.add_argument("--log", type=Path, default=Path("data/logs/openalex_cost_benchmark.jsonl"))
    args = parser.parse_args(argv)
    if not args.live:
        print(
            json.dumps(
                {
                    "mode": "dry_run",
                    "planned_calls": 100,
                    "repetitions_per_endpoint": 20,
                    "endpoints": [n for n, _ in benchmark_plan()[::20]],
                    "live_requires": [
                        "--live",
                        "--ack-zero-paid-credit-policy",
                        "--preflight-proof PATH",
                        "--max-cost-usd USD",
                    ],
                },
                indent=2,
            )
        )
        return 0
    if not args.ack_zero_paid_credit_policy or not args.preflight_proof:
        parser.error("live mode requires --ack-zero-paid-credit-policy and --preflight-proof")
    if not args.preflight_proof.is_file():
        parser.error(
            "preflight proof path must identify an existing externally verified evidence file"
        )
    if not os.environ.get("OPENALEX_API_KEY"):
        from atlas.ingest.openalex import load_openalex_key

        load_openalex_key()
    if not os.environ.get("OPENALEX_API_KEY"):
        parser.error("OPENALEX_API_KEY must be configured in the environment")
    try:
        budget = resolve_openalex_budget(
            max_cost_usd=args.max_cost_usd, max_credits=args.max_credits
        )
        result = run_benchmark(
            timeout=args.timeout,
            max_duration=args.max_duration,
            max_cost_usd=float(budget.max_cost_usd) if budget.max_cost_usd is not None else None,
            max_credits=float(budget.max_credits) if budget.max_credits is not None else None,
            log_path=args.log,
            budget=budget,
        )
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as error:
        print(f"benchmark stopped: {type(error).__name__}: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
