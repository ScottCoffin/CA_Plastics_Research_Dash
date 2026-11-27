"""FAVICON-MAIN: every page uses the Plastiverse Live icon; the header brand mark is unchanged."""

from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "site" / "assets"
FW = ROOT / "framework"
DIST = FW / "dist"
CONFIG = (FW / "observablehq.config.js").read_text(encoding="utf-8")
ICON_LINK = re.compile(r"<link\b[^>]*\brel=\"icon\"[^>]*>", re.IGNORECASE)
HREF = re.compile(r"\bhref=\"([^\"]*)\"")


def _icon_hrefs(html: str) -> list[str]:
    return [HREF.search(tag).group(1) for tag in ICON_LINK.findall(html)]


def test_build_favicons_check_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_favicons.py"), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_config_favicon_decodes_to_the_main_icon_bytes() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is needed to evaluate the Framework config")
    script = (
        f"const m = await import({json.dumps((FW / 'observablehq.config.js').resolve().as_uri())});"
        "const head = m.default.head;"
        "const pick = re => head.match(re)[1];"
        "process.stdout.write(JSON.stringify({"
        'svg: pick(/<link rel="icon" href="([^"]+)">/),'
        'png: pick(/<link rel="icon" type="image\\/png" sizes="32x32" href="([^"]+)">/),'
        "}));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        cwd=FW,
        capture_output=True,
        text=True,
        check=True,
    )
    uris = json.loads(result.stdout)
    prefix_svg = "data:image/svg+xml;base64,"
    prefix_png = "data:image/png;base64,"
    assert uris["svg"].startswith(prefix_svg)
    assert uris["png"].startswith(prefix_png)
    assert base64.b64decode(uris["svg"][len(prefix_svg) :]) == (ASSETS / "favicon.svg").read_bytes()
    assert (
        base64.b64decode(uris["png"][len(prefix_png) :]) == (ASSETS / "favicon-32.png").read_bytes()
    )


def test_header_brand_mark_keeps_the_paper_california() -> None:
    assert "const CA_MARK = " in CONFIG
    assert "const PLANE_MARK = " in CONFIG
    assert "const FAVICON = " in CONFIG and "favicon.svg" in CONFIG
    assert "FAVICON-MAIN" in CONFIG


def test_static_pages_link_the_main_icons() -> None:
    pages = {
        ROOT / "site" / "grants.html": "assets/",
        ROOT / "site" / "sem.html": "assets/",
        ROOT / "site" / "california" / "expert.html": "../assets/",
    }
    for page, prefix in pages.items():
        html = page.read_text(encoding="utf-8")
        hrefs = _icon_hrefs(html)
        assert f"{prefix}favicon.svg" in hrefs, page.name
        assert f"{prefix}favicon-32.png" in hrefs, page.name
        assert f'<link rel="apple-touch-icon" href="{prefix}apple-touch-icon.png">' in html, (
            page.name
        )


def test_seo_pages_link_the_main_icons() -> None:
    from atlas.build.seo import _page

    html = _page(
        title="Title",
        description="Description",
        canonical="https://plastiverse.live/california/",
        og_type="website",
        body="",
        schema={},
    )
    hrefs = _icon_hrefs(html)
    assert hrefs == [
        "/assets/favicon.svg",
        "/assets/favicon-32.png",
    ]
    assert '<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">' in html


def test_root_favicon_ico_is_the_main_icon() -> None:
    assert (ROOT / "site" / "favicon.ico").read_bytes() == (ASSETS / "favicon.ico").read_bytes()


def test_dist_pages_share_one_icon_set() -> None:
    if not (DIST / "index.html").is_file():
        pytest.skip("framework/dist is not built; run `npm run build` in framework/")
    index_hrefs = _icon_hrefs((DIST / "index.html").read_text(encoding="utf-8"))
    assert index_hrefs == [
        "data:image/svg+xml;base64,"
        + base64.b64encode((ASSETS / "favicon.svg").read_bytes()).decode("ascii"),
        "data:image/png;base64,"
        + base64.b64encode((ASSETS / "favicon-32.png").read_bytes()).decode("ascii"),
    ]

    checked = 0
    skipped = 0
    mismatched: list[str] = []
    for page in sorted(DIST.rglob("*.html")):
        html = page.read_text(encoding="utf-8")
        # postbuild's redirect stubs have no icon of their own; they are the only pages skipped.
        if 'http-equiv="refresh"' in html:
            skipped += 1
            continue
        checked += 1
        if _icon_hrefs(html) != index_hrefs:
            mismatched.append(str(page.relative_to(DIST)))
    print(f"favicon check: {checked} HTML files checked, {skipped} redirect stubs skipped")
    assert checked > 0
    assert not mismatched, mismatched
