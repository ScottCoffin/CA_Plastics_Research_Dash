"""Static and runtime checks for the Community groups flows, participation and language views.

The pure helpers run in node (tests/framework_groups_flows_runtime.mjs). Its fixture mirrors
build_flows in src/atlas/groups/build.py, and test_fixture_matches_build_flows checks that mirror
against the real builder. The other checks read the sources as text: no colour literals, no
internal vocabulary in visible text, and the mount signature the page relies on. Nothing here
calls the network or starts a Python subprocess.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from atlas.groups.build import build_flows

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "framework" / "src" / "components"
MODULE = COMPONENTS / "groups_flows.js"
STYLES = COMPONENTS / "groups_flows.css"
RUNTIME_CHECK = ROOT / "tests" / "framework_groups_flows_runtime.mjs"

HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
# Words that belong to the working notes, not to a reader of the page.
INTERNAL_TERMS = (
    "Sankey",
    "sankey",
    "UpSet",
    "upset",
    "F5",
    "PPSR",
    "facet",
    "Facet",
    "Tier-1",
    "Tier 1",
    "V-SANKEY",
    "V-PART",
    "V-COOC",
    "V-LANG",
    "cg-flows",
    "flows.json",
    "precision card",
)
STRING_LITERAL = re.compile(r'"((?:[^"\\\n]|\\.)*)"|`([^`]*)`')


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code_lines(text: str) -> str:
    """The module without its // comment lines, so code notes are not scanned as visible text."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for tests/framework_groups_flows_runtime.mjs")
    return node


def test_module_and_styles_exist() -> None:
    assert MODULE.is_file()
    assert STYLES.is_file()
    assert RUNTIME_CHECK.is_file()


def test_no_colour_literals_in_module_or_styles() -> None:
    for path in (MODULE, STYLES):
        found = HEX_COLOUR.findall(_code_lines(_text(path)))
        assert not found, (
            f"{path.name} has colour literals {found}; use tokens or shared/palette.js"
        )


def test_styles_reference_only_defined_tokens() -> None:
    tokens = _text(ROOT / "framework" / "src" / "design" / "tokens.css")
    defined = set(re.findall(r"(--[\w-]+)\s*:", tokens))
    used = set(re.findall(r"var\((--[\w-]+)\)", _text(STYLES)))
    missing = sorted(used - defined)
    assert not missing, f"undefined tokens in groups_flows.css: {missing}"


def _token_values() -> dict[str, str]:
    """First definition of each token in tokens.css (the :root palette)."""
    values: dict[str, str] = {}
    for name, value in re.findall(
        r"(--[\w-]+)\s*:\s*([^;]+);", _text(ROOT / "framework" / "src" / "design" / "tokens.css")
    ):
        values.setdefault(name, value.strip())
    return values


def _resolve_token(name: str, values: dict[str, str]) -> str:
    value = values[name]
    alias = re.fullmatch(r"var\((--[\w-]+)\)", value)
    return _resolve_token(alias.group(1), values) if alias else value


def _relative_luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_relative_luminance(a), _relative_luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_every_background_has_a_text_pair_at_4_5_to_1() -> None:
    values = _token_values()
    css = re.sub(r"/\*.*?\*/", "", _text(STYLES), flags=re.DOTALL)
    checked = 0
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        background = re.search(r"(?<![\w-])background(?:-color)?\s*:\s*var\((--[\w-]+)\)", body)
        if not background:
            continue
        text = re.search(r"(?<![\w-])color\s*:\s*var\((--[\w-]+)\)", body)
        assert text, f"{selector.strip()} sets a background without a text colour token"
        fill = _resolve_token(background.group(1), values)
        ink = _resolve_token(text.group(1), values)
        ratio = _contrast(fill, ink)
        assert ratio >= 4.5, f"{selector.strip()}: {ink} on {fill} is {ratio:.2f}:1"
        checked += 1
    assert checked >= 1, "expected the empty-state pair to be checked"


def test_no_internal_vocabulary_in_visible_text() -> None:
    literals = [
        match.group(1) or match.group(2) or ""
        for match in STRING_LITERAL.finditer(_code_lines(_text(MODULE)))
    ]
    # ${...} interpolations are code (variable names), not visible text, so they are removed first.
    visible = [re.sub(r"\$\{[^}]*\}", "", text) for text in literals]
    leaked = [(term, text) for text in visible for term in INTERNAL_TERMS if term in text]
    assert not leaked, f"internal vocabulary in visible strings: {leaked}"


def test_mount_and_helpers_are_exported() -> None:
    text = _text(MODULE)
    assert "export function mountGroupsFlows(el, {flows = null, groups = []" in text
    assert "Plot = null" in text
    for name in (
        "stageBars",
        "flowConservation",
        "flowRows",
        "participationFacets",
        "combinationRows",
        "combinationPanels",
        "languagePanel",
        "languageRegionCounts",
    ):
        assert f"export function {name}(" in text, name


def test_module_imports_no_npm_packages() -> None:
    specifiers = re.findall(
        r'^\s*(?:import|export)[^;]*?from "([^"]+)"', _text(MODULE), flags=re.MULTILINE
    )
    assert specifiers, "expected the module to import its helpers"
    for specifier in specifiers:
        assert specifier.startswith(("./", "../")), specifier


def test_empty_state_message_is_the_agreed_wording() -> None:
    assert "EMPTY_MESSAGE" in _text(MODULE)
    composition = _text(COMPONENTS / "groups_composition.js")
    assert (
        'EMPTY_MESSAGE = "No groups are tagged yet. These charts fill in as volunteers tag groups."'
        in composition
    )


def test_runtime_checks_pass_in_node() -> None:
    result = subprocess.run(
        [_node(), str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_fixture_matches_build_flows() -> None:
    """The node fixture's flows blocks equal what the real builder writes for the same records."""
    result = subprocess.run(
        [_node(), str(RUNTIME_CHECK), "--dump-fixture"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    fixture = json.loads(result.stdout)
    built = build_flows(fixture["groups"], fixture["vocab"], generated_from="fixture")
    expected = fixture["flows"]
    assert built["sankey"] == expected["sankey"]
    assert built["participation"] == expected["participation"]
    assert built["activity_combinations"] == expected["activity_combinations"]
