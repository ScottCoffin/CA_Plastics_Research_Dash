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
FUNDING_MD = SRC / "funding.md"
FUNDING_JS = COMP / "funding.js"
VIZ_JS = COMP / "funding_viz.js"
MODEL_JS = COMP / "funding_viz_model.js"
VIZ_CSS = COMP / "funding_viz.css"
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
    assert '<link rel="stylesheet" href="./components/funding_viz.css">' in md
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
        'aria-labelledby="fv-sankey-h"',
        'aria-labelledby="fv-year-h"',
        'aria-labelledby="fv-org-h"',
        'aria-labelledby="fv-heat-h"',
        'aria-labelledby="fv-matrix-h"',
    ]
    positions = [viz.index(token) for token in order]
    assert positions == sorted(positions)
    # The visualizations sit between the status line and the awards table.
    assert (
        md.index('id="grants-status"') < md.index('id="grants-viz"') < md.index('id="grants-table"')
    )


def test_views_keep_table_alternatives_and_accessible_names() -> None:
    viz = _read(VIZ_JS)
    assert "View the Sankey as a table" in viz
    assert viz.count("View as a table") == 1
    assert 'role="img" aria-labelledby="fv-sankey-title"' in viz
    assert 'role="img" aria-labelledby="fv-year-title"' in viz
    assert 'aria-label="Sankey diagram, scrollable"' in viz


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
