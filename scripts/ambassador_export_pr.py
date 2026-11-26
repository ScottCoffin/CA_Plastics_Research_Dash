"""Turn approved ambassador contributions into a reviewable repository change (AMB-1 step 4).

Reads GET {api}/export/approved (or a saved export with --input) and applies:

- stream ``confirm`` (confirm, correct, not_relevant): edits the item named by ``payload.item_id``
  in ``regions/<slug>/region.yml``. ``item_id`` is ``<slug>:<section or kind>:<0-based index>``.
- stream ``knowledge``: appends a ``draft`` item to the matching section (``correction`` edits one).
  Kinds ``group_tag`` and ``group_suggest`` (CG-6b) never touch region.yml: tags go to
  ``curation/group_tags.csv`` (newest per group_id) with stated affiliations in
  ``curation/group_affiliations.csv``; suggestions go to ``curation/group_suggestions.csv``.
  A tag's optional ``name_correction`` goes to ``curation/group_name_corrections.csv`` (newest per
  group_id); the group build applies it.
- consensus ``case_answers``: rows in ``curation/ambassador_labels.csv``, newest per (region, case).
- ``institutions`` (optional key, missing means none): approved institution proposals, written to
  ``curation/ambassador_institution_additions.csv``, newest per (region, domain). The builder
  then adds them to the region's eligible list.

Every payload string is validated again here; an invalid item is skipped with a printed reason.
Region files are edited line by line, so comments and untouched items keep their bytes. The
watermark in ``curation/ambassador_export_state.json`` advances only after every file is written.
The token (``AMB_EXPORT_TOKEN``) is read from the environment and is never printed or logged.

Usage:
    py -3.14 scripts/ambassador_export_pr.py [--dry-run] [--input FILE] [--api-url URL]
"""

from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.groups.schema import load_taxonomy  # noqa: E402

DEFAULT_API_URL = "https://api.plastiverse.live"
DEFAULT_STATE = ROOT / "curation" / "ambassador_export_state.json"
DEFAULT_LABELS = ROOT / "curation" / "ambassador_labels.csv"
DEFAULT_REGIONS = ROOT / "regions"
DEFAULT_ADDITIONS = ROOT / "curation" / "ambassador_institution_additions.csv"
TOKEN_ENV = "AMB_EXPORT_TOKEN"
LABEL_COLUMNS = ("region", "case_id", "answer", "correct_value", "answered_at_iso", "source")
LABEL_SOURCE = "ambassador_consensus"
ADDITION_COLUMNS = (
    "region",
    "name",
    "url",
    "domain",
    "institution_type",
    "approved_at_iso",
    "source",
)
ADDITION_SOURCE = "approved_proposal"
DEFAULT_GROUP_TAGS = ROOT / "curation" / "group_tags.csv"
DEFAULT_GROUP_AFFILIATIONS = ROOT / "curation" / "group_affiliations.csv"
DEFAULT_GROUP_SUGGESTIONS = ROOT / "curation" / "group_suggestions.csv"
DEFAULT_GROUP_NAME_CORRECTIONS = ROOT / "curation" / "group_name_corrections.csv"
# The four types the amb-v1 builder treats as eligible (ELIGIBLE_TYPES in src/atlas/build).
INSTITUTION_TYPES = frozenset({"education", "government", "nonprofit", "facility"})
# Same pattern as the owner spec for institution domains; the builder also checks registrable form.
DOMAIN_RE = re.compile(r"(?=.{3,253}$)([a-z0-9-]+\.)+[a-z]{2,}")

# Same section ids and item fields that scripts/build_region_pages.py enforces (region-v1).
SECTION_IDS = ("funding", "monitoring", "policy", "research_networks", "local_terms", "geography")
ITEM_STATUSES = ("to_confirm", "draft", "confirmed", "not_relevant")
ITEM_KEYS = frozenset({"name", "url", "kind", "status", "note"})
ITEM_KEY_ORDER = ("name", "url", "kind", "status", "note")

# Knowledge kind -> (section id, item kind). region-v1 has no `community` section, so community and
# volunteer groups go under research_networks, item kind "community" (docs/AMBASSADOR_EXPORT.md).
# Kinds not listed here (event, media, researcher) have no section and are skipped.
KNOWLEDGE_SECTIONS = {
    "funder": ("funding", "funder"),
    "policy": ("policy", "policy"),
    "dataset": ("monitoring", "dataset"),
    "research_network": ("research_networks", "research_network"),
    "institution": ("research_networks", "institute"),
    "community_group": ("research_networks", "community"),
    "volunteer_group": ("research_networks", "community"),
    "community_knowledge": ("research_networks", "community"),
}
REQUIRE_URL = frozenset(
    {"funder", "policy", "dataset", "research_network", "community_group", "volunteer_group"}
)
CONFIRM_KINDS = frozenset({"confirm", "correct", "not_relevant"})

MAX_LENGTH = {
    "name": 200,
    "url": 500,
    "description": 1000,
    "note": 1000,
    "item_id": 200,
    "answer": 40,
    "correct_value": 200,
    "case_id": 80,
}
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{0,40}$")
ITEM_ID_RE = re.compile(r"^([a-z][a-z0-9-]{0,40}):([a-z_]{1,40}):(\d{1,4})$")
CASE_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")
CONTROL_OR_HTML_RE = re.compile(r"[<>\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SECTION_LINE_RE = re.compile(r"^  - id: (\S+)\s*$")
ITEM_LINE_RE = re.compile(r"^      - \{.*\}\s*$")
MAX_MS = 253402300799000  # 9999-12-31T23:59:59Z


class ExportError(Exception):
    """A fatal problem: nothing is written and the watermark does not move."""


# ---------------------------------------------------------------- validation helpers


def clean_text(value: Any, field: str) -> str | None:
    """Trimmed text within the field's cap, with no control characters, angle brackets or HTML."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > MAX_LENGTH[field] or CONTROL_OR_HTML_RE.search(text):
        return None
    return text


def clean_url(value: Any) -> str | None:
    """https only, no credentials, no whitespace."""
    text = clean_text(value, "url")
    if text is None or re.search(r"\s", text):
        return None
    try:
        parts = urllib.parse.urlsplit(text)
    except ValueError:
        return None
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        return None
    return text


def optional(payload: dict, field: str, cleaner: Any) -> tuple[bool, Any]:
    """(valid, value). A missing or empty field is valid with value None."""
    raw = payload.get(field)
    if raw in (None, ""):
        return True, None
    value = cleaner(raw)
    return value is not None, value


def is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def payload_of(record: dict) -> dict | None:
    payload = record.get("payload")
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            return None
    return payload if isinstance(payload, dict) else None


def iso_from_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def ms_from_iso(text: str) -> int:
    return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp() * 1000)


def locate_item(data: dict, item_id: str | None, slug: str) -> tuple[dict, dict] | None:
    """Return (section, item) for ``<slug>:<section id or kind>:<n>``, or None."""
    match = ITEM_ID_RE.match(item_id or "")
    if not match or match.group(1) != slug:
        return None
    key, index = match.group(2), int(match.group(3))
    sections = data.get("sections") or []
    for section in sections:
        if section.get("id") == key:
            items = section.get("items") or []
            return (section, items[index]) if index < len(items) else None
    hits = [(s, it) for s in sections for it in s.get("items") or [] if it.get("kind") == key]
    return hits[index] if index < len(hits) else None


def region_problem(data: dict) -> str | None:
    """The region-v1 rules that build_region_pages.py enforces. None when the region is valid."""
    sections = data.get("sections")
    if not isinstance(sections, list) or tuple(s.get("id") for s in sections) != SECTION_IDS:
        return "sections must be the six region-v1 sections in order"
    for section in sections:
        items = section.get("items")
        if not isinstance(items, list) or not items:
            return f"section {section['id']} has no items"
        for item in items:
            if not isinstance(item, dict) or set(item) != ITEM_KEYS:
                return f"section {section['id']} has an item with the wrong keys"
            if item["status"] not in ITEM_STATUSES:
                return f"section {section['id']} has a bad status"
            url = item["url"]
            if not isinstance(url, str) or (url and not url.startswith("https://")):
                return f"section {section['id']} has a non-https url"
            if not isinstance(item["note"], str) or not item["note"].strip():
                return f"section {section['id']} has an empty note"
    return None


def clean_institution(inst: dict, at: int, regions_dir: Path) -> tuple[dict | None, str | None]:
    """(addition row, None) for a valid approved institution, or (None, skip reason)."""
    region = inst.get("region")
    if not isinstance(region, str) or not SLUG_RE.match(region):
        return None, "invalid region"
    if not (regions_dir / region / "region.yml").is_file():
        return None, "no regions/<slug>/region.yml for this region"
    domain = inst.get("domain")
    if not isinstance(domain, str) or not DOMAIN_RE.fullmatch(domain):
        return None, "invalid domain"
    name = clean_text(inst.get("name"), "name")  # 200 characters, no control characters or HTML
    if name is None:
        return None, "invalid name"
    ok_url, url = optional(inst, "url", clean_url)
    if not ok_url:
        return None, "invalid url (https only)"
    if inst.get("institution_type") not in INSTITUTION_TYPES:
        return None, "invalid institution_type"
    return {
        "region": region,
        "domain": domain,
        "ms": at,
        "row": {
            "region": region,
            "name": name,
            "url": url or "",
            "domain": domain,
            "institution_type": inst["institution_type"],
            "approved_at_iso": iso_from_ms(at),
            "source": ADDITION_SOURCE,
        },
    }, None


# ---------------------------------------------------------------- region.yml line editing


def render_item(item: dict) -> str:
    fields = ", ".join(f"{k}: {json.dumps(item[k], ensure_ascii=False)}" for k in ITEM_KEY_ORDER)
    return f"      - {{{fields}}}\n"


def item_line_ranges(lines: list[str]) -> dict[str, tuple[int, int]]:
    """Map section id -> [first, last+1) line range of its flow-style item lines."""
    section = None
    ranges: dict[str, tuple[int, int]] = {}
    counts: Counter = Counter()
    for index, line in enumerate(lines):
        found = SECTION_LINE_RE.match(line)
        if found:
            section = found.group(1)
        elif section and ITEM_LINE_RE.match(line):
            first = ranges.get(section, (index, index))[0]
            ranges[section] = (first, index + 1)
            counts[section] += 1
    for sid, (first, last) in ranges.items():
        if last - first != counts[sid]:
            raise ExportError(f"section {sid} items are not contiguous; edit region.yml by hand")
    return ranges


def render_region(text: str, original: dict, data: dict) -> str:
    """Rewrite only the item lines whose content changed. Everything else keeps its bytes."""
    lines = text.splitlines(keepends=True)
    ranges = item_line_ranges(lines)
    original_items = {s["id"]: s["items"] for s in original["sections"]}
    out = list(lines)
    for section in reversed(data["sections"]):
        sid = section["id"]
        if sid not in ranges:
            raise ExportError(f"region.yml has no item lines for section {sid}")
        first, last = ranges[sid]
        before = lines[first:last]
        orig = original_items[sid]
        new_lines = []
        for i, item in enumerate(section["items"]):
            keep = i < len(orig) and item == orig[i] and i < len(before)
            new_lines.append(before[i] if keep else render_item(item))
        out[first:last] = new_lines
    new_text = "".join(out)
    if yaml.safe_load(new_text) != data:
        raise ExportError("rendered region.yml does not match the edited data; nothing written")
    return new_text


# ---------------------------------------------------------------- applying submissions


class Applier:
    """Holds the region files and label rows in memory; nothing touches disk until write_all()."""

    def __init__(
        self,
        regions_dir: Path,
        labels: dict[tuple[str, str], dict],
        additions: dict[tuple[str, str], dict],
        groups: GroupStore,
    ) -> None:
        self.regions_dir = regions_dir
        self.original: dict[str, tuple[str, dict]] = {}
        self.docs: dict[str, dict] = {}
        self.changed: set[str] = set()
        self.labels = labels
        self.labels_changed = False
        self.additions = additions
        self.additions_changed = False
        self.groups = groups
        self.applied: Counter = Counter()
        self.skipped: list[tuple[str, str]] = []

    def region_path(self, slug: str) -> Path:
        return self.regions_dir / slug / "region.yml"

    def load(self, slug: str) -> dict | None:
        if slug not in self.docs:
            path = self.region_path(slug)
            if not path.is_file():
                return None
            text = path.read_text(encoding="utf-8")
            loaded = yaml.safe_load(text)
            if not isinstance(loaded, dict):
                raise ExportError(f"{path} is not a mapping")
            self.original[slug] = (text, copy.deepcopy(loaded))
            self.docs[slug] = loaded
        return self.docs[slug]

    def skip(self, record_id: str, reason: str) -> None:
        self.skipped.append((record_id, reason))

    def submission(self, sub: dict, credit: str | None) -> str | None:
        """Apply one approved submission. Returns a skip reason, or None when applied."""
        if sub.get("stream") == "knowledge" and sub.get("kind") in GROUP_KINDS:
            # Group curation (CG-6b) goes to curation/*.csv, never to region.yml.
            reason = self.groups.submission(sub, credit)
            if reason is None:
                self.applied[("groups", f"knowledge:{sub['kind']}")] += 1
            return reason
        slug = sub.get("region")
        if not isinstance(slug, str) or not SLUG_RE.match(slug):
            return "invalid region"
        data = self.load(slug)
        if data is None:
            return "no regions/<slug>/region.yml for this region"
        if "sections" not in data:
            return "region has no placeholder sections"
        payload = payload_of(sub)
        if payload is None:
            return "payload is not an object"
        kind = sub.get("kind")
        stream = sub.get("stream")
        snapshot = copy.deepcopy(data)
        if stream == "confirm":
            reason = self._confirm(slug, data, kind, payload, credit)
        elif stream == "knowledge":
            reason = self._knowledge(slug, data, kind, payload, credit)
        else:
            return "unknown stream"
        if reason is None:
            reason = region_problem(data)
            if reason is not None:
                reason = f"would make region.yml invalid ({reason})"
        if reason is not None:
            self.docs[slug] = snapshot
            return reason
        self.changed.add(slug)
        self.applied[(slug, f"{stream}:{kind}")] += 1
        return None

    def _confirm(
        self, slug: str, data: dict, kind: Any, payload: dict, credit: str | None
    ) -> str | None:
        if kind not in CONFIRM_KINDS:
            return "unknown confirm kind"
        found = locate_item(data, clean_text(payload.get("item_id"), "item_id"), slug)
        if found is None:
            return "item_id does not match an item in region.yml"
        section, item = found
        if kind == "not_relevant":
            # Marked, never removed: item ids are positions, so removing one would shift later ids.
            item["status"] = "not_relevant"
            return None
        if kind == "correct":
            ok_name, name = optional(payload, "name", lambda v: clean_text(v, "name"))
            ok_url, url = optional(payload, "url", clean_url)
            if not (ok_name and ok_url):
                return "invalid name or url"
            if name is None and url is None:
                return "correction has no name or url"
            if name is not None:
                item["name"] = name
            if url is not None:
                item["url"] = url
        item["status"] = "confirmed"
        if credit:
            item["note"] = f"{item['note']} Confirmed by {credit}."
        return None

    def _knowledge(
        self, slug: str, data: dict, kind: Any, payload: dict, credit: str | None
    ) -> str | None:
        if kind == "correction":
            return self._correction(slug, data, payload, credit)
        if kind not in KNOWLEDGE_SECTIONS:
            return f"no region section for kind {kind!r}"
        section_id, item_kind = KNOWLEDGE_SECTIONS[kind]
        name = clean_text(payload.get("name"), "name")
        if name is None:
            return "invalid or missing name"
        ok_url, url = optional(payload, "url", clean_url)
        if not ok_url:
            return "invalid url (https only)"
        if url is None:
            if kind in REQUIRE_URL:
                return "missing url"
            url = ""
        ok_desc, description = optional(
            payload, "description", lambda v: clean_text(v, "description")
        )
        if not ok_desc:
            return "invalid description"
        note = (
            description
            or "Added from an ambassador submission; not yet confirmed by a local expert."
        )
        if credit:
            note += f" Suggested by {credit}."
        section = next(s for s in data["sections"] if s["id"] == section_id)
        for existing in section["items"]:
            if existing["name"].casefold() == name.casefold() and existing["url"] == url:
                return "duplicate of an existing item"
        section["items"].append(
            {"name": name, "url": url, "kind": item_kind, "status": "draft", "note": note}
        )
        return None

    def _correction(self, slug: str, data: dict, payload: dict, credit: str | None) -> str | None:
        found = locate_item(data, clean_text(payload.get("item_id"), "item_id"), slug)
        if found is None:
            return "item_id does not match an item in region.yml"
        ok_name, name = optional(payload, "name", lambda v: clean_text(v, "name"))
        ok_url, url = optional(payload, "url", clean_url)
        ok_desc, description = optional(
            payload, "description", lambda v: clean_text(v, "description")
        )
        if not (ok_name and ok_url and ok_desc):
            return "invalid correction field"
        if name is None and url is None and description is None:
            return "correction has no fields"
        _, item = found
        if name is not None:
            item["name"] = name
        if url is not None:
            item["url"] = url
        if description is not None:
            item["note"] = description
        item["status"] = "draft"
        if credit:
            item["note"] = f"{item['note']} Corrected by {credit}."
        return None

    def institution(self, item: dict) -> str | None:
        """Keep the newest approved institution per (region, domain). Identical rows are no-ops."""
        key = (item["region"], item["domain"])
        existing = self.additions.get(key)
        if existing is not None:
            if existing["ms"] > item["ms"]:
                return "older than the stored addition for this domain"
            if existing["row"] == item["row"]:
                return None
        self.additions[key] = {"ms": item["ms"], "row": item["row"]}
        self.additions_changed = True
        self.applied[(item["region"], "institution")] += 1
        return None

    def consensus(self, row: dict) -> str | None:
        """Keep the newest consensus answer per (region, case_id)."""
        slug = row.get("region")
        case_id = row.get("case_id")
        if not isinstance(slug, str) or not SLUG_RE.match(slug):
            return "invalid region"
        if not isinstance(case_id, str) or not CASE_ID_RE.match(case_id):
            return "invalid case_id"
        answer = clean_text(row.get("answer"), "answer")
        ok_value, correct_value = optional(
            row, "correct_value", lambda v: clean_text(v, "correct_value")
        )
        at = row.get("answered_at")
        if answer is None or not ok_value or not is_int(at) or not 0 <= at <= MAX_MS:
            return "invalid answer, correct_value or answered_at"
        key = (slug, case_id)
        existing = self.labels.get(key)
        if existing is not None and existing["ms"] > at:
            return "older than the stored answer"
        self.labels[key] = {
            "ms": at,
            "row": {
                "region": slug,
                "case_id": case_id,
                "answer": answer,
                "correct_value": correct_value or "",
                "answered_at_iso": iso_from_ms(at),
                "source": LABEL_SOURCE,
            },
        }
        self.labels_changed = True
        self.applied[(slug, "consensus")] += 1
        return None


# ---------------------------------------------------------------- group curation (CG-6b)
#
# Approved group_tag and group_suggest submissions never reach region.yml. Tags go to
# curation/group_tags.csv (docs/BFFP.md section 8.3), stated affiliations to
# curation/group_affiliations.csv and suggestions to curation/group_suggestions.csv. The checks
# mirror validateGroupTag and validateGroupSuggest in worker/src/groups.ts; the taxonomy comes from
# config/groups_taxonomy.yml through atlas.groups.schema.

GROUP_KINDS = frozenset({"group_tag", "group_suggest"})
GROUP_CREDIT_FALLBACK = "a local ambassador"
GROUP_STATUSES = ("ambassador_tagged", "cannot_determine")
GROUP_TIER1 = (
    "entity_type",
    "sector",
    "plastics_centrality",
    "primary_activities",
    "geographic_scope",
)
GROUP_TIER1_EVIDENCE = ("plastics_centrality", "primary_activities")
# Facets with their own evidence columns in group_tags.csv, in column order.
GROUP_EVIDENCE_FACETS = (
    "entity_type",
    "sector",
    "plastics_centrality",
    "primary_activities",
    "geographic_scope",
    "legal_form",
    "participation_in_science",
    "website_languages",
)
GROUP_EVIDENCE_PARTS = ("url", "accessed_at", "quote", "not_stated", "note")
# Facets an evidence entry may cite (worker EVIDENCE_FACETS).
GROUP_CITABLE_FACETS = (
    "entity_type",
    "sector",
    "plastics_centrality",
    "primary_activities",
    "geographic_scope",
    "places",
    "legal_form",
    "participation_in_science",
    "website_languages",
    "themes",
    "constituency",
    "stated_affiliations",
)
GROUP_SINGLE_FIELDS = (
    "entity_type",
    "sector",
    "plastics_centrality",
    "geographic_scope",
    "legal_form",
    "participation_in_science",
)
GROUP_LIST_BOUNDS = {
    "primary_activities": (1, 5),  # A4-D26
    "places": (0, 5),
    "website_languages": (0, 10),
    "themes": (0, 10),
    "constituency": (0, 10),
}
# Facet fields that must all be absent when not_an_organisation is true.
GROUP_FACET_FIELDS = (
    "entity_type",
    "sector",
    "plastics_centrality",
    "primary_activities",
    "geographic_scope",
    "places",
    "legal_form",
    "legal_form_note",
    "participation_in_science",
    "website_languages",
    "themes",
    "constituency",
    "stated_affiliations",
    "evidence",
)
GROUP_TAG_KEYS = frozenset(
    {
        "group_id",
        "status",
        "cannot_determine_reason",
        "not_an_organisation",
        "name_correction",
        "legal_form_note",
        "stated_affiliations",
        "evidence",
        "places",
        "themes",
        "constituency",
        "website_languages",
        *GROUP_FACET_FIELDS,
    }
)
GROUP_EVIDENCE_KEYS = frozenset({"facet", "url", "accessed_at", "quote", "not_stated", "note"})
GROUP_AFFILIATION_KEYS = frozenset({"target_name", "relation", "evidence"})
GROUP_CITATION_KEYS = frozenset({"url", "accessed_at", "quote"})
GROUP_SUGGEST_KEYS = frozenset({"name", "url", "country", "note"})
GROUP_TAG_MAX_CHARS = 12000
GROUP_TAG_COLUMNS = (
    "group_id",
    "status",
    "cannot_determine_reason",
    "not_an_organisation",
    "entity_type",
    "sector",
    "plastics_centrality",
    "primary_activities",
    "geographic_scope",
    "places",
    "legal_form",
    "legal_form_note",
    "participation_in_science",
    "website_languages",
    "themes",
    "constituency",
    *(
        f"evidence_{facet}_{part}"
        for facet in GROUP_EVIDENCE_FACETS
        for part in GROUP_EVIDENCE_PARTS
    ),
    "tagged_at",
    "credit",
)
GROUP_AFFILIATION_COLUMNS = (
    "group_id",
    "target_name",
    "relation",
    "evidence_url",
    "evidence_accessed_at",
    "evidence_quote",
)
GROUP_SUGGESTION_COLUMNS = ("name", "url", "country", "note", "suggested_at")
GROUP_NAME_CORRECTION_COLUMNS = ("group_id", "name", "submitted_at")
GROUP_ID_RE = re.compile(r"cg_[0-9a-f]{16}")
GROUP_PLACE_RE = re.compile(r"[A-Z]{2}(-[A-Z0-9]{1,3})?")
GROUP_LANGUAGE_RE = re.compile(r"[a-z]{2}")
GROUP_COUNTRY_RE = re.compile(r"[A-Za-z]{2}")
GROUP_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def bounded_text(value: Any, limit: int) -> str | None:
    """Trimmed text of at most ``limit`` characters, without control characters or HTML."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > limit or CONTROL_OR_HTML_RE.search(text):
        return None
    return text


def web_url(value: Any) -> str | None:
    """An http or https URL (group websites and citations), no credentials, no whitespace."""
    text = bounded_text(value, 500)
    if text is None or re.search(r"\s", text):
        return None
    try:
        parts = urllib.parse.urlsplit(text)
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    if parts.username or parts.password:
        return None
    return text


def iso_day(value: Any) -> str | None:
    """A real calendar date written YYYY-MM-DD, or None."""
    if not isinstance(value, str) or not GROUP_DATE_RE.fullmatch(value):
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def _one_of(values: tuple[str, ...]) -> Callable[[Any], str | None]:
    return lambda value: value if isinstance(value, str) and value in values else None


def _matching(pattern: re.Pattern[str]) -> Callable[[Any], str | None]:
    return lambda value: value if isinstance(value, str) and pattern.fullmatch(value) else None


def _theme(value: Any) -> str | None:
    text = bounded_text(value, 80)
    # ';' separates list values in the CSV, so a theme cannot contain one.
    return None if text is None or ";" in text else text


def text_list(
    value: Any, low: int, high: int, item: Callable[[Any], str | None]
) -> list[str] | None:
    """A list of ``low`` to ``high`` distinct items, each accepted by ``item``, or None."""
    if not isinstance(value, list) or not low <= len(value) <= high:
        return None
    out: list[str] = []
    for raw in value:
        text = item(raw)
        if text is None or text in out:
            return None
        out.append(text)
    return out


def _citation(value: Mapping[str, Any], not_stated_allowed: bool) -> dict | None:
    """url, accessed_at and exactly one of a quote (25 words at most) or not_stated true."""
    url = web_url(value.get("url"))
    accessed = iso_day(value.get("accessed_at"))
    stated = value.get("not_stated")
    if url is None or accessed is None or (stated is not None and not isinstance(stated, bool)):
        return None
    if stated is True:
        if not not_stated_allowed or value.get("quote") is not None:
            return None
        return {"url": url, "accessed_at": accessed, "quote": None, "not_stated": True}
    quote = bounded_text(value.get("quote"), 400)
    if quote is None or len(quote.split()) > 25:
        return None
    return {"url": url, "accessed_at": accessed, "quote": quote, "not_stated": False}


def _evidence_entry(value: Any) -> dict | None:
    if not isinstance(value, dict) or set(value) - GROUP_EVIDENCE_KEYS:
        return None
    facet = value.get("facet")
    cite = _citation(value, True)
    if not isinstance(facet, str) or facet not in GROUP_CITABLE_FACETS or cite is None:
        return None
    note = value.get("note")
    if note is not None:
        note = bounded_text(note, 200)
        if note is None:
            return None
    return {"facet": facet, **cite, "note": note}


def _affiliation(value: Any, relations: tuple[str, ...]) -> dict | None:
    if not isinstance(value, dict) or set(value) - GROUP_AFFILIATION_KEYS:
        return None
    name = bounded_text(value.get("target_name"), 200)
    relation = _one_of(relations)(value.get("relation"))
    evidence = value.get("evidence")
    if name is None or relation is None or not isinstance(evidence, dict):
        return None
    if set(evidence) - GROUP_CITATION_KEYS:
        return None
    cite = _citation(evidence, False)  # affiliations never accept not_stated (V11)
    if cite is None:
        return None
    return {"target_name": name, "relation": relation, "evidence": cite}


def _list_items(taxonomy: Mapping[str, tuple[str, ...]]) -> dict[str, Callable[[Any], str | None]]:
    return {
        "primary_activities": _one_of(taxonomy["primary_activities"]),
        "places": _matching(GROUP_PLACE_RE),
        "website_languages": _matching(GROUP_LANGUAGE_RE),
        "themes": _theme,
        "constituency": _one_of(taxonomy["constituency"]),
    }


def _bad(field: str) -> tuple[None, str]:
    return None, f"invalid {field}"


def clean_group_tag(
    payload: Mapping[str, Any], taxonomy: Mapping[str, tuple[str, ...]]
) -> tuple[dict | None, str | None]:
    """Return (normalised tag, None) or (None, skip reason). Mirrors validateGroupTag (worker)."""
    unknown = sorted(set(payload) - GROUP_TAG_KEYS)
    if unknown:
        return None, f"unknown field {unknown[0]}"
    group_id = payload.get("group_id")
    status = payload.get("status")
    if not isinstance(group_id, str) or not GROUP_ID_RE.fullmatch(group_id):
        return _bad("group_id")
    if status not in GROUP_STATUSES:
        return _bad("status")
    out: dict[str, Any] = {"group_id": group_id, "status": status}

    reason = payload.get("cannot_determine_reason")
    if status == "cannot_determine":
        if reason not in taxonomy["cannot_determine_reason"]:
            return _bad("cannot_determine_reason")
        out["cannot_determine_reason"] = reason
    elif reason is not None:
        return _bad("cannot_determine_reason")

    for key in GROUP_SINGLE_FIELDS:
        value = payload.get(key)
        if value is None:
            continue
        if value not in taxonomy[key]:
            return _bad(key)
        out[key] = value
    if status == "ambassador_tagged" and out.get("plastics_centrality") == "cannot_determine":
        return _bad("plastics_centrality")  # V2

    if payload.get("legal_form_note") is not None:
        note = bounded_text(payload["legal_form_note"], 200)
        if note is None:
            return _bad("legal_form_note")
        out["legal_form_note"] = note

    for key, item in _list_items(taxonomy).items():
        if payload.get(key) is None:
            continue
        low, high = GROUP_LIST_BOUNDS[key]
        values = text_list(payload[key], low, high, item)
        if values is None:
            return _bad(key)
        out[key] = values

    # V6: participation other than not_applicable needs research_monitoring among the activities.
    if payload.get("participation_in_science") is not None:
        activities = out.get("primary_activities", [])
        if out["participation_in_science"] != "not_applicable" and (
            "research_monitoring" not in activities
        ):
            return _bad("participation_in_science")

    if payload.get("stated_affiliations") is not None:
        items = payload["stated_affiliations"]
        if not isinstance(items, list) or len(items) > 10:
            return _bad("stated_affiliations")
        parsed = [_affiliation(item, taxonomy["relation"]) for item in items]
        if any(entry is None for entry in parsed):
            return _bad("stated_affiliations")
        out["stated_affiliations"] = parsed

    if payload.get("evidence") is not None:
        items = payload["evidence"]
        if not isinstance(items, list) or len(items) > 15:
            return _bad("evidence")
        parsed = [_evidence_entry(item) for item in items]
        if any(entry is None for entry in parsed):
            return _bad("evidence")
        out["evidence"] = parsed

    if payload.get("not_an_organisation") is not None:
        flag = payload["not_an_organisation"]
        if not isinstance(flag, bool):
            return _bad("not_an_organisation")
        if flag:
            facet = next((k for k in GROUP_FACET_FIELDS if payload.get(k) is not None), None)
            if facet is not None:
                return _bad(facet)
        out["not_an_organisation"] = flag

    if payload.get("name_correction") is not None:
        name = bounded_text(payload["name_correction"], 200)
        if name is None or len(name) < 2 or EMAIL_RE.search(name):
            return _bad("name_correction")
        out["name_correction"] = name

    # Tier 1 (V2, V4): an ambassador_tagged group has the five core facets and evidence for two.
    if status == "ambassador_tagged":
        for key in GROUP_TIER1:
            if key not in out:
                return _bad(key)
        cited = {entry["facet"] for entry in out.get("evidence", [])}
        if any(facet not in cited for facet in GROUP_TIER1_EVIDENCE):
            return _bad("evidence")

    stored = json.dumps(out, ensure_ascii=False)
    if EMAIL_RE.search(stored):
        return _bad("email")
    if len(stored) > GROUP_TAG_MAX_CHARS:
        return _bad("payload")
    return out, None


def clean_group_suggest(payload: Mapping[str, Any]) -> tuple[dict | None, str | None]:
    """Return (suggestion, None) or (None, skip reason). Mirrors validateGroupSuggest (worker)."""
    unknown = sorted(set(payload) - GROUP_SUGGEST_KEYS)
    if unknown:
        return None, f"unknown field {unknown[0]}"
    name = bounded_text(payload.get("name"), 200)
    url = web_url(payload.get("url"))
    if name is None or url is None:
        return None, "invalid name or url"
    country = payload.get("country")
    if country is not None:
        if not isinstance(country, str) or not GROUP_COUNTRY_RE.fullmatch(country):
            return _bad("country")
        country = country.upper()
    note = payload.get("note")
    if note is not None:
        note = bounded_text(note, 1000)
        if note is None:
            return _bad("note")
    if any(EMAIL_RE.search(text) for text in (name, url, note or "")):
        return _bad("email")
    return {"name": name, "url": url, "country": country or "", "note": note or ""}, None


def iso_day_of(at: int) -> str:
    return datetime.fromtimestamp(at / 1000, tz=UTC).date().isoformat()


def group_tag_row(tag: Mapping[str, Any], tagged_at: str, credit: str) -> tuple[dict, int]:
    """One group_tags.csv row. Returns (row, evidence entries the CSV cannot carry)."""
    row = dict.fromkeys(GROUP_TAG_COLUMNS, "")
    row["group_id"] = tag["group_id"]
    row["status"] = tag["status"]
    row["cannot_determine_reason"] = tag.get("cannot_determine_reason", "")
    if "not_an_organisation" in tag:
        row["not_an_organisation"] = "true" if tag["not_an_organisation"] else "false"
    for key in GROUP_SINGLE_FIELDS:
        row[key] = tag.get(key, "")
    for key in GROUP_LIST_BOUNDS:
        row[key] = ";".join(tag[key]) if key in tag else ""
    row["legal_form_note"] = tag.get("legal_form_note", "")
    evidence = tag.get("evidence", [])
    carried = 0
    for facet in GROUP_EVIDENCE_FACETS:
        entry = next((e for e in evidence if e["facet"] == facet), None)
        if entry is None:
            continue
        carried += 1
        row[f"evidence_{facet}_url"] = entry["url"]
        row[f"evidence_{facet}_accessed_at"] = entry["accessed_at"]
        row[f"evidence_{facet}_quote"] = entry["quote"] or ""
        row[f"evidence_{facet}_not_stated"] = "true" if entry["not_stated"] else "false"
        row[f"evidence_{facet}_note"] = entry["note"] or ""
    row["tagged_at"] = tagged_at
    row["credit"] = credit
    return row, len(evidence) - carried


def affiliation_rows(tag: Mapping[str, Any]) -> list[dict]:
    return [
        {
            "group_id": tag["group_id"],
            "target_name": item["target_name"],
            "relation": item["relation"],
            "evidence_url": item["evidence"]["url"],
            "evidence_accessed_at": item["evidence"]["accessed_at"],
            "evidence_quote": item["evidence"]["quote"],
        }
        for item in tag.get("stated_affiliations", [])
    ]


class GroupStore:
    """Group tags, affiliations and suggestions for one export run; nothing is written yet.

    ``tags`` maps group_id to {"ms", "row"}; the newest approval wins and replaces the group's
    affiliations too. ``suggestions`` maps url to {"ms", "row"}, newest wins. ``name_corrections``
    maps group_id to {"ms", "row"}, newest wins; only a tag that carries a name_correction sets it.
    """

    def __init__(
        self,
        tags: dict[str, dict],
        affiliations: dict[str, list[dict]],
        suggestions: dict[str, dict],
        taxonomy: Mapping[str, tuple[str, ...]],
        name_corrections: dict[str, dict] | None = None,
    ) -> None:
        self.tags = tags
        self.affiliations = affiliations
        self.suggestions = suggestions
        self.taxonomy = taxonomy
        self.name_corrections = name_corrections if name_corrections is not None else {}
        self.dirty: set[str] = set()

    def submission(self, sub: dict, credit: str | None) -> str | None:
        payload = payload_of(sub)
        if payload is None:
            return "payload is not an object"
        at = sub["decided_at"]
        if not 0 <= at <= MAX_MS:
            return "invalid decided_at"
        if sub.get("kind") == "group_tag":
            return self._tag(payload, at, credit)
        return self._suggest(payload, at)

    def _tag(self, payload: Mapping[str, Any], at: int, credit: str | None) -> str | None:
        tag, reason = clean_group_tag(payload, self.taxonomy)
        if tag is None:
            return reason
        group_id = tag["group_id"]
        existing = self.tags.get(group_id)
        if existing is not None and existing["ms"] > at:
            return "older than the stored tag for this group"
        # Credit only when the export gives a public name (credit_name is null when credit is off).
        name = credit if credit and not EMAIL_RE.search(credit) else GROUP_CREDIT_FALLBACK
        row, dropped = group_tag_row(tag, iso_day_of(at), name)
        if dropped:
            print(f"note: group {group_id}: {dropped} evidence entr(ies) not carried to the CSV")
        self.tags[group_id] = {"ms": at, "row": row}
        self.affiliations[group_id] = affiliation_rows(tag)
        self.dirty.update({"tags", "affiliations"})
        if "name_correction" in tag:
            name_row = {
                "group_id": group_id,
                "name": tag["name_correction"],
                "submitted_at": iso_day_of(at),
            }
            known = self.name_corrections.get(group_id)
            if known is None or known["ms"] <= at:
                self.name_corrections[group_id] = {"ms": at, "row": name_row}
                self.dirty.add("names")
        return None

    def _suggest(self, payload: Mapping[str, Any], at: int) -> str | None:
        suggestion, reason = clean_group_suggest(payload)
        if suggestion is None:
            return reason
        url = suggestion["url"]
        existing = self.suggestions.get(url)
        if existing is not None and existing["ms"] > at:
            return "older than the stored suggestion for this url"
        row = {**suggestion, "suggested_at": iso_day_of(at)}
        self.suggestions[url] = {"ms": at, "row": row}
        self.dirty.add("suggestions")
        return None


def _csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [{k: v or "" for k, v in row.items() if k} for row in csv.DictReader(handle)]


def read_group_tags(path: Path) -> dict[str, dict]:
    tags: dict[str, dict] = {}
    for row in _csv_rows(path):
        if not row.get("group_id"):
            continue
        try:
            ms = ms_from_iso(f"{row['tagged_at']}T00:00:00Z")
        except (KeyError, TypeError, ValueError):
            raise ExportError(f"{path.name} has a row with a bad tagged_at") from None
        tags[row["group_id"]] = {
            "ms": ms,
            "row": {col: row.get(col, "") for col in GROUP_TAG_COLUMNS},
        }
    return tags


def read_group_affiliations(path: Path) -> dict[str, list[dict]]:
    affiliations: dict[str, list[dict]] = {}
    for row in _csv_rows(path):
        if row.get("group_id"):
            entry = {col: row.get(col, "") for col in GROUP_AFFILIATION_COLUMNS}
            affiliations.setdefault(row["group_id"], []).append(entry)
    return affiliations


def read_group_suggestions(path: Path) -> dict[str, dict]:
    suggestions: dict[str, dict] = {}
    for row in _csv_rows(path):
        if not row.get("url"):
            continue
        try:
            ms = ms_from_iso(f"{row['suggested_at']}T00:00:00Z")
        except (KeyError, TypeError, ValueError):
            raise ExportError(f"{path.name} has a row with a bad suggested_at") from None
        suggestions[row["url"]] = {
            "ms": ms,
            "row": {col: row.get(col, "") for col in GROUP_SUGGESTION_COLUMNS},
        }
    return suggestions


def read_group_name_corrections(path: Path) -> dict[str, dict]:
    corrections: dict[str, dict] = {}
    for row in _csv_rows(path):
        if not row.get("group_id"):
            continue
        try:
            ms = ms_from_iso(f"{row['submitted_at']}T00:00:00Z")
        except (KeyError, TypeError, ValueError):
            raise ExportError(f"{path.name} has a row with a bad submitted_at") from None
        corrections[row["group_id"]] = {
            "ms": ms,
            "row": {col: row.get(col, "") for col in GROUP_NAME_CORRECTION_COLUMNS},
        }
    return corrections


def write_group_name_corrections(path: Path, corrections: dict[str, dict]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=GROUP_NAME_CORRECTION_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for group_id in sorted(corrections):
        writer.writerow(corrections[group_id]["row"])
    write_text(path, buffer.getvalue())


def write_group_tags(path: Path, tags: dict[str, dict]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=GROUP_TAG_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for group_id in sorted(tags):
        writer.writerow(tags[group_id]["row"])
    write_text(path, buffer.getvalue())


def write_group_affiliations(path: Path, affiliations: dict[str, list[dict]]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=GROUP_AFFILIATION_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for group_id in sorted(affiliations):
        writer.writerows(affiliations[group_id])
    write_text(path, buffer.getvalue())


def write_group_suggestions(path: Path, suggestions: dict[str, dict]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=GROUP_SUGGESTION_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for url in sorted(suggestions):
        writer.writerow(suggestions[url]["row"])
    write_text(path, buffer.getvalue())


# ---------------------------------------------------------------- I/O


def read_state(path: Path) -> tuple[int, list[int]]:
    if not path.exists():
        return 0, []
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ExportError(f"{path.name} is not valid JSON") from exc
    since = state.get("since")
    if not is_int(since) or since < 0:
        raise ExportError("state 'since' must be a non-negative integer")
    ids = state.get("boundary_ids", [])
    if not isinstance(ids, list) or not all(is_int(i) for i in ids):
        raise ExportError("state 'boundary_ids' must be a list of integers")
    return since, ids


def read_labels(path: Path) -> dict[tuple[str, str], dict]:
    labels: dict[tuple[str, str], dict] = {}
    if not path.exists():
        return labels
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not (row.get("region") and row.get("case_id")):
                continue
            try:
                ms = ms_from_iso(row["answered_at_iso"])
            except (KeyError, TypeError, ValueError):
                raise ExportError(f"{path.name} has a row with a bad answered_at_iso") from None
            labels[(row["region"], row["case_id"])] = {
                "ms": ms,
                "row": {col: row.get(col, "") or "" for col in LABEL_COLUMNS},
            }
    return labels


def fetch_export(api_url: str, since: int, token: str) -> dict:
    """GET the approved export. The token is sent only in the header and never echoed."""
    if not api_url.startswith("https://"):
        raise ExportError("--api-url must be https")
    query = urllib.parse.urlencode({"since": since})
    request = urllib.request.Request(
        f"{api_url.rstrip('/')}/export/approved?{query}",
        # Cloudflare's browser check answers 403 to the default Python-urllib agent before the
        # Worker runs, so the job names itself.
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "plastiverse-export-job/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise ExportError(f"export request failed with HTTP {exc.code}") from None
    except (urllib.error.URLError, OSError):
        raise ExportError("export request failed (network error)") from None
    try:
        data = json.loads(body)
    except ValueError:
        raise ExportError("export response is not JSON") from None
    if not isinstance(data, dict) or data.get("ok") is not True:
        raise ExportError("export response is not ok")
    return data


def load_export(args: argparse.Namespace, since: int) -> dict:
    if args.input:
        try:
            data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ExportError(f"cannot read --input: {type(exc).__name__}") from None
        if not isinstance(data, dict):
            raise ExportError("--input is not an export object")
        return data
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        raise ExportError(f"{TOKEN_ENV} is not set")
    return fetch_export(args.api_url, since, token)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    os.replace(tmp, path)


def write_labels(path: Path, labels: dict[tuple[str, str], dict]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=LABEL_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for entry in labels.values():
        writer.writerow(entry["row"])
    write_text(path, buffer.getvalue())


def read_additions(path: Path) -> dict[tuple[str, str], dict]:
    additions: dict[tuple[str, str], dict] = {}
    if not path.exists():
        return additions
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not (row.get("region") and row.get("domain")):
                continue
            try:
                ms = ms_from_iso(row["approved_at_iso"])
            except (KeyError, TypeError, ValueError):
                raise ExportError(f"{path.name} has a row with a bad approved_at_iso") from None
            additions[(row["region"], row["domain"])] = {
                "ms": ms,
                "row": {col: row.get(col, "") or "" for col in ADDITION_COLUMNS},
            }
    return additions


def write_additions(path: Path, additions: dict[tuple[str, str], dict]) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=ADDITION_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for key in sorted(additions):
        writer.writerow(additions[key]["row"])
    write_text(path, buffer.getvalue())


def summary_markdown(applier: Applier, since_before: int, since_after: int) -> str:
    rows = sorted(applier.applied.items())
    lines = [
        "Approved ambassador contributions, exported since "
        f"{since_before} (new watermark {since_after}). Counts only; review each change.",
        "",
        "| Region | Kind | Applied |",
        "| --- | --- | ---: |",
    ]
    lines += [f"| {slug} | {kind} | {count} |" for (slug, kind), count in rows]
    if not rows:
        lines.append("| (none) | | 0 |")
    lines += [
        "",
        f"Skipped records: {len(applier.skipped)} (listed in the job log by id, no personal data).",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- main


def run(args: argparse.Namespace) -> int:
    since, boundary = read_state(args.since_file)
    export = load_export(args, since)

    labels = read_labels(args.labels_file)
    additions = read_additions(args.additions_file)
    groups = GroupStore(
        read_group_tags(args.group_tags_file),
        read_group_affiliations(args.group_affiliations_file),
        read_group_suggestions(args.group_suggestions_file),
        load_taxonomy(),
        read_group_name_corrections(args.group_name_corrections_file),
    )
    applier = Applier(args.regions_dir, labels, additions, groups)
    times: list[int] = []
    sub_times: list[tuple[int, int | None]] = []

    for sub in export.get("submissions") or []:
        if not isinstance(sub, dict):
            continue
        sub_id = sub.get("id") if is_int(sub.get("id")) else None
        label = str(sub_id) if sub_id is not None else "?"
        at = sub.get("decided_at")
        if not is_int(at):
            applier.skip(label, "invalid decided_at")
            continue
        times.append(at)
        sub_times.append((at, sub_id))
        if at < since or (at == since and sub_id in boundary):
            continue
        credit = clean_text(sub.get("credit_name"), "name")
        reason = applier.submission(sub, credit)
        if reason is not None:
            applier.skip(label, reason)
            print(f"skip submission {label}: {reason}")

    for inst in export.get("institutions") or []:
        if not isinstance(inst, dict):
            continue
        label = str(inst.get("id")) if is_int(inst.get("id")) else "?"
        at = inst.get("decided_at")
        if not is_int(at) or not 0 <= at <= MAX_MS:
            applier.skip(label, "invalid decided_at")
            continue
        times.append(at)
        if at < since:
            continue
        item, reason = clean_institution(inst, at, args.regions_dir)
        if item is not None:
            reason = applier.institution(item)
        if reason is not None:
            applier.skip(label, reason)
            print(f"skip institution {label}: {reason}")

    for row in export.get("case_answers") or []:
        if not isinstance(row, dict):
            continue
        at = row.get("answered_at")
        if not is_int(at):
            applier.skip("case", "invalid answered_at")
            continue
        times.append(at)
        if at < since:
            continue
        reason = applier.consensus(row)
        if reason is not None:
            applier.skip("case", reason)
            print(f"skip case answer ({row.get('region')}): {reason}")

    newest = max([since, *times])
    new_boundary = {sid for at, sid in sub_times if at == newest and sid is not None}
    if newest == since:
        new_boundary |= set(boundary)
    new_state = {"since": newest, "boundary_ids": sorted(new_boundary)}

    print(
        f"submissions in export: {len(export.get('submissions') or [])}, "
        f"case answers: {len(export.get('case_answers') or [])}"
    )
    for (slug, kind), count in sorted(applier.applied.items()):
        print(f"applied {count} x {slug} {kind}")
    print(f"skipped: {len(applier.skipped)}; watermark {since} -> {newest}")

    if args.dry_run:
        print("dry run: nothing written")
        return 0

    # Build every region text first so a rendering problem writes nothing.
    texts = {}
    for slug in sorted(applier.changed):
        original_text, original = applier.original[slug]
        texts[applier.region_path(slug)] = render_region(
            original_text, original, applier.docs[slug]
        )
    for path, text in texts.items():
        write_text(path, text)
    if applier.labels_changed:
        write_labels(args.labels_file, applier.labels)
    if applier.additions_changed:
        write_additions(args.additions_file, applier.additions)
    if "tags" in groups.dirty:
        write_group_tags(args.group_tags_file, groups.tags)
    if "affiliations" in groups.dirty:
        write_group_affiliations(args.group_affiliations_file, groups.affiliations)
    if "suggestions" in groups.dirty:
        write_group_suggestions(args.group_suggestions_file, groups.suggestions)
    if "names" in groups.dirty:
        write_group_name_corrections(args.group_name_corrections_file, groups.name_corrections)
    if args.summary_file:
        write_text(args.summary_file, summary_markdown(applier, since, newest))
    write_text(args.since_file, json.dumps(new_state, indent=2) + "\n")
    labels_state = "updated" if applier.labels_changed else "unchanged"
    additions_state = "updated" if applier.additions_changed else "unchanged"
    print(
        f"wrote {len(texts)} region file(s); labels {labels_state}; "
        f"institution additions {additions_state}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--since-file", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--input", help="saved export JSON (offline); skips the API call")
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--regions-dir", type=Path, default=DEFAULT_REGIONS)
    parser.add_argument("--labels-file", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--additions-file", type=Path, default=DEFAULT_ADDITIONS)
    parser.add_argument("--group-tags-file", type=Path, default=DEFAULT_GROUP_TAGS)
    parser.add_argument("--group-affiliations-file", type=Path, default=DEFAULT_GROUP_AFFILIATIONS)
    parser.add_argument("--group-suggestions-file", type=Path, default=DEFAULT_GROUP_SUGGESTIONS)
    parser.add_argument(
        "--group-name-corrections-file", type=Path, default=DEFAULT_GROUP_NAME_CORRECTIONS
    )
    parser.add_argument("--summary-file", type=Path, help="write a counts-only markdown summary")
    parser.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except ExportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: file operation failed ({type(exc).__name__}); nothing was marked exported")
        return 1


if __name__ == "__main__":
    sys.exit(main())
