"""UX-1/UX-21 (docs/EM_spec.md): Classic-site link, new-version banner, template fixes."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "framework"


def test_framework_header_has_no_classic_link_after_switch():
    """Owner H16 switch (2026-11-13): the app is the site root, so no "Classic site" link."""
    config = (FW / "observablehq.config.js").read_text(encoding="utf-8")
    assert "atlas-classic" not in config
    assert not re.search(r"Classic site", config)


def test_postbuild_runs_after_build():
    scripts = json.loads((FW / "package.json").read_text(encoding="utf-8"))["scripts"]
    assert scripts.get("postbuild") == "node scripts/postbuild.mjs"


def test_classic_index_links_to_app():
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    banner = re.search(r'<p class="new-version-banner"><a href="([^"]+)">([^<]+)</a>', html)
    assert banner, "classic index must show the new-version banner"
    assert banner.group(1) == "app/"
    assert banner.group(2) == "A newer version of this atlas is available."


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_postbuild_fix_html_rewrites_template():
    sample = (
        "<html>\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">'
        '<input id="observablehq-sidebar-toggle" type="checkbox" title="Toggle sidebar">'
    )
    script = "import(process.argv[1]).then(m => process.stdout.write(m.fixHtml(process.argv[2])))"
    module = (FW / "scripts" / "postbuild.mjs").resolve().as_uri()
    out = subprocess.run(
        ["node", "-e", script, module, sample], capture_output=True, text=True, check=True
    ).stdout
    assert '<html lang="en">' in out
    assert "maximum-scale" not in out
    assert 'aria-label="Toggle sidebar"' in out


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_postbuild_font_preload_is_relative_and_idempotent():
    preload = (
        '<link rel="preload" href="./assets/fonts/BarlowSemiCondensed-Bold-latin.woff2" '
        'as="font" type="font/woff2" crossorigin>'
    )
    sample = f"<html><head>{preload}{preload}</head><body></body></html>"
    script = (
        "import(process.argv[1]).then(m => {"
        "const once = m.fixHtml(process.argv[2], 'unknown');"
        "const twice = m.fixHtml(once, 'unknown');"
        "process.stdout.write(JSON.stringify([once, twice]));"
        "})"
    )
    module = (FW / "scripts" / "postbuild.mjs").resolve().as_uri()
    once, twice = json.loads(
        subprocess.run(
            ["node", "-e", script, module, sample],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    )

    assert once == twice
    assert once.count(preload) == 1
    assert once.index(preload) < once.index("</head>")
    assert 'href="/assets/fonts/' not in once


def test_style_css_keeps_contrast_overrides():
    """UX-22: named theme tokens keep contrast and running links keep an underline."""
    css = (FW / "src" / "style.css").read_text(encoding="utf-8")
    tokens = (FW / "src" / "design" / "tokens.css").read_text(encoding="utf-8")
    assert "--theme-foreground-muted: var(--atlas-muted);" in tokens
    assert "--theme-foreground-faint: var(--atlas-faint);" in tokens
    assert "text-decoration: underline" in css
    # Owner 2026-11-12: light theme only, so the dark-theme panel overrides were removed.
    assert "near-midnight" not in css
    assert "prefers-color-scheme: dark" not in css
