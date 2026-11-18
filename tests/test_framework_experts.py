from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CHECK = ROOT / "tests" / "framework_experts_runtime.mjs"


def test_framework_experts_runtime() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for tests/framework_experts_runtime.mjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    # Shared helpers are gitignored copies of site/assets; create them as `npm run build` does.
    sync = ROOT / "framework" / "scripts" / "sync_shared.mjs"
    subprocess.run([node, str(sync)], cwd=ROOT, check=True, capture_output=True)
    subprocess.run([node, str(RUNTIME_CHECK)], cwd=ROOT, check=True)


def test_removed_preset_and_url_pill_stay_removed() -> None:
    page = (ROOT / "framework" / "src" / "california" / "experts.md").read_text(encoding="utf-8")
    component = (ROOT / "framework" / "src" / "components" / "experts.js").read_text(
        encoding="utf-8"
    )
    assert "rising-preset" not in page and "rising-preset" not in component
    assert "Find up-and-coming researchers" not in page
    assert "shareable by URL" not in page
    # The rising sort option stays; only the one-click shortcut was removed.
    assert '<option value="rising">' in page
    # URL state still round-trips through the hash.
    assert "formatExpertHash(state.filters)" in component


def test_more_filters_use_equal_columns_and_a_select_height_checkbox() -> None:
    page = (ROOT / "framework" / "src" / "california" / "experts.md").read_text(encoding="utf-8")
    css = (ROOT / "framework" / "src" / "components" / "experts.css").read_text(encoding="utf-8")
    assert '<div class="atlas-filters__grid expert-more-grid">' in page
    assert (
        "#experts-root .expert-more-grid { grid-template-columns: repeat(4, minmax(0, 1fr));" in css
    )
    assert 'class="expert-check-box" for="early-filter"' in page
    assert "#experts-root .expert-check-box {" in css
    check_block = css.split("#experts-root .expert-check-box {", 1)[1].split("}", 1)[0]
    assert "min-height: 2.5rem;" in check_block
    assert 'id="early-filter"' in page and 'id="now-filter"' in page
