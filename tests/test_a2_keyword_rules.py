"""EM-1: Add-on A2 keyword rules stay aligned with the taxonomy and behave."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RULES = yaml.safe_load((ROOT / "config/a2_keyword_rules.yml").read_text(encoding="utf-8"))
TAXONOMY = yaml.safe_load((ROOT / "config/taxonomy.yml").read_text(encoding="utf-8"))["add_on_a2"]


def _fires(rule: dict[str, Any], text: str) -> bool:
    """Reference semantics from the rule file header (EM-4 owns the production matcher)."""
    text = unicodedata.normalize("NFKC", text)

    def hit(key: str) -> bool:
        return any(re.search(p, text, re.IGNORECASE) for p in rule.get(key, []))

    if not hit("any"):
        return False
    if "require_any" in rule and not hit("require_any"):
        return False
    return not hit("exclude")


def _all_rules() -> list[tuple[str, dict[str, Any]]]:
    return [*RULES["keyword_flags"].items(), *RULES["product_type"].items()]


def test_rule_ids_match_taxonomy_exactly() -> None:
    assert set(RULES["keyword_flags"]) == set(TAXONOMY["keyword_flags"])
    assert set(RULES["product_type"]) == set(TAXONOMY["product_type"])
    assert len(TAXONOMY["keyword_flags"]) == 20


def test_rules_are_well_formed_and_compile() -> None:
    for name, rule in _all_rules():
        assert set(rule) <= {"any", "require_any", "exclude", "notes"}, name
        assert rule["any"], name
        for key in ("any", "require_any", "exclude"):
            for pattern in rule.get(key, []):
                re.compile(pattern, re.IGNORECASE)


def test_parent_subtype_map_uses_known_product_types() -> None:
    known = set(TAXONOMY["product_type"])
    for parent, children in TAXONOMY["product_type_parents"].items():
        assert parent in known
        assert set(children) <= known


@pytest.mark.parametrize(
    ("rule_id", "text", "expected"),
    [
        ("kw_tire_wear", "Tire wear particles in urban stormwater runoff", True),
        ("kw_tire_wear", "The entire watershed was sampled for microplastic particles", False),
        ("kw_tire_wear", "Tire pressure monitoring and fuel economy", False),
        ("kw_fibers", "Synthetic microfibers released during laundering", True),
        ("kw_fibers", "Dietary fiber intake and gut health", False),
        ("kw_ballast_water", "Microplastics in ship ballast water", True),
        ("kw_water_column", "Depth-resolved microplastic profiles in the water column", True),
        ("kw_mobility_transport", "Chemical migration of additives from packaging", False),
        ("kw_cost_accreditation", "Reducing analytical costs of microplastic monitoring", True),
        ("kw_cost_accreditation", "The cost of plastic pollution to tourism", False),
        ("kw_equity_ej_tribal", "Tribal engagement in plastic monitoring", True),
        ("kw_equity_ej_tribal", "Private equity markets for packaging firms", False),
        ("kw_small_particles", "Detection of particles below 20 µm in drinking water", True),
        ("food_contact_tea_bags", "Plastic tea bags release billions of particles", True),
        ("cigarette_filters", "Cigarette butts as a source of microfibers", True),
        ("paints_coatings", "Paint particles shed from road markings as microplastics", True),
        ("paints_coatings", "A painted thin section of rock", False),
    ],
)
def test_rule_examples(rule_id: str, text: str, expected: bool) -> None:
    rules = dict(_all_rules())
    assert _fires(rules[rule_id], text) is expected
