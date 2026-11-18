"""Global works per evidence-map cell (PLAT-2b landing grid): one OpenAlex count per cell.

``config/evidence_cells.yml`` defines 5 rows x 6 columns. Each cell is one ``per-page=1``
count whose filter is the active query AND the row terms AND the column terms, plus the
query's type exclusions. OR lists are never split across requests (split counts cannot be
summed, A3-C1). The grid is written to ``site/data/global/evidence_cells.json`` and cached for
20 hours by query and cell-config version. A budget stop or any failed cell writes nothing.

Usage:
    py -3.14 scripts/fetch_evidence_cells.py --dry-run     # first URL and count; no call
    py -3.14 scripts/fetch_evidence_cells.py               # cached unless stale or changed
    py -3.14 scripts/fetch_evidence_cells.py --force       # refetch regardless of cache
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.ingest.openalex import (  # noqa: E402
    OPENALEX_BASE,
    _request_json,
    load_openalex_key,
)
from atlas.query import _term, load_query_config, render_query, type_filters  # noqa: E402
from atlas.util.budget import (  # noqa: E402
    UNKNOWN_429_CREDITS,
    daily_logged_usage,
    resolve_openalex_budget,
)
from atlas.util.cost import ApiCostLogger  # noqa: E402

SCHEMA_VERSION = "plat2b.v1"
SOURCE = "OpenAlex works count per cell (title and abstract search, active plastics query)"
NOTE = "Search hits, not classified works; a work can count in several cells."
ROW_IDS = ("occurrence", "effects", "methods", "fate_transport", "solutions")
COLUMN_IDS = ("ocean", "freshwater", "soil", "air", "food_biota", "people")
DEFAULT_FIELD = "title_and_abstract.search"
# The landing grid is refreshed daily; a version change refetches at once.
MAX_AGE = timedelta(hours=20)
# One logical request is at most this many HTTP attempts through the shared request path.
MAX_HTTP_ATTEMPTS = 3
MAX_URL_CHARS = 8000
# One count per cell, so the run never sends more than the grid has.
MAX_REQUESTS = len(ROW_IDS) * len(COLUMN_IDS)
# A search-filter count costs 10 credits (measured 2026-11-09); each call reserves one attempt.
ATTEMPT_CREDITS = UNKNOWN_429_CREDITS
# 30 cells x 10 credits is about 300. The extra 30 leaves room for a few retried attempts.
RUN_CREDIT_CAP = Decimal(330)
DEFAULT_OUTPUT = ROOT / "site" / "data" / "global" / "evidence_cells.json"
DEFAULT_CONFIG = ROOT / "config" / "queries.yml"
DEFAULT_CELLS = ROOT / "config" / "evidence_cells.yml"
DEFAULT_BUDGET = ROOT / "config" / "budget.yml"
DEFAULT_USAGE_LOG = ROOT / "data" / "logs" / "api_usage.jsonl"
DEFAULT_ENV = ROOT / ".env"


class FetchError(RuntimeError):
    """A request, budget or validation failure: nothing is written."""


def _non_empty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _axis(raw: Mapping[str, Any], key: str, expected: tuple[str, ...]) -> list[dict[str, Any]]:
    """Check one axis (``rows`` or ``columns``) of evidence_cells.yml and return its entries."""

    entries = raw.get(key)
    if not isinstance(entries, list):
        raise ValueError(f"evidence cells: {key} must be a list")
    ids: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"evidence cells: each {key} entry must be a mapping")
        for field in ("id", "label", "short"):
            if not _non_empty_text(entry.get(field)):
                raise ValueError(f"evidence cells: a {key} entry has no {field}")
        terms = entry.get("terms")
        if not isinstance(terms, list) or not terms or not all(_non_empty_text(t) for t in terms):
            raise ValueError(f"evidence cells: {entry['id']} needs a non-empty list of terms")
        ids.append(entry["id"])
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise ValueError(f"evidence cells: duplicate {key} ids {duplicates}")
    missing = sorted(set(expected) - set(ids))
    unexpected = sorted(set(ids) - set(expected))
    if missing or unexpected:
        raise ValueError(
            f"evidence cells: {key} must be exactly {list(expected)}; "
            f"missing {missing}, unexpected {unexpected}"
        )
    return entries


def load_cells_config(path: Path) -> dict[str, Any]:
    """Load evidence_cells.yml and check its ids and terms; ValueError on the first problem."""

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("evidence cells: the config must be a mapping")
    if not _non_empty_text(raw.get("version")):
        raise ValueError("evidence cells: version must be a non-empty string")
    gap = raw.get("gap_share")
    if isinstance(gap, bool) or not isinstance(gap, (int, float)) or not 0 <= gap < 1:
        raise ValueError("evidence cells: gap_share must be a number from 0 up to 1")
    return {
        **raw,
        "rows": _axis(raw, "rows", ROW_IDS),
        "columns": _axis(raw, "columns", COLUMN_IDS),
    }


def cell_url(
    config: Mapping[str, Any], row_terms: Sequence[str], column_terms: Sequence[str]
) -> str:
    """One count request: active query AND row terms AND column terms, plus type exclusions."""

    field = config.get("openalex", {}).get("field", DEFAULT_FIELD)
    row = " OR ".join(_term(term) for term in row_terms)
    column = " OR ".join(_term(term) for term in column_terms)
    # render_query is already parenthesised and may end in " NOT (...)", so wrap it once more.
    cell = f"{field}:({render_query(config)}) AND ({row}) AND ({column})"
    filters = [cell, *type_filters(config)]
    params = {"filter": ",".join(filters), "per-page": "1", "select": "id"}
    url = f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"
    if len(url) > MAX_URL_CHARS:
        raise FetchError(f"cell URL is {len(url)} characters; limit is {MAX_URL_CHARS}")
    return url


def cell_urls(config: Mapping[str, Any], cells: Mapping[str, Any]) -> list[list[str]]:
    """The 5 x 6 grid of count URLs, rows then columns in config order."""

    return [
        [cell_url(config, row["terms"], column["terms"]) for column in cells["columns"]]
        for row in cells["rows"]
    ]


def redact(url: str) -> str:
    """Hide any API key that might appear in a query string before printing."""

    return re.sub(r"(api_key=)[^&]+", r"\1REDACTED", url)


def works_count(body: Mapping[str, Any]) -> int:
    """The cell's works total from ``meta.count`` (``per-page=1`` returns the count, not rows)."""

    count = (body.get("meta") or {}).get("count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise FetchError("cell response has no non-negative integer meta.count")
    return count


def load_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return cache if isinstance(cache, dict) else None


def is_fresh(
    cache: Mapping[str, Any] | None, *, query_version: str, cells_version: str, now: datetime
) -> bool:
    """True when the cached grid has both versions and is under 20 hours old."""

    if not cache or cache.get("query_version") != query_version:
        return False
    if cache.get("cells_version") != cells_version:
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


class BudgetedCells:
    """Sends the cell counts one at a time and enforces every limit before each one.

    Limits: at most ``MAX_REQUESTS`` requests; before each, the run's spend plus one attempt's
    reserve must stay within ``RUN_CREDIT_CAP``; and the daily guard in ``config/budget.yml``
    (with today's logged usage) must allow it. Each request is checked again after its response.
    """

    def __init__(
        self,
        *,
        usage_log: Path,
        now: datetime,
        budget_path: Path = DEFAULT_BUDGET,
        env_path: Path = DEFAULT_ENV,
    ) -> None:
        self.budget = resolve_openalex_budget(budget_path)
        self.prior_cost, self.prior_credits = daily_logged_usage(
            usage_log, cost_per_credit_usd=self.budget.cost_per_credit_usd
        )
        load_openalex_key(env_path)
        self.requests = 0
        self.spent_credits = Decimal(0)
        self.spent_cost = Decimal(0)
        self._charged = 0
        self.logger = ApiCostLogger("evidence-cells-" + now.isoformat(), usage_log)

    def close(self) -> None:
        self.logger.close()

    def _check_before_request(self) -> None:
        if self.requests >= MAX_REQUESTS:
            raise FetchError(f"request cap of {MAX_REQUESTS} reached")
        if self.spent_credits + ATTEMPT_CREDITS > RUN_CREDIT_CAP:
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

    def count(self, url: str) -> int:
        """One cell's works count through the shared OpenAlex request path."""

        self._check_before_request()
        self.requests += 1
        try:
            body = _request_json(url, logger=self.logger, attempts=MAX_HTTP_ATTEMPTS)
        except Exception as exc:  # OpenAlex, usage-metadata and network errors
            raise FetchError(f"OpenAlex request failed: {exc}") from exc
        finally:
            self._charge()
        error = self.budget.actual_error(
            cost_usd=self.prior_cost + self.spent_cost,
            credits=self.prior_credits + self.spent_credits,
        )
        if error:
            raise FetchError(f"budget guard: {error}")
        if self.spent_credits > RUN_CREDIT_CAP:
            raise FetchError(f"run credit cap exceeded: {self.spent_credits} credits spent")
        return works_count(body)


def _axis_entry(entry: Mapping[str, Any]) -> dict[str, str]:
    return {"id": entry["id"], "label": entry["label"], "short": entry["short"]}


def build_payload(
    query_version: str,
    cells: Mapping[str, Any],
    now: datetime,
    counts: list[list[int]],
) -> dict[str, Any]:
    peak = max(max(row) for row in counts)
    if peak == 0:
        raise FetchError("every cell count is zero")
    return {
        "schema_version": SCHEMA_VERSION,
        "query_version": query_version,
        "cells_version": cells["version"],
        "fetched_at": now.isoformat(timespec="seconds"),
        "source": SOURCE,
        "note": NOTE,
        "gap_share": cells["gap_share"],
        "rows": [_axis_entry(entry) for entry in cells["rows"]],
        "columns": [_axis_entry(entry) for entry in cells["columns"]],
        "counts": counts,
        "max": peak,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--cells", type=Path, default=DEFAULT_CELLS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--usage-log", type=Path, default=DEFAULT_USAGE_LOG)
    parser.add_argument("--budget", type=Path, default=DEFAULT_BUDGET)
    parser.add_argument("--force", action="store_true", help="refetch even when cached")
    parser.add_argument("--dry-run", action="store_true", help="print the URLs and stop")
    args = parser.parse_args(argv)

    now = datetime.now(UTC)
    try:
        config = load_query_config(args.config)
        cells = load_cells_config(args.cells)
        urls = cell_urls(config, cells)
    except (FetchError, OSError, ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    query_version = str(config["version"])
    cells_version = str(cells["version"])
    fresh = is_fresh(
        load_cache(args.output),
        query_version=query_version,
        cells_version=cells_version,
        now=now,
    )
    if args.dry_run:
        first = urls[0][0]
        total = sum(len(row) for row in urls)
        print(f"{total} cell URLs; first URL ({len(first)} characters, redacted):")
        print(redact(first))
        print(
            f"query_version={query_version} cells_version={cells_version} "
            f"cache={'fresh' if fresh else 'stale'} (no call made)"
        )
        return 0
    if fresh and not args.force:
        print("cached")
        return 0

    run: BudgetedCells | None = None
    try:
        run = BudgetedCells(usage_log=args.usage_log, now=now, budget_path=args.budget)
        counts = [[run.count(url) for url in row] for row in urls]
        payload = build_payload(query_version, cells, now, counts)
    except (FetchError, ValueError) as exc:
        print(f"error: {exc}; no file written", file=sys.stderr)
        return 1
    finally:
        if run is not None:
            run.close()
    write_json(args.output, payload)
    print(
        f"wrote {args.output.name}: {len(ROW_IDS)}x{len(COLUMN_IDS)} cells, max {payload['max']}, "
        f"{run.spent_credits} credits spent, {run.requests} requests"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
