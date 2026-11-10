"""Schema checks and loading for the curated monitoring-source registry."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

DEFAULT_REGISTRY_PATH = Path("config/datasets.yml")
TIERS = {"A", "B", "C", "D"}
ENTITY_TYPES = {"dataset", "program", "literature_dataset", "planned_program"}
PROVENANCE_TYPES = {
    "dataset_record",
    "official_program",
    "literature_secondary",
    "planning_record",
    "journal_article_si",
}


class RegistryValidationError(ValueError):
    """Raised when the monitoring registry does not meet its versioned contract."""


def _require(mapping: Any, key: str, context: str) -> Any:
    if not isinstance(mapping, dict) or key not in mapping:
        raise RegistryValidationError(f"{context} requires {key!r}")
    return mapping[key]


def _http_url(value: Any, context: str) -> None:
    if not isinstance(value, str):
        raise RegistryValidationError(f"{context} must be a URL string")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RegistryValidationError(f"{context} must use an absolute HTTPS URL")


def validate_registry(payload: Any, *, minimum_entries: int = 15) -> dict[str, Any]:
    """Validate required registry fields without implying data quality or reuse rights."""
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise RegistryValidationError("registry schema_version must be 1")
    entries = payload.get("datasets")
    if not isinstance(entries, list):
        raise RegistryValidationError("registry datasets must be a list")

    seen: set[str] = set()
    eligible_identities: set[str] = set()
    for index, entry in enumerate(entries):
        context = f"datasets[{index}]"
        entry_id = _require(entry, "id", context)
        if not isinstance(entry_id, str) or not entry_id.strip() or entry_id in seen:
            raise RegistryValidationError(f"{context}.id must be non-empty and unique")
        seen.add(entry_id)
        for field in ("name", "steward", "region", "access_tier", "entity_type", "status"):
            value = _require(entry, field, context)
            if not isinstance(value, str) or not value.strip():
                raise RegistryValidationError(f"{context}.{field} must be non-empty text")
        if entry["access_tier"] not in TIERS:
            raise RegistryValidationError(f"{context}.access_tier must be one of {sorted(TIERS)}")
        if entry["entity_type"] not in ENTITY_TYPES:
            raise RegistryValidationError(
                f"{context}.entity_type must be one of {sorted(ENTITY_TYPES)}"
            )
        if not isinstance(_require(entry, "seed_eligible", context), bool):
            raise RegistryValidationError(f"{context}.seed_eligible must be boolean")
        if entry["seed_eligible"]:
            underlying_id = _require(entry, "underlying_dataset_id", context)
            if not isinstance(underlying_id, str) or not underlying_id.strip():
                raise RegistryValidationError(
                    f"{context}.underlying_dataset_id must be non-empty text"
                )
            if underlying_id in eligible_identities:
                raise RegistryValidationError(
                    f"verified seed entries must have distinct underlying datasets: {underlying_id}"
                )
            eligible_identities.add(underlying_id)
        provenance_type = _require(entry, "provenance_type", context)
        if provenance_type not in PROVENANCE_TYPES:
            raise RegistryValidationError(
                f"{context}.provenance_type must be one of {sorted(PROVENANCE_TYPES)}"
            )

        for field in ("sample_matrix", "plastic_classes", "format"):
            values = _require(entry, field, context)
            if (
                not isinstance(values, list)
                or not values
                or any(not isinstance(value, str) or not value.strip() for value in values)
            ):
                raise RegistryValidationError(f"{context}.{field} must be a non-empty text list")

        _http_url(_require(entry, "url", context), f"{context}.url")
        _http_url(_require(entry, "provenance_url", context), f"{context}.provenance_url")
        if entry["seed_eligible"]:
            _http_url(_require(entry, "verification_url", context), f"{context}.verification_url")
        raw_checked = _require(entry, "last_checked", context)
        try:
            checked = (
                raw_checked if isinstance(raw_checked, date) else date.fromisoformat(raw_checked)
            )
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError(f"{context}.last_checked must be ISO date") from exc
        if checked > date.today():
            raise RegistryValidationError(f"{context}.last_checked cannot be in the future")

        for field in ("access_method", "cadence", "license", "provenance_note"):
            value = _require(entry, field, context)
            if not isinstance(value, str) or not value.strip():
                raise RegistryValidationError(f"{context}.{field} must be non-empty text")
        if entry["seed_eligible"]:
            for field in ("evidence_excerpt", "evidence_identity"):
                value = _require(entry, field, context)
                if not isinstance(value, str) or not value.strip():
                    raise RegistryValidationError(f"{context}.{field} must be non-empty text")
            if len(entry["evidence_excerpt"]) > 240:
                raise RegistryValidationError(
                    f"{context}.evidence_excerpt must be at most 240 characters"
                )
        if entry["license"].casefold() in {"unknown", "tbd", ""}:
            raise RegistryValidationError(
                f"{context}.license must explain unknown rights explicitly, not use a blank label"
            )
    eligible = sum(entry["seed_eligible"] for entry in entries)
    if eligible < minimum_entries:
        raise RegistryValidationError(
            f"registry requires at least {minimum_entries} verified seed entries; found {eligible}"
        )
    eligible_urls = {entry["url"] for entry in entries if entry["seed_eligible"]}
    if len(eligible_urls) != eligible:
        raise RegistryValidationError("verified seed entries must have distinct source URLs")
    return payload


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, Any]:
    """Read and validate the repository's curated registry."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return validate_registry(payload)
