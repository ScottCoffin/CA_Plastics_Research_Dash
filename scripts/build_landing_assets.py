"""Build the offline assets for the PLAT-2 global landing page.

Ports two pieces of offline work from the approved prototype:

* the picnic composition in ``.impeccable/sketches/src/story_engine7.js``
  (``LAYOUT``, ``fracture`` and ``compose``): the keyed blanket, the item
  cut-outs, the item atlas, the first-paint image and ``picnic.json``;
* the world and California rasters in ``.impeccable/sketches/src/story.py``;
* the footer logo animation: the owner's MP4 is copied and its poster is written from the static
  PNG (both made by ``src/create_plastiverse_animation.py``; this script does not render them).

The build is deterministic (fixed LCG seeds, no network, no randomness).
Run with ``py -3.14 scripts/build_landing_assets.py``.
"""

from __future__ import annotations

import io
import json
import math
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SKETCH = ROOT / ".impeccable" / "sketches"
BLANKET_SRC = SKETCH / "scene" / "web" / "blanket.jpg"
BLANKET_SIDECAR = SKETCH / "scene" / "blanket.png.json"
ITEMS_SRC = SKETCH / "scene" / "web" / "picnic_items.png"
ITEMS_SIDECAR = SKETCH / "scene" / "picnic_items.png.json"
PAPERS_DIR = SKETCH / "papers" / "web"
CREDITS = SKETCH / "papers" / "credits.json"
LOGO_SRC = SKETCH / "brand" / "logo_564.png"
MOTION_SRC = ROOT / "src" / "plastiverse_live_high_res.mp4"  # owner-supplied, see provenance
MOTION_STILL_SRC = ROOT / "src" / "plastiverse_live_static.png"  # final frame of the animation
WORLD_JSON = ROOT / "site" / "assets" / "world" / "world.json"
COUNTS_JSON = ROOT / "site" / "data" / "global" / "global_counts.json"
OUT = ROOT / "site" / "assets" / "landing"
RASTER_OUT = ROOT / "site" / "data" / "global" / "world_raster.json"

# Item cut-outs: story_engine7.js compose() and fracture().
GRID = 4  # item grid, sheet px per cell (compose f)
ALPHA_MIN = 110  # foreground threshold on the item grid
MIN_AREA = 30  # smallest component kept, in cells
MATCH_MAX = 140.0  # max distance from a component centre to a LAYOUT row, sheet px
PAD_CELLS = 2  # sprite bounding box padding, cells
SEED_AREA = 220
SEED_RANGE = (6, 18)
BLANKET_GRID = 8  # blanket grid (fracture F)
BLANKET_SEEDS = 26
BLANKET_L_MIN = 40
KEY_LO, KEY_SPAN = 14, 26  # backdrop key: alpha = clamp((L - 14) / 26)
ATLAS_PAD = 2
ATLAS_W = 1024

# Output settings.
BLANKET_Q, ITEMS_Q, PAPER_Q, LOGO_Q = 82, 82, 80, 90
FIRST_Q, FIRST_Q_MIN = 80, 40  # first paint: highest quality within FIRST_PAINT_MAX
FIRST_W = 1600
PAPER_H = 560
MOTION_PX = 564  # logo animation poster: the footer logo's size (logo_564.webp)
SHADOW_OFFSET = (5, 7)
SHADOW_SIGMA = 8.0  # canvas shadowBlur 16 is a Gaussian sigma of 8
SHADOW_ALPHA = 0.45
FIRST_PAINT_MAX = 250_000  # bytes
LANDING_MAX = 2_500_000  # bytes, all landing WebP files

# World raster: story.py.
MW = 1290
CELL = 7
ZC = 0.26

# Picnic layout (story_engine7.js lines 33-38): sheet centre x, y; blanket x, y; rotation; scale.
LAYOUT: list[tuple[float, float, float, float, float, float]] = [
    (190, 355, 330, 320, 0, 0.78),
    (530, 355, 1190, 330, 0, 0.78),
    (865, 355, 720, 790, 0, 0.78),
    (1095, 315, 120, 330, 0.08, 0.7),
    (1197, 315, 525, 350, -0.1, 0.7),
    (1295, 315, 1375, 330, 0.1, 0.7),
    (280, 880, 770, 470, -0.06, 0.72),
    (290, 625, 1130, 640, -0.45, 0.75),
    (635, 610, 525, 570, 0.35, 0.75),
    (760, 610, 615, 600, -0.2, 0.75),
    (1005, 625, 330, 320, -0.25, 0.62),
    (1325, 625, 1190, 330, 0.35, 0.62),
    (130, 100, 600, 205, 0.2, 0.8),
    (330, 100, 1010, 820, -0.3, 0.8),
    (530, 100, 240, 650, 0.1, 0.8),
    (730, 100, 960, 190, -0.1, 0.8),
    (925, 100, 1395, 620, 0.2, 0.8),
    (1350, 250, 660, 150, 0.95, 0.7),
    (1440, 250, 1040, 150, 0.5, 0.7),
    (715, 880, 1335, 860, 0, 0.72),
    (1180, 880, 330, 865, 0.15, 0.62),
]


# ---------------------------------------------------------------- numeric helpers


def rng(seed: int):
    """Port of the prototype LCG: s = (s * 1664525 + 1013904223) mod 2**32; return s / 2**32."""
    state = [seed]

    def draw() -> float:
        state[0] = (state[0] * 1664525 + 1013904223) & 0xFFFFFFFF
        return state[0] / 4294967296

    return draw


def js_round(x: float) -> int:
    """JavaScript Math.round: halves go up (Python's round() goes to even)."""
    return math.floor(x + 0.5)


def clamp(x: float, lo: float, hi: float) -> float:
    return min(max(x, lo), hi)


def seed_count(area: int) -> int:
    """Number of Voronoi seeds for an item of ``area`` cells."""
    return js_round(clamp(area / SEED_AREA, *SEED_RANGE))


def luminance(rgb: np.ndarray) -> np.ndarray:
    """L = .3R + .59G + .11B on the last axis, same operation order as the prototype."""
    return 0.3 * rgb[..., 0] + 0.59 * rgb[..., 1] + 0.11 * rgb[..., 2]


def key_alpha(lum: np.ndarray) -> np.ndarray:
    """Backdrop key: round(255 * clamp((L - 14) / 26, 0, 1)) as uint8."""
    t = np.clip((lum - KEY_LO) / KEY_SPAN, 0.0, 1.0)
    return np.floor(255.0 * t + 0.5).astype(np.uint8)


# ---------------------------------------------------------------- blanket and seeds


def key_blanket(blanket_rgb: Image.Image) -> Image.Image:
    """Return the blanket as RGBA with its black backdrop keyed out."""
    rgb = np.asarray(blanket_rgb.convert("RGB"), dtype=np.uint8)
    alpha = key_alpha(luminance(rgb.astype(np.float64)))
    return Image.fromarray(np.dstack([rgb, alpha]))


def _pick_seeds(cells_xy: np.ndarray, n: int, draw) -> list[tuple[float, float]]:
    """Port of the seed loop in fracture(): index, then x jitter, then y jitter, per seed."""
    seeds = []
    for _ in range(n):
        qx, qy = cells_xy[int(math.floor(draw() * len(cells_xy)))]
        jx = draw()
        jy = draw()
        seeds.append((qx + jx - 0.5, qy + jy - 0.5))
    return seeds


def _shard_draws(cells_xy: np.ndarray, seeds: list[tuple[float, float]], draw) -> None:
    """Consume the draws fracture() makes per shard (dir, dist, rs, thr).

    A shard exists for each seed that owns at least one core cell. Owners are the
    nearest seed, first index winning ties, as in the prototype's strict '<' loop.
    """
    sx = np.array([s[0] for s in seeds])
    sy = np.array([s[1] for s in seeds])
    dx = cells_xy[:, 0:1] - sx[None, :]
    dy = cells_xy[:, 1:2] - sy[None, :]
    owner = np.argmin(dx * dx + dy * dy, axis=1)
    for _ in range(4 * len(np.unique(owner))):
        draw()


def blanket_seeds(blanket_rgb: Image.Image, draw) -> list[tuple[float, float]]:
    """26 Voronoi seeds on the 8 px blanket grid, over cells with L > 40."""
    rgb = blanket_rgb.convert("RGB")
    gw, gh = math.ceil(rgb.width / BLANKET_GRID), math.ceil(rgb.height / BLANKET_GRID)
    small = np.asarray(rgb.resize((gw, gh), Image.Resampling.BOX), dtype=np.float64)
    ys, xs = np.nonzero(luminance(small) > BLANKET_L_MIN)  # row-major, as in the prototype
    cells_xy = np.stack([xs, ys], axis=1).astype(np.float64)
    return _pick_seeds(cells_xy, BLANKET_SEEDS, draw)


# ---------------------------------------------------------------- item cut-outs


@dataclass
class Component:
    """A 4-connected foreground component on the item grid."""

    cells: list[int] = field(default_factory=list)  # flat indices, in flood-fill pop order
    x0: int = 1 << 30
    y0: int = 1 << 30
    x1: int = -1
    y1: int = -1
    sx: int = 0
    sy: int = 0

    @property
    def area(self) -> int:
        return len(self.cells)


def label_components(fg: np.ndarray) -> list[Component]:
    """Flood-fill like compose(): stack pops, neighbours pushed in order L, R, U, D."""
    h, w = fg.shape
    flat = fg.ravel().tolist()
    lab = [-1] * (w * h)
    comps: list[Component] = []
    for i in range(w * h):
        if not flat[i] or lab[i] >= 0:
            continue
        cid = len(comps)
        comp = Component()
        lab[i] = cid
        stack = [i]
        while stack:
            j = stack.pop()
            x, y = j % w, j // w
            comp.cells.append(j)
            comp.sx += x
            comp.sy += y
            comp.x0, comp.x1 = min(comp.x0, x), max(comp.x1, x)
            comp.y0, comp.y1 = min(comp.y0, y), max(comp.y1, y)
            neighbours = (
                j - 1 if x > 0 else -1,
                j + 1 if x < w - 1 else -1,
                j - w if y > 0 else -1,
                j + w if y < h - 1 else -1,
            )
            for q in neighbours:
                if q >= 0 and flat[q] and lab[q] < 0:
                    lab[q] = cid
                    stack.append(q)
        comps.append(comp)
    return comps


def match_components(
    comps: list[Component], layout: list[tuple], grid: int = GRID
) -> list[tuple[int, Component]]:
    """Greedy match in component order: nearest unused LAYOUT row by centre, <= MATCH_MAX."""
    taken: set[int] = set()
    kept: list[tuple[int, Component]] = []
    for comp in comps:
        if comp.area < MIN_AREA:
            continue
        mx = (comp.sx / comp.area + 0.5) * grid
        my = (comp.sy / comp.area + 0.5) * grid
        best, best_d = -1, 1e18
        for k, row in enumerate(layout):
            if k in taken:
                continue
            dx, dy = row[0] - mx, row[1] - my
            d = dx * dx + dy * dy
            if d < best_d:
                best, best_d = k, d
        if best < 0 or best_d > MATCH_MAX * MATCH_MAX:
            continue
        taken.add(best)
        kept.append((best, comp))
    return kept


@dataclass
class Item:
    k: int  # LAYOUT row index
    sprite: Image.Image  # RGBA crop of the sheet, neighbours cut away
    area: int
    seeds: list[tuple[float, float]]  # sprite-local item grid (4 px cells)
    up: float
    vx: float
    spin: float


def _sprite(sheet: Image.Image, comp: Component, lw: int, lh: int) -> tuple[Image.Image, int, int]:
    """Sheet crop of the component's padded bbox, alpha-masked to its 3x3-dilated cells."""
    f = GRID
    sw, sh = sheet.size
    x0, y0 = max(0, comp.x0 - PAD_CELLS), max(0, comp.y0 - PAD_CELLS)
    x1, y1 = min(lw - 1, comp.x1 + PAD_CELLS), min(lh - 1, comp.y1 + PAD_CELLS)
    mw, mh = x1 - x0 + 1, y1 - y0 + 1
    bx, by = x0 * f, y0 * f
    bw, bh = min(sw - bx, mw * f), min(sh - by, mh * f)
    mask = np.zeros((mh, mw), dtype=np.uint8)
    for j in comp.cells:
        x, y = j % lw, j // lw
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                X, Y = x + dx, y + dy
                if x0 <= X <= x1 and y0 <= Y <= y1:
                    mask[Y - y0, X - x0] = 255
    mask_px = Image.fromarray(mask).resize((mw * f, mh * f), Image.Resampling.BILINEAR)
    arr = np.array(sheet.crop((bx, by, bx + bw, by + bh)), dtype=np.uint16)
    m = np.asarray(mask_px.crop((0, 0, bw, bh)), dtype=np.uint16)
    arr[..., 3] = (arr[..., 3] * m + 127) // 255
    return Image.fromarray(arr.astype(np.uint8)), x0, y0


def cut_items(
    sheet: Image.Image,
    layout: list[tuple] = LAYOUT,
    *,
    fr=None,
) -> list[Item]:
    """Cut, match and seed the item sprites. Returns the items sorted by LAYOUT row.

    ``fr`` is the rng(91) stream. It is shared with the blanket seeds, which draw
    after the items, as in the prototype. The rng(55) stream for up/vx/spin is local.
    """
    if fr is None:
        fr = rng(91)
    tq = rng(55)
    sw, sh = sheet.size
    lw, lh = math.ceil(sw / GRID), math.ceil(sh / GRID)
    small = np.asarray(sheet.getchannel("A").resize((lw, lh), Image.Resampling.BOX))
    comps = label_components(small > ALPHA_MIN)
    items: list[Item] = []
    for k, comp in match_components(comps, layout):
        sprite, x0, y0 = _sprite(sheet, comp, lw, lh)
        up = 0.7 + tq() * 0.6
        vx = tq() - 0.5
        spin = (tq() - 0.5) * 2
        cells_xy = np.array([(j % lw, j // lw) for j in comp.cells], dtype=np.float64)
        seeds = _pick_seeds(cells_xy, seed_count(comp.area), fr)
        _shard_draws(cells_xy, seeds, fr)
        local = [(sx - x0, sy - y0) for sx, sy in seeds]
        items.append(Item(k, sprite, comp.area, local, up, vx, spin))
    items.sort(key=lambda it: it.k)
    return items


def assign_ord(values: list[float]) -> list[int]:
    """ord = position after sorting by the rng(77) value (ties keep item order)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ords = [0] * len(values)
    for pos, i in enumerate(order):
        ords[i] = pos
    return ords


def pack_atlas(items: list[Item]) -> tuple[Image.Image, dict[int, tuple[int, int]]]:
    """Shelf-pack the sprites (tallest first) with ATLAS_PAD px between and around them."""
    pos: dict[int, tuple[int, int]] = {}
    x = y = ATLAS_PAD
    shelf = 0
    for it in sorted(items, key=lambda i: (-i.sprite.height, i.k)):
        w, h = it.sprite.size
        if x + w + ATLAS_PAD > ATLAS_W:
            x = ATLAS_PAD
            y += shelf + ATLAS_PAD
            shelf = 0
        if x + w + ATLAS_PAD > ATLAS_W:
            raise ValueError(f"sprite {it.k} is wider than the atlas")
        pos[it.k] = (x, y)
        x += w + ATLAS_PAD
        shelf = max(shelf, h)
    atlas = Image.new("RGBA", (ATLAS_W, y + shelf + ATLAS_PAD), (0, 0, 0, 0))
    for it in items:
        atlas.paste(it.sprite, pos[it.k])
    return atlas, pos


# ---------------------------------------------------------------- first paint


def _place(sprite: Image.Image, tx: float, ty: float, r0: float, sc: float, size) -> Image.Image:
    """Draw ``sprite`` centred on (tx, ty), rotated r0 (canvas: clockwise on screen), scaled sc."""
    bw, bh = sprite.size
    c, s = math.cos(r0), math.sin(r0)
    data = (
        c / sc,
        s / sc,
        bw / 2 - (c * tx + s * ty) / sc,
        -s / sc,
        c / sc,
        bh / 2 + (s * tx - c * ty) / sc,
    )
    return sprite.transform(size, Image.Transform.AFFINE, data, Image.Resampling.BICUBIC)


def compose_first_paint(keyed: Image.Image, items: list[Item], layout: list[tuple] = LAYOUT):
    """Keyed blanket with each item drawn per LAYOUT, shadowed, resized to FIRST_W wide."""
    canvas = keyed.copy()
    size = canvas.size
    zero = Image.new("L", size, 0)
    for it in items:
        _, _, tx, ty, r0, sc = layout[it.k]
        layer = _place(it.sprite, tx, ty, r0, sc, size)
        shadow = Image.new("L", size, 0)
        shadow.paste(layer.getchannel("A"), SHADOW_OFFSET)
        shadow = shadow.filter(ImageFilter.GaussianBlur(SHADOW_SIGMA))
        shadow = shadow.point(lambda v: round(v * SHADOW_ALPHA))
        canvas = Image.alpha_composite(canvas, Image.merge("RGBA", (zero, zero, zero, shadow)))
        canvas = Image.alpha_composite(canvas, layer)
    height = round(canvas.height * FIRST_W / canvas.width)
    return canvas.resize((FIRST_W, height), Image.Resampling.LANCZOS)


# ---------------------------------------------------------------- world and California raster


def _points(segment: str) -> list[tuple[float, float]]:
    return [tuple(map(float, p.split(","))) for p in segment.split("L")]


def _rings(d: str) -> list[list[tuple[float, float]]]:
    return [_points(r) for r in re.findall(r"M([^Z]+)Z", d)]


def _bbox(rings) -> tuple[float, float, float, float]:
    xs = [p[0] for r in rings for p in r]
    ys = [p[1] for r in rings for p in r]
    return (min(xs), min(ys), max(xs), max(ys))


def _pip(x: float, y: float, rings) -> bool:
    """Even-odd point in polygon (port of story.py pip)."""
    inside = False
    for ring in rings:
        n = len(ring)
        j = n - 1
        for i in range(n):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
                inside = not inside
            j = i
    return inside


# Fixed log-scale breaks (works per country): under 30 stays the wash step "0"; 30-299 "1";
# 300-2,999 "2"; 3,000 and more "3". Fixed breaks keep the shading comparable from day to day and
# reserve the top step for the largest producers (finish review: terciles put 56 countries in it).
STEP_BREAKS = (30, 300, 3000)


def step_tiers(
    countries: list[dict], counts: dict[str, int], breaks: tuple[int, int, int] = STEP_BREAKS
) -> dict[str, str]:
    """ISO alpha-2 -> '1' | '2' | '3' for mapped countries at or above the first break."""
    tiers: dict[str, str] = {}
    for c in countries:
        iso = c.get("iso_a2")
        n = counts.get(iso, 0) if iso else 0
        if n >= breaks[0]:
            tiers[iso] = "3" if n >= breaks[2] else "2" if n >= breaks[1] else "1"
    if not tiers:
        raise ValueError("no mapped country reaches the first shading break")
    return tiers


def _ca_raster(b, carings) -> str:
    """California at local scale: 'w' or 'l' inside the outline (diagonal split), '.' outside."""
    rows = []
    yy = b[1] + ZC / 2
    while yy < b[3]:
        xx = b[0] + ZC / 2
        row = []
        while xx < b[2]:
            if _pip(xx, yy, carings):
                edge = b[0] + (b[2] - b[0]) * (0.25 + 0.5 * (yy - b[1]) / (b[3] - b[1]))
                row.append("w" if xx < edge else "l")
            else:
                row.append(".")
            xx += ZC
        rows.append("".join(row))
        yy += ZC
    return "|".join(rows)


def world_raster(world: dict, tiers: dict[str, str]) -> dict:
    """Equal Earth pixel raster: '.' sea or outside the sphere, 'c' California, else tier."""
    k = MW / world["w"]
    c0, c1 = world["crop"]
    cols, rows = int(MW // CELL), int((c1 - c0) * k // CELL)
    sphere = [_points(world["sphere"][1:-1])]
    carings = _rings(world["ca"])
    b = world["ca_bbox"]
    countries = []
    for c in world["countries"]:
        rings = _rings(c["d"])
        countries.append((c.get("iso_a2"), rings, _bbox(rings)))
    lines = []
    for r in range(rows):
        uy = c0 + (r + 0.5) * CELL / k
        line = []
        for col in range(cols):
            ux = (col + 0.5) * CELL / k
            ch = "."
            if _pip(ux, uy, sphere):
                if b[0] <= ux <= b[2] and b[1] <= uy <= b[3] and _pip(ux, uy, carings):
                    ch = "c"
                else:
                    for iso, rings, bb in countries:
                        if bb[0] <= ux <= bb[2] and bb[1] <= uy <= bb[3] and _pip(ux, uy, rings):
                            ch = tiers.get(iso, "0")
                            break
            line.append(ch)
        lines.append("".join(line))
    return {
        "cols": cols,
        "rows": rows,
        "cell": CELL,
        "world": "|".join(lines),
        "ca": _ca_raster(b, carings),
    }


# ---------------------------------------------------------------- papers and licence guard

NC_RE = re.compile(r"non-?commercial|\bNC\b|CC[- ]?BY[- ]?NC", re.IGNORECASE)
BY_RE = re.compile(r"CC[- ]?BY|Creative Commons Attribution", re.IGNORECASE)


def assert_cc_by(licence: str) -> None:
    """Raise unless the licence sentence names CC BY and does not name an NC licence."""
    if NC_RE.search(licence) or not BY_RE.search(licence):
        raise ValueError(f"licence is not CC BY: {ascii(licence)}")


def build_papers(credits: list[dict], out: Path) -> list[dict]:
    rows = []
    for entry in credits:
        assert_cc_by(entry["license_text"])
        stem = Path(entry["file"]).stem
        im = Image.open(PAPERS_DIR / f"{stem}.jpg").convert("RGB")
        width = round(im.width * PAPER_H / im.height)
        im = im.resize((width, PAPER_H), Image.Resampling.LANCZOS)
        im.save(out / "papers" / f"{stem}.webp", "WEBP", quality=PAPER_Q, method=6)
        rows.append(
            {
                "src": f"papers/{stem}.webp",
                "title": entry["title"],
                "doi": entry["doi"],
                "licence": entry["license_text"],
            }
        )
    return rows


# ---------------------------------------------------------------- output files


def save_within(img: Image.Image, path: Path, qualities, max_bytes: int) -> int:
    """Save WebP at the first (highest) quality whose file fits ``max_bytes``; return it."""
    for q in qualities:
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=q, method=6)
        if len(buf.getvalue()) <= max_bytes:
            path.write_bytes(buf.getvalue())
            return q
    raise ValueError(f"{path.name} does not fit in {max_bytes} bytes at any quality")


def _write_json(path: Path, obj, *, indent: int | None = None) -> None:
    style = {"indent": indent} if indent else {"separators": (",", ":")}
    text = json.dumps(obj, ensure_ascii=False, **style)
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def picnic_json(items: list[Item], pos, pts, ords: list[int], atlas_size) -> dict:
    out_items = []
    for it, ord_value in zip(items, ords, strict=True):
        lx, ly = pos[it.k]
        _, _, tx, ty, r0, sc = LAYOUT[it.k]
        out_items.append(
            {
                "k": it.k,
                "x": lx,
                "y": ly,
                "w": it.sprite.width,
                "h": it.sprite.height,
                "tx": tx,
                "ty": ty,
                "r0": r0,
                "sc": sc,
                "area": it.area,
                "seeds": [[round(x, 3), round(y, 3)] for x, y in it.seeds],
                "up": round(it.up, 4),
                "vx": round(it.vx, 4),
                "spin": round(it.spin, 4),
                "ord": ord_value,
            }
        )
    return {
        "version": 1,
        "grid": GRID,
        "blanket": {
            "src": "blanket.webp",
            "w": 1536,
            "h": 1024,
            "grid": BLANKET_GRID,
            "seeds": [[round(x, 3), round(y, 3)] for x, y in pts],
        },
        "atlas": {"src": "picnic_items.webp", "w": atlas_size[0], "h": atlas_size[1]},
        "items": out_items,
    }


def write_motion_assets(out: Path) -> None:
    """Copy the owner's logo animation and write its poster, the footer's static fallback.

    The poster is the animation's final frame, resized to MOTION_PX (Lanczos) and flattened onto
    black, the footer ground (--pv-night). Nothing is rendered here, so the output is deterministic.
    """
    shutil.copyfile(MOTION_SRC, out / "plastiverse_live.mp4")
    with Image.open(MOTION_STILL_SRC) as still:
        resized = still.convert("RGBA").resize((MOTION_PX, MOTION_PX), Image.Resampling.LANCZOS)
    flat = Image.alpha_composite(Image.new("RGBA", resized.size, (0, 0, 0, 255)), resized)
    flat.convert("RGB").save(out / "logo_motion_poster.webp", "WEBP", quality=LOGO_Q, method=6)


def _sidecar_block(path: Path) -> list[str]:
    meta = json.loads(path.read_text(encoding="utf-8"))
    lines = [f"- Generator: `{meta['model']}` via `{meta['tool']}`, created `{meta['createdAt']}`."]
    if "background" in meta:
        lines.append(f"- Background: `{meta['background']}`, output `{meta.get('outputFormat')}`.")
    lines.append("- Prompt:")
    lines.append(f"  > {meta['prompt']}")
    return lines


def provenance_md(papers: list[dict], counts: dict, world_source: str, first_q: int) -> str:
    lines = [
        "# Landing assets: provenance",
        "",
        "Generated by `scripts/build_landing_assets.py`. Do not edit by hand; rerun the script.",
        "",
        "## Picnic (beat 0)",
        "",
        "### blanket.webp",
        "",
        "- Source: `.impeccable/sketches/scene/web/blanket.jpg` (1536 x 1024, black backdrop).",
        "  Sidecar: `sidecars/blanket.png.json` (copy of `.impeccable/sketches/scene/"
        "blanket.png.json`).",
        *_sidecar_block(BLANKET_SIDECAR),
        "- Processing: backdrop keyed to alpha = round(255 * clamp((L - 14) / 26, 0, 1)), "
        "L = .3R + .59G + .11B; WebP quality 82.",
        "",
        "### picnic_items.webp and picnic.json",
        "",
        "- Source: `.impeccable/sketches/scene/web/picnic_items.png` (1536 x 1024, RGBA).",
        "  Sidecar: `sidecars/picnic_items.png.json` (copy of `.impeccable/sketches/scene/"
        "picnic_items.png.json`).",
        *_sidecar_block(ITEMS_SIDECAR),
        "- Processing: item cut-outs and LAYOUT placement as in "
        "`.impeccable/sketches/src/story_engine7.js`, ported to `scripts/build_landing_assets.py`.",
        "",
        "### picnic_first_paint.webp",
        "",
        "- Derived from blanket.webp and the item sprites, composed at blanket resolution "
        f"and resized to {FIRST_W} px wide. WebP quality {first_q}, the highest that keeps "
        f"the file within {FIRST_PAINT_MAX} bytes.",
        "",
        "## Paper pages (CC BY only)",
        "",
        "Source: `.impeccable/sketches/papers/web/pNN.jpg` with metadata from "
        "`.impeccable/sketches/papers/credits.json`. Each page is resized to 560 px tall.",
        "",
        "| File | DOI | Licence sentence (credits.json) | Redacted lines |",
        "| --- | --- | --- | --- |",
    ]
    redacted = {Path(e["file"]).stem: e for e in json.loads(CREDITS.read_text(encoding="utf-8"))}
    for p in papers:
        stem = Path(p["src"]).stem
        lines.append(
            f"| `{p['src']}` | {p['doi']} | {p['licence']} | {redacted[stem]['redacted_lines']} |"
        )
    lines += [
        "",
        "Redacted lines are the counts recorded in credits.json. The redaction was done "
        "upstream and this build does not re-check it.",
        "",
        "Licence text is copied from credits.json unchanged. Several entries end mid-sentence "
        '(for example p04; the page text includes "Creative Commons Attribution License 4.0 '
        '(CC BY)"). Replace each with the full sentence, checked against its page, before '
        "release.",
        "",
        "Papers with an empty title in credits.json: "
        + (", ".join(f"`{p['src']}`" for p in papers if not p["title"]) or "none")
        + ".",
        "",
        "## Logos",
        "",
        "- `logo_564.webp` and `logo_282.webp` come from "
        "`.impeccable/sketches/brand/logo_564.png`.",
        "- Generator prompt: `src/plastiverse_logo_gen_prompt.md`.",
        "",
        "## Logo animation (footer)",
        "",
        "- `plastiverse_live.mp4` is a byte copy of `src/plastiverse_live_high_res.mp4` "
        "(H.264, 1254 x 1254, 24 fps, 7 s). It loads at runtime from the site root, "
        "not from `framework/src/`.",
        "- `logo_motion_poster.webp` is the final frame, `src/plastiverse_live_static.png`, "
        f"resized to {MOTION_PX} px (Lanczos), flattened onto black and saved at "
        f"WebP quality {LOGO_Q}. It is the static fallback and the video's poster.",
        "- Source: owner-supplied `src/` files made by `src/create_plastiverse_animation.py`, "
        "2026-11-18. This build copies them and does not run that script.",
        "",
        "## World and California raster",
        "",
        f"- `site/data/global/world_raster.json`: {world_source}.",
        f"- Country counts: `site/data/global/global_counts.json`, query "
        f"`{counts['query_version']}`, fetched `{counts['fetched_at']}`.",
        "",
    ]
    return "\n".join(lines)


WORLD_SOURCE = (
    "world.json (world-atlas countries-110m and us-atlas states-10m) with "
    "total_by_country shading in four steps; port of .impeccable/sketches/src/story.py, "
    "fixed log breaks at 30, 300 and 3,000 works"
)


def write_raster(world: dict, counts: dict) -> dict[str, str]:
    """Write site/data/global/world_raster.json from the world geometry and country counts."""
    tiers = step_tiers(world["countries"], counts["total_by_country"])
    raster = world_raster(world, tiers)
    raster.update({"source": WORLD_SOURCE, "fetched_at": counts["fetched_at"]})
    _write_json(RASTER_OUT, raster)
    return tiers


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--raster-only",
        action="store_true",
        help="only rebuild world_raster.json (daily, after build_global_counts.py)",
    )
    args = parser.parse_args(argv)
    counts = json.loads(COUNTS_JSON.read_text(encoding="utf-8"))
    world = json.loads(WORLD_JSON.read_text(encoding="utf-8"))
    if args.raster_only:
        write_raster(world, counts)
        print(f"wrote {RASTER_OUT}")
        return 0
    credits = json.loads(CREDITS.read_text(encoding="utf-8"))

    shutil.rmtree(OUT / "papers", ignore_errors=True)
    shutil.rmtree(OUT / "sidecars", ignore_errors=True)
    (OUT / "papers").mkdir(parents=True)
    (OUT / "sidecars").mkdir(parents=True)

    blanket_rgb = Image.open(BLANKET_SRC).convert("RGB")
    sheet = Image.open(ITEMS_SRC).convert("RGBA")
    keyed = key_blanket(blanket_rgb)

    fr = rng(91)
    items = cut_items(sheet, fr=fr)
    pts = blanket_seeds(blanket_rgb, fr)
    tr = rng(77)
    ords = assign_ord([tr() for _ in items])

    atlas, pos = pack_atlas(items)
    first = compose_first_paint(keyed, items)

    keyed.save(OUT / "blanket.webp", "WEBP", quality=BLANKET_Q, method=6)
    atlas.save(OUT / "picnic_items.webp", "WEBP", quality=ITEMS_Q, method=6)
    first_q = save_within(
        first,
        OUT / "picnic_first_paint.webp",
        range(FIRST_Q, FIRST_Q_MIN - 1, -1),
        FIRST_PAINT_MAX,
    )
    # Phones get an 800 px first paint through srcset (Lighthouse mobile LCP on slow 4G).
    small = first.resize((800, round(first.height * 800 / first.width)), Image.Resampling.LANCZOS)
    small.save(OUT / "picnic_first_paint_800.webp", "WEBP", quality=72, method=6)
    _write_json(OUT / "picnic.json", picnic_json(items, pos, pts, ords, atlas.size))

    papers = build_papers(credits, OUT)
    _write_json(OUT / "papers.json", papers, indent=2)

    logo = Image.open(LOGO_SRC).convert("RGB")
    logo.save(OUT / "logo_564.webp", "WEBP", quality=LOGO_Q, method=6)
    small_h = round(logo.height * 282 / logo.width)
    logo.resize((282, small_h), Image.Resampling.LANCZOS).save(
        OUT / "logo_282.webp", "WEBP", quality=LOGO_Q, method=6
    )
    write_motion_assets(OUT)

    for src, name in (
        (BLANKET_SIDECAR, "blanket.png.json"),
        (ITEMS_SIDECAR, "picnic_items.png.json"),
    ):
        shutil.copyfile(src, OUT / "sidecars" / name)

    tiers = write_raster(world, counts)
    world_source = WORLD_SOURCE

    (OUT / "PROVENANCE.md").write_text(
        provenance_md(papers, counts, world_source, first_q), encoding="utf-8", newline="\n"
    )

    first_bytes = (OUT / "picnic_first_paint.webp").stat().st_size
    total = sum(p.stat().st_size for p in OUT.rglob("*.webp"))
    print(f"items {len(items)} of {len(LAYOUT)} LAYOUT rows matched")
    print(f"first paint {first_bytes} bytes (max {FIRST_PAINT_MAX})")
    print(f"landing webp total {total} bytes (max {LANDING_MAX})")
    print(f"shading step counts {sorted((t, list(tiers.values()).count(t)) for t in '123')}")
    if first_bytes > FIRST_PAINT_MAX or total > LANDING_MAX:
        print("budget exceeded", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
