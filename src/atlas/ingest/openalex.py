"""Incremental, resumable OpenAlex works ingestion.

The ingester keeps raw response snapshots out of Git, stores a slim raw-work
table for the next normalization stage, and advances its high-water mark only
after the merged Parquet output has been written successfully.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from atlas.query import (
    always_include_filters,
    load_query_config,
    openalex_filter,
    type_filters,
)
from atlas.util.budget import (
    conservative_request_cost,
    daily_logged_usage,
    resolve_openalex_budget,
)
from atlas.util.cost import ApiCostLogger, OpenAlexUsageMetadataError

OPENALEX_BASE = "https://api.openalex.org"
USER_AGENT = "CA-Plastics-Research-Atlas/0.1 (S2.1 works ingester; contact via GitHub)"
MAX_INSTITUTION_IDS_PER_REQUEST = 100
DEFAULT_PER_PAGE = 100
HIGH_WATER_SCHEMA_VERSION = 1
RAW_SCHEMA = pa.schema(
    [
        ("openalex_id", pa.string()),
        ("updated_date", pa.string()),
        ("publication_date", pa.string()),
        ("publication_year", pa.int64()),
        ("raw_json", pa.string()),
        ("source_run_id", pa.string()),
        ("fetched_at_utc", pa.string()),
    ]
)


class OpenAlexRateLimitError(RuntimeError):
    """A run should stop and retry on a later scheduled invocation."""

    status_code = 429

    def __init__(self, message: str, *, retry_after: str | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class OpenAlexBudgetError(RuntimeError):
    """The configured per-run credit or dollar ceiling was reached."""

    status_code = 429


@dataclass(frozen=True)
class OpenAlexPaths:
    """Filesystem paths for the S2.1 state and generated outputs."""

    raw_dir: Path = Path("data/raw/openalex_works")
    output_parquet: Path = Path("data/interim/works_raw.parquet")
    high_water_mark: Path = Path("data/interim/openalex_works_high_water_mark.json")
    usage_log: Path = Path("data/logs/api_usage.jsonl")


def load_openalex_key(path: str | Path = ".env") -> None:
    """Load the local OpenAlex key without printing or storing its value."""

    if os.environ.get("OPENALEX_API_KEY"):
        return
    dotenv = Path(path)
    if not dotenv.exists():
        return
    for line in dotenv.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        if separator and name.strip() in {"OPENALEX_API_KEY", "OPEN_ALEX_API_KEY"}:
            cleaned = value.strip().strip("'\"")
            if cleaned:
                os.environ["OPENALEX_API_KEY"] = cleaned
                return


def compact_openalex_id(value: object) -> str:
    """Return the stable OpenAlex work identifier without its URL prefix."""

    text = str(value or "").rstrip("/")
    return text.rsplit("/", 1)[-1] if text else ""


def chunks(
    values: Sequence[str], size: int = MAX_INSTITUTION_IDS_PER_REQUEST
) -> Iterable[list[str]]:
    """Yield bounded institution-ID batches accepted by OpenAlex."""

    if size < 1 or size > MAX_INSTITUTION_IDS_PER_REQUEST:
        raise ValueError("institution batch size must be between 1 and 100")
    for start in range(0, len(values), size):
        yield list(values[start : start + size])


def load_institution_ids(path: str | Path = "data/processed/institutions.parquet") -> list[str]:
    """Read and validate OpenAlex IDs from the committed CA registry."""

    table = pq.read_table(path, columns=["openalex_id"])
    ids = sorted(
        {
            compact_openalex_id(value)
            for value in table.column("openalex_id").to_pylist()
            if compact_openalex_id(value)
        }
    )
    if not ids:
        raise ValueError(f"no OpenAlex institution IDs found in {path}")
    return ids


def _date_filter(name: str, value: str) -> str:
    try:
        date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO date, got {value!r}") from error
    return f"{name}:{value}"


def build_works_url(
    config: Mapping[str, Any],
    institution_ids: Sequence[str],
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    updated_since: str | None = None,
    cursor: str = "*",
    per_page: int = DEFAULT_PER_PAGE,
    scope_filter: str | None = None,
) -> str:
    """Build one bounded works request for a date window or update cursor.

    ``scope_filter`` (an ``always_include`` entry) replaces both the term search and
    the institution filter; type exclusions and date windows still apply.
    """

    if scope_filter is not None and institution_ids:
        raise ValueError("scope_filter requests take no institution IDs")
    if scope_filter is None and not institution_ids:
        raise ValueError("at least one institution ID is required")
    if len(institution_ids) > MAX_INSTITUTION_IDS_PER_REQUEST:
        raise ValueError("OpenAlex accepts at most 100 institution IDs per request")
    if start_date and updated_since:
        raise ValueError("choose publication-date or updated-since mode, not both")
    if end_date and not start_date:
        raise ValueError("end_date requires start_date")
    if not 1 <= per_page <= 100:
        raise ValueError("per_page must be between 1 and 100")

    if scope_filter is not None:
        filters = [scope_filter, *type_filters(config)]
    else:
        filters = [
            openalex_filter(config),
            "institutions.id:" + "|".join(institution_ids),
            *type_filters(config),
        ]
    if start_date:
        filters.append(_date_filter("from_publication_date", start_date))
    if end_date:
        filters.append(_date_filter("to_publication_date", end_date))
    if updated_since:
        filters.append(_date_filter("from_updated_date", updated_since))
    params = {"filter": ",".join(filters), "per-page": per_page, "cursor": cursor}
    return f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"


MIN_REQUEST_INTERVAL_SECONDS = 0.25
_last_request_at = 0.0


def _throttle() -> None:
    """Keep below OpenAlex's 5 requests/second limit for boolean-heavy searches."""
    global _last_request_at
    wait = _last_request_at + MIN_REQUEST_INTERVAL_SECONDS - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _is_burst_limit(message: str) -> bool:
    text = message.lower()
    return "per second" in text or "wait 1s" in text


def _retry_delay(retry_after: object, attempt: int) -> float:
    try:
        return min(max(float(str(retry_after)), 1.0), 30.0)
    except (TypeError, ValueError):
        return float(2**attempt)


def _request_json(
    url: str,
    *,
    logger: ApiCostLogger,
    attempts: int = 4,
    timeout: int = 60,
) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        request.add_header("Authorization", f"Bearer {key}")
    for attempt in range(attempts):
        _throttle()
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.load(response)
                headers = dict(response.headers.items())
                status = response.status
            if not isinstance(body, dict):
                raise ValueError("OpenAlex response must be a JSON object")
            logger.record_openalex_response(
                method="GET", url=url, status_code=status, headers=headers, body=body
            )
            return body
        except urllib.error.HTTPError as error:
            headers = dict(error.headers.items())
            try:
                body = json.loads(error.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                body = {}
            if not isinstance(body, dict):
                body = {}
            try:
                logger.record_openalex_response(
                    method="GET", url=url, status_code=error.code, headers=headers, body=body
                )
            except OpenAlexUsageMetadataError:
                # A rejected 429 carries no credit header (seen 2026-11-10). The row is
                # logged; the 429 below already stops the run as deferred, unretried.
                if error.code != 429:
                    raise
            message = str(body.get("message") or body.get("error") or "request rejected")
            if error.code in {400, 401, 403, 404}:
                raise RuntimeError(f"OpenAlex returned HTTP {error.code}: {message}") from error
            if error.code == 429 and _is_burst_limit(message) and attempt + 1 < attempts:
                # Per-second limit for boolean-heavy searches (5 req/s on the free plan,
                # seen 2026-11-10): wait and retry instead of deferring the whole run.
                time.sleep(_retry_delay(headers.get("Retry-After"), attempt))
                continue
            if error.code == 429:
                raise OpenAlexRateLimitError(
                    f"OpenAlex returned HTTP 429: {message}",
                    retry_after=str(headers.get("Retry-After"))
                    if headers.get("Retry-After") is not None
                    else None,
                ) from error
            if attempt + 1 == attempts:
                raise RuntimeError(
                    f"OpenAlex request failed after {attempts} attempts: {message}"
                ) from error
            time.sleep(2**attempt)
        except OpenAlexUsageMetadataError:
            raise
        except (OSError, ValueError) as error:
            if attempt + 1 == attempts:
                raise RuntimeError(f"OpenAlex request failed after {attempts} attempts") from error
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def _snapshot_path(raw_dir: Path, run_id: str, request_number: int) -> Path:
    return raw_dir / f"{run_id}_{request_number:06d}.json"


def _write_snapshot(
    path: Path,
    *,
    run_id: str,
    request_number: int,
    url: str,
    body: Mapping[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "request_number": request_number,
        "requested_url": url,
        "response": body,
    }
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _row_from_work(work: Mapping[str, Any], *, run_id: str, fetched_at_utc: str) -> dict[str, Any]:
    work_id = compact_openalex_id(work.get("id"))
    if not work_id:
        raise ValueError("OpenAlex work is missing id")
    publication_date = work.get("publication_date")
    if publication_date is None and work.get("publication_year"):
        publication_date = f"{int(work['publication_year']):04d}-01-01"
    publication_year = work.get("publication_year")
    return {
        "openalex_id": work_id,
        "updated_date": str(work.get("updated_date") or ""),
        "publication_date": str(publication_date or ""),
        "publication_year": int(publication_year) if publication_year is not None else None,
        "raw_json": json.dumps(work, sort_keys=True, separators=(",", ":")),
        "source_run_id": run_id,
        "fetched_at_utc": fetched_at_utc,
    }


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return pq.read_table(path).to_pylist()


def _merge_rows(
    existing: Iterable[Mapping[str, Any]], new: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in [*existing, *new]:
        key = compact_openalex_id(row.get("openalex_id"))
        if key:
            merged[key] = {
                "openalex_id": key,
                "updated_date": str(row.get("updated_date") or ""),
                "publication_date": str(row.get("publication_date") or ""),
                "publication_year": (
                    int(row["publication_year"])
                    if row.get("publication_year") is not None
                    else None
                ),
                "raw_json": str(row.get("raw_json") or "{}"),
                "source_run_id": str(row.get("source_run_id") or ""),
                "fetched_at_utc": str(row.get("fetched_at_utc") or ""),
            }
    return [merged[key] for key in sorted(merged)]


def _atomic_write_parquet(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(list(rows), schema=RAW_SCHEMA)
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".parquet", prefix=f".{path.stem}-", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
    try:
        pq.write_table(table, temporary, compression="zstd")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", suffix=".json", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def read_high_water_mark(path: str | Path) -> dict[str, Any] | None:
    """Read a validated high-water mark, returning ``None`` before first run."""

    high_water_path = Path(path)
    if not high_water_path.exists():
        return None
    payload = json.loads(high_water_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != HIGH_WATER_SCHEMA_VERSION:
        raise ValueError(f"invalid high-water mark: {high_water_path}")
    return payload


def _max_date(rows: Iterable[Mapping[str, Any]], field: str) -> str | None:
    values = [str(row.get(field) or "")[:10] for row in rows]
    valid = []
    for value in values:
        try:
            date.fromisoformat(value)
        except ValueError:
            continue
        valid.append(value)
    return max(valid) if valid else None


def _run_id(prefix: str = "openalex-works") -> str:
    return f"{prefix}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"


def ingest_fixture(
    fixture_path: str | Path,
    *,
    paths: OpenAlexPaths = OpenAlexPaths(),
    run_id: str = "openalex-works-fixture",
) -> dict[str, Any]:
    """Ingest a small JSON fixture through the same merge/state path."""

    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    if not isinstance(fixture, list) or len(fixture) > 200:
        raise ValueError("S2.1 fixture must be a JSON list of at most 200 works")
    fetched_at = datetime.now(UTC).isoformat()
    rows = [_row_from_work(work, run_id=run_id, fetched_at_utc=fetched_at) for work in fixture]
    _write_snapshot(
        _snapshot_path(paths.raw_dir, run_id, 1),
        run_id=run_id,
        request_number=1,
        url=str(Path(fixture_path).resolve()),
        body={"meta": {"source": "fixture", "count": len(fixture)}, "results": fixture},
    )
    merged = _merge_rows(_read_rows(paths.output_parquet), rows)
    _atomic_write_parquet(paths.output_parquet, merged)
    max_publication_date = _max_date(rows, "publication_date")
    high_water = {
        "schema_version": HIGH_WATER_SCHEMA_VERSION,
        "mode": "fixture",
        "incremental_field": "publication_date",
        "last_publication_date": max_publication_date,
        "last_successful_run_utc": fetched_at,
        "last_run_id": run_id,
        "rows_written": len(merged),
    }
    _atomic_write_json(paths.high_water_mark, high_water)
    with ApiCostLogger(run_id, paths.usage_log) as logger:
        logger.record(
            source="openalex-fixture",
            method="READ",
            url=str(Path(fixture_path).resolve()),
            status_code=200,
        )
    return {
        "run_id": run_id,
        "fetched": len(rows),
        "rows_written": len(merged),
        "high_water": high_water,
    }


def ingest_live(
    *,
    config_path: str | Path = "config/queries.yml",
    institution_ids: Sequence[str],
    paths: OpenAlexPaths = OpenAlexPaths(),
    start_year: int | None = None,
    end_year: int | None = None,
    updated_since: str | None = None,
    per_page: int = DEFAULT_PER_PAGE,
    max_pages: int | None = None,
    allow_candidate: bool = False,
    max_credits: float | None = None,
    max_cost_usd: float | None = None,
    budget_path: str | Path = "config/budget.yml",
    run_id: str | None = None,
    replace_output: bool = False,
) -> dict[str, Any]:
    """Run a backfill or inclusive publication/update-date incremental pull.

    ``replace_output`` writes only this run's rows (a backfill after a query-version
    change) instead of merging them into rows fetched under an older query.
    """

    config = load_query_config(config_path)
    if config.get("status") != "active" and not allow_candidate:
        raise RuntimeError(
            "configured OpenAlex query is not active; obtain owner promotion or "
            "pass --allow-candidate"
        )
    if not institution_ids:
        raise ValueError("institution_ids must not be empty")
    if start_year is None and end_year is not None:
        raise ValueError("start_year is required when end_year is supplied")
    if start_year is not None and end_year is None:
        end_year = start_year
    if start_year is not None and end_year is not None and start_year > end_year:
        raise ValueError("start_year must not be after end_year")
    if updated_since and (start_year is not None or end_year is not None):
        raise ValueError("updated_since cannot be combined with a year backfill")
    budget = resolve_openalex_budget(
        budget_path, max_cost_usd=max_cost_usd, max_credits=max_credits
    )

    state = read_high_water_mark(paths.high_water_mark)
    if start_year is None and not updated_since and state:
        updated_since = state.get("last_publication_date")
        if not updated_since:
            raise ValueError("existing high-water mark has no publication date")
    if start_year is None and not updated_since:
        raise ValueError("first live run requires start_year/end_year or updated_since")

    actual_run_id = run_id or _run_id()
    fetched_at = datetime.now(UTC).isoformat()
    new_rows: list[dict[str, Any]] = []
    request_number = 0
    prior_day_cost, prior_day_credits = daily_logged_usage(
        paths.usage_log, cost_per_credit_usd=budget.cost_per_credit_usd
    )
    conservative_cost_total = Decimal(0)
    credits_total = Decimal(0)
    with ApiCostLogger(actual_run_id, paths.usage_log) as logger:
        units: list[tuple[list[str], str | None]] = [
            (batch, None) for batch in chunks(list(institution_ids))
        ]
        units += [([], scope) for scope in always_include_filters(config)]
        for batch, scope in units:
            windows: list[tuple[str | None, str | None]]
            if start_year is not None and end_year is not None:
                windows = [
                    (f"{year:04d}-01-01", f"{year:04d}-12-31")
                    for year in range(start_year, end_year + 1)
                ]
            else:
                windows = [(None, None)]
            for window_start, window_end in windows:
                cursor = "*"
                page_count = 0
                while cursor:
                    reserve_error = budget.reserve_error(
                        cost_usd=prior_day_cost + conservative_cost_total,
                        credits=prior_day_credits + credits_total,
                    )
                    if reserve_error:
                        raise OpenAlexBudgetError(f"{reserve_error}; outputs were not advanced")
                    url = build_works_url(
                        config,
                        batch,
                        scope_filter=scope,
                        start_date=window_start,
                        end_date=window_end,
                        updated_since=updated_since,
                        cursor=cursor,
                        per_page=per_page,
                    )
                    prior_request_count = len(logger.request_metrics)
                    body = _request_json(url, logger=logger)
                    attempts = logger.request_metrics[prior_request_count:]
                    if not attempts:
                        raise OpenAlexUsageMetadataError(
                            "OpenAlex request returned without accounting records"
                        )
                    response_credits = Decimal(0)
                    for attempt_record in attempts:
                        if attempt_record["credits_known"] is not True:
                            raise OpenAlexUsageMetadataError(
                                "OpenAlex request has unknown credit usage; "
                                "outputs were not advanced"
                            )
                        attempt_credits = Decimal(str(attempt_record["credits"]))
                        attempt_cost = conservative_request_cost(
                            attempt_record["cost_usd"] if attempt_record["cost_known"] else None,
                            attempt_credits,
                            budget.cost_per_credit_usd,
                            meta_cost_known=attempt_record["cost_known"] is True,
                        )
                        response_credits += attempt_credits
                        conservative_cost_total += attempt_cost
                    credits_total += response_credits
                    overrun_error = budget.actual_error(
                        cost_usd=prior_day_cost + conservative_cost_total,
                        credits=prior_day_credits + credits_total,
                    )
                    if overrun_error:
                        raise OpenAlexBudgetError(f"{overrun_error}; outputs were not advanced")
                    request_number += 1
                    _write_snapshot(
                        _snapshot_path(paths.raw_dir, actual_run_id, request_number),
                        run_id=actual_run_id,
                        request_number=request_number,
                        url=url,
                        body=body,
                    )
                    results = body.get("results")
                    if not isinstance(results, list):
                        raise ValueError("OpenAlex response results must be a list")
                    new_rows.extend(
                        _row_from_work(work, run_id=actual_run_id, fetched_at_utc=fetched_at)
                        for work in results
                        if isinstance(work, Mapping)
                    )
                    page_count += 1
                    if max_pages is not None and page_count >= max_pages:
                        break
                    meta = body.get("meta")
                    cursor = meta.get("next_cursor") if isinstance(meta, Mapping) else None

        prior_rows = [] if replace_output else _read_rows(paths.output_parquet)
        merged = _merge_rows(prior_rows, new_rows)
        _atomic_write_parquet(paths.output_parquet, merged)
        high_water = {
            "schema_version": HIGH_WATER_SCHEMA_VERSION,
            "query_version": config["version"],
            "mode": "updated_since" if updated_since else "publication_date",
            "incremental_field": "updated_date" if updated_since else "publication_date",
            "last_publication_date": _max_date(new_rows, "publication_date")
            or (state or {}).get("last_publication_date"),
            "last_updated_date": _max_date(new_rows, "updated_date")
            or (state or {}).get("last_updated_date"),
            "last_successful_run_utc": fetched_at,
            "last_run_id": actual_run_id,
            "requests": request_number,
            "fetched": len(new_rows),
            "rows_written": len(merged),
        }
        _atomic_write_json(paths.high_water_mark, high_water)
    return {
        "run_id": actual_run_id,
        "fetched": len(new_rows),
        "rows_written": len(merged),
        "requests": request_number,
        "accounted_cost_usd": float(conservative_cost_total),
        "credits": float(credits_total),
        "high_water": high_water,
    }
