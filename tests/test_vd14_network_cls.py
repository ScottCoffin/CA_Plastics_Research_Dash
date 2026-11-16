"""Acceptance checks for the Collaboration network layout-shift fix (VD-14)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "framework" / "src" / "network.md"
CSS = ROOT / "framework" / "src" / "components" / "network.css"
ICONS = ROOT / "framework" / "src" / "components" / "shared" / "icons.js"


def _css_block(css: str, selector: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(selector)}\s*\{{([^{{}}]*)\}}", css)
    assert match, selector
    return match.group(1)


def test_header_and_callout_are_static_markup_before_the_filters() -> None:
    page = PAGE.read_text(encoding="utf-8")
    # A runtime display() would insert these above .net-page after first paint and shift it.
    assert "display(html" not in page
    assert "import {icon}" not in page
    header = page.index('<header class="atlas-page-head">')
    callout = page.index('<p class="atlas-callout atlas-callout--info">')
    net_page = page.index('<section class="net-page"')
    assert header < callout < net_page
    assert page.index('<link rel="stylesheet" href="./components/network.css">') < net_page
    # The only remaining JavaScript block is the mount call, which comes after the static markup.
    assert page.count("```js") == 1
    assert page.index("```js") > net_page


def test_header_icons_reference_sprite_symbols_that_exist() -> None:
    page = PAGE.read_text(encoding="utf-8")
    icons = ICONS.read_text(encoding="utf-8")
    for name in ("network", "info"):
        assert f'<use href="#i-{name}"></use>' in page
        assert re.search(rf"(?m)^\s+{name}: '", icons), name


def test_chart_box_has_reserved_size_before_data_loads() -> None:
    css = CSS.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    assert "position: relative;" in _css_block(css, ".net-chart")
    body = _css_block(css, ".net-body")
    assert "height: 70vh;" in body and "min-height: 420px;" in body
    mobile = re.search(r"@media \(max-width: 720px\) \{(.*?)\n\}\n", css, re.DOTALL)
    assert mobile
    stage = _css_block(mobile.group(1), ".net-stage")
    assert "height: 60vh;" in stage and "min-height: 320px;" in stage
    assert 'class="net-body"' in page
    assert 'id="network-stage" class="net-stage"' in page


def test_loading_message_overlays_the_chart_box() -> None:
    css = CSS.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    message = _css_block(css, ".net-message")
    for declaration in ("position: absolute;", "inset: 0;", "pointer-events: none;"):
        assert declaration in message, declaration
    assert ".net-message[hidden] {\n  display: none;\n}" in css
    # The message sits inside the chart box, before the body it overlays; hiding it moves nothing.
    chart = page.index('<div id="network-chart"')
    text = page.index('<p id="network-message"')
    body = page.index('<div class="net-body">')
    assert chart < text < body


def test_network_css_adds_no_hex_literals() -> None:
    css = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.DOTALL)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
