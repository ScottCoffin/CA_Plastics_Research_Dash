"""S2.5: eScholarship campus evidence for works with an eScholarship copy.

Owner decision 2026-11-11 (ESCH-CA): use eScholarship's UC affiliation evidence. For every
work whose OpenAlex record has an eScholarship location (source S4306400115), in the raw
corpus or in the latest ``audit_escholarship_openalex.py`` snapshots, fetch the item from
eScholarship's public GraphQL read API (one request per item, 2 s apart, cached under
gitignored ``data/raw/escholarship_items/``) and record:

* ``ca_evidence``: ``etd`` (UC thesis/dissertation; the sole author was a UC student),
  ``uc_oa_policy`` (UC open-access-policy deposit, "Previously Published Works": at least
  one author is UC, which one is not stated), ``uc_unit`` (other campus/department series),
  or ``journal_only`` (a UC-hosted journal: authors can be anywhere, so no CA evidence);
* ``campuses``: campus unit ids reached through the unit parents (e.g. ``ucd``, ``lbnl``);
* author names and ORCIDs (never emails; ``email`` is not requested).

Writes ``data/processed/escholarship_items.parquet``.

    PYTHONPATH=src py -3.14 scripts/fetch_escholarship_items.py
"""

from __future__ import annotations

import glob
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ENDPOINT = "https://escholarship.org/graphql"
USER_AGENT = "ca-plastics-atlas/0.1 (research dashboard)"
SOURCE_ID = "S4306400115"
CACHE = Path("data/raw/escholarship_items")
RAW = Path("data/interim/works_raw.parquet")
OUT = Path("data/processed/escholarship_items.parquet")
MIN_INTERVAL = 5.0  # 2 s triggered a 403 block after ~120 requests on 2026-11-12
MAX_REQUESTS = 600
_ITEM_URL = re.compile(r"escholarship\.org/(?:uc/item|content)/(?:qt)?([0-9a-z]{8})", re.I)

QUERY = """query($id: ID!) { item(id: $id) {
  id type source ucpmsPubType
  units { id name type parents { id type parents { id type parents { id type } } } }
  authors { nodes { name orcid } }
} }"""


def item_key(work: dict) -> str:
    for location in work.get("locations") or []:
        if str((location.get("source") or {}).get("id", "")).endswith(SOURCE_ID):
            for url in (location.get("landing_page_url"), location.get("pdf_url")):
                match = _ITEM_URL.search(str(url or ""))
                if match:
                    return f"ark:/13030/qt{match.group(1).lower()}"
    return ""


def candidate_works() -> dict[str, str]:
    """work_id -> eScholarship ark for raw-corpus works and the latest audit snapshots."""

    out: dict[str, str] = {}
    for row in pq.read_table(RAW, columns=["openalex_id", "raw_json"]).to_pylist():
        key = item_key(json.loads(row["raw_json"]))
        if key:
            out[str(row["openalex_id"]).rsplit("/", 1)[-1]] = key
    for path in glob.glob("data/raw/openalex_works/escholarship-openalex-audit-*.json"):
        body = json.loads(Path(path).read_text(encoding="utf-8")).get("response") or {}
        for work in body.get("results") or []:
            key = item_key(work)
            if key:
                out[str(work["id"]).rsplit("/", 1)[-1]] = key
    return out


_last = 0.0
_requests = 0
_blocked = False


def fetch(ark: str) -> dict | None:
    """Cached item response; None when uncached and the site has blocked us this run."""
    global _last, _requests, _blocked
    path = CACHE / f"{hashlib.sha256(ark.encode()).hexdigest()[:24]}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if _blocked:
        return None
    if _requests >= MAX_REQUESTS:
        raise RuntimeError("request cap reached")
    wait = MIN_INTERVAL - (time.monotonic() - _last)
    if wait > 0:
        time.sleep(wait)
    payload = json.dumps({"query": QUERY, "variables": {"id": ark}}).encode()
    request = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code in (403, 429):
            # Bot screen or throttle: stop requesting for this run; never retry around it.
            _blocked = True
            print(f"eScholarship answered HTTP {error.code}; stopping requests (cache kept)")
            return None
        raise
    _last = time.monotonic()
    _requests += 1
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body), encoding="utf-8")
    return body


def _walk_units(unit: dict) -> list[dict]:
    out, stack = [], [unit]
    while stack:
        current = stack.pop()
        out.append(current)
        stack.extend(current.get("parents") or [])
    return out


def classify(item: dict) -> tuple[str, list[str], list[str]]:
    units = item.get("units") or []
    all_units = [u for unit in units for u in _walk_units(unit)]
    campuses = sorted({u["id"] for u in all_units if u.get("type") == "CAMPUS"})
    unit_types = sorted({str(u.get("type")) for u in units})
    if str(item.get("type")).upper() == "ETD":
        evidence = "etd"
    elif units and all(u.get("type") == "JOURNAL" for u in units):
        evidence = "journal_only"
    elif item.get("source") == "oa_harvester" or item.get("ucpmsPubType"):
        evidence = "uc_oa_policy"
    elif campuses:
        evidence = "uc_unit"
    else:
        evidence = "journal_only"
    return evidence, campuses, unit_types


def main() -> None:
    works = candidate_works()
    print(f"works with an eScholarship copy: {len(works)}")
    rows = []
    fetched_at = datetime.now(UTC).isoformat()
    for work_id, ark in sorted(works.items()):
        body = fetch(ark)
        if body is None:
            rows.append({"work_id": work_id, "ark": ark, "ca_evidence": "pending"})
            continue
        item = (body.get("data") or {}).get("item")
        if not item:
            rows.append({"work_id": work_id, "ark": ark, "ca_evidence": "not_found"})
            continue
        evidence, campuses, unit_types = classify(item)
        authors = (item.get("authors") or {}).get("nodes") or []
        rows.append(
            {
                "work_id": work_id,
                "ark": ark,
                "item_type": item.get("type"),
                "source": item.get("source"),
                "ucpms_pub_type": item.get("ucpmsPubType"),
                "unit_ids": [u.get("id") for u in item.get("units") or []],
                "unit_types": unit_types,
                "campuses": campuses,
                "ca_evidence": evidence,
                "author_names": [str(a.get("name") or "") for a in authors],
                "author_orcids": [str(a.get("orcid") or "") for a in authors],
                "fetched_at": fetched_at,
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows), OUT)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["ca_evidence"]] = counts.get(row["ca_evidence"], 0) + 1
    print(f"requests: {_requests}; blocked: {_blocked}; evidence: {counts}; wrote {OUT}")


if __name__ == "__main__":
    main()
