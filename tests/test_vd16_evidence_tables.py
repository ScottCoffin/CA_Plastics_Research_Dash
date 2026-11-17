"""VD-16: every chart on the Evidence map has a Chart/Table control and a table pane."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
COMP = SRC / "components"
PAGE = SRC / "evidence.md"
EVIDENCE_JS = COMP / "evidence.js"
EVIDENCE_CSS = COMP / "evidence.css"
TREND_JS = COMP / "v4_trend.js"
HEATMAP_JS = COMP / "ev_heatmap.js"
FLOW_JS = COMP / "v3_flow.js"
VIEW_SOURCES = (EVIDENCE_JS, TREND_JS, HEATMAP_JS, FLOW_JS)
CHART_HEADINGS = ("ev-v4-heading", "ev-heatmap-heading", "ev-v3-heading")
CHART_HOSTS = ("ev-v4", "ev-heatmap", "ev-v3")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _cards(page: str) -> dict[str, str]:
    """Map each atlas-chart section's heading id to the markup inside the section."""
    pattern = (
        r'<section class="[^"]*atlas-chart[^"]*"'
        r'[^>]*aria-labelledby="([^"]+)"[^>]*>(.*?)</section>'
    )
    return {match.group(1): match.group(2) for match in re.finditer(pattern, page, flags=re.DOTALL)}


def _head(card: str) -> str:
    parts = card.split('<div class="atlas-chart__head">', 1)
    assert len(parts) == 2, "chart card has no atlas-chart__head"
    return parts[1].split('<div class="atlas-chart__body">', 1)[0]


def test_each_chart_card_has_a_chart_table_segmented_control() -> None:
    cards = _cards(_read(PAGE))
    for heading_id in CHART_HEADINGS:
        assert heading_id in cards, heading_id
        head = _head(cards[heading_id])
        assert f'<h2 id="{heading_id}"' in head, heading_id
        assert 'class="atlas-chart__source"' in head, heading_id
        group = re.search(
            r'<div class="atlas-segmented" role="group" '
            r'aria-label="Chart or table view: [^"]+">(.*?)</div>',
            head,
            flags=re.DOTALL,
        )
        assert group is not None, heading_id
        buttons = re.findall(
            r'<button type="button" data-view="(chart|table)" aria-pressed="(true|false)">',
            group.group(1),
        )
        assert [view for view, _ in buttons] == ["chart", "table"], heading_id
        assert [pressed for _, pressed in buttons] == ["true", "false"], heading_id


def test_only_the_three_evidence_charts_carry_the_control() -> None:
    cards = _cards(_read(PAGE))
    with_control = {heading for heading, card in cards.items() if "atlas-segmented" in card}
    assert with_control == set(CHART_HEADINGS)
    # The publication table is a list, not a chart, so it has no control.
    assert "ev-table-heading" in cards
    assert "atlas-segmented" not in cards["ev-table-heading"]


def test_each_chart_card_keeps_its_runtime_host() -> None:
    cards = _cards(_read(PAGE))
    for heading_id, host in zip(CHART_HEADINGS, CHART_HOSTS, strict=True):
        body = cards[heading_id].split('<div class="atlas-chart__body">', 1)[1]
        assert f'<div id="{host}"></div>' in body, host


def test_each_chart_has_a_table_pane_next_to_its_chart_pane() -> None:
    trend = _read(TREND_JS)
    heatmap = _read(HEATMAP_JS)
    flow = _read(FLOW_JS)
    assert trend.index('<div data-pane="chart">') < trend.index('<div data-pane="table">')
    assert heatmap.index('<div data-pane="chart">') < heatmap.index('<div data-pane="table">')
    chart_pane = flow.index('setAttribute("data-pane", "chart")')
    table_pane = flow.index('setAttribute("data-pane", "table")')
    assert chart_pane < table_pane
    assert "dataTable(data, rows, globalByYear, version)" in trend
    assert "countsHtml(model, mode)" in heatmap


def test_table_panes_use_the_shared_table_styles_inside_a_scroll_region() -> None:
    for path in (TREND_JS, HEATMAP_JS, FLOW_JS):
        text = _read(path)
        assert "atlas-table-wrap" in text, path.name
        assert re.search(r'class="atlas-table"|el\("table", "atlas-table"\)', text), path.name
        assert '"region"' in text, path.name
    assert 'tabindex="0"' in _read(TREND_JS) and 'tabindex="0"' in _read(HEATMAP_JS)
    assert "wrap.tabIndex = 0;" in _read(FLOW_JS)
    # The trend table was screen-reader-only; it is now the visible table pane.
    assert "v4-sr-only" not in _read(TREND_JS)


def test_flow_table_gives_stage_name_and_count() -> None:
    flow = _read(FLOW_JS)
    for header in ('"Stage"', '"Status"', '"Step"', '"Count"'):
        assert header in flow, header
    assert "row.stage" in flow and "step.value" in flow


def test_no_view_as_a_table_links_remain_on_the_evidence_map() -> None:
    for path in (PAGE, *VIEW_SOURCES):
        text = _read(path)
        assert not re.search(r"View [^<>\"]{0,80}as a table", text, flags=re.IGNORECASE), path.name
        assert "as a table" not in text.lower(), path.name


def test_control_mode_lives_on_the_card_and_css_shows_one_pane() -> None:
    js = _read(EVIDENCE_JS)
    assert "function wireChartViews()" in js
    assert '"#evidence-root .atlas-chart > .atlas-chart__head .atlas-segmented"' in js
    assert 'group.closest(".atlas-chart").dataset.view = button.dataset.view;' in js
    assert 'other.setAttribute("aria-pressed", String(other === button));' in js
    # Wired before the bundle loads, so the controls work as soon as the cards show.
    assert js.index("wireChartViews();") < js.index("await loadBundle();")

    css = _read(EVIDENCE_CSS)
    assert '#evidence-root .atlas-chart[data-view="table"] [data-pane="chart"]' in css
    assert '#evidence-root .atlas-chart:not([data-view="table"]) [data-pane="table"]' in css
    assert "atlas-segmented" not in css, "the control reuses the shared .atlas-segmented styles"


def test_heatmap_mode_toggle_selection_and_focus_are_unchanged() -> None:
    page = _read(PAGE)
    assert '<h2 id="ev-heatmap-heading" tabindex="-1">Evidence heatmap</h2>' in page
    heatmap = _read(HEATMAP_JS)
    assert 'role="group" aria-label="Heatmap view"' in heatmap
    assert 'data-mode="${key}"' in heatmap
    assert '<div class="ev-heatmap-selection">' in heatmap
    assert "Show in table" in heatmap and "Clear selection" in heatmap
    assert '$("ev-heatmap-heading").focus({preventScroll: true});' in _read(EVIDENCE_JS)


def test_views_add_no_data_loads() -> None:
    evidence = _read(EVIDENCE_JS)
    assert evidence.count("loadJson(") == 1
    assert evidence.count("dataUrl(") == 1
    trend = _read(TREND_JS)
    assert trend.count("fetch(") == 1
    heatmap = _read(HEATMAP_JS)
    flow = _read(FLOW_JS)
    assert "fetch(" not in heatmap and "loadJson(" not in heatmap
    assert flow.count("loadJson(") == 1


def test_evidence_eyebrow_has_its_nav_icon_and_the_sprite() -> None:
    page = (ROOT / "framework" / "src" / "evidence.md").read_text(encoding="utf-8")
    assert '<use href="#i-grid"></use></svg> Data</p>' in page
    assert "injectIconSprite();" in page
