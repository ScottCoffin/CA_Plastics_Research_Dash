"""Funding visualizations on the Framework Funding page (ported from the classic grants page)."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
COMP = SRC / "components"
FUNDING_MD = SRC / "california" / "funding.md"
FUNDING_JS = COMP / "funding.js"
VIZ_JS = COMP / "funding_viz.js"
MODEL_JS = COMP / "funding_viz_model.js"
VIZ_CSS = COMP / "funding_viz.css"
STYLES = COMP / "funding.css"
RUNTIME = ROOT / "tests" / "framework_funding_viz_runtime.mjs"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_viz_runtime_checks_model_and_markup() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for tests/framework_funding_viz_runtime.mjs")
    subprocess.run([node, str(RUNTIME)], cwd=ROOT, check=True)


def test_funding_page_has_no_classic_link_or_inline_style() -> None:
    md = _read(FUNDING_MD)
    assert "Open the funding visualizations" not in md
    assert "funding-grants-link" not in md
    assert 'style="' not in md


def test_funding_page_loads_viz_stylesheet_and_mount_point() -> None:
    md = _read(FUNDING_MD)
    assert '<link rel="stylesheet" href="../components/funding_viz.css">' in md
    assert (COMP / "funding_viz.css").is_file()
    assert 'id="grants-viz"' in md
    assert "grants-chart" not in md


def test_old_charts_removed_and_viz_follows_filter_form() -> None:
    js = _read(FUNDING_JS)
    assert "svgBarChartYears" not in js
    assert "svgBarChartInstitutions" not in js
    assert 'import {mountFundingViz} from "./funding_viz.js";' in js
    assert 'state.viz = mountFundingViz($("grants-viz"));' in js
    assert "state.viz.update(state.grantsFiltered, sectorLabelsOf());" in js


def test_views_render_in_the_requested_order_before_the_table() -> None:
    md = _read(FUNDING_MD)
    viz = _read(VIZ_JS)
    order = [
        'data-fv-section="tiles"',
        'id: "fv-sankey-h"',
        'id: "fv-year-h"',
        'id: "fv-org-h"',
        'id: "fv-heat-h"',
        'id: "fv-matrix-h"',
    ]
    positions = [viz.index(token) for token in order]
    assert positions == sorted(positions)
    # The visualizations sit between the status line and the awards table.
    assert (
        md.index('id="grants-status"') < md.index('id="grants-viz"') < md.index('id="grants-table"')
    )


def test_views_keep_table_alternatives_and_accessible_names() -> None:
    viz = _read(VIZ_JS)
    # VD-7b: each chart card carries a Chart/Table control, which replaces the separate table links.
    assert "View the Sankey as a table" not in viz
    assert "View as a table" not in viz
    assert 'data-view="table"' in viz
    assert 'role="group" aria-labelledby="fv-sankey-title"' in viz
    assert 'role="img" aria-labelledby="fv-year-title"' in viz
    assert 'aria-label="Sankey diagram, scrollable"' in viz


def test_sankey_drill_down_is_a_keyboard_operable_local_control() -> None:
    viz = _read(VIZ_JS)
    css = _read(VIZ_CSS)
    assert "Show all flows" in viz
    assert 'role="button"' in viz
    assert "focusOfNode" in viz
    assert ".fv-node.is-focus" in css


def test_viz_has_no_second_filter_form() -> None:
    viz = _read(VIZ_JS)
    assert "<form" not in viz
    assert "<select" not in viz


def test_viz_text_has_no_summed_total_or_internal_ids() -> None:
    combined = _read(VIZ_JS) + _read(MODEL_JS) + _read(FUNDING_MD) + _read(VIZ_CSS)
    assert "summing to" not in combined
    for pattern in (r"\bUX-\d+", r"\bS\d+\.\d+\b", r"\bEM-\d+\b"):
        assert not re.search(pattern, combined), pattern


def test_amount_figures_carry_the_not_comparable_caveat() -> None:
    viz = _read(VIZ_JS)
    # Every line that prints a reported amount also says the source bases differ.
    for line in viz.splitlines():
        if "fmtUsd(" in line and "reported" in line:
            assert "AMOUNT_CAVEAT" in line or "source bases differ" in line, line.strip()
    assert 'const AMOUNT_CAVEAT = "source bases differ";' in viz


def test_viz_css_uses_theme_variables_and_scrolls_the_sankey_box() -> None:
    css = _read(VIZ_CSS)
    assert "var(--theme-foreground" in css
    assert re.search(r"\.fv-sankey-wrap \{[^}]*overflow-x: auto", css)
    assert re.search(r"\.fv-root \{[^}]*max-width: 100%", css)


def test_funding_css_keeps_touch_target_selectors_and_drops_chart_rules() -> None:
    css = _read(COMP / "funding.css")
    assert ".grants-chart" not in css
    assert ".grants-legend" not in css
    assert '.grants-field input[type="number"]' in css


def test_heatmap_cells_are_toggle_buttons_with_pressed_state() -> None:
    viz = _read(VIZ_JS)
    # Chart cells are buttons (Enter and Space come with the native button); a selected cell reports
    # aria-pressed.
    assert '<button type="button" class="fv-cell" data-heat="' in viz
    assert 'aria-pressed="${pressed ? "true" : "false"}"' in viz
    assert "button.fv-cell[data-heat]" in viz
    # Each heatmap has a selection line with a Clear control; its Table pane stays plain numbers.
    assert 'data-heat-selection="${kind}"' in viz
    assert 'class="fv-heat-clear" data-heat="${kind}" hidden>Clear</button>' in viz
    assert "cells selected" in viz
    assert "heatTableHtml(heat, T, {plain: true})" in viz
    assert "matrixTableHtml(matrix, state.labels, T, {plain: true})" in viz


def test_heatmap_selection_narrows_only_the_awards_table_and_its_counts() -> None:
    viz = _read(VIZ_JS)
    js = _read(FUNDING_JS)
    # The view reports the awards a selection leaves; the page owns the table, status and CSV.
    assert "onSelect(handler)" in viz
    assert "filterByHeatSelection(state.vrows, heat)" in viz
    assert "state.viz.onSelect(onHeatSelect);" in js
    assert "state.heatRows = rows;" in js
    assert "renderGrantsTable(shown);" in js
    assert "buildGrantsCsv(shownRows())" in js
    assert "Showing ${shown.length} of ${state.grantsFiltered.length} filtered awards" in js
    # The charts above keep following the page filters only.
    assert "renderSankey();" in viz and "renderYears();" in viz


def test_funding_tables_are_not_capped_at_the_framework_default_width() -> None:
    css = _read(STYLES)
    # Framework's default stylesheet caps tables at 640px; the Funding page lifts that cap.
    assert "#funding-root table { max-width: none; }" in css
    assert re.search(r"#funding-root \.grants-subtotals \{[^}]*width: 100%", css)
    assert re.search(r"#funding-root #grants-basis \{[^}]*overflow-x: auto", css)
    assert re.search(r"\.grants-subtotals \{[^}]*min-width: 36rem", css)


def test_sankey_table_gives_the_from_and_to_columns_room() -> None:
    css = _read(VIZ_CSS)
    viz = _read(VIZ_JS)
    assert '<table class="fv-sankey-table">' in viz
    assert '<td class="fv-name">' in viz
    assert re.search(r"\.fv-sankey-table \{[^}]*min-width: 36rem", css)
    assert re.search(r"\.fv-sankey-table td\.fv-name \{[^}]*min-width: 14rem", css)


def test_heatmap_selection_styles_use_tokens_and_respect_reduced_motion() -> None:
    css = _read(VIZ_CSS)
    assert 'aria-pressed="true"' in css
    assert "outline: 2px solid var(--atlas-ink)" in css
    assert "var(--atlas-task-money)" in css
    # Transitions only when the reader has not asked for reduced motion.
    motion = re.search(r"@media \(prefers-reduced-motion: no-preference\) \{(.*?)\n\}", css, re.S)
    assert motion, "heatmap transitions must sit behind prefers-reduced-motion"
    assert "transition" in motion.group(1)
    assert css.count("transition:") == motion.group(1).count("transition:")


def test_funding_lead_mentions_the_heatmap_selection() -> None:
    assert "click heatmap cells to narrow it further" in _read(FUNDING_MD)
