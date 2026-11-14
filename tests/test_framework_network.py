from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAMEWORK = ROOT / "framework"
COMPONENTS = FRAMEWORK / "src" / "components"
RUNTIME_CHECK = ROOT / "tests" / "framework_network_runtime.mjs"
MODEL = COMPONENTS / "network_model.js"
VIEW = COMPONENTS / "network.js"
CSS = COMPONENTS / "network.css"
PAGE = FRAMEWORK / "src" / "network.md"
CONFIG = FRAMEWORK / "observablehq.config.js"

# Pinned npm imports for the WebGL graph (exact versions; no range specifiers).
NPM_IMPORTS = {
    "graphology": "0.26.0",
    "sigma": "3.0.3",
    "graphology-layout-forceatlas2": "0.10.1",
}

# Internal project vocabulary (scripts/check_public_text.py and the planning IDs).
INTERNAL_ID = re.compile(
    r"\bS\d+\.\d+\b|\bSPK-\d+|\bEM-\d+|\bA2-|\bUX-\d+|\bAT-\d+|\bADR-|TODO", re.IGNORECASE
)


def _strip_js_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def test_framework_network_runtime_helpers() -> None:
    node = shutil.which("node")
    if node is None:
        raise AssertionError(
            "Node.js is required for tests/framework_network_runtime.mjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    subprocess.run([node, str(RUNTIME_CHECK)], cwd=ROOT, check=True)


def test_network_page_has_no_internal_ids() -> None:
    for path in (PAGE, VIEW, MODEL):
        text = _strip_js_comments(path.read_text(encoding="utf-8"))
        assert not INTERNAL_ID.search(text), path.name


def test_config_lists_network_after_experts() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    experts = text.index('{name: "Experts", path: "/experts"}')
    network = text.index('{name: "Collaboration network", path: "/network"}')
    assert experts < network
    assert (COMPONENTS.parent / "network.md").is_file()


def test_model_imports_are_local_only() -> None:
    text = MODEL.read_text(encoding="utf-8")
    imports = re.findall(r"^import .* from \"([^\"]+)\";", text, re.MULTILINE)
    assert all(item.startswith("./") for item in imports)
    assert "https://" not in text and "http://" not in text


def test_view_npm_imports_are_pinned_and_local_otherwise() -> None:
    text = VIEW.read_text(encoding="utf-8")
    imports = re.findall(r"^import .* from \"([^\"]+)\";", text, re.MULTILINE)
    npm = {}
    for item in imports:
        if item.startswith("npm:"):
            match = re.fullmatch(r"npm:(.+)@(\d+\.\d+\.\d+)", item)
            assert match, f"npm import must pin an exact version: {item}"
            npm[match.group(1)] = match.group(2)
        else:
            assert item.startswith("./"), item
    assert npm == NPM_IMPORTS
    assert "https://" not in text and "http://" not in text
    for host in ("cdn.jsdelivr.net", "unpkg.com", "esm.sh"):
        assert host not in text


def test_view_draws_with_sigma_not_hand_built_svg() -> None:
    text = VIEW.read_text(encoding="utf-8")
    assert "new Sigma(" in text
    assert "new Graph(" in text
    assert "forceAtlas2.assign(" in text
    assert "nodeReducer" in text and "edgeReducer" in text
    assert "createElementNS" not in text and "svgEl(" not in text
    assert "requestFullscreen" in text
    assert 'getContext("webgl' in text
    assert "mousemovebody" in text and "preventSigmaDefault" in text
    assert "animatedZoom" in text and "animatedUnzoom" in text and "animatedReset" in text
    assert "viewportToGraph" in text
    assert "experts#author=" in text
    assert "./shared/topics.js" in text


def test_view_keeps_filters_hash_and_table() -> None:
    text = VIEW.read_text(encoding="utf-8")
    assert "parseNetworkHash(window.location.hash)" in text
    assert "formatNetworkHash(state)" in text
    assert "shownEdgeWeights(" in text
    assert "sortByCollaborators(" in text
    assert "aria-pressed" in text


def test_page_loads_network_component() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="./components/network.css">' in text
    assert 'import {mountNetwork} from "./components/network.js";' in text
    assert 'id="network-status"' in text and 'role="status"' in text
    assert 'id="network-stage"' in text
    assert 'id="net-search"' in text and 'id="net-search-list"' in text
    assert 'id="net-colour"' in text and 'id="net-size"' in text
    assert 'id="net-layout"' in text and 'id="net-restore"' in text
    assert 'id="net-fullscreen"' in text
    assert "View as table" in text
    assert "Now in California only" in text
    assert "Hover or focus an expert" not in text


def test_page_copy_explains_zoom_drag_search_and_click() -> None:
    text = PAGE.read_text(encoding="utf-8")
    for phrase in ("zoom", "drag", "search", "Click a dot"):
        assert phrase in text, phrase


def test_chart_wrapper_is_labelled_div() -> None:
    text = PAGE.read_text(encoding="utf-8")
    match = re.search(r'<div id="network-chart"[^>]*aria-label="([^"]+)"', text)
    assert match and "graph" in match.group(1)


def test_css_is_scoped_to_network() -> None:
    text = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.DOTALL)
    selectors = [
        selector.strip()
        for block in re.findall(r"([^{}]+)\{", text)
        for selector in block.split(",")
        if selector.strip() and not selector.strip().startswith("@")
    ]
    assert selectors
    assert all(selector.startswith(".net-") for selector in selectors)
