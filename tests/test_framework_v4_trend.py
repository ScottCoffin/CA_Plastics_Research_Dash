from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "framework" / "src" / "components"
RUNTIME_CHECK = ROOT / "tests" / "framework_v4_trend_runtime.mjs"


def test_framework_v4_trend_runtime_helpers() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for tests/framework_v4_trend_runtime.mjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    # Shared helpers are gitignored copies of site/assets; create them as `npm run build` does.
    sync = ROOT / "framework" / "scripts" / "sync_shared.mjs"
    subprocess.run([node, str(sync)], cwd=ROOT, check=True, capture_output=True)
    subprocess.run([node, str(RUNTIME_CHECK)], cwd=ROOT, check=True)


def test_model_has_no_top_level_dom_access() -> None:
    text = (COMPONENTS / "v4_trend_model.js").read_text(encoding="utf-8")
    assert "document." not in text
    assert "window." not in text


def test_view_exports_mount_and_imports_shared_helpers() -> None:
    text = (COMPONENTS / "v4_trend.js").read_text(encoding="utf-8")
    assert re.search(
        r"export\s+async\s+function\s+mountV4Trend\s*\(\s*container,\s*idx,\s*initialRows\s*=\s*null\s*\)",
        text,
    )
    assert "seriesFromRows(initialRows, years, topics)" in text
    assert "seriesByTopic(countsFor(idx), years, topics)" in text
    assert 'import "./shared/topics.js";' in text
    assert "denominators.json" in text
    assert "Share comparison unavailable." in text
    assert "What this is and is not" in text
    assert "trend_global.json" not in text
    assert "Last 12 months: still being indexed" in text


def test_evidence_mount_uses_normalised_rows_for_initial_trend_and_table() -> None:
    evidence = (COMPONENTS / "evidence.js").read_text(encoding="utf-8")
    assert 'const trendPromise = mountV4Trend($("ev-v4"), index, plasticWorks);' in evidence
    assert 'mountWorksTable($("ev-table"), {' in evidence
    assert "initialRows: attachJournalMetrics(plasticWorks, journals)," in evidence
    assert "trend.update(app.lastIds.map((id) => app.detail.get(id)).filter(Boolean)," in evidence
    assert "{filtered: true});" in evidence
    assert re.search(
        r"catch\s*\{\s*\$\(\"ev-table\"\).*?mountV4Trend\(\$\(\"ev-v4\"\), index\)",
        evidence,
        re.DOTALL,
    )


def test_view_uses_no_chart_library_or_npm_import() -> None:
    text = (COMPONENTS / "v4_trend.js").read_text(encoding="utf-8")
    imports = re.findall(r"^import .* from \"([^\"]+)\";", text, re.MULTILINE)
    assert all(path.startswith("./") for path in imports)


def test_css_is_scoped_to_v4_trend() -> None:
    text = (COMPONENTS / "v4_trend.css").read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    selectors = [
        selector.strip()
        for block in re.findall(r"([^{}]+)\{", text)
        for selector in block.split(",")
        if selector.strip()
    ]
    assert selectors
    assert all(selector.startswith(".v4-trend") for selector in selectors)


def test_data_dictionary_documents_trend_global() -> None:
    text = (ROOT / "docs" / "DATA_DICTIONARY.md").read_text(encoding="utf-8")
    assert "### `site/data/global/trend_global.json`" in text
