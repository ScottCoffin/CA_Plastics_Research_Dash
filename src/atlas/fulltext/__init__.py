"""Open-access full-text discovery and processing modules."""

from __future__ import annotations

import ipaddress
import json
import re
from collections.abc import Iterable, Mapping
from urllib.parse import urlsplit

import pyarrow as pa
import pyarrow.parquet as pq

LOCATOR_SCHEMA = pa.schema(
    [
        ("work_id", pa.string()),
        ("source_type", pa.string()),
        ("locator_url", pa.string()),
        ("pmcid", pa.string()),
        ("license", pa.string()),
        ("license_provenance", pa.string()),
        ("license_status", pa.string()),
        ("processing_allowed", pa.bool_()),
        ("storage_decision", pa.string()),
        ("attribution_url", pa.string()),
    ]
)

# Restrict automatic processing and caching to licenses whose reuse permissions
# are clear for this project. Other labels remain reviewable, never presumed OK.
_ALLOWED_LICENSES = {
    "cc0",
    "cc0-1.0",
    "cc-by",
    "cc-by-4.0",
    "cc-by-3.0",
    "cc-by-2.0",
}
_RESTRICTED_LICENSES = {"all-rights-reserved", "arr", "closed"}
_PMCID = re.compile(r"^(?:PMC)?[0-9]+$", re.IGNORECASE)


def _id(value: object) -> str:
    text = str(value or "").rstrip("/")
    return text.rsplit("/", 1)[-1]


def _safe_https_url(value: object) -> str:
    """Return a conservative public HTTPS locator, or an empty string."""
    text = str(value or "").strip()
    if not text or len(text) > 2048:
        return ""
    try:
        parsed = urlsplit(text)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return ""
        if parsed.port not in (None, 443):
            return ""
        host = parsed.hostname.rstrip(".").casefold()
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost"):
            return ""
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            if not address.is_global:
                return ""
        return text
    except ValueError:
        return ""


def _license_decision(value: object) -> tuple[str, bool, str]:
    label = str(value or "").strip()
    normalized = label.casefold().replace("https://creativecommons.org/licenses/", "")
    if normalized.startswith("by/"):
        normalized = f"cc-{normalized}"
    normalized = normalized.replace("https://creativecommons.org/publicdomain/zero/", "cc0-")
    normalized = normalized.strip("/ ").replace("/", "-")
    normalized = normalized.replace(" ", "-")
    if normalized.startswith("by-"):
        normalized = f"cc-{normalized}"
    if normalized.endswith("deed.en"):
        normalized = normalized[:-8].rstrip("-")
    if normalized in _ALLOWED_LICENSES:
        return "permissive", True, "cache_only"
    if normalized in _RESTRICTED_LICENSES:
        return "restricted", False, "do_not_cache"
    return ("unknown" if not label else "review"), False, "review"


def _pmc_location_license(raw: Mapping[str, object], pmcid: str) -> tuple[str, str]:
    """Read license evidence only from a trusted PMC/Europe PMC copy URL."""
    locations = raw.get("locations")
    if not isinstance(locations, list):
        return "", "unknown: no OpenAlex locations list"
    matches: list[tuple[str, str]] = []
    for index, location in enumerate(locations):
        if not isinstance(location, Mapping):
            continue
        urls = [location.get("landing_page_url"), location.get("pdf_url")]
        if not any(_url_names_pmcid(url, pmcid) for url in urls):
            continue
        label = str(location.get("license") or "").strip()
        if label:
            matches.append(
                (
                    label,
                    f"OpenAlex locations[{index}].license; "
                    f"trusted repository path identifies {pmcid}",
                )
            )
    unique_labels = {label for label, _ in matches}
    if len(unique_labels) > 1:
        return "", f"unknown: conflicting license evidence for {pmcid} locations"
    if matches:
        return matches[0]
    return "", f"unknown: no license evidence tied to {pmcid} location"


def _url_names_pmcid(value: object, pmcid: str) -> bool:
    """Require HTTPS article/fulltext paths on a trusted PMC repository host."""
    text = str(value or "")
    if not text or not _safe_https_url(text):
        return False
    try:
        parsed = urlsplit(text)
    except ValueError:
        return False
    host = (parsed.hostname or "").casefold()
    path = [segment for segment in parsed.path.split("/") if segment]
    canonical_id = pmcid.casefold()
    if host == "pmc.ncbi.nlm.nih.gov":
        return (
            len(path) >= 2
            and path[0].casefold() == "articles"
            and path[1].casefold() == canonical_id
        )
    if host == "www.ncbi.nlm.nih.gov":
        # Legacy PMC paths, as OpenAlex reports them: /pmc/articles/<PMCID or digits>.
        return (
            len(path) >= 3
            and path[0].casefold() == "pmc"
            and path[1].casefold() == "articles"
            and path[2].casefold() in {canonical_id, canonical_id.removeprefix("pmc")}
        )
    if host in {"europepmc.org", "www.europepmc.org"}:
        return (
            len(path) >= 2
            and path[0].casefold() == "articles"
            and path[1].casefold() == canonical_id
        )
    if host == "www.ebi.ac.uk":
        return (
            len(path) == 5
            and [segment.casefold() for segment in path[:3]] == ["europepmc", "webservices", "rest"]
            and path[3].casefold() == canonical_id
            and path[4].casefold() == "fulltextxml"
        )
    return False


def _raw_record(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, Mapping) else {}
    return {}


def locate_records(
    candidates: Iterable[Mapping[str, object]],
    raw_by_work_id: Mapping[str, object],
) -> list[dict[str, object]]:
    """Choose an XML/PDF/none locator without downloading article text.

    Europe PMC XML wins when an OA PMCID is present. Otherwise only the best
    OA location's direct PDF URL is considered. A locator is not permission:
    unknown/review licenses are retained for audit but cannot be processed or
    cached automatically.
    """
    output = []
    for candidate in candidates:
        work_id = _id(candidate.get("work_id"))
        raw = _raw_record(raw_by_work_id.get(work_id, {}))
        ids = raw.get("ids") if isinstance(raw.get("ids"), Mapping) else {}
        pmcid_value = ids.get("pmcid") if isinstance(ids, Mapping) else None
        # OpenAlex gives a URL (https://www.ncbi.nlm.nih.gov/pmc/articles/221095); keep the
        # last path segment so the bare-ID check below accepts it.
        pmcid = str(pmcid_value or "").strip().rstrip("/").rsplit("/", 1)[-1]
        if pmcid and _PMCID.fullmatch(pmcid):
            pmcid = pmcid.upper()
            if not pmcid.startswith("PMC"):
                pmcid = f"PMC{pmcid}"
        else:
            pmcid = ""

        oa = raw.get("open_access") if isinstance(raw.get("open_access"), Mapping) else {}
        is_oa = bool(oa.get("is_oa", candidate.get("is_oa", False)))
        best = raw.get("best_oa_location")
        best = best if isinstance(best, Mapping) else {}
        source_type = "none"
        locator_url = ""
        selected_pmcid = ""
        attribution_url = ""
        license_value = ""
        license_provenance = "unknown: no selected full-text copy"
        if is_oa and pmcid:
            source_type = "xml"
            selected_pmcid = pmcid
            locator_url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
            attribution_url = f"https://europepmc.org/articles/{pmcid}"
            license_value, license_provenance = _pmc_location_license(raw, pmcid)
        elif is_oa:
            pdf_url = _safe_https_url(best.get("pdf_url"))
            if pdf_url:
                source_type = "pdf"
                locator_url = pdf_url
                attribution_url = str(best.get("landing_page_url") or candidate.get("oa_url") or "")
                attribution_url = _safe_https_url(attribution_url) or pdf_url
                license_value = str(best.get("license") or "").strip()
                license_provenance = (
                    "unknown: best_oa_location license missing for selected pdf_url"
                    if not license_value
                    else "OpenAlex best_oa_location.license for selected pdf_url"
                )
        license_label, processing_allowed, storage_decision = _license_decision(license_value)

        output.append(
            {
                "work_id": work_id,
                "source_type": source_type,
                "locator_url": locator_url,
                "pmcid": selected_pmcid,
                "license": str(license_value or ""),
                "license_provenance": license_provenance,
                "license_status": license_label,
                "processing_allowed": processing_allowed,
                "storage_decision": storage_decision,
                "attribution_url": attribution_url,
            }
        )
    return sorted(output, key=lambda row: str(row["work_id"]))


def write_locator(rows: Iterable[Mapping[str, object]], path: str) -> None:
    """Write deterministic locator records as Parquet."""
    pq.write_table(
        pa.Table.from_pylist(list(rows), schema=LOCATOR_SCHEMA), path, compression="zstd"
    )


def coverage_report(rows: Iterable[Mapping[str, object]], *, source: str) -> str:
    """Render deterministic XML/PDF/none and license coverage counts."""
    records = list(rows)
    total = len(records)
    counts = {
        kind: sum(row.get("source_type") == kind for row in records)
        for kind in ("xml", "pdf", "none")
    }
    lines = [
        "# S6.1 full-text locator coverage",
        "",
        f"Source: `{source}` (candidate rows: {total})",
        "",
        "| Locator | Works | Share |",
        "|---|---:|---:|",
    ]
    for kind in ("xml", "pdf", "none"):
        share = counts[kind] / total * 100 if total else 0.0
        lines.append(
            f"| {kind.upper() if kind != 'none' else 'None'} | {counts[kind]} | {share:.1f}% |"
        )
    lines.extend(
        [
            "",
            "License handling: `permissive` licenses allow processing and gitignored cache only;",
            "`restricted` licenses are blocked; `review`/`unknown` licenses require human review.",
            "A locator is metadata only; this command does not fetch article text.",
            "",
            "| License decision | Works |",
            "|---|---:|",
        ]
    )
    for status in ("permissive", "restricted", "review", "unknown"):
        count = sum(row.get("license_status") == status for row in records)
        lines.append(f"| {status} | {count} |")
    lines.append("")
    return "\n".join(lines)
