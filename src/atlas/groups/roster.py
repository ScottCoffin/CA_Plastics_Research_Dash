"""BFFP roster extraction (Add-on A4, CG-2): raw fetch, cache, allow-list and structural guard.

Only the organisation list (``/api/members_org``) is read. One GET, identified by the project
User-Agent, no pagination. Raw bodies go to ``data/raw/bffp/<YYYY-MM-DD>/`` (gitignored, purged
after 30 days, A4-D23). Only ``organization``, ``country`` and ``website`` survive parsing; the
membership ``type`` and any other field are dropped at read time.

Nothing here publishes anything. Admission and writing live in ``atlas.groups.admission`` and
``scripts/build_groups_roster.py``. Tests inject ``fetcher`` so no request leaves the process.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

__all__ = [
    "BFFP_MEMBERS_ORG_URL",
    "DEFAULT_RAW_ROOT",
    "DROP_THRESHOLD",
    "PARSER_VERSION",
    "RAW_FILE_NAME",
    "USER_AGENT",
    "BFFP_ABOUT_URL",
    "BffpPublicSource",
    "page_fetcher",
    "CsvFileSource",
    "RawEntry",
    "RosterFetchError",
    "RosterSource",
    "RosterStructureError",
    "check_structural_change",
    "parse_members_org",
    "purge_raw_cache",
    "read_raw_file",
    "sha256_file",
]

PARSER_VERSION = "cg-roster-parser-1"
USER_AGENT = "PlastiverseLive-Research (+https://plastiverse.live)"
BFFP_MEMBERS_ORG_URL = "https://coremember.breakfreefromplastic.org/api/members_org"
# The public page whose own script loads the member list (docs/bffp_roster_discovery.md).
BFFP_ABOUT_URL = "https://www.breakfreefromplastic.org/about/"
PAGE_TIMEOUT_MS = 60_000
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RAW_ROOT = REPO_ROOT / "data" / "raw" / "bffp"
RAW_FILE_NAME = "members_org.json"
MANIFEST_FILE_NAME = "manifest.json"
MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = (2.0, 4.0)
STOP_STATUSES = frozenset({403, 429})
RAW_RETENTION_DAYS = 30
DROP_THRESHOLD = 0.20
ALLOWED_FIELDS = ("organization", "country", "website")

# fetcher(url, user_agent) -> (http_status, body_bytes). Network failures raise OSError.
Fetcher = Callable[[str, str], tuple[int, bytes]]


class RosterFetchError(RuntimeError):
    """The source refused access (403/429), kept failing, or returned an unusable payload."""


class RosterStructureError(RuntimeError):
    """The entry count dropped too far against the previous local manifest, or fields vanished."""


@dataclass(frozen=True)
class RawEntry:
    """One source row after the allow-list. Every field is a string or None."""

    organization: str | None
    country: str | None
    website: str | None

    @classmethod
    def from_mapping(cls, item: Mapping[str, object]) -> RawEntry:
        values = {key: item.get(key) for key in ALLOWED_FIELDS}
        cleaned = {key: value if isinstance(value, str) else None for key, value in values.items()}
        return cls(cleaned["organization"], cleaned["country"], cleaned["website"])


class RosterSource(Protocol):
    """A roster adapter: anything that yields raw entries (BFFP export, public API, CSV)."""

    def fetch(self) -> Iterable[RawEntry]: ...


def _urllib_fetch(url: str, user_agent: str) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url, headers={"User-Agent": user_agent, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""


def page_fetcher(url: str, user_agent: str) -> tuple[int, bytes]:
    """Load BFFP's public About page once and return the member-list response that page receives.

    The members endpoint answers only requests made by BFFP's own pages ("Origin not allowed"
    otherwise), so no header is set by hand: a headless browser views the public page as a visitor
    would and the response its own script requests is kept (owner decision 2026-11-26, with BFFP's
    permission, A4-D1). ``url`` names the only member API request allowed. Needs Playwright with
    Chromium, imported only for the live fetch.
    """
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright

    members_host = urllib.parse.urlsplit(url).hostname

    def bffp_only(route, request):  # type: ignore[no-untyped-def]
        host = urllib.parse.urlsplit(request.url).hostname or ""
        if host == members_host:
            if request.url.split("?", 1)[0] == url:
                return route.continue_()
            return route.abort()
        if (
            host == "breakfreefromplastic.org" or host.endswith(".breakfreefromplastic.org")
        ) and request.resource_type in {"document", "script", "xhr", "fetch"}:
            return route.continue_()
        return route.abort()

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            context = browser.new_context(user_agent=f"{user_agent} HeadlessChrome")
            context.route("**/*", bffp_only)
            page = context.new_page()
            with page.expect_response(
                lambda r: r.url.split("?", 1)[0] == url, timeout=PAGE_TIMEOUT_MS
            ) as info:
                navigation = page.goto(
                    BFFP_ABOUT_URL, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS
                )
                if navigation is None:
                    raise RosterFetchError("BFFP About page returned no response")
                if not navigation.ok:
                    raise RosterFetchError(f"BFFP About page: HTTP {navigation.status}")
            response = info.value
            return response.status, response.body()
        except PlaywrightTimeoutError as exc:
            raise RosterFetchError("BFFP member list timed out on the About page") from exc
        finally:
            browser.close()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_members_org(body: bytes | str) -> list[RawEntry]:
    """Parse the ``members_org`` payload ``{error: int, data: [...]}`` through the allow-list."""
    payload = json.loads(body)
    if not isinstance(payload, dict) or payload.get("error") != 0:
        raise RosterFetchError("members_org payload reports an error or has no error field")
    data = payload.get("data")
    if not isinstance(data, list):
        raise RosterFetchError("members_org payload has no data list")
    rows = [RawEntry.from_mapping(item) for item in data if isinstance(item, dict)]
    if data and not any(row.organization for row in rows):
        raise RosterStructureError("members_org: no entry carries an organization field")
    return rows


def read_raw_file(path: Path) -> list[RawEntry]:
    """Read a saved raw file: a ``members_org`` JSON body, or a CSV export."""
    if path.suffix.lower() == ".csv":
        return list(CsvFileSource(path).fetch())
    return parse_members_org(path.read_bytes())


class BffpPublicSource:
    """The public BFFP member map endpoint, with a per-day raw cache and a sha256 manifest."""

    def __init__(
        self,
        cache_dir: Path | str = DEFAULT_RAW_ROOT,
        fetcher: Fetcher | None = None,
        *,
        today: dt.date | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.fetcher: Fetcher = fetcher or _urllib_fetch
        self.today = today or dt.datetime.now(dt.UTC).date()
        self.sleep = sleep
        self.request_count = 0
        self.status_counts: dict[str, int] = {}
        self.raw_path: Path | None = None

    @property
    def day_dir(self) -> Path:
        return self.cache_dir / self.today.isoformat()

    def fetch(self) -> list[RawEntry]:
        """Return today's entries, reusing today's cache when present (no request then)."""
        raw_file = self.day_dir / RAW_FILE_NAME
        if raw_file.exists():
            self._verify_cache(raw_file)
            self.raw_path = raw_file
            return parse_members_org(raw_file.read_bytes())
        body = self._get_with_retries()
        parse_members_org(body)  # validate before anything is written to the cache
        self.day_dir.mkdir(parents=True, exist_ok=True)
        raw_file.write_bytes(body)
        digest = hashlib.sha256(body).hexdigest()
        manifest = {
            "retrieved_at": self.today.isoformat(),
            "source_url": BFFP_MEMBERS_ORG_URL,
            "sha256": digest,
            "bytes": len(body),
            "file": RAW_FILE_NAME,
        }
        (self.day_dir / MANIFEST_FILE_NAME).write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        self.raw_path = raw_file
        return parse_members_org(body)

    def _verify_cache(self, raw_file: Path) -> None:
        manifest_path = self.day_dir / MANIFEST_FILE_NAME
        if not manifest_path.exists():
            raise RosterFetchError(f"{raw_file}: cache has no sha256 manifest")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("sha256") != sha256_file(raw_file):
            raise RosterFetchError(f"{raw_file}: cache does not match its sha256 manifest")

    def _get_with_retries(self) -> bytes:
        attempts = MAX_RETRIES + 1
        for attempt in range(attempts):
            self.request_count += 1
            try:
                status, body = self.fetcher(BFFP_MEMBERS_ORG_URL, USER_AGENT)
            except OSError as exc:
                self._record(f"network:{type(exc).__name__}")
                if attempt + 1 == attempts:
                    raise RosterFetchError("members_org: network failure after retries") from exc
                self.sleep(RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)])
                continue
            self._record(str(status))
            if status == 200:
                return body
            if status in STOP_STATUSES:
                raise RosterFetchError(f"members_org: HTTP {status}; stopping, not retrying")
            if status >= 500 and attempt + 1 < attempts:
                self.sleep(RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)])
                continue
            raise RosterFetchError(f"members_org: HTTP {status}")
        raise RosterFetchError("members_org: retries exhausted")  # pragma: no cover

    def _record(self, key: str) -> None:
        self.status_counts[key] = self.status_counts.get(key, 0) + 1


class CsvFileSource:
    """A saved CSV export (for example a later BFFP-supplied file). Extra columns are ignored."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def fetch(self) -> list[RawEntry]:
        with self.path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = reader.fieldnames or []
            if "organization" not in fields:
                raise RosterStructureError(f"{self.path.name}: CSV has no organization column")
            return [RawEntry.from_mapping(row) for row in reader]


def check_structural_change(
    current_count: int,
    previous_count: int | None,
    *,
    acknowledge_drop: bool = False,
    threshold: float = DROP_THRESHOLD,
) -> None:
    """Raise when the entry count fell by more than ``threshold`` against the previous run."""
    if previous_count is None or previous_count <= 0 or acknowledge_drop:
        return
    if current_count < previous_count * (1 - threshold):
        drop = 100 * (previous_count - current_count) / previous_count
        raise RosterStructureError(
            f"entry count dropped {drop:.0f}% against the previous run; "
            "rerun with --acknowledge-drop after checking the source"
        )


def purge_raw_cache(
    root: Path | str, now: dt.datetime, max_age_days: int = RAW_RETENTION_DAYS
) -> list[str]:
    """Delete dated raw folders older than ``max_age_days`` (A4-D23). Returns the removed names."""
    base = Path(root)
    if not base.is_dir():
        return []
    today = now.date()
    removed: list[str] = []
    for child in sorted(base.iterdir()):
        if not child.is_dir():
            continue
        try:
            folder_day = dt.date.fromisoformat(child.name)
        except ValueError:
            continue  # not a dated folder; never touch it
        if (today - folder_day).days > max_age_days:
            shutil.rmtree(child)
            removed.append(child.name)
    return removed
