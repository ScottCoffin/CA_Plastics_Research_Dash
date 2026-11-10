"""California Sea Grant research-project scraper (S8.5).

The crawl reads keyword-filtered pages of the Research Projects listing
(``/our-work/research-projects?keywords=...``), follows each unique project link, and
keeps projects that are plastic-related.  Relevance rules:

* the title or summary names a plastic term (microplastic, plastic, marine debris,
  ocean or marine litter, tire wear); or
* the funder names the Ocean Protection Council (OPC) and the project page mentions a
  plastic term anywhere (for example in an attached summary).

Fetching is polite and bounded: robots.txt is read first and obeyed, requests are at
least ``MIN_INTERVAL_SECONDS`` apart, and each run stops at ``max_requests``.  Every
fetched page is cached under ``data/raw/ca_sea_grant/`` (ignored by git), so a rerun
or a resumed run does not refetch pages it already has.

A run that hits the request cap is ``partial``: its rows are merged over the prior
output.  A failed fetch is ``deferred``: nothing is written and the prior output is
kept.  Robots and HTTP details are recorded in ``docs/api_notes/ca_sea_grant.md``.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from atlas.ingest.grants.normalize import normalize_grant, write_grants_parquet

SOURCE = "ca_sea_grant"
BASE_URL = "https://caseagrant.ucsd.edu"
LISTING_PATH = "/our-work/research-projects"
USER_AGENT = "ca-plastics-atlas/0.1 (research dashboard)"
ROBOT_AGENT = "ca-plastics-atlas"
SEA_GRANT_NAME = "California Sea Grant"
# Keyword listings are the only way to reach the plastic-related projects: the full
# listing is about 480 projects over 44 pages.
KEYWORDS: tuple[str, ...] = (
    "microplastic",
    "plastic",
    "debris",
    "litter",
    "Ocean Protection Council",
)
MAX_LISTING_PAGES = 10
MAX_REQUESTS = 150
MIN_INTERVAL_SECONDS = 2.0
TIMEOUT_SECONDS = 60.0
PLASTIC_PATTERN = re.compile(
    r"\b(?:micro|nano)?plastics?\b|\bmicrobeads?\b|\bmarine debris\b|\b(?:ocean|marine) litter\b"
    r"|\btire wear\b",
    re.IGNORECASE,
)
OPC_PATTERN = re.compile(r"\bOPC\b|Ocean Protection Council", re.IGNORECASE)
# Only used to set org_state.  Institutions that match nothing are left unknown.
CA_INSTITUTION_PATTERN = re.compile(
    r"California|\bUCLA\b|\bUC[A-Z]?\b|\bCal ?Poly\b|\bCSU\b|\bCaltech\b|\bStanford\b|\bUSC\b"
    r"|Scripps|Los Angeles|San Diego|San Francisco|Monterey|Berkeley|Santa Barbara|Santa Cruz"
    r"|Irvine|Riverside|Davis",
    re.IGNORECASE,
)
_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
)


class CaSeaGrantError(RuntimeError):
    """Base class for scraper failures."""


class BudgetExhausted(CaSeaGrantError):
    """The request cap was reached.  Pages already cached are still used."""


class CaSeaGrantFetchError(CaSeaGrantError):
    """A fetch failed (network error or non-200 status).  The run is deferred."""


# --- minimal DOM -----------------------------------------------------------------


@dataclass(eq=False)
class Node:
    tag: str
    attrs: dict[str, str]
    children: list[Node | str] = field(default_factory=list)

    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("[document]", {})
        self._stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, {key: value or "" for key, value in attrs})
        self._stack[-1].children.append(node)
        if tag not in _VOID_TAGS:
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)


def parse_html(text: str) -> Node:
    builder = _TreeBuilder()
    builder.feed(text)
    builder.close()
    return builder.root


def _walk(node: Node) -> Iterator[Node]:
    for child in node.children:
        if isinstance(child, Node):
            yield child
            yield from _walk(child)


def _text(node: Node) -> str:
    pieces = [child if isinstance(child, str) else _text(child) for child in node.children]
    return " ".join(" ".join(pieces).split())


def _field_node(root: Node, name: str) -> Node | None:
    for node in _walk(root):
        if f"field--name-{name}" in node.classes():
            return node
    return None


def _top_items(node: Node) -> Iterator[Node]:
    """Yield the outermost ``field--item`` nodes below a field, without descending into them.

    Principal-investigator cards nest their institution in a second ``field--item``, so a
    full walk would read the institution as a second value.
    """

    for child in node.children:
        if isinstance(child, Node):
            if "field--item" in child.classes():
                yield child
            else:
                yield from _top_items(child)


def _clean(text: str) -> str:
    """Strip the separator punctuation that Drupal leaves between multi-value items."""

    return text.strip().strip(",;").strip()


def _field_items(root: Node, name: str) -> list[str]:
    """Return the distinct item texts of one Drupal field, in page order."""

    node = _field_node(root, name)
    if node is None:
        return []
    items: list[str] = []
    for item in _top_items(node):
        text = _clean(_text(item))
        if text and text not in items:
            items.append(text)
    return items


def _people(root: Node, name: str) -> list[str]:
    """Return person names from a person-card field.  The name is the card's first link."""

    node = _field_node(root, name)
    if node is None:
        return []
    names: list[str] = []
    for item in _top_items(node):
        link = next((child for child in _walk(item) if child.tag == "a"), None)
        text = _clean(_text(link if link is not None else item))
        if text and text not in names:
            names.append(text)
    return names


def _field_times(root: Node, name: str) -> list[str]:
    node = _field_node(root, name)
    if node is None:
        return []
    return [
        time_node.attrs.get("datetime", "")[:10]
        for time_node in _walk(node)
        if time_node.tag == "time"
    ]


# --- listing pages ---------------------------------------------------------------


@dataclass(frozen=True)
class ListingRow:
    number: str
    title: str
    url: str
    focus_area: str
    start: str | None
    end: str | None


@dataclass(frozen=True)
class Listing:
    rows: tuple[ListingRow, ...]
    has_next: bool


def _cell(row: Node, name: str) -> Node | None:
    for node in _walk(row):
        if node.tag == "td" and f"views-field-{name}" in node.classes():
            return node
    return None


def parse_listing(text: str) -> Listing:
    """Parse one page of the Research Projects table.  The header row (``th``) is skipped."""

    root = parse_html(text)
    rows: list[ListingRow] = []
    for tr in _walk(root):
        if tr.tag != "tr":
            continue
        number_cell = _cell(tr, "field-project-number")
        title_cell = _cell(tr, "title")
        if number_cell is None or title_cell is None:
            continue
        link = next((node for node in _walk(title_cell) if node.tag == "a"), None)
        href = link.attrs.get("href", "") if link is not None else ""
        if not href.startswith(LISTING_PATH + "/"):
            continue
        focus = _cell(tr, "field-focus-area")
        dates = _cell(tr, "field-project-date-range")
        times = [t.attrs.get("datetime", "")[:10] for t in _walk(dates)] if dates else []
        times = [t for t in times if t]
        rows.append(
            ListingRow(
                number=_text(number_cell),
                title=_text(title_cell),
                url=urllib.parse.urljoin(BASE_URL, href),
                focus_area=_text(focus) if focus is not None else "",
                start=times[0] if len(times) > 0 else None,
                end=times[1] if len(times) > 1 else None,
            )
        )
    has_next = any("pager__item--next" in node.classes() for node in _walk(root))
    return Listing(rows=tuple(rows), has_next=has_next)


def listing_url(keyword: str, page: int) -> str:
    query = urllib.parse.urlencode({"keywords": keyword, "page": page})
    return f"{BASE_URL}{LISTING_PATH}?{query}"


# --- project pages ---------------------------------------------------------------


@dataclass(frozen=True)
class Project:
    number: str
    title: str
    url: str
    summary: str
    pi_names: tuple[str, ...]
    institution: str | None
    funders: tuple[str, ...]
    focus_areas: tuple[str, ...]
    start: str | None
    end: str | None
    page_text: str


def _decode(body: bytes) -> str:
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        # Some pages carry Windows-1252 apostrophes.
        return body.decode("cp1252", errors="replace")


def parse_project(text: str, url: str) -> Project:
    """Parse one project page.  Raises ``ValueError`` when the number or title is missing."""

    root = parse_html(text)
    numbers = _field_items(root, "field-project-number")
    h1s = [node for node in _walk(root) if node.tag == "h1"]
    h1_page = [node for node in h1s if "page-header" in node.classes()]
    title = _text((h1_page or h1s)[0]) if (h1_page or h1s) else ""
    if not numbers or not title:
        raise ValueError(f"project page lacks a number or title: {url}")
    body_node = _field_node(root, "body")
    summary = _text(body_node) if body_node is not None else ""
    times = _field_times(root, "field-project-date-range")
    article = next((node for node in _walk(root) if node.tag == "article"), root)
    return Project(
        number=numbers[0],
        title=title,
        url=url,
        summary=summary,
        pi_names=tuple(
            dict.fromkeys(
                _people(root, "field-principal-investigators")
                + _people(root, "field-co-principal-investigators")
            )
        ),
        institution=(_field_items(root, "field-university-gov-affi") or [None])[0],
        funders=tuple(_field_items(root, "field-funding-agency")),
        focus_areas=tuple(_field_items(root, "field-focus-area")),
        start=times[0] if len(times) > 0 and times[0] else None,
        end=times[1] if len(times) > 1 and times[1] else None,
        page_text=_text(article),
    )


def is_opc_funded(project: Project) -> bool:
    return any(OPC_PATTERN.search(funder) for funder in project.funders)


def is_relevant(project: Project) -> bool:
    """Plastic terms in title or summary, or an OPC funder with a plastic term on the page."""

    if PLASTIC_PATTERN.search(f"{project.title} {project.summary}"):
        return True
    return is_opc_funded(project) and PLASTIC_PATTERN.search(project.page_text) is not None


def to_raw_grant(project: Project) -> dict[str, Any]:
    """Map one project onto ``normalize_grant`` fields.

    ``funder_chain`` lists the funding agencies named on the page, then California Sea
    Grant as the administering source.  ``funder`` joins the agencies with ``; ``.
    """

    institution = project.institution
    state = "CA" if institution and CA_INSTITUTION_PATTERN.search(institution) else None
    agencies = list(project.funders)
    return {
        "source_award_id": project.number,
        "title": project.title,
        "abstract": project.summary or None,
        "pi_names": list(project.pi_names),
        "org": institution,
        "org_state": state,
        "start": project.start,
        "end": project.end,
        "amount": None,
        "currency": None,
        "funder": "; ".join(agencies) or None,
        "program": "; ".join(project.focus_areas) or None,
        "funder_chain": [*agencies, SEA_GRANT_NAME],
        "url": project.url,
    }


# --- fetching --------------------------------------------------------------------

Transport = Callable[[str], tuple[int, bytes]]


def _urllib_transport(url: str) -> tuple[int, bytes]:
    """Default transport.  Contacts only ``caseagrant.ucsd.edu``."""

    if urllib.parse.urlsplit(url).hostname != "caseagrant.ucsd.edu":
        raise ValueError(f"refusing to fetch outside caseagrant.ucsd.edu: {url}")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, b""


def cache_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()[:24]}.html"


class PoliteFetcher:
    """Serves cached pages first, then paces and counts live requests against the cap."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        max_requests: int,
        transport: Transport = _urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cache_dir = cache_dir
        self.max_requests = max_requests
        self.transport = transport
        self.sleep = sleep
        self.clock = clock
        self.requests = 0
        self.cache_hits = 0
        self._last: float | None = None

    def get(self, url: str) -> str:
        path = cache_path(self.cache_dir, url)
        if path.exists():
            self.cache_hits += 1
            return _decode(path.read_bytes())
        if self.requests >= self.max_requests:
            raise BudgetExhausted(f"max_requests={self.max_requests} reached")
        if self._last is not None:
            wait = MIN_INTERVAL_SECONDS - (self.clock() - self._last)
            if wait > 0:
                self.sleep(wait)
        self._last = self.clock()
        self.requests += 1
        try:
            status, body = self.transport(url)
        except OSError as error:
            raise CaSeaGrantFetchError(f"network error: {error}") from error
        if status != 200:
            raise CaSeaGrantFetchError(f"HTTP {status} for {urllib.parse.urlsplit(url).path}")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(dir=self.cache_dir, prefix=".page-", suffix=".tmp")
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(body)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return _decode(body)


def load_robots(fetcher: PoliteFetcher) -> urllib.robotparser.RobotFileParser:
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(fetcher.get(f"{BASE_URL}/robots.txt").splitlines())
    return parser


def crawl(
    fetcher: PoliteFetcher, robots: urllib.robotparser.RobotFileParser, stats: dict[str, Any]
) -> list[Project]:
    """Walk keyword listings, then fetch and filter each unique project page.

    A ``BudgetExhausted`` stops the crawl and is recorded in ``stats``; projects already
    parsed are returned so the caller can apply a partial run.
    """

    projects: list[Project] = []
    urls: dict[str, None] = {}
    try:
        for keyword in KEYWORDS:
            for page in range(MAX_LISTING_PAGES):
                listing = parse_listing(fetcher.get(listing_url(keyword, page)))
                stats["listing_pages"] += 1
                for row in listing.rows:
                    urls.setdefault(row.url, None)
                if not listing.has_next or not listing.rows:
                    break
        for url in urls:
            if not robots.can_fetch(ROBOT_AGENT, url):
                stats["robots_skipped"] += 1
                continue
            try:
                project = parse_project(fetcher.get(url), url)
            except ValueError:
                stats["skipped_invalid"] += 1
                continue
            stats["projects_fetched"] += 1
            if is_relevant(project):
                projects.append(project)
    except BudgetExhausted as error:
        stats["partial_reason"] = str(error)
    return projects


def normalize_projects(
    projects: Sequence[Project],
    *,
    query_config: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], int]:
    """Return rows keyed by ``grant_key`` (first occurrence wins) and the skip count."""

    rows: dict[str, dict[str, Any]] = {}
    skipped = 0
    for project in projects:
        try:
            row = normalize_grant(
                to_raw_grant(project), source=SOURCE, query_config=query_config, taxonomy=taxonomy
            )
        except ValueError:
            skipped += 1
            continue
        rows.setdefault(row["grant_key"], row)
    return rows, skipped


def _prior_rows(output: Path) -> dict[str, dict[str, Any]]:
    if not output.exists():
        return {}
    return {row["grant_key"]: row for row in pq.read_table(output).to_pylist()}


def run_ingest(
    *,
    output: Path,
    cache_dir: Path,
    query_config: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
    max_requests: int = MAX_REQUESTS,
    transport: Transport = _urllib_transport,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Crawl, normalize, and write.  Status is ``ok``, ``partial``, or ``deferred``.

    ``deferred`` writes nothing.  ``partial`` keeps prior rows that this run did not
    reach.  The summary holds counts only.
    """

    if max_requests < 1:
        raise ValueError("max_requests must be at least 1")
    fetcher = PoliteFetcher(
        cache_dir, max_requests=max_requests, transport=transport, sleep=sleep, clock=clock
    )
    stats: dict[str, Any] = {
        "listing_pages": 0,
        "projects_fetched": 0,
        "robots_skipped": 0,
        "skipped_invalid": 0,
    }
    summary: dict[str, Any] = {
        "source": SOURCE,
        "status": "ok",
        "reason": "",
        "max_requests": max_requests,
        "requests": 0,
        "cache_hits": 0,
        "rows_written": None,
    }
    try:
        robots = load_robots(fetcher)
        projects = crawl(fetcher, robots, stats)
    except BudgetExhausted as error:
        summary.update(status="partial", reason=str(error))
        projects = []
    except CaSeaGrantFetchError as error:
        summary.update(status="deferred", reason=str(error))
        summary.update(requests=fetcher.requests, cache_hits=fetcher.cache_hits, **stats)
        return summary

    if "partial_reason" in stats:
        summary.update(status="partial", reason=stats.pop("partial_reason"))
    summary.update(stats)
    summary["requests"] = fetcher.requests
    summary["cache_hits"] = fetcher.cache_hits
    summary["projects_relevant"] = len(projects)
    rows, skipped = normalize_projects(projects, query_config=query_config, taxonomy=taxonomy)
    summary["skipped_invalid"] += skipped
    if summary["status"] == "partial":
        rows = {**_prior_rows(output), **rows}
    write_grants_parquet(list(rows.values()), output)
    summary["rows_written"] = len(rows)
    summary["checked_at_utc"] = (now or datetime.now(UTC)).isoformat()
    return summary
