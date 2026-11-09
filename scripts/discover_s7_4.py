"""Bounded DataCite metadata candidate discovery; never downloads data files."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from atlas.dataset_discovery import QUERY_VERSION, canonical_doi, datacite_query_candidates

DEFAULT_QUERIES = (
    "titles.title:microplastic AND titles.title:California",
    "descriptions.description:microplastics AND descriptions.description:California",
    "titles.title:plastic AND descriptions.description:California",
)


def sanitize_request_url(request_url: str) -> str:
    """Remove credential-like parameters before provenance is written."""
    parts = urlsplit(request_url)
    safe = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.casefold() not in {"key", "api_key", "token", "access_token", "authorization"}
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(safe), ""))


def fetch_query(query: str, *, timeout: int = 30) -> tuple[list[dict[str, object]], str, str]:
    params = urlencode({"query": query, "page[size]": 100})
    request_url = f"https://api.datacite.org/dois?{params}"
    request = Request(
        request_url,
        headers={"User-Agent": "CA-Plastics-Atlas-S7.4-discovery/1.0"},
    )
    with urlopen(request, timeout=timeout) as response:
        response_body = response.read()
    payload = json.loads(response_body)
    sanitized = json.dumps(payload.get("data", []), sort_keys=True, separators=(",", ":"))
    return (
        payload.get("data", []),
        sanitize_request_url(request_url),
        hashlib.sha256(sanitized.encode("utf-8")).hexdigest(),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", action="append", help="DataCite query; repeat up to 10 times")
    parser.add_argument(
        "--input-json", type=Path, help="Offline DataCite JSON:API response fixture"
    )
    parser.add_argument("--output", type=Path, default=Path("data/interim/s7_4_candidates.json"))
    parser.add_argument("--max-queries", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.max_queries <= 10:
        parser.error("--max-queries must be between 1 and 10")

    queries = args.query or list(DEFAULT_QUERIES)
    if len(queries) > args.max_queries:
        parser.error("query count exceeds --max-queries")
    metadata_records: list[dict[str, object]] = []
    evidence: dict[str, str] = {}
    record_provenance: dict[str, dict[str, object]] = {}
    if args.input_json:
        payload = json.loads(args.input_json.read_text(encoding="utf-8"))
        metadata_records = payload.get("data", payload)
        evidence = {"offline_fixture": str(args.input_json)}
    else:
        for index, query in enumerate(queries):
            rows, request_url, response_hash = fetch_query(query)
            request_time = datetime.now(UTC).isoformat(timespec="seconds")
            metadata_records.extend(rows)
            evidence[f"query_{index + 1}"] = query
            for record in rows:
                attrs = record.get("attributes", {})
                doi = canonical_doi(str(record.get("id") or attrs.get("doi") or ""))
                if doi is None:
                    continue
                provenance = record_provenance.setdefault(
                    doi,
                    {
                        "query_membership": [],
                        "metadata_request_urls": [],
                        "sanitized_response_sha256": [],
                        "metadata_retrieved_at": [],
                    },
                )
                for field, value in (
                    ("query_membership", f"query_{index + 1}"),
                    ("metadata_request_urls", request_url),
                    ("sanitized_response_sha256", response_hash),
                    ("metadata_retrieved_at", request_time),
                ):
                    if value not in provenance[field]:
                        provenance[field].append(value)
            if index + 1 < len(queries):
                time.sleep(1.0)

    retrieved_at = datetime.now(UTC).isoformat(timespec="seconds")
    output = {
        "schema_version": 1,
        "query_version": QUERY_VERSION,
        "retrieved_at": retrieved_at,
        "metadata_request_count": 0 if args.input_json else len(queries),
        "query_evidence": evidence,
        "candidates": datacite_query_candidates(
            metadata_records,
            query_evidence=evidence,
            retrieved_at=retrieved_at,
            record_provenance=record_provenance,
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(output['candidates'])} unique DOI candidates to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
