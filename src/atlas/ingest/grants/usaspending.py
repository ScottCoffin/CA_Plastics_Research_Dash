"""USAspending grant ingester (S8.4).

Each fiscal year is fetched in two sweeps over the same curated keyword set:
``ca_recipient`` (recipient state CA) and ``ca_pop`` (place of performance in CA).
A sweep is one unit of work and is applied only after every page of it was
fetched.  Rows are keyed by ``grant_key``, which is derived from
``generated_internal_id``, so an award returned by both sweeps is stored once.

USAspending keywords are OR-joined across the list, so one request covers the whole
term set.  Multi-word keywords match far fewer awards, and plural forms need no
separate entry.  The noise findings behind the term set are recorded in
``docs/api_notes/usaspending.md``.

``--bulk`` (backfill only) downloads the award CSV archive for one fiscal year and
filters it locally.  It is implemented but has only been exercised with fakes, and
its CSV column names are unverified.  See the same note.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, BinaryIO

from atlas.ingest.grants.nih_reporter import (
    UnitResult,
    fiscal_years_for,
    merge_units,
    read_prior_rows,
)
from atlas.ingest.grants.normalize import normalize_grant, write_grants_parquet

SOURCE = "usaspending"
API_BASE = "https://api.usaspending.gov/api/v2"
SEARCH_PATH = "/search/spending_by_award/"
BULK_PATH = "/bulk_download/awards/"
DOWNLOAD_HOSTS = frozenset({"api.usaspending.gov", "files.usaspending.gov"})
USER_AGENT = "ca-plastics-atlas/0.1 (research dashboard)"
AWARD_URL = "https://www.usaspending.gov/award/{award_id}"
FIELDS: tuple[str, ...] = (
    "Award ID",
    "Recipient Name",
    "Start Date",
    "End Date",
    "Award Amount",
    "Awarding Agency",
    "Awarding Sub Agency",
    "Description",
    "Place of Performance State Code",
    "Recipient State Code",
)
# Grant award type codes: block, formula, project, and cooperative agreement.
AWARD_TYPE_CODES: tuple[str, ...] = ("02", "03", "04", "05")
CA_LOCATION: Mapping[str, str] = {"country": "USA", "state": "CA"}
SWEEP_LOCATION_FILTERS: Mapping[str, str] = {
    "ca_recipient": "recipient_locations",
    "ca_pop": "place_of_performance_locations",
}
SWEEPS: tuple[str, ...] = tuple(SWEEP_LOCATION_FILTERS)
# Curated set.  "plastic" and "polymer" are excluded: they match inside "plasticity"
# and "polymerization" and were too noisy (see docs/api_notes/usaspending.md).
USASPENDING_TERMS: tuple[str, ...] = (
    "microplastic",
    "nanoplastic",
    "plastic pollution",
    "marine debris",
    "tire wear particle",
)
PAGE_SIZE = 100
# The API rejects limit above 100.  page * limit is capped at 10,000, and pages past
# that ceiling return an empty page silently, so the cap is enforced here.
MAX_PAGES = 100
MIN_INTERVAL_SECONDS = 1.1
MAX_RETRIES = 3
BACKOFF_SECONDS = 2.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
BACKFILL_YEARS = 15
STATE_VERSION = 1
TITLE_CHARS = 200
BULK_FILE_FORMAT = "csv"
# UNVERIFIED: bulk CSV column names were not checked against a live archive.
BULK_COLUMNS: Mapping[str, str] = {
    "generated_internal_id": "generated_unique_award_id",
    "Award ID": "award_id_fain",
    "Recipient Name": "recipient_name",
    "Recipient State Code": "recipient_state_code",
    "Start Date": "period_of_performance_start_date",
    "End Date": "period_of_performance_current_end_date",
    "Award Amount": "total_obligated_amount",
    "Awarding Agency": "awarding_agency_name",
    "Awarding Sub Agency": "awarding_sub_agency_name",
    "Description": "prime_award_base_transaction_description",
}

Transport = Callable[[str, Mapping[str, Any]], tuple[int, str]]
Downloader = Callable[[str, Path], None]


class UsaspendingError(RuntimeError):
    """Base class for ingest failures that defer the run."""


class BudgetExhausted(UsaspendingError):
    """The request cap was reached.  Completed units are still applied."""


class UsaspendingHTTPError(UsaspendingError):
    """A non-retryable or retry-exhausted HTTP failure."""


class UsaspendingResponseError(UsaspendingError):
    """The API answered 200 with a payload this module cannot use."""


class PageCapExceeded(UsaspendingError):
    """A unit still has pages after ``MAX_PAGES``.  Its rows are not applied."""


def fiscal_year_bounds(fiscal_year: int) -> tuple[date, date]:
    """Federal fiscal years run 1 October to 30 September and are named for the ending year."""

    return date(fiscal_year - 1, 10, 1), date(fiscal_year, 9, 30)


def build_filters(
    sweep: str, fiscal_year: int, terms: Sequence[str] = USASPENDING_TERMS
) -> dict[str, Any]:
    if sweep not in SWEEP_LOCATION_FILTERS:
        raise ValueError(f"unknown sweep: {sweep!r}")
    start, end = fiscal_year_bounds(fiscal_year)
    return {
        "keywords": list(terms),
        "time_period": [{"start_date": start.isoformat(), "end_date": end.isoformat()}],
        "award_type_codes": list(AWARD_TYPE_CODES),
        SWEEP_LOCATION_FILTERS[sweep]: [dict(CA_LOCATION)],
    }


def build_body(
    sweep: str, fiscal_year: int, page: int, page_size: int = PAGE_SIZE
) -> dict[str, Any]:
    return {
        "filters": build_filters(sweep, fiscal_year),
        "fields": list(FIELDS),
        "page": page,
        "limit": page_size,
        "sort": "Award ID",
        "order": "asc",
    }


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


class UsaspendingClient:
    """Paced, budgeted client.  Every request and every download counts toward the cap."""

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

    def spend(self) -> None:
        """Check the budget, pace the next call, and count it."""

        if self.requests >= self.max_requests:
            raise BudgetExhausted(f"max_requests={self.max_requests} reached")
        if self._last is not None:
            wait = MIN_INTERVAL_SECONDS - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
        self._last = self.clock()
        self.requests += 1

    def post(self, path: str, body: Mapping[str, Any]) -> dict[str, Any]:
        for attempt in range(MAX_RETRIES + 1):
            self.spend()
            try:
                status, text = self.transport(path, body)
            except OSError as error:
                status, text = None, str(error)
            if status == 200:
                try:
                    payload = json.loads(text)
                except ValueError as error:
                    raise UsaspendingResponseError("200 response is not JSON") from error
                if not isinstance(payload, dict):
                    raise UsaspendingResponseError("200 response is not a JSON object")
                return payload
            retryable = status is None or status in RETRY_STATUSES
            if retryable and attempt < MAX_RETRIES:
                self.sleep(BACKOFF_SECONDS * (2**attempt))
                continue
            raise UsaspendingHTTPError(f"HTTP {status}: {text[:200]}")
        raise UsaspendingHTTPError("retries exhausted")  # pragma: no cover - loop returns


def fetch_unit(
    client: UsaspendingClient,
    *,
    fiscal_year: int,
    sweep: str,
    page_size: int = PAGE_SIZE,
    max_pages: int = MAX_PAGES,
) -> list[dict[str, Any]]:
    """Fetch every page of one sweep for one fiscal year, following ``page_metadata.hasNext``."""

    records: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        payload = client.post(SEARCH_PATH, build_body(sweep, fiscal_year, page, page_size))
        results = payload.get("results")
        meta = payload.get("page_metadata")
        has_next = meta.get("hasNext") if isinstance(meta, Mapping) else None
        if not isinstance(results, list) or not isinstance(has_next, bool):
            raise UsaspendingResponseError("results or page_metadata.hasNext is missing")
        if not results and has_next:
            raise UsaspendingResponseError("empty page reports hasNext")
        records.extend(results)
        if not has_next:
            return records
    raise PageCapExceeded(f"{fiscal_year}:{sweep} has more pages after page {max_pages}")


_DATE_TEXT = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date_text(value: object) -> str | None:
    """USAspending dates look like ``2024-10-01``; keep the calendar date only."""

    if isinstance(value, str):
        match = _DATE_TEXT.match(value.strip())
        if match is not None:
            return match.group(1)
    return None


def to_raw_grant(record: Mapping[str, Any]) -> dict[str, Any] | None:
    """Map one ``spending_by_award`` result (or a bulk CSV row) onto ``normalize_grant`` fields.

    The result has no award title, so ``title`` is the first ``TITLE_CHARS`` of the
    description, or ``Award <Award ID>`` when the description is blank.
    """

    award_key = _text(record.get("generated_internal_id"))
    if award_key is None:
        return None
    description = _text(record.get("Description"))
    award_id = _text(record.get("Award ID"))
    excerpt = " ".join(description.split())[:TITLE_CHARS].strip() if description else ""
    title = excerpt or (f"Award {award_id}" if award_id else None)
    if title is None:
        return None
    agency = _text(record.get("Awarding Agency"))
    sub_agency = _text(record.get("Awarding Sub Agency"))
    amount = record.get("Award Amount")
    return {
        "source_award_id": award_key,
        "title": title,
        "abstract": description,
        "pi_names": [],
        "org": _text(record.get("Recipient Name")),
        "org_state": _text(record.get("Recipient State Code")),
        "start": _date_text(record.get("Start Date")),
        "end": _date_text(record.get("End Date")),
        "amount": amount,
        "currency": "USD" if amount is not None else None,
        "funder": agency,
        "program": sub_agency,
        "funder_chain": [name for name in (agency, sub_agency) if name],
        "url": AWARD_URL.format(award_id=award_key),
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
    return {"schema_version": STATE_VERSION, "terms": None, "completed": {}, "provenance": {}}


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_state()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != STATE_VERSION:
        raise ValueError(f"unsupported USAspending state file: {path}")
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


def _completed_for_terms(state: Mapping[str, Any]) -> dict[str, str]:
    """Completed units only count when they were fetched with the current term set."""

    if state.get("terms") == list(USASPENDING_TERMS):
        return dict(state.get("completed") or {})
    return {}


def _summary(
    mode: str, fiscal_years: Sequence[int], units_planned: int, max_requests: int
) -> dict[str, Any]:
    return {
        "mode": mode,
        "status": "ok",
        "reason": "",
        "fiscal_years": list(fiscal_years),
        "units_planned": units_planned,
        "units_completed": 0,
        "skipped_invalid": 0,
        "requests": 0,
        "max_requests": max_requests,
        "rows_written": None,
    }


def _apply_results(
    *,
    mode: str,
    status: str,
    results: Sequence[UnitResult],
    output: Path,
    state_path: Path,
    state: Mapping[str, Any],
    completed: dict[str, str],
    stamp: str,
    requests: int,
) -> int:
    prior = read_prior_rows(output)
    rows, provenance = merge_units(prior, state.get("provenance") or {}, results)
    write_grants_parquet(rows, output)
    for unit in results:
        completed[unit.tag] = stamp
    _write_json_atomic(
        state_path,
        {
            "schema_version": STATE_VERSION,
            "terms": list(USASPENDING_TERMS),
            "completed": completed,
            "provenance": provenance,
            "last_run_utc": stamp,
            "last_run": {
                "mode": mode,
                "status": status,
                "requests": requests,
                "units_completed": len(results),
                "rows_written": len(rows),
            },
        },
    )
    return len(rows)


def dry_run_plan(
    *,
    mode: str,
    today: date,
    state_path: Path,
    max_requests: int,
    page_size: int = PAGE_SIZE,
) -> dict[str, Any]:
    """Describe the planned first-page requests without contacting the API or writing files."""

    completed = _completed_for_terms(load_state(state_path))
    units = plan_units(mode, today, completed)
    requests = [
        {
            "unit": f"{fiscal_year}:{sweep}",
            "path": SEARCH_PATH,
            "first_page": build_body(sweep, fiscal_year, 1, page_size),
        }
        for fiscal_year, sweep in units
    ]
    return {
        "mode": mode,
        "fiscal_years": fiscal_years_for(mode, today),
        "units": len(units),
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
    max_pages: int = MAX_PAGES,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Fetch planned sweeps and apply the completed ones.

    Status ``ok``: every planned unit completed.  ``partial``: the request cap stopped
    the run, and the completed units were applied.  ``deferred``: an HTTP, response, or
    page-cap failure stopped the run, so nothing was written and prior output is kept.
    """

    if mode not in {"backfill", "incremental"}:
        raise ValueError(f"unknown mode: {mode!r}")
    state = load_state(state_path)
    completed = _completed_for_terms(state)
    units = plan_units(mode, today, completed)
    client = UsaspendingClient(transport, max_requests=max_requests, sleep=sleep, clock=clock)
    summary = _summary(mode, fiscal_years_for(mode, today), len(units), max_requests)
    results: list[UnitResult] = []
    try:
        for fiscal_year, sweep in units:
            records = fetch_unit(
                client,
                fiscal_year=fiscal_year,
                sweep=sweep,
                page_size=page_size,
                max_pages=max_pages,
            )
            rows, skipped = normalize_records(records, query_config=query_config, taxonomy=taxonomy)
            results.append(UnitResult(f"{fiscal_year}:{sweep}", rows, skipped))
    except BudgetExhausted as error:
        summary.update(status="partial", reason=str(error))
    except UsaspendingError as error:
        summary.update(status="deferred", reason=str(error), requests=client.requests)
        return summary

    summary["requests"] = client.requests
    summary["units_completed"] = len(results)
    summary["skipped_invalid"] = sum(unit.skipped for unit in results)
    if not results:
        return summary
    stamp = (now or datetime.now(UTC)).isoformat()
    summary["rows_written"] = _apply_results(
        mode=mode,
        status=summary["status"],
        results=results,
        output=output,
        state_path=state_path,
        state=state,
        completed=completed,
        stamp=stamp,
        requests=client.requests,
    )
    return summary


def bulk_request_body(fiscal_year: int) -> dict[str, Any]:
    start, end = fiscal_year_bounds(fiscal_year)
    return {
        "filters": {
            "prime_award_types": list(AWARD_TYPE_CODES),
            "sub_award_types": [],
            "date_type": "action_date",
            "date_range": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        },
        "file_format": BULK_FILE_FORMAT,
    }


def bulk_file_url(payload: Mapping[str, Any]) -> str:
    """Return the archive URL only when it is HTTPS on an allowed USAspending host."""

    url = payload.get("file_url")
    parts = urllib.parse.urlsplit(url) if isinstance(url, str) else None
    if parts is None or parts.scheme != "https" or parts.hostname not in DOWNLOAD_HOSTS:
        raise UsaspendingResponseError("bulk response has no usable file_url")
    return url


def download_archive(url: str, destination: Path, *, timeout: float = 600.0) -> None:
    """Default downloader.  Streams the archive to ``destination`` and never extracts it."""

    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in DOWNLOAD_HOSTS:
        raise UsaspendingResponseError(f"refusing to download from {parts.hostname!r}")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise UsaspendingHTTPError(f"HTTP {response.status} while downloading archive")
        with destination.open("wb") as stream:
            shutil.copyfileobj(response, stream)


def bulk_records(
    archive: BinaryIO | str | Path, terms: Sequence[str] = USASPENDING_TERMS
) -> list[dict[str, Any]]:
    """Read CSV members from a zip in memory and keep CA recipients whose description has a term.

    The bulk path cannot apply the keyword filter server-side, so the term match is a
    local case-insensitive substring test.  Place-of-performance is not read here.
    """

    lowered = tuple(term.lower() for term in terms)
    records: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive) as bundle:
        for name in bundle.namelist():
            if not name.lower().endswith(".csv"):
                continue
            with bundle.open(name) as raw:
                reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
                for row in reader:
                    record = {api: row.get(column) for api, column in BULK_COLUMNS.items()}
                    state = (record.get("Recipient State Code") or "").strip().upper()
                    text = (record.get("Description") or "").lower()
                    if state == "CA" and any(term in text for term in lowered):
                        records.append(record)
    return records


def run_bulk_ingest(
    *,
    fiscal_years: Sequence[int],
    output: Path,
    state_path: Path,
    query_config: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
    transport: Transport,
    max_requests: int,
    today: date,
    now: datetime | None = None,
    download: Downloader = download_archive,
    work_dir: Path | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Backfill-only bulk path.  Each fiscal year costs one submit POST and one download."""

    state = load_state(state_path)
    completed = _completed_for_terms(state)
    units = [year for year in fiscal_years if f"{year}:bulk" not in completed]
    client = UsaspendingClient(transport, max_requests=max_requests, sleep=sleep, clock=clock)
    summary = _summary("bulk", fiscal_years, len(units), max_requests)
    results: list[UnitResult] = []
    try:
        with tempfile.TemporaryDirectory(prefix="usaspending-bulk-", dir=work_dir) as directory:
            for fiscal_year in units:
                payload = client.post(BULK_PATH, bulk_request_body(fiscal_year))
                url = bulk_file_url(payload)
                client.spend()
                archive = Path(directory) / f"award-{fiscal_year}.zip"
                download(url, archive)
                records = bulk_records(archive)
                rows, skipped = normalize_records(
                    records, query_config=query_config, taxonomy=taxonomy
                )
                results.append(UnitResult(f"{fiscal_year}:bulk", rows, skipped))
    except BudgetExhausted as error:
        summary.update(status="partial", reason=str(error))
    except UsaspendingError as error:
        summary.update(status="deferred", reason=str(error), requests=client.requests)
        return summary

    summary["requests"] = client.requests
    summary["units_completed"] = len(results)
    summary["skipped_invalid"] = sum(unit.skipped for unit in results)
    if not results:
        return summary
    stamp = (now or datetime.now(UTC)).isoformat()
    summary["rows_written"] = _apply_results(
        mode="bulk",
        status=summary["status"],
        results=results,
        output=output,
        state_path=state_path,
        state=state,
        completed=completed,
        stamp=stamp,
        requests=client.requests,
    )
    return summary


def urllib_transport(
    path: str, body: Mapping[str, Any], *, timeout: float = 60.0
) -> tuple[int, str]:
    """Default transport.  Contacts only ``api.usaspending.gov``, at relative paths."""

    if not path.startswith("/"):
        raise ValueError("transport paths must be relative to the USAspending API base")
    request = urllib.request.Request(
        API_BASE + path,
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
