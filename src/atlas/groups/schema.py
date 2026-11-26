"""cg-v2 record schema and validation rules V1-V14 for the community groups layer (Add-on A4).

The rules are those of docs/BFFP.md section 8.2. Vocabularies come from
``config/groups_taxonomy.yml``. Problems are returned as strings that start with the rule id
(``"V3: ..."``). Shape errors that no V-rule covers (missing key, wrong type) start with
``"SCHEMA: "``.

Nothing here touches the network. The module reads only the taxonomy file, and only when no
taxonomy is passed in.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterator, Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

__all__ = [
    "DEFAULT_TAXONOMY_PATH",
    "ISO_639_1_CODES",
    "derive_layer",
    "load_taxonomy",
    "quote_word_count",
    "validate_group",
    "validate_groups",
]

SCHEMA_VERSION = "cg-v2"
DEFAULT_TAXONOMY_PATH = Path(__file__).resolve().parents[3] / "config" / "groups_taxonomy.yml"

# ISO 639-1: the 184 two-letter codes (V13).
ISO_639_1_CODES = frozenset(
    """
    aa ab ae af ak am an ar as av ay az ba be bg bh bi bm bn bo br bs ca ce ch co cr cs cu cv cy
    da de dv dz ee el en eo es et eu fa ff fi fj fo fr fy ga gd gl gn gu gv ha he hi ho hr ht hu
    hy hz ia id ie ig ii ik io is it iu ja jv ka kg ki kj kk kl km kn ko kr ks ku kv kw ky la lb
    lg li ln lo lt lu lv mg mh mi mk ml mn mr ms mt my na nb nd ne ng nl nn no nr nv ny oc oj om
    or os pa pi pl ps pt qu rm rn ro ru rw sa sc sd se sg si sk sl sm sn so sq sr ss st su sv sw
    ta te tg th ti tk tl tn to tr ts tt tw ty ug uk ur uz ve vi vo wa wo xh yi yo za zh zu
    """.split()
)

# Statuses at or above ambassador_tagged (section 5.3); their facets must be set (V2).
TAGGED_STATUSES = frozenset({"ambassador_tagged", "reviewed", "group_confirmed"})
# Only these org_status values are admitted (V12; section 4.4, A4-D20).
ADMITTED_ORG_STATUS = frozenset({"source_declared_org", "heuristic_org", "human_confirmed_org"})
# Keys that would carry personal data (V8).
PERSONAL_KEY_PARTS = ("email", "phone", "ambassador", "person", "contact_person")
# Keys that identify an Ambassador and must never be published (V9).
AMBASSADOR_KEYS = frozenset({"ambassador_id", "tagged_by", "reviewed_by"})

MAX_QUOTE_WORDS = 25
MAX_NOTE_CHARS = 200
MAX_PLACES = 5
MAX_PRIMARY_ACTIVITIES = 3

REQUIRED_KEYS = (
    "schema",
    "group_id",
    "name",
    "name_alt",
    "url",
    "country",
    "region",
    "places",
    "source",
    "org_status",
    "bffp_listed",
    "bffp_listed_asof",
    "status",
    "cannot_determine_reason",
    "layer",
    "entity_type",
    "sector",
    "plastics_centrality",
    "primary_activities",
    "geographic_scope",
    "legal_form",
    "legal_form_note",
    "participation_in_science",
    "website_languages",
    "themes",
    "analytic_lens",
    "constituency",
    "parent_group_id",
    "stated_affiliations",
    "evidence",
    "tagged_at",
    "reviewed_at",
)

# Enumerated fields that may be null: field name -> taxonomy key.
NULLABLE_ENUMS = {
    "entity_type": "entity_type",
    "sector": "sector",
    "plastics_centrality": "plastics_centrality",
    "geographic_scope": "geographic_scope",
    "legal_form": "legal_form",
    "participation_in_science": "participation_in_science",
    "cannot_determine_reason": "cannot_determine_reason",
    "source": "source",
    "status": "status",
}

_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
# Group websites are often still http (2026-11-26 roster), so both schemes are accepted.
_HTTPS_RE = re.compile(r"https?://[^\s/]+\S*")
_COUNTRY_RE = re.compile(r"[A-Z]{2}")
_PLACE_RE = re.compile(r"[A-Z]{2}(-[A-Z0-9]{1,3})?")
_LANG_RE = re.compile(r"[a-z]{2}")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_EXCLUDED_COUNT_RE = re.compile(
    r"\b(excluded|ambiguous)\b.*\d|\d.*\b(excluded|ambiguous)\b", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Taxonomy and small helpers
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4)
def _read_taxonomy(path_text: str) -> Mapping[str, tuple[str, ...]]:
    raw = yaml.safe_load(Path(path_text).read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict) or raw.get("schema") != SCHEMA_VERSION:
        raise ValueError(f"{path_text}: taxonomy must declare schema {SCHEMA_VERSION!r}")
    vocabularies: dict[str, tuple[str, ...]] = {}
    for key, values in raw.items():
        if key == "schema":
            continue
        if (
            not isinstance(values, list)
            or not all(isinstance(v, str) for v in values)
            or len(set(values)) != len(values)
        ):
            raise ValueError(f"{path_text}: vocabulary {key!r} must be a list of unique strings")
        vocabularies[key] = tuple(values)
    return MappingProxyType(vocabularies)


def load_taxonomy(path: Path | str | None = None) -> dict[str, tuple[str, ...]]:
    """Return the controlled vocabularies, keyed by name, in the order of the YAML file."""
    target = DEFAULT_TAXONOMY_PATH if path is None else Path(path)
    return dict(_read_taxonomy(str(target.resolve())))


def _resolve_taxonomy(taxonomy: Mapping[str, Sequence[str]] | None) -> Mapping[str, Any]:
    if taxonomy is None:
        return _read_taxonomy(str(DEFAULT_TAXONOMY_PATH.resolve()))
    return taxonomy


def derive_layer(centrality: str | None) -> str:
    """Return the derived layer for a plastics_centrality value (V1, section 8.2)."""
    if centrality in ("primary", "substantial"):
        return "core"
    if centrality in ("incidental", "none"):
        return "adjacent"
    return "untagged"


def quote_word_count(text: str | None) -> int:
    """Count words in a quote by splitting on whitespace (V3)."""
    return len(text.split()) if text else 0


def _is_date(value: Any) -> bool:
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        return False
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_https(value: Any) -> bool:
    return isinstance(value, str) and _HTTPS_RE.fullmatch(value) is not None


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _walk(node: Any, path: str = "record") -> Iterator[tuple[str, str | None, Any]]:
    """Yield (path, dict_key_or_None, value) for every dict entry and list item, recursively."""
    if isinstance(node, Mapping):
        for key, value in node.items():
            child = f"{path}.{key}"
            yield child, str(key), value
            yield from _walk(value, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            child = f"{path}[{index}]"
            yield child, None, value
            yield from _walk(value, child)


# ---------------------------------------------------------------------------
# Shape (not a V-rule): required keys and types from section 8.2
# ---------------------------------------------------------------------------


def _check_shape(record: Mapping[str, Any], vocab: Mapping[str, Any], problems: list[str]) -> None:
    for key in REQUIRED_KEYS:
        if key not in record:
            problems.append(f"SCHEMA: missing key {key!r}")
    if record.get("schema", SCHEMA_VERSION) != SCHEMA_VERSION:
        problems.append(f"SCHEMA: schema must be {SCHEMA_VERSION!r}")
    for key in ("group_id", "name", "region"):
        if key in record and not _is_nonempty_str(record[key]):
            problems.append(f"SCHEMA: {key} must be a non-empty string")
    if "url" in record and record["url"] is not None and not _is_https(record["url"]):
        problems.append("SCHEMA: url must be an http(s) URL or null")
    if "country" in record and record["country"] is not None:
        if not isinstance(record["country"], str) or not _COUNTRY_RE.fullmatch(record["country"]):
            problems.append("SCHEMA: country must be an ISO 3166-1 alpha-2 code or null")
    for key in ("name_alt", "places", "primary_activities", "website_languages", "themes"):
        if key in record and not _is_str_list(record[key]):
            problems.append(f"SCHEMA: {key} must be a list of strings")
    if _is_str_list(record.get("places")):
        for code in record["places"]:
            if not _PLACE_RE.fullmatch(code):
                problems.append(f"SCHEMA: places value {code!r} is not an ISO 3166 code")
    for key, taxonomy_key in NULLABLE_ENUMS.items():
        if key in record and record[key] is not None and record[key] not in vocab[taxonomy_key]:
            problems.append(f"SCHEMA: {key} {record[key]!r} is not in the vocabulary")
    if _is_str_list(record.get("primary_activities")):
        for value in record["primary_activities"]:
            if value not in vocab["primary_activities"]:
                problems.append(f"SCHEMA: primary_activities value {value!r} is not in the list")
    if isinstance(record.get("constituency"), list):
        for value in record["constituency"]:
            if value not in vocab["constituency"]:
                problems.append(f"SCHEMA: constituency value {value!r} is not in the vocabulary")
    if "bffp_listed" in record and not isinstance(record["bffp_listed"], bool):
        problems.append("SCHEMA: bffp_listed must be true or false")
    for key in ("bffp_listed_asof", "tagged_at", "reviewed_at"):
        if record.get(key) is not None and not _is_date(record.get(key)):
            problems.append(f"SCHEMA: {key} must be YYYY-MM-DD or null")
    for key in ("legal_form_note", "parent_group_id"):
        if record.get(key) is not None and not isinstance(record.get(key), str):
            problems.append(f"SCHEMA: {key} must be a string or null")
    if "analytic_lens" in record and not _is_str_list(record["analytic_lens"]):
        problems.append("SCHEMA: analytic_lens must be a list of strings")
    if "constituency" in record and not _is_str_list(record["constituency"]):
        problems.append("SCHEMA: constituency must be a list of strings")
    for key in ("evidence", "stated_affiliations"):
        if key in record and not (
            isinstance(record[key], list) and all(isinstance(v, Mapping) for v in record[key])
        ):
            problems.append(f"SCHEMA: {key} must be a list of objects")


def _is_str_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(v, str) for v in value)


# ---------------------------------------------------------------------------
# V-rules
# ---------------------------------------------------------------------------


def _check_v1(record: Mapping[str, Any], problems: list[str]) -> None:
    expected = derive_layer(record.get("plastics_centrality"))
    if record.get("layer") != expected:
        problems.append(
            f"V1: layer {record.get('layer')!r} must be derived as {expected!r} "
            f"from plastics_centrality {record.get('plastics_centrality')!r}"
        )


def _check_v2(record: Mapping[str, Any], problems: list[str]) -> None:
    status = record.get("status")
    centrality = record.get("plastics_centrality")
    reason = record.get("cannot_determine_reason")
    if status == "cannot_determine" and reason is None:
        problems.append("V2: status cannot_determine requires cannot_determine_reason")
    if status != "cannot_determine" and reason is not None:
        problems.append("V2: cannot_determine_reason is only valid with status cannot_determine")
    if centrality == "cannot_determine" and status != "cannot_determine":
        problems.append("V2: plastics_centrality cannot_determine requires status cannot_determine")
    if status in TAGGED_STATUSES:
        for key in ("entity_type", "sector", "plastics_centrality", "geographic_scope"):
            if record.get(key) is None:
                problems.append(f"V2: status {status} requires {key}")
        if not record.get("primary_activities"):
            problems.append(f"V2: status {status} requires primary_activities")


def _check_evidence_item(
    item: Any, where: str, problems: list[str], *, facet_required: bool
) -> None:
    if not isinstance(item, Mapping):
        return  # reported by the shape check
    if facet_required and not _is_nonempty_str(item.get("facet")):
        problems.append(f"SCHEMA: {where}.facet must be a non-empty string")
    if not _is_https(item.get("url")):
        problems.append(f"SCHEMA: {where}.url must be an http(s) URL")
    if not _is_date(item.get("accessed_at")):
        problems.append(f"SCHEMA: {where}.accessed_at must be YYYY-MM-DD")
    quote = item.get("quote")
    not_stated = item.get("not_stated")
    if not isinstance(not_stated, bool):
        problems.append(f"SCHEMA: {where}.not_stated must be true or false")
    if quote is not None and not isinstance(quote, str):
        problems.append(f"SCHEMA: {where}.quote must be a string or null")
        quote = None
    has_quote = quote is not None
    if has_quote == (not_stated is True):
        problems.append(f"V3: {where} needs exactly one of quote or not_stated=true")
    if has_quote:
        words = quote_word_count(quote)
        if words == 0:
            problems.append(f"V3: {where} quote is empty")
        elif words > MAX_QUOTE_WORDS:
            problems.append(f"V3: {where} quote has {words} words (max {MAX_QUOTE_WORDS})")
    note = item.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > MAX_NOTE_CHARS):
        problems.append(f"SCHEMA: {where}.note must be a string of at most {MAX_NOTE_CHARS} chars")


def _check_v3_and_v4(record: Mapping[str, Any], problems: list[str]) -> None:
    evidence = record.get("evidence") if isinstance(record.get("evidence"), list) else []
    facets = set()
    for index, item in enumerate(evidence):
        _check_evidence_item(item, f"evidence[{index}]", problems, facet_required=True)
        if isinstance(item, Mapping) and isinstance(item.get("facet"), str):
            facets.add(item["facet"])
    if record.get("plastics_centrality") is not None and "plastics_centrality" not in facets:
        problems.append("V4: evidence needs an entry for plastics_centrality")
    if record.get("primary_activities") and "primary_activities" not in facets:
        problems.append("V4: evidence needs an entry for primary_activities")


def _check_v5(record: Mapping[str, Any], problems: list[str]) -> None:
    places = record.get("places")
    if isinstance(places, list) and len(places) > MAX_PLACES:
        problems.append(f"V5: places has {len(places)} entries (max {MAX_PLACES})")
    activities = record.get("primary_activities")
    if isinstance(activities, list):
        if len(activities) > MAX_PRIMARY_ACTIVITIES:
            problems.append(
                f"V5: primary_activities has {len(activities)} entries "
                f"(max {MAX_PRIMARY_ACTIVITIES})"
            )
        if not activities and record.get("status") in TAGGED_STATUSES:
            problems.append("V5: primary_activities needs 1-3 values for a tagged status")


def _check_v6(record: Mapping[str, Any], problems: list[str]) -> None:
    participation = record.get("participation_in_science")
    activities = record.get("primary_activities") or []
    if participation not in (None, "not_applicable") and "research_monitoring" not in activities:
        problems.append(
            f"V6: participation_in_science {participation!r} requires research_monitoring "
            "in primary_activities"
        )


def _check_v7(record: Mapping[str, Any], problems: list[str]) -> None:
    if record.get("bffp_listed") is True and not _is_date(record.get("bffp_listed_asof")):
        problems.append("V7: bffp_listed true requires bffp_listed_asof (YYYY-MM-DD)")


def _check_v8_v9_v14(record: Mapping[str, Any], problems: list[str]) -> None:
    for path, key, value in _walk(record):
        if key is not None:
            lowered = key.lower()
            if any(part in lowered for part in PERSONAL_KEY_PARTS):
                problems.append(f"V8: {path} is a personal-data field name")
            if key in AMBASSADOR_KEYS:
                problems.append(f"V9: {path} must not appear in a published record")
            if "excluded" in lowered or "ambiguous" in lowered:
                problems.append(f"V14: {path} reports excluded or ambiguous counts")
        if isinstance(value, str):
            if _EMAIL_RE.search(value):
                problems.append(f"V8: {path} holds an email-pattern value")
            if _EXCLUDED_COUNT_RE.search(value):
                problems.append(f"V14: {path} reports excluded or ambiguous counts")


def _check_v10(
    record: Mapping[str, Any], known_group_ids: set[str] | None, problems: list[str]
) -> None:
    if known_group_ids is None:
        return
    parent = record.get("parent_group_id")
    if parent is not None and parent not in known_group_ids:
        problems.append(f"V10: parent_group_id {parent!r} is not a known group_id")
    affiliations = record.get("stated_affiliations")
    if not isinstance(affiliations, list):
        return
    for index, affiliation in enumerate(affiliations):
        if not isinstance(affiliation, Mapping):
            continue
        target = affiliation.get("target_group_id")
        if target is not None and target not in known_group_ids:
            problems.append(
                f"V10: stated_affiliations[{index}].target_group_id {target!r} "
                "is not a known group_id"
            )


def _check_v11(record: Mapping[str, Any], vocab: Mapping[str, Any], problems: list[str]) -> None:
    affiliations = record.get("stated_affiliations")
    if not isinstance(affiliations, list):
        return
    for index, affiliation in enumerate(affiliations):
        if not isinstance(affiliation, Mapping):
            continue
        if affiliation.get("target_group_id") is None and affiliation.get("target_name") is None:
            problems.append(f"SCHEMA: stated_affiliations[{index}] needs a target")
        if affiliation.get("relation") not in vocab["relation"]:
            problems.append(f"SCHEMA: stated_affiliations[{index}].relation is not in the list")
        evidence = affiliation.get("evidence")
        if not isinstance(evidence, Mapping):
            problems.append(f"SCHEMA: stated_affiliations[{index}].evidence must be an object")
            continue
        _check_evidence_item(
            evidence, f"stated_affiliations[{index}].evidence", problems, facet_required=False
        )
        if evidence.get("not_stated") is True or not isinstance(evidence.get("quote"), str):
            problems.append(
                f"V11: stated_affiliations[{index}] needs a quote (not_stated is not allowed)"
            )


def _check_v12(record: Mapping[str, Any], problems: list[str]) -> None:
    if record.get("org_status") not in ADMITTED_ORG_STATUS:
        problems.append(
            f"V12: org_status {record.get('org_status')!r} is not admitted "
            "(source_declared_org, heuristic_org or human_confirmed_org)"
        )


def _check_v13(record: Mapping[str, Any], problems: list[str]) -> None:
    languages = record.get("website_languages")
    if not isinstance(languages, list):
        return
    for code in languages:
        if not (isinstance(code, str) and _LANG_RE.fullmatch(code) and code in ISO_639_1_CODES):
            problems.append(f"V13: website_languages value {code!r} is not an ISO 639-1 code")


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def validate_group(
    record: Mapping[str, Any],
    *,
    known_group_ids: set[str] | None = None,
    taxonomy: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """Return the problems found in one cg-v2 record; an empty list means it passes.

    ``known_group_ids`` enables the V10 reference checks; without it they are skipped.
    ``taxonomy`` defaults to ``config/groups_taxonomy.yml``.
    """
    if not isinstance(record, Mapping):
        return ["SCHEMA: record must be a JSON object"]
    vocab = _resolve_taxonomy(taxonomy)
    problems: list[str] = []
    _check_shape(record, vocab, problems)
    _check_v1(record, problems)
    _check_v2(record, problems)
    _check_v3_and_v4(record, problems)
    _check_v5(record, problems)
    _check_v6(record, problems)
    _check_v7(record, problems)
    _check_v8_v9_v14(record, problems)
    _check_v10(record, known_group_ids, problems)
    _check_v11(record, vocab, problems)
    _check_v12(record, problems)
    _check_v13(record, problems)
    return problems


def validate_groups(
    records: Sequence[Mapping[str, Any]],
    *,
    taxonomy: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    """Validate a whole file: every record, plus V10 duplicate and cross-reference checks.

    Each problem is prefixed with its rule id and the group_id (``"V10: cg_x: ..."``).
    """
    vocab = _resolve_taxonomy(taxonomy)
    known = {r["group_id"] for r in records if isinstance(r, Mapping) and "group_id" in r}
    problems: list[str] = []
    seen: set[str] = set()
    for index, record in enumerate(records):
        group_id = record.get("group_id") if isinstance(record, Mapping) else None
        label = group_id if isinstance(group_id, str) else f"record[{index}]"
        if isinstance(group_id, str):
            if group_id in seen:
                problems.append(f"V10: {label}: duplicate group_id")
            seen.add(group_id)
        for problem in validate_group(record, known_group_ids=known, taxonomy=vocab):
            rule, _, message = problem.partition(": ")
            problems.append(f"{rule}: {label}: {message}")
    return problems
