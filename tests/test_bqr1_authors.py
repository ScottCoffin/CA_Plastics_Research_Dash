"""BQ-R1: the Authors page replaces Experts; the old route keeps a redirect stub (A3-C4)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CALIFORNIA = ROOT / "framework" / "src" / "california"
POSTBUILD = ROOT / "framework" / "scripts" / "postbuild.mjs"


def test_authors_page_exists_and_experts_page_source_is_gone() -> None:
    page = (CALIFORNIA / "authors.md").read_text(encoding="utf-8")
    assert "title: Authors" in page
    assert "<h1>Authors</h1>" in page
    assert not (CALIFORNIA / "experts.md").exists()


def test_nav_points_to_authors() -> None:
    config = (ROOT / "framework" / "observablehq.config.js").read_text(encoding="utf-8")
    assert '{name: "Authors", path: "/california/authors"}' in config
    assert 'path: "/california/experts"' not in config


def test_postbuild_writes_a_redirect_stub_that_keeps_search_and_hash() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("install Node.js 20 or newer and ensure `node` is on PATH.")
    script = (
        f"const m = await import({json.dumps(POSTBUILD.as_uri())});"
        "console.log(JSON.stringify({stubs: m.ROUTE_STUBS, html: m.redirectStub('authors')}));"
    )
    out = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    result = json.loads(out.strip().splitlines()[-1])
    assert result["stubs"] == {"california/experts": "authors"}
    html = result["html"]
    assert 'location.replace("./authors" + location.search + location.hash)' in html
    assert '<meta name="robots" content="noindex">' in html
    assert '<a href="./authors">' in html


def test_public_text_check_flags_experts_but_allows_quoted_titles_and_file_names(
    tmp_path: Path,
) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_public_text", ROOT / "scripts" / "check_public_text.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bad = tmp_path / "bad.html"
    bad.write_text("<h1>Experts</h1><p>Find an expert.</p>", encoding="utf-8")
    assert len(module.find_matches(bad)) == 2
    ok = tmp_path / "ok.html"
    ok.write_text(
        '<h1>Authors</h1><li><span data-public-text="quoted">Expert elicitation of risk</span></li>'
        "<cite>Experts and plastics</cite><code>experts.js</code>"
        '<a href="expert.html#author=A1">profile</a><p>See expert.html and experts/A1/.</p>',
        encoding="utf-8",
    )
    assert module.find_matches(ok) == []


def test_public_text_check_reads_visible_attributes_and_json_method_text(tmp_path: Path) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_public_text", ROOT / "scripts" / "check_public_text.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    page = tmp_path / "attrs.html"
    page.write_text(
        '<input placeholder="Search experts"><img alt="An expert"><p>expert-led work</p>'
        '<a class="expert-name" data-x="experts" href="experts/A1/">A</a>',
        encoding="utf-8",
    )
    assert len(module.find_matches(page)) == 3
    data = tmp_path / "net.json"
    data.write_text(
        json.dumps({"method": {"labels": "Communities of 4 experts"}, "names": ["Expert Co"]}),
        encoding="utf-8",
    )
    assert [m[0] for m in module.find_matches(data)] == ["$.method.labels"]
