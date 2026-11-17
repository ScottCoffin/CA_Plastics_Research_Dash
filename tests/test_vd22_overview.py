"""Focused contracts for the VD-22 Overview rework (owner H25 feedback, 2026-11-16)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "framework" / "src" / "index.md"
CSS = ROOT / "framework" / "src" / "components" / "overview.css"
ICONS = ROOT / "framework" / "src" / "components" / "shared" / "icons.js"


def _block(css: str, selector: str) -> str:
    match = re.search(rf"(?m)^{re.escape(selector)} \{{([^}}]*)\}}", css)
    assert match, f"missing rule {selector}"
    return match.group(1)


def test_eyebrow_line_and_its_css_are_removed() -> None:
    page = INDEX.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    assert "atlas-hero__eyebrow" not in page
    assert "atlas-hero__eyebrow" not in css
    assert "32.5° to 42° N" not in page
    assert "Plastics research since 1950" not in page


def test_stats_have_no_negative_margin_and_keep_reserved_kpi_height() -> None:
    css = CSS.read_text(encoding="utf-8")

    # The only negative margin left is the visually-hidden utility (margin: -1px).
    assert "margin: -2rem" not in css
    assert "margin-top: -1.25rem" not in css
    assert ".overview-stats .atlas-kpi {" in css
    assert "min-height: 8rem;" in _block(css, ".overview-stats .atlas-kpi")


def test_how_it_works_follows_explore_with_h2_and_five_items() -> None:
    page = INDEX.read_text(encoding="utf-8")
    heading = '<h2 id="how-it-works">How it works</h2>'

    assert page.count(heading) == 1
    assert page.index(heading) > page.index('<h2 id="explore-atlas-title">')
    assert 'aria-labelledby="how-it-works"' in page
    steps = re.findall(r'<li class="overview-step[ "]', page)
    assert len(steps) == 5
    assert page.count("overview-step--note") == 1


def test_how_it_works_keeps_the_owner_facts_in_utc_and_links_methods() -> None:
    page = INDEX.read_text(encoding="utf-8")

    for fact in (
        "GitHub Actions, daily at 10:17 UTC",
        "Daily at 10:15 UTC and on every change",
        "Mondays at 10:31 UTC",
        "Daily at 11:47 UTC, plus a monthly keepalive",
        "CEDEN",
        "OpenAlex",
        "Parquet",
        '<a href="./about">Read the methods</a>',
    ):
        assert fact in page, fact


def test_how_it_works_icons_exist_in_the_shared_icon_map() -> None:
    page = INDEX.read_text(encoding="utf-8")
    icons_src = ICONS.read_text(encoding="utf-8")
    used = set(re.findall(r'data-atlas-icon="([a-z]+)"', page))

    assert {"download", "tools", "search", "alert", "book"} <= used
    for name in used:
        assert re.search(rf"(?m)^\s+{name}:", icons_src), name


def test_start_here_cards_have_no_subtitles_and_short_titles() -> None:
    page = INDEX.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    titles = re.findall(r'<span class="atlas-task__title">([^<]+)</span>', page)

    assert "atlas-task__text" not in page
    assert "atlas-task__text" not in css
    assert titles == [
        "Find a California researcher",
        "See plastics research funding",
        "Check monitoring data",
    ]


def test_start_here_cards_use_three_distinct_token_families() -> None:
    page = INDEX.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    washes = set()
    for modifier in ("experts", "funding", "monitoring"):
        assert f'class="atlas-task atlas-task--{modifier}"' in page
        wash = re.search(rf"\.atlas-task--{modifier} \{{([^}}]*)\}}", css)
        assert wash, modifier
        token = re.search(r"--task-wash: (var\(--atlas-[a-z-]+\));", wash.group(1))
        assert token, modifier
        washes.add(token.group(1))
    assert len(washes) == 3


def test_explore_entry_text_is_at_most_six_words() -> None:
    page = INDEX.read_text(encoding="utf-8")
    texts = re.findall(r'<span class="atlas-entry__text">([^<]+)</span>', page)

    assert len(texts) == 8
    for text in texts:
        assert len(text.split()) <= 6, text


def test_home_sections_are_full_width_bands_that_alternate_tokens() -> None:
    page = INDEX.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    bands = re.findall(r'<section class="[^"]*overview-band--(sunken|surface)"', page)

    assert bands == ["sunken", "surface", "sunken", "surface"]
    assert "box-shadow: 0 0 0 100vmax var(--atlas-sunken);" in css
    assert "box-shadow: 0 0 0 100vmax var(--atlas-surface);" in css


def test_full_bleed_uses_no_viewport_width_margin() -> None:
    css = CSS.read_text(encoding="utf-8")
    hero = _block(css, ".atlas-hero")

    assert "100vw" not in css
    assert "box-shadow: 0 0 0 100vmax var(--atlas-brand-strong);" in hero
    assert "clip-path: inset(0 -100vmax);" in hero
    assert "border-radius" not in hero
    assert "clip-path: inset(0 -100vmax);" in _block(css, ".overview-band")


def test_hero_lead_and_content_span_the_column() -> None:
    css = CSS.read_text(encoding="utf-8")

    assert "46ch" not in css
    # The 42rem cap was on the content wrapper; the media query also reads "max-width: 42rem".
    assert "max-width" not in _block(css, ".atlas-hero__content")
    assert "max-width: none;" in _block(css, "#observablehq-main .atlas-hero__lead")


def test_hero_has_no_tooltip() -> None:
    page = INDEX.read_text(encoding="utf-8")
    hero = page[page.index('<section class="atlas-hero"') : page.index("</section>")]

    assert " title=" not in hero


def test_section_headings_on_the_home_page_are_larger() -> None:
    css = CSS.read_text(encoding="utf-8")
    heading = _block(css, ".atlas-overview h2")

    assert "font-size: clamp(1.75rem, 1.4rem + 1.2vw, 2.25rem);" in heading


def test_methods_link_has_a_24px_hit_area() -> None:
    css = CSS.read_text(encoding="utf-8")

    assert "min-height: 1.5rem;" in _block(css, ".overview-step__text a")


def test_overview_stylesheet_has_no_hex_literals() -> None:
    css = CSS.read_text(encoding="utf-8")

    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
