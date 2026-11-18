"""Offline tests for scripts/build_landing_assets.py (PLAT-2 landing assets).

Synthetic images live in tmp_path. The committed-output checks read the built
files under site/assets/landing/ and site/data/global/world_raster.json.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_landing_assets.py"
LANDING = ROOT / "site" / "assets" / "landing"
RASTER = ROOT / "site" / "data" / "global" / "world_raster.json"


def _load_script():
    name = "build_landing_assets"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ba = _load_script()


# ---------------------------------------------------------------- RNG and numeric helpers


@pytest.mark.parametrize(
    ("seed", "expected"),
    [
        # Printed by node 25 with the prototype formula
        # rng = s => () => { s = (s*1664525 + 1013904223) >>> 0; return s / 4294967296 }
        (91, (0.27133524371311069, 0.53260953840799630, 0.12798654288053513)),
        (55, (0.25738335633650422, 0.26727399253286421, 0.47848873864859343)),
        (77, (0.26590950973331928, 0.26275682612322271, 0.54207073012366891)),
        (3, (0.23723063012585044, 0.55067820404656231, 0.87365857698023319)),
    ],
)
def test_rng_matches_prototype_lcg(seed, expected):
    draw = ba.rng(seed)
    got = tuple(draw() for _ in range(3))
    assert got == pytest.approx(expected, rel=1e-15)


def test_rng_first_state_is_the_lcg_step():
    assert (91 * 1664525 + 1013904223) % 2**32 == 1165375998
    assert ba.rng(91)() == 1165375998 / 4294967296


def test_seed_count_clamps_and_rounds_half_up():
    assert ba.seed_count(100) == 6
    assert ba.seed_count(1430) == 7  # 6.5 rounds up, as Math.round does
    assert ba.seed_count(2200) == 10
    assert ba.seed_count(10_000) == 18


def test_key_alpha_follows_backdrop_formula():
    lum = np.array([0.0, 14.0, 27.0, 40.0, 60.0])
    assert ba.key_alpha(lum).tolist() == [0, 0, 128, 255, 255]


def test_key_blanket_keys_black_backdrop_and_keeps_rgb(tmp_path):
    rgb = np.zeros((2, 2, 3), dtype=np.uint8)
    rgb[0, 1] = (27, 27, 27)  # L = 27 keys to alpha 128
    rgb[1, 0] = (200, 40, 40)  # bright: fully opaque
    path = tmp_path / "blanket.png"
    Image.fromarray(rgb).save(path)
    keyed = ba.key_blanket(Image.open(path).convert("RGB"))
    out = np.asarray(keyed)
    assert out.shape == (2, 2, 4)
    assert out[0, 0, 3] == 0
    assert out[0, 1, 3] == 128
    assert out[1, 0, 3] == 255
    assert out[1, 0, :3].tolist() == [200, 40, 40]


# ---------------------------------------------------------------- item cut-outs


def _two_blob_sheet(blobs, size=(512, 256)):
    """RGBA sheet with opaque blobs. Blob cells are on the 4 px grid, inclusive."""
    img = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    img[..., :3] = 180
    for x0, y0, x1, y1 in blobs:
        img[y0 * 4 : (y1 + 1) * 4, x0 * 4 : (x1 + 1) * 4, 3] = 255
    return Image.fromarray(img)


def test_components_and_matching_on_two_blobs():
    # A and B are 1 cell apart, so they are separate components. C is too small
    # to keep. D sits more than MATCH_MAX from every LAYOUT row.
    sheet = _two_blob_sheet([(20, 10, 29, 19), (31, 10, 40, 19), (60, 5, 61, 5), (70, 40, 79, 49)])
    layout = [(100, 60, 0, 0, 0, 1), (150, 60, 0, 0, 0, 1), (900, 900, 0, 0, 0, 1)]
    alpha = np.asarray(sheet.getchannel("A").resize((128, 64), Image.Resampling.BOX))
    comps = ba.label_components(alpha > ba.ALPHA_MIN)
    assert sorted(c.area for c in comps) == [2, 100, 100, 100]
    kept = ba.match_components(comps, layout)
    assert [k for k, _ in kept] == [0, 1]
    assert all(c.area == 100 for _, c in kept)


def test_cut_items_masks_neighbours_and_seeds_are_sprite_local():
    sheet = _two_blob_sheet([(20, 10, 29, 19), (31, 10, 40, 19)])
    layout = [(100, 60, 0, 0, 0, 1), (150, 60, 0, 0, 0, 1)]
    items = ba.cut_items(sheet, layout, fr=ba.rng(91))
    assert [it.k for it in items] == [0, 1]
    first = items[0]
    assert first.sprite.size == (56, 56)  # 14 cells of 4 px: bbox plus 2 cells each side
    arr = np.asarray(first.sprite)
    assert arr[20, 30, 3] == 255  # inside the item
    assert arr[20, 54, 3] == 0  # neighbour B (sheet column 31) is cut away
    assert len(first.seeds) == ba.seed_count(100) == 6
    assert all(-0.5 <= gx <= 14.5 and -0.5 <= gy <= 14.5 for gx, gy in first.seeds)


def test_assign_ord_is_position_after_sorting_by_value():
    assert ba.assign_ord([0.3, 0.1, 0.2]) == [2, 0, 1]


def test_pack_atlas_leaves_two_px_padding():
    sprite = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
    items = [ba.Item(k, sprite, 1, [], 1.0, 0.0, 0.0) for k in range(2)]
    atlas, pos = ba.pack_atlas(items)
    assert pos[0] == (2, 2)
    assert pos[1] == (2 + 10 + 2, 2)
    assert atlas.size[0] == ba.ATLAS_W


def test_place_centres_on_target_and_rotates_clockwise_on_screen():
    # 20 x 10 sprite with an opaque marker in its four right-hand columns.
    sprite = Image.new("RGBA", (20, 10), (0, 0, 0, 0))
    sprite.paste((255, 255, 255, 255), (16, 0, 20, 10))
    size = (200, 200)
    upright = np.asarray(ba._place(sprite, 100, 100, 0.0, 1.0, size))
    assert upright[100, 107, 3] > 200  # marker sits right of centre, on the centre row
    assert upright[100, 89, 3] == 0
    # Quarter turn clockwise on screen (y down): the right side moves to the bottom.
    turned = np.asarray(ba._place(sprite, 100, 100, np.pi / 2, 1.0, size))
    assert turned[108, 100, 3] > 200
    assert turned[92, 100, 3] == 0


def test_blanket_seeds_come_from_bright_grid_cells():
    rgb = np.zeros((128, 256, 3), dtype=np.uint8)
    rgb[32:96, 64:192] = (120, 110, 100)  # bright block on the 8 px grid, cols 8-23, rows 4-11
    seeds = ba.blanket_seeds(Image.fromarray(rgb), ba.rng(91))
    assert len(seeds) == ba.BLANKET_SEEDS
    for gx, gy in seeds:
        assert 7.5 <= gx < 24.5
        assert 3.5 <= gy < 12.5


# ---------------------------------------------------------------- world raster


def _synthetic_world():
    return {
        "w": 1000.0,
        "h": 486.7,
        "crop": [2.0, 436.7],
        "sphere": "M0,2L920,2L920,436.7L0,436.7Z",
        "ca": "M150,150L170,150L170,170L150,170Z",
        "ca_bbox": [140.0, 140.0, 180.0, 180.0],
        "countries": [
            {"id": "1", "iso_a2": "FR", "d": "M100,100L300,100L300,200L100,200Z"},
            {"id": "2", "iso_a2": "XX", "d": "M500,100L700,100L700,200L500,200Z"},
            {"id": "3", "iso_a2": None, "d": "M800,100L900,100L900,200L800,200Z"},
        ],
    }


def _cell(ux_target, uy_target):
    """Column and row whose centre is nearest the target, on the raster grid."""
    k = ba.MW / 1000.0
    col = int(ux_target * k // ba.CELL)
    row = int((uy_target - 2.0) * k // ba.CELL)
    return row, col


def test_step_tiers_use_fixed_log_breaks():
    countries = [{"iso_a2": iso} for iso in ("A", "B", "C", "D", "E", "F")] + [{"iso_a2": None}]
    counts = {"A": 29, "B": 30, "C": 299, "D": 300, "E": 2999, "F": 3000}
    tiers = ba.step_tiers(countries, counts)
    assert "A" not in tiers  # under 30 works: the wash step "0"
    assert [tiers[k] for k in "BCDEF"] == list("11223")


def test_world_raster_marks_sea_california_and_countries():
    world = _synthetic_world()
    tiers = {"FR": "3"}  # France in the top shading step
    raster = ba.world_raster(world, tiers)
    lines = raster["world"].split("|")
    assert raster["cols"] == 184 and raster["rows"] == 80 and raster["cell"] == 7
    assert len(lines) == raster["rows"]
    assert all(len(line) == raster["cols"] for line in lines)
    row, col = _cell(160, 160)
    assert lines[row][col] == "c"  # inside the California outline
    row, col = _cell(250, 150)
    assert lines[row][col] == "3"  # France: the shading step
    row, col = _cell(550, 150)
    assert lines[row][col] == "0"  # country with no works
    row, col = _cell(850, 150)
    assert lines[row][col] == "0"  # no ISO code
    row, col = _cell(50, 50)
    assert lines[row][col] == "."  # sea inside the sphere
    row, col = _cell(950, 150)
    assert lines[row][col] == "."  # outside the sphere


def test_ca_raster_splits_west_and_local_cells():
    # A square outline covering the whole bounding box: the top row starts west of the
    # diagonal split and ends east of it, so both letters appear.
    bbox = [140.0, 140.0, 180.0, 180.0]
    outline = ba._rings("M140,140L180,140L180,180L140,180Z")
    grid = ba._ca_raster(bbox, outline).split("|")
    assert grid[0][0] == "w" and grid[0][-1] == "l"
    assert {c for line in grid for c in line} == {"w", "l"}


# ---------------------------------------------------------------- papers and licence guard


@pytest.mark.parametrize(
    "licence",
    [
        "This article is licensed under CC-BY 4",
        "This is an open access article under the CC BY license",
        "Open Access This article is licensed under a Creative Commons Attribution 4",
    ],
)
def test_licence_guard_accepts_cc_by(licence):
    ba.assert_cc_by(licence)


@pytest.mark.parametrize(
    "licence",
    [
        "This work is licensed under CC BY-NC 4.0",
        "Licensed under Creative Commons Attribution-NonCommercial 4",
        "All rights reserved",
    ],
)
def test_licence_guard_rejects_nc_and_non_cc_by(licence):
    with pytest.raises(ValueError):
        ba.assert_cc_by(licence)


# ---------------------------------------------------------------- committed outputs


def test_committed_picnic_items_sorted_with_unique_ord():
    picnic = json.loads((LANDING / "picnic.json").read_text(encoding="utf-8"))
    items = picnic["items"]
    assert [it["k"] for it in items] == sorted(it["k"] for it in items)
    assert sorted(it["ord"] for it in items) == list(range(len(items)))
    assert len(items) == 21
    atlas_w, atlas_h = picnic["atlas"]["w"], picnic["atlas"]["h"]
    for it in items:
        assert it["x"] + it["w"] <= atlas_w and it["y"] + it["h"] <= atlas_h
        assert len(it["seeds"]) == ba.seed_count(it["area"])
    assert len(picnic["blanket"]["seeds"]) == ba.BLANKET_SEEDS


def test_committed_landing_assets_respect_budgets():
    first = LANDING / "picnic_first_paint.webp"
    assert first.stat().st_size <= ba.FIRST_PAINT_MAX
    total = sum(p.stat().st_size for p in LANDING.rglob("*.webp"))
    assert total <= ba.LANDING_MAX


def test_committed_papers_are_cc_by_and_present():
    papers = json.loads((LANDING / "papers.json").read_text(encoding="utf-8"))
    assert len(papers) == 15
    for paper in papers:
        ba.assert_cc_by(paper["licence"])
        assert (LANDING / paper["src"]).is_file()


def test_committed_world_raster_has_consistent_shape():
    raster = json.loads(RASTER.read_text(encoding="utf-8"))
    world_lines = raster["world"].split("|")
    assert len(world_lines) == raster["rows"]
    assert all(len(line) == raster["cols"] for line in world_lines)
    assert set("".join(world_lines)) <= set(".c0123")
    assert raster["fetched_at"]
