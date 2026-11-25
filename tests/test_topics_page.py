"""BQ-4.4: static checks for /california/topics (page, renderer, styles, nav wiring).

No browser and no build: the rendered page is checked by the Playwright smoke run. These tests
keep the required blocks, data helper, table alternative and text-not-colour rules from drifting.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "framework" / "src" / "california" / "topics.md"
RENDERER = ROOT / "framework" / "src" / "components" / "topics_page.js"
STYLES = ROOT / "framework" / "src" / "components" / "topics_page.css"
CONFIG = ROOT / "framework" / "observablehq.config.js"
POSTBUILD = ROOT / "framework" / "scripts" / "postbuild.mjs"


def test_page_exists_with_root_and_head() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert "topics-root" in text
    assert 'class="atlas-page-head"' in text
    assert "../components/topics_page.css" in text


def test_page_loads_both_payloads_through_the_data_helper() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert 'loadJson("topics_timeseries.json")' in text
    assert 'loadJson("topic_bursts.json")' in text
    assert "../components/atlas.js" in text
    renderer = RENDERER.read_text(encoding="utf-8")
    assert "loadJson" not in renderer and "fetch(" not in renderer


def test_what_this_is_and_is_not_block_states_the_limits() -> None:
    text = PAGE.read_text(encoding="utf-8")
    block = text[text.index("## What this is and is not") :]
    block = block[: block.index("<section")]
    assert "rule-based" in block
    assert "not a measure of importance" in block
    assert "multiple testing" in block
    assert "counts and shares of plastic-related california works" in block.lower()


def test_page_publishes_no_numeric_figures_in_static_text() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert not re.search(r"\b\d+(\.\d+)?%", text)
    assert not re.search(r"\b0\.\d{2,}\b", text)


def test_renderer_has_a_table_alternative_and_sets_text_only() -> None:
    source = RENDERER.read_text(encoding="utf-8")
    assert ".innerHTML" not in source and ".outerHTML" not in source
    assert '"table"' in source and "tp-table" in source
    assert 'scope: "col"' in source or 'scope: "row"' in source
    assert "aria-label" in source
    assert "aria-sort" in source


def test_rising_flag_and_accuracy_are_text_not_colour_only() -> None:
    source = RENDERER.read_text(encoding="utf-8")
    assert "Flagged as rising" in source and "Not flagged as rising" in source
    assert "Accuracy: " in source
    assert "insufficient data" in source
    assert "tp-muted" in source
    assert "greyed" in source or "Pairs with fewer than" in source


def test_styles_are_scoped_and_add_no_hex_colours() -> None:
    text = STYLES.read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", text)
    for line in text.splitlines():
        if line.strip().startswith(".") and "{" in line:
            assert line.strip().startswith(".tp"), line


def test_navigation_places_topics_before_evidence_and_footer_links_it() -> None:
    config = CONFIG.read_text(encoding="utf-8")
    data_group = config[config.index('{name: "Data"') :]
    data_group = data_group[: data_group.index("]},")]
    assert data_group.index('path: "/california/topics"') < data_group.index(
        'path: "/california/evidence"'
    )
    assert 'path: "/california/topics"' in data_group
    footer = config.split("footer:", 1)[1]
    assert 'href="./california/topics"' in footer
    assert '"california/topics":' in POSTBUILD.read_text(encoding="utf-8")
