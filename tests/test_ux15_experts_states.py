"""UX-15: Experts list states (loading, load failure with Retry, no results with Reset filters),
the `N of M experts` count, and the row element (div listitem, not article)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
MODEL = SRC / "components" / "experts_model.js"
COMPONENT = SRC / "components" / "experts.js"
CSS = SRC / "components" / "experts.css"
PAGE = SRC / "experts.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_virtual_row_is_a_div_listitem():
    model = _read(MODEL)
    assert '<div class="virtual-row" role="listitem"' in model
    assert "<article" not in model
    assert "article.virtual-row" not in _read(CSS)


def test_page_has_state_panel_above_hidden_list_and_loading_text():
    page = _read(PAGE)
    assert 'id="expert-state"' in page
    assert "Loading experts…" in page
    state_at = page.index('id="expert-state"')
    list_at = page.index('id="expert-list"')
    assert state_at < list_at
    assert 'role="list" aria-label="Experts" aria-live="polite" hidden>' in page


def test_component_wires_loading_failure_retry_and_reset():
    js = _read(COMPONENT)
    # Loading is shown on start and on retry; failure swaps in a Retry button.
    assert "setStatePanel(LOADING_HTML)" in js
    assert 'id="expert-retry"' in js and ">Retry</button>" in js
    # No-results state uses the shared message and a Reset filters button.
    assert "EMPTY_MATCH_TEXT" in _read(MODEL)
    assert 'id="expert-state-reset"' in js and ">Reset filters</button>" in js
    assert "function resetAllFilters()" in js
    assert 'addEventListener("click", resetAllFilters' in js
    assert 'closest("#expert-state-reset")' in js
    assert 'closest("#expert-retry")' in js
    # The old unannounced HTML in the list is gone.
    assert "EMPTY_MATCH_HTML" not in js


def _run_node(script: str) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for the UX-15 model checks; install Node.js 20 or newer.")
    # Shared topic helpers are gitignored copies of site/assets; create them as
    # `npm run build` does.
    sync = ROOT / "framework" / "scripts" / "sync_shared.mjs"
    subprocess.run([node, str(sync)], cwd=ROOT, check=True, capture_output=True)
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_count_text_and_row_markup_at_runtime():
    model_url = MODEL.as_uri()
    topics_url = (SRC / "components" / "shared" / "topics.js").as_uri()
    script = f"""
import {json.dumps(topics_url)};
const m = await import({json.dumps(model_url)});
const lookups = m.buildLookups({{works: [], authors: []}}, []);
const raw = {{author_id: "A1", name: "Test Person", work_ids: [], institution_ids: [],
  cited_by_count: 1, h_index: 1, plastic_citations: 0, plastic_works_count: 0,
  work_count: 0, ca_works_count: 0}};
const author = m.summarizeAuthor(raw, lookups.worksById, lookups.institutionsById);
const row = m.expertRowHtml(author, 0, 232, "plastic_citations");
console.log(JSON.stringify({{
  zero: m.expertCountText(0, 5),
  one: m.expertCountText(1, 1),
  all: m.expertCountText(2614, 2614),
  rowStart: row.slice(0, 60),
  rowEnd: row.slice(-6),
  hasArticle: row.includes("<article"),
  emptyText: m.EMPTY_MATCH_TEXT
}}));
"""
    out = _run_node(script)
    assert out["zero"] == "0 of 5 experts"
    assert out["one"] == "1 of 1 expert"
    assert out["all"] == "2,614 of 2,614 experts"
    assert out["rowStart"].startswith('<div class="virtual-row" role="listitem"'), out["rowStart"]
    assert out["rowEnd"].endswith("</div>"), out["rowEnd"]
    assert out["hasArticle"] is False
    assert out["emptyText"] == "No experts match these filters."
