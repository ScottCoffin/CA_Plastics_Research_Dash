from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CHECK = ROOT / "tests" / "framework_institutions_runtime.mjs"
CLASSIC_PAGE = ROOT / "site" / "index.html"
COMPONENTS = ROOT / "framework" / "src" / "components"
PAGE = ROOT / "framework" / "src" / "institutions.md"


def _code_lines(text: str) -> list[str]:
    # Compare code only: drop indentation, blank lines and the `export` keyword.
    stripped = (re.sub(r"\s+", "", line.replace("export ", "", 1)) for line in text.splitlines())
    return [line for line in stripped if line]


def test_inst_tiers_matches_classic_block() -> None:
    # Drift guard: the ported tiers helpers must carry the classic code unchanged.
    html = CLASSIC_PAGE.read_text(encoding="utf-8")
    match = re.search(r'<script id="inst-tiers-helpers">(.*?)</script>', html, re.S)
    assert match, "the classic page must keep the inst-tiers-helpers block"
    ported = (COMPONENTS / "inst_tiers.js").read_text(encoding="utf-8")
    ported = ported.split("export const instTiers", 1)[1]
    assert _code_lines("const instTiers" + ported) == _code_lines(
        "const instTiers" + match.group(1).split("const instTiers", 1)[1]
    )


def test_page_markup_and_wiring() -> None:
    text = PAGE.read_text(encoding="utf-8")
    markup, _, script = text.partition("```js")
    assert 'id="institutions-root"' in markup
    assert 'data-inst-view="tiers"' in markup and 'data-inst-view="list"' in markup
    assert "${" not in markup, "no template literal in the HTML block"
    assert 'role="tabpanel"' not in markup and 'href="#about"' not in markup
    html_block = markup.split('<div id="institutions-root">', 1)[1].rstrip()
    assert "\n\n" not in html_block, "no blank line inside the HTML block"
    assert "mountInstitutions();" in script
    # Every element the page script looks up must exist in the markup.
    component = (COMPONENTS / "institutions.js").read_text(encoding="utf-8")
    ids = set(re.findall(r'\$\("([\w-]+)"\)', component))
    assert ids, "institutions.js must look up page elements"
    missing = sorted(i for i in ids if f'id="{i}"' not in markup)
    assert not missing, f"ids used by institutions.js but absent from the page: {missing}"


def test_framework_institutions_runtime_regressions() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for tests/framework_institutions_runtime.mjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    subprocess.run([node, str(RUNTIME_CHECK)], cwd=ROOT, check=True)
