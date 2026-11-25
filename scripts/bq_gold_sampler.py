"""Adaptive gold sampler for the A3 global block (BQ-G4).

Run from the repository root (Git Bash, Windows):

    py -3.14 scripts/bq_gold_sampler.py round0        # first draw: min(10, N_h) per stratum
    py -3.14 scripts/bq_gold_sampler.py next-round    # next 25 draws (Jeffreys-Neyman allocation)
    py -3.14 scripts/bq_gold_sampler.py status        # counts, checkpoints, spend-down

Inputs: the frozen frame ``curation/gold_global_frame_v1.csv.gz`` (checked against the sha256 in its
manifest on every run) and the manifest ``curation/gold_global_frame_v1.json``. The draw ledger
``curation/gold_global_draws_v1.csv`` is append-only: a run only adds rows for a new round. The
labelling sheet ``curation/annotations/annotations_global_SC.csv`` is read for label counts and
appended to when works are drawn. Nothing is written to a public output, and no interval is
computed here (the precision estimator is BQ-1.1).

Optional goals file (``--goals``): JSON ``{"met": ["P1"]}`` lists the goals the owner has marked
met. Without it no goal is met, so the spend-down order is P1, P3, P4, P5, P6, reserve.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas import gold_label_review as gl  # noqa: E402
from atlas.nlp import gold_frame as gf  # noqa: E402
from atlas.nlp import gold_sampler as gs  # noqa: E402

DEFAULT_FRAME = ROOT / "curation" / "gold_global_frame_v1.csv.gz"
DEFAULT_MANIFEST = ROOT / "curation" / "gold_global_frame_v1.json"
DEFAULT_LEDGER = ROOT / "curation" / "gold_global_draws_v1.csv"
DEFAULT_SHEET = ROOT / "curation" / "annotations" / gl.GLOBAL_SHEET_NAME
DEFAULT_GUIDES = ROOT / "curation" / "a3_guide_examples.csv"
DEFAULT_GOALS = ROOT / "curation" / "gold_sampler_goals_v1.json"
LEDGER_FIELDS = (
    "round",
    "stratum",
    "work_id",
    "rank_in_stratum",
    "n_h_after_round",
    "N_h",
    "N_h_full",
    "incl_prob_within_stratum",
    "seed",
    "model_version",
    "frame_sha256",
)


class SamplerError(RuntimeError):
    """A refusal: the run stops and writes nothing."""


def read_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_frame(path: Path, manifest: Mapping[str, Any]) -> list[dict[str, str]]:
    if gf.sha256_file(path) != manifest["frame_sha256"]:
        raise SamplerError("frame sha256 does not match the manifest; refusing to draw")
    # ADR-GOLD-GLOBAL-SAMPLER: the frame is stored gzipped (every query hit, zero-score ones too).
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_guides(path: Path) -> tuple[set[str], set[str]]:
    """Guide-example work ids and DOIs (A3 section 4.3 item 8): never drawn."""
    if not path.exists():
        return set(), set()
    with path.open(encoding="utf-8", newline="") as handle:
        guides = [row for row in csv.DictReader(handle) if row.get("role") == "guide_example"]
    return gf.guide_example_ids(guides)


def build_population(
    frame: Sequence[Mapping[str, str]],
    excluded: tuple[set[str], set[str]],
) -> tuple[dict[str, list[str]], dict[str, dict[str, str]]]:
    """stratum -> work ids in rand_key order, and stratum -> its field values."""
    ids_ex, dois_ex = excluded
    members: dict[str, list[tuple[float, str]]] = defaultdict(list)
    fields: dict[str, dict[str, str]] = {}
    for row in frame:
        work_id = row["work_id"]
        if gf.is_guide_example(work_id, row.get("doi"), ids_ex, dois_ex):
            continue
        stratum = row["stratum"]
        members[stratum].append((float(row["rand_key"]), work_id))
        fields[stratum] = {f: row[f] for f in gs.FIELDS}
    population = {s: [w for _, w in sorted(items)] for s, items in members.items()}
    return population, fields


def read_draws(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != LEDGER_FIELDS:
            raise SamplerError(f"{path}: ledger header mismatch")
        return list(reader)


def append_draws(path: Path, rows: Sequence[Mapping[str, str]]) -> None:
    """Append rows. An existing file is only ever opened in append mode."""
    if not rows:
        return
    new_file = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        if new_file:
            writer.writeheader()
        writer.writerows(rows)


def read_labels(sheet: Path) -> dict[str, dict[str, str]]:
    if not sheet.exists():
        return {}
    return {row["work_id"]: row for row in gl.read_rows(sheet)}


def label_counts(
    draws: Sequence[Mapping[str, str]], labels: Mapping[str, Mapping[str, str]]
) -> tuple[dict[str, tuple[int, int]], int]:
    """stratum -> (positives, labelled) from complete labels; and the number of unlabelled draws.

    Only the owner's completed labels count. Adjudication holds are drawn but not labelled.
    """
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    pending = 0
    for draw in draws:
        label = labels.get(draw["work_id"], {})
        status = label.get("decision_status", "")
        if status == "complete":
            counts[draw["stratum"]][1] += 1
            counts[draw["stratum"]][0] += label.get("plastic_related") == "true"
        elif status != "adjudication_required":
            pending += 1
    return {s: (x, n) for s, (x, n) in counts.items()}, pending


def goal_met_ids(path: Path) -> list[str]:
    if not path.exists():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get("met", []))


def _draw_rows(
    round_number: int,
    selected: Sequence[tuple[str, int, str]],
    drawn_after: Mapping[str, int],
    sizes: Mapping[str, int],
    full_sizes: Mapping[str, int],
    manifest: Mapping[str, Any],
) -> list[dict[str, str]]:
    rows = []
    for stratum, rank, work_id in selected:
        after = drawn_after[stratum]
        rows.append(
            {
                "round": str(round_number),
                "stratum": stratum,
                "work_id": work_id,
                "rank_in_stratum": str(rank),
                "n_h_after_round": str(after),
                "N_h": str(sizes[stratum]),
                "N_h_full": str(full_sizes.get(stratum, sizes[stratum])),
                "incl_prob_within_stratum": f"{after / sizes[stratum]:.6f}",
                "seed": str(manifest["seed"]),
                "model_version": str(manifest["model_version"]),
                "frame_sha256": str(manifest["frame_sha256"]),
            }
        )
    return rows


def _full_sizes(manifest: Mapping[str, Any]) -> dict[str, int]:
    return {row["stratum"]: int(row["N_h"]) for row in manifest["strata"]}


def _context(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, list[str]], dict]:
    manifest = read_manifest(args.manifest)
    frame = read_frame(args.frame, manifest)
    population, fields = build_population(frame, read_guides(args.guides))
    return manifest, population, fields


def cmd_round0(args: argparse.Namespace) -> str:
    manifest, population, _ = _context(args)
    draws = read_draws(args.ledger)
    if any(row["round"] == "0" for row in draws):
        raise SamplerError("round 0 is already drawn; use next-round")
    sizes = {s: len(ids) for s, ids in population.items()}
    alloc = gs.round0_sizes(sizes)
    selected = gs.select_round(population, {}, alloc)
    rows = _draw_rows(0, selected, alloc, sizes, _full_sizes(manifest), manifest)
    append_draws(args.ledger, rows)
    gl.sync_global_sheet(args.sheet, rows)
    return f"round 0: {len(rows)} draws over {len(alloc)} non-empty strata"


def cmd_next_round(args: argparse.Namespace) -> str:
    manifest, population, fields = _context(args)
    draws = read_draws(args.ledger)
    if not any(row["round"] == "0" for row in draws):
        raise SamplerError("round 0 has not been drawn; run round0 first")
    labels = read_labels(args.sheet)
    counts, pending = label_counts(draws, labels)
    if pending:
        raise SamplerError(f"{pending} drawn works are not labelled yet; label them first")
    budget = gs.round_budget(len(draws))
    if budget == 0:
        raise SamplerError(f"the global cap of {gs.MAX_GLOBAL_LABELS} draws is reached")
    goal = gs.active_goal(gs.DEFAULT_GOALS, goal_met_ids(args.goals))
    drawn = Counter(row["stratum"] for row in draws)
    sizes = {s: len(ids) for s, ids in population.items()}
    states = []
    for stratum in sorted(sizes):
        x, n = counts.get(stratum, (0, 0))
        priority = goal is not None and gs.matches(goal.where, fields[stratum])
        states.append(
            gs.StratumState(
                id=stratum,
                capacity=sizes[stratum] - drawn[stratum],
                weight=gs.neyman_weight(sizes[stratum], x, n),
                priority=priority,
                drawn=drawn[stratum],
            )
        )
    alloc, unmet = gs.allocate(states, budget)
    round_number = max(int(row["round"]) for row in draws) + 1
    drawn_after = {s: drawn[s] + alloc.get(s, 0) for s in sizes}
    selected = gs.select_round(population, drawn, alloc)
    rows = _draw_rows(round_number, selected, drawn_after, sizes, _full_sizes(manifest), manifest)
    append_draws(args.ledger, rows)
    gl.sync_global_sheet(args.sheet, rows)
    spend = f"; spend-down toward {goal.id}" if goal and any(s.priority for s in states) else ""
    floor = f"; floor not met in {len(unmet)} strata" if unmet else ""
    return f"round {round_number}: {len(rows)} draws{spend}{floor}"


def cmd_status(args: argparse.Namespace) -> str:
    manifest, population, fields = _context(args)
    draws = read_draws(args.ledger)
    labels = read_labels(args.sheet)
    counts, pending = label_counts(draws, labels)
    complete = sum(n for _, n in counts.values())
    adjudication = sum(
        1
        for row in draws
        if labels.get(row["work_id"], {}).get("decision_status") == "adjudication_required"
    )
    goal = gs.active_goal(gs.DEFAULT_GOALS, goal_met_ids(args.goals))
    lines = [
        f"rounds drawn: {len(set(row['round'] for row in draws))}; draws: {len(draws)}",
        f"labelled (complete): {complete}; adjudication holds: {adjudication}; pending: {pending}",
    ]
    check = gs.checkpoint_status(complete)
    lines.append(
        f"checkpoints reached: {check['checkpoints_reached']}; "
        f"next: {check['next_checkpoint']}; early stop allowed: {check['at_checkpoint']}"
    )
    lines.append(f"active goal: {goal.id if goal else 'none (all goals met)'}")
    drawn = Counter(row["stratum"] for row in draws)
    full = _full_sizes(manifest)
    lines.append("stratum | N_h drawable | N_h full | drawn | complete | incl_prob")
    for stratum in sorted(population):
        n_drawable = len(population[stratum])
        done = counts.get(stratum, (0, 0))[1]
        share = drawn[stratum] / n_drawable
        lines.append(
            f"{stratum} | {n_drawable} | {full.get(stratum, '?')} | {drawn[stratum]} | "
            f"{done} | {share:.4f}"
        )
    gap = sum(full.values()) - sum(len(ids) for ids in population.values())
    if gap:
        lines.append(
            f"note: {gap} zero-score works are in N_h but not in the frame CSV and cannot be "
            "drawn; incl_prob uses the drawable N_h (see docs/GOLD_GLOBAL_FRAME.md)"
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=("round0", "next-round", "status"))
    parser.add_argument("--frame", type=Path, default=DEFAULT_FRAME)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--sheet", type=Path, default=DEFAULT_SHEET)
    parser.add_argument("--guides", type=Path, default=DEFAULT_GUIDES)
    parser.add_argument("--goals", type=Path, default=DEFAULT_GOALS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for name in ("frame", "manifest", "ledger", "sheet", "guides", "goals"):
        path = getattr(args, name)
        setattr(args, name, path if path.is_absolute() else ROOT / path)
    commands = {"round0": cmd_round0, "next-round": cmd_next_round, "status": cmd_status}
    try:
        print(commands[args.command](args))
    except (SamplerError, ValueError, KeyError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
