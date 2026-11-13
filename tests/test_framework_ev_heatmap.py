from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "framework" / "src" / "components"
RUNTIME_CHECK = ROOT / "tests" / "framework_ev_heatmap_runtime.mjs"
MODEL = COMPONENTS / "ev_heatmap_model.js"
VIEW = COMPONENTS / "ev_heatmap.js"
CSS = COMPONENTS / "ev_heatmap.css"


def _strip_js_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def test_framework_ev_heatmap_runtime_helpers() -> None:
    node = shutil.which("node")
    if node is None:
        raise AssertionError(
            "Node.js is required for tests/framework_ev_heatmap_runtime.mjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    subprocess.run([node, str(RUNTIME_CHECK)], cwd=ROOT, check=True)


def test_model_has_no_dom_access() -> None:
    text = MODEL.read_text(encoding="utf-8")
    assert "document." not in text
    assert "window." not in text


def test_model_exports_public_api() -> None:
    text = MODEL.read_text(encoding="utf-8")
    for name in ("heatmapCells", "colorFor", "textInk", "escapeHtml"):
        assert re.search(rf"export\s+function\s+{name}\s*\(", text), name
    assert re.search(r"export\s+function\s+heatmapCells\s*\(rows,\s*mode\)", text)
    assert re.search(r"export\s+function\s+colorFor\s*\(count,\s*max\)", text)
    assert re.search(r"export\s+function\s+textInk\s*\(fill\)", text)
    assert "#f4f7f6" in text
    assert '"No matrix tag"' in text


def test_view_exports_mount_and_imports_shared_helpers() -> None:
    text = VIEW.read_text(encoding="utf-8")
    assert re.search(
        r"export\s+function\s+mountHeatmap\s*\(\s*container,\s*\{onCell\s*=\s*\(\)\s*=>\s*\{\}\}\s*=\s*\{\}\s*\)",
        text,
    )
    assert 'import "./shared/topics.js";' in text
    assert "window.AtlasTopics" in text
    assert "Topic × matrix" in text
    assert "Topic × time" in text
    assert 'aria-pressed="${key === mode}"' in text
    assert "No works match the current filters." in text
    assert "Works can carry several tags, so cells overlap and do not sum to the total." in text
    assert "Tags come from keyword rules and are provisional." in text


def test_view_imports_are_local_only() -> None:
    for path in (VIEW, MODEL):
        text = path.read_text(encoding="utf-8")
        imports = re.findall(r"^import .* from \"([^\"]+)\";", text, re.MULTILINE)
        assert all(item.startswith("./") for item in imports), path.name
        assert "https://" not in text and "http://" not in text, path.name


def test_no_top_level_view_variable() -> None:
    for path in (VIEW, MODEL):
        text = _strip_js_comments(path.read_text(encoding="utf-8"))
        assert not re.search(r"(?m)^\s*(const|let|var|function|class)\s+view\b", text), path.name


def test_public_text_has_no_internal_vocabulary() -> None:
    for path in (VIEW, MODEL):
        text = _strip_js_comments(path.read_text(encoding="utf-8"))
        assert not re.search(r"EM-\d|fixture|TODO", text, re.IGNORECASE), path.name


def test_css_is_scoped_to_ev_heatmap() -> None:
    text = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.DOTALL)
    selectors = [
        selector.strip()
        for block in re.findall(r"([^{}]+)\{", text)
        for selector in block.split(",")
        if selector.strip()
    ]
    assert selectors
    assert all(selector.startswith(".ev-heatmap") for selector in selectors)
