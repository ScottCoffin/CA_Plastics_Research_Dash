"""Static checks for the BQ-1.4 quality pages (/quality and /california/quality) and their wiring.

No browser and no build: the rendered behaviour is checked by the Playwright smoke run recorded in
the checkpoint report. These tests keep the wording, data paths and nav links from drifting.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GLOBAL_PAGE = ROOT / "framework" / "src" / "quality.md"
CA_PAGE = ROOT / "framework" / "src" / "california" / "quality.md"
RENDERER = ROOT / "framework" / "src" / "components" / "quality.js"
STYLES = ROOT / "framework" / "src" / "components" / "quality.css"
ABOUT = ROOT / "framework" / "src" / "california" / "about.md"
CONFIG = ROOT / "framework" / "observablehq.config.js"
POSTBUILD = ROOT / "framework" / "scripts" / "postbuild.mjs"


def test_both_pages_exist_and_show_the_placeholder_status():
    for page in (GLOBAL_PAGE, CA_PAGE):
        text = page.read_text(encoding="utf-8")
        assert "No validated estimate yet" in text
        assert "quality-root" in text


def test_pages_load_their_own_scope_payload():
    assert 'fetch("./data/global/quality.json"' in GLOBAL_PAGE.read_text(encoding="utf-8")
    assert 'loadJson("quality.json")' in CA_PAGE.read_text(encoding="utf-8")


def test_pages_publish_no_numeric_estimate_in_static_text():
    for page in (GLOBAL_PAGE, CA_PAGE):
        text = page.read_text(encoding="utf-8")
        # Static prose carries no figure; figures come only from the payload at a final checkpoint.
        assert not re.search(r"\b0\.\d{2,}\b", text), page
        assert not re.search(r"\b\d+(\.\d+)?%", text), page


def test_renderer_sets_text_without_innerhtml_and_adds_no_numbers():
    source = RENDERER.read_text(encoding="utf-8")
    assert ".innerHTML" not in source
    assert ".outerHTML" not in source
    assert 'status === "ok"' in source
    assert "No validated estimate yet" in source


def test_styles_are_scoped_to_the_quality_root():
    for line in STYLES.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(".") and "{" in line:
            assert line.strip().startswith(".qx"), line


def test_about_limitation_links_to_the_quality_page():
    text = ABOUT.read_text(encoding="utf-8")
    limitation = text[text.index("about-limitations-card") :]
    limitation = limitation[: limitation.index("</article>")]
    assert "No gold-set evaluation exists yet" in limitation
    assert 'href="./quality"' in limitation


def test_navigation_and_postbuild_registration():
    config = CONFIG.read_text(encoding="utf-8")
    assert 'path: "/california/quality"' in config
    assert "footer: regionFooter" in config
    assert 'href="./california/quality"' in config.split("function regionFooter", 1)[1]
    postbuild = POSTBUILD.read_text(encoding="utf-8")
    assert '"california/quality":' in postbuild
    assert "  quality:" in postbuild


def test_public_text_checker_reads_both_quality_payloads():
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(
        "check_public_text", ROOT / "scripts" / "check_public_text.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("check_public_text", module)
    spec.loader.exec_module(module)
    assert "site/data/california/quality.json" in module.DEFAULT_JSON
    assert "site/data/global/quality.json" in module.DEFAULT_JSON
