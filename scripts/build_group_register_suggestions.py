#!/usr/bin/env python3
"""Build register_suggestions.json (cg-register-suggestions-v1): IRS EO BMF roster suggestions.

GRP-ENRICH slice 3 (ADR-GRP-ENRICH-2026-11-26). Facts here are suggestions only: an ambassador
confirms each one with evidence, and nothing is tagged automatically. Source: IRS Exempt
Organizations Business Master File, US government data (no licence statement on the IRS page).

Usage:
  py -3.14 scripts/build_group_register_suggestions.py             # download (cached) and write
  py -3.14 scripts/build_group_register_suggestions.py --offline   # use only the raw cache
  py -3.14 scripts/build_group_register_suggestions.py --check     # validate; rebuild if cached

Downloads go to data/raw/irs_eo_bmf/<date>/ (ignored, never committed), one request a second,
only to www.irs.gov. A snapshot is complete once COMPLETE.txt is written.

Matching: roster records with country US only. The primary NAME column is compared with the roster
name after atlas.groups.admission.merge_key (with "&" read as "and"). Alternate names are not used.
A roster group that matches several EINs is dropped, and so is an EIN that matches several groups.

NTEE hints are conservative (see NTEE_MAJOR_SECTOR, NTEE_ACTIVITY and higher_ed_code). Every value
is checked against config/groups_taxonomy.yml. Exit codes: 0 ok, 1 invalid or differs from the
rebuild, 2 network error or cache miss.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.groups import admission  # noqa: E402
from atlas.groups.build import to_bytes  # noqa: E402
from atlas.groups.schema import load_taxonomy  # noqa: E402

GROUPS_DIR = ROOT / "site" / "data" / "global" / "groups"
ROSTER_PATH = GROUPS_DIR / "roster.json"
OUTPUT_PATH = GROUPS_DIR / "register_suggestions.json"
RAW_DIR = ROOT / "data" / "raw" / "irs_eo_bmf"

SCHEMA = "cg-register-suggestions-v1"
SOURCE = "IRS Exempt Organizations Business Master File (US government data)"
REGISTER = "irs_eo_bmf"
COUNTRY = "US"
INDEX_URL = "https://www.irs.gov/charities-non-profits/exempt-organizations-business-master-file-extract-eo-bmf"
FILE_URL = "https://www.irs.gov/pub/irs-soi/"
USER_AGENT = "PlastiverseLive/1.0 (https://plastiverse.live)"
PAUSE = 1.0  # seconds between requests
TIMEOUT = 120
COMPLETE_MARKER = "COMPLETE.txt"
MIN_STATE_FILES = 50
STATE_FILE_RE = re.compile(r"/pub/irs-soi/(eo_[a-z]{2}\.csv)")
EIN_RE = re.compile(r"^\d{9}$")
NTEE_RE = re.compile(r"^[A-Z][0-9A-Z]{2,3}$")
RULING_RE = re.compile(r"^(\d{4})\d{2}$")
STATE_RE = re.compile(r"^[A-Z]{2}$")
MIN_YEAR = 1800

# NTEE major letter -> sector hint. Only C (environment) and T (philanthropy) are mapped broadly.
NTEE_MAJOR_SECTOR = {"C": "ngo_civil_society", "T": "foundation"}
# Higher education (B40-B49 and B50) -> academia_research. Other B codes get no sector hint.
HIGHER_ED_RE = re.compile(r"^B(4\d|50)")
# Three-character NTEE code -> activity hints. Codes not listed get no activity hint (C30, C32,
# C34 and C36 are natural resources, water and land: no hint).
NTEE_ACTIVITY = {
    "C01": ("advocacy_campaigning",),  # alliances and advocacy
    "C05": ("research_monitoring",),  # research
    "C27": ("waste_management_recycling",),  # recycling
    "C60": ("education_awareness",),  # environmental education
}

_TAXONOMY = load_taxonomy()
SECTORS = frozenset(_TAXONOMY["sector"])
ACTIVITIES = frozenset(_TAXONOMY["primary_activities"])


class RegisterError(Exception):
    """Network failure, unexpected response or an incomplete cache."""


class CacheMiss(RegisterError):
    """Offline run needs a snapshot that is not in the cache."""


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read()
    except Exception as exc:  # network, HTTP or timeout: one error type for the caller
        raise RegisterError(f"request to www.irs.gov failed: {exc}") from exc


def discover_state_files(index_page: bytes) -> list[str]:
    """The eo_<state>.csv file names linked from the IRS EO BMF page (regions eo1-4 excluded)."""
    names = sorted(set(STATE_FILE_RE.findall(index_page.decode("utf-8", errors="replace"))))
    if len(names) < MIN_STATE_FILES:
        raise RegisterError(f"found {len(names)} state files on the IRS page; expected 50 or more")
    return names


def download_snapshot(
    snapshot: Path,
    names: Sequence[str],
    fetch: Callable[[str], bytes] = _get,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Fetch missing files into snapshot, one request per PAUSE seconds, then mark it complete."""
    snapshot.mkdir(parents=True, exist_ok=True)
    for name in names:
        dest = snapshot / name
        if dest.exists():
            continue
        sleep(PAUSE)
        data = fetch(FILE_URL + name)
        if not data.startswith(b"EIN,"):
            raise RegisterError(f"{name} does not look like an EO BMF file; not stored")
        tmp = snapshot / (name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
    (snapshot / COMPLETE_MARKER).write_text("\n".join(names) + "\n", encoding="utf-8")


def fetch_snapshot(snapshot: Path, fetch: Callable[[str], bytes] = _get) -> Path:
    """Return the complete snapshot directory, downloading it first if needed."""
    if (snapshot / COMPLETE_MARKER).exists():
        return snapshot
    names = discover_state_files(fetch(INDEX_URL))
    download_snapshot(snapshot, names, fetch=fetch)
    return snapshot


def _is_date(text: str) -> bool:
    try:
        dt.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def latest_snapshot(raw_dir: Path = RAW_DIR) -> Path | None:
    """The newest complete snapshot directory (named by date), or None."""
    if not raw_dir.is_dir():
        return None
    complete = [
        p
        for p in raw_dir.iterdir()
        if p.is_dir() and _is_date(p.name) and (p / COMPLETE_MARKER).exists()
    ]
    return max(complete, key=lambda p: p.name, default=None)


def iter_rows(snapshot: Path) -> Iterator[dict[str, str]]:
    for path in sorted(snapshot.glob("eo_*.csv")):
        with path.open(encoding="utf-8", errors="replace", newline="") as fh:
            yield from csv.DictReader(fh)


def name_key(name: str | None) -> str:
    """merge_key of the name, with "&" read as "and" ("Paper & Plastics" = "Paper and Plastics")."""
    return admission.merge_key(html.unescape(name or "").replace("&", " and "))


def ntee_hints(code: str | None) -> tuple[str | None, tuple[str, ...]]:
    """(sector_hint, activity_hints) for an NTEE code. Unknown codes give (None, ())."""
    if not code:
        return None, ()
    sector = NTEE_MAJOR_SECTOR.get(code[:1])
    if code[:1] == "B" and HIGHER_ED_RE.match(code):
        sector = "academia_research"
    return sector, NTEE_ACTIVITY.get(code[:3], ())


def _text(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def _ruling_year(value: str | None, today_year: int) -> int | None:
    """RULING is YYYYMM; return the year when it is plausible."""
    m = RULING_RE.match((value or "").strip())
    if not m:
        return None
    year = int(m.group(1))
    return year if MIN_YEAR <= year <= today_year else None


def register_entry(ein: str, row: Mapping[str, str], today_year: int) -> dict[str, Any]:
    code = (row.get("NTEE_CD") or "").strip().upper() or None
    sector, activities = ntee_hints(code)
    return {
        "register": REGISTER,
        "ein": ein,
        "registered_name": (row.get("NAME") or "").strip(),
        "city": _text(row.get("CITY")),
        "state": _text(row.get("STATE")),
        "ruling_year": _ruling_year(row.get("RULING"), today_year),
        "ntee_code": code,
        "ntee_major": code[:1] if code else None,
        "sector_hint": sector,
        "activity_hints": list(activities),
    }


def match_groups(
    records: Sequence[Mapping[str, Any]], rows: Iterable[Mapping[str, str]], today_year: int
) -> tuple[dict[str, dict[str, Any]], Counter]:
    """Return ({group_id: entry}, counts) for US roster records with one unambiguous EIN."""
    stats: Counter = Counter()
    keys: dict[str, str] = {}
    for rec in records:
        if rec.get("country") != COUNTRY:
            continue
        key = name_key(rec.get("name"))
        if key:
            keys[rec["group_id"]] = key
    wanted = set(keys.values())
    eins_by_key: dict[str, dict[str, Mapping[str, str]]] = defaultdict(dict)
    for row in rows:
        key = name_key(row.get("NAME"))
        ein = (row.get("EIN") or "").strip()
        if key in wanted and EIN_RE.match(ein):
            eins_by_key[key].setdefault(ein, row)

    hit: dict[str, tuple[str, Mapping[str, str]]] = {}
    for gid, key in sorted(keys.items()):
        found = eins_by_key.get(key, {})
        if len(found) == 1:
            hit[gid] = next(iter(found.items()))
        elif len(found) > 1:
            stats["ambiguous_group"] += 1

    owners: dict[str, list[str]] = defaultdict(list)
    for gid, (ein, _) in hit.items():
        owners[ein].append(gid)
    for gids in owners.values():
        if len(gids) > 1:
            stats["ambiguous_ein"] += len(gids)
            for gid in gids:
                del hit[gid]

    groups: dict[str, dict[str, Any]] = {}
    for gid in sorted(hit):
        ein, row = hit[gid]
        entry = register_entry(ein, row, today_year)
        groups[gid] = entry
        stats["matched"] += 1
        stats[f"ntee_major_{entry['ntee_major'] or '-'}"] += 1
    return groups, stats


def validate(doc: Mapping[str, Any], group_ids: set[str], today_year: int) -> list[str]:
    """Structure checks shared by the build and --check. Returns error strings (empty if valid)."""
    errors: list[str] = []
    if doc.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if doc.get("source") != SOURCE:
        errors.append(f"source must be {SOURCE}")
    try:
        dt.date.fromisoformat(str(doc.get("retrieved_at")))
    except ValueError:
        errors.append("retrieved_at must be YYYY-MM-DD")
    groups = doc.get("groups")
    if not isinstance(groups, dict):
        return errors + ["groups must be an object"]
    for gid, item in sorted(groups.items()):
        where = f"groups[{gid}]"
        if gid not in group_ids:
            errors.append(f"{where}: not a roster group_id")
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object")
            continue
        if item.get("register") != REGISTER:
            errors.append(f"{where}: register must be {REGISTER}")
        if not isinstance(item.get("ein"), str) or not EIN_RE.match(item["ein"]):
            errors.append(f"{where}: ein must be nine digits")
        if not isinstance(item.get("registered_name"), str) or not item["registered_name"]:
            errors.append(f"{where}: registered_name must be a non-empty string")
        for field in ("city", "state"):
            if item.get(field) is not None and not isinstance(item.get(field), str):
                errors.append(f"{where}: {field} must be a string or null")
        state = item.get("state")
        if isinstance(state, str) and not STATE_RE.match(state):
            errors.append(f"{where}: state must be two capital letters")
        year = item.get("ruling_year")
        if year is not None and not (isinstance(year, int) and MIN_YEAR <= year <= today_year):
            errors.append(f"{where}: ruling_year out of range")
        code = item.get("ntee_code")
        if code is not None and not (isinstance(code, str) and NTEE_RE.match(code)):
            errors.append(f"{where}: ntee_code must be an NTEE code or null")
        major = item.get("ntee_major")
        if major != (code[:1] if isinstance(code, str) else None):
            errors.append(f"{where}: ntee_major must be the first letter of ntee_code")
        sector = item.get("sector_hint")
        if sector is not None and sector not in SECTORS:
            errors.append(f"{where}: sector_hint is not in the sector vocabulary")
        hints = item.get("activity_hints")
        if not isinstance(hints, list) or not all(h in ACTIVITIES for h in hints):
            errors.append(f"{where}: activity_hints must list primary_activities values")
        elif len(set(hints)) != len(hints):
            errors.append(f"{where}: activity_hints must not repeat")
    return errors


def render(
    records: Sequence[Mapping[str, Any]],
    rows: Iterable[Mapping[str, str]],
    committed: Mapping[str, Any] | None,
    retrieved: str,
) -> tuple[dict[str, Any], Counter]:
    """Build the document. retrieved_at keeps the committed date when the groups are unchanged."""
    groups, stats = match_groups(records, rows, dt.date.fromisoformat(retrieved).year)
    kept = retrieved
    if committed and committed.get("groups") == groups and committed.get("retrieved_at"):
        kept = committed["retrieved_at"]
    doc = {"schema": SCHEMA, "source": SOURCE, "retrieved_at": kept, "groups": groups}
    return doc, stats


def load_roster(path: Path = ROSTER_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["records"]


def _read_committed(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _summary(stats: Counter, groups: Mapping[str, Any]) -> str:
    majors = sorted(k.removeprefix("ntee_major_") for k in stats if k.startswith("ntee_major_"))
    dist = " ".join(f"{m}={stats['ntee_major_' + m]}" for m in majors)
    return (
        f"groups={len(groups)} matched={stats['matched']} "
        f"ambiguous_group={stats['ambiguous_group']} ambiguous_ein={stats['ambiguous_ein']} "
        f"ntee_major: {dist}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true", help="validate the committed file")
    parser.add_argument("--offline", action="store_true", help="use only the raw cache")
    args = parser.parse_args(argv)

    today = dt.date.today()
    roster = load_roster(ROSTER_PATH)
    group_ids = {r["group_id"] for r in roster}
    committed = _read_committed(OUTPUT_PATH)

    if args.check:
        if committed is None:
            print(f"{OUTPUT_PATH.name} is missing; run scripts/build_group_register_suggestions.py")
            return 1
        errors = validate(committed, group_ids, today.year)
        if errors:
            print("\n".join(errors[:20]))
            return 1
        print(f"{OUTPUT_PATH.name} structure is valid ({len(committed['groups'])} groups)")
        snapshot = latest_snapshot(RAW_DIR)
        if snapshot is None:
            print("no raw cache; structure checked only")
            return 0
        try:
            doc, _ = render(roster, iter_rows(snapshot), committed, snapshot.name)
        except RegisterError as exc:
            print(f"cache does not cover this roster: {exc}")
            return 1
        if to_bytes(doc) != OUTPUT_PATH.read_bytes():
            print(f"{OUTPUT_PATH.name} differs from the offline rebuild; run the builder")
            return 1
        print(f"{OUTPUT_PATH.name} matches the offline rebuild from the cache")
        return 0

    try:
        if args.offline:
            snapshot = latest_snapshot(RAW_DIR)
            if snapshot is None:
                raise CacheMiss(
                    "no complete snapshot in data/raw/irs_eo_bmf; run without --offline"
                )
        else:
            snapshot = fetch_snapshot(RAW_DIR / today.isoformat())
        doc, stats = render(roster, iter_rows(snapshot), committed, snapshot.name)
    except RegisterError as exc:
        print(f"stopped: {exc}")
        return 2
    print(_summary(stats, doc["groups"]))
    errors = validate(doc, group_ids, today.year)
    if errors:
        print("\n".join(errors[:20]))
        return 1
    OUTPUT_PATH.write_bytes(to_bytes(doc))
    print(f"wrote {OUTPUT_PATH.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
