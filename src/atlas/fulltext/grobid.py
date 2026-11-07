"""License-gated GROBID PDF extraction with a local pdfminer fallback."""

from __future__ import annotations

import hashlib
import io
import ipaddress
import json
import math
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from pathlib import Path

from defusedxml import ElementTree as SafeET
from defusedxml.common import DefusedXmlException

from atlas.fulltext import _license_decision
from atlas.fulltext.jats import _LABELS, _bounded, _clean, _norm_heading

DEFAULT_CACHE_DIR = Path("data/raw/fulltext_cache/pdf")
DEFAULT_MAX_PDF_BYTES = 40 * 1024 * 1024
PARSER_VERSION = "s6.3-pdf-sections-v3"
_last_request_at: float | None = None
_rate_lock = threading.Lock()


class PDFExtractionError(ValueError):
    """Raised when a PDF cannot be processed under the selected-copy license."""


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _public_https_url(url: str) -> urllib.parse.SplitResult:
    """Validate the complete HTTPS locator and reject private/reserved DNS targets."""
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.fragment
    ):
        raise PDFExtractionError("PDF source must be a public HTTPS URL on port 443")
    host = parsed.hostname.rstrip(".").casefold()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
        raise PDFExtractionError("PDF source hostname is not public")
    try:
        addresses = {
            ipaddress.ip_address(item[4][0])
            for item in socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
        }
    except (OSError, ValueError) as error:
        raise PDFExtractionError("PDF source hostname could not be resolved safely") from error
    if not addresses or any(not address.is_global for address in addresses):
        raise PDFExtractionError("PDF source resolves to a non-public address")
    return parsed


def _validate_grobid_endpoint(base_url: str) -> str:
    """Accept only explicit loopback HTTP to the fixed local GROBID port."""
    try:
        parsed = urllib.parse.urlsplit(base_url)
        host = (parsed.hostname or "").casefold()
        is_loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        parsed = urllib.parse.urlsplit(base_url)
        is_loopback = (parsed.hostname or "").casefold() == "localhost"
    if (
        parsed.scheme != "http"
        or not is_loopback
        or parsed.port != 8070
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise PDFExtractionError("GROBID endpoint must be local HTTP on port 8070")
    return f"{parsed.scheme}://{parsed.netloc}"


def _validate_locator(locator: Mapping[str, object]) -> tuple[str, str]:
    url = str(locator.get("locator_url") or "").strip()
    license_label = str(locator.get("license") or "").strip()
    if locator.get("source_type") != "pdf" or not url.startswith("https://"):
        raise PDFExtractionError("only selected HTTPS PDF locators can be processed")
    _, allowed, decision = _license_decision(license_label)
    if (
        locator.get("processing_allowed") is not True
        or locator.get("license_status") != "permissive"
        or locator.get("storage_decision") != "cache_only"
        or not allowed
        or decision != "cache_only"
    ):
        raise PDFExtractionError("selected-copy license does not allow processing and cache")
    return url, license_label


def _post_grobid(pdf: bytes, *, base_url: str, timeout: float) -> bytes:
    base_url = _validate_grobid_endpoint(base_url)
    boundary = "----atlas-grobid-" + hashlib.sha256(pdf[:4096]).hexdigest()[:24]
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="input"; '
            'filename="article.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()
        + pdf
        + f"\r\n--{boundary}--\r\n".encode()
    )
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/processFulltextDocument",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    opener = urllib.request.build_opener(_RejectRedirects())
    with opener.open(request, timeout=timeout) as response:
        if response.status != 200:
            raise urllib.error.HTTPError(request.full_url, response.status, "GROBID", {}, None)
        if response.geturl() != request.full_url:
            raise PDFExtractionError("GROBID request redirected away from the local service")
        return response.read(20 * 1024 * 1024 + 1)


def parse_tei(tei: bytes | str, *, max_chars: int = 1200) -> dict[str, object]:
    """Map GROBID TEI body divisions into the JATS section result shape."""
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    try:
        root = SafeET.fromstring(tei)
    except (DefusedXmlException, ET.ParseError, ValueError) as error:
        raise PDFExtractionError(f"invalid GROBID TEI: {error}") from error
    if root.tag.rsplit("}", 1)[-1].casefold() != "tei":
        raise PDFExtractionError("GROBID response root is not TEI")
    results: dict[str, list[dict[str, str]]] = {
        "methods": [],
        "study_area": [],
        "sampling": [],
        "data_availability": [],
    }
    body = next((node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "body"), None)
    if body is None:
        raise PDFExtractionError("GROBID TEI contains no body")
    for div in body.iter():
        if div.tag.rsplit("}", 1)[-1] != "div":
            continue
        head = next((node for node in div if node.tag.rsplit("}", 1)[-1] == "head"), None)
        title = _clean(" ".join(head.itertext())) if head is not None else ""
        heading_title = (
            re.sub(
                r"^\s*(?:\d+(?:\.\d+)*|[ivxlcdm]+)[.)]?\s+",
                "",
                title,
                flags=re.IGNORECASE,
            )
            .split(":", 1)[0]
            .strip()
        )
        normalized = _norm_heading(heading_title)
        kind = str(div.attrib.get("type") or "")
        kind_norm = _norm_heading(kind)
        target = next(
            (
                name
                for name, labels in _LABELS.items()
                if normalized in {_norm_heading(label) for label in labels}
                or kind_norm in {_norm_heading(label) for label in labels}
            ),
            None,
        )
        score = (
            3
            if target and normalized in {_norm_heading(label) for label in _LABELS[target]}
            else 2
            if target
            else 0
        )
        if target is None:
            if normalized.startswith(("methods ", "materials and methods ")):
                target = "methods"
            elif normalized.startswith(
                ("study area ", "study site ", "study region ", "study location ")
            ):
                target = "study_area"
            elif normalized.startswith(("sampling ", "sample collection ", "specimen collection ")):
                target = "sampling"
            elif normalized.startswith(("data availability ", "availability of data ")):
                target = "data_availability"
            if target:
                score = 1
        if not target:
            continue
        paragraphs = []
        for node in div.iter():
            if node is div or node is head:
                continue
            if node.tag.rsplit("}", 1)[-1] == "p":
                text = _clean(" ".join(node.itertext()))
                if text:
                    paragraphs.append(text)
        evidence = _clean(" ".join(paragraphs))
        if evidence:
            results[target].append(
                {
                    "section_id": str(div.attrib.get("n") or ""),
                    "title": title,
                    "sec_type": kind,
                    "evidence": _bounded(evidence, max_chars),
                    "truncated": str(len(evidence) > max_chars).lower(),
                    "match_score": str(score),
                }
            )
    return {"sections": results, "fallback": "" if any(results.values()) else "no_target_sections"}


def extract_pdfminer(pdf: bytes, *, max_chars: int = 1200) -> dict[str, object]:
    """Extract section snippets from selectable PDF text using pdfminer.six."""
    try:
        from pdfminer.high_level import extract_text
        from pdfminer.pdfdocument import PDFEncryptionError
        from pdfminer.pdfparser import PDFSyntaxError

        text = extract_text(io.BytesIO(pdf), maxpages=200)
    except ImportError as error:
        raise PDFExtractionError("pdfminer.six is not installed") from error
    except (PDFEncryptionError, PDFSyntaxError, ValueError, OSError) as error:
        raise PDFExtractionError(f"pdfminer could not read PDF: {error}") from error
    results: dict[str, list[dict[str, str]]] = {
        "methods": [],
        "study_area": [],
        "sampling": [],
        "data_availability": [],
    }
    active: list[str] | None = None
    chunks: dict[str, list[tuple[str, list[str]]]] = {}
    for raw in text.splitlines():
        line = _clean(raw)
        if not line:
            continue
        matched = _pdf_heading_target(line)
        if matched:
            target = matched
            bucket = chunks.setdefault(target, [])
            heading_title = line.split(":", 1)[0].strip()
            inline_text = line.split(":", 1)[1].strip() if ":" in line else ""
            bucket.append((heading_title, [inline_text] if inline_text else []))
            active = bucket[-1][1]
        elif _is_other_pdf_heading(line):
            active = None
        elif active is not None:
            active.append(line)
    for target, sections in chunks.items():
        for index, (title, pieces) in enumerate(sections, start=1):
            evidence = _clean(" ".join(pieces))
            if evidence:
                results[target].append(
                    {
                        "section_id": f"pdfminer-{target}-{index}",
                        "title": title,
                        "sec_type": "",
                        "evidence": _bounded(evidence, max_chars),
                        "truncated": str(len(evidence) > max_chars).lower(),
                        "match_score": "1",
                    }
                )
    return {"sections": results, "fallback": "" if any(results.values()) else "no_target_sections"}


def _pdf_heading_target(line: str) -> str | None:
    """Match standalone, heading-like PDF lines without treating prose as headings."""
    heading_line = line.split(":", 1)[0].strip() if ":" in line else line
    heading_norm = _norm_heading(heading_line)
    exact = {
        target: {_norm_heading(label) for label in labels} for target, labels in _LABELS.items()
    }
    for target, labels in exact.items():
        if heading_norm in labels:
            return target
    if not _is_other_pdf_heading(heading_line) or "," in heading_line:
        return None
    if heading_norm.startswith(("methods ", "materials and methods ")):
        return "methods"
    if heading_norm.startswith(("study area ", "study site ", "study region ", "study location ")):
        return "study_area"
    if heading_norm.startswith(("sampling ", "sample collection ", "specimen collection ")):
        return "sampling"
    if heading_norm.startswith(("data availability ", "availability of data ")):
        return "data_availability"
    return None


def _is_other_pdf_heading(line: str) -> bool:
    """Conservative layout heuristic used only to delimit fallback PDF sections."""
    trimmed = line.strip()
    if (
        not trimmed
        or len(trimmed) > 100
        or trimmed.endswith((".", "?", "!", ";"))
        or len(trimmed.split()) > 12
    ):
        return False
    if re.search(
        r"\b(?:am|are|is|was|were|has|have|had|can|could|may|might|will|would)\b",
        trimmed,
        re.I,
    ):
        return False
    return trimmed[0].isupper() or trimmed.isupper()


def extract_pdf(
    pdf: bytes,
    *,
    grobid_url: str = "http://127.0.0.1:8070",
    grobid_timeout: float = 120.0,
    max_chars: int = 1200,
    grobid: Callable[..., bytes] | None = None,
    fallback: Callable[..., dict[str, object]] | None = None,
) -> dict[str, object]:
    """Try GROBID TEI, then fallback to pdfminer with an explicit failure code."""
    if not math.isfinite(grobid_timeout) or grobid_timeout <= 0:
        raise ValueError("grobid_timeout must be a positive finite number")
    if len(pdf) > DEFAULT_MAX_PDF_BYTES:
        return {
            "sections": _empty_sections(),
            "extractor": "none",
            "failure_category": "pdf_too_large",
            "fallback": "pdf_exceeds_40_mib_limit",
        }
    if not pdf.startswith(b"%PDF-"):
        return {
            "sections": _empty_sections(),
            "extractor": "none",
            "failure_category": "malformed_pdf",
            "fallback": "invalid_pdf_header",
        }
    category = ""
    try:
        tei = (grobid or _post_grobid)(pdf, base_url=grobid_url, timeout=grobid_timeout)
        if len(tei) > 20 * 1024 * 1024:
            raise PDFExtractionError("GROBID TEI response exceeds 20 MiB")
        parsed = parse_tei(tei, max_chars=max_chars)
        if parsed["fallback"]:
            category = "no_target_sections"
        else:
            return {**parsed, "extractor": "grobid", "failure_category": ""}
    except TimeoutError:
        category = "grobid_timeout"
    except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError) as error:
        reason = error.reason if isinstance(error, urllib.error.URLError) else error
        if isinstance(reason, (TimeoutError, socket.timeout)):
            category = "grobid_timeout"
        elif isinstance(reason, (ConnectionError, OSError)):
            category = "grobid_unavailable"
        else:
            category = "grobid_http_or_transport_error"
    except PDFExtractionError:
        category = "invalid_tei"
    except Exception:
        category = "grobid_error"
    try:
        parsed = (fallback or extract_pdfminer)(pdf, max_chars=max_chars)
        return {**parsed, "extractor": "pdfminer", "failure_category": category}
    except Exception as error:
        return {
            "sections": _empty_sections(),
            "extractor": "none",
            "failure_category": category or "grobid_error",
            "fallback": f"pdfminer_error: {type(error).__name__}",
        }


def _empty_sections() -> dict[str, list[dict[str, str]]]:
    return {name: [] for name in ("methods", "study_area", "sampling", "data_availability")}


def _throttle(interval: float) -> None:
    global _last_request_at
    with _rate_lock:
        now = time.monotonic()
        if _last_request_at is not None and interval > now - _last_request_at:
            time.sleep(interval - (now - _last_request_at))
        _last_request_at = time.monotonic()


def _fetch_pdf(url: str, *, timeout: float, max_bytes: int) -> bytes:
    _public_https_url(url)
    request = urllib.request.Request(
        url, headers={"User-Agent": "CA-Plastics-Research-Dash/0.1", "Accept": "application/pdf"}
    )
    opener = urllib.request.build_opener(_RejectRedirects())
    with opener.open(request, timeout=timeout) as response:
        if response.status != 200 or response.geturl() != url:
            raise PDFExtractionError("PDF request returned an unexpected response")
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes or not data.startswith(b"%PDF-"):
        raise PDFExtractionError("download is not a valid bounded PDF")
    return data


def extract_pdf_cached(
    locator: Mapping[str, object],
    *,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    grobid_url: str = "http://127.0.0.1:8070",
    timeout: float = 30.0,
    grobid_timeout: float = 120.0,
    minimum_interval: float = 1.0,
    expected_pdf_sha256: str | None = None,
    fetcher: Callable[..., bytes] | None = None,
    grobid: Callable[..., bytes] | None = None,
    fallback: Callable[..., dict[str, object]] | None = None,
) -> dict[str, object]:
    """License-check, fetch, extract, and cache only bounded derived sections."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("download timeout must be a positive finite number")
    if not math.isfinite(grobid_timeout) or grobid_timeout <= 0:
        raise ValueError("grobid_timeout must be a positive finite number")
    if not math.isfinite(minimum_interval) or minimum_interval < 0:
        raise ValueError("minimum_interval must be a finite non-negative number")
    grobid_url = _validate_grobid_endpoint(grobid_url)
    url, license_label = _validate_locator(locator)
    work_id = str(locator.get("work_id") or "")
    license_provenance = str(locator.get("license_provenance") or "")
    identity = hashlib.sha256(
        f"{PARSER_VERSION}\0{work_id}\0{url}\0{license_label}\0{license_provenance}".encode()
    ).hexdigest()
    path = Path(cache_dir) / f"{identity}.json"
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        encoded_result = json.dumps(cached["result"], ensure_ascii=False, sort_keys=True)
        if (
            cached.get("locator_url") == url
            and cached.get("license") == license_label
            and cached.get("license_provenance") == license_provenance
            and cached.get("work_id") == work_id
            and cached.get("license_status") == "permissive"
            and cached.get("storage_decision") == "cache_only"
            and cached.get("result_sha256") == hashlib.sha256(encoded_result.encode()).hexdigest()
            and re.fullmatch(r"[0-9a-f]{64}", str(cached.get("pdf_sha256") or ""))
            and (expected_pdf_sha256 is None or cached.get("pdf_sha256") == expected_pdf_sha256)
        ):
            return cached["result"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    _throttle(minimum_interval)
    pdf = (fetcher or _fetch_pdf)(url, timeout=timeout, max_bytes=DEFAULT_MAX_PDF_BYTES)
    pdf_digest = hashlib.sha256(pdf).hexdigest()
    if expected_pdf_sha256 is not None and pdf_digest != expected_pdf_sha256:
        raise PDFExtractionError("fetched PDF hash does not match the bound selected copy")
    result = extract_pdf(
        pdf, grobid_url=grobid_url, grobid_timeout=grobid_timeout, grobid=grobid, fallback=fallback
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded_result = json.dumps(result, ensure_ascii=False, sort_keys=True)
    envelope = {
        "work_id": work_id,
        "locator_url": url,
        "license": license_label,
        "license_provenance": license_provenance,
        "license_status": "permissive",
        "storage_decision": "cache_only",
        "pdf_sha256": pdf_digest,
        "result_sha256": hashlib.sha256(encoded_result.encode()).hexdigest(),
        "result": result,
    }
    temp = path.with_suffix(".json.tmp")
    try:
        temp.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return result
