"""Build reusable geography-scoped group payloads."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from atlas.groups.build import build_coverage, build_flows, build_graph, build_tree
from atlas.groups.schema import load_taxonomy


def scoped_records(
    records: Sequence[Mapping[str, Any]],
    *,
    countries: set[str] | None = None,
    region: str | None = None,
    explicit_place: str | None = None,
) -> list[Mapping[str, Any]]:
    """Select records by roster geography. CA slices require an explicit US-CA place."""
    selected = []
    for record in records:
        if countries is not None and record.get("country") not in countries:
            continue
        if explicit_place and explicit_place not in (record.get("places") or []):
            continue
        if region and record.get("region") != region:
            continue
        selected.append(record)
    return selected


def build_scope_payload(
    roster_records: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
    generated_from: str,
    vocab: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    """Rebuild the derived payloads from a truthful roster subset."""
    vocab = vocab or load_taxonomy()
    roster_ids = {record["group_id"] for record in roster_records}
    subset = [record for record in records if record["group_id"] in roster_ids]
    return {
        "coverage": build_coverage(roster_records, subset, vocab, generated_from),
        "tree": build_tree(subset, vocab, generated_from),
        "flows": build_flows(subset, vocab, generated_from),
        "graph": build_graph(subset, vocab, generated_from),
    }
