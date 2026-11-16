"""Repair OpenAlex authorships whose author ID is null (S2.6).

OpenAlex sometimes returns ``authorship.author.id = null``, occasionally with the
author's ORCID still on the same authorship. Normalization used to keep those rows with
an empty ``author_id``, so they never became experts. :func:`repair_author_ids` fills an
ID only when one of these sources supports it, and reports which source did:

(a) ``curated``: a row of ``curation/author_attach.csv`` names the authorship's work and
    full normalized name. Applied first; it wins over (b) and (c).
(b) ``orcid``: the authorship's ORCID maps to one author ID. The map is the raw index
    (ORCIDs that map to exactly one ID across the authorships that carry both), overlaid
    by ``curation/orcid_author_ids.csv``, which wins.
(c) ``name_institution``: exactly one known author ID has the same full normalized name
    at one of the authorship's institutions. Known pairs come from the authorships that
    already have an ID, including those filled by (a) and (b). This is a single pass.
(d) Otherwise the ID stays ``""``. Nothing here creates an ID.

:func:`normalize_name` is moved unchanged from ``scripts/build_author_merges.py``. Its
owner rule (2026-11-11) is that one name at one institution is one person.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_ATTACH_PATH = Path("curation/author_attach.csv")
DEFAULT_ORCID_IDS_PATH = Path("curation/orcid_author_ids.csv")
ATTACH_HEADER = ("work_id", "author_name", "to_author_id", "reason", "reviewed_by", "reviewed_at")
ORCID_IDS_HEADER = ("orcid", "author_id", "display_name", "fetched_at")

SOURCE_OPENALEX = "openalex"
SOURCE_CURATED = "curated"
SOURCE_ORCID = "orcid"
SOURCE_NAME_INSTITUTION = "name_institution"
UNRESOLVED = "unresolved"
REPAIR_SOURCES = (SOURCE_CURATED, SOURCE_ORCID, SOURCE_NAME_INSTITUTION)

RepairKey = tuple[str, int]


def normalize_name(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name or "")
    folded = "".join(c for c in folded if not unicodedata.combining(c)).lower()
    folded = re.sub(r"[^a-z\s]", " ", folded.replace("‐", "-").replace("-", " "))
    return " ".join(folded.split())


def compact_openalex_id(value: object) -> str:
    """``https://openalex.org/A123`` -> ``A123`` (same rule as ``normalize.compact_id``)."""

    text = str(value or "").rstrip("/")
    return text.rsplit("/", 1)[-1] if text else ""


def normalize_orcid(value: object) -> str:
    """Bare upper-case ORCID, ``0000-0003-4337-622X``, without its URL prefix."""

    return compact_openalex_id(str(value or "").strip()).upper()


@dataclass(frozen=True)
class _Authorship:
    key: RepairKey
    author_id: str
    name: str
    orcid: str
    institutions: tuple[str, ...]


def _sequence(value: object) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return list(value)


def _authorships(work_rows: Mapping[str, Mapping[str, Any]]) -> list[_Authorship]:
    """Every mapping authorship, keyed like normalization enumerates them."""

    found: list[_Authorship] = []
    for work_id, work in work_rows.items():
        for index, authorship in enumerate(_sequence(work.get("authorships"))):
            if not isinstance(authorship, Mapping):
                continue
            author = authorship.get("author")
            author = author if isinstance(author, Mapping) else {}
            institutions = [
                compact_openalex_id(inst.get("id"))
                for inst in _sequence(authorship.get("institutions"))
                if isinstance(inst, Mapping)
            ]
            found.append(
                _Authorship(
                    key=(work_id, index),
                    author_id=compact_openalex_id(author.get("id")),
                    name=normalize_name(str(author.get("display_name") or "")),
                    orcid=normalize_orcid(author.get("orcid")),
                    institutions=tuple(dict.fromkeys(i for i in institutions if i)),
                )
            )
    return found


def _orcid_index(slots: Sequence[_Authorship]) -> dict[str, str]:
    ids: dict[str, set[str]] = defaultdict(set)
    for slot in slots:
        if slot.author_id and slot.orcid:
            ids[slot.orcid].add(slot.author_id)
    return {orcid: next(iter(found)) for orcid, found in ids.items() if len(found) == 1}


def build_orcid_index(work_rows: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    """``{ORCID: author ID}`` for ORCIDs that map to exactly one ID in ``work_rows``."""

    return _orcid_index(_authorships(work_rows))


def null_author_orcids(work_rows: Mapping[str, Mapping[str, Any]]) -> set[str]:
    """ORCIDs carried by authorships whose author ID is null."""

    return {slot.orcid for slot in _authorships(work_rows) if not slot.author_id and slot.orcid}


def _csv_rows(path: str | Path | None) -> list[dict[str, str]]:
    if path is None or not Path(path).exists():
        return []
    with Path(path).open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def load_attach_rows(path: str | Path | None = DEFAULT_ATTACH_PATH) -> list[dict[str, str]]:
    """Rows of ``author_attach.csv``; a missing file means no curated attaches."""

    return _csv_rows(path)


def load_orcid_author_ids(path: str | Path | None = DEFAULT_ORCID_IDS_PATH) -> dict[str, str]:
    """``{ORCID: author ID}`` from ``orcid_author_ids.csv``; blank author IDs are ignored."""

    result: dict[str, str] = {}
    for row in _csv_rows(path):
        orcid = normalize_orcid(row.get("orcid"))
        author_id = compact_openalex_id(str(row.get("author_id") or "").strip())
        if orcid and author_id:
            result[orcid] = author_id
    return result


def repair_author_ids(
    work_rows: Mapping[str, Mapping[str, Any]],
    orcid_ids: Mapping[str, str],
    attach_rows: Sequence[Mapping[str, Any]],
) -> tuple[dict[RepairKey, tuple[str, str]], dict[str, int]]:
    """Fill null author IDs by the precedence in the module docstring.

    Returns ``({(work_id, authorship index): (author_id, source)}, counts)``. The index is
    the position in the work's ``authorships`` list, as normalization enumerates it. Only
    null-ID authorships appear as keys. ``counts`` has one entry per repair source plus
    ``unresolved``, the null-ID authorships that stay ``""``.
    """

    slots = _authorships(work_rows)
    nulls = [slot for slot in slots if not slot.author_id]
    resolved: dict[RepairKey, tuple[str, str]] = {}

    # (a) Curated attach. The first row for a (work, normalized name) pair wins.
    curated: dict[tuple[str, str], str] = {}
    for row in attach_rows:
        work_id = compact_openalex_id(str(row.get("work_id") or "").strip())
        name = normalize_name(str(row.get("author_name") or ""))
        target = compact_openalex_id(str(row.get("to_author_id") or "").strip())
        if work_id and name and target:
            curated.setdefault((work_id, name), target)
    for slot in nulls:
        target = curated.get((slot.key[0], slot.name))
        if target:
            resolved[slot.key] = (target, SOURCE_CURATED)

    # (b) ORCID: the raw index, overlaid by the reviewed CSV (the CSV wins).
    lookup = _orcid_index(slots)
    for orcid, author_id in orcid_ids.items():
        key = normalize_orcid(orcid)
        value = compact_openalex_id(str(author_id or "").strip())
        if key and value:
            lookup[key] = value
    for slot in nulls:
        if slot.key not in resolved and slot.orcid and slot.orcid in lookup:
            resolved[slot.key] = (lookup[slot.orcid], SOURCE_ORCID)

    # (c) Name + institution, from IDs known after (a) and (b). Single pass.
    known: dict[tuple[str, str], set[str]] = defaultdict(set)
    for slot in slots:
        author_id = slot.author_id or resolved.get(slot.key, ("", ""))[0]
        if author_id and slot.name:
            for institution in slot.institutions:
                known[(slot.name, institution)].add(author_id)
    for slot in nulls:
        if slot.key in resolved or not slot.name:
            continue
        candidates: set[str] = set()
        for institution in slot.institutions:
            candidates |= known.get((slot.name, institution), set())
        if len(candidates) == 1:
            resolved[slot.key] = (next(iter(candidates)), SOURCE_NAME_INSTITUTION)

    # Never give a work the same author twice: drop a repair whose ID already sits on the
    # work (an original ID, or an earlier repair in authorship order).
    on_work: dict[str, set[str]] = defaultdict(set)
    for slot in slots:
        if slot.author_id:
            on_work[slot.key[0]].add(slot.author_id)
    for key in sorted(resolved):
        author_id = resolved[key][0]
        if author_id in on_work[key[0]]:
            del resolved[key]
        else:
            on_work[key[0]].add(author_id)

    counts = {source: 0 for source in REPAIR_SOURCES}
    for _, source in resolved.values():
        counts[source] += 1
    counts[UNRESOLVED] = len(nulls) - len(resolved)
    return resolved, counts
