"""BQ-3.4: the collaboration-structure panel on /california/network (static checks).

Browser checks (axe, horizontal overflow, keyboard toggle, payload-to-DOM agreement) were run with
Playwright outside the repo; these tests pin the source rules that do not need a browser.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
COMPONENT = SRC / "components" / "network_metrics.js"
STYLE = SRC / "components" / "network_metrics.css"
NETWORK_JS = SRC / "components" / "network.js"
ATLAS_JS = SRC / "components" / "atlas.js"
PAGE = SRC / "california" / "network.md"

HEX_COLOUR = re.compile(
    r"(?<![\w-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9a-fA-F])"
)
HELP_TEXT = re.compile(r'aria-label="About ([^":]+): ([^"]+)" data-atlas-tip="([^"]+)"')
# Identifiers that would expose a person or an institution (payload keys and ranking words).
PERSON_OR_RANK = re.compile(
    r"author_ids?|inst_id|institution_ids|\.name\b|\bname:|display_name|\brank|leaderboard|\btop\s+\d",
    re.IGNORECASE,
)


def _strip_js_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def _strip_css_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def _panel_markup() -> str:
    page = PAGE.read_text(encoding="utf-8")
    start = page.index('<section id="network-metrics"')
    return page[start : page.index("```js", start)]


def test_component_and_style_exist_and_the_page_imports_them() -> None:
    assert COMPONENT.is_file()
    assert STYLE.is_file()
    page = PAGE.read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="../components/network_metrics.css">' in page
    assert 'import {mountNetworkMetrics} from "../components/network_metrics.js";' in page
    assert "mountNetworkMetrics();" in page
    # network.js is not touched: the panel is mounted from the page's own script block.
    assert "network_metrics" not in NETWORK_JS.read_text(encoding="utf-8")


def test_payload_is_loaded_through_site_root_and_lazily() -> None:
    text = COMPONENT.read_text(encoding="utf-8")
    assert 'import {escapeHtml, formatCount, formatRefresh, loadJson} from "./atlas.js";' in text
    assert 'loadJson("network_metrics.json")' in text
    assert "../data/" not in text
    atlas = ATLAS_JS.read_text(encoding="utf-8")
    assert "export async function loadJson" in atlas
    assert 'dataFolderUrl("data/california/", path)' in atlas
    assert "new URL(folder, siteRoot())" in atlas
    # Lazy: the payload is fetched only when the panel nears the viewport.
    assert "IntersectionObserver" in text and "rootMargin" in text
    assert text.count("loadPanel(panel);") == 2


def test_payload_schema_is_checked_and_periods_are_the_four_windows() -> None:
    text = COMPONENT.read_text(encoding="utf-8")
    assert 'const SCHEMA = "bq3-v1";' in text
    assert "payload.schema_version !== SCHEMA" in text
    for key in ("2011-2015", "2016-2020", "2021-2025", "2026"):
        assert f'key: "{key}"' in text, key
    assert 'key: "all"' in text
    assert "partial: true" in text


def test_table_view_has_caption_scope_headers_and_keyboard_region() -> None:
    text = COMPONENT.read_text(encoding="utf-8")
    assert "<caption" in text
    assert 'scope="col"' in text and 'scope="row"' in text
    assert 'class="atlas-table-wrap nm-table-wrap" role="region" tabindex="0"' in text
    assert 'class="atlas-table nm-table"' in text
    markup = _panel_markup()
    assert 'class="atlas-chart nm-card" data-view="chart"' in markup
    assert 'class="atlas-segmented"' in markup
    assert 'data-view="chart" aria-pressed="true"' in markup
    assert 'data-view="table" aria-pressed="false"' in markup


def test_panel_renders_no_person_or_institution_identifiers_or_rankings() -> None:
    code = _strip_js_comments(COMPONENT.read_text(encoding="utf-8"))
    assert not PERSON_OR_RANK.search(code), PERSON_OR_RANK.search(code)
    assert "<a " not in code and "href" not in code
    markup = _panel_markup()
    assert "<a " not in markup and "href" not in markup


def test_no_hex_colours_in_component_or_style() -> None:
    code = _strip_js_comments(COMPONENT.read_text(encoding="utf-8"))
    style = _strip_css_comments(STYLE.read_text(encoding="utf-8"))
    assert not HEX_COLOUR.search(code)
    assert not HEX_COLOUR.search(style)


def test_style_selectors_are_scoped_to_the_panel() -> None:
    style = _strip_css_comments(STYLE.read_text(encoding="utf-8"))
    selectors = [
        selector.strip()
        for block in re.findall(r"([^{}]+)\{", style)
        for selector in re.split(r",(?![^()]*\))", block)
        if selector.strip() and not selector.strip().startswith("@")
    ]
    assert selectors
    assert all(
        selector.startswith((".nm-", "#observablehq-main .nm-panel")) for selector in selectors
    ), [s for s in selectors if not s.startswith((".nm-", "#observablehq-main .nm-panel"))]


def test_panel_copy_avoids_the_retired_public_word() -> None:
    assert not re.search(r"expert", COMPONENT.read_text(encoding="utf-8"), re.IGNORECASE)
    assert not re.search(r"expert", _panel_markup(), re.IGNORECASE)


def test_panel_help_button_follows_the_tooltip_rule() -> None:
    markup = _panel_markup()
    matches = list(HELP_TEXT.finditer(markup))
    assert matches, "the panel has no help button"
    for match in matches:
        assert match.group(2) == match.group(3)
        assert 'class="atlas-help"' in markup[match.start() - 80 : match.start()]


def test_heading_stays_static_markup() -> None:
    markup = _panel_markup()
    assert '<h2 id="network-metrics-heading">How California authors collaborate</h2>' in markup
