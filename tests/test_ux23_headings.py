"""UX-23: one visible h1 per /app/ route and no heading-level skips (axe rules)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"


def _read(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def _levels_in_order(text: str) -> list[int]:
    """Heading levels in document order, from raw HTML tags and markdown ATX headings."""
    found = [(m.start(), int(m.group(1))) for m in re.finditer(r"<h([1-6])[\s>]", text)]
    found += [
        (m.start(), len(m.group(1))) for m in re.finditer(r"^(#{1,6}) \S", text, flags=re.MULTILINE)
    ]
    return [level for _, level in sorted(found)]


def _assert_no_skips(levels: list[int]) -> None:
    assert levels, "expected at least one heading"
    assert levels[0] == 1, f"first heading must be h1, got h{levels[0]}"
    assert levels.count(1) == 1, "exactly one visible h1 per page"
    for prev, cur in zip(levels, levels[1:]):
        assert cur <= prev + 1, f"heading-order skip: h{prev} followed by h{cur}"


def test_experts_and_funding_have_one_visible_h1():
    for rel in ("experts.md", "funding.md"):
        text = _read(rel)
        assert re.search(r"<h1>[^<]+</h1>", text), f"{rel} needs a visible h1"
        assert "<h2>Experts</h2>" not in text and "<h2>Funding</h2>" not in text


def test_experts_page_heading_order_has_no_skips():
    _assert_no_skips(_levels_in_order(_read("experts.md")))


def test_funding_page_heading_order_has_no_skips():
    _assert_no_skips(_levels_in_order(_read("funding.md")))


def test_institutions_page_heading_order_has_no_skips():
    text = _read("institutions.md")
    assert "<h2>California institution map</h2>" in text
    _assert_no_skips(_levels_in_order(text))


def test_institution_runtime_headings_follow_h1():
    js = _read("components/institutions.js")
    # UX-31: the card title links to the institution page; it stays an h2.
    assert (
        '<div class="card-header"><h2><a href="'
        '${escapeHtml(institutionPageUrl(institution.inst_id))}">'
        "${escapeHtml(institution.name)}</a></h2>"
    ) in js
    assert '<div class="top-experts"><h3>Top experts</h3>' in js
    assert '<section class="map-inst"><h4>${escapeHtml(institution.name)}</h4>' in js
    assert '<div class="map-details-head"><h3>${metrics.length}' in js


def test_resources_emit_card_names_as_h2():
    js = _read("components/resources.js")
    assert 'el("h2", "rs-name")' in js
    assert 'el("h3", "rs-name")' not in js


def test_experts_runtime_cards_sit_under_a_section_heading():
    text = _read("experts.md")
    assert '<h2 class="expert-sr-only">Expert list</h2>' in text
    # Expert cards are emitted as h3 by experts_model.js, so they need an h2 above them.
    assert text.index('<h2 class="expert-sr-only">') < text.index('id="expert-list"')
    assert "<h3><button" in _read("components/experts_model.js")


def test_about_has_no_h3_before_first_h2():
    text = _read("about.md")
    first_h2 = re.search(r"^## \S", text, flags=re.MULTILINE)
    assert first_h2, "about.md must use ## for its section headings"
    assert not re.search(r"^### \S", text[: first_h2.start()], flags=re.MULTILINE)
    _assert_no_skips(_levels_in_order(text))
