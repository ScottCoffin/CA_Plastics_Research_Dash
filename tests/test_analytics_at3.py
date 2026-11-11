"""AT-3 institution analytics tests on a hand-checked 10-work fixture (no binary fixtures)."""

from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import duckdb
import pytest

from atlas.analytics.sql import build_analytics, write_fixture

B = 200
SEED = 20261111


def _rows(path: Path, sql: str) -> list[tuple]:
    con = duckdb.connect()
    try:
        return con.execute(sql.replace("{p}", f"'{path.as_posix()}'")).fetchall()
    finally:
        con.close()


@pytest.fixture(scope="module")
def fixture_paths(tmp_path_factory) -> dict[str, Path]:
    return write_fixture(tmp_path_factory.mktemp("at3_fixture") / "in")


@pytest.fixture(scope="module")
def built(fixture_paths, tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("at3_out") / "analytics"
    build_analytics(
        works_path=fixture_paths["works"],
        authorships_path=fixture_paths["authorships"],
        institutions_path=fixture_paths["institutions"],
        scope_path=fixture_paths["scope"],
        output_dir=out,
        bootstrap_replicates=B,
        seed=SEED,
        generated_at="2026-11-11T00:00:00+00:00",
    )
    return out


def _weights(out: Path) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for work_id, inst_id, w in _rows(
        out / "work_inst_weights.parquet", "SELECT work_id, inst_id, w FROM read_parquet({p})"
    ):
        result.setdefault(work_id, {})[inst_id] = w
    return result


def _counts(out: Path) -> dict[str, tuple]:
    rows = _rows(
        out / "inst_counts.parquet",
        "SELECT inst_id, works_full, works_frac, rank_full, rank_frac, ca_flag, name "
        "FROM read_parquet({p})",
    )
    return {row[0]: row[1:] for row in rows}


def test_weights_sum_to_one_per_work(built):
    weights = _weights(built)
    assert len(weights) == 8
    for work_id, by_inst in weights.items():
        assert sum(by_inst.values()) == pytest.approx(1.0, abs=1e-9), work_id


def test_leiden_example_w1(built):
    # W1: five authors, a1 and a2 at I_A only; a3-a5 with no institution.
    # Each author is 1/5; I_A = 2 * 1/5 = 0.4, unaffiliated = 3 * 1/5 = 0.6.
    w1 = _weights(built)["W1"]
    assert w1["I_A"] == pytest.approx(0.4)
    assert w1["unaffiliated"] == pytest.approx(0.6)


def test_multi_affiliated_author_w2(built):
    # W2: b1 has {I_A, I_B} -> 1/2 * 1/2 = 0.25 each; b2 has {I_B} -> 1/2.
    # I_A = 0.25, I_B = 0.25 + 0.5 = 0.75.
    w2 = _weights(built)["W2"]
    assert w2["I_A"] == pytest.approx(0.25)
    assert w2["I_B"] == pytest.approx(0.75)


def test_retracted_work_excluded(built):
    assert "W3" not in _weights(built)
    manifest = json.loads((built / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["exclusions"]["retracted"] == 1


def test_plastic_filter_respected(fixture_paths, tmp_path):
    kwargs = dict(
        works_path=fixture_paths["works"],
        authorships_path=fixture_paths["authorships"],
        institutions_path=fixture_paths["institutions"],
        scope_path=fixture_paths["scope"],
        bootstrap_replicates=B,
        seed=SEED,
    )
    default = build_analytics(output_dir=tmp_path / "pl", plastic_only=True, **kwargs)
    assert "W4" not in _weights(default.output_dir)
    assert default.manifest["exclusions"]["not_plastic_related"] == 1

    everything = build_analytics(output_dir=tmp_path / "all", plastic_only=False, **kwargs)
    weights = _weights(everything.output_dir)
    assert weights["W4"] == {"I_C": pytest.approx(1.0)}
    assert everything.manifest["n_works"] == 9
    assert everything.manifest["exclusions"]["not_plastic_related"] == 0


def test_work_without_authorships_is_unaffiliated(built):
    # W5 has no authorship rows: one synthetic anonymous author, unaffiliated, weight 1.0.
    assert _weights(built)["W5"] == {"unaffiliated": pytest.approx(1.0)}


def test_empty_author_ids_are_not_merged(built):
    # W6: two anonymous authors at I_B and one named author z1 at I_C.
    # Three authors of 1/3 each: I_B = 2/3, I_C = 1/3. Merging the two blanks would give 1/2.
    w6 = _weights(built)["W6"]
    assert w6["I_B"] == pytest.approx(2 / 3)
    assert w6["I_C"] == pytest.approx(1 / 3)


def test_non_ca_institution_counted_not_ranked(built):
    counts = _counts(built)
    # I_X appears only in W7 (weight 0.5): counted, but ca_flag false and no rank.
    works_full, works_frac, rank_full, rank_frac, ca_flag, _ = counts["I_X"]
    assert (works_full, works_frac) == (1, pytest.approx(0.5))
    assert ca_flag is False
    assert rank_full is None and rank_frac is None
    assert counts["unaffiliated"][3] is None


def test_expected_counts_by_hand(built):
    counts = _counts(built)
    # I_A: W1 2/5, W2 1/4, W7 1/2, W8 1/3, W9 1/2 -> 119/60; works W1, W2, W7, W8, W9 = 5.
    # I_B: W2 3/4, W6 2/3, W8 2/3, W10 3/8 -> 59/24; works W2, W6, W8, W10 = 4.
    # I_C: W6 1/3, W9 1/2, W10 3/8 -> 29/24; works W6, W9, W10 = 3.
    # unaffiliated: W1 3/5, W5 1, W10 1/4 -> 37/20; works W1, W5, W10 = 3.
    expected = {
        "I_A": (5, Fraction(119, 60)),
        "I_B": (4, Fraction(59, 24)),
        "I_C": (3, Fraction(29, 24)),
        "unaffiliated": (3, Fraction(37, 20)),
    }
    for inst_id, (full, frac) in expected.items():
        assert counts[inst_id][0] == full, inst_id
        assert counts[inst_id][1] == pytest.approx(float(frac)), inst_id
    # _counts tuple: (works_full, works_frac, rank_full, rank_frac, ca_flag, name).
    # Frac ranks: B (2.46) > A (1.98) > C (1.21). Full ranks: A (5) > B (4) > C (3).
    assert (counts["I_B"][3], counts["I_A"][3], counts["I_C"][3]) == (1, 2, 3)
    assert (counts["I_A"][2], counts["I_B"][2], counts["I_C"][2]) == (1, 2, 3)


def test_rank_intervals_contain_point_rank(built):
    rows = _rows(
        built / "inst_stability.parquet",
        "SELECT inst_id, works_frac, frac_lo, frac_hi, rank_frac, rank_lo, rank_hi "
        "FROM read_parquet({p})",
    )
    assert len(rows) == 3
    for inst_id, frac, frac_lo, frac_hi, rank, rank_lo, rank_hi in rows:
        assert rank_lo <= rank <= rank_hi, inst_id
        assert frac_lo <= frac <= frac_hi, inst_id


def test_same_seed_gives_identical_stability(fixture_paths, tmp_path):
    kwargs = dict(
        works_path=fixture_paths["works"],
        authorships_path=fixture_paths["authorships"],
        institutions_path=fixture_paths["institutions"],
        scope_path=fixture_paths["scope"],
        bootstrap_replicates=B,
    )
    first = build_analytics(output_dir=tmp_path / "a", seed=SEED, **kwargs)
    second = build_analytics(output_dir=tmp_path / "b", seed=SEED, **kwargs)
    query = "SELECT * FROM read_parquet({p}) ORDER BY inst_id"
    assert _rows(first.output_dir / "inst_stability.parquet", query) == _rows(
        second.output_dir / "inst_stability.parquet", query
    )


def test_year_tag_counts(built):
    rows = _rows(built / "year_tag.parquet", "SELECT year, tag, works FROM read_parquet({p})")
    got = {(year, tag): works for year, tag, works in rows}
    # Scope: 8 in-scope works (W3 retracted and W4 non-plastic excluded).
    assert got[(2019, "_all")] == 1 and got[(2019, "water")] == 1 and got[(2019, "health")] == 1
    assert got[(2020, "_all")] == 2 and got[(2020, "water")] == 1  # W1 and W7 (no tags)
    assert (2020, "health") not in got
    assert got[(2021, "_all")] == 2  # W5 and W6 (W3 excluded)
    assert got[(2021, "health")] == 1 and got[(2021, "water")] == 1
    assert got[(2022, "_all")] == 1 and got[(2022, "health")] == 1  # W8 only (W4 excluded)
    assert got[(2023, "water")] == 1 and got[(2023, "health")] == 1
    assert got[(2024, "_all")] == 1
    assert sum(w for (y, t), w in got.items() if t == "_all") == 8


def test_tag_and_topic_cooccurrence(built):
    tags = _rows(
        built / "tag_cooccurrence.parquet", "SELECT tag_a, tag_b, works FROM read_parquet({p})"
    )
    # W2 and W9 both carry water and health.
    assert tags == [("health", "water", 2)]
    topics = _rows(
        built / "topic_cooccurrence.parquet",
        "SELECT topic_a, topic_b, works FROM read_parquet({p}) ORDER BY 1, 2",
    )
    # (T1,T2): W1, W2, W10 = 3; (T1,T3): W2, W9 = 2; (T2,T3): W2, W6 = 2.
    assert topics == [("T1", "T2", 3), ("T1", "T3", 2), ("T2", "T3", 2)]


def test_topic_min_pair_threshold(fixture_paths, tmp_path):
    result = build_analytics(
        works_path=fixture_paths["works"],
        authorships_path=fixture_paths["authorships"],
        institutions_path=fixture_paths["institutions"],
        scope_path=fixture_paths["scope"],
        output_dir=tmp_path / "t3",
        bootstrap_replicates=B,
        topic_min_pair=3,
    )
    topics = _rows(
        result.output_dir / "topic_cooccurrence.parquet",
        "SELECT topic_a, topic_b, works FROM read_parquet({p})",
    )
    assert topics == [("T1", "T2", 3)]


def test_inst_cooccurrence_ca_only(built):
    pairs = _rows(
        built / "inst_cooccurrence.parquet",
        "SELECT inst_a, inst_b, works FROM read_parquet({p}) ORDER BY 1, 2",
    )
    # I_A-I_B: W2, W8. I_A-I_C: W9. I_B-I_C: W6, W10. I_X (non-CA) never pairs.
    assert pairs == [("I_A", "I_B", 2), ("I_A", "I_C", 1), ("I_B", "I_C", 2)]


def test_manifest_exclusions_and_fields(built):
    manifest = json.loads((built / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["exclusions"] == {
        "total_works_in_table": 10,
        "retracted": 1,
        "not_in_scope": 0,
        "not_plastic_related": 1,
    }
    assert manifest["n_works"] == 8
    assert manifest["bootstrap_replicates"] == B
    assert manifest["seed"] == SEED
    assert manifest["plastic_only"] is True
    assert manifest["generated_at"] == "2026-11-11T00:00:00+00:00"
    assert manifest["rows"]["inst_counts"] == 5
    assert manifest["rows"]["inst_stability"] == 3
    assert manifest["duckdb_version"]


def test_is_retracted_absent_is_treated_as_false(fixture_paths, tmp_path):
    paths = write_fixture(tmp_path / "old", include_retracted=False)
    result = build_analytics(
        works_path=paths["works"],
        authorships_path=paths["authorships"],
        institutions_path=paths["institutions"],
        scope_path=paths["scope"],
        output_dir=tmp_path / "out",
        bootstrap_replicates=B,
    )
    assert result.manifest["exclusions"]["retracted"] == 0
    assert result.manifest["n_works"] == 9


def test_failed_build_leaves_no_output(fixture_paths, tmp_path):
    out = tmp_path / "analytics"
    with pytest.raises(ValueError):
        build_analytics(
            works_path=fixture_paths["works"],
            authorships_path=fixture_paths["authorships"],
            institutions_path=fixture_paths["institutions"],
            scope_path=fixture_paths["scope"],
            output_dir=out,
            bootstrap_replicates=0,
        )
    assert not out.exists()
    assert not any(p.name.startswith("analytics.tmp-") for p in tmp_path.iterdir())
