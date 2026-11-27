"""GP-5: reference-schema institution payloads for a non-default registry region (offline).

Reads the ignored global partition (PLAT-4b) and builds, for one registry region with a single
country code, the files the reference institution pages read:

- ``institutions.json`` (list of institutions, same keys as the reference builder),
- ``index.json`` (only the works and authors those institutions reference),
- ``institution_works/<inst_id>.json`` (one file per institution: experts and works).

Rules follow ``scripts/build_export_site.py`` (``_institution_experts``,
``_write_institution_works``) and ``docs/GLOBAL_PARITY.md`` section 3b.
Differences, all recorded in the ``method`` note:

- Works are region works (``work_regions`` rows of kind ``country`` with the region's ISO code).
  Every work carries ``screening_status: "unscreened_query_hit"``; ``plastic_related`` is null
  because no relevance review exists outside the reference region.
- Reference-only fields (labels, paid author metrics, reference connection) are null.
  ``domain_tags`` and ``facet_tags`` come from the reference rule labeller (``atlas.nlp.labels``)
  run on title and abstract, with the OpenAlex topic names, as the reference pipeline does. The
  abstract comes from the latest raw page and is used in memory only: it is never written here.
  Authors take the union of their region works' domain tags; institutions take the union of
  their works' domain and facet tags. Expert topics use the OpenAlex primary topic name instead.
- ``atlas_type`` maps the OpenAlex institution type to the reference vocabulary. Education and
  government institutions map to ``other`` because the partition does not say whether they are
  public or private, or which government level they belong to.
- ``lat``, ``lon`` and ``city`` are null (not in the partition).

Offline and deterministic: the same inputs give byte-identical JSON (sorted keys, compact
separators, LF, trailing newline), as ``export_site._atomic_json`` writes it.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from atlas.build.global_graphs import (
    _abstract_text,
    _iter_works,
    _ordered_pages,
    _short_id,
)
from atlas.build.region_pages import SCREENING_STATUS, read_work_countries
from atlas.ingest.abstract_qc import misattached_abstract_ids
from atlas.nlp.labels import (
    PLASTIC_CHEMICALS_TAG,
    _load_yaml,
    _raw_topic_info,
    _taxonomy_tags,
    always_relevant,
    classify_plastic_text,
)

# Same value as atlas.build.export_site.SCHEMA_VERSION (test_region_export pins it).
SCHEMA_VERSION = "s3.1"
EXPERTS_PER_INSTITUTION = 150
TOP_EXPERTS = 3
TOP_TOPICS = 5
REGION_BUDGET_BYTES = 20_000_000
OTHER_ATLAS_TYPE = "other"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw" / "openalex_global"
DEFAULT_CONFIG_DIR = REPO_ROOT / "config"

# OpenAlex institution ``type`` -> reference atlas_type. The nonprofit/NGO group matches the ROR
# rule in atlas.ingest.institutions.classify_atlas_type. Anything absent (education, government,
# other) falls back to ``other``.
ATLAS_TYPE_BY_OPENALEX_TYPE = {
    "company": "company",
    "nonprofit": "nonprofit/NGO",
    "funder": "nonprofit/NGO",
    "facility": "nonprofit/NGO",
    "archive": "nonprofit/NGO",
    "healthcare": "nonprofit/NGO",
}

# Evidence page (GP-8): the publication table's rows, one compact row per region work. Same shape as
# the reference works_detail.json rows (export_site._write_evidence_works), but no abstracts: the
# region export never writes abstract text. Authors per work match the reference limit.
WORKS_DETAIL_FILE = "works_detail.json"
DETAIL_AUTHORS_PER_WORK = 20
WORKS_DETAIL_ROW_KEYS = frozenset(
    {
        "work_id",
        "title",
        "year",
        "pub_date",
        "first_seen",
        "doi",
        "journal",
        "type",
        "cited_by_count",
        "is_oa",
        "oa_url",
        "plastic_related",
        "ca_led",
        "domain_tags",
        "facet_tags",
        "authors",
        "author_count",
        "has_abstract",
    }
)
# Bundle folder written next to index.json (the evidence page's facet index, AT-4 layout).
BUNDLE_FOLDER = "bundle"

METHOD_NOTE = (
    "Region export (GP-5). Works are region works (country work_regions rows) and are unscreened "
    "query hits (screening_status). plastic_related and reference-only fields are null; "
    "domain_tags and facet_tags come from the reference rule labeller (title and abstract, with "
    "OpenAlex topic names); lat, lon and city are null. atlas_type maps the "
    "OpenAlex type (education and government map to other). Expert topics are OpenAlex primary "
    "topics."
)

# Reference key sets (checked against the reference region's data by tests/fixtures/region_export).
INSTITUTIONS_FILE_KEYS = frozenset({"generated_at", "institutions", "schema_version"})
INSTITUTION_KEYS = frozenset(
    {
        "atlas_type",
        "author_count",
        "ca_flag",
        "city",
        "domain_tags",
        "inst_id",
        "lat",
        "lon",
        "name",
        "region",
        "ror",
        "top_experts",
        "work_count",
        "years",
    }
)
TOP_EXPERT_KEYS = frozenset({"author_id", "in_atlas_index", "name", "topic", "works"})
INDEX_FILE_KEYS = frozenset({"authors", "counts", "generated_at", "schema_version", "works"})
INDEX_WORK_KEYS = frozenset(
    {
        "author_ids",
        "ca_any_author",
        "ca_led",
        "cited_by_count",
        "domain_tags",
        "facet_tags",
        "institution_ids",
        "needs_review",
        "plastic_related",
        "plastic_tier",
        "screening_status",
        "study_type",
        "title",
        "type",
        "work_id",
        "year",
    }
)
INDEX_AUTHOR_KEYS = frozenset(
    {
        "author_id",
        "ca_plastic_works_count",
        "ca_works_count",
        "cited_by_count",
        "current_in_ca",
        "domain_tags",
        "early_career",
        "first_pub_year",
        "first_year",
        "h_index",
        "institution_ids",
        "last_ca_year",
        "last_year",
        "m_quotient",
        "name",
        "orcid",
        "plastic_basis",
        "plastic_citations",
        "plastic_works_count",
        "primary_affiliations",
        "rising_pct",
        "rising_score",
        "work_count",
        "work_ids",
    }
)
INSTITUTION_WORKS_FILE_KEYS = frozenset({"experts", "institution", "schema_version", "works"})
INSTITUTION_WORKS_INSTITUTION_KEYS = (INSTITUTION_KEYS - {"top_experts", "years"}) | {"scope"}
EXPERT_KEYS = frozenset(
    {
        "author_id",
        "first_year",
        "h_index",
        "in_atlas_index",
        "last_year",
        "name",
        "plastic_citations",
        "plastic_works_count",
        "topics",
        "works_at_institution",
        "years",
    }
)
FULL_WORK_KEYS = INDEX_WORK_KEYS | {
    "abstract",
    "author_names",
    "doi",
    "is_oa",
    "journal",
    "last_updated",
    "license",
    "oa_status",
    "oa_url",
    "openalex_topics",
    "primary_topic",
    "pub_date",
}
# Top-level keys of institutions.json and index.json; "method" is the region-only note.
TOP_LEVEL_EXTRA_KEYS = frozenset({"method"})
# Author files (GP-2): the reference region's author-file layout, with its region-only values null.
# An author gets a file (and an index row and in_atlas_index true) only with MIN_AUTHOR_WORKS works.
MIN_AUTHOR_WORKS = 2
AUTHOR_FILES_FOLDER = "authors"
AUTHOR_FILE_TOP_KEYS = frozenset({"author", "schema_version", "works"})
AUTHOR_FILE_KEYS = INDEX_AUTHOR_KEYS | {"affiliation_history", "citations_by_year"}
AUTHOR_FILE_WORK_KEYS = FULL_WORK_KEYS | {"author_count", "authors", "author_institution_ids"}

WORK_COLUMNS = [
    "work_id",
    "title",
    "publication_year",
    "publication_date",
    "type",
    "primary_topic_name",
    "cited_by_count",
    "doi",
]
AUTHORSHIP_COLUMNS = [
    "work_id",
    "author_position",
    "author_id",
    "author_name",
    "author_orcid",
    "institution_id",
]


@dataclass(frozen=True)
class RawWorkFields:
    """Labeller inputs from a work's latest raw page: abstract (in memory only), topic names."""

    abstract: str | None = None
    topic_names: tuple[str, ...] = ()
    primary_topic_name: str = ""


@dataclass(frozen=True)
class RegionInputs:
    """Partition rows for the region plus the labeller inputs (raw fields, rule configs)."""

    works: list[Mapping[str, Any]]
    work_regions: list[Mapping[str, Any]]
    authorships: list[Mapping[str, Any]]
    institutions: list[Mapping[str, Any]]
    raw: Mapping[str, RawWorkFields] = field(default_factory=dict)
    query_config: Mapping[str, Any] = field(default_factory=dict)
    taxonomy: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RegionExport:
    """The payloads for one region. ``files()`` maps repo-relative names under the region folder."""

    slug: str
    institutions: dict[str, Any]
    index: dict[str, Any]
    institution_works: dict[str, dict[str, Any]] = field(default_factory=dict)
    author_files: dict[str, dict[str, Any]] = field(default_factory=dict)
    works_detail: dict[str, Any] | None = None

    def files(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {
            "institutions.json": self.institutions,
            "index.json": self.index,
        }
        if self.works_detail is not None:
            out[WORKS_DETAIL_FILE] = self.works_detail
        for inst_id, payload in self.institution_works.items():
            out[f"institution_works/{inst_id}.json"] = payload
        for author_id, payload in self.author_files.items():
            out[f"{AUTHOR_FILES_FOLDER}/{author_id}.json"] = payload
        return out


def encode(payload: Mapping[str, Any]) -> bytes:
    """The reference JSON format: sorted keys, compact separators, ASCII, LF, trailing newline."""
    text = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    return text.encode("utf-8")


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _country(value: object) -> str | None:
    text = _text(value)
    return text.upper() if text and len(text) == 2 and text.isalpha() else None


def atlas_type_for(openalex_type: object) -> str:
    key = (_text(openalex_type) or "").casefold()
    return ATLAS_TYPE_BY_OPENALEX_TYPE.get(key, OTHER_ATLAS_TYPE)


def _raw_fields(record: Mapping[str, Any]) -> RawWorkFields:
    topic_names, primary = _raw_topic_info(record)
    return RawWorkFields(
        abstract=_text(_abstract_text(record.get("abstract_inverted_index"))),
        topic_names=tuple(topic_names.values()),
        primary_topic_name=primary,
    )


def read_raw_fields(raw_dir: str | Path, work_ids: AbstractSet[str]) -> dict[str, RawWorkFields]:
    """Labeller inputs for the given works from the raw pages; the latest page wins."""
    wanted = set(work_ids)
    found: dict[str, RawWorkFields] = {}
    headers, _, _ = _ordered_pages(raw_dir)
    for _, path in headers:
        for record in _iter_works(path):
            work_id = _short_id(record.get("id"))
            if work_id in wanted:
                found[work_id] = _raw_fields(record)
    return found


def read_inputs(
    partition_dir: str | Path,
    iso: str,
    *,
    raw_dir: str | Path = DEFAULT_RAW_DIR,
    config_dir: str | Path = DEFAULT_CONFIG_DIR,
) -> RegionInputs:
    """Read the partition files for one country code, filtering works and authorships by region.

    Also reads each region work's raw-page fields (abstract, topic names) and the rule configs
    (``queries.yml``, ``taxonomy.yml``) that the reference labeller uses.
    """
    folder = Path(partition_dir)
    work_regions = pq.read_table(folder / "work_regions.parquet").to_pylist()
    region_ids = sorted(
        work_id
        for work_id, codes in read_work_countries(work_regions).items()
        if iso.upper() in codes
    )
    if region_ids:
        works = pq.read_table(
            folder / "works.parquet", columns=WORK_COLUMNS, filters=[("work_id", "in", region_ids)]
        ).to_pylist()
        authorships = pq.read_table(
            folder / "authorships.parquet",
            columns=AUTHORSHIP_COLUMNS,
            filters=[("work_id", "in", region_ids)],
        ).to_pylist()
    else:
        works, authorships = [], []
    institutions = [
        row
        for row in pq.read_table(folder / "institutions.parquet").to_pylist()
        if _country(row.get("country_code")) == iso.upper()
    ]
    raw = read_raw_fields(raw_dir, {w["work_id"] for w in works}) if works else {}
    return RegionInputs(
        works=works,
        work_regions=work_regions,
        authorships=authorships,
        institutions=institutions,
        raw=raw,
        query_config=_load_yaml(Path(config_dir) / "queries.yml"),
        taxonomy=_load_yaml(Path(config_dir) / "taxonomy.yml"),
    )


def _work_tags(
    title: str,
    abstract: str | None,
    raw: RawWorkFields | None,
    query_config: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    """Domain and facet tags for one work: the reference labeller rule on title and abstract."""
    text = " ".join(value for value in (title, abstract) if value)
    decision = classify_plastic_text(text, query_config)
    tier = decision.tier
    if not decision.related and always_relevant(text, query_config):
        tier = "always"  # the reference owner rule for micro-nano plastics (label_records)
    topic_names = [*(raw.topic_names if raw else ()), raw.primary_topic_name if raw else ""]
    domain_tags, facet_tags = _taxonomy_tags(text, topic_names, taxonomy, title=title)
    if tier == "chemicals-in-plastics":
        domain_tags = sorted({*domain_tags, PLASTIC_CHEMICALS_TAG})
    return domain_tags, facet_tags


def _sorted_union(tag_lists: Iterable[Iterable[str]]) -> list[str]:
    return sorted({tag for tags in tag_lists for tag in tags if tag})


def _ordered(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            r.get("author_position") is None,
            r.get("author_position") or 0,
            _text(r.get("author_id")) or "",
            _text(r.get("institution_id")) or "",
        ),
    )


def build_region_export(
    slug: str, iso: str, inputs: RegionInputs, generated_at: str
) -> RegionExport:
    """Build the region payloads from partition rows. Pure: no I/O."""
    code = iso.upper()
    region_ids = {
        w for w, codes in read_work_countries(inputs.work_regions).items() if code in codes
    }
    works_by_id = {r["work_id"]: r for r in inputs.works if r["work_id"] in region_ids}
    inst_meta = {
        r["institution_id"]: r
        for r in inputs.institutions
        if _country(r.get("country_code")) == code
    }

    rows_by_work: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in inputs.authorships:
        if row["work_id"] in works_by_id:
            rows_by_work[row["work_id"]].append(row)

    # Institutions of the region that appear on at least one region work; works that list one.
    region_inst = {
        _text(r.get("institution_id"))
        for rows in rows_by_work.values()
        for r in rows
        if _text(r.get("institution_id")) in inst_meta
    }
    included = sorted(
        w
        for w, rows in rows_by_work.items()
        if any(_text(r.get("institution_id")) in region_inst for r in rows)
    )

    # Per work: ordered distinct authors, institution ids, and a full and index record.
    # Abstracts OpenAlex attached to unrelated works are blanked before labelling (abstract QC).
    abstract_of = {w: inputs.raw[w].abstract if w in inputs.raw else None for w in included}
    shared = misattached_abstract_ids(
        {
            "work_id": w,
            "title": works_by_id[w].get("title"),
            "doi": works_by_id[w].get("doi"),
            "abstract": abstract_of[w],
        }
        for w in included
    )
    work_inst: dict[str, set[str]] = {}
    work_authors: dict[str, list[tuple[str | None, str]]] = {}
    full_work: dict[str, dict[str, Any]] = {}
    works_at: defaultdict[tuple[str, str], set[str]] = defaultdict(set)
    names: dict[str, str] = {}
    for wid in included:
        base = works_by_id[wid]
        seen: set[str] = set()
        ordered_authors: list[tuple[str | None, str]] = []
        insts: set[str] = set()
        for row in _ordered(rows_by_work[wid]):
            aid = _text(row.get("author_id"))
            inst = _text(row.get("institution_id"))
            name = _text(row.get("author_name")) or ""
            if inst:
                insts.add(inst)
            key = aid or f"name:{name}"
            if key not in seen:
                seen.add(key)
                ordered_authors.append((aid, name))
            if aid and name:
                names.setdefault(aid, name)
            if aid and inst:
                works_at[(inst, aid)].add(wid)
        work_inst[wid] = insts
        work_authors[wid] = ordered_authors
        title = _text(base.get("title")) or ""
        abstract = None if wid in shared else abstract_of[wid]
        domain_tags, facet_tags = _work_tags(
            title, abstract, inputs.raw.get(wid), inputs.query_config, inputs.taxonomy
        )
        full = {
            "abstract": None,
            "author_ids": [a for a, _ in ordered_authors if a],
            "author_names": [n for _, n in ordered_authors],
            "ca_any_author": None,
            "ca_led": None,
            "cited_by_count": base.get("cited_by_count"),
            "doi": _text(base.get("doi")),
            "domain_tags": domain_tags,
            "facet_tags": facet_tags,
            "institution_ids": sorted(insts),
            "is_oa": None,
            "journal": None,
            "last_updated": None,
            "license": None,
            "needs_review": None,
            "oa_status": None,
            "oa_url": None,
            "openalex_topics": None,
            "plastic_related": None,
            "plastic_tier": None,
            "primary_topic": _text(base.get("primary_topic_name")),
            "pub_date": _text(base.get("publication_date")),
            "screening_status": SCREENING_STATUS,
            "study_type": None,
            "title": title,
            "type": _text(base.get("type")),
            "work_id": wid,
            "year": base.get("publication_year"),
        }
        assert set(full) == FULL_WORK_KEYS, "full work keys drifted from FULL_WORK_KEYS"
        full_work[wid] = full

    author_rows = _index_authors(included, works_by_id, names, rows_by_work)
    indexed = {a["author_id"] for a in author_rows if a["work_count"] >= MIN_AUTHOR_WORKS}
    authors = [a for a in author_rows if a["author_id"] in indexed]
    for row in authors:
        row["domain_tags"] = _sorted_union(full_work[w]["domain_tags"] for w in row["work_ids"])
    inst_name = {i: _text(m.get("display_name")) or i for i, m in inst_meta.items()}
    author_files = _author_files(authors, full_work, rows_by_work, work_authors, inst_name)

    institutions_out: list[dict[str, Any]] = []
    institution_works: dict[str, dict[str, Any]] = {}
    author_count_by_inst: dict[str, set[str]] = defaultdict(set)
    for inst, aid in works_at:
        author_count_by_inst[inst].add(aid)

    for inst_id in sorted(region_inst):
        meta = inst_meta[inst_id]
        here = sorted(
            (w for w in included if inst_id in work_inst[w]),
            key=lambda w: (-(full_work[w]["year"] or 0), full_work[w]["title"], w),
        )
        years = sorted(
            {full_work[w]["year"] for w in here if isinstance(full_work[w]["year"], int)}
        )
        experts = _experts(inst_id, here, works_at, full_work, names, indexed)
        ror = _text(meta.get("ror")) or ""
        inst_row = {
            "atlas_type": atlas_type_for(meta.get("type")),
            "author_count": len(author_count_by_inst.get(inst_id, set())),
            "ca_flag": False,
            "city": None,
            "domain_tags": _sorted_union(
                [*full_work[w]["domain_tags"], *full_work[w]["facet_tags"]] for w in here
            ),
            "inst_id": inst_id,
            "lat": None,
            "lon": None,
            "name": _text(meta.get("display_name")) or inst_id,
            "region": slug,
            "ror": ror,
            "top_experts": [
                {
                    "author_id": e["author_id"],
                    "in_atlas_index": e["in_atlas_index"],
                    "name": e["name"],
                    "topic": e["topics"][0][0] if e["topics"] else "",
                    "works": e["works_at_institution"],
                }
                for e in experts[:TOP_EXPERTS]
            ],
            "work_count": len(here),
            "years": years,
        }
        institutions_out.append(inst_row)
        institution_works[inst_id] = {
            "experts": experts[:EXPERTS_PER_INSTITUTION],
            "institution": {
                **{k: inst_row[k] for k in inst_row if k not in {"years", "top_experts"}},
                "scope": "region",
            },
            "schema_version": SCHEMA_VERSION,
            "works": [full_work[w] for w in here],
        }

    index_works = [{k: full_work[w][k] for k in sorted(INDEX_WORK_KEYS)} for w in sorted(full_work)]
    detail_works = [_detail_row(full_work[w]) for w in sorted(full_work)]
    works_detail = {"schema_version": SCHEMA_VERSION, "works": detail_works}
    institutions_payload = {
        "generated_at": generated_at,
        "institutions": institutions_out,
        "method": METHOD_NOTE,
        "schema_version": SCHEMA_VERSION,
    }
    index_payload = {
        "authors": authors,
        "counts": {
            "authors": len(authors),
            "ca_institutions": 0,
            "institutions": len(institutions_out),
            "labeled_works": 0,
            "works": len(index_works),
        },
        "generated_at": generated_at,
        "method": METHOD_NOTE,
        "schema_version": SCHEMA_VERSION,
        "works": index_works,
    }
    return RegionExport(
        slug=slug,
        institutions=institutions_payload,
        index=index_payload,
        institution_works=institution_works,
        author_files=author_files,
        works_detail=works_detail,
    )


def _detail_row(work: Mapping[str, Any]) -> dict[str, Any]:
    """One evidence-table row. Region works are unscreened, so plastic_related is null."""
    names = [n for n in work.get("author_names", []) if n]
    return {
        "work_id": work["work_id"],
        "title": work.get("title") or "",
        "year": work.get("year"),
        "pub_date": work.get("pub_date") or "",
        "first_seen": "",
        "doi": work.get("doi") or "",
        "journal": work.get("journal") or "",
        "type": work.get("type") or "",
        "cited_by_count": work.get("cited_by_count") or 0,
        "is_oa": False,
        "oa_url": "",
        "plastic_related": None,
        "ca_led": False,
        "domain_tags": list(work.get("domain_tags", [])),
        "facet_tags": list(work.get("facet_tags", [])),
        "authors": names[:DETAIL_AUTHORS_PER_WORK],
        "author_count": len(names),
        "has_abstract": False,
    }


def write_bundle(out_dir: str | Path, generated_at: str) -> dict[str, Any]:
    """Write the evidence page's facet bundle (``bundle/``) from the region's ``index.json``.

    Uses the AT-4 bundle builder with no normalized or analytics inputs, so the bundle carries only
    the region's works and their tags. The build is atomic (staging folder, then swap).
    """
    from atlas.build.bundle import build_bundle

    folder = Path(out_dir)
    return build_bundle(folder / "index.json", folder / BUNDLE_FOLDER, generated_at=generated_at)


def _experts(
    inst_id: str,
    work_ids: Sequence[str],
    works_at: Mapping[tuple[str, str], set[str]],
    full_work: Mapping[str, Mapping[str, Any]],
    names: Mapping[str, str],
    indexed: AbstractSet[str],
) -> list[dict[str, Any]]:
    """Authors at one institution, most works first (the reference expert rule without h-index).

    ``in_atlas_index`` is true only for authors with an author file (``indexed``), so the
    institution page links to a profile only where one exists.
    """
    experts: list[dict[str, Any]] = []
    here = set(work_ids)
    for (inst, aid), wids in works_at.items():
        if inst != inst_id:
            continue
        mine = sorted(wids & here)
        if not mine:
            continue
        works = [full_work[w] for w in mine]
        years = [w["year"] for w in works if isinstance(w["year"], int)]
        topics: Counter[str] = Counter(w["primary_topic"] for w in works if w["primary_topic"])
        per_year: Counter[str] = Counter(
            str(w["year"]) for w in works if isinstance(w["year"], int)
        )
        experts.append(
            {
                "author_id": aid,
                "first_year": min(years) if years else None,
                "h_index": None,
                "in_atlas_index": aid in indexed,
                "last_year": max(years) if years else None,
                "name": names.get(aid, ""),
                "plastic_citations": None,
                "plastic_works_count": None,
                "topics": [
                    [name, count]
                    for name, count in sorted(topics.items(), key=lambda kv: (-kv[1], kv[0]))[
                        :TOP_TOPICS
                    ]
                ],
                "works_at_institution": len(mine),
                "years": dict(sorted(per_year.items())),
            }
        )
    experts.sort(key=lambda e: (-e["works_at_institution"], e["name"], e["author_id"]))
    return experts


def _author_files(
    authors: Sequence[Mapping[str, Any]],
    full_work: Mapping[str, Mapping[str, Any]],
    rows_by_work: Mapping[str, Sequence[Mapping[str, Any]]],
    work_authors: Mapping[str, Sequence[tuple[str | None, str]]],
    inst_name: Mapping[str, str],
) -> dict[str, dict[str, Any]]:
    """One reference-layout author file per indexed author, with the author's region works.

    ``affiliation_history`` lists the region institutions the author is recorded with, with years.
    """
    files: dict[str, dict[str, Any]] = {}
    for row in authors:
        aid = row["author_id"]
        inst_years: defaultdict[str, set[int]] = defaultdict(set)
        for wid in row["work_ids"]:
            year = full_work[wid]["year"]
            for r in rows_by_work[wid]:
                inst = _text(r.get("institution_id"))
                if _text(r.get("author_id")) == aid and inst in inst_name and isinstance(year, int):
                    inst_years[inst].add(year)
        ordered_works = sorted(
            row["work_ids"],
            key=lambda w: (-(full_work[w]["year"] or 0), full_work[w]["title"], w),
        )
        works = []
        for wid in ordered_works:
            work = dict(full_work[wid])
            work["author_count"] = len(work_authors[wid])
            work["authors"] = [{"id": a, "name": n} for a, n in work_authors[wid] if a]
            work["author_institution_ids"] = sorted(
                {
                    _text(r.get("institution_id"))
                    for r in rows_by_work[wid]
                    if _text(r.get("author_id")) == aid
                }
                - {None}
            )
            assert set(work) == AUTHOR_FILE_WORK_KEYS, "author work keys drifted"
            works.append(work)
        history = [
            {"id": inst, "name": inst_name[inst], "years": sorted(inst_years[inst])}
            for inst in sorted(inst_years, key=lambda i: (inst_name[i], i))
        ]
        author = {**row, "affiliation_history": history, "citations_by_year": []}
        assert set(author) == AUTHOR_FILE_KEYS, "author file keys drifted"
        files[aid] = {"author": author, "schema_version": SCHEMA_VERSION, "works": works}
    return files


def _index_authors(
    included: Sequence[str],
    works_by_id: Mapping[str, Mapping[str, Any]],
    names: Mapping[str, str],
    rows_by_work: Mapping[str, list[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    """Every author on an included work, with the works and institutions the payload references."""
    work_ids: defaultdict[str, set[str]] = defaultdict(set)
    inst_ids: defaultdict[str, set[str]] = defaultdict(set)
    orcid: dict[str, str] = {}
    years: defaultdict[str, list[int]] = defaultdict(list)
    for wid in included:
        year = works_by_id[wid].get("publication_year")
        for row in rows_by_work[wid]:
            aid = _text(row.get("author_id"))
            if not aid:
                continue
            work_ids[aid].add(wid)
            inst = _text(row.get("institution_id"))
            if inst:
                inst_ids[aid].add(inst)
            if _text(row.get("author_orcid")):
                orcid.setdefault(aid, _text(row.get("author_orcid")))
        if isinstance(year, int):
            for aid in {_text(r.get("author_id")) for r in rows_by_work[wid]} - {None}:
                years[aid].append(year)
    authors = []
    for aid in sorted(work_ids):
        ys = years.get(aid, [])
        first = min(ys) if ys else None
        authors.append(
            {
                "author_id": aid,
                "ca_plastic_works_count": None,
                "ca_works_count": None,
                "cited_by_count": None,
                "current_in_ca": None,
                "domain_tags": [],
                "early_career": None,
                "first_pub_year": first,
                "first_year": first,
                "h_index": None,
                "institution_ids": sorted(inst_ids.get(aid, set())),
                "last_ca_year": None,
                "last_year": max(ys) if ys else None,
                "m_quotient": None,
                "name": names.get(aid, ""),
                "orcid": orcid.get(aid),
                "plastic_basis": None,
                "plastic_citations": None,
                "plastic_works_count": None,
                "primary_affiliations": None,
                "rising_pct": None,
                "rising_score": None,
                "work_count": len(work_ids[aid]),
                "work_ids": sorted(work_ids[aid]),
            }
        )
    return authors


def write_export(out_dir: str | Path, export: RegionExport) -> dict[str, int]:
    """Write every payload; remove stale institution_works files. Returns ``{relpath: bytes}``."""
    folder = Path(out_dir)
    written: dict[str, int] = {}
    for rel, payload in export.files().items():
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        data = encode(payload)
        target.write_bytes(data)
        written[rel] = len(data)
    for name in ("institution_works", AUTHOR_FILES_FOLDER):
        sub = folder / name
        if sub.is_dir():
            for stale in sub.glob("*.json"):
                if f"{name}/{stale.name}" not in written:
                    stale.unlink()
    return written


def existing_generated_at(out_dir: str | Path) -> str | None:
    """The committed ``generated_at``, reused so that rebuilds are byte-identical."""
    path = Path(out_dir) / "institutions.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("generated_at")
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) else None


def compare_export(out_dir: str | Path, export: RegionExport) -> list[str]:
    """Problems where the committed files differ from a rebuild (missing, changed or stale)."""
    folder = Path(out_dir)
    problems: list[str] = []
    expected = export.files()
    for rel, payload in expected.items():
        path = folder / rel
        if not path.is_file():
            problems.append(f"missing {rel}")
        elif path.read_bytes() != encode(payload):
            problems.append(f"stale {rel}")
    for name in ("institution_works", AUTHOR_FILES_FOLDER):
        sub = folder / name
        if sub.is_dir():
            for stale in sorted(sub.glob("*.json")):
                if f"{name}/{stale.name}" not in expected:
                    problems.append(f"unexpected {name}/{stale.name}")
    return problems


def validate_structure(out_dir: str | Path) -> list[str]:
    """Key sets, schema_version, id uniqueness and cross-file references of committed payloads."""
    folder = Path(out_dir)
    problems: list[str] = []
    try:
        inst_payload = json.loads((folder / "institutions.json").read_text(encoding="utf-8"))
        index_payload = json.loads((folder / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"cannot read institutions.json or index.json: {error}"]
    if set(inst_payload) - TOP_LEVEL_EXTRA_KEYS != INSTITUTIONS_FILE_KEYS:
        problems.append("institutions.json top-level keys differ from the reference layout")
    if set(index_payload) - TOP_LEVEL_EXTRA_KEYS != INDEX_FILE_KEYS:
        problems.append("index.json top-level keys differ from the reference layout")
    if inst_payload.get("schema_version") != SCHEMA_VERSION:
        problems.append("institutions.json schema_version differs")
    ids = [row.get("inst_id") for row in inst_payload.get("institutions", [])]
    if len(ids) != len(set(ids)):
        problems.append("institutions.json repeats an inst_id")
    for row in inst_payload.get("institutions", []):
        if set(row) != INSTITUTION_KEYS:
            inst_id = row.get("inst_id")
            problems.append(f"institution {inst_id} keys differ from the reference layout")
            break
        if any(set(e) != TOP_EXPERT_KEYS for e in row["top_experts"]):
            problems.append(f"institution {row.get('inst_id')} top_experts keys differ")
            break
    detail_path = folder / WORKS_DETAIL_FILE
    if detail_path.is_file():
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        if (
            set(detail) != {"schema_version", "works"}
            or detail.get("schema_version") != SCHEMA_VERSION
        ):
            problems.append("works_detail.json top-level keys or schema_version differ")
        for row in detail.get("works", []):
            if set(row) != WORKS_DETAIL_ROW_KEYS:
                problems.append(f"works_detail row {row.get('work_id')} keys differ")
                break
    else:
        problems.append(f"missing {WORKS_DETAIL_FILE}")
    work_ids = {w.get("work_id") for w in index_payload.get("works", [])}
    for row in index_payload.get("works", []):
        if set(row) != INDEX_WORK_KEYS or row.get("screening_status") != SCREENING_STATUS:
            problems.append(f"index work {row.get('work_id')} keys or screening_status differ")
            break
    for row in index_payload.get("authors", []):
        if set(row) != INDEX_AUTHOR_KEYS:
            author_id = row.get("author_id")
            problems.append(f"index author {author_id} keys differ from the reference layout")
            break
    works_folder = folder / "institution_works"
    files = sorted(works_folder.glob("*.json")) if works_folder.is_dir() else []
    if {p.stem for p in files} != set(ids):
        problems.append("institution_works files do not match institutions.json")
    author_folder = folder / AUTHOR_FILES_FOLDER
    author_files = sorted(author_folder.glob("*.json")) if author_folder.is_dir() else []
    indexed = {a.get("author_id") for a in index_payload.get("authors", [])}
    if {p.stem for p in author_files} != indexed:
        problems.append("authors files do not match index.json authors")
    for path in author_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if set(payload) != AUTHOR_FILE_TOP_KEYS or set(payload["author"]) != AUTHOR_FILE_KEYS:
            problems.append(f"authors/{path.name} keys differ from the reference layout")
            continue
        if any(set(w) != AUTHOR_FILE_WORK_KEYS for w in payload["works"]):
            problems.append(f"authors/{path.name} work keys differ from the reference layout")
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if set(payload) != INSTITUTION_WORKS_FILE_KEYS:
            problems.append(f"{path.name} top-level keys differ from the reference layout")
            continue
        if set(payload["institution"]) != INSTITUTION_WORKS_INSTITUTION_KEYS:
            problems.append(f"{path.name} institution keys differ from the reference layout")
        if any(set(e) != EXPERT_KEYS for e in payload["experts"]):
            problems.append(f"{path.name} expert keys differ from the reference layout")
        if any(e["in_atlas_index"] != (e["author_id"] in indexed) for e in payload["experts"]):
            problems.append(f"{path.name} in_atlas_index disagrees with the author files")
        for work in payload["works"]:
            if set(work) != FULL_WORK_KEYS or work["work_id"] not in work_ids:
                problems.append(
                    f"{path.name} work {work.get('work_id')} keys or index reference differ"
                )
                break
    return problems
