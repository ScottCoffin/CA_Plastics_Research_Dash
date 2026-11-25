"""GA-2b: /explore static contract checks (no browser, no build).

The page is the GA-1 prototype ported to Observable Framework (docs/GA_2_BUILD_SPEC.md section 3).
These tests keep the wiring honest in CI: the Framework front matter and the single .gx wrapper,
the module's data URL and exports, the stylesheet's .gx scoping and token-only colours, the honest
preview copy, and the GLOBAL_PAGES registration that scripts/check_at5.py uses.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
PAGE = SRC / "explore.md"
INDEX = SRC / "index.md"
MODULE = SRC / "components" / "explore.js"
STYLE = SRC / "components" / "explore.css"
TOKENS = SRC / "design" / "tokens.css"
HEX_COLOUR = re.compile(
    r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9A-Za-z_-])"
)


def _load_check_at5():
    spec = importlib.util.spec_from_file_location("check_at5", ROOT / "scripts" / "check_at5.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHECK_AT5 = _load_check_at5()


def _front_matter(text: str) -> list[str]:
    assert text.startswith("---\n"), "page needs Framework front matter"
    end = text.index("\n---\n", 4)
    return text[4:end].split("\n")


def _js_block(text: str) -> str:
    match = re.search(r"^```js\n(.*?)^```\s*$", text, re.M | re.S)
    assert match, "explore.md must end with a ```js block that mounts the page"
    return match.group(1)


def _strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _split_selectors(prelude: str) -> list[str]:
    """Split a selector list on commas that sit outside parentheses (:where(h1, h2) stays whole)."""
    parts: list[str] = []
    depth = 0
    current = ""
    for char in prelude:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    parts.append(current.strip())
    return [part for part in parts if part]


def _style_selectors(css: str) -> list[str]:
    """Selectors of style rules. At-rule preludes such as @media are skipped; their rules stay."""
    selectors: list[str] = []
    for prelude in re.findall(r"([^{}]+)\{", _strip_css_comments(css)):
        prelude = prelude.strip()
        if not prelude.startswith("@"):
            selectors.extend(_split_selectors(prelude))
    return selectors


def test_page_front_matter_is_the_landing_shell_with_an_explore_title():
    page = _front_matter(PAGE.read_text(encoding="utf-8"))
    landing = _front_matter(INDEX.read_text(encoding="utf-8"))
    flags = {"sidebar: false", "header: false", "footer: false", "toc: false", "pager: false"}
    assert flags <= set(page)
    assert "title: Explore the data · Plastiverse Live" in page
    # The head (font faces, favicon, theme colour) is copied from index.md; only the title differs.
    assert [line for line in page if not line.startswith("title:")] == [
        line for line in landing if not line.startswith("title:")
    ]


def test_page_links_the_stylesheet_and_mounts_the_module():
    text = PAGE.read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="./components/explore.css">' in text
    js = _js_block(text)
    assert 'import {mountExplore} from "./components/explore.js";' in js
    assert 'mountExplore(document.querySelector(".gx"))' in js
    assert not re.search(r"^(?:const|let|var|function|class)\s+view\b", js, re.M)


def test_static_markup_is_one_gx_block_safe_for_framework_markdown():
    text = PAGE.read_text(encoding="utf-8")
    markup = text[text.index('<div class="gx">') : text.index("```js")].strip("\n")
    assert text.count('<div class="gx">') == 1
    assert markup.endswith("</div>")
    # A blank line would end the HTML block, and ${...} is read as an expression in markdown.
    assert "\n\n" not in markup
    assert "${" not in text
    assert "<script" not in text.lower()


def test_page_links_stay_site_relative_and_point_at_the_built_pages():
    page = PAGE.read_text(encoding="utf-8")
    module = MODULE.read_text(encoding="utf-8")
    assert "https://plastiverse.live" not in page + module
    for target in (
        "./california/about#how-works-are-screened",
        "./california/about",
        "./feed.xml",
        "./assets/landing/logo_564.webp",
        "./ambassadors",
    ):
        assert target in page, target
    assert 'href: "./california/"' in module
    assert 'href: "./ambassadors"' in module


def test_module_fetches_explore_json_through_site_root_and_exports_mount():
    js = MODULE.read_text(encoding="utf-8")
    assert 'import {globalDataUrl} from "./atlas.js";' in js
    assert 'fetch(globalDataUrl("explore.json"), {cache: "no-cache"})' in js
    assert re.search(r"^export async function mountExplore\(root\)", js, re.M)
    assert "window.__explore = {go, setTab" in js
    assert "window.GA" not in js
    assert "norway_outline" not in js
    # Popovers and the drawer are appended inside root, so the .gx rules still apply to them.
    assert "document.body" not in js


def test_preview_copy_is_honest_about_what_arrives_later():
    js = MODULE.read_text(encoding="utf-8")
    assert "arrive with the global build" in js
    assert "Illustrative counts" in js


def test_stylesheet_is_scoped_under_gx_with_framework_resets():
    css = STYLE.read_text(encoding="utf-8")
    assert ":root" not in css
    assert "@font-face" not in css
    selectors = _style_selectors(css)
    assert selectors, "stylesheet has no rules"
    for selector in selectors:
        assert ".gx" in selector, selector
    for reset in (
        "body:has(.gx) #observablehq-center",
        "body:has(.gx) #observablehq-main",
        "body:has(.gx) #observablehq-footer",
        "html:has(.gx)",
        "#observablehq-main .gx :where(h1, h2, h3, p, ol, ul, table)",
    ):
        assert reset in css, reset


def test_stylesheet_has_no_hex_colour_outside_a_url():
    css = _strip_css_comments(STYLE.read_text(encoding="utf-8"))
    css = re.sub(r"url\([^)]*\)", "url()", css)
    assert HEX_COLOUR.findall(css) == []


def test_stylesheet_uses_only_defined_pv_tokens_and_keeps_local_custom_properties():
    css = STYLE.read_text(encoding="utf-8")
    defined = set(re.findall(r"(--pv-[a-z0-9-]+)\s*:", TOKENS.read_text(encoding="utf-8")))
    used = set(re.findall(r"var\((--pv-[a-z0-9-]+)", css))
    assert used, "stylesheet should use the --pv-* tokens"
    assert used - defined == set(), sorted(used - defined)
    assert re.search(r"\.gx\s*\{[^}]*--ga-bar:\s*52px", css)
    assert re.search(r"\.gx\s*\{[^}]*--ga-ease:", css)


def test_check_at5_registers_explore_as_a_global_page():
    assert "explore.md" in CHECK_AT5.GLOBAL_PAGES
    assert PAGE.is_file()


def test_js_block_is_separated_from_the_html_block() -> None:
    """A fence glued to closing HTML stays inside the HTML block and never runs (GA-2 lesson)."""

    text = (ROOT / "framework" / "src" / "explore.md").read_text(encoding="utf-8")
    assert "\n\n```js" in text.replace("\r\n", "\n")


def _media_bodies(css: str, query: str) -> list[str]:
    """Bodies of every @media block whose query matches exactly (brace-matched)."""
    bodies = []
    for match in re.finditer(r"@media\s*" + re.escape(query) + r"\s*\{", css):
        depth, index = 1, match.end()
        while depth and index < len(css):
            if css[index] == "{":
                depth += 1
            elif css[index] == "}":
                depth -= 1
            index += 1
        bodies.append(css[match.end() : index - 1])
    return bodies


def test_phone_menu_drawer_has_views_then_scope_then_atlases():
    page = PAGE.read_text(encoding="utf-8")
    js = MODULE.read_text(encoding="utf-8")
    assert ">Menu</span>" in page
    assert 'role="group" aria-labelledby="menu-views"' in page
    order = [
        page.index(">Views</p>"),
        page.index(">Scope</p>"),
        page.index('id="find-mob"'),
        page.index('id="vlad"'),
    ]
    assert order == sorted(order)
    assert 'data-view="${id}"' in js
    assert 'aria-current="page"' in js
    assert "chooseView(b.dataset.view)" in js
    assert "panel.focus({preventScroll: true})" in js
    assert js.index('row("world"') < js.index("Regional atlases")


def test_tab_row_is_hidden_on_phones_and_kept_on_desktop():
    css = _strip_css_comments(STYLE.read_text(encoding="utf-8"))
    phone = "".join(_media_bodies(css, "(max-width: 860px)"))
    assert re.search(r"\.gx \.tabs\s*\{\s*display:\s*none", phone)
    desktop = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css)
    assert ".gx .tabs" in desktop
    assert not re.search(r"\.gx \.tabs\s*\{[^}]*display:\s*none", desktop)


def test_narrow_world_map_is_two_stacked_panes_with_captions():
    js = MODULE.read_text(encoding="utf-8")
    css = STYLE.read_text(encoding="utf-8")
    assert '"Americas"' in js
    assert '"Europe, Africa, Asia and Oceania"' in js
    assert "78 * G.u" in js and "76 * G.u" in js and "108 * G.u" in js
    assert "PORTRAIT = 3 / 5" in js
    assert 'class="mcap"' in js and 'class="mp-box"' in js
    assert ".gx .mapcard.pair #map { display: none; }" in css
    assert ".gx .mapcard.portrait .mapbox { aspect-ratio: 3 / 5; }" in css
    assert "function targetBox(aspect = ASPECT)" in js
