"""BQ-V.3: the reusable global graph viewer (framework/src/components/graph_viewer.js).

Runs the Node helper checks (tests/framework_graph_viewer_runtime.mjs), static checks on the
component, stylesheet and dev page, and checks the committed graph files that the viewer loads.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "framework/src/components/graph_viewer.js"
MODEL = ROOT / "framework/src/components/graph_viewer_model.js"
STYLE = ROOT / "framework/src/components/graph_viewer.css"
DEV_PAGE = ROOT / "framework/src/dev_graph.md"
RUNTIME_CHECK = ROOT / "tests" / "framework_graph_viewer_runtime.mjs"
GRAPHS = ROOT / "site/data/global/graphs"


def test_runtime_helpers_under_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for tests/framework_graph_viewer_runtime.mjs")
    result = subprocess.run(
        [node, str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "27 checks passed" in result.stdout


def test_component_uses_the_shared_contract() -> None:
    text = COMPONENT.read_text(encoding="utf-8")
    assert 'import Graph from "npm:graphology@0.26.0";' in text
    assert 'import Sigma from "npm:sigma@3.0.3";' in text
    assert "npm:" not in re.sub(r'import [^\n]*"npm:[^"]+";', "", text)
    assert "export function mountGraph(root, options = {})" in text
    assert 'from "./graph_viewer_model.js"' in text
    assert "globalDataUrl(manifestPathFor(name))" in text
    assert "manifest.graphs?.[graphFileKey(name, phone)]" in text
    assert "globalDataUrl(`graphs/${entry.file}`)" in text
    assert "globalDataUrl(`graphs/${entry.layout_file}`)" in text


def test_works_graph_is_wired_into_the_viewer_and_explore() -> None:
    model = MODEL.read_text(encoding="utf-8")
    assert 'export const GRAPHS = Object.freeze(["institutions", "authors", "works"]);' in model
    assert '"graphs/works_manifest.json"' in model
    text = COMPONENT.read_text(encoding="utf-8")
    assert 'works: "Works"' in text
    assert "WORKS_SORTABLE" in text
    explore = (ROOT / "framework/src/components/explore.js").read_text(encoding="utf-8")
    labels = 'GRAPH_LABEL = {institutions: "Institutions", authors: "Authors", works: "Works"}'
    assert labels in explore
    assert '["authors", "institutions", "works"]' in explore
    assert 'globalDataUrl("graphs/works_manifest.json")' in explore
    assert "manifestNoteFor(graph, manifest)" in explore


def test_component_teardown_kills_the_renderer_and_listeners() -> None:
    text = COMPONENT.read_text(encoding="utf-8")
    assert "renderer?.kill()" in text
    assert "new MutationObserver" in text and "root.isConnected" in text
    assert "abort.abort()" in text
    assert "{signal" in text


def test_hash_prefix_and_note_options_are_wired() -> None:
    # explore mounts the viewer with hashPrefix "gv." so its scope= and view= keys survive;
    # the default
    # (no prefix) keeps the bare g/n/z/x/y keys that /dev_graph uses.
    text = COMPONENT.read_text(encoding="utf-8")
    assert 'const prefix = options.hashPrefix ?? "";' in text
    assert "hashPrefixOk(prefix)" in text
    assert "parseGraphHash(window.location.hash, prefix)" in text
    assert "x: state.x, y: state.y}, prefix, window.location.hash)" in text
    assert "options.note !== false" in text
    assert "if (ui.note) ui.note.textContent = manifestNoteFor(name, manifest);" in text
    model = MODEL.read_text(encoding="utf-8")
    assert 'export function formatGraphHash(state = {}, prefix = "", current = "")' in model
    assert "export function exportFiles(manifest, name)" in model


def test_canvas_is_focusable_and_table_fallback_exists() -> None:
    text = COMPONENT.read_text(encoding="utf-8")
    assert 'data-gv="stage" role="application" tabindex="0"' in text
    assert 'data-gv="table-toggle" aria-expanded="false"' in text
    assert "Show as table" in text and 'data-gv="table"' in text
    assert "aria-sort" in text and 'data-gv="filter"' in text
    assert "Unscreened search hits" in text


def test_motion_gate_and_wheel_rule() -> None:
    text = COMPONENT.read_text(encoding="utf-8")
    assert "prefers-reduced-motion: reduce" in text
    assert "motionOff" in text
    assert "event.ctrlKey || event.metaKey" in text
    assert "stopImmediatePropagation" in text
    assert "{capture: true" in text
    assert "clickNode" in text


def test_no_literal_data_paths_in_the_viewer() -> None:
    for path in (COMPONENT, MODEL):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"""["'`]/?data/""", text), path.name


def test_stylesheet_has_no_colour_literals() -> None:
    text = STYLE.read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", text)
    assert "url(" not in text
    assert "prefers-reduced-motion" in text


def test_dev_page_is_unlisted_and_noindex() -> None:
    page = DEV_PAGE.read_text(encoding="utf-8")
    assert page.startswith("---\n")
    assert "sidebar: false" in page
    assert '<meta name="robots" content="noindex, nofollow">' in page
    config = (ROOT / "framework/observablehq.config.js").read_text(encoding="utf-8")
    assert "dev_graph" not in config
    llms = (ROOT / "site/llms.txt").read_text(encoding="utf-8")
    assert "dev_graph" not in llms


def _manifest() -> dict:
    return json.loads((GRAPHS / "graphs_manifest.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("key", ["institutions", "institutions_phone", "authors", "authors_phone"])
def test_committed_graph_files_match_the_manifest(key: str) -> None:
    entry = _manifest()["graphs"][key]
    graph = json.loads((GRAPHS / entry["file"]).read_text(encoding="utf-8"))
    nodes = graph["nodes"]["rows"]
    fields = graph["nodes"]["fields"]
    assert graph["graph"] == key
    assert len(nodes) == entry["nodes"]
    assert all(len(row) == len(fields) for row in nodes)
    layout = (GRAPHS / entry["layout_file"]).read_bytes()
    assert len(layout) >= 8 * len(nodes)
    count = len(nodes)
    for source, target, weight in graph["edges"]["rows"]:
        assert 0 <= source < count and 0 <= target < count and source != target
        assert weight >= 1


def test_phone_layout_is_the_prefix_of_the_desktop_layout() -> None:
    manifest = _manifest()["graphs"]
    for name in ("institutions", "authors"):
        desktop = (GRAPHS / manifest[name]["layout_file"]).read_bytes()
        phone_entry = manifest[f"{name}_phone"]
        phone = (GRAPHS / phone_entry["layout_file"]).read_bytes()
        assert phone_entry["layout_file"] == manifest[name]["layout_file"]
        assert desktop[: 8 * phone_entry["nodes"]] == phone[: 8 * phone_entry["nodes"]]


def test_author_graph_carries_no_person_level_contact_fields() -> None:
    graph = json.loads((GRAPHS / "authors.json").read_text(encoding="utf-8"))
    assert graph["nodes"]["fields"] == ["id", "display_name", "country_code", "works", "community"]
    assert "email" not in json.dumps(graph).lower()


def test_works_graph_names_its_communities_by_topic() -> None:
    viewer = (ROOT / "framework" / "src" / "components" / "graph_viewer.js").read_text(
        encoding="utf-8"
    )
    # A works graph links similar texts, not collaborators.
    assert 'name === "works" ? "Topic community" : "Collaboration community"' in viewer
