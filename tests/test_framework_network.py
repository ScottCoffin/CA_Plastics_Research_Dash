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

# Internal project vocabulary (scripts/check_public_text.py and the planning IDs).
SVG_NAMESPACE = "http://www.w3.org/2000/svg"  # an XML namespace, not a fetch
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


def test_view_imports_are_local_only() -> None:
    for path in (VIEW, MODEL):
        text = path.read_text(encoding="utf-8").replace(SVG_NAMESPACE, "")
        imports = re.findall(r"^import .* from \"([^\"]+)\";", text, re.MULTILINE)
        assert all(item.startswith("./") for item in imports), path.name
        assert "https://" not in text and "http://" not in text, path.name


def test_page_loads_network_component() -> None:
    text = PAGE.read_text(encoding="utf-8")
    assert '<link rel="stylesheet" href="./components/network.css">' in text
    assert 'import {mountNetwork} from "./components/network.js";' in text
    assert 'id="network-status"' in text and 'role="status"' in text
    assert "View as table" in text
    assert "Now in California only" in text


def test_css_is_scoped_to_network() -> None:
    text = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.DOTALL)
    selectors = [
        selector.strip()
        for block in re.findall(r"([^{}]+)\{", text)
        for selector in block.split(",")
        if selector.strip()
    ]
    assert selectors
    assert all(selector.startswith(".net-") for selector in selectors)
