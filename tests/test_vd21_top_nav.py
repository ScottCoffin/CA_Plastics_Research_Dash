"""VD-21: desktop top navigation in the Framework header, and no sidebar above 52rem."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK = ROOT / "framework"
SHELL_CSS = FRAMEWORK / "src" / "design" / "shell.css"
GROUPS = ("Explore", "Data", "Context", "Reference")
BUTTON = re.compile(r"<button\b([^>]*)>([^<]*)</button>")
ATTRIBUTE = re.compile(r'([\w-]+)="([^"]*)"')


def _header(path: str) -> str:
    config_uri = (FRAMEWORK / "observablehq.config.js").resolve().as_uri()
    script = (
        f"import({json.dumps(config_uri)}).then(m => {{"
        f"process.stdout.write(m.default.header({{title:'Test',path:{json.dumps(path)}}}));"
        "})"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=FRAMEWORK,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _attributes(tag_attributes: str) -> dict[str, str]:
    return dict(ATTRIBUTE.findall(tag_attributes))


def _desktop_block(css: str) -> str:
    """Comment-free inner text of the `@media not all and (max-width: 52rem)` block."""
    start = css.index("@media not all and (max-width: 52rem) {")
    open_brace = css.index("{", start)
    depth = 0
    for index in range(open_brace, len(css)):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
            if depth == 0:
                return re.sub(r"/\*.*?\*/", "", css[open_brace + 1 : index], flags=re.S)
    raise AssertionError("desktop media block is not closed")


def _rules(body: str) -> list[tuple[list[str], str]]:
    """(selectors, declarations) for each plain rule in a block with no nested at-rules."""
    return [
        ([selector.strip() for selector in match.group(1).split(",")], match.group(2))
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", body)
    ]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_header_has_four_group_buttons_with_disclosure_attributes() -> None:
    header = _header("/california/authors")

    for name in GROUPS:
        matches = [m for m in BUTTON.finditer(header) if m.group(2) == name]
        assert len(matches) == 1, f"expected one {name} button in the header"
        attrs = _attributes(matches[0].group(1))
        assert attrs["type"] == "button"
        assert attrs["aria-expanded"] == "false"
        panel_id = attrs["aria-controls"]
        assert panel_id == f"atlas-topnav-{name.lower()}"
        assert re.search(
            rf'<div class="atlas-topnav__panel" id="{re.escape(panel_id)}" hidden>', header
        ), f"{name} panel must exist and start hidden"


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
@pytest.mark.parametrize(
    ("path", "group", "label"),
    [
        ("/california/authors", "Explore", "Authors"),
        ("/california/evidence", "Data", "Evidence map"),
        ("/california/policy", "Context", "Policy"),
        ("/california/about", "Reference", "About"),
    ],
)
def test_top_nav_marks_the_current_link_and_its_group(path: str, group: str, label: str) -> None:
    header = _header(path)

    current = re.findall(
        r'<a class="atlas-topnav__link" href="[^"]+"( aria-current="page")?>([^<]+)</a>', header
    )
    assert [text for aria, text in current if aria] == [label]
    highlighted = [
        m.group(2)
        for m in BUTTON.finditer(header)
        if "atlas-topnav__button--current" in _attributes(m.group(1)).get("class", "")
    ]
    assert highlighted == [group]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_top_nav_script_handles_escape_focus_and_outside_clicks() -> None:
    header = _header("/california/authors")

    assert '"Escape"' in header
    assert "focusout" in header
    assert ".focus()" in header
    assert "panel.hidden" in header


def test_shell_css_hides_the_sidebar_above_52rem() -> None:
    desktop = _desktop_block(SHELL_CSS.read_text(encoding="utf-8"))

    hidden = [
        selectors
        for selectors, body in _rules(desktop)
        if "#observablehq-sidebar" in selectors and re.search(r"display:\s*none", body)
    ]
    assert hidden, "the desktop block must set display: none on #observablehq-sidebar"


def test_shell_css_resets_the_centre_inset_and_spans_the_header_above_52rem() -> None:
    desktop = _desktop_block(SHELL_CSS.read_text(encoding="utf-8"))
    rules = _rules(desktop)

    centre = [
        body
        for selectors, body in rules
        if any(selector.endswith("~ #observablehq-center") for selector in selectors)
    ]
    assert centre and all("padding-left: 0;" in body for body in centre)
    header = [body for selectors, body in rules if "#observablehq-header" in selectors]
    assert header and "left: 0;" in header[0] and "right: 0;" in header[0]


def test_mobile_block_keeps_the_drawer_and_search_toggle() -> None:
    css = SHELL_CSS.read_text(encoding="utf-8")

    assert "@media (max-width: 52rem) {" in css
    assert ".atlas-search-open .atlas-header__search" in css
    assert ".atlas-menu-button" in css


BUILD_OUT = os.environ.get("ATLAS_FW_OUT")


@pytest.mark.skipif(
    not BUILD_OUT or not (FRAMEWORK / BUILD_OUT / "california" / "authors.html").is_file(),
    reason="set ATLAS_FW_OUT to a folder built by `npm run build` in framework/",
)
def test_built_pages_carry_the_four_group_buttons() -> None:
    html = (FRAMEWORK / BUILD_OUT / "california" / "authors.html").read_text(encoding="utf-8")

    for name in GROUPS:
        pattern = (
            r'<button [^>]*aria-expanded="false"[^>]*'
            rf'aria-controls="atlas-topnav-{name.lower()}"[^>]*>{name}</button>'
        )
        assert re.search(pattern, html), f"built authors page is missing the {name} group button"
