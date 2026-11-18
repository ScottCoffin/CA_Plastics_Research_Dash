"""Focused contracts for the VD-22 full-bleed technique on the Overview (kept through VD-25b)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "framework" / "src" / "california" / "index.md"
CSS = ROOT / "framework" / "src" / "components" / "overview.css"


def _rules(css: str, selector: str) -> str:
    """Every top-level rule body whose selector list contains `selector`, joined."""
    bodies = [
        match.group(2)
        for match in re.finditer(r"(?m)^([^{}@/]+?)\s*\{([^{}]*)\}", css)
        if selector in [part.strip() for part in match.group(1).split(",")]
    ]
    assert bodies, f"missing rule {selector}"
    return "\n".join(bodies)


def test_eyebrow_line_and_its_css_are_removed() -> None:
    page = INDEX.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    assert "atlas-hero__eyebrow" not in page
    assert "atlas-hero__eyebrow" not in css
    assert "Plastics research since 1950" not in page
    assert "California · 32.5°" not in page
    # The 32.5° to 42° N line that remains is the reference figure caption.
    assert page.count("32.5° to 42° N") == 1


def test_full_bleed_sections_paint_outward_and_clip_to_their_own_height() -> None:
    css = CSS.read_text(encoding="utf-8")

    for selector, token in (
        (".overview-hero", "--atlas-page"),
        (".overview-band", "--atlas-page"),
        (".overview-clock", "--atlas-ink"),
    ):
        body = _rules(css, selector)
        assert f"box-shadow: 0 0 0 100vmax var({token});" in body, selector
        assert "clip-path: inset(0 -100vmax);" in _rules(css, selector), selector


def test_full_bleed_uses_no_viewport_width_margin() -> None:
    css = CSS.read_text(encoding="utf-8")

    assert "100vw" not in css
    assert not re.search(r"margin-(left|right): calc\(50%", css)
    # The band rule that bleeds is a pseudo-element with paint only: no negative offsets that
    # would add scrollable width.
    assert not re.search(r"(?:left|right|margin-left|margin-right): -", css)
    assert "box-shadow: 0 0 0 100vmax var(--atlas-line);" in _rules(css, ".overview-band::before")
    assert "clip-path: inset(0 -100vmax);" in _rules(css, ".overview-band::before")


def test_hero_has_no_tooltip() -> None:
    page = INDEX.read_text(encoding="utf-8")
    hero = page[page.index('<section class="overview-hero"') : page.index("</section>")]

    assert " title=" not in hero
    assert "atlas-help" not in hero
    assert "data-atlas-tip" not in hero


def test_lead_keeps_the_reference_measure_against_the_page_paragraph_cap() -> None:
    css = CSS.read_text(encoding="utf-8")

    # style.css caps every paragraph in #observablehq-main at 70ch with an ID selector, so the
    # lead needs the same ID to hold its own measure.
    assert "max-width: 46ch;" in _rules(css, "#observablehq-main .overview-lead")


def test_band_titles_are_larger_than_the_shared_h2() -> None:
    css = CSS.read_text(encoding="utf-8")

    assert "font-size: clamp(1.9rem, 1.4rem + 1.8vw, 2.75rem);" in _rules(
        css, "#observablehq-main .overview-band__title"
    )


def test_notes_links_have_a_24px_hit_area() -> None:
    css = CSS.read_text(encoding="utf-8")
    page = INDEX.read_text(encoding="utf-8")

    assert "min-height: 1.5rem;" in _rules(css, "#observablehq-main .overview-notes a")
    assert '<a href="./about">Read the methods</a>' in page


def test_overview_stylesheet_has_no_hex_literals() -> None:
    css = CSS.read_text(encoding="utf-8")

    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
