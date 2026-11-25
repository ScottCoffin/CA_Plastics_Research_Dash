"""Budget-guarded, resumable raw fetch of the global plastics query (PLAT-4a).

Unpublished (owner 2026-11-18, A3-Q15). One active query from ``config/queries.yml``
with no institution, California or paid filter is cursor-paged per publication-year
slice into the ignored ``data/raw/openalex_global/``. Pages keep the full OpenAlex work
records (including ``ids``). Nothing here feeds the site or the CA works table; the
regional partition and labelling come in PLAT-4.

HTTP, credit accounting and the daily USD guard are the CA ingester's
(``atlas.ingest.openalex``, ``atlas.util.budget``, ``atlas.util.cost``).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import os
import tempfile
import urllib.error
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from atlas.ingest.openalex import (
    DEFAULT_PER_PAGE,
    OPENALEX_BASE,
    REJECTED_REQUEST_CREDITS,
    OpenAlexRateLimitError,
    _request_json,
)
from atlas.query import load_query_config, openalex_filter, type_filters
from atlas.util.budget import (
    OpenAlexBudget,
    conservative_request_cost,
    daily_logged_usage,
    resolve_openalex_budget,
)
from atlas.util.cost import ApiCostLogger, OpenAlexUsageMetadataError

STATE_SCHEMA_VERSION = 1
# Same backfill floor as scripts/run_daily_works.py (BACKFILL_START_YEAR).
GLOBAL_START_YEAR = 1950
# Owner (2026-11-18, PLAT-4a): stop the global fetch at USD 0.95 per UTC day. Passed as the
# caller cap to resolve_openalex_budget, so the strictest value wins over config and env.
DAILY_STOP_USD = 0.95
# Per-run credit cap default (about 200 boolean-search pages).
DEFAULT_MAX_CREDITS = 2000
# OpenAlex's maximum page size; atlas.ingest.openalex enforces the same limit.
GLOBAL_PER_PAGE = DEFAULT_PER_PAGE
DEFAULT_RAW_DIR = Path("data/raw/openalex_global")
DEFAULT_USAGE_LOG = Path("data/logs/api_usage.jsonl")
DEFAULT_CONFIG = Path("config/queries.yml")
DEFAULT_BUDGET = Path("config/budget.yml")


class StateMismatchError(RuntimeError):
    """A saved state does not match the active query, or no estimate was recorded yet."""


def query_identity(config: Mapping[str, Any]) -> dict[str, Any]:
    """The parts of a request that decide which works come back (a resume must match these)."""

    return {
        "schema": "openalex_global_query_v1",
        "endpoint": f"{OPENALEX_BASE}/works",
        "query_version": config["version"],
        "filter": openalex_filter(config),
        "type_filters": type_filters(config),
    }


def query_hash(config: Mapping[str, Any]) -> str:
    """SHA-256 of the canonical query identity; a changed query changes this value."""

    payload = json.dumps(query_identity(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_global_url(
    config: Mapping[str, Any],
    *,
    start_date: str,
    end_date: str,
    cursor: str = "*",
    per_page: int = GLOBAL_PER_PAGE,
) -> str:
    """One works request: the active query, its type exclusions and a publication-date window.

    No institution, California or raw-affiliation filter, and no paid filter
    (``from_updated_date`` and ``from_created_date`` are rejected by OpenAlex on the free plan).
    """

    date.fromisoformat(start_date)
    date.fromisoformat(end_date)
    if not 1 <= per_page <= GLOBAL_PER_PAGE:
        raise ValueError(f"per_page must be between 1 and {GLOBAL_PER_PAGE}")
    filters = [
        openalex_filter(config),
        *type_filters(config),
        f"from_publication_date:{start_date}",
        f"to_publication_date:{end_date}",
    ]
    params = {"filter": ",".join(filters), "per-page": per_page, "cursor": cursor}
    return f"{OPENALEX_BASE}/works?{urlencode(params)}"


def year_windows(start_year: int, end_year: int, today: date) -> list[dict[str, Any]]:
    """One publication-year slice per year, ending no later than yesterday (complete days only)."""

    if start_year > end_year:
        raise ValueError("start_year must not be after end_year")
    yesterday = today - timedelta(days=1)
    windows: list[dict[str, Any]] = []
    for year in range(start_year, end_year + 1):
        start = date(year, 1, 1)
        if start > yesterday:
            continue
        stop = min(date(year, 12, 31), yesterday)
        windows.append({"year": year, "from": start.isoformat(), "to": stop.isoformat()})
    if not windows:
        raise ValueError("no complete-day publication window in the requested years")
    return windows


def _daily_budget(budget_path: str | Path) -> OpenAlexBudget:
    return resolve_openalex_budget(budget_path, max_cost_usd=DAILY_STOP_USD)


def _accounted(
    logger: ApiCostLogger, start_index: int, cost_per_credit: Decimal
) -> tuple[Decimal, Decimal]:
    """Credits and conservative USD for every attempt logged since ``start_index``.

    Mirrors the CA ingester: a 429 without a credit header is charged the planned reserve.
    """

    credits = Decimal(0)
    cost = Decimal(0)
    for attempt in logger.request_metrics[start_index:]:
        if attempt["credits_known"] is not True and attempt.get("status_code") == 429:
            credits += REJECTED_REQUEST_CREDITS
            cost += REJECTED_REQUEST_CREDITS * cost_per_credit
            continue
        if attempt["credits_known"] is not True:
            raise OpenAlexUsageMetadataError(
                "OpenAlex request has unknown credit usage; stopping before saving the page"
            )
        attempt_credits = Decimal(str(attempt["credits"]))
        cost += conservative_request_cost(
            attempt["cost_usd"] if attempt["cost_known"] else None,
            attempt_credits,
            cost_per_credit,
            meta_cost_known=attempt["cost_known"] is True,
        )
        credits += attempt_credits
    return credits, cost


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=path.parent, prefix=f".{path.name}-", delete=False
    ) as stream:
        stream.write(data)
        temporary = Path(stream.name)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    _atomic_write_bytes(path, text.encode("utf-8"))


def _write_page(
    path: Path,
    *,
    header: Mapping[str, Any],
    works: Sequence[Mapping[str, Any]],
) -> None:
    """One gzip JSONL page: a header line, then one unmodified OpenAlex work per line."""

    lines = [json.dumps({"record_type": "page_header", **header}, sort_keys=True)]
    lines.extend(json.dumps(work, sort_keys=True, separators=(",", ":")) for work in works)
    data = gzip.compress(("\n".join(lines) + "\n").encode("utf-8"), mtime=0)
    _atomic_write_bytes(path, data)


NETWORK_ERROR_MESSAGE = (
    "OpenAlex could not be reached after retries; progress is saved, re-run to resume"
)


def _is_network_failure(error: BaseException) -> bool:
    """True for a transport failure (no HTTP response), e.g. DNS, refused or timed-out connection.

    ``_request_json`` wraps transport errors in a RuntimeError whose ``__cause__`` is the
    underlying OSError. HTTP errors (``HTTPError``, a URLError subclass) are excluded because
    they carry a status code and are handled as real failures.
    """

    cause = error.__cause__ if isinstance(error, RuntimeError) else error
    if cause is None or isinstance(cause, urllib.error.HTTPError):
        return False
    return isinstance(cause, urllib.error.URLError | TimeoutError | ConnectionError)


def _max_iso_date(current: str | None, values: Sequence[object]) -> str | None:
    best = current
    for value in values:
        if not isinstance(value, str):
            continue
        try:
            date.fromisoformat(value[:10])
        except ValueError:
            continue
        if best is None or value[:10] > best[:10]:
            best = value[:10]
    return best


def _run_id(prefix: str, now: datetime) -> str:
    return f"openalex-global-{prefix}-{now.strftime('%Y%m%dT%H%M%SZ')}"


def estimate_global(
    *,
    config_path: str | Path = DEFAULT_CONFIG,
    budget_path: str | Path = DEFAULT_BUDGET,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    usage_log: str | Path = DEFAULT_USAGE_LOG,
    start_year: int = GLOBAL_START_YEAR,
    end_year: int | None = None,
    per_page: int = GLOBAL_PER_PAGE,
    now: datetime | None = None,
) -> dict[str, Any]:
    """One count request (``per_page=1``) that records the expected works, pages and cost.

    Writes ``estimate.json`` under ``raw_dir``. Paging later refuses to start without it.
    """

    clock = now or datetime.now(UTC)
    config = load_query_config(config_path)
    windows = year_windows(start_year, end_year or clock.year, clock.date())
    span_start = windows[0]["from"]
    span_end = windows[-1]["to"]
    budget = _daily_budget(budget_path)
    prior_cost, prior_credits = daily_logged_usage(
        usage_log, cost_per_credit_usd=budget.cost_per_credit_usd
    )
    blocked = budget.reserve_error(cost_usd=prior_cost, credits=prior_credits)
    if blocked:
        return {"status": "deferred", "reason": "budget_exceeded", "message": blocked}
    url = build_global_url(config, start_date=span_start, end_date=span_end, per_page=1)
    with ApiCostLogger(_run_id("estimate", clock), usage_log) as logger:
        before = len(logger.request_metrics)
        body = _request_json(url, logger=logger)
        call_credits, call_cost = _accounted(logger, before, budget.cost_per_credit_usd)
    meta = body.get("meta")
    count = meta.get("count") if isinstance(meta, Mapping) else None
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("OpenAlex count response has no meta.count")
    pages_min = math.ceil(count / per_page)
    # Each year slice can end on a partial page and an empty year still costs one call.
    pages_max = pages_min + len(windows)
    credits_per_page = float(call_credits)
    credits_max = pages_max * credits_per_page
    usd_max = credits_max * float(budget.cost_per_credit_usd)
    result = {
        "estimated_utc": clock.isoformat(),
        "query_version": config["version"],
        "query_hash": query_hash(config),
        "span": [span_start, span_end],
        "slices": len(windows),
        "per_page": per_page,
        "works": count,
        "pages_min": pages_min,
        "pages_max": pages_max,
        "credits_per_page": credits_per_page,
        "credits_max": credits_max,
        "usd_max": round(usd_max, 4),
        "days_at_daily_cap": round(usd_max / DAILY_STOP_USD, 2),
        "count_call_credits": float(call_credits),
        "count_call_usd": float(call_cost),
    }
    _atomic_write_json(Path(raw_dir) / "estimate.json", result)
    return {"status": "estimated", **result}


def dry_run(
    *,
    config_path: str | Path = DEFAULT_CONFIG,
    start_year: int = GLOBAL_START_YEAR,
    end_year: int | None = None,
    per_page: int = GLOBAL_PER_PAGE,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Print the request URLs without any network call or file write."""

    clock = now or datetime.now(UTC)
    config = load_query_config(config_path)
    windows = year_windows(start_year, end_year or clock.year, clock.date())
    first = windows[0]
    return {
        "status": "dry_run",
        "query_hash": query_hash(config),
        "estimate_url": build_global_url(
            config, start_date=windows[0]["from"], end_date=windows[-1]["to"], per_page=1
        ),
        "first_page_url": build_global_url(
            config, start_date=first["from"], end_date=first["to"], per_page=per_page
        ),
    }


def _load_state(
    state_path: Path,
    *,
    config: Mapping[str, Any],
    qhash: str,
    per_page: int,
) -> dict[str, Any] | None:
    """Return the saved state to resume, or None when there is none to resume."""

    if not state_path.exists():
        return None
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise StateMismatchError(f"unreadable state file {state_path}; pass --restart") from error
    if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise StateMismatchError(f"unrecognised state file {state_path}; pass --restart")
    if state.get("query_hash") != qhash or state.get("query_version") != config["version"]:
        raise StateMismatchError(
            "saved state was made for a different query "
            f"({state.get('query_version')!r}); pass --restart to start over"
        )
    if state.get("per_page") != per_page:
        raise StateMismatchError("saved state used a different per_page; pass --restart")
    return state


def _archive_previous(raw_dir: Path, clock: datetime) -> None:
    """Move the old state and pages aside (nothing is deleted) before a restart."""

    stamp = clock.strftime("%Y%m%dT%H%M%SZ")
    state_path = raw_dir / "state.json"
    if state_path.exists():
        os.replace(state_path, raw_dir / f"state.restart-{stamp}.json")
    pages_dir = raw_dir / "pages"
    if pages_dir.exists():
        os.replace(pages_dir, raw_dir / f"pages.restart-{stamp}")


def _new_state(
    *, config: Mapping[str, Any], qhash: str, per_page: int, clock: datetime
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "query_version": config["version"],
        "query_hash": qhash,
        "per_page": per_page,
        "created_utc": clock.isoformat(),
        "slices": {},
        "pages_done": 0,
        "works_fetched": 0,
        "credits_total": 0.0,
        "credits_by_utc_day": {},
        "last_run": None,
    }


def _add_slices(state: dict[str, Any], windows: Sequence[Mapping[str, Any]]) -> None:
    """Add requested years not yet tracked. Existing slices keep their stored date window,
    so a cursor is never reused with a different filter (e.g. a new "yesterday" end date)."""

    for window in windows:
        key = str(window["year"])
        if key not in state["slices"]:
            state["slices"][key] = {
                "from": window["from"],
                "to": window["to"],
                "cursor": "*",
                "done": False,
                "pages": 0,
                "works": 0,
                "high_water_publication_date": None,
            }


def fetch_global(
    *,
    config_path: str | Path = DEFAULT_CONFIG,
    budget_path: str | Path = DEFAULT_BUDGET,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    usage_log: str | Path = DEFAULT_USAGE_LOG,
    start_year: int = GLOBAL_START_YEAR,
    end_year: int | None = None,
    per_page: int = GLOBAL_PER_PAGE,
    max_credits: float = DEFAULT_MAX_CREDITS,
    restart: bool = False,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Cursor-page the global query into ``raw_dir``, resuming from ``state.json``.

    Stops cleanly (status ``deferred``, progress saved) when the per-run credit cap or the
    daily USD guard would be exceeded, on a non-burst HTTP 429, or when OpenAlex cannot be
    reached (``network_error``). Re-running resumes at the saved cursor. Pages are written
    before the state that points at them. Other request failures are raised.
    """

    clock = now or datetime.now(UTC)
    raw = Path(raw_dir)
    state_path = raw / "state.json"
    pages_dir = raw / "pages"
    config = load_query_config(config_path)
    qhash = query_hash(config)
    windows = year_windows(start_year, end_year or clock.year, clock.date())
    if not (raw / "estimate.json").exists():
        raise StateMismatchError("no cost estimate recorded; run --estimate before paging")
    cap = Decimal(str(max_credits))
    if restart:
        _archive_previous(raw, clock)
    state = _load_state(state_path, config=config, qhash=qhash, per_page=per_page)
    if state is None:
        state = _new_state(config=config, qhash=qhash, per_page=per_page, clock=clock)
    _add_slices(state, windows)
    requested = [str(window["year"]) for window in windows]

    budget = _daily_budget(budget_path)
    cost_rate = budget.cost_per_credit_usd
    prior_cost, prior_credits = daily_logged_usage(usage_log, cost_per_credit_usd=cost_rate)
    run_id = _run_id("fetch", clock)
    run_cost = Decimal(0)
    run_credits = Decimal(0)
    pages_this_run = 0
    works_this_run = 0
    stop: tuple[str, str] | None = None
    day_key = clock.date().isoformat()

    with ApiCostLogger(run_id, usage_log) as logger:
        for key in requested:
            slice_state = state["slices"][key]
            while not slice_state["done"]:
                if run_credits + budget.reserve_credits > cap:
                    stop = ("run_credit_cap", "per-run credit cap reached")
                    break
                blocked = budget.reserve_error(
                    cost_usd=prior_cost + run_cost, credits=prior_credits + run_credits
                )
                if blocked:
                    stop = ("budget_exceeded", blocked)
                    break
                url = build_global_url(
                    config,
                    start_date=slice_state["from"],
                    end_date=slice_state["to"],
                    cursor=slice_state["cursor"],
                    per_page=per_page,
                )
                before = len(logger.request_metrics)
                try:
                    body = _request_json(url, logger=logger)
                except OpenAlexRateLimitError as error:
                    stop = ("rate_limited", str(error))
                    break
                except (RuntimeError, urllib.error.URLError) as error:
                    if not _is_network_failure(error):
                        raise
                    stop = ("network_error", NETWORK_ERROR_MESSAGE)
                    break
                credits, cost = _accounted(logger, before, cost_rate)
                run_credits += credits
                run_cost += cost
                results = body.get("results")
                if not isinstance(results, list):
                    raise ValueError("OpenAlex response results must be a list")
                works = [work for work in results if isinstance(work, Mapping)]
                page_number = slice_state["pages"] + 1
                meta = body.get("meta")
                next_cursor = meta.get("next_cursor") if isinstance(meta, Mapping) else None
                _write_page(
                    pages_dir / f"{key}_{page_number:05d}.jsonl.gz",
                    header={
                        "schema_version": STATE_SCHEMA_VERSION,
                        "query_version": config["version"],
                        "query_hash": qhash,
                        "slice_year": int(key),
                        "page_index": page_number,
                        "requested_url": url,
                        "run_id": run_id,
                        "fetched_utc": clock.isoformat(),
                        "meta": meta,
                    },
                    works=works,
                )
                # The page is on disk; only now advance the cursor that points past it.
                slice_state["pages"] = page_number
                slice_state["works"] += len(works)
                slice_state["cursor"] = next_cursor or ""
                slice_state["done"] = not next_cursor or not works
                slice_state["high_water_publication_date"] = _max_iso_date(
                    slice_state["high_water_publication_date"],
                    [work.get("publication_date") for work in works],
                )
                state["pages_done"] += 1
                state["works_fetched"] += len(works)
                state["credits_total"] = round(state["credits_total"] + float(credits), 4)
                by_day = state["credits_by_utc_day"]
                by_day[day_key] = round(by_day.get(day_key, 0.0) + float(credits), 4)
                pages_this_run += 1
                works_this_run += len(works)
                _atomic_write_json(state_path, state)
                overrun = budget.actual_error(
                    cost_usd=prior_cost + run_cost, credits=prior_credits + run_credits
                )
                if overrun:
                    stop = ("budget_exceeded", overrun)
                    break
            if stop:
                break

        complete = all(state["slices"][key]["done"] for key in requested)
        state["last_run"] = {
            "run_id": run_id,
            "finished_utc": datetime.now(UTC).isoformat(),
            "pages": pages_this_run,
            "works": works_this_run,
            "credits": float(run_credits),
            "stop_reason": None if complete or stop is None else stop[0],
        }
        _atomic_write_json(state_path, state)

    done_slices = sum(1 for key in requested if state["slices"][key]["done"])
    return {
        "status": "success" if complete else "deferred",
        "reason": None if complete or stop is None else stop[0],
        "message": stop[1] if stop else None,
        "run_id": run_id,
        "pages_this_run": pages_this_run,
        "works_this_run": works_this_run,
        "credits_this_run": float(run_credits),
        "usd_this_run": round(float(run_cost), 6),
        "pages_done": state["pages_done"],
        "works_fetched": state["works_fetched"],
        "slices_done": done_slices,
        "slices_total": len(requested),
        "state_path": str(state_path),
    }
