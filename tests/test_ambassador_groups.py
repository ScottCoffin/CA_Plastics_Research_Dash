"""CG-6c browser module contract checks; API behavior is exercised by the Worker tests."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "framework/src/components/ambassador_groups.js"
WORKSPACE = ROOT / "framework/src/components/ambassador_workspace.js"
TAXONOMY = ROOT / "worker/src/groups_taxonomy.ts"
CSS = ROOT / "framework/src/components/ambassador_groups.css"
RUNTIME = ROOT / "tests/framework_ambassador_groups_runtime.mjs"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_group_taxonomy_matches_generated_worker_values() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required to check the group form taxonomy")
    result = subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            "const m=await import(process.argv[1]); console.log(JSON.stringify(m.GROUP_TAXONOMY));",
            MODULE.as_uri(),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    actual = json.loads(result.stdout)
    source = _text(TAXONOMY)
    for field, values in actual.items():
        match = re.search(
            rf"export const {field.upper()}: readonly string\[\] = \[(.*?)\];", source, re.S
        )
        assert match, field
        expected = re.findall(r'"([a-z0-9_]+)"', match.group(1))
        assert values == expected, field


def test_stream_uses_only_authenticated_workspace_api_and_separate_routes() -> None:
    module = _text(MODULE)
    workspace = _text(WORKSPACE)
    assert 'import {mountGroups} from "./ambassador_groups.js";' in workspace
    assert 'if (state.screen === "D") return mountGroups(host' in workspace
    assert 'plainCard("D", "Tag local groups"' in workspace
    assert 'ctx.api("/submissions", {method: "POST", body})' in module
    assert "`/groups/batch?region=${encodeURIComponent(ctx.region)}`" in module
    assert "ctx.api(`/groups/${action}`" in module
    assert 'kind: "group_tag"' in module and 'kind: "group_suggest"' in module
    assert "https://api.plastiverse.live" not in module
    assert not re.search(r"(localStorage|sessionStorage)\.", module)
    assert "document.cookie" not in module
    assert "safeUrl(group?.url)" in module


def test_stream_exposes_reviewable_forms_states_and_accessible_hooks() -> None:
    module = _text(MODULE)
    css = _text(CSS)
    for hook in (
        "data-g-tag-form",
        "data-g-submit",
        'data-g-action="renew"',
        'data-g-action="release"',
        "data-g-suggest-form",
        "data-g-suggest-submit",
        "aria-busy",
        'aria-label="Group progress"',
    ):
        assert hook in module
    assert "state.drafts[group.group_id]" in module
    assert "aria-live" in module or 'role="status"' in module
    assert '[data-g-evidence="${facet}"]' in module
    assert 'primary_activities: ["advocacy_campaigning"' in module
    assert "var(--pv-" in css
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)


def test_targeted_runtime_checks_pass() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for CG-6c runtime checks")
    result = subprocess.run(
        [node, str(RUNTIME)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
