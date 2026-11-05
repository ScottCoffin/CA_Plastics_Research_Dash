"""Build full-resolution and browser California geography assets."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import mapping
from shapely.validation import make_valid

NATURAL_EARTH_ARCHIVE_URL = (
    "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip"
)
CDFW_ARCHIVE_URL = (
    "https://filelib.wildlife.ca.gov/Public/BDB/GIS/BIOS/Public_Datasets/3100_3199/ds3158.zip"
)

ROOT = Path(__file__).resolve().parents[1]
FULL_DIR = ROOT / "data" / "processed" / "geo"
BROWSER_PATH = ROOT / "site" / "assets" / "ca_boundaries.geojson"


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "CA-Plastics-Atlas/0.0"})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        with destination.open("wb") as output:
            shutil.copyfileobj(response, output)


def _load_land(archive: Path, extract_dir: Path) -> tuple[object, dict[str, str]]:
    with zipfile.ZipFile(archive) as source_zip:
        source_zip.extractall(extract_dir)
    shapefile = extract_dir / "ne_10m_admin_1_states_provinces.shp"
    frame = gpd.read_file(shapefile)
    california = frame[
        (frame["admin"] == "United States of America") & (frame["iso_3166_2"] == "US-CA")
    ]
    if len(california) != 1:
        raise RuntimeError("Natural Earth did not contain exactly one US-CA feature")
    geometry = make_valid(california.geometry.iloc[0])
    return geometry, {
        "boundary": "land",
        "source": "Natural Earth 1:10m Admin 1 states and provinces, version 5.1.1",
        "source_url": NATURAL_EARTH_ARCHIVE_URL,
        "license": "Public domain",
    }


def _load_cdfw_waters(archive: Path, extract_dir: Path) -> tuple[object, dict[str, str]]:
    with zipfile.ZipFile(archive) as source_zip:
        source_zip.extractall(extract_dir)
    geodatabase = extract_dir / "ds3158_alt.gdb"
    frame = gpd.read_file(geodatabase, layer="ds3158_poly").to_crs(4326)
    if len(frame) != 1 or frame.geometry.iloc[0].geom_type not in {"Polygon", "MultiPolygon"}:
        raise RuntimeError("CDFW archive did not contain the expected state-waters polygon")
    geometry = make_valid(frame.geometry.iloc[0])
    return geometry, {
        "boundary": "state_waters",
        "source": "California Department of Fish and Wildlife ds3158 polygon",
        "source_url": CDFW_ARCHIVE_URL,
        "license": "CC BY 4.0",
    }


def _feature(geometry, properties: dict[str, str]) -> dict:
    return {"type": "Feature", "properties": properties, "geometry": mapping(geometry)}


def _write_collection(path: Path, features: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"type": "FeatureCollection", "features": features}
    with path.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(payload, output, ensure_ascii=True, separators=(",", ":"))
        output.write("\n")


def _write_full_resolution(path: Path, geometry, properties: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {**properties, "geometry": geometry}
    gpd.GeoDataFrame([row], geometry="geometry", crs="EPSG:4326").to_parquet(path, index=False)


def build(
    land_archive: Path | None = None,
    cdfw_archive: Path | None = None,
    simplify_tolerance: float = 0.002,
) -> None:
    with tempfile.TemporaryDirectory(prefix="ca-atlas-geo-") as temporary:
        temp_dir = Path(temporary)
        natural_earth_archive = land_archive or temp_dir / "ne_admin1.zip"
        if land_archive is None:
            _download(NATURAL_EARTH_ARCHIVE_URL, natural_earth_archive)
        cdfw_source_archive = cdfw_archive or temp_dir / "ds3158.zip"
        if cdfw_archive is None:
            _download(CDFW_ARCHIVE_URL, cdfw_source_archive)

        land, land_properties = _load_land(natural_earth_archive, temp_dir / "land")
        waters, water_properties = _load_cdfw_waters(cdfw_source_archive, temp_dir / "cdfw")

        _write_full_resolution(FULL_DIR / "ca_land.parquet", land, land_properties)
        _write_full_resolution(FULL_DIR / "ca_state_waters.parquet", waters, water_properties)

        browser_features = [
            _feature(land.simplify(simplify_tolerance, preserve_topology=True), land_properties),
            _feature(waters.simplify(simplify_tolerance, preserve_topology=True), water_properties),
        ]
        _write_collection(BROWSER_PATH, browser_features)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--land-archive",
        type=Path,
        help="Use a downloaded Natural Earth Admin 1 archive",
    )
    parser.add_argument(
        "--cdfw-archive",
        type=Path,
        help="Use a previously downloaded official ds3158.zip instead of downloading it",
    )
    parser.add_argument("--simplify-tolerance", type=float, default=0.002)
    args = parser.parse_args()
    build(args.land_archive, args.cdfw_archive, args.simplify_tolerance)
    print(f"land={FULL_DIR / 'ca_land.parquet'}")
    print(f"state_waters={FULL_DIR / 'ca_state_waters.parquet'}")
    print(f"browser={BROWSER_PATH} bytes={BROWSER_PATH.stat().st_size}")


if __name__ == "__main__":
    main()
