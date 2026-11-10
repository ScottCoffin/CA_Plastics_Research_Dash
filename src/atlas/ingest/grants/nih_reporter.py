"""NIH RePORTER grant ingester (S8.2).

Each fiscal year is fetched in two sweeps: ``ca`` (organisation state CA plus the
term set) and ``terms`` (term set only, which keeps out-of-state recipients).  A
sweep is one unit of work and is applied only after every page of it was fetched.

Provenance (which sweep and fiscal year reported each grant) lives in the state
file, not in the C3 row.  Verified API facts and the term set are recorded in
``docs/api_notes/nih_reporter.md``.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from atlas.ingest.grants.normalize import normalize_grant, write_grants_parquet

SOURCE = "nih_reporter"
FUNDER = "NIH"
API_URL = "https://api.reporter.nih.gov/v2/projects/search"
USER_AGENT = "ca-plastics-atlas/0.1 (research dashboard)"
SEARCH_FIELDS = "projecttitle,abstracttext,terms"
SWEEPS: tuple[str, ...] = ("ca", "terms")
PAGE_SIZE = 500
# Verified: offset 15000 is rejected with "Maximum offset is 14,999".
MAX_OFFSET = 14999
MAX_RECORDS = MAX_OFFSET + 1
# UNVERIFIED: the API's text length limit is not known.  Groups are kept under this
# conservative bound, and a single group is used for the current term set.
MAX_SEARCH_TEXT_CHARS = 1000
MIN_INTERVAL_SECONDS = 1.1
MAX_RETRIES = 3
BACKOFF_SECONDS = 2.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
BACKFILL_YEARS = 15
STATE_VERSION = 1

Transport = Callable[[Mapping[str, Any]], tuple[int, str]]


class NihReporterError(RuntimeError):
    """Base class for ingest failures that defer the run."""


class BudgetExhausted(NihReporterError):
    """The request cap was reached.  Completed units are still applied."""


class ReporterHTTPError(NihReporterError):
    """A non-retryable or retry-exhausted HTTP failure."""


class ReporterResponseError(NihReporterError):
    """The API answered 200 with a payload this module cannot use."""


class CeilingExceeded(NihReporterError):
    """A unit has more records than the API can page through (offset ceiling)."""


@dataclass(frozen=True)
class UnitResult:
    tag: str
    rows: dict[str, dict[str, Any]]
    skipped: int


def search_phrases(core_terms: Sequence[str]) -> list[str]:
    """Return quoted-phrase candidates: each term plus its plural when it has none."""

    phrases: list[str] = []
    for raw in core_terms:
        term = " ".join(str(raw).split())
        if not term:
            continue
        variants = [term] if term.endswith("s") else [term, f"{term}s"]
        for variant in variants:
            if variant not in phrases:
                phrases.append(variant)
    return phrases


def search_text_groups(
    core_terms: Sequence[str], max_chars: int = MAX_SEARCH_TEXT_CHARS
) -> list[str]:
    """Pack quoted phrases into OR-joined groups no longer than ``max_chars``."""

    groups: list[str] = []
    current = ""
    for phrase in search_phrases(core_terms):
        quoted = f'"{phrase}"'
        if len(quoted) > max_chars:
            raise ValueError(f"search phrase exceeds {max_chars} characters: {phrase!r}")
        candidate = quoted if not current else f"{current} OR {quoted}"
        if len(candidate) > max_chars:
            groups.append(current)
            current = quoted
        else:
            current = candidate
    if current:
        groups.append(current)
    return groups


def fiscal_year_of(day: date) -> int:
    """NIH fiscal years start on 1 October and are named for the ending calendar year."""

    return day.year + 1 if day.month >= 10 else day.year


def fiscal_years_for(mode: str, today: date, backfill_years: int = BACKFILL_YEARS) -> list[int]:
    current = fiscal_year_of(today)
    if mode == "incremental":
        return [current, current - 1]
    if mode == "backfill":
        return list(range(current, current - backfill_years, -1))
    raise ValueError(f"unknown mode: {mode!r}")


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


def build_body(
    sweep: str, fiscal_year: int, search_text: str, offset: int, page_size: int = PAGE_SIZE
) -> dict[str, Any]:
    criteria: dict[str, Any] = {}
    if sweep == "ca":
        criteria["org_states"] = ["CA"]
    criteria["fiscal_years"] = [fiscal_year]
    criteria["advanced_text_search"] = {
        "operator": "advanced",
        "search_field": SEARCH_FIELDS,
        "search_text": search_text,
    }
    return {
        "criteria": criteria,
        "offset": offset,
        "limit": page_size,
        "sort_field": "appl_id",
        "sort_order": "asc",
    }


class ReporterClient:
    """Paced, budgeted POST client.  Every transport call counts toward the cap."""

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

    def post(self, body: Mapping[str, Any]) -> dict[str, Any]:
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
                status, text = self.transport(body)
            except OSError as error:
                status, text = None, str(error)
            if status == 200:
                try:
                    payload = json.loads(text)
                except ValueError as error:
                    raise ReporterResponseError("200 response is not JSON") from error
                if not isinstance(payload, dict):
                    raise ReporterResponseError("200 response is not a JSON object")
                return payload
            retryable = status is None or status in RETRY_STATUSES
            if retryable and attempt < MAX_RETRIES:
                self.sleep(BACKOFF_SECONDS * (2**attempt))
                continue
            raise ReporterHTTPError(f"HTTP {status}: {text[:200]}")
        raise ReporterHTTPError("retries exhausted")  # pragma: no cover - loop always returns


def _total(payload: Mapping[str, Any]) -> int:
    meta = payload.get("meta")
    total = meta.get("total") if isinstance(meta, Mapping) else None
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        raise ReporterResponseError("meta.total is missing or not a count")
    return total


def fetch_unit(
    client: ReporterClient,
    *,
    fiscal_year: int,
    sweep: str,
    groups: Sequence[str],
    page_size: int = PAGE_SIZE,
) -> list[dict[str, Any]]:
    """Fetch every page of one sweep for one fiscal year."""

    records: list[dict[str, Any]] = []
    for search_text in groups:
        offset = 0
        while True:
            payload = client.post(build_body(sweep, fiscal_year, search_text, offset, page_size))
            total = _total(payload)
            if total > MAX_RECORDS:
                raise CeilingExceeded(
                    f"{fiscal_year}:{sweep} has {total} records; offset ceiling is {MAX_RECORDS}"
                )
            page = payload.get("results")
            if not isinstance(page, list):
                raise ReporterResponseError("results is missing or not a list")
            records.extend(page)
            offset += len(page)
            if not page or offset >= total:
                break
    return records


_DATE_TEXT = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date_text(value: object) -> str | None:
    """API dates look like ``2024-03-11T00:00:00``; keep the calendar date only."""

    if isinstance(value, str):
        match = _DATE_TEXT.match(value.strip())
        if match is not None:
            return match.group(1)
    return None


def _pi_name(person: object) -> str | None:
    if not isinstance(person, Mapping):
        return None
    full = _text(person.get("full_name"))
    if full:
        return full
    parts = [_text(person.get("first_name")), _text(person.get("last_name"))]
    return " ".join(part for part in parts if part) or None


def to_raw_grant(record: Mapping[str, Any]) -> dict[str, Any] | None:
    """Map one RePORTER project onto the ``normalize_grant`` input fields."""

    appl_id = _text(record.get("appl_id"))
    if appl_id is None:
        return None
    organization = record.get("organization")
    org = organization if isinstance(organization, Mapping) else {}
    ic_admin = record.get("agency_ic_admin")
    ic = ic_admin if isinstance(ic_admin, Mapping) else {}
    ic_name = _text(ic.get("abbreviation")) or _text(ic.get("code"))
    amount = record.get("award_amount")
    principal = record.get("principal_investigators")
    people = principal if isinstance(principal, list) else []
    return {
        "source_award_id": appl_id,
        "title": record.get("project_title"),
        "abstract": record.get("abstract_text"),
        "pi_names": [_pi_name(person) for person in people],
        "org": org.get("org_name"),
        "org_state": org.get("org_state"),
        "start": _date_text(record.get("project_start_date")),
        "end": _date_text(record.get("project_end_date")),
        "amount": amount,
        "currency": "USD" if amount is not None else None,
        "funder": FUNDER,
        "program": ic_name,
        "funder_chain": [FUNDER, ic_name] if ic_name else [FUNDER],
        "url": record.get("project_detail_url"),
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
        raise ValueError(f"unsupported NIH RePORTER state file: {path}")
    return payload


def read_prior_rows(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {row["grant_key"]: row for row in pq.read_table(path).to_pylist()}


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


def merge_units(
    prior_rows: Mapping[str, Mapping[str, Any]],
    state_provenance: Mapping[str, Sequence[str]],
    units: Sequence[UnitResult],
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """Replace each completed unit's provenance, then keep only grants still reported.

    A grant is kept while at least one unit still reports it.  A grant whose state
    provenance is unknown (no state entry) keeps its prior row unchanged.
    """

    known_before = set(state_provenance)
    provenance = {key: set(tags) for key, tags in state_provenance.items()}
    content: dict[str, dict[str, Any]] = {}
    for unit in units:
        for key in [key for key, tags in provenance.items() if unit.tag in tags]:
            provenance[key].discard(unit.tag)
            if not provenance[key]:
                del provenance[key]
        for key, row in unit.rows.items():
            provenance.setdefault(key, set()).add(unit.tag)
            content[key] = row

    rows: list[dict[str, Any]] = []
    for key in provenance:
        row = content.get(key) or prior_rows.get(key)
        if row is not None:
            rows.append(dict(row))
    for key, row in prior_rows.items():
        if key not in known_before and key not in provenance and key not in content:
            rows.append(dict(row))
    return rows, {key: sorted(tags) for key, tags in provenance.items()}


def dry_run_plan(
    *,
    mode: str,
    today: date,
    query_config: Mapping[str, Any],
    state_path: Path,
    max_requests: int,
    page_size: int = PAGE_SIZE,
    max_chars: int = MAX_SEARCH_TEXT_CHARS,
) -> dict[str, Any]:
    """Describe the planned requests without contacting the API or writing files."""

    groups = search_text_groups(list(query_config.get("core_terms") or []), max_chars)
    state = load_state(state_path)
    completed = (state.get("completed") or {}) if state.get("search_groups") == groups else {}
    units = plan_units(mode, today, completed)
    requests = [
        {
            "unit": f"{fiscal_year}:{sweep}",
            "first_page": build_body(sweep, fiscal_year, group, 0, page_size),
        }
        for fiscal_year, sweep in units
        for group in groups
    ]
    return {
        "mode": mode,
        "fiscal_years": fiscal_years_for(mode, today),
        "units": len(units),
        "search_groups": len(groups),
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
    max_chars: int = MAX_SEARCH_TEXT_CHARS,
) -> dict[str, Any]:
    """Fetch planned units and apply the completed ones.

    Status ``ok``: every planned unit completed.  ``partial``: the request cap stopped
    the run, and the completed units were applied.  ``deferred``: an HTTP, response,
    or ceiling failure stopped the run, so nothing was written and prior output is
    preserved.
    """

    if mode not in {"backfill", "incremental"}:
        raise ValueError(f"unknown mode: {mode!r}")
    groups = search_text_groups(list(query_config.get("core_terms") or []), max_chars)
    state = load_state(state_path)
    same_terms = state.get("search_groups") == groups
    completed: dict[str, str] = dict(state.get("completed") or {}) if same_terms else {}
    units = plan_units(mode, today, completed)
    client = ReporterClient(transport, max_requests=max_requests, sleep=sleep, clock=clock)
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
    except NihReporterError as error:
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


def urllib_transport(body: Mapping[str, Any], *, timeout: float = 60.0) -> tuple[int, str]:
    """Default transport.  Only ``api.reporter.nih.gov`` is contacted."""

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")
