"""Global institutions graph (BQ-V.1 slice 1) on synthetic raw pages."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from atlas.build.global_graphs import (
    FILE_NAMES,
    MAX_INSTITUTIONS_PER_WORK,
    NODE_FIELDS,
    SCHEMA_VERSION,
    build_graphs,
    check_outputs,
    co_occurrence,
    read_raw_works,
    thin_edges,
)
from atlas.ingest.global_partition import NoRawStoreError

PERSON_NAME = "Dr Person Example"
PERSON_ID = "A987654321"


def _inst(inst_id: str) -> dict[str, Any]:
    return {
        "id": f"https://openalex.org/{inst_id}",
        "display_name": f"Institution {inst_id}",
        "ror": f"https://ror.org/{inst_id.lower()}",
        "country_code": "NL",
        "type": "education",
    }


def _work(work_id: str, inst_groups: list[list[str]]) -> dict[str, Any]:
    """One authorship per group; each group lists the institution ids of that author."""
    authorships = [
        {
            "author": {"id": f"https://openalex.org/{PERSON_ID}", "display_name": PERSON_NAME},
            "institutions": [_inst(i) for i in group],
        }
        for group in inst_groups
    ]
    return {"id": f"https://openalex.org/{work_id}", "authorships": authorships}


def _write_page(raw: Path, name: str, fetched: str, works: list[dict[str, Any]]) -> None:
    pages = raw / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    header = {
        "record_type": "page_header",
        "fetched_utc": fetched,
        "query_version": "plastic-v3.1",
        "query_hash": "testhash",
    }
    with gzip.open(pages / name, "wt", encoding="utf-8") as handle:
        handle.write(json.dumps(header) + "\n")
        for work in works:
            handle.write(json.dumps(work) + "\n")


def _dataset(tmp_path: Path) -> Path:
    """Giant component I1-I5 (more works on I1/I2), a small pair I8-I9, one wide work."""
    raw = tmp_path / "raw"
    works = [
        _work("W1", [["I1"], ["I2"]]),
        _work("W2", [["I1"], ["I2"], ["I3"]]),
        _work("W3", [["I2"], ["I3"]]),
        _work("W4", [["I1"], ["I4"]]),
        _work("W5", [["I4"], ["I5"]]),
        _work("W6", [["I1"], ["I2"], ["I5"]]),
        _work("W7", [["I8"], ["I9"]]),
    ]
    _write_page(raw, "2022_00001.jsonl.gz", "2026-11-25T10:00:00+00:00", works)
    return raw


def test_edge_weights_count_shared_works(tmp_path: Path) -> None:
    raw = _dataset(tmp_path)
    works_insts, _, summary = read_raw_works(raw)
    works, edges = co_occurrence(works_insts)
    assert summary.works == 7
    assert summary.query_version == "plastic-v3.1"
    assert edges[("I1", "I2")] == 3  # W1, W2, W6
    assert edges[("I2", "I3")] == 2  # W2, W3
    assert edges[("I4", "I5")] == 1  # W5
    assert works["I2"] == 4  # W1, W2, W3, W6


def test_works_above_cap_count_for_nodes_but_add_no_edges(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    wide = [f"X{i:02d}" for i in range(MAX_INSTITUTIONS_PER_WORK + 1)]
    edge_case = [f"Y{i:02d}" for i in range(MAX_INSTITUTIONS_PER_WORK)]
    _write_page(
        raw,
        "2022_00001.jsonl.gz",
        "2026-11-25T10:00:00+00:00",
        [
            _work("W1", [[i] for i in wide]),
            _work("W2", [[i] for i in edge_case]),
        ],
    )
    works_insts, _, _ = read_raw_works(raw)
    works, edges = co_occurrence(works_insts)
    assert works["X00"] == 1
    assert not any(a.startswith("X") for a, _ in edges)
    assert len(edges) == MAX_INSTITUTIONS_PER_WORK * (MAX_INSTITUTIONS_PER_WORK - 1) // 2


def test_graph_keeps_only_largest_component(tmp_path: Path) -> None:
    raw = _dataset(tmp_path)
    build = build_graphs(raw, layout_iterations=5)
    graph = json.loads(build.files["institutions"])
    nodes = {row[0] for row in graph["nodes"]["rows"]}
    assert nodes == {"I1", "I2", "I3", "I4", "I5"}
    assert "I8" not in nodes and "I9" not in nodes


def test_node_cap_and_phone_subset_take_top_works(tmp_path: Path) -> None:
    raw = _dataset(tmp_path)
    build = build_graphs(raw, node_cap=3, phone_cap=2, layout_iterations=5)
    full = json.loads(build.files["institutions"])
    phone = json.loads(build.files["institutions_phone"])
    full_ids = [row[0] for row in full["nodes"]["rows"]]
    # Works per node: I2 4, I1 4 (ties by id: I1 first), I3 2, I5 2, I4 2.
    assert full_ids == ["I1", "I2", "I3"]
    assert [row[0] for row in phone["nodes"]["rows"]] == ["I1", "I2"]
    for a, b, _ in phone["edges"]["rows"]:
        assert a < 2 and b < 2
    assert len(build.files["layout"]) == 8 * len(full_ids)
    assert build.manifest["caps"]["node_cap"] == 3
    assert build.manifest["caps"]["phone_node_cap"] == 2


def test_build_is_deterministic(tmp_path: Path) -> None:
    raw = _dataset(tmp_path)
    first = build_graphs(raw, layout_iterations=20)
    second = build_graphs(raw, layout_iterations=20)
    assert first.files == second.files


def test_output_has_no_person_level_data(tmp_path: Path) -> None:
    build = build_graphs(_dataset(tmp_path), layout_iterations=5)
    for key, blob in build.files.items():
        if key == "layout":
            continue
        text = blob.decode("utf-8")
        assert PERSON_NAME not in text
        assert PERSON_ID not in text
        assert "openalex.org/A" not in text
    graph = json.loads(build.files["institutions"])
    assert graph["nodes"]["fields"] == list(NODE_FIELDS)
    assert set(graph) == {"communities", "edges", "graph", "nodes", "schema_version"}


def test_manifest_schema_and_check_outputs(tmp_path: Path) -> None:
    build = build_graphs(_dataset(tmp_path), layout_iterations=5)
    manifest = build.manifest
    assert manifest["schema_version"] == SCHEMA_VERSION == "bqv-v1"
    assert manifest["screening_status"] == "unscreened_query_hit"
    assert manifest["what_this_is_and_is_not"]
    assert manifest["query_hash"] == "testhash"
    assert manifest["seed"] == 42
    full = manifest["graphs"]["institutions"]
    assert full["bytes"] == len(build.files["institutions"])
    assert full["layout_bytes"] == len(build.files["layout"])
    assert full["nodes"] == 5 and full["communities"] >= 1
    assert manifest["graphs"]["institutions_phone"]["nodes"] == 5

    out = tmp_path / "out"
    out.mkdir()
    for key, name in FILE_NAMES.items():
        (out / name).write_bytes(build.files[key])
    assert check_outputs(out) == []
    (out / FILE_NAMES["layout"]).write_bytes(b"\x00" * 4)
    assert check_outputs(out)


def _ring_with_chords() -> list[tuple[int, int, int]]:
    """Ten nodes: a ring of weight 1, plus heavy chords from node 0 (weight 9 to 5 and 7)."""
    edges = {(i, i + 1): 1 for i in range(9)}
    edges[(0, 9)] = 1
    edges[(0, 5)] = 9
    edges[(0, 7)] = 8
    edges[(2, 6)] = 4
    return sorted((a, b, w) for (a, b), w in edges.items())


def _nodes_with_edges(edges: list[tuple[int, int, int]]) -> set[int]:
    return {n for a, b, _ in edges for n in (a, b)}


def test_thinning_respects_budget_and_keeps_each_node_connected() -> None:
    edges = _ring_with_chords()
    kept, info = thin_edges(edges, 10, budget=10, start_k=2)
    assert len(kept) <= 10
    assert info["edges_after"] == len(kept)
    assert _nodes_with_edges(kept) == set(range(10))
    # Node 0's two heaviest edges survive the top-k step.
    assert (0, 5, 9) in kept and (0, 7, 8) in kept


def test_thinning_is_deterministic() -> None:
    edges = _ring_with_chords()
    assert thin_edges(edges, 10, budget=10, start_k=2) == thin_edges(
        edges, 10, budget=10, start_k=2
    )


def test_thinning_reports_share_and_k() -> None:
    edges = _ring_with_chords()
    kept, info = thin_edges(edges, 10, budget=100, start_k=1)
    assert set(kept) <= set(edges)
    assert info["k_used"] == 1
    assert 0 < info["weight_retained_share"] < 1
    assert info["edges_before"] == len(edges)


def test_thinning_rejects_non_positive_k() -> None:
    with pytest.raises(ValueError):
        thin_edges(_ring_with_chords(), 10, budget=6, start_k=0)


def test_built_graphs_obey_budgets_and_manifest_records_them(tmp_path: Path) -> None:
    build = build_graphs(
        _dataset(tmp_path),
        layout_iterations=5,
        edge_budget=6,
        start_k=2,
        phone_edge_budget=5,
        phone_start_k=1,
    )
    full = json.loads(build.files["institutions"])
    phone = json.loads(build.files["institutions_phone"])
    assert len(full["edges"]["rows"]) <= 6
    assert len(phone["edges"]["rows"]) <= 5
    touched = {n for a, b, _ in full["edges"]["rows"] for n in (a, b)}
    assert touched == set(range(len(full["nodes"]["rows"])))
    graphs = build.manifest["graphs"]
    assert graphs["institutions"]["thinning"]["budget"] == 6
    assert graphs["institutions_phone"]["thinning"]["budget"] == 5
    assert build.manifest["caps"]["thinning_rule"]
    assert 0 < graphs["institutions"]["thinning"]["weight_retained_share"] <= 1


def test_missing_raw_store_raises(tmp_path: Path) -> None:
    with pytest.raises(NoRawStoreError):
        build_graphs(tmp_path / "absent", layout_iterations=5)
