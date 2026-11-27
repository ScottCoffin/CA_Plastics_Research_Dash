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
- Reference-only fields (labels, paid author metrics, CA connection) are null. ``domain_tags`` and
  ``facet_tags`` are empty lists because the reference labels need abstracts and classifiers that
  the partition does not hold. Expert topics use the OpenAlex primary topic name instead.
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from atlas.build.region_pages import SCREENING_STATUS, read_work_countries

# Same value as atlas.build.export_site.SCHEMA_VERSION (test_region_export pins it).
SCHEMA_VERSION = "s3.1"
EXPERTS_PER_INSTITUTION = 150
TOP_EXPERTS = 3
TOP_TOPICS = 5
REGION_BUDGET_BYTES = 20_000_000
OTHER_ATLAS_TYPE = "other"

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

METHOD_NOTE = (
    "Region export (GP-5). Works are region works (country work_regions rows) and are unscreened "
    "query hits (screening_status). plastic_related and reference-only fields are null; "
    "domain_tags and facet_tags are empty; lat, lon and city are null. atlas_type maps the "
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
class RegionInputs:
    """Partition rows for the region: works, work_regions, authorships and institutions."""

    works: list[Mapping[str, Any]]
    work_regions: list[Mapping[str, Any]]
    authorships: list[Mapping[str, Any]]
    institutions: list[Mapping[str, Any]]


@dataclass(frozen=True)
class RegionExport:
    """The payloads for one region. ``files()`` maps repo-relative names under the region folder."""

    slug: str
    institutions: dict[str, Any]
    index: dict[str, Any]
    institution_works: dict[str, dict[str, Any]] = field(default_factory=dict)

    def files(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {
            "institutions.json": self.institutions,
            "index.json": self.index,
        }
        for inst_id, payload in self.institution_works.items():
            out[f"institution_works/{inst_id}.json"] = payload
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


def read_inputs(partition_dir: str | Path, iso: str) -> RegionInputs:
    """Read the partition files for one country code, filtering works and authorships by region."""
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
    return RegionInputs(
        works=works, work_regions=work_regions, authorships=authorships, institutions=institutions
    )


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
        full = {
            "abstract": None,
            "author_ids": [a for a, _ in ordered_authors if a],
            "author_names": [n for _, n in ordered_authors],
            "ca_any_author": None,
            "ca_led": None,
            "cited_by_count": base.get("cited_by_count"),
            "doi": _text(base.get("doi")),
            "domain_tags": [],
            "facet_tags": [],
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
            "title": _text(base.get("title")) or "",
            "type": _text(base.get("type")),
            "work_id": wid,
            "year": base.get("publication_year"),
        }
        assert set(full) == FULL_WORK_KEYS, "full work keys drifted from FULL_WORK_KEYS"
        full_work[wid] = full

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
        experts = _experts(inst_id, here, works_at, full_work, names)
        ror = _text(meta.get("ror")) or ""
        inst_row = {
            "atlas_type": atlas_type_for(meta.get("type")),
            "author_count": len(author_count_by_inst.get(inst_id, set())),
            "ca_flag": False,
            "city": None,
            "domain_tags": [],
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
    authors = _index_authors(included, works_by_id, names, rows_by_work)
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
    )


def _experts(
    inst_id: str,
    work_ids: Sequence[str],
    works_at: Mapping[tuple[str, str], set[str]],
    full_work: Mapping[str, Mapping[str, Any]],
    names: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Authors at one institution, most works first (the reference expert rule without h-index).

    ``in_atlas_index`` is false for every expert until region author pages exist (GP-2), so the
    institution page shows them as plain text rather than links to missing author pages.
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
                "in_atlas_index": False,
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
    works_folder = folder / "institution_works"
    if works_folder.is_dir():
        for stale in works_folder.glob("*.json"):
            if f"institution_works/{stale.name}" not in written:
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
    works_folder = folder / "institution_works"
    if works_folder.is_dir():
        for stale in sorted(works_folder.glob("*.json")):
            if f"institution_works/{stale.name}" not in expected:
                problems.append(f"unexpected institution_works/{stale.name}")
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
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if set(payload) != INSTITUTION_WORKS_FILE_KEYS:
            problems.append(f"{path.name} top-level keys differ from the reference layout")
            continue
        if set(payload["institution"]) != INSTITUTION_WORKS_INSTITUTION_KEYS:
            problems.append(f"{path.name} institution keys differ from the reference layout")
        if any(set(e) != EXPERT_KEYS for e in payload["experts"]):
            problems.append(f"{path.name} expert keys differ from the reference layout")
        for work in payload["works"]:
            if set(work) != FULL_WORK_KEYS or work["work_id"] not in work_ids:
                problems.append(
                    f"{path.name} work {work.get('work_id')} keys or index reference differ"
                )
                break
    return problems
