"""Tests for the BQ-3.3 degree-preserving null model and profile sensitivity (tiny graphs)."""

from __future__ import annotations

import json
import random
from typing import Any

import networkx as nx

from atlas.analytics.network_null import (
    DEFAULT_REPLICATES,
    build_null_block,
    double_edge_swap,
    null_model,
    profile_sensitivity,
)

PERSON_KEYS = {"author_id", "author_ids", "name", "institution_ids", "inst_id", "id"}


def _weighted(graph: nx.Graph, seed: int) -> nx.Graph:
    rng = random.Random(seed)
    for u, v in graph.edges():
        graph[u][v]["weight"] = rng.randint(1, 4)
    return graph


def _planted() -> nx.Graph:
    return _weighted(nx.planted_partition_graph(2, 30, 0.3, 0.02, seed=7), seed=7)


def _erdos_renyi() -> nx.Graph:
    return _weighted(nx.gnp_random_graph(80, 0.1, seed=3), seed=3)


def _walk_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        out = set(value)
        for item in value.values():
            out |= _walk_keys(item)
        return out
    if isinstance(value, list):
        out: set[str] = set()
        for item in value:
            out |= _walk_keys(item)
        return out
    return set()


# --- swap mechanics ----------------------------------------------------------------------------


def test_degree_sequence_and_weight_multiset_preserved_in_every_replicate() -> None:
    graph = _weighted(nx.gnm_random_graph(30, 80, seed=1), seed=1)
    degrees = dict(graph.degree())
    weights = sorted(d["weight"] for _, _, d in graph.edges(data=True))
    for replicate_seed in range(10):
        swapped, done, tries = double_edge_swap(
            graph, nswap=400, max_tries=8000, rng=random.Random(replicate_seed)
        )
        assert dict(swapped.degree()) == degrees
        assert sorted(d["weight"] for _, _, d in swapped.edges(data=True)) == weights
        assert swapped.number_of_nodes() == graph.number_of_nodes()
        assert 0 < done <= tries <= 8000
        assert not any(u == v for u, v in swapped.edges())


def test_swaps_never_create_parallel_links_and_actually_rewire() -> None:
    graph = _weighted(nx.gnm_random_graph(30, 80, seed=2), seed=2)
    swapped, done, _ = double_edge_swap(graph, nswap=400, max_tries=8000, rng=random.Random(5))
    assert done > 0
    assert set(map(frozenset, swapped.edges())) != set(map(frozenset, graph.edges()))
    assert swapped.number_of_edges() == graph.number_of_edges()


def test_complete_graph_has_no_valid_swap() -> None:
    graph = _weighted(nx.complete_graph(5), seed=0)
    _, done, _ = double_edge_swap(graph, nswap=50, max_tries=500, rng=random.Random(0))
    assert done == 0


# --- null model --------------------------------------------------------------------------------


def test_null_is_deterministic_given_the_seed() -> None:
    graph = _planted()
    first = null_model(graph, replicates=12, seed=9)
    assert null_model(graph, replicates=12, seed=9) == first
    assert first["seed"] == 9 and first["replicates"] == 12
    assert first["nswap"] == 10 * graph.number_of_edges()
    other = null_model(graph, replicates=12, seed=10)
    assert (
        other["statistics"]["modularity"]["null_mean"]
        != first["statistics"]["modularity"]["null_mean"]
    )


def test_null_does_not_depend_on_insertion_order() -> None:
    # Graphs built from sets follow hash order, which changes with PYTHONHASHSEED.
    forward = _planted()
    backward = nx.Graph()
    backward.add_nodes_from(reversed(list(forward.nodes())))
    backward.add_weighted_edges_from(
        (v, u, d["weight"]) for u, v, d in reversed(list(forward.edges(data=True)))
    )
    assert null_model(backward, replicates=6, seed=3) == null_model(forward, replicates=6, seed=3)


def test_observed_statistics_do_not_depend_on_edge_orientation() -> None:
    # The same links, written as (b, a) instead of (a, b), must give the same modularity.
    forward = _erdos_renyi()
    flipped = nx.Graph()
    flipped.add_nodes_from(forward.nodes())
    flipped.add_weighted_edges_from((v, u, d["weight"]) for u, v, d in forward.edges(data=True))
    a = null_model(forward, replicates=2, seed=5)["statistics"]
    b = null_model(flipped, replicates=2, seed=5)["statistics"]
    assert a == b


def test_z_is_null_when_null_sd_is_zero() -> None:
    result = null_model(nx.complete_graph(5), replicates=5)
    summary = result["statistics"]["average_clustering"]
    assert summary["null_sd"] == 0
    assert summary["z"] is None
    assert summary["observed"] == 1.0
    assert result["swaps_succeeded"] == {"min": 0, "mean": 0.0, "max": 0}


def test_planted_partition_modularity_is_far_above_chance() -> None:
    summary = null_model(_planted(), replicates=50)["statistics"]["modularity"]
    assert summary["z"] is not None and summary["z"] > 3
    assert summary["p_two_sided"] < 0.05


def test_erdos_renyi_modularity_is_close_to_chance() -> None:
    summary = null_model(_erdos_renyi(), replicates=50)["statistics"]["modularity"]
    assert summary["z"] is not None and abs(summary["z"]) < 2.5
    assert summary["p_two_sided"] > 0.05


def test_p_value_uses_plus_one_correction() -> None:
    summary = null_model(_erdos_renyi(), replicates=20)["statistics"]["giant_component_share"]
    assert summary["p_two_sided"] >= 1 / 21 - 1e-9


# --- sensitivity -------------------------------------------------------------------------------


def _works() -> list[list[str]]:
    # Component one: A and A2 share a name and sit together. Component two: E and F2 share a name
    # but are in different components, so they must not merge.
    return [
        ["A", "B"],
        ["A2", "C"],
        ["B", "C", "D"],
        ["C", "D"],
        ["E", "X"],
        ["F2", "Y"],
        ["Y", "W"],
    ]


def test_merge_joins_same_name_only_within_a_component() -> None:
    names = {"A": "Jo Smith", "A2": "jo  smith.", "E": "Ana Lee", "F2": "Ana Lee"}
    result = profile_sensitivity(_works(), names, split_share=0.0)
    merged = result["merge_same_name_within_component"]
    assert merged["merged_away"] == 1
    assert merged["nodes"] == result["observed"]["nodes"] - 1
    assert result["observed"]["nodes"] == 10
    assert set(merged["delta"]) == {"average_clustering", "modularity", "giant_component_share"}


def test_merge_without_names_changes_nothing() -> None:
    result = profile_sensitivity(_works(), {}, split_share=0.0)
    assert result["merge_same_name_within_component"]["merged_away"] == 0
    assert result["merge_same_name_within_component"]["delta"] == {
        "average_clustering": 0.0,
        "modularity": 0.0,
        "giant_component_share": 0.0,
    }


def test_split_takes_seeded_share_of_authors_with_two_or_more_links() -> None:
    works = [[f"p{i}", f"p{(i + 1) % 40}", f"p{(i + 7) % 40}"] for i in range(40)]
    first = profile_sensitivity(works, {}, seed=4, split_share=0.05)
    again = profile_sensitivity(works, {}, seed=4, split_share=0.05)
    assert first == again
    split = first["split_authors"]
    assert split["authors_split"] == 2  # 5% of 40 authors, all with degree >= 2
    assert split["split_share"] == 0.05
    assert split["nodes"] >= first["observed"]["nodes"]


def test_split_with_no_candidates_leaves_observed_values() -> None:
    result = profile_sensitivity([["A"], ["B"]], {}, split_share=0.05)
    assert result["split_authors"]["authors_split"] == 0
    assert result["split_authors"]["nodes"] == result["observed"]["nodes"]
    assert all(v == 0.0 for v in result["split_authors"]["delta"].values() if v is not None)


# --- aggregates only ---------------------------------------------------------------------------


def test_null_block_has_no_per_node_keys_or_identifiers() -> None:
    index = {
        "authors": [
            {"author_id": "A-901", "name": "Test Person One", "institution_ids": ["I-1"]},
            {"author_id": "A-902", "name": "Test Person Two", "institution_ids": ["I-1"]},
            {"author_id": "A-903", "name": "Test Person Three", "institution_ids": []},
        ],
        "works": [
            {
                "work_id": "W-1",
                "plastic_related": True,
                "year": 2020,
                "author_ids": ["A-901", "A-902", "A-903"],
                "institution_ids": ["I-1", "I-2"],
            },
            {
                "work_id": "W-2",
                "plastic_related": True,
                "year": 2021,
                "author_ids": ["A-901", "A-902"],
                "institution_ids": ["I-2"],
            },
        ],
    }
    block = build_null_block(index, replicates=4)
    assert not _walk_keys(block) & PERSON_KEYS
    text = json.dumps(block)
    for identifier in ("A-901", "A-902", "A-903", "Test Person", "W-1", "I-1"):
        assert identifier not in text
    assert block["replicates"] == 4
    assert [w["window"] for w in block["graphs"]["authors"]["windows"]] == [
        "all",
        "2011-2015",
        "2016-2020",
        "2021-2025",
        "2026",
    ]
    assert DEFAULT_REPLICATES == 100
