"""Region page payloads (REG-1): ``site/data/<slug>/region.json``, schema ``region-v1``.

One payload per Tier A or B region that has a ``country_codes`` predicate. The country numbers
(stats, works_by_year, top topics) are copied from ``site/data/global/countries.json`` for the
region's ISO code, so the two files cannot disagree. Institutions, researchers and partner
countries come from the ignored global partition and the raw OpenAlex pages. Local sections come
from ``regions/<slug>/region.yml``; every candidate starts as ``to_confirm``.

Every count is an unscreened query hit. Researcher rows carry only the public OpenAlex id,
display name and works count: no ORCID, email or affiliation strings.

Offline and deterministic: the same inputs give a byte-identical file (``generated_at`` is taken
from ``countries.json``, not the clock).
"""

from __future__ import annotations

import gzip
import json
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = "region-v1"
PAGE_STATUS = "in_preparation"
SCREENING_STATUS = "unscreened_query_hit"
SECTION_IDS = (
    "funding",
    "monitoring",
    "policy",
    "research_networks",
    "local_terms",
    "geography",
)
# `not_relevant` (set by a local ambassador, AMB-1) keeps the item in region.yml so item
# positions, which ambassador submissions use as ids, never shift; the page leaves such items out.
ITEM_STATUSES = ("to_confirm", "draft", "confirmed", "not_relevant")
TOP_TOPICS = 10
TOP_INSTITUTIONS = 15
TOP_RESEARCHERS = 15
TOP_PARTNERS = 10
AMBASSADORS = {"status": "recruiting", "url": "/ambassadors"}
WHAT_THIS_IS = (
    "A regional page built from the global set of published plastics research. Each count is an "
    "unscreened query hit: an OpenAlex work that matched the plastics search, grouped by the "
    "country of its authors' institutions. Nothing has been checked for relevance to this country."
)
WHAT_THIS_IS_NOT = (
    "Not a verified list of local funders, monitoring programmes, policies or institutes: every "
    "local item is a placeholder until a local collaborator confirms it. Not a share of world "
    "research, and not a ranking of people or organisations."
)
PERSON_KEYS = frozenset({"orcid", "email", "affiliation", "raw_author_name", "contact"})
RESEARCHER_KEYS = frozenset({"id", "name", "works"})
ITEM_KEYS = frozenset({"name", "url", "kind", "status", "note"})
# Keys of an item as written to region.json (region.yml keys plus the stable item_id).
ITEM_PUBLIC_KEYS = frozenset({"item_id", "name", "url", "kind", "status", "note"})
SECTION_KEYS = frozenset({"id", "title", "summary", "needs", "items"})
TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "generated_at",
        "slug",
        "name",
        "iso",
        "status",
        "screening_status",
        "what_this_is_and_is_not",
        "stats",
        "works_by_year",
        "top_topics",
        "top_institutions",
        "top_researchers",
        "partner_countries",
        "sections",
        "ambassadors",
    }
)
_OPENALEX_WORK = re.compile(r"https://openalex\.org/(W\d+)")
_EXPERT_WORD = re.compile(r"\bexperts?\b", re.IGNORECASE)
_ISO = re.compile(r"^[A-Z]{2}$")


class RegionConfigError(ValueError):
    """A region.yml file is missing a required field or has a bad value."""


def _short(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    prefix = "https://openalex.org/"
    if text.startswith(prefix):
        text = text[len(prefix) :]
    return text or None


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _country(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    code = value.strip().upper()
    return code if len(code) == 2 and code.isalpha() else None


# --- region.yml -----------------------------------------------------------------------------


def _require(where: str, mapping: Any, keys: frozenset[str]) -> None:
    if not isinstance(mapping, dict):
        raise RegionConfigError(f"{where}: expected a mapping")
    missing = keys - set(mapping)
    if missing:
        raise RegionConfigError(f"{where}: missing keys {sorted(missing)}")
    unknown = set(mapping) - keys
    if unknown:
        raise RegionConfigError(f"{where}: unknown keys {sorted(unknown)}")


def validate_config(data: Any) -> dict[str, Any]:
    """Check a loaded region.yml mapping and return it. Raises RegionConfigError."""
    top = frozenset(
        {
            "schema_version",
            "slug",
            "name",
            "iso",
            "tier",
            "languages",
            "local_search_terms",
            "sections",
        }
    )
    _require("region.yml", data, top)
    if data["schema_version"] != 1:
        raise RegionConfigError("region.yml: schema_version must be 1")
    if not _ISO.match(str(data["iso"])):
        raise RegionConfigError(f"region.yml: iso {data['iso']!r} must be two capital letters")
    if not isinstance(data["name"], str) or not data["name"].strip():
        raise RegionConfigError("region.yml: name must be a non-empty string")
    if not isinstance(data["languages"], list) or not data["languages"]:
        raise RegionConfigError("region.yml: languages must be a non-empty list")
    for term in data["local_search_terms"] or []:
        _require(
            "region.yml local_search_terms", term, frozenset({"term", "language", "status", "note"})
        )
        if term["status"] not in ITEM_STATUSES:
            raise RegionConfigError(f"region.yml: term {term['term']!r} has bad status")
    sections = data["sections"]
    if not isinstance(sections, list) or tuple(s.get("id") for s in sections) != SECTION_IDS:
        raise RegionConfigError(
            f"region.yml: sections must be exactly {list(SECTION_IDS)} in order"
        )
    for section in sections:
        where = f"section {section['id']!r}"
        _require(where, section, SECTION_KEYS)
        if not isinstance(section["items"], list) or not section["items"]:
            raise RegionConfigError(f"{where}: items must be a non-empty list")
        for item in section["items"]:
            _require(f"{where} item", item, ITEM_KEYS)
            if item["status"] not in ITEM_STATUSES:
                raise RegionConfigError(
                    f"{where}: item {item['name']!r} has status {item['status']!r}"
                )
            url = item["url"]
            if not isinstance(url, str) or (url and not url.startswith("https://")):
                raise RegionConfigError(
                    f"{where}: item {item['name']!r} url must be https or empty"
                )
            if not isinstance(item["note"], str) or not item["note"].strip():
                raise RegionConfigError(f"{where}: item {item['name']!r} needs a note")
    return data


def load_config(path: str | Path) -> dict[str, Any]:
    return validate_config(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def section_status(items: Sequence[Mapping[str, Any]]) -> str:
    """``placeholder`` if every item is unconfirmed, ``confirmed`` if all are, else ``draft``."""
    statuses = {item["status"] for item in items}
    if statuses == {"confirmed"}:
        return "confirmed"
    if statuses <= {"to_confirm"}:
        return "placeholder"
    return "draft"


def build_sections(config: Mapping[str, Any], slug: str) -> list[dict[str, Any]]:
    """Local sections for the page.

    ``item_id`` is ``<slug>:<section id>:<index in region.yml>``, counted before
    ``not_relevant`` items are left out, so an id never shifts when an item is hidden.
    Ambassador submissions and ``scripts/ambassador_export_pr.py`` address items by it."""
    sections: list[dict[str, Any]] = []
    for section in config["sections"]:
        items = [
            {
                "item_id": f"{slug}:{section['id']}:{index}",
                **{key: item[key] for key in ("name", "url", "kind", "status", "note")},
            }
            for index, item in enumerate(section["items"])
            if item["status"] != "not_relevant"
        ]
        sections.append(
            {
                "id": section["id"],
                "title": section["title"],
                "status": section_status(items),
                "summary": section["summary"],
                "items": items,
                "needs": section["needs"],
            }
        )
    return sections


def unconfirmed_items(sections: Sequence[Mapping[str, Any]]) -> list[str]:
    """``section: item name`` for every item that is not confirmed (the placeholder flags)."""
    return [
        f"{section['id']}: {item['name']}"
        for section in sections
        for item in section["items"]
        if item["status"] != "confirmed"
    ]


# --- partition and raw pages ----------------------------------------------------------------


def read_work_countries(regions_rows: Iterable[Mapping[str, Any]]) -> dict[str, frozenset[str]]:
    """``{work_id: countries}`` from work_regions rows of kind ``country``."""
    found: dict[str, set[str]] = {}
    for row in regions_rows:
        if row["region_kind"] != "country":
            continue
        code = _country(row["region_code"])
        if code:
            found.setdefault(row["work_id"], set()).add(code)
    return {work_id: frozenset(codes) for work_id, codes in found.items()}


def _slim_authorship(authorship: Mapping[str, Any]) -> dict[str, Any]:
    author = authorship.get("author") or {}
    institutions = []
    for institution in authorship.get("institutions") or []:
        if not isinstance(institution, Mapping):
            continue
        institutions.append(
            {
                "id": _short(institution.get("id")),
                "name": _text(institution.get("display_name")),
                "ror": _text(institution.get("ror")),
                "type": _text(institution.get("type")),
                "country_code": _country(institution.get("country_code")),
            }
        )
    return {
        "author_id": _short(author.get("id")),
        "author_name": _text(author.get("display_name")),
        "countries": [c for c in (_country(x) for x in authorship.get("countries") or []) if c],
        "institutions": institutions,
    }


def scan_authorships(
    page_paths: Iterable[Path], work_ids: set[str]
) -> dict[str, list[dict[str, Any]]]:
    """Slim authorships for the wanted works, read from raw gzip JSONL pages (later pages win)."""
    found: dict[str, list[dict[str, Any]]] = {}
    for path in page_paths:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            handle.readline()  # page_header
            for line in handle:
                if not line.strip():
                    continue
                # Cheap pre-filter: most lines are other works; parse only the wanted ones.
                if not any(w in work_ids for w in _OPENALEX_WORK.findall(line)):
                    continue
                work = json.loads(line)
                work_id = _short(work.get("id"))
                if work_id not in work_ids:
                    continue
                found[work_id] = [
                    _slim_authorship(a)
                    for a in work.get("authorships") or []
                    if isinstance(a, Mapping)
                ]
    return found


# --- blocks ---------------------------------------------------------------------------------


def stats_block(
    entry: Mapping[str, Any], last_complete: int, works_with_pmid: int
) -> dict[str, Any]:
    return {
        "works_total": entry["works_total"],
        "first_year": entry["first_year"],
        "last_complete_year": last_complete,
        "works_with_pmid": works_with_pmid,
    }


def series_block(entry: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Same year rows as countries.json; ``partial`` is True only for the current year."""
    return [
        {"year": row["year"], "count": row["count"], "partial": bool(row.get("partial", False))}
        for row in entry["works_by_year"]
    ]


def institutions_block(
    iso: str, work_ids: Iterable[str], authorships: Mapping[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    info: dict[str, dict[str, Any]] = {}
    for work_id in sorted(work_ids):
        seen: set[str] = set()
        for authorship in authorships.get(work_id, []):
            for institution in authorship["institutions"]:
                inst_id = institution["id"]
                if not inst_id or institution["country_code"] != iso or inst_id in seen:
                    continue
                seen.add(inst_id)
                counts[inst_id] += 1
                info.setdefault(inst_id, institution)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:TOP_INSTITUTIONS]
    return [
        {
            "id": inst_id,
            "name": info[inst_id]["name"] or inst_id,
            "ror": info[inst_id]["ror"],
            "type": info[inst_id]["type"],
            "works": count,
        }
        for inst_id, count in ranked
    ]


def researchers_block(
    iso: str, work_ids: Iterable[str], authorships: Mapping[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    """Authors with an authorship in the country (institution or author country), by works."""
    counts: Counter[str] = Counter()
    names: dict[str, str] = {}
    for work_id in sorted(work_ids):
        seen: set[str] = set()
        for authorship in authorships.get(work_id, []):
            author_id = authorship["author_id"]
            if not author_id or author_id in seen:
                continue
            in_country = iso in authorship["countries"] or any(
                i["country_code"] == iso for i in authorship["institutions"]
            )
            if not in_country:
                continue
            seen.add(author_id)
            counts[author_id] += 1
            names.setdefault(author_id, authorship["author_name"] or author_id)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:TOP_RESEARCHERS]
    return [{"id": a, "name": names[a], "works": n} for a, n in ranked]


def partners_block(
    iso: str,
    work_ids: Iterable[str],
    work_countries: Mapping[str, frozenset[str]],
    names: Mapping[str, str],
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for work_id in work_ids:
        for code in work_countries.get(work_id, frozenset()):
            if code != iso:
                counts[code] += 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:TOP_PARTNERS]
    return [{"iso": code, "name": names.get(code, code), "works": n} for code, n in ranked]


def build_region_payload(
    *,
    slug: str,
    name: str,
    iso: str,
    config: Mapping[str, Any],
    countries_payload: Mapping[str, Any],
    work_countries: Mapping[str, frozenset[str]],
    authorships: Mapping[str, list[dict[str, Any]]],
    names: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The region-v1 payload. Raises KeyError when countries.json has no entry for ``iso``."""
    entry = next((c for c in countries_payload.get("countries") or [] if c.get("iso") == iso), None)
    if entry is None:
        raise KeyError(f"countries.json has no entry for {iso}")
    work_ids = {w for w, codes in work_countries.items() if iso in codes}
    names = names or {}
    last_complete = int(countries_payload["years"]["last_complete"])
    works_with_pmid = int(entry["works_with_pmid"])
    topics = [
        {"id": t["id"], "name": t["name"], "count": t["count"]}
        for t in (entry.get("top_primary_topics") or [])[:TOP_TOPICS]
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": countries_payload["generated_at"],
        "slug": slug,
        "name": name,
        "iso": iso,
        "status": PAGE_STATUS,
        "screening_status": SCREENING_STATUS,
        "what_this_is_and_is_not": {"is": WHAT_THIS_IS, "is_not": WHAT_THIS_IS_NOT},
        "stats": stats_block(entry, last_complete, works_with_pmid),
        "works_by_year": series_block(entry),
        "top_topics": topics,
        "top_institutions": institutions_block(iso, work_ids, authorships),
        "top_researchers": researchers_block(iso, work_ids, authorships),
        "partner_countries": partners_block(iso, work_ids, work_countries, names),
        "sections": build_sections(config, slug),
        "ambassadors": dict(AMBASSADORS),
    }


def encode(payload: Mapping[str, Any]) -> str:
    """Pretty JSON, UTF-8 text, LF line endings, trailing newline."""
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


# --- validation -----------------------------------------------------------------------------


def _walk_keys(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield path, str(key)
            yield from _walk_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_keys(item, f"{path}[{index}]")


def _walk_strings(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield from _walk_strings(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_strings(item, f"{path}[{index}]")


def validate_payload(
    payload: Mapping[str, Any], countries_payload: Mapping[str, Any] | None = None
) -> list[str]:
    """Schema, labels, placeholder rule, privacy and wording problems (empty list = pass)."""
    problems: list[str] = []
    if set(payload) != TOP_LEVEL_KEYS:
        problems.append(f"top-level keys differ: {sorted(set(payload) ^ TOP_LEVEL_KEYS)}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version is not {SCHEMA_VERSION}")
    if payload.get("screening_status") != SCREENING_STATUS:
        problems.append("screening_status is not unscreened_query_hit")
    if payload.get("status") != PAGE_STATUS:
        problems.append(f"status is not {PAGE_STATUS}")
    sections = payload.get("sections") or []
    if tuple(s.get("id") for s in sections) != SECTION_IDS:
        problems.append("sections are not the six contract sections in order")
    for section in sections:
        if set(section) != SECTION_KEYS | {"status"}:
            problems.append(f"section {section.get('id')}: keys differ")
        for item in section.get("items") or []:
            if set(item) != ITEM_PUBLIC_KEYS:
                problems.append(f"section {section.get('id')}: item keys differ")
            if not str(item.get("item_id", "")).startswith(
                f"{payload.get('slug')}:{section.get('id')}:"
            ):
                problems.append(f"section {section.get('id')}: item_id does not name this item")
            if item.get("status") not in ITEM_STATUSES:
                problems.append(
                    f"section {section.get('id')}: item {item.get('name')!r} has no status"
                )
    for row in payload.get("top_researchers") or []:
        if set(row) != RESEARCHER_KEYS:
            problems.append("top_researchers row carries keys other than id, name, works")
    for path, key in _walk_keys(payload):
        if key.lower() in PERSON_KEYS:
            problems.append(f"{path}.{key}: person-level key")
    for path, text in _walk_strings(payload):
        if _EXPERT_WORD.search(text):
            problems.append(f"{path}: public text uses the word 'expert'")
    if countries_payload is not None:
        entry = next(
            (
                c
                for c in countries_payload.get("countries") or []
                if c.get("iso") == payload.get("iso")
            ),
            None,
        )
        if entry is None:
            problems.append("no countries.json entry for this ISO code")
        else:
            expected_series = series_block(entry)
            if payload.get("works_by_year") != expected_series:
                problems.append("works_by_year differs from countries.json")
            if payload.get("stats", {}).get("works_total") != entry["works_total"]:
                problems.append("stats.works_total differs from countries.json")
            if payload.get("stats", {}).get("first_year") != entry["first_year"]:
                problems.append("stats.first_year differs from countries.json")
    return problems
