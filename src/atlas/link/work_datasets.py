"""Evidence-typed work-to-dataset links (S9.2).

Two matchers feed the links table; anything weaker is kept out of the links:

1. ``DataCite-relation``: a DataCite record of a dataset-type resource whose
   ``relatedIdentifiers`` names a work DOI with a paper relation type. Typing is
   delegated to ``atlas.dataset_discovery.datacite_candidates``. Records come from
   ``api.datacite.org`` through ``fetch_relation_records`` (cached, budgeted).
2. ``DAS-match``: a DOI named in a cached JATS data-availability section of the
   work, where that DOI is a dataset-type DataCite record retrieved by step 1.

Candidates that fail the typing rules (for example a non-dataset resource or a
non-paper relation) are returned as review rows and never linked.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas.dataset_discovery import (
    DATASET_TYPES,
    canonical_doi,
    datacite_candidates,
    extract_data_availability,
)

USER_AGENT = "ca-plastics-atlas/0.1 (research dashboard)"
DATACITE_URL = "https://api.datacite.org/dois"
DATACITE_HOST = "api.datacite.org"
DATACITE_BATCH = 8
DATACITE_PAGE = 100
MIN_REQUEST_INTERVAL = 1.1
CACHE_SCHEMA = "s9.2-datacite-relations-v1"

EVIDENCE_DATACITE = "DataCite-relation"
EVIDENCE_DAS = "DAS-match"
EVIDENCE_TYPES = (EVIDENCE_DATACITE, EVIDENCE_DAS)
EVIDENCE_PRECEDENCE = {EVIDENCE_DATACITE: 0, EVIDENCE_DAS: 1}
EVIDENCE_LABELS = {
    EVIDENCE_DATACITE: "DataCite relation",
    EVIDENCE_DAS: "Data availability statement",
}
_PMCID = re.compile(r"PMC\d+", re.IGNORECASE)


@dataclass(frozen=True)
class WorkDatasetLink:
    work_id: str
    dataset_doi: str
    relation_type: str
    evidence_type: str
    evidence_value: str
    confidence: str


@dataclass(frozen=True)
class ReviewRow:
    work_id: str
    dataset_doi: str
    evidence_type: str
    evidence_value: str
    reason: str


@dataclass(frozen=True)
class FetchReport:
    records: list[dict[str, Any]]
    requests: int
    cached_batches: int
    failed_batches: int
    incomplete_batches: int


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def work_index(raw_rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map canonical work DOI to ``work_id``, title and PMCID from OpenAlex raw JSON."""
    index: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        data = json.loads(str(row.get("raw_json") or "{}"))
        doi = canonical_doi(str(data.get("doi") or ""))
        openalex_id = str(data.get("id") or "").rsplit("/", 1)[-1]
        if doi is None or not openalex_id:
            continue
        pmcid_match = _PMCID.search(str((data.get("ids") or {}).get("pmcid") or ""))
        index.setdefault(
            doi,
            {
                "work_id": openalex_id,
                "title": str(data.get("title") or ""),
                "pmcid": pmcid_match.group(0).upper() if pmcid_match else "",
            },
        )
    return index


def _queryable(doi: str) -> bool:
    return '"' not in doi and "\\" not in doi and not any(ch.isspace() for ch in doi)


def _chunks(items: Sequence[str], size: int) -> list[list[str]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def relation_query(dois: Sequence[str]) -> str:
    phrases = " OR ".join(f'"{doi}"' for doi in dois)
    return f"relatedIdentifiers.relatedIdentifier:({phrases})"


def relation_request_url(dois: Sequence[str], page: int) -> str:
    params = {
        "query": relation_query(dois),
        "page[size]": str(DATACITE_PAGE),
        "page[number]": str(page),
    }
    return f"{DATACITE_URL}?{urllib.parse.urlencode(params)}"


def datacite_transport(url: str, *, timeout: float = 60.0) -> tuple[int, str]:
    """GET one DataCite metadata search. Only ``api.datacite.org`` is contacted."""
    if urllib.parse.urlsplit(url).netloc != DATACITE_HOST:
        raise ValueError("only api.datacite.org may be contacted for S9.2")
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")


def _slim_record(record: Mapping[str, Any]) -> dict[str, Any]:
    attrs = record.get("attributes") or {}
    return {
        "id": str(record.get("id") or "").casefold(),
        "attributes": {
            "url": attrs.get("url"),
            "titles": attrs.get("titles") or [],
            "types": {"resourceTypeGeneral": (attrs.get("types") or {}).get("resourceTypeGeneral")},
            "relatedIdentifiers": attrs.get("relatedIdentifiers") or [],
        },
    }


def _batch_key(batch: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(batch).encode("utf-8")).hexdigest()


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": CACHE_SCHEMA, "batches": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if data.get("schema") == CACHE_SCHEMA else {"schema": CACHE_SCHEMA, "batches": {}}


def _save_cache(path: Path, cache: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def fetch_relation_records(
    dois: Sequence[str],
    *,
    cache_path: Path,
    transport: Callable[[str], tuple[int, str]] = datacite_transport,
    max_requests: int = 60,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], str] = _utc_now,
) -> FetchReport:
    """Fetch DataCite records whose relatedIdentifiers name any of ``dois``.

    Each batch of up to ``DATACITE_BATCH`` DOIs is one OR query. Complete batches
    are cached with the sanitized request URLs, retrieval time and a SHA-256 of the
    canonical records, so reruns make no requests. Failed or budget-cut batches are
    not cached and are counted in the report.
    """
    cache = _load_cache(cache_path)
    queryable = sorted({d for d in dois if _queryable(d)})
    records: dict[str, dict[str, Any]] = {}
    used = cached = failed = incomplete = 0
    for batch in _chunks(queryable, DATACITE_BATCH):
        key = _batch_key(batch)
        entry = cache["batches"].get(key)
        if entry is not None:
            cached += 1
            for record in entry["records"]:
                records.setdefault(record["id"], record)
            continue
        if used >= max_requests:
            incomplete += 1
            continue
        collected: list[dict[str, Any]] = []
        urls: list[str] = []
        page, total_pages, ok = 1, 1, True
        while page <= total_pages:
            if used >= max_requests:
                ok = False
                incomplete += 1
                break
            if used:
                sleep(MIN_REQUEST_INTERVAL)
            url = relation_request_url(batch, page)
            status, text = transport(url)
            used += 1
            if status != 200:
                failed += 1
                ok = False
                break
            payload = json.loads(text)
            urls.append(url)
            collected.extend(_slim_record(r) for r in payload.get("data") or [])
            total_pages = int((payload.get("meta") or {}).get("totalPages") or 1)
            page += 1
        if not ok:
            continue
        canonical = json.dumps(collected, sort_keys=True, ensure_ascii=False)
        cache["batches"][key] = {
            "dois": list(batch),
            "request_urls": urls,
            "retrieved_at": now(),
            "records_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "records": collected,
        }
        _save_cache(cache_path, cache)
        for record in collected:
            records.setdefault(record["id"], record)
    return FetchReport(
        records=[records[k] for k in sorted(records)],
        requests=used,
        cached_batches=cached,
        failed_batches=failed,
        incomplete_batches=incomplete,
    )


def relation_matches(
    records: Sequence[Mapping[str, Any]],
    works: Mapping[str, Mapping[str, Any]],
) -> tuple[list[WorkDatasetLink], list[ReviewRow]]:
    """Type DataCite relations with the S7.4 rules; uncertain candidates go to review."""
    doi_to_work = {doi: {"work_id": w["work_id"], "title": w["title"]} for doi, w in works.items()}
    linked: list[WorkDatasetLink] = []
    review: list[ReviewRow] = []
    for candidate in datacite_candidates(list(records), doi_to_work):
        pair = (candidate["work_id"], candidate["dataset_doi"])
        if candidate["candidate_status"] == "candidate":
            linked.append(
                WorkDatasetLink(
                    work_id=pair[0],
                    dataset_doi=pair[1],
                    relation_type=str(candidate["relation_type"]),
                    evidence_type=EVIDENCE_DATACITE,
                    evidence_value=str(candidate["relation_type"]),
                    confidence="high",
                )
            )
        else:
            review.append(
                ReviewRow(
                    work_id=pair[0],
                    dataset_doi=pair[1],
                    evidence_type=EVIDENCE_DATACITE,
                    evidence_value=str(candidate["relation_type"]),
                    reason=(
                        f"relation {candidate['relation_type']!r} on resource "
                        f"{candidate['resource_type'] or 'unknown'!r} is not a typed dataset link"
                    ),
                )
            )
    return linked, review


def dataset_dois(records: Sequence[Mapping[str, Any]]) -> set[str]:
    """Canonical DOIs of dataset-type DataCite records."""
    out: set[str] = set()
    for record in records:
        attrs = record.get("attributes") or {}
        resource = str(((attrs.get("types") or {}).get("resourceTypeGeneral")) or "")
        doi = canonical_doi(str(record.get("id") or ""))
        if doi and resource.casefold() in DATASET_TYPES:
            out.add(doi)
    return out


def das_matches(
    work_id: str,
    work_doi: str | None,
    xml_documents: Sequence[str | bytes],
    known_datasets: set[str],
) -> tuple[list[WorkDatasetLink], list[ReviewRow]]:
    """Link DOIs named in a work's data-availability section to known dataset records."""
    links: dict[str, WorkDatasetLink] = {}
    review: list[ReviewRow] = []
    for xml in xml_documents:
        for section in extract_data_availability(xml):
            for doi in section["doi_mentions"]:
                if doi == work_doi:
                    continue
                if doi in known_datasets:
                    links.setdefault(
                        doi,
                        WorkDatasetLink(
                            work_id=work_id,
                            dataset_doi=doi,
                            relation_type="data-availability",
                            evidence_type=EVIDENCE_DAS,
                            evidence_value=doi,
                            confidence="high",
                        ),
                    )
                else:
                    review.append(
                        ReviewRow(
                            work_id=work_id,
                            dataset_doi=doi,
                            evidence_type=EVIDENCE_DAS,
                            evidence_value=doi,
                            reason="DOI in data availability is not a retrieved dataset record",
                        )
                    )
    return list(links.values()), review


def load_cached_jats(cache_dir: Path, pmcids: Iterable[str]) -> dict[str, list[str | bytes]]:
    """Read cached JATS XML (``<PMCID>.xml``) for the given PMCIDs, keyed by PMCID.

    The S7.4 full-text cache writes only license-cleared XML, so no further rights
    gate is applied here. Returns an empty mapping when the cache has no XML.
    """
    wanted = {p.upper() for p in pmcids if p}
    out: dict[str, list[str | bytes]] = {}
    if not cache_dir.is_dir():
        return out
    for path in sorted(cache_dir.glob("*.xml")):
        stem = path.stem.upper()
        if stem in wanted:
            out.setdefault(stem, []).append(path.read_bytes())
    return out


def combine_links(links: Iterable[WorkDatasetLink]) -> list[WorkDatasetLink]:
    """Keep one link per (work, dataset), using the strongest evidence type."""
    best: dict[tuple[str, str], WorkDatasetLink] = {}
    for link in links:
        key = (link.work_id, link.dataset_doi)
        current = best.get(key)
        if current is None or (
            EVIDENCE_PRECEDENCE[link.evidence_type] < EVIDENCE_PRECEDENCE[current.evidence_type]
        ):
            best[key] = link
    return sorted(best.values(), key=lambda link: (link.work_id, link.dataset_doi))


def write_review_csv(path: Path, rows: Sequence[ReviewRow]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["work_id", "dataset_doi", "evidence_type", "evidence_value", "reason"])
        for row in rows:
            writer.writerow(
                [row.work_id, row.dataset_doi, row.evidence_type, row.evidence_value, row.reason]
            )


def evidence_label(evidence_type: str) -> str:
    return EVIDENCE_LABELS.get(evidence_type, "Unrecognized evidence")
