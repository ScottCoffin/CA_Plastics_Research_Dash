from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CHECK = ROOT / "tests" / "framework_resources_runtime.mjs"
PAGE = ROOT / "framework" / "src" / "resources.md"


def test_resources_page_has_no_minderoo_mention() -> None:
    assert "minderoo" not in PAGE.read_text(encoding="utf-8").lower()


def test_framework_resources_runtime_helpers() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for tests/framework_resources_runtime.mjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    # Shared helpers are gitignored copies of site/assets; create them as `npm run build` does.
    sync = ROOT / "framework" / "scripts" / "sync_shared.mjs"
    subprocess.run([node, str(sync)], cwd=ROOT, check=True, capture_output=True)
    subprocess.run([node, str(RUNTIME_CHECK)], cwd=ROOT, check=True)
