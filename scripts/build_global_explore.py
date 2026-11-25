"""Map cells and country data for the Global explore page: ``site/data/global/explore.json``.

Ported from the GA-1 design prototype (``.impeccable/sketches/src/build_global_app_data.py``),
which wrote a JavaScript module; this writes JSON. Offline and deterministic: the same inputs give
a byte-identical file, and nothing reads the wall clock. Run it after
``fetch_global_explore_sample.py`` and ``build_global_counts.py``.

Each raster cell goes to the country whose outline holds its centre (the nearest outline for edge
cells). A country that holds no centre (the Netherlands, Belgium, Singapore) takes the land cell
nearest its interior point. California keeps the raster's own ``c`` cells.

Usage:
    py -3.14 scripts/build_global_explore.py          # write explore.json
    py -3.14 scripts/build_global_explore.py --check  # exit 1 if the committed file is stale
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from functools import reduce
from pathlib import Path
from typing import Any

from shapely import STRtree, make_valid
from shapely.geometry import Point, Polygon

ROOT = Path(__file__).resolve().parent.parent
GLOBAL = ROOT / "site" / "data" / "global"
DEFAULT_RASTER = GLOBAL / "world_raster.json"
DEFAULT_WORLD = ROOT / "site" / "assets" / "world" / "world.json"
DEFAULT_COUNTS = GLOBAL / "global_counts.json"
DEFAULT_TREND = ROOT / "site" / "data" / "global" / "trend_global.json"
DEFAULT_SAMPLE = GLOBAL / "explore_sample.json"
DEFAULT_OUTPUT = GLOBAL / "explore.json"

CALIFORNIA = "US-CA"
# The California atlas's own works count (counts.works in its build metadata, rebuilt daily).
DEFAULT_METADATA = ROOT / "site" / "data" / "california" / "build_metadata.json"
TREND_FIRST_YEAR = 1970
# A small country's land cell must lie within 3 cells (squared distance 9) of its interior point.
MAX_STEAL_DIST2 = 9
NUM = re.compile(r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")

CONTINENTS = {
    "Africa": "AO BF BI BJ BW CD CF CG CI CM CV DJ DZ EG EH ER ET GA GH GM GN GQ GW KE KM LR LS LY "
    "MA MG ML MR MU MW MZ NA NE NG RE RW SC SD SL SN SO SS ST SZ TD TG TN TZ UG ZA ZM ZW",
    "Asia": "AE AF AM AZ BD BH BN BT CN CY GE HK ID IL IN IQ IR JO JP KG KH KP KR KW KZ LA LB LK "
    "MM MN MO MV MY NP OM PH PK PS QA SA SG SY TH TJ TL TM TR TW UZ VN YE",
    "Europe": "AL AT BA BE BG BY CH CZ DE DK EE ES FI FO FR GB GI GR HR HU IE IS IT JE LT LU LV MC "
    "MD ME MK MT NL NO PL PT RO RS RU SE SI SJ SK SM UA XK",
    "North America": "AG AW BB BM BS BZ CA CR CU CW DM DO GD GL GP GT HN HT JM KN LC MX NI PA PR "
    "SV TT US VI",
    "South America": "AR BO BR CL CO EC FK GF GY PE PY SR UY VE",
    "Oceania": "AU FJ FM GU NC NZ PF PG PW SB VU",
}
CONTINENT_OF = {c: k for k, v in CONTINENTS.items() for c in v.split()}

# Short names for Natural Earth abbreviations. These override the map's own names.
NAME_FIX = {
    "XK": "Kosovo",
    "TW": "Taiwan",
    "KR": "South Korea",
    "KP": "North Korea",
    "RU": "Russia",
    "IR": "Iran",
    "SY": "Syria",
    "VN": "Vietnam",
    "LA": "Laos",
    "BO": "Bolivia",
    "VE": "Venezuela",
    "TZ": "Tanzania",
    "MD": "Moldova",
    "CD": "DR Congo",
    "CG": "Congo",
    "PS": "Palestine",
    "FM": "Micronesia",
    "BN": "Brunei",
    "CZ": "Czechia",
    "CI": "Côte d'Ivoire",
    "TR": "Türkiye",
    "GB": "United Kingdom",
    "US": "United States",
    "DO": "Dominican Republic",
    "FK": "Falkland Islands",
    "CF": "Central African Republic",
    "GQ": "Equatorial Guinea",
    "SB": "Solomon Islands",
    "BA": "Bosnia and Herzegovina",
    "SS": "South Sudan",
    "EH": "Western Sahara",
    "TF": "French Southern Lands",
}
# Names for the codes that the 110m map lacks, used when world.json has no name for a code.
FALLBACK_NAMES = {
    "AG": "Antigua and Barbuda",
    "AW": "Aruba",
    "BB": "Barbados",
    "BH": "Bahrain",
    "BM": "Bermuda",
    "CV": "Cabo Verde",
    "CW": "Curaçao",
    "DM": "Dominica",
    "FM": "Micronesia",
    "FO": "Faroe Islands",
    "GD": "Grenada",
    "GF": "French Guiana",
    "GI": "Gibraltar",
    "GP": "Guadeloupe",
    "GU": "Guam",
    "HK": "Hong Kong",
    "JE": "Jersey",
    "KN": "Saint Kitts and Nevis",
    "LC": "Saint Lucia",
    "MC": "Monaco",
    "MO": "Macao",
    "MT": "Malta",
    "MU": "Mauritius",
    "MV": "Maldives",
    "PF": "French Polynesia",
    "PW": "Palau",
    "RE": "Réunion",
    "SC": "Seychelles",
    "SG": "Singapore",
    "SJ": "Svalbard and Jan Mayen",
    "SM": "San Marino",
    "VI": "U.S. Virgin Islands",
    "XK": "Kosovo",
}


def resolve_name(code: str, world_names: Mapping[str, str]) -> str:
    """NAME_FIX, then the name in world.json, then the fixed table; the code is the last resort."""

    return NAME_FIX.get(code) or world_names.get(code) or FALLBACK_NAMES.get(code) or code


def rings(d: str) -> list[list[tuple[float, float]]]:
    out = []
    for part in d.split("M")[1:]:
        pts = [(float(x), float(y)) for x, y in NUM.findall(part)]
        if len(pts) >= 3:
            out.append(pts)
    return out


def geometry(d: str) -> Any:
    polys = [make_valid(Polygon(r)) for r in rings(d)]
    return reduce(lambda a, b: a.symmetric_difference(b), polys)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def map_cells(
    rows: Sequence[str],
    u: float,
    v: float,
    y0: float,
    shapes: Sequence[tuple[str, Any]],
    tree: STRtree,
) -> dict[str, list[tuple[int, int, str]]]:
    """Each cell goes to the outline holding its centre, else to the nearest outline."""

    cells: dict[str, list[tuple[int, int, str]]] = {}
    for r, row in enumerate(rows):
        for col, ch in enumerate(row):
            if ch == ".":
                continue
            if ch == "c":
                cells.setdefault(CALIFORNIA, []).append((col, r, ch))
                continue
            p = Point((col + 0.5) * u, y0 + (r + 0.5) * v)
            hit = sorted(int(i) for i in tree.query(p) if shapes[i][1].contains(p))
            idx = hit[0] if hit else int(tree.nearest(p))
            cells.setdefault(shapes[idx][0], []).append((col, r, ch))
    return cells


def assign_small_countries(
    cells: dict[str, list[tuple[int, int, str]]],
    shapes: Sequence[tuple[str, Any]],
    total: Mapping[str, int],
    u: float,
    v: float,
    y0: float,
) -> None:
    """Give each country with works but no cell the land cell nearest its interior point.

    The cell is taken from the neighbour that held it. Cells owned by California are never taken,
    a cell is taken at most once, and a country's last cell is never taken (Israel keeps its one
    cell when Palestine looks for one).
    """

    owner = {(col, r): k for k, cs in cells.items() for col, r, _ in cs}
    stolen: set[tuple[int, int]] = set()
    for code, shape in sorted(shapes, key=lambda s: -total.get(s[0], 0)):
        if cells.get(code) or not total.get(code):
            continue
        p = shape.representative_point()
        pc, pr = p.x / u - 0.5, (p.y - y0) / v - 0.5
        best = min(
            (
                k
                for k in owner
                if k not in stolen and owner[k] != CALIFORNIA and len(cells[owner[k]]) > 1
            ),
            key=lambda k: (k[0] - pc) ** 2 + (k[1] - pr) ** 2,
        )
        if (best[0] - pc) ** 2 + (best[1] - pr) ** 2 > MAX_STEAL_DIST2:
            continue
        prev = owner[best]
        ch = next(t[2] for t in cells[prev] if (t[0], t[1]) == best)
        cells[prev] = [t for t in cells[prev] if (t[0], t[1]) != best]
        cells[code] = [(best[0], best[1], ch)]
        owner[best] = code
        stolen.add(best)


def runs_of(cs: Sequence[tuple[int, int, str]]) -> list[list[int]]:
    """Horizontal runs ``[col, row, length]`` of a country's cells, in row-major order."""

    runs: list[list[int]] = []
    for col, r, _ in sorted(cs, key=lambda t: (t[1], t[0])):
        if runs and runs[-1][1] == r and runs[-1][0] + runs[-1][2] == col:
            runs[-1][2] += 1
        else:
            runs.append([col, r, 1])
    return runs


def bbox_of(cs: Sequence[tuple[int, int, str]]) -> list[int] | None:
    if not cs:
        return None
    return [
        min(c[0] for c in cs),
        min(c[1] for c in cs),
        max(c[0] for c in cs) + 1,
        max(c[1] for c in cs) + 1,
    ]


def trend_world(trend: Mapping[str, Any], fetched_at: str) -> dict[str, int]:
    """Years from 1970 to the UTC year of the counts file's ``fetched_at``. No wall clock."""

    fetched = datetime.fromisoformat(fetched_at)
    if fetched.tzinfo is not None:
        fetched = fetched.astimezone(UTC)
    by_year = {int(k): n for k, n in trend["by_year"].items()}
    return {
        str(year): by_year[year]
        for year in sorted(by_year)
        if TREND_FIRST_YEAR <= year <= fetched.year
    }


def build(
    *,
    raster: Path = DEFAULT_RASTER,
    world: Path = DEFAULT_WORLD,
    counts: Path = DEFAULT_COUNTS,
    trend: Path = DEFAULT_TREND,
    sample: Path = DEFAULT_SAMPLE,
    metadata: Path = DEFAULT_METADATA,
) -> dict[str, Any]:
    """The explore.json payload, rebuilt from the input files."""

    raster_doc = _load(raster)
    world_doc = _load(world)
    counts_doc = _load(counts)
    trend_doc = _load(trend)
    sample_doc = _load(sample)
    california_works = (_load(metadata).get("counts") or {}).get("works")

    rows = raster_doc["world"].split("|")
    ncols = raster_doc["cols"]
    y0, y1 = world_doc["crop"]
    u, v = world_doc["w"] / ncols, (y1 - y0) / len(rows)

    shapes = [(c["iso_a2"], geometry(c["d"])) for c in world_doc["countries"] if c.get("iso_a2")]
    tree = STRtree([s for _, s in shapes])
    cells = map_cells(rows, u, v, y0, shapes, tree)

    total = counts_doc["total_by_country"]
    recent = counts_doc["recent_5y_by_country"]
    week = counts_doc["new_this_week_by_country"]
    assign_small_countries(cells, shapes, total, u, v, y0)

    world_names = {
        c["iso_a2"]: c["name"] for c in world_doc["countries"] if c.get("iso_a2") and c.get("name")
    }
    codes = sorted(set(total) | {k for k in cells if k != CALIFORNIA})
    countries = [
        {
            "iso": code,
            "name": resolve_name(code, world_names),
            "continent": CONTINENT_OF.get(code, "Other"),
            "works": total.get(code, 0),
            "recent5": recent.get(code, 0),
            "week": week.get(code, 0),
            "runs": runs_of(cells.get(code, [])),
            "bbox": bbox_of(cells.get(code, [])),
        }
        for code in codes
    ]
    return {
        "grid": {"cols": ncols, "rows": len(rows), "u": u, "v": v, "y0": y0, "w": world_doc["w"]},
        "countries": countries,
        "california": {
            "cells": [[c, r] for c, r, _ in cells.get(CALIFORNIA, [])],
            "works": california_works,
        },
        "totals": counts_doc["totals"],
        "fetched_at": counts_doc["fetched_at"],
        "query_version": counts_doc["query_version"],
        "trend_world": trend_world(trend_doc, counts_doc["fetched_at"]),
        "sample": sample_doc,
    }


def encode(data: Mapping[str, Any]) -> bytes:
    """Compact JSON, UTF-8, LF, trailing newline."""

    return (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raster", type=Path, default=DEFAULT_RASTER)
    ap.add_argument("--world", type=Path, default=DEFAULT_WORLD)
    ap.add_argument("--counts", type=Path, default=DEFAULT_COUNTS)
    ap.add_argument("--trend", type=Path, default=DEFAULT_TREND)
    ap.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    ap.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument(
        "--check", action="store_true", help="exit 1 unless the output matches a rebuild"
    )
    args = ap.parse_args(argv)

    try:
        data = build(
            raster=args.raster,
            world=args.world,
            counts=args.counts,
            trend=args.trend,
            sample=args.sample,
        )
    except (OSError, KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    text = encode(data)

    if args.check:
        same = args.output.is_file() and args.output.read_bytes() == text
        print("ok" if same else "stale")
        return 0 if same else 1

    write_atomic(args.output, text)
    unnamed = [c["iso"] for c in data["countries"] if c["name"] == c["iso"]]
    if unnamed:
        print(f"warning: no name for {', '.join(unnamed)}; the code is shown", file=sys.stderr)
    no_cells = sum(1 for c in data["countries"] if c["works"] and not c["runs"])
    print(
        f"wrote {args.output.name}: {len(text):,} bytes, {len(data['countries'])} countries, "
        f"{no_cells} with works but no map cells, "
        f"{len(data['california']['cells'])} California cells"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
