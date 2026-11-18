from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CHECK = ROOT / "tests" / "framework_policy_runtime.mjs"
POLICY_MD = ROOT / "framework" / "src" / "california" / "policy.md"
POLICY_CSS = ROOT / "framework" / "src" / "components" / "policy.css"


def test_framework_policy_runtime_helpers() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for tests/framework_policy_runtime.mjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    # Shared helpers are gitignored copies of site/assets; create them as `npm run build` does.
    sync = ROOT / "framework" / "scripts" / "sync_shared.mjs"
    subprocess.run([node, str(sync)], cwd=ROOT, check=True, capture_output=True)
    subprocess.run([node, str(RUNTIME_CHECK)], cwd=ROOT, check=True)


def test_opc_panel_replaces_the_placeholder() -> None:
    md = POLICY_MD.read_text(encoding="utf-8")
    assert "In preparation" not in md
    assert '<div id="policy-opc" class="opc-panel"></div>' in md
    assert "mountOpcActions();" in md


def test_policy_page_text_is_full_width() -> None:
    # style.css caps paragraphs at 70ch on other pages; policy.css lifts that cap on this page.
    css = POLICY_CSS.read_text(encoding="utf-8")
    assert (
        "#observablehq-main:has(#policy-timeline) :is(p, li, ol, ul, dd) { max-width: none; }"
        in css
    )
    assert "max-width: 70ch" not in css
