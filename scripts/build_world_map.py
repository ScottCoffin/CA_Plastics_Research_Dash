"""Build the landing-page world and California outlines (PLAT-2a).

Projects Natural Earth 1:110m admin-0 countries (world-atlas ``countries-110m.json``) and the
California polygon (us-atlas ``states-10m.json``, FIPS ``06``) to Equal Earth. The method is the
one in the design prototype ``.impeccable/sketches/src/build_geo.py``: TopoJSON arcs are decoded,
rings are unwrapped across the antimeridian and copied to the seam, rings under 0.6 px are
dropped, and the sphere outline and vertical crop are computed. The output is
``site/assets/world/world.json``; ``site/assets/world/PROVENANCE.md`` records the inputs.

The two inputs are cached under ``data/raw/world/`` (git-ignored) and checked against pinned
SHA-256 digests. The first run downloads them; ``--offline`` reads the cache and never touches
the network.

Usage:
    py -3.14 scripts/build_world_map.py             # download once if needed, then write
    py -3.14 scripts/build_world_map.py --offline   # cache only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

COUNTRIES_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-110m.json"
STATES_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json"
COUNTRIES_SHA256 = "2516c915867c7baf18ddec727aec46c315541a07cfb3d79a6559b05d5e94eee8"
STATES_SHA256 = "d76b391ccfa8bff601d51e3e3da5d43a89fa46cd5caca72ce731b383be5596d0"
COUNTRIES_FILE = Path("countries") / "countries-110m.json"
STATES_FILE = Path("states") / "states-10m.json"
DEFAULT_RAW_DIR = ROOT / "data" / "raw" / "world"
DEFAULT_OUTPUT = ROOT / "site" / "assets" / "world" / "world.json"
SOURCE = (
    "world-atlas@2.0.2 countries-110m.json (Natural Earth 1:110m admin-0); "
    "us-atlas@3.0.1 states-10m.json (California, FIPS 06); Equal Earth projection"
)
LICENCE = "Natural Earth, public domain"
USER_AGENT = "CA-Plastics-Research-Atlas/0.1 (PLAT-2a world map build)"
ANTARCTICA = "010"
CALIFORNIA = "06"
# Rings whose projected bounding box is under this many pixels in both directions are dropped.
MIN_RING_SPAN_PX = 0.6
# California keeps every third vertex (the prototype's step), plus the closing vertex.
CA_STEP = 3

# Equal Earth (Savric, Patterson and Jenny, 2018) coefficients.
EE_A1, EE_A2, EE_A3, EE_A4 = 1.340264, -0.081106, 0.000893, 0.003796
EE_M = math.sqrt(3) / 2
# Half-extent of the projected sphere in Equal Earth units: x at longitude 180, y at latitude 90.
EE_XM, EE_YM = 2.7066, 1.3173
WIDTH = 1000.0
SCALE = WIDTH / (2 * EE_XM)
HEIGHT = round(2 * EE_YM * SCALE, 1)

# ISO 3166-1 numeric to alpha-2 for the country ids in world-atlas countries-110m. Each entry was
# checked against pycountry during the PLAT-2a build (173 of 173 matched, no duplicates). Ids that
# world-atlas leaves out (N. Cyprus, Somaliland, Kosovo) and Antarctica (010) have no entry, so
# their iso_a2 is null or the country is dropped.
ISO_NUMERIC_TO_ALPHA2: dict[str, str] = {
    "004": "AF",  # Afghanistan
    "008": "AL",  # Albania
    "012": "DZ",  # Algeria
    "024": "AO",  # Angola
    "031": "AZ",  # Azerbaijan
    "032": "AR",  # Argentina
    "036": "AU",  # Australia
    "040": "AT",  # Austria
    "044": "BS",  # Bahamas
    "050": "BD",  # Bangladesh
    "051": "AM",  # Armenia
    "056": "BE",  # Belgium
    "064": "BT",  # Bhutan
    "068": "BO",  # Bolivia
    "070": "BA",  # Bosnia and Herz.
    "072": "BW",  # Botswana
    "076": "BR",  # Brazil
    "084": "BZ",  # Belize
    "090": "SB",  # Solomon Is.
    "096": "BN",  # Brunei
    "100": "BG",  # Bulgaria
    "104": "MM",  # Myanmar
    "108": "BI",  # Burundi
    "112": "BY",  # Belarus
    "116": "KH",  # Cambodia
    "120": "CM",  # Cameroon
    "124": "CA",  # Canada
    "140": "CF",  # Central African Rep.
    "144": "LK",  # Sri Lanka
    "148": "TD",  # Chad
    "152": "CL",  # Chile
    "156": "CN",  # China
    "158": "TW",  # Taiwan
    "170": "CO",  # Colombia
    "178": "CG",  # Congo
    "180": "CD",  # Dem. Rep. Congo
    "188": "CR",  # Costa Rica
    "191": "HR",  # Croatia
    "192": "CU",  # Cuba
    "196": "CY",  # Cyprus
    "203": "CZ",  # Czechia
    "204": "BJ",  # Benin
    "208": "DK",  # Denmark
    "214": "DO",  # Dominican Rep.
    "218": "EC",  # Ecuador
    "222": "SV",  # El Salvador
    "226": "GQ",  # Eq. Guinea
    "231": "ET",  # Ethiopia
    "232": "ER",  # Eritrea
    "233": "EE",  # Estonia
    "238": "FK",  # Falkland Is.
    "242": "FJ",  # Fiji
    "246": "FI",  # Finland
    "250": "FR",  # France
    "260": "TF",  # Fr. S. Antarctic Lands
    "262": "DJ",  # Djibouti
    "266": "GA",  # Gabon
    "268": "GE",  # Georgia
    "270": "GM",  # Gambia
    "275": "PS",  # Palestine
    "276": "DE",  # Germany
    "288": "GH",  # Ghana
    "300": "GR",  # Greece
    "304": "GL",  # Greenland
    "320": "GT",  # Guatemala
    "324": "GN",  # Guinea
    "328": "GY",  # Guyana
    "332": "HT",  # Haiti
    "340": "HN",  # Honduras
    "348": "HU",  # Hungary
    "352": "IS",  # Iceland
    "356": "IN",  # India
    "360": "ID",  # Indonesia
    "364": "IR",  # Iran
    "368": "IQ",  # Iraq
    "372": "IE",  # Ireland
    "376": "IL",  # Israel
    "380": "IT",  # Italy
    "384": "CI",  # Côte d'Ivoire
    "388": "JM",  # Jamaica
    "392": "JP",  # Japan
    "398": "KZ",  # Kazakhstan
    "400": "JO",  # Jordan
    "404": "KE",  # Kenya
    "408": "KP",  # North Korea
    "410": "KR",  # South Korea
    "414": "KW",  # Kuwait
    "417": "KG",  # Kyrgyzstan
    "418": "LA",  # Laos
    "422": "LB",  # Lebanon
    "426": "LS",  # Lesotho
    "428": "LV",  # Latvia
    "430": "LR",  # Liberia
    "434": "LY",  # Libya
    "440": "LT",  # Lithuania
    "442": "LU",  # Luxembourg
    "450": "MG",  # Madagascar
    "454": "MW",  # Malawi
    "458": "MY",  # Malaysia
    "466": "ML",  # Mali
    "478": "MR",  # Mauritania
    "484": "MX",  # Mexico
    "496": "MN",  # Mongolia
    "498": "MD",  # Moldova
    "499": "ME",  # Montenegro
    "504": "MA",  # Morocco
    "508": "MZ",  # Mozambique
    "512": "OM",  # Oman
    "516": "NA",  # Namibia
    "524": "NP",  # Nepal
    "528": "NL",  # Netherlands
    "540": "NC",  # New Caledonia
    "548": "VU",  # Vanuatu
    "554": "NZ",  # New Zealand
    "558": "NI",  # Nicaragua
    "562": "NE",  # Niger
    "566": "NG",  # Nigeria
    "578": "NO",  # Norway
    "586": "PK",  # Pakistan
    "591": "PA",  # Panama
    "598": "PG",  # Papua New Guinea
    "600": "PY",  # Paraguay
    "604": "PE",  # Peru
    "608": "PH",  # Philippines
    "616": "PL",  # Poland
    "620": "PT",  # Portugal
    "624": "GW",  # Guinea-Bissau
    "626": "TL",  # Timor-Leste
    "630": "PR",  # Puerto Rico
    "634": "QA",  # Qatar
    "642": "RO",  # Romania
    "643": "RU",  # Russia
    "646": "RW",  # Rwanda
    "682": "SA",  # Saudi Arabia
    "686": "SN",  # Senegal
    "688": "RS",  # Serbia
    "694": "SL",  # Sierra Leone
    "703": "SK",  # Slovakia
    "704": "VN",  # Vietnam
    "705": "SI",  # Slovenia
    "706": "SO",  # Somalia
    "710": "ZA",  # South Africa
    "716": "ZW",  # Zimbabwe
    "724": "ES",  # Spain
    "728": "SS",  # S. Sudan
    "729": "SD",  # Sudan
    "732": "EH",  # W. Sahara
    "740": "SR",  # Suriname
    "748": "SZ",  # eSwatini
    "752": "SE",  # Sweden
    "756": "CH",  # Switzerland
    "760": "SY",  # Syria
    "762": "TJ",  # Tajikistan
    "764": "TH",  # Thailand
    "768": "TG",  # Togo
    "780": "TT",  # Trinidad and Tobago
    "784": "AE",  # United Arab Emirates
    "788": "TN",  # Tunisia
    "792": "TR",  # Turkey
    "795": "TM",  # Turkmenistan
    "800": "UG",  # Uganda
    "804": "UA",  # Ukraine
    "807": "MK",  # Macedonia
    "818": "EG",  # Egypt
    "826": "GB",  # United Kingdom
    "834": "TZ",  # Tanzania
    "840": "US",  # United States of America
    "854": "BF",  # Burkina Faso
    "858": "UY",  # Uruguay
    "860": "UZ",  # Uzbekistan
    "862": "VE",  # Venezuela
    "887": "YE",  # Yemen
    "894": "ZM",  # Zambia
}


class WorldMapError(RuntimeError):
    """A missing, unpinned or malformed input: nothing is written."""


def equal_earth(lon: float, lat: float) -> tuple[float, float]:
    """Equal Earth coordinates (unit-sphere units) of a longitude and latitude in degrees."""

    lam = math.radians(lon)
    phi = math.radians(lat)
    theta = math.asin(EE_M * math.sin(phi))
    t2 = theta * theta
    t6 = t2**3
    x = (
        lam
        * math.cos(theta)
        / (EE_M * (EE_A1 + 3 * EE_A2 * t2 + t6 * (7 * EE_A3 + 9 * EE_A4 * t2)))
    )
    y = theta * (EE_A1 + EE_A2 * t2 + t6 * (EE_A3 + EE_A4 * t2))
    return x, y


def to_pixels(lon: float, lat: float) -> tuple[float, float]:
    """Position in the viewBox (0..WIDTH by 0..HEIGHT, y pointing down)."""

    x, y = equal_earth(lon, lat)
    return (x + EE_XM) * SCALE, (EE_YM - y) * SCALE


def decode_arcs(topology: Mapping[str, Any]) -> list[list[tuple[float, float]]]:
    """Every TopoJSON arc as absolute (lon, lat) points.

    A quantized topology stores delta-encoded integers with ``scale`` and ``translate``; an
    unquantized one stores absolute positions.
    """

    transform = topology.get("transform")
    arcs: list[list[tuple[float, float]]] = []
    for arc in topology["arcs"]:
        if transform:
            scale_x, scale_y = transform["scale"]
            translate_x, translate_y = transform["translate"]
            x = y = 0
            points: list[tuple[float, float]] = []
            for point in arc:
                x += point[0]
                y += point[1]
                points.append((x * scale_x + translate_x, y * scale_y + translate_y))
        else:
            points = [(float(point[0]), float(point[1])) for point in arc]
        arcs.append(points)
    return arcs


def ring_coordinates(
    arcs: Sequence[Sequence[tuple[float, float]]], indices: Sequence[int]
) -> list[tuple[float, float]]:
    """Join the arcs of one ring. A negative index ``i`` names arc ``~i`` traversed backwards."""

    ring: list[tuple[float, float]] = []
    for index in indices:
        arc = arcs[index] if index >= 0 else arcs[~index][::-1]
        # Each arc starts where the previous one ended, so its first point is not repeated.
        ring.extend(arc if not ring else arc[1:])
    return ring


def unwrap_longitudes(points: Sequence[tuple[float, float]]) -> list[tuple[float, float]]:
    """Make longitudes continuous so a ring that crosses the antimeridian stays in one piece."""

    if not points:
        return []
    unwrapped = [points[0]]
    for lon, lat in points[1:]:
        previous = unwrapped[-1][0]
        while lon - previous > 180:
            lon -= 360
        while lon - previous < -180:
            lon += 360
        unwrapped.append((lon, lat))
    return unwrapped


def polygon_path(xy: Sequence[tuple[float, float]]) -> str:
    """One closed SVG subpath with one-decimal coordinates."""

    return "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in xy) + "Z"


def ring_paths(points: Sequence[tuple[float, float]], step: int = 1) -> list[str]:
    """SVG subpaths for one ring: thinned, unwrapped, copied across the seam, tiny rings dropped.

    A ring that reaches past 180 degrees gets a copy shifted by -360, and one that reaches past
    -180 gets a copy shifted by +360, so the part beyond the map edge is drawn on the other side.
    """

    if not points:
        return []
    if step > 1:
        points = [*points[::step], points[-1]]
    unwrapped = unwrap_longitudes(points)
    longitudes = [lon for lon, _ in unwrapped]
    shifts = [0]
    if min(longitudes) < -180:
        shifts.append(360)
    if max(longitudes) > 180:
        shifts.append(-360)
    paths: list[str] = []
    for shift in shifts:
        xy = [to_pixels(lon + shift, lat) for lon, lat in unwrapped]
        xs = [x for x, _ in xy]
        ys = [y for _, y in xy]
        if max(xs) - min(xs) < MIN_RING_SPAN_PX and max(ys) - min(ys) < MIN_RING_SPAN_PX:
            continue
        paths.append(polygon_path(xy))
    return paths


def geometry_path(
    geometry: Mapping[str, Any],
    arcs: Sequence[Sequence[tuple[float, float]]],
    step: int = 1,
) -> str:
    """Concatenated SVG path for a Polygon or MultiPolygon. Other geometry types give ''."""

    if geometry.get("type") == "MultiPolygon":
        polygons = geometry["arcs"]
    elif geometry.get("type") == "Polygon":
        polygons = [geometry["arcs"]]
    else:
        return ""
    parts: list[str] = []
    for polygon in polygons:
        for ring_indices in polygon:
            parts.extend(ring_paths(ring_coordinates(arcs, ring_indices), step))
    return "".join(parts)


def sphere_path() -> str:
    """Outline of the projected sphere, along longitude -180 up and 180 down."""

    left = [to_pixels(-180, lat) for lat in range(-90, 91, 2)]
    right = [to_pixels(180, lat) for lat in range(90, -91, -2)]
    return polygon_path([*left, *right])


def path_bbox(path: str) -> list[float]:
    """Bounding box ``[x0, y0, x1, y1]`` of the coordinate pairs in an SVG path."""

    pairs = [(float(x), float(y)) for x, y in re.findall(r"(-?[\d.]+),(-?[\d.]+)", path)]
    xs = [x for x, _ in pairs]
    ys = [y for _, y in pairs]
    return [min(xs), min(ys), max(xs), max(ys)]


def country_outlines(topology: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One ``{id, name, iso_a2, d}`` entry per country that still has a visible outline."""

    arcs = decode_arcs(topology)
    outlines: list[dict[str, Any]] = []
    for geometry in topology["objects"]["countries"]["geometries"]:
        country_id = geometry.get("id")
        if country_id == ANTARCTICA:
            continue
        d = geometry_path(geometry, arcs)
        if not d:
            continue
        outlines.append(
            {
                "id": country_id,
                "name": geometry.get("properties", {}).get("name", ""),
                "iso_a2": ISO_NUMERIC_TO_ALPHA2.get(country_id),
                "d": d,
            }
        )
    return outlines


def build_payload(
    countries_topology: Mapping[str, Any], states_topology: Mapping[str, Any]
) -> dict[str, Any]:
    """The world.json payload: the prototype's keys plus source and licence."""

    countries = country_outlines(countries_topology)
    if not countries:
        raise WorldMapError("no country outlines were produced")
    states_arcs = decode_arcs(states_topology)
    california = [
        geometry
        for geometry in states_topology["objects"]["states"]["geometries"]
        if geometry.get("id") == CALIFORNIA
    ]
    if len(california) != 1:
        raise WorldMapError("expected exactly one California (FIPS 06) geometry")
    ca = geometry_path(california[0], states_arcs, step=CA_STEP)
    if not ca:
        raise WorldMapError("California geometry produced no outline")
    crop_top = to_pixels(0, 84)[1]
    crop_bottom = to_pixels(0, -57)[1]
    return {
        "sphere": sphere_path(),
        "crop": [round(crop_top, 1), round(crop_bottom, 1)],
        "w": WIDTH,
        "h": HEIGHT,
        "countries": countries,
        "ca": ca,
        "ca_bbox": path_bbox(ca),
        "source": SOURCE,
        "licence": LICENCE,
    }


def check_digest(data: bytes, expected: str, name: str) -> None:
    """Refuse an input whose SHA-256 differs from the pinned value."""

    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise WorldMapError(f"{name}: SHA-256 {actual} does not match the pinned {expected}")


def download(url: str) -> bytes:
    """Fetch one input. Called only when the cache is empty and ``--offline`` is not set."""

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def read_source(url: str, path: Path, sha256: str, *, offline: bool) -> dict[str, Any]:
    """Load one TopoJSON input from the cache, downloading it once if the cache is empty."""

    if not path.exists():
        if offline:
            raise WorldMapError(f"{path} is not cached; run once without --offline to fetch it")
        data = download(url)
        check_digest(data, sha256, path.name)  # never cache a file that fails its pin
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    data = path.read_bytes()
    check_digest(data, sha256, path.name)
    topology: dict[str, Any] = json.loads(data.decode("utf-8"))
    return topology


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Write UTF-8 JSON with LF line endings and a trailing newline."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--offline", action="store_true", help="read the cached inputs only; never download"
    )
    args = parser.parse_args(argv)
    try:
        countries = read_source(
            COUNTRIES_URL, args.raw_dir / COUNTRIES_FILE, COUNTRIES_SHA256, offline=args.offline
        )
        states = read_source(
            STATES_URL, args.raw_dir / STATES_FILE, STATES_SHA256, offline=args.offline
        )
        payload = build_payload(countries, states)
    except WorldMapError as exc:
        print(f"error: {exc}; no file written", file=sys.stderr)
        return 1
    write_json(args.output, payload)
    size = args.output.stat().st_size
    print(
        f"wrote {args.output.name}: {len(payload['countries'])} countries, "
        f"viewBox 0 0 {WIDTH:g} {HEIGHT:g}, {size} bytes"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
