"""Build the place-search index for the Explore page: ``site/data/global/places.json``.

The file also carries ``markers``: ``[iso, lon, lat]`` for each small country, the same points that
``world.json`` uses for its ``small`` markers, so Explore can draw them without loading
the world file.

Three kinds of place, one entry each, compact arrays::

    [name, kind, parent, iso2, geom, population]

* ``country``: every ISO-coded country in world-atlas ``countries-50m.json`` (the same topology
  that feeds ``site/assets/world/world.json``). ``geom`` is the ``[west, south, east, north]``
  bounding box in degrees (the eastern cluster when a country crosses the antimeridian), or
  ``[lon, lat]`` for a country with no outline in that file (Tuvalu).
* ``admin1``: first-level subdivisions (states, provinces, counties where Natural Earth has them)
  from Natural Earth 10m ``ne_10m_admin_1_states_provinces``. ``geom`` is the bounding box, or a
  representative point when the feature crosses the antimeridian.
* ``city``: GeoNames ``cities15000`` (populated places with at least 15,000 people). ``geom`` is
  ``[lon, lat]``. ``parent`` is the admin-1 region the point falls in (a spatial join) and the
  country, for example "Hordaland, Norway"; it is the country alone when there is no such region
  or the region has the city's own name.

Coordinates are rounded to two decimals. Alternative names are kept for countries only (the
``aliases`` map); city names are matched after accents are removed on the Explore page. The
licence and credit block is in the file: Natural Earth is public domain, GeoNames is CC BY 4.0.

The inputs are cached under ``data/raw/places/`` and ``data/raw/world/`` (both git-ignored) and
checked against pinned SHA-256 digests. The first run downloads them; ``--offline`` reads the
cache and never touches the network.

Usage:
    py -3.14 scripts/build_places_index.py             # download once if needed, then write
    py -3.14 scripts/build_places_index.py --check     # exit 1 if the committed file is stale
    py -3.14 scripts/build_places_index.py --offline   # cache only
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import sys
import urllib.request
import zipfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = ROOT / "data" / "raw" / "places"
DEFAULT_WORLD_RAW_DIR = ROOT / "data" / "raw" / "world"
DEFAULT_OUTPUT = ROOT / "site" / "data" / "global" / "places.json"

NE_ADMIN1_URL = "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip"
NE_ADMIN1_SHA256 = "efc59726337323058f9446210adc96673179cd344e053666ee3d28cb58ba2b05"
NE_ADMIN1_FILE = Path("ne_admin1") / "ne_10m_admin_1_states_provinces.zip"
NE_ADMIN1_MEMBER = "ne_10m_admin_1_states_provinces.shp"
GEONAMES_URL = "https://download.geonames.org/export/dump/cities15000.zip"
GEONAMES_SHA256 = "ceb887cfe141c5d14c5da67998fc5dadf1bf20af926d49070af6937962896ed7"
GEONAMES_FILE = Path("geonames") / "cities15000.zip"
GEONAMES_MEMBER = "cities15000.txt"
USER_AGENT = "CA-Plastics-Research-Atlas/0.1 (place index build)"

SCHEMA = "places-v1"
# Entry fields: kind and parent are indices into the "kinds" and "parents" lists of the payload.
FIELDS = ["name", "kind", "parent", "iso2", "geom", "population"]
KINDS = ("country", "admin1", "city")
MIN_POPULATION = 15000
# GeoNames feature class P: populated places.
GEONAMES_CLASS = "P"
# Pinned fields of the GeoNames dump (https://download.geonames.org/export/dump/readme.txt).
GN_NAME, GN_LAT, GN_LON, GN_CC, GN_CLASS, GN_POP = 1, 4, 5, 8, 6, 14

LICENCE = {
    "natural_earth": (
        "Natural Earth admin-0 (world-atlas countries-50m) and admin-1 10m: public domain."
    ),
    "geonames": "GeoNames cities15000: Creative Commons Attribution 4.0 (CC BY 4.0), https://www.geonames.org/",
}
CREDIT = (
    "Contains data from Natural Earth (public domain, https://www.naturalearthdata.com/) and "
    "GeoNames (CC BY 4.0, https://www.geonames.org/)."
)

# Names used for search and display, by ISO alpha-2. world-atlas uses short or abbreviated names
# (Dem. Rep. Congo); the full name is shown instead.
NAME_BY_ISO: dict[str, str] = {
    "AG": "Antigua and Barbuda",
    "AX": "Åland Islands",
    "BA": "Bosnia and Herzegovina",
    "BL": "Saint Barthélemy",
    "BM": "Bermuda",
    "BN": "Brunei",
    "CD": "Democratic Republic of the Congo",
    "CF": "Central African Republic",
    "CI": "Côte d'Ivoire",
    "CK": "Cook Islands",
    "CV": "Cabo Verde",
    "DO": "Dominican Republic",
    "FK": "Falkland Islands",
    "FO": "Faroe Islands",
    "GQ": "Equatorial Guinea",
    "GS": "South Georgia and the South Sandwich Islands",
    "HM": "Heard Island and McDonald Islands",
    "IO": "British Indian Ocean Territory",
    "KN": "Saint Kitts and Nevis",
    "KY": "Cayman Islands",
    "MF": "Saint Martin",
    "MH": "Marshall Islands",
    "MK": "North Macedonia",
    "MP": "Northern Mariana Islands",
    "PF": "French Polynesia",
    "PM": "Saint Pierre and Miquelon",
    "PN": "Pitcairn Islands",
    "SB": "Solomon Islands",
    "SH": "Saint Helena",
    "SS": "South Sudan",
    "ST": "São Tomé and Príncipe",
    "SZ": "Eswatini",
    "TC": "Turks and Caicos Islands",
    "TF": "French Southern Territories",
    "US": "United States",
    "VA": "Vatican City",
    "VC": "Saint Vincent and the Grenadines",
    "VG": "British Virgin Islands",
    "VI": "U.S. Virgin Islands",
    "WF": "Wallis and Futuna",
    "EH": "Western Sahara",
    "AS": "American Samoa",
    "GU": "Guam",
    "MS": "Montserrat",
    "TT": "Trinidad and Tobago",
    "CW": "Curaçao",
    "SX": "Sint Maarten",
    "NC": "New Caledonia",
    "MO": "Macao",
    "HK": "Hong Kong",
    "SJ": "Svalbard and Jan Mayen",
    "PR": "Puerto Rico",
    "TV": "Tuvalu",
}
# Other alternative names, by ISO alpha-2, used for search only.
ALIASES: dict[str, list[str]] = {
    "US": ["USA", "U.S.", "United States of America", "America"],
    "GB": ["UK", "Britain", "Great Britain"],
    "NL": ["Holland"],
    "CZ": ["Czech Republic"],
    "MK": ["Macedonia"],
    "SZ": ["Swaziland"],
    "CI": ["Ivory Coast"],
    "MM": ["Burma"],
    "TR": ["Türkiye", "Turkiye"],
    "VA": ["Holy See"],
    "CD": ["DRC", "DR Congo"],
    "CG": ["Republic of the Congo"],
    "KR": ["Korea", "Republic of Korea"],
    "KP": ["North Korea", "DPRK"],
    "AE": ["UAE"],
    "RU": ["Russian Federation"],
    "VN": ["Viet Nam"],
    "PS": ["Palestine"],
    "TL": ["East Timor"],
    "CV": ["Cape Verde"],
    "GM": ["The Gambia"],
    "FM": ["Micronesia"],
    "IR": ["Iran"],
    "BO": ["Bolivia"],
}


class PlacesError(RuntimeError):
    """A missing, unpinned or malformed input: nothing is written."""


def _load_world_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "build_world_map", ROOT / "scripts" / "build_world_map.py"
    )
    if spec is None or spec.loader is None:
        raise PlacesError("cannot load scripts/build_world_map.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _round_geom(geom: Sequence[float]) -> list[float]:
    return [round(value, 2) for value in geom]


def _unwrap_ring(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Longitudes made continuous along the ring, as in build_world_map."""

    if not points:
        return []
    out = [points[0]]
    for lon, lat in points[1:]:
        previous = out[-1][0]
        while lon - previous > 180:
            lon -= 360
        while lon - previous < -180:
            lon += 360
        out.append((lon, lat))
    return out


def _bbox_of_points(points: Sequence[tuple[float, float]]) -> list[float]:
    """Bounding box of lon/lat points, on whichever side of the antimeridian is narrower."""

    lons = [lon for lon, _ in points]
    lats = [lat for _, lat in points]
    west, east = min(lons), max(lons)
    if east - west > 180:
        shifted = [(lon + 360 if lon < 0 else lon, lat) for lon, lat in points]
        s_lons = [lon for lon, _ in shifted]
        if max(s_lons) - min(s_lons) < east - west:
            west, east = min(s_lons), max(s_lons)
    return [west, min(lats), east, max(lats)]


def country_table(world: ModuleType, topology: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """ISO alpha-2 -> ``{"name", "geom"}`` for every coded country in the 50m topology."""

    arcs = world.decode_arcs(topology)
    points_by_iso: dict[str, list[tuple[float, float]]] = {}
    names: dict[str, tuple[int, str]] = {}
    for geometry in topology["objects"]["countries"]["geometries"]:
        country_id = geometry.get("id")
        iso = world.ISO_NUMERIC_TO_ALPHA2.get(country_id or "")
        if country_id == world.ANTARCTICA or not iso:
            continue
        polygons = (
            geometry["arcs"]
            if geometry.get("type") == "MultiPolygon"
            else [geometry["arcs"]]
            if geometry.get("type") == "Polygon"
            else []
        )
        count = 0
        for polygon in polygons:
            for ring_indices in polygon:
                ring = _unwrap_ring(world.ring_coordinates(arcs, ring_indices))
                points_by_iso.setdefault(iso, []).extend(ring)
                count += len(ring)
        # The primary geometry gives the name: the one with the most vertices (Australia's islets
        # are a second geometry with their own name).
        raw_name = geometry.get("properties", {}).get("name", "")
        if count > names.get(iso, (-1, ""))[0]:
            names[iso] = (count, raw_name)
    table: dict[str, dict[str, Any]] = {}
    for iso, points in points_by_iso.items():
        if not points:
            continue
        table[iso] = {
            "name": NAME_BY_ISO.get(iso, names[iso][1]),
            "geom": _round_geom(_bbox_of_points(points)),
        }
    for country_id, (lon, lat) in world.MANUAL_MARKERS.items():
        iso = world.ISO_NUMERIC_TO_ALPHA2[country_id]
        table.setdefault(iso, {"name": NAME_BY_ISO.get(iso, iso), "geom": _round_geom([lon, lat])})
    return table


def country_entries(table: Mapping[str, Mapping[str, Any]]) -> list[list[Any]]:
    return [
        [value["name"], "country", "", iso, value["geom"], None] for iso, value in table.items()
    ]


def admin1_entries(
    rows: Sequence[Mapping[str, Any]], table: Mapping[str, Mapping[str, Any]]
) -> list[list[Any]]:
    """``rows``: dicts with ``name``, ``iso`` and ``geom`` (bbox), ``point`` (lon/lat) keys."""

    entries: list[list[Any]] = []
    for row in rows:
        iso = row["iso"]
        name = row["name"].strip() if isinstance(row["name"], str) else ""
        if not name or iso not in table:
            continue
        geom = row.get("geom") or row.get("point")
        if geom is None:
            continue
        entries.append([name, "admin1", table[iso]["name"], iso, _round_geom(geom), None])
    return entries


def city_entries(
    rows: Sequence[Mapping[str, Any]], table: Mapping[str, Mapping[str, Any]]
) -> list[list[Any]]:
    """``rows``: dicts with ``name``, ``iso``, ``lon``, ``lat``, ``population`` and ``admin1``."""

    entries: list[list[Any]] = []
    for row in rows:
        iso = row["iso"]
        population = int(row["population"])
        if iso not in table or population < MIN_POPULATION:
            continue
        country = table[iso]["name"]
        admin1 = row.get("admin1") or ""
        parent = f"{admin1}, {country}" if admin1 and admin1 != row["name"] else country
        entries.append(
            [row["name"], "city", parent, iso, _round_geom([row["lon"], row["lat"]]), population]
        )
    return entries


def build_payload(
    countries: list[list[Any]],
    admin1: list[list[Any]],
    cities: list[list[Any]],
    aliases: Mapping[str, Sequence[str]],
    markers: Sequence[Sequence[Any]],
) -> dict[str, Any]:
    order = {kind: index for index, kind in enumerate(KINDS)}
    entries = sorted(
        [*countries, *admin1, *cities],
        key=lambda e: (order[e[1]], e[0].casefold(), e[3], e[2]),
    )
    counts = {kind: sum(1 for e in entries if e[1] == kind) for kind in KINDS}
    if counts["country"] == 0 or counts["admin1"] == 0 or counts["city"] == 0:
        raise PlacesError(f"an input produced no places: {counts}")
    parents: list[str] = []
    parent_index: dict[str, int] = {}
    compact: list[list[Any]] = []
    for name, kind, parent, iso, geom, population in entries:
        if parent not in parent_index:
            parent_index[parent] = len(parents)
            parents.append(parent)
        compact.append([name, order[kind], parent_index[parent], iso, geom, population])
    return {
        "schema": SCHEMA,
        "fields": FIELDS,
        "kinds": list(KINDS),
        "parents": parents,
        "geom": "[west, south, east, north] degrees for a bounding box; [lon, lat] for a point",
        "counts": counts,
        "licence": LICENCE,
        "credit": CREDIT,
        "aliases": {iso: list(values) for iso, values in sorted(aliases.items())},
        "markers": [list(marker) for marker in markers],
        "entries": compact,
    }


def serialise(payload: Mapping[str, Any]) -> bytes:
    """Compact UTF-8 JSON with LF line endings and a trailing newline."""

    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (text + "\n").encode("utf-8")


def check_digest(data: bytes, expected: str, name: str) -> None:
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise PlacesError(f"{name}: SHA-256 {actual} does not match the pinned {expected}")


def read_cached(url: str, path: Path, sha256: str, *, offline: bool) -> bytes:
    """A pinned input from the cache; downloaded once when the cache is empty and not offline."""

    if not path.exists():
        if offline:
            raise PlacesError(f"{path} is not cached; run once without --offline to fetch it")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read()
        check_digest(data, sha256, path.name)  # never cache a file that fails its pin
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    data = path.read_bytes()
    check_digest(data, sha256, path.name)
    return data


def admin1_rows(zip_path: Path) -> list[dict[str, Any]]:
    """Admin-1 features: name, iso, the bounding box (or a point), and the polygon for the join."""

    import pyogrio

    frame = pyogrio.read_dataframe(
        f"/vsizip/{zip_path.as_posix()}/{NE_ADMIN1_MEMBER}", columns=["name", "iso_a2"]
    )
    rows: list[dict[str, Any]] = []
    for name, iso, geometry in zip(frame["name"], frame["iso_a2"], frame.geometry, strict=True):
        if geometry is None or geometry.is_empty:
            continue
        minx, miny, maxx, maxy = geometry.bounds
        row: dict[str, Any] = {
            "name": name,
            "iso": iso,
            "geom": None,
            "point": None,
            "shape": geometry,
        }
        if maxx - minx > 180:
            point = geometry.representative_point()
            row["point"] = [point.x, point.y]
        else:
            row["geom"] = [minx, miny, maxx, maxy]
        rows.append(row)
    return rows


def city_rows(
    zip_bytes: bytes, admin1: Sequence[Mapping[str, Any]], table_iso: set[str]
) -> list[dict[str, Any]]:
    """GeoNames populated places with population, and the admin-1 region each one falls in."""

    import geopandas as gpd

    text = zipfile.ZipFile(io.BytesIO(zip_bytes)).read(GEONAMES_MEMBER).decode("utf-8")
    rows: list[dict[str, Any]] = []
    for fields in csv.reader(io.StringIO(text), delimiter="\t", quoting=csv.QUOTE_NONE):
        if len(fields) <= GN_POP or fields[GN_CLASS] != GEONAMES_CLASS:
            continue
        population = int(fields[GN_POP] or 0)
        if population < MIN_POPULATION or fields[GN_CC] not in table_iso:
            continue
        rows.append(
            {
                "name": fields[GN_NAME],
                "iso": fields[GN_CC],
                "lon": float(fields[GN_LON]),
                "lat": float(fields[GN_LAT]),
                "population": population,
                "admin1": "",
            }
        )
    if not rows:
        return rows
    points = gpd.GeoDataFrame(
        {"row": range(len(rows))},
        geometry=gpd.points_from_xy([r["lon"] for r in rows], [r["lat"] for r in rows]),
        crs="EPSG:4326",
    )
    regions = gpd.GeoDataFrame(
        {"region": [a["name"] for a in admin1], "iso": [a["iso"] for a in admin1]},
        geometry=[a["shape"] for a in admin1],
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(points, regions, how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]
    for index, region, iso in zip(joined["row"], joined["region"], joined["iso"], strict=True):
        if isinstance(region, str) and iso == rows[int(index)]["iso"]:
            rows[int(index)]["admin1"] = region
    return rows


def build(raw_dir: Path, world_raw_dir: Path, *, offline: bool) -> bytes:
    world = _load_world_module()
    countries_bytes = read_cached(
        world.COUNTRIES_URL,
        world_raw_dir / world.COUNTRIES_FILE,
        world.COUNTRIES_SHA256,
        offline=offline,
    )
    topology = json.loads(countries_bytes.decode("utf-8"))
    table = country_table(world, topology)
    read_cached(NE_ADMIN1_URL, raw_dir / NE_ADMIN1_FILE, NE_ADMIN1_SHA256, offline=offline)
    geonames_zip = read_cached(
        GEONAMES_URL, raw_dir / GEONAMES_FILE, GEONAMES_SHA256, offline=offline
    )
    admin1 = [row for row in admin1_rows(raw_dir / NE_ADMIN1_FILE) if row["iso"] in table]
    cities = city_rows(geonames_zip, admin1, set(table))
    markers = [[m["iso"], m["lon"], m["lat"]] for m in world.small_markers(topology)]
    payload = build_payload(
        country_entries(table),
        admin1_entries(admin1, table),
        city_entries(cities, table),
        ALIASES,
        markers,
    )
    return serialise(payload)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--world-raw-dir", type=Path, default=DEFAULT_WORLD_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--offline", action="store_true", help="read the cached inputs only")
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if the output file is missing or stale"
    )
    args = parser.parse_args(argv)
    try:
        data = build(args.raw_dir, args.world_raw_dir, offline=args.offline or args.check)
    except PlacesError as exc:
        print(f"error: {exc}; no file written", file=sys.stderr)
        return 1
    if args.check:
        if not args.output.exists() or args.output.read_bytes() != data:
            print(
                f"error: {args.output} is stale; rerun scripts/build_places_index.py",
                file=sys.stderr,
            )
            return 1
        print(f"{args.output.name} is up to date ({len(data)} bytes)")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    payload = json.loads(data)
    print(f"wrote {args.output.name}: {payload['counts']}, {len(data)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
