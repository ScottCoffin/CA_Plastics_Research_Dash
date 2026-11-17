"""Contract checks for the VD-4 shared component reference."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ICONS = ROOT / "framework/src/components/shared/icons.js"
STYLES = ROOT / "framework/src/design/components.css"
STYLEGUIDE = ROOT / "framework/src/styleguide.md"
FW = ROOT / "framework"
STYLEGUIDE_SAMPLE = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="robots" content="noindex, nofollow">'
    "<title>Shared components | CA Plastics Research Atlas</title>"
    "</head><body><main>Style guide</main></body></html>"
)

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


def _postbuild(expression: str) -> str:
    module = (FW / "scripts" / "postbuild.mjs").resolve().as_uri()
    script = (
        f"const m = await import({json.dumps(module)}); process.stdout.write(String({expression}));"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=FW,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


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


def test_postbuild_restores_global_head_for_styleguide_once() -> None:
    once = _postbuild(f"m.fixHtml({json.dumps(STYLEGUIDE_SAMPLE)}, 'styleguide')")
    twice = _postbuild(f"m.fixHtml({json.dumps(once)}, 'styleguide')")

    assert once == twice
    assert '<meta name="robots" content="noindex, nofollow">' in once
    assert once.count('font-family: "Archivo"') == 1
    assert once.count('<link rel="icon" href="data:image/svg+xml') == 1
    assert (
        len(
            re.findall(
                r'<link\b(?=[^>]*\brel="preload")'
                r'(?=[^>]*\bhref="\.\/assets\/fonts\/Archivo-Variable-latin\.woff2")[^>]*>',
                once,
            )
        )
        == 1
    )
    assert once.count('<meta name="description" content="') == 1
    title = re.search(r"<title>(.*?)</title>", once)
    assert title is not None
    assert title.group(1) == "Shared components | CA Plastics Research Atlas"
    assert title.group(1).count("CA Plastics Research Atlas") == 1


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
    heading_anchor = re.search(r"\.observablehq-header-anchor\s*\{([^}]*)\}", css)
    assert heading_anchor is not None
    assert "display: inline-flex" in heading_anchor.group(1)
    assert "min-height: 1.5rem" in heading_anchor.group(1)
    assert "align-items: center" in heading_anchor.group(1)
    assert '<p class="atlas-kpi__note">' not in guide
    assert 'class="atlas-active-filters" role="group" aria-label=' in guide
    assert 'class="atlas-card" aria-label=' not in guide
    assert "https://" not in css
