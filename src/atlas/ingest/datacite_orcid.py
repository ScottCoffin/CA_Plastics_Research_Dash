"""DataCite outputs (posters, datasets, presentations) by expert ORCID (S2.5d).

OpenAlex misses many non-article outputs. DataCite indexes them with creator
ORCIDs, so this module asks ``api.datacite.org`` for DOIs whose creators carry
an expert's ORCID. Only identifiers, bibliographic fields and classification
flags are stored. Descriptions are read in memory to derive ``plastic_related``
and are then discarded; they are never written to Parquet or notes.

Raw JSON pages are cached per request URL under ``data/raw/datacite_orcid/``
(gitignored). A cached page is never re-requested, and ``offline`` reads the
cache only.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from atlas.ingest.orcid import normalize_doi, normalize_orcid
from atlas.nlp.labels import classify_plastic_text
from atlas.query import load_query_config

API_URL = "https://api.datacite.org/dois"
USER_AGENT = "CAPlasticsAtlas/0.1 (https://github.com/ScottCoffin/CA_Plastics_Research_Dash)"
ORCID_URL_PREFIX = "https://orcid.org/"
ORCID_BATCH_SIZE = 25
PAGE_SIZE = 1000
DEFAULT_MAX_REQUESTS = 400
MIN_REQUEST_INTERVAL = 0.25  # seconds; keeps the client under 5 requests per second
MAX_ATTEMPTS = 4
MAX_PAGES_PER_BATCH = 200
MAX_BACKOFF_SECONDS = 60.0
TRANSIENT_STATUSES = frozenset({0, 429, 500, 502, 503, 504})  # 0 = transport failure
ACTIVE_QUERY_VERSION = "plastic-v3.1"
QUERY_CONFIG_PATH = "config/queries.yml"
PROFILES_PATH = "data/processed/orcid_profiles.parquet"
WORKS_PATH = "data/processed/normalized/works.parquet"
OUTPUT_PATH = "data/processed/expert_datacite_outputs.parquet"
CACHE_DIR = "data/raw/datacite_orcid"
KARAPETROVA_PROBE_DOI = "10.5281/zenodo.7217432"

OUTPUT_SCHEMA = pa.schema(
    [
        ("author_id", pa.string()),
        ("orcid", pa.string()),
        ("doi", pa.string()),
        ("title", pa.string()),
        ("resource_type_general", pa.string()),
        ("resource_type", pa.string()),
        ("publisher", pa.string()),
        ("year", pa.int64()),
        ("plastic_related", pa.bool_()),
        ("in_corpus", pa.bool_()),
        ("version_of", pa.string()),
        ("is_version", pa.bool_()),
        ("family_doi", pa.string()),
    ]
)


class RequestBudgetExhausted(RuntimeError):
    """Raised before a live request would exceed ``max_requests``."""


class CacheMiss(RuntimeError):
    """Raised in offline mode when a required page is not cached."""


class DataCiteHTTPError(RuntimeError):
    """Raised for a non-retryable or retry-exhausted HTTP failure."""


@dataclass(frozen=True)
class DataCiteRecord:
    """One DataCite DOI, stripped to metadata safe to store (no descriptions)."""

    doi: str
    title: str
    resource_type_general: str
    resource_type: str
    publisher: str
    year: int | None
    version_of: str
    creator_orcids: tuple[str, ...]
    plastic_related: bool


@dataclass(frozen=True)
class RunSummary:
    experts_queried: int
    batches: int
    requests_used: int
    cache_hits: int
    items_returned: int
    unparsed_items: int
    rows: int
    unique_dois: int
    by_resource_type_general: dict[str, int]
    is_version_dois: int
    plastic_related_dois: int
    plastic_not_in_corpus_dois: int
    plastic_families: int
    plastic_not_in_corpus_families: int
    karapetrova_probe_found: bool

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- query building


def orcid_batches(orcids: Sequence[str], size: int = ORCID_BATCH_SIZE) -> list[list[str]]:
    """Split ORCIDs into consecutive batches of at most ``size``."""

    if not 1 <= size <= ORCID_BATCH_SIZE:
        raise ValueError(f"batch size must be between 1 and {ORCID_BATCH_SIZE}")
    return [list(orcids[start : start + size]) for start in range(0, len(orcids), size)]


def orcid_query(orcids: Sequence[str]) -> str:
    """OR together creator-ORCID clauses for up to 25 ORCIDs."""

    if not 1 <= len(orcids) <= ORCID_BATCH_SIZE:
        raise ValueError(f"an ORCID query takes 1 to {ORCID_BATCH_SIZE} ORCIDs")
    clauses = [f'creators.nameIdentifiers.nameIdentifier:"{ORCID_URL_PREFIX}{o}"' for o in orcids]
    return "(" + " OR ".join(clauses) + ")"


def request_url(query: str, page_size: int = PAGE_SIZE) -> str:
    params = urllib.parse.urlencode({"query": query, "page[size]": page_size})
    return f"{API_URL}?{params}"


# --------------------------------------------------------------------------- transport and cache


def http_transport(url: str, *, timeout: float = 60.0) -> tuple[int, bytes, str | None]:
    """Return ``(status, body, retry_after)``; transport errors raise OSError."""

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(), response.headers.get("Retry-After")
    except urllib.error.HTTPError as error:
        return error.code, error.read(), error.headers.get("Retry-After")


def cache_path(cache_dir: Path, url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return cache_dir / f"{digest}.json"


def _backoff_seconds(attempt: int, retry_after: str | None) -> float:
    if retry_after and retry_after.strip().isdigit():
        return min(float(retry_after), MAX_BACKOFF_SECONDS)
    return min(float(2**attempt), MAX_BACKOFF_SECONDS)


@dataclass
class PageSource:
    """Cached, paced, budget-capped access to DataCite JSON pages."""

    cache_dir: Path
    max_requests: int = DEFAULT_MAX_REQUESTS
    offline: bool = False
    transport: Callable[[str], tuple[int, bytes, str | None]] = http_transport
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    min_interval: float = MIN_REQUEST_INTERVAL
    requests_used: int = 0
    cache_hits: int = 0
    _last_request: float = field(default=float("-inf"))

    def get_json(self, url: str) -> dict[str, Any]:
        path = cache_path(self.cache_dir, url)
        if path.exists():
            self.cache_hits += 1
            return _json_object(path.read_bytes(), url)
        if self.offline:
            raise CacheMiss(f"page not cached (offline run): {url}")
        body = self._fetch(url)
        payload = _json_object(body, url)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_bytes(body)
        temporary.replace(path)
        return payload

    def _fetch(self, url: str) -> bytes:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            if self.requests_used >= self.max_requests:
                raise RequestBudgetExhausted(
                    f"request budget of {self.max_requests} exhausted before {url}"
                )
            self.requests_used += 1
            self._pace()
            retry_after: str | None = None
            try:
                status, body, retry_after = self.transport(url)
            except OSError:
                status, body = 0, b""
            if status == 200:
                return body
            if status not in TRANSIENT_STATUSES or attempt == MAX_ATTEMPTS:
                raise DataCiteHTTPError(f"HTTP {status} for {url}")
            self.sleep(_backoff_seconds(attempt, retry_after))
        raise AssertionError("unreachable: retry loop always returns or raises")

    def _pace(self) -> None:
        elapsed = self.clock() - self._last_request
        if elapsed < self.min_interval:
            self.sleep(self.min_interval - elapsed)
        self._last_request = self.clock()


def _json_object(body: bytes, url: str) -> dict[str, Any]:
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise DataCiteHTTPError(f"expected a JSON object from {url}")
    return payload


def fetch_batch_items(source: PageSource, orcids: Sequence[str]) -> list[Mapping[str, Any]]:
    """Return every DOI item for one ORCID batch, following ``links.next`` cursors."""

    url = request_url(orcid_query(orcids))
    items: list[Mapping[str, Any]] = []
    visited: set[str] = set()
    for _ in range(MAX_PAGES_PER_BATCH):
        visited.add(url)
        payload = source.get_json(url)
        data = payload.get("data") or []
        items.extend(item for item in data if isinstance(item, Mapping))
        next_url = _text((payload.get("links") or {}).get("next"))
        if not data or not next_url or next_url in visited:
            return items
        if not next_url.startswith(API_URL):
            raise DataCiteHTTPError(f"unexpected cursor link outside DataCite: {next_url}")
        url = next_url
    raise DataCiteHTTPError(f"pagination limit of {MAX_PAGES_PER_BATCH} pages reached")


# --------------------------------------------------------------------------- parsing


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _first_text(entries: object, key: str) -> str:
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        return ""
    for entry in entries:
        if isinstance(entry, Mapping):
            text = _text(entry.get(key))
            if text:
                return text
    return ""


def _year(value: object) -> int | None:
    text = _text(value)
    return int(text) if text.isdigit() else None


def parse_record(item: Mapping[str, Any], query_config: Mapping[str, Any]) -> DataCiteRecord | None:
    """Parse one DataCite DOI item; description is used for labelling only."""

    attributes = item.get("attributes")
    if not isinstance(attributes, Mapping):
        return None
    doi = normalize_doi(_text(attributes.get("doi")) or _text(item.get("id")))
    if not doi:
        return None
    title = _first_text(attributes.get("titles"), "title")
    description = _first_text(attributes.get("descriptions"), "description")
    types = attributes.get("types")
    types = types if isinstance(types, Mapping) else {}
    publisher = attributes.get("publisher")
    if isinstance(publisher, Mapping):
        publisher = publisher.get("name")
    version_of = ""
    for related in attributes.get("relatedIdentifiers") or []:
        if isinstance(related, Mapping) and _text(related.get("relationType")).lower() == (
            "isversionof"
        ):
            version_of = normalize_doi(_text(related.get("relatedIdentifier")))
            if version_of:
                break
    creator_orcids: list[str] = []
    for creator in attributes.get("creators") or []:
        if not isinstance(creator, Mapping):
            continue
        for identifier in creator.get("nameIdentifiers") or []:
            if isinstance(identifier, Mapping):
                orcid = normalize_orcid(_text(identifier.get("nameIdentifier")))
                if orcid and orcid not in creator_orcids:
                    creator_orcids.append(orcid)
    decision = classify_plastic_text(" ".join(v for v in (title, description) if v), query_config)
    return DataCiteRecord(
        doi=doi,
        title=title,
        resource_type_general=_text(types.get("resourceTypeGeneral")),
        resource_type=_text(types.get("resourceType")),
        publisher=_text(publisher),
        year=_year(attributes.get("publicationYear")),
        version_of=version_of,
        creator_orcids=tuple(creator_orcids),
        plastic_related=decision.related,
    )


# --------------------------------------------------------------------------- rows and summary


def build_rows(
    records: Iterable[DataCiteRecord],
    expert_map: Mapping[str, Sequence[str]],
    corpus_dois: Iterable[str] | set[str],
) -> list[dict[str, Any]]:
    """One row per (author_id, DOI) where a creator ORCID belongs to that expert."""

    corpus = set(corpus_dois)
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        for orcid in record.creator_orcids:
            for author_id in expert_map.get(orcid, ()):
                key = (author_id, record.doi)
                if key in rows:
                    continue
                rows[key] = {
                    "author_id": author_id,
                    "orcid": orcid,
                    "doi": record.doi,
                    "title": record.title or None,
                    "resource_type_general": record.resource_type_general or None,
                    "resource_type": record.resource_type or None,
                    "publisher": record.publisher or None,
                    "year": record.year,
                    "plastic_related": record.plastic_related,
                    "in_corpus": record.doi in corpus,
                    "version_of": record.version_of or None,
                    "is_version": bool(record.version_of),
                    "family_doi": record.version_of or record.doi,
                }
    return [rows[key] for key in sorted(rows)]


def summarize(
    rows: Sequence[Mapping[str, Any]],
    corpus_dois: Iterable[str] | set[str],
    *,
    experts_queried: int,
    batches: int,
    requests_used: int,
    cache_hits: int,
    items_returned: int,
    unparsed_items: int,
) -> RunSummary:
    """Count DOIs once, then collapse plastic DOIs into version families."""

    unique: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        unique.setdefault(row["doi"], row)
    by_type: dict[str, int] = {}
    for row in unique.values():
        label = row["resource_type_general"] or "(none)"
        by_type[label] = by_type.get(label, 0) + 1
    corpus = set(corpus_dois)
    families: dict[str, dict[str, bool]] = {}
    for row in unique.values():
        family = families.setdefault(row["family_doi"], {"plastic": False, "in_corpus": False})
        family["plastic"] = family["plastic"] or bool(row["plastic_related"])
        family["in_corpus"] = family["in_corpus"] or bool(row["in_corpus"])
    # A family counts as in the corpus if any member or its concept DOI is in works.
    family_in_corpus = {
        fam for fam, state in families.items() if state["in_corpus"] or fam in corpus
    }
    plastic_families = [fam for fam, state in families.items() if state["plastic"]]
    return RunSummary(
        experts_queried=experts_queried,
        batches=batches,
        requests_used=requests_used,
        cache_hits=cache_hits,
        items_returned=items_returned,
        unparsed_items=unparsed_items,
        rows=len(rows),
        unique_dois=len(unique),
        by_resource_type_general=dict(sorted(by_type.items())),
        is_version_dois=sum(1 for row in unique.values() if row["is_version"]),
        plastic_related_dois=sum(1 for row in unique.values() if row["plastic_related"]),
        plastic_not_in_corpus_dois=sum(
            1 for row in unique.values() if row["plastic_related"] and not row["in_corpus"]
        ),
        plastic_families=len(plastic_families),
        plastic_not_in_corpus_families=sum(
            1 for fam in plastic_families if fam not in family_in_corpus
        ),
        karapetrova_probe_found=KARAPETROVA_PROBE_DOI in unique,
    )


# --------------------------------------------------------------------------- file IO


def load_active_query_config(path: str | Path = QUERY_CONFIG_PATH) -> dict[str, Any]:
    config = load_query_config(path)
    if config.get("version") != ACTIVE_QUERY_VERSION:
        raise ValueError(f"expected active query version {ACTIVE_QUERY_VERSION}")
    return config


def read_expert_map(path: str | Path = PROFILES_PATH) -> dict[str, list[str]]:
    """Map each bare ORCID to every author_id that carries it."""

    expert_map: dict[str, list[str]] = {}
    for row in pq.read_table(path, columns=["author_id", "orcid"]).to_pylist():
        orcid = normalize_orcid(_text(row.get("orcid")))
        author_id = _text(row.get("author_id"))
        if orcid and author_id:
            authors = expert_map.setdefault(orcid, [])
            if author_id not in authors:
                authors.append(author_id)
    return expert_map


def read_corpus_dois(path: str | Path = WORKS_PATH) -> set[str]:
    values = pq.read_table(path, columns=["doi"]).column("doi").to_pylist()
    return {normalize_doi(_text(value)) for value in values} - {""}


def write_rows(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp")
    pq.write_table(
        pa.Table.from_pylist(list(rows), schema=OUTPUT_SCHEMA), temporary, compression="zstd"
    )
    temporary.replace(output)


def run_expert_outputs(
    *,
    profiles_path: str | Path = PROFILES_PATH,
    works_path: str | Path = WORKS_PATH,
    query_path: str | Path = QUERY_CONFIG_PATH,
    cache_dir: str | Path = CACHE_DIR,
    output_path: str | Path = OUTPUT_PATH,
    limit: int | None = None,
    max_requests: int = DEFAULT_MAX_REQUESTS,
    offline: bool = False,
    transport: Callable[[str], tuple[int, bytes, str | None]] = http_transport,
    sleep: Callable[[float], None] = time.sleep,
) -> RunSummary:
    """Fetch, label and write expert DataCite outputs.

    Nothing is written unless every batch completes, so a budget stop or cache
    miss never leaves a partial output file behind.
    """

    query_config = load_active_query_config(query_path)
    full_map = read_expert_map(profiles_path)
    orcids = sorted(full_map)
    if limit is not None:
        orcids = orcids[:limit]
    expert_map = {orcid: full_map[orcid] for orcid in orcids}
    corpus = read_corpus_dois(works_path)
    source = PageSource(
        cache_dir=Path(cache_dir),
        max_requests=max_requests,
        offline=offline,
        transport=transport,
        sleep=sleep,
    )
    batches = orcid_batches(orcids)
    records: list[DataCiteRecord] = []
    items_returned = unparsed = 0
    for batch in batches:
        for item in fetch_batch_items(source, batch):
            items_returned += 1
            record = parse_record(item, query_config)
            if record is None:
                unparsed += 1
            else:
                records.append(record)
    rows = build_rows(records, expert_map, corpus)
    write_rows(output_path, rows)
    return summarize(
        rows,
        corpus,
        experts_queried=len(orcids),
        batches=len(batches),
        requests_used=source.requests_used,
        cache_hits=source.cache_hits,
        items_returned=items_returned,
        unparsed_items=unparsed,
    )
