from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CHECK = ROOT / "tests" / "monitoring_view_runtime.cjs"


def test_monitoring_view_runtime_regressions() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for tests/monitoring_view_runtime.cjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    subprocess.run([node, str(RUNTIME_CHECK)], cwd=ROOT, check=True)
