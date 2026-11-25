"""Global institutions (BQ-V.1 slice 1) and authors (slice 2) graphs on synthetic raw pages."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from atlas.analytics.denominators import load_pollution_core
from atlas.build.global_graphs import (
    AUTHOR_GRAPH_NAME,
    AUTHOR_NODE_FIELDS,
    AUTHOR_PHONE_GRAPH_NAME,
    FILE_NAMES,
    FORBIDDEN_KEYS,
    GRAPH_NAME,
    MAX_AUTHORS_PER_WORK,
    MAX_INSTITUTIONS_PER_WORK,
    NODE_FIELDS,
    PHONE_GRAPH_NAME,
    SCHEMA_VERSION,
    author_tables,
    build_author_graph,
    build_graphs,
    check_outputs,
    co_occurrence,
    read_backbone,
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


def test_institution_output_has_no_person_level_data(tmp_path: Path) -> None:
    build = build_graphs(_dataset(tmp_path), layout_iterations=5)
    for key in (GRAPH_NAME, PHONE_GRAPH_NAME, "manifest"):
        text = build.files[key].decode("utf-8")
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


def _author_entry(author_id: str, name: str, insts: list[tuple[str, str]]) -> dict[str, Any]:
    """One authorship. It carries an ORCID, an email and a raw affiliation: none may be output."""
    return {
        "author": {
            "id": f"https://openalex.org/{author_id}",
            "display_name": name,
            "orcid": "https://orcid.org/0000-0001-2345-6789",
        },
        "institutions": [
            {
                "id": f"https://openalex.org/{inst}",
                "display_name": f"Institution {inst}",
                "ror": f"https://ror.org/{inst.lower()}",
                "country_code": country,
                "type": "education",
            }
            for inst, country in insts
        ],
        "raw_affiliation_strings": [
            f"Dept of Things, Institution {insts[0][0]}, {author_id.lower()}@example.org"
        ],
    }


def _author_work(
    work_id: str,
    title: str,
    abstract: dict[str, list[int]] | None,
    authorships: list[dict[str, Any]],
) -> dict[str, Any]:
    work: dict[str, Any] = {
        "id": f"https://openalex.org/{work_id}",
        "title": title,
        "authorships": authorships,
    }
    if abstract is not None:
        work["abstract_inverted_index"] = abstract
    return work


def _author_dataset(tmp_path: Path, *, with_titles: bool = True) -> Path:
    """Backbone works W1 (title), W2 (abstract only), W3 (title), W5 (26 authors, title).

    W4 is off the backbone. With ``with_titles=False`` no work matches, so the author graph is
    empty while the institution inputs stay identical.
    """
    raw = tmp_path / "raw"
    if with_titles:
        titles = (
            "Microplastic in river sediment",
            "Field survey",
            "Plastic debris on beaches",
            "Soil carbon dynamics",
            "Nanoplastic exposure",
        )
    else:
        titles = ("Untitled",) * 5
    abstract = {"marine": [0], "debris": [1]} if with_titles else None
    hyper = [_author_entry(f"A{10 + i}", f"Hyper Author {i}", [("I9", "US")]) for i in range(26)]
    works = [
        _author_work(
            "W1",
            titles[0],
            None,
            [
                _author_entry("A1", "Ann Example", [("I1", "NL")]),
                _author_entry("A2", "Bo Example", [("I2", "NL")]),
            ],
        ),
        _author_work(
            "W2",
            titles[1],
            abstract,
            [
                _author_entry("A2", "Bo Example", [("I2", "US")]),
                _author_entry("A3", "Cy Example", [("I3", "US")]),
            ],
        ),
        _author_work(
            "W3",
            titles[2],
            None,
            [
                _author_entry("A1", "Ann Example", [("I1", "NL")]),
                _author_entry("A2", "Bo Example", [("I2", "US")]),
                _author_entry("A3", "Cy Example", [("I3", "DE")]),
            ],
        ),
        _author_work(
            "W4",
            titles[3],
            None,
            [
                _author_entry("A4", "Di Example", [("I4", "NL")]),
                _author_entry("A5", "Ed Example", [("I4", "NL")]),
            ],
        ),
        _author_work("W5", titles[4], None, hyper),
    ]
    _write_page(raw, "2022_00001.jsonl.gz", "2026-11-25T10:00:00+00:00", works)
    return raw


def _core_terms() -> list[str]:
    return list(load_pollution_core()["core_terms"])


def test_backbone_matches_title_or_abstract_only(tmp_path: Path) -> None:
    backbone = read_backbone(_author_dataset(tmp_path), _core_terms())
    assert backbone.seen == 5
    assert backbone.matching == 4  # W4 has no core term
    assert set(backbone.works) == {"W1", "W2", "W3", "W5"}
    assert {ref.author_id for ref in backbone.works["W2"]} == {"A2", "A3"}  # abstract match


def test_author_tables_count_backbone_works_and_pairs(tmp_path: Path) -> None:
    backbone = read_backbone(_author_dataset(tmp_path), _core_terms()).works
    tables = author_tables(backbone)
    assert "A4" not in tables.works and "A5" not in tables.works
    assert tables.works["A2"] == 3 and tables.works["A1"] == 2 and tables.works["A3"] == 2
    assert dict(tables.edges) == {("A1", "A2"): 2, ("A2", "A3"): 2, ("A1", "A3"): 1}
    assert tables.edge_works == 3 and tables.hyper_works == 1


def test_hyper_authorship_work_adds_nodes_but_no_edges(tmp_path: Path) -> None:
    backbone = read_backbone(_author_dataset(tmp_path), _core_terms()).works
    assert MAX_AUTHORS_PER_WORK == 25
    tables = author_tables(backbone)
    hyper_ids = {f"A{10 + i}" for i in range(26)}
    assert all(tables.works[author] == 1 for author in hyper_ids)
    assert not any(a in hyper_ids or b in hyper_ids for a, b in tables.edges)
    # Lifting the cap to 26 makes the same work add C(26, 2) = 325 pairs.
    lifted = author_tables(backbone, max_authors=26)
    assert len(lifted.edges) == len(tables.edges) + 325
    assert lifted.hyper_works == 0


def test_author_nodes_names_countries_and_weights(tmp_path: Path) -> None:
    build = build_graphs(_author_dataset(tmp_path), layout_iterations=5)
    authors = json.loads(build.files[AUTHOR_GRAPH_NAME])
    rows = authors["nodes"]["rows"]
    assert authors["nodes"]["fields"] == list(AUTHOR_NODE_FIELDS)
    assert [row[0] for row in rows] == ["A2", "A1", "A3"]  # works desc, then id
    assert [row[1] for row in rows] == ["Bo Example", "Ann Example", "Cy Example"]
    assert [row[2] for row in rows] == ["US", "NL", "DE"]  # A3 ties US/DE: lowest code
    assert [row[3] for row in rows] == [3, 2, 2]
    assert sorted(authors["edges"]["rows"]) == [[0, 1, 2], [0, 2, 2], [1, 2, 1]]
    assert len(build.files["authors_layout"]) == 8 * 3
    assert build.manifest["graphs"][AUTHOR_GRAPH_NAME]["nodes"] == 3


def test_author_caps_and_budgets(tmp_path: Path) -> None:
    raw = _author_dataset(tmp_path)
    capped = build_graphs(raw, layout_iterations=5, author_node_cap=2, author_phone_cap=1)
    authors = json.loads(capped.files[AUTHOR_GRAPH_NAME])
    phone = json.loads(capped.files[AUTHOR_PHONE_GRAPH_NAME])
    assert [row[0] for row in authors["nodes"]["rows"]] == ["A2", "A1"]
    assert authors["edges"]["rows"] == [[0, 1, 2]]
    assert [row[0] for row in phone["nodes"]["rows"]] == ["A2"]
    assert phone["edges"]["rows"] == []
    assert len(capped.files["authors_layout"]) == 16

    budgeted = build_graphs(
        raw,
        layout_iterations=5,
        author_edge_budget=2,
        author_start_k=1,
        author_phone_edge_budget=2,
        author_phone_start_k=1,
    )
    kept = json.loads(budgeted.files[AUTHOR_GRAPH_NAME])["edges"]["rows"]
    assert len(kept) <= 2
    assert {n for a, b, _ in kept for n in (a, b)} == {0, 1, 2}  # every node keeps an edge
    manifest = budgeted.manifest["graphs"][AUTHOR_GRAPH_NAME]
    assert manifest["thinning"]["budget"] == 2


def test_author_build_is_deterministic(tmp_path: Path) -> None:
    raw = _author_dataset(tmp_path)
    first = build_graphs(raw, layout_iterations=20)
    second = build_graphs(raw, layout_iterations=20)
    assert first.files == second.files


def test_author_outputs_have_no_email_orcid_or_affiliation(tmp_path: Path) -> None:
    build = build_graphs(_author_dataset(tmp_path), layout_iterations=5)
    assert set(AUTHOR_NODE_FIELDS).isdisjoint(FORBIDDEN_KEYS)
    for key in (AUTHOR_GRAPH_NAME, AUTHOR_PHONE_GRAPH_NAME):
        text = build.files[key].decode("utf-8")
        for banned in ("@", "example.org", "orcid", "affiliation", "dept of things", "marine"):
            assert banned not in text.lower(), banned
        payload = json.loads(text)
        assert set(payload) == {"communities", "edges", "graph", "nodes", "schema_version"}


def test_institution_outputs_do_not_depend_on_author_backbone(tmp_path: Path) -> None:
    with_titles = build_graphs(_author_dataset(tmp_path / "a"), layout_iterations=5)
    without = build_graphs(_author_dataset(tmp_path / "b", with_titles=False), layout_iterations=5)
    for key in (GRAPH_NAME, PHONE_GRAPH_NAME, "layout"):
        assert with_titles.files[key] == without.files[key]
    assert json.loads(without.files[AUTHOR_GRAPH_NAME])["nodes"]["rows"] == []


def test_empty_backbone_gives_empty_author_graph(tmp_path: Path) -> None:
    build = build_graphs(_author_dataset(tmp_path, with_titles=False), layout_iterations=5)
    authors = json.loads(build.files[AUTHOR_GRAPH_NAME])
    assert authors["nodes"]["rows"] == [] and authors["edges"]["rows"] == []
    assert build.files["authors_layout"] == b""
    assert build.manifest["author_graph"]["backbone"]["works_matching"] == 0
    empty = build_author_graph({})
    assert empty["ids"] == [] and empty["positions"] == []


def test_check_outputs_covers_author_files(tmp_path: Path) -> None:
    build = build_graphs(_author_dataset(tmp_path), layout_iterations=5)
    out = tmp_path / "out"
    out.mkdir()
    for key, name in FILE_NAMES.items():
        (out / name).write_bytes(build.files[key])
    assert check_outputs(out) == []
    (out / FILE_NAMES["authors_layout"]).write_bytes(b"\x00" * 4)
    assert any("authors layout" in problem for problem in check_outputs(out))
