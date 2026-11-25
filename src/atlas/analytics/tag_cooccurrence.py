"""Tag co-occurrence data layer (BQ-4.3, schema bq4-cooc-v1).

Pair counts over CA plastic-related works, read from the frozen labels snapshot that
``atlas.analytics.topic_series`` writes. Only approved, non-experimental topic tags count. Works are
counted per window (complete years, all years, and the earlier and recent periods split at a fixed
year). Pair statistics: n_ab, n_a, n_b, N, Jaccard, lift, and phi. Nothing here reads the network,
the live labels, or writes under ``site/``.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from atlas.analytics.topic_series import CaWork, reported_tags

SCHEMA = "bq4-cooc-v1"
MIN_PAIR_N = 5
RECENT_YEARS = 5
SENSITIVITY_VARIANTS = ("all_sources", "owner_model_only", "rule_only")
NOT_TESTABLE_MESSAGE = "no labels from this source in any year"
OWNER_MODEL_SOURCES = frozenset({"owner", "model"})


def _ratio(numerator: float, denominator: float) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _phi(n_ab: int, n_a: int, n_b: int, total: int) -> float | None:
    denominator = math.sqrt(n_a * (total - n_a) * n_b * (total - n_b))
    if denominator == 0:
        return None
    return round((n_ab * total - n_a * n_b) / denominator, 4)


def _variant_tags(work: CaWork, variant: str, allowed: frozenset[str]) -> frozenset[str]:
    kept = set()
    for tag, source in work.topic_sources.items():
        if tag not in allowed:
            continue
        if variant == "all_sources":
            kept.add(tag)
        elif variant == "owner_model_only" and source in OWNER_MODEL_SOURCES:
            kept.add(tag)
        elif variant == "rule_only" and source == "rule":
            kept.add(tag)
    return frozenset(kept)


def _in_window(year: int | None, bounds: tuple[int | None, int | None]) -> bool:
    if year is None:
        return False
    low, high = bounds
    return (low is None or year >= low) and (high is None or year <= high)


def window_bounds(last_complete: int, split_year: int) -> dict[str, tuple[int | None, int | None]]:
    """Inclusive ``(from, to)`` year bounds (``None`` is open). Undated works fall in no window."""

    return {
        "complete_years": (None, last_complete),
        "all_years": (None, None),
        "earlier": (None, min(split_year - 1, last_complete)),
        "recent": (split_year, last_complete),
    }


def pair_statistics(sets: Sequence[frozenset[str]], tags: Sequence[str]) -> dict[str, Any]:
    """Pair counts and statistics for ``tags`` (sorted) over one set of works.

    ``sets`` holds one tag set per plastic-related work in the window, so ``N`` counts every work,
    including those with no tags in the variant.
    """

    total = len(sets)
    tag_counts = Counter(tag for tags_of_work in sets for tag in tags_of_work)
    pair_counts = Counter(
        pair for tags_of_work in sets for pair in itertools.combinations(sorted(tags_of_work), 2)
    )
    pairs: list[dict[str, Any]] = []
    for a, b in itertools.combinations(tags, 2):
        n_ab = pair_counts.get((a, b), 0)
        n_a = tag_counts.get(a, 0)
        n_b = tag_counts.get(b, 0)
        pairs.append(
            {
                "a": a,
                "b": b,
                "n_ab": n_ab,
                "n_a": n_a,
                "n_b": n_b,
                "N": total,
                "jaccard": _ratio(n_ab, n_a + n_b - n_ab),
                "lift": _ratio(n_ab * total, n_a * n_b),
                "phi": _phi(n_ab, n_a, n_b, total),
                "status": "sufficient" if n_ab >= MIN_PAIR_N else "insufficient_data",
            }
        )
    return {"N": total, "pairs": pairs}


def build_cooccurrence(
    *,
    works: Sequence[CaWork],
    taxonomy: Mapping[str, Any],
    as_of: Any,
    snapshot_path: str,
    snapshot_sha256: str,
    taxonomy_path: str,
    taxonomy_sha256: str,
    split_year: int | None = None,
) -> dict[str, Any]:
    """Assemble the bq4-cooc-v1 payload from frozen CA works (deterministic for equal inputs)."""

    last_complete = int(as_of.year) - 1
    split = last_complete - RECENT_YEARS + 1 if split_year is None else int(split_year)
    reported, excluded = reported_tags(taxonomy)
    tags = sorted(reported, key=lambda entry: entry["tag"])
    tag_ids = [entry["tag"] for entry in tags]
    allowed = frozenset(tag_ids)
    plastic = [work for work in works if work.plastic_related]
    bounds = window_bounds(last_complete, split)

    variants: dict[str, Any] = {}
    for variant in SENSITIVITY_VARIANTS:
        tagged = [
            work
            for work in plastic
            if _in_window(work.year, bounds["all_years"]) and _variant_tags(work, variant, allowed)
        ]
        if not tagged:
            variants[variant] = {"status": "not_testable", "message": NOT_TESTABLE_MESSAGE}
            continue
        windows: dict[str, Any] = {}
        for name, window in bounds.items():
            sets = [
                _variant_tags(work, variant, allowed)
                for work in plastic
                if _in_window(work.year, window)
            ]
            windows[name] = pair_statistics(sets, tag_ids)
        variants[variant] = {"status": "testable", "windows": windows}

    return {
        "schema": SCHEMA,
        "as_of": as_of.isoformat(),
        "last_complete_year": last_complete,
        "split_year": split,
        "windows": {name: {"from": low, "to": high} for name, (low, high) in bounds.items()},
        "min_pair_n": MIN_PAIR_N,
        "scope": "ca",
        "unit": "plastic-related work",
        "inputs": {
            "labels_snapshot": {"path": snapshot_path, "content_sha256": snapshot_sha256},
            "taxonomy": {"path": taxonomy_path, "sha256": taxonomy_sha256},
        },
        "tags": [{k: entry[k] for k in ("tag", "label", "approval")} for entry in tags],
        "tags_excluded": excluded,
        "variants": variants,
    }
