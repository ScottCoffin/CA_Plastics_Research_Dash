"""Atom 1.0 digest feed of new CA-plastic papers and new awards (S11.4).

Reads the public payloads ``site/data/index.json`` (works and authors) and
``site/data/grants.json`` (awards) and renders ``site/feed.xml``. Stdlib only. The feed
carries titles, identifiers, links, dates, and short summaries. It never copies
abstracts, contact fields, or any corpus data.

Selection rules
- Papers: ``plastic_related`` is true, ``needs_review`` is not true, and the work has a
  California link (``ca_any_author`` or ``ca_led``). The slim payload holds only a
  ``year``, not a full publication date, so papers are ordered by year, newest first,
  then by ``work_id``. At most 30.
- Awards: ``start`` is a valid ISO date and ``plastic_related`` is true or null (the S8.10
  default for unlabelled rows). Ordered by ``start``, newest first, then ``grant_key``.
  Undated awards are left out. At most 30.

Dates: a paper's ``updated`` is ``<year>-01-01T00:00:00Z``; an award's is its ``start``
at midnight UTC. The feed ``updated`` is the newest entry date, never the build time, so
unchanged inputs give byte-identical output.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ATOM_NS = "http://www.w3.org/2005/Atom"
SITE_URL = "https://scottcoff.in/CA_Plastics_Research_Dash/"
FEED_ID = SITE_URL
FEED_URL = SITE_URL + "feed.xml"
FEED_TITLE = "CA Plastics Research Atlas: new papers and awards"
FEED_AUTHOR = "CA Plastics Research Atlas"
TAG_ROOT = "tag:scottcoff.in,2026:ca-plastics-atlas"
MAX_PAPERS = 30
MAX_AWARDS = 30
EPOCH = "1970-01-01T00:00:00Z"
PAPER_LINK_BASE = "https://openalex.org/"

DEFAULT_INDEX = Path("site/data/index.json")
DEFAULT_GRANTS = Path("site/data/grants.json")
DEFAULT_OUTPUT = Path("site/feed.xml")

_WORK_ID = re.compile(r"^W[0-9]+$")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _is_real_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_ca_plastic_paper(work: Mapping[str, Any]) -> bool:
    if work.get("plastic_related") is not True or work.get("needs_review") is True:
        return False
    return work.get("ca_any_author") is True or work.get("ca_led") is True


def _paper_year(work: Mapping[str, Any]) -> int | None:
    year = work.get("year")
    if isinstance(year, int) and not isinstance(year, bool) and 1000 <= year <= 9999:
        return year
    return None


def _award_date(row: Mapping[str, Any]) -> str | None:
    text = _text(row.get("start"))
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _paper_summary(work: Mapping[str, Any], authors: Mapping[str, str], year: int) -> str:
    author_ids = [aid for aid in work.get("author_ids") or [] if isinstance(aid, str)]
    names = [authors[aid] for aid in author_ids if authors.get(aid)]
    if names:
        shown = ", ".join(names[:3])
        if len(author_ids) > 3:
            shown += f" and {len(author_ids) - 3} more"
        author_text = f"Authors: {shown}"
    else:
        author_text = f"Authors on record: {len(author_ids)}"
    institutions = len(work.get("institution_ids") or [])
    parts = [author_text, f"Year {year}"]
    if _text(work.get("type")):
        parts.append(f"Type: {_text(work.get('type'))}")
    parts.append(f"Institutions on record: {institutions}")
    return " · ".join(parts)


def _award_summary(row: Mapping[str, Any]) -> str:
    funder_chain = [_text(item) for item in row.get("funder_chain") or [] if _text(item)]
    funder = " > ".join(funder_chain) or _text(row.get("funder")) or "Funder not recorded"
    parts = [f"Funder: {funder}"]
    org = _text(row.get("org"))
    if org:
        parts.append(f"Recipient: {org}")
    amount = row.get("amount")
    if _is_real_number(amount):
        currency = _text(row.get("currency")) or "USD"
        parts.append(f"Amount: {currency} {amount:,.0f}")
    else:
        parts.append("Amount: not reported")
    basis = _text(row.get("amount_basis"))
    if basis:
        parts.append(f"Amount basis: {basis}")
    return " · ".join(parts)


def select_papers(index_payload: Mapping[str, Any], limit: int = MAX_PAPERS) -> list[dict]:
    """Return up to ``limit`` paper entries, newest first."""
    authors = {
        str(a.get("author_id")): _text(a.get("name"))
        for a in index_payload.get("authors") or []
        if isinstance(a, Mapping) and a.get("author_id")
    }
    entries: list[dict] = []
    for work in index_payload.get("works") or []:
        if not isinstance(work, Mapping) or not _is_ca_plastic_paper(work):
            continue
        year = _paper_year(work)
        work_id = _text(work.get("work_id"))
        if year is None or not work_id:
            continue
        link = PAPER_LINK_BASE + work_id if _WORK_ID.match(work_id) else FEED_ID
        entries.append(
            {
                "category": "paper",
                "id": f"{TAG_ROOT}/work/{work_id}",
                "title": _text(work.get("title")) or "Untitled work",
                "link": link,
                "updated": f"{year:04d}-01-01T00:00:00Z",
                "summary": _paper_summary(work, authors, year),
            }
        )
    entries.sort(key=lambda e: (e["updated"], e["id"]), reverse=True)
    return entries[:limit]


def select_awards(grants_payload: Mapping[str, Any], limit: int = MAX_AWARDS) -> list[dict]:
    """Return up to ``limit`` award entries, newest start date first.

    Awards starting after the payload's own ``generated_at`` date (for example
    future-dated NSF starts) are skipped, so the feed never claims a future
    ``updated`` time. Using the payload date keeps the output deterministic.
    """
    as_of = _text(grants_payload.get("generated_at"))[:10] or None
    entries: list[dict] = []
    for row in grants_payload.get("rows") or []:
        if not isinstance(row, Mapping) or row.get("plastic_related") not in (True, None):
            continue
        start = _award_date(row)
        grant_key = _text(row.get("grant_key"))
        if start is None or not grant_key or (as_of and start > as_of):
            continue
        url = _text(row.get("url"))
        entries.append(
            {
                "category": "award",
                "id": f"{TAG_ROOT}/award/{grant_key}",
                "title": _text(row.get("title")) or "Untitled award",
                "link": url if url.startswith("https://") else FEED_ID,
                "updated": f"{start}T00:00:00Z",
                "summary": _award_summary(row),
            }
        )
    entries.sort(key=lambda e: (e["updated"], e["id"]), reverse=True)
    return entries[:limit]


def _sub(parent: ET.Element, tag: str, text: str | None = None, **attrib: str) -> ET.Element:
    element = ET.SubElement(parent, f"{{{ATOM_NS}}}{tag}", attrib)
    if text is not None:
        element.text = text
    return element


def build_feed_element(entries: Sequence[Mapping[str, Any]]) -> ET.Element:
    """Return the Atom ``feed`` element for the given entries."""
    updated = max((e["updated"] for e in entries), default=EPOCH)
    feed = ET.Element(f"{{{ATOM_NS}}}feed")
    _sub(feed, "id", FEED_ID)
    _sub(feed, "title", FEED_TITLE)
    _sub(
        feed,
        "subtitle",
        "Newly indexed California-connected plastic research papers and newly recorded "
        "awards. Summaries only; open the source for details.",
    )
    _sub(feed, "link", rel="self", type="application/atom+xml", href=FEED_URL)
    _sub(feed, "link", rel="alternate", type="text/html", href=FEED_ID)
    _sub(feed, "updated", updated)
    author = _sub(feed, "author")
    _sub(author, "name", FEED_AUTHOR)
    for entry in entries:
        node = _sub(feed, "entry")
        _sub(node, "id", entry["id"])
        _sub(node, "title", entry["title"])
        _sub(node, "link", rel="alternate", type="text/html", href=entry["link"])
        _sub(node, "updated", entry["updated"])
        _sub(node, "summary", entry["summary"], type="text")
        _sub(node, "category", term=entry["category"])
    return feed


def render_feed(index_payload: Mapping[str, Any], grants_payload: Mapping[str, Any]) -> bytes:
    """Return the UTF-8 Atom document. Identical inputs give identical bytes."""
    entries = select_papers(index_payload) + select_awards(grants_payload)
    entries.sort(key=lambda e: (e["updated"], e["id"]), reverse=True)
    ET.register_namespace("", ATOM_NS)
    root = build_feed_element(entries)
    ET.indent(root, space="  ")
    body = ET.tostring(root, encoding="unicode")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n").encode("utf-8")


def entry_counts(index_payload: Mapping[str, Any], grants_payload: Mapping[str, Any]) -> dict:
    papers = len(select_papers(index_payload))
    awards = len(select_awards(grants_payload))
    return {"papers": papers, "awards": awards, "entries": papers + awards}


def write_feed(
    index_path: Path = DEFAULT_INDEX,
    grants_path: Path = DEFAULT_GRANTS,
    output: Path = DEFAULT_OUTPUT,
) -> dict:
    """Read the public payloads, write the feed, and return entry counts."""
    index_payload = json.loads(Path(index_path).read_text(encoding="utf-8"))
    grants_payload = json.loads(Path(grants_path).read_text(encoding="utf-8"))
    data = render_feed(index_payload, grants_payload)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return {**entry_counts(index_payload, grants_payload), "bytes": len(data)}
