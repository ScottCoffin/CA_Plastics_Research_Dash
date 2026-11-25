"""The global raster and the outlines share one projection: Natural Earth I.

The committed ``site/data/global/world_raster.json`` is laid over ``site/assets/world/world.json``
(landing_story.js draws the outlines on top of the pixels). These tests project known points with
``scripts/build_world_map.py`` and read the raster cell under each point, using the builder's own
sampling rule, so a land point must not fall in sea and the reverse.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
RASTER = ROOT / "site" / "data" / "global" / "world_raster.json"
WORLD = ROOT / "site" / "assets" / "world" / "world.json"
MW = 1290  # raster pixel width used by scripts/build_landing_assets.py
CELL = 7


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bwm = _load("build_world_map", ROOT / "scripts" / "build_world_map.py")


def _cell_value(raster: dict, world: dict, lon: float, lat: float) -> str:
    """The raster character at the cell the builder samples for this longitude and latitude."""
    ux, uy = bwm.to_pixels(lon, lat)
    k = MW / world["w"]
    c0, _ = world["crop"]
    col = int(ux * k // CELL)
    row = int((uy - c0) * k // CELL)
    lines = raster["world"].split("|")
    assert 0 <= row < len(lines) and 0 <= col < raster["cols"], (lon, lat)
    return lines[row][col]


@pytest.fixture(scope="module")
def raster() -> dict:
    return json.loads(RASTER.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def world() -> dict:
    return json.loads(WORLD.read_text(encoding="utf-8"))


def test_world_json_is_natural_earth_i(world: dict) -> None:
    assert world["w"] == bwm.WIDTH and world["h"] == bwm.HEIGHT == 520.0
    assert "Natural Earth I" in world["source"] and "countries-50m" in world["source"]


def test_raster_source_names_the_same_projection(raster: dict) -> None:
    assert "Natural Earth I" in raster["source"]


# Central Australia, Brazil, Germany, China, Canada and Kenya: land in the raster.
LAND = [
    ("central Australia", 133.9, -25.3),
    ("Brazil", -53.0, -10.0),
    ("Germany", 10.4, 51.2),
    ("China", 104.0, 35.0),
    ("Canada", -100.0, 60.0),
    ("Kenya", 37.9, 0.2),
]
# Mid-Pacific, mid-Atlantic, Indian Ocean and open sea west of California: sea ('.').
SEA = [
    ("mid-Pacific", -150.0, -15.0),
    ("mid-Atlantic", -35.0, 20.0),
    ("southern Indian Ocean", 75.0, -20.0),
    ("off California", -130.0, 37.0),
]


@pytest.mark.parametrize(("name", "lon", "lat"), LAND, ids=[x[0] for x in LAND])
def test_land_points_fall_on_land(
    raster: dict, world: dict, name: str, lon: float, lat: float
) -> None:
    assert _cell_value(raster, world, lon, lat) != ".", name


@pytest.mark.parametrize(("name", "lon", "lat"), SEA, ids=[x[0] for x in SEA])
def test_sea_points_fall_on_sea(
    raster: dict, world: dict, name: str, lon: float, lat: float
) -> None:
    assert _cell_value(raster, world, lon, lat) == ".", name


def test_california_centroid_is_the_california_cell(raster: dict, world: dict) -> None:
    assert _cell_value(raster, world, -119.4, 37.2) == "c"


def test_pixel_positions_match_the_frontend_formula(world: dict) -> None:
    # explore.js frameXY uses the same polynomial. tests/framework_explore_places_runtime.mjs
    # asserts the same numbers in the browser module, so the two projections cannot drift apart.
    assert bwm.to_pixels(0, 0) == pytest.approx((500.0, 260.0), abs=0.1)
    assert bwm.to_pixels(134.5, 7.5)[0] == pytest.approx(872.6, abs=0.1)
    assert bwm.to_pixels(134.5, 7.5)[1] == pytest.approx(235.9, abs=0.1)
    assert bwm.to_pixels(-119.4, 37.2)[0] == pytest.approx(190.4, abs=0.1)
    assert bwm.to_pixels(-119.4, 37.2)[1] == pytest.approx(140.0, abs=0.1)
    assert world["crop"][0] == pytest.approx(bwm.to_pixels(0, 84)[1], abs=0.1)
    assert world["crop"][1] == pytest.approx(bwm.to_pixels(0, -57)[1], abs=0.1)
