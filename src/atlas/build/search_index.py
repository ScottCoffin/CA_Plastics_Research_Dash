"""Header search index for the Atlas (VD-19): site/data/search_index.json.

The header search fetches this one file on first use and matches it in the browser. Each item is
``[type_index, label, detail, href]``; ``types`` names the type indexes in display order. Hrefs are
relative to the site root. Items carry only text the public pages already show: no abstracts and
no e-mail addresses.
"""

from __future__ import annotations

import html
import json
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from atlas.build.seo import load_topic_labels

SCHEMA_VERSION = 1
TYPES = ("page", "expert", "institution", "topic", "funder", "term", "resource")
OVERVIEW_PAGE = ("Overview", "Home", "california/")
EXCERPT_LIMIT = 140
FUNDER_TYPE_DETAIL = {
    "federal": "Federal agency",
    "state": "State agency",
    "other": "Other funder",
}

PAGE_GROUP = re.compile(r'\{name:\s*"([^"]+)",\s*pages:\s*\[(.*?)\]\s*\}', re.S)
PAGE_ENTRY = re.compile(r'name:\s*"([^"]+)",\s*path:\s*"/([^"]+)"')
GLOSSARY_ENTRY = re.compile(r'<dt id="([^"]+)"[^>]*>(.*?)</dt>\s*<dd>(.*?)</dd>', re.S)
PARAGRAPH = re.compile(r"<p>(.*?)</p>", re.S)
MATRIX_BLOCK = re.compile(r"const MATRICES = \{(.*?)\};", re.S)
INSTITUTION_BLOCK = re.compile(r"INSTITUTION_TYPE_LABELS = Object\.freeze\(\{(.*?)\}\);", re.S)
KEY_VALUE = re.compile(r'^\s*"?([A-Za-z0-9_/-]+)"?:\s*"([^"]+)"', re.M)
TAG = re.compile(r"<[^>]+>")


def _text(value: Any) -> str:
    """A display string: None and empty values become "", whitespace collapses."""
    if value is None:
        return ""
    return " ".join(str(value).split())


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _plain(fragment: str) -> str:
    return _text(html.unescape(TAG.sub(" ", fragment)))


def _excerpt(text: str) -> str:
    if len(text) <= EXCERPT_LIMIT:
        return text
    cut = text[:EXCERPT_LIMIT].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


# PLAT-1: hrefs are relative to the site root (site_search.js resolves them there), and the
# California pages live under california/.
REGION_PREFIX = "california/"


def _href(path: str, **params: str) -> str:
    """``california/path#key=value&...``, form-encoded the way URLSearchParams reads it."""
    return f"{REGION_PREFIX}{path}#{urlencode(params)}"


def parse_page_groups(config_text: str) -> list[tuple[str, str, str]]:
    """``(label, group, href)`` for each nav page in PAGE_GROUPS, in config order."""
    pages: list[tuple[str, str, str]] = []
    for group, body in PAGE_GROUP.findall(config_text):
        for label, path in PAGE_ENTRY.findall(body):
            pages.append((label, group, path))
    return pages


def parse_glossary(markdown: str) -> list[tuple[str, str, str]]:
    """``(id, term, excerpt)`` for each ``<dt id>`` entry of the glossary page."""
    terms: list[tuple[str, str, str]] = []
    for term_id, dt_html, dd_html in GLOSSARY_ENTRY.findall(markdown):
        term = _plain(dt_html)
        paragraph = PARAGRAPH.search(dd_html)
        excerpt = _excerpt(_plain(paragraph.group(1) if paragraph else dd_html))
        if term_id and term:
            terms.append((term_id, term, excerpt))
    return terms


def parse_matrix_labels(topics_js: str) -> dict[str, str]:
    """Matrix key -> label from the MATRICES table in ``assets/topics.js``.

    The tag for a matrix key is ``matrix:<key>``.
    """
    block = MATRIX_BLOCK.search(topics_js)
    return {key: label for key, label in KEY_VALUE.findall(block.group(1))} if block else {}


def parse_institution_types(labels_js: str) -> dict[str, str]:
    """Institution type slug -> display label from ``shared/labels.js``."""
    block = INSTITUTION_BLOCK.search(labels_js)
    return {key: label for key, label in KEY_VALUE.findall(block.group(1))} if block else {}


def _page_items(pages: Iterable[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    rows = [(OVERVIEW_PAGE[0], OVERVIEW_PAGE[1], OVERVIEW_PAGE[2])]
    rows += [(label, group, path) for label, group, path in pages]
    return rows


def _expert_items(authors: Iterable[dict]) -> list[tuple[str, str, str]]:
    rows = []
    for author in authors:
        name = _text(author.get("name"))
        author_id = _text(author.get("author_id"))
        if not name or not author_id:
            continue
        affiliations = author.get("primary_affiliations") or []
        if isinstance(affiliations, str):
            affiliations = [affiliations]
        detail = _text(affiliations[0]) if affiliations else ""
        href = f"{REGION_PREFIX}expert.html#{urlencode({'author': author_id})}"
        rows.append((name, detail, href))
    return rows


def _institution_items(
    institutions: Iterable[dict], type_labels: dict[str, str]
) -> list[tuple[str, str, str]]:
    rows = []
    for inst in institutions:
        # The Institutions page lists California institutions by default; the rest appear only
        # as collaborators on their pages, so the header search leaves them out.
        inst_id = _text(inst.get("inst_id"))
        name = _text(inst.get("name"))
        if not _truthy(inst.get("ca_flag")) or not inst_id or not name:
            continue
        type_label = type_labels.get(_text(inst.get("atlas_type")), "")
        detail = " · ".join(part for part in (type_label, _text(inst.get("city"))) if part)
        rows.append((name, detail, _href("institution", inst=inst_id)))
    return rows


def _topic_items(
    topic_labels: dict[str, str], matrix_labels: dict[str, str]
) -> list[tuple[str, str, str]]:
    rows = [
        (label, "Research topic", _href("experts", tag=tag)) for tag, label in topic_labels.items()
    ]
    rows += [
        (label, "Matrix", _href("experts", tag=f"matrix:{key}"))
        for key, label in matrix_labels.items()
    ]
    return rows


def _grant_records(grants: dict) -> list[dict]:
    """Rows of ``grants.json`` as dicts; the columnar form (``columns`` + list rows) also works."""
    rows = grants.get("rows") or []
    columns = grants.get("columns") or []
    return [dict(zip(columns, row)) if isinstance(row, list) else row for row in rows]


def _funder_items(grants: dict) -> list[tuple[str, str, str]]:
    records = _grant_records(grants)
    agency_types: dict[str, Counter] = {}
    for row in records:
        agency = _text(row.get("funder_agency"))
        if agency:
            agency_types.setdefault(agency, Counter())[_text(row.get("funder_type"))] += 1
    rows = []
    for agency, types in agency_types.items():
        kind = types.most_common(1)[0][0] if types else ""
        rows.append(
            (agency, FUNDER_TYPE_DETAIL.get(kind, "Funding agency"), _href("funding", fa=agency))
        )
    # Funder names that are not agency names (the Funding page's text search matches them).
    for name in sorted({_text(row.get("funder")) for row in records}):
        if name and ";" not in name and name not in agency_types:
            rows.append((name, "Funder", _href("funding", q=name)))
    return rows


def _resource_items(entries: Iterable[dict]) -> list[tuple[str, str, str]]:
    rows = []
    for entry in entries:
        name = _text(entry.get("name"))
        if not name:
            continue
        url = _text(entry.get("root_url"))
        href = url if url.startswith(("https://", "http://")) else f"{REGION_PREFIX}resources"
        rows.append((name, _text(entry.get("relation")), href))
    return rows


def build_search_index(
    *,
    generated_at: str,
    pages: Iterable[tuple[str, str, str]] = (),
    authors: Iterable[dict] = (),
    institutions: Iterable[dict] = (),
    institution_types: dict[str, str] | None = None,
    topic_labels: dict[str, str] | None = None,
    matrix_labels: dict[str, str] | None = None,
    grants: dict | None = None,
    glossary: Iterable[tuple[str, str, str]] = (),
    resources: Iterable[dict] = (),
) -> dict:
    """Build the search index. Output is deterministic for the same inputs."""
    by_type = {
        "page": _page_items(pages),
        "expert": _expert_items(authors),
        "institution": _institution_items(institutions, institution_types or {}),
        "topic": _topic_items(topic_labels or {}, matrix_labels or {}),
        "funder": _funder_items(grants or {}),
        "term": [
            (term, excerpt, f"{REGION_PREFIX}glossary#{quote(term_id, safe='')}")
            for term_id, term, excerpt in glossary
        ],
        "resource": _resource_items(resources),
    }
    items: list[list[Any]] = []
    for type_index, type_name in enumerate(TYPES):
        rows = list(dict.fromkeys(by_type[type_name]))
        if type_name != "page":
            # Pages keep their navigation order; every other type sorts by label.
            rows.sort(key=lambda row: (row[0].casefold(), row[1].casefold(), row[2]))
        items.extend([type_index, label, detail, href] for label, detail, href in rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "types": list(TYPES),
        "items": items,
    }


def serialize(index: dict) -> str:
    return json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n"


def load_sources(root: Path) -> dict[str, Any]:
    """Read the committed site files and framework sources the index is built from."""
    data = root / "site" / "data"
    site_index = json.loads((data / "index.json").read_text(encoding="utf-8"))
    institutions = json.loads((data / "institutions.json").read_text(encoding="utf-8"))
    if isinstance(institutions, dict):
        institutions = institutions.get("institutions", [])
    grants = json.loads((data / "grants.json").read_text(encoding="utf-8"))
    linkouts = json.loads((data / "linkouts.json").read_text(encoding="utf-8"))
    framework = root / "framework"
    topics_js = (root / "site" / "assets" / "topics.js").read_text(encoding="utf-8")
    labels_js = (framework / "src" / "components" / "shared" / "labels.js").read_text(
        encoding="utf-8"
    )
    return {
        "generated_at": site_index["generated_at"],
        "pages": parse_page_groups(
            (framework / "observablehq.config.js").read_text(encoding="utf-8")
        ),
        "authors": site_index.get("authors", []),
        "institutions": institutions,
        "institution_types": parse_institution_types(labels_js),
        "topic_labels": load_topic_labels(root / "site" / "assets" / "topics.js"),
        "matrix_labels": parse_matrix_labels(topics_js),
        "grants": grants,
        "glossary": parse_glossary(
            (framework / "src" / "california" / "glossary.md").read_text(encoding="utf-8")
        ),
        "resources": linkouts.get("entries", []),
    }
