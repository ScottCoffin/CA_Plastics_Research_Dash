"""Real OpenAlex sample for the Global explore page: ``site/data/global/explore_sample.json``.

Ported from the GA-1 design prototype (``.impeccable/sketches/src/fetch_global_app_sample.py``).
One budget-guarded group_by or list request per (scope, facet) under the active plastics query,
sent through ``scripts/build_global_counts.py``'s ``BudgetedRun`` (daily ceilings in
``config/budget.yml``; usage logged to ``data/logs/api_usage.jsonl``). A search-filter request
costs 10 credits, so a full refresh is 35 requests and about 350 credits.

Scopes: world, US, CN and NO (authors, institutions, topics, years, co-author countries and the
12 newest works), plus co-author countries for the 15 largest countries by total works that are
not US, CN or NO (ranked in ``global_counts.json``).

Raw responses are kept under ``data/raw/global_explore_sample/<UTC date>/`` (git-ignored). Only
today's folder is reused, so a rerun on the same UTC day, or after a partial failure, sends only
the missing requests, and a complete folder costs nothing. The output is skipped while it is under
seven days old and has the current query version; ``--force`` overrides that skip.

Usage:
    py -3.14 scripts/fetch_global_explore_sample.py --dry-run  # plan and credit estimate, no call
    py -3.14 scripts/fetch_global_explore_sample.py            # cached unless stale
    py -3.14 scripts/fetch_global_explore_sample.py --force    # rebuild from today's raw files
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_global_counts as g  # noqa: E402

RAW_ROOT = ROOT / "data" / "raw" / "global_explore_sample"
OUTPUT = ROOT / "site" / "data" / "global" / "explore_sample.json"
COUNTS = ROOT / "site" / "data" / "global" / "global_counts.json"

# Profiles drawn in full; the network adds co-author countries for the top countries.
PROFILE_SCOPES = ["US", "CN", "NO"]
NETWORK_TOP = 15
# A search-filter request costs 10 credits (measured 2026-11-09).
CREDITS_PER_REQUEST = 10
FACETS = {
    "authors": ("authorships.author.id", 25),
    "institutions": ("authorships.institutions.id", 25),
    "topics": ("primary_topic.id", 25),
    "years": ("publication_year", 200),
    "countries": ("authorships.countries", 200),
}
RECENT_SELECT = "id,doi,display_name,publication_date,primary_location,authorships"
RECENT_PER_PAGE = 12


def base_filters(config: Mapping[str, Any], scope: str | None) -> list[str]:
    filters = [g.openalex_filter(config), *g.type_filters(config)]
    if scope:
        filters.append(f"authorships.countries:{scope}")
    return filters


def _works_url(params: Mapping[str, Any]) -> str:
    return f"{g.OPENALEX_BASE}/works?{urllib.parse.urlencode(params, safe=':,|')}"


def group_url(config: Mapping[str, Any], scope: str | None, facet: str) -> str:
    field, per_page = FACETS[facet]
    params = {
        "filter": ",".join(base_filters(config, scope)),
        "group_by": field,
        "per_page": per_page,
    }
    return _works_url(params)


def recent_url(config: Mapping[str, Any], scope: str | None, now: datetime) -> str:
    yesterday = (now - timedelta(days=1)).date().isoformat()
    filters = [*base_filters(config, scope), f"to_publication_date:{yesterday}"]
    params = {
        "filter": ",".join(filters),
        "sort": "publication_date:desc",
        "per_page": RECENT_PER_PAGE,
        "select": RECENT_SELECT,
    }
    return _works_url(params)


def plan(
    config: Mapping[str, Any], counts: Mapping[str, int], now: datetime
) -> list[tuple[str, str]]:
    """(label, URL) for each request in the prototype's order: world, the profiles, co-authors.

    ``counts`` is ``total_by_country``; the co-author lists go to its 15 largest codes that are
    not profile scopes. Ties are ordered by code, so the plan is deterministic.
    """

    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top = [code for code, _ in ranked[:NETWORK_TOP]]
    jobs = [
        (f"world_{f}", group_url(config, None, f)) for f in ("authors", "institutions", "topics")
    ]
    jobs.append(("world_recent", recent_url(config, None, now)))
    for scope in PROFILE_SCOPES:
        jobs += [(f"{scope}_{f}", group_url(config, scope, f)) for f in FACETS]
        jobs.append((f"{scope}_recent", recent_url(config, scope, now)))
    jobs += [
        (f"{c}_countries", group_url(config, c, "countries"))
        for c in top
        if c not in PROFILE_SCOPES
    ]
    return jobs


def groups(body: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "key": str(x.get("key", "")).rsplit("/", 1)[-1],
            "name": x.get("key_display_name"),
            "count": x.get("count"),
        }
        for x in body.get("group_by") or []
    ]


def slim_work(w: Mapping[str, Any]) -> dict[str, Any]:
    src = ((w.get("primary_location") or {}).get("source") or {}).get("display_name")
    auths = w.get("authorships") or []
    countries = sorted({c for a in auths for c in (a.get("countries") or [])})
    first = (auths[0].get("author") or {}).get("display_name") if auths else None
    return {
        "id": str(w.get("id", "")).rsplit("/", 1)[-1],
        "doi": w.get("doi"),
        "title": w.get("display_name"),
        "date": w.get("publication_date"),
        "source": src,
        "first_author": first,
        "n_authors": len(auths),
        "countries": countries,
    }


def assemble(
    version: str | None,
    labels: Sequence[str],
    bodies: Mapping[str, Mapping[str, Any]],
    fetched_at: str,
) -> dict[str, Any]:
    """The explore_sample.json payload: ``{query_version, fetched_at, scopes}``."""

    out: dict[str, Any] = {"query_version": version, "fetched_at": fetched_at, "scopes": {}}
    for label in labels:
        body = bodies[label]
        scope, facet = label.split("_", 1)
        entry = out["scopes"].setdefault(scope, {})
        entry.setdefault("works", (body.get("meta") or {}).get("count"))
        if facet == "recent":
            entry["recent"] = [slim_work(w) for w in body.get("results") or []]
        else:
            entry[facet] = groups(body)
    return out


def read_raw(path: Path) -> dict[str, Any]:
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise g.FetchError(f"cannot read raw file {path}: {exc}") from exc
    if not isinstance(body, dict):
        raise g.FetchError(f"raw file {path} does not hold a JSON object")
    return body


def write_compact_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomic write: compact separators, UTF-8, LF, trailing newline.

    ``build_global_counts.write_json`` pretty-prints (indent=1), so this writer is local.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


@contextmanager
def _send_limits(planned: int) -> Iterator[None]:
    """This run's own caps, as the prototype set them: the planned requests plus two spares, and
    the planned spend plus 40 credits. The shared module values are restored afterwards, so the
    limits do not leak into other runs in the same process.
    """

    saved = (g.MAX_REQUESTS, g.RUN_CREDIT_CAP)
    g.MAX_REQUESTS = planned + 2
    g.RUN_CREDIT_CAP = Decimal(planned * CREDITS_PER_REQUEST + 40)
    try:
        yield
    finally:
        g.MAX_REQUESTS, g.RUN_CREDIT_CAP = saved


def main(argv: Sequence[str] | None = None, *, now: datetime | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--counts", type=Path, default=COUNTS, help="global_counts.json")
    ap.add_argument("--output", type=Path, default=OUTPUT)
    ap.add_argument("--raw-root", type=Path, default=RAW_ROOT)
    ap.add_argument("--force", action="store_true", help="rebuild the output even when fresh")
    ap.add_argument("--dry-run", action="store_true", help="print the plan and stop")
    args = ap.parse_args(argv)
    now = now or datetime.now(UTC)

    config = g.load_query_config(g.DEFAULT_CONFIG)
    version = str(config.get("version") or "")
    if not version:
        print("query config has no version", file=sys.stderr)
        return 1
    try:
        counts = json.loads(args.counts.read_text(encoding="utf-8"))["total_by_country"]
        jobs = plan(config, counts, now)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(f"error: cannot plan from {args.counts}: {exc}", file=sys.stderr)
        return 1

    labels = [label for label, _ in jobs]
    raw_dir = args.raw_root / now.date().isoformat()
    cached = {label for label in labels if (raw_dir / f"{label}.json").is_file()}
    todo = [(label, url) for label, url in jobs if label not in cached]
    fresh = g.is_fresh(g.load_cache(args.output), version, now)

    if args.dry_run:
        for label in labels:
            print(f"{label}: {'cached' if label in cached else 'to fetch'}")
        print(
            f"{len(todo)} of {len(jobs)} requests to send "
            f"(about {len(todo) * CREDITS_PER_REQUEST} credits) into {raw_dir}; "
            f"output {'fresh' if fresh else 'stale'} (no call made)"
        )
        return 0
    if fresh and not args.force:
        print("cached")
        return 0

    requests, credits = 0, Decimal(0)
    if todo:
        try:
            with _send_limits(len(todo)):
                run = g.BudgetedRun(usage_log=g.DEFAULT_USAGE_LOG, raw_dir=raw_dir, now=now)
                try:
                    for label, url in todo:
                        run.get(url, label)
                finally:
                    run.close()
        except (g.FetchError, ValueError) as exc:
            print(f"error: {exc}; no file written", file=sys.stderr)
            return 1
        requests, credits = run.requests, run.spent_credits

    try:
        bodies = {label: read_raw(raw_dir / f"{label}.json") for label in labels}
    except g.FetchError as exc:
        print(f"error: {exc}; no file written", file=sys.stderr)
        return 1
    newest = max((raw_dir / f"{label}.json").stat().st_mtime for label in labels)
    fetched_at = datetime.fromtimestamp(newest, UTC).isoformat(timespec="seconds")
    payload = assemble(version, labels, bodies, fetched_at)
    write_compact_json(args.output, payload)
    print(
        f"wrote {args.output.name}: {args.output.stat().st_size:,} bytes; "
        f"{len(cached)} cached raw files used, {requests} requests, {credits} credits"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
