"""UX-29: the "Current affiliation" filter and the "Now outside California" badge on the
Framework Experts page, the classic Experts tab and the expert profile page, plus the
glossary entry."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FW_SRC = ROOT / "framework" / "src"
MODEL = FW_SRC / "components" / "experts_model.js"
COMPONENT = FW_SRC / "components" / "experts.js"
CSS = FW_SRC / "components" / "experts.css"
EXPERTS_PAGE = FW_SRC / "experts.md"
GLOSSARY = FW_SRC / "glossary.md"
CLASSIC = ROOT / "site" / "index.html"
PROFILE = ROOT / "site" / "expert.html"

OPTIONS = [
    '<option value="">Any</option>',
    '<option value="ca">In California now</option>',
    '<option value="outside">Outside California now</option>',
    '<option value="unknown">Unknown</option>',
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    light, dark = sorted([_luminance(a), _luminance(b)], reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _badge_colours(text: str) -> tuple[str, str]:
    rule = re.search(r"\.now-badge \{[^}]*\}", text)
    assert rule, "a .now-badge rule must exist"
    colour = re.search(r"(?<![-\w])color: (#[0-9a-fA-F]{6});", rule.group(0))
    background = re.search(r"background: (#[0-9a-fA-F]{6});", rule.group(0))
    assert colour and background, rule.group(0)
    return colour.group(1), background.group(1)


def test_framework_filter_options_and_hash_key() -> None:
    page = _read(EXPERTS_PAGE)
    assert '<label for="now-filter">' in page and 'name="now"' in page
    for option in OPTIONS:
        assert option in page, option
    assert "./glossary#current-affiliation" in page, "the filter label links to the glossary entry"
    assert page.index('id="now-filter"') < page.index('id="early-filter"'), (
        "placed beside Career stage"
    )
    model = _read(MODEL)
    assert 'NOW_VALUES = ["", "ca", "outside", "unknown"]' in model
    assert 'params.set("now", filters.now)' in model
    assert 'pick("now")' in model
    component = _read(COMPONENT)
    assert '"now-filter"' in component
    assert '$("now-filter").value = f.now;' in component
    assert 'now: $("now-filter").value' in component


def test_framework_badge_text_and_helpers() -> None:
    model = _read(MODEL)
    assert "Now outside California" in model
    assert "last California affiliation" in model
    assert "current_in_ca !== false" in model
    assert "Number.isInteger(author.last_ca_year)" in model
    assert "currentAffiliationHtml(author)" in model


def test_classic_tab_has_same_select_key_and_badge() -> None:
    html = _read(CLASSIC)
    select = html.index('<select id="now-filter" name="now">')
    career = html.index("Career stage")
    tag = html.index('<select id="tag-filter"')
    assert career < select < tag, "the select sits next to the Career stage field"
    for option in OPTIONS:
        assert option in html, option
    assert 'state.now = ["", "ca", "outside", "unknown"].includes(params.get("now")' in html
    assert 'params.set("now", state.now)' in html
    assert '"now-filter", "expert-sort", "early-filter"' in html
    assert 'state.now = ""' in html, "reset clears the filter"
    assert "currentAffiliationHtml(author)" in html
    assert "Now outside California" in html
    assert "if (state.now && currentAffiliationStatus(author) !== state.now) return false;" in html


def test_profile_page_shows_badge_under_primary_affiliation() -> None:
    html = _read(PROFILE)
    primary = html.index('id="affil-primary"')
    slot = html.index('id="expert-now"')
    assert primary < slot, "badge slot follows the primary affiliation list"
    assert 'if (author.current_in_ca !== false) return "";' in html
    assert '$("expert-now").innerHTML = currentAffiliationHtml(author);' in html
    assert "Now outside California" in html


def test_glossary_entry_has_anchor_and_definition() -> None:
    glossary = _read(GLOSSARY)
    assert '<dt id="current-affiliation">' in glossary
    entry = glossary.split('<dt id="current-affiliation">', 1)[1].split("<dt ", 1)[0]
    assert "OpenAlex" in entry
    assert "California institution registry" in entry
    assert "latest year OpenAlex lists the expert at a California institution" in entry


def test_badge_contrast_meets_aa_in_every_surface() -> None:
    for path in (CSS, CLASSIC, PROFILE):
        colour, background = _badge_colours(_read(path))
        ratio = _contrast(colour, background)
        assert ratio >= 4.5, f"{path.name}: badge contrast {ratio:.2f} is below 4.5:1"


def test_no_internal_ids_in_new_text() -> None:
    for path in (EXPERTS_PAGE, GLOSSARY, CLASSIC, PROFILE, MODEL, COMPONENT):
        assert not re.search(r"\bUX-\d+", _read(path)), path.name
