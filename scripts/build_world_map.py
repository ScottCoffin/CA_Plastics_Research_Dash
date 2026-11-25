"""Build the landing-page world and California outlines (PLAT-2a).

Projects Natural Earth 1:50m admin-0 countries (world-atlas ``countries-50m.json``) and the
California polygon (us-atlas ``states-10m.json``, FIPS ``06``) to Natural Earth I (d3
``geoNaturalEarth1``, the owner's AMB-1 decision). The method is the one in the design prototype
``.impeccable/sketches/src/build_geo.py``: TopoJSON arcs are decoded, rings are unwrapped across
the antimeridian and copied to the seam, rings under 0.6 px are dropped, and the sphere outline and
vertical crop are computed. Countries whose projected area is under ``SMALL_AREA_PX2`` also get a
centroid marker in ``small`` (``{iso, x, y, lon, lat}``), so tiny island states stay visible,
focusable and clickable. The output is ``site/assets/world/world.json``;
``site/assets/world/PROVENANCE.md`` records the inputs.

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

COUNTRIES_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json"
STATES_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3.0.1/states-10m.json"
COUNTRIES_SHA256 = "04342cdc1e3016bcd7db1630de95684d67b79fe3c8c460321e87aef469502394"
STATES_SHA256 = "d76b391ccfa8bff601d51e3e3da5d43a89fa46cd5caca72ce731b383be5596d0"
COUNTRIES_FILE = Path("countries") / "countries-50m.json"
STATES_FILE = Path("states") / "states-10m.json"
DEFAULT_RAW_DIR = ROOT / "data" / "raw" / "world"
DEFAULT_OUTPUT = ROOT / "site" / "assets" / "world" / "world.json"
SOURCE = (
    "world-atlas@2.0.2 countries-50m.json (Natural Earth 1:50m admin-0); "
    "us-atlas@3.0.1 states-10m.json (California, FIPS 06); "
    "Natural Earth I projection (d3 geoNaturalEarth1)"
)
LICENCE = "Natural Earth, public domain"
USER_AGENT = "CA-Plastics-Research-Atlas/0.1 (PLAT-2a world map build)"
ANTARCTICA = "010"
CALIFORNIA = "06"
# Rings whose projected bounding box is under this many pixels in both directions are dropped.
MIN_RING_SPAN_PX = 0.6
# California keeps every third vertex (the prototype's step), plus the closing vertex.
CA_STEP = 3


def natural_earth(lon: float, lat: float) -> tuple[float, float]:
    """Natural Earth I (Patterson, 2007) coordinates of a longitude and latitude in degrees.

    The polynomial is d3's ``geoNaturalEarth1`` forward transform, so the map matches the
    d3 projection used on the site. Units are radians on the unit sphere.
    """

    lam = math.radians(lon)
    phi = math.radians(lat)
    phi2 = phi * phi
    phi4 = phi2 * phi2
    x = lam * (
        0.8707 - 0.131979 * phi2 + phi4 * (-0.013791 + phi4 * (0.003971 * phi2 - 0.001529 * phi4))
    )
    y = phi * (
        1.007226 + phi2 * (0.015085 + phi4 * (-0.044475 + 0.028874 * phi2 - 0.005916 * phi4))
    )
    return x, y


# Half-extent of the projected sphere in Natural Earth units: x at longitude 180, y at latitude 90.
NE_XM, NE_YM = natural_earth(180, 0)[0], natural_earth(0, 90)[1]
WIDTH = 1000.0
SCALE = WIDTH / (2 * NE_XM)
HEIGHT = round(2 * NE_YM * SCALE, 1)
# Countries whose projected land area is below this many square pixels at world scale get a marker.
SMALL_AREA_PX2 = 4.0
# world-atlas countries-50m has no Tuvalu outline; its marker sits on Funafuti (179.2 E, 8.5 S).
MANUAL_MARKERS = {"798": (179.2, -8.52)}

# ISO 3166-1 numeric to alpha-2 for the country ids in world-atlas countries-110m. Each entry was
# checked against pycountry during the PLAT-2a build (173 of 173 matched, no duplicates). Ids that
# world-atlas leaves out (N. Cyprus, Somaliland, Kosovo) and Antarctica (010) have no entry, so
# their iso_a2 is null or the country is dropped.
ISO_NUMERIC_TO_ALPHA2: dict[str, str] = {
    "004": "AF",  # Afghanistan
    "008": "AL",  # Albania
    "012": "DZ",  # Algeria
    "016": "AS",  # American Samoa
    "020": "AD",  # Andorra
    "024": "AO",  # Angola
    "028": "AG",  # Antigua and Barb.
    "031": "AZ",  # Azerbaijan
    "032": "AR",  # Argentina
    "036": "AU",  # Australia
    "040": "AT",  # Austria
    "044": "BS",  # Bahamas
    "048": "BH",  # Bahrain
    "050": "BD",  # Bangladesh
    "051": "AM",  # Armenia
    "052": "BB",  # Barbados
    "056": "BE",  # Belgium
    "060": "BM",  # Bermuda
    "064": "BT",  # Bhutan
    "068": "BO",  # Bolivia
    "070": "BA",  # Bosnia and Herz.
    "072": "BW",  # Botswana
    "076": "BR",  # Brazil
    "084": "BZ",  # Belize
    "086": "IO",  # Br. Indian Ocean Ter.
    "090": "SB",  # Solomon Is.
    "092": "VG",  # British Virgin Is.
    "096": "BN",  # Brunei
    "100": "BG",  # Bulgaria
    "104": "MM",  # Myanmar
    "108": "BI",  # Burundi
    "112": "BY",  # Belarus
    "116": "KH",  # Cambodia
    "120": "CM",  # Cameroon
    "124": "CA",  # Canada
    "132": "CV",  # Cabo Verde
    "136": "KY",  # Cayman Is.
    "140": "CF",  # Central African Rep.
    "144": "LK",  # Sri Lanka
    "148": "TD",  # Chad
    "152": "CL",  # Chile
    "156": "CN",  # China
    "158": "TW",  # Taiwan
    "170": "CO",  # Colombia
    "174": "KM",  # Comoros
    "178": "CG",  # Congo
    "180": "CD",  # Dem. Rep. Congo
    "184": "CK",  # Cook Is.
    "188": "CR",  # Costa Rica
    "191": "HR",  # Croatia
    "192": "CU",  # Cuba
    "196": "CY",  # Cyprus
    "203": "CZ",  # Czechia
    "204": "BJ",  # Benin
    "208": "DK",  # Denmark
    "212": "DM",  # Dominica
    "214": "DO",  # Dominican Rep.
    "218": "EC",  # Ecuador
    "222": "SV",  # El Salvador
    "226": "GQ",  # Eq. Guinea
    "231": "ET",  # Ethiopia
    "232": "ER",  # Eritrea
    "233": "EE",  # Estonia
    "234": "FO",  # Faeroe Is.
    "238": "FK",  # Falkland Is.
    "239": "GS",  # S. Geo. and the Is.
    "242": "FJ",  # Fiji
    "246": "FI",  # Finland
    "248": "AX",  # Åland
    "250": "FR",  # France
    "258": "PF",  # Fr. Polynesia
    "260": "TF",  # Fr. S. Antarctic Lands
    "262": "DJ",  # Djibouti
    "266": "GA",  # Gabon
    "268": "GE",  # Georgia
    "270": "GM",  # Gambia
    "275": "PS",  # Palestine
    "276": "DE",  # Germany
    "288": "GH",  # Ghana
    "296": "KI",  # Kiribati
    "300": "GR",  # Greece
    "304": "GL",  # Greenland
    "308": "GD",  # Grenada
    "316": "GU",  # Guam
    "320": "GT",  # Guatemala
    "324": "GN",  # Guinea
    "328": "GY",  # Guyana
    "332": "HT",  # Haiti
    "334": "HM",  # Heard I. and McDonald Is.
    "336": "VA",  # Vatican
    "340": "HN",  # Honduras
    "344": "HK",  # Hong Kong
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
    "438": "LI",  # Liechtenstein
    "440": "LT",  # Lithuania
    "442": "LU",  # Luxembourg
    "446": "MO",  # Macao
    "450": "MG",  # Madagascar
    "454": "MW",  # Malawi
    "458": "MY",  # Malaysia
    "462": "MV",  # Maldives
    "466": "ML",  # Mali
    "470": "MT",  # Malta
    "478": "MR",  # Mauritania
    "480": "MU",  # Mauritius
    "484": "MX",  # Mexico
    "492": "MC",  # Monaco
    "496": "MN",  # Mongolia
    "498": "MD",  # Moldova
    "499": "ME",  # Montenegro
    "500": "MS",  # Montserrat
    "504": "MA",  # Morocco
    "508": "MZ",  # Mozambique
    "512": "OM",  # Oman
    "516": "NA",  # Namibia
    "520": "NR",  # Nauru
    "524": "NP",  # Nepal
    "528": "NL",  # Netherlands
    "531": "CW",  # Curaçao
    "533": "AW",  # Aruba
    "534": "SX",  # Sint Maarten
    "540": "NC",  # New Caledonia
    "548": "VU",  # Vanuatu
    "554": "NZ",  # New Zealand
    "558": "NI",  # Nicaragua
    "562": "NE",  # Niger
    "566": "NG",  # Nigeria
    "570": "NU",  # Niue
    "574": "NF",  # Norfolk Island
    "578": "NO",  # Norway
    "580": "MP",  # N. Mariana Is.
    "583": "FM",  # Micronesia
    "584": "MH",  # Marshall Is.
    "585": "PW",  # Palau
    "586": "PK",  # Pakistan
    "591": "PA",  # Panama
    "598": "PG",  # Papua New Guinea
    "600": "PY",  # Paraguay
    "604": "PE",  # Peru
    "608": "PH",  # Philippines
    "612": "PN",  # Pitcairn Is.
    "616": "PL",  # Poland
    "620": "PT",  # Portugal
    "624": "GW",  # Guinea-Bissau
    "626": "TL",  # Timor-Leste
    "630": "PR",  # Puerto Rico
    "634": "QA",  # Qatar
    "642": "RO",  # Romania
    "643": "RU",  # Russia
    "646": "RW",  # Rwanda
    "652": "BL",  # St-Barthélemy
    "654": "SH",  # Saint Helena
    "659": "KN",  # St. Kitts and Nevis
    "660": "AI",  # Anguilla
    "662": "LC",  # Saint Lucia
    "663": "MF",  # St-Martin
    "666": "PM",  # St. Pierre and Miquelon
    "670": "VC",  # St. Vincent and the Grenadines
    "674": "SM",  # San Marino
    "678": "ST",  # São Tomé and Príncipe
    "682": "SA",  # Saudi Arabia
    "686": "SN",  # Senegal
    "688": "RS",  # Serbia
    "690": "SC",  # Seychelles
    "694": "SL",  # Sierra Leone
    "702": "SG",  # Singapore
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
    "776": "TO",  # Tonga
    "780": "TT",  # Trinidad and Tobago
    "784": "AE",  # United Arab Emirates
    "788": "TN",  # Tunisia
    "792": "TR",  # Turkey
    "795": "TM",  # Turkmenistan
    "796": "TC",  # Turks and Caicos Is.
    "798": "TV",  # Tuvalu
    "800": "UG",  # Uganda
    "804": "UA",  # Ukraine
    "807": "MK",  # Macedonia
    "818": "EG",  # Egypt
    "826": "GB",  # United Kingdom
    "831": "GG",  # Guernsey
    "832": "JE",  # Jersey
    "833": "IM",  # Isle of Man
    "834": "TZ",  # Tanzania
    "840": "US",  # United States of America
    "850": "VI",  # U.S. Virgin Is.
    "854": "BF",  # Burkina Faso
    "858": "UY",  # Uruguay
    "860": "UZ",  # Uzbekistan
    "862": "VE",  # Venezuela
    "876": "WF",  # Wallis and Futuna Is.
    "882": "WS",  # Samoa
    "887": "YE",  # Yemen
    "894": "ZM",  # Zambia
}


class WorldMapError(RuntimeError):
    """A missing, unpinned or malformed input: nothing is written."""


def to_pixels(lon: float, lat: float) -> tuple[float, float]:
    """Position in the viewBox (0..WIDTH by 0..HEIGHT, y pointing down)."""

    x, y = natural_earth(lon, lat)
    return (x + NE_XM) * SCALE, (NE_YM - y) * SCALE


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
    """One ``{id, name, iso_a2, d}`` entry per country that still has a visible outline.

    A country that world-atlas splits into several geometries (Australia with Ashmore and Cartier
    Islands) gets one entry: its paths are joined and the name and id come from the geometry with
    the longest path. Geometries without an ISO code stay separate.
    """

    arcs = decode_arcs(topology)
    outlines: dict[str, dict[str, Any]] = {}
    primary_length: dict[str, int] = {}
    for geometry in topology["objects"]["countries"]["geometries"]:
        country_id = geometry.get("id")
        if country_id == ANTARCTICA:
            continue
        d = geometry_path(geometry, arcs)
        if not d:
            continue
        iso = ISO_NUMERIC_TO_ALPHA2.get(country_id or "")
        key = iso or f"{country_id}|{geometry.get('properties', {}).get('name', '')}"
        if key in outlines:
            outlines[key]["d"] += d
            if len(d) > primary_length[key]:
                primary_length[key] = len(d)
                outlines[key].update(
                    id=country_id, name=geometry.get("properties", {}).get("name", "")
                )
            continue
        primary_length[key] = len(d)
        outlines[key] = {
            "id": country_id,
            "name": geometry.get("properties", {}).get("name", ""),
            "iso_a2": iso,
            "d": d,
        }
    return list(outlines.values())


def shoelace_area(points: Sequence[tuple[float, float]]) -> float:
    """Absolute area of a closed ring of projected points (pixels squared)."""

    total = 0.0
    for (x0, y0), (x1, y1) in zip(points, [*points[1:], points[0]]):
        total += x0 * y1 - x1 * y0
    return abs(total) / 2


def small_markers(topology: Mapping[str, Any]) -> list[dict[str, Any]]:
    """``{iso, x, y, lon, lat}`` for every country under SMALL_AREA_PX2 projected area.

    The area sums the outer rings of each polygon (holes and seam copies are not counted). The
    marker sits at the mean vertex of the largest outer ring, so a scattered state (Kiribati,
    Micronesia) is marked on its largest island. Countries that world-atlas omits are listed in
    MANUAL_MARKERS. Only countries with an ISO alpha-2 code get a marker.
    """

    arcs = decode_arcs(topology)
    rings_by_iso: dict[str, list[list[tuple[float, float]]]] = {}
    for geometry in topology["objects"]["countries"]["geometries"]:
        country_id = geometry.get("id")
        iso = ISO_NUMERIC_TO_ALPHA2.get(country_id or "")
        if country_id == ANTARCTICA or not iso:
            continue
        if geometry.get("type") == "MultiPolygon":
            polygons = geometry["arcs"]
        elif geometry.get("type") == "Polygon":
            polygons = [geometry["arcs"]]
        else:
            continue
        # A country can have more than one geometry (world-atlas splits off some islets), so the
        # rings are pooled per code before the threshold is applied.
        rings = rings_by_iso.setdefault(iso, [])
        for polygon in polygons:
            if polygon:
                ring = unwrap_longitudes(ring_coordinates(arcs, polygon[0]))
                if ring:
                    rings.append(ring)
    markers: dict[str, dict[str, Any]] = {}
    for iso, rings in rings_by_iso.items():
        if not rings:
            continue
        areas = [shoelace_area([to_pixels(lon, lat) for lon, lat in ring]) for ring in rings]
        if sum(areas) >= SMALL_AREA_PX2:
            continue
        largest = rings[areas.index(max(areas))]
        lon = sum(lon for lon, _ in largest) / len(largest)
        lat = sum(lat for _, lat in largest) / len(largest)
        lon = ((lon + 180) % 360) - 180
        markers[iso] = _marker(iso, lon, lat)
    for country_id, (lon, lat) in MANUAL_MARKERS.items():
        iso = ISO_NUMERIC_TO_ALPHA2[country_id]
        markers.setdefault(iso, _marker(iso, lon, lat))
    return [markers[iso] for iso in sorted(markers)]


def _marker(iso: str, lon: float, lat: float) -> dict[str, Any]:
    x, y = to_pixels(lon, lat)
    return {
        "iso": iso,
        "x": round(x, 1),
        "y": round(y, 1),
        "lon": round(lon, 2),
        "lat": round(lat, 2),
    }


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
        "small": small_markers(countries_topology),
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
