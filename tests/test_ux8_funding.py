"""UX-8: no headline dollar total on Funding; per-source subtotals carry the not-a-total caveat."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FUNDING_JS = ROOT / "framework" / "src" / "components" / "funding.js"
FUNDING_MD = ROOT / "framework" / "src" / "funding.md"
GRANTS_HTML = ROOT / "site" / "grants.html"


def test_funding_js_has_no_summed_total_sentence() -> None:
    js = FUNDING_JS.read_text(encoding="utf-8")
    assert "summing to" not in js
    # The status line reports counts only.
    assert re.search(r"report an amount\.`", js)


def test_funding_subtotal_caption_carries_not_a_total_caveat() -> None:
    js = FUNDING_JS.read_text(encoding="utf-8")
    match = re.search(r"<caption>([^<]*)</caption>", js)
    assert match, "per-source subtotal table needs a caption"
    caption = match.group(1)
    assert "not a total" in caption
    assert "cannot be added" in caption
    # The subtotal table is written into the amount-basis container.
    assert 'class="grants-subtotals"' in js
    assert '$("grants-basis").innerHTML = `<table class="grants-subtotals">' in js


def test_rows_per_page_default_is_stated_and_selected() -> None:
    md = FUNDING_MD.read_text(encoding="utf-8")
    assert "Rows per page (default 50)" in md
    assert re.search(r'<option value="50" selected>50</option>', md)
    js = FUNDING_JS.read_text(encoding="utf-8")
    assert re.search(r"grantsPageSize:\s*50\b", js)
    assert 'Number($("grants-page-size").value) || 50' in js


def test_classic_grants_tiles_have_no_reported_amount_tile() -> None:
    html = GRANTS_HTML.read_text(encoding="utf-8")
    assert 'tile("Reported amount"' not in html
    # The tiles function still builds the other summary tiles and the dl stays the container.
    assert 'class="metrics" id="tiles"' in html
    assert 'tile("Awards"' in html


def test_classic_grants_dollar_figures_carry_caveat_in_same_sentence() -> None:
    html = GRANTS_HTML.read_text(encoding="utf-8")
    # Every Sankey tooltip that prints a reported amount also says the bases differ.
    for line in html.splitlines():
        if "Reported amount: " in line and "fmtUsd" in line:
            assert "source bases differ" in line, line.strip()
