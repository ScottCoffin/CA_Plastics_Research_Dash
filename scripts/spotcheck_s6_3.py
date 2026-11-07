"""Run a bounded 30-PDF Frontiers CC BY spot check through local GROBID."""

from __future__ import annotations

import hashlib
import io
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

from pdfminer.high_level import extract_text

from atlas.fulltext.cache import _license_blocks
from atlas.fulltext.grobid import (
    DEFAULT_CACHE_DIR,
    PARSER_VERSION,
    PDFExtractionError,
    _public_https_url,
    extract_pdf_cached,
)

API = "https://www.ebi.ac.uk/europepmc/webservices/rest"
SEARCH_QUERY = (
    "OPEN_ACCESS:Y AND (microplastic OR nanoplastic OR plastic pollution) AND DOI:10.3389*"
)
PDF_DIR = Path("data/raw/fulltext_cache/pdf_spotcheck")
REPORT = Path("docs/api_notes/s6_3_pdf_spotcheck.json")
TARGET_COUNT = 30
PAGE_SIZE = 30
MAX_PAGES = 2
GROBID_URL = "http://127.0.0.1:8070"
_last_get_at = 0.0


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _get(url: str, *, timeout: float = 30.0, max_bytes: int = 40 * 1024 * 1024) -> bytes:
    global _last_get_at
    _public_https_url(url)
    elapsed = time.monotonic() - _last_get_at
    if _last_get_at and elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _last_get_at = time.monotonic()
    request = urllib.request.Request(
        url, headers={"User-Agent": "CA-Plastics-Research-Dash/0.1 (bounded CC BY spot check)"}
    )
    opener = urllib.request.build_opener(_RejectRedirects())
    with opener.open(request, timeout=timeout) as response:
        if response.status != 200 or response.geturl() != url:
            raise RuntimeError("response did not match the exact selected HTTPS URL")
        content_type = response.headers.get("Content-Type", "").casefold()
        payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise RuntimeError("response exceeded configured size limit")
    if url.endswith("/pdf") and (
        "application/pdf" not in content_type or not payload.startswith(b"%PDF-")
    ):
        raise RuntimeError("publisher endpoint did not return a direct PDF")
    return payload


def _json(url: str) -> dict[str, object]:
    return json.loads(_get(url, max_bytes=8 * 1024 * 1024))


def _check_grobid() -> None:
    parsed = urllib.parse.urlsplit(GROBID_URL)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port != 8070:
        raise RuntimeError("spot check accepts only the configured local GROBID endpoint")
    request = urllib.request.Request(GROBID_URL + "/api/isalive")
    opener = urllib.request.build_opener(_RejectRedirects())
    with opener.open(request, timeout=5) as response:
        if response.status != 200 or response.geturl() != request.full_url:
            raise RuntimeError("local GROBID health request returned an unexpected response")
        if response.read(100).strip().lower() != b"true":
            raise RuntimeError("local GROBID health check did not return true")


def _frontiers_pdf_url(record: dict[str, object]) -> str:
    doi = str(record.get("doi") or "").strip()
    if not re.fullmatch(r"10\.3389/[A-Za-z0-9._-]+", doi):
        raise ValueError("record has no valid Frontiers DOI")
    info = record.get("journalInfo")
    journal = info.get("journal") if isinstance(info, dict) else None
    title = str(journal.get("title") or "") if isinstance(journal, dict) else ""
    prefix = "frontiers in "
    if not title.casefold().startswith(prefix):
        raise ValueError("Europe PMC record does not identify a Frontiers journal")
    journal_name = title[len(prefix) :].casefold()
    slug = re.sub(r"[^a-z0-9]+", "-", journal_name).strip("-")
    return f"https://www.frontiersin.org/journals/{slug}/articles/{doi}/pdf"


def _selected_pdf_license_text(pdf: bytes) -> str:
    text = " ".join(extract_text(io.BytesIO(pdf), maxpages=200).split())
    match = re.search(
        r"(?:This is an )?open-access article distributed under the terms of the "
        r"Creative Commons Attribution(?: 4\.0 International)? License(?: \(CC BY\))?",
        text,
        re.IGNORECASE,
    )
    if not match:
        raise PDFExtractionError(
            "selected PDF itself contains no recognized CC BY license statement"
        )
    return " ".join(match.group(0).split())


def _publication_types(record: dict[str, object]) -> list[str]:
    value = record.get("pubTypeList")
    if isinstance(value, dict) and isinstance(value.get("pubType"), list):
        return [str(item) for item in value["pubType"]]
    return []


def _search_page(cursor_mark: str) -> tuple[list[dict[str, object]], str, str]:
    url = f"{API}/search?" + urllib.parse.urlencode(
        {
            "query": SEARCH_QUERY,
            "format": "json",
            "pageSize": str(PAGE_SIZE),
            "cursorMark": cursor_mark,
            "resultType": "core",
        }
    )
    result = _json(url)
    rows = result.get("resultList", {}).get("result", [])
    return (
        [row for row in rows if isinstance(row, dict)],
        url,
        str(result.get("nextCursorMark") or ""),
    )


def _search_candidates(
    *,
    max_pages: int = MAX_PAGES,
    json_loader=_json,
) -> tuple[list[dict[str, object]], list[str]]:
    """Follow Europe PMC cursor marks and stop on a repeated/missing cursor."""
    candidates: list[dict[str, object]] = []
    urls: list[str] = []
    seen_cursor_marks = {"*"}
    cursor = "*"
    seen_records: set[tuple[str, str]] = set()
    for _ in range(max_pages):
        params = {
            "query": SEARCH_QUERY,
            "format": "json",
            "pageSize": str(PAGE_SIZE),
            "cursorMark": cursor,
            "resultType": "core",
        }
        url = f"{API}/search?" + urllib.parse.urlencode(params)
        payload = json_loader(url)
        urls.append(url)
        result_list = payload.get("resultList", {})
        rows = result_list.get("result", []) if isinstance(result_list, dict) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            identity = (str(row.get("pmcid") or ""), str(row.get("doi") or ""))
            if identity not in seen_records:
                seen_records.add(identity)
                candidates.append(row)
        next_cursor = str(payload.get("nextCursorMark") or "")
        if not next_cursor or next_cursor in seen_cursor_marks:
            break
        seen_cursor_marks.add(next_cursor)
        cursor = next_cursor
    return candidates, urls


def main() -> int:
    _check_grobid()
    candidates, search_urls = _search_candidates()

    previous = {}
    if REPORT.exists():
        try:
            previous = json.loads(REPORT.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {}
    prior_records = previous.get("records", [])
    prior_by_doi = {
        str(row.get("doi") or ""): row
        for row in prior_records
        if isinstance(row, dict) and row.get("doi")
    }
    processed = []
    if previous.get("search_query") == SEARCH_QUERY:
        by_doi = {str(row.get("doi") or ""): row for row in candidates}
        for prior in prior_records:
            if previous.get("processor_version") != PARSER_VERSION:
                break
            local_path = Path(str(prior.get("ignored_local_pdf") or ""))
            doi = str(prior.get("doi") or "")
            try:
                data = local_path.read_bytes()
            except OSError:
                continue
            if hashlib.sha256(data).hexdigest() != prior.get("pdf_sha256"):
                continue
            metadata = by_doi.get(doi, {})
            prior["publication_types"] = _publication_types(metadata)
            prior["article_classification"] = (
                "review"
                if any("review" in item.casefold() for item in prior["publication_types"])
                else "original_or_other"
            )
            processed.append(prior)

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[dict[str, str]] = list(previous.get("acquisition_or_processing_failures", []))
    seen_dois: set[str] = {str(row.get("doi") or "") for row in processed}
    seen_dois.update(str(row.get("doi") or "") for row in failures)
    attempted = len(processed) + len(failures)
    for record in candidates:
        if len(processed) >= TARGET_COUNT:
            break
        pmcid = str(record.get("pmcid") or "").upper()
        doi = str(record.get("doi") or "").strip()
        license_label = str(record.get("license") or "").strip()
        license_key = license_label.casefold().replace(" ", "-")
        if (
            not re.fullmatch(r"PMC[0-9]+", pmcid)
            or not re.fullmatch(r"10\.3389/[A-Za-z0-9._-]+", doi)
            or doi in seen_dois
            or license_key not in {"cc-by", "cc-by-4.0", "cc-by-3.0", "cc-by-2.0", "cc0", "cc0-1.0"}
        ):
            continue
        if doi in seen_dois:
            continue
        seen_dois.add(doi)
        attempted += 1
        pdf_url = ""
        try:
            xml_url = f"{API}/{pmcid}/fullTextXML"
            xml = _get(xml_url, timeout=30, max_bytes=20 * 1024 * 1024)
            xml_license_blocks = _license_blocks(xml)
            pdf_url = _frontiers_pdf_url(record)
            prior = prior_by_doi.get(doi, {})
            prior_path = Path(str(prior.get("ignored_local_pdf") or ""))
            try:
                prior_resolved = prior_path.resolve()
                cache_root = PDF_DIR.resolve()
                prior_is_cached = prior_resolved.is_relative_to(cache_root)
                prior_bytes = prior_path.read_bytes() if prior_is_cached else b""
            except OSError:
                prior_bytes = b""
            if (
                prior_bytes
                and prior.get("selected_pdf_url") == pdf_url
                and hashlib.sha256(prior_bytes).hexdigest() == prior.get("pdf_sha256")
            ):
                pdf = prior_bytes
            else:
                pdf = _get(pdf_url, timeout=30, max_bytes=40 * 1024 * 1024)
            pdf_license = _selected_pdf_license_text(pdf)
            pdf_sha256 = hashlib.sha256(pdf).hexdigest()
            pdf_path = PDF_DIR / f"{pmcid}.pdf"
            pdf_path.write_bytes(pdf)
            locator = {
                "work_id": doi,
                "source_type": "pdf",
                "locator_url": pdf_url,
                "license": license_label,
                "license_provenance": (
                    "Europe PMC selected-copy XML license block: "
                    + "; ".join(xml_license_blocks)
                    + f"; exact selected PDF statement: {pdf_license}"
                ),
                "license_status": "permissive",
                "processing_allowed": True,
                "storage_decision": "cache_only",
            }
            extraction = extract_pdf_cached(
                locator,
                cache_dir=DEFAULT_CACHE_DIR,
                grobid_url=GROBID_URL,
                timeout=30,
                grobid_timeout=90,
                minimum_interval=1.0,
                expected_pdf_sha256=pdf_sha256,
                fetcher=lambda url, *, timeout, max_bytes, data=pdf: data,
            )
            sections = extraction.get("sections", {})
            processed.append(
                {
                    "pmcid": pmcid,
                    "doi": doi,
                    "processor_version": PARSER_VERSION,
                    "title": str(record.get("title") or ""),
                    "authors": str(record.get("authorString") or ""),
                    "publication_types": _publication_types(record),
                    "article_classification": (
                        "review"
                        if any("review" in item.casefold() for item in _publication_types(record))
                        else "original_or_other"
                    ),
                    "license": license_label,
                    "xml_license_blocks": list(xml_license_blocks),
                    "pdf_license_text": pdf_license,
                    "article_url": f"https://www.frontiersin.org/articles/{doi}/full",
                    "selected_pdf_url": pdf_url,
                    "pdf_sha256": pdf_sha256,
                    "pdf_bytes": len(pdf),
                    "ignored_local_pdf": str(pdf_path).replace("\\", "/"),
                    "extractor": extraction.get("extractor"),
                    "grobid_failure_category": extraction.get("failure_category"),
                    "fallback_status": extraction.get("fallback"),
                    "sections": {
                        name: [
                            {
                                "title": row.get("title", ""),
                                "evidence": row.get("evidence", "")[:180],
                            }
                            for row in rows[:1]
                        ]
                        for name, rows in sections.items()
                        if isinstance(rows, list) and rows
                    },
                    "manual_accuracy_review": "pending",
                }
            )
            print(f"processed {len(processed)}/{TARGET_COUNT}: {doi}", flush=True)
        except Exception as error:
            failures.append(
                {
                    "pmcid": pmcid,
                    "doi": doi,
                    "selected_pdf_url": pdf_url,
                    "failure_category": type(error).__name__,
                    "reason": str(error)[:300],
                }
            )
            print(f"failed {doi}: {type(error).__name__}: {error}", flush=True)

    grobid_categories = Counter(str(row.get("grobid_failure_category") or "") for row in processed)
    fallbacks = sum(row.get("extractor") == "pdfminer" for row in processed)
    no_sections = sum(row.get("fallback_status") == "no_target_sections" for row in processed)
    technical_errors = sum(
        row.get("grobid_failure_category")
        in {
            "grobid_timeout",
            "grobid_unavailable",
            "grobid_http_or_transport_error",
            "invalid_tei",
            "grobid_error",
        }
        for row in processed
    )
    no_target_reviews = sum(
        row.get("grobid_failure_category") == "no_target_sections"
        and row.get("article_classification") == "review"
        for row in processed
    )
    report = {
        "task": "S6.3",
        "status": "processed_30_manual_accuracy_review_pending"
        if len(processed) == TARGET_COUNT
        else "incomplete_30_pdf_processing",
        "target_count": TARGET_COUNT,
        "processor_version": PARSER_VERSION,
        "processed_count": len(processed),
        "candidate_count": len(candidates),
        "attempted_count": attempted,
        "search_query": SEARCH_QUERY,
        "search_urls": search_urls,
        "grobid_runtime": {
            "health_check": "HTTP 200 true",
            "image": "grobid/grobid:0.9.1-crf",
            "image_digest": (
                "sha256:223957791ac2bbe48609dcc58a689b16b60baeae13a8734ef440ae6bfb38f4cd"
            ),
            "container": "ca-plastics-s6-3-grobid",
            "memory_gb": 4,
        },
        "sample_bias": (
            "Convenience sample of Europe PMC-indexed, OA, CC BY/CC0 microplastic-related records "
            "with Frontiers DOIs and direct publisher PDFs. It is not representative of all PDFs "
            "or the project's candidate corpus."
        ),
        "grobid_failure_rate": technical_errors / len(processed) if processed else None,
        "grobid_non_target_or_error_rate": (
            (technical_errors + grobid_categories.get("no_target_sections", 0)) / len(processed)
            if processed
            else None
        ),
        "grobid_technical_failure_rate": technical_errors / len(processed) if processed else None,
        "grobid_no_target_sections_rate": (
            grobid_categories.get("no_target_sections", 0) / len(processed) if processed else None
        ),
        "grobid_failure_categories": dict(grobid_categories),
        "pdfminer_fallback_count": fallbacks,
        "no_target_sections_count": no_sections,
        "grobid_no_target_reviews_count": no_target_reviews,
        "manual_accuracy_review": (
            "pending; automated section output and the selected PDF's license statement "
            "are recorded per PDF"
        ),
        "acquisition_or_processing_failures": failures,
        "records": processed,
        "notes": [
            "The search follows at most two 30-record cursor pages.",
            "Processing stops at 30 verified PDFs.",
            "The selected PDF and its XML copy must both carry CC BY license evidence.",
            "PDF requests reject redirects and non-public DNS resolutions.",
            "The GROBID endpoint is restricted to 127.0.0.1:8070.",
            "Full PDFs and GROBID TEI stay in ignored data/raw caches.",
            "The report contains hashes and short evidence snippets.",
        ],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"S6.3: {len(processed)}/{TARGET_COUNT} PDFs processed; GROBID failure rate="
        f"{report['grobid_failure_rate']}; pdfminer fallback={fallbacks}; "
        f"no target sections={no_sections}"
    )
    print(f"Report: {REPORT}; acquisition/processing failures: {len(failures)}")
    return 0 if len(processed) == TARGET_COUNT else 1


if __name__ == "__main__":
    raise SystemExit(main())
