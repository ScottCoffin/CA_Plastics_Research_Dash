"""License-gated, integrity-checked Europe PMC JATS file cache."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from atlas.fulltext import _license_decision
from atlas.fulltext.jats import JATSParseError, _parse_xml_document

DEFAULT_CACHE_DIR = Path("data/raw/fulltext_cache")
DEFAULT_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_AGE_DAYS = 30
_PMCID = re.compile(r"^PMC[0-9]+$", flags=re.IGNORECASE)
_last_request_at: float | None = None
_rate_lock = threading.Lock()


class FulltextCacheError(ValueError):
    """Raised when a selected XML copy cannot safely enter or leave cache."""


def _source_url(pmcid: str) -> str:
    return f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"


def _validated_locator(locator: Mapping[str, object]) -> tuple[str, str, str]:
    pmcid = str(locator.get("pmcid") or "").upper()
    license_label = str(locator.get("license") or "").strip()
    if not _PMCID.fullmatch(pmcid):
        raise FulltextCacheError("locator has an invalid PMCID")
    if locator.get("source_type") != "xml":
        raise FulltextCacheError("only XML locators can be cached here")
    if locator.get("processing_allowed") is not True:
        raise FulltextCacheError("selected-copy license does not allow processing")
    if locator.get("license_status") != "permissive":
        raise FulltextCacheError("selected-copy license is not permissive")
    if locator.get("storage_decision") != "cache_only":
        raise FulltextCacheError("selected-copy storage decision does not allow cache")
    normalized, allowed, decision = _license_decision(license_label)
    if not allowed or decision != "cache_only":
        raise FulltextCacheError("locator license label is not on the processing allowlist")
    source = _source_url(pmcid)
    if locator.get("locator_url") != source:
        raise FulltextCacheError("locator URL does not match the selected Europe PMC PMCID")
    return pmcid, license_label, source


def _license_blocks(xml: bytes) -> tuple[str, ...]:
    try:
        document = _parse_xml_document(xml)
    except JATSParseError as error:
        raise FulltextCacheError(f"invalid JATS XML: {error}") from error
    if document.tag.rsplit("}", 1)[-1].casefold() != "article":
        raise FulltextCacheError("XML root is not a JATS article")
    blocks = []
    article_metadata = [
        node for node in document.iter() if node.tag.rsplit("}", 1)[-1].casefold() == "article-meta"
    ]
    for metadata in article_metadata:
        permissions = [
            node for node in metadata if node.tag.rsplit("}", 1)[-1].casefold() == "permissions"
        ]
        for permission in permissions:
            for node in permission.iter():
                if node.tag.rsplit("}", 1)[-1].casefold() != "license":
                    continue
                hrefs = [
                    value
                    for key, value in node.attrib.items()
                    if key.rsplit("}", 1)[-1].casefold() == "href"
                ]
                text = " ".join(hrefs + [" ".join(" ".join(node.itertext()).split())])
                lowered = text.casefold()
                is_by = (
                    "creative commons attribution" in lowered
                    or "creativecommons.org/licenses/by/" in lowered
                ) and not any(
                    marker in lowered
                    for marker in (
                        "noncommercial",
                        "non-commercial",
                        "non commercial",
                        "by-nc",
                        "no derivatives",
                        "no-derivatives",
                        "noderivatives",
                        "by-nd",
                        "by-sa",
                        "share alike",
                        "sharealike",
                    )
                )
                is_cc0 = "creativecommons.org/publicdomain/zero" in lowered or "cc0" in lowered
                if is_by or is_cc0:
                    blocks.append(text)
    if not blocks:
        raise FulltextCacheError("selected JATS copy contains no confirmed CC BY/CC0 license block")
    return tuple(blocks)


def _article_pmcid(xml: bytes) -> str:
    try:
        document = _parse_xml_document(xml)
    except JATSParseError as error:
        raise FulltextCacheError(f"invalid JATS XML: {error}") from error
    values = set()
    for node in document.iter():
        if node.tag.rsplit("}", 1)[-1].casefold() != "article-id":
            continue
        kind = next(
            (
                value.casefold()
                for key, value in node.attrib.items()
                if key.rsplit("}", 1)[-1].casefold() == "pub-id-type"
            ),
            "",
        )
        value = "".join(node.itertext()).strip().upper()
        if kind in {"pmc", "pmcid", "pmcid-ver"}:
            values.add(value.split(".", 1)[0])
    if len(values) != 1:
        raise FulltextCacheError("JATS article must identify exactly one selected PMCID")
    return values.pop()


def _valid_cache(
    xml_path: Path,
    metadata_path: Path,
    *,
    work_id: str,
    pmcid: str,
    license_label: str,
    license_provenance: str,
    source: str,
    now: float,
    max_age_days: int,
) -> bool:
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        payload = xml_path.read_bytes()
        fetched_at = float(metadata["fetched_at_epoch"])
        if not math.isfinite(now) or not math.isfinite(fetched_at) or fetched_at > now:
            return False
        age = now - fetched_at
        max_age_seconds = max_age_days * 86400
        if (
            not math.isfinite(age)
            or not math.isfinite(max_age_seconds)
            or age < 0
            or age > max_age_seconds
        ):
            return False
        if (
            metadata.get("work_id") != work_id
            or metadata.get("pmcid") != pmcid
            or metadata.get("source_url") != source
            or metadata.get("license") != license_label
            or metadata.get("license_provenance") != license_provenance
            or metadata.get("license_status") != "permissive"
            or metadata.get("processing_allowed") is not True
            or metadata.get("storage_decision") != "cache_only"
            or metadata.get("content_sha256") != hashlib.sha256(payload).hexdigest()
            or metadata.get("bytes") != len(payload)
            or not payload.lstrip(b"\xef\xbb\xbf \r\n\t").startswith(b"<")
            or _article_pmcid(payload) != pmcid
        ):
            return False
        license_blocks = list(_license_blocks(payload))
        if metadata.get("selected_copy_license_blocks") != license_blocks:
            return False
        return True
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError, FulltextCacheError):
        return False


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Return no follow-up request for every redirect response."""
        return None


def _fetch_http(url: str, *, timeout: float, max_bytes: int) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "CA-Plastics-Research-Dash/0.1 (license-gated full-text cache)",
            "Accept": "application/xml",
        },
    )
    opener = build_opener(_RejectRedirects())
    try:
        response_context = opener.open(request, timeout=timeout)
    except HTTPError as error:
        raise FulltextCacheError(f"Europe PMC returned HTTP {error.code}") from error
    with response_context as response:
        if response.status != 200:
            raise FulltextCacheError(f"Europe PMC returned HTTP {response.status}")
        if response.geturl() != url:
            raise FulltextCacheError("Europe PMC redirected the XML request")
        payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise FulltextCacheError(f"Europe PMC XML exceeds {max_bytes} bytes")
    return payload


def _wait_for_request(minimum_interval: float) -> None:
    global _last_request_at
    with _rate_lock:
        now = time.monotonic()
        if _last_request_at is not None:
            remaining = minimum_interval - (now - _last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        _last_request_at = time.monotonic()


def fetch_jats_cached(
    locator: Mapping[str, object],
    *,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    timeout: float = 20.0,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
    minimum_interval: float = 1.0,
    fetcher: Callable[..., bytes] | None = None,
    now: float | None = None,
) -> Path:
    """Reuse or fetch one exact license-permitted Europe PMC JATS copy.

    Cache hits require matching PMCID/source/license/storage metadata, a fresh
    cache age, matching SHA-256/size, a valid article identifier, and a
    revalidated CC BY/CC0 JATS license block. Network requests are sequentially
    throttled; failed and nonpermissive responses are never written.
    """
    pmcid, license_label, source = _validated_locator(locator)
    work_id = str(locator.get("work_id") or "")
    license_provenance = str(locator.get("license_provenance") or "")
    directory = Path(cache_dir)
    xml_path = directory / f"{pmcid}.xml"
    metadata_path = directory / f"{pmcid}.json"
    try:
        current_time = float(time.time() if now is None else now)
        numeric_settings = (float(timeout), float(max_age_days), float(minimum_interval))
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("cache timing settings must be finite numbers") from error
    if not math.isfinite(current_time) or not all(
        math.isfinite(value) for value in numeric_settings
    ):
        raise ValueError("cache timing settings must be finite numbers")
    if not math.isfinite(max_age_days * 86400):
        raise ValueError("max_age_days is too large")
    if timeout <= 0 or max_bytes < 1 or max_age_days < 0 or minimum_interval < 0:
        raise ValueError("timeout, max_bytes, max_age_days, and minimum_interval must be valid")
    if _valid_cache(
        xml_path,
        metadata_path,
        work_id=work_id,
        pmcid=pmcid,
        license_label=license_label,
        license_provenance=license_provenance,
        source=source,
        now=current_time,
        max_age_days=max_age_days,
    ):
        return xml_path

    _wait_for_request(minimum_interval)
    payload = (fetcher or _fetch_http)(source, timeout=timeout, max_bytes=max_bytes)
    if not isinstance(payload, bytes) or len(payload) > max_bytes:
        raise FulltextCacheError("fetcher returned invalid or oversized XML bytes")
    if _article_pmcid(payload) != pmcid:
        raise FulltextCacheError("response article ID does not match selected PMCID")
    license_blocks = _license_blocks(payload)
    normalized, _, _ = _license_decision(license_label)
    block_text = " ".join(text.casefold() for text in license_blocks)
    block_by = (
        "creative commons attribution" in block_text
        or "creativecommons.org/licenses/by/" in block_text
    )
    block_cc0 = "creativecommons.org/publicdomain/zero" in block_text or "cc0" in block_text
    if (normalized.startswith("cc-by") and not block_by) or (
        normalized.startswith("cc0") and not block_cc0
    ):
        raise FulltextCacheError("JATS license block does not match locator license class")

    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(payload).hexdigest()
    try:
        fetched_at_utc = datetime.fromtimestamp(current_time, UTC).isoformat()
    except (OverflowError, OSError, ValueError) as error:
        raise ValueError("cache timestamp is outside the supported date range") from error
    metadata = {
        "pmcid": pmcid,
        "work_id": work_id,
        "source_url": source,
        "license": license_label,
        "license_provenance": license_provenance,
        "license_status": "permissive",
        "processing_allowed": True,
        "storage_decision": "cache_only",
        "selected_copy_license_blocks": list(license_blocks),
        "content_sha256": digest,
        "bytes": len(payload),
        "fetched_at_epoch": current_time,
        "fetched_at_utc": fetched_at_utc,
    }
    xml_temp = xml_path.with_suffix(".xml.tmp")
    metadata_temp = metadata_path.with_suffix(".json.tmp")
    try:
        xml_temp.write_bytes(payload)
        metadata_temp.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        os.replace(xml_temp, xml_path)
        os.replace(metadata_temp, metadata_path)
    finally:
        xml_temp.unlink(missing_ok=True)
        metadata_temp.unlink(missing_ok=True)
    return xml_path
