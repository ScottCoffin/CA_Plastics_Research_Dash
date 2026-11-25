"""Runs the Node check for the Explore place helpers (AMB-1, framework runtime check)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CHECK = ROOT / "tests" / "framework_explore_places_runtime.mjs"


def test_explore_place_helpers_runtime() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for tests/framework_explore_places_runtime.mjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    result = subprocess.run(
        [node, str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout
