"""Journal metrics for the Evidence map publication table (VD-34).

Writes ``site/data/california/journal_metrics.json``. Every work in
``site/data/california/works_detail.json`` is looked
up for its primary OpenAlex source (``/works``, 100 ids per call); each distinct source is then read
for its ``summary_stats`` (``/sources``, 100 ids per call). Journals are keyed by the display name
that ``works_detail.journal`` uses. A name whose works sit in more than one source takes the source
that holds most of them, and the others are listed under ``ambiguous_journals``. When OpenAlex's
display name for that source differs from the journal name (a repository or a different venue),
the metrics are withheld and the case is listed under ``name_mismatches``.

``two_yr_mean_citedness`` is OpenAlex's open analogue of the impact factor: the average number of
citations received this year by a source's works from the two previous years. It is not Clarivate's
Journal Impact Factor, which is proprietary.

Modes:

* default: live. One credit per list call (about 30 for the current corpus). Raw responses are
  cached in ``data/interim/journal_metrics_raw.json`` (ignored by git), then the JSON is built. A
  budget or rate stop writes nothing, so the committed file is never half-built.
* ``--offline``: rebuild the JSON from that cache. No network.
* ``--check``: validate the committed JSON (schema, coverage counts, and that its journal names are
  exactly those in ``works_detail.json``). Exit 1 when it is malformed or stale.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import urllib.parse
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.ingest.openalex import (  # noqa: E402
    OPENALEX_BASE,
    OpenAlexRateLimitError,
    _request_json,
    load_openalex_key,
)
from atlas.regions.scope import region_data_dir  # noqa: E402
from atlas.util.budget import daily_logged_usage, resolve_openalex_budget  # noqa: E402
from atlas.util.cost import ApiCostLogger, OpenAlexUsageMetadataError  # noqa: E402

SCHEMA_VERSION = 1
SOURCE_LABEL = "OpenAlex sources summary_stats"
BATCH = 100
# Owner request (2026-11-17): at most 60 credits for one live run.
MAX_RUN_CREDITS = Decimal(60)
# A list call costs one credit; keep one in reserve before each request.
RESERVE_CREDITS = Decimal(1)
WORKS_DETAIL = region_data_dir() / "works_detail.json"
OUTPUT = region_data_dir() / "journal_metrics.json"
RAW_CACHE = ROOT / "data" / "interim" / "journal_metrics_raw.json"
USAGE_LOG = ROOT / "data" / "logs" / "api_usage.jsonl"
JOURNAL_KEYS = {"source_id", "issn_l", "two_yr_mean_citedness", "h_index", "type"}
WORK_ID = re.compile(r"^W\d+$")
SOURCE_ID = re.compile(r"^S\d+$")
SOURCE_FIELDS = "id,display_name,issn_l,summary_stats,type"
WORK_FIELDS = "id,primary_location"

Call = Callable[[str], dict[str, Any]]


class Stop(Exception):
    """Budget, rate or credit-cap stop: nothing is written, so the next run starts again."""


def _short(value: object) -> str:
    return str(value or "").rstrip("/").rsplit("/", 1)[-1]


def _batches(ids: Iterable[str]) -> list[list[str]]:
    values = list(ids)
    return [values[start : start + BATCH] for start in range(0, len(values), BATCH)]


def _numeric(source_id: str) -> int:
    return int(source_id[1:])


def _norm(name: str) -> str:
    """Case- and spacing-insensitive form of a journal name, for comparing it with OpenAlex's."""
    return " ".join(name.casefold().split())


def works_url(ids: list[str]) -> str:
    params = {
        "filter": "openalex:" + "|".join(ids),
        "per-page": BATCH,
        "select": WORK_FIELDS,
    }
    return f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"


def sources_url(ids: list[str]) -> str:
    params = {
        "filter": "openalex:" + "|".join(ids),
        "per-page": BATCH,
        "select": SOURCE_FIELDS,
    }
    return f"{OPENALEX_BASE}/sources?{urllib.parse.urlencode(params)}"


def load_works(path: Path) -> dict[str, str]:
    """``{work_id: journal name}`` for each works_detail row; the name is "" when unlisted."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("works") if isinstance(payload, dict) else payload
    works: dict[str, str] = {}
    for row in rows or []:
        work_id = str(row.get("work_id") or "").strip()
        if WORK_ID.match(work_id) and work_id not in works:
            works[work_id] = str(row.get("journal") or "").strip()
    return works


def fetch_primary_sources(ids: list[str], call: Call, out: dict[str, str | None]) -> None:
    """Fill ``out`` with each work's primary source id (None when OpenAlex gives none)."""
    for batch in _batches(ids):
        found: dict[str, str | None] = {}
        for work in call(works_url(batch)).get("results") or []:
            location = work.get("primary_location") or {}
            source_id = _short((location.get("source") or {}).get("id"))
            found[_short(work.get("id"))] = source_id if SOURCE_ID.match(source_id) else None
        for work_id in batch:
            out[work_id] = found.get(work_id)


def fetch_sources(ids: list[str], call: Call, out: dict[str, dict[str, Any]]) -> None:
    """Fill ``out`` with each source's display name, ISSN-L, type and two summary statistics."""
    for batch in _batches(ids):
        for source in call(sources_url(batch)).get("results") or []:
            source_id = _short(source.get("id"))
            if not SOURCE_ID.match(source_id):
                continue
            stats = source.get("summary_stats") or {}
            out[source_id] = {
                "display_name": str(source.get("display_name") or ""),
                "issn_l": source.get("issn_l") or None,
                "type": source.get("type") or None,
                "summary_stats": {
                    "2yr_mean_citedness": stats.get("2yr_mean_citedness"),
                    "h_index": stats.get("h_index"),
                },
            }


def _metric(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        return None
    return round(float(value), 3) if value >= 0 else None


def _count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def build_payload(
    works: Mapping[str, str],
    primary: Mapping[str, str | None],
    sources: Mapping[str, Mapping[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    """Join works to journal names and sources. Pure: no network and no file access."""
    by_name: dict[str, Counter[str]] = {}
    for work_id, name in works.items():
        if name:
            counter = by_name.setdefault(name, Counter())
            if primary.get(work_id):
                counter[str(primary[work_id])] += 1
    journals: dict[str, dict[str, Any]] = {}
    unmatched: list[str] = []
    mismatches: list[dict[str, str]] = []
    ambiguous: list[dict[str, Any]] = []
    for name in sorted(by_name):
        counter = by_name[name]
        if not counter:
            unmatched.append(name)
            continue
        ranked = sorted(counter.items(), key=lambda item: (-item[1], _numeric(item[0])))
        source_id = ranked[0][0]
        if len(ranked) > 1:
            ambiguous.append(
                {
                    "journal": name,
                    "source_id": source_id,
                    "other_source_ids": [sid for sid, _ in ranked[1:]],
                }
            )
        source = sources.get(source_id, {})
        stats = source.get("summary_stats") or {}
        display = str(source.get("display_name") or "")
        if display and _norm(display) != _norm(name):
            # A different venue (often a repository): keep the id for review, withhold metrics.
            mismatches.append(
                {"journal": name, "openalex_display_name": display, "source_id": source_id}
            )
            journals[name] = {
                "source_id": source_id,
                "issn_l": None,
                "two_yr_mean_citedness": None,
                "h_index": None,
                "type": None,
            }
            continue
        journals[name] = {
            "source_id": source_id,
            "issn_l": source.get("issn_l") or None,
            "two_yr_mean_citedness": _metric(stats.get("2yr_mean_citedness")),
            "h_index": _count(stats.get("h_index")),
            "type": source.get("type") or None,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": SOURCE_LABEL,
        "coverage": {
            "works": len(works),
            "works_with_source": sum(1 for work_id in works if primary.get(work_id)),
            "journals": len(by_name),
            "journals_with_source": len(journals),
            "journals_with_metric": sum(
                1 for entry in journals.values() if entry["two_yr_mean_citedness"] is not None
            ),
        },
        # A list, not an object keyed by name: the release snapshot refuses JSON keys
        # starting "abstract", and a journal such as "Abstracts with programs" would trip it.
        "journals": [{"name": name, **journals[name]} for name in sorted(journals)],
        "unmatched_journals": unmatched,
        "name_mismatches": mismatches,
        "ambiguous_journals": ambiguous,
    }


def check_payload(payload: object, journal_names: set[str] | None = None) -> list[str]:
    """Problems with a journal_metrics payload; an empty list means it is valid and current."""
    problems: list[str] = []
    if not isinstance(payload, dict):
        return ["top level must be a JSON object"]
    if payload.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("source") != SOURCE_LABEL:
        problems.append(f"source must be {SOURCE_LABEL!r}")
    try:
        datetime.fromisoformat(str(payload.get("generated_at")))
    except ValueError:
        problems.append("generated_at must be an ISO 8601 timestamp")
    listed = payload.get("journals")
    unmatched = payload.get("unmatched_journals")
    if not isinstance(listed, list):
        return problems + ["journals must be a list"]
    journals: dict[str, dict[str, Any]] = {}
    for item in listed:
        if (
            not isinstance(item, dict)
            or set(item) != JOURNAL_KEYS | {"name"}
            or not isinstance(item["name"], str)
        ):
            problems.append(f"journals[] entries must have exactly name and {sorted(JOURNAL_KEYS)}")
            continue
        name = item["name"]
        if name in journals:
            problems.append(f"{name!r}: listed more than once")
        journals[name] = {key: item[key] for key in JOURNAL_KEYS}
    if not isinstance(unmatched, list) or unmatched != sorted(set(unmatched)):
        problems.append("unmatched_journals must be a sorted list without duplicates")
        unmatched = []
    for name, entry in journals.items():
        if not name or name != name.strip():
            problems.append(f"journal name {name!r} must be non-empty and trimmed")
        if not isinstance(entry, dict) or set(entry) != JOURNAL_KEYS:
            problems.append(f"{name!r}: entry must have exactly {sorted(JOURNAL_KEYS)}")
            continue
        if not (isinstance(entry["source_id"], str) and SOURCE_ID.match(entry["source_id"])):
            problems.append(f"{name!r}: source_id must look like S123")
        if entry["issn_l"] is not None and not (
            isinstance(entry["issn_l"], str) and entry["issn_l"]
        ):
            problems.append(f"{name!r}: issn_l must be a string or null")
        if (
            entry["two_yr_mean_citedness"] is not None
            and _metric(entry["two_yr_mean_citedness"]) is None
        ):
            problems.append(f"{name!r}: two_yr_mean_citedness must be a finite number >= 0 or null")
        if entry["h_index"] is not None and _count(entry["h_index"]) is None:
            problems.append(f"{name!r}: h_index must be an integer >= 0 or null")
        if entry["type"] is not None and not (isinstance(entry["type"], str) and entry["type"]):
            problems.append(f"{name!r}: type must be a string or null")
    if set(journals) & set(unmatched):
        problems.append("a journal cannot be both matched and unmatched")
    for item in payload.get("name_mismatches") or []:
        entry = journals.get(item.get("journal")) if isinstance(item, dict) else None
        if not isinstance(entry, dict) or entry.get("two_yr_mean_citedness") is not None:
            problems.append("a name mismatch must be listed in journals with its metrics withheld")
            break
    coverage = payload.get("coverage")
    expected = {
        "journals_with_source": len(journals),
        "journals": len(journals) + len(unmatched),
        "journals_with_metric": sum(
            1
            for entry in journals.values()
            if isinstance(entry, dict) and entry.get("two_yr_mean_citedness") is not None
        ),
    }
    if not isinstance(coverage, dict) or any(
        coverage.get(key) != value for key, value in expected.items()
    ):
        problems.append(f"coverage must agree with the journals ({expected})")
    return problems


def staleness(payload: Mapping[str, Any], journal_names: set[str]) -> str | None:
    """A note when the daily export has journals the file lacks (or no longer lists).

    Not an error: new journals arrive with every daily ingest and show no value until the
    next refresh (the ingest workflow refreshes this file after each export).
    """
    journals = payload.get("journals")
    unmatched = payload.get("unmatched_journals")
    named = (
        {row.get("name") for row in journals if isinstance(row, Mapping)}
        if isinstance(journals, list)
        else set(journals or {})
    )
    names = named | set(unmatched or [])
    missing = sorted(journal_names - names)
    extra = sorted(names - journal_names)
    if not (missing or extra):
        return None
    return (
        f"{len(missing)} works_detail journals not yet in the file and {len(extra)} no longer "
        "listed; they show no value until scripts/fetch_journal_metrics.py runs again"
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    temp.write_text(text + "\n", encoding="utf-8")
    temp.replace(path)


def fetch_live(
    works: Mapping[str, str], *, usage_log: Path, max_credits: Decimal, fetched_at: str
) -> dict[str, Any]:
    """Look up each work's source and each source's metrics. Raises Stop on a budget stop."""
    load_openalex_key()
    budget = resolve_openalex_budget()
    prior_cost, prior_credits = daily_logged_usage(
        usage_log, cost_per_credit_usd=budget.cost_per_credit_usd
    )
    spent = {"cost": Decimal(0), "credits": Decimal(0)}
    raw: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "fetched_at_utc": fetched_at,
        "works": {},
        "sources": {},
    }
    with ApiCostLogger(f"journal-metrics-{fetched_at}", usage_log) as logger:

        def call(url: str) -> dict[str, Any]:
            if spent["credits"] + RESERVE_CREDITS > max_credits:
                raise Stop("run credit cap reached")
            error = budget.reserve_error(
                cost_usd=prior_cost + spent["cost"], credits=prior_credits + spent["credits"]
            )
            if error:
                raise Stop(error)
            before = len(logger.request_metrics)
            try:
                body = _request_json(url, logger=logger)
            except OpenAlexRateLimitError as exc:
                raise Stop(f"rate limited ({exc})") from exc
            except OpenAlexUsageMetadataError as exc:
                raise Stop(f"OpenAlex request failed ({exc})") from exc
            for record in logger.request_metrics[before:]:
                credits = Decimal(str(record.get("credits") or 10))
                spent["credits"] += credits
                spent["cost"] += credits * budget.cost_per_credit_usd
            if spent["credits"] > max_credits:
                raise Stop("run credit cap exceeded after a response")
            return body

        fetch_primary_sources(sorted(works), call, raw["works"])
        source_ids = sorted({sid for sid in raw["works"].values() if sid}, key=_numeric)
        fetch_sources(source_ids, call, raw["sources"])
    raw["credits"] = str(spent["credits"])
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--works-detail", type=Path, default=WORKS_DETAIL)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--raw", type=Path, default=RAW_CACHE)
    parser.add_argument("--usage-log", type=Path, default=USAGE_LOG)
    parser.add_argument("--max-credits", type=Decimal, default=MAX_RUN_CREDITS)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="rebuild the JSON from the raw cache")
    mode.add_argument(
        "--check", action="store_true", help="validate the committed JSON; no network"
    )
    args = parser.parse_args(argv)

    if args.check:
        if not args.output.exists():
            print(f"journal metrics: {args.output} is missing", file=sys.stderr)
            return 1
        payload = json.loads(args.output.read_text(encoding="utf-8"))
        journal_names = set(load_works(args.works_detail).values()) - {""}
        problems = check_payload(payload, journal_names)
        if problems:
            for problem in problems:
                print(f"journal metrics: {problem}", file=sys.stderr)
            return 1
        note = staleness(payload, journal_names)
        if note:
            print(f"journal metrics: note: {note}")
        print(f"journal metrics ok: {len(payload['journals'])} journals")
        return 0

    fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
    works = load_works(args.works_detail)
    if args.offline:
        if not args.raw.exists():
            print(
                f"journal metrics: no raw cache at {args.raw}; run without --offline first",
                file=sys.stderr,
            )
            return 2
        raw = json.loads(args.raw.read_text(encoding="utf-8"))
        status = "offline"
    else:
        try:
            raw = fetch_live(
                works, usage_log=args.usage_log, max_credits=args.max_credits, fetched_at=fetched_at
            )
        except Stop as stop:
            print(f"journal metrics deferred ({stop}); nothing written", file=sys.stderr)
            return 1
        _write_json(args.raw, raw)
        status = "live"

    payload = build_payload(
        works,
        raw.get("works") or {},
        raw.get("sources") or {},
        generated_at=fetched_at,
    )
    problems = check_payload(payload, set(works.values()) - {""})
    if problems:
        for problem in problems:
            print(f"journal metrics: {problem}", file=sys.stderr)
        return 1
    _write_json(args.output, payload)
    coverage = payload["coverage"]
    network = f"{raw.get('credits', 'n/a')} credits spent" if status == "live" else "no network"
    print(
        f"journal metrics {status}: {coverage['journals']} journal names; "
        f"{coverage['journals_with_source']} with a source; "
        f"{coverage['journals_with_metric']} with a 2-yr mean citedness value; "
        f"{len(payload['unmatched_journals'])} unmatched; "
        f"{len(payload['name_mismatches'])} name mismatches; "
        f"{len(payload['ambiguous_journals'])} ambiguous; {network}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
