"""REG-1: region page (Norway, Belgium) static checks and Node runtime tests of the pure helpers.

The shared component components/region_page.js renders docs/REGION_PAGES.md (region-v1).
These tests use tests/fixtures/region_v1_fixture.json, so they run before the data worker's
site/data/<slug>/region.json exists. No browser and no build here (the build runs in the gate).
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
COMPONENT = SRC / "components" / "region_page.js"
STYLE = SRC / "components" / "region_page.css"
ATLAS = SRC / "components" / "atlas.js"
EXPLORE = SRC / "components" / "explore.js"
FIXTURE = ROOT / "tests" / "fixtures" / "region_v1_fixture.json"
PAGES = {"norway": SRC / "norway" / "index.md", "belgium": SRC / "belgium" / "index.md"}
POSTBUILD = ROOT / "framework" / "scripts" / "postbuild.mjs"
HEX_COLOUR = re.compile(
    r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![0-9A-Za-z_-])"
)

NODE_SCRIPT = """
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {pathToFileURL} from "node:url";

const mod = await import(pathToFileURL(process.argv[2]).href);
const atlas = await import(pathToFileURL(process.argv[3]).href);
const payload = JSON.parse(readFileSync(process.argv[4], "utf8"));

// Normalisation: sections in contract order, partial year split off, text kept.
const model = mod.normalizeRegion(payload);
assert.ok(model, "fixture must normalise");
assert.equal(model.name, "Norway");
const order = ["funding", "monitoring", "policy", "research_networks", "local_terms", "geography"];
assert.deepEqual(model.sections.map((s) => s.id), order);
assert.deepEqual(model.years.rows, [{year: 2024, count: 180}, {year: 2025, count: 210}]);
assert.deepEqual(model.years.partial, {year: 2026, count: 96, partial: true});
assert.equal(model.worksTotal, 1234);
assert.equal(model.worksWithPmid, 567);

// Wrong schema or missing name: no model, so the page shows the error state.
assert.equal(mod.normalizeRegion({...payload, schema_version: "region-v0"}), null);
assert.equal(mod.normalizeRegion({...payload, name: undefined}), null);

// Section order follows the contract even when the payload lists them differently.
const reversed = {...payload, sections: [...payload.sections].reverse()};
const ids = (m) => m.sections.map((s) => s.id);
assert.deepEqual(ids(mod.normalizeRegion(reversed)), ids(model));

// Links: only http(s); OpenAlex author ids become public author pages.
assert.equal(mod.safeUrl("javascript:alert(1)"), null);
assert.equal(mod.safeUrl("https://example.org/a"), "https://example.org/a");
assert.equal(mod.openalexAuthorUrl("A123"), "https://openalex.org/A123");
assert.equal(mod.openalexAuthorUrl("https://openalex.org/A9"), "https://openalex.org/A9");
assert.equal(mod.openalexAuthorUrl("x1"), null);

// Badges: anything not confirmed is a placeholder.
assert.equal(mod.badgeText("to_confirm"), "To be confirmed by a local researcher");
assert.equal(mod.badgeText("placeholder"), "To be confirmed by a local researcher");
assert.equal(mod.badgeText("confirmed"), "Confirmed by a local researcher");

// Text is rendered as written (no silent rewriting; the data is checked instead).
assert.equal(mod.publicText("Expert Group on Marine Litter"), "Expert Group on Marine Litter");
assert.equal(mod.publicText(null), "");

// Bars and years.
assert.equal(mod.barPercent(50, 200), 25);
assert.equal(mod.barPercent(5, 0), 0);
assert.match(mod.worksChartSvg(model.years, "Norway"), /rg-bar-partial/);
assert.equal(mod.worksChartSvg({rows: [], partial: null}, "Norway").includes("<svg"), false);

// Full render: every section, the placeholder badge, the partial hatch and the scope note.
const html = mod.renderRegion(model, "https://plastiverse.example/ambassadors");
assert.ok(html.includes("In preparation with local collaborators"));
assert.ok(html.includes("Help build this page"));
assert.ok(html.includes("Figures are unscreened search hits from OpenAlex"));
assert.ok(html.includes('href="https://openalex.org/A1"'));
assert.ok(html.includes('href="https://ror.org/00example1"'));
assert.ok(!html.includes('href="javascript'));
assert.ok(!/expert/i.test(html), "public text must not say expert");
assert.equal((html.match(/To be confirmed by a local researcher/g) || []).length >= 6, true);
assert.ok(html.includes('id="research_networks"'));
assert.ok(html.includes("No candidates listed yet."));
assert.ok(html.includes("Partial year"));
assert.ok(html.includes('aria-pressed="true"'));

// GP-5: a listed institution links to its institution page only when the region export holds it.
const listed = {...model, institutions: [
  {id: "I1", name: "Lab", works: 3},
  {id: "I2", name: "Other", works: 1},
]};
const linked = mod.renderRegion(listed, "/a", new Set(["I1"]));
assert.ok(linked.includes('href="./institution#inst=I1"'));
assert.ok(!linked.includes("inst=I2"));
assert.ok(linked.includes('href="./institutions"'));
assert.ok(!mod.renderRegion(listed, "/a").includes("./institution#inst="));

// No works: the empty note appears and the page still renders its sections.
const empty = mod.renderRegion(mod.normalizeRegion({...payload, stats: {works_total: 0}}), "/a");
assert.ok(empty.includes("No works for this region"));
assert.ok(empty.includes('id="funding"'));

// Data URLs go through the site root and never hard-code data/ paths in pages.
assert.equal(atlas.regionFileUrl("norway", "region.json"), "http://localhost/data/norway/region.json");
assert.equal(atlas.siteRoot("http://localhost/norway/").href, "http://localhost/");
assert.equal(atlas.siteRoot("http://localhost/california/authors").href, "http://localhost/");
assert.equal(atlas.siteRoot("http://localhost/app/norway/").href, "http://localhost/");
assert.equal(atlas.siteRoot("http://localhost/explore").href, "http://localhost/");
console.log("region runtime ok");
"""


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH (source ~/.bashrc puts it there)")
    return node


def test_node_runtime_helpers_render_the_region_fixture(tmp_path: Path) -> None:
    node = _node()
    script = tmp_path / "region_runtime.mjs"
    script.write_text(NODE_SCRIPT, encoding="utf-8")
    result = subprocess.run(
        [node, str(script), str(COMPONENT), str(ATLAS), str(FIXTURE)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "region runtime ok" in result.stdout


def test_fixture_is_region_v1_with_six_sections() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "region-v1"
    assert payload["status"] == "in_preparation"
    assert payload["screening_status"] == "unscreened_query_hit"
    assert set(payload["stats"]) == {
        "works_total",
        "first_year",
        "last_complete_year",
        "works_with_pmid",
    }
    assert [s["id"] for s in payload["sections"]] == [
        "funding",
        "monitoring",
        "policy",
        "research_networks",
        "local_terms",
        "geography",
    ]
    assert len(payload["top_topics"]) <= 10 and len(payload["top_institutions"]) <= 15
    assert len(payload["top_researchers"]) <= 15 and len(payload["partner_countries"]) <= 10
    assert sum(1 for row in payload["works_by_year"] if row["partial"]) == 1


@pytest.mark.parametrize("slug", ["norway", "belgium"])
def test_region_page_is_a_thin_mount_of_the_shared_component(slug: str) -> None:
    text = PAGES[slug].read_text(encoding="utf-8")
    assert text.startswith("---\n") and f"title: {slug.capitalize()} " in text
    assert "sidebar: false" in text and "header: false" in text and "footer: false" in text
    assert '<link rel="stylesheet" href="../components/region_page.css">' in text
    assert 'import {mountRegion} from "../components/region_page.js";' in text
    assert f'mountRegion(document.querySelector("#rg-root"), "{slug}")' in text
    assert 'href="../ambassadors"' in text
    assert "Figures" not in text  # the footer note comes from region.json, not from the page
    assert not re.search(r"\bexperts?\b", text, re.IGNORECASE)


def test_region_folders_and_pages_are_registered_for_check_at5() -> None:
    spec = importlib.util.spec_from_file_location("check_at5", ROOT / "scripts" / "check_at5.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert {"california", "norway", "belgium"} <= set(module.REGIONS)
    assert set(module.REGION_PAGES) == {"norway/index", "belgium/index"}
    assert "explore.md" in module.GLOBAL_PAGES  # the explore page keeps its global registration


def _split_selectors(prelude: str) -> list[str]:
    """Split on commas outside parentheses, so :where(h1, h2) stays whole."""
    parts, depth, current = [], 0, ""
    for char in prelude:
        depth += (char == "(") - (char == ")")
        if char == "," and depth == 0:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    parts.append(current.strip())
    return [part for part in parts if part]


def test_stylesheet_is_scoped_and_uses_tokens_only() -> None:
    css = STYLE.read_text(encoding="utf-8")
    assert not HEX_COLOUR.search(css), "colours come from design/tokens.css"
    preludes = re.findall(r"([^{}]+)\{", re.sub(r"/\*.*?\*/", "", css, flags=re.S))
    for prelude in preludes:
        if prelude.strip().startswith("@"):
            continue
        for selector in _split_selectors(prelude):
            assert selector.startswith(("body:has(.rg)", ".rg", "#observablehq-main .rg")), selector


def test_explore_links_norway_to_its_region_page_and_postbuild_describes_it() -> None:
    assert 'href: "./norway/"' in EXPLORE.read_text(encoding="utf-8")
    text = POSTBUILD.read_text(encoding="utf-8")
    assert '"norway/index":' in text and '"belgium/index":' in text


def test_atlas_region_file_helper_is_the_only_region_data_path() -> None:
    text = ATLAS.read_text(encoding="utf-8")
    assert "export function regionFileUrl(slug, file)" in text
    assert "data/${" in text and "siteRoot()" in text
