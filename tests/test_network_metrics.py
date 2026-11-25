"""BQ-3.2 collaboration metrics: hand-computed synthetic graphs, windows, privacy and schema."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import pytest

from atlas.analytics.network_metrics import (
    ASCERTAINMENT_NOTE,
    DEFINITIONS,
    SCHEMA_VERSION,
    build_metrics,
    comparable,
    in_window,
)

pytest.importorskip("networkx")

ROOT = Path(__file__).resolve().parents[1]
COMMITTED = ROOT / "site" / "data" / "california" / "network_metrics.json"
SCRIPT = ROOT / "scripts" / "build_network_metrics.py"
WINDOW_IDS = ["all", "2011-2015", "2016-2020", "2021-2025", "2026"]
# Ids in the synthetic corpus; X is a co-author outside the authors list.
PERSON_IDS = {"A", "B", "C", "D", "E", "F", "X", "I1", "I2", "I3", "I4", "I5", "I6"}

AUTHORS = [
    {"author_id": "A", "current_in_ca": True, "institution_ids": ["I1"]},
    {"author_id": "B", "current_in_ca": True, "institution_ids": ["I1"]},
    {"author_id": "C", "current_in_ca": True, "institution_ids": ["I2"]},
    {"author_id": "D", "current_in_ca": False, "institution_ids": ["I3"]},
    {"author_id": "E", "current_in_ca": True, "institution_ids": ["I2"]},
    {"author_id": "F", "current_in_ca": True, "institution_ids": []},
]
INSTITUTIONS = [
    {"inst_id": "I1", "atlas_type": "UC", "ca_flag": True},
    {"inst_id": "I2", "atlas_type": "CSU", "ca_flag": True},
    {"inst_id": "I3", "atlas_type": "other", "ca_flag": False},
    {"inst_id": "I4", "atlas_type": "other", "ca_flag": False},
    {"inst_id": "I5", "atlas_type": "UC", "ca_flag": True},
    {"inst_id": "I6", "atlas_type": "other", "ca_flag": False},
]


def _work(
    work_id: str,
    year: int | None,
    author_ids: list[str],
    institution_ids: list[str],
    *,
    plastic: bool = True,
) -> dict[str, Any]:
    return {
        "work_id": work_id,
        "year": year,
        "author_ids": author_ids,
        "institution_ids": institution_ids,
        "plastic_related": plastic,
        "ca_any_author": True,
    }


WORKS = [
    _work("W1", 2012, ["A", "B"], ["I1", "I2"]),
    _work("W2", 2014, ["B", "C", "X"], ["I1", "I2", "I3"]),
    _work("W3", 2018, ["C", "D"], ["I2", "I3"]),
    _work("W4", 2019, ["A"], ["I1"]),
    _work("W5", 2019, ["E"], ["I3"]),
    _work("W6", 2019, ["A", "B"], ["I1"]),
    _work("W7", 2024, ["D", "E"], ["I3", "I4"]),
    _work("W8", 2026, ["F", "X"], ["I5"]),
    _work("W9", 1995, ["A", "B", "C"], ["I1", "I5"]),
    _work("W10", 2012, ["A", "E"], ["I6"], plastic=False),
]


def _index(works: list[dict[str, Any]] = WORKS, authors: list[dict[str, Any]] = AUTHORS) -> dict:
    return {"generated_at": "2026-11-22T00:00:00+00:00", "authors": authors, "works": works}


def _payload(**kwargs: Any) -> dict[str, Any]:
    return build_metrics(_index(), INSTITUTIONS, index_build_timestamp="T0", **kwargs)


def _window(payload: dict[str, Any], graph: str, window: str) -> dict[str, Any]:
    rows = [row for row in payload["graphs"][graph]["windows"] if row["window"] == window]
    assert len(rows) == 1
    return rows[0]


def _walk(value: Any):
    """Yield every (key, value) pair and every string in a nested JSON structure."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield ("key", key)
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)
    else:
        yield ("value", value)


# --- author graph (G-A), hand-computed ---------------------------------------------------------
#
# Author edges on plastic works (X and non-plastic W10 are dropped):
#   all: A-B (W1, W6, W9) = 3, B-C (W2, W9) = 2, A-C (W9) = 1, C-D (W3) = 1, D-E (W7) = 1.
#   nodes A..F; F is on W8 with only the non-corpus X, so F is the single isolate.


def test_author_all_window_hand_computed() -> None:
    row = _window(_payload(), "authors", "all")
    assert row["works"] == 9
    assert row["nodes"] == 6
    assert row["edges"] == 5
    assert row["components"] == 2
    assert row["components_with_edges"] == 1
    assert row["giant_component_nodes"] == 5
    assert row["giant_component_share"] == pytest.approx(5 / 6, abs=1e-4)
    assert row["density"] == pytest.approx(10 / 30, abs=1e-4)  # 2*5 / (6*5)
    # Local clustering: A 1, B 1, C 1/3, D 0, E 0, F 0 -> 7/3 over 6 nodes.
    assert row["average_clustering"] == pytest.approx(7 / 3 / 6, abs=1e-4)
    assert row["isolates"] == 1
    assert row["isolate_share"] == pytest.approx(1 / 6, abs=1e-4)
    # Degrees A 2, B 2, C 3, D 2, E 1, F 0 -> sorted 0,1,2,2,2,3.
    assert row["degree"] == {
        "min": 0.0,
        "p25": 1.25,
        "median": 2.0,
        "p75": 2.0,
        "p90": 2.5,
        "max": 3.0,
    }
    # Louvain on the non-isolate subgraph splits {A,B,C} from {D,E}: modularity 0.1797.
    assert row["communities"] == 2
    assert row["modularity"] == pytest.approx(0.1797, abs=1e-4)


def test_author_all_window_edge_flags() -> None:
    row = _window(_payload(), "authors", "all")
    # Shared institution only for A-B; B-C, A-C, C-D, D-E have none in common.
    assert row["cross_institution"] == {"fraction": 0.8, "edges_considered": 5}
    # Sectors: D has only 'other' (unclassified), so C-D and D-E are not considered.
    assert row["cross_sector"] == {"fraction": 0.6667, "edges_considered": 3}
    # Out of region: D is outside California, which touches C-D and D-E.
    assert row["out_of_region"] == {"fraction": 0.4, "edges_considered": 5}


def test_author_windows_split_by_year() -> None:
    payload = _payload()
    early = _window(payload, "authors", "2011-2015")
    assert early["works"] == 2
    assert (early["nodes"], early["edges"]) == (3, 2)  # A-B, B-C; X dropped
    assert early["components"] == 1
    assert early["density"] == pytest.approx(4 / 6, abs=1e-4)
    assert early["average_clustering"] == 0.0
    assert early["modularity"] == 0.0
    assert early["cross_institution"] == {"fraction": 0.5, "edges_considered": 2}

    mid = _window(payload, "authors", "2016-2020")
    assert mid["works"] == 4
    assert (mid["nodes"], mid["edges"]) == (5, 2)  # A-B and C-D; E is alone in 2019
    assert mid["components"] == 3
    assert mid["components_with_edges"] == 2
    assert mid["giant_component_share"] == pytest.approx(2 / 5, abs=1e-4)
    assert mid["isolates"] == 1
    assert mid["communities"] == 2
    assert mid["modularity"] == pytest.approx(0.5, abs=1e-4)
    assert mid["cross_sector"] == {"fraction": 0.0, "edges_considered": 1}
    assert mid["out_of_region"] == {"fraction": 0.5, "edges_considered": 2}

    late = _window(payload, "authors", "2021-2025")
    assert late["works"] == 1
    assert (late["nodes"], late["edges"], late["isolates"]) == (2, 1, 0)
    assert late["density"] == 1.0
    assert late["cross_sector"] == {"fraction": None, "edges_considered": 0}
    assert late["out_of_region"] == {"fraction": 1.0, "edges_considered": 1}


def test_author_2026_partial_window_has_isolate_only() -> None:
    row = _window(_payload(), "authors", "2026")
    assert row["partial"] is True
    assert row["works"] == 1
    assert (row["nodes"], row["edges"], row["isolates"]) == (1, 0, 1)
    assert row["components"] == 1
    assert row["giant_component_share"] == 1.0
    assert row["isolate_share"] == 1.0
    assert row["density"] is None
    assert row["average_clustering"] == 0.0
    assert row["degree"] == {
        "min": 0.0,
        "p25": 0.0,
        "median": 0.0,
        "p75": 0.0,
        "p90": 0.0,
        "max": 0.0,
    }
    assert row["communities"] == 0
    assert row["modularity"] is None
    assert row["cross_institution"] == {"fraction": None, "edges_considered": 0}


# --- institution graph (G-I), hand-computed ----------------------------------------------------
#
# Institution edges from the work-level institution_ids (plastic works only):
#   all: I1-I2 (W1, W2) = 2, I1-I3 (W2) = 1, I2-I3 (W2, W3) = 2, I3-I4 (W7) = 1, I1-I5 (W9) = 1.


def test_institution_all_window_hand_computed() -> None:
    row = _window(_payload(), "institutions", "all")
    assert row["works"] == 9
    assert (row["nodes"], row["edges"]) == (5, 5)
    assert row["components"] == 1
    assert row["giant_component_share"] == 1.0
    assert row["density"] == 0.5  # 2*5 / (5*4)
    assert row["average_clustering"] == pytest.approx(1 / 3, abs=1e-4)
    assert row["isolates"] == 0
    # Degrees I1 3, I2 2, I3 3, I4 1, I5 1 -> sorted 1,1,2,3,3.
    assert row["degree"] == {
        "min": 1.0,
        "p25": 1.0,
        "median": 2.0,
        "p75": 3.0,
        "p90": 3.0,
        "max": 3.0,
    }
    # By construction every institution edge joins two institutions.
    assert row["cross_institution"] == {"fraction": 1.0, "edges_considered": 5}
    # Only I1-I2 and I1-I5 join two California institutions with a sector; I1-I2 differs.
    assert row["cross_sector"] == {"fraction": 0.5, "edges_considered": 2}
    # I3 and I4 are outside California: I1-I3, I2-I3 and I3-I4 are out of region.
    assert row["out_of_region"] == {"fraction": 0.6, "edges_considered": 5}


def test_institution_windows_split_by_year() -> None:
    payload = _payload()
    early = _window(payload, "institutions", "2011-2015")
    assert (early["works"], early["nodes"], early["edges"]) == (2, 3, 3)
    assert early["density"] == 1.0
    assert early["average_clustering"] == 1.0
    assert early["communities"] == 1
    assert early["modularity"] == 0.0
    assert early["cross_sector"] == {"fraction": 1.0, "edges_considered": 1}
    assert early["out_of_region"] == {"fraction": 0.6667, "edges_considered": 3}

    mid = _window(payload, "institutions", "2016-2020")
    assert mid["works"] == 4
    assert (mid["nodes"], mid["edges"], mid["isolates"]) == (3, 1, 1)
    assert mid["components"] == 2
    assert mid["giant_component_share"] == pytest.approx(2 / 3, abs=1e-4)
    assert mid["density"] == pytest.approx(1 / 3, abs=1e-4)
    assert mid["cross_sector"] == {"fraction": None, "edges_considered": 0}
    assert mid["out_of_region"] == {"fraction": 1.0, "edges_considered": 1}

    partial = _window(payload, "institutions", "2026")
    assert partial["partial"] is True
    assert (partial["nodes"], partial["edges"], partial["isolates"]) == (1, 0, 1)


def test_undated_works_count_only_in_all_window() -> None:
    works = [_work("W1", None, ["A", "B"], ["I1", "I2"])]
    payload = build_metrics(_index(works), INSTITUTIONS)
    all_row = _window(payload, "authors", "all")
    assert (all_row["works"], all_row["nodes"], all_row["edges"]) == (1, 2, 1)
    assert payload["corpus"]["works_without_year"] == 1
    assert payload["corpus"]["works_in_year_windows"] == 0
    for window in WINDOW_IDS[1:]:
        row = _window(payload, "authors", window)
        assert (row["works"], row["nodes"], row["edges"]) == (0, 0, 0)
        assert row["giant_component_share"] is None
        assert row["isolate_share"] is None
        assert row["degree"] is None
        assert row["modularity"] is None


def test_in_window_boundaries() -> None:
    assert in_window({"year": 2011}, 2011, 2015)
    assert in_window({"year": 2015}, 2011, 2015)
    assert not in_window({"year": 2010}, 2011, 2015)
    assert not in_window({"year": 2016}, 2011, 2015)
    assert in_window({"year": 2026}, 2026, 2026)
    assert in_window({"year": 1963}, None, None)
    assert not in_window({"year": None}, 2011, 2015)
    assert in_window({"year": None}, None, None)


def test_corpus_counts_and_non_plastic_works_are_ignored() -> None:
    payload = _payload()
    assert payload["corpus"] == {
        "atlas_authors": 6,
        "plastic_related_works": 9,
        "works_in_year_windows": 8,
        "works_before_2011": 1,
        "works_without_year": 0,
        "works_with_no_california_author": 0,
    }
    # W10 (non-plastic) would add an A-E edge to the author graph if it were counted.
    assert _window(payload, "authors", "all")["edges"] == 5


def test_works_with_no_california_author_are_counted() -> None:
    works = [dict(WORKS[0], ca_any_author=False), dict(WORKS[1])]
    payload = build_metrics(_index(works), INSTITUTIONS)
    assert payload["corpus"]["works_with_no_california_author"] == 1


# --- privacy -----------------------------------------------------------------------------------


def test_payload_has_no_per_person_keys_or_identifiers() -> None:
    payload = _payload()
    keys = {v for kind, v in _walk(payload) if kind == "key"}
    assert not keys & {"author_id", "author_ids", "name", "institution_ids", "inst_id", "id"}
    text = json.dumps(payload)
    assert '"author_id"' not in text
    assert '"name"' not in text
    strings = {v for kind, v in _walk(payload) if kind == "value" and isinstance(v, str)}
    assert not strings & PERSON_IDS


# --- determinism -------------------------------------------------------------------------------


def test_build_is_deterministic_and_order_independent() -> None:
    first = comparable(_payload())
    assert comparable(_payload()) == first
    shuffled = build_metrics(
        _index(list(reversed(WORKS)), list(reversed(AUTHORS))),
        list(reversed(INSTITUTIONS)),
        index_build_timestamp="T0",
    )
    assert comparable(shuffled) == first


def test_generated_at_is_the_only_field_check_ignores() -> None:
    a = _payload(generated_at="2026-01-01T00:00:00+00:00")
    b = _payload(generated_at="2026-06-01T00:00:00+00:00")
    assert a["generated_at"] != b["generated_at"]
    assert comparable(a) == comparable(b)
    assert "generated_at" not in comparable(a)


# --- committed file and CLI --------------------------------------------------------------------


def _committed() -> dict[str, Any]:
    if not COMMITTED.exists():
        pytest.skip("site/data/california/network_metrics.json not built yet")
    return json.loads(COMMITTED.read_text(encoding="utf-8"))


def test_committed_file_schema() -> None:
    payload = _committed()
    assert payload["schema_version"] == SCHEMA_VERSION == "bq3-v1"
    assert payload["generated_at"]
    assert payload["source"]["index_build_timestamp"]
    assert payload["ascertainment_note"].startswith("This build covers the California")
    assert set(payload["graphs"]) == {"authors", "institutions"}
    for graph in payload["graphs"].values():
        windows = graph["windows"]
        assert [w["window"] for w in windows] == WINDOW_IDS
        assert [w["partial"] for w in windows] == [False, False, False, False, True]
        for row in windows:
            assert row["isolates"] <= row["nodes"]
            assert row["components"] >= (1 if row["nodes"] else 0)
            assert row["giant_component_nodes"] <= row["nodes"]
            for key in ("giant_component_share", "density", "average_clustering", "isolate_share"):
                assert row[key] is None or 0.0 <= row[key] <= 1.0
            for key in ("cross_institution", "cross_sector", "out_of_region"):
                assert set(row[key]) == {"fraction", "edges_considered"}
                assert row[key]["fraction"] is None or 0.0 <= row[key]["fraction"] <= 1.0
            assert set(row["degree"] or {}) in (
                set(),
                {"min", "p25", "median", "p75", "p90", "max"},
            )


def test_committed_file_has_rounded_numbers_and_no_person_keys() -> None:
    payload = _committed()
    for kind, value in _walk(payload):
        if kind == "value" and isinstance(value, float):
            assert round(value, 4) == value
    keys = {v for kind, v in _walk(payload) if kind == "key"}
    assert not keys & {"author_id", "name", "author_ids", "institution_ids", "inst_id"}


# Public text (the ascertainment note and definitions) is shown on the network page. It must read in
# plain words: no field names such as current_in_ca, and no library names.
UNDERSCORE_IDENTIFIER = re.compile(r"\b[A-Za-z]+_[A-Za-z_]+\b")


def _assert_plain_public_text(texts: list[str]) -> None:
    for text in texts:
        assert not UNDERSCORE_IDENTIFIER.search(text), text
        assert "networkx" not in text.lower(), text


def test_public_text_has_no_field_names_or_library_names() -> None:
    _assert_plain_public_text([ASCERTAINMENT_NOTE, *DEFINITIONS.values()])


def test_committed_public_text_has_no_field_names_or_library_names() -> None:
    payload = _committed()
    _assert_plain_public_text([payload["ascertainment_note"], *payload["definitions"].values()])


def _load_script():
    spec = importlib.util.spec_from_file_location("build_network_metrics", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_writes_then_check_passes_and_detects_staleness(tmp_path: Path) -> None:
    module = _load_script()
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps(_index()), encoding="utf-8")
    inst_path = tmp_path / "institutions.json"
    inst_path.write_text(json.dumps({"institutions": INSTITUTIONS}), encoding="utf-8")
    meta_path = tmp_path / "build_metadata.json"
    meta_path.write_text(
        json.dumps({"generated_at": "2026-11-22T17:54:04+00:00"}), encoding="utf-8"
    )
    out = tmp_path / "network_metrics.json"
    common = [
        "--index",
        str(index_path),
        "--institutions",
        str(inst_path),
        "--metadata",
        str(meta_path),
        "--out",
        str(out),
    ]

    assert module.main(["--check", *common]) == 1  # missing file is stale
    assert module.main(common) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["source"]["index_build_timestamp"] == "2026-11-22T17:54:04+00:00"
    assert module.main(["--check", *common]) == 0

    written["graphs"]["authors"]["windows"][0]["nodes"] += 1
    out.write_text(json.dumps(written), encoding="utf-8")
    assert module.main(["--check", *common]) == 1


def test_cli_falls_back_to_index_timestamp_and_missing_institutions(tmp_path: Path) -> None:
    module = _load_script()
    index = _index()
    index["generated_at"] = "2026-02-02T00:00:00+00:00"
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps(index), encoding="utf-8")
    out = tmp_path / "network_metrics.json"
    assert (
        module.main(
            [
                "--index",
                str(index_path),
                "--institutions",
                str(tmp_path / "missing.json"),
                "--metadata",
                str(tmp_path / "missing_metadata.json"),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["source"]["index_build_timestamp"] == "2026-02-02T00:00:00+00:00"
    # Without institutions.json there are no sectors or regions, so no edge can be judged.
    institutions_all = written["graphs"]["institutions"]["windows"][0]
    assert institutions_all["cross_sector"]["edges_considered"] == 0
    assert institutions_all["out_of_region"]["edges_considered"] == 0
    assert institutions_all["nodes"] > 0


def test_reuse_null_keeps_the_committed_null_block_and_rebuilds_the_rest(tmp_path: Path) -> None:
    # Daily ingest mode (2026-11-25): the null block is copied, not recomputed.
    module = _load_script()
    index_path = tmp_path / "index.json"
    index_path.write_text(json.dumps(_index()), encoding="utf-8")
    inst_path = tmp_path / "institutions.json"
    inst_path.write_text(json.dumps({"institutions": INSTITUTIONS}), encoding="utf-8")
    meta_path = tmp_path / "build_metadata.json"
    meta_path.write_text(
        json.dumps({"generated_at": "2026-11-22T17:54:04+00:00"}), encoding="utf-8"
    )
    out = tmp_path / "network_metrics.json"
    common = ["--index", str(index_path), "--institutions", str(inst_path)]
    common += ["--metadata", str(meta_path), "--out", str(out), "--null-replicates", "3"]
    assert module.main(common) == 0
    marker = json.loads(out.read_text(encoding="utf-8"))
    marker["null_model"]["marker"] = "kept"
    out.write_text(json.dumps(marker), encoding="utf-8")
    module.build_null_block = lambda *a, **k: (_ for _ in ()).throw(AssertionError("recomputed"))
    assert module.main([*common, "--reuse-null"]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["null_model"]["marker"] == "kept"
    assert module.main(["--check", *common]) == 0
