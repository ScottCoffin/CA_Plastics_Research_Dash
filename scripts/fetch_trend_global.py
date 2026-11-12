"""Global works per publication year under the active plastics query (EM-7, V-4 trend panel).

The CA share in the Evidence Map trend panel divides California-connected corpus works by
the global count this script writes to ``site/data/trend_global.json``. One ``group_by``
request per run; the file is cached by query version and refreshed after 30 days.

Usage:
    py -3.14 scripts/fetch_trend_global.py --dry-run     # print the redacted URL, no call
    py -3.14 scripts/fetch_trend_global.py               # cached unless stale or version changed
    py -3.14 scripts/fetch_trend_global.py --force       # refetch regardless of cache
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from datetime import UTC, datetime, timedelta
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
from atlas.util.budget import daily_logged_usage, resolve_openalex_budget  # noqa: E402
from atlas.util.cost import ApiCostLogger  # noqa: E402

SCHEMA_VERSION = "em7.v1"
SOURCE = "OpenAlex group_by publication_year"
MAX_AGE = timedelta(days=30)
# One logical request; _request_json's attempts cap keeps retries inside this budget.
MAX_HTTP_ATTEMPTS = 3
MAX_URL_CHARS = 8000
DEFAULT_OUTPUT = ROOT / "site" / "data" / "trend_global.json"
DEFAULT_CONFIG = ROOT / "config" / "queries.yml"
DEFAULT_USAGE_LOG = ROOT / "data" / "logs" / "api_usage.jsonl"


class FetchError(RuntimeError):
    """A request or validation failure: nothing is written."""


def build_url(config: dict[str, Any]) -> str:
    """Active query filter (with exclusions and type exclusions) grouped by year."""

    filters = [openalex_filter(config), *type_filters(config)]
    params = {"filter": ",".join(filters), "group_by": "publication_year"}
    url = f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"
    if len(url) > MAX_URL_CHARS:
        raise FetchError(f"request URL is {len(url)} characters; limit is {MAX_URL_CHARS}")
    return url


def redact(url: str) -> str:
    """Hide any API key that might appear in a query string before printing."""

    return re.sub(r"(api_key=)[^&]+", r"\1REDACTED", url)


def works_by_year(body: dict[str, Any]) -> dict[int, int]:
    """``{year: works}`` from a ``group_by=publication_year`` response."""

    out: dict[int, int] = {}
    for group in body.get("group_by") or []:
        try:
            year = int(str(group.get("key")))
        except ValueError:
            continue
        out[year] = out.get(year, 0) + int(group.get("count") or 0)
    return out


def load_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return cache if isinstance(cache, dict) else None


def is_fresh(cache: dict[str, Any] | None, version: str, now: datetime) -> bool:
    """True when the cached file has this query version and is under 30 days old."""

    if not cache or cache.get("query_version") != version:
        return False
    try:
        fetched = datetime.fromisoformat(str(cache.get("fetched_at")))
    except ValueError:
        return False
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=UTC)
    return now - fetched < MAX_AGE


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomic write with LF line endings and a trailing newline."""

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


def fetch(url: str, usage_log: Path) -> dict[str, Any]:
    """Run the single budgeted request through the shared OpenAlex request path."""

    budget = resolve_openalex_budget()
    prior_cost, prior_credits = daily_logged_usage(
        usage_log, cost_per_credit_usd=budget.cost_per_credit_usd
    )
    error = budget.reserve_error(cost_usd=prior_cost, credits=prior_credits)
    if error:
        raise FetchError(f"budget guard: {error}")
    load_openalex_key()
    try:
        with ApiCostLogger("trend-global-" + datetime.now(UTC).isoformat(), usage_log) as logger:
            return _request_json(url, logger=logger, attempts=MAX_HTTP_ATTEMPTS)
    except Exception as exc:  # OpenAlex errors, usage-metadata errors, network errors
        raise FetchError(f"OpenAlex request failed: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--usage-log", type=Path, default=DEFAULT_USAGE_LOG)
    parser.add_argument("--force", action="store_true", help="refetch even when cached")
    parser.add_argument("--dry-run", action="store_true", help="print the URL and stop")
    args = parser.parse_args(argv)

    config = load_query_config(args.config)
    version = str(config.get("version") or "")
    if not version:
        print("query config has no version", file=sys.stderr)
        return 1
    now = datetime.now(UTC)
    try:
        url = build_url(config)
    except FetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    fresh = is_fresh(load_cache(args.output), version, now)
    if args.dry_run:
        print(redact(url))
        print(f"query_version={version} cache={'fresh' if fresh else 'stale'} (no call made)")
        return 0
    if fresh and not args.force:
        print("cached")
        return 0

    try:
        counts = works_by_year(fetch(url, args.usage_log))
    except FetchError as exc:
        print(f"error: {exc}; no file written", file=sys.stderr)
        return 1
    if not counts:
        print("error: OpenAlex returned no publication years; no file written", file=sys.stderr)
        return 1
    payload = {
        "schema_version": SCHEMA_VERSION,
        "query_version": version,
        "fetched_at": now.isoformat(timespec="seconds"),
        "source": SOURCE,
        "by_year": {str(year): counts[year] for year in sorted(counts)},
    }
    write_json(args.output, payload)
    print(f"wrote {args.output.name}: {len(counts)} years, {sum(counts.values())} works")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
