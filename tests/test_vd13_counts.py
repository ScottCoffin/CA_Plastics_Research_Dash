"""VD-13: Overview entry-card counts in build_metadata.json, refreshed after the network build."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from atlas.build.export_site import _sibling_counts, export_site, refresh_metadata_counts
from atlas.build.network import network_counts
from atlas.ingest.normalize import normalize_fixture

pytest.importorskip("networkx")

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "s2_2_openalex_works.json"
INSTITUTIONS = ROOT / "data" / "processed" / "institutions.parquet"
BUILD_NETWORK = ROOT / "scripts" / "build_network.py"
INDEX_PAGE = ROOT / "framework" / "src" / "index.md"
EXPORT_SRC = ROOT / "src" / "atlas" / "build" / "export_site.py"
NETWORK_SRC = ROOT / "src" / "atlas" / "build" / "network.py"
SITE_DATA = ROOT / "docs" / "SITE_DATA.md"
CARD_KEYS = {
    "awards",
    "monitoring_samples",
    "monitoring_sources",
    "network_experts",
    "network_links",
    "plastic_works",
}
SIBLING_KEYS = CARD_KEYS - {"plastic_works"}

NETWORK = {
    "nodes": [{"id": "A"}, {"id": "B"}, {"id": "C"}],
    "edges": [
        {"source": "A", "target": "B", "weight": 2},
        {"source": "B", "target": "C", "weight": 0.5},
        {"source": "A", "target": "C", "weight": 1},
    ],
}
NETWORK_INDEX = {
    "authors": [
        {"author_id": "A1", "name": "One", "ca_plastic_works_count": 5, "plastic_citations": 10},
        {"author_id": "A2", "name": "Two", "ca_plastic_works_count": 3, "plastic_citations": 50},
        {"author_id": "A3", "name": "Three", "ca_plastic_works_count": 3, "plastic_citations": 5},
        {"author_id": "A4", "name": "Solo", "ca_plastic_works_count": 9, "plastic_citations": 99},
        {"author_id": "A5", "name": "Five", "ca_plastic_works_count": 1, "plastic_citations": 1},
    ],
    "works": [
        {"work_id": "W1", "plastic_related": True, "year": 2020, "author_ids": ["A1", "A2"]},
        {"work_id": "W2", "plastic_related": True, "year": 2021, "author_ids": ["A1", "A2", "A3"]},
        {"work_id": "W3", "plastic_related": False, "year": 2021, "author_ids": ["A1", "A5"]},
        {"work_id": "W4", "plastic_related": True, "year": 2022, "author_ids": ["A4"]},
        {"work_id": "W5", "plastic_related": True, "year": 2022, "author_ids": ["A3", "A5"]},
    ],
    "generated_at": "fixture",
}


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_siblings(output: Path) -> None:
    _write(
        output / "grants.json",
        {
            "rows": [
                {"plastic_related": True},
                {"plastic_related": None},
                {"plastic_related": False},
                {"plastic_related": True},
            ]
        },
    )
    _write(
        output / "monitoring.json",
        {
            "publication_mode": "public_cleared",
            "sample_count": 7,
            "datasets": [{"id": "d1"}, {"id": "d2"}],
        },
    )
    _write(output / "network.json", NETWORK)


def _load_build_network():
    spec = importlib.util.spec_from_file_location("build_network_vd13", BUILD_NETWORK)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _export(tmp_path: Path, *, with_siblings: bool) -> Path:
    normalized = normalize_fixture(
        FIXTURE,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "normalized",
        qc_path=tmp_path / "qc.md",
        generated_at="test",
    )
    output = tmp_path / "site"
    if with_siblings:
        _write_siblings(output)
    export_site(
        works_path=normalized.output_dir / "works.parquet",
        authors_path=normalized.output_dir / "authors.parquet",
        authorships_path=normalized.output_dir / "authorships.parquet",
        institutions_path=normalized.output_dir / "institutions.parquet",
        output_dir=output,
        generated_at="test",
    )
    return output


def test_sibling_counts_follow_the_default_view_of_each_page(tmp_path: Path) -> None:
    _write_siblings(tmp_path)

    assert _sibling_counts(tmp_path) == {
        "awards": 3,  # Funding default: plastic_related true or unknown
        "monitoring_samples": 7,
        "monitoring_sources": 2,
        "network_experts": 3,
        "network_links": 2,  # A-C weight 1 and A-B weight 2; B-C (0.5) is hidden by default
    }


def test_sibling_counts_omit_keys_whose_source_is_absent_or_unreadable(tmp_path: Path) -> None:
    assert _sibling_counts(tmp_path) == {}

    (tmp_path / "grants.json").write_text("{not json", encoding="utf-8")
    _write(tmp_path / "monitoring.json", {"sample_count": "7"})
    _write(tmp_path / "network.json", {"nodes": "not a list", "edges": []})

    assert _sibling_counts(tmp_path) == {}


def test_private_monitoring_preview_is_not_counted(tmp_path: Path) -> None:
    _write(
        tmp_path / "monitoring.json",
        {"publication_mode": "private_preview", "sample_count": 7, "datasets": [{"id": "d1"}]},
    )

    assert _sibling_counts(tmp_path) == {}


def test_network_counts_mirror_the_page_default_view() -> None:
    nodes = [{"id": "A"}, {"id": "B"}, {"id": "C"}, {"name": "no id"}, {"id": 7}]
    edges = [
        {"source": "A", "target": "B", "weight": 2},
        {"source": "B", "target": "C", "weight": 0.5},  # below the default minimum of one
        {"source": "A", "target": "Z", "weight": 3},  # unlisted endpoint
        {"source": "A", "target": "A", "weight": 1},  # self-loop
        {"source": "C", "target": "A", "weight": 1},
    ]

    assert network_counts({"nodes": nodes, "edges": edges}) == {
        "network_experts": 3,
        "network_links": 2,
    }


def test_export_merges_card_counts_into_metadata_only(tmp_path: Path) -> None:
    output = _export(tmp_path, with_siblings=True)
    index = json.loads((output / "index.json").read_text(encoding="utf-8"))
    metadata = json.loads((output / "build_metadata.json").read_text(encoding="utf-8"))

    assert set(index["counts"]) == {
        "authors",
        "ca_institutions",
        "institutions",
        "labeled_works",
        "works",
    }
    assert metadata["counts"]["works"] == index["counts"]["works"]
    assert metadata["counts"]["plastic_works"] == sum(
        1 for work in index["works"] if work["plastic_related"] is True
    )
    assert {key: metadata["counts"][key] for key in SIBLING_KEYS} == {
        "awards": 3,
        "monitoring_samples": 7,
        "monitoring_sources": 2,
        "network_experts": 3,
        "network_links": 2,
    }


def test_export_omits_card_counts_whose_sources_are_absent(tmp_path: Path) -> None:
    output = _export(tmp_path, with_siblings=False)
    metadata = json.loads((output / "build_metadata.json").read_text(encoding="utf-8"))

    assert "plastic_works" in metadata["counts"]
    assert not SIBLING_KEYS & set(metadata["counts"])


def test_refresh_metadata_counts_keeps_every_other_field(tmp_path: Path) -> None:
    path = tmp_path / "build_metadata.json"
    _write(
        path,
        {
            "schema_version": "s3.1",
            "generated_at": "t",
            "counts": {"works": 4, "network_experts": 0},
            "files": {"index.json": {"bytes": 1, "gzip_bytes": 1}},
            "payload_bytes": 1,
        },
    )

    assert refresh_metadata_counts(path, {"network_experts": 3, "network_links": 2}) is True
    refreshed = json.loads(path.read_text(encoding="utf-8"))
    assert refreshed["counts"] == {"works": 4, "network_experts": 3, "network_links": 2}
    assert refreshed["files"] == {"index.json": {"bytes": 1, "gzip_bytes": 1}}
    assert refreshed["schema_version"] == "s3.1" and refreshed["payload_bytes"] == 1
    assert refresh_metadata_counts(tmp_path / "absent.json", {"network_experts": 1}) is False
    assert not (tmp_path / "absent.json").exists()


def test_build_network_refreshes_network_counts_in_metadata(tmp_path: Path, capsys) -> None:
    module = _load_build_network()
    index = tmp_path / "index.json"
    _write(index, NETWORK_INDEX)
    out = tmp_path / "site" / "network.json"
    metadata_path = tmp_path / "site" / "build_metadata.json"
    _write(
        metadata_path,
        {
            "schema_version": "s3.1",
            "counts": {"works": 5, "network_experts": 99, "network_links": 99},
            "files": {"index.json": {"bytes": 1, "gzip_bytes": 1}},
        },
    )

    status = module.main(
        ["--index", str(index), "--institutions", str(tmp_path / "none.json"), "--out", str(out)]
    )

    assert status == 0
    network = json.loads(out.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["counts"] == {"works": 5, **network_counts(network)}
    assert metadata["counts"]["network_experts"] == 4  # A1, A2, A3, A5 (A4 is isolated)
    assert metadata["files"] == {"index.json": {"bytes": 1, "gzip_bytes": 1}}
    assert "not refreshed" not in capsys.readouterr().err


def test_build_network_without_metadata_writes_no_metadata(tmp_path: Path, capsys) -> None:
    module = _load_build_network()
    index = tmp_path / "index.json"
    _write(index, NETWORK_INDEX)
    out = tmp_path / "site" / "network.json"
    out.parent.mkdir(parents=True)

    status = module.main(
        ["--index", str(index), "--institutions", str(tmp_path / "none.json"), "--out", str(out)]
    )

    assert status == 0 and out.exists()
    assert not (tmp_path / "site" / "build_metadata.json").exists()
    assert "not refreshed" in capsys.readouterr().err


def test_overview_cards_read_the_card_counts_from_build_metadata() -> None:
    page = INDEX_PAGE.read_text(encoding="utf-8")
    export = EXPORT_SRC.read_text(encoding="utf-8") + NETWORK_SRC.read_text(encoding="utf-8")
    # VD-25b: every count is a data-count placeholder. Authors and California institutions come
    # from the About stats; the six card keys come from metadata.counts.
    placeholders = set(re.findall(r'data-count="([^"]+)"', page))

    assert CARD_KEYS <= placeholders
    # type_summary (owner 2026-11-17) is the living output mix from metadata.flow.by_type.
    assert placeholders - CARD_KEYS == {"authors", "california_institutions", "type_summary"}
    assert "metadata?.flow?.by_type" in page
    # Four door counts and seven band facts, each hidden unless every value in it is present.
    assert len(re.findall(r"<(?:li|small)[^>]*data-count-group", page)) == 11
    assert 'import {loadJson, aboutViewModel, formatCount} from "./components/atlas.js";' in page
    assert "metadata?.counts" in page
    assert "countText(formatCount(metadataCounts[key]))" in page
    assert "group.hidden = !ready" in page
    assert 'data-suffix="works in snapshot"' not in page
    for key in CARD_KEYS:
        assert f'"{key}"' in export
    assert "counts.awards" not in page


def test_site_data_documents_the_card_count_keys() -> None:
    text = SITE_DATA.read_text(encoding="utf-8")

    for key in CARD_KEYS:
        assert f"`{key}`" in text
