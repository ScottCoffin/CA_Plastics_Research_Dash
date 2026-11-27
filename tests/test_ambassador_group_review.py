"""Static checks for the group tag checks on the moderation page (CG-7c).

The pure helpers run in node (tests/framework_ambassador_group_review_runtime.mjs). These
checks read the sources as text: the reason list must equal REVIEW_REASON in the Worker, the five
fields and their vocabulary must equal ambassador_groups.js, the page must mount the section, and
no submitted text is written as HTML. Nothing here calls the network.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
COMPONENTS = SRC / "components"
PAGE = SRC / "ambassador_moderation.md"
MODULE = COMPONENTS / "ambassador_group_review.js"
STYLES = COMPONENTS / "ambassador_group_review.css"
GROUPS_JS = COMPONENTS / "ambassador_groups.js"
TAXONOMY_TS = ROOT / "worker" / "src" / "groups_taxonomy.ts"
RUNTIME_CHECK = ROOT / "tests" / "framework_ambassador_group_review_runtime.mjs"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _block(text: str, start: str, end: str = "\n};") -> str:
    """The text after `start` up to the line that closes the object literal (`end`)."""
    return text.split(start, 1)[1].split(end, 1)[0]


def _strings(fragment: str) -> list[str]:
    return re.findall(r'"([^"]*)"', fragment)


def _worker_reasons() -> list[str]:
    match = re.search(r"REVIEW_REASON[^=]*=\s*\[(.*?)\];", _text(TAXONOMY_TS), re.DOTALL)
    assert match, "REVIEW_REASON not found in worker/src/groups_taxonomy.ts"
    return _strings(match.group(1))


def _js_reason_codes() -> list[str]:
    block = _block(_text(MODULE), "export const REVIEW_REASONS = Object.freeze({", "\n});")
    return re.findall(r"^\s*(\w+): \{label:", block, re.MULTILINE)


def _js_array(text: str, name: str) -> list[str]:
    match = re.search(rf"export const {name} = \[(.*?)\];", text, re.DOTALL)
    assert match, f"{name} not found"
    return _strings(match.group(1))


def _js_facet_values(text: str, name: str) -> dict[str, list[str]]:
    block = _block(text, f"export const {name} = {{")
    return {key: _strings(body) for key, body in re.findall(r"(\w+): \[([^\]]*)\]", block)}


def test_reason_codes_equal_the_worker_list_in_order() -> None:
    assert _js_reason_codes() == _worker_reasons()
    assert _js_reason_codes() == [
        "evidence_contradicts",
        "better_evidence_found",
        "guide_rule",
        "activity_order",
        "slip",
        "other",
    ]


def test_fields_equal_tag_facets_in_ambassador_groups() -> None:
    module_fields = _js_array(_text(MODULE), "TAG_FACETS")
    groups_fields = _js_array(_text(GROUPS_JS), "TAG_FACETS")
    assert module_fields == groups_fields
    assert len(module_fields) == 5


def test_field_vocabulary_equals_group_taxonomy() -> None:
    taxonomy = _js_facet_values(_text(GROUPS_JS), "GROUP_TAXONOMY")
    values = _js_facet_values(_text(MODULE), "FACET_VALUES")
    for facet in _js_array(_text(MODULE), "TAG_FACETS"):
        assert values[facet] == taxonomy[facet], facet


def test_module_never_writes_submitted_text_as_html() -> None:
    text = _text(MODULE)
    assert "innerHTML" not in text
    assert "insertAdjacentHTML" not in text
    assert "outerHTML" not in text


def test_module_does_not_touch_the_dom_at_import() -> None:
    text = _text(MODULE)
    top_level = [line for line in text.splitlines() if line and not line[0].isspace()]
    assert all("document." not in line for line in top_level), "a top-level line touches the DOM"


def test_page_mounts_the_section_and_stylesheet() -> None:
    page = _text(PAGE)
    assert '<section class="sec grv" id="grv-root" aria-label="Group tag checks">' in page
    assert 'id="grv-status"' in page and 'id="grv-body"' in page
    assert 'href="./components/ambassador_group_review.css"' in page
    assert 'import {mountGroupReview} from "./components/ambassador_group_review.js";' in page
    assert 'mountGroupReview(document.querySelector("#grv-root"))' in page
    # The section sits after the moderation queue and before the page closes.
    assert page.index('id="mod-root"') < page.index('id="grv-root"') < page.index("</main>")


def test_page_stays_unlisted() -> None:
    page = _text(PAGE)
    assert 'content="noindex, nofollow"' in page
    assert "title: Moderation" in page


def test_styles_use_tokens_and_no_hex_literals() -> None:
    styles = _text(STYLES)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", styles)
    assert "var(--pv-" in styles


def test_no_internal_vocabulary_in_visible_text() -> None:
    # Visible strings use "check", "field" and "value", never the internal terms.
    # Sentences are quoted strings starting with a capital letter, matched one line at a time.
    sentences = []
    for line in (_text(MODULE) + _text(PAGE)).splitlines():
        sentences += re.findall(r'"([A-Z][^"]*)"', line)
    assert sentences, "no sentences found"
    for term in ("CG-7", "Tier-1", "Tier-2", "payload", "facet"):
        assert all(term not in sentence for sentence in sentences), term


def test_runtime_checks_pass_in_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for tests/framework_ambassador_group_review_runtime.mjs")
    result = subprocess.run(
        [node, str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout
