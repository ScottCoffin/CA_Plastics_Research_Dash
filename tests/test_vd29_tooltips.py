"""VD-29 source contracts: tooltips that stay on screen, smaller help icons in filter label
rows, and the full-width Monitoring map description.

The browser check (bubble inside the viewport and not clipped, no overlap with controls,
description width, at 390 and 1440 px) ran with Playwright; these tests pin the CSS and script
hooks that check depends on.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
COMPONENTS = SRC / "design" / "components.css"
TOOLTIP_JS = SRC / "components" / "shared" / "tooltip.js"
MONITORING_CSS = SRC / "components" / "monitoring.css"
MONITORING_JS = SRC / "components" / "monitoring.js"
MONITORING_PAGE = SRC / "california" / "monitoring.md"
INSTITUTIONS_PAGE = SRC / "california" / "institutions.md"
REDUCED_MOTION = re.compile(r"@media \(prefers-reduced-motion: reduce\) \{.*?\n\}", re.S)


def _rule(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css, re.S)
    assert match, f"missing rule for {selector}"
    return match.group(1)


def test_bubble_is_one_fixed_element_kept_inside_the_viewport() -> None:
    css = COMPONENTS.read_text(encoding="utf-8")
    bubble = _rule(css, ".atlas-tip")
    assert "position: fixed;" in bubble
    assert "max-width: min(20rem, calc(100vw - 16px));" in bubble
    z_index = int(re.search(r"z-index:\s*(\d+)", bubble).group(1))
    assert z_index > 20, "the bubble must sit above the fixed site header (z-index 20)"
    # Position is measured in script, not centred with a translate that can run off the screen.
    assert "transform" not in bubble
    assert "[data-atlas-tip]::after" not in css

    js = TOOLTIP_JS.read_text(encoding="utf-8")
    assert "const EDGE = 8;" in js and "const GAP = 8;" in js
    assert "document.documentElement.clientWidth" in js
    assert "getBoundingClientRect()" in js
    # Flip above or below, or to the other side, when the requested side has no room.
    for name in ("fitsAbove", "fitsBelow", "fitsLeft", "fitsRight"):
        assert name in js, name
    assert "node.style.left = `${left}px`;" in js
    assert "node.style.top = `${top}px`;" in js


def test_bubble_is_appended_outside_every_trigger_so_no_overflow_clips_it() -> None:
    js = TOOLTIP_JS.read_text(encoding="utf-8")
    # The bubble is appended to the page, never to a trigger inside a scroll container.
    assert "host.append(node)" in js
    assert "document.fullscreenElement || document.body" in js
    assert "fullscreenchange" in js
    assert "capture: true" in js
    assert 'window.addEventListener("resize"' in js
    assert "trigger.append" not in js and "tip.append" not in js


def test_bubble_stays_open_for_the_pointer_and_respects_reduced_motion() -> None:
    js = TOOLTIP_JS.read_text(encoding="utf-8")
    assert "(hover: hover)" in js
    assert "HOVER_GRACE_MS" in js and "bubble.contains(" in js
    assert '"Escape"' in js and "dismissed = true" in js

    css = COMPONENTS.read_text(encoding="utf-8")
    blocks = REDUCED_MOTION.findall(css)
    assert any(".atlas-tip" in block and "animation-duration: 0s;" in block for block in blocks)


def test_filter_label_help_button_is_a_24_px_hit_area_without_negative_margins() -> None:
    css = COMPONENTS.read_text(encoding="utf-8")
    assert (
        ":is(#evidence-root, #funding-root, #institutions-root, #monitoring-root, #experts-root) "
        ".atlas-field > .atlas-help-row > .atlas-help {"
    ) in css
    button = re.search(r"\.atlas-field > \.atlas-help-row > \.atlas-help \{([^}]*)\}", css)
    assert button, "missing filter label help rule"
    body = button.group(1)
    assert "width: 1.5rem;" in body and "height: 1.5rem;" in body
    assert "margin: 0;" in body and "margin: -" not in body
    # The visible disc is 20 px (24 px less 2 px inset each side), drawn by ::before.
    ring = re.search(r"\.atlas-field > \.atlas-help-row > \.atlas-help::before \{([^}]*)\}", css)
    assert ring and "inset: 2px;" in ring.group(1)


def test_filter_label_row_keeps_the_label_and_its_help_button_on_one_line() -> None:
    css = COMPONENTS.read_text(encoding="utf-8")
    assert "flex-wrap: nowrap;" in _rule(css, ".atlas-field > .atlas-help-row")


def test_help_buttons_sit_inline_after_their_filter_labels() -> None:
    monitoring = MONITORING_PAGE.read_text(encoding="utf-8")
    access_tier = (
        r'<div class="atlas-help-row"><label class="atlas-label" for="monitoring-tier">'
        r'Access tier</label><button type="button" class="atlas-help"'
    )
    assert re.search(access_tier, monitoring)
    # The help button comes before the select it describes, inside the same field.
    assert monitoring.index('class="atlas-help"') < monitoring.index('id="monitoring-tier"')
    institutions = INSTITUTIONS_PAGE.read_text(encoding="utf-8")
    view_field = (
        r'<div [^>]*class="atlas-field institution-view-field"[^>]*>'
        r'<div class="atlas-help-row"><span[^>]*>Leaderboard view</span>'
        r'<button type="button" class="atlas-help"'
    )
    assert re.search(view_field, institutions)


def test_monitoring_map_description_is_full_width_of_the_card() -> None:
    css = MONITORING_CSS.read_text(encoding="utf-8")
    selector = r"#monitoring-root #monitoring-map-note,\s*#monitoring-root #monitoring-map-hint"
    match = re.search(selector + r" \{([^}]*)\}", css)
    assert match and "max-width: none;" in match.group(1)
    page = MONITORING_PAGE.read_text(encoding="utf-8")
    assert 'id="monitoring-map-note"' in page and 'id="monitoring-map-hint"' in page
    # The status text is written by monitoring.js; the rule above applies to it too.
    script = MONITORING_JS.read_text(encoding="utf-8")
    assert "observations match; ${located.length} have valid coordinate pairs" in script
