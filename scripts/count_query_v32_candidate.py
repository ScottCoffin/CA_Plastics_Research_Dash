"""BQ-S2 count requests for the candidate plastic-v3.2 query (A3 sections 5.8 and 5.9; owner A3-C1).

One count request per theme (title_and_abstract), one per title-only theme (title.search), the v3.1
baseline, the combined expression when its URL fits (otherwise the split parts), and theme AND NOT
v3.1 where the URL fits. Count requests are never OR-split. Over-5-operator requests are throttled,
not refused, so operator counts are reported and not capped.

Live requests go through the shared path of scripts/fetch_denominator_series.py (Budgeted: budget
guard, ApiCostLogger, _request_json). The run is capped at 400 credits. Counts are cached under
data/interim/query_v32/ (ignored) and written to docs/api_notes/query_v32_counts.json.

    py -3.14 scripts/count_query_v32_candidate.py --dry-run            # URLs, lengths; no network
    py -3.14 scripts/count_query_v32_candidate.py --offline            # cached counts only
    py -3.14 scripts/count_query_v32_candidate.py                      # live (uses cache first)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.ingest.openalex import (  # noqa: E402
    OpenAlexPlanError,
    OpenAlexRateLimitError,
    _request_json,
)
from atlas.query import (  # noqa: E402
    QueryCacheError,
    load_query_config,
    read_count_cache,
    write_count_cache,
)
from atlas.query_v32 import Plan, load_candidate, plan  # noqa: E402
from atlas.util.cost import ApiCostLogger  # noqa: E402

CREDIT_CAP = Decimal(400)
DEFAULT_CONFIG = ROOT / "config" / "queries_v32_candidate.yml"
DEFAULT_V31 = ROOT / "config" / "queries.yml"
DEFAULT_CACHE_DIR = ROOT / "data" / "interim" / "query_v32"
DEFAULT_OUTPUT = ROOT / "docs" / "api_notes" / "query_v32_counts.json"
DEFAULT_BUDGET = ROOT / "config" / "budget.yml"
DEFAULT_USAGE_LOG = ROOT / "data" / "logs" / "api_usage.jsonl"
DEFAULT_ENV = ROOT / ".env"


def _load_denominator_module() -> Any:
    """The shared OpenAlex request path lives in fetch_denominator_series.py (Budgeted)."""

    spec = importlib.util.spec_from_file_location(
        "fetch_denominator_series", ROOT / "scripts" / "fetch_denominator_series.py"
    )
    if spec is None or spec.loader is None:
        raise ImportError("cannot load scripts/fetch_denominator_series.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses needs the module registered
    spec.loader.exec_module(module)
    return module


fds = _load_denominator_module()


class CountError(RuntimeError):
    """A count request could not be completed."""


class CountRun(fds.Budgeted):
    """Budgeted count requests with this script's 400-credit cap and usage label."""

    def __init__(
        self, *, usage_log: Path, budget_path: Path, env_path: Path, now: datetime
    ) -> None:
        super().__init__(usage_log=usage_log, budget_path=budget_path, env_path=env_path, now=now)
        self.logger.close()
        self.logger = ApiCostLogger("query-v32-" + now.isoformat(), usage_log)

    def _check_before_request(self) -> None:
        worst_case = fds.ATTEMPT_CREDITS * fds.MAX_HTTP_ATTEMPTS
        if self.spent_credits + worst_case > CREDIT_CAP:
            raise fds.RefusedError(
                f"run credit cap of {CREDIT_CAP}: {self.spent_credits} credits spent"
            )
        error = self.budget.reserve_error(
            cost_usd=self.prior_cost + self.spent_cost,
            credits=self.prior_credits + self.spent_credits,
        )
        if error:
            raise fds.RefusedError(f"budget guard: {error}")

    def count_total(self, url: str) -> int:
        """meta.count of one count request (per_page=1), budgeted like the denominator series."""

        self._check_before_request()
        self.requests += 1
        try:
            body = _request_json(url, logger=self.logger, attempts=fds.MAX_HTTP_ATTEMPTS)
        except (OpenAlexRateLimitError, OpenAlexPlanError) as exc:
            raise fds.RefusedError(f"OpenAlex refused the request: {exc}") from exc
        except Exception as exc:  # OpenAlex, usage-metadata and network errors
            raise CountError(f"OpenAlex request failed: {exc}") from exc
        finally:
            self._charge()
        error = self.budget.actual_error(
            cost_usd=self.prior_cost + self.spent_cost,
            credits=self.prior_credits + self.spent_credits,
        )
        if error:
            raise fds.RefusedError(f"budget guard: {error}")
        if self.spent_credits > CREDIT_CAP:
            raise fds.RefusedError(f"run credit cap exceeded: {self.spent_credits} credits spent")
        count = body.get("meta", {}).get("count")
        if not isinstance(count, int) or count < 0:
            raise CountError("OpenAlex response has no meta.count")
        return count


def slug(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", label).strip("_") + ".json"


def print_dry_run(query_plan: Plan) -> None:
    print(f"combined expression: {query_plan.combined_length} characters (limit 8000)")
    for request in query_plan.requests():
        print(f"{request.label}: {request.length} characters; {request.operators} operators")
        print(request.url)
    for theme, length in query_plan.skipped_incremental:
        print(f"skipped incremental:{theme}: {length} characters (over 8000; not requested)")
    print("no call made")


def collect_counts(
    query_plan: Plan,
    config: dict[str, Any],
    *,
    cache_dir: Path,
    offline: bool,
    force: bool,
    run_args: dict[str, Any],
) -> tuple[list[dict[str, Any]], Decimal, list[str]]:
    """Return one record per request, the credits spent, and the labels still missing."""

    records: list[dict[str, Any]] = []
    missing: list[str] = []
    run: CountRun | None = None
    now = datetime.now(UTC)
    for request in query_plan.requests():
        path = cache_dir / slug(request.label)
        record: dict[str, Any] = {
            "label": request.label,
            "kind": request.kind,
            "field": request.field,
            "url_length": request.length,
            "operators": request.operators,
            "rendered_query": request.expression,
            "count": None,
            "source": None,
        }
        cached = None
        if not force:
            try:
                cached = read_count_cache(
                    path,
                    query_version=config["version"],
                    rendered_query=request.expression,
                )
            except QueryCacheError:
                cached = None
        if cached is not None:
            record.update(count=cached["count"], source="cache", timestamp=cached["timestamp_utc"])
        elif offline:
            missing.append(request.label)
        else:
            if run is None:
                run = CountRun(now=now, **run_args)
            try:
                count = run.count_total(request.url)
            except (fds.FetchError, CountError) as exc:
                # A refusal or failure stops the run; every request not yet counted is missing.
                index = [r.label for r in query_plan.requests()].index(request.label)
                missing.extend(r.label for r in query_plan.requests()[index:])
                print(f"stopped at {request.label}: {exc}", file=sys.stderr)
                break
            payload = write_count_cache(
                path,
                config=config,
                rendered_query=request.expression,
                count=count,
                usage={"credits_spent_run": str(run.spent_credits)},
            )
            record.update(count=count, source="live", timestamp=payload["timestamp_utc"])
        records.append(record)
    spent = run.spent_credits if run is not None else Decimal(0)
    if run is not None:
        run.close()
    return records, spent, missing


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--v31", type=Path, default=DEFAULT_V31)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--budget", type=Path, default=DEFAULT_BUDGET)
    parser.add_argument("--usage-log", type=Path, default=DEFAULT_USAGE_LOG)
    parser.add_argument("--dry-run", action="store_true", help="print the URLs and stop")
    parser.add_argument("--offline", action="store_true", help="use cached counts only; no network")
    parser.add_argument("--force", action="store_true", help="ignore the cache and recount")
    args = parser.parse_args(argv)

    try:
        config = load_candidate(str(args.config))
        v31 = load_query_config(str(args.v31))
        query_plan = plan(config, v31)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print_dry_run(query_plan)
        return 0

    now = datetime.now(UTC)
    records, spent, missing = collect_counts(
        query_plan,
        config,
        cache_dir=args.cache_dir,
        offline=args.offline,
        force=args.force,
        run_args={
            "usage_log": args.usage_log,
            "budget_path": args.budget,
            "env_path": DEFAULT_ENV,
        },
    )
    payload = {
        "query_version": config["version"],
        "v31_version": v31["version"],
        "generated_at": now.isoformat(timespec="seconds"),
        "source": "OpenAlex works meta.count (per_page=1)",
        "credit_cap": str(CREDIT_CAP),
        "credits_spent_this_run": str(spent),
        "skipped_incremental": [
            {"theme": theme, "url_length": length}
            for theme, length in query_plan.skipped_incremental
        ],
        "requests": records,
    }
    if missing:
        print("missing counts: " + "; ".join(missing), file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wrote {args.output.name}: {len(records)} requests; {spent} credits this run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
