"""Acceptance checks for the Collaboration network visual refresh."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "framework" / "src" / "california" / "network.md"
CSS = ROOT / "framework" / "src" / "components" / "network.css"
VIEW = ROOT / "framework" / "src" / "components" / "network.js"
SHARED_CSS = ROOT / "framework" / "src" / "design" / "components.css"


def test_primary_and_more_filters_keep_the_existing_network_controls() -> None:
    page = PAGE.read_text(encoding="utf-8")
    primary = re.search(
        r'<div class="atlas-filters__grid net-primary-grid">(.*?)</form>', page, re.DOTALL
    )
    assert primary
    primary_fields = primary.group(1)
    primary_ids = ("net-search", "net-colour", "net-size", "net-topic")
    assert [primary_fields.index(f'id="{item}"') for item in primary_ids] == sorted(
        primary_fields.index(f'id="{item}"') for item in primary_ids
    )
    more = re.search(
        r'<details class="atlas-filters__more">(.*?)</details>', primary_fields, re.DOTALL
    )
    assert more
    for field in (
        "net-sector",
        "net-institution",
        "net-year-from",
        "net-year-to",
        "net-min",
        "net-current",
    ):
        assert f'id="{field}"' in more.group(1)
    assert "More filters (6)" in primary_fields

    for control in (
        'id="network-filters"',
        'id="network-reset"',
        'id="net-topic" name="topic"',
        'id="net-sector" name="sector"',
        'id="net-institution" name="institution"',
        'id="net-year-from" name="year_from"',
        'id="net-year-to" name="year_to"',
        'id="net-min" name="min" type="range" min="1" max="10" step="1" value="1"',
        'id="net-current" name="now" type="checkbox"',
        'id="net-colour" name="colour"',
        'id="net-size" name="size"',
        'id="network-table"',
        'id="network-rows"',
    ):
        assert control in page

    view = VIEW.read_text(encoding="utf-8")
    assert "parseNetworkHash(window.location.hash)" in view
    assert "formatNetworkHash(state)" in view
    assert 'controls.form.addEventListener("input"' in view
    assert 'controls.form.addEventListener("change"' in view


def test_graph_controls_have_shared_icon_buttons_and_tooltips() -> None:
    page = PAGE.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    view = VIEW.read_text(encoding="utf-8")
    for button_id, label in (
        ("net-zoom-in", "Zoom in"),
        ("net-zoom-out", "Zoom out"),
        ("net-reset-view", "Reset view"),
        ("net-fullscreen", "Full screen"),
        ("net-layout", "Re-run layout"),
        ("net-restore", "Restore saved layout"),
    ):
        assert re.search(
            rf'<button id="{button_id}" class="atlas-btn atlas-btn--secondary '
            rf'atlas-btn--icon net-btn"[^>]*aria-label="{re.escape(label)}" '
            rf'data-tooltip="{re.escape(label)}"',
            page,
        )
    assert ".net-btn {" in css and "width: 2.5rem;" in css and "height: 2.5rem;" in css
    assert ".net-btn:hover .net-btn__tooltip" in css
    assert ".net-btn:focus-visible .net-btn__tooltip" in css
    assert 'import {icon, injectIconSprite} from "./shared/icons.js";' in view
    assert "injectIconSprite();" in view and "icon(GRAPH_BUTTON_ICONS[key])" in view
    assert 'buttons.layout.setAttribute("aria-label", label);' in view
    assert 'buttons.layout.querySelector(".net-btn__tooltip").textContent = label;' in view


def test_network_page_header_caveat_disclosure_and_cards_are_present() -> None:
    page = PAGE.read_text(encoding="utf-8")
    view = VIEW.read_text(encoding="utf-8")
    assert 'class="atlas-page-head"' in page
    lead = re.search(r'<p class="atlas-page-head__lead">(.*?)</p>', page, re.DOTALL)
    assert lead and lead.group(1).count(".") == 2
    assert 'class="atlas-callout atlas-callout--info"' in page
    caveat = page.index("Volume note")
    disclosure = page.index('<details id="network-how-to" class="atlas-disclosure">')
    assert caveat < disclosure
    assert "How to read the network" in page
    assert "zoom" in page and "drag" in page and "search" in page and "Click a dot" in page
    assert (
        '<section id="network-panel" class="net-panel atlas-card" aria-label="Selected expert">'
        in page
    )
    assert '<aside id="network-panel"' not in page
    assert 'class="net-table-wrap atlas-table-wrap"' in page
    assert 'class="atlas-disclosure"' in page
    assert 'button.className = "net-legend-item atlas-pill";' in view


def test_network_interactive_targets_meet_the_24_pixel_minimum() -> None:
    page = PAGE.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    shared_css = SHARED_CSS.read_text(encoding="utf-8")
    assert 'class="net-range"' in page
    assert ".net-range {" in css and "min-height: 2.5rem;" in css
    for selector in (".net-link-button {", ".net-profile-link {", ".net-legend-item {"):
        assert selector in css
    assert ".net-link-button {\n  width: 100%;\n  min-height: 2.5rem;" in css
    assert ".net-profile-link {\n  display: inline-flex;\n  min-height: 2.5rem;" in css
    assert ".net-legend-item {\n  min-width: 0;\n  min-height: 1.75rem;" in css

    for component, declarations in (
        (r"\.atlas-btn\s*\{", ("min-height: 2.5rem;",)),
        (
            r"\.atlas-input,\s*\.atlas-select,\s*\.atlas-search input\s*\{",
            ("min-height: 2.5rem;",),
        ),
        (r"\.atlas-check\s*\{", ("width: 1.5rem;", "height: 1.5rem;")),
        (r"\.atlas-filters__more > summary\s*\{", ("min-height: 2.5rem;",)),
        (r"\.atlas-disclosure > summary\s*\{", ("min-height: 2.75rem;",)),
    ):
        block = re.search(rf"{component}([^{{}}]*)\}}", shared_css, re.DOTALL)
        assert block, component
        for declaration in declarations:
            assert declaration in block.group(1), (component, declaration)
    for control_id in ("net-search", "net-colour", "net-size", "net-topic"):
        assert re.search(
            rf'<(?:input|select) class="[^"]*atlas-(?:input|select)[^"]*" id="{control_id}"', page
        )

    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    selectors = [
        selector.strip()
        for block in re.findall(r"([^{}]+)\{", css)
        for selector in block.split(",")
        if selector.strip() and not selector.strip().startswith("@")
    ]
    assert selectors and all(selector.startswith(".net-") for selector in selectors)
