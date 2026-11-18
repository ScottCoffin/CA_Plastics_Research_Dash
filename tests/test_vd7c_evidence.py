"""Source checks for the VD-7c Evidence map presentation refresh."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "framework" / "src" / "california" / "evidence.md"
EVIDENCE_CSS = ROOT / "framework" / "src" / "components" / "evidence.css"
EVIDENCE_JS = ROOT / "framework" / "src" / "components" / "evidence.js"
TABLE_CSS = ROOT / "framework" / "src" / "components" / "ev_table.css"
TABLE_JS = ROOT / "framework" / "src" / "components" / "ev_table.js"


def _rule(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css, flags=re.DOTALL)
    assert match is not None, f"missing CSS rule for {selector}"
    return match.group(1)


def test_page_header_lead_is_two_sentences() -> None:
    page = PAGE.read_text(encoding="utf-8")
    header = re.search(r'<header class="atlas-page-head">(.*?)</header>', page, flags=re.DOTALL)
    assert header is not None
    assert "atlas-page-head__eyebrow" in header.group(1)
    # VD-24: the h1 and lead sit inside the page head, so the full-width band holds both.
    assert '<h1 id="evidence-map">Evidence map</h1>' in header.group(1)
    assert 'class="atlas-page-head__lead"' in header.group(1)
    assert "# Evidence map" not in page

    css = EVIDENCE_CSS.read_text(encoding="utf-8")
    assert "header.atlas-page-head + h1" not in css
    assert "h1 + .atlas-page-head__lead" not in css

    lead = re.search(r'<p class="atlas-page-head__lead">(.*?)</p>', page, flags=re.DOTALL)
    assert lead is not None
    sentences = [part for part in re.split(r"(?<=[.!?])\s+", lead.group(1).strip()) if part]
    assert len(sentences) == 2


def test_evidence_runtime_waits_for_initial_paint_and_reports_failure() -> None:
    page = PAGE.read_text(encoding="utf-8")
    bootstrap = re.search(r"```js\s*(.*?)\s*```", page, flags=re.DOTALL)
    assert bootstrap is not None
    source = bootstrap.group(1)

    assert 'import {mountEvidence} from "../components/evidence.js";' in source
    assert re.search(
        r"requestAnimationFrame\(\(\) =>\s*\{\s*"
        r"requestAnimationFrame\(\(\) =>\s*\{\s*"
        r"mountEvidence\(\)\.catch\(\(error\) => console\.error\("
        r'"Failed to initialize the Evidence map\."',
        source,
    )
    assert not re.search(r"(?m)^mountEvidence\(\);$", source)


def test_page_styles_load_before_markup_and_callouts_follow_filters() -> None:
    page = PAGE.read_text(encoding="utf-8")
    expected_stylesheets = (
        "evidence.css",
        "v3_flow.css",
        "v4_trend.css",
        "ev_heatmap.css",
        "ev_table.css",
    )
    stylesheet_links = list(
        re.finditer(r'<link rel="stylesheet" href="\.\./components/([^"]+)">', page)
    )
    assert tuple(match.group(1) for match in stylesheet_links) == expected_stylesheets
    header_start = page.index('<header class="atlas-page-head">')
    assert all(match.start() < header_start for match in stylesheet_links)

    layout_start = page.index('<div class="ev-layout">')
    layout_end = page.index("\n  </div>", layout_start)
    info_start = page.index('<div class="atlas-callout atlas-callout--info ev-info-callout"')
    recent_start = page.index('<section id="ev-recent"')
    publications_start = page.index(
        '<section class="ev-view atlas-chart" aria-labelledby="ev-table-heading"'
    )
    assert layout_start < layout_end < info_start < recent_start < publications_start


def test_how_to_disclosure_preserves_filter_and_selection_guidance() -> None:
    page = PAGE.read_text(encoding="utf-8")
    disclosure = re.search(
        r'<details class="atlas-disclosure ev-how-to">(.*?)</details>',
        page,
        flags=re.DOTALL,
    )
    assert disclosure is not None
    assert "<summary>How to use this page</summary>" in disclosure.group(1)
    assert "year range, topic, sector, work type, open access" in disclosure.group(1)
    assert "The page lists plastic-related works only." in disclosure.group(1)
    assert "selecting heatmap cells narrows the publication table below" in disclosure.group(1)
    assert "Click a topic, matrix, or period heading" in disclosure.group(1)


def test_development_information_and_recent_items_use_callouts() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert '<div class="atlas-callout atlas-callout--dev ev-dev-callout" role="note">' in page
    assert '<p class="ev-notice">In development:' in page
    assert '<div class="atlas-callout atlas-callout--info ev-info-callout" role="note">' in page
    assert '<aside class="atlas-callout' not in page
    assert 'class="data-note ev-aux-note"' in page
    assert 'id="ev-recent" class="ev-recent atlas-callout atlas-callout--new"' in page
    assert 'aria-label="New in the last 2 weeks" hidden' in page
    assert (
        '<div class="atlas-callout atlas-callout--caution ev-volume-callout" '
        'role="note"><p class="data-note volume-caption">Counts show how much has been published, '
        "not the strength or quality of the evidence.</p></div>"
    ) in page

    css = EVIDENCE_CSS.read_text(encoding="utf-8")
    no_icon_callouts = _rule(css, "#evidence-root .ev-recent, .ev-dev-callout, .ev-info-callout")
    assert "grid-template-columns: minmax(0, 1fr)" in no_icon_callouts
    info_link = _rule(css, ".ev-info-callout a")
    assert "display: inline-flex" in info_link
    assert "min-height: 1.5rem" in info_link
    assert "align-items: center" in info_link
    assert "padding-inline" not in info_link
    caution = _rule(css, "#evidence-root .ev-volume-callout > .volume-caption")
    assert "color: var(--atlas-caution-ink)" in caution


def test_topic_filter_rows_get_decorative_colored_pattern_dots() -> None:
    source = EVIDENCE_JS.read_text(encoding="utf-8")
    assert 'if (ui.key === "topic")' in source
    assert 'dot.className = "topic-dot";' in source
    assert 'dot.setAttribute("aria-hidden", "true");' in source
    assert "dot.style.background = window.AtlasTopics.cssFill(label);" in source
    assert 'window.AtlasTopics.pattern(label) === "hatch"' in source
    assert "window.AtlasTopics.isAuxiliary(label)" in source
    assert "name.prepend(dot);" in source

    css = EVIDENCE_CSS.read_text(encoding="utf-8")
    assert "#evidence-root .topic-dot" in css
    assert "#evidence-root .topic-dot.hatch" in css
    assert "#evidence-root .topic-dot.auxiliary" in css
    dot = re.search(r"#evidence-root \.topic-dot\s*\{([^}]*)\}", css, flags=re.DOTALL)
    assert dot is not None
    assert "border-radius: 50%" in dot.group(1)


def test_trends_heatmap_and_publications_keep_runtime_targets_in_chart_cards() -> None:
    page = PAGE.read_text(encoding="utf-8")
    for heading_id in ("ev-v4-heading", "ev-heatmap-heading", "ev-table-heading"):
        section_pattern = (
            rf'<section class="ev-view atlas-chart" '
            rf'aria-labelledby="{heading_id}"[^>]*>(.*?)</section>'
        )
        match = re.search(
            section_pattern,
            page,
            flags=re.DOTALL,
        )
        assert match is not None
        assert f'id="{heading_id}"' in match.group(1)
        assert 'class="atlas-chart__head"' in match.group(1)
        assert 'class="atlas-chart__body"' in match.group(1)

    assert 'id="ev-v4"></div>' in page
    assert 'id="ev-heatmap"></div>' in page
    assert '<div class="atlas-chart__body"><div id="ev-v4"></div></div>' in page
    assert '<div class="atlas-chart__body"><div id="ev-heatmap"></div></div>' in page
    assert '<div class="atlas-chart__body"><div id="ev-table-selection"' in page


def test_ux30_banner_semantics_are_retained_with_filter_chip_presentation() -> None:
    page = PAGE.read_text(encoding="utf-8")
    banner = (
        '<div id="ev-table-selection" class="ev-table-selection ev-table-root" '
        'role="status" aria-live="polite" hidden></div>'
    )
    assert f'<div class="atlas-chart__body">{banner}<div id="ev-table">' in page

    css = TABLE_CSS.read_text(encoding="utf-8")
    chip = re.search(r"\.ev-table-root\.ev-table-selection\s*\{([^}]*)\}", css, flags=re.DOTALL)
    assert chip is not None
    assert "display: inline-flex" in chip.group(1)
    assert "border-radius: var(--atlas-radius-pill)" in chip.group(1)
    assert "background: var(--theme-background-alt)" in chip.group(1)
    assert re.search(
        r"\.ev-table-root\.ev-table-selection button\s*\{[^}]*"
        r"border-radius: var\(--atlas-radius-pill\)",
        css,
        flags=re.DOTALL,
    )


def test_evidence_filter_checkboxes_and_labels_have_24px_targets() -> None:
    evidence_js = EVIDENCE_JS.read_text(encoding="utf-8")
    table_js = TABLE_JS.read_text(encoding="utf-8")
    assert 'row.className = "ev-option";' in evidence_js
    assert 'input.type = "checkbox";' in evidence_js
    assert 'class="ev-check"><input type="checkbox"' in table_js

    evidence_css = EVIDENCE_CSS.read_text(encoding="utf-8")
    filter_row = _rule(evidence_css, "#evidence-root .ev-option")
    filter_input = _rule(evidence_css, '#evidence-root .ev-option input[type="checkbox"]')
    assert "min-height: 1.75rem" in filter_row
    assert all(
        size in filter_input
        for size in (
            "width: 1.5rem",
            "height: 1.5rem",
            "min-width: 1.5rem",
            "min-height: 1.5rem",
        )
    )

    table_css = TABLE_CSS.read_text(encoding="utf-8")
    table_label = _rule(table_css, ".ev-table-root .ev-check")
    table_input = _rule(table_css, '.ev-table-root .ev-check input[type="checkbox"]')
    assert "min-height: 2.1rem" in table_label
    assert all(
        size in table_input
        for size in (
            "width: 1.5rem",
            "height: 1.5rem",
            "min-width: 1.5rem",
            "min-height: 1.5rem",
        )
    )


def test_table_disclosures_and_links_have_24px_targets_and_keep_scroll() -> None:
    table_js = TABLE_JS.read_text(encoding="utf-8")
    assert 'class="ev-abstract"' in table_js
    assert "<summary>Abstract" in table_js
    assert 'class="ev-links"' in table_js
    assert '<a href="${escapeHtml(row.doi)}"' in table_js
    assert 'class="ev-recent-list"' in table_js

    css = TABLE_CSS.read_text(encoding="utf-8")
    summary = _rule(css, ".ev-table-root details.ev-abstract summary")
    links = _rule(css, ".ev-table-root a, .ev-recent a")
    assert "min-height: 1.5rem" in summary
    assert "padding-block: 0.1rem" in summary
    assert "display: inline-flex" in links
    assert "min-width: 1.5rem" in links
    assert "min-height: 1.5rem" in links

    scroll = _rule(css, ".ev-table-root .ev-table-scroll")
    table = _rule(css, ".ev-table-root table.ev-works")
    assert "overflow-x: auto" in scroll
    assert "width: 100%" in table
    assert "min-width: 52rem" in table
