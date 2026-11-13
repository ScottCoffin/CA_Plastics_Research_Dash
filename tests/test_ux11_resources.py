"""UX-11: Related resources show one reuse badge and the stewards stated on their own pages."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "framework" / "src" / "components" / "resources.js"
PAYLOAD = ROOT / "site" / "data" / "linkouts.json"


def test_card_uses_a_single_badge_instead_of_not_stated_fields() -> None:
    js = JS.read_text(encoding="utf-8")
    assert js.count("Reuse terms not recorded") == 1
    assert 'labelled("Terms", entry.terms ?? entry.terms_status)' not in js
    assert "entry.update_model !== NOT_STATED" in js
    assert "entry.steward_source" in js


def test_known_stewards_are_filled_with_a_source_link() -> None:
    entries = {
        row["name"]: row for row in json.loads(PAYLOAD.read_text(encoding="utf-8"))["entries"]
    }
    ncei = entries["NOAA NCEI Marine Microplastics"]
    assert ncei["steward"] == "NOAA National Centers for Environmental Information"
    assert ncei["steward_source"].startswith("https://www.ncei.noaa.gov/")
    plastiverse = entries["Plastiverse tools directory"]
    assert plastiverse["steward"] == "Plastiverse"
    assert plastiverse["steward_source"].startswith("https://www.plastiverse.org/")
    assert all("steward_source" in row for row in entries.values())
