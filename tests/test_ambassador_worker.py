"""Runs the ambassador Worker test suite (worker/, vitest in workerd) when deps are installed.

Skipped when worker/node_modules is absent (CI does not install it yet; a CI job can be added later)
or when npm is not on PATH. The suite is offline: it fakes Turnstile and blocks all other fetches.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
NPM = shutil.which("npm")


@pytest.mark.skipif(
    not (WORKER / "node_modules").is_dir() or NPM is None,
    reason="needs worker/node_modules (npm ci in worker/) and npm on PATH",
)
def test_ambassador_worker_suite_passes() -> None:
    result = subprocess.run(
        [NPM, "test"],
        cwd=WORKER,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    output = (result.stdout + result.stderr).strip()
    assert result.returncode == 0, output[-4000:]
