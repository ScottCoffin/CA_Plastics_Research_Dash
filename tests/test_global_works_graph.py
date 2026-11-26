"""Global works similarity graph (BQ-V.1 slice 3) on synthetic raw pages and a fake embedder."""

from __future__ import annotations

import gzip
import importlib.util
import json
import re
import zlib
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import atlas.nlp.active_relevance as active_relevance
from atlas.build import global_works_graph as works
from atlas.build.global_graphs import FORBIDDEN_KEYS
from atlas.build.global_works_graph import (
    FILE_NAMES,
    WorkCandidate,
    build_works_graph,
    check_works_outputs,
    knn_edges,
    ordered_candidates,
    read_works,
    rebuild_for_check,
)
from atlas.ingest.global_partition import NoRawStoreError

ROOT = Path(__file__).resolve().parents[1]
CORE = {"version": "test-core", "core_terms": ["microplastic"]}
PERSON_NAME = "Dr Person Example"
ABSTRACT_SECRET = "secretword"


def _fake_embedder(texts: Any) -> np.ndarray:
    """Hash words into 16 buckets and normalise: deterministic, no model."""
    rows = np.zeros((len(texts), 16), dtype=np.float32)
    for i, text in enumerate(texts):
        for word in re.findall(r"[a-z]+", text.lower()):
            rows[i, zlib.crc32(word.encode("utf-8")) % 16] += 1.0
    norms = np.linalg.norm(rows, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return rows / norms


def _write_page(raw: Path, name: str, fetched: str, works_list: list[dict[str, Any]]) -> None:
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
        for work in works_list:
            handle.write(json.dumps(work) + "\n")


def _work(
    work_id: str,
    title: str,
    *,
    cited: int = 0,
    language: str | None = "en",
    abstract: str | None = None,
    year: int = 2020,
) -> dict[str, Any]:
    work: dict[str, Any] = {
        "id": f"https://openalex.org/{work_id}",
        "title": title,
        "publication_year": year,
        "cited_by_count": cited,
        "language": language,
        "authorships": [
            {
                "author": {
                    "id": "https://openalex.org/A987654321",
                    "display_name": PERSON_NAME,
                    "orcid": "https://orcid.org/0000-0000-0000-0000",
                },
                "institutions": [{"id": "https://openalex.org/I1", "display_name": "Uni"}],
            }
        ],
    }
    if abstract:
        work["abstract_inverted_index"] = {w: [i] for i, w in enumerate(abstract.split())}
    return work


def _dataset(tmp_path: Path) -> Path:
    """Page 1 then page 2 (page 2 overrides W1 and removes W4). W3, W5 and W4 are not candidates."""
    raw = tmp_path / "raw"
    long_title = "Microplastic fibres " + "wastewater " * 20
    _write_page(
        raw,
        "2022_00001.jsonl.gz",
        "2026-11-20T10:00:00+00:00",
        [
            _work("W1", "Microplastic in river sediment", cited=40, abstract="sampling outfalls"),
            _work("W2", long_title, cited=40, year=2021),
            _work("W3", "Soil nutrient cycling", cited=90),
            _work("W4", "Old microplastic title", cited=5),
            _work("W5", "", cited=7),
            _work("W6", "Microplastic uptake in mussels", cited=12, language="fr"),
            _work(
                "W7",
                "Microplastic in ocean gyres",
                cited=12,
                language=None,
                abstract=f"plastic {ABSTRACT_SECRET} particles",
            ),
        ],
    )
    _write_page(
        raw,
        "2022_00002.jsonl.gz",
        "2026-11-22T10:00:00+00:00",
        [
            _work("W1", "Microplastic in river sediment, revised", cited=50),
            _work("W4", "Soil nutrient cycling", cited=5),
        ],
    )
    return raw


def _build(raw: Path, tmp_path: Path, name: str = "cache", **kwargs: Any) -> Any:
    return build_works_graph(
        raw,
        embedder=_fake_embedder,
        cache_path=tmp_path / name / "works.npz",
        pollution_core=CORE,
        **kwargs,
    )


def _write_out(out: Path, build: Any) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for key, name in FILE_NAMES.items():
        (out / name).write_bytes(build.files[key])


def _load_script() -> Any:
    spec = importlib.util.spec_from_file_location(
        "build_global_works_graph", ROOT / "scripts" / "build_global_works_graph.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_read_latest_page_wins_and_filters_candidates(tmp_path: Path) -> None:
    read = read_works(_dataset(tmp_path), CORE["core_terms"])
    ids = sorted(c.id for c in read.candidates)
    assert ids == ["W1", "W2", "W6", "W7"]  # W3 off backbone, W4 overridden, W5 empty text
    assert read.works_distinct == 7
    assert read.pages == 2
    assert read.query_version == "plastic-v3.1"
    by_id = {c.id: c for c in read.candidates}
    assert by_id["W1"].cited_by_count == 50
    assert by_id["W1"].title == "Microplastic in river sediment, revised"
    assert by_id["W6"].language == "fr"
    assert by_id["W7"].language is None
    assert by_id["W2"].publication_year == 2021
    assert ABSTRACT_SECRET in by_id["W7"].text
    assert ABSTRACT_SECRET not in by_id["W7"].title


def test_ordering_is_cited_by_count_then_id() -> None:
    def cand(work_id: str, cited: int) -> WorkCandidate:
        return WorkCandidate(work_id, "t", None, cited, "en", "t")

    ordered = ordered_candidates([cand("W9", 3), cand("W2", 10), cand("W1", 3), cand("W5", 10)])
    assert [c.id for c in ordered] == ["W2", "W5", "W1", "W9"]


def test_knn_tie_rule_prefers_lower_index() -> None:
    vectors = np.array([[1, 0], [0, 1], [0, 1], [0, 1]], dtype=np.float32)
    edges = knn_edges(vectors, 1)
    # node 0 ties on 1, 2, 3 -> 1; node 1 ties on 2, 3 -> 2; node 2 ties on 1, 3 -> 1; node 3 -> 1
    assert [(a, b) for a, b, _ in edges] == [(0, 1), (1, 2), (1, 3)]
    assert [w for _, _, w in edges] == [0.0, 1.0, 1.0]  # cosine of orthogonal rows is 0


def test_knn_matches_brute_force_union_and_block_size_is_irrelevant() -> None:
    rng = np.random.default_rng(0)
    vectors = rng.normal(size=(25, 8)).astype(np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    sims = vectors @ vectors.T
    k = 3
    expected: set[tuple[int, int]] = set()
    for i in range(25):
        others = sorted((j for j in range(25) if j != i), key=lambda j: (-sims[i, j], j))[:k]
        expected |= {(min(i, j), max(i, j)) for j in others}
    edges = knn_edges(vectors, k)
    assert {(a, b) for a, b, _ in edges} == expected
    assert all(a < b for a, b, _ in edges)
    assert edges == knn_edges(vectors, k, block_rows=4)
    for a, b, w in edges:
        assert abs(w - float(sims[a, b])) < 1e-3


def test_build_selects_desktop_then_phone_prefix(tmp_path: Path) -> None:
    raw = _dataset(tmp_path)
    build = _build(raw, tmp_path, node_cap=3, phone_cap=2, k=1, phone_k=1)
    desktop = json.loads(build.files["works"])
    phone = json.loads(build.files["works_phone"])
    assert [row[0] for row in desktop["nodes"]] == ["W1", "W2", "W6"]
    assert [row[0] for row in phone["nodes"]] == ["W1", "W2"]
    assert build.manifest["counts"]["candidates"] == 4
    assert build.manifest["counts"]["desktop_nodes"] == 3
    assert build.manifest["counts"]["phone_nodes"] == 2
    assert all(a < b for a, b, _ in desktop["edges"])
    assert 2 <= len(desktop["edges"]) <= 3  # k=1 on three nodes: at least 2 distinct pairs


def test_each_node_keeps_k_neighbours_and_edges_are_union(tmp_path: Path) -> None:
    build = _build(_dataset(tmp_path), tmp_path, k=2)
    desktop = json.loads(build.files["works"])
    n = len(desktop["nodes"])
    degree = [0] * n
    for a, b, _ in desktop["edges"]:
        degree[a] += 1
        degree[b] += 1
    assert min(degree) >= min(2, n - 1)
    assert build.manifest["counts"]["desktop_edges"] == len(desktop["edges"])


def test_phone_recomputes_knn_inside_its_subset(tmp_path: Path) -> None:
    raw = _dataset(tmp_path)
    build = _build(raw, tmp_path, node_cap=4, phone_cap=3, k=2, phone_k=1)
    phone = json.loads(build.files["works_phone"])
    texts = [c.text for c in ordered_candidates(read_works(raw, CORE["core_terms"]).candidates)]
    vectors = _fake_embedder(texts[:3])
    expected = {(a, b) for a, b, _ in knn_edges(vectors, 1)}
    assert {(a, b) for a, b, _ in phone["edges"]} == expected
    assert all(a < b < 3 for a, b, _ in phone["edges"])


def test_embedding_quality_and_title_truncation(tmp_path: Path) -> None:
    build = _build(_dataset(tmp_path), tmp_path)
    rows = {row[0]: row for row in json.loads(build.files["works"])["nodes"]}
    assert rows["W1"][4] == "ok"
    assert rows["W6"][4] == "low"  # French
    assert rows["W7"][4] == "low"  # no language recorded
    long = rows["W2"][1]
    assert len(long) == works.TITLE_MAX_CHARS
    assert long.endswith("…")
    assert rows["W2"][2] == 2021
    assert build.manifest["counts"]["low_quality_nodes"] == 2


def test_no_forbidden_keys_abstract_or_names_are_written(tmp_path: Path) -> None:
    build = _build(_dataset(tmp_path), tmp_path)
    for key in ("works", "works_phone", "manifest"):
        payload = json.loads(build.files[key])
        assert not works._forbidden_key_hits(payload)
    assert {"abstract", "text"} <= works.WORKS_FORBIDDEN_KEYS
    assert FORBIDDEN_KEYS <= works.WORKS_FORBIDDEN_KEYS
    for data in build.files.values():
        assert ABSTRACT_SECRET.encode() not in data
        assert PERSON_NAME.encode() not in data
        assert b"orcid" not in data
        assert b"A987654321" not in data


def test_build_is_deterministic(tmp_path: Path) -> None:
    raw = _dataset(tmp_path)
    first = _build(raw, tmp_path, name="a")
    second = _build(raw, tmp_path, name="b")
    assert first.files == second.files


def test_check_outputs_accepts_build_and_catches_broken_file(tmp_path: Path) -> None:
    out = tmp_path / "out"
    build = _build(_dataset(tmp_path), tmp_path)
    _write_out(out, build)
    assert check_works_outputs(out) == []

    layout = out / FILE_NAMES["layout"]
    good = layout.read_bytes()
    layout.write_bytes(good[:-4])
    assert any("layout" in problem for problem in check_works_outputs(out))
    layout.write_bytes(good)

    desktop = out / FILE_NAMES["works"]
    payload = json.loads(desktop.read_text(encoding="utf-8"))
    payload["schema_version"] = "bad"
    desktop.write_text(json.dumps(payload), encoding="utf-8")
    problems = check_works_outputs(out)
    assert any("schema or graph name" in problem for problem in problems)


def test_check_outputs_reports_missing_files(tmp_path: Path) -> None:
    problems = check_works_outputs(tmp_path / "nothing")
    assert problems and problems[0].startswith("missing:")


def test_rebuild_for_check_never_embeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _dataset(tmp_path)
    build = _build(raw, tmp_path)
    out = tmp_path / "out"
    _write_out(out, build)
    calls: list[int] = []

    def boom(*_: Any, **__: Any) -> Any:
        calls.append(1)
        raise AssertionError("the model must not be loaded")

    monkeypatch.setattr(active_relevance, "sentence_transformer_embedder", boom)
    cache = tmp_path / "cache" / "works.npz"
    cache_bytes = cache.read_bytes()
    rebuilt = rebuild_for_check(raw, cache)
    assert rebuilt is not None
    assert rebuilt.files == build.files
    assert calls == []

    _write_page(
        raw,
        "2022_00003.jsonl.gz",
        "2026-11-24T10:00:00+00:00",
        [_work("W8", "Microplastic newly added", cited=100)],
    )
    assert rebuild_for_check(raw, cache) is None
    assert cache.read_bytes() == cache_bytes
    assert calls == []


def test_missing_raw_store_and_no_candidates_raise(tmp_path: Path) -> None:
    with pytest.raises(NoRawStoreError):
        build_works_graph(tmp_path / "absent", embedder=_fake_embedder, pollution_core=CORE)
    raw = tmp_path / "raw"
    _write_page(raw, "2022_00001.jsonl.gz", "2026-11-20T10:00:00+00:00", [_work("W1", "Soil")])
    with pytest.raises(ValueError, match="no backbone works"):
        _build(raw, tmp_path)


def test_script_check_passes_skips_and_flags_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script = _load_script()
    raw = _dataset(tmp_path)
    build = _build(raw, tmp_path)
    out = tmp_path / "out"
    _write_out(out, build)
    cache = tmp_path / "cache" / "works.npz"
    base = ["--check", "--raw-dir", str(raw), "--out-dir", str(out), "--cache", str(cache)]

    assert script.main(base) == 0
    assert "current" in capsys.readouterr().out

    # a text change with the same byte length makes the committed file stale
    desktop = out / FILE_NAMES["works"]
    desktop.write_bytes(desktop.read_bytes().replace(b"river", b"rivex", 1))
    assert script.main(base) == 1
    assert "stale" in capsys.readouterr().err
    desktop.write_bytes(build.files["works"])

    # a work the cache does not hold: nothing is embedded, the check is skipped
    _write_page(
        raw,
        "2022_00003.jsonl.gz",
        "2026-11-24T10:00:00+00:00",
        [_work("W8", "Microplastic newly added", cited=100)],
    )
    assert script.main(base) == 0
    assert "embedding cache incomplete" in capsys.readouterr().out

    absent = ["--check", "--raw-dir", str(tmp_path / "absent"), "--out-dir", str(out)]
    absent += ["--cache", str(cache)]
    assert script.main(absent) == 0
    assert "raw store absent" in capsys.readouterr().out


def test_fit_budget_drops_weakest_edges_without_isolating_a_node() -> None:
    from atlas.build.global_works_graph import fit_budget

    edges = [(0, 1, 0.9), (0, 2, 0.2), (1, 2, 0.3), (2, 3, 0.1)]
    # (2, 3) is weakest but node 3 has no other edge, so the next weakest, (0, 2), goes.
    assert fit_budget(edges, 3) == [(0, 1, 0.9), (1, 2, 0.3), (2, 3, 0.1)]
    assert fit_budget(edges, 10) == edges
    # Cannot go lower without isolating a node: stays above the budget.
    assert fit_budget([(0, 1, 0.5), (2, 3, 0.4)], 1) == [(0, 1, 0.5), (2, 3, 0.4)]
