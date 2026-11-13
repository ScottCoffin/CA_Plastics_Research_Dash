"""UX-7: glossary page, footer link, and inline term links on Institutions and Experts."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK = ROOT / "framework"
GLOSSARY = FRAMEWORK / "src" / "glossary.md"
CONFIG = FRAMEWORK / "observablehq.config.js"
INSTITUTIONS = FRAMEWORK / "src" / "institutions.md"
EXPERTS = FRAMEWORK / "src" / "experts.md"

GLOSSARY_IDS = [
    "access-tiers",
    "tier",
    "fractional-works",
    "bootstrap-interval",
    "rank-range",
    "rising-percentile",
    "m-quotient",
    "ca-led",
    "ca-sampled",
    "matrix",
    "plastic-related",
    "licences",
]


def _anchor_ids(markup: str) -> set[str]:
    return set(re.findall(r'<dt id="([^"]+)"', markup))


def _links(markup: str) -> set[str]:
    return set(re.findall(r'href="\./glossary#([^"]+)"', markup))


def test_glossary_has_anchor_for_every_term() -> None:
    markup = GLOSSARY.read_text(encoding="utf-8")
    assert markup.startswith("---\ntitle: Glossary\n---")
    assert len(re.findall(r"^# ", markup, flags=re.MULTILINE)) == 1
    ids = _anchor_ids(markup)
    missing = [term for term in GLOSSARY_IDS if term not in ids]
    assert missing == []


def test_glossary_entries_have_source_notes_and_no_task_ids() -> None:
    markup = GLOSSARY.read_text(encoding="utf-8")
    assert len(_anchor_ids(markup)) == markup.count("<dt id=")
    assert markup.count("<dt id=") == markup.count("Source:")
    assert not re.search(r"\b(EM|UX|AT|S\d)[-.]\d", markup)


def test_footer_links_to_glossary_and_page_is_listed() -> None:
    config = CONFIG.read_text(encoding="utf-8")
    assert '{name: "Glossary", path: "/glossary"}' in config
    assert 'href="./glossary">Glossary</a>' in config
    about = config.index('name: "About"')
    glossary = config.index('name: "Glossary"')
    assert about < glossary


def test_institutions_and_experts_link_to_glossary_anchors() -> None:
    inst_links = _links(INSTITUTIONS.read_text(encoding="utf-8"))
    exp_links = _links(EXPERTS.read_text(encoding="utf-8"))
    assert {"tier", "rank-range", "bootstrap-interval", "fractional-works"} <= inst_links
    assert {"m-quotient", "rising-percentile", "ca-led", "plastic-related"} <= exp_links
    known = set(GLOSSARY_IDS)
    assert (inst_links | exp_links) <= known
