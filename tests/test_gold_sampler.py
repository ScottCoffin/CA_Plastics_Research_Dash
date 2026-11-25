"""Tests for the BQ-G4 adaptive gold sampler (gold_sampler and bq_gold_sampler.py).

Every file is written under pytest tmp_path; nothing under data/ or curation/ is read or changed.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import random
import statistics
import sys
from pathlib import Path

import pytest

from atlas.nlp import gold_frame as gf
from atlas.nlp import gold_sampler as gs

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "bq_gold_sampler.py"


def _load_cli():
    spec = importlib.util.spec_from_file_location("bq_gold_sampler", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules.setdefault("bq_gold_sampler", module)
    spec.loader.exec_module(module)
    return module


cli = _load_cli()


# --- allocation -------------------------------------------------------------------------


def test_round0_takes_ten_or_all_per_non_empty_stratum():
    sizes = gs.round0_sizes({"a": 0, "b": 3, "c": 10, "d": 25})
    assert sizes == {"b": 3, "c": 10, "d": 10}


def test_jeffreys_prevalence_and_weight_are_positive_before_labels():
    assert gs.jeffreys_p(0, 0) == pytest.approx(0.5)
    assert gs.jeffreys_p(10, 10) == pytest.approx(10.5 / 11)
    assert gs.neyman_weight(100, 0, 0) == pytest.approx(50.0)
    # A stratum with all labels negative keeps a positive weight (Jeffreys smoothing).
    assert gs.neyman_weight(100, 0, 20) > 0


def test_round_sums_to_exact_budget_and_respects_floor():
    states = [gs.StratumState(f"s{i}", capacity=100, weight=float(i + 1)) for i in range(6)]
    alloc, unmet = gs.allocate(states, 25)
    assert sum(alloc.values()) == 25
    assert unmet == []
    assert all(v >= 1 for v in alloc.values())  # positive floor per stratum
    assert alloc["s5"] > alloc["s0"]  # heavier Neyman weight draws more


def test_floor_is_reported_when_strata_outnumber_the_budget():
    states = [gs.StratumState(f"s{i:02d}", capacity=50, weight=1.0) for i in range(30)]
    alloc, unmet = gs.allocate(states, 25)
    assert sum(alloc.values()) == 25
    assert len(unmet) == 5
    assert set(unmet).isdisjoint({k for k, v in alloc.items() if v})


def test_floor_rotates_so_every_stratum_is_reached():
    """With 32 strata and a budget of 25, a light stratum is not starved by the heavy ones."""
    drawn = {f"s{i:02d}": 0 for i in range(32)}
    weights = {name: float(10 ** (i % 4)) for i, name in enumerate(drawn)}  # widely unequal
    for _ in range(2):
        states = [
            gs.StratumState(
                name, capacity=100 - drawn[name], weight=weights[name], drawn=drawn[name]
            )
            for name in drawn
        ]
        alloc, _ = gs.allocate(states, 25)
        for name, count in alloc.items():
            drawn[name] += count
    assert min(drawn.values()) >= 1  # every stratum drawn within two rounds


def test_capacity_cap_moves_the_remainder_to_other_strata():
    states = [
        gs.StratumState("small", capacity=2, weight=1000.0),
        gs.StratumState("big", capacity=100, weight=1.0),
    ]
    alloc, _ = gs.allocate(states, 25)
    assert alloc == {"small": 2, "big": 23}


def test_spend_down_gives_priority_strata_the_budget_first():
    states = [
        gs.StratumState("p3", capacity=100, weight=1.0, priority=True),
        gs.StratumState("other", capacity=100, weight=50.0),
    ]
    alloc, _ = gs.allocate(states, 25)
    assert alloc["p3"] == 24 and alloc["other"] == 1  # other keeps its one-draw floor
    # Once the priority strata are exhausted the rest goes to every other stratum.
    states = [
        gs.StratumState("p3", capacity=3, weight=1.0, priority=True),
        gs.StratumState("other", capacity=100, weight=1.0),
    ]
    alloc, _ = gs.allocate(states, 25)
    assert alloc == {"p3": 3, "other": 22}


def test_active_goal_follows_the_order_and_owner_flags():
    goals = gs.DEFAULT_GOALS
    assert [g.id for g in goals] == ["P1", "P3", "P4", "P5", "P6", "reserve"]
    assert gs.active_goal(goals, []).id == "P1"
    assert gs.active_goal(goals, ["P1"]).id == "P3"
    assert gs.active_goal(goals, [g.id for g in goals]) is None


def test_checkpoints_report_counts_only():
    assert gs.checkpoint_status(100)["at_checkpoint"] is True
    status = gs.checkpoint_status(125)
    assert status["checkpoints_reached"] == [100]
    assert status["next_checkpoint"] == 200
    assert status["at_checkpoint"] is False
    assert gs.round_budget(340) == 10
    assert gs.round_budget(350) == 0


def test_select_round_draws_in_rand_key_order_with_ranks():
    population = {"s": ["w1", "w2", "w3", "w4"]}
    first = gs.select_round(population, {}, {"s": 2})
    assert first == [("s", 1, "w1"), ("s", 2, "w2")]
    second = gs.select_round(population, {"s": 2}, {"s": 2})
    assert second == [("s", 3, "w3"), ("s", 4, "w4")]
    with pytest.raises(ValueError):
        gs.select_round(population, {"s": 3}, {"s": 2})


# --- unbiasedness on a simulated adaptive run ------------------------------------------

SIM_N = [40, 300, 900, 2000, 60, 5]  # stratum sizes (5 is fully drawn in round 0)
SIM_P = [0.9, 0.6, 0.3, 0.05, 0.5, 0.8]  # true stratum prevalences
SIM_RUNS = 500
SIM_ROUNDS = 10  # round 0 plus 10 rounds of 25: 30 + 250 labels in total


def _simulate(*, adaptive: bool, runs: int = SIM_RUNS) -> tuple[float, float, float]:
    """(truth, mean estimate, standard error of the mean) over repeated sampling runs.

    The population labels are fixed. Each run draws fresh rand_keys, so every run is a new draw
    of the frame's sampling order. The estimator is sum_h N_h * (x_h / n_h), the stratified form
    of BQ-1.1 with weights N_h / n_h.
    """
    names = [f"s{i}" for i in range(len(SIM_N))]
    label_rng = random.Random(1)
    labels = {
        name: [1 if label_rng.random() < p else 0 for _ in range(n)]
        for name, n, p in zip(names, SIM_N, SIM_P, strict=True)
    }
    truth = float(sum(sum(v) for v in labels.values()))
    estimates = []
    for run in range(runs):
        rng = random.Random(10_000 + run)
        order = {
            n: sorted(range(k), key=lambda _: rng.random())
            for n, k in zip(names, SIM_N, strict=True)
        }
        drawn = dict.fromkeys(names, 0)
        positives = dict.fromkeys(names, 0)

        def take(alloc: dict[str, int]) -> None:
            for name, count in alloc.items():
                for _ in range(count):
                    idx = order[name][drawn[name]]
                    positives[name] += labels[name][idx]
                    drawn[name] += 1

        alloc = gs.round0_sizes(dict(zip(names, SIM_N, strict=True)))
        take(alloc)
        total = sum(alloc.values())
        for _ in range(SIM_ROUNDS):
            budget = gs.round_budget(total)
            states = [
                gs.StratumState(
                    name,
                    capacity=SIM_N[k] - drawn[name],
                    drawn=drawn[name],
                    weight=(
                        gs.neyman_weight(SIM_N[k], positives[name], drawn[name])
                        if adaptive
                        else float(SIM_N[k])
                    ),
                )
                for k, name in enumerate(names)
            ]
            round_alloc, _ = gs.allocate(states, budget)
            assert sum(round_alloc.values()) == budget
            take(round_alloc)
            total += budget
        estimates.append(sum(SIM_N[k] * positives[n] / drawn[n] for k, n in enumerate(names)))
    mean = statistics.fmean(estimates)
    return truth, mean, statistics.stdev(estimates) / math.sqrt(runs)


def test_unbiased_when_allocation_ignores_labels():
    truth, mean, se = _simulate(adaptive=False)
    assert abs(mean - truth) < 3 * se  # the stratified estimator with a fixed design is unbiased


def test_adaptive_run_bias_is_small_and_reported():
    truth, mean, se = _simulate(adaptive=True)
    relative_bias = (mean - truth) / truth
    print(f"adaptive run: truth={truth:.0f} mean={mean:.2f} bias={relative_bias:+.2%} se={se:.2f}")
    # Label-dependent allocation adds a small bias (about -0.9% on this frame). Bound it.
    assert abs(relative_bias) < 0.02


# --- sampler CLI on a synthetic frame --------------------------------------------------

STRATA = (("registry_region", "pollution-core", "low"), ("global_english", "other", "high"))


def _write_fixture(tmp: Path, *, sizes=(30, 40), guide_id: str | None = None) -> dict[str, Path]:
    frame = tmp / "frame.csv"
    rows = []
    counter = 0
    for (block, theme, band), size in zip(STRATA, sizes, strict=True):
        stratum = f"{block}|{theme}|{band}"
        for i in range(size):
            counter += 1
            work_id = f"W{counter:04d}"
            rows.append(
                {
                    "work_id": work_id,
                    "doi": "",
                    "block": block,
                    "theme_group": theme,
                    "score": "0.2500",
                    "band": band,
                    "stratum": stratum,
                    "rand_key": f"{(counter * 0.6180339887) % 1:.16f}",
                }
            )
    with frame.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(gf.FRAME_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    manifest = tmp / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "seed": 42043,
                "model_version": "rules-v3.1-proxy",
                "frame_sha256": gf.sha256_file(frame),
                "strata": [
                    {"stratum": f"{b}|{t}|{d}", "N_h": size}
                    for (b, t, d), size in zip(STRATA, sizes, strict=True)
                ],
            }
        ),
        encoding="utf-8",
    )
    guides = tmp / "guides.csv"
    with guides.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["example_id", "work_id", "doi", "role"])
        writer.writerow(["guide", guide_id or "", "", "guide_example"])
    return {
        "frame": frame,
        "manifest": manifest,
        "ledger": tmp / "draws.csv",
        "sheet": tmp / "annotations_global_SC.csv",
        "guides": guides,
        "goals": tmp / "goals.json",
    }


def _argv(command: str, paths: dict[str, Path]) -> list[str]:
    out = [command]
    for key in ("frame", "manifest", "ledger", "sheet", "guides", "goals"):
        out += [f"--{key}", str(paths[key])]
    return out


def _label_all_drawn(paths: dict[str, Path]) -> None:
    from atlas import gold_label_review as gl

    draws = gl.read_rows(paths["sheet"])
    index = gl.global_split_index(draws)
    for row in draws:
        gl.save_decision(
            paths["sheet"],
            row["work_id"],
            {"plastic_related": "false"},
            "complete",
            index,
            guide_version=gl.GLOBAL_GUIDE_VERSION,
        )


def test_round0_then_next_round_writes_an_append_only_ledger(tmp_path):
    paths = _write_fixture(tmp_path)
    assert cli.main(_argv("round0", paths)) == 0
    first = paths["ledger"].read_bytes()
    assert first.count(b"\n") == 1 + 10 + 10  # header plus min(10, N) per stratum
    assert cli.main(_argv("next-round", paths)) == 2  # refused: labels are missing
    _label_all_drawn(paths)
    assert cli.main(_argv("next-round", paths)) == 0
    second = paths["ledger"].read_bytes()
    assert second.startswith(first)  # earlier rows are untouched
    assert second.count(b"\n") == first.count(b"\n") + 25
    assert cli.main(_argv("round0", paths)) == 2  # round 0 is never drawn twice


def test_round0_is_deterministic_for_the_frame(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    a = _write_fixture(tmp_path / "a")
    b = _write_fixture(tmp_path / "b")
    assert cli.main(_argv("round0", a)) == 0
    assert cli.main(_argv("round0", b)) == 0
    assert a["ledger"].read_bytes() == b["ledger"].read_bytes()


def test_guide_examples_are_never_drawn(tmp_path):
    paths = _write_fixture(tmp_path, guide_id="W0003")
    assert cli.main(_argv("round0", paths)) == 0
    drawn = {row["work_id"] for row in cli.read_draws(paths["ledger"])}
    assert "W0003" not in drawn


def test_frame_checksum_mismatch_refuses_to_draw(tmp_path):
    paths = _write_fixture(tmp_path)
    paths["frame"].write_text(paths["frame"].read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert cli.main(_argv("round0", paths)) == 2
    assert not paths["ledger"].exists()


def test_status_prints_counts_only(tmp_path, capsys):
    paths = _write_fixture(tmp_path)
    cli.main(_argv("round0", paths))
    capsys.readouterr()
    assert cli.main(_argv("status", paths)) == 0
    out = capsys.readouterr().out
    assert "checkpoints reached" in out
    assert "interval" not in out.lower()
    assert "ci " not in out.lower()
