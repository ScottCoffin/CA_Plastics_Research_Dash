"""UX-24 static guards: Monitoring layout stability and grants.html axe fixes.

Browser results (Lighthouse CLS, axe) come from the audit run recorded in the task report;
these tests pin the markup that those results depend on.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MONITORING_MD = ROOT / "framework" / "src" / "monitoring.md"
MONITORING_JS = ROOT / "framework" / "src" / "components" / "monitoring.js"
MONITORING_CSS = ROOT / "framework" / "src" / "components" / "monitoring.css"
GRANTS = ROOT / "site" / "grants.html"


def _summaries(text: str) -> list[str]:
    return re.findall(r"<summary>(.*?)</summary>", text, re.S)


def test_monitoring_quality_note_has_static_text_before_data_loads() -> None:
    md = MONITORING_MD.read_text(encoding="utf-8")
    note = re.search(
        r'<div id="monitoring-quality-note"[^>]*>(.*?)</div>\s*\n\s*<div class="facet-controls"',
        md,
        re.S,
    )
    assert note, "quality note must be a container with static content"
    # The visible lead is in the markup, so the box has its height before monitoring.json loads.
    assert 'class="notice-lead"' in note.group(1)
    assert "not evidence of a data gap" in note.group(1)
    # Variable, data-driven text goes into a closed disclosure, so growth cannot shift the page.
    assert '<details class="notice-details">' in note.group(1)
    assert '<p id="monitoring-quality-detail"></p>' in note.group(1)


def test_monitoring_js_fills_the_detail_not_the_note() -> None:
    js = MONITORING_JS.read_text(encoding="utf-8")
    assert '$("monitoring-quality-detail").textContent' in js
    assert '$("monitoring-quality-note")' not in js


def test_monitoring_summaries_contain_no_headings_or_links() -> None:
    # Headings with ids get a Framework anchor <a>, which nests an interactive control in <summary>.
    md = MONITORING_MD.read_text(encoding="utf-8")
    summaries = _summaries(md)
    assert len(summaries) == 6  # five facets plus the notice disclosure
    for body in summaries:
        assert not re.search(r"<h[1-6]\b|<a\b|<button\b|<input\b|<select\b", body), body


def test_monitoring_has_no_heading_level_skips() -> None:
    md = MONITORING_MD.read_text(encoding="utf-8")
    assert not re.search(r"<h[3-6]\b", md)
    assert not re.search(r"^####", md, re.M)
    assert "<h2>${rows.length}" in MONITORING_JS.read_text(encoding="utf-8")


def test_monitoring_facet_titles_keep_section_labels() -> None:
    md = MONITORING_MD.read_text(encoding="utf-8")
    for element_id in (
        "monitoring-filters-heading",
        "monitoring-sources-heading",
        "monitoring-map-heading",
        "monitoring-gaps-heading",
        "monitoring-samples-heading",
    ):
        assert re.search(rf'<span class="facet-title" id="{element_id}">', md), element_id
    for element_id in ("monitoring-sources-heading", "monitoring-map-heading"):
        assert f'aria-labelledby="{element_id}"' in md
    assert "#monitoring-root .facet-title" in MONITORING_CSS.read_text(encoding="utf-8")


def test_grants_chips_group_has_role_for_aria_label() -> None:
    html = GRANTS.read_text(encoding="utf-8")
    match = re.search(r'<div class="chips" id="chips"[^>]*>', html)
    assert match and 'role="group"' in match.group(0)


def test_grants_tiles_put_small_inside_dd() -> None:
    html = GRANTS.read_text(encoding="utf-8")
    # A <small> directly inside the wrapper <div> fails axe definition-list; it belongs inside <dd>.
    expected = (
        'const tile = (t, v, s) => `<div class="metric"><dt>${t}</dt>'
        '<dd>${v}${s ? `<small>${s}</small>` : ""}</dd></div>`;'
    )
    assert expected in html


def test_grants_stacked_bar_svg_is_a_group_not_an_image() -> None:
    html = GRANTS.read_text(encoding="utf-8")
    assert 'role="img" aria-label="Stacked bar chart' not in html
    assert 'role="group" aria-label="Stacked bar chart of awards per fiscal year' in html
    # The segments stay keyboard-reachable.
    assert 'tabindex="0" role="button" aria-label="${yr.year}' in html


def test_grants_rowhead_cells_have_hidden_text_and_class_exists() -> None:
    html = GRANTS.read_text(encoding="utf-8")
    assert '<th class="rowhead"></th>' not in html
    assert '<th class="rowhead"><span class="visually-hidden">Topic</span></th>' in html
    assert '<th class="rowhead"><span class="visually-hidden">Recipient sector</span></th>' in html
    assert re.search(r"\.visually-hidden \{[^}]*position: absolute", html)
