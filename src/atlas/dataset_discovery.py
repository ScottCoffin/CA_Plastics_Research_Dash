"""Evidence-preserving discovery of paper-linked dataset metadata.

This module never downloads dataset payloads or article full text. It consumes
DataCite JSON and caller-supplied, already-permitted JATS snippets.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import unquote

from atlas.fulltext.jats import parse_jats

QUERY_VERSION = "s7.4-datacite-relations-v1"
_DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
DATASET_TYPES = {"dataset", "software", "model", "collection"}
PAPER_RELATIONS = {
    "issupplementto",
    "issupplementedby",
    "isreferencedby",
    "references",
    "iscitedby",
    "cites",
    "isderivedfrom",
    "issourceof",
}


def canonical_doi(value: str | None) -> str | None:
    """Return a normalized DOI, or None for non-DOI identifiers."""
    if not value:
        return None
    candidate = unquote(value.strip())
    if candidate.lower().startswith(("https://doi.org/", "http://doi.org/", "doi:")):
        candidate = re.sub(r"^(?:https?://doi\.org/|doi:)\s*", "", candidate, flags=re.I)
    candidate = candidate.rstrip(".,;:)]}").casefold()
    return candidate if _DOI.fullmatch(candidate) else None


def _attr(record: dict[str, Any]) -> dict[str, Any]:
    attrs = record.get("attributes", record)
    return attrs if isinstance(attrs, dict) else {}


def datacite_query_candidates(
    records: list[dict[str, Any]],
    *,
    query_evidence: dict[str, str],
    query_version: str = QUERY_VERSION,
    retrieved_at: str | None = None,
    record_provenance: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Retain unique records returned by DataCite discovery queries.

    These are dataset discovery candidates, not work-dataset links. Their
    ``source_work_id`` is explicitly null until a paper-level relation is
    independently established.
    """
    timestamp = retrieved_at or datetime.now(UTC).isoformat(timespec="seconds")
    output: dict[str, dict[str, Any]] = {}
    for record in records:
        attrs = _attr(record)
        doi = canonical_doi(str(record.get("id") or attrs.get("doi") or ""))
        if doi is None:
            continue
        titles = attrs.get("titles") or []
        output.setdefault(
            doi,
            {
                "candidate_id": doi,
                "dataset_doi": doi,
                "dataset_title": titles[0].get("title", "") if titles else "",
                "resource_type": ((attrs.get("types") or {}).get("resourceTypeGeneral") or ""),
                "dataset_url": attrs.get("url") or f"https://doi.org/{doi}",
                "source_work_id": None,
                "source_url": f"https://api.datacite.org/dois/{doi}",
                "evidence_type": "datacite-query",
                "query_evidence": dict(query_evidence),
                "query_version": query_version,
                "retrieved_at": timestamp,
                "candidate_status": "unreviewed",
                "uncertainty": (
                    "discovery query match does not establish California coverage, plastic "
                    "relevance, dataset type, or a paper link"
                ),
                **(record_provenance or {}).get(doi, {}),
            },
        )
    return [output[key] for key in sorted(output)]


def datacite_candidates(
    records: list[dict[str, Any]],
    works: dict[str, dict[str, str]],
    *,
    query_version: str = QUERY_VERSION,
    retrieved_at: str | None = None,
) -> list[dict[str, Any]]:
    """Build deduplicated DOI relation candidates with explicit evidence.

    ``works`` maps canonical article DOI to work_id/title. Dataset metadata
    lacking a matching work DOI is not promoted into a paper link.
    """
    timestamp = retrieved_at or datetime.now(UTC).isoformat(timespec="seconds")
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        attrs = _attr(record)
        dataset_doi = canonical_doi(str(record.get("id") or attrs.get("doi") or ""))
        if dataset_doi is None:
            continue
        title_list = attrs.get("titles") or []
        dataset_title = title_list[0].get("title", "") if title_list else ""
        url = attrs.get("url") or f"https://doi.org/{dataset_doi}"
        resource_type = ((attrs.get("types") or {}).get("resourceTypeGeneral") or "").casefold()
        for relation in attrs.get("relatedIdentifiers") or []:
            article_doi = canonical_doi(relation.get("relatedIdentifier"))
            relation_type = str(relation.get("relationType") or "")
            if article_doi is None or article_doi not in works:
                continue
            # Self-relations can occur when a repository DOI is itself in the
            # works table; do not represent the article as its own dataset.
            if dataset_doi == article_doi:
                continue
            work = works[article_doi]
            key = (work["work_id"], dataset_doi)
            supported = relation_type.casefold() in PAPER_RELATIONS
            candidate = {
                "work_id": work["work_id"],
                "work_doi": article_doi,
                "work_title": work.get("title", ""),
                "dataset_doi": dataset_doi,
                "dataset_title": dataset_title,
                "dataset_url": url,
                "resource_type": resource_type,
                "evidence_type": "datacite-relation",
                "relation_type": relation_type,
                "source_work_id": work["work_id"],
                "source_url": f"https://api.datacite.org/dois/{dataset_doi}",
                "query_version": query_version,
                "retrieved_at": timestamp,
                "uncertainty": (
                    "relation metadata indicates a link; topical and geographic "
                    "relevance require review"
                ),
                "candidate_status": "candidate"
                if supported and resource_type in DATASET_TYPES
                else "uncertain",
            }
            previous = output.get(key)
            if previous is None or candidate["candidate_status"] == "candidate":
                output[key] = candidate
    return [output[key] for key in sorted(output)]


def extract_data_availability(xml: str | bytes, *, max_chars: int = 1200) -> list[dict[str, str]]:
    """Extract bounded JATS data-availability evidence and DOI/URL mentions."""
    parsed = parse_jats(xml, max_chars=max_chars)
    grouped = parsed.get("sections")
    sections = grouped.get("data_availability") if isinstance(grouped, dict) else None
    if not isinstance(sections, list):
        return []
    output = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        text = str(section.get("evidence") or "")
        urls = sorted(
            set(
                re.sub(r"[.,;:)\]]+$", "", value)
                for value in re.findall(r"https?://[^\s<>\"']+", text)
            )
        )
        dois = sorted(
            {
                doi
                for match in re.findall(r"10\.\d{4,9}/[^\s<>\"']+", text)
                if (doi := canonical_doi(match))
            }
        )
        output.append(
            {
                "evidence_type": "data_availability",
                "section_id": str(section.get("section_id") or ""),
                "heading": str(section.get("title") or ""),
                "text": text,
                "doi_mentions": dois,
                "url_mentions": urls,
                "truncated": str(section.get("truncated") == "true").lower(),
            }
        )
    return output


def data_availability_candidates(
    xml: str | bytes,
    *,
    source_work_id: str,
    source_url: str,
    source_article_doi: str | None = None,
    query_version: str = QUERY_VERSION,
    retrieved_at: str | None = None,
    max_chars: int = 1200,
) -> list[dict[str, Any]]:
    """Create uncertain dataset candidates from supplied JATS evidence only."""
    timestamp = retrieved_at or datetime.now(UTC).isoformat(timespec="seconds")
    output: dict[str, dict[str, Any]] = {}
    excluded_dois = {
        doi
        for value in (source_article_doi, source_work_id)
        if value and (doi := canonical_doi(value))
    }
    for section in extract_data_availability(xml, max_chars=max_chars):
        identifiers: dict[str, dict[str, Any]] = {}
        for doi in section["doi_mentions"]:
            if doi in excluded_dois:
                continue
            identifiers.setdefault(doi, {"doi": doi, "urls": []})
        for url in section["url_mentions"]:
            doi = canonical_doi(url)
            if doi in excluded_dois:
                continue
            identity = doi or url.rstrip("/.").casefold()
            entry = identifiers.setdefault(identity, {"doi": doi, "urls": []})
            entry["urls"].append(url)

        for identity, mention in identifiers.items():
            candidate = output.setdefault(
                identity,
                {
                    "candidate_doi": mention["doi"],
                    "candidate_url": (
                        mention["urls"][0]
                        if mention["urls"]
                        else f"https://doi.org/{mention['doi']}"
                        if mention["doi"]
                        else identity
                    ),
                    "candidate_type": "data_availability_identifier",
                    "source_work_id": source_work_id,
                    "source_url": source_url,
                    "evidence_type": "data_availability",
                    "evidence_excerpt": section["text"],
                    "section_id": section["section_id"],
                    "doi_mentions": [],
                    "url_mentions": [],
                    "query_version": query_version,
                    "retrieved_at": timestamp,
                    "candidate_status": "uncertain",
                    "uncertainty": (
                        "data-availability mention requires dataset identity, coverage, "
                        "and rights review"
                    ),
                },
            )
            if mention["doi"] and mention["doi"] not in candidate["doi_mentions"]:
                candidate["doi_mentions"].append(mention["doi"])
            for url in mention["urls"]:
                if url not in candidate["url_mentions"]:
                    candidate["url_mentions"].append(url)
    return [output[key] for key in sorted(output)]
