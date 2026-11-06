"""Build the reproducible California GeoNames SQLite subset."""

from __future__ import annotations

import argparse
import csv
import io
import sqlite3
import urllib.request
import zipfile
from collections.abc import Iterable
from pathlib import Path

from atlas.geo.gazetteer import DEFAULT_DATABASE_PATH, normalize_name

GEONAMES_US_ARCHIVE_URL = "https://download.geonames.org/export/dump/US.zip"
GEONAMES_README_URL = "https://download.geonames.org/export/dump/readme.txt"
USER_AGENT = "CA-Plastics-Atlas/0.0"
GEONAMES_COLUMNS = (
    "geonames_id",
    "name",
    "asciiname",
    "alternate_names",
    "latitude",
    "longitude",
    "feature_class",
    "feature_code",
    "country_code",
    "cc2",
    "admin1_code",
    "admin2_code",
    "admin3_code",
    "admin4_code",
    "population",
    "elevation",
    "dem",
    "timezone",
    "modification_date",
)


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        destination.write_bytes(response.read())


def _database_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE feature (
            geonames_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            feature_class TEXT NOT NULL,
            feature_code TEXT NOT NULL,
            population INTEGER NOT NULL,
            country_code TEXT NOT NULL,
            admin1_code TEXT NOT NULL
        );
        CREATE TABLE name_variant (
            geonames_id INTEGER NOT NULL REFERENCES feature(geonames_id),
            normalized_name TEXT NOT NULL,
            display_name TEXT NOT NULL,
            PRIMARY KEY (geonames_id, normalized_name)
        );
        CREATE INDEX idx_name_variant_normalized_name ON name_variant(normalized_name);
        """
    )


def _rows(archive: Path) -> Iterable[dict[str, str]]:
    with zipfile.ZipFile(archive) as source_zip:
        member = next((name for name in source_zip.namelist() if name.endswith("US.txt")), None)
        if member is None:
            raise ValueError(f"Expected US.txt in GeoNames archive: {archive}")
        with source_zip.open(member) as binary_stream:
            text_stream = io.TextIOWrapper(binary_stream, encoding="utf-8")
            reader = csv.reader(text_stream, delimiter="\t")
            for values in reader:
                if len(values) != len(GEONAMES_COLUMNS):
                    raise ValueError(
                        f"Expected {len(GEONAMES_COLUMNS)} GeoNames columns, found {len(values)}"
                    )
                row = dict(zip(GEONAMES_COLUMNS, values, strict=True))
                if row["country_code"] == "US" and row["admin1_code"] == "CA":
                    yield row


def _variants(row: dict[str, str]) -> dict[str, str]:
    names = {row["name"], row["asciiname"], *row["alternate_names"].split(",")}
    variants: dict[str, str] = {}
    for name in names:
        normalized = normalize_name(name)
        if normalized:
            variants.setdefault(normalized, name)
    return variants


def build_gazetteer(
    archive: Path,
    destination: Path = DEFAULT_DATABASE_PATH,
) -> tuple[int, int]:
    """Create ``destination`` from a downloaded GeoNames U.S. archive."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    feature_count = 0
    variant_count = 0
    connection = sqlite3.connect(temporary)
    try:
        with connection:
            _database_schema(connection)
            for row in _rows(archive):
                geonames_id = int(row["geonames_id"])
                connection.execute(
                    """
                    INSERT INTO feature VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        geonames_id,
                        row["name"],
                        float(row["latitude"]),
                        float(row["longitude"]),
                        row["feature_class"],
                        row["feature_code"],
                        int(row["population"] or 0),
                        row["country_code"],
                        row["admin1_code"],
                    ),
                )
                variants = _variants(row)
                connection.executemany(
                    "INSERT INTO name_variant VALUES (?, ?, ?)",
                    (
                        (geonames_id, normalized, display)
                        for normalized, display in variants.items()
                    ),
                )
                feature_count += 1
                variant_count += len(variants)
            connection.executemany(
                "INSERT INTO metadata VALUES (?, ?)",
                [
                    ("source", "GeoNames US.zip"),
                    ("source_url", GEONAMES_US_ARCHIVE_URL),
                    ("license", "CC BY 4.0"),
                    ("subset_rule", "country_code=US and admin1_code=CA"),
                ],
            )
    finally:
        connection.close()
    temporary.replace(destination)
    return feature_count, variant_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Existing official US.zip archive")
    parser.add_argument("--output", type=Path, default=DEFAULT_DATABASE_PATH)
    args = parser.parse_args()
    if args.archive is not None:
        archive = args.archive
    else:
        raw_directory = Path("data/raw")
        raw_directory.mkdir(parents=True, exist_ok=True)
        archive = raw_directory / "geonames_us.zip"
        _download(GEONAMES_US_ARCHIVE_URL, archive)
    features, variants = build_gazetteer(archive, args.output)
    print(f"features={features}")
    print(f"name_variants={variants}")
    print(f"database={args.output}")


if __name__ == "__main__":
    main()
