"""VD-7a source contracts for the Monitoring page redesign."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "framework" / "src" / "monitoring.md"
STYLES = ROOT / "framework" / "src" / "components" / "monitoring.css"
SCRIPT = ROOT / "framework" / "src" / "components" / "monitoring.js"
MAP_SCRIPT = ROOT / "framework" / "src" / "components" / "svg_map.js"

PAGE_IDS = {
    "monitoring-root",
    "monitoring",
    "monitoring-status",
    "monitoring-quality-note",
    "monitoring-quality-detail",
    "monitoring-facets-expand",
    "monitoring-facets-collapse",
    "facet-filters",
    "monitoring-filters-heading",
    "facet-filters-count",
    "monitoring-filters",
    "monitoring-tier",
    "monitoring-search",
    "monitoring-contributor",
    "monitoring-matrix",
    "monitoring-year",
    "monitoring-region",
    "facet-sources",
    "monitoring-sources-heading",
    "facet-sources-count",
    "monitoring-source-count",
    "monitoring-sources",
    "facet-map",
    "monitoring-map-heading",
    "facet-map-count",
    "monitoring-map-note",
    "monitoring-map-hint",
    "monitoring-zoom-in",
    "monitoring-zoom-out",
    "monitoring-zoom-reset",
    "monitoring-map",
    "monitoring-map-details",
    "monitoring-map-legend",
    "facet-gaps",
    "monitoring-gaps-heading",
    "facet-gaps-count",
    "monitoring-gaps-note",
    "monitoring-gaps",
    "facet-samples",
    "monitoring-samples-heading",
    "facet-samples-count",
    "monitoring-download-csv",
    "monitoring-download-note",
    "monitoring-samples",
}

DISCLOSURE_TITLES = {
    "facet-filters": "monitoring-filters-heading",
    "facet-sources": "monitoring-sources-heading",
    "facet-map": "monitoring-map-heading",
    "facet-gaps": "monitoring-gaps-heading",
    "facet-samples": "monitoring-samples-heading",
}


def test_page_header_and_static_caveat_use_shared_components() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert '<header class="atlas-page-head">' in page
    assert 'class="atlas-page-head__eyebrow"' in page
    assert 'class="atlas-page-head__lead"' in page
    assert '<h1 id="monitoring">Monitoring</h1>' in page
    assert 'href="#i-drop"' in page
    assert 'id="monitoring-status"' in page

    note = re.search(
        r'<div id="monitoring-quality-note"[^>]*>(.*?)</div>\s*\n\s*<div class="facet-controls"',
        page,
        re.S,
    )
    assert note, "the static caveat must remain in the page before data loads"
    assert 'class="atlas-callout atlas-callout--caution"' in note.group(0)
    assert 'href="#i-alert"' in note.group(1)
    assert (
        "Observations describe individual source samples; they do not establish statewide "
        "monitoring coverage or comparable concentrations. Blank cells are not evidence of a "
        "data gap."
    ) in note.group(1)


def test_existing_page_ids_and_disclosure_count_heads_are_preserved() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert set(re.findall(r'id="([^"]+)"', page)) == PAGE_IDS

    for disclosure_id, title_id in DISCLOSURE_TITLES.items():
        details = re.search(
            rf'<details\b(?=[^>]*\bid="{disclosure_id}")([^>]*)>(.*?)</details>',
            page,
            re.S,
        )
        assert details, disclosure_id
        assert "atlas-disclosure" in details.group(1), disclosure_id
        summary = re.search(r"<summary\b[^>]*>(.*?)</summary>", details.group(2), re.S)
        assert summary, disclosure_id
        assert f'id="{title_id}"' in summary.group(1)
        assert f'id="{disclosure_id}-count"' in summary.group(1)


def test_filter_controls_and_map_panel_use_shared_styles() -> None:
    page = PAGE.read_text(encoding="utf-8")
    filters = re.search(r'<details\b(?=[^>]*\bid="facet-filters")[^>]*>(.*?)</details>', page, re.S)
    assert filters and "atlas-filters" in filters.group(0)
    assert 'class="atlas-filters__body atlas-filters__grid"' in filters.group(1)
    assert 'class="atlas-field"' in filters.group(1)
    assert 'class="atlas-select"' in filters.group(1)
    assert 'class="atlas-search"' in filters.group(1)
    assert 'class="atlas-card institution-map-panel"' in page


def test_monitoring_map_and_disclosure_panels_can_shrink_at_320px() -> None:
    css = STYLES.read_text(encoding="utf-8")
    assert re.search(
        r"\.institution-map-panel\s*,\s*#monitoring-root \.monitoring-layout > section\s*"
        r"\{[^}]*min-width:\s*0",
        css,
        re.S,
    )
    assert re.search(r"#monitoring-root \.facet-title\s*\{[^}]*min-width:\s*0", css, re.S)
    assert re.search(r"#monitoring-root \.facet-count\s*\{[^}]*white-space:\s*normal", css, re.S)


def test_disclosure_state_and_map_interaction_hooks_remain_in_place() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert (
        'const FACET_IDS = ["facet-filters", "facet-sources", "facet-map", "facet-gaps", '
        '"facet-samples"];'
    ) in script
    assert 'const FACET_STORAGE_KEY = "monitoring-facets";' in script
    assert 'import {injectIconSprite} from "./shared/icons.js";' in script
    assert "  injectIconSprite();" in script
    assert "attachMapInteractions(mapContainer" in script
    assert 'document.querySelectorAll("[data-map-extent]")' in script
    assert '$("monitoring-quality-detail").textContent' in script


def test_actionable_map_markers_have_transparent_non_scaling_hit_areas() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    marker = re.search(r'return `(<g class="monitoring-marker.*?</g>)`;', script)
    assert marker, "map markers remain native SVG button groups"
    assert 'role="button" tabindex="0"' in marker.group(1)
    assert re.search(
        r'<circle class="marker-hit-area" cx="\$\{cluster\.x\}" '
        r'cy="\$\{cluster\.y\}" r="1" aria-hidden="true"/>',
        marker.group(1),
    )

    css = STYLES.read_text(encoding="utf-8")
    hit_area = re.search(
        r"#monitoring-root \.monitoring-marker circle\.marker-hit-area\s*\{([^}]*)\}",
        css,
        re.S,
    )
    assert hit_area
    assert re.search(r"stroke-width:\s*24px", hit_area.group(1))
    assert re.search(r"vector-effect:\s*non-scaling-stroke", hit_area.group(1))
    assert re.search(r"pointer-events:\s*none", hit_area.group(1))
    assert re.search(r"stroke:\s*transparent", hit_area.group(1))
    assert re.search(r"fill:\s*transparent", hit_area.group(1))
    assert "#monitoring-root .monitoring-marker:focus-visible .marker-body" in css

    assert (
        'class="monitoring-table-wrap" role="region" tabindex="0" '
        'aria-label="Selected observation details"' in script
    )
    assert (
        '$("monitoring-filters").addEventListener("submit", preventMonitoringFilterSubmit)'
        in script
    )
    assert '$(id).addEventListener("input", onFilterInput)' in script
    assert '$(id).addEventListener("change", onFilterInput)' in script


def test_monitoring_pointer_clicks_resolve_overlapping_hit_areas_by_visible_center() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    resolver = re.search(
        r"export function nearestMonitoringMarker\(event, hitMarker, container\)\s*\{(.*?)\n\}",
        script,
        re.S,
    )
    assert resolver
    assert "if (hitMarker) return hitMarker" in resolver.group(1)
    assert 'container.querySelectorAll(".monitoring-marker")' in resolver.group(1)
    assert 'marker.querySelector(".marker-body")' in resolver.group(1)
    assert "body.getBoundingClientRect()" in resolver.group(1)
    assert "event.clientX" in resolver.group(1)
    assert "event.clientY" in resolver.group(1)
    assert "nearestDistance <= 12 * 12" in resolver.group(1)
    assert "resolveMarker: nearestMonitoringMarker" in script

    map_script = MAP_SCRIPT.read_text(encoding="utf-8")
    click = re.search(
        r'container\.addEventListener\("click", \(event\) => \{(.*?)\n  \}\);', map_script, re.S
    )
    assert click
    handler = click.group(1)
    assert handler.index("if (suppressClick)") < handler.index("hooks.resolveMarker")
    assert handler.index("hooks.resolveMarker") < handler.index("if (!marker) return")
    assert "if (hooks.resolveMarker)" in handler
    assert "hooks.resolveMarker(event, marker, container)" in handler
    assert "if (!marker) return" in handler

    keyboard = re.search(
        r'container\.addEventListener\("keydown", \(event\) => \{(.*?)\n  \}\);', map_script, re.S
    )
    assert keyboard
    assert "hooks.select(Number(marker.dataset.clusterIndex))" in keyboard.group(1)
    assert "resolveMarker" not in keyboard.group(1)
