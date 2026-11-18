"""Real OpenAlex sample data for the Global app prototype (`.impeccable/sketches/global_app.html`).

Design-prototype data, not a pipeline output. One budget-guarded group_by or list request per
(scope, facet) under the active plastics query, through ``scripts/build_global_counts.py``'s
``BudgetedRun`` (daily ceilings in ``config/budget.yml``, usage logged to
``data/logs/api_usage.jsonl``). Search-filter requests cost 10 credits each; the full run is
about 35 requests (about 350 credits, USD 0.035), within the owner's daily OpenAlex rule.

Raw responses are kept in ignored ``data/raw/global_app_sample/``; a request whose raw file
exists is not repeated, so a rebuild after the first run is offline. Output:
``.impeccable/sketches/src/global_app_sample.json``.

    py -3.14 .impeccable/sketches/src/fetch_global_app_sample.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import build_global_counts as g  # noqa: E402

RAW = ROOT / "data" / "raw" / "global_app_sample"
OUT = Path(__file__).with_name("global_app_sample.json")
COUNTS = ROOT / "site" / "data" / "global" / "global_counts.json"

# Profiles drawn in full; the network adds co-author countries for the top countries.
PROFILE_SCOPES = ["US", "CN", "NO"]
NETWORK_TOP = 15
FACETS = {
    "authors": ("authorships.author.id", 25),
    "institutions": ("authorships.institutions.id", 25),
    "topics": ("primary_topic.id", 25),
    "years": ("publication_year", 200),
    "countries": ("authorships.countries", 200),
}
RECENT_SELECT = "id,doi,display_name,publication_date,primary_location,authorships"


def base_filters(config, scope: str | None) -> list[str]:
    filters = [g.openalex_filter(config), *g.type_filters(config)]
    if scope:
        filters.append(f"authorships.countries:{scope}")
    return filters


def group_url(config, scope, facet) -> str:
    field, per_page = FACETS[facet]
    params = {
        "filter": ",".join(base_filters(config, scope)),
        "group_by": field,
        "per_page": per_page,
    }
    return f"{g.OPENALEX_BASE}/works?{urllib.parse.urlencode(params, safe=':,|')}"


def recent_url(config, scope) -> str:
    yesterday = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
    filters = [*base_filters(config, scope), f"to_publication_date:{yesterday}"]
    params = {
        "filter": ",".join(filters),
        "sort": "publication_date:desc",
        "per_page": 12,
        "select": RECENT_SELECT,
    }
    return f"{g.OPENALEX_BASE}/works?{urllib.parse.urlencode(params, safe=':,|')}"


def plan(config) -> list[tuple[str, str]]:
    counts = json.loads(COUNTS.read_text(encoding="utf-8"))["total_by_country"]
    top = [c for c, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:NETWORK_TOP]]
    jobs = [
        (f"world_{f}", group_url(config, None, f)) for f in ("authors", "institutions", "topics")
    ]
    jobs.append(("world_recent", recent_url(config, None)))
    for scope in PROFILE_SCOPES:
        jobs += [(f"{scope}_{f}", group_url(config, scope, f)) for f in FACETS]
        jobs.append((f"{scope}_recent", recent_url(config, scope)))
    jobs += [
        (f"{c}_countries", group_url(config, c, "countries"))
        for c in top
        if c not in PROFILE_SCOPES
    ]
    return jobs


def groups(body) -> list[dict]:
    return [
        {
            "key": str(x.get("key", "")).rsplit("/", 1)[-1],
            "name": x.get("key_display_name"),
            "count": x.get("count"),
        }
        for x in body.get("group_by") or []
    ]


def slim_work(w) -> dict:
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    config = g.load_query_config(g.DEFAULT_CONFIG)
    jobs = plan(config)
    todo = [(k, u) for k, u in jobs if not (RAW / f"{k}.json").exists()]
    if args.dry_run:
        for k, u in todo:
            print(k, len(u))
        print(f"{len(todo)} of {len(jobs)} requests to send (about {len(todo) * 10} credits)")
        return 0
    if todo:
        g.MAX_REQUESTS = len(todo) + 2
        g.RUN_CREDIT_CAP = Decimal(len(todo) * 10 + 40)
        now = datetime.now(UTC)
        run = g.BudgetedRun(usage_log=g.DEFAULT_USAGE_LOG, raw_dir=RAW, now=now)
        try:
            for k, u in todo:
                run.get(u, k)
        except g.FetchError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        finally:
            run.close()
        print(f"{run.requests} requests, {run.spent_credits} credits")
    out = {"query_version": config.get("version"), "fetched_at": None, "scopes": {}}
    for k, _ in jobs:
        body = json.loads((RAW / f"{k}.json").read_text(encoding="utf-8"))
        scope, facet = k.split("_", 1)
        entry = out["scopes"].setdefault(scope, {})
        if facet == "recent":
            entry["recent"] = [slim_work(w) for w in body.get("results") or []]
        else:
            entry[facet] = groups(body)
        entry.setdefault("works", (body.get("meta") or {}).get("count"))
    out["fetched_at"] = datetime.fromtimestamp(
        max(p.stat().st_mtime for p in RAW.glob("*.json")), UTC
    ).isoformat(timespec="seconds")
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.name}: {OUT.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
