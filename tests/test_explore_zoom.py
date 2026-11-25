"""Checks for the /explore map: zoom helpers (node runtime), controls in the frame, boundary layers.

The runtime part runs tests/framework_explore_zoom_runtime.mjs. The static parts read
framework/src/components/explore.js and explore.css as text, because the map renders in the browser.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPLORE_JS = ROOT / "framework" / "src" / "components" / "explore.js"
EXPLORE_CSS = ROOT / "framework" / "src" / "components" / "explore.css"
RUNTIME_CHECK = ROOT / "tests" / "framework_explore_zoom_runtime.mjs"
WORLD_MAP_JS = ROOT / "framework" / "src" / "components" / "world_map.js"


def gesture_body() -> str:
    """The shared gesture wiring (world_map.js attachMapGestures), moved from explore.js."""
    source = WORLD_MAP_JS.read_text(encoding="utf-8")
    return source[source.index("export function attachMapGestures(") :]


def test_explore_zoom_helpers_runtime() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for tests/framework_explore_zoom_runtime.mjs")
    result = subprocess.run(
        [node, str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_zoom_controls_sit_inside_the_map_frame_and_are_labelled() -> None:
    js = EXPLORE_JS.read_text(encoding="utf-8")
    frame = js.index('<div class="mapbox" id="mapbox"')
    group = js.index('<div class="map-zoom" role="group" aria-label="Map zoom">')
    # The group is inside the mapbox element: it comes after the frame opens and before the
    # sibling strip that follows the frame.
    assert frame < group < js.index('<div class="astrip">')
    for control, label in (
        ("zoom-in", "Zoom in"),
        ("zoom-out", "Zoom out"),
        ("zoom-reset", "Reset map view"),
    ):
        match = re.search(
            rf'<button type="button" class="btn" id="{control}" aria-label="([^"]+)"', js
        )
        assert match and match.group(1) == label, control
    # The overlay has no zoom buttons outside the frame.
    assert js.count('id="zoom-in"') == 1 and js.count('id="zoom-out"') == 1


def test_map_takes_keyboard_focus_and_the_overlay_is_positioned_in_the_frame() -> None:
    js = EXPLORE_JS.read_text(encoding="utf-8")
    assert re.search(r'<svg class="map" id="map" tabindex="0"', js)
    css = EXPLORE_CSS.read_text(encoding="utf-8")
    assert re.search(r"\.gx \.mapbox \{ position: relative;", css)
    assert re.search(r"\.gx \.map-zoom \{ position: absolute;", css)


def test_zoom_wiring_covers_wheel_drag_pinch_double_click_and_keys() -> None:
    js = EXPLORE_JS.read_text(encoding="utf-8")
    body = gesture_body()
    assert "attachMapGestures(mapEl" in js and "function wireZoom()" in js
    for event in ("wheel", "dblclick", "pointerdown", "pointermove", "keydown"):
        assert f'addEventListener("{event}"' in body, event
    assert "passive: false" in body
    for key in ('"+"', '"-"', "ArrowLeft", '"0"'):
        assert key in body, key
    assert "ZOOM_MAX" in js and "clampView(next, frame)" in body
    # A drag ends with a click that must not select a country.
    assert "if (drag.moved) return;" in js


def test_boundary_layers_are_drawn_dashed_and_dotted_and_credited() -> None:
    js = EXPLORE_JS.read_text(encoding="utf-8")
    css = EXPLORE_CSS.read_text(encoding="utf-8")
    assert '<path class="bd" d="${BOUNDARY.disputed}"/>' in js
    assert '<path class="pg" d="${BOUNDARY.pacific}"/>' in js
    assert re.search(
        r"\.gx \.map \.bd \{[^}]*stroke-dasharray: 4 3;[^}]*vector-effect: non-scaling-stroke", css
    )
    assert re.search(r"\.gx \.map \.pg \{[^}]*stroke-dasharray: 0 3\.2", css)
    assert "Disputed boundary, as drawn by Natural Earth" in js
    assert "Boundaries: Natural Earth, including its disputed-area lines." in js
    assert "assets/world/world.json" in js


def test_wheel_is_gated_and_touch_scrolls_the_page() -> None:
    js = EXPLORE_JS.read_text(encoding="utf-8")
    css = EXPLORE_CSS.read_text(encoding="utf-8")
    body = gesture_body()
    gate = body.index("if (!wheelZooms(e, active))")
    # The page keeps scrolling: preventDefault comes only after the gate.
    assert gate < body.index("e.preventDefault();", gate)
    assert "setHint(WHEEL_HINT)" in body and "setHint(TOUCH_HINT)" in body
    # The how-to hint stays until the map is activated (owner, 2026-11-25); never timed.
    assert 'hint.classList.toggle("show", !active)' in body and "setTimeout" not in body
    assert "touch-action: none" not in css
    assert "touch-action: pan-y" in css
    hint = js.index('<div class="map-hint" id="map-hint" aria-live="polite">')
    assert js.index('<div class="mapbox" id="mapbox"') < hint < js.index('<div class="astrip">')
    assert re.search(r"\.gx \.map-hint \{[^}]*pointer-events: none", css)
    # Focus and Escape drive the active state; a press outside deactivates it.
    for needle in (
        'addEventListener("focusin"',
        'addEventListener("focusout"',
        'setActive("escape")',
        'setActive("outside")',
    ):
        assert needle in body or needle in js, needle
