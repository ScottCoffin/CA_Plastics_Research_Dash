"""Global-denominator series counts with a 30-day cache (BQ-2.2; A3 section 7 Module 2).

One ``group_by=publication_year`` request per series, four in all (about 40 credits):

- ``A-all`` and ``A-article_review``: the active plastics query (v3.1), all OpenAlex types, or
  types article and review only. ``A-all`` sends the same filter as fetch_trend_global.py.
- ``B-all`` and ``B-article_review``: the pollution-core v0 terms (A3 section 5.3, from
  config/pollution_core_v0.yml) with the query's exclusions, the same type filters, and the
  sensitivity clause. No qualified or lifecycle terms.

No series has a language filter (A3: 14.7% of declared-language labels were false positives;
Cespedes et al. 2025). Each request goes through the shared OpenAlex path: the budget guard,
ApiCostLogger and _request_json. Results go to data/interim/denominator_series_cache.json, keyed
by series id, query version and filter digest, and fresh for 30 days.

A refused refresh (HTTP 429, a plan refusal, or the local budget guard) never keeps the old values
silently: the cached values are marked ``stale`` with a ``stale_reason``, the run stops, and the
exit code is 1. ``--allow-stale`` exits 0 in that case when every refused series still has cached
values, which is what the daily job needs.

Usage:
    py -3.14 scripts/fetch_denominator_series.py --dry-run        # print the URLs; no call
    py -3.14 scripts/fetch_denominator_series.py                  # cached unless stale or changed
    py -3.14 scripts/fetch_denominator_series.py --force          # refetch regardless of cache
    py -3.14 scripts/fetch_denominator_series.py --allow-stale    # exit 0 on a refused refresh
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.analytics.denominators import (  # noqa: E402
    CACHE_MAX_AGE,
    CACHE_SCHEMA,
    FETCH_SERIES,
    cache_key,
    fetch_series_filters,
    filter_digest,
    load_denominator_cache,
)
from atlas.ingest.openalex import (  # noqa: E402
    OPENALEX_BASE,
    OpenAlexPlanError,
    OpenAlexRateLimitError,
    _request_json,
    load_openalex_key,
)
from atlas.query import load_query_config  # noqa: E402
from atlas.util.budget import (  # noqa: E402
    UNKNOWN_429_CREDITS,
    daily_logged_usage,
    resolve_openalex_budget,
)
from atlas.util.cost import ApiCostLogger  # noqa: E402

SOURCE = "OpenAlex group_by publication_year"
# One logical request is at most this many HTTP attempts through the shared request path.
MAX_HTTP_ATTEMPTS = 3
MAX_URL_CHARS = 8000
# A count request costs 10 credits (measured 2026-11-09). An attempt without a credit header is
# charged this amount.
ATTEMPT_CREDITS = UNKNOWN_429_CREDITS
# Four series at about 10 credits each is about 40. Before each request the run must have room for
# that request's worst case (every attempt charged), so the run total cannot pass this cap.
RUN_CREDIT_CAP = Decimal(100)
DEFAULT_CACHE = ROOT / "data" / "interim" / "denominator_series_cache.json"
DEFAULT_CONFIG = ROOT / "config" / "queries.yml"
DEFAULT_BUDGET = ROOT / "config" / "budget.yml"
DEFAULT_USAGE_LOG = ROOT / "data" / "logs" / "api_usage.jsonl"
DEFAULT_ENV = ROOT / ".env"


class FetchError(RuntimeError):
    """A request or validation failure: the run stops; series already fetched are kept."""


class RefusedError(FetchError):
    """OpenAlex refused a request (HTTP 429 or plan refusal), or the local budget guard did."""


@dataclass(frozen=True)
class SeriesRequest:
    series_id: str
    query_version: str
    digest: str
    filter_text: str
    url: str

    @property
    def key(self) -> str:
        return cache_key(self.series_id, self.query_version, self.digest)


def build_requests(config: Mapping[str, Any]) -> list[SeriesRequest]:
    """One group_by request per fetched series, in FETCH_SERIES order."""

    version = str(config.get("version") or "")
    requests = []
    for series_id in FETCH_SERIES:
        filters = fetch_series_filters(config, series_id)
        filter_text = ",".join(filters)
        params = {"filter": filter_text, "group_by": "publication_year"}
        url = f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"
        if len(url) > MAX_URL_CHARS:
            raise FetchError(
                f"{series_id}: request URL is {len(url)} characters; limit is {MAX_URL_CHARS}"
            )
        requests.append(SeriesRequest(series_id, version, filter_digest(filters), filter_text, url))
    return requests


def redact(url: str) -> str:
    """Hide any API key that might appear in a query string before printing."""

    return re.sub(r"(api_key=)[^&]+", r"\1REDACTED", url)


def works_by_year(body: Mapping[str, Any]) -> dict[int, int]:
    """``{year: works}`` from a ``group_by=publication_year`` response; other keys are dropped."""

    out: dict[int, int] = {}
    for group in body.get("group_by") or []:
        try:
            year = int(str(group.get("key")))
        except ValueError:
            continue
        out[year] = out.get(year, 0) + int(group.get("count") or 0)
    return out


def empty_cache() -> dict[str, Any]:
    return {"schema_version": CACHE_SCHEMA, "source": SOURCE, "entries": {}}


def read_cache(path: Path) -> dict[str, Any]:
    """The cache file, or an empty cache when it is missing or unreadable (then rewritten)."""

    if not path.exists():
        return empty_cache()
    try:
        return load_denominator_cache(path)
    except (OSError, ValueError) as exc:
        print(f"warning: {path.name} is unreadable ({exc}); starting an empty cache")
        return empty_cache()


def is_fresh(
    entry: Mapping[str, Any] | None, *, query_version: str, digest: str, now: datetime
) -> bool:
    """True when the entry has this query version and filter digest, is not flagged stale, and is
    under 30 days old."""

    if not entry or entry.get("stale") is True:
        return False
    if entry.get("query_version") != query_version or entry.get("filter_digest") != digest:
        return False
    try:
        fetched = datetime.fromisoformat(str(entry.get("fetched_at")))
    except ValueError:
        return False
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=UTC)
    return now - fetched < CACHE_MAX_AGE


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomic write with LF line endings and a trailing newline."""

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


class Budgeted:
    """Runs the count requests one at a time and checks every limit before and after each."""

    def __init__(
        self,
        *,
        usage_log: Path,
        budget_path: Path,
        env_path: Path,
        now: datetime,
    ) -> None:
        self.budget = resolve_openalex_budget(budget_path)
        self.prior_cost, self.prior_credits = daily_logged_usage(
            usage_log, cost_per_credit_usd=self.budget.cost_per_credit_usd
        )
        load_openalex_key(env_path)
        self.logger = ApiCostLogger("denominator-series-" + now.isoformat(), usage_log)
        self.requests = 0
        self.spent_credits = Decimal(0)
        self.spent_cost = Decimal(0)
        self._charged = 0

    def close(self) -> None:
        self.logger.close()

    def _check_before_request(self) -> None:
        worst_case = ATTEMPT_CREDITS * MAX_HTTP_ATTEMPTS
        if self.spent_credits + worst_case > RUN_CREDIT_CAP:
            raise RefusedError(
                f"run credit cap of {RUN_CREDIT_CAP}: {self.spent_credits} credits spent and the "
                "next request could take the run past it"
            )
        error = self.budget.reserve_error(
            cost_usd=self.prior_cost + self.spent_cost,
            credits=self.prior_credits + self.spent_credits,
        )
        if error:
            raise RefusedError(f"budget guard: {error}")

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

    def count_by_year(self, url: str) -> dict[int, int]:
        """One series' by-year counts through the shared OpenAlex request path."""

        self._check_before_request()
        self.requests += 1
        try:
            body = _request_json(url, logger=self.logger, attempts=MAX_HTTP_ATTEMPTS)
        except (OpenAlexRateLimitError, OpenAlexPlanError) as exc:
            raise RefusedError(f"OpenAlex refused the request: {exc}") from exc
        except Exception as exc:  # OpenAlex, usage-metadata and network errors
            raise FetchError(f"OpenAlex request failed: {exc}") from exc
        finally:
            self._charge()
        error = self.budget.actual_error(
            cost_usd=self.prior_cost + self.spent_cost,
            credits=self.prior_credits + self.spent_credits,
        )
        if error:
            raise RefusedError(f"budget guard: {error}")
        if self.spent_credits > RUN_CREDIT_CAP:
            raise RefusedError(f"run credit cap exceeded: {self.spent_credits} credits spent")
        return works_by_year(body)


def new_entry(
    request: SeriesRequest, counts: Mapping[int, int], *, now: datetime
) -> dict[str, Any]:
    return {
        "series_id": request.series_id,
        "query_version": request.query_version,
        "filter_digest": request.digest,
        "filter": request.filter_text,
        "fetched_at": now.isoformat(timespec="seconds"),
        "source": SOURCE,
        "by_year": {str(year): counts[year] for year in sorted(counts)},
        "stale": False,
        "stale_reason": None,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--budget", type=Path, default=DEFAULT_BUDGET)
    parser.add_argument("--usage-log", type=Path, default=DEFAULT_USAGE_LOG)
    parser.add_argument("--force", action="store_true", help="refetch even when cached")
    parser.add_argument(
        "--allow-stale",
        action="store_true",
        help="exit 0 when a refused refresh leaves cached values (the daily job)",
    )
    parser.add_argument("--dry-run", action="store_true", help="print the URLs and stop")
    args = parser.parse_args(argv)

    now = datetime.now(UTC)
    try:
        config = load_query_config(args.config)
        requests = build_requests(config)
    except (FetchError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    version = str(config["version"])
    cache = read_cache(args.cache)
    entries = cache["entries"]

    if args.dry_run:
        for request in requests:
            entry = entries.get(request.key)
            if entry is None:
                state = "missing"
            elif is_fresh(entry, query_version=version, digest=request.digest, now=now):
                state = "fresh"
            else:
                state = "stale"
            print(f"{request.series_id}: {len(request.url)} characters; cache {state}")
            print(redact(request.url))
        print("no call made")
        return 0

    refreshed: set[str] = set()
    changed = False
    stop: tuple[str, str] | None = None  # ("refused" or "failed", message)
    run: Budgeted | None = None
    current = requests[0].series_id
    try:
        for request in requests:
            current = request.series_id
            entry = entries.get(request.key)
            if not args.force and is_fresh(
                entry, query_version=version, digest=request.digest, now=now
            ):
                print(f"{request.series_id}: cached (fetched {entry['fetched_at']})")
                continue
            if run is None:
                run = Budgeted(
                    usage_log=args.usage_log,
                    budget_path=args.budget,
                    env_path=DEFAULT_ENV,
                    now=now,
                )
            counts = run.count_by_year(request.url)
            if not counts:
                raise FetchError("OpenAlex returned no publication years")
            entries[request.key] = new_entry(request, counts, now=now)
            refreshed.add(request.series_id)
            changed = True
            print(
                f"{request.series_id}: fetched {len(counts)} years, {sum(counts.values())} records"
            )
    except RefusedError as exc:
        stop = ("refused", f"{current}: {exc}")
    except (FetchError, OSError, ValueError) as exc:
        stop = ("failed", f"{current}: {exc}")
    finally:
        if run is not None:
            run.close()

    # Every series that was not refreshed and has no current fresh entry is marked stale (its
    # values are kept but flagged) or, with no entry at all, listed as missing.
    reason = stop[1] if stop else "not refreshed in this run"
    missing: list[str] = []
    stale_ids: list[str] = []
    for request in requests:
        if request.series_id in refreshed:
            continue
        entry = entries.get(request.key)
        if (
            entry is not None
            and not args.force
            and is_fresh(entry, query_version=version, digest=request.digest, now=now)
        ):
            continue
        if entry is None:
            missing.append(request.series_id)
            continue
        entry["stale"] = True
        entry["stale_reason"] = reason
        entry["refused_at"] = now.isoformat(timespec="seconds")
        stale_ids.append(request.series_id)
        changed = True

    if changed:
        try:
            write_json(args.cache, {**cache, "entries": entries})
        except OSError as exc:
            print(f"error: cannot write {args.cache.name}: {exc}", file=sys.stderr)
            return 1
    if run is not None:
        print(f"{run.requests} requests, {run.spent_credits} credits spent this run")
    if stop and stop[0] == "failed":
        print(
            f"error: {stop[1]}; refreshed: {', '.join(sorted(refreshed)) or 'none'}; "
            f"marked stale: {', '.join(stale_ids) or 'none'}",
            file=sys.stderr,
        )
        return 1
    if missing:
        print(
            f"error: no cached values for {', '.join(missing)}; nothing to serve",
            file=sys.stderr,
        )
        return 1
    if stop:
        detail = (
            f"OpenAlex refused a refresh ({stop[1]}); cached values marked stale: "
            f"{', '.join(stale_ids) or 'none'}"
        )
        if args.allow_stale:
            print(f"warning: {detail}; exiting 0 (--allow-stale)", file=sys.stderr)
            return 0
        print(f"error: {detail}", file=sys.stderr)
        return 1
    if changed:
        kept = len(requests) - len(refreshed)
        print(f"wrote {args.cache.name}: {len(refreshed)} refreshed, {kept} kept")
    else:
        print("cache current; nothing written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
