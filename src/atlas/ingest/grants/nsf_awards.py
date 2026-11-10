"""NSF Award Search ingester (S8.3).

Each fiscal year is fetched in two sweeps.  ``ca`` runs the keyword groups twice,
once with ``awardeeStateCode=CA`` and once with ``perfStateCode=CA``.  ``terms`` runs
the keyword groups alone, which also catches out-of-state recipients.  A sweep is one
unit of work and is applied only after every query of it was fetched.

The live API accepts one quoted phrase per keyword query.  Two quoted phrases joined
by ``OR`` silently return ``totalCount: 0``, so each multi-word phrase gets its own
query.  Single words are OR-joined without quotes in one query.  Verified facts and
the cost of this rule are recorded in ``docs/api_notes/nsf_awards.md``.

Provenance (which sweep and fiscal year reported each grant) lives in the state file,
not in the C3 row.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from atlas.ingest.grants.nih_reporter import (
    BACKFILL_YEARS,
    UnitResult,
    fiscal_years_for,
    merge_units,
    read_prior_rows,
    search_phrases,
)
from atlas.ingest.grants.normalize import normalize_grant, write_grants_parquet

SOURCE = "nsf_awards"
FUNDER = "NSF"
API_URL = "https://api.nsf.gov/services/v1/awards.json"
USER_AGENT = "ca-plastics-atlas/0.1 (research dashboard)"
PRINT_FIELDS = (
    "id,title,abstractText,piFirstName,piLastName,pdPIName,awardeeName,awardeeStateCode,"
    "perfStateCode,startDate,expDate,estimatedTotalAmt,fundsObligatedAmt,agency,"
    "fundProgramName,date"
)
# Verified: rpp 1000 and 3000 are accepted.  The ingester uses the smaller value.
PAGE_SIZE = 1000
# Observed: a broad unquoted query reports totalCount 10000.  Treated as a ceiling, so
# any unit reporting at least this many matches is deferred rather than truncated.
MAX_TOTAL = 10000
MIN_INTERVAL_SECONDS = 1.1
MAX_RETRIES = 3
BACKOFF_SECONDS = 2.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
STATE_VERSION = 1
SWEEP_FILTERS: dict[str, tuple[dict[str, str], ...]] = {
    "ca": ({"awardeeStateCode": "CA"}, {"perfStateCode": "CA"}),
    "terms": ({},),
}
SWEEPS: tuple[str, ...] = tuple(SWEEP_FILTERS)
_PLAIN_WORD = re.compile(r"[A-Za-z]+")
_US_DATE = "%m/%d/%Y"

Transport = Callable[[Mapping[str, Any]], tuple[int, str]]


class NsfAwardsError(RuntimeError):
    """Base class for ingest failures that defer the run."""


class BudgetExhausted(NsfAwardsError):
    """The request cap was reached.  Completed units are still applied."""


class NsfHTTPError(NsfAwardsError):
    """A non-retryable or retry-exhausted HTTP failure."""


class NsfResponseError(NsfAwardsError):
    """The API answered with a payload this module cannot use, including a 200 error."""


class CeilingExceeded(NsfAwardsError):
    """A query reports too many matches to read in full."""


def keyword_groups(core_terms: Sequence[str]) -> list[str]:
    """Return keyword queries, each with at most one quoted phrase.

    The first query holds every single-word phrase, OR-joined and unquoted.  Each
    multi-word or hyphenated phrase gets its own quoted query.
    """

    phrases = search_phrases(core_terms)
    for phrase in phrases:
        if '"' in phrase:
            raise ValueError(f"search phrase must not contain a double quote: {phrase!r}")
    singles = [phrase for phrase in phrases if _PLAIN_WORD.fullmatch(phrase)]
    multis = [phrase for phrase in phrases if not _PLAIN_WORD.fullmatch(phrase)]
    groups = [" OR ".join(singles)] if singles else []
    groups.extend(f'"{phrase}"' for phrase in multis)
    return groups


def requests_per_unit(groups: Sequence[str], sweep: str) -> int:
    """Return the first-page request count for one fiscal year and sweep."""

    return len(groups) * len(SWEEP_FILTERS[sweep])


def fiscal_window(fiscal_year: int) -> tuple[str, str]:
    """Return the mm/dd/yyyy window for an NSF fiscal year (1 October to 30 September)."""

    return f"10/01/{fiscal_year - 1}", f"09/30/{fiscal_year}"


def plan_units(
    mode: str, today: date, completed: Mapping[str, Any], backfill_years: int = BACKFILL_YEARS
) -> list[tuple[int, str]]:
    """Return ``(fiscal_year, sweep)`` units.  Backfill skips units already completed."""

    units: list[tuple[int, str]] = []
    for fiscal_year in fiscal_years_for(mode, today, backfill_years):
        for sweep in SWEEPS:
            if mode == "backfill" and f"{fiscal_year}:{sweep}" in completed:
                continue
            units.append((fiscal_year, sweep))
    return units


def build_params(
    *,
    keyword: str,
    fiscal_year: int,
    state_filter: Mapping[str, str],
    offset: int,
    page_size: int = PAGE_SIZE,
) -> dict[str, Any]:
    start, end = fiscal_window(fiscal_year)
    params: dict[str, Any] = {
        "keyword": keyword,
        "dateStart": start,
        "dateEnd": end,
        "offset": offset,
        "rpp": page_size,
        "printFields": PRINT_FIELDS,
    }
    params.update(state_filter)
    return params


def urllib_transport(params: Mapping[str, Any], *, timeout: float = 60.0) -> tuple[int, str]:
    """Default transport.  Only ``api.nsf.gov`` is contacted."""

    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")


class NsfClient:
    """Paced, budgeted GET client.  Every transport call counts toward the cap."""

    def __init__(
        self,
        transport: Transport,
        *,
        max_requests: int,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.transport = transport
        self.max_requests = max_requests
        self.sleep = sleep
        self.clock = clock
        self.requests = 0
        self._last: float | None = None

    def get(self, params: Mapping[str, Any]) -> dict[str, Any]:
        for attempt in range(MAX_RETRIES + 1):
            if self.requests >= self.max_requests:
                raise BudgetExhausted(f"max_requests={self.max_requests} reached")
            if self._last is not None:
                wait = MIN_INTERVAL_SECONDS - (self.clock() - self._last)
                if wait > 0:
                    self.sleep(wait)
            self._last = self.clock()
            self.requests += 1
            try:
                status, text = self.transport(params)
            except OSError as error:
                status, text = None, str(error)
            if status == 200:
                try:
                    payload = json.loads(text)
                except ValueError as error:
                    raise NsfResponseError("200 response is not JSON") from error
                if not isinstance(payload, dict):
                    raise NsfResponseError("200 response is not a JSON object")
                return payload
            retryable = status is None or status in RETRY_STATUSES
            if retryable and attempt < MAX_RETRIES:
                self.sleep(BACKOFF_SECONDS * (2**attempt))
                continue
            raise NsfHTTPError(f"HTTP {status}: {text[:200]}")
        raise NsfHTTPError("retries exhausted")  # pragma: no cover - loop always returns


def _response_body(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return ``payload["response"]``.  A 200 with a serviceNotification is an error."""

    body = payload.get("response")
    if not isinstance(body, Mapping):
        raise NsfResponseError("response object is missing")
    notes = body.get("serviceNotification")
    if notes:
        messages = [
            str(note.get("notificationMessage", "")) for note in notes if isinstance(note, Mapping)
        ]
        raise NsfResponseError(f"API error notification: {'; '.join(messages)[:200]}")
    return body


def _total(body: Mapping[str, Any]) -> int:
    meta = body.get("metadata")
    total = meta.get("totalCount") if isinstance(meta, Mapping) else None
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise NsfResponseError("metadata.totalCount is missing or not a count")
    return total


def fetch_unit(
    client: NsfClient,
    *,
    fiscal_year: int,
    sweep: str,
    groups: Sequence[str],
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Fetch every page of every query of one sweep for one fiscal year."""

    records: list[dict[str, Any]] = []
    for state_filter in SWEEP_FILTERS[sweep]:
        for keyword in groups:
            offset = 0
            while True:
                params = build_params(
                    keyword=keyword,
                    fiscal_year=fiscal_year,
                    state_filter=state_filter,
                    offset=offset,
                    page_size=page_size,
                )
                body = _response_body(client.get(params))
                total = _total(body)
                if total >= MAX_TOTAL:
                    raise CeilingExceeded(
                        f"{fiscal_year}:{sweep} query reports {total} records; "
                        f"ceiling is {MAX_TOTAL}"
                    )
                if total == 0:
                    break
                page = body.get("award")
                if not isinstance(page, list):
                    raise NsfResponseError("award is missing or not a list")
                records.extend(page)
                offset += len(page)
                if not page or offset >= total:
                    break
    return records


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _us_date(value: object) -> str | None:
    """NSF dates look like ``09/01/2026``.  Return ISO ``yyyy-mm-dd`` or None."""

    text = _text(value)
    if text is None:
        return None
    try:
        return datetime.strptime(text, _US_DATE).date().isoformat()
    except ValueError:
        return None


def _pi_name(record: Mapping[str, Any]) -> str | None:
    parts = [_text(record.get("piFirstName")), _text(record.get("piLastName"))]
    return " ".join(part for part in parts if part) or _text(record.get("pdPIName"))


def to_raw_grant(record: Mapping[str, Any]) -> dict[str, Any] | None:
    """Map one NSF award onto the ``normalize_grant`` input fields.

    The amount is ``estimatedTotalAmt``, the anticipated total award value.  It is not
    ``fundsObligatedAmt``, which is cumulative obligations to date.
    """

    award_id = _text(record.get("id"))
    if award_id is None:
        return None
    amount = _text(record.get("estimatedTotalAmt"))
    pi_name = _pi_name(record)
    return {
        "source_award_id": award_id,
        "title": record.get("title"),
        "abstract": record.get("abstractText"),
        "pi_names": [pi_name] if pi_name else [],
        "org": record.get("awardeeName"),
        "org_state": _text(record.get("awardeeStateCode")),
        "start": _us_date(record.get("startDate")),
        "end": _us_date(record.get("expDate")),
        "amount": amount,
        "currency": "USD" if amount is not None else None,
        "funder": FUNDER,
        "program": _text(record.get("fundProgramName")),
        "funder_chain": [FUNDER],
        "url": f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={award_id}",
    }


def normalize_records(
    records: Sequence[Mapping[str, Any]],
    *,
    query_config: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], int]:
    """Return rows keyed by ``grant_key`` (first occurrence wins) and the skip count."""

    rows: dict[str, dict[str, Any]] = {}
    skipped = 0
    for record in records:
        raw = to_raw_grant(record)
        if raw is None:
            skipped += 1
            continue
        try:
            row = normalize_grant(raw, source=SOURCE, query_config=query_config, taxonomy=taxonomy)
        except ValueError:
            skipped += 1
            continue
        rows.setdefault(row["grant_key"], row)
    return rows, skipped


def empty_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_VERSION,
        "search_groups": None,
        "completed": {},
        "provenance": {},
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_state()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != STATE_VERSION:
        raise ValueError(f"unsupported NSF awards state file: {path}")
    return payload


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.stem}-", suffix=".json"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def dry_run_plan(
    *,
    mode: str,
    today: date,
    query_config: Mapping[str, Any],
    state_path: Path,
    max_requests: int,
    page_size: int = PAGE_SIZE,
) -> dict[str, Any]:
    """Describe the planned first-page requests without contacting the API or writing."""

    groups = keyword_groups(list(query_config.get("core_terms") or []))
    state = load_state(state_path)
    completed = (state.get("completed") or {}) if state.get("search_groups") == groups else {}
    units = plan_units(mode, today, completed)
    requests = [
        build_params(
            keyword=keyword,
            fiscal_year=fiscal_year,
            state_filter=state_filter,
            offset=0,
            page_size=page_size,
        )
        | {"unit": f"{fiscal_year}:{sweep}"}
        for fiscal_year, sweep in units
        for state_filter in SWEEP_FILTERS[sweep]
        for keyword in groups
    ]
    return {
        "mode": mode,
        "fiscal_years": fiscal_years_for(mode, today),
        "units": len(units),
        "keyword_queries": len(groups),
        "max_requests": max_requests,
        "planned_requests_at_least": len(requests),
        "requests": requests[:max_requests],
    }


def run_ingest(
    *,
    mode: str,
    output: Path,
    state_path: Path,
    query_config: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
    transport: Transport,
    max_requests: int,
    today: date,
    now: datetime | None = None,
    page_size: int = PAGE_SIZE,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Fetch planned units and apply the completed ones.

    Status ``ok``: every planned unit completed.  ``partial``: the request cap stopped
    the run, and the completed units were applied (possibly none).  ``deferred``: an
    HTTP, response, or ceiling failure stopped the run, so nothing was written and
    prior output is preserved.
    """

    if mode not in {"backfill", "incremental"}:
        raise ValueError(f"unknown mode: {mode!r}")
    groups = keyword_groups(list(query_config.get("core_terms") or []))
    state = load_state(state_path)
    same_terms = state.get("search_groups") == groups
    completed: dict[str, str] = dict(state.get("completed") or {}) if same_terms else {}
    units = plan_units(mode, today, completed)
    client = NsfClient(transport, max_requests=max_requests, sleep=sleep, clock=clock)
    summary: dict[str, Any] = {
        "mode": mode,
        "status": "ok",
        "reason": "",
        "fiscal_years": fiscal_years_for(mode, today),
        "units_planned": len(units),
        "units_completed": 0,
        "skipped_invalid": 0,
        "requests": 0,
        "max_requests": max_requests,
        "rows_written": None,
    }
    results: list[UnitResult] = []
    try:
        for fiscal_year, sweep in units:
            records = fetch_unit(
                client, fiscal_year=fiscal_year, sweep=sweep, groups=groups, page_size=page_size
            )
            rows, skipped = normalize_records(records, query_config=query_config, taxonomy=taxonomy)
            results.append(UnitResult(f"{fiscal_year}:{sweep}", rows, skipped))
    except BudgetExhausted as error:
        summary["status"] = "partial"
        summary["reason"] = str(error)
    except NsfAwardsError as error:
        summary.update(status="deferred", reason=str(error), requests=client.requests)
        return summary

    summary["requests"] = client.requests
    summary["units_completed"] = len(results)
    summary["skipped_invalid"] = sum(unit.skipped for unit in results)
    if not results:
        return summary

    prior = read_prior_rows(output)
    rows, provenance = merge_units(prior, state.get("provenance") or {}, results)
    write_grants_parquet(rows, output)
    stamp = (now or datetime.now(UTC)).isoformat()
    for unit in results:
        completed[unit.tag] = stamp
    _write_json_atomic(
        state_path,
        {
            "schema_version": STATE_VERSION,
            "search_groups": groups,
            "completed": completed,
            "provenance": provenance,
            "last_run_utc": stamp,
            "last_run": {
                "mode": mode,
                "status": summary["status"],
                "requests": client.requests,
                "units_completed": len(results),
                "rows_written": len(rows),
            },
        },
    )
    summary["rows_written"] = len(rows)
    return summary
