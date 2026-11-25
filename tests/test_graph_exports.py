"""Graph exports (BQ-V.6): GEXF and GraphML files built from a tiny synthetic graph set."""

from __future__ import annotations

import gzip
import importlib.util
import json
import struct
from pathlib import Path
from typing import Any

import networkx as nx
import pytest

from atlas.build import graph_exports
from atlas.build.graph_exports import build_exports, check_exports, write_exports

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_graph_exports.py"
ALLOWED_ATTRIBUTES = {"label", "works", "community", "country", "type", "ror", "x", "y", "viz"}
FORBIDDEN_KEYS = {
    "email",
    "emails",
    "affiliation",
    "affiliations",
    "raw_affiliation_strings",
    "orcid",
    "observed_orcids",
    "institutions",
    "institution_ids",
    "primary_affiliations",
    "current_in_ca",
}
GENERATED_AT = "2026-11-25T15:42:44.357657+00:00"
INSTITUTION_FIELDS = ["id", "display_name", "ror", "country_code", "type", "works", "community"]
AUTHOR_FIELDS = ["id", "display_name", "country_code", "works", "community"]


def _pack(points: list[tuple[float, float]]) -> bytes:
    flat = [value for point in points for value in point]
    return struct.pack(f"<{len(flat)}f", *flat)


def _write_fixture(root: Path) -> tuple[Path, Path]:
    """Write a synthetic graphs directory and network file; return (graphs_dir, network)."""
    graphs = root / "graphs"
    graphs.mkdir(parents=True)
    institutions = {
        "communities": 2,
        "edges": {
            "fields": ["source", "target", "weight"],
            "rows": [[0, 1, 3], [1, 2, 1], [0, 2, 2]],
        },
        "graph": "institutions",
        "nodes": {
            "fields": INSTITUTION_FIELDS,
            "rows": [
                ["I3", "Gamma University", None, "US", "education", 5, 1],
                ["I1", "Alpha Lab", "https://ror.org/abc", "US", "government", 9, 0],
                ["I2", "Beta Institute", None, "NL", None, 4, 0],
            ],
        },
        "schema_version": "bqv-v1",
    }
    authors = {
        "communities": 2,
        "edges": {
            "fields": ["source", "target", "weight"],
            "rows": [[0, 1, 2], [1, 2, 1], [2, 3, 4]],
        },
        "graph": "authors",
        "nodes": {
            "fields": AUTHOR_FIELDS,
            "rows": [
                ["A2", "Second Author", "NL", 3, 0],
                ["A1", "First Author", None, 7, 1],
                ["A3", "Third Author", "US", 2, 0],
                ["A4", "Fourth Author", None, 1, 1],
            ],
        },
        "schema_version": "bqv-v1",
    }
    (graphs / "institutions.json").write_text(json.dumps(institutions), encoding="utf-8")
    (graphs / "authors.json").write_text(json.dumps(authors), encoding="utf-8")
    (graphs / "layout_institutions.bin").write_bytes(
        _pack([(0.5, -1.25), (0.1234, 2.0), (-0.9999, 0.0)])
    )
    (graphs / "layout_authors.bin").write_bytes(
        _pack([(1.0, 1.0), (-2.5, 0.25), (0.0, -0.125), (3.75, 4.5)])
    )
    manifest = {
        "generated_at": GENERATED_AT,
        "what_this_is_and_is_not": "Institution fixture of unscreened search hits.",
        "author_graph": {"what_this_is_and_is_not": "Author fixture of unscreened search hits."},
    }
    (graphs / "graphs_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    network = {
        "communities": 1,
        "edges": [
            {"source": "A9", "target": "A8", "weight": 2.0, "years": {"2024": 2.0}},
            {"source": "A8", "target": "A7", "weight": 1.0, "years": {"2025": 1.0}},
        ],
        "generated_at": "2026-11-24T20:43:43+00:00",
        "nodes": [
            {
                "community": 0,
                "current_in_ca": True,
                "degree": 2,
                "id": "A9",
                "institution_ids": ["I1"],
                "institutions": ["Alpha Lab"],
                "name": "Cal One",
                "plastic_works": 4,
                "primary_affiliations": ["Alpha Lab"],
                "x": 0.25,
                "y": -0.5,
            },
            {
                "community": 0,
                "current_in_ca": False,
                "degree": 2,
                "id": "A8",
                "institution_ids": [],
                "institutions": [],
                "name": "Cal Two",
                "plastic_works": 2,
                "primary_affiliations": [],
                "x": -0.75,
                "y": 0.5,
            },
            {
                "community": 0,
                "current_in_ca": False,
                "degree": 1,
                "id": "A7",
                "institution_ids": [],
                "institutions": [],
                "name": "Cal Three",
                "plastic_works": 1,
                "primary_affiliations": [],
                "x": 0.0,
                "y": 1.0,
            },
        ],
        "schema_version": "s9.4-v1.1",
    }
    network_path = root / "network.json"
    network_path.write_text(json.dumps(network), encoding="utf-8")
    return graphs, network_path


def _read(path: Path, tmp_path: Path) -> nx.Graph:
    """Read an export back with networkx; gzipped files are decompressed first."""
    if path.suffix == ".gz":
        plain = tmp_path / "decompressed" / path.name[: -len(".gz")]
        plain.parent.mkdir(exist_ok=True)
        plain.write_bytes(gzip.decompress(path.read_bytes()))
        path = plain
    if path.name.endswith(".gexf"):
        return nx.read_gexf(path)
    return nx.read_graphml(path)


def _weights(graph: nx.Graph) -> dict[frozenset[str], float]:
    return {frozenset((u, v)): float(data["weight"]) for u, v, data in graph.edges(data=True)}


def _position(graph: nx.Graph, node: str) -> tuple[float, float]:
    data = graph.nodes[node]
    if "viz" in data:
        position = data["viz"]["position"]
        return float(position["x"]), float(position["y"])
    return float(data["x"]), float(data["y"])


def _build(tmp_path: Path) -> tuple[dict[str, bytes], Path]:
    graphs, network = _write_fixture(tmp_path)
    return build_exports(graphs, network), tmp_path


def test_exports_cover_each_graph_and_format(tmp_path: Path) -> None:
    files, _ = _build(tmp_path)
    assert set(files) == {
        "institutions.gexf",
        "institutions.graphml",
        "authors.gexf",
        "authors.graphml",
        "california_network.gexf",
        "california_network.graphml",
        "manifest.json",
    }


def test_round_trip_counts_weights_and_positions(tmp_path: Path) -> None:
    files, _ = _build(tmp_path)
    out = tmp_path / "exports"
    write_exports(out, files)
    expected_positions = {
        "institutions": {"I3": (0.5, -1.25), "I1": (0.1234, 2.0), "I2": (-0.9999, 0.0)},
        "authors": {
            "A2": (1.0, 1.0),
            "A1": (-2.5, 0.25),
            "A3": (0.0, -0.125),
            "A4": (3.75, 4.5),
        },
    }
    for stem in ("institutions", "authors"):
        for fmt in ("gexf", "graphml"):
            graph = _read(out / f"{stem}.{fmt}", tmp_path)
            assert graph.number_of_nodes() == len(expected_positions[stem])
            assert graph.number_of_edges() == 3
            for node, (x, y) in expected_positions[stem].items():
                px, py = _position(graph, node)
                assert px == pytest.approx(x, abs=1e-6), (stem, fmt, node)
                assert py == pytest.approx(y, abs=1e-6), (stem, fmt, node)
    inst = _read(out / "institutions.gexf", tmp_path)
    assert _weights(inst) == {
        frozenset(("I3", "I1")): 3.0,
        frozenset(("I1", "I2")): 1.0,
        frozenset(("I3", "I2")): 2.0,
    }
    assert inst.nodes["I1"]["label"] == "Alpha Lab"
    assert inst.nodes["I1"]["works"] == 9
    assert _weights(_read(out / "institutions.graphml", tmp_path)) == _weights(inst)
    cal = _read(out / "california_network.graphml", tmp_path)
    assert cal.number_of_nodes() == 3
    assert _weights(cal) == {frozenset(("A9", "A8")): 2.0, frozenset(("A8", "A7")): 1.0}
    assert cal.nodes["A9"]["label"] == "Cal One"


def test_attributes_are_whitelisted(tmp_path: Path) -> None:
    files, _ = _build(tmp_path)
    out = tmp_path / "exports"
    write_exports(out, files)
    for path in out.glob("*.gexf"):
        graph = _read(path, tmp_path)
        for _, data in graph.nodes(data=True):
            assert set(data) <= ALLOWED_ATTRIBUTES, path.name
            assert not FORBIDDEN_KEYS & set(data), path.name
    for path in out.glob("*.graphml"):
        graph = _read(path, tmp_path)
        for _, data in graph.nodes(data=True):
            assert set(data) <= ALLOWED_ATTRIBUTES, path.name
            assert not FORBIDDEN_KEYS & set(data), path.name


def test_build_is_deterministic_and_pins_gexf_date(tmp_path: Path) -> None:
    first, _ = _build(tmp_path / "a")
    second, _ = _build(tmp_path / "b")
    assert first == second
    gexf = first["institutions.gexf"]
    assert b'lastmodifieddate="2026-11-25"' in gexf


def test_large_files_are_committed_gzipped_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(graph_exports, "GZIP_THRESHOLD_BYTES", 10)
    graphs, network = _write_fixture(tmp_path)
    files = build_exports(graphs, network)
    assert "institutions.gexf" not in files
    assert "institutions.gexf.gz" in files
    out = tmp_path / "exports"
    write_exports(out, files)
    graph = _read(out / "authors.graphml.gz", tmp_path)
    assert graph.number_of_edges() == 3
    entries = json.loads(files["manifest.json"])["files"]
    gz_entry = next(entry for entry in entries if entry["file"] == "authors.graphml.gz")
    assert gz_entry["gzip"] is True
    assert gz_entry["bytes"] == len(files["authors.graphml.gz"])
    assert gz_entry["uncompressed_sha256"] != gz_entry["sha256"]


def test_check_detects_stale_export(tmp_path: Path) -> None:
    graphs, network = _write_fixture(tmp_path)
    files = build_exports(graphs, network)
    out = tmp_path / "exports"
    write_exports(out, files)
    assert check_exports(out, files) == []

    (out / "authors.gexf").write_bytes(files["authors.gexf"] + b"\n")
    assert check_exports(out, files) == ["authors.gexf"]

    write_exports(out, files)
    (out / "stray.graphml").write_text("<graphml/>", encoding="utf-8")
    assert check_exports(out, files) == ["unexpected stray.graphml"]

    (out / "stray.graphml").unlink()
    edited = json.loads((graphs / "institutions.json").read_text(encoding="utf-8"))
    edited["edges"]["rows"][0][2] = 4
    (graphs / "institutions.json").write_text(json.dumps(edited), encoding="utf-8")
    rebuilt = build_exports(graphs, network)
    assert check_exports(out, rebuilt) == [
        "institutions.gexf",
        "institutions.graphml",
        "manifest.json",
    ]


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location("build_graph_exports", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_cli_writes_then_checks_and_fails_when_stale(tmp_path: Path) -> None:
    graphs, network = _write_fixture(tmp_path)
    out = tmp_path / "exports"
    script = _load_script()
    args = ["--graphs-dir", str(graphs), "--network", str(network), "--out-dir", str(out)]
    assert script.main(args) == 0
    assert (out / "manifest.json").exists()
    assert script.main([*args, "--check"]) == 0
    (out / "institutions.graphml").write_bytes(b"stale")
    assert script.main([*args, "--check"]) == 1
