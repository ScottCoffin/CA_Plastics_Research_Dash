"""Look up OpenAlex author IDs for ORCIDs on null-ID authorships (S2.6).

Reads the raw works (``data/interim/works_raw.parquet``, column ``raw_json``) and collects
the ORCIDs of authorships whose OpenAlex author ID is null. An ORCID is skipped when the
raw works already map it to exactly one author ID (``build_orcid_index``) or when it is
already in ``curation/orcid_author_ids.csv``. Each remaining ORCID gets one
``GET /authors/orcid:<ORCID>`` through the OpenAlex budget guard. A found author is
appended as ``orcid,author_id,display_name,fetched_at`` (UTC ISO time); a 404 is written
with a blank ``author_id`` so it is not retried. The CSV is rewritten sorted by ORCID after
every lookup, so a budget or rate stop keeps what was done and the next run resumes.

``--dry-run`` lists the ORCIDs that would be looked up, with no network call and no key.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.ingest.author_repair import (  # noqa: E402
    DEFAULT_ORCID_IDS_PATH,
    ORCID_IDS_HEADER,
    build_orcid_index,
    compact_openalex_id,
    normalize_orcid,
    null_author_orcids,
)
from atlas.ingest.openalex import (  # noqa: E402
    OPENALEX_BASE,
    OpenAlexRateLimitError,
    _request_json,
    load_openalex_key,
)
from atlas.util.budget import daily_logged_usage, resolve_openalex_budget  # noqa: E402
from atlas.util.cost import ApiCostLogger, OpenAlexUsageMetadataError  # noqa: E402

RAW_PATH = Path("data/interim/works_raw.parquet")
USAGE_LOG = Path("data/logs/api_usage.jsonl")
ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
NOT_FOUND_PREFIX = "OpenAlex returned HTTP 404"


class Stop(Exception):
    """Budget or rate stop: keep progress and exit cleanly."""


def load_work_rows(raw_path: Path) -> dict[str, Mapping[str, Any]]:
    """Work objects keyed by compact work ID; the last record for an ID wins, as in normalize."""

    works: dict[str, Mapping[str, Any]] = {}
    for row in pq.read_table(raw_path, columns=["raw_json"]).to_pylist():
        record = json.loads(row["raw_json"])
        if isinstance(record, dict):
            work_id = compact_openalex_id(record.get("id"))
            if work_id:
                works[work_id] = record
    return works


def read_rows(path: Path) -> dict[str, dict[str, str]]:
    """Existing CSV rows keyed by normalized ORCID, including blank (404) rows."""

    if not path.exists():
        return {}
    rows: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            orcid = normalize_orcid(row.get("orcid"))
            if orcid:
                rows[orcid] = {key: str(row.get(key) or "") for key in ORCID_IDS_HEADER}
                rows[orcid]["orcid"] = orcid
    return rows


def write_rows(path: Path, rows: Mapping[str, Mapping[str, str]]) -> None:
    """Rewrite the whole CSV sorted by ORCID with LF line endings, via a temporary file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=ORCID_IDS_HEADER, lineterminator="\n")
        writer.writeheader()
        for orcid in sorted(rows):
            writer.writerow({key: rows[orcid].get(key, "") for key in ORCID_IDS_HEADER})
    temporary.replace(path)


def pending_orcids(
    work_rows: Mapping[str, Mapping[str, Any]], rows: Mapping[str, Any]
) -> list[str]:
    """Null-ID ORCIDs not already mapped by the raw works or the CSV, sorted."""

    indexed = build_orcid_index(work_rows)
    return sorted(
        orcid
        for orcid in null_author_orcids(work_rows)
        if ORCID_RE.match(orcid) and orcid not in indexed and orcid not in rows
    )


def author_row(body: Mapping[str, Any] | None, orcid: str, fetched_at: str) -> dict[str, str]:
    """CSV row for a lookup result; ``None`` (HTTP 404) gives a blank author ID."""

    row = {"orcid": orcid, "author_id": "", "display_name": "", "fetched_at": fetched_at}
    if body is None:
        return row
    found = normalize_orcid(body.get("orcid"))
    if found and found != orcid:
        # A record for a different ORCID must not be attached to this one.
        return row
    row["author_id"] = compact_openalex_id(body.get("id"))
    row["display_name"] = str(body.get("display_name") or "")
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_ORCID_IDS_PATH)
    parser.add_argument("--usage-log", type=Path, default=USAGE_LOG)
    parser.add_argument("--limit", type=int, default=None, help="look up at most N ORCIDs")
    parser.add_argument(
        "--dry-run", action="store_true", help="list the ORCIDs to look up; no network call"
    )
    args = parser.parse_args(argv)
    if not args.raw.exists():
        print(f"{args.raw} not found; run the works fetch first", file=sys.stderr)
        return 1
    rows = read_rows(args.output)
    todo = pending_orcids(load_work_rows(args.raw), rows)
    if args.limit is not None:
        todo = todo[: max(args.limit, 0)]
    if args.dry_run:
        for orcid in todo:
            print(orcid)
        print(f"{len(todo)} ORCIDs to look up", file=sys.stderr)
        return 0
    if not todo:
        print("orcid author ids: nothing to look up")
        return 0

    load_openalex_key()
    budget = resolve_openalex_budget()
    prior_cost, prior_credits = daily_logged_usage(
        args.usage_log, cost_per_credit_usd=budget.cost_per_credit_usd
    )
    fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
    spent = {"cost": Decimal(0), "credits": Decimal(0)}

    def call(url: str, logger: ApiCostLogger) -> dict[str, Any] | None:
        error = budget.reserve_error(
            cost_usd=prior_cost + spent["cost"], credits=prior_credits + spent["credits"]
        )
        if error:
            raise Stop(error)
        before = len(logger.request_metrics)
        try:
            body: dict[str, Any] | None = _request_json(url, logger=logger)
        except OpenAlexRateLimitError as exc:
            raise Stop(f"rate limited ({exc})") from exc
        except OpenAlexUsageMetadataError as exc:
            # A response without a credit header: stop before any retry or write.
            raise Stop(f"OpenAlex request failed ({exc})") from exc
        except RuntimeError as exc:
            if not str(exc).startswith(NOT_FOUND_PREFIX):
                raise
            body = None
        for record in logger.request_metrics[before:]:
            credits = Decimal(str(record.get("credits") or 10))
            spent["credits"] += credits
            spent["cost"] += credits * budget.cost_per_credit_usd
        return body

    looked_up = resolved = 0
    status = "complete"
    with ApiCostLogger(f"orcid-author-ids-{fetched_at}", args.usage_log) as logger:
        try:
            for orcid in todo:
                row = author_row(
                    call(f"{OPENALEX_BASE}/authors/orcid:{orcid}", logger), orcid, fetched_at
                )
                rows[orcid] = row
                write_rows(args.output, rows)
                looked_up += 1
                resolved += bool(row["author_id"])
        except Stop as stop:
            status = f"deferred ({stop})"
    print(
        f"orcid author ids {status}: {looked_up} looked up ({resolved} resolved, "
        f"{looked_up - resolved} not found); {len(todo) - looked_up} pending; "
        f"{spent['credits']} credits"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
