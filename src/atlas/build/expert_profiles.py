"""Expert drawer profiles: ORCID bio, keywords and links, plus owner-approved photos.

Inputs are read with pyarrow (ORCID profiles) and csv (owner photo review). A
missing input file is skipped without error. Nothing containing an email address
or a ``mailto:`` link reaches the site: such keywords, links and bio sentences are
dropped. Photos are used only when the owner recorded ``approve``.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pyarrow.parquet as pq

BIO_MAX_CHARS = 600
KEYWORDS_MAX = 12
LINKS_MAX = 6

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _is_contact(text: str) -> bool:
    lowered = text.lower()
    return "@" in lowered or "mailto:" in lowered


def _http_url(value: object) -> str:
    url = _text(value)
    if not url:
        return ""
    try:
        parts = urlsplit(url)
    except ValueError:
        return ""
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        return ""
    return url


def _clean_bio(value: object) -> str:
    text = " ".join(_text(value).split())
    if not text:
        return ""
    kept = [s for s in _SENTENCE_SPLIT.split(text) if s and not _is_contact(s)]
    text = " ".join(kept)
    if len(text) <= BIO_MAX_CHARS:
        return text
    # Leave room for the ellipsis, then cut back to the last word boundary.
    head = text[: BIO_MAX_CHARS - 1]
    boundary = head.rfind(" ")
    if boundary > 0:
        head = head[:boundary]
    return head.rstrip() + "…"


def _keywords(values: object) -> list[str]:
    if not isinstance(values, list | tuple):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in values:
        for piece in _text(item).split(","):
            keyword = piece.strip()
            if not keyword or _is_contact(keyword):
                continue
            key = keyword.casefold()
            if key in seen:
                continue
            seen.add(key)
            out.append(keyword)
            if len(out) == KEYWORDS_MAX:
                return out
    return out


def _links(values: object) -> list[dict[str, str]]:
    if not isinstance(values, list | tuple):
        return []
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        url = _http_url(item.get("url"))
        if not url or _is_contact(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        name = _text(item.get("name"))
        if _is_contact(name):
            continue
        label = name or urlsplit(url).netloc
        out.append({"label": label, "url": url})
        if len(out) == LINKS_MAX:
            break
    return out


def _read_orcid(path: Path) -> dict[str, dict[str, Any]]:
    columns = ["author_id", "biography", "keywords", "researcher_urls"]
    table = pq.read_table(path, columns=columns)
    found: dict[str, dict[str, Any]] = {}
    for row in table.to_pylist():
        author_id = _text(row.get("author_id"))
        if not author_id:
            continue
        found[author_id] = {
            "bio": _clean_bio(row.get("biography")),
            "keywords": _keywords(row.get("keywords")),
            "links": _links(row.get("researcher_urls")),
        }
    return found


def _read_photos(path: Path) -> dict[str, dict[str, str]]:
    photos: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            author_id = _text(row.get("author_id"))
            if not author_id or _text(row.get("owner_decision")).lower() != "approve":
                continue
            thumb = _http_url(row.get("thumb_url"))
            if not thumb:
                continue
            source = _http_url(row.get("commons_page_url"))
            photos[author_id] = {
                "thumb_url": thumb,
                "license": _text(row.get("license_short")),
                "credit": _text(row.get("credit")),
                "source_url": source,
            }
    return photos


def load_expert_profiles(
    orcid_path: str | Path | None,
    photo_review_path: str | Path | None,
) -> dict[str, dict]:
    """Return drawer profiles keyed by author_id; authors with nothing to show are omitted.

    Each value has ``bio`` (str), ``keywords`` (list[str]) and ``links`` (list of
    ``{"label", "url"}``), plus ``photo`` (``thumb_url``, ``license``, ``credit``,
    ``source_url``) only for owner-approved photos. A falsy or missing path skips that input.
    """
    orcid_file = Path(orcid_path) if orcid_path else None
    photo_file = Path(photo_review_path) if photo_review_path else None
    profiles: dict[str, dict[str, Any]] = {}
    if orcid_file is not None and orcid_file.exists():
        for author_id, item in _read_orcid(orcid_file).items():
            if item["bio"] or item["keywords"] or item["links"]:
                profiles[author_id] = item
    if photo_file is not None and photo_file.exists():
        for author_id, photo in _read_photos(photo_file).items():
            profiles.setdefault(author_id, {"bio": "", "keywords": [], "links": []})
            profiles[author_id]["photo"] = photo
    return profiles
