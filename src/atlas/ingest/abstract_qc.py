"""Detect abstracts that OpenAlex attached to the wrong works.

Found 2026-11-11: OpenAlex serves one teaser-style micro-nano plastics abstract (two
snippets joined by "...", apparently scraped from "related articles" text on PNAS
landing pages) as the abstract of ten unrelated PNAS papers from 1962-2023 that have
no abstract of their own. Europe PMC has no abstract for them either.

Legitimate sharing also exists and must not be flagged: versions of one preprint
(PeerJ ``...2697v1`` / ``...2697/v2``), a book and its chapters (``..._0109``), or a
report series with near-identical titles (Kelp Wrack by county). So an abstract is
treated as mis-attached only when it is shared by ``min_works`` or more works that
have ``min_works`` or more distinct DOI roots *and* ``min_works`` or more distinct
title families. Normalization blanks such abstracts so no page, rule or model sees
them; the review apps do the same when reading raw records.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

MIN_WORKS = 3
MIN_CHARS = 200
TITLE_FAMILY_WORDS = 4

_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", re.IGNORECASE)
# Version, chapter and supplementary-file suffixes (PeerJ ".../2697v1/supp-1").
_DOI_VERSION = re.compile(r"(?:[/._-]?v\d+|_\d+|/\d+|/supp[-_]?\d*)$", re.IGNORECASE)
_WORD = re.compile(r"[a-z0-9]+")


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def abstract_key(value: object) -> str:
    return " ".join(_text(value).casefold().split())


def doi_root(doi: object, work_id: str) -> str:
    """DOI without version/chapter suffixes; works without a DOI count as distinct."""

    value = _DOI_PREFIX.sub("", _text(doi).casefold())
    if not value:
        return f"id:{work_id}"
    previous = None
    while previous != value:
        previous, value = value, _DOI_VERSION.sub("", value)
    return value


def title_family(title: object, work_id: str) -> str:
    words = _WORD.findall(_text(title).casefold())
    return " ".join(words[:TITLE_FAMILY_WORDS]) if words else f"id:{work_id}"


def misattached_abstract_ids(
    works: Iterable[Mapping[str, Any]],
    *,
    min_works: int = MIN_WORKS,
    id_key: str = "work_id",
) -> frozenset[str]:
    """IDs of works whose abstract is shared with unrelated works (see module doc)."""

    groups: dict[str, list[tuple[str, str, str]]] = {}
    for work in works:
        work_id = _text(work.get(id_key))
        key = abstract_key(work.get("abstract"))
        if work_id and len(key) >= MIN_CHARS:
            groups.setdefault(key, []).append(
                (
                    work_id,
                    doi_root(work.get("doi"), work_id),
                    title_family(work.get("title"), work_id),
                )
            )
    flagged: set[str] = set()
    for members in groups.values():
        if len(members) < min_works:
            continue
        roots = {root for _, root, _ in members}
        families = {family for _, _, family in members}
        if len(roots) >= min_works and len(families) >= min_works:
            flagged.update(work_id for work_id, _, _ in members)
    return frozenset(flagged)
