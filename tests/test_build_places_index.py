"""Tests for scripts/build_places_index.py (AMB-1 place-search index).

Unit tests use small in-memory inputs and never touch the network. The committed-file tests read
site/data/global/places.json; the --check test runs only when the raw caches are present.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLACES = ROOT / "site" / "data" / "global" / "places.json"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "build_places_index", ROOT / "scripts" / "build_places_index.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bpi = _load_module()


def test_bbox_keeps_the_narrow_side_of_the_antimeridian() -> None:
    # A ring from 170 E to 170 W is 20 degrees wide across 180, not 340 degrees wide.
    assert bpi._bbox_of_points([(170.0, 0.0), (-170.0, 10.0)]) == [170.0, 0.0, 190.0, 10.0]
    assert bpi._bbox_of_points([(0.0, 0.0), (30.0, 20.0)]) == [0.0, 0.0, 30.0, 20.0]


def test_city_entries_apply_the_population_floor_and_parent_rule() -> None:
    table = {"NO": {"name": "Norway"}, "XX": {"name": "Nowhere"}}
    rows = [
        {
            "name": "Bergen",
            "iso": "NO",
            "lon": 5.32,
            "lat": 60.39,
            "population": 294029,
            "admin1": "Hordaland",
        },
        {
            "name": "Oslo",
            "iso": "NO",
            "lon": 10.75,
            "lat": 59.91,
            "population": 709037,
            "admin1": "Oslo",
        },
        {"name": "Small", "iso": "NO", "lon": 10.0, "lat": 60.0, "population": 14999, "admin1": ""},
        {"name": "Ghost", "iso": "ZZ", "lon": 0.0, "lat": 0.0, "population": 50000, "admin1": ""},
    ]
    entries = bpi.city_entries(rows, table)
    assert [e[0] for e in entries] == ["Bergen", "Oslo"]
    assert entries[0][2] == "Hordaland, Norway"
    # A region with the city's own name adds nothing to the parent label.
    assert entries[1][2] == "Norway"
    assert entries[0][4] == [5.32, 60.39]


def test_admin1_entries_skip_unnamed_and_unknown_countries() -> None:
    table = {"PW": {"name": "Palau"}}
    rows = [
        {"name": "Koror", "iso": "PW", "geom": [134.35, 7.22, 134.53, 7.36], "point": None},
        {"name": "", "iso": "PW", "geom": [0, 0, 1, 1], "point": None},
        {"name": "Nowhere", "iso": "ZZ", "geom": [0, 0, 1, 1], "point": None},
        {"name": "Dateline", "iso": "PW", "geom": None, "point": [179.9, -1.0]},
    ]
    entries = bpi.admin1_entries(rows, table)
    assert [(e[0], e[2], e[4]) for e in entries] == [
        ("Koror", "Palau", [134.35, 7.22, 134.53, 7.36]),
        ("Dateline", "Palau", [179.9, -1.0]),
    ]


def test_build_payload_uses_indices_for_kind_and_parent() -> None:
    countries = [["Palau", "country", "", "PW", [131.1, 2.9, 134.7, 7.7], None]]
    admin1 = [["Koror", "admin1", "Palau", "PW", [134.3, 7.2, 134.5, 7.3], None]]
    cities = [["Ngerulmud", "city", "Palau", "PW", [134.6, 7.5], 15000]]
    payload = bpi.build_payload(countries, admin1, cities, {"PW": ["Belau"]}, [["PW", 134.6, 7.5]])
    assert payload["kinds"] == ["country", "admin1", "city"]
    assert payload["counts"] == {"country": 1, "admin1": 1, "city": 1}
    assert payload["aliases"] == {"PW": ["Belau"]}
    assert payload["markers"] == [["PW", 134.6, 7.5]]
    assert payload["fields"] == ["name", "kind", "parent", "iso2", "geom", "population"]
    kinds = [payload["kinds"][entry[1]] for entry in payload["entries"]]
    assert kinds == ["country", "admin1", "city"]
    parents = [payload["parents"][entry[2]] for entry in payload["entries"]]
    assert parents == ["", "Palau", "Palau"]
    assert "CC BY 4.0" in payload["licence"]["geonames"]
    assert "public domain" in payload["licence"]["natural_earth"]


def test_build_payload_refuses_an_input_with_no_places() -> None:
    with pytest.raises(bpi.PlacesError, match="no places"):
        bpi.build_payload([], [], [], {}, [])


def test_serialise_is_compact_utf8_with_a_trailing_newline() -> None:
    data = bpi.serialise({"entries": [["Malmö", 2]]})
    assert data == '{"entries":[["Malmö",2]]}\n'.encode()


def test_check_digest_rejects_a_changed_input() -> None:
    with pytest.raises(bpi.PlacesError, match="does not match the pinned"):
        bpi.check_digest(b"not the file", bpi.GEONAMES_SHA256, "cities15000.zip")


def _committed() -> dict[str, Any]:
    return json.loads(PLACES.read_text(encoding="utf-8"))


def _named(payload: dict[str, Any], name: str, kind: str) -> list[list[Any]]:
    kinds = payload["kinds"]
    return [entry for entry in payload["entries"] if entry[0] == name and kinds[entry[1]] == kind]


def test_committed_places_contain_the_required_places() -> None:
    payload = _committed()
    assert payload["schema"] == "places-v1"
    counts = payload["counts"]
    assert counts["country"] >= 230 and counts["admin1"] >= 4000 and counts["city"] >= 30000
    palau = _named(payload, "Palau", "country")
    assert palau and palau[0][3] == "PW"
    assert payload["parents"][_named(payload, "Koror", "admin1")[0][2]] == "Palau"
    hordaland = _named(payload, "Hordaland", "admin1")
    assert hordaland and payload["parents"][hordaland[0][2]] == "Norway"
    bergen = [e for e in _named(payload, "Bergen", "city") if e[3] == "NO"]
    assert bergen and payload["parents"][bergen[0][2]] == "Hordaland, Norway"
    for name in ("Nauru", "Singapore", "Tuvalu"):
        assert _named(payload, name, "country"), name


def test_committed_places_credit_both_sources_and_stay_small() -> None:
    payload = _committed()
    assert "CC BY 4.0" in payload["credit"] and "public domain" in payload["credit"]
    assert "geonames.org" in payload["licence"]["geonames"]
    assert PLACES.stat().st_size < 2_500_000
    assert {m[0] for m in payload["markers"]} >= set(
        "PW NR TV MH FM KI MV SC MT SG LI MC SM AD VA".split()
    )


def test_committed_places_rows_are_well_formed() -> None:
    payload = _committed()
    assert len(payload["entries"]) == sum(payload["counts"].values())
    for entry in payload["entries"]:
        name, kind, parent, iso, geom, population = entry
        assert isinstance(name, str) and name.strip() == name and name
        assert payload["kinds"][kind] in ("country", "admin1", "city")
        assert isinstance(payload["parents"][parent], str)
        assert len(iso) == 2 and iso.isupper()
        assert len(geom) in (2, 4)
        if payload["kinds"][kind] == "city":
            assert population >= bpi.MIN_POPULATION
        else:
            assert population is None


def test_check_mode_matches_the_committed_file(tmp_path: Path) -> None:
    world = bpi._load_world_module()
    if not (
        (bpi.DEFAULT_RAW_DIR / bpi.NE_ADMIN1_FILE).exists()
        and (bpi.DEFAULT_RAW_DIR / bpi.GEONAMES_FILE).exists()
        and (bpi.DEFAULT_WORLD_RAW_DIR / world.COUNTRIES_FILE).exists()
    ):
        pytest.skip("place caches are not present; run scripts/build_places_index.py once")
    assert bpi.main(["--check", "--output", str(PLACES)]) == 0
    assert bpi.main(["--check", "--output", str(tmp_path / "missing.json")]) == 1
