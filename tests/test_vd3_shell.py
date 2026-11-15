from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK = ROOT / "framework"
SAMPLE = (
    "<!DOCTYPE html><html><head></head><body>"
    '<input id="observablehq-sidebar-toggle" type="checkbox" title="Toggle sidebar">'
    '<label id="observablehq-sidebar-backdrop" for="observablehq-sidebar-toggle"></label>'
    '<nav id="observablehq-sidebar"><ol>'
    '<label id="observablehq-sidebar-close" for="observablehq-sidebar-toggle"></label>'
    '<li class="observablehq-link observablehq-link-active"><a href="./">Atlas</a></li>'
    '</ol></nav><div id="observablehq-center">'
    '<header id="observablehq-header"><a class="atlas-skip-link" href="#observablehq-main">'
    'Skip to content</a></header><main id="observablehq-main"></main></div></body></html>'
)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_sidebar_groups_header_search_and_footer_contract() -> None:
    config_uri = (FRAMEWORK / "observablehq.config.js").resolve().as_uri()
    script = (
        f"import({json.dumps(config_uri)}).then(m => {{"
        "const c=m.default;"
        "process.stdout.write(JSON.stringify({pages:c.pages,header:c.header({title:'Experts',path:'/experts'}),footer:c.footer,home:c.home}));"
        "})"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=FRAMEWORK,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)

    assert [section["name"] for section in data["pages"]] == [
        "Explore",
        "Data",
        "Context",
        "Reference",
    ]
    assert data["pages"][0]["pages"][0] == {"name": "Experts", "path": "/experts"}
    assert data["pages"][1]["pages"][-1] == {"name": "Evidence map", "path": "/evidence"}
    assert "CA Plastics Research Atlas" in data["home"]
    assert "CA Plastics Research Atlas" in data["header"]
    assert 'aria-label="Toggle navigation menu"' in data["header"]
    assert 'name="search"' in data["header"]
    assert 'href="./about#how-to-cite">How to cite</a>' in data["footer"]
    assert "Independent project; not an official OEHHA or State product." in data["footer"]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_postbuild_places_skip_link_first_and_repairs_framework_sidebar() -> None:
    module_uri = (FRAMEWORK / "scripts" / "postbuild.mjs").resolve().as_uri()
    script = (
        f"import({json.dumps(module_uri)}).then(m => {{"
        f"const once=m.fixHtml({json.dumps(SAMPLE)},'index');"
        "const twice=m.fixHtml(once,'index');"
        "process.stdout.write(JSON.stringify([once,twice]));"
        "})"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=FRAMEWORK,
        capture_output=True,
        text=True,
        check=True,
    )
    once, twice = json.loads(result.stdout)

    assert once == twice
    assert '<body>\n<a class="atlas-skip-link"' in once
    assert once.index("atlas-skip-link") < once.index("observablehq-sidebar-toggle")
    assert 'aria-hidden="true" tabindex="-1"' in once
    assert '<ol><li class="observablehq-link observablehq-link-active"><a' in once
    assert 'id="observablehq-sidebar-close"' not in once
    assert 'aria-label="Overview" aria-current="page"' in once


def test_shell_css_has_route_icons_and_mobile_controls() -> None:
    css = (FRAMEWORK / "src" / "design" / "shell.css").read_text(encoding="utf-8")

    for route in (
        "experts",
        "network",
        "institutions",
        "monitoring",
        "funding",
        "evidence",
        "policy",
        "resources",
        "about",
        "glossary",
    ):
        assert f'a[href$="/{route}"]' in css
    assert "env(safe-area-inset-left" in css
    assert ".atlas-search-open .atlas-header__search" in css
    assert ".atlas-menu-button" in css


def test_async_resources_keep_the_footer_out_of_the_initial_viewport() -> None:
    css = (FRAMEWORK / "src" / "components" / "resources.css").read_text(encoding="utf-8")

    assert "min-height: calc(100vh - var(--observablehq-header-height));" in css
