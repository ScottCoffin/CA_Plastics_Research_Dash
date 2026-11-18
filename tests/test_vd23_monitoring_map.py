"""VD-23 source contracts: Monitoring map toolbar, full screen and the filter sidebar.

Visual and keyboard behaviour is checked in a browser (see the VD-23 report); these tests pin the
markup, CSS and script hooks that behaviour depends on.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "framework" / "src" / "california" / "monitoring.md"
STYLES = ROOT / "framework" / "src" / "components" / "monitoring.css"
SHARED_STYLES = ROOT / "framework" / "src" / "design" / "components.css"
SCRIPT = ROOT / "framework" / "src" / "components" / "monitoring.js"
MAP_SCRIPT = ROOT / "framework" / "src" / "components" / "svg_map.js"
TOOLTIP_JS = ROOT / "framework" / "src" / "components" / "shared" / "tooltip.js"
INSTITUTIONS_SCRIPT = ROOT / "framework" / "src" / "components" / "institutions.js"

HEX_COLOR = re.compile(
    r"(?<![\w-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})"
    r"(?![0-9a-fA-F])"
)
TOOL_LABELS = {
    "Statewide view",
    "San Francisco Bay view",
    "Zoom in",
    "Zoom out",
    "Reset view",
    "Full screen",
}


def _rule(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css, re.S)
    assert match, f"missing rule for {selector}"
    return match.group(1)


def _media_block(css: str, query: str) -> str:
    start = css.index(query)
    end = css.index("\n}", start)
    return css[start:end]


def test_toolbar_sits_inside_the_map_frame_in_order() -> None:
    page = PAGE.read_text(encoding="utf-8")
    frame = page.index('<div id="monitoring-map-frame"')
    tools = page.index('class="monitoring-map-tools"')
    map_el = page.index('id="monitoring-map" class="monitoring-map"')
    legend = page.index('id="monitoring-map-legend"')
    details = page.index('id="monitoring-map-details"')
    assert frame < tools < map_el < legend < details
    assert page.count('id="monitoring-map-frame"') == 1


def test_external_text_map_buttons_are_removed() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert "monitoring-map-controls" not in page
    for text in ("Statewide", "SF Bay", "Zoom in (+)", "Zoom out (-)", "Reset view"):
        assert f">{text}<" not in page, text


def test_every_map_tool_is_an_icon_button_with_label_and_tip() -> None:
    page = PAGE.read_text(encoding="utf-8")
    buttons = re.findall(
        r'<button type="button" class="monitoring-map-tool"[^>]*>(.*?)</button>', page, re.S
    )
    assert len(buttons) == len(TOOL_LABELS) == 6
    labels: set[str] = set()
    for match in re.finditer(
        r'<button type="button" class="monitoring-map-tool"([^>]*)>(.*?)</button>', page, re.S
    ):
        attrs, body = match.groups()
        label = re.search(r'aria-label="([^"]+)"', attrs)
        tip = re.search(r'data-atlas-tip="([^"]+)"', attrs)
        assert label and tip, attrs
        assert label.group(1) == tip.group(1)
        labels.add(label.group(1))
        # Icon only: no visible text, just 24x24 stroke icons drawn in currentColor.
        assert re.sub(r"<svg.*?</svg>", "", body, flags=re.S).strip() == ""
        for svg in re.findall(r"<svg[^>]*>", body):
            assert 'viewBox="0 0 24 24"' in svg
            assert 'stroke="currentColor"' in svg
    assert labels == TOOL_LABELS


def test_fullscreen_button_has_enter_and_exit_icons() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert 'id="monitoring-fullscreen"' in page
    assert 'aria-controls="monitoring-map-frame"' in page
    assert "monitoring-map-tool__icon--enter" in page
    assert "monitoring-map-tool__icon--exit" in page


def test_tool_hit_area_is_at_least_40_px() -> None:
    css = STYLES.read_text(encoding="utf-8")
    tool = _rule(css, "#monitoring-root .monitoring-map-tool")
    assert re.search(r"(?<!min-)width:\s*2\.5rem", tool)
    assert re.search(r"(?<!min-)height:\s*2\.5rem", tool)


def test_tooltip_is_the_shared_left_variant_timed_under_300_ms() -> None:
    # VD-24/VD-29: the tooltip is one shared .atlas-tip bubble (design/components.css), placed by
    # components/shared/tooltip.js. The map tools use data-atlas-tip-pos="left", which it reads.
    shared = SHARED_STYLES.read_text(encoding="utf-8")
    assert PAGE.read_text(encoding="utf-8").count('data-atlas-tip-pos="left"') == 6
    assert "[data-atlas-tip]::after" not in STYLES.read_text(encoding="utf-8")
    assert 'tip.getAttribute("data-atlas-tip-pos")' in TOOLTIP_JS.read_text(encoding="utf-8")

    bubble = _rule(shared, ".atlas-tip")
    assert "position: fixed;" in bubble
    shown = re.search(r"animation: atlas-tip-in ([^;]+);", shared)
    assert shown is not None
    delays = [
        float(value) / (1000 if unit == "ms" else 1)
        for value, unit in re.findall(r"(\d*\.?\d+)(ms|s)\b", shown.group(1))
    ]
    assert delays and max(delays) <= 0.3, delays

    reduced = _media_block(shared, "@media (prefers-reduced-motion: reduce)")
    assert ".atlas-tip" in reduced and "animation-duration: 0s;" in reduced


def test_tooltip_is_not_clipped_by_the_toolbar_or_frame() -> None:
    css = STYLES.read_text(encoding="utf-8")
    for selector in (
        "#monitoring-root .monitoring-map-frame",
        "#monitoring-root .monitoring-map-tools",
        "#monitoring-root .monitoring-map-tool",
    ):
        assert "overflow" not in _rule(css, selector), selector


def test_map_frame_full_screen_styles_and_fallback_layer() -> None:
    css = STYLES.read_text(encoding="utf-8")
    fixed = _rule(css, "#monitoring-root .monitoring-map-frame.is-expanded")
    assert "position: fixed;" in fixed and "inset: 0;" in fixed
    z_index = int(re.search(r"z-index:\s*(\d+)", fixed).group(1))
    assert z_index > 20, "the fallback must sit above the fixed site header (z-index 20)"
    # #observablehq-main is a stacking context at z-index 0, so the header is hidden while expanded.
    assert "body.monitoring-map-expanded #observablehq-header" in css
    script = SCRIPT.read_text(encoding="utf-8")
    assert 'document.body.classList.toggle("monitoring-map-expanded", state.mapExpanded);' in script
    fill = _rule(css, "#monitoring-root .monitoring-map-frame.is-fullscreen .monitoring-map-svg")
    assert "height: 100%;" in fill


def test_fullscreen_uses_the_api_with_a_viewport_fallback() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "frame.requestFullscreen()" in script
    assert "document.exitFullscreen()" in script
    assert "document.fullscreenEnabled === true" in script
    assert 'document.addEventListener("fullscreenchange", syncMapFullscreen);' in script
    assert 'event.key === "Escape" && state.mapExpanded' in script
    assert 'button.setAttribute("aria-label", label);' in script
    assert "button.dataset.atlasTip = label;" in script
    assert 'frame.classList.toggle("is-expanded", state.mapExpanded);' in script
    assert '$("monitoring-fullscreen").focus({ preventScroll: true });' in script


def test_filter_sidebar_is_wrapped_after_the_caveat_and_collapses_with_aria_expanded() -> None:
    page = PAGE.read_text(encoding="utf-8")
    note = page.index('id="monitoring-quality-note"')
    controls = page.index('class="facet-controls"')
    filters = page.index('id="facet-filters"')
    assert note < controls < filters

    script = SCRIPT.read_text(encoding="utf-8")
    wrap = re.search(r"function wrapFilterSidebar\(\) \{(.*?)\n\}", script, re.S)
    assert wrap, "wrapFilterSidebar must exist"
    body = wrap.group(1)
    assert body.index("controls.before(sidebar);") < body.index("body.append(controls, filters);")
    assert 'toggle.setAttribute("aria-controls", "monitoring-sidebar-body");' in body
    assert "setSidebarCollapsed(false);" in body
    assert "wrapFilterSidebar();" in script[script.index("export async function mountMonitoring") :]

    collapse = re.search(r"function setSidebarCollapsed\(collapsed\) \{(.*?)\n\}", script, re.S)
    assert collapse
    assert 'toggle.setAttribute("aria-expanded", String(!collapsed));' in collapse.group(1)
    assert 'classList.toggle("is-sidebar-collapsed", collapsed)' in collapse.group(1)


def test_sidebar_is_a_sticky_column_only_at_64rem_and_up() -> None:
    css = STYLES.read_text(encoding="utf-8")
    wide = _media_block(css, "@media (min-width: 64rem)")
    sidebar = re.search(r"#monitoring-root > \.monitoring-sidebar \{([^}]*)\}", wide, re.S)
    assert sidebar
    rule = sidebar.group(1)
    assert "position: sticky;" in rule
    assert "overflow-y: auto;" in rule
    assert "max-height: calc(100vh" in rule
    assert "top: calc(var(--observablehq-header-height" in rule
    assert "grid-template-columns: minmax(15rem, 18rem) minmax(0, 1fr);" in wide
    assert "grid-row: 2;" in _rule(css, "#monitoring-root > #monitoring-quality-note")

    # Below 64rem the toggle and the collapsed body rules must not apply.
    head = _rule(css, "#monitoring-root .monitoring-sidebar__head")
    assert "display: none;" in head
    assert (
        "is-sidebar-collapsed .monitoring-sidebar__body"
        not in css[: css.index("@media (min-width: 64rem)")]
    )
    assert "is-sidebar-collapsed .monitoring-sidebar__body { display: none; }" in wide


def test_svg_map_interaction_contract_is_unchanged_for_institutions() -> None:
    map_script = MAP_SCRIPT.read_text(encoding="utf-8")
    assert "export function attachMapInteractions(container, hooks)" in map_script
    assert "hooks.setView(monitoringMap.zoomView(hooks.getView(), factor))" in map_script
    institutions = INSTITUTIONS_SCRIPT.read_text(encoding="utf-8")
    assert (
        "attachMapInteractions(mapContainer, { getView: institutionMapCurrentView" in institutions
    )
    assert '$("institution-zoom-in")' in institutions
    assert '$("institution-zoom-out")' in institutions


def test_colours_come_from_tokens_and_no_external_resources() -> None:
    css = STYLES.read_text(encoding="utf-8")
    assert not HEX_COLOR.findall(css)
    assert "url(http" not in css and "@import" not in css
    assert "https://" not in css
