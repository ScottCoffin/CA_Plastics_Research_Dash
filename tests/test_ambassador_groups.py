"""CG-6c browser module contract checks (AMB-GROUPS-UX wording).

API behavior is exercised by the Worker tests.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "framework/src/components/ambassador_groups.js"
PICKERS = ROOT / "framework/src/components/ambassador_groups_pickers.js"
WORKSPACE = ROOT / "framework/src/components/ambassador_workspace.js"
TAXONOMY = ROOT / "worker/src/groups_taxonomy.ts"
CSS = ROOT / "framework/src/components/ambassador_groups.css"
RUNTIME = ROOT / "tests/framework_ambassador_groups_runtime.mjs"
WORKER_GROUPS = ROOT / "worker/src/groups.ts"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _visible_lines(path: Path) -> str:
    """Source lines without JS comments: the text that can reach the page or code strings."""
    lines = [
        line for line in _text(path).splitlines() if not line.lstrip().startswith(("//", "/*", "*"))
    ]
    return "\n".join(lines)


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


def test_same_as_answers_match_worker_constant() -> None:
    pattern = r"export const SAME_AS_ANSWERS = \[(.*?)\];"
    worker = re.search(pattern, _text(WORKER_GROUPS), re.S)
    assert worker, "SAME_AS_ANSWERS in worker/src/groups.ts"
    expected = re.findall(r'"([a-z_]+)"', worker.group(1))
    assert expected == ["same", "different", "unsure"]
    module = re.search(pattern, _text(MODULE), re.S)
    assert module, "SAME_AS_ANSWERS in the group form module"
    assert re.findall(r'"([a-z_]+)"', module.group(1)) == expected


def test_stream_uses_only_authenticated_workspace_api_and_separate_routes() -> None:
    module = _text(MODULE)
    workspace = _text(WORKSPACE)
    assert 'import {mountGroups, mountGroupSuggest} from "./ambassador_groups.js";' in workspace
    assert 'if (state.screen === "D") return mountGroups(host' in workspace
    assert 'if (state.screen === "E") return mountGroupSuggest(host' in workspace
    assert (
        'plainCard("D", "Tag local groups", "Check assigned organisations\' public pages '
        'and tag them", "Open tasks")' in workspace
    )
    assert (
        'plainCard("E", "Suggest a missing group", "Add an organisation that is missing '
        'from the list", "Suggest a group")' in workspace
    )
    assert "Tag assigned organisations or suggest a missing group" not in workspace
    assert 'ctx.api("/submissions", {method: "POST", body})' in module
    assert "`/groups/batch?region=${encodeURIComponent(ctx.region)}`" in module
    assert "`${batchPath}&group_id=${encodeURIComponent(group.group_id)}`" in module
    assert 'kind: "group_tag"' in module and 'kind: "group_suggest"' in module
    assert "export function mountGroupSuggest(host, ctx)" in module
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
        'data-g-action="next"',
        'data-g-action="previous"',
        "data-g-suggest-form",
        "data-g-suggest-submit",
        "aria-busy",
        'aria-label="Group progress"',
        "data-g-picker-add",
        "data-g-picker-remove",
        "[data-g-org][aria-pressed",
        "data-g-date-change",
        "data-g-facet-quote",
        'data-g-field="name_correction"',
    ):
        assert hook in module
    assert "state.drafts[group.group_id]" in module
    assert 'label for="g-name-correction">Correct the name (optional)</label>' in module
    assert 'set(".g-name-correction", no)' in module
    assert "aria-live" in module or 'role="status"' in module
    assert 'data-g-field="quote"' in module
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


def test_pool_holds_are_invisible_and_second_tags_get_a_status_message() -> None:
    module = _text(MODULE)
    for old_control in ('data-g-action="renew"', 'data-g-action="release"', "Lease until"):
        assert old_control not in module
    assert "Someone else just tagged this group. Your answers still help check agreement." in module
    assert 'class="g-success" role="status"' in module
    assert "title=" not in module


def test_visible_wording_has_no_iso_codes_or_internal_ids() -> None:
    for path in (MODULE, PICKERS):
        visible = _visible_lines(path)
        assert not re.search(r"ISO", visible), path.name
        assert not re.search(r"(CG-\d|A[1-4]-|F\d)", visible), path.name
    assert "Website languages" in _text(MODULE) and "Places (optional" in _text(MODULE)
    assert "Country code" not in _text(MODULE)


def test_quote_and_picker_wording_is_plain_and_evidence_is_one_block() -> None:
    module = _text(MODULE)
    assert "Words from their page that show their plastics work (up to 25 words)" in module
    assert "Add a quote for this" in module
    assert "Page you read" in module
    assert module.count('<fieldset class="g-evidence g-wide"><legend>Evidence</legend>') == 1
    assert "Evidence · " not in module
    assert "The page does not state this" not in module
    assert 'rel="noopener noreferrer"' in module and 'target="_blank"' in module
    assert "Open their website" in module


def test_not_stated_plastics_and_plain_labels_in_the_form() -> None:
    module = _text(MODULE)
    assert "data-g-not-stated-wrap" in module and "Their pages do not mention plastics" in module
    assert 'NOT_STATED_CENTRALITY = ["incidental", "none"]' in module
    assert "Choose one from the list" in module
    labels = ROOT / "framework/src/components/group_labels.js"
    label_text = _text(labels)
    assert "Advocacy and campaigns" in label_text and "Clean-ups and litter removal" in label_text
    assert "groupLabel" in module and "NICE(" not in module
    for path in (MODULE, labels):
        visible = _visible_lines(path)
        assert not re.search(r"(CG-\d|A[1-4]-|F\d)", visible), path.name


def test_suggestion_box_is_optional_hints_loaded_once_and_never_filled() -> None:
    module = _text(MODULE)
    assert 'getJson("groups/suggestions.json")' in module
    assert 'data?.schema === "cg-suggestions-v1"' in module
    assert "Suggestions to check (from Wikidata)" in module
    assert "These are hints, not tags. Confirm each value on the group's own pages" in module
    assert "before you use it." in module
    assert "Matched by name only. Check that this is the same organisation." in module
    assert "Look it up in an official register:" in module
    assert "Suggestions to check" not in _text(CSS)
