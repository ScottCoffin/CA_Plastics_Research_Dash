"""California GeoNames gazetteer lookup with curated aliases and safe exclusions."""

from __future__ import annotations

import csv
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE_PATH = _REPO_ROOT / "data" / "processed" / "gazetteer_ca.sqlite"
DEFAULT_ALIASES_PATH = _REPO_ROOT / "config" / "gazetteer_ca.csv"
DEFAULT_BLACKLIST_PATH = _REPO_ROOT / "config" / "gazetteer_blacklist.csv"


@dataclass(frozen=True)
class GazetteerMatch:
    """One exact California place-name match suitable for later disambiguation."""

    name: str
    latitude: float
    longitude: float
    feature_type: str
    geonames_id: int | None
    source: str
    matched_name: str


def normalize_name(value: str) -> str:
    """Return a case- and punctuation-insensitive exact-match key."""

    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    normalized = normalized.casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", normalized)).strip()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _blacklist(path: Path) -> set[str]:
    return {normalize_name(row["name"]) for row in _read_csv(path) if row.get("name")}


def is_blacklisted(name: str, *, blacklist_path: str | Path = DEFAULT_BLACKLIST_PATH) -> bool:
    """Whether a name is explicitly excluded from automatic geographic matching."""

    return normalize_name(name) in _blacklist(Path(blacklist_path))


def _alias_matches(name: str, path: Path) -> list[GazetteerMatch]:
    normalized = normalize_name(name)
    matches: list[GazetteerMatch] = []
    for row in _read_csv(path):
        aliases = (row.get("alias") or "").split("|")
        if normalized not in {normalize_name(alias) for alias in aliases if alias}:
            continue
        geonames_id = row.get("geonames_id", "").strip()
        matches.append(
            GazetteerMatch(
                name=row["name"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                feature_type=row["feature_type"],
                geonames_id=int(geonames_id) if geonames_id else None,
                source="curated_alias",
                matched_name=name,
            )
        )
    return matches


def lookup(
    name: str,
    *,
    database_path: str | Path = DEFAULT_DATABASE_PATH,
    aliases_path: str | Path = DEFAULT_ALIASES_PATH,
    blacklist_path: str | Path = DEFAULT_BLACKLIST_PATH,
) -> tuple[GazetteerMatch, ...]:
    """Return exact GeoNames and curated California matches for ``name``.

    The ambiguity blacklist is checked before either source so callers cannot
    accidentally promote a common word to a location without context.
    """

    query = normalize_name(name)
    if not query or is_blacklisted(query, blacklist_path=blacklist_path):
        return ()

    matches = _alias_matches(name, Path(aliases_path))
    database = Path(database_path)
    if not database.exists():
        raise FileNotFoundError(f"Gazetteer database does not exist: {database}")
    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            """
            SELECT feature.name, feature.latitude, feature.longitude,
                   feature.feature_class || '.' || feature.feature_code,
                   feature.geonames_id, name_variant.display_name
            FROM name_variant
            JOIN feature USING (geonames_id)
            WHERE name_variant.normalized_name = ?
            ORDER BY feature.population DESC, feature.geonames_id
            """,
            (query,),
        ).fetchall()
    matches.extend(
        GazetteerMatch(
            name=row[0],
            latitude=row[1],
            longitude=row[2],
            feature_type=row[3],
            geonames_id=row[4],
            source="geonames",
            matched_name=row[5],
        )
        for row in rows
    )
    return tuple(matches)
