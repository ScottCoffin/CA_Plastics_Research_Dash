"""GP-3: reference-region collaboration network (unscreened region works, region-folder output)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("networkx")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_network  # noqa: E402

from atlas.build.network import (  # noqa: E402
    REGION_WORKS_METHOD,
    unscreened_region_index,
)
from atlas.build.network import build_network as build  # noqa: E402

INDEX = {
    "schema_version": "region-v1-index",
    "generated_at": "2026-11-27T00:00:00+00:00",
    "authors": [
        {
            "author_id": "A1",
            "name": "One",
            "work_count": 3,
            "cited_by_count": None,
            "institution_ids": ["I1"],
            "primary_affiliations": ["Uni X"],
            "domain_tags": [],
        },
        {
            "author_id": "A2",
            "name": "Two",
            "work_count": 2,
            "cited_by_count": None,
            "institution_ids": ["I1"],
            "primary_affiliations": ["Uni X"],
            "domain_tags": [],
        },
        {
            "author_id": "A3",
            "name": "Three",
            "work_count": 2,
            "cited_by_count": None,
            "institution_ids": ["I2"],
            "primary_affiliations": [],
            "domain_tags": [],
        },
        {
            "author_id": "A4",
            "name": "Four",
            "work_count": 2,
            "cited_by_count": None,
            "institution_ids": ["I2"],
            "primary_affiliations": [],
            "domain_tags": [],
        },
    ],
    "works": [
        {
            "work_id": "W1",
            "plastic_related": None,
            "year": 2020,
            "author_ids": ["A1", "A2"],
            "domain_tags": ["recycling"],
        },
        {
            "work_id": "W2",
            "plastic_related": None,
            "year": 2021,
            "author_ids": ["A1", "A2", "A3"],
            "domain_tags": ["recycling"],
        },
        {
            "work_id": "W3",
            "plastic_related": None,
            "year": 2022,
            "author_ids": ["A3", "A4"],
            "domain_tags": ["microplastics"],
        },
        {
            "work_id": "W4",
            "plastic_related": None,
            "year": 2022,
            "author_ids": ["A1", "A4"],
            "domain_tags": [],
        },
    ],
}
INSTITUTIONS = [
    {"inst_id": "I1", "name": "Uni X", "atlas_type": "academic"},
    {"inst_id": "I2", "name": "Institute Y", "atlas_type": "government"},
]


def test_unscreened_view_counts_every_region_work_as_plastic():
    view = unscreened_region_index(INDEX)
    assert all(work["plastic_related"] is True for work in view["works"])
    volumes = {a["author_id"]: a["ca_plastic_works_count"] for a in view["authors"]}
    assert volumes == {"A1": 3, "A2": 2, "A3": 2, "A4": 2}
    # The input is not mutated.
    assert INDEX["works"][0]["plastic_related"] is None


def test_region_network_schema_and_edges():
    network = build(unscreened_region_index(INDEX), INSTITUTIONS, cap=10)
    assert network["schema_version"] == "s9.4-v1.1"
    assert {node["id"] for node in network["nodes"]} == {"A1", "A2", "A3", "A4"}
    pairs = {(e["source"], e["target"]): e["weight"] for e in network["edges"]}
    assert pairs[("A1", "A2")] == 2.0
    assert pairs[("A3", "A4")] == 1.0
    assert all(
        set(node) >= {"x", "y", "community", "institutions", "sectors"} for node in network["nodes"]
    )


def test_region_network_is_deterministic():
    view = unscreened_region_index(INDEX)
    first = build(view, INSTITUTIONS, cap=10)
    second = build(view, INSTITUTIONS, cap=10)
    assert first == second


def test_cli_region_writes_region_file_and_checks(tmp_path):
    paths = {}
    for name, payload in (("index", INDEX), ("institutions", INSTITUTIONS)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[name] = str(path)
    out = tmp_path / "network.json"
    argv = [
        "--region",
        "norway",
        "--index",
        paths["index"],
        "--institutions",
        paths["institutions"],
        "--out",
        str(out),
    ]
    assert build_network.main(argv) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["method"]["works"] == REGION_WORKS_METHOD
    assert build_network.main([*argv, "--check"]) == 0
    out.write_text(out.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert build_network.main([*argv, "--check"]) == 1
    assert not (tmp_path / "build_metadata.json").exists()


def test_cli_rejects_bad_region_slug():
    with pytest.raises(SystemExit):
        build_network.main(["--region", "../etc"])
