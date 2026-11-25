from __future__ import annotations

import json
import re
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
        "process.stdout.write(JSON.stringify({pages:c.pages,header:c.header({title:'Authors',path:'/california/authors'}),footer:c.footer,home:c.home}));"
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

    # PLAT-1: the California overview is the first sidebar entry; the groups follow it.
    assert [section["name"] for section in data["pages"]] == [
        "California overview",
        "Explore",
        "Data",
        "Context",
        "Reference",
    ]
    assert data["pages"][1]["pages"][0] == {"name": "Authors", "path": "/california/authors"}
    # BQ-1.4 adds Quality after the Evidence map at the end of the Data group.
    assert data["pages"][2]["pages"][-2:] == [
        {"name": "Evidence map", "path": "/california/evidence"},
        {"name": "Quality", "path": "/california/quality"},
    ]
    assert "Plastiverse Live" in data["home"]
    assert "CA Plastics Research Atlas" in data["header"]
    assert 'aria-label="Toggle navigation menu"' in data["header"]
    assert 'name="q"' in data["header"]
    assert 'action="./search"' in data["header"]
    assert "data-atlas-site-search" in data["header"]
    assert "Search the Atlas" in data["header"]
    assert 'href="./california/about#how-to-cite">How to cite</a>' in data["footer"]
    # NOTIFY-AB: the footer links to the About page's Get updates section.
    assert '<li><a href="./california/about#get-updates">Get updates</a></li>' in data["footer"]
    # Owner 2026-11-17: the footer credits the creator; the former disclaimer was removed.
    assert 'Created by <a href="https://scottcoff.in"' in data["footer"]
    assert "not an official OEHHA" not in data["footer"]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_postbuild_places_skip_link_first_and_repairs_framework_sidebar() -> None:
    module_uri = (FRAMEWORK / "scripts" / "postbuild.mjs").resolve().as_uri()
    script = (
        f"import({json.dumps(module_uri)}).then(m => {{"
        f"const once=m.fixHtml({json.dumps(SAMPLE)},'california/index');"
        "const twice=m.fixHtml(once,'california/index');"
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
        "authors",
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


def test_skip_link_colors_override_framework_link_states() -> None:
    css = (FRAMEWORK / "src" / "design" / "shell.css").read_text(encoding="utf-8")
    states = ("link", "visited", "hover", "focus", "active")
    selector = r"a\.atlas-skip-link:" + r",\s*a\.atlas-skip-link:".join(states)
    rule = re.search(selector + r"\s*\{([^}]*)\}", css, flags=re.DOTALL)

    assert rule is not None
    assert "background: var(--atlas-brand-strong);" in rule.group(1)
    assert "color: var(--atlas-on-brand);" in rule.group(1)
    assert re.search(r"\.atlas-skip-link:focus\s*\{[^}]*transform: translate\(-50%, 0\)", css)


def test_async_resources_keep_the_footer_out_of_the_initial_viewport() -> None:
    css = (FRAMEWORK / "src" / "components" / "resources.css").read_text(encoding="utf-8")

    assert "min-height: calc(100vh - var(--observablehq-header-height));" in css
