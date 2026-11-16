"""VD-7b source contracts for the Funding page visual adoption."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
COMP = SRC / "components"
PAGE = SRC / "funding.md"
STYLES = COMP / "funding.css"
VIZ_STYLES = COMP / "funding_viz.css"
SCRIPT = COMP / "funding.js"
VIZ = COMP / "funding_viz.js"
SHARED_STYLES = SRC / "design" / "components.css"
HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])")

PRIMARY_IDS = {
    "grants-search",
    "grants-agency",
    "grants-tag",
    "grants-year-from",
    "grants-year-to",
}
MORE_IDS = {
    "grants-sector",
    "grants-funder-type",
    "grants-funder",
    "grants-program",
    "grants-amount-min",
    "grants-amount-max",
    "grants-institution-type",
    "grants-ca-led",
    "grants-plastic",
}
# Ids that the page script, scripts/ux_tasks.py and the URL hash state rely on.
SCRIPT_IDS = {
    "grants-reset",
    "grants-filter-count",
    "grants-more-filters",
    "grants-chips",
    "grants-status",
    "grants-csv",
    "grants-viz",
    "grants-table",
    "grants-prev",
    "grants-next",
    "grants-page",
    "grants-page-size",
    "grants-basis",
    "open-calls",
    "open-calls-status",
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _ids(markup: str) -> list[str]:
    return re.findall(r'\sid="([^"]+)"', markup)


def _render_viz_frame() -> str:
    """Return the static chart frame that funding_viz.js writes before any award arrives."""
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required to render framework/src/components/funding_viz.js")
    script = "const m = await import(process.argv[1]); process.stdout.write(m.VIZ_SKELETON);"
    result = subprocess.run(
        [node, "--input-type=module", "-e", script, VIZ.as_uri()],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_page_has_one_h1_and_no_awards_heading_after_it() -> None:
    page = _read(PAGE)
    assert len(re.findall(r"<h1[\s>]", page)) == 1
    assert "<h1>Funding</h1>" in page
    after = page[page.index("<h1>Funding</h1>") + len("<h1>Funding</h1>") :]
    following = re.search(r"<h([1-6])[^>]*>(.*?)</h\1>", after, re.S)
    assert following, "the page has headings after the h1"
    assert following.group(2).strip() != "Awards"
    assert not re.search(r"<h2[^>]*>\s*Awards\s*</h2>", page)
    assert not re.search(r"^## Awards\s*$", page, re.M)


def test_header_uses_the_shared_page_head() -> None:
    page = _read(PAGE)
    assert '<header class="atlas-page-head funding-page-head">' in page
    assert 'class="atlas-page-head__eyebrow"' in page
    assert ">Data</" in page
    assert 'class="atlas-page-head__lead"' in page
    assert 'href="#i-coins"' in page


def test_amount_basis_and_volume_note_are_visible_callouts() -> None:
    page = _read(PAGE)
    outside_details = re.sub(r"<details\b.*?</details>", "", page, flags=re.S)
    caution = re.search(
        r'<div id="grants-basis-caution" class="atlas-callout atlas-callout--caution">'
        r"(.*?)</div>",
        outside_details,
        re.S,
    )
    assert caution, "the amount-basis caution must be visible, not inside a closed disclosure"
    assert "Amounts follow each source's own basis" in caution.group(1)
    info = re.search(
        r'<div class="atlas-callout atlas-callout--info"[^>]*>(.*?)</div>',
        outside_details,
        re.S,
    )
    assert info, "the volume note must be a visible info callout"
    assert 'class="data-note volume-caption"' in info.group(1)
    assert "Award counts show volume, not strength" in info.group(1)


def test_primary_and_more_filters_split_the_fields() -> None:
    page = _read(PAGE)
    primary = re.search(
        r'<div class="atlas-filters__grid grants-primary-filters">(.*?)<details\b', page, re.S
    )
    assert primary, "primary fields sit in one atlas-filters__grid before the disclosure"
    assert set(_ids(primary.group(1))) == PRIMARY_IDS
    more = re.search(
        r'<details id="grants-more-filters" class="atlas-filters__more">(.*?)</details>',
        page,
        re.S,
    )
    assert more, "the other filters sit under atlas-filters__more"
    assert set(_ids(more.group(1))) == MORE_IDS
    assert re.search(r"<summary>More filters <span>\(9\)</span></summary>", more.group(1))
    assert len(MORE_IDS) == 9


def test_filter_panel_uses_the_shared_head_count_and_clear_all() -> None:
    page = _read(PAGE)
    assert 'class="atlas-filters" aria-labelledby="grants-filters-heading"' in page
    head = re.search(r'<div class="atlas-filters__head">(.*?)</div>', page, re.S)
    assert head, "the filter panel has an atlas-filters__head"
    assert ">Filters</h2>" in head.group(1)
    assert 'id="grants-filter-count"' in head.group(1)
    assert re.search(r'<button id="grants-reset"[^>]*>Clear all</button>', head.group(1))


def test_every_id_the_script_uses_exists_on_the_page() -> None:
    page = _read(PAGE)
    script = _read(SCRIPT)
    ids = set(_ids(page))
    filter_ids = set(re.findall(r'\{key: "\w+", id: "([^"]+)"\}', script))
    assert len(filter_ids) == 13
    assert filter_ids | {"grants-plastic"} <= ids
    assert SCRIPT_IDS <= ids
    assert 'state.viz = mountFundingViz($("grants-viz"));' in script


def test_active_filters_are_removable_chips_and_the_count_is_kept_current() -> None:
    page = _read(PAGE)
    script = _read(SCRIPT)
    assert re.search(r'<div id="grants-chips" class="atlas-active-filters"', page)
    assert 'class="atlas-filter-chip"' in script
    assert 'aria-label="Remove ${escapeHtml(field)} filter"' in script
    assert "Reset all filters and sort" in script
    assert "`${active} on`" in script


def test_more_filters_opens_itself_for_a_hidden_active_filter() -> None:
    script = _read(SCRIPT)
    assert (
        "if (plasticOff || HIDDEN_FILTER_IDS.some((id) => $(id).value)) "
        '$("grants-more-filters").open = true;'
    ) in script
    assert '"grants-ca-led"' in script
    assert "grants-filter-panel" not in script


def test_chart_cards_have_a_chart_table_control_with_aria_pressed() -> None:
    frame = _render_viz_frame()
    cards = frame.split('<section class="atlas-chart"')[1:]
    assert len(cards) == 5, "sankey, years, organisations, topic heatmap and sector heatmap"
    for card in cards:
        body = card.split("</section>", 1)[0]
        assert 'class="atlas-segmented"' in body
        buttons = re.findall(
            r'<button type="button" data-view="(chart|table)" aria-pressed="(true|false)">',
            body,
        )
        assert [view for view, _ in buttons] == ["chart", "table"]
        assert [pressed for _, pressed in buttons] == ["true", "false"]
        assert 'data-fv-pane="chart"' in body
        assert 'data-fv-pane="table" hidden' in body
    assert "View the Sankey as a table" not in frame
    assert "View as a table" not in frame


def test_stat_tiles_reserve_height_before_the_awards_arrive() -> None:
    frame = _render_viz_frame()
    assert '<dl class="atlas-kpis" data-fv="tiles">' in frame
    assert frame.count('class="atlas-kpi atlas-kpi--loading"') == 5
    shared = _read(SHARED_STYLES)
    assert re.search(r"\.atlas-kpi \{[^}]*min-height: 8\.5rem", shared, re.S)
    assert not re.search(r"atlas-kpi[^{}]*\{[^}]*min-height", _read(STYLES))


def test_page_and_visualization_stylesheets_use_tokens_not_hex() -> None:
    assert HEX.findall(_read(STYLES)) == []
    assert HEX.findall(_read(VIZ_STYLES)) == []
    assert "var(--atlas-" in _read(STYLES)


def test_page_has_no_facet_disclosures_and_keeps_the_volume_caption_once() -> None:
    page = _read(PAGE)
    assert 'class="facet' not in page
    assert page.count('class="data-note volume-caption"') == 1
    assert 'id="grants-basis"' in page
    assert "Per-source subtotals" in _read(SCRIPT)
