"""GP-5 step 1: region-aware data URLs in framework/src/components/atlas.js.

The Node runtime checks live in tests/framework_region_data_url_runtime.mjs. This runner finds node
with shutil.which (skips when it is absent) and checks that REGION_SLUGS matches the tier A slugs
in regions/_registry.yml, the single source of truth for region slugs.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from atlas.regions.registry import regions

ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "framework" / "src" / "components" / "atlas.js"
RUNTIME = ROOT / "tests" / "framework_region_data_url_runtime.mjs"


def _registry_region_slugs() -> list[str]:
    # Tier A regions are the curated regions with a data folder (California, Norway, Belgium).
    # The root tier (global) has no data folder of its own and is not a region slug.
    return sorted(region.slug for region in regions(tier="A"))


def test_region_slugs_match_registry() -> None:
    source = ATLAS.read_text(encoding="utf-8")
    match = re.search(r"export const REGION_SLUGS = Object\.freeze\(\[([^\]]*)\]\)", source)
    assert match, "atlas.js must export REGION_SLUGS as Object.freeze([...])"
    slugs = sorted(re.findall(r'"([a-z0-9_-]+)"', match.group(1)))
    assert slugs == _registry_region_slugs()
    assert 'DEFAULT_REGION_SLUG = "california"' in source


def test_node_runtime_region_data_urls() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH (source ~/.bashrc puts it there)")
    result = subprocess.run(
        [node, str(RUNTIME), str(ATLAS), json.dumps(_registry_region_slugs())],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "region data URL runtime checks passed" in result.stdout
