"""Build the "Pacific Contour" design motif from the committed California land polygon.

Writes two SVGs by default (docs/VISUAL_DESIGN_SPEC.md, task VD-2):
- ``ca_contours.svg``: the land outline plus seaward offset lines (the hero and page-header motif);
- ``ca_mark.svg``: a small mainland silhouette with two offset lines (the logo mark).

With ``--mask``, writes ``ca_contours_mask.svg`` instead: the same committed geometry as a
white-stroke, transparent-background mask for the Overview hero.

Source geometry: ``site/assets/ca_boundaries.geojson`` feature ``land`` (Natural Earth 1:10m
Admin 1 v5.1.1, public domain). Offsets are computed in an equirectangular kilometre projection
centred on 37 N, so line spacing is in real kilometres. The lines are decorative, not
bathymetry; never label them as depth.

Usage: py -3.14 scripts/build_design_motif.py [--out DIR] [--mask]
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from shapely.geometry import Polygon, shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
GEOJSON = ROOT / "site" / "assets" / "ca_boundaries.geojson"
DEFAULT_OUT = ROOT / "framework" / "src" / "assets" / "design"
LAT0 = 37.0
KX = math.cos(math.radians(LAT0)) * 111.32
KY = 110.57
# Sea-side mask: west of a line through the interior, between the Oregon and Mexico borders.
SEA_MASK = [
    (-140, 42.0),
    (-123.0, 42.0),
    (-121.5, 39.0),
    (-119.5, 36.0),
    (-117.5, 34.5),
    (-116.6, 32.53),
    (-140, 32.53),
]
HERO_OFFSETS_KM = [5, 12, 21, 32, 45, 60, 78, 99, 123, 150, 180, 214]
MARK_OFFSETS_KM = [22, 48]


def to_km(lon, lat, z=None):
    """Project lon/lat to km east of 120 W and km south of 37 N (SVG y grows downward)."""
    return (lon + 120.0) * KX, -(lat - LAT0) * KY


def path_d(geom, precision: int = 1) -> str:
    """Serialise a shapely geometry as SVG path data."""
    parts: list[str] = []
    for g in getattr(geom, "geoms", [geom]):
        if g.is_empty:
            continue
        if g.geom_type == "Polygon":
            for ring in [g.exterior, *g.interiors]:
                coords = "L".join(f"{x:.{precision}f},{y:.{precision}f}" for x, y in ring.coords)
                parts.append(f"M{coords}Z")
        elif g.geom_type in ("LineString", "LinearRing"):
            if len(g.coords) >= 2:
                coords = "L".join(f"{x:.{precision}f},{y:.{precision}f}" for x, y in g.coords)
                parts.append(f"M{coords}")
        else:
            parts.append(path_d(g, precision))
    return "".join(parts)


def load_land():
    data = json.loads(GEOJSON.read_text(encoding="utf-8"))
    feature = next(f for f in data["features"] if f["properties"]["boundary"] == "land")
    return transform(to_km, shape(feature["geometry"])).buffer(0)


def view_box(geoms, pad: float) -> str:
    minx, miny, maxx, maxy = unary_union(geoms).bounds
    width, height = maxx - minx + 2 * pad, maxy - miny + 2 * pad
    return f"{minx - pad:.0f} {miny - pad:.0f} {width:.0f} {height:.0f}"


def svg(view: str, body: str, fill_none: bool) -> str:
    fill = ' fill="none"' if fill_none else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}"{fill} '
        f'aria-hidden="true" focusable="false">{body}</svg>'
    )


def build_hero(land, mask) -> str:
    land_s = land.simplify(1.2, preserve_topology=True)
    lines = []
    for km in HERO_OFFSETS_KM:
        ring = land.buffer(km, quad_segs=8).boundary.intersection(mask)
        ring = ring.simplify(1.4, preserve_topology=False)
        if not ring.is_empty:
            lines.append((km, ring))
    body = f'<path class="land" d="{path_d(land_s)}"/>' + "".join(
        f'<path class="c c{i}" data-km="{km}" d="{path_d(g)}"/>' for i, (km, g) in enumerate(lines)
    )
    return svg(view_box([land_s, *[g for _, g in lines]], 6), body, fill_none=True)


def build_mask_variant(land, mask) -> str:
    """Build an alpha mask with the same land and seaward contours as the hero motif."""
    land_s = land.simplify(1.2, preserve_topology=True)
    lines = []
    for km in HERO_OFFSETS_KM:
        ring = land.buffer(km, quad_segs=8).boundary.intersection(mask)
        ring = ring.simplify(1.4, preserve_topology=False)
        if not ring.is_empty:
            lines.append((km, ring))
    body = (
        f'<path class="land" fill="white" fill-opacity="0.12" stroke="white" '
        f'stroke-opacity="0.55" stroke-width="1.4" d="{path_d(land_s)}"/>'
        + "".join(
            f'<path class="c c{i}" fill="none" stroke="white" '
            f'stroke-opacity="{0.44 if i < 2 else 0.28}" stroke-width="1.2" '
            f'd="{path_d(g)}"/>'
            for i, (_, g) in enumerate(lines)
        )
    )
    return svg(view_box([land_s, *[g for _, g in lines]], 6), body, fill_none=True)


def build_mark(land, mask) -> str:
    simple = land.simplify(9, preserve_topology=True)
    main = max(getattr(simple, "geoms", [simple]), key=lambda g: g.area)
    lines = [
        main.buffer(km, quad_segs=4).boundary.intersection(mask).simplify(7)
        for km in MARK_OFFSETS_KM
    ]
    body = f'<path class="mark-land" d="{path_d(main, 0)}"/>' + "".join(
        f'<path class="mark-line" fill="none" d="{path_d(line, 0)}"/>' for line in lines
    )
    return svg(view_box([main, *lines], 4), body, fill_none=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output folder")
    parser.add_argument(
        "--mask",
        action="store_true",
        help="write the white-stroke transparent-background Overview mask variant",
    )
    args = parser.parse_args()
    land = load_land()
    mask = transform(to_km, Polygon(SEA_MASK))
    args.out.mkdir(parents=True, exist_ok=True)
    outputs = (
        {"ca_contours_mask.svg": build_mask_variant(land, mask)}
        if args.mask
        else {"ca_contours.svg": build_hero(land, mask), "ca_mark.svg": build_mark(land, mask)}
    )
    for name, text in outputs.items():
        (args.out / name).write_text(text, encoding="utf-8", newline="\n")
        print(f"{name}: {len(text.encode('utf-8')):,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
