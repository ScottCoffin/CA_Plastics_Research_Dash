"""Static and runtime checks for the Community groups composition views (CG-12 part 2).

The pure helpers run in node (tests/framework_groups_composition_runtime.mjs), which uses a 30-group
fixture and a precision card fixture. The checks here read the sources as text: no colour literals
(colours come from tokens), no internal vocabulary in visible text, and the mount signature the page
relies on. Nothing here calls the network.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "framework" / "src" / "components"
MODULE = COMPONENTS / "groups_composition.js"
STYLES = COMPONENTS / "groups_composition.css"
RUNTIME_CHECK = ROOT / "tests" / "framework_groups_composition_runtime.mjs"

HEX_COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b")
# Words that belong to the working notes, not to a reader of the page.
INTERNAL_TERMS = (
    "V-HEAT",
    "V-COMP",
    "V-EVID",
    "Tier-1",
    "Tier 1",
    "facet",
    "precision card",
    "cg-precision",
)
STRING_LITERAL = re.compile(r'"((?:[^"\\\n]|\\.)*)"|`([^`]*)`')


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _code_lines(text: str) -> str:
    """The module without its // comment lines, so code notes are not scanned as visible text."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


def test_module_and_styles_exist() -> None:
    assert MODULE.is_file()
    assert STYLES.is_file()
    assert RUNTIME_CHECK.is_file()


def test_no_colour_literals_in_module_or_styles() -> None:
    for path in (MODULE, STYLES):
        found = HEX_COLOUR.findall(_code_lines(_text(path)))
        assert not found, f"{path.name} has colour literals {found}; use tokens from tokens.css"


def test_styles_reference_only_defined_tokens() -> None:
    tokens = _text(ROOT / "framework" / "src" / "design" / "tokens.css")
    defined = set(re.findall(r"(--[\w-]+)\s*:", tokens))
    used = set(re.findall(r"var\((--[\w-]+)\)", _text(STYLES)))
    missing = sorted(used - defined)
    assert not missing, f"undefined tokens in groups_composition.css: {missing}"


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
    assert checked >= 6, "expected the header, tile and frame pairs to be checked"


def test_no_internal_vocabulary_in_visible_text() -> None:
    literals = []
    for match in STRING_LITERAL.finditer(_code_lines(_text(MODULE))):
        literals.append(match.group(1) or match.group(2) or "")
    leaked = [(term, text) for text in literals for term in INTERNAL_TERMS if term in text]
    assert not leaked, f"internal vocabulary in visible strings: {leaked}"


def test_mount_and_helpers_are_exported() -> None:
    text = _text(MODULE)
    assert "export function mountGroupsComposition(el, {groups" in text
    assert "Plot = null, d3 = null" in text
    assert 'id: "all"' in text or "All tagged groups" in text
    for name in (
        "centralityBySector",
        "activityByRegion",
        "compositionTree",
        "evidenceRows",
        "labelFits",
    ):
        assert f"export function {name}(" in text, name


def test_module_imports_no_npm_packages() -> None:
    for line in _text(MODULE).splitlines():
        if line.startswith("import "):
            assert 'from "./' in line or 'from "../' in line, line


def test_empty_state_message_is_the_agreed_wording() -> None:
    assert '"No groups are tagged yet. These charts fill in as volunteers tag groups."' in _text(
        MODULE
    )


def test_runtime_checks_pass_in_node() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for tests/framework_groups_composition_runtime.mjs")
    result = subprocess.run(
        [node, str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout
