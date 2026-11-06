from __future__ import annotations

import zipfile
from pathlib import Path

from atlas.geo.gazetteer import is_blacklisted, lookup, normalize_name
from scripts.build_gazetteer import build_gazetteer

FIXTURE = Path(__file__).parent / "fixtures" / "geonames_us_sample.txt"
ALIASES = Path("config/gazetteer_ca.csv")
BLACKLIST = Path("config/gazetteer_blacklist.csv")


def _database(tmp_path: Path) -> Path:
    archive = tmp_path / "US.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.write(FIXTURE, "US.txt")
    database = tmp_path / "gazetteer.sqlite"
    assert build_gazetteer(archive, database) == (3, 7)
    return database


def test_lookup_matches_geonames_aliases_and_blacklist(tmp_path: Path) -> None:
    database = _database(tmp_path)
    sacramento = lookup(
        "SACRAMENTO",
        database_path=database,
        aliases_path=ALIASES,
        blacklist_path=BLACKLIST,
    )
    assert sacramento[0].geonames_id == 5389489
    assert sacramento[0].source == "geonames"

    sf_bay = lookup(
        "SF Bay", database_path=database, aliases_path=ALIASES, blacklist_path=BLACKLIST
    )
    assert sf_bay[0].source == "curated_alias"
    assert sf_bay[0].name == "San Francisco Bay"

    assert is_blacklisted("orange", blacklist_path=BLACKLIST)
    assert (
        lookup("Orange", database_path=database, aliases_path=ALIASES, blacklist_path=BLACKLIST)
        == ()
    )


def test_builder_excludes_non_california_rows(tmp_path: Path) -> None:
    database = _database(tmp_path)
    assert (
        lookup("Madison", database_path=database, aliases_path=ALIASES, blacklist_path=BLACKLIST)
        == ()
    )
    assert normalize_name("San-Francisco  Bay") == "san francisco bay"
