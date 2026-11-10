"""SWRCB FAAST awarded proposals (S8.8): keyword search of the public FAAST tool.

Flow (plain HTTP with ASP.NET postbacks, cookies kept in one session)::

    GET  https://faast.waterboards.ca.gov/
    POST same URL                       PublicTool=PUBLIC SEARCH TOOL
    POST Public_Interface/PublicPropSearchMain.aspx   GotoSearch=Public Search Tool
    POST Public_Interface/PublicSearch.aspx           DescriptionText=<keyword>,
                                                      StatusDDL=AWARDED, search button
    POST GridView pager postbacks (``Page$N``), capped at ``MAX_PAGES``
    GET  PublicProposalDetails.aspx?Pin=..&PropId=.., once per awarded PIN

Privacy (spec F4): only four labelled detail fields are read (RFP/Survey Title,
Submitting Organization, Project Title, Project Description). The Contacts section
and any email or phone are never parsed, stored or logged. Only the search-result
grid HTML is cached on disk, under ``data/raw/faast/`` (git-ignored).

A fetch failure, a robots disallow, a budget overrun, or an unrecognised page raises
:class:`FaastDeferred`. The run then writes a ``deferred`` status and leaves the
output parquet untouched.
"""

from __future__ import annotations

import html as html_lib
import http.cookiejar
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atlas.ingest.grants.normalize import normalize_grant, write_grants_parquet

SOURCE = "swrcb_faast"
FUNDER = "State Water Resources Control Board"
FUNDER_CHAIN: tuple[str, ...] = (FUNDER, "Division of Financial Assistance")
BASE_URL = "https://faast.waterboards.ca.gov/"
SEARCH_PAGE_URL = urllib.parse.urljoin(BASE_URL, "Public_Interface/PublicSearch.aspx")
DETAIL_PATH = "Public_Interface/PublicProposalDetails.aspx"
USER_AGENT = "ca-plastics-atlas/0.1 (research dashboard)"
KEYWORDS: tuple[str, ...] = (
    "microplastic",
    "plastic",
    "trash",
    "litter",
    "debris",
    "tire wear",
    "6PPD",
    "polystyrene",
)
STATUS_FILTER = "AWARDED"
MIN_INTERVAL_SECONDS = 1.0
TIMEOUT_SECONDS = 60.0
MAX_REQUESTS = 120
MAX_PAGES = 20
RAW_DIR = Path("data/raw/faast")
OUTPUT = Path("data/interim/grants/swrcb_faast.parquet")
STATUS_PATH = Path("data/interim/grants/swrcb_faast_status.json")
GRID_ID = "ContentPlaceHolder1_PublicProposalSearchGV"
GRID_TARGET = "PublicProposalSearchGV"
GRID_COLUMNS = 9
PREFIX = "ctl00$ContentPlaceHolder1$"
DESCRIPTION_FIELD = f"{PREFIX}AccrodianPane2_content$DescriptionText"
STATUS_FIELD = f"{PREFIX}AccordianPaneMain_content$StatusDDL"
SEARCH_BUTTON_FIELD = f"{PREFIX}PublicSearchBtn"
SEARCH_BUTTON_VALUE = "Search for Application(s)"
# Detail labels read by ``parse_detail``. Nothing else on the page is read.
DETAIL_LABELS: Mapping[str, str] = {
    "rfp_title": "RFP/Survey Title:",
    "submitting_org": "Submitting Organization:",
    "project_title": "Project Title:",
    "project_description": "Project Description:",
}
PAGER_RE = re.compile(r"__doPostBack\('([^']*" + GRID_TARGET + r"[^']*)',\s*'Page\$(\d+)'\)")
ABSTRACT_CHARS = 600


class FaastDeferred(RuntimeError):
    """Any condition that defers the whole run (exit 0, output untouched)."""


class FaastHTTPError(FaastDeferred):
    def __init__(self, status: int, url: str) -> None:
        super().__init__(f"HTTP {status} from FAAST for {url}")
        self.status = status


@dataclass(frozen=True)
class GridRow:
    pin: str
    agreement_no: str | None
    title: str | None
    applicant: str | None
    req_funds: str | None
    status: str
    detail_url: str


def _plain(fragment: str) -> str | None:
    """Return the visible text of an HTML fragment, or ``None`` when blank."""

    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", fragment))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def money(text: str | None) -> float | None:
    """Parse a requested-funds cell such as ``"     $870,000"``. Never guesses."""

    if text is None:
        return None
    cleaned = text.replace("$", "").replace(",", "").strip()
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return number if math.isfinite(number) and number >= 0 else None


def hidden_fields(page: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for tag in re.findall(r"<input[^>]*type=\"hidden\"[^>]*>", page):
        name = re.search(r'name="([^"]+)"', tag)
        value = re.search(r'value="([^"]*)"', tag)
        if name:
            out[html_lib.unescape(name.group(1))] = (
                html_lib.unescape(value.group(1)) if value else ""
            )
    return out


def select_values(page: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for match in re.finditer(r"<select[^>]*name=\"([^\"]+)\"[^>]*>(.*?)</select>", page, re.S):
        chosen = re.search(r'<option[^>]*selected="selected"[^>]*value="([^"]*)"', match.group(2))
        first = re.search(r'<option[^>]*value="([^"]*)"', match.group(2))
        picked = chosen or first
        out[html_lib.unescape(match.group(1))] = (
            html_lib.unescape(picked.group(1)) if picked else ""
        )
    return out


def form_action(page_url: str, page: str) -> str:
    match = re.search(r'<form[^>]*action="([^"]*)"', page)
    if match is None:
        raise FaastDeferred("FAAST page has no form")
    return urllib.parse.urljoin(page_url, html_lib.unescape(match.group(1)))


def parse_grid(page: str, page_url: str) -> list[GridRow]:
    """Return every result row in the search grid. A page with no grid yields no rows."""

    start = page.find(GRID_ID)
    if start < 0:
        if "PublicSearchBtn" in page:
            return []
        raise FaastDeferred("FAAST search results page not recognised")
    rows: list[GridRow] = []
    for body in re.findall(r"<tr[^>]*>(.*?)</tr>", page[start:], re.S):
        link = re.search(r'href="(PublicProposalDetails\.aspx\?[^"]+)"', body)
        if link is None:
            continue
        cells = [_plain(cell) for cell in re.findall(r"<td[^>]*>(.*?)</td>", body, re.S)]
        if len(cells) != GRID_COLUMNS:
            continue
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(html_lib.unescape(link.group(1))).query)
        pin = (query.get("Pin") or [cells[0] or ""])[0].strip()
        if not pin:
            continue
        rows.append(
            GridRow(
                pin=pin,
                agreement_no=cells[1],
                title=cells[2],
                applicant=cells[3],
                req_funds=cells[7],
                status=(cells[8] or "").upper(),
                detail_url=urllib.parse.urljoin(page_url, html_lib.unescape(link.group(1))),
            )
        )
    return rows


def pager_targets(page: str) -> dict[int, str]:
    """Return ``{page number: postback target}`` for grid pager links on ``page``."""

    text = html_lib.unescape(page)
    return {int(number): target for target, number in PAGER_RE.findall(text)}


def parse_detail(page: str) -> dict[str, str | None]:
    """Return the four labelled detail fields. Nothing else on the page is read."""

    out: dict[str, str | None] = {}
    for key, label in DETAIL_LABELS.items():
        pattern = (
            r'class="left_column1"[^>]*>\s*' + re.escape(label) + r"\s*</td>\s*<td[^>]*>(.*?)</td>"
        )
        match = re.search(pattern, page, re.S)
        out[key] = _plain(match.group(1)) if match else None
    return out


def build_raw(row: GridRow, detail: Mapping[str, str | None]) -> dict[str, Any]:
    """Map one awarded PIN onto the raw grant record consumed by ``normalize_grant``."""

    rfp_title = detail.get("rfp_title")
    title = detail.get("project_title") or row.title
    parts = []
    if row.agreement_no:
        parts.append(f"Agreement No. {row.agreement_no}.")
    description = detail.get("project_description")
    if description:
        parts.append(description)
    abstract = " ".join(parts)[:ABSTRACT_CHARS] or None
    program = (
        f"FAAST: {rfp_title} (amount = requested funds)"
        if rfp_title
        else "FAAST (amount = requested funds)"
    )
    return {
        "source_award_id": row.pin,
        "title": title,
        "abstract": abstract,
        "org": row.applicant,
        "org_state": "CA",
        "amount": money(row.req_funds),
        "currency": "USD",
        "start": None,
        "end": None,
        "funder": FUNDER,
        "program": program,
        "funder_chain": list(FUNDER_CHAIN),
        "url": row.detail_url,
    }


class FaastSession:
    """One cookie-keeping session. Spaces requests and enforces the request budget."""

    def __init__(
        self,
        *,
        max_requests: int = MAX_REQUESTS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_requests = max_requests
        self.requests = 0
        self._sleep = sleep
        self._clock = clock
        self._last_started: float | None = None
        jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def _send(
        self, url: str, data: Mapping[str, str] | None, referer: str | None
    ) -> tuple[str, str]:
        if self.requests >= self.max_requests:
            raise FaastDeferred(f"request budget of {self.max_requests} exhausted")
        if self._last_started is not None:
            remaining = MIN_INTERVAL_SECONDS - (self._clock() - self._last_started)
            if remaining > 0:
                self._sleep(remaining)
        self._last_started = self._clock()
        self.requests += 1
        headers = {"User-Agent": USER_AGENT}
        if referer:
            headers["Referer"] = referer
        body = urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
        request = urllib.request.Request(url, data=body, headers=headers)
        try:
            with self._opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                return response.geturl(), response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            raise FaastHTTPError(error.code, url) from error
        except (urllib.error.URLError, OSError) as error:
            raise FaastDeferred(f"FAAST unreachable: {error}") from error

    def get(self, url: str, referer: str | None = None) -> tuple[str, str]:
        return self._send(url, None, referer)

    def post(self, url: str, data: Mapping[str, str], referer: str | None) -> tuple[str, str]:
        return self._send(url, data, referer)


def robots_allow(session: FaastSession, urls: Sequence[str]) -> bool:
    """Return whether robots.txt allows every URL. A 404 means no rules."""

    try:
        _, body = session.get(urllib.parse.urljoin(BASE_URL, "robots.txt"))
    except FaastHTTPError as error:
        if error.status != 404:
            raise
        body = ""
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(body.splitlines())
    return all(parser.can_fetch(USER_AGENT, url) for url in urls)


def _slug(keyword: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", keyword.lower()).strip("_")


class LiveFaast:
    """Network provider: the postback flow, one session, grid HTML cached under ``raw_dir``."""

    def __init__(self, session: FaastSession, raw_dir: Path = RAW_DIR) -> None:
        self.session = session
        self.raw_dir = raw_dir
        self._page_url: str | None = None
        self._search_html: str | None = None

    @property
    def requests(self) -> int:
        return self.session.requests

    def _start(self) -> None:
        if not robots_allow(
            self.session, [SEARCH_PAGE_URL, urllib.parse.urljoin(BASE_URL, DETAIL_PATH)]
        ):
            raise FaastDeferred("robots.txt disallows the FAAST search or detail pages")
        url, home = self.session.get(BASE_URL)
        data = hidden_fields(home)
        data["PublicTool"] = "PUBLIC SEARCH TOOL"
        url, main = self.session.post(BASE_URL, data, referer=url)
        data = hidden_fields(main)
        data["GotoSearch"] = "Public Search Tool"
        url, search = self.session.post(form_action(url, main), data, referer=url)
        if "PublicSearchBtn" not in search:
            raise FaastDeferred("FAAST search page was not reached")
        self._page_url, self._search_html = url, search

    def search(self, keyword: str) -> list[GridRow]:
        if self._search_html is None or self._page_url is None:
            self._start()
        assert self._search_html is not None and self._page_url is not None
        search_url, search_html = self._page_url, self._search_html
        data = hidden_fields(search_html)
        data.update(select_values(search_html))
        data[DESCRIPTION_FIELD] = keyword
        data[STATUS_FIELD] = STATUS_FILTER
        data[SEARCH_BUTTON_FIELD] = SEARCH_BUTTON_VALUE
        action = form_action(search_url, search_html)
        url, page = self.session.post(action, data, referer=search_url)
        rows: list[GridRow] = []
        visited = {1}
        self._cache(keyword, 1, page)
        rows.extend(parse_grid(page, url))
        while len(visited) < MAX_PAGES:
            targets = {n: t for n, t in pager_targets(page).items() if n not in visited}
            if not targets:
                break
            number = min(targets)
            visited.add(number)
            data = hidden_fields(page)
            data.update(select_values(page))
            data[DESCRIPTION_FIELD] = keyword
            data[STATUS_FIELD] = STATUS_FILTER
            data["__EVENTTARGET"] = targets[number]
            data["__EVENTARGUMENT"] = f"Page${number}"
            url, page = self.session.post(form_action(url, page), data, referer=url)
            self._cache(keyword, number, page)
            rows.extend(parse_grid(page, url))
        return rows

    def _cache(self, keyword: str, number: int, page: str) -> None:
        """Keep only the search-result grid HTML on disk."""

        if GRID_ID not in page:
            return
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        (self.raw_dir / f"grid_{_slug(keyword)}_p{number}.html").write_text(page, encoding="utf-8")

    def detail(self, row: GridRow) -> dict[str, str | None]:
        _, page = self.session.get(row.detail_url, referer=self._page_url or SEARCH_PAGE_URL)
        return parse_detail(page)


class FixtureFaast:
    """Offline provider: ``grid_<keyword>.html`` and ``detail_<pin>.html`` in one directory."""

    requests = 0

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.missing: int = 0

    def search(self, keyword: str) -> list[GridRow]:
        path = self.directory / f"grid_{_slug(keyword)}.html"
        if not path.exists():
            self.missing += 1
            return []
        return parse_grid(path.read_text(encoding="utf-8"), SEARCH_PAGE_URL)

    def detail(self, row: GridRow) -> dict[str, str | None]:
        path = self.directory / f"detail_{row.pin}.html"
        if not path.exists():
            self.missing += 1
            return {}
        return parse_detail(path.read_text(encoding="utf-8"))


def assemble(
    provider: Any, keywords: Sequence[str] = KEYWORDS
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Search each keyword, union awarded hits by PIN, and build raw grant records."""

    per_keyword: dict[str, int] = {}
    unique: dict[str, GridRow] = {}
    non_awarded = 0
    for keyword in keywords:
        found = provider.search(keyword)
        awarded = [row for row in found if row.status == STATUS_FILTER]
        non_awarded += len(found) - len(awarded)
        per_keyword[keyword] = len(awarded)
        for row in awarded:
            unique.setdefault(row.pin, row)
    raw_rows: list[dict[str, Any]] = []
    amount_unparsed = 0
    for pin in sorted(unique):
        row = unique[pin]
        raw_rows.append(build_raw(row, provider.detail(row)))
        if row.req_funds and money(row.req_funds) is None:
            amount_unparsed += 1
    counts: dict[str, Any] = {
        "keyword_hits": per_keyword,
        "unique_awarded": len(unique),
        "non_awarded_skipped": non_awarded,
        "amount_unparsed": amount_unparsed,
    }
    return raw_rows, counts


def run_faast(
    provider: Any,
    *,
    query_config: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
    output: Path = OUTPUT,
    status_path: Path = STATUS_PATH,
    keywords: Sequence[str] = KEYWORDS,
) -> dict[str, Any]:
    """Collect, normalize, and write the FAAST parquet. Defers on any FAAST error."""

    try:
        raw_rows, counts = assemble(provider, keywords)
    except FaastDeferred as error:
        summary: dict[str, Any] = {
            "status": "deferred",
            "reason": str(error),
            "requests": provider.requests,
        }
        _write_json(status_path, summary)
        return summary
    rows: list[dict[str, Any]] = []
    rejected = 0
    for raw in raw_rows:
        try:
            rows.append(
                normalize_grant(raw, source=SOURCE, query_config=query_config, taxonomy=taxonomy)
            )
        except ValueError:
            rejected += 1
    write_grants_parquet(rows, output)
    summary = {
        "status": "ok",
        "requests": provider.requests,
        "output_rows": len(rows),
        "rejected": rejected,
        **counts,
    }
    _write_json(status_path, summary)
    return summary


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
