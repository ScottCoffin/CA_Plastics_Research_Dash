"""S9.3 expert badges: funding (linked works or PI name at a CA organisation) and datasets."""

from __future__ import annotations

from atlas.build.expert_badges import build_badges, name_key

AUTHORS = [
    {"author_id": "A1", "name": "Ana María Barral", "work_ids": ["W1"]},
    {"author_id": "A2", "name": "Chelsea M. Rochman", "work_ids": ["W2"]},
    {"author_id": "A3", "name": "Ting Xu", "work_ids": []},
    {"author_id": "A4", "name": "Ting Xu", "work_ids": []},  # shared key: never matched by name
]


def _grant(key: str, pi: str, state: str = "CA", plastic: bool = True, end: str = "2027-01-01"):
    return {
        "grant_key": key,
        "pi_names": [pi],
        "org_state": state,
        "plastic_related": plastic,
        "title": f"Grant {key}",
        "end": end,
    }


def test_name_key_folds_accents_initials_and_comma_order() -> None:
    assert name_key("Ana María Barral") == ("ana", "barral")
    assert name_key("Barral, Ana Maria") == ("ana", "barral")
    assert name_key("Chelsea M. Rochman") == ("chelsea", "rochman")
    assert name_key("X") is None


def test_pi_name_matches_only_unique_experts_at_california_organisations() -> None:
    grants = [
        _grant("g1", "Ana Maria Barral"),
        _grant("g2", "Chelsea Rochman", state="WA"),  # outside California: no name match
        _grant("g3", "Ting Xu"),  # two experts share the key: skipped
        _grant("g4", "Ana Maria Barral", plastic=False),  # not plastic-related
    ]
    badges = build_badges(AUTHORS, grants)
    assert [g["grant_key"] for g in badges["A1"]["grants"]] == ["g1"]
    assert badges["A1"]["grants"][0]["match"] == "pi_name"
    assert "A2" not in badges and "A3" not in badges and "A4" not in badges


def test_linked_work_grants_count_for_every_author_of_the_work() -> None:
    grants = [_grant("g2", "Someone Else", state="WA")]
    links = [{"work_id": "W2", "grant_key": "g2"}]
    badges = build_badges(AUTHORS, grants, links)
    assert badges["A2"]["grants"][0]["match"] == "linked_work"


def test_datasets_are_plastic_related_and_collapse_versions() -> None:
    outputs = [
        {"author_id": "A2", "doi": "10.1/a.v1", "family_doi": "10.1/a", "title": "A",
         "year": 2020, "resource_type_general": "Dataset", "plastic_related": True},
        {"author_id": "A2", "doi": "10.1/a.v2", "family_doi": "10.1/a", "title": "A",
         "year": 2022, "resource_type_general": "Dataset", "plastic_related": True},
        {"author_id": "A2", "doi": "10.1/b", "family_doi": None, "title": "B",
         "year": 2019, "resource_type_general": "Software", "plastic_related": True},
        {"author_id": "A2", "doi": "10.1/c", "family_doi": None, "title": "C",
         "year": 2021, "resource_type_general": "Dataset", "plastic_related": False},
        {"author_id": "A9", "doi": "10.1/d", "family_doi": None, "title": "D",
         "year": 2021, "resource_type_general": "Dataset", "plastic_related": True},
    ]  # fmt: skip
    badges = build_badges(AUTHORS, [], [], outputs)
    assert badges["A2"]["datasets"] == {
        "count": 1,
        "items": [{"doi": "10.1/a.v2", "title": "A", "publisher": None, "year": 2022}],
    }
    assert "A9" not in badges
