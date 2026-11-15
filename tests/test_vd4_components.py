"""Contract checks for the VD-4 shared component reference."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "framework/src/components/shared/icons.js"
STYLES = ROOT / "framework/src/design/components.css"
STYLEGUIDE = ROOT / "framework/src/styleguide.md"

EXPECTED_ICONS = {
    "home",
    "person",
    "network",
    "building",
    "drop",
    "coins",
    "grid",
    "scale",
    "link",
    "info",
    "book",
    "search",
    "download",
    "filter",
    "x",
    "chevron",
    "arrow",
    "alert",
    "spark",
    "tools",
    "check",
    "calendar",
    "menu",
    "external",
}


def test_styleguide_is_unlisted_and_noindex() -> None:
    page = STYLEGUIDE.read_text(encoding="utf-8")
    config = (ROOT / "framework/observablehq.config.js").read_text(encoding="utf-8")
    llms = (ROOT / "site/llms.txt").read_text(encoding="utf-8")
    seo = (ROOT / "src/atlas/build/seo.py").read_text(encoding="utf-8")

    assert page.startswith("---\n")
    assert '<meta name="robots" content="noindex, nofollow">' in page
    assert "styleguide" not in config
    assert "/styleguide" not in llms
    assert '"/styleguide"' not in seo


def test_icon_sprite_contains_the_atlas_symbols_and_is_injected_once() -> None:
    source = ICONS.read_text(encoding="utf-8")
    definitions = dict(re.findall(r"^  (\w+): '(.*)',$", source, re.MULTILINE))
    names = set(definitions)
    tile = (ROOT / "docs/design/style_tile.html").read_text(encoding="utf-8")
    tile_symbols = dict(
        re.findall(r'<symbol id="i-(\w+)" viewBox="0 0 24 24">(.*?)</symbol>', tile)
    )

    assert names == EXPECTED_ICONS
    assert len(names) == 24
    assert set(tile_symbols) == EXPECTED_ICONS - {"external"}
    assert {name: definitions[name] for name in tile_symbols} == tile_symbols
    assert definitions["external"] == (
        '<path d="M13 5h6v6"/><path d="m19 5-8 8"/>'
        '<path d="M17 13v5a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h5"/>'
    )
    assert 'sprite.id = "atlas-icon-sprite"' in source
    assert 'getElementById("atlas-icon-sprite")' in source
    assert "if (existing) return existing;" in source
    assert "export function injectIconSprite" in source
    assert "export function icon(name, { label } = {})" in source
    assert "if (!Object.hasOwn(ICONS, name))" in source
    assert 'svg.setAttribute("aria-hidden", "true")' in source
    assert 'svg.setAttribute("role", "img")' in source
    assert 'svg.setAttribute("aria-label", accessibleLabel)' in source
    assert "symbol.innerHTML = markup" in source


def test_component_styles_cover_each_spec_family_and_preserve_accessibility() -> None:
    css = STYLES.read_text(encoding="utf-8")
    guide = STYLEGUIDE.read_text(encoding="utf-8")
    classes = {
        "atlas-page-head",
        "atlas-page-head__eyebrow",
        "atlas-page-head__lead",
        "atlas-page-head__meta",
        "motif",
        "atlas-demo-row",
        "atlas-demo-cards",
        "atlas-pill",
        "atlas-btn",
        "atlas-btn--primary",
        "atlas-btn--secondary",
        "atlas-btn--ghost",
        "atlas-btn--icon",
        "atlas-field",
        "atlas-field--check",
        "atlas-label",
        "atlas-hint",
        "atlas-input",
        "atlas-select",
        "atlas-search",
        "atlas-check",
        "atlas-filters",
        "atlas-filters__head",
        "atlas-filters__body",
        "atlas-filters__grid",
        "atlas-filters__more",
        "atlas-active-filters",
        "atlas-filter-chip",
        "atlas-result-line",
        "atlas-callout",
        "atlas-callout--info",
        "atlas-callout--caution",
        "atlas-callout--new",
        "atlas-callout--dev",
        "atlas-badge",
        "atlas-badge--good",
        "atlas-badge--accent",
        "atlas-badge--muted",
        "atlas-kpis",
        "atlas-kpi",
        "atlas-kpi__label",
        "atlas-kpi__value",
        "atlas-kpi__note",
        "atlas-kpi--loading",
        "atlas-card",
        "atlas-entry",
        "atlas-task",
        "atlas-table-wrap",
        "atlas-table",
        "r",
        "atlas-chart",
        "atlas-chart__head",
        "atlas-segmented",
        "atlas-disclosure",
        "atlas-skeleton",
    }

    for class_name in classes:
        assert class_name in css
        assert class_name in guide
    assert "topic-chip" in guide
    assert not re.search(r"^\.topic-chip\b", css, re.MULTILINE)
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "overflow-x: auto" in css
    assert ".atlas-btn {" in css and "min-height: 2.5rem" in css
    assert ".atlas-input," in css and "min-height: 2.5rem" in css
    assert ".atlas-check {" in css and "width: 1.5rem" in css and "height: 1.5rem" in css
    assert ".atlas-filter-chip button {" in css and "height: 1.5rem" in css
    assert '<p class="atlas-kpi__note">' not in guide
    assert 'class="atlas-active-filters" role="group" aria-label=' in guide
    assert 'class="atlas-card" aria-label=' not in guide
    assert "https://" not in css
