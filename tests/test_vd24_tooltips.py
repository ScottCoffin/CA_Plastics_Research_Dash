"""VD-24 source contracts: heading scale, full-bleed page-head bands, shared tooltips, help buttons.

Visual checks (overflow at 390, 1024 and 1440 px, tooltip placement) ran in a browser; these tests
pin the markup, CSS and script hooks those checks depend on.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
TOKENS = SRC / "design" / "tokens.css"
COMPONENTS = SRC / "design" / "components.css"
TOOLTIP_JS = SRC / "components" / "shared" / "tooltip.js"
EVIDENCE_CSS = SRC / "components" / "evidence.css"
NETWORK_CSS = SRC / "components" / "network.css"
MONITORING_CSS = SRC / "components" / "monitoring.css"
INDEX = SRC / "index.md"
HELP_PAGES = ("evidence.md", "network.md", "institutions.md", "monitoring.md")
# funding.md only imports the module: its help button is built by components/funding_viz.js.
IMPORT_PAGES = HELP_PAGES + ("funding.md",)
HEAD_PATTERN = r'<header class="atlas-page-head[^"]*">(.*?)</header>'
HELP_TEXT = re.compile(r'aria-label="About ([^":]+): ([^"]+)" data-atlas-tip="([^"]+)"')


def _block(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css, flags=re.DOTALL)
    assert match is not None, f"missing CSS rule for {selector}"
    return match.group(1)


def _media(css: str, query: str) -> str:
    start = css.index(query)
    return css[start : css.index("\n}", start)]


def test_heading_scale_raises_h1_about_20_and_h2_h3_about_15_percent() -> None:
    tokens = TOKENS.read_text(encoding="utf-8")
    assert "--atlas-type-page-size: clamp(2.16rem, 1.68rem + 1.68vw, 2.88rem);" in tokens
    assert "--atlas-type-section-size: 1.58rem;" in tokens
    assert "--atlas-type-subsection-size: 1.3rem;" in tokens
    # Line heights stay tight.
    assert re.search(r"h1 \{[^}]*line-height: 1\.05;", tokens, flags=re.DOTALL)


def test_page_head_is_a_full_width_band_with_the_vd22_bleed() -> None:
    css = COMPONENTS.read_text(encoding="utf-8")
    base = _block(css, ".atlas-page-head")
    assert "width: 100%;" in base and "box-sizing: border-box;" in base
    assert "max-width" not in base

    band = _block(css, ".atlas-page-head:not(.drawer-header)")
    assert "background: var(--atlas-head-band);" in band
    assert "box-shadow: 0 0 0 100vmax var(--atlas-head-band);" in band
    assert "clip-path: inset(0 -100vmax);" in band
    assert "100vw" not in band
    assert "--atlas-head-band: var(--atlas-brand-tint);" in TOKENS.read_text(encoding="utf-8")


def test_evidence_title_and_lead_sit_inside_the_page_head() -> None:
    page = (SRC / "evidence.md").read_text(encoding="utf-8")
    header = re.search(r'<header class="atlas-page-head">(.*?)</header>', page, flags=re.DOTALL)
    assert header is not None
    assert '<h1 id="evidence-map">Evidence map</h1>' in header.group(1)
    assert 'class="atlas-page-head__lead"' in header.group(1)
    assert "# Evidence map" not in page
    assert "header.atlas-page-head" not in EVIDENCE_CSS.read_text(encoding="utf-8")


def test_no_page_in_framework_splits_its_head_from_the_title() -> None:
    for md in sorted(SRC.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        for match in re.finditer(HEAD_PATTERN, text, re.S):
            after = text[match.end() : match.end() + 400]
            assert not re.match(r"\s*(#\s|<h1|<p class=\"atlas-page-head__lead\")", after), md.name
            if "drawer-header" not in match.group(0):
                assert "<h1" in match.group(1), md.name
                assert "atlas-page-head__lead" in match.group(1), md.name


def test_shared_tooltip_rules_show_on_hover_and_focus_after_200_ms() -> None:
    css = COMPONENTS.read_text(encoding="utf-8")
    after = _block(css, "[data-atlas-tip]::after")
    assert "content: attr(data-atlas-tip);" in after
    assert "max-width: min(18rem" in after
    assert "display: none;" in after
    assert "white-space: normal;" in after
    hover = _media(css, "@media (hover: hover)")
    assert "[data-atlas-tip]:hover::after" in hover and "display: block;" in hover
    assert re.search(r"animation: atlas-tip-in 120ms ease-out 200ms both;", css)
    for variant in ("below", "left", "right"):
        assert f'[data-atlas-tip-pos="{variant}"]::after' in css
    assert '[data-atlas-tip-align="end"]::after' in css
    assert "[data-atlas-tip].atlas-tip--dismissed::after" in css
    reduced = _media(css, "@media (prefers-reduced-motion: reduce)")
    assert "animation-duration: 0s;" in reduced and "data-atlas-tip" in reduced


def test_tooltip_is_defined_once_and_monitoring_keeps_only_its_layout() -> None:
    css = MONITORING_CSS.read_text(encoding="utf-8")
    assert "[data-atlas-tip]::after" not in css
    assert "attr(data-atlas-tip)" not in css


def test_tooltip_module_exports_init_and_help_markup() -> None:
    js = TOOLTIP_JS.read_text(encoding="utf-8")
    assert "export function initTooltips(root = document)" in js
    assert "export function helpButtonHtml(" in js
    assert '"Escape"' in js and "atlas-tip--dismissed" in js
    assert "aria-expanded" in js


def test_help_buttons_have_matching_label_and_tip_and_pages_import_the_module() -> None:
    for name in IMPORT_PAGES:
        page = (SRC / name).read_text(encoding="utf-8")
        assert "./components/shared/tooltip.js" in page, name
        assert "initTooltips(document);" in page, name
    assert "helpButtonHtml(" in (SRC / "components" / "funding_viz.js").read_text(encoding="utf-8")
    for name in HELP_PAGES:
        page = (SRC / name).read_text(encoding="utf-8")
        matches = list(HELP_TEXT.finditer(page))
        assert matches, f"{name} has no help button"
        for match in matches:
            assert match.group(2) == match.group(3), name
            assert 'class="atlas-help"' in page[match.start() - 80 : match.start()], name
        assert 'aria-expanded="false"' in page, name


def test_help_buttons_are_not_on_the_home_hero() -> None:
    page = INDEX.read_text(encoding="utf-8")
    assert "atlas-help" not in page
    assert "data-atlas-tip" not in page


def test_network_legend_wraps_long_names_inside_their_pills() -> None:
    css = NETWORK_CSS.read_text(encoding="utf-8")
    pill = _block(css, ".net-legend .net-legend-item")
    assert "white-space: normal;" in pill and "max-width: 100%;" in pill
    assert "max-width: 100%;" in _block(css, ".net-legend > li")
