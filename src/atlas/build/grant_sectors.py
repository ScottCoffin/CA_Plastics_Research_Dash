"""Recipient sector and funder agency for grants (Funding visualizations).

Rules live in ``config/grant_sectors.yml``: exact organisation names win, then ordered
regex rules, then known registry types (``UC``, ``CSU`` -> academia, ...). The funder agency
is the first mapped element of ``funder_chain`` after skipping parent departments.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH = Path("config/grant_sectors.yml")
REGISTRY_SECTORS = {
    "UC": ("academia", "university"),
    "CSU": ("academia", "university"),
    "local-agency": ("government", "local"),
    "state-agency": ("government", "state"),
    "federal": ("government", "federal"),
    "nonprofit/NGO": ("nonprofit", "nonprofit"),
    "company": ("industry", "company"),
    "JPA": ("jpa", "regional"),
    "utility": ("government", "utility"),
    "intergovernmental-organization": ("government", "intergovernmental"),
}


def _key(text: object) -> str:
    return " ".join(str(text or "").lower().split())


@dataclass(frozen=True)
class SectorRules:
    labels: Mapping[str, str]
    names: Mapping[str, tuple[str, str]]
    rules: Sequence[tuple[str, str, re.Pattern[str]]]
    agencies: Mapping[str, str]
    parents: frozenset[str]

    def sector(self, org: object, institution_type: object = None) -> tuple[str, str]:
        name = _key(org)
        if not name:
            return "unknown", "unknown"
        if name in self.names:
            return self.names[name]
        for sector, detail, pattern in self.rules:
            if pattern.search(str(org)):
                return sector, detail
        return REGISTRY_SECTORS.get(str(institution_type or ""), ("unknown", "unknown"))

    def agency(self, chain: Sequence[object] | None, funder: object = None) -> str:
        for element in [*(chain or []), funder]:
            key = _key(element)
            if not key or key in self.parents:
                continue
            return self.agencies.get(key, str(element).strip())
        return "Unknown funder"


def load_sector_rules(path: str | Path = DEFAULT_PATH) -> SectorRules:
    raw: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    labels = dict(raw.get("sectors") or {})
    names = {_key(k): (v[0], v[1]) for k, v in (raw.get("names") or {}).items()}
    rules = [
        (sector, detail, re.compile(pattern, re.IGNORECASE))
        for sector, detail, pattern in raw.get("rules") or []
    ]
    for sector, _detail in [*names.values(), *((s, d) for s, d, _p in rules)]:
        if sector not in labels:
            raise ValueError(f"{path}: sector {sector!r} has no label")
    return SectorRules(
        labels=labels,
        names=names,
        rules=rules,
        agencies={_key(k): str(v) for k, v in (raw.get("funder_agencies") or {}).items()},
        parents=frozenset(_key(p) for p in raw.get("parent_departments") or []),
    )
