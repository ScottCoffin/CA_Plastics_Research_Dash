"""Tests for the AT-4 serving bundle builder and the facets.js bit-set engine (offline)."""

from __future__ import annotations

import json
import math
import random
import shutil
import struct
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.build.bundle import assign_tiers, build_bundle, run_node_cases

N_WORKS = 80
CA_INST = {
    "I1": ("UC", "University of Test"),
    "I2": ("state-agency", "State Test Agency"),
    "I3": ("company", "Test Co"),
}
NON_CA_INST = "I9"
PHRASES = [
    "Microplastics in fish",
    "River survey of microplastics",
    "Plastic recycling policy",
    "Air fibres indoors",
    "Marine debris economics",
    "Landfill leachate study",
]


def _works() -> list[dict]:
    rng = random.Random(7)
    works = []
    for i in range(N_WORKS):
        tags = [
            t for t, k in (("marine", i % 2), ("health", i % 3 == 0), ("policy", i % 5 == 0)) if k
        ]
        inst = [f"I{1 + (i + k) % 3}" for k in range(i % 3)]
        if i % 4 == 0:
            inst.append(NON_CA_INST)
        works.append(
            {
                "work_id": f"W{i:05d}",
                "title": f"{PHRASES[i % len(PHRASES)]} study {i}",
                "year": None if i % 11 == 0 else 2015 + i % 8,
                "type": ["article", "review", "preprint"][i % 3],
                "domain_tags": tags,
                "plastic_related": [True, False, None][i % 3],
                "ca_led": i % 2 == 0,
                "institution_ids": sorted(set(inst)),
                "cited_by_count": int(rng.randint(0, 50)),
                "author_ids": [],
                "needs_review": False,
            }
        )
    return works


def _write_index(path: Path, works: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": "test", "works": works}), encoding="utf-8")
    return path


def _write_normalized(directory: Path, works: list[dict]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "work_id": w["work_id"],
            "doi": f"10.1/{w['work_id']}",
            "journal": "J Test" if i % 2 else None,
            "is_oa": (i % 3 != 0) if i % 7 else None,
            "oa_status": "gold",
            "abstract": "SECRET ABSTRACT TEXT",
        }
        for i, w in enumerate(works)
        if i != 5  # one published work without a normalized row
    ]
    pq.write_table(pa.Table.from_pylist(rows), directory / "works.parquet")
    insts = [
        {"inst_id": k, "name": name, "atlas_type": kind, "ca_flag": True}
        for k, (kind, name) in CA_INST.items()
    ]
    insts.append(
        {"inst_id": NON_CA_INST, "name": "Elsewhere", "atlas_type": "university", "ca_flag": False}
    )
    pq.write_table(pa.Table.from_pylist(insts), directory / "institutions.parquet")
    return directory


def _write_analytics(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    counts = [
        {
            "inst_id": k,
            "name": name,
            "atlas_type": kind,
            "parent_system": None,
            "ca_flag": True,
            "works_full": 10 - i,
            "works_frac": 5.0 - i,
            "rank_full": i + 1,
            "rank_frac": i + 1,
        }
        for i, (k, (kind, name)) in enumerate(CA_INST.items())
    ]
    stab = [
        {
            "inst_id": k,
            "works_frac": 5.0 - i,
            "frac_lo": 3.0 - i,
            "frac_hi": 6.0 - i,
            "rank_frac": i + 1,
            "rank_lo": 1,
            "rank_hi": 2,
            "widened": False,
            "not_distinguishable": True,
        }
        for i, k in enumerate(CA_INST)
    ]
    year_tag = [
        {"year": 2019, "tag": "marine", "works": 3},
        {"year": None, "tag": "health", "works": 1},
    ]
    pq.write_table(pa.Table.from_pylist(counts), directory / "inst_counts.parquet")
    pq.write_table(pa.Table.from_pylist(stab), directory / "inst_stability.parquet")
    pq.write_table(pa.Table.from_pylist(year_tag), directory / "year_tag.parquet")
    return directory


@pytest.fixture()
def built(tmp_path: Path):
    works = _works()
    index = _write_index(tmp_path / "src" / "index.json", works)
    normalized = _write_normalized(tmp_path / "src" / "normalized", works)
    analytics = _write_analytics(tmp_path / "src" / "analytics")
    out = tmp_path / "bundle"
    manifest = build_bundle(
        index,
        out,
        normalized_dir=normalized,
        analytics_dir=analytics,
        generated_at="2026-11-11T00:00:00+00:00",
    )
    return {
        "works": works,
        "out": out,
        "manifest": manifest,
        "index": index,
        "normalized": normalized,
        "analytics": analytics,
    }


def _labels(work: dict, oa_flag) -> dict[str, set[str]]:
    year = work["year"]
    plastic = work["plastic_related"]
    ca_ids = {i for i in work["institution_ids"] if i in CA_INST}
    return {
        "year": {"unknown" if year is None else str(year)},
        "type": {work["type"]},
        "topic": set(work["domain_tags"]),
        "plastic": {"unlabelled" if plastic is None else ("yes" if plastic else "no")},
        "ca_led": {"yes" if work["ca_led"] else "no"},
        "institution": ca_ids,
        "sector": {CA_INST[i][0] for i in ca_ids},
        "oa": {"unknown" if oa_flag is None else ("open" if oa_flag else "closed")},
    }


def _oa_flags(works: list[dict]) -> dict[str, bool | None]:
    flags = {}
    for i, w in enumerate(works):
        if i == 5:
            continue
        flags[w["work_id"]] = (i % 3 != 0) if i % 7 else None
    return flags


def _reference(works: list[dict], oa: dict, facets: dict, sel: dict, tokens: list[str] | None):
    labels = {w["work_id"]: _labels(w, oa.get(w["work_id"])) for w in works}
    titles = {w["work_id"]: w["title"].lower() for w in works}

    def ok(wid: str, skip: str | None) -> bool:
        for facet, chosen in sel.items():
            if facet == skip or not chosen:
                continue
            if not any(c in labels[wid][facet] for c in chosen):
                return False
        return all(t in titles[wid] for t in tokens or [])

    selected = [w["work_id"] for w in works if ok(w["work_id"], None)]
    counts = {}
    for facet, entries in facets.items():
        for e in entries:
            counts[f"{facet}|{e['label']}"] = 0
    for facet in facets:
        for wid in (w["work_id"] for w in works if ok(w["work_id"], facet)):
            for lab in labels[wid][facet]:
                counts[f"{facet}|{lab}"] += 1
    return {"total": len(selected), "counts": counts, "ids": selected}


def _node_or_skip() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not on PATH; the facets.js round trip needs Node.js 20 or newer")
    return node


def test_bit_layout_header_and_word_count(built) -> None:
    out, works = built["out"], built["works"]
    raw = (out / "facets.bin").read_bytes()
    magic, version, n, nsets = struct.unpack_from("<4sIII", raw, 0)
    facets = json.loads((out / "facets.json").read_text(encoding="utf-8"))
    assert magic == b"BMF1"
    assert version == 1
    assert n == N_WORKS == len(works)
    assert nsets == sum(len(v) for v in facets.values())
    words = math.ceil(N_WORKS / 32)
    assert words == 3  # 80 works span more than two words
    assert len(raw) == 16 + nsets * words * 4
    # Bit i of a set is bit (i & 31) of word (i >> 5), little-endian.
    year_2019 = next(e for e in facets["year"] if e["label"] == "2019")
    body = np.frombuffer(raw, dtype="<u4", offset=16).reshape(nsets, words)
    expected = [i for i, w in enumerate(works) if w["year"] == 2019]
    got = [i for i in range(N_WORKS) if (int(body[year_2019["id"], i >> 5]) >> (i & 31)) & 1]
    assert got == expected and expected


def test_facet_counts_match_python_reference(built) -> None:
    facets = json.loads((built["out"] / "facets.json").read_text(encoding="utf-8"))
    works, oa = built["works"], _oa_flags(built["works"])
    for facet in ("year", "type", "topic", "plastic", "ca_led", "institution", "sector", "oa"):
        assert facet in facets
    ref = _reference(works, oa, facets, {}, None)
    for facet, entries in facets.items():
        for e in entries:
            assert e["count"] == ref["counts"][f"{facet}|{e['label']}"], (facet, e["label"])
    assert facets["oa"] and {e["label"] for e in facets["oa"]} <= {"open", "closed", "unknown"}
    inst = facets["institution"]
    assert {e["label"] for e in inst} <= set(CA_INST)
    assert all(e["name"] == CA_INST[e["label"]][1] for e in inst)
    assert NON_CA_INST not in {e["label"] for e in inst}


def test_node_round_trip_counts_and_search(built) -> None:
    node = _node_or_skip()
    facets = json.loads((built["out"] / "facets.json").read_text(encoding="utf-8"))
    works, oa = built["works"], _oa_flags(built["works"])
    cases = [
        {"sel": {}, "query": None},
        {"sel": {"year": ["2019", "2020"]}, "query": None},
        {"sel": {"topic": ["marine"], "plastic": ["yes"]}, "query": "microplastics"},
        {"sel": {"institution": ["I1"], "year": ["2016"]}, "query": "  STUDY 12  "},
        {"sel": {"type": ["review"]}, "query": "river microplastics"},
        {"sel": {"oa": ["unknown"], "sector": ["company"]}, "query": ""},
    ]
    got = run_node_cases(built["out"], cases, node)
    assert len(got) == len(cases)
    for case, res in zip(cases, got):
        tokens = None if case["query"] is None else case["query"].lower().split()
        ref = _reference(works, oa, facets, case["sel"], tokens)
        assert res["total"] == ref["total"], case
        assert res["counts"] == ref["counts"], case
        assert res["ids"] == ref["ids"], case


def test_search_requires_every_token(built) -> None:
    node = _node_or_skip()
    cases = [{"sel": {}, "query": "microplastics fish"}, {"sel": {}, "query": "fish"}]
    got = run_node_cases(built["out"], cases, node)
    titles = {w["work_id"]: w["title"].lower() for w in built["works"]}
    both = [wid for wid, t in titles.items() if "microplastics" in t and "fish" in t]
    assert got[0]["ids"] == both and both
    assert got[1]["total"] == sum(1 for t in titles.values() if "fish" in t)


def test_tier_algorithm_on_hand_made_table() -> None:
    rows = [
        {"inst_id": "B", "rank_frac": 2, "rank_lo": 1, "rank_hi": 3},
        {"inst_id": "A", "rank_frac": 1, "rank_lo": 1, "rank_hi": 3},
        {"inst_id": "C", "rank_frac": 3, "rank_lo": 4, "rank_hi": 5},
        {"inst_id": "E", "rank_frac": 5, "rank_lo": 7, "rank_hi": 8},
        {"inst_id": "D", "rank_frac": 4, "rank_lo": 2, "rank_hi": 6},
        {"inst_id": "Z", "rank_frac": 4, "rank_lo": 3, "rank_hi": 4},
    ]
    tiers = {r["inst_id"]: r["tier"] for r in assign_tiers(rows)}
    # A leads tier 1 (hi 3); B joins (lo 1); C lo 4 > 3 starts tier 2 (hi 5);
    # D (rank 4, inst_id D) lo 2 <= 5 joins; Z (rank 4) lo 3 <= 5 joins; E lo 7 > 5 starts tier 3.
    assert tiers == {"A": 1, "B": 1, "C": 2, "D": 2, "Z": 2, "E": 3}
    ordered = [r["inst_id"] for r in assign_tiers(rows)]
    assert ordered == ["A", "B", "C", "D", "Z", "E"]


def test_no_abstract_column_in_parquet_and_all_files_read(built) -> None:
    parquet_files = sorted((built["out"] / "parquet").glob("*.parquet"))
    assert {p.name for p in parquet_files} >= {
        "works.parquet",
        "inst_counts.parquet",
        "inst_tiers.parquet",
        "year_tag.parquet",
    }
    for path in parquet_files:
        names = pq.ParquetFile(path).schema_arrow.names
        assert not [c for c in names if "abstract" in c.lower()], path.name
        pq.read_table(path)


def test_build_without_analytics_or_normalized(tmp_path: Path) -> None:
    works = _works()
    index = _write_index(tmp_path / "index.json", works)
    out = tmp_path / "bundle"
    manifest = build_bundle(index, out, normalized_dir=None, analytics_dir=None, generated_at="t")
    assert not (out / "inst_tiers.json").exists()
    assert not (out / "parquet" / "inst_tiers.parquet").exists()
    assert not (out / "parquet" / "inst_counts.parquet").exists()
    assert not (out / "parquet" / "year_tag.parquet").exists()
    assert (out / "parquet" / "works.parquet").exists()
    assert manifest["inputs"]["analytics_parquet_copied"] is False
    assert {s["input"] for s in manifest["inputs"]["skipped"]} >= {"normalized", "analytics"}
    facets = json.loads((out / "facets.json").read_text(encoding="utf-8"))
    assert facets["institution"] == [] and facets["sector"] == []
    assert {e["label"] for e in facets["oa"]} == {"unknown"}
    rows = pq.read_table(out / "parquet" / "works.parquet").to_pylist()
    assert all(r["doi"] is None and r["is_oa"] is None for r in rows)
    assert len(rows) == N_WORKS


def test_build_is_deterministic_apart_from_generated_at(tmp_path: Path) -> None:
    works = _works()
    index = _write_index(tmp_path / "src" / "index.json", works)
    normalized = _write_normalized(tmp_path / "src" / "normalized", works)
    analytics = _write_analytics(tmp_path / "src" / "analytics")
    first = tmp_path / "first"
    second = tmp_path / "second"
    build_bundle(
        index,
        first,
        normalized_dir=normalized,
        analytics_dir=analytics,
        generated_at="2026-01-01T00:00:00+00:00",
    )
    build_bundle(
        index,
        second,
        normalized_dir=normalized,
        analytics_dir=analytics,
        generated_at="2026-06-01T00:00:00+00:00",
    )
    files_a = sorted(p.relative_to(first).as_posix() for p in first.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(second).as_posix() for p in second.rglob("*") if p.is_file())
    assert files_a == files_b
    for rel in files_a:
        a, b = (first / rel).read_bytes(), (second / rel).read_bytes()
        if rel == "manifest.json":
            ma, mb = json.loads(a), json.loads(b)
            assert ma.pop("generated_at") != mb.pop("generated_at")
            assert ma == mb
        elif rel == "inst_tiers.json":
            ta, tb = json.loads(a), json.loads(b)
            ta.pop("generated_at"), tb.pop("generated_at")
            assert ta == tb
        else:
            assert a == b, rel
    assert not list(tmp_path.glob(".*staging*"))  # no staging leftovers


def test_rebuild_replaces_existing_bundle(tmp_path: Path) -> None:
    works = _works()
    index = _write_index(tmp_path / "index.json", works)
    out = tmp_path / "bundle"
    build_bundle(index, out, generated_at="t1")
    (out / "stale.txt").write_text("old", encoding="utf-8")
    build_bundle(index, out, generated_at="t2")
    assert not (out / "stale.txt").exists()
    assert not (tmp_path / "bundle.previous").exists()
