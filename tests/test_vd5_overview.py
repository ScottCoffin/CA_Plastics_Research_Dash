"""Focused contracts for the VD-5 Overview presentation."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote_to_bytes

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "framework" / "src" / "index.md"
CSS = ROOT / "framework" / "src" / "components" / "overview.css"
MASK = ROOT / "framework" / "src" / "assets" / "design" / "ca_contours_mask.svg"


def test_overview_stylesheet_does_not_replace_the_global_style() -> None:
    page = INDEX.read_text(encoding="utf-8")
    _, frontmatter, body = page.split("---", maxsplit=2)

    assert not re.search(r"(?m)^style:\s*", frontmatter)
    assert '<link rel="stylesheet" href="./components/overview.css">' in body


def test_overview_hero_copy_and_single_heading() -> None:
    page = INDEX.read_text(encoding="utf-8")

    assert page.count("<h1 ") == 1
    assert (
        '<h1 class="atlas-hero__title" id="atlas-overview-title">CA Plastics Research Atlas</h1>'
        in page
    )
    # VD-18: the eyebrow separators are accent dots (style tile), not "·" text.
    assert (
        '<p class="atlas-hero__eyebrow"><span>California</span> <i></i> '
        "<span>32.5° to 42° N</span> <i></i> <span>Plastics research since 1950</span></p>"
    ) in page
    assert "California · 32.5°" not in page
    assert "Quick routes" not in page
    assert (
        "A transparent starting point for finding plastic-related research connected to California."
        in page
    )
    assert "Loading snapshot refresh time" in page
    assert "<time datetime=${snapshot.refreshIso}>${snapshot.refreshDisplay}</time>" in page


def test_hero_search_is_the_site_wide_search() -> None:
    # H25 (2026-11-16): the hero uses the same site-wide combobox as the header (VD-19).
    page = INDEX.read_text(encoding="utf-8")
    config = (ROOT / "framework" / "observablehq.config.js").read_text(encoding="utf-8")

    form = re.search(r'<form class="atlas-hero__search"(.*?)</form>', page, re.DOTALL)
    assert form
    assert "data-atlas-site-search" in form.group(1)
    assert 'action="./search" method="get"' in form.group(1)
    assert 'type="search" name="q"' in form.group(1)
    assert "data-atlas-expert-search" not in page
    assert "data-atlas-expert-search" not in config


def test_four_snapshot_tiles_three_tasks_and_eight_entries() -> None:
    page = INDEX.read_text(encoding="utf-8")
    expected_stats = {"Authors", "Works", "Institutions", "California institutions"}
    skeleton_labels = re.findall(r'<dt class="atlas-kpi__label">([^<]+)</dt>', page)
    task_cards = re.findall(r'<li>\s*<a href="([^"]+)">(.*?)</a>\s*</li>', page, re.DOTALL)
    entries = re.findall(r'<a class="atlas-entry" href="([^"]+)">', page)

    assert skeleton_labels == ["Authors", "Works", "Institutions", "California institutions"]
    assert page.count('class="atlas-kpi atlas-kpi--loading"') == 4
    assert "const statLabels = [...statIcons.keys()]" in page
    assert "snapshot.stats.map(({label, value, note}) => [label, {value, note}])" in page
    assert "noteNode.textContent = stat?.note" in page
    assert 'class="stat-note"' in page
    assert 'noteNode.className = "atlas-kpi__note stat-note"' in page
    assert len(task_cards) == 3
    assert {href for href, _ in task_cards} == {"./experts", "./funding", "./monitoring"}
    assert all('data-atlas-icon="' in card for _, card in task_cards)
    assert len(entries) == 8
    assert {
        "./experts",
        "./network",
        "./institutions",
        "./monitoring",
        "./funding",
        "./evidence",
        "./policy",
        "./resources",
    } == set(entries)
    assert expected_stats.issubset(set(skeleton_labels))


def test_overview_raw_html_blocks_start_at_column_zero() -> None:
    page = INDEX.read_text(encoding="utf-8")
    markup = page[
        page.index('<div class="atlas-overview">') : page.index(
            "\n```js", page.index('<div class="atlas-overview">')
        )
    ]

    starts = (
        '<section class="overview-stats"',
        '<section class="overview-section" id="start-here"',
        '<section class="overview-section" aria-labelledby="explore-atlas-title"',
    )
    for start in starts:
        assert re.search(rf"(?m)^{re.escape(start)}", page)
    assert "\n\n" not in markup


def test_entry_counts_use_only_existing_snapshot_metadata() -> None:
    page = INDEX.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    count_keys = re.findall(r'data-overview-count="([^"]+)"', page)
    count_groups = re.findall(
        r'<span class="atlas-entry__meta" data-overview-count-group hidden>(.*?)</span></span>',
        page,
    )

    # VD-13: the Funding, Monitoring, Network and Evidence cards read build_metadata counts.
    assert set(count_keys) == {
        "Authors",
        "Institutions",
        "California institutions",
        "Awards",
        "Monitoring samples",
        "Monitoring sources",
        "Network experts",
        "Network links",
        "Plastic-related works",
    }
    assert len(count_groups) == 6
    assert "counts.authors" not in page
    assert "counts.works" not in page
    assert "counts.institutions" not in page
    assert "counts.ca_institutions" not in page
    assert "[data-overview-count-group]" in page
    assert 'data-overview-suffix="plastic-related works"' in page
    assert ".atlas-entry__meta[hidden]" in css
    assert "400 experts" not in page and "1,241 links" not in page
    assert "samples ·" not in page and "awards ·" not in page


def test_coastline_uses_a_css_mask_without_javascript_motif_work() -> None:
    page = INDEX.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    js_blocks = re.findall(r"```js\s+(.*?)```", page, re.DOTALL)
    root = ET.parse(MASK).getroot()
    paths = root.findall("{http://www.w3.org/2000/svg}path")

    assert '<div class="atlas-hero__motif" aria-hidden="true"></div>' in page
    mask_uri = re.search(r'mask-image: url\("data:image/svg\+xml,([^"]+)"\)', css)
    webkit_mask_uri = re.search(r'-webkit-mask-image: url\("data:image/svg\+xml,([^"]+)"\)', css)
    assert mask_uri and webkit_mask_uri
    assert mask_uri.group(1) == webkit_mask_uri.group(1)
    assert unquote_to_bytes(mask_uri.group(1)) == MASK.read_bytes()
    assert "assets/design/" not in css
    assert all("atlas-hero__motif" not in block for block in js_blocks)
    assert root.get("fill") == "none"
    assert paths and all(path.get("stroke") == "white" for path in paths)
    assert MASK.stat().st_size <= 20 * 1024
    assert ".atlas-hero .visually-hidden" in css
    assert ".atlas-task-list > li > a:focus-visible" in css
    assert "outline: 3px solid var(--atlas-accent)" in css


def test_phone_layout_keeps_two_by_two_stats_and_one_column_cards() -> None:
    css = CSS.read_text(encoding="utf-8")
    mobile = css.split("@media (max-width: 42rem)", maxsplit=1)[1]

    assert ".overview-stats .atlas-kpis" in mobile
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in mobile
    assert ".atlas-task-list,\n  .atlas-entry-grid" in mobile
    assert "grid-template-columns: minmax(0, 1fr);" in mobile


def test_desktop_task_grid_uses_full_content_width() -> None:
    css = CSS.read_text(encoding="utf-8")
    task_grid = re.search(r"\.atlas-task-list\s*\{([^}]*)\}", css)

    assert task_grid
    assert "width: 100%;" in task_grid.group(1)
    assert "max-width: none;" in task_grid.group(1)


def test_vd18_hero_motif_and_start_here_links_match_the_style_tile() -> None:
    # VD-18: the coastline strokes use the tile colour at full mask alpha, and the Start-here
    # rows carry no underline in any state (style.css underlines links inside list items).
    css = CSS.read_text(encoding="utf-8")
    motif = re.search(r"\.atlas-hero__motif \{([^}]*)\}", css)

    assert motif
    assert "background-color: var(--atlas-brand-tint);" in motif.group(1)
    assert "opacity: 1;" in motif.group(1)
    assert "#observablehq-main .atlas-task-list a:hover" in css
    assert ".atlas-hero__eyebrow i" in css
    assert ".atlas-task__title {" in css and ".atlas-task__text," in css
