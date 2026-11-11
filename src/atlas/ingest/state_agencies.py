"""California state agencies that have no OpenAlex institution record.

OpenAlex links OEHHA to the CalEPA umbrella and the State Water Board, Regional Water
Quality Control Boards and State Lands Commission to "State of California". This module
loads ``config/ca_state_agencies.yml`` and resolves such agencies from raw-affiliation
strings so the atlas can show each body separately (S1.2-AGENCIES, 2026-11-11).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH = Path("config/ca_state_agencies.yml")
# OpenAlex umbrella records that stand in for agencies they do not model.
UMBRELLA_IDS = frozenset({"I65137940", "I4389425283"})  # CalEPA, State of California
_BOARD = r"(?:regional water quality control board|regional water board|water board)"


@dataclass(frozen=True)
class StateAgency:
    id: str
    name: str
    short_name: str
    atlas_type: str
    parent_id: str
    parent_name: str
    city: str
    region: str
    lat: float
    lon: float
    patterns: tuple[re.Pattern[str], ...]


def region_board_patterns(region: str, number: int) -> list[str]:
    """Strict patterns for one Regional Water Quality Control Board."""

    return [
        rf"\b{region}\b.{{0,40}}?\b{_BOARD}\b",
        rf"\b{_BOARD}\b.{{0,40}}?\b{region}\b",
        rf"\b{_BOARD}\b[\s,(\-]*region\s*\(?{number}\b",
    ]


def load_state_agencies(path: str | Path = DEFAULT_PATH) -> list[StateAgency]:
    raw: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    agencies: list[StateAgency] = []
    seen: set[str] = set()
    for entry in raw.get("agencies", []):
        agency_id = str(entry["id"])
        if agency_id in seen:
            raise ValueError(f"duplicate state agency id: {agency_id}")
        seen.add(agency_id)
        patterns = list(entry.get("patterns") or [])
        if entry.get("region_pattern"):
            patterns += region_board_patterns(
                str(entry["region_pattern"]), int(entry["region_number"])
            )
        if not patterns:
            raise ValueError(f"state agency {agency_id} has no patterns")
        agencies.append(
            StateAgency(
                id=agency_id,
                name=str(entry["name"]),
                short_name=str(entry.get("short_name") or entry["name"]),
                atlas_type=str(entry.get("atlas_type") or "state-agency"),
                parent_id=str(entry.get("parent_id") or ""),
                parent_name=str(entry.get("parent_name") or ""),
                city=str(entry.get("city") or ""),
                region=str(entry.get("region") or "California"),
                lat=float(entry["lat"]),
                lon=float(entry["lon"]),
                patterns=tuple(re.compile(p, re.IGNORECASE) for p in patterns),
            )
        )
    return agencies


def match_state_agencies(raw_affiliation: str, agencies: Iterable[StateAgency]) -> list[str]:
    """Agency ids named by any ``" | "``-separated raw-affiliation string, in config order."""

    segments = [part for part in raw_affiliation.split(" | ") if part.strip()]
    return [
        agency.id
        for agency in agencies
        if any(pattern.search(segment) for segment in segments for pattern in agency.patterns)
    ]


def apply_state_agencies(institution_ids: Sequence[str], matched: Sequence[str]) -> list[str]:
    """Add matched agency ids and drop the umbrellas they replace (no double counting)."""

    if not matched:
        return list(institution_ids)
    kept = [value for value in institution_ids if value not in UMBRELLA_IDS]
    return list(dict.fromkeys([*kept, *matched]))


def registry_row(agency: StateAgency) -> dict[str, Any]:
    """Normalized-institutions row for a synthetic agency."""

    return {
        "inst_id": agency.id,
        "ror": "",
        "name": agency.name,
        "city": agency.city,
        "region": agency.region,
        "lat": agency.lat,
        "lon": agency.lon,
        "ror_types": ["government"],
        "atlas_type": agency.atlas_type,
        "parent_system": agency.parent_id,
        "ca_flag": True,
    }
