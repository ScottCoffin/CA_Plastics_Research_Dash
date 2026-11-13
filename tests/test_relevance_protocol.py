"""REL-1 (2026-11-13): title-only relevance patterns, the chemicals-in-plastics policy and
the experts' California status. See docs/RELEVANCE_AUDIT_2026-11-13.md."""

from __future__ import annotations

from pathlib import Path

import pytest

from atlas.build.curation import load_work_low_confidence_false
from atlas.build.expert_metrics import california_status
from atlas.nlp.labels import title_relevant
from atlas.query import load_query_config

ROOT = Path(__file__).resolve().parents[1]
CONFIG = load_query_config(ROOT / "config" / "queries.yml")

# Real titles from the 2026-11-13 audit that the query rules missed.
MISSED = [
    "The plastic-associated microorganisms of the North Pacific Gyre",
    "Effect of supplemented diet on the kinetic profile of polystyrene biodegradation by"
    " Tenebrio molitor larvae",
    "Charting success for the Plastics Treaty",
    "Introduction to the Marine Policy special issue on abandoned, lost and discarded fishing gear",
    "Leachates from Cigarette Butts Can Persist in Marine Sediment",
    "Airborne Tire Particles in the Environment: A Possible Asthma Risk from Latex Proteins?",
    "Fields of plastic: Tracking the growing footprint of agricultural plastics using remote"
    " sensing in California",
    "Upcycling of polyvinyl chloride into polyalphaolefin lubricants",
]

# Real titles that must stay out (plasticity, unrelated polymers, archaeology).
KEPT_OUT = [
    "Investigating early brewing and filtering technology in late Neolithic: pottery residue"
    " analysis of the Wayaoli site in Southern China",
    "Engineering 2-Pyrone-4,6-Dicarboxylic Acid Production Reveals Metabolic Plasticity of Poplar",
    "Pillared Graphene Nanostructures for Electrochemical Energy Storage",
    "Controlling Polymer Morphology in Blade-Coated All-Polymer Solar Cells",
    "Polyethylene glycol hydrogels for biodegradable drug delivery",
    "",
]


@pytest.mark.parametrize("title", MISSED)
def test_title_patterns_catch_missed_titles(title: str) -> None:
    assert title_relevant(title, CONFIG)


@pytest.mark.parametrize("title", KEPT_OUT)
def test_title_patterns_skip_unrelated_titles(title: str) -> None:
    assert not title_relevant(title, CONFIG)


def test_title_patterns_must_be_a_list() -> None:
    with pytest.raises(ValueError):
        title_relevant("x", {"title_relevant_patterns": "plastic"})


def test_tier2_policy_is_on() -> None:
    assert CONFIG["relevance_policy"]["tier2_survives_low_confidence_false"] is True


def test_low_confidence_false_skips_owner_reviewed_and_true_rows(tmp_path: Path) -> None:
    path = tmp_path / "work_relevance.csv"
    path.write_bytes(
        b"work_id,plastic_related,assist_plastic_related,confidence,reason,reviewer,"
        b"reviewed_at,owner_review\n"
        b"W1,false,false,low,r,h,2026-11-13,pending\n"
        b"W2,false,false,low,r,h,2026-11-13,confirmed\n"
        b"W3,false,false,high,r,h,2026-11-13,pending\n"
        b"W4,true,true,low,r,h,2026-11-13,pending\n"
    )
    assert load_work_low_confidence_false(path) == frozenset({"W1"})
    assert load_work_low_confidence_false(tmp_path / "missing.csv") == frozenset()


def test_california_status_uses_registry_not_country_code() -> None:
    # OpenAlex "CA" is Canada: Toronto must not count as California.
    primary = [{"id": "I185261750", "name": "University of Toronto", "country_code": "CA"}]
    history = [
        {"id": "I185261750", "years": [2016, 2026]},
        {"id": "I84218800", "years": [2013, 2019]},
    ]
    status = california_status(primary, history, {"I84218800"})
    assert status == {"current_in_ca": False, "last_ca_year": 2019}


def test_california_status_current_and_unknown() -> None:
    assert california_status([{"id": "I1"}], [{"id": "I1", "years": [2026]}], {"I1"}) == {
        "current_in_ca": True,
        "last_ca_year": 2026,
    }
    assert california_status([], [], {"I1"}) == {"current_in_ca": None, "last_ca_year": None}
