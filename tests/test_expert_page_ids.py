"""UX-2: expert profile ID parsing (site/assets/expert_page.js parseExpertId) and page wiring."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HELPERS = ROOT / "site" / "assets" / "expert_page.js"
PAGE = ROOT / "site" / "expert.html"

# Loads the helper module with require() (it exports through module.exports under Node), runs each
# [search, hash] pair given as JSON on argv, and prints the results as a JSON array.
NODE_RUN = r"""
const helpers = require(process.argv[1]);
const cases = JSON.parse(process.argv[2]);
const out = cases.map(([search, hash]) => helpers.parseExpertId(search, hash));
process.stdout.write(JSON.stringify(out));
"""

CASES = [
    ("", "#author=A5046986222"),
    ("?id=A5046986222", ""),
    ("?author=A5046986222", ""),
    ("?id=A5046986222", "#author=A1"),
    ("", ""),
    ("", "#other=1"),
    ("?id=", ""),
    ("", "#author=ABC"),
    ("?id=5046986222", ""),
    ("?id=https://openalex.org/A5046986222", ""),
    ("", "#author=https%3A%2F%2Fopenalex.org%2FA5046986222"),
    ("", "#author=%20a5046986222%20"),
    ("", "#author=A0000000000"),
    ("?id=../etc", ""),
]

EXPECTED = [
    {"id": "A5046986222", "status": "ok", "raw": "A5046986222"},
    {"id": "A5046986222", "status": "ok", "raw": "A5046986222"},
    {"id": "A5046986222", "status": "ok", "raw": "A5046986222"},
    {"id": "A1", "status": "ok", "raw": "A1"},
    {"id": "", "status": "missing", "raw": ""},
    {"id": "", "status": "missing", "raw": ""},
    {"id": "", "status": "missing", "raw": ""},
    {"id": "", "status": "malformed", "raw": "ABC"},
    {"id": "", "status": "malformed", "raw": "5046986222"},
    {"id": "A5046986222", "status": "ok", "raw": "https://openalex.org/A5046986222"},
    {"id": "A5046986222", "status": "ok", "raw": "https://openalex.org/A5046986222"},
    {"id": "A5046986222", "status": "ok", "raw": "a5046986222"},
    {"id": "A0000000000", "status": "ok", "raw": "A0000000000"},
    {"id": "", "status": "malformed", "raw": "../etc"},
]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_parse_expert_id_runtime() -> None:
    node = shutil.which("node")
    assert node is not None
    cases = json.dumps([list(pair) for pair in CASES])
    out = subprocess.run(
        [node, "-e", NODE_RUN, HELPERS.resolve().as_posix(), cases],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert json.loads(out) == EXPECTED


def test_parse_expert_id_is_exported_and_dom_free() -> None:
    source = HELPERS.read_text(encoding="utf-8")
    assert "function parseExpertId(search, hash)" in source
    assert "parseExpertId,\n" in source, "parseExpertId must be in the exported api object"
    assert "document" not in source and "location" not in source, "helpers must stay DOM-free"


def test_expert_page_uses_parse_expert_id_and_canonical_hash() -> None:
    html = PAGE.read_text(encoding="utf-8")
    assert "parseExpertId(location.search, location.hash)" in html
    assert 'history.replaceState(null, "", `${location.pathname}#author=' in html
    assert "expert.html#author=A5046986222" in html, "no-ID message shows the profile address form"
    assert 'href="index.html#experts"' in html, "message section links back to the Experts list"
