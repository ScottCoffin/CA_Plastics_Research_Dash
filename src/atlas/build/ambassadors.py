"""Ambassador data per region (AMB-1 step 1, docs/AMBASSADORS_SPEC.md sections 2 and 4).

Two public files per region folder, both built offline from ignored inputs and committed:

- ``ambassador_institutions.json`` (schema ``amb-v1``): the eligible institutions (institutions
  only, no people) with their registrable domains. An institution is eligible when at least
  ``MIN_WORKS`` plastics works in the region's corpus have an author there and its OpenAlex type
  is one of ``ELIGIBLE_TYPES``.
- ``ambassador_cases.json`` (schema ``amb-cases-v1``): case queues for review stream A. Each case
  carries public evidence only (titles, institution names, place names, short affiliation strings).
  Case ids hash the region, kind and entity key, so answers survive rebuilds.

Region inputs follow the registry predicate: a region with an ``institution_registry`` uses the
curated corpus (authorships whose ``ca_basis`` is one of ``ca_basis_values``); a region with
``country_codes`` uses the global partition (an authorship institution whose country is the code).

Domains come from the domain cache under ``data/interim/ambassador_domains`` (ignored), which only
--fetch-domains fills (OpenAlex institution records and ROR v2 records; the only network path).
Precedence: ROR domains, then the OpenAlex homepage host, then ROR website links. Each host is
reduced to its registrable domain with the suffix table below; subdomains are accepted. Free-mail
and generic domains are always refused. Owner overrides live in
``regions/<slug>/ambassador_domains.csv``.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pyarrow.parquet as pq
import yaml

from atlas.ingest.global_partition import raw_page_paths
from atlas.ingest.openalex import OPENALEX_BASE, _request_json
from atlas.ingest.openalex import chunks as openalex_chunks
from atlas.regions.registry import REPO_ROOT, Region
from atlas.regions.scope import registry_row_matcher
from atlas.util.budget import resolve_openalex_budget
from atlas.util.cost import ApiCostLogger

INSTITUTIONS_SCHEMA = "amb-v1"
CASES_SCHEMA = "amb-cases-v1"
MIN_WORKS = 3
ELIGIBLE_TYPES = ("education", "government", "nonprofit", "facility")
# Companies with this many works get a type check (they may be mislabelled research bodies).
MANY_WORKS = 10
TYPE_OPTIONS = (*ELIGIBLE_TYPES, "company", "healthcare", "archive", "other", "unsure")
YES_NO_OPTIONS = ("agree", "disagree", "unsure")
CASE_CAPS = {
    "institution_in_region": 200,
    "institution_type": 100,
    "local_language_relevance": 200,
}
CASE_KINDS = (
    "institution_in_region",
    "institution_type",
    "local_language_relevance",
    "local_terms",
)
RULE = (
    "An institution is eligible when at least 3 plastics works in this region's corpus have an "
    "author at it, and its OpenAlex type is education, government, nonprofit or facility. "
    "Domains come from the institution's homepage and ROR website, reduced to the registrable "
    "domain (the last two labels, or three under a two-level suffix such as ca.gov); subdomains "
    "are accepted. Free-mail and generic domains are never listed. Owner overrides add or remove "
    "domains. An institution with no known domain is listed with needs_domain true. An institution "
    "an owner or region lead approved as a proposal is listed with its domain, without the works "
    "minimum (source approved_proposal)."
)
OVERRIDE_COLUMNS = ("institution_id", "domain", "action", "note")
ADDITIONS_CSV = Path("curation/ambassador_institution_additions.csv")
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
OPENALEX_SOURCE = "openalex"
_ADDITION_SLUG = re.compile(r"[a-z][a-z0-9-]{0,40}")
_ADDITION_NAME_BAD = re.compile(r"[<>\x00-\x1f\x7f]")
_UTC_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
OVERRIDE_ACTIONS = ("add", "remove")
GLOBAL_WORKS = Path("data/processed/global/works.parquet")
NORMALIZED_AUTHORSHIPS = Path("data/processed/normalized/authorships.parquet")
NORMALIZED_WORKS = Path("data/processed/normalized/works.parquet")
RAW_DIR = Path("data/raw")
RAW_PAGES = Path("data/raw/openalex_global")

FREE_MAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "msn.com",
        "yahoo.com",
        "proton.me",
        "protonmail.com",
        "pm.me",
        "icloud.com",
        "me.com",
        "mac.com",
        "aol.com",
        "mail.com",
        "qq.com",
        "163.com",
        "126.com",
        "web.de",
        "t-online.de",
        "yandex.ru",
        "zoho.com",
        "gmx.net",
    }
)
# Any domain whose first label is one of these is refused (gmx.de, yahoo.co.uk, outlook.fr, ...).
FREE_MAIL_LABELS = frozenset({"gmx", "yahoo", "hotmail", "outlook", "live"})
# Two-level public suffixes; a registrable domain keeps one label more under them.
TWO_LEVEL_SUFFIXES = frozenset({"ca.gov", "ac.uk", "gov.uk", "co.uk", "org.uk", "edu.au", "gov.au"})

_HOST_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_ROR_DUMP_NAME = re.compile(r"(?:^|[^a-z])ror(?:[^a-z]|$)")
_OPENALEX_INSTITUTION = re.compile(r"^I\d+$")
_TEXT_LIMIT = 160
_TITLE_LIMIT = 1000

# Keys that must never appear in public ambassador outputs (people, contact, text bodies).
FORBIDDEN_KEYS = frozenset(
    {
        "email",
        "emails",
        "orcid",
        "contact",
        "author",
        "authors",
        "author_id",
        "author_name",
        "raw_author_name",
        "affiliation",
        "raw_affiliation",
        "abstract",
        "abstract_inverted_index",
    }
)
INSTITUTION_KEYS = frozenset(
    {
        "id",
        "name",
        "type",
        "works",
        "domains",
        "needs_domain",
        "ror",
        "acronyms",
        "aliases",
        "source",
    }
)
CASE_KEYS = frozenset({"case_id", "kind", "question", "evidence", "current_value", "options"})
INSTITUTIONS_TOP_KEYS = frozenset(
    {
        "schema",
        "generated_at",
        "region",
        "rule",
        "min_works",
        "eligible_types",
        "trusted_email_suffixes",
        "institutions",
    }
)
TRUSTED_SUFFIXES_KEY = "trusted_email_suffixes"
# Lower-case labels joined by dots, no leading or trailing dot ("ca.gov", "edu").
_SUFFIX_RE = re.compile(
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*"
)


# --- text and domain helpers ----------------------------------------------------------------


def _short(value: object) -> str:
    """Compact OpenAlex or ROR id: the last path segment of a URL, or the value itself."""
    text = str(value or "").strip().rstrip("/")
    return text.rsplit("/", 1)[-1] if text else ""


def _country(value: object) -> str:
    return str(value or "").strip().upper()


def public_text(value: object, limit: int = _TEXT_LIMIT) -> str | None:
    """Collapsed, truncated text for public evidence; None when empty or when it contains '@'."""
    text = " ".join(str(value or "").split())
    if not text or "@" in text:
        return None
    return text[:limit].rstrip()


def host_of(value: object) -> str | None:
    """Lower-case host of a URL or bare domain (no port, user info or leading ``www.``)."""
    text = str(value or "").strip()
    if not text:
        return None
    if "://" not in text:
        text = "https://" + text
    try:
        host = urlsplit(text).hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def registrable_domain(value: object) -> str | None:
    """The registrable domain of a URL or host, or None when it is not a domain.

    The last two labels, or the last three under a two-level suffix (``waterboards.ca.gov``).
    ``ca.gov`` itself and bare suffixes return None.
    """
    host = host_of(value)
    if host is None or not _HOST_RE.match(host):
        return None
    labels = host.split(".")
    size = 3 if ".".join(labels[-2:]) in TWO_LEVEL_SUFFIXES else 2
    if len(labels) < size:
        return None
    return ".".join(labels[-size:])


def is_free_mail(domain: str) -> bool:
    """True for free-mail and generic mail domains, which never qualify an institution."""
    return domain in FREE_MAIL_DOMAINS or domain.split(".", 1)[0] in FREE_MAIL_LABELS


# --- inputs ---------------------------------------------------------------------------------


@dataclass
class Facts:
    """What the inputs say about one institution in a region's corpus."""

    name: str = ""
    type: str | None = None
    ror: str = ""
    hosts: set[str] = field(default_factory=set)
    works: set[str] = field(default_factory=set)
    in_region: bool = False
    signals: set[str] = field(default_factory=set)
    affiliations: set[str] = field(default_factory=set)
    raw: set[str] = field(default_factory=set)  # raw affiliation strings, read for acronyms only
    acronyms: set[str] = field(default_factory=set)

    def fill(self, name: str, type_: str | None, ror: str, hosts: Iterable[object]) -> None:
        if not self.name and name:
            self.name = name
        if self.type is None and type_:
            self.type = type_
        if not self.ror and ror:
            self.ror = ror
        self.hosts.update(str(h) for h in hosts if h)


@dataclass
class RegionCorpus:
    facts: dict[str, Facts]
    local_titles: dict[str, str | None]  # work id -> title, for works with a region author
    languages: dict[str, str]  # work id -> language code from the global partition
    terms: list[dict[str, str]]  # local search terms from regions/<slug>/region.yml


@dataclass(frozen=True)
class Override:
    action: str
    domain: str
    note: str


# A name followed by a bracketed acronym, as in "Norwegian Institute for Water Research (NIVA)".
_NAME_ACRONYM = re.compile(r"([^(),]+?)\s*\(([A-Z][A-Z0-9&]{1,11})\)")


def _fold_name(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def affiliation_acronyms(raw_strings: Iterable[str], name: str) -> set[str]:
    """Acronyms that raw affiliation strings give to an institution of this exact name."""
    target = _fold_name(name)
    found: set[str] = set()
    for raw in raw_strings:
        for match in _NAME_ACRONYM.finditer(raw):
            if _fold_name(match.group(1)) == target:
                found.add(match.group(2))
    return found


def prefix_aliases(name: str, rules: Sequence[tuple[str, str]]) -> set[str]:
    """Aliases from a region's naming rules: (prefix, alias prefix) pairs in region.yml.

    A rule such as ("Some University, ", "SU ") turns "Some University, Campus" into "SU Campus".
    Region names live in the region config, not in this module (region-name ratchet).
    """
    found: set[str] = set()
    for prefix, alias_prefix in rules:
        if prefix and name.startswith(prefix) and len(name) > len(prefix):
            found.add(alias_prefix + name[len(prefix) :])
    return found


def load_alias_rules(root: Path, slug: str) -> tuple[tuple[str, str], ...]:
    """`name_alias_rules` from regions/<slug>/region.yml: [{prefix, alias_prefix}] (optional)."""
    path = root / "regions" / slug / "region.yml"
    if not path.exists():
        return ()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = []
    for rule in data.get("name_alias_rules") or []:
        prefix = str(rule.get("prefix") or "")
        alias_prefix = str(rule.get("alias_prefix") or "")
        if prefix and alias_prefix:
            rules.append((prefix, alias_prefix))
    return tuple(rules)


def trusted_suffix_problems(values: object) -> list[str]:
    """Problems with a ``trusted_email_suffixes`` list (empty when it is valid or absent)."""
    if values is None:
        return []
    if not isinstance(values, list):
        return ["must be a list of suffixes such as ca.gov"]
    problems: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not _SUFFIX_RE.fullmatch(value):
            problems.append(f"has {value!r}: use lower-case labels with no leading dot")
        elif value in seen:
            problems.append(f"lists {value!r} twice")
        elif is_free_mail(value) or any(
            domain == value or domain.endswith("." + value) for domain in FREE_MAIL_DOMAINS
        ):
            problems.append(f"lists the free-mail domain {value!r}")
        seen.add(str(value))
    return problems


def load_trusted_suffixes(root: Path, slug: str) -> tuple[str, ...]:
    """``trusted_email_suffixes`` from regions/<slug>/region.yml (optional; missing means none)."""
    path = root / "regions" / slug / "region.yml"
    if not path.exists():
        return ()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    values = data.get(TRUSTED_SUFFIXES_KEY)
    problems = trusted_suffix_problems(values)
    if problems:
        raise ValueError(f"regions/{slug}/region.yml: {TRUSTED_SUFFIXES_KEY} {problems[0]}")
    return tuple(values or ())


ROR_NAME_TYPES = frozenset({"acronym", "alias", "label"})


def ror_names(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Acronym, alias and label names of a ROR v2 record: [{"value", "types"}]."""
    found: dict[str, set[str]] = {}
    for entry in record.get("names") or []:
        if not isinstance(entry, Mapping):
            continue
        types = {str(t) for t in entry.get("types") or []} & ROR_NAME_TYPES
        value = str(entry.get("value") or "").strip()
        if types and value:
            found.setdefault(value, set()).update(types)
    return [{"value": v, "types": sorted(found[v])} for v in sorted(found)]


@dataclass(frozen=True)
class RorValues:
    """Domains and website links of one ROR record (from a local dump or the ROR API)."""

    domains: tuple[str, ...] = ()
    websites: tuple[str, ...] = ()


def ror_values(record: Mapping[str, Any]) -> RorValues:
    """Domains and website links of a ROR v2 record (``domains`` and ``links``)."""
    domains = {str(d) for d in record.get("domains") or [] if d}
    websites: set[str] = set()
    for link in record.get("links") or []:
        if isinstance(link, Mapping) and link.get("type") == "website" and link.get("value"):
            websites.add(str(link["value"]))
        elif isinstance(link, str) and link:
            websites.add(link)
    return RorValues(tuple(sorted(domains)), tuple(sorted(websites)))


def load_ror_domains(raw_root: Path = REPO_ROOT / RAW_DIR) -> dict[str, RorValues]:
    """ROR id -> values from a local ROR dump if one exists (never fetched).

    A dump is any ``*.json`` or ``*.json.gz`` under ``raw_root`` whose file name has ``ror`` as a
    word (``ror-v2.json``). It is a JSON list of ROR records.
    """
    found: dict[str, RorValues] = {}
    if not raw_root.is_dir():
        return {}
    for path in sorted(raw_root.rglob("*")):
        name = path.name.lower()
        if not path.is_file() or not _ROR_DUMP_NAME.search(name):
            continue
        if not name.endswith((".json", ".json.gz")):
            continue
        opener = gzip.open if name.endswith(".gz") else open
        with opener(path, "rt", encoding="utf-8") as handle:
            records = json.load(handle)
        if not isinstance(records, list):
            continue
        for record in records:
            if not isinstance(record, Mapping):
                continue
            ror_id = _short(record.get("id"))
            if not ror_id:
                continue
            new, old = ror_values(record), found.get(ror_id, RorValues())
            found[ror_id] = RorValues(
                tuple(sorted({*old.domains, *new.domains})),
                tuple(sorted({*old.websites, *new.websites})),
            )
    return found


def load_overrides(path: Path) -> dict[str, list[Override]]:
    """Owner overrides by institution id, in file order. A missing file means no overrides.

    Invalid rows raise ``ValueError`` so that an owner typo is seen at build time.
    """
    if not path.is_file():
        return {}
    found: dict[str, list[Override]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != OVERRIDE_COLUMNS:
            raise ValueError(f"{path}: header must be {','.join(OVERRIDE_COLUMNS)}")
        for number, row in enumerate(reader, start=2):
            inst_id = (row.get("institution_id") or "").strip()
            domain_text = (row.get("domain") or "").strip()
            if not inst_id and not domain_text:
                continue
            action = (row.get("action") or "").strip().lower()
            if not _OPENALEX_INSTITUTION.match(inst_id):
                raise ValueError(f"{path}:{number}: institution_id must look like I123")
            if action not in OVERRIDE_ACTIONS:
                raise ValueError(f"{path}:{number}: action must be add or remove")
            domain = registrable_domain(domain_text)
            if domain is None:
                raise ValueError(f"{path}:{number}: {domain_text!r} is not a registrable domain")
            if action == "add" and is_free_mail(domain):
                raise ValueError(f"{path}:{number}: free-mail domain {domain} is refused")
            note = (row.get("note") or "").strip()
            found.setdefault(inst_id, []).append(Override(action, domain, note))
    return found


def _addition_problem(row: Mapping[str, str]) -> str | None:
    if not _ADDITION_SLUG.fullmatch(row["region"]):
        return "region must be a lowercase slug"
    name = row["name"]
    if not name or len(name) > 200 or _ADDITION_NAME_BAD.search(name):
        return "name must be 1 to 200 characters with no HTML or control characters"
    url = row["url"]
    if url and (not url.startswith("https://") or re.search(r"\s", url)):
        return "url must be https or empty"
    domain = row["domain"]
    if registrable_domain(domain) != domain or is_free_mail(domain):
        return f"domain {domain!r} must be a registrable, non-free-mail domain"
    if row["institution_type"] not in ELIGIBLE_TYPES:
        return f"institution_type must be one of {', '.join(ELIGIBLE_TYPES)}"
    if not _UTC_ISO.fullmatch(row["approved_at_iso"]):
        return "approved_at_iso must look like 2026-11-26T00:00:00Z"
    if row["source"] != ADDITION_SOURCE:
        return f"source must be {ADDITION_SOURCE}"
    return None


def load_institution_additions(path: Path) -> list[dict[str, str]]:
    """Approved institution proposals, newest per (region, domain). A missing file means none.

    Invalid rows raise ``ValueError`` so that a bad row is seen at build time.
    """
    if not path.is_file():
        return []
    found: dict[tuple[str, str], dict[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ADDITION_COLUMNS:
            raise ValueError(f"{path}: header must be {','.join(ADDITION_COLUMNS)}")
        for number, raw in enumerate(reader, start=2):
            row = {col: (raw.get(col) or "").strip() for col in ADDITION_COLUMNS}
            if not any(row.values()):
                continue
            problem = _addition_problem(row)
            if problem is not None:
                raise ValueError(f"{path}:{number}: {problem}")
            key = (row["region"], row["domain"])
            kept = found.get(key)
            if kept is None or row["approved_at_iso"] >= kept["approved_at_iso"]:
                found[key] = row
    return list(found.values())


def additions_problems(path: Path) -> list[str]:
    try:
        load_institution_additions(path)
    except ValueError as error:
        return [str(error)]
    return []


def _approved_rows(
    slug: str,
    additions: Sequence[Mapping[str, str]],
    listed: Sequence[Mapping[str, Any]],
    notes: list[str] | None,
) -> list[dict[str, Any]]:
    """Allowlist rows for this region's approved proposals; a domain already listed is skipped."""
    listed_domains = {domain for row in listed for domain in row["domains"]}
    rows: list[dict[str, Any]] = []
    for addition in additions:
        if addition["region"] != slug:
            continue
        domain = addition["domain"]
        if domain in listed_domains:
            if notes is not None:
                notes.append(f"{slug}: {domain} is already listed; approved proposal not added")
            continue
        rows.append(
            {
                "id": f"add:{domain}",
                "name": addition["name"],
                "type": addition["institution_type"],
                "works": 0,
                "domains": [domain],
                "needs_domain": False,
                "ror": None,
                "acronyms": [],
                "aliases": [],
                "source": ADDITION_SOURCE,
            }
        )
    return rows


def _usable(values: Iterable[object]) -> set[str]:
    """Registrable domains from URLs or hosts, without free-mail or generic domains."""
    found: set[str] = set()
    for value in values:
        domain = registrable_domain(value)
        if domain is not None and not is_free_mail(domain):
            found.add(domain)
    return found


def resolve_domains(
    homepage: Iterable[object], ror: RorValues, overrides: Sequence[Override]
) -> list[str]:
    """Sorted registrable domains for one institution, after owner overrides.

    Owner precedence rule: ROR domains first, then the OpenAlex homepage host, then ROR website
    links. The first group that yields a usable domain is used (groups are not merged); owner
    overrides are applied afterwards in file order.
    """
    found: set[str] = set()
    for group in (ror.domains, list(homepage), ror.websites):
        found = _usable(group)
        if found:
            break
    for override in overrides:
        if override.action == "add":
            found.add(override.domain)
        else:
            found.discard(override.domain)
    return sorted(found)


def load_region_terms(config_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """(local search terms, geography item names) from a region.yml; empty when it is absent."""
    if not config_path.is_file():
        return [], []
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    terms: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in data.get("local_search_terms") or []:
        if not isinstance(entry, Mapping) or not entry.get("term"):
            continue
        term = str(entry["term"]).strip()
        if term.casefold() in seen:
            continue
        seen.add(term.casefold())
        terms.append(
            {
                "term": term,
                "language": str(entry.get("language") or ""),
                "note": str(entry.get("note") or ""),
            }
        )
    places: list[str] = []
    for section in data.get("sections") or []:
        if not isinstance(section, Mapping) or section.get("id") != "geography":
            continue
        for item in section.get("items") or []:
            if isinstance(item, Mapping) and item.get("name"):
                places.append(str(item["name"]))
    return terms, places


def _languages(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    rows = pq.read_table(path, columns=["work_id", "language"]).to_pylist()
    return {
        _short(r["work_id"]): str(r["language"] or "").strip().lower() for r in rows if r["work_id"]
    }


def _collect_registry(region: Region, root: Path) -> tuple[dict[str, Facts], dict[str, str | None]]:
    """Curated corpus: authorships whose ca_basis is in the predicate's ca_basis_values."""
    predicate = region.predicate
    assert predicate is not None and predicate.institution_registry is not None
    values = frozenset(predicate.ca_basis_values)
    inst_rows = pq.read_table(
        root / predicate.institution_registry,
        columns=[
            "openalex_id",
            "display_name",
            "ror_id",
            "openalex_type",
            "country_code",
            "region",
        ],
    ).to_pylist()
    matches = registry_row_matcher(region)
    registry_ids: set[str] = set()
    details: dict[str, dict[str, str | None]] = {}
    for row in inst_rows:
        inst_id = _short(row["openalex_id"])
        if not inst_id:
            continue
        details[inst_id] = {
            "name": str(row["display_name"] or "").strip(),
            "type": str(row["openalex_type"] or "").strip() or None,
            "ror": _short(row["ror_id"]),
        }
        if matches(str(row["region"] or "").strip(), str(row["country_code"] or "").strip()):
            registry_ids.add(inst_id)

    facts: dict[str, Facts] = {}
    bases: dict[str, set[str]] = {}
    local: set[str] = set()
    authorships = pq.read_table(
        root / NORMALIZED_AUTHORSHIPS,
        columns=["work_id", "institution_ids", "raw_affiliation", "ca_basis"],
    ).to_pylist()
    for row in authorships:
        basis = row["ca_basis"] or ""
        if basis not in values:
            continue
        work_id = _short(row["work_id"])
        local.add(work_id)
        note = public_text(row["raw_affiliation"]) if basis == "raw_affiliation" else None
        for raw_id in row["institution_ids"] or []:
            inst_id = _short(raw_id)
            if not inst_id:
                continue
            item = facts.setdefault(inst_id, Facts(in_region=True))
            item.works.add(work_id)
            bases.setdefault(inst_id, set()).add(basis)
            if isinstance(row["raw_affiliation"], str):
                item.raw.add(row["raw_affiliation"])
            if note:
                item.affiliations.add(note)
    for inst_id, item in facts.items():
        detail = details.get(inst_id, {})
        item.fill(
            str(detail.get("name") or ""), detail.get("type"), str(detail.get("ror") or ""), []
        )
        item.acronyms = affiliation_acronyms(item.raw, item.name)
        item.raw = set()
        if inst_id not in registry_ids and bases[inst_id] <= {"raw_affiliation"}:
            item.signals.add("matched only by raw affiliation")

    titles: dict[str, str | None] = {}
    for row in pq.read_table(root / NORMALIZED_WORKS, columns=["work_id", "title"]).to_pylist():
        work_id = _short(row["work_id"])
        if work_id in local:
            titles[work_id] = public_text(row["title"], limit=_TITLE_LIMIT)
    for work_id in local - titles.keys():
        titles[work_id] = None
    return facts, titles


def _type_of(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _add_country_work(
    facts: dict[str, Facts],
    local_titles: dict[str, str | None],
    work: Mapping[str, Any],
    work_id: str,
    iso: str,
    place: re.Pattern[str],
) -> None:
    in_region_work = False
    for authorship in work.get("authorships") or []:
        if not isinstance(authorship, Mapping):
            continue
        author_in_region = iso in {_country(c) for c in authorship.get("countries") or []}
        raw_strings = [
            s for s in authorship.get("raw_affiliation_strings") or [] if isinstance(s, str)
        ]
        places = sorted({m.group(0) for s in raw_strings for m in place.finditer(s)})
        notes = [n for n in (public_text(s) for s in raw_strings) if n]
        for inst in authorship.get("institutions") or []:
            if not isinstance(inst, Mapping):
                continue
            inst_id = _short(inst.get("id"))
            if not inst_id:
                continue
            country = _country(inst.get("country_code"))
            item = facts.setdefault(inst_id, Facts())
            item.fill(
                str(inst.get("display_name") or "").strip(),
                _type_of(inst.get("type")),
                _short(inst.get("ror")),
                [inst.get("homepage_url")] if isinstance(inst.get("homepage_url"), str) else [],
            )
            item.works.add(work_id)
            item.raw.update(raw_strings)
            if country == iso:
                item.in_region = True
                in_region_work = True
                continue
            if author_in_region:
                item.signals.add(f"author country {iso}")
                in_region_work = True
            if places:
                item.signals.update(f'affiliation mentions "{p}"' for p in places)
                item.affiliations.update(notes)
    if in_region_work:
        local_titles[work_id] = public_text(work.get("title"), limit=_TITLE_LIMIT)


def _collect_country(
    region: Region, root: Path, places: Sequence[str]
) -> tuple[dict[str, Facts], dict[str, str | None]]:
    """Global partition: authorship institutions in the region's country, from raw pages."""
    predicate = region.predicate
    assert predicate is not None and len(predicate.country_codes) == 1
    iso = predicate.country_codes[0]
    names = sorted({region.name, *places}, key=len, reverse=True)
    place = re.compile(r"\b(?:" + "|".join(re.escape(n) for n in names) + r")\b", re.IGNORECASE)
    corpus = set(_languages(root / GLOBAL_WORKS))
    needle = f'"{iso}"'
    facts: dict[str, Facts] = {}
    local_titles: dict[str, str | None] = {}
    for path in raw_page_paths(root / RAW_PAGES):
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            handle.readline()  # page_header
            for line in handle:
                if needle not in line and not place.search(line):
                    continue
                work = json.loads(line)
                work_id = _short(work.get("id"))
                if work_id in corpus:
                    _add_country_work(facts, local_titles, work, work_id, iso, place)
    for item in facts.values():
        item.acronyms = affiliation_acronyms(item.raw, item.name)
        item.raw = set()
    return facts, local_titles


def load_corpus(region: Region, root: Path = REPO_ROOT) -> RegionCorpus:
    """Read the region's inputs under ``root`` (ignored partition, raw pages, normalized tables)."""
    predicate = region.predicate
    assert predicate is not None
    terms, places = load_region_terms(root / "regions" / region.slug / "region.yml")
    if predicate.institution_registry is not None:
        facts, titles = _collect_registry(region, root)
    else:
        facts, titles = _collect_country(region, root, places)
    return RegionCorpus(
        facts=facts,
        local_titles=titles,
        languages=_languages(root / GLOBAL_WORKS),
        terms=terms,
    )


def inputs_present(region: Region, root: Path = REPO_ROOT) -> bool:
    """True when every ignored input this region needs exists (staleness can then be checked)."""
    predicate = region.predicate
    if predicate is None or not (root / GLOBAL_WORKS).is_file():
        return False
    if predicate.institution_registry is not None:
        needed = [
            NORMALIZED_AUTHORSHIPS,
            NORMALIZED_WORKS,
            Path(predicate.institution_registry),
        ]
        return all((root / path).is_file() for path in needed)
    return bool(raw_page_paths(root / RAW_PAGES))


# --- outputs --------------------------------------------------------------------------------


def _eligible(corpus: RegionCorpus) -> list[tuple[str, Facts]]:
    """Institutions in the region with enough works and an eligible type, by id."""
    return [
        (inst_id, item)
        for inst_id, item in corpus.facts.items()
        if item.in_region and len(item.works) >= MIN_WORKS and item.type in ELIGIBLE_TYPES
    ]


def eligible_ids(corpus: RegionCorpus) -> list[str]:
    return sorted(inst_id for inst_id, _ in _eligible(corpus))


# --- domain cache (ignored, data/interim) and the fetch mode ------------------------------

DOMAIN_CACHE = Path("data/interim/ambassador_domains")
USAGE_LOG = Path("data/logs/api_usage.jsonl")
OPENALEX_SELECT = "id,display_name,homepage_url,ror"
OPENALEX_BATCH = 100
FETCH_CREDIT_CAP = Decimal(20)
PLANNED_CREDITS_PER_CALL = Decimal(1)
ROR_API = "https://api.ror.org/v2/organizations/{ror}"
ROR_USER_AGENT = "ca-plastics-atlas/0.1 (research dashboard)"
ROR_INTERVAL_SECONDS = 1.0
_ROR_ID = re.compile(r"^0[a-z0-9]{8}$")
_ROR_URL = re.compile(r"^https://ror\.org/0[a-z0-9]{8}$")


class FetchLimitError(RuntimeError):
    """The OpenAlex credit cap or the daily budget guard would be exceeded."""


def cache_path(root: Path, inst_id: str) -> Path:
    return root / DOMAIN_CACHE / f"{inst_id}.json"


def read_cache(root: Path, ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    """Cached domain entries for the given institution ids (missing files are skipped)."""
    found: dict[str, dict[str, Any]] = {}
    for inst_id in ids:
        path = cache_path(root, inst_id)
        if path.is_file():
            found[inst_id] = json.loads(path.read_text(encoding="utf-8"))
    return found


def _write_cache(root: Path, inst_id: str, entry: Mapping[str, Any]) -> None:
    path = cache_path(root, inst_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    text = json.dumps(entry, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _ror_id(item: Facts, entry: Mapping[str, Any]) -> str:
    openalex = entry.get("openalex") or {}
    return item.ror or str(openalex.get("ror") or "")


def missing_domain_cache(root: Path, corpus: RegionCorpus) -> list[str]:
    """Eligible ids whose OpenAlex record, or ROR record when a ROR id is known, is not cached."""
    cached = read_cache(root, eligible_ids(corpus))
    missing = []
    for inst_id, item in _eligible(corpus):
        entry = cached.get(inst_id, {})
        if "openalex" not in entry or (_ror_id(item, entry) and "ror" not in entry):
            missing.append(inst_id)
    return sorted(missing)


def fetch_openalex(
    ids: Sequence[str],
    root: Path,
    *,
    logger: Any,
    budget: Any,
    request_json: Any = _request_json,
    today: str,
) -> int:
    """Fetch OpenAlex institution records for uncached ids in batches; returns the call count.

    Each call is a plain filter (about 1 credit). The run stops before a call that would exceed
    ``FETCH_CREDIT_CAP`` or the daily budget guard (``budget.reserve_error``).
    """
    cached = read_cache(root, ids)
    todo = [i for i in ids if "openalex" not in cached.get(i, {})]
    calls = 0
    for batch in openalex_chunks(todo, OPENALEX_BATCH):
        spent = Decimal(str(logger.credits_total))
        if spent + PLANNED_CREDITS_PER_CALL > FETCH_CREDIT_CAP:
            raise FetchLimitError(f"OpenAlex credit cap {FETCH_CREDIT_CAP} reached")
        error = budget.reserve_error(cost_usd=Decimal(str(logger.cost_usd_total)), credits=spent)
        if error:
            raise FetchLimitError(error)
        filter_ids = "|".join(batch)
        url = (
            f"{OPENALEX_BASE}/institutions?filter=openalex_id:{filter_ids}"
            f"&select={OPENALEX_SELECT}&per-page={OPENALEX_BATCH}"
        )
        body = request_json(url, logger=logger)
        calls += 1
        records = {
            _short(r.get("id")): r for r in body.get("results") or [] if isinstance(r, Mapping)
        }
        for inst_id in batch:
            record = records.get(inst_id) or {}
            entry = cached.get(inst_id, {})
            entry["institution_id"] = inst_id
            entry["openalex"] = {
                "fetched": today,
                "found": bool(record),
                "display_name": str(record.get("display_name") or ""),
                "homepage_url": record.get("homepage_url") or None,
                "ror": _short(record.get("ror")),
            }
            cached[inst_id] = entry
            _write_cache(root, inst_id, entry)
    return calls


def _get_ror(url: str) -> dict[str, Any] | None:
    """One ROR API GET with a generic User-Agent; None for an unknown id (HTTP 404)."""
    request = urllib.request.Request(
        url, headers={"User-Agent": ROR_USER_AGENT, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise
    return body if isinstance(body, dict) else None


def fetch_ror(
    ror_by_id: Mapping[str, str],
    root: Path,
    *,
    get_json: Any = _get_ror,
    sleep: Any = time.sleep,
    today: str,
) -> int:
    """Fetch ROR v2 records for an institution-to-ROR map, one request per unique uncached id.

    Pauses ``ROR_INTERVAL_SECONDS`` between requests (ROR asks for one request per second).
    Returns the number of ROR requests.
    """
    cached = read_cache(root, ror_by_id)
    wanted = sorted({r for inst, r in ror_by_id.items() if "ror" not in cached.get(inst, {})})
    results: dict[str, dict[str, Any]] = {}
    calls = 0
    for ror in wanted:
        if not _ROR_ID.match(ror):
            continue
        if calls:
            sleep(ROR_INTERVAL_SECONDS)
        body = get_json(ROR_API.format(ror=ror))
        calls += 1
        if body is None:
            results[ror] = {
                "ror_id": ror,
                "fetched": today,
                "found": False,
                "domains": [],
                "websites": [],
            }
        else:
            values = ror_values(body)
            results[ror] = {
                "ror_id": ror,
                "fetched": today,
                "found": True,
                "domains": list(values.domains),
                "websites": list(values.websites),
                "names": ror_names(body),
            }
    for inst_id, ror in ror_by_id.items():
        if ror in results:
            entry = cached.get(inst_id, {"institution_id": inst_id})
            entry["ror"] = results[ror]
            _write_cache(root, inst_id, entry)
    return calls


def run_fetch(
    corpora: Mapping[str, RegionCorpus],
    root: Path,
    *,
    usage_log: Path,
    request_json: Any = _request_json,
    get_json: Any = _get_ror,
    sleep: Any = time.sleep,
    budget: Any = None,
    today: str | None = None,
) -> dict[str, Any]:
    """Fill the domain cache for every eligible institution of every region (network).

    OpenAlex records first (batched, logged to ``usage_log``), then ROR records for the
    institutions that have a ROR id. Returns request and credit counts.
    """
    stamp = today or date.today().isoformat()
    budget = budget or resolve_openalex_budget()
    items: dict[str, Facts] = {}
    for corpus in corpora.values():
        for inst_id, item in _eligible(corpus):
            items.setdefault(inst_id, item)
    with ApiCostLogger(f"ambassador-domains-{stamp}", usage_log) as logger:
        calls = fetch_openalex(
            sorted(items),
            root,
            logger=logger,
            budget=budget,
            request_json=request_json,
            today=stamp,
        )
        cached = read_cache(root, items)
        ror_by_id = {}
        for inst_id, item in items.items():
            ror = _ror_id(item, cached.get(inst_id, {}))
            if ror:
                ror_by_id[inst_id] = ror
        ror_calls = fetch_ror(ror_by_id, root, get_json=get_json, sleep=sleep, today=stamp)
        credits = Decimal(str(logger.credits_total))
    return {
        "institutions": len(items),
        "openalex_calls": calls,
        "ror_requests": ror_calls,
        "credits": str(credits),
    }


def _institution_rows(
    corpus: RegionCorpus,
    ror_dump: Mapping[str, RorValues],
    cache: Mapping[str, Mapping[str, Any]],
    overrides: Mapping[str, Sequence[Override]],
    alias_rules: Sequence[tuple[str, str]] = (),
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for inst_id, item in _eligible(corpus):
        entry = cache.get(inst_id, {})
        openalex = entry.get("openalex") or {}
        fetched = entry.get("ror") or {}
        local = ror_dump.get(_ror_id(item, entry), RorValues())
        ror = RorValues(
            tuple(sorted({*fetched.get("domains", []), *local.domains})),
            tuple(sorted({*fetched.get("websites", []), *local.websites})),
        )
        homepage = [*sorted(item.hosts)]
        if openalex.get("homepage_url"):
            homepage.append(str(openalex["homepage_url"]))
        domains = resolve_domains(homepage, ror, overrides.get(inst_id, ()))
        ror_id = _ror_id(item, entry).lower()
        name = item.name or inst_id
        ror_names_here = fetched.get("names", [])
        ror_acronyms = {n["value"] for n in ror_names_here if "acronym" in n["types"]}
        ror_aliases = {n["value"] for n in ror_names_here if "acronym" not in n["types"]}
        acronyms = sorted({*item.acronyms, *ror_acronyms} - {""})
        aliases = sorted(
            {*prefix_aliases(name, alias_rules), *ror_aliases} - {name, *acronyms} - {""}
        )
        rows.append(
            {
                "id": inst_id,
                "name": name,
                "type": item.type,
                "works": len(item.works),
                "domains": domains,
                "needs_domain": not domains,
                # Short ROR URL (https://ror.org/<id>), or null when no ROR id is known.
                "ror": f"https://ror.org/{ror_id}" if _ROR_ID.match(ror_id) else None,
                "acronyms": acronyms,
                "aliases": aliases,
                "source": OPENALEX_SOURCE,
            }
        )
    rows.sort(key=lambda r: (-r["works"], r["name"].casefold(), r["id"]))
    return rows


def _case(
    slug: str,
    kind: str,
    key: str,
    question: str,
    evidence: dict[str, Any],
    current: str,
    options: Sequence[str],
) -> dict[str, Any]:
    digest = hashlib.sha256(f"{slug}|{kind}|{key}".encode()).hexdigest()[:12]
    return {
        "case_id": f"amb-{digest}",
        "kind": kind,
        "question": question,
        "evidence": evidence,
        "current_value": current,
        "options": list(options),
    }


def _case_rows(region: Region, corpus: RegionCorpus) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Case queues by kind (capped, deterministic) and the number of candidates before the cap."""
    slug = region.slug
    cases: list[dict[str, Any]] = []
    available: dict[str, int] = {}

    # Affiliation evidence (place names, raw-affiliation-only matches) ranks before
    # author-country-only signals, so the cap keeps the disagreements a reviewer needs most.
    region_cands = sorted(
        ((i, f) for i, f in corpus.facts.items() if f.signals),
        key=lambda pair: (
            0
            if any(s.startswith(("affiliation mentions", "matched only")) for s in pair[1].signals)
            else 1,
            -len(pair[1].works),
            pair[0],
        ),
    )
    available["institution_in_region"] = len(region_cands)
    for inst_id, item in region_cands[: CASE_CAPS["institution_in_region"]]:
        cases.append(
            _case(
                slug,
                "institution_in_region",
                inst_id,
                f"Is this institution in {region.name}?",
                {
                    "institution_id": inst_id,
                    "institution_name": item.name or None,
                    "works": len(item.works),
                    "signals": sorted(item.signals),
                    "affiliation_examples": sorted(item.affiliations)[:3],
                },
                "in region" if item.in_region else "not in region",
                YES_NO_OPTIONS,
            )
        )

    type_cands = sorted(
        (
            (i, f)
            for i, f in corpus.facts.items()
            if f.in_region
            and len(f.works) >= MIN_WORKS
            and (f.type in (None, "other") or (f.type == "company" and len(f.works) >= MANY_WORKS))
        ),
        key=lambda pair: (-len(pair[1].works), pair[0]),
    )
    available["institution_type"] = len(type_cands)
    for inst_id, item in type_cands[: CASE_CAPS["institution_type"]]:
        cases.append(
            _case(
                slug,
                "institution_type",
                inst_id,
                "Is this institution's type right?",
                {
                    "institution_id": inst_id,
                    "institution_name": item.name or None,
                    "works": len(item.works),
                },
                item.type or "missing",
                TYPE_OPTIONS,
            )
        )

    language_cands = []
    for work_id in sorted(corpus.local_titles):
        title = corpus.local_titles[work_id]
        language = corpus.languages.get(work_id, "")
        if title and language and language != "en":
            language_cands.append((work_id, title, language))
    available["local_language_relevance"] = len(language_cands)
    for work_id, title, language in language_cands[: CASE_CAPS["local_language_relevance"]]:
        cases.append(
            _case(
                slug,
                "local_language_relevance",
                work_id,
                "Is this local-language work about plastics?",
                {"work_id": work_id, "title": title, "language": language},
                f"language {language}",
                YES_NO_OPTIONS,
            )
        )

    available["local_terms"] = len(corpus.terms)
    for entry in corpus.terms:
        cases.append(
            _case(
                slug,
                "local_terms",
                entry["term"].casefold(),
                "Is this term used locally for plastic pollution?",
                {"term": entry["term"], "language": entry["language"], "note": entry["note"]},
                "listed in region config",
                YES_NO_OPTIONS,
            )
        )
    return cases, available


def build_payloads(
    region: Region,
    corpus: RegionCorpus,
    ror_dump: Mapping[str, RorValues],
    cache: Mapping[str, Mapping[str, Any]],
    overrides: Mapping[str, Sequence[Override]],
    generated_at: str,
    alias_rules: Sequence[tuple[str, str]] = (),
    additions: Sequence[Mapping[str, str]] = (),
    notes: list[str] | None = None,
    trusted_suffixes: Sequence[str] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    """(ambassador_institutions payload, ambassador_cases payload) for one region."""
    rows = _institution_rows(corpus, ror_dump, cache, overrides, alias_rules)
    approved = _approved_rows(region.slug, additions, rows, notes)
    if approved:
        rows = sorted(
            [*rows, *approved], key=lambda r: (-r["works"], r["name"].casefold(), r["id"])
        )
    institutions = {
        "schema": INSTITUTIONS_SCHEMA,
        "generated_at": generated_at,
        "region": region.slug,
        "rule": RULE,
        "min_works": MIN_WORKS,
        "eligible_types": list(ELIGIBLE_TYPES),
        TRUSTED_SUFFIXES_KEY: list(trusted_suffixes),
        "institutions": rows,
    }
    cases, available = _case_rows(region, corpus)
    counts = {kind: sum(1 for c in cases if c["kind"] == kind) for kind in CASE_KINDS}
    queue = {
        "schema": CASES_SCHEMA,
        "generated_at": generated_at,
        "region": region.slug,
        "caps": CASE_CAPS,
        "available": {kind: available.get(kind, 0) for kind in CASE_KINDS},
        "counts": counts,
        "cases": cases,
    }
    return institutions, queue


def build_from_corpus(
    region: Region,
    corpus: RegionCorpus,
    root: Path = REPO_ROOT,
    generated_at: str | None = None,
    notes: list[str] | None = None,
) -> tuple[dict, dict]:
    """Both payloads from a loaded corpus, the local ROR dump, the domain cache and overrides."""
    stamp = generated_at or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return build_payloads(
        region,
        corpus,
        load_ror_domains(root / RAW_DIR),
        read_cache(root, corpus.facts),
        load_overrides(root / "regions" / region.slug / "ambassador_domains.csv"),
        stamp,
        load_alias_rules(root, region.slug),
        load_institution_additions(root / ADDITIONS_CSV),
        notes,
        load_trusted_suffixes(root, region.slug),
    )


def build_region(
    region: Region, root: Path = REPO_ROOT, generated_at: str | None = None
) -> tuple[dict, dict]:
    """Load the region's inputs under ``root`` and build both payloads (offline)."""
    return build_from_corpus(region, load_corpus(region, root), root, generated_at)


def encode(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _walk(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    """(path, problem) for forbidden keys and '@' inside any string of a payload."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in FORBIDDEN_KEYS:
                yield path, f"forbidden key {key!r}"
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
    elif isinstance(value, str) and "@" in value:
        yield path, "string contains '@' (possible contact detail)"


def validate_outputs(
    institutions: Mapping[str, Any], cases: Mapping[str, Any], slug: str
) -> list[str]:
    """Schema, eligibility, case and privacy problems for one region's committed outputs."""
    problems: list[str] = []
    if institutions.get("schema") != INSTITUTIONS_SCHEMA:
        problems.append("institutions: schema must be amb-v1")
    unknown = sorted(set(institutions) - INSTITUTIONS_TOP_KEYS)
    if unknown:
        problems.append(f"institutions: unknown top-level keys {unknown}")
    problems.extend(
        f"institutions: {TRUSTED_SUFFIXES_KEY} {text}"
        for text in trusted_suffix_problems(institutions.get(TRUSTED_SUFFIXES_KEY, []))
    )
    if cases.get("schema") != CASES_SCHEMA:
        problems.append("cases: schema must be amb-cases-v1")
    for name, payload in (("institutions", institutions), ("cases", cases)):
        if payload.get("region") != slug:
            problems.append(f"{name}: region must be {slug}")
        problems.extend(f"{name}: {where} {text}" for where, text in _walk(payload))
    for index, row in enumerate(institutions.get("institutions") or []):
        if set(row) != INSTITUTION_KEYS:
            problems.append(f"institutions[{index}]: keys must be {sorted(INSTITUTION_KEYS)}")
            continue
        source = row["source"]
        if source == OPENALEX_SOURCE:
            if row["works"] < MIN_WORKS or row["type"] not in ELIGIBLE_TYPES:
                problems.append(f"institutions[{index}]: not eligible ({row['id']})")
        elif source == ADDITION_SOURCE:
            if (
                row["works"] != 0
                or row["type"] not in ELIGIBLE_TYPES
                or len(row["domains"]) != 1
                or row["id"] != f"add:{row['domains'][0] if row['domains'] else ''}"
            ):
                problems.append(f"institutions[{index}]: bad approved proposal ({row['id']})")
        else:
            problems.append(f"institutions[{index}]: source must be openalex or approved_proposal")
        if row["needs_domain"] != (not row["domains"]):
            problems.append(f"institutions[{index}]: needs_domain disagrees with domains")
        if row["ror"] is not None and not _ROR_URL.match(str(row["ror"])):
            problems.append(f"institutions[{index}]: ror must be null or https://ror.org/<id>")
        for domain in row["domains"]:
            if registrable_domain(domain) != domain or is_free_mail(domain):
                problems.append(f"institutions[{index}]: bad domain {domain!r}")
        for key in ("acronyms", "aliases"):
            values = row[key]
            if not isinstance(values, list) or not all(isinstance(v, str) and v for v in values):
                problems.append(f"institutions[{index}]: {key} must be a list of strings")
    for index, row in enumerate(institutions.get("institutions") or []):
        if set(row) != INSTITUTION_KEYS or row["source"] != ADDITION_SOURCE:
            continue
        for other in institutions["institutions"]:
            if other is not row and set(row["domains"]) & set(other.get("domains") or []):
                problems.append(f"institutions[{index}]: approved domain is listed twice")
    ids: list[str] = []
    counts: dict[str, int] = {}
    for index, case in enumerate(cases.get("cases") or []):
        if set(case) != CASE_KEYS or case["kind"] not in CASE_KINDS:
            problems.append(f"cases[{index}]: keys or kind invalid")
            continue
        ids.append(case["case_id"])
        counts[case["kind"]] = counts.get(case["kind"], 0) + 1
    if len(ids) != len(set(ids)):
        problems.append("cases: duplicate case_id")
    for kind, cap in CASE_CAPS.items():
        if counts.get(kind, 0) > cap:
            problems.append(f"cases: {kind} exceeds cap {cap}")
    return problems


def overrides_problems(path: Path) -> list[str]:
    try:
        load_overrides(path)
    except ValueError as error:
        return [str(error)]
    return []
