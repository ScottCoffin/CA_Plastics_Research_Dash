#!/usr/bin/env python3
"""Build the BFFP organisation roster (Add-on A4, CG-2 and CG-3).

Usage:
  py -3.14 scripts/build_groups_roster.py --fetch [--acknowledge-drop]   # one live GET (lead only)
  py -3.14 scripts/build_groups_roster.py --input FILE                    # saved JSON or CSV
  py -3.14 scripts/build_groups_roster.py                                 # today's raw cache
  py -3.14 scripts/build_groups_roster.py --check                         # validate committed files

Published (committed) files: site/data/global/groups/roster.json and roster_manifest.json.
Local only (gitignored): data/interim/bffp/roster_manifest.local.json, roster_quarantine.csv,
dupe_review.csv. Excluded counts and names never reach a published file (A4-D20, A4-D24).
Exit codes: 0 ok or SKIP, 1 failure or fetch refused, 2 structural-change guard tripped.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.groups import admission, roster  # noqa: E402
from atlas.regions.registry import load_registry  # noqa: E402

SCHEMA = "cg-roster-v1"
SOURCE_NAME = (
    "Break Free From Plastic member map, organisations only (members_org), "
    "as cited (Break Free From Plastic 2026)"
)
PUBLIC_ROSTER_KEYS = ("schema", "retrieved_at", "source", "source_url", "records")
PUBLIC_RECORD_KEYS = (
    "group_id",
    "name",
    "name_alt",
    "country",
    "region",
    "ambassador_region",
    "url",
    "bffp_listed",
    "bffp_listed_asof",
    "org_status",
    "roster_retrieved_at",
)
PUBLIC_MANIFEST_KEYS = ("retrieved_at", "parser_version", "admitted_by_org_status", "source_urls")
FORBIDDEN_KEY_PARTS = ("total", "exclud", "ambig", "fetch", "individual")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
QUARANTINE_HEADER = ["group_id", "name", "country", "url", "reason"]
DUPE_HEADER = ["country", "reason", "group_id_a", "name_a", "group_id_b", "name_b"]


@dataclass(frozen=True)
class Paths:
    raw_root: Path
    site_dir: Path
    interim_dir: Path


def default_paths() -> Paths:
    return Paths(
        raw_root=roster.DEFAULT_RAW_ROOT,
        site_dir=ROOT / "site" / "data" / "global" / "groups",
        interim_dir=ROOT / "data" / "interim" / "bffp",
    )


def _dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _previous_fetched(interim_dir: Path) -> int | None:
    path = interim_dir / "roster_manifest.local.json"
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8")).get("entries_fetched")
    return value if isinstance(value, int) else None


def _latest_raw(raw_root: Path) -> Path | None:
    if not raw_root.is_dir():
        return None
    candidates = []
    for child in raw_root.iterdir():
        try:
            dt.date.fromisoformat(child.name)
        except ValueError:
            continue
        if (child / roster.RAW_FILE_NAME).exists():
            candidates.append(child / roster.RAW_FILE_NAME)
    return max(candidates, key=lambda p: p.parent.name) if candidates else None


def _write_local(paths: Paths, result: admission.AdmissionResult, meta: dict[str, Any]) -> None:
    paths.interim_dir.mkdir(parents=True, exist_ok=True)
    local = {
        **meta,
        "entries_fetched": result.fetched,
        "admitted_by_org_status": result.admitted_by_status,
        "excluded": result.excluded,
        "ambiguous": len(result.ambiguous),
        "duplicates_collapsed": result.duplicates_collapsed,
        "near_duplicate_pairs": len(result.dupe_review),
    }
    (paths.interim_dir / "roster_manifest.local.json").write_text(_dump(local), encoding="utf-8")
    (paths.interim_dir / "roster_quarantine.csv").write_text(
        admission.render_csv(QUARANTINE_HEADER, result.ambiguous), encoding="utf-8"
    )
    (paths.interim_dir / "dupe_review.csv").write_text(
        admission.render_csv(DUPE_HEADER, result.dupe_review), encoding="utf-8"
    )


def _write_public(paths: Paths, result: admission.AdmissionResult, day: dt.date) -> None:
    paths.site_dir.mkdir(parents=True, exist_ok=True)
    records = [{key: record[key] for key in PUBLIC_RECORD_KEYS} for record in result.records]
    roster_payload = {
        "schema": SCHEMA,
        "retrieved_at": day.isoformat(),
        "source": SOURCE_NAME,
        "source_url": roster.BFFP_MEMBERS_ORG_URL,
        "records": records,
    }
    manifest = {
        "retrieved_at": day.isoformat(),
        "parser_version": roster.PARSER_VERSION,
        "admitted_by_org_status": result.admitted_by_status,
        "source_urls": [roster.BFFP_MEMBERS_ORG_URL],
    }
    # Site JSON is LF-pinned; write LF on Windows too so a rebuild matches the committed bytes.
    (paths.site_dir / "roster.json").write_bytes(_dump(roster_payload).encode("utf-8"))
    (paths.site_dir / "roster_manifest.json").write_bytes(_dump(manifest).encode("utf-8"))


def build(
    input_path: Path | None,
    *,
    fetch: bool,
    acknowledge_drop: bool,
    paths: Paths,
    day: dt.date,
    fetcher: roster.Fetcher | None,
) -> int:
    if fetch:
        # Default: view BFFP's public page and keep the list it loads (direct GETs get 403).
        source = roster.BffpPublicSource(paths.raw_root, fetcher or roster.page_fetcher, today=day)
        try:
            entries = list(source.fetch())
        except roster.RosterFetchError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        raw_path = source.raw_path
        meta_request = {
            "request_count": source.request_count,
            "status_counts": source.status_counts,
        }
    else:
        raw_path = input_path or paths.raw_root / day.isoformat() / roster.RAW_FILE_NAME
        if not raw_path.exists():
            print("ERROR: no raw input; run with --fetch or --input FILE", file=sys.stderr)
            return 1
        try:
            entries = roster.read_raw_file(raw_path)
        except (roster.RosterFetchError, roster.RosterStructureError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        meta_request = {"request_count": 0, "status_counts": {}}
    try:
        roster.check_structural_change(
            len(entries), _previous_fetched(paths.interim_dir), acknowledge_drop=acknowledge_drop
        )
    except roster.RosterStructureError as exc:
        print(f"GUARD: {exc}", file=sys.stderr)
        return 2
    result = admission.admit(entries, retrieved_on=day.isoformat(), registry=load_registry())
    meta = {
        "retrieved_at": day.isoformat(),
        "parser_version": roster.PARSER_VERSION,
        "source_urls": [roster.BFFP_MEMBERS_ORG_URL],
        **meta_request,
        "raw_sha256": roster.sha256_file(raw_path),
        "drop_acknowledged": acknowledge_drop,
    }
    _write_public(paths, result, day)
    _write_local(paths, result, meta)
    roster.purge_raw_cache(paths.raw_root, dt.datetime.combine(day, dt.time(), tzinfo=dt.UTC))
    counts = ", ".join(f"{k}={v}" for k, v in result.admitted_by_status.items())
    # Admitted counts only: a fetched total would reveal how many entries were dropped (A4-D24),
    # and CI logs of this public repository are public. The local manifest keeps the rest.
    print(f"OK: admitted: {counts}; records={len(result.records)}")
    return 0


def _check_record(index: int, record: Any, problems: list[str]) -> None:
    if not isinstance(record, dict) or set(record) != set(PUBLIC_RECORD_KEYS):
        problems.append(f"record {index}: keys must be exactly {PUBLIC_RECORD_KEYS}")
        return
    if record["org_status"] not in admission.ADMITTED_STATUSES:
        problems.append(f"record {index}: org_status {record['org_status']!r} not admitted")
    if record["bffp_listed"] is not True:
        problems.append(f"record {index}: bffp_listed must be true")
    if record["country"] is not None and not re.fullmatch(r"[A-Z]{2}", str(record["country"])):
        problems.append(f"record {index}: country must be ISO alpha-2 or null")


def check(paths: Paths) -> int:
    """Validate the committed roster; rebuild and compare when a raw cache exists."""
    roster_path = paths.site_dir / "roster.json"
    manifest_path = paths.site_dir / "roster_manifest.json"
    if not roster_path.exists() or not manifest_path.exists():
        print("FAIL: committed roster files are missing")
        return 1
    problems: list[str] = []
    for path in (roster_path, manifest_path):
        if EMAIL_RE.search(path.read_text(encoding="utf-8")):
            problems.append(f"{path.name}: contains an email-like string")
    payload = json.loads(roster_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != set(PUBLIC_ROSTER_KEYS):
        problems.append(f"roster.json: top-level keys must be exactly {PUBLIC_ROSTER_KEYS}")
    if payload.get("schema") != SCHEMA:
        problems.append(f"roster.json: schema must be {SCHEMA!r}")
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        problems.append("roster.json: records must be a list")
        records = []
    for index, record in enumerate(records):
        _check_record(index, record, problems)
    ids = [r.get("group_id") for r in records if isinstance(r, dict)]
    if len(ids) != len(set(ids)):
        problems.append("roster.json: group_id values are not unique")
    if set(manifest) != set(PUBLIC_MANIFEST_KEYS):
        problems.append(f"roster_manifest.json: keys must be exactly {PUBLIC_MANIFEST_KEYS}")
    for key in list(manifest) + list(payload):
        if any(part in str(key).lower() for part in FORBIDDEN_KEY_PARTS):
            problems.append(f"public file: forbidden key {key!r}")
    by_status = manifest.get("admitted_by_org_status", {})
    if set(by_status) != set(admission.ADMITTED_STATUSES):
        problems.append("roster_manifest.json: admitted_by_org_status must list every status")
    elif sum(by_status.values()) != len(records):
        problems.append("roster_manifest.json: admitted counts do not match the records")
    raw = _latest_raw(paths.raw_root)
    if raw is None:
        if problems:
            print("FAIL:\n  " + "\n  ".join(problems))
            return 1
        print("PASS (structure); SKIP rebuild comparison: no raw cache")
        return 0
    rebuilt = admission.admit(
        roster.read_raw_file(raw),
        retrieved_on=str(payload.get("retrieved_at", "")),
        registry=load_registry(),
    )
    volatile = ("bffp_listed_asof", "roster_retrieved_at")

    def stable(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{k: v for k, v in r.items() if k not in volatile} for r in items]

    if stable(rebuilt.records) != stable(records):
        problems.append("roster.json: does not match a rebuild from the raw cache")
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    print("PASS (structure and rebuild comparison)")
    return 0


def main(
    argv: list[str] | None = None,
    *,
    paths: Paths | None = None,
    fetcher: roster.Fetcher | None = None,
    today: dt.date | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--fetch",
        action="store_true",
        help="one view of the BFFP About page, keeping the member list it loads",
    )
    mode.add_argument("--input", type=Path, help="saved members_org JSON or CSV export")
    mode.add_argument("--check", action="store_true", help="validate committed files")
    parser.add_argument(
        "--acknowledge-drop", action="store_true", help="accept a >20%% drop in entry count"
    )
    args = parser.parse_args(argv)
    resolved = paths or default_paths()
    if args.check:
        return check(resolved)
    day = today or dt.datetime.now(dt.UTC).date()
    return build(
        args.input,
        fetch=args.fetch,
        acknowledge_drop=args.acknowledge_drop,
        paths=resolved,
        day=day,
        fetcher=fetcher,
    )


if __name__ == "__main__":
    raise SystemExit(main())
