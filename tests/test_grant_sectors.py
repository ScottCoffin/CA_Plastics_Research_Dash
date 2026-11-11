"""Grant recipient sectors and funder agencies (config/grant_sectors.yml)."""

from __future__ import annotations

import pytest

from atlas.build.grant_sectors import load_sector_rules


@pytest.fixture(scope="module")
def rules():
    return load_sector_rules()


@pytest.mark.parametrize(
    ("org", "inst_type", "expected"),
    [
        ("UNIVERSITY OF CALIFORNIA, DAVIS", None, "academia"),
        ("Hobart and William Smith Colleges", None, "academia"),
        ("Southern California Coastal Water Research Project", None, "jpa"),
        ("San Francisco Estuary Institute", None, "nonprofit"),
        ("EARTH ISLAND INSTITUTE INC", None, "nonprofit"),
        ("Woods Hole Oceanographic Institution", None, "nonprofit"),
        ("BIKO BIOLABS, LLC", None, "industry"),
        ("CITY OF OAKLAND", None, "government"),
        ("CALIFORNIA COASTAL COMMISSION", "local-agency", "government"),
        ("WIYOT TRIBE", None, "government"),
        ("Savoca, Matthew S", None, "individual"),
        ("Unlisted Thing", "UC", "academia"),
        ("", None, "unknown"),
    ],
)
def test_sector(rules, org, inst_type, expected) -> None:
    assert rules.sector(org, inst_type)[0] == expected


def test_state_vs_local_detail(rules) -> None:
    assert rules.sector("CALIFORNIA COASTAL COMMISSION", "local-agency") == ("government", "state")


def test_funder_agency(rules) -> None:
    assert (
        rules.agency(["Department of Commerce", "National Oceanic and Atmospheric Administration"])
        == "NOAA"
    )
    assert rules.agency(["National Science Foundation", "National Science Foundation"]) == "NSF"
    assert rules.agency(["NIH", "NIEHS"]) == "NIH"
    assert rules.agency([], "Some New Funder") == "Some New Funder"
    assert rules.agency(None, None) == "Unknown funder"


def test_every_sector_has_label(rules) -> None:
    assert {"academia", "nonprofit", "jpa", "government", "industry", "unknown"} <= set(
        rules.labels
    )
