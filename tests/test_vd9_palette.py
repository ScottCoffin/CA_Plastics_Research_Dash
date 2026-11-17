"""VD-9: chart and map colours come from one JavaScript palette that mirrors tokens.css."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMP = ROOT / "framework" / "src" / "components"
TOKENS = ROOT / "framework" / "src" / "design" / "tokens.css"
PALETTE = COMP / "shared" / "palette.js"
# Modules whose colour constants must come from palette.js. Topic hues stay in shared/topics.js.
PALETTE_USERS = (
    "svg_map.js",
    "funding_viz_model.js",
    "network_model.js",
    "ev_heatmap_model.js",
    "funding.js",
    "funding_viz.js",
)
HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])")
SECONDARY = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#7A4E9B"]
OTHER = "#8a969c"


def _tokens() -> dict[str, str]:
    text = TOKENS.read_text(encoding="utf-8")
    pairs = re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", text)
    return {name: value.lower() for name, value in pairs}


def _palette() -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required to load framework/src/components/shared/palette.js")
    script = (
        "const m = await import(process.argv[1]);"
        "console.log(JSON.stringify({"
        "SECONDARY: m.SECONDARY, SECONDARY_ALL_PAIRS: m.SECONDARY_ALL_PAIRS, OTHER: m.OTHER,"
        " SEQ: m.SEQ, CHROME: m.CHROME, NEUTRAL_STEPS: m.NEUTRAL_STEPS,"
        " ramp: [m.rampFill(0), m.rampFill(1), m.rampFill(0.5)]}));"
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script, PALETTE.as_uri()],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def _luminance(hex_value: str) -> float:
    channels = [int(hex_value[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_sequential_ramp_and_chrome_equal_tokens() -> None:
    tokens = _tokens()
    palette = _palette()
    seq_names = [f"--seq-{step}" for step in range(100, 800, 100)]
    assert [value.lower() for value in palette["SEQ"]] == [tokens[name] for name in seq_names]
    chrome = palette["CHROME"]
    assert chrome["grid"].lower() == tokens["--atlas-line"]
    assert chrome["axis"].lower() == tokens["--atlas-muted"]
    assert chrome["text"].lower() == tokens["--atlas-text"]
    assert chrome["surface"].lower() == tokens["--atlas-surface"]
    assert chrome["sunken"].lower() == tokens["--atlas-sunken"]
    assert chrome["page"].lower() == tokens["--atlas-page"]
    assert re.search(
        r"--atlas-chart-grid:\s*var\(--atlas-line\)\s*;", TOKENS.read_text(encoding="utf-8")
    )


def test_secondary_set_has_seven_fixed_slots_and_all_pairs_is_the_first_six() -> None:
    palette = _palette()
    assert palette["SECONDARY"] == SECONDARY
    assert len({value.lower() for value in palette["SECONDARY"]}) == 7
    assert palette["SECONDARY_ALL_PAIRS"] == SECONDARY[:6]
    assert palette["OTHER"] == OTHER
    assert OTHER not in SECONDARY


def test_ramp_lightness_steps_down_and_lightest_step_reads_as_near_zero() -> None:
    palette = _palette()
    seq = palette["SEQ"]
    luminances = [_luminance(value) for value in seq]
    assert all(a > b for a, b in zip(luminances, luminances[1:]))
    # seq-100 is #e6e8ef (about 1.22:1 on white): still barely distinguishable from an empty cell.
    assert _contrast(seq[0], "#ffffff") < 1.3
    # rampFill runs end to end and interpolates; t = 0.5 lands exactly on the fourth step.
    assert palette["ramp"] == [seq[0], seq[-1], seq[3]]


@pytest.mark.parametrize("name", PALETTE_USERS)
def test_component_colour_constants_come_from_palette(name: str) -> None:
    text = (COMP / name).read_text(encoding="utf-8")
    assert HEX.findall(text) == [], f"{name} still has hex literals"
    assert 'from "./shared/palette.js"' in text
