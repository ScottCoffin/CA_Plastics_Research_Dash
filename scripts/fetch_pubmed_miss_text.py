"""Fetch the title and abstract of each PubMed miss in the triage sheet (BQ-S9 part D).

The review app shows these so the owner can judge each case. Run it once. Rerun it only after the
sheet gains PMIDs: the cache keeps every PMID it already holds.

    py -3.14 scripts/fetch_pubmed_miss_text.py             # fetch PMIDs not yet cached
    py -3.14 scripts/fetch_pubmed_miss_text.py --refresh   # refetch every PMID in the sheet

One or two NCBI EFetch calls (db=pubmed, retmode=xml, at most 200 ids per call) return the
ArticleTitle and AbstractText of each PMID. The result goes to data/interim/pubmed/miss_text.json,
which is gitignored: abstracts are never committed. Optional environment: NCBI_EMAIL (sent as the
contact ``email``) and NCBI_API_KEY (10 requests per second instead of 3). Neither value is printed
or written to the cache.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SHEET_PATH = ROOT / "curation" / "pubmed_miss_triage_v1.csv"
CACHE_PATH = ROOT / "data" / "interim" / "pubmed" / "miss_text.json"
EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
TOOL_NAME = "ca-plastics-research-atlas"
BATCH_SIZE = 200
MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 60.0
SCHEMA_VERSION = 1
SOURCE = "NCBI E-utilities efetch, db=pubmed, retmode=xml"

Opener = Callable[[str], bytes]


class FetchError(RuntimeError):
    """The sheet or NCBI is unusable; nothing is written."""


def read_sheet_pmids(path: Path) -> list[str]:
    """PMIDs of the triage sheet in sheet order; digits only, no duplicates."""
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if "pmid" not in (reader.fieldnames or []):
            raise FetchError(f"{path.name} has no pmid column")
        pmids = [(row.get("pmid") or "").strip() for row in reader]
    if any(not pmid.isdigit() for pmid in pmids):
        raise FetchError(f"{path.name} has an empty or non-numeric pmid")
    if len(set(pmids)) != len(pmids):
        raise FetchError(f"{path.name} lists a pmid more than once")
    return pmids


def batches(pmids: Sequence[str], size: int = BATCH_SIZE) -> list[list[str]]:
    return [list(pmids[start : start + size]) for start in range(0, len(pmids), size)]


def efetch_url(pmids: Sequence[str], environ: Mapping[str, str]) -> str:
    """One EFetch request; the contact email and API key are added only when set."""
    query = {
        "db": "pubmed",
        "retmode": "xml",
        "id": ",".join(pmids),
        "tool": TOOL_NAME,
    }
    if environ.get("NCBI_EMAIL"):
        query["email"] = environ["NCBI_EMAIL"]
    if environ.get("NCBI_API_KEY"):
        query["api_key"] = environ["NCBI_API_KEY"]
    return f"{EFETCH_URL}?{urllib.parse.urlencode(query)}"


def _text(element: ET.Element | None) -> str:
    """All text under an element, with inline markup kept and whitespace collapsed."""
    if element is None:
        return ""
    return " ".join("".join(element.itertext()).split())


def _abstract(element: ET.Element | None) -> str:
    """Each AbstractText paragraph, prefixed by its label when NCBI gives one."""
    if element is None:
        return ""
    parts: list[str] = []
    for paragraph in element.findall("AbstractText"):
        text = _text(paragraph)
        label = (paragraph.get("Label") or "").strip()
        if text:
            parts.append(f"{label}: {text}" if label else text)
    return "\n".join(parts)


def parse_efetch(raw: bytes) -> dict[str, dict[str, str]]:
    """Title and abstract per PMID from one EFetch XML response."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise FetchError("EFetch response was not XML") from None
    if root.tag != "PubmedArticleSet":
        detail = (root.findtext("ERROR") or root.tag).strip()
        raise FetchError(f"EFetch returned no article set ({detail})")
    records: dict[str, dict[str, str]] = {}
    for article in root.iter("PubmedArticle"):
        pmid = (article.findtext("MedlineCitation/PMID") or "").strip()
        if not pmid:
            continue
        records[pmid] = {
            "title": _text(article.find("MedlineCitation/Article/ArticleTitle")),
            "abstract": _abstract(article.find("MedlineCitation/Article/Abstract")),
        }
    return records


def _urlopen(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=TIMEOUT_SECONDS) as response:
        return response.read()


def _get(url: str, opener: Opener, sleep: Callable[[float], None]) -> bytes:
    """Fetch with up to MAX_ATTEMPTS tries on HTTP 429, 5xx and network errors.

    Error messages never include the URL, so the email and API key cannot leak through them.
    """
    reason = "no attempt"
    for attempt in range(MAX_ATTEMPTS):
        try:
            return opener(url)
        except urllib.error.HTTPError as error:
            if error.code != 429 and error.code < 500:
                raise FetchError(f"NCBI returned HTTP {error.code}") from None
            reason = f"HTTP {error.code}"
        except OSError as error:
            reason = type(error).__name__
        if attempt + 1 < MAX_ATTEMPTS:
            sleep(2.0 * 2**attempt)
    raise FetchError(f"NCBI request failed after {MAX_ATTEMPTS} attempts ({reason})")


def fetch_records(
    pmids: Sequence[str],
    *,
    environ: Mapping[str, str],
    opener: Opener | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, dict[str, str]]:
    """Title and abstract for each requested PMID that NCBI returns, with polite spacing."""
    fetch = _urlopen if opener is None else opener
    gap = 0.11 if environ.get("NCBI_API_KEY") else 0.34  # 10 or 3 requests per second
    records: dict[str, dict[str, str]] = {}
    for index, batch in enumerate(batches(pmids)):
        if index:
            sleep(gap)
        parsed = parse_efetch(_get(efetch_url(batch, environ), fetch, sleep))
        records.update({pmid: parsed[pmid] for pmid in batch if pmid in parsed})
    return records


def read_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_cache(
    path: Path,
    records: Mapping[str, Mapping[str, str]],
    *,
    pmids: Sequence[str],
    fetched_at: str,
) -> None:
    """Write the cache for the sheet's PMIDs only, atomically."""
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "fetched_at": fetched_at,
        "records": {pmid: dict(records[pmid]) for pmid in pmids if pmid in records},
        "not_returned": [pmid for pmid in pmids if pmid not in records],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(
        json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    os.replace(temp, path)


def plan(pmids: Sequence[str], cached: Mapping[str, Any] | None, refresh: bool) -> list[str]:
    """PMIDs to fetch: all with --refresh; otherwise those neither cached nor reported missing."""
    if refresh or cached is None:
        return list(pmids)
    known = set(cached.get("records", {})) | set(cached.get("not_returned", []))
    return [pmid for pmid in pmids if pmid not in known]


def summary(pmids: Sequence[str], records: Mapping[str, Mapping[str, str]]) -> str:
    kept = [records[pmid] for pmid in pmids if pmid in records]
    titles = sum(1 for record in kept if record.get("title"))
    abstracts = sum(1 for record in kept if record.get("abstract"))
    return (
        f"PMIDs in sheet {len(pmids)}; with title {titles}; with abstract {abstracts}; "
        f"not returned by NCBI {len(pmids) - len(kept)}"
    )


def _display(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="refetch every PMID in the sheet")
    parser.add_argument("--sheet", type=Path, default=SHEET_PATH, help="triage sheet to read")
    parser.add_argument("--out", type=Path, default=CACHE_PATH, help="cache file to write")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    opener: Opener | None = None,
    environ: Mapping[str, str] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    args = _parser().parse_args(argv)
    env: Mapping[str, str] = os.environ if environ is None else environ
    try:
        pmids = read_sheet_pmids(args.sheet)
        cached = read_cache(args.out)
        todo = plan(pmids, cached, args.refresh)
        if todo:
            fetched = fetch_records(todo, environ=env, opener=opener, sleep=sleep)
            prior = {} if args.refresh or cached is None else cached.get("records", {})
            records = {**prior, **fetched}
            fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
            write_cache(args.out, records, pmids=pmids, fetched_at=fetched_at)
            print(f"fetched {len(todo)} PMID(s) from NCBI")
            print(f"wrote {_display(args.out)} (gitignored; not committed)")
        else:
            records = cached.get("records", {}) if cached else {}
            print(f"nothing to fetch: every PMID is already cached in {_display(args.out)}")
    except (FetchError, OSError, ValueError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(summary(pmids, records))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
