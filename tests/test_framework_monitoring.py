from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CHECK = ROOT / "tests" / "framework_monitoring_runtime.mjs"
CLASSIC_PAGE = ROOT / "site" / "index.html"
COMPONENTS = ROOT / "framework" / "src" / "components"


def _code_lines(text: str) -> list[str]:
    # Compare code only: drop indentation, blank lines and the `export` keyword.
    stripped = (re.sub(r"\s+", "", line.replace("export ", "", 1)) for line in text.splitlines())
    return [line for line in stripped if line]


def _classic_helper_block() -> str:
    html = CLASSIC_PAGE.read_text(encoding="utf-8")
    match = re.search(r'<script id="monitoring-view-helpers">(.*?)</script>', html, re.S)
    assert match, "the classic page must keep the monitoring-view-helpers block"
    return match.group(1)


def test_ported_helpers_match_classic_block() -> None:
    # Drift guard: the Framework modules must carry the classic monitoringView and
    # monitoringMap code unchanged.
    classic_view, classic_map = _classic_helper_block().split("const monitoringMap", 1)
    classic_map = "const monitoringMap" + classic_map
    classic_view = classic_view.split("const monitoringView", 1)[1]
    view_module = (COMPONENTS / "monitoring_view.js").read_text(encoding="utf-8")
    map_module = (COMPONENTS / "svg_map.js").read_text(encoding="utf-8")
    ported_view = view_module.split("export const monitoringView", 1)[1]
    ported_map = map_module.split("export const monitoringMap", 1)[1]
    ported_map = "const monitoringMap" + ported_map.split("export function mapScreen", 1)[0]
    assert _code_lines("const monitoringView" + ported_view) == _code_lines(
        "const monitoringView" + classic_view
    )
    assert _code_lines(ported_map) == _code_lines(classic_map)


def test_framework_monitoring_runtime_regressions() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for tests/framework_monitoring_runtime.mjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    subprocess.run([node, str(RUNTIME_CHECK)], cwd=ROOT, check=True)
