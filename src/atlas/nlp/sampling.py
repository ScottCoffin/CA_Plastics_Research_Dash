"""Label-independent deterministic gold-set sampling and split assignment.

This module uses only bibliographic metadata, affiliation IDs, and an optional
precomputed gazetteer-hit indicator. It never reads provisional model labels.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

STRATA_FIELDS = ("year_bin", "journal_type", "matrix", "oa_status", "institution_type")
MATRIX_PATTERNS = {
    "marine": r"\b(marine|ocean|estuary|estuaries|coastal|beach|bight)\b",
    "freshwater": r"\b(freshwater|river|lake|stream|stormwater)\b",
    "soil": r"\b(soil|agriculture|crop|plant|terrestrial)\b",
    "wastewater": r"\b(wastewater|sewage|effluent|treatment plant)\b",
    "air": r"\b(airborne|atmosphere|aerosol|deposition)\b",
    "food": r"\b(food|drink|dietary|beverage)\b",
}


def _stable_rank(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def _value(record: Mapping[str, Any], field: str) -> str:
    value = record.get(field)
    return str(value).strip() if value is not None and str(value).strip() else "unknown"


def sampling_strata(record: Mapping[str, Any]) -> tuple[str, ...]:
    """Return fixed sampling dimensions; absent matrix metadata stays unknown."""
    year = record.get("year")
    if isinstance(year, int):
        year_bin = f"{(year // 5) * 5}-{(year // 5) * 5 + 4}"
    else:
        year_bin = "unknown"
    journal_type = _value(record, "type").lower()
    matrix = _value(record, "matrix").lower()
    if matrix == "unknown":
        text = f"{record.get('title') or ''} {record.get('abstract') or ''}".lower()
        matches = [name for name, pattern in MATRIX_PATTERNS.items() if re.search(pattern, text)]
        matrix = "+".join(matches) if matches else "unknown"
    oa_status = _value(record, "oa_status").lower()
    institution_type = _value(record, "institution_type").lower()
    return year_bin, journal_type, matrix, oa_status, institution_type


def _author_groups(records: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Connected components of works linked by any known author ID."""
    parent: dict[str, str] = {}

    def find(item: str) -> str:
        parent.setdefault(item, item)
        root = item
        while parent[root] != root:
            root = parent[root]
        while parent[item] != item:
            next_item = parent[item]
            parent[item] = root
            item = next_item
        return root

    def union(left: str, right: str) -> None:
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)

    author_to_work: dict[str, str] = {}
    ids = [str(row["work_id"]) for row in records]
    for work_id in ids:
        find(work_id)
    for row in records:
        work_id = str(row["work_id"])
        authors = row.get("author_ids", ()) or ()
        for author_id in authors:
            if author_id:
                author_id = str(author_id)
                prior = author_to_work.setdefault(author_id, work_id)
                union(work_id, prior)
    roots = {work_id: find(work_id) for work_id in ids}
    return {work_id: roots[work_id] for work_id in ids}


def _assign_splits(
    records: Sequence[Mapping[str, Any]], seed: int, ratios: Mapping[str, float]
) -> dict[str, str]:
    names = ("train", "dev", "test")
    if set(ratios) != set(names) or any(ratios[name] <= 0 for name in names):
        raise ValueError("split ratios must provide positive train, dev, and test values")
    total = sum(ratios.values())
    normalized = [ratios[name] / total for name in names]
    groups = _author_groups(records)
    members: dict[str, list[str]] = defaultdict(list)
    for work_id, group in groups.items():
        members[group].append(work_id)
    ordered = sorted(members, key=lambda group: (_stable_rank(seed, group), group))
    if len(ordered) == 2:
        return {
            work_id: split
            for group, split in zip(ordered, ("train", "test"), strict=True)
            for work_id in members[group]
        }
    cumulative = (normalized[0], normalized[0] + normalized[1])
    result: dict[str, str] = {}
    for index, group in enumerate(ordered):
        point = (index + 0.5) / max(len(ordered), 1)
        split = "train" if point < cumulative[0] else "dev" if point < cumulative[1] else "test"
        result.update({work_id: split for work_id in members[group]})
    # Small samples can miss a split at the ratio boundaries; assign whole
    # author components deterministically to empty splits when feasible.
    present = {split for split in result.values()}
    for missing in (name for name in names if name not in present):
        candidates = [group for group in ordered if len({result[x] for x in members[group]}) == 1]
        counts = {name: sum(value == name for value in result.values()) for name in names}
        movable = [
            group for group in candidates if counts[result[members[group][0]]] > len(members[group])
        ]
        if movable:
            group = min(movable, key=lambda item: (_stable_rank(seed + 1, item), item))
            result.update({work_id: missing for work_id in members[group]})
            present.add(missing)
    return result


def build_split_rows(
    records: Iterable[Mapping[str, Any]],
    *,
    seed: int = 42042,
    sample_size: int = 500,
    leak_test_size: int = 100,
    ratios: Mapping[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Stratify a pool sample, separately retain leak candidates, and freeze splits.

    ``gazetteer_hit`` must come from a separately versioned, deterministic hit
    pass. Leak-test rows are held out and never mixed into development splits.
    """
    ratios = ratios or {"train": 0.70, "dev": 0.15, "test": 0.15}
    if sample_size < 0 or leak_test_size < 0:
        raise ValueError("sample sizes must be non-negative")
    by_id: dict[str, Mapping[str, Any]] = {}
    for record in records:
        work_id = str(record.get("work_id") or "").strip()
        if not work_id:
            raise ValueError("each record needs work_id")
        if work_id in by_id:
            raise ValueError(f"duplicate work_id: {work_id}")
        by_id[work_id] = record
    pool = [row for row in by_id.values() if bool(row.get("ca_any_author"))]
    leak = [
        row
        for row in by_id.values()
        if not bool(row.get("ca_any_author")) and bool(row.get("gazetteer_hit"))
    ]
    strata: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in pool:
        strata[sampling_strata(row)].append(row)
    for values in strata.values():
        values.sort(key=lambda row: (_stable_rank(seed, str(row["work_id"])), str(row["work_id"])))
    stratum_order = sorted(strata, key=lambda key: (_stable_rank(seed, json.dumps(key)), key))
    selected: list[Mapping[str, Any]] = []
    while len(selected) < min(sample_size, len(pool)):
        progressed = False
        for key in stratum_order:
            if strata[key]:
                selected.append(strata[key].pop(0))
                progressed = True
                if len(selected) >= sample_size:
                    break
        if not progressed:
            break
    selected_leak = sorted(
        leak,
        key=lambda row: (_stable_rank(seed, str(row["work_id"])), str(row["work_id"])),
    )[:leak_test_size]
    combined = [*selected, *selected_leak]
    combined_groups = _author_groups(combined)
    leak_groups = {combined_groups[str(row["work_id"])] for row in selected_leak}
    held_out_pool = [row for row in selected if combined_groups[str(row["work_id"])] in leak_groups]
    development_pool = [row for row in selected if row not in held_out_pool]
    splits = _assign_splits(development_pool, seed, ratios) if development_pool else {}
    splits.update({str(row["work_id"]): "test" for row in held_out_pool})
    splits.update({str(row["work_id"]): "test" for row in selected_leak})
    rows: list[dict[str, Any]] = []
    for row in selected:
        work_id = str(row["work_id"])
        dimensions = sampling_strata(row)
        rows.append(
            {
                "work_id": work_id,
                "sample_role": "pool",
                "split": splits[work_id],
                "year_bin": dimensions[0],
                "journal_type": dimensions[1],
                "matrix": dimensions[2],
                "oa_status": dimensions[3],
                "institution_type": dimensions[4],
                "author_group": hashlib.sha256(
                    combined_groups[work_id].encode("utf-8")
                ).hexdigest(),
            }
        )
    for row in selected_leak:
        dimensions = sampling_strata(row)
        rows.append(
            {
                "work_id": str(row["work_id"]),
                "sample_role": "leak_test",
                "split": "test",
                "year_bin": dimensions[0],
                "journal_type": dimensions[1],
                "matrix": dimensions[2],
                "oa_status": dimensions[3],
                "institution_type": dimensions[4],
                "author_group": hashlib.sha256(
                    combined_groups[str(row["work_id"])].encode("utf-8")
                ).hexdigest(),
            }
        )
    return sorted(rows, key=lambda row: (row["sample_role"], row["work_id"]))
