"""Smoke-test the official GeoNames California-gazetteer source and license."""

from __future__ import annotations

import urllib.request

GEONAMES_US_ARCHIVE_URL = "https://download.geonames.org/export/dump/US.zip"
GEONAMES_README_URL = "https://download.geonames.org/export/dump/readme.txt"
USER_AGENT = "CA-Plastics-Atlas/0.0"


def _request(url: str):
    return urllib.request.urlopen(  # noqa: S310
        urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=120
    )


def smoke() -> None:
    with _request(GEONAMES_README_URL) as response:
        readme = response.read().decode("utf-8", errors="replace")
    assert "Creative Commons Attribution 4.0 License" in readme
    assert "XX.zip" in readme
    with _request(GEONAMES_US_ARCHIVE_URL) as response:
        assert response.read(4) == b"PK\x03\x04"
    print("GeoNames: US.zip is downloadable")
    print("GeoNames license: CC BY 4.0")
    print("GeoNames format: UTF-8 tab-delimited geoname fields")


if __name__ == "__main__":
    smoke()
