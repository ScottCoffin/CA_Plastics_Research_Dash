"""State funder grant sources (S8.6): OPC, Delta Science Tracker, CSU COAST, SCC.

Adapters
--------
``opc_council``: Ocean Protection Council Council-meeting summary pages. Summaries
state approvals as ``<Title> : Up to $<amount> ...``. An item is kept only when the
S2.3 plastic rule matches its title and text. Titles that do not read as Title Case
are skipped and counted, not guessed.

``delta_science_tracker``: the Science Tracker Excel export. Activities whose text
matches the plastic rule are joined to their Funding Awards rows.

``csu_coast`` and ``scc_board``: recorded as gaps (see ``docs/api_notes/state_funders.md``).

Every request goes through :class:`Fetcher`. It obeys robots.txt, spaces network
requests at least ``MIN_INTERVAL_SECONDS`` apart, enforces ``max_requests``, and caches
raw responses under ``data/raw/state_funders/`` (git-ignored). A run that hits an HTTP,
budget, or robots error is deferred: the caller exits 0 and the output is left untouched.
"""

from __future__ import annotations

import csv
import html as html_lib
import io
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

import openpyxl

from atlas.ingest.grants.normalize import normalize_grant, write_grants_parquet
from atlas.ingest.grants.schema import GRANT_COLUMNS
from atlas.nlp.labels import classify_plastic_text

SOURCE_OPC = "opc_council"
SOURCE_DELTA = "delta_science_tracker"
SOURCE_COAST = "csu_coast"
SOURCE_SCC = "scc_board"
OPC_FUNDER = "California Ocean Protection Council"
USER_AGENT = "ca-plastics-atlas/0.1 (research dashboard)"
MIN_INTERVAL_SECONDS = 2.0
TIMEOUT_SECONDS = 60.0
RAW_DIR = Path("data/raw/state_funders")
OUTPUT = Path("data/interim/grants/state_funders.parquet")
STATUS_PATH = Path("data/interim/grants/state_funders_status.json")
CURATION_PATH = Path("curation/grants_manual.csv")
OPC_BASE = "https://opc.ca.gov"
# Council archives scanned for summary links: Jan 2025 through Nov 2026.
OPC_MONTHS: tuple[str, ...] = tuple(
    f"{year}/{month:02d}"
    for year in (2025, 2026)
    for month in range(1, 13)
    if (year, month) <= (2026, 11)
)
DELTA_EXPORT_URL = "https://sciencetracker.deltacouncil.ca.gov/excel-export?/activities"
COAST_ROBOTS_URL = "https://csucoast.org/robots.txt"
SCC_LISTING_URL = "https://scc.ca.gov/public-meetings/"
ACTIVITY_TEXT_COLUMNS: tuple[str, ...] = (
    "Title",
    "Description",
    "Science topics",
    "Science themes",
    "Notes",
)
DERIVED_COLUMNS: frozenset[str] = frozenset(
    {"grant_key", "plastic_related", "domain_tags", "ca_led", "ca_sampling_flag"}
)
LIST_COLUMNS: frozenset[str] = frozenset({"pi_names", "funder_chain", "domain_tags"})
CURATION_EXTRA_COLUMNS: tuple[str, ...] = ("curation_note", "evidence_url")
MONTHS_PATTERN = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
MEETING_RE = re.compile(rf"({MONTHS_PATTERN}) (\d{{1,2}}), (\d{{4}}) Council Meeting")
SUMMARY_LINK_RE = re.compile(
    r'href="(https://opc\.ca\.gov/\d{4}/\d{2}/[^"#?]*council-meeting-summary/?)"'
)
APPROVAL_RE = re.compile(r"\s:\s*Up to \$(\d[\d,]*(?:\.\d+)?)")
TITLE_WINDOW_CHARS = 200
BODY_CHARS = 400
ABSTRACT_CHARS = 600
CONNECTORS: frozenset[str] = frozenset({"and", "of", "for", "the", "in", "on", "&"})


class StateFunderError(RuntimeError):
    """Base error. Any subclass defers the whole run."""


class BudgetExhausted(StateFunderError):
    pass


class RobotsDisallowed(StateFunderError):
    pass


class StateFunderHTTPError(StateFunderError):
    def __init__(self, status: int, url: str) -> None:
        super().__init__(f"HTTP {status} for {url}")
        self.status = status


class HostUnreachable(StateFunderError):
    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"{url} unreachable: {reason}")
        self.reason = reason


def cache_name(url: str) -> str:
    """Return the cache file name for ``url`` (non-alphanumerics become ``_``)."""

    return re.sub(r"[^A-Za-z0-9]+", "_", url)[:120] + ".raw"


def _urlopen_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


class Fetcher:
    """Polite, cached, budget-limited GET. ``requests`` counts network calls only."""

    def __init__(
        self,
        *,
        raw_dir: Path = RAW_DIR,
        max_requests: int = 60,
        refresh: bool = False,
        opener: Callable[[str], bytes] = _urlopen_bytes,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.raw_dir = raw_dir
        self.max_requests = max_requests
        self.refresh = refresh
        self.requests = 0
        self._opener = opener
        self._sleep = sleep
        self._clock = clock
        self._last_started: float | None = None
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    def get(self, url: str) -> bytes:
        if not url.endswith("/robots.txt") and not self.allowed(url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")
        return self._load(url, use_cache=not self.refresh)

    def allowed(self, url: str) -> bool:
        parts = urllib.parse.urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        parser = self._robots.get(base)
        if parser is None:
            parser = urllib.robotparser.RobotFileParser()
            try:
                body = self._load(f"{base}/robots.txt", use_cache=True)
            except StateFunderHTTPError as error:
                if error.status != 404:
                    raise
                body = b""
            parser.parse(body.decode("utf-8", "replace").splitlines())
            self._robots[base] = parser
        return parser.can_fetch(USER_AGENT, url)

    def _load(self, url: str, *, use_cache: bool) -> bytes:
        path = self.raw_dir / cache_name(url)
        if use_cache and path.exists():
            return path.read_bytes()
        if self.requests >= self.max_requests:
            raise BudgetExhausted(f"request budget of {self.max_requests} exhausted at {url}")
        if self._last_started is not None:
            remaining = MIN_INTERVAL_SECONDS - (self._clock() - self._last_started)
            if remaining > 0:
                self._sleep(remaining)
        self._last_started = self._clock()
        self.requests += 1
        try:
            body = self._opener(url)
        except urllib.error.HTTPError as error:
            raise StateFunderHTTPError(error.code, url) from error
        except urllib.error.URLError as error:
            raise HostUnreachable(url, str(error.reason)) from error
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return body


def html_text(page: str) -> str:
    """Return the visible text of an HTML page with whitespace collapsed."""

    text = re.sub(r"<(script|style)\b.*?</\1>", " ", page, flags=re.S | re.I)
    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text).strip()


def slugify(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-")


def _title_before(text: str, colon: int, floor: int) -> tuple[str, int] | None:
    """Return the Title-Case run that ends just before ``colon``, with its start offset.

    The walk stops at lowercase words, at tokens ending in sentence punctuation, and at
    ``floor`` (the end of the previous approval). Leading and trailing connectors are
    dropped.
    """

    window_start = max(floor, colon - TITLE_WINDOW_CHARS)
    tokens = list(re.finditer(r"\S+", text[window_start:colon]))
    accepted: list[re.Match[str]] = []
    for match in reversed(tokens):
        token = match.group()
        if token.endswith((".", ";", ":")):
            break
        if re.match(r"[A-Z]", token) or token.lower() in CONNECTORS:
            accepted.append(match)
            continue
        break
    while accepted and accepted[0].group().lower() in CONNECTORS:
        accepted.pop(0)
    while accepted and accepted[-1].group().lower() in CONNECTORS:
        accepted.pop()
    if not accepted:
        return None
    start = window_start + accepted[-1].start()
    end = window_start + accepted[0].end()
    return text[start:end], start


def opc_approvals(text: str) -> tuple[list[tuple[str, str, str]], int]:
    """Return ``(title, amount_text, body)`` per approval, and the count of unparsed ones."""

    occurrences = list(APPROVAL_RE.finditer(text))
    titles: list[tuple[str, int] | None] = []
    floor = 0
    for match in occurrences:
        titles.append(_title_before(text, match.start(), floor))
        floor = match.end()
    approvals: list[tuple[str, str, str]] = []
    unparsed = 0
    for index, match in enumerate(occurrences):
        found = titles[index]
        if found is None:
            unparsed += 1
            continue
        if index + 1 < len(occurrences):
            following = titles[index + 1]
            body_end = following[1] if following else occurrences[index + 1].start()
        else:
            body_end = len(text)
        body = text[match.end() : min(body_end, match.end() + BODY_CHARS)].strip()
        approvals.append((found[0].strip(), match.group(1), body))
    return approvals, unparsed


def discover_summary_links(page: str) -> list[str]:
    links: list[str] = []
    for link in SUMMARY_LINK_RE.findall(page):
        if link not in links:
            links.append(link)
    return links


def parse_opc_council_summary(
    page: str, source_url: str, query_config: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return plastic-related OPC approvals as raw grant records, plus parse counts."""

    text = html_text(page)
    meeting = MEETING_RE.search(text)
    if meeting is None:
        return [], {"approvals": 0, "plastic": 0, "unparsed": 0, "no_meeting_date": 1}
    meeting_date = datetime.strptime(f"{meeting[1]} {meeting[2]} {meeting[3]}", "%B %d %Y").date()
    approvals, unparsed = opc_approvals(text)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for title, amount_text, body in approvals:
        if not classify_plastic_text(f"{title} {body}", query_config).related:
            continue
        base_id = f"{meeting_date.isoformat()}-{slugify(title)}"
        award_id = base_id
        suffix = 2
        while award_id in seen:
            award_id = f"{base_id}-{suffix}"
            suffix += 1
        seen.add(award_id)
        rows.append(
            {
                "source_award_id": award_id,
                "title": title,
                "abstract": body[:ABSTRACT_CHARS] or None,
                "amount": float(amount_text.replace(",", "")),
                "currency": "USD",
                "start": meeting_date.isoformat(),
                "funder": OPC_FUNDER,
                "program": "Council meeting approval (staff summary)",
                "funder_chain": [OPC_FUNDER],
                "url": source_url,
            }
        )
    counts = {"approvals": len(approvals), "plastic": len(rows), "unparsed": unparsed}
    return rows, counts


def _cell(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text or None


def _sheet_records(workbook: Any, name: str) -> list[dict[str, Any]]:
    if name not in workbook.sheetnames:
        raise ValueError(f"Delta export has no sheet {name!r}")
    rows = workbook[name].iter_rows(values_only=True)
    header = next(rows, None) or ()
    names = [str(cell).strip() if cell is not None else "" for cell in header]
    return [dict(zip(names, row, strict=False)) for row in rows if any(c is not None for c in row)]


def parse_delta_export(
    data: bytes, query_config: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return plastic-related Delta funding awards as raw grant records, plus counts."""

    workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        activities = _sheet_records(workbook, "Science Activities")
        awards = _sheet_records(workbook, "Funding Awards")
    finally:
        workbook.close()
    plastic: dict[str, dict[str, Any]] = {}
    for activity in activities:
        activity_id = _cell(activity.get("Science Activity ID"))
        if activity_id is None:
            continue
        text = " ".join(_cell(activity.get(column)) or "" for column in ACTIVITY_TEXT_COLUMNS)
        if classify_plastic_text(text, query_config).related:
            plastic[activity_id] = activity
    rows: list[dict[str, Any]] = []
    with_awards: set[str] = set()
    for award in awards:
        activity_id = _cell(award.get("Science Activity ID"))
        award_id = _cell(award.get("AwardID"))
        if activity_id not in plastic or award_id is None:
            continue
        activity = plastic[activity_id]
        funder = _cell(award.get("Funding organization"))
        rows.append(
            {
                "source_award_id": award_id,
                "title": _cell(activity.get("Title")),
                "abstract": (_cell(activity.get("Description")) or "")[:ABSTRACT_CHARS] or None,
                "org": _cell(activity.get("Lead implementing organization")),
                "amount": award.get("Total award amount ($)"),
                "currency": "USD",
                "start": _cell(award.get("Date awarded")),
                "funder": funder,
                "program": _cell(award.get("Funding program")),
                "funder_chain": [funder] if funder else [],
                "url": _cell(activity.get("Permalink")),
            }
        )
        with_awards.add(activity_id)
    counts = {
        "activities": len(activities),
        "plastic_activities": len(plastic),
        "award_rows": len(rows),
        "plastic_activities_without_awards": len(plastic) - len(with_awards),
    }
    return rows, counts


def normalize_raw(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    source: str,
    query_config: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Normalize raw records, returning ``(rows, rejections)``. Bad rows are never guessed."""

    rows: list[dict[str, Any]] = []
    rejected: list[str] = []
    for raw in raw_rows:
        try:
            rows.append(
                normalize_grant(raw, source=source, query_config=query_config, taxonomy=taxonomy)
            )
        except ValueError as error:
            rejected.append(f"{source} {raw.get('source_award_id')}: {error}")
    return rows, rejected


def load_curation(
    path: Path, query_config: Mapping[str, Any], taxonomy: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Read curated rows. Each needs ``evidence_url``; derived columns are recomputed."""

    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        header = reader.fieldnames or []
        missing = [c for c in (*GRANT_COLUMNS, *CURATION_EXTRA_COLUMNS) if c not in header]
        if missing:
            raise ValueError(f"{path} header is missing {missing}")
        for number, record in enumerate(reader, start=2):
            if not (record.get("evidence_url") or "").strip():
                raise ValueError(f"{path} line {number}: evidence_url is required")
            raw: dict[str, Any] = {}
            for column in GRANT_COLUMNS:
                if column in DERIVED_COLUMNS:
                    continue
                value = (record.get(column) or "").strip()
                if column in LIST_COLUMNS:
                    raw[column] = [part.strip() for part in value.split("|") if part.strip()]
                else:
                    raw[column] = value or None
            row = normalize_grant(
                raw,
                source=raw.get("source") or "",
                query_config=query_config,
                taxonomy=taxonomy,
            )
            given = (record.get("grant_key") or "").strip()
            if given and given != row["grant_key"]:
                raise ValueError(f"{path} line {number}: grant_key does not match its source id")
            if row["grant_key"] in seen:
                raise ValueError(f"{path} line {number}: duplicate curated grant_key")
            seen.add(row["grant_key"])
            rows.append(row)
    return rows


def merge_curated(
    scraped: Sequence[Mapping[str, Any]], curated: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Merge rows by ``grant_key``. Curated rows win over scraped rows."""

    by_key: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for row in scraped:
        if row["grant_key"] in by_key:
            duplicates += 1
            continue
        by_key[row["grant_key"]] = dict(row)
    overrides = 0
    for row in curated:
        if row["grant_key"] in by_key:
            overrides += 1
        by_key[row["grant_key"]] = dict(row)
    return list(by_key.values()), {
        "curation_overrides": overrides,
        "scraped_duplicates": duplicates,
    }


def collect_delta(
    fetcher: Fetcher, query_config: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    return parse_delta_export(fetcher.get(DELTA_EXPORT_URL), query_config)


def collect_opc(
    fetcher: Fetcher, query_config: Mapping[str, Any], months: Sequence[str]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    summary_urls: list[str] = []
    for month in months:
        try:
            archive = fetcher.get(f"{OPC_BASE}/{month}/").decode("utf-8", "replace")
        except StateFunderHTTPError as error:
            if error.status == 404:
                continue
            raise
        for link in discover_summary_links(archive):
            if link not in summary_urls:
                summary_urls.append(link)
    rows: list[dict[str, Any]] = []
    totals = {"summary_pages": len(summary_urls), "approvals": 0, "plastic": 0, "unparsed": 0}
    for url in summary_urls:
        page = fetcher.get(url).decode("utf-8", "replace")
        page_rows, counts = parse_opc_council_summary(page, url, query_config)
        rows.extend(page_rows)
        for key in ("approvals", "plastic", "unparsed"):
            totals[key] += counts.get(key, 0)
    return rows, totals


def collect_scc(fetcher: Fetcher) -> dict[str, Any]:
    text = html_text(fetcher.get(SCC_LISTING_URL).decode("utf-8", "replace"))
    plastic_hits = len(re.findall(r"plastic", text, flags=re.I))
    coast_hits = len(re.findall(r"\bCOAST\b", text))
    return {
        "status": "gap",
        "reason": (
            "scc_board: board items are PDF staff reports with no item-level parser; "
            f"listing page mentions plastic {plastic_hits} times and COAST {coast_hits} times"
        ),
    }


def collect_coast(fetcher: Fetcher) -> dict[str, Any]:
    try:
        fetcher.get(COAST_ROBOTS_URL)
    except HostUnreachable as error:
        return {
            "status": "gap",
            "reason": (
                f"csu_coast: csucoast.org unreachable ({error.reason}); no awardee lists retrieved"
            ),
        }
    return {
        "status": "gap",
        "reason": "csu_coast: host reachable but the awardee-list page is not located; no parser",
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def run_state_funders(
    *,
    fetcher: Fetcher,
    query_config: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
    output: Path = OUTPUT,
    status_path: Path = STATUS_PATH,
    curation_path: Path = CURATION_PATH,
    months: Sequence[str] = OPC_MONTHS,
) -> dict[str, Any]:
    """Collect every state source and write the merged parquet. Defers on any fetch error."""

    try:
        delta_raw, delta_counts = collect_delta(fetcher, query_config)
        opc_raw, opc_counts = collect_opc(fetcher, query_config, months)
        scc_status = collect_scc(fetcher)
        coast_status = collect_coast(fetcher)
    except StateFunderError as error:
        summary: dict[str, Any] = {
            "status": "deferred",
            "reason": str(error),
            "requests": fetcher.requests,
        }
        _write_json(status_path, summary)
        return summary

    delta_rows, delta_rejected = normalize_raw(
        delta_raw, source=SOURCE_DELTA, query_config=query_config, taxonomy=taxonomy
    )
    opc_rows, opc_rejected = normalize_raw(
        opc_raw, source=SOURCE_OPC, query_config=query_config, taxonomy=taxonomy
    )
    curated = load_curation(curation_path, query_config, taxonomy)
    merged, merge_counts = merge_curated([*delta_rows, *opc_rows], curated)
    write_grants_parquet(merged, output)
    summary = {
        "status": "ok",
        "requests": fetcher.requests,
        "output_rows": len(merged),
        "sources": {
            SOURCE_DELTA: {
                "status": "ok",
                "rows": len(delta_rows),
                "rejected": len(delta_rejected),
                **delta_counts,
            },
            SOURCE_OPC: {
                "status": "ok",
                "rows": len(opc_rows),
                "rejected": len(opc_rejected),
                **opc_counts,
            },
            SOURCE_COAST: coast_status,
            SOURCE_SCC: scc_status,
        },
        "curation_rows": len(curated),
        **merge_counts,
        "gaps": [
            info["reason"] for info in (coast_status, scc_status) if info.get("status") == "gap"
        ],
    }
    _write_json(status_path, summary)
    return summary
