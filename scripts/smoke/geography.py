"""Smoke-test the official California geography sources and licenses."""

from __future__ import annotations

import argparse
import json
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import pyogrio

NATURAL_EARTH_ARCHIVE_URL = (
    "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_1_states_provinces.zip"
)
NATURAL_EARTH_TERMS_URL = "https://www.naturalearthdata.com/about/terms-of-use/"
CDFW_ARCHIVE_URL = (
    "https://filelib.wildlife.ca.gov/Public/BDB/GIS/BIOS/Public_Datasets/3100_3199/ds3158.zip"
)

CDFW_ITEM_URL = (
    "https://www.arcgis.com/sharing/rest/content/items/28454c15a784418fa5488241559bcd18?f=json"
)


def _json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "CA-Plastics-Atlas/0.0"})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        return json.load(response)


def _text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "CA-Plastics-Atlas/0.0"})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "CA-Plastics-Atlas/0.0"})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        destination.write_bytes(response.read())


def smoke(land_archive: Path | None = None, cdfw_archive: Path | None = None) -> None:
    natural_earth_terms = _text(NATURAL_EARTH_TERMS_URL).lower()
    assert "public domain" in natural_earth_terms
    cdfw_item = _json(CDFW_ITEM_URL)
    assert cdfw_item["id"] == "28454c15a784418fa5488241559bcd18"
    assert "creativecommons.org/licenses/by/4.0" in cdfw_item["licenseInfo"].lower()

    with tempfile.TemporaryDirectory(prefix="ca-atlas-geo-smoke-") as temporary:
        temp_dir = Path(temporary)
        natural_earth_source = land_archive or temp_dir / "ne_admin1.zip"
        if land_archive is None:
            _download(NATURAL_EARTH_ARCHIVE_URL, natural_earth_source)
        with zipfile.ZipFile(natural_earth_source) as source_zip:
            source_zip.extractall(temp_dir / "land")
        land_layers = pyogrio.list_layers(temp_dir / "land")
        assert ["ne_10m_admin_1_states_provinces", "Polygon"] in land_layers.tolist()

        cdfw_source = cdfw_archive or temp_dir / "ds3158.zip"
        if cdfw_archive is None:
            _download(CDFW_ARCHIVE_URL, cdfw_source)
        with zipfile.ZipFile(cdfw_source) as source_zip:
            source_zip.extractall(temp_dir / "cdfw")
        line_layers = pyogrio.list_layers(temp_dir / "cdfw" / "ds3158.gdb")
        polygon_layers = pyogrio.list_layers(temp_dir / "cdfw" / "ds3158_alt.gdb")
        assert ["ds3158", "MultiLineString"] in line_layers.tolist()
        assert ["ds3158_poly", "MultiPolygon"] in polygon_layers.tolist()

    print("Natural Earth: 1:10m Admin 1 polygon archive available")
    print("Natural Earth license: public domain")
    print("CDFW: official ds3158 archive contains line and ds3158_poly multipolygon")
    print("CDFW license: Creative Commons Attribution 4.0")
    print(f"CDFW source: {urllib.parse.urlsplit(CDFW_ARCHIVE_URL).netloc}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--land-archive", type=Path)
    parser.add_argument("--cdfw-archive", type=Path)
    args = parser.parse_args()
    smoke(args.land_archive, args.cdfw_archive)


if __name__ == "__main__":
    main()
