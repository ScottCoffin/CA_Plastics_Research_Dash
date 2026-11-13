"""UX-14: Overview refresh time, duplicate "Labeled works" tile, and the Start here row."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"

SCRIPT = """
import(process.argv[1]).then((m) => {
  const meta = (labeled) => ({generated_at: "2026-11-12T17:09:05+00:00",
    counts: {authors: 1, works: 5, labeled_works: labeled, institutions: 2, ca_institutions: 1}});
  const same = m.aboutViewModel(meta(5), null);
  const differ = m.aboutViewModel(meta(4), null);
  const fixture = m.aboutViewModel({generated_at: "fixture", counts: {}}, null);
  console.log(JSON.stringify({
    display: m.formatRefresh("2026-11-12T17:09:05+00:00"),
    bad: m.formatRefresh("fixture"),
    text: same.refreshText, iso: same.refreshIso,
    sameLabels: same.stats.map((s) => s.label),
    differLabels: differ.stats.map((s) => s.label),
    fixtureText: fixture.refreshText, fixtureIso: fixture.refreshIso,
  }));
});
"""


@pytest.fixture(scope="module")
def result() -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    module = (SRC / "components" / "atlas.js").resolve().as_uri()
    out = subprocess.run(
        [node, "--input-type=module", "-e", SCRIPT, module],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


def test_refresh_time_is_formatted_for_prose(result: dict) -> None:
    assert result["display"] == "12 Nov 2026, 17:09 UTC"
    assert result["bad"] is None
    assert result["text"] == "Last refresh: 12 Nov 2026, 17:09 UTC"
    assert result["iso"] == "2026-11-12T17:09:05.000Z"
    assert result["fixtureIso"] is None
    assert result["fixtureText"].startswith("Example data loaded")


def test_labeled_works_tile_only_when_it_differs(result: dict) -> None:
    assert "Labeled works" not in result["sameLabels"]
    assert "Labeled works" in result["differLabels"]


def test_pages_render_time_element_and_start_row() -> None:
    index = (SRC / "index.md").read_text(encoding="utf-8")
    about = (SRC / "about.md").read_text(encoding="utf-8")
    for text in (index, about):
        assert "<time datetime=${snapshot.refreshIso}>" in text
    assert 'id="start-here"' in index
    for href in ("./experts", "./funding", "./monitoring"):
        assert f'<li><a href="{href}">' in index
