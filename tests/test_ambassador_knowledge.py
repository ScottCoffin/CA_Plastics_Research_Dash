"""Static checks for the ambassador "Add local knowledge" forms.

The pure helpers run in node (tests/framework_ambassador_knowledge_runtime.mjs). The kinds offered
by the form are checked against the Worker's KINDS in worker/src/submissions.ts, the live contract.
Nothing here calls the network or the Worker.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "framework" / "src" / "components"
KNOWLEDGE = COMPONENTS / "ambassador_knowledge.js"
KNOWLEDGE_CSS = COMPONENTS / "ambassador_knowledge.css"
WORKER_SUBMISSIONS = ROOT / "worker" / "src" / "submissions.ts"
RUNTIME_CHECK = ROOT / "tests" / "framework_ambassador_knowledge_runtime.mjs"

WORKER_KIND_RE = re.compile(
    r'^\s*(\w+): \{ stream: "(\w+)", required: \[([^\]]*)\], optional: \[([^\]]*)\]'
)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _worker_knowledge_kinds() -> dict[str, tuple[list[str], list[str]]]:
    """The Worker's knowledge kinds, minus correction, with required and optional fields."""
    kinds: dict[str, tuple[list[str], list[str]]] = {}
    for line in _text(WORKER_SUBMISSIONS).splitlines():
        match = WORKER_KIND_RE.match(line)
        if not match or match.group(2) != "knowledge":
            continue
        kind = match.group(1)
        if kind == "correction":
            continue
        required = re.findall(r'"(\w+)"', match.group(3))
        optional = re.findall(r'"(\w+)"', match.group(4))
        kinds[kind] = (required, optional)
    return kinds


def test_form_offers_the_worker_knowledge_kinds_minus_correction() -> None:
    worker = _worker_knowledge_kinds()
    assert len(worker) == 11, worker.keys()
    assert "correction" not in worker
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required to read KNOWLEDGE_KINDS")
    script = (
        "const m = await import(process.argv[1]); console.log(JSON.stringify(m.KNOWLEDGE_KINDS));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script, KNOWLEDGE.as_uri()],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    offered = json.loads(result.stdout)
    assert {item["kind"] for item in offered} == set(worker), "same kinds, no more, no fewer"
    for item in offered:
        required, optional = worker[item["kind"]]
        assert item["required"] == required, item["kind"]
        assert item["optional"] == optional, item["kind"]


def test_no_browser_storage_or_personal_data_in_the_browser() -> None:
    text = _text(KNOWLEDGE)
    assert not re.search(r"(localStorage|sessionStorage)\.", text)
    assert "localStorage" not in text and "sessionStorage" not in text
    assert "document.cookie" not in text


def test_the_only_worker_route_is_submissions_and_no_hard_coded_origin() -> None:
    text = _text(KNOWLEDGE)
    assert "https://api.plastiverse.live" not in text
    routes = set(re.findall(r'api\(\s*"(/[^"]*)"', text))
    assert routes == {"/submissions"}, routes
    assert 'ctx.api("/submissions", {method: "POST", body})' in text
    assert 'stream: "knowledge"' in text


def test_the_module_imports_no_sign_up_or_workspace_code() -> None:
    text = _text(KNOWLEDGE)
    imports = re.findall(r'^import .* from "([^"]+)";', text, flags=re.MULTILINE)
    assert imports == ["./atlas.js"], imports


def test_user_visible_text_avoids_internal_jargon() -> None:
    text = _text(KNOWLEDGE)
    for term in ("AMB-1", "stream C", "Stream C"):
        assert term not in text, term


def test_css_uses_tokens_and_is_scoped_under_the_ambassador_page() -> None:
    styles = _text(KNOWLEDGE_CSS)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", styles), "no hex colours"
    assert "min-height: 44px" in styles
    rules = re.sub(r"/\*.*?\*/", "", styles, flags=re.DOTALL)
    for prefix_match in re.finditer(r"([^{}]+)\{", rules):
        selector = prefix_match.group(1).strip()
        if selector.startswith("@") or not selector:
            continue
        for part in selector.split(","):
            assert part.strip().startswith(".am .kn-"), part.strip()
    for token in ("--pv-ink", "--pv-paper", "--pv-line", "--pv-wash", "--pv-coral-ink", "--pv-sun"):
        assert f"var({token})" in styles, token


def test_runtime_helpers_pass_in_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for tests/framework_ambassador_knowledge_runtime.mjs")
    result = subprocess.run(
        [node, str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout
