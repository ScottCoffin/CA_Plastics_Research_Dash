from atlas.groups.scope import scoped_records


def test_explicit_subnational_scope_uses_enriched_places() -> None:
    groups = [
        {"group_id": "ca", "country": "US", "places": ["US-CA"]},
        {"group_id": "us", "country": "US", "places": ["US-NY"]},
        {"group_id": "no", "country": "NO", "places": []},
    ]
    assert [
        g["group_id"] for g in scoped_records(groups, countries={"US"}, explicit_place="US-CA")
    ] == ["ca"]


def test_country_scope_does_not_claim_subnational_membership() -> None:
    groups = [
        {"group_id": "ca", "country": "US", "places": ["US-CA"]},
        {"group_id": "no", "country": "NO", "places": []},
    ]
    assert [g["group_id"] for g in scoped_records(groups, countries={"NO"})] == ["no"]
