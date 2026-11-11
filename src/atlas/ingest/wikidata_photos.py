"""Wikidata and Wikimedia Commons photo metadata for Atlas experts.

Metadata only: no image file is downloaded. Wikidata P496 (ORCID iD) links can
be wrong, so every row carries a name match flag and the owner must review
before any photo is displayed.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, TypeVar

USER_AGENT = "CAPlasticsAtlas/0.1 (https://github.com/ScottCoffin/CA_Plastics_Research_Dash)"
SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
SPARQL_BATCH_SIZE = 200
COMMONS_BATCH_SIZE = 50
REQUEST_INTERVAL_S = 1.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
USABLE_LICENSES = frozenset({"CC0", "PD", "CC BY", "CC BY-SA"})

_ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
_ORCID_PREFIX_RE = re.compile(r"^(?:https?://)?(?:www\.)?orcid\.org/", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[^\W_]+")
_FILEPATH_MARKER = "Special:FilePath/"
_FOLD_TABLE = str.maketrans({"ø": "o", "ł": "l", "đ": "d", "ħ": "h", "ı": "i"})

T = TypeVar("T")

_last_request_at = 0.0


def normalize_orcid(value: str | None) -> str | None:
    """Return the bare ORCID (0000-0000-0000-000X) or None if malformed."""
    if not value:
        return None
    text = _ORCID_PREFIX_RE.sub("", str(value).strip()).upper()
    return text if _ORCID_RE.match(text) else None


def build_sparql_query(orcids: Sequence[str]) -> str:
    """Build the batched Wikidata lookup for bare ORCIDs."""
    for orcid in orcids:
        if not _ORCID_RE.match(orcid):
            raise ValueError(f"not a bare ORCID: {orcid!r}")
    values = " ".join(f'"{orcid}"' for orcid in orcids)
    return (
        "SELECT ?orcid ?item ?itemLabel ?image WHERE { "
        f"VALUES ?orcid {{{values}}} "
        "?item wdt:P496 ?orcid . "
        "OPTIONAL { ?item wdt:P18 ?image } "
        'SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }'
    )


def batched(items: Sequence[T], size: int) -> list[list[T]]:
    """Split a sequence into consecutive chunks of at most ``size`` items."""
    if size < 1:
        raise ValueError("batch size must be positive")
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def image_file_from_url(url: str | None) -> str | None:
    """Extract the Commons file name from a Wikidata P18 Special:FilePath URL."""
    if not url or _FILEPATH_MARKER not in url:
        return None
    name = urllib.parse.unquote(url.split(_FILEPATH_MARKER, 1)[1]).strip()
    return name or None


def _title_key(file_name: str) -> str:
    """Canonical key for a Commons file name (underscores, first-letter case)."""
    text = file_name.replace("_", " ").strip()
    if text.startswith("File:"):
        text = text[len("File:") :]
    return text[:1].upper() + text[1:]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def strip_html(value: str | None) -> str | None:
    """Return the visible text of an HTML fragment, or None when empty."""
    if not value:
        return None
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    text = re.sub(r"\s+", " ", "".join(parser.parts)).strip()
    return text or None


def classify_license(short_name: str | None, license_url: str | None = None) -> str:
    """Classify a Commons licence as CC0, PD, CC BY, CC BY-SA or other.

    The short name is authoritative. The licence URL is used only when the
    short name is missing. NC and ND variants, fair use and all-rights-reserved
    fall into ``other``.
    """
    url = (license_url or "").lower()
    text = re.sub(r"[\s_]+", " ", (short_name or "").strip().lower())
    if not text:
        if "/licenses/by-sa/" in url:
            return "CC BY-SA"
        if "/licenses/by/" in url:
            return "CC BY"
        if "publicdomain/zero" in url:
            return "CC0"
        if "publicdomain/mark" in url:
            return "PD"
        return "other"
    if text.startswith("cc0"):
        return "CC0"
    if text.startswith("public domain") or text == "pd" or text.startswith("pd-"):
        return "PD"
    match = re.match(r"^cc by(-sa)?(?= |$)", text)
    if match and not re.search(r"\b(nc|nd)\b", text):
        return "CC BY-SA" if match.group(1) else "CC BY"
    return "other"


def is_usable(license_class: str, name_match_ok: bool, thumb_url: str | None) -> bool:
    """A photo is usable only with an open licence, a name match and a thumb."""
    return license_class in USABLE_LICENSES and name_match_ok and bool(thumb_url)


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.translate(_FOLD_TABLE))
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()


def _family_and_tokens(name: str) -> tuple[str | None, set[str]]:
    folded = _fold(name)
    tokens = set(_TOKEN_RE.findall(folded))
    family_part = folded.split(",", 1)[0] if "," in folded else folded
    family_tokens = _TOKEN_RE.findall(family_part)
    return (family_tokens[-1] if family_tokens else None), tokens


def name_match(atlas_name: str | None, wikidata_label: str | None) -> bool:
    """True when the Atlas and Wikidata names share the family name.

    Accents and case are folded. The family name is the last token (or the
    part before a comma). A match requires either family name to appear among
    the other name's tokens, which tolerates compound surnames.
    """
    if not atlas_name or not wikidata_label:
        return False
    family_a, tokens_a = _family_and_tokens(atlas_name)
    family_b, tokens_b = _family_and_tokens(wikidata_label)
    if not family_a or not family_b:
        return False
    return family_a in tokens_b or family_b in tokens_a


def parse_sparql_response(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Group SPARQL bindings by ORCID, then by Wikidata item.

    Each item is ``{"qid", "label", "images"}`` where ``images`` is the sorted
    set of Commons file names reported for that item.
    """
    grouped: dict[str, dict[str, dict[str, Any]]] = {}
    for binding in payload.get("results", {}).get("bindings", []):
        orcid = normalize_orcid(binding.get("orcid", {}).get("value"))
        item_uri = binding.get("item", {}).get("value", "")
        if not orcid or not item_uri:
            continue
        qid = item_uri.rsplit("/", 1)[-1]
        entry = grouped.setdefault(orcid, {}).setdefault(
            qid,
            {
                "qid": qid,
                "label": binding.get("itemLabel", {}).get("value"),
                "images": set(),
            },
        )
        image_file = image_file_from_url(binding.get("image", {}).get("value"))
        if image_file:
            entry["images"].add(image_file)
    return {
        orcid: [{**item, "images": sorted(item["images"])} for _, item in sorted(items.items())]
        for orcid, items in grouped.items()
    }


def choose_item(items: Sequence[dict[str, Any]]) -> dict[str, Any] | None:
    """Prefer an item that has an image, then the lowest QID."""
    if not items:
        return None
    with_image = [item for item in items if item["images"]]
    return (with_image or list(items))[0]


_EMPTY_IMAGE: dict[str, Any] = {
    "thumb_url": None,
    "description_url": None,
    "license_short": None,
    "license_url": None,
    "artist": None,
    "credit": None,
    "attribution_required": None,
}


def parse_commons_response(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map canonical file key to licence and credit metadata.

    Files missing from Commons are omitted from the result.
    """
    result: dict[str, dict[str, Any]] = {}
    for page in payload.get("query", {}).get("pages", {}).values():
        if "missing" in page or "title" not in page:
            continue
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        info = infos[0]
        ext = info.get("extmetadata", {})

        def field(name: str) -> str | None:
            return strip_html(ext.get(name, {}).get("value"))

        attribution = (ext.get("AttributionRequired", {}).get("value") or "").lower()
        result[_title_key(page["title"])] = {
            "thumb_url": info.get("thumburl"),
            "description_url": info.get("descriptionurl"),
            "license_short": field("LicenseShortName"),
            "license_url": field("LicenseUrl"),
            "artist": field("Artist"),
            "credit": field("Credit"),
            "attribution_required": (
                None if attribution not in {"true", "false"} else attribution == "true"
            ),
        }
    return result


def _throttle() -> None:
    global _last_request_at
    wait = REQUEST_INTERVAL_S - (time.monotonic() - _last_request_at)
    if _last_request_at and wait > 0:
        time.sleep(wait)
    _last_request_at = time.monotonic()


def _http_json(url: str, data: bytes | None, accept: str) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT, "Accept": accept}
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        _throttle()
        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRY_STATUSES or attempt == MAX_ATTEMPTS:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == MAX_ATTEMPTS:
                raise
        time.sleep(5 * attempt)
    raise RuntimeError("unreachable")  # pragma: no cover


def sparql_request(query: str) -> dict[str, Any]:
    body = urllib.parse.urlencode({"query": query, "format": "json"}).encode("utf-8")
    return _http_json(SPARQL_ENDPOINT, body, "application/sparql-results+json")


def commons_request(file_names: Sequence[str]) -> dict[str, Any]:
    titles = "|".join(f"File:{name}" for name in file_names)
    params = {
        "action": "query",
        "titles": titles,
        "prop": "imageinfo",
        "iiprop": "extmetadata|url",
        "iiurlwidth": "240",
        "format": "json",
    }
    url = f"{COMMONS_API}?{urllib.parse.urlencode(params)}"
    return _http_json(url, None, "application/json")


@dataclass(frozen=True)
class CachedResponse:
    kind: str
    fetched_at: str
    payload: dict[str, Any]


def _cache_file(cache_dir: Path, kind: str, request_key: str) -> Path:
    digest = hashlib.sha256(request_key.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{kind}_{digest}.json"


def cached_request(
    kind: str,
    request_key: str,
    cache_dir: Path,
    send: Callable[[], dict[str, Any]],
    *,
    offline: bool,
) -> CachedResponse:
    """Return a cached response, fetching and caching it when online.

    The cache key is a hash of the exact request, so an offline rebuild with
    the same inputs replays the same responses.
    """
    path = _cache_file(cache_dir, kind, request_key)
    if path.exists():
        envelope = json.loads(path.read_text(encoding="utf-8"))
        return CachedResponse(kind, envelope["fetched_at"], envelope["payload"])
    if offline:
        raise FileNotFoundError(f"offline: no cached {kind} response at {path}")
    payload = send()
    fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
    cache_dir.mkdir(parents=True, exist_ok=True)
    envelope = {"kind": kind, "fetched_at": fetched_at, "payload": payload}
    path.write_text(json.dumps(envelope, ensure_ascii=False), encoding="utf-8")
    return CachedResponse(kind, fetched_at, payload)


def _unique_orcids(authors: Iterable[dict[str, Any]]) -> list[str]:
    seen: dict[str, None] = {}
    for author in authors:
        orcid = normalize_orcid(author.get("orcid"))
        if orcid:
            seen.setdefault(orcid, None)
    return list(seen)


def build_expert_rows(
    authors: Sequence[dict[str, Any]],
    cache_dir: Path,
    *,
    offline: bool = False,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Look up Wikidata and Commons metadata for authors with a valid ORCID.

    ``limit`` caps the number of distinct ORCIDs queried, in index order.
    Returns one row per author whose ORCID was queried.
    """
    orcids = _unique_orcids(authors)
    if limit is not None:
        orcids = orcids[:limit]
    queried = set(orcids)

    items_by_orcid: dict[str, list[dict[str, Any]]] = {}
    sparql_time: dict[str, str] = {}
    for batch in batched(orcids, SPARQL_BATCH_SIZE):
        query = build_sparql_query(batch)
        cached = cached_request(
            "sparql", query, cache_dir, lambda q=query: sparql_request(q), offline=offline
        )
        for orcid in batch:
            sparql_time[orcid] = cached.fetched_at
        for orcid, items in parse_sparql_response(cached.payload).items():
            if orcid in queried:
                items_by_orcid[orcid] = items

    chosen = {orcid: choose_item(items) for orcid, items in items_by_orcid.items()}
    # Only the first image per expert is stored, so only that file is looked up.
    files = sorted({item["images"][0] for item in chosen.values() if item and item["images"]})

    commons: dict[str, dict[str, Any]] = {}
    commons_time: dict[str, str] = {}
    for batch in batched(files, COMMONS_BATCH_SIZE):
        key = "|".join(batch)
        cached = cached_request(
            "commons",
            key,
            cache_dir,
            lambda names=batch: commons_request(names),
            offline=offline,
        )
        for file_key, meta in parse_commons_response(cached.payload).items():
            commons[file_key] = meta
            commons_time[file_key] = cached.fetched_at

    rows: list[dict[str, Any]] = []
    for author in authors:
        orcid = normalize_orcid(author.get("orcid"))
        if not orcid or orcid not in queried:
            continue
        item = chosen.get(orcid)
        image_file = item["images"][0] if item and item["images"] else None
        label = item["label"] if item else None
        match = name_match(author.get("name"), label) if item else False
        meta = dict(_EMPTY_IMAGE)
        fetched_at = sparql_time[orcid]
        if image_file:
            file_key = _title_key(image_file)
            meta = {**meta, **commons.get(file_key, {})}
            fetched_at = max(fetched_at, commons_time.get(file_key, ""))
        license_class = classify_license(meta["license_short"], meta["license_url"])
        rows.append(
            {
                "author_id": author.get("author_id"),
                "orcid": orcid,
                "wikidata_qid": item["qid"] if item else None,
                "wikidata_label": label,
                "name_match": match,
                "image_file": image_file,
                "license_short": meta["license_short"],
                "license_url": meta["license_url"],
                "artist": meta["artist"],
                "credit": meta["credit"],
                "attribution_required": meta["attribution_required"],
                "thumb_url": meta["thumb_url"],
                "description_url": meta["description_url"],
                "usable": is_usable(license_class, match, meta["thumb_url"]),
                "fetched_at": fetched_at,
            }
        )
    return rows


def expert_photo_schema() -> Any:
    """Arrow schema for ``data/processed/expert_photos.parquet``."""
    import pyarrow as pa

    return pa.schema(
        [
            ("author_id", pa.string()),
            ("orcid", pa.string()),
            ("wikidata_qid", pa.string()),
            ("wikidata_label", pa.string()),
            ("name_match", pa.bool_()),
            ("image_file", pa.string()),
            ("license_short", pa.string()),
            ("license_url", pa.string()),
            ("artist", pa.string()),
            ("credit", pa.string()),
            ("attribution_required", pa.bool_()),
            ("thumb_url", pa.string()),
            ("description_url", pa.string()),
            ("usable", pa.bool_()),
            ("fetched_at", pa.string()),
        ]
    )


def write_expert_photos(rows: Sequence[dict[str, Any]], path: Path) -> None:
    """Write the metadata rows to Parquet with a fixed schema."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    schema = expert_photo_schema()
    table = pa.Table.from_pylist(list(rows), schema=schema)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)


def summarize(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Counts for the API note: items, images, licence classes and usable rows."""
    with_item = [r for r in rows if r["wikidata_qid"]]
    with_image = [r for r in rows if r["image_file"]]
    classes: dict[str, int] = {}
    raw_licences: dict[str, int] = {}
    for row in with_image:
        cls = classify_license(row["license_short"], row["license_url"])
        classes[cls] = classes.get(cls, 0) + 1
        short = row["license_short"] or "(none)"
        raw_licences[short] = raw_licences.get(short, 0) + 1
    mismatches = [r for r in with_item if not r["name_match"]]
    return {
        "orcids_queried": len(rows),
        "items_found": len(with_item),
        "with_image": len(with_image),
        "usable": sum(1 for r in rows if r["usable"]),
        "licence_class": dict(sorted(classes.items())),
        "licence_raw": dict(sorted(raw_licences.items(), key=lambda kv: -kv[1])),
        "name_mismatch": len(mismatches),
        "name_mismatch_examples": [
            {
                "author_id": r["author_id"],
                "wikidata_qid": r["wikidata_qid"],
                "wikidata_label": r["wikidata_label"],
            }
            for r in mismatches[:10]
        ],
    }
