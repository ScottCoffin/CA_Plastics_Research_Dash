"""Global works per country under the active plastics query (PLAT-2a landing map).

One ``group_by=authorships.countries`` request per window, each under the active query filter
(the ``openalex_filter`` and ``type_filters`` that ``scripts/fetch_trend_global.py`` also uses):

* ``total_by_country``: every publication year;
* ``recent_5y_by_country``: the current year and the four before it;
* ``new_this_week_by_country``: publication date in the last seven days, today included.

OpenAlex returns at most 200 groups per group_by and refuses page 2 (HTTP 400). A window that
fills all 200 places is listed in ``truncated_windows``, and its smallest countries may be
missing. The result is ``site/data/global/global_counts.json``. It is cached per query version
and refreshed after seven days or with ``--force``. A run makes three OpenAlex requests, never
spends more than 60 credits (``RUN_CREDIT_CAP``), and the daily ceilings in ``config/budget.yml``
still apply. Each response is also saved under ``data/raw/global_counts/`` (git-ignored) as the
record of what OpenAlex returned.

Usage:
    py -3.14 scripts/build_global_counts.py --dry-run   # print the redacted URLs, no call
    py -3.14 scripts/build_global_counts.py             # cached unless stale or version changed
    py -3.14 scripts/build_global_counts.py --force     # refetch regardless of cache
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.ingest.openalex import (  # noqa: E402
    OPENALEX_BASE,
    _request_json,
    load_openalex_key,
)
from atlas.query import load_query_config, openalex_filter, type_filters  # noqa: E402
from atlas.util.budget import (  # noqa: E402
    UNKNOWN_429_CREDITS,
    daily_logged_usage,
    resolve_openalex_budget,
)
from atlas.util.cost import ApiCostLogger  # noqa: E402

SOURCE = (
    "OpenAlex works group_by=authorships.countries under the active query: all years; "
    "the last 5 publication years; publication date in the last 7 days; "
    "at most 200 countries per window (the group_by limit)"
)
GROUP_FIELD = "authorships.countries"
# group_by returns at most this many groups, from page 1 only (page 2 is HTTP 400).
GROUP_LIMIT = 200
# Three windows make three requests; four is the ceiling.
MAX_REQUESTS = 4
# One logical request is at most this many HTTP attempts through the shared request path.
MAX_HTTP_ATTEMPTS = 3
# A search-filter count costs 10 credits (measured 2026-11-09), and an attempt with unknown
# credits is charged the same, so each attempt is budgeted at 10.
ATTEMPT_CREDITS = UNKNOWN_429_CREDITS
# Reserved before each logical request, so retries inside it cannot take the run past the cap.
WORST_CASE_CREDITS = ATTEMPT_CREDITS * MAX_HTTP_ATTEMPTS
RUN_CREDIT_CAP = Decimal(60)
RECENT_YEARS = 5
NEW_DAYS = 7
# The "new this week" window goes stale quickly, so cached results expire after a week.
MAX_AGE = timedelta(days=7)
MAX_URL_CHARS = 8000
COUNTRY_CODE = re.compile(r"[A-Z]{2}")
DEFAULT_OUTPUT = ROOT / "site" / "data" / "global" / "global_counts.json"
DEFAULT_CONFIG = ROOT / "config" / "queries.yml"
DEFAULT_BUDGET = ROOT / "config" / "budget.yml"
DEFAULT_USAGE_LOG = ROOT / "data" / "logs" / "api_usage.jsonl"
DEFAULT_RAW_DIR = ROOT / "data" / "raw" / "global_counts"
DEFAULT_ENV = ROOT / ".env"


class FetchError(RuntimeError):
    """A request, budget or validation failure: nothing is written."""


@dataclass(frozen=True)
class Window:
    """One group_by request: the output key it fills and the filters that narrow it."""

    name: str
    extra_filters: tuple[str, ...]


@dataclass(frozen=True)
class WindowResult:
    """One window's country counts, its works total, and whether the 200-group limit was hit."""

    counts: dict[str, int]
    works: int
    truncated: bool


def windows(now: datetime) -> list[Window]:
    """The three windows. ``now`` is UTC; the five-year window ends with the current year."""

    years = "|".join(str(year) for year in range(now.year - RECENT_YEARS + 1, now.year + 1))
    since = (now.date() - timedelta(days=NEW_DAYS - 1)).isoformat()
    return [
        Window("total_by_country", ()),
        Window("recent_5y_by_country", (f"publication_year:{years}",)),
        Window("new_this_week_by_country", (f"from_publication_date:{since}",)),
    ]


def build_url(config: Mapping[str, Any], window: Window) -> str:
    """The active query filter, the window's filters, and the group_by (page 1 only)."""

    filters = [openalex_filter(config), *type_filters(config), *window.extra_filters]
    params = {"filter": ",".join(filters), "group_by": GROUP_FIELD, "per_page": GROUP_LIMIT}
    url = f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"
    if len(url) > MAX_URL_CHARS:
        raise FetchError(f"request URL is {len(url)} characters; limit is {MAX_URL_CHARS}")
    return url


def redact(url: str) -> str:
    """Hide any API key that might appear in a query string before printing."""

    return re.sub(r"(api_key=)[^&]+", r"\1REDACTED", url)


def country_counts(body: Mapping[str, Any]) -> tuple[dict[str, int], list[str]]:
    """``{ISO alpha-2: works}`` from one group_by page, plus any keys that are not country codes.

    OpenAlex may return a bare code (``US``) or a URI ending in one; both are accepted.
    """

    counts: dict[str, int] = {}
    skipped: list[str] = []
    for group in body.get("group_by") or []:
        key = str(group.get("key") or "")
        code = key.rsplit("/", 1)[-1].upper()
        if not COUNTRY_CODE.fullmatch(code):
            skipped.append(key)
            continue
        counts[code] = int(group.get("count") or 0)
    return counts, skipped


def works_total(body: Mapping[str, Any]) -> int:
    """The number of works matching the request, from ``meta.count``."""

    meta = body.get("meta") or {}
    count = meta.get("count")
    if not isinstance(count, int) or isinstance(count, bool):
        raise FetchError("group_by response has no integer meta.count")
    return count


def load_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return cache if isinstance(cache, dict) else None


def is_fresh(cache: Mapping[str, Any] | None, version: str, now: datetime) -> bool:
    """True when the cached file has this query version and is under seven days old."""

    if not cache or cache.get("query_version") != version:
        return False
    try:
        fetched = datetime.fromisoformat(str(cache.get("fetched_at")))
    except ValueError:
        return False
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=UTC)
    return now - fetched < MAX_AGE


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomic write with LF line endings and a trailing newline."""

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


class BudgetedRun:
    """Sends this run's requests and enforces every limit before each one.

    Limits: at most ``MAX_REQUESTS`` logical requests; before each, the run's spend plus a
    worst-case reservation must stay within ``RUN_CREDIT_CAP``; and the daily guard in
    ``config/budget.yml`` (with today's logged usage) must allow it.
    """

    def __init__(
        self,
        *,
        usage_log: Path,
        raw_dir: Path,
        now: datetime,
        budget_path: Path = DEFAULT_BUDGET,
        env_path: Path = DEFAULT_ENV,
    ) -> None:
        # No caller cap here: the 60-credit cap is this run's own limit, and the daily
        # ceilings in config/budget.yml must not shrink to it.
        self.budget = resolve_openalex_budget(budget_path)
        self.prior_cost, self.prior_credits = daily_logged_usage(
            usage_log, cost_per_credit_usd=self.budget.cost_per_credit_usd
        )
        load_openalex_key(env_path)
        self.raw_dir = raw_dir
        self.requests = 0
        self.spent_credits = Decimal(0)
        self.spent_cost = Decimal(0)
        self._charged = 0
        self.logger = ApiCostLogger("global-counts-" + now.isoformat(), usage_log)

    def close(self) -> None:
        self.logger.close()

    def _check_before_request(self) -> None:
        if self.requests >= MAX_REQUESTS:
            raise FetchError(f"request cap of {MAX_REQUESTS} reached")
        if self.spent_credits + WORST_CASE_CREDITS > RUN_CREDIT_CAP:
            raise FetchError(
                f"run credit cap: {self.spent_credits} credits spent and the next request "
                f"could take the run past {RUN_CREDIT_CAP}"
            )
        error = self.budget.reserve_error(
            cost_usd=self.prior_cost + self.spent_cost,
            credits=self.prior_credits + self.spent_credits,
        )
        if error:
            raise FetchError(f"budget guard: {error}")

    def _charge(self) -> None:
        """Add the attempts logged since the last charge to this run's spend."""

        metrics = self.logger.request_metrics
        for metric in metrics[self._charged :]:
            credits = (
                Decimal(str(metric["credits"]))
                if metric["credits_known"] is True
                else ATTEMPT_CREDITS
            )
            metadata_cost = (
                Decimal(str(metric["cost_usd"])) if metric["cost_known"] is True else Decimal(0)
            )
            self.spent_credits += credits
            self.spent_cost += max(metadata_cost, credits * self.budget.cost_per_credit_usd)
        self._charged = len(metrics)

    def get(self, url: str, label: str) -> dict[str, Any]:
        """One logical request through the shared OpenAlex path, saved under ``label``."""

        self._check_before_request()
        self.requests += 1
        try:
            body = _request_json(url, logger=self.logger, attempts=MAX_HTTP_ATTEMPTS)
        except Exception as exc:  # OpenAlex, usage-metadata and network errors
            raise FetchError(f"OpenAlex request failed: {exc}") from exc
        finally:
            self._charge()
        write_json(self.raw_dir / f"{label}.json", body)
        error = self.budget.actual_error(
            cost_usd=self.prior_cost + self.spent_cost,
            credits=self.prior_credits + self.spent_credits,
        )
        if error:
            raise FetchError(f"budget guard: {error}")
        if self.spent_credits > RUN_CREDIT_CAP:
            raise FetchError(f"run credit cap exceeded: {self.spent_credits} credits spent")
        return body

    def window_counts(self, config: Mapping[str, Any], window: Window) -> WindowResult:
        """Country counts and the works total for one window, from its single group_by."""

        body = self.get(build_url(config, window), window.name)
        counts, skipped = country_counts(body)
        if skipped:
            print(
                f"warning: {window.name}: ignored non-country keys {sorted(skipped)}",
                file=sys.stderr,
            )
        groups = body.get("group_by") or []
        return WindowResult(
            counts=counts,
            works=works_total(body),
            truncated=len(groups) >= GROUP_LIMIT,
        )


def collect(config: Mapping[str, Any], run: BudgetedRun, now: datetime) -> dict[str, WindowResult]:
    """Run the three windows in order and return their results by window name."""

    return {window.name: run.window_counts(config, window) for window in windows(now)}


def sorted_counts(counts: Mapping[str, int]) -> dict[str, int]:
    return {code: counts[code] for code in sorted(counts)}


def build_payload(
    version: str, now: datetime, results: Mapping[str, WindowResult]
) -> dict[str, Any]:
    """The global_counts.json payload. Countries with zero works are absent, not zero.

    ``countries_with_works`` counts the countries in the total window. If that window is in
    ``truncated_windows`` it is a lower bound, because OpenAlex stopped at 200 countries.
    """

    total = results["total_by_country"]
    week = results["new_this_week_by_country"]
    if not total.counts:
        raise FetchError("OpenAlex returned no country groups")
    return {
        "query_version": version,
        "fetched_at": now.isoformat(timespec="seconds"),
        "source": SOURCE,
        "total_by_country": sorted_counts(total.counts),
        "recent_5y_by_country": sorted_counts(results["recent_5y_by_country"].counts),
        "new_this_week_by_country": sorted_counts(week.counts),
        "countries_with_works": len(total.counts),
        "truncated_windows": [name for name, result in results.items() if result.truncated],
        "totals": {"works_all": total.works, "works_week": week.works},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--usage-log", type=Path, default=DEFAULT_USAGE_LOG)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--force", action="store_true", help="refetch even when cached")
    parser.add_argument("--dry-run", action="store_true", help="print the URLs and stop")
    args = parser.parse_args(argv)

    config = load_query_config(args.config)
    version = str(config.get("version") or "")
    if not version:
        print("query config has no version", file=sys.stderr)
        return 1
    now = datetime.now(UTC)
    try:
        planned = [(window, build_url(config, window)) for window in windows(now)]
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    fresh = is_fresh(load_cache(args.output), version, now)
    if args.dry_run:
        for window, url in planned:
            print(f"{window.name}: {redact(url)}")
        print(f"query_version={version} cache={'fresh' if fresh else 'stale'} (no call made)")
        return 0
    if fresh and not args.force:
        print("cached")
        return 0

    run: BudgetedRun | None = None
    try:
        run = BudgetedRun(usage_log=args.usage_log, raw_dir=args.raw_dir, now=now)
        payload = build_payload(version, now, collect(config, run, now))
    except (FetchError, ValueError) as exc:
        print(f"error: {exc}; no file written", file=sys.stderr)
        return 1
    finally:
        if run is not None:
            run.close()
    write_json(args.output, payload)
    truncated = ", ".join(payload["truncated_windows"]) or "none"
    print(
        f"wrote {args.output.name}: {payload['countries_with_works']} countries, "
        f"{payload['totals']['works_all']} works, truncated: {truncated}, "
        f"{run.spent_credits} credits spent, {run.requests} requests"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
