"""S9.4 expert collaboration network: node selection, edge weights, seeded stability."""

from __future__ import annotations

import pytest

from atlas.build.network import build_network, edge_years, select_nodes

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
