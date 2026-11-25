"""Static checks for the graph viewer's accessibility contract (BQ-V.5).

These read the component, model and stylesheet as text. The rendered behaviour (axe, keyboard walk)
is checked in a browser and recorded in docs/BQ_V5_VERIFICATION.md.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "framework/src/components/graph_viewer.js"
MODEL = ROOT / "framework/src/components/graph_viewer_model.js"
STYLE = ROOT / "framework/src/components/graph_viewer.css"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_canvas_is_a_labelled_application_with_keys_described() -> None:
    text = _text(COMPONENT)
    assert 'role="application" tabindex="0"' in text
    assert 'aria-describedby="${id}-keys"' in text
    assert 'id="${id}-keys"' in text
    # The label names the graph, its node and link counts, and where the table is.
    assert "network graph:" in text and "Show as table button" in text
    # sigma draws into canvases; those are not content for assistive technology.
    assert 'canvas.setAttribute("aria-hidden", "true")' in text
    assert 'data-gv="stage" aria-hidden' not in text


def test_graph_keys_cover_zoom_pan_reset_and_escape() -> None:
    text = _text(COMPONENT)
    for key in (
        '"+"',
        '"-"',
        '"0"',
        '"ArrowLeft"',
        '"ArrowRight"',
        '"ArrowUp"',
        '"ArrowDown"',
        '"Escape"',
    ):
        assert key in text, key
    assert 'ui.stage.addEventListener("keydown", onGraphKey' in text
    assert 'ui.details.addEventListener("keydown"' in text


def test_selection_moves_focus_and_is_announced() -> None:
    text = _text(COMPONENT)
    # The details heading is the focus target; the live region announces each selection change.
    assert 'data-gv="details-title" tabindex="-1"' in text
    assert 'data-gv="announce" aria-live="polite"' in text
    assert "ui.detailsTitle.focus()" in text
    assert "Selected ${node.name}" in text
    assert "Selection cleared." in text
    # Escape returns focus to the control that made the selection.
    assert "returnFocus" in text and "clearSelection" in text


def test_search_results_move_with_arrow_keys() -> None:
    text = _text(COMPONENT)
    assert 'event.key !== "ArrowDown" && event.key !== "ArrowUp"' in text
    assert "buttons[next].focus()" in text


def test_details_panel_is_a_labelled_region_and_its_body_is_not_a_paragraph() -> None:
    text = _text(COMPONENT)
    assert 'aria-labelledby="${id}-details-title" data-gv="details"' in text
    # Lists and definition lists are appended into the body, so it must not be a <p>.
    assert '<p data-gv="details-body"' not in text
    assert '<div data-gv="details-body">' in text


def test_legend_is_a_text_list_not_colour_alone() -> None:
    text = _text(COMPONENT)
    assert 'el("ul", {class: "gv-legend__list", "aria-label": `${title} colours`})' in text
    assert 'el("span", {}, `${label} (${formatCount(row.count)})`)' in text
    assert 'swatch = el("span", {class: "gv-swatch", "aria-hidden": "true"})' in text


def test_table_has_caption_scoped_headers_and_keyboard_sort_buttons() -> None:
    text = _text(COMPONENT)
    assert '<caption class="gv-sr">' in text
    assert 'el("th", {scope: "col", "aria-sort"' in text
    assert 'el("button", {class: "gv-sort", type: "button", "data-sort": key}, label)' in text
    assert 'el("th", {scope: "col"}, "Strongest links")' in text
    assert 'el("th", {scope: "row"})' in text
    # Header order and row cells must line up: name, kind, works, links, community, strongest links.
    assert 'links: "Links"' in text
    assert "topNeighbours(adjacency, node.index, 3)" in text


def test_sort_supports_links() -> None:
    model = _text(MODEL)
    assert 'key === "links"' in model


def test_stylesheet_has_focus_rings_and_24px_targets() -> None:
    css = _text(STYLE)
    assert ".gv-stage:focus-visible" in css
    assert ".gv-details__title:focus-visible" in css
    for selector in (".gv-link {", ".gv-sort {"):
        block = re.search(re.escape(selector) + r"(.*?)\}", css, re.S)
        assert block, selector
        assert "min-height: 1.5rem" in block.group(1), selector  # 24 px at the default root size
