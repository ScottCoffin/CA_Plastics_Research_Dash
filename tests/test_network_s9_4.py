"""S9.4 expert collaboration network: node selection, edge weights, seeded stability."""

from __future__ import annotations

import pytest

from atlas.build.network import (
    SCHEMA_VERSION,
    _normalise,
    build_network,
    community_labels,
    edge_years,
    select_nodes,
)

pytest.importorskip("networkx")

AUTHORS = [
    {"author_id": "A1", "name": "One", "ca_plastic_works_count": 5, "plastic_citations": 10},
    {"author_id": "A2", "name": "Two", "ca_plastic_works_count": 3, "plastic_citations": 50},
    {"author_id": "A3", "name": "Three", "ca_plastic_works_count": 3, "plastic_citations": 5},
    {"author_id": "A4", "name": "Solo", "ca_plastic_works_count": 9, "plastic_citations": 99},
    {"author_id": "A5", "name": "Five", "ca_plastic_works_count": 1, "plastic_citations": 1},
]
WORKS = [
    {"work_id": "W1", "plastic_related": True, "year": 2020, "author_ids": ["A1", "A2"]},
    {"work_id": "W2", "plastic_related": True, "year": 2021, "author_ids": ["A1", "A2", "A3"]},
    {"work_id": "W3", "plastic_related": False, "year": 2021, "author_ids": ["A1", "A5"]},
    {"work_id": "W4", "plastic_related": True, "year": 2022, "author_ids": ["A4"]},
    {"work_id": "W5", "plastic_related": True, "year": 2022, "author_ids": ["A3", "A5"]},
]
INDEX = {"authors": AUTHORS, "works": WORKS, "generated_at": "fixture"}


def test_select_nodes_skips_isolated_and_non_plastic_and_ranks() -> None:
    assert select_nodes(AUTHORS, WORKS) == ["A1", "A2", "A3", "A5"]
    assert select_nodes(AUTHORS, WORKS, cap=2) == ["A1", "A2"]


def test_select_nodes_needs_another_atlas_expert_on_a_plastic_work() -> None:
    authors = [
        {"author_id": "E1", "name": "Lone", "ca_plastic_works_count": 4, "plastic_citations": 9},
        {"author_id": "E2", "name": "Paired", "ca_plastic_works_count": 2, "plastic_citations": 1},
        {"author_id": "E3", "name": "Partner", "ca_plastic_works_count": 1, "plastic_citations": 0},
    ]
    works = [
        # E1's only plastic work is co-authored with X9, who is not in authors: not eligible.
        {"work_id": "W1", "plastic_related": True, "year": 2020, "author_ids": ["E1", "X9"]},
        # E2 and E3 are both Atlas experts on this plastic work: both eligible.
        {"work_id": "W2", "plastic_related": True, "year": 2021, "author_ids": ["E2", "E3", "X9"]},
    ]
    assert select_nodes(authors, works) == ["E2", "E3"]


def test_edge_weights_count_plastic_works_by_year() -> None:
    edges = edge_years(WORKS, ["A1", "A2", "A3", "A5"])
    assert edges[("A1", "A2")] == {2020: 1.0, 2021: 1.0}
    assert edges[("A2", "A3")] == {2021: 1.0}
    assert ("A1", "A5") not in edges  # W3 is not plastic-related


def test_fractional_weights() -> None:
    edges = edge_years(WORKS, ["A1", "A2", "A3"], fractional=True)
    assert edges[("A1", "A2")] == {2020: 1.0, 2021: 0.5}


def test_build_is_seeded_and_complete() -> None:
    first = build_network(INDEX)
    second = build_network(INDEX)
    assert first == second
    ids = {n["id"] for n in first["nodes"]}
    assert ids == {"A1", "A2", "A3", "A5"}
    assert all(e["source"] in ids and e["target"] in ids for e in first["edges"])
    assert first["communities"] == len({n["community"] for n in first["nodes"]})
    assert not any("email" in key for n in first["nodes"] for key in n)


# ---- VD-20: ForceAtlas2 layout and algorithmic community labels -------------------------------


def _row(community: int, primary=(), institutions=(), topics=()) -> dict:
    return {
        "community": community,
        "primary_affiliations": list(primary),
        "institutions": list(institutions),
        "topics": list(topics),
    }


def _label_for(labels: list[dict], community: int) -> dict:
    (found,) = [entry for entry in labels if entry["community"] == community]
    return found


def test_normalise_centres_and_scales_to_unit_square() -> None:
    out = _normalise({"a": (0.0, 0.0), "b": (4.0, 2.0)})
    assert out == {"a": (-1.0, -0.5), "b": (1.0, 0.5)}
    assert _normalise({"a": (3.0, 3.0)}) == {"a": (0.0, 0.0)}
    assert _normalise({}) == {}


def _members(community: int, primaries: list[str]) -> list[dict]:
    """One row per expert, each with the given first primary affiliation."""
    return [_row(community, primary=[name]) for name in primaries]


def test_institution_threshold_needs_share_and_count() -> None:
    rows = (
        _members(0, ["Uni A", "Uni A", "Uni A", "Uni B"])  # 3 of 4: share 0.75, kept
        + _members(1, ["Uni A", "Uni A", "Uni B", "Uni C"])  # 2 of 4: share 0.5, kept
        + _members(2, ["Uni A", "Uni B", "Uni C", "Uni D"])  # 1 of 4: count below 2
        + _members(3, ["Uni A", "Uni A", "Uni B", "Uni B", "Uni C", "Uni C"])  # 2 of 6: below 0.35
        + _members(4, ["Uni A", "Uni A", "Uni B", "Uni C", "Uni D"])  # 2 of 5: share 0.4, kept
    )
    labels = community_labels(rows)
    assert [entry["community"] for entry in labels] == [0, 1, 2, 3, 4]
    assert _label_for(labels, 0)["institution"] == {"name": "Uni A", "share": 0.75}
    assert _label_for(labels, 1)["institution"] == {"name": "Uni A", "share": 0.5}
    assert _label_for(labels, 2)["institution"] is None
    assert _label_for(labels, 3)["institution"] is None
    assert _label_for(labels, 4)["institution"] == {"name": "Uni A", "share": 0.4}


def test_institution_fallback_skips_system_and_ties_are_by_name() -> None:
    rows = [_row(0, institutions=["System", "Uni Z"]) for _ in range(4)]
    rows += [_row(1, institutions=["System"]) for _ in range(4)]
    labels = community_labels(rows)
    assert _label_for(labels, 0)["institution"] == {"name": "Uni Z", "share": 1.0}
    assert _label_for(labels, 1)["institution"] is None


def test_topic_picks_highest_lift_not_highest_share() -> None:
    # Community 0 (4 experts): "tag_a" on all four, "tag_c" on two. Across all 10 experts
    # tag_a sits on 8 (lift 1.25) and tag_c on 2 (lift 2.5), so tag_c wins despite lower share.
    rows = [
        _row(0, topics=["tag_a", "tag_c"]),
        _row(0, topics=["tag_a", "tag_c"]),
        _row(0, topics=["tag_a"]),
        _row(0, topics=["tag_a"]),
        _row(1, topics=["tag_a"]),
        _row(1, topics=["tag_a"]),
        _row(1, topics=["tag_a"]),
        _row(1, topics=["tag_a"]),
        _row(2),
        _row(2),
    ]
    labels = community_labels(rows)
    assert _label_for(labels, 0)["topic"] == {"tag": "tag_c", "share": 0.5, "lift": 2.5}
    assert _label_for(labels, 1)["topic"] == {"tag": "tag_a", "share": 1.0, "lift": 1.25}
    assert [entry["community"] for entry in labels] == [0, 1]  # community 2 has 2 experts


def test_topic_ties_break_by_share_then_tag() -> None:
    # Both tags have lift 2.0 (4 of 4 vs 4 of 8 overall); "tag_a" has the higher share (1.0 vs 0.5).
    rows = [_row(0, topics=["tag_a", "tag_b"]), _row(0, topics=["tag_a", "tag_b"])]
    rows += [_row(0, topics=["tag_a"]), _row(0, topics=["tag_a"])]
    rows += [
        _row(1, topics=["tag_b"]),
        _row(1, topics=["tag_b"]),
        _row(1, topics=["tag_b"]),
        _row(1),
    ]
    labels = community_labels(rows)
    assert _label_for(labels, 0)["topic"]["tag"] == "tag_a"
    # Equal share and lift: the alphabetically first tag wins.
    tie = [_row(0, topics=["m_tag", "a_tag"]), _row(0, topics=["m_tag", "a_tag"])]
    tie += [_row(0), _row(0), _row(1), _row(1), _row(1), _row(1)]
    tie_labels = community_labels(tie)
    assert _label_for(tie_labels, 0)["topic"]["tag"] == "a_tag"


def test_topic_null_when_lift_or_share_is_low() -> None:
    flat = [_row(0, topics=["t_flat"]) for _ in range(4)] + [
        _row(1, topics=["t_flat"]) for _ in range(4)
    ]
    assert _label_for(community_labels(flat), 0)["topic"] is None  # lift exactly 1.0
    thin = [_row(0, topics=["t_x"])] + [_row(0) for _ in range(3)] + [_row(1) for _ in range(4)]
    assert _label_for(community_labels(thin), 0)["topic"] is None  # share 0.25 < 0.4


def test_small_communities_are_not_listed_and_empty_input_is_empty() -> None:
    assert community_labels([]) == []
    assert community_labels(_members(0, ["Uni A"] * 3)) == []
    rows = _members(0, ["Uni A"] * 4) + _members(1, ["Uni B"] * 3)
    assert [entry["community"] for entry in community_labels(rows)] == [0]


def _two_group_index() -> dict:
    """Two disconnected groups of five experts plus a pair (too small to label)."""
    authors, works = [], []
    spec = {
        "P": ("Uni North", ["t_north", "t_shared"]),
        "Q": ("Uni South", ["t_south", "t_shared"]),
    }
    for prefix, (affiliation, tags) in spec.items():
        ids = [f"{prefix}{i}" for i in range(5)]
        for author_id in ids:
            authors.append(
                {
                    "author_id": author_id,
                    "name": author_id,
                    "ca_plastic_works_count": 3,
                    "plastic_citations": 1,
                    "primary_affiliations": [affiliation],
                }
            )
        works.append(
            {
                "work_id": f"W{prefix}",
                "plastic_related": True,
                "year": 2020,
                "author_ids": ids,
                "domain_tags": tags,
            }
        )
    for author_id in ("R0", "R1"):
        authors.append(
            {
                "author_id": author_id,
                "name": author_id,
                "ca_plastic_works_count": 1,
                "plastic_citations": 0,
            }
        )
    works.append(
        {"work_id": "WR", "plastic_related": True, "year": 2021, "author_ids": ["R0", "R1"]}
    )
    return {"authors": authors, "works": works, "generated_at": "two-group"}


def test_two_group_fixture_gets_labels_layout_and_is_deterministic() -> None:
    index = _two_group_index()
    first = build_network(index)
    assert first == build_network(index)
    by_id = {node["id"]: node for node in first["nodes"]}
    labels = first["community_labels"]
    assert [entry["size"] for entry in labels] == [5, 5]  # the pair R0-R1 is not labelled
    north = _label_for(labels, by_id["P0"]["community"])
    south = _label_for(labels, by_id["Q0"]["community"])
    assert north["institution"] == {"name": "Uni North", "share": 1.0}
    # 12 experts in all (the pair counts): lift = (5 / 5) / (5 / 12) = 2.4.
    assert north["topic"] == {"tag": "t_north", "share": 1.0, "lift": 2.4}
    assert south["institution"] == {"name": "Uni South", "share": 1.0}
    assert south["topic"] == {"tag": "t_south", "share": 1.0, "lift": 2.4}
    assert (
        "35%" in first["method"]["community_labels"]
        and "1.15" in first["method"]["community_labels"]
    )
    assert "ForceAtlas2" in first["method"]["layout"]
    assert first["communities"] == len({node["community"] for node in first["nodes"]})


def test_layout_is_normalised_and_separates_groups() -> None:
    payload = build_network(_two_group_index())
    xs = [node["x"] for node in payload["nodes"]]
    ys = [node["y"] for node in payload["nodes"]]
    assert all(-1.0001 <= value <= 1.0001 for value in (*xs, *ys))
    assert max(max(map(abs, xs)), max(map(abs, ys))) == pytest.approx(1.0, abs=1e-3)
    centroids, radii = {}, {}
    for community in {node["community"] for node in payload["nodes"] if node["id"] in {"P0", "Q0"}}:
        pts = [
            (n["x"], n["y"])
            for n in payload["nodes"]
            if n["community"] == community and n["id"][0] in "PQ"
        ]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        centroids[community] = (cx, cy)
        radii[community] = max(((p[0] - cx) ** 2 + (p[1] - cy) ** 2) ** 0.5 for p in pts)
    (a, b) = sorted(centroids)
    gap = (
        (centroids[a][0] - centroids[b][0]) ** 2 + (centroids[a][1] - centroids[b][1]) ** 2
    ) ** 0.5
    assert gap > 2 * max(radii.values())  # clusters are visibly apart on first load


def test_no_labels_when_no_community_reaches_four() -> None:
    payload = build_network(INDEX)
    assert payload["community_labels"] == []
    assert SCHEMA_VERSION == payload["schema_version"] == "s9.4-v1.1"
