#!/usr/bin/env python3
"""Build the BFFP organisation roster (Add-on A4, CG-2 and CG-3).

Usage:
  py -3.14 scripts/build_groups_roster.py --fetch [--incremental]       # one live member-list fetch
  py -3.14 scripts/build_groups_roster.py --input FILE                    # saved JSON or CSV
  py -3.14 scripts/build_groups_roster.py                                 # today's raw cache
  py -3.14 scripts/build_groups_roster.py --check [--incremental]       # validate committed files

Published (committed) files: site/data/global/groups/roster.json and roster_manifest.json.
Reviewed curation read at build time: curation/group_merges.csv (same/different decisions),
curation/group_name_corrections.csv (display names; the group_id never changes).
Local only (gitignored): data/interim/bffp/roster_manifest.local.json, roster_quarantine.csv,
dupe_review.csv, auto_merges.csv. Excluded counts and names never reach a published file
(A4-D20, A4-D24).
Exit codes: 0 ok or SKIP, 1 failure or fetch refused, 2 structural-change guard tripped.
"""

from __future__ import annotations

import argparse
import csv
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
MERGES_FILE = "group_merges.csv"
NAME_CORRECTIONS_FILE = "group_name_corrections.csv"


@dataclass(frozen=True)
class Paths:
    raw_root: Path
    site_dir: Path
    interim_dir: Path
    curation_dir: Path = ROOT / "curation"


def default_paths() -> Paths:
    return Paths(
        raw_root=roster.DEFAULT_RAW_ROOT,
        site_dir=ROOT / "site" / "data" / "global" / "groups",
        interim_dir=ROOT / "data" / "interim" / "bffp",
        curation_dir=ROOT / "curation",
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
        "placeholders_quarantined": result.placeholders,
        "auto_merged_records": len(result.auto_merges),
        "reviewed_merges_applied": result.reviewed_merges_applied,
        "reviewed_merges_unmatched": result.reviewed_merges_unmatched,
    }
    (paths.interim_dir / "roster_manifest.local.json").write_text(_dump(local), encoding="utf-8")
    (paths.interim_dir / "roster_quarantine.csv").write_text(
        admission.render_csv(QUARANTINE_HEADER, result.ambiguous), encoding="utf-8"
    )
    (paths.interim_dir / "dupe_review.csv").write_text(
        admission.render_csv(DUPE_HEADER, result.dupe_review), encoding="utf-8"
    )
    (paths.interim_dir / "auto_merges.csv").write_text(
        admission.render_csv(admission.AUTO_MERGE_HEADER, result.auto_merges), encoding="utf-8"
    )


def _curation_inputs(curation_dir: Path) -> tuple[list[dict[str, str]], dict[str, str]]:
    """Reviewed merges and name corrections. Raises ValueError or OSError when they are invalid."""
    merges = admission.read_merges(curation_dir / MERGES_FILE)
    corrections = admission.read_name_corrections(curation_dir / NAME_CORRECTIONS_FILE)
    return merges, corrections


def _apply_corrections(records: list[dict[str, Any]], corrections: dict[str, str]) -> None:
    """Apply corrected display names in place; each old name is kept in name_alt."""
    for record in records:
        if record["group_id"] in corrections:
            admission.apply_name_correction(record, corrections[record["group_id"]])


def _not_organisations(curation_dir: Path, records: list[dict[str, Any]]) -> set[str]:
    """Read the approved hash IDs that must be removed from every public denominator."""
    path = curation_dir / "group_tags.csv"
    if not path.exists():
        return set()
    with path.open(encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        excluded: set[str] = set()
        roster_ids = {str(record["group_id"]) for record in records}
        for row in rows:
            group_id = (row.get("group_id") or "").strip()
            flag = (row.get("not_an_organisation") or "").strip()
            if flag not in ("", "true", "false"):
                raise ValueError("group_tags.csv contains an invalid not_an_organisation flag")
            if flag == "true" and group_id in roster_ids:
                excluded.add(group_id)
        return excluded


def _write_public(paths: Paths, records: list[dict[str, Any]], day: dt.date) -> None:
    paths.site_dir.mkdir(parents=True, exist_ok=True)
    admitted_by_status = {status: 0 for status in admission.ADMITTED_STATUSES}
    for record in records:
        admitted_by_status[record["org_status"]] += 1
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
        "admitted_by_org_status": admitted_by_status,
        "source_urls": [roster.BFFP_MEMBERS_ORG_URL],
    }
    # Site JSON is LF-pinned; write LF on Windows too so a rebuild matches the committed bytes.
    for path, value in (
        (paths.site_dir / "roster.json", roster_payload),
        (paths.site_dir / "roster_manifest.json", manifest),
    ):
        data = _dump(value).encode("utf-8")
        if not path.exists() or path.read_bytes() != data:
            path.write_bytes(data)


def _load_existing(paths: Paths, *, required: bool) -> tuple[list[dict[str, Any]], dt.date | None]:
    path = paths.site_dir / "roster.json"
    if (
        not required
        and not path.exists()
        and not (paths.site_dir / "roster_manifest.json").exists()
    ):
        return [], None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError("invalid roster schema")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("invalid records")
    problems: list[str] = []
    for index, row in enumerate(records):
        _check_record(index, row, problems)
    if problems or len({row["group_id"] for row in records}) != len(records):
        raise ValueError("invalid or duplicate roster records")
    return records, dt.date.fromisoformat(payload["retrieved_at"])


def _name_keys(row: dict[str, Any]) -> set[tuple[str, str]]:
    country = row["country"]
    if country is None:
        return set()
    names = [row["name"], *row["name_alt"]]
    return {(country, key) for name in names if (key := admission.merge_key(name))}


def _incremental_records(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    merges: list[dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Overlay current admissions while retaining established roster identities."""
    result = [dict(row) for row in existing]
    by_id = {str(row["group_id"]): i for i, row in enumerate(result)}
    reviewed_same = {
        merge["group_id_drop"]: merge["group_id_keep"]
        for merge in merges or []
        if merge.get("decision") == "same"
    }
    reviewed_different = {
        frozenset((merge["group_id_keep"], merge["group_id_drop"]))
        for merge in merges or []
        if merge.get("decision") == "different"
    }
    by_name: dict[tuple[str, str], set[int]] = {}
    for i, row in enumerate(result):
        for key in _name_keys(row):
            by_name.setdefault(key, set()).add(i)
    for candidate in incoming:
        candidate_id = str(candidate["group_id"])
        idx = by_id.get(reviewed_same.get(candidate_id, candidate_id))
        if idx is None:
            matches: set[int] = set()
            for key in _name_keys(candidate):
                matches.update(by_name.get(key, ()))
            safe = [
                i
                for i in matches
                if frozenset((str(result[i]["group_id"]), candidate_id)) not in reviewed_different
            ]
            idx = next(iter(safe)) if len(safe) == 1 else None
        if idx is None:
            idx = len(result)
            result.append(dict(candidate))
            by_id[candidate_id] = idx
            for key in _name_keys(candidate):
                by_name.setdefault(key, set()).add(idx)
    return result


def build(
    input_path: Path | None,
    *,
    fetch: bool,
    acknowledge_drop: bool,
    paths: Paths,
    day: dt.date,
    fetcher: roster.Fetcher | None,
    incremental: bool = False,
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
    existing_records: list[dict[str, Any]] = []
    prior_day = None
    try:
        previous = _previous_fetched(paths.interim_dir)
        if incremental:
            existing_records, prior_day = _load_existing(paths, required=fetch)
            previous = max(previous or 0, len(existing_records))
        roster.check_structural_change(len(entries), previous, acknowledge_drop=acknowledge_drop)
    except roster.RosterStructureError as exc:
        print(f"GUARD: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError):
        print("ERROR: existing roster is invalid; public roster was not written", file=sys.stderr)
        return 1
    try:
        merges, corrections = _curation_inputs(paths.curation_dir)
    except (OSError, csv.Error, ValueError) as exc:
        print(
            f"ERROR: invalid group curation ({exc}); public roster was not written", file=sys.stderr
        )
        return 1
    result = admission.admit(
        entries, retrieved_on=day.isoformat(), registry=load_registry(), merges=merges
    )
    if incremental:
        result.records = _incremental_records(existing_records, result.records, merges)
    _apply_corrections(result.records, corrections)
    meta = {
        "retrieved_at": day.isoformat(),
        "parser_version": roster.PARSER_VERSION,
        "source_urls": [roster.BFFP_MEMBERS_ORG_URL],
        **meta_request,
        "raw_sha256": roster.sha256_file(raw_path),
        "drop_acknowledged": acknowledge_drop,
    }
    try:
        excluded_ids = _not_organisations(paths.curation_dir, result.records)
    except (OSError, csv.Error, ValueError):
        print("ERROR: invalid group curation; public roster was not written", file=sys.stderr)
        return 1
    records = [
        {key: row[key] for key in PUBLIC_RECORD_KEYS}
        for row in result.records
        if row["group_id"] not in excluded_ids
    ]
    published_day = prior_day if prior_day is not None and records == existing_records else day
    _write_public(paths, records, published_day)
    _write_local(paths, result, meta)
    roster.purge_raw_cache(paths.raw_root, dt.datetime.combine(day, dt.time(), tzinfo=dt.UTC))
    # Keep public logs silent about record volumes; the private local manifest retains diagnostics.
    print("OK: roster files written")
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
    if not isinstance(record["group_id"], str) or not re.fullmatch(
        r"cg_[0-9a-f]{16}", record["group_id"]
    ):
        problems.append(f"record {index}: invalid group ID")
    if (
        not isinstance(record["name"], str)
        or not isinstance(record["name_alt"], list)
        or any(not isinstance(name, str) for name in record["name_alt"])
    ):
        problems.append(f"record {index}: invalid display or alternate names")


def check(paths: Paths, *, incremental: bool = False) -> int:
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
    if incremental:
        if not problems:
            try:
                _, corrections = _curation_inputs(paths.curation_dir)
                if _not_organisations(paths.curation_dir, records):
                    problems.append("roster.json: does not apply current group curation")
                if any(corrections.get(r["group_id"], r["name"]) != r["name"] for r in records):
                    problems.append("roster.json: does not apply current name corrections")
            except (OSError, csv.Error, ValueError):
                problems.append("group curation: invalid")
        if problems:
            print("FAIL:\n  " + "\n  ".join(problems))
            return 1
        print("PASS (structure and curation)")
        return 0
    raw = _latest_raw(paths.raw_root)
    if raw is None:
        try:
            excluded_ids = _not_organisations(paths.curation_dir, records)
        except (OSError, csv.Error, ValueError):
            problems.append("group_tags.csv: invalid roster exclusion curation")
            excluded_ids = set()
        if any(record.get("group_id") in excluded_ids for record in records):
            problems.append("roster.json: does not apply current group curation")
        if problems:
            print("FAIL:\n  " + "\n  ".join(problems))
            return 1
        print("PASS (structure); SKIP rebuild comparison: no raw cache")
        return 0
    try:
        merges, corrections = _curation_inputs(paths.curation_dir)
    except (OSError, csv.Error, ValueError):
        problems.append("group curation (merges or name corrections): invalid")
        merges, corrections = [], {}
    rebuilt = admission.admit(
        roster.read_raw_file(raw),
        retrieved_on=str(payload.get("retrieved_at", "")),
        registry=load_registry(),
        merges=merges,
    )
    _apply_corrections(rebuilt.records, corrections)
    try:
        excluded_ids = _not_organisations(paths.curation_dir, rebuilt.records)
    except (OSError, csv.Error, ValueError):
        problems.append("group_tags.csv: invalid roster exclusion curation")
        excluded_ids = set()
    rebuilt_records = [r for r in rebuilt.records if r["group_id"] not in excluded_ids]
    volatile = ("bffp_listed_asof", "roster_retrieved_at")

    def stable(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{k: v for k, v in r.items() if k not in volatile} for r in items]

    if stable(rebuilt_records) != stable(records):
        problems.append("roster.json: does not match a rebuild from the raw cache")
    if problems:
        print("FAIL:\n  " + "\n  ".join(problems))
        return 1
    print("PASS (structure and rebuild comparison)")
    return 0


def apply_curation(paths: Paths) -> int:
    """Apply approved organisation removals to the committed roster without raw source data."""
    roster_path = paths.site_dir / "roster.json"
    manifest_path = paths.site_dir / "roster_manifest.json"
    try:
        payload = json.loads(roster_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        records = payload["records"]
        excluded_ids = _not_organisations(paths.curation_dir, records)
    except (OSError, KeyError, TypeError, json.JSONDecodeError, csv.Error, ValueError):
        print("ERROR: committed roster or group curation is invalid", file=sys.stderr)
        return 1
    kept = [record for record in records if record.get("group_id") not in excluded_ids]
    by_status = {status: 0 for status in admission.ADMITTED_STATUSES}
    try:
        for record in kept:
            by_status[record["org_status"]] += 1
    except (KeyError, TypeError):
        print("ERROR: committed roster is invalid", file=sys.stderr)
        return 1
    payload["records"] = kept
    manifest["admitted_by_org_status"] = by_status
    (paths.site_dir / "roster.json").write_bytes(_dump(payload).encode("utf-8"))
    (paths.site_dir / "roster_manifest.json").write_bytes(_dump(manifest).encode("utf-8"))
    print("OK: applied current group curation to the roster")
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
        "--incremental", action="store_true", help="preserve established roster IDs"
    )
    mode.add_argument(
        "--apply-curation",
        action="store_true",
        help=(
            "apply approved removals without raw data; restoration requires clearing the curation "
            "flag and rebuilding from raw source"
        ),
    )
    parser.add_argument(
        "--acknowledge-drop", action="store_true", help="accept a >20%% drop in entry count"
    )
    args = parser.parse_args(argv)
    resolved = paths or default_paths()
    if args.check:
        return check(resolved, incremental=args.incremental)
    if args.apply_curation:
        return apply_curation(resolved)
    day = today or dt.datetime.now(dt.UTC).date()
    return build(
        args.input,
        fetch=args.fetch,
        acknowledge_drop=args.acknowledge_drop,
        paths=resolved,
        day=day,
        fetcher=fetcher,
        incremental=args.incremental,
    )


if __name__ == "__main__":
    raise SystemExit(main())
