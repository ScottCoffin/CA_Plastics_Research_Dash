"""BQ-1.3 recall probes: language-probe overlap, theme and lens anchor overlap, T10753 overlap.

These are PROBES, not recall estimates. No gold set exists yet, so nothing here says how many
relevant works the v3.1 query finds. Every output is labelled as a probe in the JSON.

1. Language probe (no network): for each of the 16 term sets in ``site/data/language_probe.json``,
   the share of its fixed-seed sample that the v3.1 query also retrieves, with a Wilson 95%
   interval. Sets are never pooled.
2. Anchor overlap: the 42 theme anchors (``tests/fixtures/theme_anchors.json``, BQ-S6) are filtered
   to their OpenAlex IDs in one request, combined with the v3.1 title-and-abstract search and the
   v3.1 type exclusions. Shares are reported per theme and per lens group with Wilson intervals.
   The request pattern follows ``scripts/bq1_5_anchor_overlap.py``.
3. T10753 overlap (count queries only): OpenAlex topic T10753 (microplastics) through
   ``primary_topic.id:T10753``, with the same type exclusions as v3.1. Reports the count of T10753
   works, the count of v3.1 works, their intersection, and the two shares. Topic assignment is
   OpenAlex's classifier.

Credits: search counts cost 10 credits per call, so the live run is about 31 credits. A run cap of
300 credits is enforced before each call.

Usage:
    py -3.14 scripts/bq1_3_recall_probes.py            # live: reuse cache, fetch the rest
    py -3.14 scripts/bq1_3_recall_probes.py --offline  # rebuild the JSON from the cache only
    py -3.14 scripts/bq1_3_recall_probes.py --check    # validate committed JSON (SKIP w/o cache)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import urllib.parse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.ingest.openalex import (  # noqa: E402
    OPENALEX_BASE,
    _request_json,
    compact_openalex_id,
    load_openalex_key,
)
from atlas.query import load_query_config, openalex_filter, type_filters  # noqa: E402
from atlas.util.budget import daily_logged_usage, resolve_openalex_budget  # noqa: E402
from atlas.util.cost import ApiCostLogger  # noqa: E402

SCHEMA_VERSION = "bq13-v1"
CONFIG = ROOT / "config" / "queries.yml"
LANGUAGE_PROBE = ROOT / "site" / "data" / "language_probe.json"
THEME_ANCHORS = ROOT / "tests" / "fixtures" / "theme_anchors.json"
CACHE_DIR = ROOT / "data" / "interim" / "bq1_3"
USAGE_LOG = ROOT / "data" / "logs" / "api_usage.jsonl"
OUT_JSON = ROOT / "docs" / "api_notes" / "bq1_3_recall_probes.json"

T10753 = "T10753"
PER_PAGE = 50
ANCHOR_BATCH = 50
CREDIT_CAP = 300.0
RESERVE_CREDITS = 10.0
MAX_HTTP_ATTEMPTS = 3
MAX_URL_CHARS = 8000
USD_PER_CREDIT = 0.0001  # docs/BQ_S6_THEME_ANCHORS.md: 1 credit = USD 0.0001
WILSON_Z = 1.959963984540054
EXPECTED_LANGUAGE_SETS = 16
EXPECTED_ANCHORS = 42

# Lens groups are a default assumption for review (see docs/BQ_1_3_RECALL_PROBES.md). The theme
# anchors carry no per-work lens tag, so each theme is assigned to the A3 section 4.3 stratum
# (pollution-core, lifecycle-and-society, lens-candidate) that its name implies.
LENS_GROUP_OF_THEME = {
    "litter": "pollution_core",
    "chemicals": "pollution_core",
    "pollution_exposure_health": "pollution_core",
    "waste_recycling": "lifecycle_and_society",
    "policy": "lifecycle_and_society",
    "behaviour": "lifecycle_and_society",
    "lca_bioplastics": "lifecycle_and_society",
    "ssbd": "lifecycle_and_society",
    "book": "lifecycle_and_society",
    "reviews_2025_2026": "lifecycle_and_society",
    "waste_colonialism_justice": "lens_candidate",
    "labour_critique": "lens_candidate",
}

PROBE_NOTE = (
    "PROBE, not a recall estimate. No gold set exists yet; the shares say what the v3.1 query "
    "returns for these sets, not how many relevant works it finds."
)


class FetchError(RuntimeError):
    """A live or cached OpenAlex response could not be used."""


class CacheMiss(FetchError):
    """Offline mode found no cached response for a planned call."""


class CreditCapError(FetchError):
    """The next call would take this run past the credit cap."""


# ---------------------------------------------------------------- statistics


def wilson_interval(successes: int, n: int) -> tuple[float | None, float | None]:
    """Wilson score interval at 95 percent, rounded to four places; None when n is zero."""

    if n == 0:
        return None, None
    if n < 0 or not 0 <= successes <= n:
        raise ValueError(f"successes {successes} outside 0..{n}")
    z2 = WILSON_Z * WILSON_Z
    p = successes / n
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = WILSON_Z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


def _share(successes: int, n: int) -> float | None:
    return round(successes / n, 4) if n else None


def _proportion(label: str, successes: int, n: int) -> dict[str, Any]:
    low, high = wilson_interval(successes, n)
    return {
        "label": label,
        "k": successes,
        "n": n,
        "share": _share(successes, n),
        "wilson95_low": low,
        "wilson95_high": high,
    }


# ---------------------------------------------------------------- OpenAlex request text


def _works_url(filters: Sequence[str], select: str, per_page: int) -> str:
    params = {"filter": ",".join(filters), "select": select, "per-page": per_page}
    url = f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"
    if len(url) > MAX_URL_CHARS:
        raise ValueError(f"request URL is {len(url)} characters; limit is {MAX_URL_CHARS}")
    return url


def v31_filters(config: Mapping[str, Any]) -> list[str]:
    return [openalex_filter(config), *type_filters(config)]


def query_fingerprint(config: Mapping[str, Any]) -> str:
    return hashlib.sha256("|".join(v31_filters(config)).encode("utf-8")).hexdigest()


def id_filter(ids: Sequence[str]) -> str:
    if not 1 <= len(ids) <= ANCHOR_BATCH:
        raise ValueError(f"1 to {ANCHOR_BATCH} OpenAlex IDs per call, got {len(ids)}")
    return "ids.openalex:" + "|".join(ids)


def anchor_probe_url(config: Mapping[str, Any], ids: Sequence[str]) -> str:
    """The v3.1 search, its type exclusions and the anchor ID filter (order as in build_url)."""

    return _works_url([*v31_filters(config), id_filter(ids)], select="id", per_page=PER_PAGE)


def count_url(filters: Sequence[str]) -> str:
    """A count-only request: one row back, ``meta.count`` is the answer."""

    return _works_url(list(filters), select="id", per_page=1)


def topic_filter() -> str:
    return f"primary_topic.id:{T10753}"


# ---------------------------------------------------------------- inputs


def load_language_rows(path: Path = LANGUAGE_PROBE) -> list[dict[str, Any]]:
    """One row per term set: k of n sample works also retrieved by v3.1. Never pooled."""

    data = json.loads(path.read_text(encoding="utf-8"))
    sets = data.get("term_sets")
    if not isinstance(sets, list) or len(sets) != EXPECTED_LANGUAGE_SETS:
        raise ValueError(f"{path.name}: expected {EXPECTED_LANGUAGE_SETS} term_sets")
    rows = []
    for entry in sets:
        n = int(entry["sample_size"])
        k = int(entry["sample_in_v31"])
        if not 0 <= k <= n:
            raise ValueError(f"term set {entry.get('id')}: k={k} outside 0..{n}")
        row = _proportion(str(entry["id"]), k, n)
        row["languages"] = list(entry.get("languages") or [])
        row["openalex_count"] = int(entry.get("count") or 0)
        rows.append(row)
    return rows


def load_anchors(path: Path = THEME_ANCHORS) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    anchors = data.get("anchors")
    if not isinstance(anchors, list) or len(anchors) != EXPECTED_ANCHORS:
        raise ValueError(f"{path.name}: expected {EXPECTED_ANCHORS} anchors")
    for anchor in anchors:
        if not anchor.get("openalex_id") or anchor.get("theme") not in LENS_GROUP_OF_THEME:
            raise ValueError(f"anchor {anchor.get('doi')} lacks an OpenAlex ID or known theme")
    return anchors


# ---------------------------------------------------------------- live fetch and cache


def _live_fetch(url: str, usage_log: Path) -> tuple[dict[str, Any], float, str]:
    """One budgeted request, the same sequence as scripts/bq1_5_anchor_overlap.py."""

    budget = resolve_openalex_budget()
    prior_cost, prior_credits = daily_logged_usage(
        usage_log, cost_per_credit_usd=budget.cost_per_credit_usd
    )
    error = budget.reserve_error(cost_usd=prior_cost, credits=prior_credits)
    if error:
        raise FetchError(f"budget guard: {error}")
    load_openalex_key()
    fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        with ApiCostLogger("bq1-3-recall-probes-" + fetched_at, usage_log) as logger:
            body = _request_json(url, logger=logger, attempts=MAX_HTTP_ATTEMPTS)
            credits = float(logger.request_metrics[-1]["credits"])
    except Exception as exc:  # OpenAlex, usage-metadata and network errors alike
        raise FetchError(f"OpenAlex request failed: {exc}") from exc
    return body, credits, fetched_at


Fetcher = Callable[[str], tuple[dict[str, Any], float, str]]


@dataclass(frozen=True)
class Call:
    label: str
    url: str


class CallCache:
    """One JSON file per request, named by label and URL digest. Offline never calls out."""

    def __init__(self, directory: Path, *, offline: bool, fetcher: Fetcher | None = None) -> None:
        self.directory = Path(directory)
        self.offline = offline
        self.fetcher = fetcher or (lambda url: _live_fetch(url, USAGE_LOG))

    @staticmethod
    def _digest(url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def path(self, call: Call) -> Path:
        return self.directory / f"{call.label}_{self._digest(call.url)[:16]}.json"

    def load(self, call: Call) -> dict[str, Any] | None:
        path = self.path(call)
        if not path.exists():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("url_sha256") != self._digest(call.url):
            raise FetchError(f"cache file {path.name} does not match its URL")
        return record

    def write(self, call: Call, body: Mapping[str, Any], credits: float, fetched_at: str) -> dict:
        record = {
            "schema_version": "bq13_call.v1",
            "label": call.label,
            "url": call.url,
            "url_sha256": self._digest(call.url),
            "fetched_at": fetched_at,
            "credits": credits,
            "body": body,
        }
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path(call)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
        return record


def run_calls(calls: Sequence[Call], cache: CallCache, cap: float = CREDIT_CAP) -> dict[str, dict]:
    """Cached responses first; then new calls, stopping before the cap would be passed."""

    records: dict[str, dict] = {}
    for call in calls:
        cached = cache.load(call)
        if cached is not None:
            records[call.label] = cached
    spent = sum(float(record["credits"]) for record in records.values())
    for call in calls:
        if call.label in records:
            continue
        if cache.offline:
            raise CacheMiss(f"offline: no cached response for {call.label}")
        if spent + RESERVE_CREDITS > cap:
            raise CreditCapError(
                f"stopping before {call.label}: {spent:g} credits used, cap {cap:g}"
            )
        body, credits, fetched_at = cache.fetcher(call.url)
        _check_body(call.label, body)
        record = cache.write(call, body, credits, fetched_at)
        records[call.label] = record
        spent += credits
    return records


def _check_body(label: str, body: Mapping[str, Any]) -> None:
    results = body.get("results")
    count = (body.get("meta") or {}).get("count")
    if not isinstance(results, list) or not isinstance(count, int):
        raise FetchError(f"{label}: response lacks results or meta.count")
    if label.startswith("anchor_probe") and count > len(results):
        raise FetchError(f"{label}: response is paged; batch incomplete")


def planned_calls(config: Mapping[str, Any], anchors: Sequence[Mapping[str, Any]]) -> list[Call]:
    calls: list[Call] = []
    ids = [str(anchor["openalex_id"]) for anchor in anchors]
    for index in range(0, len(ids), ANCHOR_BATCH):
        batch = ids[index : index + ANCHOR_BATCH]
        calls.append(
            Call(f"anchor_probe_{index // ANCHOR_BATCH + 1}", anchor_probe_url(config, batch))
        )
    calls.append(Call("t10753_count", count_url([topic_filter(), *type_filters(config)])))
    calls.append(Call("v31_count", count_url(v31_filters(config))))
    calls.append(Call("v31_and_t10753_count", count_url([*v31_filters(config), topic_filter()])))
    return calls


# ---------------------------------------------------------------- scoring


def score_anchors(
    anchors: Sequence[Mapping[str, Any]], records: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    retrieved: set[str] = set()
    for label, record in records.items():
        if label.startswith("anchor_probe"):
            for result in record["body"]["results"]:
                retrieved.add(compact_openalex_id(result.get("id")))
    rows = []
    for anchor in anchors:
        rows.append(
            {
                "doi": anchor["doi"],
                "openalex_id": anchor["openalex_id"],
                "theme": anchor["theme"],
                "lens_group": LENS_GROUP_OF_THEME[anchor["theme"]],
                "retrieved_by_v31": anchor["openalex_id"] in retrieved,
            }
        )

    def tally(key: str, groups: Sequence[str]) -> list[dict[str, Any]]:
        out = []
        for group in groups:
            members = [row for row in rows if row[key] == group]
            hits = sum(row["retrieved_by_v31"] for row in members)
            entry = _proportion(group, hits, len(members))
            entry["misses"] = [row["doi"] for row in members if not row["retrieved_by_v31"]]
            out.append(entry)
        return out

    themes = list(dict.fromkeys(anchor["theme"] for anchor in anchors))
    lens_groups = list(dict.fromkeys(LENS_GROUP_OF_THEME[theme] for theme in themes))
    total = _proportion("all anchors", sum(row["retrieved_by_v31"] for row in rows), len(rows))
    total["misses"] = [row["doi"] for row in rows if not row["retrieved_by_v31"]]
    return {
        "overall": total,
        "per_theme": tally("theme", themes),
        "per_lens_group": tally("lens_group", lens_groups),
        "rows": rows,
    }


def score_t10753(records: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    def count(label: str) -> int:
        return int(records[label]["body"]["meta"]["count"])

    t_total = count("t10753_count")
    v31_total = count("v31_count")
    both = count("v31_and_t10753_count")
    if both > min(t_total, v31_total):
        raise FetchError("intersection exceeds one of its parents; counts are inconsistent")
    return {
        "topic_id": T10753,
        "filter": topic_filter(),
        "type_exclusions_applied": True,
        "count_t10753_works": t_total,
        "count_v31_works": v31_total,
        "count_intersection": both,
        "share_t10753_retrieved_by_v31": _proportion("T10753 works also in v3.1", both, t_total),
        "share_v31_in_t10753": _proportion("v3.1 works with T10753 primary topic", both, v31_total),
        "limitation": (
            "Topic assignment is OpenAlex's primary_topic classifier, not a relevance judgement."
        ),
    }


# ---------------------------------------------------------------- payload


def build_payload(
    config: Mapping[str, Any],
    language_rows: Sequence[Mapping[str, Any]],
    anchors: Sequence[Mapping[str, Any]],
    records: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    credits = sum(float(record["credits"]) for record in records.values())
    generated_at = max((record["fetched_at"] for record in records.values()), default="")
    anchors_out = score_anchors(anchors, records)
    return {
        "schema_version": SCHEMA_VERSION,
        "probe_label": "PROBE",
        "note": PROBE_NOTE,
        "generated_at": generated_at,
        "query_version": config.get("version"),
        "query_fingerprint_sha256": query_fingerprint(config),
        "cost": {
            "calls": len(records),
            "credits": credits,
            "usd_estimate": round(credits * USD_PER_CREDIT, 6),
            "credit_cap": CREDIT_CAP,
            "calls_detail": [
                {
                    "label": label,
                    "credits": record["credits"],
                    "fetched_at": record["fetched_at"],
                    "url_sha256": record["url_sha256"],
                }
                for label, record in sorted(records.items())
            ],
        },
        "language_probe": {
            "source": "site/data/language_probe.json",
            "method": "Share of the fixed-seed sample of each term set also retrieved by v3.1; "
            "Wilson 95%; no network calls; term sets are not pooled.",
            "term_sets": list(language_rows),
        },
        "anchor_overlap": {
            "source": "tests/fixtures/theme_anchors.json (BQ-S6)",
            "method": "One OpenAlex request filters the anchors by ID and applies the v3.1 search "
            "and type exclusions; Wilson 95%.",
            "lens_basis": "Lens groups are a default assumption: each theme is assigned to an A3 "
            "section 4.3 stratum (see docs/BQ_1_3_RECALL_PROBES.md).",
            "overall": anchors_out["overall"],
            "per_theme": anchors_out["per_theme"],
            "per_lens_group": anchors_out["per_lens_group"],
        },
        "t10753_overlap": score_t10753(records),
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


# ---------------------------------------------------------------- CLI


def run_probe(*, offline: bool, cache_dir: Path, fetcher: Fetcher | None = None) -> dict[str, Any]:
    config = load_query_config(CONFIG)
    language_rows = load_language_rows()
    anchors = load_anchors()
    calls = planned_calls(config, anchors)
    cache = CallCache(cache_dir, offline=offline, fetcher=fetcher)
    records = run_calls(calls, cache)
    return build_payload(config, language_rows, anchors, records)


def check_committed(cache_dir: Path, out_json: Path = OUT_JSON) -> int:
    if not cache_dir.exists() or not any(cache_dir.glob("*.json")):
        print(f"SKIP: no cache under {cache_dir}; committed JSON not rebuilt")
        return 0
    if not out_json.exists():
        print(f"error: {out_json.name} is missing", file=sys.stderr)
        return 1
    committed = json.loads(out_json.read_text(encoding="utf-8"))
    try:
        rebuilt = run_probe(offline=True, cache_dir=cache_dir)
    except FetchError as exc:
        print(f"error: cache is incomplete: {exc}", file=sys.stderr)
        return 1
    if committed != rebuilt:
        print(f"error: {out_json.name} differs from a rebuild of the cache", file=sys.stderr)
        return 1
    print(f"OK: {out_json.name} matches a rebuild of the cache")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="rebuild from cache; no network")
    parser.add_argument(
        "--check", action="store_true", help="validate committed JSON; SKIP without cache"
    )
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    args = parser.parse_args(argv)
    if args.check:
        return check_committed(args.cache_dir)
    try:
        payload = run_probe(offline=args.offline, cache_dir=args.cache_dir)
    except FetchError as exc:
        print(f"error: {exc}; no file written", file=sys.stderr)
        return 1
    write_json(OUT_JSON, payload)
    overall = payload["anchor_overlap"]["overall"]
    t = payload["t10753_overlap"]
    print(f"anchors: {overall['k']}/{overall['n']} retrieved by v3.1 (probe)")
    print(
        f"T10753: {t['count_intersection']} of {t['count_t10753_works']} T10753 works in v3.1; "
        f"{t['count_intersection']} of {t['count_v31_works']} v3.1 works in T10753"
    )
    print(
        f"wrote {OUT_JSON.name}: {payload['cost']['calls']} calls, "
        f"{payload['cost']['credits']:g} credits"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
