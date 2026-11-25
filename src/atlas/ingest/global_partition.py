"""Local partition of the PLAT-4a global raw store (PLAT-4b slice 1, unpublished).

Reads the gzip JSONL pages written by ``atlas.ingest.global_raw`` (line 1 a ``page_header``,
then one unmodified OpenAlex work per line) and writes two ignored Parquet tables:

- ``works.parquet``: one row per OpenAlex work (latest page wins), every row labelled
  ``screening_status = "unscreened_query_hit"``, with ``pmid`` compacted from ``ids.pmid``.
- ``work_regions.parquet``: one row per (work, region). Region kinds are ``country``
  (ISO alpha-2), ``subdivision`` (ISO ``CC-SUB`` form, only when the record carries a
  subdivision code) and ``registry_region`` (slug of each registry region whose predicate
  matches). Assigning a work to every region it touches is a local join; nothing is fetched.
  A registry region also matches when an authorship institution id is in the region's
  institution registry (``registry_institution``, PLAT-4b slice 2).

Region names are never written here: predicates come from ``regions/_registry.yml`` through
``atlas.regions.scope``. The strict raw-affiliation rule for the default region is the
engine's existing ``normalize.matches_california_affiliation``, because no scope helper can
express it (see ``docs/api_notes/global_partition.md``).
"""

from __future__ import annotations

import gzip
import json
import os
import re
import tempfile
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from atlas.ingest.normalize import matches_california_affiliation
from atlas.regions import scope
from atlas.regions.registry import Region, load_registry

DEFAULT_RAW_DIR = Path("data/raw/openalex_global")
DEFAULT_OUT_DIR = Path("data/processed/global")
WORKS_FILE = "works.parquet"
WORK_REGIONS_FILE = "work_regions.parquet"

SCREENING_UNSCREENED = "unscreened_query_hit"
REGION_KINDS = ("country", "subdivision", "registry_region")
BASES = (
    "institution_country",
    "author_country",
    "raw_affiliation",
    "registry_predicate",
    "registry_institution",
)
# Strongest evidence first; the first basis that applies to a (work, region) pair wins.
BASIS_PREFERENCE = (
    "institution_country",
    "registry_institution",
    "registry_predicate",
    "author_country",
    "raw_affiliation",
)
OPENALEX_PREFIX = "https://openalex.org/"

WORKS_SCHEMA = pa.schema(
    [
        ("work_id", pa.string()),
        ("doi", pa.string()),
        ("pmid", pa.string()),
        ("title", pa.string()),
        ("publication_year", pa.int32()),
        ("publication_date", pa.string()),
        ("type", pa.string()),
        ("language", pa.string()),
        ("primary_topic_id", pa.string()),
        ("is_retracted", pa.bool_()),
        ("cited_by_count", pa.int64()),
        ("screening_status", pa.string()),
        ("query_version", pa.string()),
        ("query_hash", pa.string()),
    ]
)
WORK_REGIONS_SCHEMA = pa.schema(
    [
        ("work_id", pa.string()),
        ("region_kind", pa.string()),
        ("region_code", pa.string()),
        ("basis", pa.string()),
    ]
)

_PMID_TAIL = re.compile(r"(\d+)$")
_RAW_BOUNDARY = r"(?<![A-Za-z]){}(?![A-Za-z])"


class NoRawStoreError(RuntimeError):
    """The raw pages directory is absent or holds no page files."""


@dataclass(frozen=True)
class PartitionResult:
    works: int
    work_regions: int
    skipped_records: int
    works_path: Path
    work_regions_path: Path


def raw_page_paths(raw_dir: str | Path) -> list[Path]:
    """Page files in ``<raw_dir>/pages``, sorted by name (not the archived restart folders)."""
    pages = Path(raw_dir) / "pages"
    if not pages.is_dir():
        return []
    return sorted(pages.glob("*.jsonl.gz"))


def _read_header(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        first = handle.readline()
    header = json.loads(first)
    if not isinstance(header, dict) or header.get("record_type") != "page_header":
        raise ValueError(f"{path}: first line is not a page_header record")
    return header


def _read_works(path: Path) -> Iterable[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        handle.readline()
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _short_id(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.startswith(OPENALEX_PREFIX):
        text = text[len(OPENALEX_PREFIX) :]
    return text or None


def compact_pmid(value: object) -> str | None:
    """``"https://pubmed.ncbi.nlm.nih.gov/123"`` -> ``"123"``; anything without digits -> None."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return str(value) if value > 0 else None
    if not isinstance(value, str):
        return None
    match = _PMID_TAIL.search(value.strip().rstrip("/"))
    return match.group(1) if match else None


def _country(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    code = value.strip().upper()
    return code if len(code) == 2 and code.isalpha() else None


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def work_row(work: Mapping[str, Any], header: Mapping[str, Any]) -> dict[str, Any] | None:
    """One ``works.parquet`` row, or None when the record has no OpenAlex id."""
    work_id = _short_id(work.get("id"))
    if work_id is None:
        return None
    ids = work.get("ids") or {}
    primary_topic = work.get("primary_topic") or {}
    year = work.get("publication_year")
    cited = work.get("cited_by_count")
    return {
        "work_id": work_id,
        "doi": _text(work.get("doi")) or _text(ids.get("doi")),
        "pmid": compact_pmid(ids.get("pmid")),
        "title": _text(work.get("title")) or _text(work.get("display_name")),
        "publication_year": int(year) if isinstance(year, int) else None,
        "publication_date": _text(work.get("publication_date")),
        "type": _text(work.get("type")),
        "language": _text(work.get("language")),
        "primary_topic_id": _short_id(primary_topic.get("id")),
        "is_retracted": bool(work.get("is_retracted")),
        "cited_by_count": int(cited) if isinstance(cited, int) else None,
        "screening_status": SCREENING_UNSCREENED,
        "query_version": str(header.get("query_version") or ""),
        "query_hash": str(header.get("query_hash") or ""),
    }


def _raw_affiliation_strings(authorship: Mapping[str, Any]) -> list[str]:
    values = list(authorship.get("raw_affiliation_strings") or [])
    for affiliation in authorship.get("affiliations") or []:
        if isinstance(affiliation, Mapping):
            values.append(affiliation.get("raw_affiliation_string"))
    return [value for value in values if isinstance(value, str) and value.strip()]


def _raw_affiliation_hit(region: Region, text: str) -> bool:
    """Strict rule for the default region (mirrors normalize); word-bounded terms otherwise."""
    if region.slug == scope.DEFAULT_REGION_SLUG:
        return matches_california_affiliation(text)
    terms = region.predicate.raw_affiliation_terms if region.predicate else ()
    return any(re.search(_RAW_BOUNDARY.format(re.escape(t)), text, re.IGNORECASE) for t in terms)


def _institution_hit(region: Region, institution: Mapping[str, Any], country: str | None) -> bool:
    predicate = region.predicate
    if predicate is None:
        return False
    allowed = {"", *(code.upper() for code in predicate.country_codes)}
    if (country or "") not in allowed:
        return False
    geo = institution.get("geo") or {}
    region_name = _text(geo.get("region"))
    if region_name and region_name.casefold() in {
        name.casefold() for name in predicate.institution_region_names
    }:
        return True
    subdivision = _text(geo.get("country_subdivision_code"))
    return bool(subdivision) and subdivision.upper() in {
        code.upper() for code in predicate.ror_subdivision_codes
    }


def work_region_bases(
    work: Mapping[str, Any],
    regions: Sequence[Region],
    institution_ids: Mapping[str, frozenset[str]] | None = None,
) -> dict[tuple[str, str], str]:
    """``{(region_kind, region_code): basis}`` for one work; strongest basis per pair.

    ``institution_ids`` maps a region slug to its registry institution ids (loaded once per run).
    """
    found: dict[tuple[str, str], str] = {}

    def offer(kind: str, code: str, basis: str) -> None:
        current = found.get((kind, code))
        if current is None or BASIS_PREFERENCE.index(basis) < BASIS_PREFERENCE.index(current):
            found[(kind, code)] = basis

    authorships = [a for a in work.get("authorships") or [] if isinstance(a, Mapping)]
    institutions: list[tuple[Mapping[str, Any], str | None]] = []
    work_institution_ids: set[str] = set()
    for authorship in authorships:
        for institution in authorship.get("institutions") or []:
            if not isinstance(institution, Mapping):
                continue
            country = _country(institution.get("country_code"))
            institutions.append((institution, country))
            inst_id = _short_id(institution.get("id"))
            if inst_id:
                work_institution_ids.add(inst_id)
            if country:
                offer("country", country, "institution_country")
                geo = institution.get("geo") or {}
                subdivision = _text(geo.get("country_subdivision_code"))
                if subdivision:
                    code = subdivision.upper()
                    if "-" not in code:
                        code = f"{country}-{code}"
                    offer("subdivision", code, "institution_country")
        for code in authorship.get("countries") or []:
            country = _country(code)
            if country:
                offer("country", country, "author_country")

    raw_texts = [
        text for authorship in authorships for text in _raw_affiliation_strings(authorship)
    ]
    for region in regions:
        if region.predicate is None:
            continue
        registry_ids = (institution_ids or {}).get(region.slug, frozenset())
        if work_institution_ids & registry_ids:
            offer("registry_region", region.slug, "registry_institution")
        if any(_institution_hit(region, inst, country) for inst, country in institutions):
            offer("registry_region", region.slug, "registry_predicate")
        if any(_raw_affiliation_hit(region, text) for text in raw_texts):
            offer("registry_region", region.slug, "raw_affiliation")
    return found


def _atomic_write_parquet(table: pa.Table, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-", suffix=".tmp")
    os.close(handle)
    try:
        pq.write_table(table, tmp_name, compression="zstd")
        os.replace(tmp_name, path)
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def build_partition(
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    out_dir: str | Path = DEFAULT_OUT_DIR,
    regions: Sequence[Region] | None = None,
) -> PartitionResult:
    """Stream every raw page and write both tables atomically. Latest page wins per work."""
    pages = raw_page_paths(raw_dir)
    if not pages:
        raise NoRawStoreError(f"no raw pages under {Path(raw_dir) / 'pages'}")
    headers = sorted(
        ((_read_header(path), path) for path in pages),
        key=lambda item: (str(item[0].get("fetched_utc") or ""), item[1].name),
    )
    query_identities = {
        (str(header.get("query_version")), str(header.get("query_hash"))) for header, _ in headers
    }
    if len(query_identities) != 1:
        raise ValueError(f"raw pages mix query identities: {sorted(query_identities)}")

    if regions is None:
        regions = load_registry(scope.REGISTRY_PATH).regions
    # Registry institution ids are read once per run, not once per work.
    institution_ids = {
        region.slug: scope.region_institution_ids(region)
        for region in regions
        if region.predicate is not None and region.predicate.institution_registry
    }
    rows: dict[str, dict[str, Any]] = {}
    bases: dict[str, dict[tuple[str, str], str]] = {}
    skipped = 0
    for header, path in headers:
        for work in _read_works(path):
            row = work_row(work, header)
            if row is None:
                skipped += 1
                continue
            rows[row["work_id"]] = row
            bases[row["work_id"]] = work_region_bases(work, regions, institution_ids)

    works = [rows[key] for key in sorted(rows)]
    region_rows = [
        {"work_id": work_id, "region_kind": kind, "region_code": code, "basis": basis}
        for work_id in sorted(bases)
        for (kind, code), basis in sorted(bases[work_id].items())
    ]
    out = Path(out_dir)
    works_path = out / WORKS_FILE
    regions_path = out / WORK_REGIONS_FILE
    _atomic_write_parquet(pa.Table.from_pylist(works, schema=WORKS_SCHEMA), works_path)
    _atomic_write_parquet(
        pa.Table.from_pylist(region_rows, schema=WORK_REGIONS_SCHEMA), regions_path
    )
    return PartitionResult(len(works), len(region_rows), skipped, works_path, regions_path)


def check_outputs(out_dir: str | Path = DEFAULT_OUT_DIR) -> list[str]:
    """Schema, uniqueness, label and referential problems in the two tables (empty = pass)."""
    out = Path(out_dir)
    problems: list[str] = []
    works_path, regions_path = out / WORKS_FILE, out / WORK_REGIONS_FILE
    for path in (works_path, regions_path):
        if not path.exists():
            return [f"missing {path}"]
    works = pq.read_table(works_path)
    regions = pq.read_table(regions_path)
    if not works.schema.equals(WORKS_SCHEMA, check_metadata=False):
        problems.append("works.parquet schema differs from WORKS_SCHEMA")
    if not regions.schema.equals(WORK_REGIONS_SCHEMA, check_metadata=False):
        problems.append("work_regions.parquet schema differs from WORK_REGIONS_SCHEMA")
    if problems:
        return problems
    work_ids = works.column("work_id").to_pylist()
    if any(not value for value in work_ids):
        problems.append("works.work_id has empty values")
    if len(set(work_ids)) != len(work_ids):
        problems.append("works.work_id is not unique")
    statuses = set(works.column("screening_status").to_pylist())
    if statuses - {SCREENING_UNSCREENED}:
        problems.append(f"works with a screening label other than unscreened: {sorted(statuses)}")
    kinds = set(regions.column("region_kind").to_pylist())
    if kinds - set(REGION_KINDS):
        problems.append(f"unknown region_kind values: {sorted(kinds)}")
    bases = set(regions.column("basis").to_pylist())
    if bases - set(BASES):
        problems.append(f"unknown basis values: {sorted(bases)}")
    keys = list(
        zip(
            regions.column("work_id").to_pylist(),
            regions.column("region_kind").to_pylist(),
            regions.column("region_code").to_pylist(),
            strict=True,
        )
    )
    if len(set(keys)) != len(keys):
        problems.append("work_regions has duplicate (work_id, region_kind, region_code) rows")
    orphans = set(regions.column("work_id").to_pylist()) - set(work_ids)
    if orphans:
        problems.append(f"work_regions rows point at {len(orphans)} unknown works")
    return problems


def summarize(out_dir: str | Path = DEFAULT_OUT_DIR, top: int = 10) -> dict[str, Any]:
    """Headline counts from the two tables: works, pmid, top countries, default-region works."""
    out = Path(out_dir)
    works = pq.read_table(out / WORKS_FILE, columns=["work_id", "pmid"])
    regions = pq.read_table(out / WORK_REGIONS_FILE)
    country_rows = regions.filter(pc.equal(regions.column("region_kind"), "country"))
    per_country = Counter(country_rows.column("region_code").to_pylist())
    default_slug = scope.DEFAULT_REGION_SLUG
    default_rows = regions.filter(
        pc.and_(
            pc.equal(regions.column("region_kind"), "registry_region"),
            pc.equal(regions.column("region_code"), default_slug),
        )
    )
    return {
        "works": works.num_rows,
        "works_with_pmid": sum(1 for value in works.column("pmid").to_pylist() if value),
        "top_countries": sorted(per_country.items(), key=lambda kv: (-kv[1], kv[0]))[:top],
        "default_region_works": default_rows.num_rows,
        "default_region": default_slug,
    }
