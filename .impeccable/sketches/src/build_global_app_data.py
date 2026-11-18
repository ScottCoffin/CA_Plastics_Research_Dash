"""Data module for the Global app prototype: `.impeccable/sketches/global_app_data.js`.

Offline. Inputs: the landing's pixel raster (`site/data/global/world_raster.json`), country
outlines (`site/assets/world/world.json`), country counts (`site/data/global/global_counts.json`),
the global trend (`site/data/trend_global.json`) and the real OpenAlex sample
(`global_app_sample.json`, from `fetch_global_app_sample.py`). Each raster cell is assigned to
the country whose outline holds its centre (nearest outline for edge cells), so the prototype
can hover, select and zoom per country. California keeps the raster's own `c` cells.

    py -3.14 .impeccable/sketches/src/build_global_app_data.py
"""

from __future__ import annotations

import json
import re
from functools import reduce
from pathlib import Path

import pycountry
from shapely import STRtree, make_valid
from shapely.geometry import Point, Polygon

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE.parent / "global_app_data.js"

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
}
NUM = re.compile(r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")


def name_of(code: str) -> str:
    if code in NAME_FIX:
        return NAME_FIX[code]
    c = pycountry.countries.get(alpha_2=code)
    return (getattr(c, "common_name", None) or c.name) if c else code


def rings(d: str) -> list[list[tuple[float, float]]]:
    out = []
    for part in d.split("M")[1:]:
        pts = [(float(x), float(y)) for x, y in NUM.findall(part)]
        if len(pts) >= 3:
            out.append(pts)
    return out


def geometry(d: str):
    polys = [make_valid(Polygon(r)) for r in rings(d)]
    return reduce(lambda a, b: a.symmetric_difference(b), polys)


def main() -> None:
    raster = json.loads((ROOT / "site/data/global/world_raster.json").read_text(encoding="utf-8"))
    world = json.loads((ROOT / "site/assets/world/world.json").read_text(encoding="utf-8"))
    counts = json.loads((ROOT / "site/data/global/global_counts.json").read_text(encoding="utf-8"))
    trend = json.loads((ROOT / "site/data/trend_global.json").read_text(encoding="utf-8"))
    sample = json.loads((HERE / "global_app_sample.json").read_text(encoding="utf-8"))

    rows = raster["world"].split("|")
    nrows, ncols = len(rows), raster["cols"]
    y0, y1 = world["crop"]
    u, v = world["w"] / ncols, (y1 - y0) / nrows

    shapes = [(c["iso_a2"], geometry(c["d"])) for c in world["countries"] if c.get("iso_a2")]
    tree = STRtree([s for _, s in shapes])
    cells: dict[str, list[tuple[int, int, str]]] = {}
    for r, row in enumerate(rows):
        for col, ch in enumerate(row):
            if ch == ".":
                continue
            if ch == "c":
                cells.setdefault("US-CA", []).append((col, r, ch))
                continue
            p = Point((col + 0.5) * u, y0 + (r + 0.5) * v)
            hit = [i for i in tree.query(p) if shapes[i][1].contains(p)]
            idx = hit[0] if hit else int(tree.nearest(p))
            cells.setdefault(shapes[idx][0], []).append((col, r, ch))

    total, recent, week = (
        counts[k] for k in ("total_by_country", "recent_5y_by_country", "new_this_week_by_country")
    )
    # Small countries (the Netherlands, Belgium, Singapore) hold no cell centre: give each the
    # land cell nearest its interior point, taken from the neighbour that held it.
    owner = {(col, r): k for k, cs in cells.items() for col, r, _ in cs}
    stolen: set[tuple[int, int]] = set()
    for code, shape in sorted(shapes, key=lambda s: -total.get(s[0], 0)):
        if cells.get(code) or not total.get(code):
            continue
        p = shape.representative_point()
        pc, pr = p.x / u - 0.5, (p.y - y0) / v - 0.5
        best = min(
            (k for k in owner if k not in stolen and owner[k] != "US-CA"),
            key=lambda k: (k[0] - pc) ** 2 + (k[1] - pr) ** 2,
        )
        if (best[0] - pc) ** 2 + (best[1] - pr) ** 2 > 9:
            continue
        prev = owner[best]
        ch = next(t[2] for t in cells[prev] if (t[0], t[1]) == best)
        cells[prev] = [t for t in cells[prev] if (t[0], t[1]) != best]
        cells[code] = [(best[0], best[1], ch)]
        owner[best] = code
        stolen.add(best)
    codes = sorted(set(total) | {k for k in cells if k != "US-CA"})
    countries = []
    for code in codes:
        cs = cells.get(code, [])
        runs = []
        for col, r, _ in sorted(cs, key=lambda t: (t[1], t[0])):
            if runs and runs[-1][1] == r and runs[-1][0] + runs[-1][2] == col:
                runs[-1][2] += 1
            else:
                runs.append([col, r, 1])
        countries.append(
            {
                "iso": code,
                "name": name_of(code),
                "continent": CONTINENT_OF.get(code, "Other"),
                "works": total.get(code, 0),
                "recent5": recent.get(code, 0),
                "week": week.get(code, 0),
                "runs": runs,
                "bbox": [
                    min(c[0] for c in cs),
                    min(c[1] for c in cs),
                    max(c[0] for c in cs) + 1,
                    max(c[1] for c in cs) + 1,
                ]
                if cs
                else None,
            }
        )
    ca = cells["US-CA"]
    norway = next(c["d"] for c in world["countries"] if c["id"] == "578")
    data = {
        "grid": {"cols": ncols, "rows": nrows, "u": u, "v": v, "y0": y0, "w": world["w"]},
        "countries": countries,
        "california": {"cells": [[c, r] for c, r, _ in ca], "works": 1918},
        "norway_outline": norway,
        "totals": counts["totals"],
        "fetched_at": counts["fetched_at"],
        "query_version": counts["query_version"],
        "trend_world": {k: n for k, n in trend["by_year"].items() if int(k) >= 1970},
        "sample": sample,
    }
    OUT.write_text(
        "window.GA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    unmatched = sum(1 for c in countries if c["works"] and not c["runs"])
    print(
        f"wrote {OUT.name}: {OUT.stat().st_size:,} bytes, {len(countries)} countries, "
        f"{unmatched} with works but no map cells, {len(ca)} California cells"
    )


if __name__ == "__main__":
    main()
