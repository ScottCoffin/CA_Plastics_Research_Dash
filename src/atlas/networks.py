"""Research networks and consortia registry (NET-1, owner request 2026-11-15).

Reads config/research_networks.yml, validates it, and builds the public payload written to
the region's ``research_networks.json``. Link, don't mirror: nothing is fetched or scraped, and the
full contributor roster is not copied (only Atlas expert IDs and the roster size).
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "config" / "research_networks.yml"
SITE_DIR = ROOT / "site"
SOURCE = "config/research_networks.yml"
SCHEMA_VERSION = 1
PAYLOAD_SCHEMA_VERSION = "net1.v1"

NETWORK_ID = re.compile(r"NET-\d+")
INSTITUTION_ID = re.compile(r"[A-Za-z0-9-]+")
AUTHOR_ID = re.compile(r"A\d+")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

TOP_KEYS = {"schema_version", "networks"}
NETWORK_REQUIRED = (
    "id",
    "name",
    "url",
    "steward",
    "steward_source",
    "description",
    "description_source",
    "focus_areas",
    "related_links",
    "host_institution_ids",
    "member_institution_ids",
    "listed_contributor_count",
    "roster_as_of",
    "atlas_contributors",
    "logo",
    "disclosure",
)
NETWORK_KEYS = {*NETWORK_REQUIRED, "name_variants", "url_status"}
LINK_KEYS = {"label", "url"}
CONTRIBUTOR_KEYS = {"author_id", "name"}
LOGO_REQUIRED = ("path", "alt", "source_url")
LOGO_KEYS = {*LOGO_REQUIRED, "treatment", "terms", "permission"}


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Parse the registry YAML; YAML syntax errors surface as ValueError."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    return data


def _matches(pattern: re.Pattern[str], value: object) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _non_empty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_https(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parts = urlparse(value)
    return parts.scheme == "https" and bool(parts.netloc)


def _string_list(value: object, *, allow_empty: bool = True) -> bool:
    if not isinstance(value, list) or (not allow_empty and not value):
        return False
    return all(_non_empty(item) for item in value)


def _id_list(value: object) -> bool:
    return isinstance(value, list) and all(_matches(INSTITUTION_ID, item) for item in value)


def _is_relative(path: str) -> bool:
    absolute = PurePosixPath(path).is_absolute() or PureWindowsPath(path).is_absolute()
    return not absolute and path[0] not in "/\\"


def validate_registry(data: Any) -> list[str]:
    """Return a list of human-readable problems; an empty list means valid."""
    if not isinstance(data, dict):
        return ["registry must be a mapping"]
    errors = [f"unknown top-level key {key}" for key in data if key not in TOP_KEYS]
    version = data.get("schema_version")
    if type(version) is not int or version != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    entries = data.get("networks")
    if not isinstance(entries, list):
        return [*errors, "networks must be a list"]
    ids = [net.get("id") for net in entries if isinstance(net, dict)]
    str_ids = [i for i in ids if isinstance(i, str)]
    for dup in sorted({i for i in str_ids if str_ids.count(i) > 1}):
        errors.append(f"duplicate id {dup}")
    for network in entries:
        if not isinstance(network, dict):
            errors.append("network must be a mapping")
            continue
        errors.extend(_validate_network(network))
    return errors


def _validate_network(network: dict[str, Any]) -> list[str]:
    label = str(network.get("id", "?"))
    errors = [f"{label}: unknown key {key}" for key in network if key not in NETWORK_KEYS]
    errors += [f"{label}: missing key {key}" for key in NETWORK_REQUIRED if key not in network]
    if not _matches(NETWORK_ID, network.get("id")):
        errors.append(f"{label}: id must match NET-<number>")
    for key in ("name", "steward", "description", "disclosure"):
        if not _non_empty(network.get(key)):
            errors.append(f"{label}: {key} must be a non-empty string")
    for key in ("url", "steward_source", "description_source"):
        if not _is_https(network.get(key)):
            errors.append(f"{label}: {key} must be an https URL")
    if "name_variants" in network and not _string_list(network["name_variants"]):
        errors.append(f"{label}: name_variants must be a list of non-empty strings")
    if not _string_list(network.get("focus_areas"), allow_empty=False):
        errors.append(f"{label}: focus_areas must be a non-empty list of strings")
    errors.extend(_validate_related_links(label, network.get("related_links")))
    host = network.get("host_institution_ids")
    member = network.get("member_institution_ids")
    for key, value in (("host_institution_ids", host), ("member_institution_ids", member)):
        if not _id_list(value):
            errors.append(f"{label}: {key} must be a list of IDs matching [A-Za-z0-9-]+")
    if isinstance(host, list) and isinstance(member, list):
        overlap = sorted({str(i) for i in host} & {str(i) for i in member})
        if overlap:
            errors.append(f"{label}: institution is both host and member: {overlap}")
    errors.extend(_validate_contributors(label, network))
    roster = network.get("roster_as_of")
    if not _matches(ISO_DATE, roster):
        errors.append(f"{label}: roster_as_of must be a YYYY-MM-DD string")
    errors.extend(_validate_logo(label, network.get("logo")))
    return errors


def _validate_related_links(label: str, links: object) -> list[str]:
    if not isinstance(links, list):
        return [f"{label}: related_links must be a list"]
    errors: list[str] = []
    for link in links:
        if not isinstance(link, dict):
            errors.append(f"{label}: related_links item must be a mapping")
            continue
        errors += [f"{label}: related_links unknown key {k}" for k in link if k not in LINK_KEYS]
        if not _non_empty(link.get("label")):
            errors.append(f"{label}: related_links label must be a non-empty string")
        if not _is_https(link.get("url")):
            errors.append(f"{label}: related_links url must be an https URL")
    return errors


def _validate_contributors(label: str, network: dict[str, Any]) -> list[str]:
    count = network.get("listed_contributor_count")
    contributors = network.get("atlas_contributors")
    errors: list[str] = []
    if type(count) is not int or count < 0:
        errors.append(f"{label}: listed_contributor_count must be a non-negative integer")
    if not isinstance(contributors, list):
        return [*errors, f"{label}: atlas_contributors must be a list"]
    for item in contributors:
        if not isinstance(item, dict):
            errors.append(f"{label}: atlas_contributors item must be a mapping")
            continue
        errors += [
            f"{label}: atlas_contributors unknown key {k}"
            for k in item
            if k not in CONTRIBUTOR_KEYS
        ]
        if not _matches(AUTHOR_ID, item.get("author_id")):
            errors.append(f"{label}: atlas_contributors author_id must match A<digits>")
        if not _non_empty(item.get("name")):
            errors.append(f"{label}: atlas_contributors name must be a non-empty string")
    if type(count) is int and count < len(contributors):
        errors.append(
            f"{label}: listed_contributor_count ({count}) is below the number of "
            f"atlas_contributors ({len(contributors)})"
        )
    return errors


def _validate_logo(label: str, logo: object) -> list[str]:
    if not isinstance(logo, dict):
        return [f"{label}: logo must be a mapping"]
    errors = [f"{label}: logo unknown key {k}" for k in logo if k not in LOGO_KEYS]
    errors += [f"{label}: logo missing key {k}" for k in LOGO_REQUIRED if k not in logo]
    if not _non_empty(logo.get("alt")):
        errors.append(f"{label}: logo.alt must be a non-empty string")
    if not _is_https(logo.get("source_url")):
        errors.append(f"{label}: logo.source_url must be an https URL")
    path = logo.get("path")
    if not _non_empty(path):
        errors.append(f"{label}: logo.path must be a non-empty string")
    elif not _is_relative(path):
        errors.append(f"{label}: logo.path must be relative to site/")
    elif ".." in re.split(r"[\\/]", path):
        errors.append(f"{label}: logo.path must not contain '..'")
    elif not (SITE_DIR / path).is_file():
        errors.append(f"{label}: logo file not found at site/{path}")
    return errors


def public_payload(data: Any) -> dict[str, Any]:
    """Return the display-only payload; raises ValueError when validate_registry fails."""
    errors = validate_registry(data)
    if errors:
        raise ValueError("invalid research networks registry: " + "; ".join(errors))
    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "source": SOURCE,
        "networks": [_public_network(network) for network in data["networks"]],
    }


def _public_network(network: dict[str, Any]) -> dict[str, Any]:
    logo = network["logo"]
    return {
        "id": network["id"],
        "name": network["name"],
        "url": network["url"],
        "steward": network["steward"],
        "steward_source": network["steward_source"],
        "description": network["description"],
        "description_source": network["description_source"],
        "focus_areas": list(network["focus_areas"]),
        "related_links": [
            {"label": link["label"], "url": link["url"]} for link in network["related_links"]
        ],
        "host_institution_ids": list(network["host_institution_ids"]),
        "member_institution_ids": list(network["member_institution_ids"]),
        "listed_contributor_count": network["listed_contributor_count"],
        "roster_as_of": network["roster_as_of"],
        "atlas_contributors": [
            {"author_id": item["author_id"], "name": item["name"]}
            for item in network["atlas_contributors"]
        ],
        "logo": {"path": logo["path"], "alt": logo["alt"]},
        "disclosure": network["disclosure"],
    }
