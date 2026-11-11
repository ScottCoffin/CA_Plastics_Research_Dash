from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.ingest.institutions import classify_atlas_type
from atlas.ingest.normalize import normalize_records
from atlas.ingest.state_agencies import (
    apply_state_agencies,
    load_state_agencies,
    match_state_agencies,
)

CONFIG = Path("config/ca_state_agencies.yml")
CALEPA = "I65137940"
STATE_OF_CA = "I4389425283"
AGENCIES = load_state_agencies(CONFIG)


def _match(text: str) -> list[str]:
    return match_state_agencies(text, AGENCIES)


def _gov(name: str, openalex_type: str = "government", ror_types=("government",)) -> str:
    record = {
        "display_name": name,
        "type": openalex_type,
        "ror_record": {"types": list(ror_types)},
    }
    return classify_atlas_type(record, [])[0]


def test_config_ids_are_unique_and_cover_required_agencies() -> None:
    ids = {agency.id for agency in AGENCIES}
    assert len(ids) == len(AGENCIES)
    assert {"CAAG-OEHHA", "CAAG-SWRCB", "CAAG-SLC"} <= ids
    assert {f"CAAG-RWQCB{n}" for n in range(1, 10)} <= ids
    assert all(a.atlas_type == "state-agency" and a.lat and a.lon for a in AGENCIES)
    assert {a.parent_id for a in AGENCIES} <= {CALEPA, STATE_OF_CA}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Office of Environmental Health Hazard Assessment, California Environmental "
            "Protection Agency, 1515 Clay Street, Oakland, CA",
            ["CAAG-OEHHA"],
        ),
        ("California Office of Environmental Health and Hazard Assessment", ["CAAG-OEHHA"]),
        ("California State Water Resources Control Board, Sacramento", ["CAAG-SWRCB"]),
        (
            "California State Water Resources Control Board–Division of Drinking Water",
            ["CAAG-SWRCB"],
        ),
        (
            "Citizen Monitoring Coordinator, SWRCB-SWAMP-Clean Water Team, Los Angeles",
            ["CAAG-SWRCB"],
        ),
        ("Division of Drinking Water, Sacramento, California", ["CAAG-SWRCB"]),
        ("San Diego Regional Water Quality Control Board, San Diego, CA", ["CAAG-RWQCB9"]),
        ("California Regional Water Quality Control Board, Region 2", ["CAAG-RWQCB2"]),
        ("Central Valley Water Board, Rancho Cordova", ["CAAG-RWQCB5"]),
        (
            "Marine Invasive Species Program, California State Lands Commission, Long Beach",
            ["CAAG-SLC"],
        ),
    ],
)
def test_resolver_positive_patterns(text: str, expected: list[str]) -> None:
    assert _match(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "University of California, Davis, Department of Environmental Toxicology",
        "California Environmental Protection Agency, Sacramento, CA",
        "Division of Drinking Water, Texas Commission on Environmental Quality, Austin",
        "State Lands Department of Queensland",
        "San Diego County Water Authority",
        "Los Angeles Department of Water and Power",
        "",
    ],
)
def test_resolver_negatives(text: str) -> None:
    assert _match(text) == []


def test_resolver_matches_each_segment_separately() -> None:
    both = "State Water Resources Control Board | Office of Environmental Health Hazard Assessment"
    assert _match(both) == ["CAAG-OEHHA", "CAAG-SWRCB"]


def test_umbrella_replacement_has_no_double_count() -> None:
    assert apply_state_agencies([CALEPA, "I1"], ["CAAG-OEHHA"]) == ["I1", "CAAG-OEHHA"]
    assert apply_state_agencies([STATE_OF_CA], ["CAAG-SWRCB"]) == ["CAAG-SWRCB"]
    assert apply_state_agencies([CALEPA, STATE_OF_CA], ["CAAG-SWRCB", "CAAG-SLC"]) == [
        "CAAG-SWRCB",
        "CAAG-SLC",
    ]
    # No match leaves the umbrella alone; a real agency record is never removed.
    assert apply_state_agencies([CALEPA], []) == [CALEPA]
    assert apply_state_agencies(["I1336788258", CALEPA], ["CAAG-OEHHA"]) == [
        "I1336788258",
        "CAAG-OEHHA",
    ]


def _registry(path: Path) -> Path:
    rows = [
        {"openalex_id": CALEPA, "display_name": "California Environmental Protection Agency"},
        {"openalex_id": STATE_OF_CA, "display_name": "State of California"},
    ]
    table = pa.Table.from_pylist(
        [
            {
                **row,
                "ror_id": "",
                "atlas_type": "state-agency",
                "ror_types": ["government"],
                "lineage": [row["openalex_id"]],
                "country_code": "US",
                "region": "California",
                "city": "Sacramento",
                "latitude": 38.5,
                "longitude": -121.5,
            }
            for row in rows
        ]
    )
    pq.write_table(table, path)
    return path


def _work(work_id: str, author: str, institutions: list[str], raw: str) -> dict:
    return {
        "id": f"https://openalex.org/{work_id}",
        "title": f"Microplastics {work_id}",
        "publication_year": 2024,
        "authorships": [
            {
                "author": {"id": f"https://openalex.org/{author}", "display_name": author},
                "author_position": "first",
                "institutions": [
                    {"id": f"https://openalex.org/{inst}", "display_name": inst}
                    for inst in institutions
                ],
                "raw_affiliation_strings": [raw],
            }
        ],
    }


def test_normalize_replaces_umbrella_and_emits_synthetic_rows(tmp_path: Path) -> None:
    records = [
        _work(
            "W1",
            "A1",
            [CALEPA],
            "Office of Environmental Health Hazard Assessment, California EPA, Oakland",
        ),
        _work("W2", "A2", [STATE_OF_CA], "State Water Resources Control Board, Sacramento"),
        _work("W3", "A3", [CALEPA], "California Environmental Protection Agency, Sacramento"),
        _work("W4", "A4", [], "State Lands Commission, Sacramento, California"),
    ]
    result = normalize_records(
        records,
        institution_path=_registry(tmp_path / "registry.parquet"),
        output_dir=tmp_path / "out",
        qc_path=tmp_path / "qc.md",
        source="test",
        author_overrides_path=tmp_path / "none.csv",
        suppressions_path=None,
        generated_at="test",
        state_agencies_path=CONFIG,
    )
    authorships = {
        row["work_id"]: row
        for row in pq.read_table(result.output_dir / "authorships.parquet").to_pylist()
    }
    assert authorships["W1"]["institution_ids"] == ["CAAG-OEHHA"]
    assert authorships["W2"]["institution_ids"] == ["CAAG-SWRCB"]
    assert authorships["W3"]["institution_ids"] == [CALEPA]  # umbrella kept, no agency named
    assert authorships["W4"]["institution_ids"] == ["CAAG-SLC"]
    assert all(authorships[w]["ca_basis"] == "registry" for w in authorships)
    institutions = {
        row["inst_id"]: row
        for row in pq.read_table(result.output_dir / "institutions.parquet").to_pylist()
    }
    oehha = institutions["CAAG-OEHHA"]
    assert oehha["ca_flag"] is True
    assert oehha["atlas_type"] == "state-agency"
    assert oehha["parent_system"] == CALEPA
    assert oehha["lat"] == pytest.approx(38.5767)
    assert institutions["CAAG-SLC"]["parent_system"] == STATE_OF_CA
    assert "CAAG-RWQCB1" not in institutions  # emitted only when an authorship links it


@pytest.mark.parametrize(
    ("name", "expected", "rule"),
    [
        ("California Department of Public Health", "state-agency", None),
        ("California Ocean Protection Council", "state-agency", None),
        ("California Arts Council", "state-agency", "government-state-name"),
        ("State of California", "state-agency", None),
        ("Judicial Council of California", "state-agency", "government-state-name"),
        ("California Department of Food and Agriculture", "state-agency", None),
        (
            "NOAA National Marine Fisheries Service Southwest Fisheries Science Center",
            "federal",
            None,
        ),
        ("Pacific Southwest Research Station", "federal", "government-federal-name"),
        ("Naval Air Warfare Center Weapons Division", "federal", "government-federal-name"),
        ("Kings Canyon National Park", "federal", "government-federal-name"),
        ("East Bay Municipal Utility District", "local-agency", "government-local-name"),
        ("Bay Area Air Quality Management District", "local-agency", "government-local-name"),
        ("Los Angeles Police Department", "local-agency", "government-local-name"),
    ],
)
def test_government_classification(name: str, expected: str, rule: str | None) -> None:
    record = {"display_name": name, "type": "government", "ror_record": {"types": ["government"]}}
    atlas_type, observed_rule = classify_atlas_type(record, [])
    assert atlas_type == expected
    if rule:
        assert observed_rule == rule


@pytest.mark.parametrize(
    ("name", "ror_types", "openalex_type"),
    [
        ("San Francisco Department of Public Health", ["healthcare"], "healthcare"),
        (
            "Los Angeles County Department of Public Health",
            ["government", "healthcare"],
            "government",
        ),
        ("Santa Clara County Public Health Department", ["nonprofit"], "nonprofit"),
        ("County of Sonoma Department of Health Services", ["government"], "government"),
        ("Monterey County Health Department", ["government"], "government"),
        ("City of San Diego Health Services", ["nonprofit"], "nonprofit"),
    ],
)
def test_county_public_health_is_local_agency(name, ror_types, openalex_type) -> None:
    record = {"display_name": name, "type": openalex_type, "ror_record": {"types": ror_types}}
    assert classify_atlas_type(record, [])[0] == "local-agency"


def test_county_health_rule_leaves_health_systems_alone() -> None:
    record = {
        "display_name": "Kaiser Permanente Northern California",
        "type": "healthcare",
        "ror_record": {"types": ["healthcare"]},
    }
    assert classify_atlas_type(record, [])[0] == "nonprofit/NGO"
    assert _gov("California Institute of Technology", "education", ["education"]) != "state-agency"


def test_rebuild_never_rewrites_owner_reviewed_queue(tmp_path) -> None:
    """Regression: a rebuild dropped owner reviews on 2026-11-06 (annotations lost)."""
    import inspect

    from atlas.ingest import institutions

    source = inspect.getsource(institutions.write_outputs)
    assert "owner_reviewed_at" in source and "if not owner_reviewed" in source
