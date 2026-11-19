"""PLAT-2b landing evidence grid: static checks that live cell counts are wired in (no browser).

The engine reads data/global/evidence_cells.json. When the file is missing or not plat2b.v1 it keeps
the illustrative grid, table and footnotes; these tests keep the hooks, the schema check, the
fallback text and the public wording in place.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
INDEX = SRC / "index.md"
ENGINE = SRC / "components" / "landing_story.js"


def _evidence_section() -> str:
    page = INDEX.read_text(encoding="utf-8")
    assert page.count('id="evidence"') == 1
    return page.split('id="evidence"', 1)[1].split("</section>", 1)[0]


def test_evidence_section_has_one_hook_per_live_element() -> None:
    section = _evidence_section()
    for hook in ("evidence-lede", "evidence-table", "evidence-caption", "evidence-src"):
        assert section.count(f'data-plv="{hook}"') == 1, hook
    assert '<table class="plv-evt" data-plv="evidence-table">' in section
    assert '<caption class="sr-only" data-plv="evidence-caption">' in section
    assert '<p class="lede" data-plv="evidence-lede">' in section
    assert '<p class="plv-evsrc" data-plv="evidence-src">' in section


def test_evidence_section_keeps_the_illustrative_fallback_markup() -> None:
    section = _evidence_section()
    body = section.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    assert len(re.findall(r"<tr>", body)) == 5
    assert len(re.findall(r"<td[ >]", body)) == 30
    assert body.count('class="gap"') == 4
    assert "Illustrative study counts by topic and setting, worldwide" in section
    assert "Rebuilt daily from OpenAlex once the cell definitions are agreed." in section
    assert "Illustrative counts. The live version counts works per cell" in section
    assert 'role="region" aria-label="Evidence map table"' in section
    assert 'aria-labelledby="plv-evidence-h"' in section


def test_engine_reads_the_live_cells_and_checks_the_schema() -> None:
    engine = ENGINE.read_text(encoding="utf-8")
    assert 'json("data/global/evidence_cells.json")' in engine
    assert '"plat2b.v1"' in engine
    assert "Number.isInteger(n) && n >= 0" in engine
    assert "data.max > 0" in engine
    assert "evidenceCells()" in engine and "validCells" in engine


def test_engine_keeps_the_illustrative_fallback_text() -> None:
    engine = ENGINE.read_text(encoding="utf-8")
    assert '"worldwide; illustrative cell counts until the live counts are built"' in engine
    assert '"illustrative counts"' in engine
    assert '"Rebuilt daily from OpenAlex once the cell definitions are agreed."' in engine


def test_engine_names_the_live_footnote_caption_lede_and_source_line() -> None:
    engine = ENGINE.read_text(encoding="utf-8")
    assert '"works per cell"' in engine
    assert "worldwide; works per cell, OpenAlex" in engine
    assert "Works per cell by topic and setting, worldwide, from OpenAlex" in engine
    assert '"Rebuilt daily from OpenAlex."' in engine
    assert "A work can count in several cells." in engine


def test_engine_updater_sets_counts_shade_and_gap_class() -> None:
    engine = ENGINE.read_text(encoding="utf-8")
    assert 'toLocaleString("en-US")' in engine
    assert "toFixed(2)" in engine
    # LAND-1: no white-text switch; the CSS ramp stops at 70% slate so ink text stays AA.
    assert 'classList.toggle("dk"' not in engine
    css = (ENGINE.parent / "landing_story.css").read_text(encoding="utf-8")
    assert "calc(var(--v) * 70%)" in css and "td.dk" not in css
    assert 'classList.toggle("gap", n < gapBelow)' in engine
    # The updater runs at module start, not behind the story's load waits.
    assert 'document.addEventListener("DOMContentLoaded", startEvidenceMap' in engine
    assert "else startEvidenceMap();" in engine


def test_plat2b_identifier_appears_only_in_code_comments() -> None:
    for path in (ENGINE, INDEX):
        for line in path.read_text(encoding="utf-8").splitlines():
            if "PLAT-2b" in line:
                assert line.lstrip().startswith("//"), f"{path.name}: {line.strip()}"
    assert "PLAT-2b" not in _evidence_section()
