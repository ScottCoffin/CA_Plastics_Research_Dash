"""VD-12 design snapshots: colourfulness maths, font rules and route list (no browser needed)."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "design_snapshots", ROOT / "scripts" / "design_snapshots.py"
)
assert _SPEC and _SPEC.loader
design_snapshots = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(design_snapshots)


def test_grey_image_has_zero_colourfulness() -> None:
    grey = [(128, 128, 128)] * 1000
    assert design_snapshots.colourfulness(grey) == 0.0
    assert design_snapshots.colourfulness_stats(grey) == (0.0, 0.0)


def test_two_colour_image_matches_hand_computed_value() -> None:
    # Half pure red, half pure blue. rg = R - G and yb = (R + G) / 2 - B:
    #   red  -> rg 255, yb 127.5;  blue -> rg 0, yb -255.
    #   mean rg 127.5, sd rg 127.5; mean yb -63.75, sd yb 191.25.
    #   M = sqrt(127.5^2 + 191.25^2) + 0.3 * sqrt(127.5^2 + 63.75^2)
    #     = sqrt(52832.8125) + 0.3 * sqrt(20320.3125) = 229.854 + 42.765 = 272.619
    pixels = [(255, 0, 0)] * 500 + [(0, 0, 255)] * 500
    m = design_snapshots.colourfulness(pixels)
    assert m > 0
    assert m == pytest.approx(math.hypot(127.5, 191.25) + 0.3 * math.hypot(127.5, 63.75))
    assert m == pytest.approx(272.619, abs=0.001)


def test_empty_image_has_zero_colourfulness() -> None:
    assert design_snapshots.colourfulness([]) == 0.0


def test_saturation_thresholds() -> None:
    def saturated(pixel: tuple[int, int, int]) -> float:
        return design_snapshots.colourfulness_stats([pixel])[1]

    assert saturated((255, 0, 0)) == 100.0  # S 1.0, V 1.0
    assert saturated((60, 0, 0)) == 0.0  # S 1.0 but V 0.235 is below 0.3
    assert saturated((200, 180, 180)) == 0.0  # S 0.1
    assert saturated((200, 100, 100)) == 0.0  # S exactly 0.5 is not above 0.5
    assert saturated((200, 90, 90)) == 100.0  # S 0.55


def test_image_metrics_matches_pixel_function(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    path = tmp_path / "two_colour.png"
    image = Image.new("RGB", (20, 10), (255, 0, 0))
    image.paste((0, 0, 255), (10, 0, 20, 10))
    image.save(path)
    pixels = [(255, 0, 0)] * 100 + [(0, 0, 255)] * 100
    assert design_snapshots.image_metrics(path) == pytest.approx(
        design_snapshots.colourfulness_stats(pixels)
    )


def test_font_problems_accepts_target_faces() -> None:
    target = {
        "h1": ["Archivo"],
        "h2": ["Archivo"],
        "p": ["Segoe UI"],
        "sidebar_link": ["Archivo"],
        "header": ["Archivo"],
    }
    assert design_snapshots.font_problems(target) == []


def test_font_problems_accepts_weight_variants_of_target_faces() -> None:
    weighted = {"h2": ["Archivo ExtraBold"], "p": ["Segoe UI Semibold"]}
    assert design_snapshots.font_problems(weighted) == []


def test_font_problems_accepts_archivo_body_text() -> None:
    # VD-25a: body text is Archivo too, so p may render Archivo or one of its weights.
    assert design_snapshots.font_problems({"p": ["Archivo"]}) == []
    assert design_snapshots.font_problems({"p": ["Archivo SemiBold"]}) == []


def test_font_problems_flags_banned_and_wrong_faces() -> None:
    legacy = {"h1": ["Palatino Linotype"], "p": ["Times New Roman"], "header": ["Arial"]}
    problems = design_snapshots.font_problems(legacy)
    assert "h1 renders Palatino Linotype" in problems
    assert "p renders Times New Roman" in problems
    assert "header renders Arial" in problems
    assert "h1 renders Palatino Linotype, not Archivo" in problems
    assert "p renders Times New Roman, not Archivo or the system face" in problems


def test_route_keys_match_baseline() -> None:
    baseline = json.loads(
        (ROOT / "docs" / "design" / "baseline_2026-11-14.json").read_text("utf-8")
    )
    assert list(design_snapshots.ROUTES) == list(baseline["routes"])


def test_entity_routes_use_the_brief_ids() -> None:
    assert design_snapshots.ROUTES["institution"] == "institution#inst=I84218800"
    assert design_snapshots.ROUTES["expert_profile"] == "expert.html#author=A5036007957"
