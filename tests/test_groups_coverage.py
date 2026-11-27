"""Static checks for the community groups coverage and map (CG-12 part 1).

The pure helpers run in node (tests/framework_groups_coverage_runtime.mjs). These checks read the
sources as text: the stylesheet has no hex colours, the module never touches the DOM at import, and
visible sentences use plain public words, never internal codes. Nothing here calls the network.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "framework" / "src" / "components"
MODULE = COMPONENTS / "groups_coverage.js"
STYLES = COMPONENTS / "groups_coverage.css"
RUNTIME_CHECK = ROOT / "tests" / "framework_groups_coverage_runtime.mjs"

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
INTERNAL_TERMS = ("V-COV", "V-MAP", "CG-", "facet", "payload", "roster", "QC", "Tier-", "Codex")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_stylesheet_has_no_hex_colours() -> None:
    assert not HEX.findall(_text(STYLES)), "use --pv-* or --seq-* tokens, not hex literals"


def test_stylesheet_scopes_every_rule_under_gc() -> None:
    selectors = []
    for line in _text(STYLES).splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(("/*", "*", "@", "}")) and "{" in stripped:
            selectors.append(stripped.split("{", 1)[0])
    assert selectors, "no rules found"
    for selector in selectors:
        for part in selector.split(","):
            assert part.strip().startswith(".gc"), f"unscoped selector: {part.strip()}"


def test_module_does_not_touch_the_dom_at_import() -> None:
    # Top-level code is imports, constants and declarations; the DOM is used only inside functions.
    source = _text(MODULE)
    for token in ("document.", "window.", "localStorage"):
        assert token not in source.split("export function mountGroupsCoverage", 1)[0], token


def test_module_imports_only_the_shared_map_helpers() -> None:
    imports = re.findall(r"^import .* from \"([^\"]+)\";", _text(MODULE), flags=re.MULTILINE)
    assert imports == ["./world_map.js"]


def test_module_has_no_hex_colours() -> None:
    assert not HEX.findall(_text(MODULE)), "colours belong in groups_coverage.css"


def test_visible_sentences_use_no_internal_vocabulary() -> None:
    # Visible strings are the quoted sentences starting with a capital letter.
    sentences = []
    for line in _text(MODULE).splitlines():
        sentences += re.findall(r'"([A-Z][^"]*)"', line)
        sentences += re.findall(r"`([A-Z][^`]*)`", line)
    assert sentences, "no sentences found"
    for term in INTERNAL_TERMS:
        assert all(term not in sentence for sentence in sentences), term


def test_design_token_audit_passes() -> None:
    script = ROOT / "scripts" / "check_design_tokens.py"
    result = subprocess.run(
        ["py", "-3.14", str(script)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_runtime_checks_pass_in_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    result = subprocess.run(
        [node, str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "groups coverage runtime checks passed" in result.stdout
