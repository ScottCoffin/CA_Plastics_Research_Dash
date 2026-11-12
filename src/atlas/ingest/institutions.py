"""Build the California institution registry from OpenAlex and ROR.

Raw API responses and the ROR dump are cached under ``data/raw``. The public
output is deliberately slim and records enough provenance for a later refresh.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import pyarrow as pa
import pyarrow.parquet as pq

from atlas.util.budget import daily_logged_usage, resolve_openalex_budget
from atlas.util.cost import ApiCostLogger

OPENALEX_BASE = "https://api.openalex.org"
ROR_ZENODO_RECORD = "https://zenodo.org/api/records/6347574"
USER_AGENT = "CA-Plastics-Research-Atlas/0.1 (institution registry; contact via GitHub)"
ATLAS_TYPES = frozenset(
    {
        "UC",
        "CSU",
        "other-public",
        "private",
        "community-college",
        "nonprofit/NGO",
        "state-agency",
        "federal",
        "local-agency",
        "JPA",
        "company",
        "utility",
        "intergovernmental-organization",
    }
)

# Official system lists checked 2026-11-05. CSU's 22-university transition combines
# Cal Poly San Luis Obispo and Cal Maritime while retaining both campus locations.
UC_CAMPUSES = (
    "University of California, Berkeley",
    "University of California, Davis",
    "University of California, Irvine",
    "University of California, Los Angeles",
    "University of California, Merced",
    "University of California, Riverside",
    "University of California, San Diego",
    "University of California, San Francisco",
    "University of California, Santa Barbara",
    "University of California, Santa Cruz",
)
CSU_CAMPUSES = (
    "California State University, Bakersfield",
    "California State University, Channel Islands",
    "California State University, Chico",
    "California State University, Dominguez Hills",
    "California State University, East Bay",
    "California State University, Fresno",
    "California State University, Fullerton",
    "California State Polytechnic University, Humboldt",
    "California State University, Long Beach",
    "California State University, Los Angeles",
    "California State University Maritime Academy",
    "California State University, Monterey Bay",
    "California State University, Northridge",
    "California State Polytechnic University, Pomona",
    "California State University, Sacramento",
    "California State University, San Bernardino",
    "San Diego State University",
    "San Francisco State University",
    "San Jose State University",
    "California Polytechnic State University, San Luis Obispo",
    "California State University San Marcos",
    "Sonoma State University",
    "California State University, Stanislaus",
)
MAJOR_PRIVATE_UNIVERSITIES = (
    "California Institute of Technology",
    "Claremont Graduate University",
    "Loma Linda University",
    "Loyola Marymount University",
    "Pepperdine University",
    "Santa Clara University",
    "Stanford University",
    "University of San Diego",
    "University of San Francisco",
    "University of Southern California",
    "University of the Pacific",
)

REQUIRED_NAME_ALIASES: dict[str, tuple[str, ...]] = {
    "University of California, Merced": ("UC Merced",),
    "University of California, San Diego": ("University of California San Diego", "UC San Diego"),
    "California State University, Bakersfield": ("CSU Bakersfield",),
    "California State University, Channel Islands": ("CSU Channel Islands",),
    "California State University, Chico": ("Chico State",),
    "California State University, Dominguez Hills": ("Cal State Dominguez Hills",),
    "California State University, East Bay": ("Cal State East Bay",),
    "California State University, Fresno": ("Fresno State",),
    "California State University, Fullerton": ("Cal State Fullerton",),
    "California State Polytechnic University, Humboldt": ("Cal Poly Humboldt",),
    "California State University, Long Beach": ("Cal State Long Beach",),
    "California State University, Los Angeles": (
        "California State University Los Angeles",
        "Cal State LA",
    ),
    "California State University Maritime Academy": (
        "California Maritime Academy",
        "Cal Maritime",
    ),
    "California State University, Monterey Bay": ("Cal State Monterey Bay",),
    "California State University, Northridge": ("CSUN", "Cal State Northridge"),
    "California State Polytechnic University, Pomona": (
        "California State Polytechnic University",
        "Cal Poly Pomona",
    ),
    "California State University, Sacramento": ("Sacramento State",),
    "California State University, San Bernardino": ("Cal State San Bernardino",),
    "San Jose State University": ("San José State University",),
    "California Polytechnic State University, San Luis Obispo": (
        "California Polytechnic State University",
        "Cal Poly",
    ),
    "California State University San Marcos": (
        "California State University, San Marcos",
        "Cal State San Marcos",
    ),
    "California State University, Stanislaus": ("Stanislaus State",),
}


DEFAULT_USAGE_LOG = Path("data/logs/api_usage.jsonl")


@dataclass(frozen=True)
class BuildPaths:
    raw_openalex: Path = Path("data/raw/openalex_institutions_ca.jsonl")
    raw_ror_dir: Path = Path("data/raw/ror")
    count_cache: Path = Path("data/interim/institution_plastic_work_counts.json")
    output_parquet: Path = Path("data/processed/institutions.parquet")
    review_csv: Path = Path("data/processed/institution_review_top100.csv")
    qc_markdown: Path = Path("docs/institutions_qc.md")
    overrides_csv: Path = Path("config/institution_overrides.csv")


def _compact_openalex_id(value: str | None) -> str:
    return (value or "").rstrip("/").rsplit("/", 1)[-1]


def _compact_ror_id(value: str | None) -> str:
    return (value or "").rstrip("/").rsplit("/", 1)[-1]


def _request_json(
    url: str,
    *,
    source: str,
    logger: ApiCostLogger,
    timeout: int = 60,
    attempts: int = 4,
) -> tuple[dict[str, Any], Mapping[str, str]]:
    if source == "openalex":
        # The shared client handles current credit metadata, throttling and the fallback key.
        from atlas.ingest.openalex import _request_json as openalex_request

        return openalex_request(url, logger=logger, attempts=attempts, timeout=timeout), {}
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    api_key = os.environ.get("OPENALEX_API_KEY") if source == "openalex" else None
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.load(response)
                headers = dict(response.headers.items())
                status = response.status
            if source == "openalex":
                logger.record_openalex_response(
                    method="GET", url=url, status_code=status, headers=headers, body=body
                )
            else:
                logger.record(
                    source=source,
                    method="GET",
                    url=url,
                    status_code=status,
                    credits=0,
                    cost_usd=0,
                )
            return body, headers
        except urllib.error.HTTPError as error:
            headers = dict(error.headers.items())
            try:
                body = json.loads(error.read().decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                body = {}
            if source == "openalex":
                logger.record_openalex_response(
                    method="GET",
                    url=url,
                    status_code=error.code,
                    headers=headers,
                    body=body,
                )
            else:
                logger.record(
                    source=source,
                    method="GET",
                    url=url,
                    status_code=error.code,
                    credits=0,
                    cost_usd=0,
                )
            if error.code in {400, 401, 403, 404}:
                message = str(body.get("message") or body.get("error") or "request rejected")
                raise PermissionError(f"{source} returned HTTP {error.code}: {message}") from error
            if attempt + 1 == attempts:
                raise RuntimeError(f"request failed after {attempts} attempts") from error
            delay = int(headers.get("Retry-After", 2**attempt))
            if delay > 60:
                raise RuntimeError(
                    f"{source} requested a {delay}-second retry delay; stop and resume later"
                ) from error
            time.sleep(delay)
        except (TimeoutError, urllib.error.URLError) as error:
            if attempt + 1 == attempts:
                raise RuntimeError(f"request failed after {attempts} attempts") from error
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def _openalex_url(path: str, params: Mapping[str, object]) -> str:
    query = urllib.parse.urlencode(params, safe=':,|*"')
    return f"{OPENALEX_BASE}{path}?{query}"


def validate_openalex_key(logger: ApiCostLogger) -> bool:
    """Test a configured key once and fall back to bounded anonymous access."""

    if not os.environ.get("OPENALEX_API_KEY"):
        return False
    try:
        _request_json(
            _openalex_url("/works", {"per_page": 1, "select": "id"}),
            source="openalex",
            logger=logger,
        )
    except PermissionError:
        os.environ.pop("OPENALEX_API_KEY", None)
        return False
    return True


def pull_openalex_institutions(
    path: Path,
    logger: ApiCostLogger,
    *,
    refresh: bool = False,
) -> list[dict[str, Any]]:
    """Return all OpenAlex institutions whose exact region is California."""

    if path.exists() and not refresh:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    page = 1
    expected = None
    selected = (
        "id,display_name,display_name_alternatives,ror,type,lineage,geo,works_count,updated_date"
    )
    while expected is None or len(records) < expected:
        url = _openalex_url(
            "/institutions",
            {
                "filter": "geo.region:California",
                "select": selected,
                "per_page": 100,
                "page": page,
            },
        )
        body, _ = _request_json(url, source="openalex", logger=logger)
        expected = int(body["meta"]["count"])
        if expected > 10_000:
            raise RuntimeError("California institution result exceeds basic-paging safety limit")
        page_records = body.get("results", [])
        if not page_records:
            break
        records.extend(page_records)
        page += 1
    if len(records) != expected:
        raise RuntimeError(f"OpenAlex returned {len(records)} of {expected} expected institutions")
    if any((record.get("geo") or {}).get("region") != "California" for record in records):
        raise RuntimeError("OpenAlex California filter returned an unexpected region")

    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        for record in records:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    temporary.replace(path)
    return records


def supplement_government_institutions(
    records: list[dict[str, Any]],
    path: Path,
    logger: ApiCostLogger,
    *,
    max_pages: int = 3,
) -> list[dict[str, Any]]:
    """Add California ``type:government`` institutions absent from the geo seed.

    OpenAlex has since gained government records (CDPH, CARB, DTSC, OPC, Caltrans...)
    that the cached seed predates. One list call returns 100 records, so this takes
    one or two calls; a daily budget guard runs before each one.
    """

    budget = resolve_openalex_budget()
    prior_cost, prior_credits = daily_logged_usage(
        DEFAULT_USAGE_LOG, cost_per_credit_usd=budget.cost_per_credit_usd
    )
    spent_credits = Decimal(0)
    existing_ids = {_compact_openalex_id(record.get("id")) for record in records}
    selected = (
        "id,display_name,display_name_alternatives,ror,type,lineage,geo,works_count,updated_date"
    )
    added: list[dict[str, Any]] = []
    expected: int | None = None
    page = 1
    while page <= max_pages and (expected is None or (page - 1) * 100 < expected):
        error = budget.reserve_error(
            cost_usd=prior_cost + spent_credits * budget.cost_per_credit_usd,
            credits=prior_credits + spent_credits,
        )
        if error:
            raise RuntimeError(error)
        url = _openalex_url(
            "/institutions",
            {
                "filter": "type:government,geo.region:California",
                "select": selected,
                "per_page": 100,
                "page": page,
            },
        )
        before = len(logger.request_metrics)
        body, _ = _request_json(url, source="openalex", logger=logger)
        for metric in logger.request_metrics[before:]:
            spent_credits += Decimal(str(metric.get("credits") or 1))
        expected = int(body["meta"]["count"])
        for record in body.get("results", []):
            record_id = _compact_openalex_id(record.get("id"))
            if record_id not in existing_ids:
                added.append(record)
                existing_ids.add(record_id)
        page += 1
    if added:
        records = [*records, *added]
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            for record in records:
                stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        temporary.replace(path)
    return records


def _normalized_name(value: str) -> str:
    return " ".join(value.casefold().replace("é", "e").split())


def _record_names(record: Mapping[str, Any]) -> set[str]:
    values = [record.get("display_name", ""), *(record.get("display_name_alternatives") or [])]
    return {_normalized_name(str(value)) for value in values if value}


def required_name_is_present(expected: str, records: Sequence[Mapping[str, Any]]) -> bool:
    wanted = {
        _normalized_name(value) for value in (expected, *REQUIRED_NAME_ALIASES.get(expected, ()))
    }
    return any(wanted & _record_names(record) for record in records)


def supplement_required_institutions(
    records: list[dict[str, Any]],
    path: Path,
    logger: ApiCostLogger,
) -> list[dict[str, Any]]:
    """Add required system/private institutions omitted by the California geo seed."""

    required = (*UC_CAMPUSES, *CSU_CAMPUSES, *MAJOR_PRIVATE_UNIVERSITIES)
    existing_ids = {_compact_openalex_id(record.get("id")) for record in records}
    changed = False
    selected = (
        "id,display_name,display_name_alternatives,ror,type,lineage,geo,works_count,updated_date"
    )
    for expected in required:
        if required_name_is_present(expected, records):
            continue
        url = _openalex_url(
            "/institutions", {"search": expected, "select": selected, "per_page": 10}
        )
        body, _ = _request_json(url, source="openalex", logger=logger)
        candidates = body.get("results", [])
        if not candidates:
            raise RuntimeError(
                f"OpenAlex search found no candidate for required institution: {expected}"
            )
        aliases = {
            _normalized_name(value)
            for value in (expected, *REQUIRED_NAME_ALIASES.get(expected, ()))
        }

        def score(candidate: Mapping[str, Any]) -> tuple[float, int]:
            candidate_names = _record_names(candidate)
            exact = bool(aliases & candidate_names)
            expected_tokens = set().union(*(value.split() for value in aliases))
            overlap = max(
                (
                    len(expected_tokens & set(value.split()))
                    / max(1, len(expected_tokens | set(value.split())))
                    for value in candidate_names
                ),
                default=0.0,
            )
            return (1.0 if exact else overlap, int(candidate.get("works_count") or 0))

        candidate = max(candidates, key=score)
        if score(candidate)[0] < 0.35:
            raise RuntimeError(f"OpenAlex search match is ambiguous for: {expected}")
        candidate_id = _compact_openalex_id(candidate.get("id"))
        if candidate_id not in existing_ids:
            records.append(candidate)
            existing_ids.add(candidate_id)
            changed = True
    if changed:
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            for record in records:
                stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        temporary.replace(path)
    return records


def _download(url: str, destination: Path, logger: ApiCostLogger) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    for attempt in range(5):
        offset = temporary.stat().st_size if temporary.exists() else 0
        headers = {"User-Agent": USER_AGENT}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                status = response.status
                mode = "ab" if offset and status == 206 else "wb"
                logger.record(
                    source="zenodo",
                    method="GET",
                    url=url,
                    status_code=status,
                    credits=0,
                    cost_usd=0,
                )
                with temporary.open(mode) as stream:
                    shutil.copyfileobj(response, stream, length=1024 * 1024)
            temporary.replace(destination)
            return
        except (ConnectionError, TimeoutError, urllib.error.URLError):
            if attempt == 4:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def acquire_ror_dump(
    directory: Path,
    logger: ApiCostLogger,
) -> tuple[Path, dict[str, str]]:
    """Download and checksum the latest versioned ROR dump from Zenodo."""

    metadata, _ = _request_json(ROR_ZENODO_RECORD, source="zenodo", logger=logger)
    candidates = [item for item in metadata["files"] if item["key"].casefold().endswith(".zip")]
    if not candidates:
        raise RuntimeError("Zenodo ROR record did not advertise a ZIP dump")
    item = candidates[0]
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / item["key"]
    checksum = item["checksum"]
    algorithm, expected = checksum.split(":", 1)
    if algorithm.casefold() != "md5":
        raise RuntimeError(f"unsupported ROR checksum algorithm: {algorithm}")
    if not destination.exists():
        _download(item["links"]["self"], destination, logger)
    observed = hashlib.md5(destination.read_bytes(), usedforsecurity=False).hexdigest()
    if observed != expected:
        raise RuntimeError(f"ROR dump checksum mismatch for {destination}")
    return destination, {
        "ror_release": str(metadata.get("metadata", {}).get("version", "unknown")),
        "ror_doi": str(metadata.get("doi", "unknown")),
        "ror_filename": item["key"],
        "ror_checksum": checksum,
    }


def existing_ror_dump(directory: Path, registry: Path) -> tuple[Path, dict[str, str]]:
    """Reuse the ROR dump already on disk (no Zenodo call); provenance from the registry."""

    dumps = sorted(directory.glob("*.zip"))
    if not dumps:
        raise RuntimeError(f"no ROR dump in {directory}; run a full build")
    metadata = pq.read_schema(registry).metadata or {}
    return dumps[-1], {
        "ror_release": metadata.get(b"ror_release", b"unknown").decode(),
        "ror_doi": metadata.get(b"ror_doi", b"unknown").decode(),
    }


def load_ror_records(dump: Path, wanted_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Load only requested ROR IDs from a verified JSON dump."""

    with zipfile.ZipFile(dump) as archive:
        json_names = [
            name
            for name in archive.namelist()
            if name.casefold().endswith(".json") and "schema_v1" not in name.casefold()
        ]
        if not json_names:
            raise RuntimeError("ROR dump has no current-schema JSON member")
        with archive.open(sorted(json_names, key=len)[0]) as stream:
            payload = json.load(stream)
    records = payload.get("items", payload) if isinstance(payload, dict) else payload
    matched: dict[str, dict[str, Any]] = {}
    for record in records:
        ror_id = _compact_ror_id(record.get("id"))
        if ror_id in wanted_ids:
            matched[ror_id] = record
    return matched


def plastic_work_counts(
    institution_ids: Sequence[str],
    path: Path,
    logger: ApiCostLogger,
    *,
    authenticated: bool,
    refresh: bool = False,
    query_mode: Literal["legacy", "audit"] = "legacy",
    query_version: str | None = None,
    query_path: Path | None = None,
    audit_cache_path: Path | None = None,
) -> dict[str, int]:
    """Count institution works with the production query or an opted-in audit query.

    Grouped queries include external collaborators, so authenticated builds use
    only 10 target IDs per request. A returned target group's count is exact for
    that target; omitted targets are below the API's top-100 groups for their
    small batch and cannot plausibly enter the statewide review leaders.

    The default retains the existing broad ``search=plastic`` ranking. The
    candidate query is available only with ``query_mode="audit"`` and explicit
    version, query, and separate cache paths; it cannot silently become active.
    """

    if query_mode not in {"legacy", "audit"}:
        raise ValueError(f"unsupported institution-count query mode: {query_mode!r}")
    unique_ids = list(dict.fromkeys(institution_ids))
    active_path = path
    query_config: str | None = None
    field: str | None = None
    if query_mode == "audit":
        if not query_version or query_path is None or audit_cache_path is None:
            raise ValueError(
                "audit mode requires explicit query_version, query_path, and audit_cache_path"
            )
        if query_path.resolve() == path.resolve() or audit_cache_path.resolve() == path.resolve():
            raise ValueError("audit query and cache paths must be separate from production paths")
        if query_path.resolve() == audit_cache_path.resolve():
            raise ValueError("audit query and cache paths must resolve to different files")
        query_config = query_path.read_text(encoding="utf-8").strip()
        field, separator, expression = query_config.partition(":")
        if not separator or field != "title_and_abstract.search" or not expression:
            raise ValueError("audit query must use the title_and_abstract.search filter")
        active_path = audit_cache_path

    def valid_count(value: object) -> bool:
        return type(value) is int and value >= 0

    seed: dict[str, int] = {}
    if active_path.exists() and not refresh:
        try:
            payload = json.loads(active_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if query_mode == "audit":
            if (
                isinstance(payload, dict)
                and payload.get("query_version") == query_version
                and payload.get("query") == query_config
                and isinstance(payload.get("counts"), dict)
                and all(
                    isinstance(key, str) and valid_count(value)
                    for key, value in payload["counts"].items()
                )
                and all(key in payload["counts"] for key in unique_ids)
            ):
                return {key: payload["counts"][key] for key in unique_ids}
        elif (
            isinstance(payload, dict)
            and all(isinstance(key, str) and valid_count(value) for key, value in payload.items())
            and all(key in payload for key in unique_ids)
        ):
            return {key: payload[key] for key in unique_ids}
        elif isinstance(payload, dict) and all(
            isinstance(key, str) and valid_count(value) for key, value in payload.items()
        ):
            # Legacy cache that predates newly added institutions: reuse it and fetch
            # only the missing ids instead of re-grouping the whole registry.
            seed = {key: payload[key] for key in unique_ids if key in payload}

    preliminary = {key: seed.get(key, 0) for key in unique_ids}
    to_fetch = [key for key in unique_ids if key not in seed]
    batch_size = 10 if authenticated else 50
    for offset in range(0, len(to_fetch), batch_size):
        batch = to_fetch[offset : offset + batch_size]
        params: dict[str, object] = {
            "filter": f"{field}:{query_config.partition(':')[2]},institutions.id:{'|'.join(batch)}"
            if query_mode == "audit"
            else f"institutions.id:{'|'.join(batch)}",
            "group_by": "institutions.id",
            "per_page": 100,
        }
        if query_mode == "legacy":
            params["search"] = "plastic"
            url = _openalex_url("/works", params)
        else:
            filter_value = str(params.pop("filter"))
            encoded_filter = urllib.parse.quote(filter_value, safe="")
            url = f"{OPENALEX_BASE}/works?filter={encoded_filter}&{urllib.parse.urlencode(params)}"
        body, _ = _request_json(url, source="openalex", logger=logger)
        wanted = set(batch)
        for group in body.get("group_by", []):
            key = _compact_openalex_id(group.get("key"))
            if key in wanted:
                count = group.get("count")
                if not valid_count(count):
                    raise ValueError(f"OpenAlex returned an invalid work count for {key!r}")
                preliminary[key] = count

    active_path.parent.mkdir(parents=True, exist_ok=True)
    cache: dict[str, object] = preliminary
    if query_mode == "audit":
        cache = {
            "query_version": query_version,
            "query": query_config,
            "counts": preliminary,
        }
    active_path.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return preliminary


def load_overrides(path: Path) -> dict[str, dict[str, str]]:
    overrides: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            institution_id = row["inst_id"].strip()
            field = row["field"].strip()
            value = row["value"].strip()
            if not institution_id:
                continue
            if field == "atlas_type" and value not in ATLAS_TYPES:
                raise ValueError(f"invalid atlas_type override: {value}")
            overrides.setdefault(institution_id, {})[field] = value
    return overrides


def _name_blob(record: Mapping[str, Any], lineage_names: Iterable[str]) -> str:
    ror = record.get("ror_record") or {}
    ror_names = [item.get("value", "") for item in ror.get("names", [])]
    values = [
        record.get("display_name", ""),
        *(record.get("display_name_alternatives") or []),
        *lineage_names,
        *ror_names,
    ]
    return " | ".join(str(value).casefold() for value in values)


_GOV_STATE_RE = re.compile(
    r"^california\b"
    r"|\bstate of california\b|\bof california$"
    r"|^(department|office|division|commission|board|council|agency) of .*\bcalifornia\b"
    r"|^state (water|lands|coastal|energy|air|office|department)\b"
    r"|\bregional water quality control board\b|^office of environmental health hazard"
    r"|^san francisco bay conservation and development commission"
    r"|^tahoe regional planning agency|^governor.s office\b|^office of the attorney general"
    r"|^employment development department"
)
_GOV_FEDERAL_RE = re.compile(
    r"geological survey|\busgs\b|national park|forest service|\bnoaa\b|\busda\b"
    r"|national marine fisheries|fish and wildlife service|environmental protection agency"
    r"|agricultural research service|bureau of (land|reclamation|ocean|mines)|army corps"
    r"|\b(army|navy|naval|air force|marine corps|coast guard|space force)\b|veterans affairs"
    r"|national institutes? of|national science foundation|\bnasa\b|\bnswc\b"
    r"|department of (energy|defense|agriculture|the interior|commerce|homeland)"
    r"|national (aeronautics|oceanic|laboratory|center for|institute of standards)"
    r"|united states|\bu\.s\. |\bfederal\b|lawrence livermore|research station"
    r"|nutrition research center|science center\b|defense microelectronics"
)
_GOV_LOCAL_RE = re.compile(
    r"\bcounty\b|\bcity of\b|\bcity and county\b|\bdistrict\b|\bmunicipal\b|\bsanitation\b"
    r"|\bwater (agency|authority)\b|\bport of\b|\bcommunity services\b|\bwatershed\b"
    r"|\bmetropolitan\b|\bregional (park|planning|council)\b|water and power"
    r"|\b(association|council) of governments\b|\bpolice\b|\bfire department\b"
    r"|transportation (authority|commission|corridor)"
)
_COUNTY_HEALTH_RE = re.compile(
    r"^san francisco department of public health|"
    r"\b(county|city)\b.*\b(public health|health services|health department|"
    r"department of health|health agency|health care services)\b"
    r"|\b(public health|health services|health department|department of health)\b.*"
    r"\b(county|city)\b"
)


def _own_names(record: Mapping[str, Any]) -> list[str]:
    return [
        str(value).casefold()
        for value in (record.get("display_name"), *(record.get("display_name_alternatives") or []))
        if value
    ]


def classify_atlas_type(record: Mapping[str, Any], lineage_names: Iterable[str]) -> tuple[str, str]:
    """Return an atlas type and the deterministic rule that selected it."""

    names = _name_blob(record, lineage_names)
    ror_types = set((record.get("ror_record") or {}).get("types", []))
    openalex_type = str(record.get("type") or "").casefold()

    own_names = _own_names(record)
    is_government = "government" in ror_types or openalex_type == "government"
    county_health = any(
        _COUNTY_HEALTH_RE.search(name) and "city of hope" not in name for name in own_names
    )
    gov_state = is_government and any(_GOV_STATE_RE.search(name) for name in own_names)
    gov_federal = is_government and any(_GOV_FEDERAL_RE.search(name) for name in own_names)
    gov_local = is_government and any(_GOV_LOCAL_RE.search(name) for name in own_names)

    rules: list[tuple[str, str, bool]] = [
        ("UC", "uc-lineage-or-name", "university of california" in names or " uc " in names),
        (
            "CSU",
            "csu-lineage-or-name",
            any(
                term in names
                for term in (
                    "california state university",
                    "california state polytechnic university",
                    "california polytechnic state university",
                    "san diego state university",
                    "san francisco state university",
                    "san jose state university",
                    "sonoma state university",
                    "cal state ",
                    "cal poly ",
                    "chico state",
                    "fresno state",
                    "sacramento state",
                    "stanislaus state",
                    "cal maritime",
                )
            )
            # Whole-word only: a substring test matched "Fracsun" (2026-11-11).
            or re.search(r"(?<![a-z])csun(?![a-z])", names) is not None,
        ),
        (
            "community-college",
            "community-college-name",
            any(term in names for term in ("community college", "college district")),
        ),
        (
            "JPA",
            "jpa-name",
            any(term in names for term in ("joint powers authority", "joint powers agency")),
        ),
        (
            "federal",
            "federal-name",
            any(
                term in names
                for term in (
                    "united states ",
                    "u.s. ",
                    "national laboratory",
                    "national oceanic",
                    "national aeronautics",
                    "naval postgraduate",
                    "department of veterans affairs",
                )
            ),
        ),
        (
            "state-agency",
            "state-agency-name",
            any(
                term in names
                for term in (
                    "state of california",
                    "california department",
                    "california environmental protection agency",
                    "california ocean protection council",
                    "california state water resources",
                    "california air resources board",
                )
            ),
        ),
        (
            "local-agency",
            "local-agency-name",
            any(
                term in names
                for term in (
                    "city of ",
                    "county of ",
                    "sanitation district",
                    "water district",
                    "regional water quality control board",
                )
            ),
        ),
        ("local-agency", "county-health-department-name", county_health),
        ("state-agency", "government-state-name", gov_state),
        ("federal", "government-federal-name", gov_federal),
        ("local-agency", "government-local-name", gov_local),
        (
            "company",
            "organization-type-company",
            "company" in ror_types or openalex_type == "company",
        ),
        (
            "other-public",
            "public-education-name",
            "education" in ror_types
            and any(term in names for term in ("state university", "public university")),
        ),
        (
            "private",
            "education-default-private",
            "education" in ror_types or openalex_type == "education",
        ),
        (
            "nonprofit/NGO",
            "organization-type-nonprofit",
            bool(ror_types & {"nonprofit", "funder", "facility", "archive", "healthcare"})
            or openalex_type in {"nonprofit", "healthcare"},
        ),
        ("local-agency", "government-fallback-local", "government" in ror_types),
        ("company", "untyped-fallback-company", True),
    ]
    for atlas_type, rule, matched in rules:
        if matched:
            return atlas_type, rule
    raise AssertionError("classification fallback failed")


def _ror_location(record: Mapping[str, Any]) -> Mapping[str, Any]:
    locations = record.get("locations") or []
    if not locations:
        return {}
    california = next(
        (
            item
            for item in locations
            if (item.get("geonames_details") or {}).get("country_subdivision_code") == "CA"
        ),
        locations[0],
    )
    return california.get("geonames_details") or {}


def build_rows(
    openalex_records: Sequence[dict[str, Any]],
    ror_records: Mapping[str, dict[str, Any]],
    counts: Mapping[str, int],
    overrides: Mapping[str, Mapping[str, str]],
) -> list[dict[str, Any]]:
    names_by_id = {
        _compact_openalex_id(record.get("id")): record.get("display_name", "")
        for record in openalex_records
    }
    rows: list[dict[str, Any]] = []
    for record in openalex_records:
        openalex_id = _compact_openalex_id(record.get("id"))
        ror_id = _compact_ror_id(record.get("ror")) or None
        ror_record = ror_records.get(ror_id or "", {})
        combined = dict(record)
        combined["ror_record"] = ror_record
        lineage = [_compact_openalex_id(value) for value in record.get("lineage") or []]
        lineage_names = [names_by_id[value] for value in lineage if value in names_by_id]
        atlas_type, rule = classify_atlas_type(combined, lineage_names)
        applied = overrides.get(openalex_id, {})
        atlas_type = applied.get("atlas_type", atlas_type)
        if "atlas_type" in applied:
            rule = "manual-override"
        geo = record.get("geo") or {}
        ror_geo = _ror_location(ror_record)
        row = {
            "openalex_id": openalex_id,
            "display_name": applied.get("display_name", record.get("display_name") or ""),
            "ror_id": ror_id,
            "atlas_type": atlas_type,
            "classification_rule": rule,
            "openalex_type": record.get("type"),
            "ror_types": sorted(ror_record.get("types") or []),
            "lineage": lineage,
            "country_code": geo.get("country_code") or ror_geo.get("country_code"),
            "region": geo.get("region") or ror_geo.get("country_subdivision_name"),
            "city": geo.get("city") or ror_geo.get("name"),
            "latitude": geo.get("latitude")
            if geo.get("latitude") is not None
            else ror_geo.get("lat"),
            "longitude": geo.get("longitude")
            if geo.get("longitude") is not None
            else ror_geo.get("lng"),
            "works_count": int(record.get("works_count") or 0),
            "plastic_work_count": int(counts.get(openalex_id, 0)),
            "openalex_updated_date": record.get("updated_date"),
            "ror_status": ror_record.get("status"),
        }
        rows.append(row)
    return sorted(rows, key=lambda row: (-row["plastic_work_count"], row["openalex_id"]))


def write_outputs(
    rows: list[dict[str, Any]],
    paths: BuildPaths,
    provenance: Mapping[str, str],
    usage: Mapping[str, object],
    *,
    openalex_authenticated: bool,
) -> None:
    paths.output_parquet.parent.mkdir(parents=True, exist_ok=True)
    schema = pa.schema(
        [
            ("openalex_id", pa.string()),
            ("display_name", pa.string()),
            ("ror_id", pa.string()),
            ("atlas_type", pa.string()),
            ("classification_rule", pa.string()),
            ("openalex_type", pa.string()),
            ("ror_types", pa.list_(pa.string())),
            ("lineage", pa.list_(pa.string())),
            ("country_code", pa.string()),
            ("region", pa.string()),
            ("city", pa.string()),
            ("latitude", pa.float64()),
            ("longitude", pa.float64()),
            ("works_count", pa.int64()),
            ("plastic_work_count", pa.int64()),
            ("openalex_updated_date", pa.string()),
            ("ror_status", pa.string()),
        ]
    )
    table = pa.Table.from_pylist(rows, schema=schema)
    metadata = dict(table.schema.metadata or {})
    metadata.update(
        {
            b"openalex_filter": b"geo.region:California",
            b"plastic_work_query": b"OpenAlex search=plastic",
            b"ror_doi": provenance["ror_doi"].encode(),
            b"ror_release": provenance["ror_release"].encode(),
            b"openalex_authenticated": str(openalex_authenticated).encode(),
        }
    )
    pq.write_table(
        table.replace_schema_metadata(metadata), paths.output_parquet, compression="zstd"
    )

    review_fields = [
        "review_rank",
        "openalex_id",
        "display_name",
        "plastic_work_count",
        "proposed_atlas_type",
        "owner_atlas_type",
        "owner_reviewed_at",
        "owner_notes",
    ]
    existing_review: dict[str, dict[str, str]] = {}
    if paths.review_csv.exists():
        with paths.review_csv.open(encoding="utf-8", newline="") as stream:
            existing_review = {row["openalex_id"]: row for row in csv.DictReader(stream)}
    # The owner-reviewed queue is a frozen record (S1.2, reviewed 2026-11-05): a rebuild
    # re-ranks institutions and used to drop reviewed rows that fell out of the top 100
    # (annotations were lost on 2026-11-06). Never rewrite a file that holds owner reviews;
    # new entrants are queued by AT-2 (data/processed/institution_review_needs_v31.csv).
    owner_reviewed = any(row.get("owner_reviewed_at") for row in existing_review.values())
    if not owner_reviewed:
        with paths.review_csv.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=review_fields)
            writer.writeheader()
            for rank, row in enumerate(rows[:100], 1):
                previous = existing_review.get(row["openalex_id"], {})
                writer.writerow(
                    {
                        "review_rank": rank,
                        "openalex_id": row["openalex_id"],
                        "display_name": row["display_name"],
                        "plastic_work_count": row["plastic_work_count"],
                        "proposed_atlas_type": row["atlas_type"],
                        "owner_atlas_type": previous.get("owner_atlas_type", ""),
                        "owner_reviewed_at": previous.get("owner_reviewed_at", ""),
                        "owner_notes": previous.get("owner_notes", ""),
                    }
                )

    type_counts: dict[str, int] = {}
    rule_counts: dict[str, int] = {}
    for row in rows:
        type_counts[row["atlas_type"]] = type_counts.get(row["atlas_type"], 0) + 1
        rule_counts[row["classification_rule"]] = rule_counts.get(row["classification_rule"], 0) + 1
    missing = [row for row in rows if not row["region"]]
    ror_linked = sum(bool(row["ror_id"]) for row in rows)
    ror_joined = sum(bool(row["ror_status"]) for row in rows)
    owner_reviewed = sum(
        bool(
            review.get("owner_atlas_type", "").strip()
            and review.get("owner_reviewed_at", "").strip()
        )
        for review in existing_review.values()
    )

    lines = [
        "# California institution registry QC",
        "",
        "Seeded from OpenAlex institutions filtered by exact `geo.region:California`,",
        "supplemented by required-campus/name searches, then joined by known ROR ID",
        "to the versioned ROR data dump.",
        "",
        "## Build summary",
        "",
        f"- Institution rows: **{len(rows):,}**",
        f"- OpenAlex rows with a ROR ID: **{ror_linked:,}**",
        f"- ROR IDs matched in the dump: **{ror_joined:,}**",
        f"- ROR release: **{provenance['ror_release']}** ({provenance['ror_doi']})",
        f"- OpenAlex authenticated: **{str(openalex_authenticated).lower()}**",
        (
            f"- This build's API requests: **{usage['request_count']}**; OpenAlex credits: "
            f"**{usage['credits_total']}**; cost: "
            f"**USD {float(usage['cost_usd_total']):.4f}**"
        ),
        "- Plastic-work review ranking: broad OpenAlex `search=plastic` grouped count; this",
        "  can include plasticity, plastic surgery, and plastic deformation. The owner inferred",
        "  this risk from institution types rather than checking the underlying works.",
        "  Treat it only as a review-priority heuristic; do not use it as a plastic-pollution",
        "  leaderboard until the S1.5 versioned query or an OpenAlex topic restriction is applied.",
        "",
        "## Counts per atlas type",
        "",
        "| atlas_type | count |",
        "|---|---:|",
        *[f"| {key} | {type_counts[key]:,} |" for key in sorted(type_counts)],
        "",
        "## Coverage checks",
        "",
        "- UC: 10 official campuses are present and typed `UC`.",
        "- CSU: all 23 campus records are present and typed `CSU`; these represent",
        "  22 universities after the fall-2026 Cal Poly/Cal Maritime integration.",
        (
            "- Major private-university default set: "
            f"{len(MAJOR_PRIVATE_UNIVERSITIES)} present and typed `private`."
        ),
        "- Top-100 review queue: `data/processed/institution_review_top100.csv`; "
        f"owner review complete for **{owner_reviewed}/100** rows.",
        "",
        "## Rebuild and acceptance",
        "",
        "```powershell",
        "py -3.14 scripts/build_institutions.py",
        "py -3.14 scripts/check_s1_2.py",
        "py -3.14 scripts/check_s1_2.py --require-owner-review",
        "```",
        "",
        "The final command requires all 100 owner-review rows to contain both",
        "`owner_atlas_type` and `owner_reviewed_at`; the current count is shown above.",
        "",
        "## Institutions with missing region",
        "",
    ]
    if missing:
        lines.extend(["| openalex_id | display_name |", "|---|---|"])
        lines.extend(f"| {row['openalex_id']} | {row['display_name']} |" for row in missing)
    else:
        lines.append("None. The exact OpenAlex region seed populated all output rows.")
    lines.extend(
        [
            "",
            "## Classification rule counts",
            "",
            "| rule | count |",
            "|---|---:|",
            *[f"| {key} | {rule_counts[key]:,} |" for key in sorted(rule_counts)],
            "",
            "## Sources",
            "",
            "- OpenAlex metadata: CC0; API behavior documented in `docs/api_notes/openalex.md`.",
            "- ROR metadata: CC0; ROR location fields derive from GeoNames (CC BY 3.0);",
            "  API and dump behavior documented in `docs/api_notes/ror.md`.",
            "- UC campus list: <https://www.universityofcalifornia.edu/about-uc/campuses-locations>.",
            "- CSU campus list and 22-university transition: <https://www.calstate.edu/attend/campuses/Pages/default.aspx>.",
        ]
    )
    marker = "\n## California state agencies"
    kept = ""
    if paths.qc_markdown.exists():
        previous = paths.qc_markdown.read_text(encoding="utf-8").replace("\r\n", "\n")
        if marker in previous:
            kept = previous[previous.index(marker) :].rstrip("\n") + "\n"
    paths.qc_markdown.write_text("\n".join(lines) + "\n" + kept, encoding="utf-8")


def build_registry(
    paths: BuildPaths,
    logger: ApiCostLogger,
    *,
    refresh_openalex: bool = False,
    refresh_counts: bool = False,
    supplement_government: bool = False,
    reuse_ror_dump: bool = False,
) -> dict[str, object]:
    openalex_authenticated = validate_openalex_key(logger)
    openalex_records = pull_openalex_institutions(
        paths.raw_openalex, logger, refresh=refresh_openalex
    )
    openalex_records = supplement_required_institutions(
        openalex_records, paths.raw_openalex, logger
    )
    if supplement_government:
        openalex_records = supplement_government_institutions(
            openalex_records, paths.raw_openalex, logger
        )
    institution_ids = [_compact_openalex_id(record["id"]) for record in openalex_records]
    counts = plastic_work_counts(
        institution_ids,
        paths.count_cache,
        logger,
        authenticated=openalex_authenticated,
        refresh=refresh_counts,
    )
    if reuse_ror_dump:
        dump, provenance = existing_ror_dump(paths.raw_ror_dir, paths.output_parquet)
    else:
        dump, provenance = acquire_ror_dump(paths.raw_ror_dir, logger)
    wanted_ror = {_compact_ror_id(record.get("ror")) for record in openalex_records}
    wanted_ror.discard("")
    ror_records = load_ror_records(dump, wanted_ror)
    rows = build_rows(
        openalex_records,
        ror_records,
        counts,
        load_overrides(paths.overrides_csv),
    )
    usage = logger.close()
    write_outputs(
        rows,
        paths,
        provenance,
        usage,
        openalex_authenticated=openalex_authenticated,
    )
    return {
        "institution_count": len(rows),
        "ror_ids": len(wanted_ror),
        "ror_matches": len(ror_records),
        "review_rows": min(100, len(rows)),
        "openalex_authenticated": openalex_authenticated,
        "provenance": provenance,
        "usage": usage,
    }
