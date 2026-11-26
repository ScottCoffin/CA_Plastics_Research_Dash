"""Admission, normalisation, dedupe and region mapping for the BFFP roster (Add-on A4, CG-3).

Rules (docs/BFFP.md section 4.4, A4-D20): positive admission only. Entries that the source lists
as organisations are ``source_declared_org``. Heuristics may demote an entry to
``excluded_individual`` (dropped, never written) or ``ambiguous`` (quarantined locally); they never
promote. Exact duplicates collapse on ``group_id``; near-duplicates within a country go to a local
review list and are never merged.

Region mapping (A4-C3): a country maps to an ambassador region only when that registry region's
predicate names exactly that one country code. ``region`` is the UN M49 sub-region name, or
``region_unknown``.
"""

from __future__ import annotations

import csv
import difflib
import hashlib
import html
import io
import itertools
import json
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from atlas.groups.roster import RawEntry
from atlas.regions.registry import Registry, load_registry

__all__ = [
    "ADMITTED_STATUSES",
    "AdmissionResult",
    "admit",
    "ambassador_region_map",
    "apply_name_correction",
    "apply_reviewed_merges",
    "auto_merge",
    "excluded_host",
    "classify",
    "group_id_for",
    "is_placeholder_name",
    "iso_for_country",
    "m49_subregion",
    "merge_key",
    "normalise_text",
    "normalise_url",
    "read_merges",
    "read_name_corrections",
    "registrable_domain",
    "region_for",
    "same_host_pairs",
]

REPO_ROOT = Path(__file__).resolve().parents[3]
PLACES_PATH = REPO_ROOT / "site" / "data" / "global" / "places.json"
UNKNOWN_REGION = "region_unknown"
NEAR_DUPLICATE_RATIO = 0.9
ADMITTED_STATUSES = ("source_declared_org", "heuristic_org", "human_confirmed_org")

# Mapping from the UN M49 sub-region name to its ISO 3166-1 alpha-2 members.
# Source: UN M49 (United Nations Statistics Division), Standard country or area codes for
# statistical use. Intermediate regions are not used. Codes are listed per sub-region.
M49_SUBREGIONS: dict[str, str] = {
    "Northern Africa": "DZ EG EH LY MA SD TN",
    "Western Africa": "BF BJ CI CV GH GM GN GW LR ML MR NE NG SH SL SN TG",
    "Middle Africa": "AO CD CF CG CM GA GQ ST TD",
    "Eastern Africa": "BI DJ ER ET KE KM MG MU MW MZ RE RW SC SO SS TZ UG YT ZM ZW",
    "Southern Africa": "BW LS NA SZ ZA",
    "Northern America": "BM CA GL PM US",
    "Central America": "BZ CR GT HN MX NI PA SV",
    "Caribbean": (
        "AG AI AW BB BL BQ BS CU CW DM DO GD GP HT JM KN KY LC MF MQ MS PR SX TC TT VC VG VI"
    ),
    "South America": "AR BO BR BV CL CO EC FK GF GS GY PE PY SR UY VE",
    "Western Asia": ("AE AM AZ BH CY GE IL IQ JO KW LB OM PS QA SA SY TR YE"),
    "Central Asia": "KG KZ TJ TM UZ",
    "Southern Asia": "AF BD BT IN IO IR LK MV NP PK",
    "Eastern Asia": "CN HK JP KP KR MN MO TW",
    "South-eastern Asia": "BN ID KH LA MM MY PH SG TH TL VN",
    "Northern Europe": "AX DK EE FI FO GB GG IE IM IS JE LT LV NO SE SJ",
    "Western Europe": "AT BE CH DE FR LI LU MC NL",
    "Eastern Europe": "BG BY CZ HU MD PL RO RU SK UA",
    "Southern Europe": "AD AL BA ES GI GR HR IT ME MK MT PT RS SI SM VA",
    "Australia and New Zealand": "AU CC CX HM NF NZ",
    "Melanesia": "FJ NC PG SB VU",
    "Micronesia": "FM GU KI MH MP NR PW UM",
    "Polynesia": "AS CK NU PF PN TK TO TV WF WS",
}

# Spellings BFFP and other sources use that the repo's country list does not carry.
# Keys are folded with _fold() before lookup.
# Country values in BFFP's data that name no country. "eSwatini<" (stray "<") tags entries whose
# websites are mostly UK domains (2026-11-26): a broken source value, not Eswatini. It maps to no
# country (region_unknown), not to a country guessed from web domains
# (QUESTIONS BFFP-COUNTRY-ARTEFACTS). No count of these entries is recorded (A4-D24).
NOT_A_COUNTRY = frozenset({"eswatini<", "global"})

EXTRA_COUNTRY_ALIASES: dict[str, str] = {
    "Mainland China": "CN",
    # Spellings seen in BFFP's member data (2026-11-26).
    "Korea (Republic of)": "KR",
    "Taiwan; Republic of China (ROC)": "TW",
    "United Kingdom of Great Britain and Northern Ireland": "GB",
    "Croatia (Hrvatska)": "HR",
    "Congo (Democratic Republic)": "CD",
    "Congo (Democratic Republic of the)": "CD",
    "United States Minor Outlying Islands": "UM",
    "Palestinian Occupied Territories": "PS",
    "Palestine, State of": "PS",
    "Reunion": "RE",
    "Slovakia (Slovak Republic)": "SK",
    "Libyan Arab Jamahiriya": "LY",
    "Bosnia and Herzegowina": "BA",
    "China, mainland": "CN",
    "United States of America": "US",
    "USA": "US",
    "UK": "GB",
    "U.K.": "GB",
    "England": "GB",
    "Scotland": "GB",
    "Wales": "GB",
    "Northern Ireland": "GB",
    "Korea, Republic of": "KR",
    "Korea, Democratic People's Republic of": "KP",
    "Iran, Islamic Republic of": "IR",
    "Tanzania, United Republic of": "TZ",
    "Bolivia, Plurinational State of": "BO",
    "Venezuela, Bolivarian Republic of": "VE",
    "Moldova, Republic of": "MD",
    "Syrian Arab Republic": "SY",
    "Lao People's Democratic Republic": "LA",
    "Taiwan, Province of China": "TW",
    "Micronesia, Federated States of": "FM",
    "Brunei Darussalam": "BN",
    "Hong Kong SAR": "HK",
    "Macau SAR": "MO",
    "Macao SAR": "MO",
    "The Netherlands": "NL",
    "The Philippines": "PH",
    "The Bahamas": "BS",
    "Bahamas, The": "BS",
    "Gambia, The": "GM",
    "Congo, Democratic Republic of the": "CD",
    "Congo, The Democratic Republic of the": "CD",
    "Congo, Republic of the": "CG",
    "Palestinian Territory, Occupied": "PS",
    "State of Palestine": "PS",
    "Slovak Republic": "SK",
    "Bosnia & Herzegovina": "BA",
    "Trinidad & Tobago": "TT",
    "St. Kitts and Nevis": "KN",
    "St. Lucia": "LC",
    "St. Vincent and the Grenadines": "VC",
}

# Free-mail and personal-mail domains: a website on one of these marks a single person (A4-D20).
FREE_MAIL_DOMAINS = frozenset(
    {
        "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "hotmail.com", "outlook.com",
        "live.com", "msn.com", "aol.com", "icloud.com", "me.com", "mac.com", "protonmail.com",
        "proton.me", "pm.me", "gmx.net", "gmx.de", "gmx.com", "web.de", "mail.com", "zoho.com",
        "fastmail.com", "tutanota.com", "hey.com", "qq.com", "163.com", "126.com", "sina.com",
        "yandex.ru", "mail.ru", "orange.fr", "free.fr", "laposte.net", "libero.it", "virgilio.it",
        "btinternet.com", "sky.com", "talktalk.net", "bigpond.com", "rocketmail.com",
        "naver.com", "daum.net", "rediffmail.com", "uol.com.br", "bol.com.br",
    }
)  # fmt: skip
# Hosts where a path segment, not the host, shows a personal profile.
SOCIAL_HOSTS = frozenset(
    {
        "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com", "tiktok.com",
        "youtube.com", "medium.com", "substack.com", "github.com", "researchgate.net",
        "bsky.app", "threads.net",
    }
)  # fmt: skip
PERSONAL_PATH_SEGMENTS = frozenset(
    {"in", "pub", "people", "user", "users", "profile", "profiles", "u", "profile.php"}
)
ORCID_HOSTS = frozenset({"orcid.org"})
SECOND_LEVEL_LABELS = frozenset(
    {"co", "com", "org", "net", "gov", "edu", "ac", "or", "ne", "go", "gob", "gouv"}
)
ORG_KEYWORDS = frozenset(
    {
        # English
        "association", "associations", "network", "foundation", "collective", "society", "group",
        "club", "alliance", "coalition", "institute", "council", "campaign", "project",
        "initiative", "ngo", "trust", "centre", "center", "movement", "cooperative", "co-operative",
        "coop", "union", "federation", "fund", "organisation", "organization", "agency", "forum",
        "hub", "academy", "university", "school", "office", "partners", "partnership", "team",
        "company", "ltd", "llc", "inc", "limited",
        # Spanish, Portuguese, Italian, French
        "asociación", "asociacion", "asociaciones", "fundación", "fundacion", "red", "colectivo",
        "associação", "associacao", "rede", "fundação", "fundacao", "coletivo", "cooperativa",
        "cooperativo", "federación", "federacion", "coalición", "coalicion", "instituto", "centro",
        "movimiento", "movimento", "movimento", "gruppo", "associazione", "fondazione", "rete",
        "association", "fondation", "réseau", "reseau", "collectif", "coopérative",
        # German, Dutch, Scandinavian
        "verein", "vereinigung", "stiftung", "netzwerk", "gesellschaft", "initiative", "bund",
        "stichting", "netwerk", "vereniging", "forening", "förening", "nettverk", "stiftelse",
        "gmbh", "bv", "aps", "oy", "ab",
    }
)  # fmt: skip
_TOKEN_RE = re.compile(r"[^\W_]+(?:[-'’][^\W_]+)*", re.UNICODE)
# Stand-in names (casefolded, stripped). Quarantined as ambiguous, never published.
PLACEHOLDER_NAMES = frozenset(
    {"-", "n/a", "na", "tbc", "tbd", "test", "tes", "hhh", "xxx", "none", "null", "unknown", "?"}
)
# Hosts shared by many unrelated groups, and link shorteners: a shared host is not a duplicate key.
SHARED_HOST_SUFFIXES = frozenset(
    {
        "sites.google.com", "docs.google.com", "drive.google.com", "blogspot.com",
        "wordpress.com", "wixsite.com", "wix.com", "weebly.com", "github.io", "gitlab.io",
        "notion.site", "squarespace.com", "carrd.co", "linktr.ee", "linktree.com", "bit.ly",
        "tinyurl.com", "t.co", "ow.ly", "lnkd.in", "goo.gl", "is.gd", "buff.ly", "rebrand.ly",
        "shorturl.at", "bit.do", "medium.com", "yolasite.com", "webnode.com", "jimdo.com",
        "vk.com", "t.me", "wa.me", "whatsapp.com", "eventbrite.com",
    }
)  # fmt: skip
# Legal-form tokens removed from the merge key (single tokens, and token pairs for "e.V.", "S.A.").
LEGAL_FORM_TOKENS = frozenset(
    {"ggmbh", "gmbh", "inc", "ltd", "llc", "cic", "cio", "asbl", "vzw", "ngo", "ong", "plc", "gug",
     "ev"}
)  # fmt: skip
LEGAL_FORM_PAIRS = frozenset({("e", "v"), ("s", "a"), ("a", "s")})
_NON_WORD_RE = re.compile(r"[\W_]+")
AUTO_MERGE_HEADER = ["group_id_keep", "group_id_drop", "country", "name_keep", "name_drop"]
MERGE_HEADER = ["group_id_keep", "group_id_drop", "decided_at", "decision"]
MERGE_DECISIONS = ("same", "different")
NAME_CORRECTION_HEADER = ["group_id", "name", "submitted_at"]


# ---------------------------------------------------------------------------
# Text and URL normalisation
# ---------------------------------------------------------------------------


def normalise_text(value: str | None) -> str:
    """NFC, trim and collapse whitespace. Original script is kept as given."""
    if not value:
        return ""
    return " ".join(unicodedata.normalize("NFC", value).split())


# Stray punctuation that is stripped from the published display name only (CG-NAME-CLEAN).
# The group_id still hashes the normalised name, so cleaning never changes an id.
_CLEAN_LEADING = "/\\|_-.,;:*#•·~"
_CLEAN_TRAILING = "/\\|,;:*#•·~_-"  # a trailing "." is kept (R.I.S.E., Co.)
_CLEAN_PAIRS = (('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"))
# An opening quote with no closing partner later in the name is stray, and so is a closing one.
_CLOSER_FOR_OPENER = {'"': '"', "'": "'", "“": "”", "‘": "’"}
_OPENER_FOR_CLOSER = {'"': '"', "”": "“"}


def clean_display_name(name: str) -> str:
    """Display form of an organisation name: stray edge punctuation and wrapping quotes removed.

    Inner punctuation and script are kept. Never returns an empty string: if cleaning would
    leave nothing, the normalised input is returned instead.
    """
    base = normalise_text(name)
    text = base
    while True:
        previous = text
        text = text.strip().lstrip(_CLEAN_LEADING).rstrip(_CLEAN_TRAILING).strip()
        if len(text) >= 2 and (text[0], text[-1]) in _CLEAN_PAIRS:
            text = text[1:-1].strip()
        if text and text[0] in _CLOSER_FOR_OPENER and _CLOSER_FOR_OPENER[text[0]] not in text[1:]:
            text = text[1:]
        if (
            text
            and text[-1] in _OPENER_FOR_CLOSER
            and _OPENER_FOR_CLOSER[text[-1]] not in text[:-1]
        ):
            text = text[:-1]
        if text == previous:
            break
    cleaned = normalise_text(text)
    return cleaned or base


def _fold(value: str) -> str:
    """Case-, accent- and spacing-insensitive key for country lookup."""
    decomposed = unicodedata.normalize("NFKD", value)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    text = stripped.replace("’", "'").replace("&", " and ")
    return " ".join(text.casefold().split())


def normalise_url(value: str | None) -> str | None:
    """Keep http(s) URLs as given; add https:// when the scheme is missing; drop invalid ones."""
    if value is None:
        return None
    text = value.strip()
    if not text or any(ch.isspace() for ch in text) or any(ch in text for ch in '<>"'):
        return None
    if "://" not in text:
        text = "https://" + text
    try:
        parts = urlsplit(text)
        host = parts.hostname
        _ = parts.port  # raises ValueError for a malformed port
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https"):
        return None
    if not host or "." not in host or parts.username or parts.password:
        return None
    return text


def _host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


def registrable_domain(url: str | None) -> str | None:
    """The registrable domain of a URL (eTLD+1), with a short list of second-level labels."""
    if not url:
        return None
    labels = _host(url).split(".")
    if len(labels) < 2:
        return None
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in SECOND_LEVEL_LABELS:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


# ---------------------------------------------------------------------------
# Countries and regions
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _country_tables() -> tuple[frozenset[str], dict[str, str]]:
    """ISO codes and a folded-name index, built from the repo's places file plus aliases."""
    payload = json.loads(PLACES_PATH.read_text(encoding="utf-8"))
    kinds = payload["kinds"]
    codes: set[str] = set()
    index: dict[str, str] = {}
    for entry in payload["entries"]:
        if kinds[entry[1]] != "country":
            continue
        name, iso = entry[0], entry[3]
        codes.add(iso)
        index[_fold(name)] = iso
    for iso, names in payload.get("aliases", {}).items():
        codes.add(iso)
        for name in names:
            index.setdefault(_fold(name), iso)
    for name, iso in EXTRA_COUNTRY_ALIASES.items():
        index.setdefault(_fold(name), iso)
    return frozenset(codes), index


def iso_for_country(value: str | None) -> str | None:
    """Map a country name or ISO alpha-2 code to ISO alpha-2. Unmatched names return None."""
    text = normalise_text(value)
    if not text or text.casefold() in NOT_A_COUNTRY:
        return None
    # A stray trailing "<" appears on some BFFP values ("Kenya<"); the name before it is kept.
    text = text.rstrip("<").strip()
    if not text:
        return None
    codes, index = _country_tables()
    if len(text) == 2 and text.upper() in codes:
        return text.upper()
    return index.get(_fold(text))


@lru_cache(maxsize=1)
def _m49_by_code() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for subregion, codes in M49_SUBREGIONS.items():
        for code in codes.split():
            mapping[code] = subregion
    return mapping


def m49_subregion(iso: str | None) -> str:
    """The UN M49 sub-region name for an ISO code, or ``region_unknown``."""
    if iso is None:
        return UNKNOWN_REGION
    return _m49_by_code().get(iso, UNKNOWN_REGION)


def ambassador_region_map(registry: Registry) -> dict[str, str]:
    """Country code -> registry slug, for regions whose predicate is one country code only.

    Subnational regions (predicates with subdivision or institution rules) are not included: a
    country code alone cannot place a record in them (A4-C3). Codes claimed by two regions are
    left out.
    """
    owners: dict[str, set[str]] = {}
    for region in registry.by_tier():
        predicate = region.predicate
        if predicate is None or region.status == "retired":
            continue
        other_rules = (
            predicate.openalex_institution_filter,
            predicate.institution_registry,
            predicate.ror_subdivision_codes,
            predicate.institution_region_names,
            predicate.raw_affiliation_terms,
            predicate.ca_basis_values,
        )
        if len(predicate.country_codes) != 1 or any(other_rules):
            continue
        owners.setdefault(predicate.country_codes[0], set()).add(region.slug)
    return {code: next(iter(slugs)) for code, slugs in owners.items() if len(slugs) == 1}


def region_for(iso: str | None, ambassador_map: Mapping[str, str]) -> tuple[str | None, str]:
    """Return (ambassador_region slug or None, M49 sub-region or region_unknown)."""
    if iso is None:
        return None, UNKNOWN_REGION
    return ambassador_map.get(iso), m49_subregion(iso)


# ---------------------------------------------------------------------------
# Identity and classification
# ---------------------------------------------------------------------------


def group_id_for(name: str, iso: str | None, domain: str | None) -> str:
    """Stable id: ``cg_`` plus 16 hex digits of sha256 over (casefolded name, country, domain)."""
    material = "\x1f".join([name.casefold(), iso or "", domain or ""])
    return "cg_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _tokens(name: str) -> list[str]:
    return _TOKEN_RE.findall(name)


def _looks_personal(name: str) -> bool:
    """Two or three capitalised alphabetic words, for example 'Example Person'."""
    tokens = _tokens(name)
    if not 2 <= len(tokens) <= 3 or len(tokens) != len(name.split()):
        return False
    return all(t.isalpha() and t[0].isupper() and t[1:].islower() for t in tokens)


def _has_org_keyword(name: str) -> bool:
    return any(token.casefold() in ORG_KEYWORDS for token in _tokens(name))


def _is_personal_profile(url: str) -> bool:
    parts = urlsplit(url)
    host = _host(url)
    segments = [s for s in parts.path.split("/") if s]
    first = segments[0].casefold() if segments else ""
    if host in ORCID_HOSTS:
        return True
    return host in SOCIAL_HOSTS and first in PERSONAL_PATH_SEGMENTS


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


@dataclass(frozen=True)
class Verdict:
    org_status: str
    reason: str = ""


def classify(name: str, url: str | None) -> Verdict:
    """Decide the org_status of a source-listed entry. Heuristics only demote (A4-D20)."""
    # An email address as the "organisation" name is a personal identifier (seen 2026-11-26, many of
    # them phone-to-SMS gateways); never admitted, never written (V8). No count is kept (A4-D24).
    if EMAIL_RE.search(name or "") or (url and EMAIL_RE.search(url)):
        return Verdict("excluded_individual", "email address as name or website")
    if url:
        domain = registrable_domain(url)
        if domain in FREE_MAIL_DOMAINS:
            return Verdict("excluded_individual", "free-mail website")
        if _is_personal_profile(url):
            return Verdict("excluded_individual", "personal profile URL")
    if not name:
        return Verdict("ambiguous", "no name")
    if url is None and _looks_personal(name) and not _has_org_keyword(name):
        return Verdict("ambiguous", "personal-looking name without a website")
    return Verdict("source_declared_org")


# ---------------------------------------------------------------------------
# Placeholders, merge keys and reviewed decisions (CG-ROSTER-QC)
# ---------------------------------------------------------------------------


def is_placeholder_name(name: str) -> bool:
    """True for a name with no letter or digit, or a stand-in word from PLACEHOLDER_NAMES."""
    text = name.strip().casefold()
    return text in PLACEHOLDER_NAMES or not any(ch.isalnum() for ch in text)


def merge_key(name: str) -> str:
    """Key for the automatic merge: equal keys within one country name the same organisation.

    The name is unescaped, accent-free and casefolded. A leading "the" and legal-form tokens are
    removed, and every other run of non-word characters becomes a space. Generic words such as
    Foundation are kept, so those pairs are reviewed rather than merged.
    """
    text = html.unescape(name or "")
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()
    tokens = _NON_WORD_RE.sub(" ", stripped).split()
    if tokens[:1] == ["the"]:
        tokens = tokens[1:]
    kept: list[str] = []
    index = 0
    while index < len(tokens):
        if tuple(tokens[index : index + 2]) in LEGAL_FORM_PAIRS:
            index += 2
            continue
        if tokens[index] not in LEGAL_FORM_TOKENS:
            kept.append(tokens[index])
        index += 1
    return " ".join(kept)


def apply_name_correction(record: dict[str, Any], corrected: str) -> None:
    """Replace a display name; the old name joins name_alt. A name already equal is left alone."""
    if record["name"] == corrected:
        return
    previous = record["name"]
    alternates = [alt for alt in record["name_alt"] if alt != corrected]
    if previous not in alternates:
        alternates.append(previous)
    record["name"] = corrected
    record["name_alt"] = alternates


def _absorb(keep: dict[str, Any], drop: dict[str, Any]) -> None:
    """Move the dropped record's names into the kept record's name_alt, without repeats."""
    for name in [drop["name"], *drop["name_alt"]]:
        if name != keep["name"] and name not in keep["name_alt"]:
            keep["name_alt"].append(name)


def _keeper_rank(record: Mapping[str, Any]) -> tuple[bool, bool, int, str]:
    # Sort order: has a website, no "??" in the name, longer name, lowest group_id.
    return (record["url"] is None, "??" in record["name"], -len(record["name"]), record["group_id"])


def auto_merge(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Collapse records whose merge keys match within one country. Returns (records, merge log)."""
    clusters: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in records:
        key = merge_key(record["name"])
        if record["country"] is not None and key:
            clusters.setdefault((record["country"], key), []).append(record)
    dropped: set[str] = set()
    log: list[dict[str, str]] = []
    for (country, _key), members in clusters.items():
        if len(members) < 2:
            continue
        members.sort(key=_keeper_rank)
        keep = members[0]
        for drop in members[1:]:
            _absorb(keep, drop)
            dropped.add(drop["group_id"])
            log.append(
                {
                    "group_id_keep": keep["group_id"],
                    "group_id_drop": drop["group_id"],
                    "country": country,
                    "name_keep": keep["name"],
                    "name_drop": drop["name"],
                }
            )
    return [r for r in records if r["group_id"] not in dropped], log


def read_merges(path: Path) -> list[dict[str, str]]:
    """Reviewed merge decisions (curation/group_merges.csv). Header-only or missing gives []."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in MERGE_HEADER if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"{path.name} is missing column(s) {', '.join(missing)}")
        rows = [{c: (row.get(c) or "").strip() for c in MERGE_HEADER} for row in reader]
    for row in rows:
        if row["decision"] not in MERGE_DECISIONS:
            raise ValueError(f"{path.name}: decision must be same or different")
        keep, drop = row["group_id_keep"], row["group_id_drop"]
        if not keep or not drop or keep == drop:
            raise ValueError(f"{path.name}: each row needs two different group ids")
    return rows


def decided_pairs(
    merges: Iterable[Mapping[str, str]], decision: str | None = None
) -> set[frozenset[str]]:
    """Unordered id pairs with a reviewed decision (or with the given decision only)."""
    return {
        frozenset((m["group_id_keep"], m["group_id_drop"]))
        for m in merges
        if decision is None or m["decision"] == decision
    }


def apply_reviewed_merges(
    records: list[dict[str, Any]], merges: Iterable[Mapping[str, str]]
) -> tuple[list[dict[str, Any]], int, int]:
    """Apply "same" decisions. Returns (records, applied, unmatched); unknown ids are unmatched."""
    by_id = {r["group_id"]: r for r in records}
    applied = unmatched = 0
    for row in merges:
        if row["decision"] != "same":
            continue
        keep = by_id.get(row["group_id_keep"])
        drop = by_id.get(row["group_id_drop"])
        if keep is None or drop is None:
            unmatched += 1
            continue
        _absorb(keep, drop)
        del by_id[row["group_id_drop"]]
        applied += 1
    return [r for r in records if r["group_id"] in by_id], applied, unmatched


def read_name_corrections(path: Path) -> dict[str, str]:
    """group_id -> corrected name from curation/group_name_corrections.csv; the last row wins."""
    if not path.exists():
        return {}
    corrections: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            name = normalise_text(row.get("name"))
            if not name:
                raise ValueError(f"{path.name} has a row with no name")
            corrections[(row.get("group_id") or "").strip()] = name
    return corrections


def _is_broken_url(url: str) -> bool:
    """A URL with a second scheme inside it, for example 'http://a.org/http://b.org'."""
    rest = url.split("://", 1)[-1].lower()
    return "http:" in rest or "https:" in rest or _host(url).startswith("http")


def _host_matches(host: str, hosts: frozenset[str]) -> bool:
    return any(host == h or host.endswith("." + h) for h in hosts)


def excluded_host(url: str | None) -> bool:
    """True for a social, shared or link-shortener host, or a broken URL: never a duplicate key."""
    if not url:
        return False
    host = _host(url)
    return (
        _is_broken_url(url) or not host or _host_matches(host, SOCIAL_HOSTS | SHARED_HOST_SUFFIXES)
    )


def same_host_pairs(records: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Pairs in one country whose websites share an exact host (input to the review queue)."""
    clusters: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for record in records:
        url = record.get("url")
        if not url or record.get("country") is None or excluded_host(url):
            continue
        clusters.setdefault((record["country"], _host(url)), []).append(record)
    pairs: list[dict[str, str]] = []
    for (country, host), members in sorted(clusters.items()):
        for first, second in itertools.combinations(members, 2):
            pairs.append(
                {
                    "country": country,
                    "reason": "same website host",
                    "host": host,
                    "group_id_a": first["group_id"],
                    "name_a": first["name"],
                    "group_id_b": second["group_id"],
                    "name_b": second["name"],
                }
            )
    return pairs


# ---------------------------------------------------------------------------
# Admission
# ---------------------------------------------------------------------------


@dataclass
class AdmissionResult:
    """Output of one admission pass. Only ``records`` is public; the rest stays local."""

    records: list[dict[str, Any]]
    admitted_by_status: dict[str, int]
    fetched: int
    excluded: int
    ambiguous: list[dict[str, str]] = field(default_factory=list)
    duplicates_collapsed: int = 0
    dupe_review: list[dict[str, str]] = field(default_factory=list)
    placeholders: int = 0
    auto_merges: list[dict[str, str]] = field(default_factory=list)
    reviewed_merges_applied: int = 0
    reviewed_merges_unmatched: int = 0


def _similar_names(a: str, b: str) -> bool:
    key_a = " ".join(sorted(set(t.casefold() for t in _tokens(a))))
    key_b = " ".join(sorted(set(t.casefold() for t in _tokens(b))))
    return difflib.SequenceMatcher(None, key_a, key_b).ratio() >= NEAR_DUPLICATE_RATIO


def _near_duplicates(
    records: list[dict[str, Any]], suppressed: set[frozenset[str]] = frozenset()
) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    by_country: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if record["country"] is not None:
            by_country.setdefault(record["country"], []).append(record)
    for country, group in sorted(by_country.items()):
        for index, first in enumerate(group):
            for second in group[index + 1 :]:
                same_domain = (
                    first["_domain"] is not None
                    and first["_domain"] == second["_domain"]
                    and first["_domain"] not in SOCIAL_HOSTS
                )
                if same_domain:
                    reason = "same registrable domain"
                elif _similar_names(first["name"], second["name"]):
                    reason = "similar name"
                else:
                    continue
                if frozenset((first["group_id"], second["group_id"])) in suppressed:
                    continue
                pairs.append(
                    {
                        "country": country,
                        "reason": reason,
                        "group_id_a": first["group_id"],
                        "name_a": first["name"],
                        "group_id_b": second["group_id"],
                        "name_b": second["name"],
                    }
                )
    return pairs


def admit(
    entries: Iterable[RawEntry],
    *,
    retrieved_on: str,
    registry: Registry | None = None,
    merges: Iterable[Mapping[str, str]] = (),
) -> AdmissionResult:
    """Normalise, classify, dedupe and map regions for a fetched list of raw entries.

    ``merges`` holds the reviewed decisions from curation/group_merges.csv (see read_merges).
    """
    ambassador_map = ambassador_region_map(registry or load_registry())
    rows = list(entries)
    merges = list(merges)
    excluded = 0
    placeholders = 0
    ambiguous: list[dict[str, str]] = []
    seen: dict[str, dict[str, Any]] = {}
    duplicates = 0

    for row in rows:
        raw_name = normalise_text(row.organization)
        iso = iso_for_country(row.country)
        url = normalise_url(row.website)
        domain = registrable_domain(url)
        # The id hashes the raw normalised name (entities included), so cleaning never changes it.
        group_id = group_id_for(raw_name, iso, domain)
        display = clean_display_name(html.unescape(raw_name))
        verdict = classify(display, url)
        if verdict.org_status == "source_declared_org" and is_placeholder_name(display):
            verdict = Verdict("ambiguous", "placeholder name")
            placeholders += 1
        if verdict.org_status == "excluded_individual":
            excluded += 1
            continue
        if verdict.org_status == "ambiguous":
            ambiguous.append(
                {
                    "group_id": group_id,
                    "name": display,
                    "country": iso or "",
                    "url": url or "",
                    "reason": verdict.reason,
                }
            )
            continue
        if group_id in seen:
            duplicates += 1
            kept = seen[group_id]
            if display != kept["name"] and display not in kept["name_alt"]:
                kept["name_alt"].append(display)
            continue
        ambassador, region = region_for(iso, ambassador_map)
        seen[group_id] = {
            "group_id": group_id,
            "name": display,
            "name_alt": [],
            "country": iso,
            "region": region,
            "ambassador_region": ambassador,
            "url": url,
            "bffp_listed": True,
            "bffp_listed_asof": retrieved_on,
            "org_status": verdict.org_status,
            "roster_retrieved_at": retrieved_on,
            "_domain": domain,
        }

    admitted = sorted(seen.values(), key=lambda r: (r["country"] or "", r["name"]))
    admitted, auto_log = auto_merge(admitted)
    admitted, applied, unmatched = apply_reviewed_merges(admitted, merges)
    dupe_review = _near_duplicates(admitted, decided_pairs(merges, "different"))
    records = [{k: v for k, v in r.items() if k != "_domain"} for r in admitted]
    by_status = {status: 0 for status in ADMITTED_STATUSES}
    for record in records:
        by_status[record["org_status"]] += 1
    return AdmissionResult(
        records=records,
        admitted_by_status=by_status,
        fetched=len(rows),
        excluded=excluded,
        ambiguous=ambiguous,
        duplicates_collapsed=duplicates,
        dupe_review=dupe_review,
        placeholders=placeholders,
        auto_merges=auto_log,
        reviewed_merges_applied=applied,
        reviewed_merges_unmatched=unmatched,
    )


def render_csv(header: list[str], rows: Iterable[Mapping[str, Any]]) -> str:
    """CSV text for the local quarantine and review files (never published)."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()
