"""Adaptive gold sampler for the A3 global block (BQ-G4). Pure logic: no files, no Streamlit.

Design (A3 section 4.3, items 2-4 and 6-7):

* Strata are frozen in ``curation/gold_global_frame_v1.csv.gz`` (block x theme group x band).
* Within a stratum the draw is simple random without replacement: the next undrawn works in
  ``rand_key`` order. The order is fixed by the frame, so the draw never depends on a label.
* Round 0 takes ``min(10, N_h)`` works from every non-empty stratum.
* Adaptive rounds of 25 labels allocate across strata with Neyman weights
  ``N_h * sqrt(p_h (1 - p_h))`` where ``p_h = (x_h + 0.5) / (n_h + 1)`` (Jeffreys-smoothed from
  the labels so far). Every stratum that still has undrawn works gets a floor of one draw per
  round while the budget allows it. Rounding is largest-remainder, so the allocation sums to
  exactly the round budget (or to the capacity left when that is smaller).
* Spend-down: goals are predicates over strata in order. While a goal is unmet, the strata that
  match it receive the round before any other stratum does (the floor still applies to all).

Inclusion probabilities depend only on the frozen population and on the draw counts, so the
stratified estimator ``sum_h N_h * (mean of y over the n_h drawn works)`` is the estimator that
BQ-1.1 will use. Precision goals are computed there, not here: ``goal_met`` returns an owner flag.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

ROUND0_MIN_PER_STRATUM = 10
ROUND_SIZE = 25
CHECKPOINTS = (100, 200, 300, 350)
MAX_GLOBAL_LABELS = 350
FIELDS = ("block", "theme_group", "band")


@dataclass(frozen=True)
class Goal:
    """A precision goal (A3 section 4.2) and the strata it spends labels on.

    ``where`` maps a stratum field to the allowed values; an empty mapping matches every stratum.
    """

    id: str
    description: str
    where: Mapping[str, Sequence[str]]


# Order is the spend-down order: P1, then P3, then P4-P6, then the reserve (A3 section 4.3, item 6).
# P3 reads "auto-excluded works" as the low band; the lead must confirm.
DEFAULT_GOALS: tuple[Goal, ...] = (
    Goal("P1", "CA reporting precision (registry_region block)", {"block": ("registry_region",)}),
    Goal("P3", "Residual relevant share among auto-excluded works (low band)", {"band": ("low",)}),
    Goal(
        "P4",
        "Lifecycle-and-society block",
        {"theme_group": ("lifecycle-and-society",)},
    ),
    Goal("P5", "Language probe (non-English works)", {"block": ("global_non_english",)}),
    Goal("P6", "Lens facet (lens-candidate stratum)", {"theme_group": ("lens-candidate",)}),
    Goal("reserve", "Reserve: every stratum", {}),
)


def goal_met(goal_id: str, owner_met: Iterable[str]) -> bool:
    """Stub until BQ-1.1 supplies the precision computation: a goal is met only when the owner
    flags it in the goal file. The estimator will replace this with the CI test of section 4.2."""
    return goal_id in set(owner_met)


def matches(where: Mapping[str, Sequence[str]], stratum: Mapping[str, str]) -> bool:
    return all(stratum[field] in values for field, values in where.items() if values)


def active_goal(goals: Sequence[Goal], owner_met: Iterable[str]) -> Goal | None:
    """The first goal in order that is not met, or None when all are met."""
    met = set(owner_met)
    for goal in goals:
        if not goal_met(goal.id, met):
            return goal
    return None


def jeffreys_p(labelled_positive: int, labelled: int) -> float:
    """Jeffreys-smoothed prevalence (x + 0.5) / (n + 1); 0.5 before any label."""
    return (labelled_positive + 0.5) / (labelled + 1)


def neyman_weight(population: int, labelled_positive: int, labelled: int) -> float:
    p = jeffreys_p(labelled_positive, labelled)
    return population * math.sqrt(p * (1 - p))


def round0_sizes(populations: Mapping[str, int]) -> dict[str, int]:
    """Round 0 draw per stratum: min(10, N_h) for every non-empty stratum."""
    return {s: min(ROUND0_MIN_PER_STRATUM, n) for s, n in populations.items() if n > 0}


@dataclass(frozen=True)
class StratumState:
    id: str
    capacity: int  # undrawn drawable works
    weight: float  # Neyman weight
    priority: bool = False  # matches the active goal
    drawn: int = 0  # works already drawn in this stratum (orders the floor)


def _fill(pool: Sequence[StratumState], alloc: dict[str, int], budget: int) -> int:
    """Add up to ``budget`` draws to ``pool`` in proportion to weight, capped at capacity.

    Returns the number of draws still unassigned. Largest-remainder rounding keeps the total exact.
    """
    room = {s.id: s.capacity - alloc[s.id] for s in pool if s.capacity - alloc[s.id] > 0}
    weight = {s.id: s.weight for s in pool if s.id in room}
    target = min(budget, sum(room.values()))
    if target <= 0:
        return budget
    frac = {k: 0.0 for k in room}
    left = float(target)
    active = set(room)
    while left > 1e-9 and active:
        total_w = sum(weight[k] for k in active)
        share = {
            k: (left * weight[k] / total_w if total_w > 0 else left / len(active)) for k in active
        }
        saturated = [k for k in active if frac[k] + share[k] >= room[k]]
        if not saturated:
            for k in active:
                frac[k] += share[k]
            left = 0.0
            break
        for k in saturated:
            left -= room[k] - frac[k]
            frac[k] = float(room[k])
            active.discard(k)
    ints = {k: min(int(math.floor(frac[k] + 1e-9)), room[k]) for k in room}
    missing = target - sum(ints.values())
    order = sorted(room, key=lambda k: (-(frac[k] - ints[k]), k))
    while missing > 0:
        progressed = False
        for k in order:
            if missing > 0 and ints[k] < room[k]:
                ints[k] += 1
                missing -= 1
                progressed = True
        if not progressed:
            break
    for k, extra in ints.items():
        alloc[k] += extra
    return budget - target


def allocate(
    states: Sequence[StratumState], budget: int, floor: int = 1
) -> tuple[dict[str, int], list[str]]:
    """Draws per stratum for one round, and the ids whose floor could not be met.

    The floor gives each eligible stratum ``floor`` draws. When there are more eligible strata
    than budget, the floor goes first to the strata with the fewest draws so far (then the
    heaviest weight, then id), so every stratum is reached within ceil(strata / budget) rounds.
    The strata left out are reported.
    Remaining budget goes to priority strata first (spend-down), then to all others.
    """
    alloc = {s.id: 0 for s in states}
    eligible = [s for s in states if s.capacity > 0]
    if budget <= 0 or not eligible:
        return alloc, []
    if len(eligible) <= budget:
        floored = list(eligible)
    else:
        floored = sorted(eligible, key=lambda s: (s.drawn, -s.weight, s.id))[:budget]
    floored_ids = {s.id for s in floored}
    for s in floored:
        alloc[s.id] = min(floor, s.capacity)
    unmet = sorted(s.id for s in eligible if s.id not in floored_ids)
    remaining = budget - sum(alloc.values())
    for tier in (
        [s for s in eligible if s.priority],
        [s for s in eligible if not s.priority],
    ):
        if remaining <= 0:
            break
        pool = [s for s in tier if s.capacity - alloc[s.id] > 0]
        if pool:
            remaining = _fill(pool, alloc, remaining)
    return alloc, unmet


def select_round(
    population: Mapping[str, Sequence[str]],
    drawn: Mapping[str, int],
    alloc: Mapping[str, int],
) -> list[tuple[str, int, str]]:
    """(stratum, rank within stratum, work_id) for the next draws, in rand_key order.

    ``population[s]`` lists the stratum's work ids in rand_key order; ``drawn[s]`` is how many were
    already drawn. Rank is 1-based over the whole stratum.
    """
    out: list[tuple[str, int, str]] = []
    for stratum in sorted(alloc):
        count = alloc[stratum]
        start = drawn.get(stratum, 0)
        ids = population.get(stratum, ())
        if start + count > len(ids):
            raise ValueError(f"stratum {stratum} has only {len(ids)} works; cannot draw {count}")
        for offset in range(count):
            out.append((stratum, start + offset + 1, ids[start + offset]))
    return out


def checkpoint_status(total_labels: int) -> dict[str, object]:
    """Counts only (no estimates). Early stopping is allowed only at a checkpoint."""
    reached = [c for c in CHECKPOINTS if total_labels >= c]
    upcoming = [c for c in CHECKPOINTS if c > total_labels]
    return {
        "labels": total_labels,
        "checkpoints_reached": reached,
        "at_checkpoint": total_labels in CHECKPOINTS,
        "next_checkpoint": upcoming[0] if upcoming else None,
    }


def round_budget(total_draws: int) -> int:
    """Size of the next round, capped so the total stays within MAX_GLOBAL_LABELS."""
    return max(0, min(ROUND_SIZE, MAX_GLOBAL_LABELS - total_draws))
