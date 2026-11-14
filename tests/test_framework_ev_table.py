from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "framework" / "src" / "components"
RUNTIME_CHECK = ROOT / "tests" / "framework_ev_table_runtime.mjs"
MODEL = COMPONENTS / "ev_table_model.js"
VIEW = COMPONENTS / "ev_table.js"
CSS = COMPONENTS / "ev_table.css"


def _strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def test_framework_ev_table_runtime_helpers() -> None:
    node = shutil.which("node")
    if node is None:
        raise AssertionError(
            "Node.js is required for tests/framework_ev_table_runtime.mjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    subprocess.run([node, str(RUNTIME_CHECK)], cwd=ROOT, check=True)


def test_model_has_no_dom_access_or_imports() -> None:
    text = MODEL.read_text(encoding="utf-8")
    assert "document." not in text
    assert "window." not in text
    assert not re.search(r"^import\s", text, re.MULTILINE)


def test_view_exports_mount_and_recent_callout() -> None:
    text = VIEW.read_text(encoding="utf-8")
    mount = (
        r"export\s+function\s+mountWorksTable\s*\(\s*container,"
        r"\s*\{\s*today\s*=\s*new Date\(\),\s*hint\s*=\s*DEFAULT_HINT\s*\}\s*=\s*\{\}\s*\)"
    )
    assert re.search(mount, text)
    callout = r"export\s+function\s+renderRecentCallout\s*\(\s*container,\s*rows,\s*today"
    assert re.search(callout, text)
    assert "update(workIds)" in text


def test_view_loads_payloads_lazily_and_imports_shared_helpers() -> None:
    text = VIEW.read_text(encoding="utf-8")
    assert 'import "./shared/topics.js";' in text
    assert "works_detail.json" in text
    assert "work_text/abstracts.json" in text
    # The abstracts file is fetched from the abstract toggle, not at mount time.
    assert text.index("function fillAbstract") < text.index("loadAbstracts().then")
    assert text.count('loadJson("work_text/abstracts.json")') == 1
    assert "No abstract available" in text
    assert "No works match these filters." in text


def test_view_imports_only_local_modules() -> None:
    text = VIEW.read_text(encoding="utf-8")
    imports = re.findall(r"^import .* from \"([^\"]+)\";", text, re.MULTILINE)
    assert imports
    assert all(path.startswith("./") for path in imports)


def test_view_has_no_top_level_view_variable_or_cdn() -> None:
    text = VIEW.read_text(encoding="utf-8")
    assert not re.search(r"^\s*(const|let|var|function)\s+view\b", text, re.MULTILINE)
    for host in ("cdn.", "unpkg.", "jsdelivr", "cdnjs"):
        assert host not in text


def test_public_text_avoids_internal_vocabulary() -> None:
    for path in (MODEL, VIEW, CSS):
        text = path.read_text(encoding="utf-8")
        assert not re.search(r"\bEM-\d+\b", text), path
        assert not re.search(r"fixture|todo", text, re.IGNORECASE), path


def test_css_is_scoped_to_ev_table() -> None:
    text = _strip_comments(CSS.read_text(encoding="utf-8"))
    selectors = [
        selector.strip()
        for block in re.findall(r"([^{}]+)\{", text)
        for selector in block.split(",")
        if selector.strip()
    ]
    assert selectors
    assert all(selector.startswith((".ev-table-root", ".ev-recent")) for selector in selectors)


def test_css_has_no_media_queries_or_external_urls() -> None:
    text = CSS.read_text(encoding="utf-8")
    assert "@media" not in text
    assert "url(" not in text
    assert "@import" not in text
