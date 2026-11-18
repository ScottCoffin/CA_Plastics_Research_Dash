"""VD-6c: Institutions and Institution pages adopt the shared page, control and card components."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
COMPONENTS = SRC / "components"
LIST_PAGE = SRC / "california" / "institutions.md"
DETAIL_PAGE = SRC / "california" / "institution.md"
LIST_CSS = COMPONENTS / "institutions.css"
DETAIL_CSS = COMPONENTS / "institution.css"
LIST_JS = COMPONENTS / "institutions.js"
DETAIL_JS = COMPONENTS / "institution.js"
MAP_JS = COMPONENTS / "svg_map.js"
ICONS_JS = COMPONENTS / "shared" / "icons.js"
DESIGN_CSS = SRC / "design" / "components.css"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rule(css: str, selector: str) -> str:
    """Return the declaration block of the rule whose selector is exactly ``selector``."""
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"missing rule: {selector}"
    return match.group(1)


def _opening_tag(markup: str, marker: str) -> str:
    """Return the opening tag that contains ``marker``."""
    match = re.search(r"<[a-z]+\b[^>]*" + re.escape(marker) + r"[^>]*>", markup)
    assert match, f"missing element with {marker}"
    return match.group(0)


def test_both_pages_have_the_shared_page_header() -> None:
    page = _read(LIST_PAGE)
    header = re.search(r'<header class="atlas-page-head[^"]*">(.*?)</header>', page, re.S)
    assert header, "institutions.md needs an .atlas-page-head"
    assert 'class="atlas-page-head__eyebrow"' in header.group(1)
    assert "<h1>Institutions</h1>" in header.group(1)
    assert 'class="atlas-page-head__lead"' in header.group(1)
    assert 'class="atlas-page-head__meta"' in header.group(1)
    assert page.count("<h1>") == 1

    detail = _read(DETAIL_JS)
    assert '<header class="atlas-page-head inst-page-head">' in detail
    assert (
        '<p class="atlas-page-head__eyebrow">${icon("building").outerHTML}Institution</p>' in detail
    )
    assert '<p class="atlas-page-head__lead">' in detail
    assert '<div class="atlas-page-head__meta">' in detail
    assert "<h1>${escapeHtml(name)}</h1>" in detail


def test_icons_used_by_the_pages_exist_in_the_shared_sprite() -> None:
    names = set(re.findall(r"^  ([a-z]+): '", _read(ICONS_JS), re.M))
    used = set(re.findall(r'href="#i-([a-z]+)"', _read(LIST_PAGE) + _read(DETAIL_JS)))
    used |= set(re.findall(r'icon\("([a-z]+)"', _read(DETAIL_JS)))
    assert used, "the pages should use sprite icons"
    assert used <= names, f"icons missing from icons.js: {sorted(used - names)}"
    assert "injectIconSprite();" in _read(LIST_PAGE)


def test_institution_type_badges_use_display_labels() -> None:
    detail = _read(DETAIL_JS)
    badge = (
        r'<span class="atlas-badge">\$\{escapeHtml\(institutionTypeLabel'
        r'\(institution\.atlas_type \|\| "other"\)\)\}</span>'
    )
    assert re.search(badge, detail)
    assert 'import {institutionTypeLabel} from "./shared/labels.js";' in detail
    listing = _read(LIST_JS)
    assert 'import {institutionTypeLabel} from "./shared/labels.js";' in listing
    assert (
        '<span class="atlas-badge">${escapeHtml(institutionTypeLabel(institution.atlas_type'
        in listing
    )
    assert "${escapeHtml(institutionTypeLabel(type))}</button>" in listing


def test_kpi_tiles_use_the_shared_classes_with_reserved_height() -> None:
    detail = _read(DETAIL_JS)
    assert '<dl class="atlas-kpis inst-tiles">' in detail
    assert '<div class="atlas-kpi"><dt class="atlas-kpi__label">' in detail
    assert '<dd class="atlas-kpi__value">' in detail
    assert 'class="atlas-kpi__note"' in detail
    design = _read(DESIGN_CSS)
    assert re.search(r"\.atlas-kpi \{[^}]*min-height: 8\.5rem", design)


def test_detail_sections_are_cards() -> None:
    detail = _read(DETAIL_JS)
    assert re.search(r'<section class="inst-section atlas-card" id="section-\$\{id\}"', detail)


def test_no_outer_page_panel_border_on_either_page() -> None:
    assert "border" not in _rule(_read(LIST_CSS), "#institutions-root")
    assert "border" not in _rule(_read(DETAIL_CSS), "#institution-root")
    assert '<div id="institutions-root">' in _read(LIST_PAGE)
    assert '<div id="institution-root" class="institution-page">' in _read(DETAIL_PAGE)
    assert 'class="panel"' not in _read(LIST_PAGE)
    assert 'class="panel"' not in _read(DETAIL_PAGE)


def test_leaderboard_toggle_is_a_segmented_control_with_aria_pressed() -> None:
    page = _read(LIST_PAGE)
    segmented = re.search(r'<div class="atlas-segmented"[^>]*>(.*?)</div>', page, re.S)
    assert segmented, "the leaderboard toggle must be an .atlas-segmented control"
    group = _opening_tag(page, 'class="atlas-segmented"')
    assert 'role="group"' in group and 'aria-labelledby="institution-view-label"' in group
    buttons = re.findall(r"<button\b[^>]*>", segmented.group(1))
    assert len(buttons) == 2
    assert all('type="button"' in tag and "aria-pressed=" in tag for tag in buttons)
    assert 'data-inst-view="tiers"' in segmented.group(1)
    assert 'data-inst-view="list"' in segmented.group(1)
    listing = _read(LIST_JS)
    assert 'button.setAttribute("aria-pressed", String(button.dataset.instView' in listing


def test_type_chip_row_reserves_its_height_above_the_sort_row() -> None:
    css = _read(LIST_CSS)
    assert re.search(
        r"min-height:\s*2\.75rem", _rule(css, "#institutions-root #institution-type-chips")
    )
    assert "#institutions-root #institution-type-chips { min-height: 5.5rem; }" in css
    page = _read(LIST_PAGE)
    assert page.index('id="institution-type-chips"') < page.index('class="institution-sort-row"')


def test_caveat_and_tier_overlap_text_stay_visible_in_callouts() -> None:
    page = _read(LIST_PAGE)
    caution = re.search(
        r'<div class="atlas-callout atlas-callout--caution">(.*?)</div>', page, re.S
    )
    assert caution, "the quality caveat must be a caution callout"
    assert "it is not a quality ranking" in caution.group(1)
    tiers = re.search(
        r'<div id="institution-tiers" hidden><div class="atlas-callout[^"]*">(.*?)</div>',
        page,
        re.S,
    )
    assert tiers, "the tier note must sit in a callout"
    assert 'class="tier-note"' in tiers.group(1)
    assert "cannot be reliably ordered" in tiers.group(1)


def test_map_control_buttons_have_accessible_names_and_keep_their_handlers() -> None:
    page = _read(LIST_PAGE)
    expected = {
        "institution-zoom-in": "Zoom in",
        "institution-zoom-out": "Zoom out",
        "institution-zoom-reset": "Reset view",
    }
    for button_id, name in expected.items():
        tag = _opening_tag(page, f'id="{button_id}"')
        assert tag.startswith("<button "), tag
        assert 'type="button"' in tag
        assert 'class="atlas-btn atlas-btn--icon atlas-btn--secondary"' in tag
        assert f'aria-label="{name}"' in tag, tag
    assert (
        'id="institution-map" class="monitoring-map institution-map" role="group" tabindex="0"'
        in page
    )
    assert 'aria-describedby="institution-map-hint"' in page

    listing = _read(LIST_JS)
    assert '$("institution-zoom-in").addEventListener("click"' in listing
    assert '$("institution-zoom-out").addEventListener("click"' in listing
    assert '$("institution-zoom-reset").addEventListener("click"' in listing
    assert "attachMapInteractions(mapContainer, { getView: institutionMapCurrentView" in listing
    keys = _read(MAP_JS)
    assert "const actions = { ArrowLeft: () => panBy(-step, 0)" in keys
    assert '"+": () => zoomBy(1.25)' in keys
    assert '"-": () => zoomBy(0.8)' in keys


def test_land_fill_moves_to_a_mist_token() -> None:
    css = _read(LIST_CSS)
    assert "fill: var(--atlas-sunken)" in _rule(
        css, "#institutions-root .monitoring-map-svg .map-land"
    )
    assert "#f1efe4" not in css


def test_tier_rows_are_cards_with_brand_rank_bars_and_display_headers() -> None:
    css = _read(LIST_CSS)
    row = _rule(css, "#institutions-root .tier-row")
    assert "border: 1px solid var(--line)" in row
    assert "background: var(--surface)" in row
    assert "stroke: var(--brand)" in _rule(css, "#institutions-root .tier-bar-range")
    assert "var(--atlas-font-display)" in _rule(css, "#institutions-root .tier-group > summary")


def test_institution_detail_stylesheet_has_no_hex_literals() -> None:
    css = _read(DETAIL_CSS)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert "min-height: calc(100vh - 6rem);" in css
