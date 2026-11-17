"""Focused contracts for the VD-5 Overview presentation (rebuilt as the VD-25b Plane Poster)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "framework" / "src" / "index.md"
CSS = ROOT / "framework" / "src" / "components" / "overview.css"

# Live counts: the About stats (authors, California institutions) and metadata.counts (the rest).
COUNT_KEYS = {
    "authors",
    "california_institutions",
    "type_summary",  # owner 2026-11-17: living output mix from metadata.flow.by_type
    "awards",
    "monitoring_samples",
    "monitoring_sources",
    "network_experts",
    "network_links",
    "plastic_works",
}


def _markup(page: str) -> str:
    start = page.index('<div class="atlas-overview">')
    return page[start : page.index("\n```js", start)]


def _block(css: str, selector: str) -> str:
    match = re.search(rf"(?m)^{re.escape(selector)} \{{([^}}]*)\}}", css)
    assert match, f"missing rule {selector}"
    return match.group(1)


def test_overview_stylesheet_does_not_replace_the_global_style() -> None:
    page = INDEX.read_text(encoding="utf-8")
    _, frontmatter, body = page.split("---", maxsplit=2)

    assert not re.search(r"(?m)^style:\s*", frontmatter)
    assert '<link rel="stylesheet" href="./components/overview.css">' in body


def test_overview_hero_copy_and_single_heading() -> None:
    page = INDEX.read_text(encoding="utf-8")

    assert page.count("<h1 ") == 1
    assert (
        '<h1 class="overview-title" id="overview-title">'
        "California plastics research, in four parts.</h1>"
    ) in page
    assert (
        "Who studies plastics in California, what is monitored, what is funded, and what has been "
        "published. Rebuilt from open sources every day."
    ) in page
    # The old eyebrow line, hero motif and Quick routes block are gone.
    assert "Plastics research since 1950" not in page
    assert "California · 32.5°" not in page
    assert "Quick routes" not in page
    assert "atlas-hero" not in page
    assert "Loading snapshot refresh time" in page


def test_refresh_time_line_sits_in_the_static_notes() -> None:
    page = INDEX.read_text(encoding="utf-8")

    assert "<time datetime=${snapshot.refreshIso}>${snapshot.refreshDisplay}</time>" in page
    notes = page.index("<h3>Every number has a source</h3>")
    refresh = page.index('<p class="overview-refresh" id="overview-refresh" aria-live="polite">')
    assert notes < refresh < page.index("</section>", refresh)
    assert page.count('id="overview-refresh"') == 1


def test_hero_search_is_the_site_wide_search() -> None:
    # H25 (2026-11-16): the hero uses the same site-wide combobox as the header (VD-19).
    page = INDEX.read_text(encoding="utf-8")
    config = (ROOT / "framework" / "observablehq.config.js").read_text(encoding="utf-8")

    form = re.search(r'<form class="overview-search"(.*?)</form>', page, re.DOTALL)
    assert form
    assert "data-atlas-site-search" in form.group(1)
    assert 'action="./search" method="get"' in form.group(1)
    assert 'type="search" name="q"' in form.group(1)
    assert '<label class="visually-hidden" for="overview-q">' in form.group(1)
    assert page.count("data-atlas-site-search") == 1
    assert "data-atlas-expert-search" not in page
    assert "data-atlas-expert-search" not in config


def test_counts_are_live_placeholders_not_typed_numbers() -> None:
    page = INDEX.read_text(encoding="utf-8")
    markup = _markup(page)

    assert set(re.findall(r'data-count="([^"]+)"', markup)) == COUNT_KEYS
    # The snapshot numbers from the approved reference must not be typed into the page. SVG path
    # data is skipped: its coordinates include numbers such as -211.
    prose = re.sub(r"<svg.*?</svg>", "", markup, flags=re.S)
    for typed in ("2,635", "1,579", "1,245", "503", "298", "211"):
        assert not re.search(rf"\b{re.escape(typed)}\b", prose), typed
    assert "Unavailable" not in markup
    assert "counts.authors" not in page
    assert "counts.works" not in page
    assert "counts.institutions" not in page
    assert "counts.ca_institutions" not in page


def test_counts_load_through_the_atlas_helpers_and_hide_when_missing() -> None:
    page = INDEX.read_text(encoding="utf-8")
    js = " ".join(re.findall(r"```js\s+(.*?)```", page, re.DOTALL))

    assert 'import {loadJson, aboutViewModel, formatCount} from "./components/atlas.js";' in js
    assert 'await loadJson("build_metadata.json")' in js
    assert "aboutViewModel(metadata, null)" in js
    assert "metadata?.counts" in js
    assert "node.dataset.count" in js
    # A group with any missing value is hidden; nothing reads "Unavailable" in the page.
    assert 'querySelectorAll("[data-count-group]")' in js
    assert "group.hidden = !ready" in js
    assert 'text && text !== "Unavailable"' in js
    # Definitions for the two About counts travel with their values.
    assert 'querySelectorAll("[data-stat-note]")' in js
    assert 'data-stat-note="Authors"' in page
    assert 'data-stat-note="California institutions"' in page


def test_counts_reserve_their_height_before_the_value_arrives() -> None:
    css = CSS.read_text(encoding="utf-8")

    assert "min-height: 1.4em;" in _block(css, ".overview-door__count")
    assert "min-height: 1em;" in _block(css, ".overview-facts b")
    assert "min-height: 1.5em;" in _block(
        css, "#observablehq-main .overview-notes .overview-refresh"
    )
    assert "aspect-ratio: 1000 / 260;" in _block(css, ".overview-chart__frame")
    assert "min-width: 760px;" in _block(css, ".overview-chart__frame")


def test_no_hex_literals_in_the_overview_page_or_stylesheet() -> None:
    page = INDEX.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", page)
    assert "fonts.googleapis" not in page and "fonts.googleapis" not in css


def test_raw_html_blocks_start_at_column_zero_and_have_no_blank_lines() -> None:
    page = INDEX.read_text(encoding="utf-8")
    markup = _markup(page)

    # Blank lines end a raw HTML block in Markdown, so the whole composition stays one block.
    assert "\n\n" not in markup
    for start in (
        '<section class="overview-hero" aria-labelledby="overview-title">',
        '<section class="overview-band" id="people"',
        '<section class="overview-clock" aria-labelledby="overview-clock-title">',
    ):
        assert re.search(rf"(?m)^{re.escape(start)}", page), start


def test_phone_and_tablet_layout_stack_the_hero_and_bands() -> None:
    css = CSS.read_text(encoding="utf-8")
    tablet = css.split("@media (max-width: 64rem)", maxsplit=1)[1].split("@media", maxsplit=1)[0]
    phone = css.split("@media (max-width: 42rem)", maxsplit=1)[1].split("@media", maxsplit=1)[0]

    assert ".overview-hero__grid," in tablet and "grid-template-columns: minmax(0, 1fr);" in tablet
    assert "order: -1;" in phone
    assert "display: none;" in phone
