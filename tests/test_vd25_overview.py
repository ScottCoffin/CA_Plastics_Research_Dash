"""VD-25b: the Overview is the approved Plane Poster (ADR-VD25-PLANE-POSTER-2026-11-16).

The composition is ported from docs/design/intro_option_plane.html. These tests pin the parts that
must match it (the California figure, the door rows, the copy, the bands and their links) and the
parts that differ by design (live counts, token-only colours, no retired Overview sections).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "framework" / "src" / "index.md"
CSS = ROOT / "framework" / "src" / "components" / "overview.css"
TOKENS = ROOT / "framework" / "src" / "design" / "tokens.css"
REFERENCE = ROOT / "docs" / "design" / "intro_option_plane.html"

# Plane, route and door title, in the reference order: researchers, monitoring, funding, evidence.
DOORS = [
    ("people", "./experts", "Find a researcher"),
    ("water", "./monitoring", "Check monitoring data"),
    ("money", "./funding", "See funding"),
    ("evidence", "./evidence", "Explore the evidence"),
]
BANDS = ["people", "water", "money", "evidence"]
BAND_LINKS = {
    "people": [
        ("Experts", "./experts"),
        ("Collaboration network", "./network"),
        ("Institutions", "./institutions"),
    ],
    "water": [("Monitoring map", "./monitoring")],
    "money": [("Funding", "./funding")],
    "evidence": [
        ("Evidence map", "./evidence"),
        ("Policy", "./policy"),
        ("Related resources", "./resources"),
    ],
}
# Reference copy kept verbatim (the reference's own paragraphs and facts).
REFERENCE_COPY = [
    "Who studies plastics in California, what is monitored, what is funded, and what has been "
    "published. Rebuilt from open sources every day.",
    "Search California-affiliated authors by topic, institution and output, and see who publishes "
    "with whom. Profiles are built from OpenAlex and ROR records.",
    "Browse public plastic samples from California waters on a map, with each source's licence and "
    "citation. Samples describe individual sites; they do not establish statewide coverage.",
    "Browse plastic-related grants and awards connected to California, and open funding calls, "
    "drawn from public grant databases.",
    "Filter published plastic-related works by topic, year and sector, see trends and a topic "
    "heatmap, and follow the DTSC microplastics regulatory timeline. Topic tags come from keyword "
    "rules and are provisional.",
    "Scheduled GitHub Actions jobs run in a two-hour window each morning, UTC (about 2 to 4 a.m. "
    "in California in winter). Times below are drawn to scale.",
    "No server or database. Data ship as versioned JSON and Parquet files beside the pages.",
    "Code, queries and decisions are public on GitHub.",
    "sample observations",
    "verified sources",
    "plastic-related awards",
    "plastic-related works",
    "experts in the network",
]
SCHEDULE_JOBS = [
    "Keepalive",
    "Build and deploy",
    "Daily ingest from OpenAlex",
    "Source watch",
    "Watchdog",
]


def _markup(page: str) -> str:
    start = page.index('<div class="atlas-overview">')
    return page[start : page.index("\n```js", start)]


def _js(page: str) -> str:
    return " ".join(re.findall(r"```js\s+(.*?)```", page, re.DOTALL))


def _section(page: str, section_id: str) -> str:
    match = re.search(
        rf'<section class="overview-band" id="{section_id}"(.*?)</section>', page, re.S
    )
    assert match, section_id
    return match.group(1)


def _reference_polygons(text: str) -> list[tuple[str, str]]:
    return re.findall(r'data-plane="(\w+)" points="([^"]+)"', text)


def test_hero_doors_link_to_the_four_task_pages_in_order() -> None:
    markup = _markup(INDEX.read_text(encoding="utf-8"))
    doors = re.findall(
        r'<a class="overview-door" data-plane="(\w+)" href="([^"]+)"[^>]*>'
        r'<span class="overview-door__swatch" aria-hidden="true"></span>'
        r'<strong class="overview-door__task">([^<]+)</strong>',
        markup,
    )

    assert [(plane, href, title) for plane, href, title in doors] == DOORS
    assert all(f"--c: var(--atlas-task-{plane})" in markup for plane, _, _ in DOORS)


def test_figure_is_the_reference_california_composition() -> None:
    page = INDEX.read_text(encoding="utf-8")
    reference = REFERENCE.read_text(encoding="utf-8")
    ref_path = re.search(r'<clipPath id="ca"><path d="([^"]+)"/></clipPath>', reference)
    markup = _markup(page)

    assert ref_path, "reference clipPath missing"
    assert f'<clipPath id="overview-ca"><path d="{ref_path.group(1)}"/></clipPath>' in markup
    assert (
        '<svg viewBox="-470 -575 1010 1090" role="group" aria-labelledby="overview-fig-title">'
        in markup
    )
    assert _reference_polygons(markup) == _reference_polygons(reference)
    assert len(_reference_polygons(markup)) == 4
    assert (
        '<path d="M-330,70 A62,62 0 0 0 -206,70 Z" style="fill: var(--atlas-vermilion)"' in markup
    )
    # VD-30: each plane is its own group with the same clip, so the clip moves with the plane.
    assert markup.count('<g clip-path="url(#overview-ca)">') == 4
    for plane, _, _ in DOORS:
        assert (
            f'<g class="overview-piece" data-plane="{plane}"><g clip-path="url(#overview-ca)">'
            in markup
        ), plane


def test_plane_links_are_hidden_from_assistive_tech_and_the_tab_order() -> None:
    markup = _markup(INDEX.read_text(encoding="utf-8"))
    planes = re.findall(
        r'<a href="([^"]+)" tabindex="-1" aria-hidden="true"><polygon class="overview-plane" '
        r'data-plane="(\w+)"',
        markup,
    )

    assert sorted(planes) == sorted((href, plane) for plane, href, _ in DOORS)
    assert '<title id="overview-fig-title">' in markup


def test_row_and_plane_highlight_is_wired_for_pointer_and_keyboard() -> None:
    js = _js(INDEX.read_text(encoding="utf-8"))

    assert '"has-lit"' in js and '"is-lit"' in js
    for event in ("mouseenter", "mouseleave", "focus", "blur"):
        assert f'addEventListener("{event}"' in js, event
    assert "p.dataset.plane === key" in js and "d.dataset.plane === key" in js


def test_hero_search_sits_under_the_door_rows_and_before_the_figure() -> None:
    markup = _markup(INDEX.read_text(encoding="utf-8"))

    doors = markup.index('class="overview-doors"')
    search = markup.index('class="overview-search"')
    figure = markup.index('<figure class="overview-figure"')
    assert doors < search < figure


def test_task_bands_carry_their_links_and_reference_copy() -> None:
    page = INDEX.read_text(encoding="utf-8")

    for band in BANDS:
        section = _section(page, band)
        links = re.findall(r'<a href="([^"]+)">([^<]+)</a>', section)
        expected = [(href, label) for label, href in BAND_LINKS[band]]
        assert links == expected, band
        assert f'aria-labelledby="{band}-h"' in section
        assert f'<h2 class="overview-band__title" id="{band}-h">' in section
    for text in REFERENCE_COPY:
        assert text in page, text


def test_bands_use_plane_colours_for_their_swatch_and_link_arrows() -> None:
    page = INDEX.read_text(encoding="utf-8")

    assert 'id="people" aria-labelledby="people-h" style="--c: var(--atlas-task-people)"' in page
    assert 'style="--c: var(--atlas-task-water)"' in page
    assert 'style="--c: var(--atlas-task-money)"' in page
    assert "--c-arrow: var(--atlas-gold)" in page  # the ink band's arrows turn gold on hover


def test_schedule_is_a_dark_to_scale_section_with_the_five_jobs() -> None:
    page = INDEX.read_text(encoding="utf-8")
    js = _js(page)

    assert re.search(
        r'<section class="overview-clock" aria-labelledby="overview-clock-title">', page
    )
    assert '<div class="overview-chart__frame" id="overview-chart"></div>' in page
    for job in SCHEDULE_JOBS:
        assert f'label: "{job}"' in js, job
    # One linear scale from 09:30 to 12:00 UTC, as in the reference.
    assert "t0 = 9 * 60 + 30, t1 = 12 * 60" in js
    assert "host.innerHTML = s" in js
    assert "Scheduled jobs between 09:30 and 12:00 UTC" in js


def test_static_notes_and_about_and_glossary_links() -> None:
    page = INDEX.read_text(encoding="utf-8")
    clock = page[
        page.index('<section class="overview-clock"') : page.index(
            "</section>", page.index('<section class="overview-clock"')
        )
    ]

    headings = re.findall(r"<h3>([^<]+)</h3>", clock)
    assert headings == ["Static by design", "Open methods", "Every number has a source"]
    assert '<a href="./about">Read the methods</a>' in clock
    assert '<a href="./glossary">glossary</a>' in clock


def test_retired_overview_sections_are_gone() -> None:
    page = INDEX.read_text(encoding="utf-8")

    for retired in (
        'id="start-here"',
        "Explore the Atlas",
        "Browse by collection",
        "How it works",
        "overview-steps",
        "overview-stats",
        'class="atlas-kpi',
        'class="atlas-task',
        'class="atlas-entry',
        "atlas-hero",
        "data-atlas-icon",
        "Quick routes",
    ):
        assert retired not in page, retired


def test_every_section_is_labelled_by_an_existing_heading() -> None:
    page = INDEX.read_text(encoding="utf-8")

    for label in re.findall(r'aria-labelledby="([^"]+)"', page):
        assert f'id="{label}"' in page, label


def test_colours_come_only_from_design_tokens() -> None:
    page = INDEX.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    tokens = set(re.findall(r"(--atlas-[a-z0-9-]+):", TOKENS.read_text(encoding="utf-8")))
    used = set(re.findall(r"var\((--atlas-[a-z0-9-]+)", page + css))

    assert used, "no token references found"
    assert used <= tokens, sorted(used - tokens)
    # SVG paint is set through var() tokens only, never fill="..." or stroke="..." literals.
    assert not re.search(r'\b(?:fill|stroke)="', page)
    assert "fonts.googleapis" not in page and "fonts.gstatic" not in page


def test_figure_caption_and_reference_eyebrow_copy() -> None:
    page = INDEX.read_text(encoding="utf-8")

    assert '<figcaption class="overview-caps">32.5° to 42° N</figcaption>' in page
    title = "California in four colour planes, one for each part of the Atlas"
    assert f'<title id="overview-fig-title">{title}</title>' in page
