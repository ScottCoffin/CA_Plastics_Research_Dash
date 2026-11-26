"""Build ``groups.json`` (cg-v2) and the derived group files (Add-on A4, CG-9).

Inputs are the published roster (``site/data/global/groups/roster.json``) and, optionally, tag rows
that were already ingested, keyed by ``group_id``. Outputs are deterministic JSON bytes, one per
file: ``groups.json``, ``groups_tree.json``, ``groups_graph.json``, ``coverage.json``,
``flows.json`` and ``precision_card.json`` (docs/BFFP.md sections 8.2, 9.4 and 9.5).

Rules enforced here:

* every record passes ``atlas.groups.schema.validate_groups`` (V1-V14) and the chapter rule;
* untagged groups appear only as aggregated counts in tree and coverage views, never as graph nodes;
* no output carries a count of excluded or ambiguous entries (V14, A4-D24) or an ambassador id;
* a group is tagged when its status is ``ambassador_tagged``, ``reviewed`` or ``group_confirmed``.

Nothing here touches the network.
"""

from __future__ import annotations

import copy
import json
import random
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from itertools import combinations
from typing import Any

from atlas.groups.schema import TAGGED_STATUSES, derive_layer, load_taxonomy, validate_groups

__all__ = [
    "DERIVED_SCHEMAS",
    "GROUPS_SCHEMA",
    "OUTPUT_FILES",
    "GroupsBuildError",
    "build_flows",
    "build_graph",
    "build_groups",
    "build_coverage",
    "build_precision",
    "build_tree",
    "check_flow_conservation",
    "chapter_problems",
    "denominator_note",
    "merge_records",
    "public_output_problems",
    "to_bytes",
]

GROUPS_SCHEMA = "cg-v2"
GROUPS_FILE = "groups.json"
DERIVED_SCHEMAS = {
    "groups_tree.json": "cg-tree-v1",
    "groups_graph.json": "cg-graph-v1",
    "coverage.json": "cg-coverage-v1",
    "flows.json": "cg-flows-v1",
    "precision_card.json": "cg-precision-v1",
}
OUTPUT_FILES = (GROUPS_FILE, *DERIVED_SCHEMAS)
# Tier-1 facets (docs/BFFP.md section 4.4): F1, F2, F3, F4 and F7, by record field name.
TIER1_FACETS = (
    "entity_type",
    "sector",
    "plastics_centrality",
    "primary_activities",
    "geographic_scope",
)
MIN_COMBINATION_GROUPS = 3
UNTAGGED_LEAF = "not_yet_tagged"
UNKNOWN_KEY = "unknown"
UNKNOWN_LABEL = "Not stated"
NO_AMBASSADOR_REGION = "none"
ROSTER_KEYS = ("group_id", "name", "name_alt", "country", "region", "url", "bffp_listed_asof")
HTTPS_URL_RE = re.compile(r"https?://[^\s/]+\S*")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
FORBIDDEN_RE = re.compile(r"ambassador_id|excluded|ambiguous", re.IGNORECASE)


class GroupsBuildError(ValueError):
    """Raised when roster or submission inputs, or the built outputs, fail validation."""


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def denominator_note(tagged: int, roster: int) -> str:
    """Return the plain-language caption required on every file (docs/BFFP.md section 9.0)."""
    pct = 100.0 * tagged / roster if roster else 0.0
    return (
        f"Based on {tagged} of {roster} roster organisations tagged ({pct:.1f}%). "
        "Tagged groups are not a random sample."
    )


def is_tagged(record: Mapping[str, Any]) -> bool:
    """Return True when the record's status is one that requires the Tier-1 facets (V2)."""
    return record.get("status") in TAGGED_STATUSES


def to_bytes(document: Mapping[str, Any]) -> bytes:
    """Serialise deterministically: sorted keys, indent 1, UTF-8, LF, trailing newline."""
    text = json.dumps(document, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    return text.encode("utf-8")


def _https_or_none(url: Any) -> str | None:
    # Malformed roster URLs become null; http and https are both kept.
    if isinstance(url, str) and HTTPS_URL_RE.fullmatch(url):
        return url
    return None


def _meta(generated_from: str, tagged: int, roster: int, schema: str) -> dict[str, Any]:
    return {
        "schema": schema,
        "generated_from": generated_from,
        "denominator_note": denominator_note(tagged, roster),
    }


def _index(vocab: Mapping[str, Sequence[str]], key: str) -> dict[str, int]:
    return {value: position for position, value in enumerate(vocab[key])}


# ---------------------------------------------------------------------------
# groups.json: roster base records, submission merge, chapter rule
# ---------------------------------------------------------------------------


def _base_record(entry: Mapping[str, Any]) -> dict[str, Any]:
    country = entry["country"]
    return {
        "schema": GROUPS_SCHEMA,
        "group_id": entry["group_id"],
        "name": entry["name"],
        "name_alt": list(entry["name_alt"]),
        "url": _https_or_none(entry["url"]),
        "country": country,
        "region": entry["region"],
        "places": [country] if country else [],
        "source": "bffp_roster",
        "org_status": entry["org_status"],
        "bffp_listed": True,
        "bffp_listed_asof": entry["bffp_listed_asof"],
        "status": "unlabelled",
        "cannot_determine_reason": None,
        "layer": "untagged",
        "entity_type": None,
        "sector": None,
        "plastics_centrality": None,
        "primary_activities": [],
        "geographic_scope": None,
        "legal_form": None,
        "legal_form_note": None,
        "participation_in_science": None,
        "website_languages": [],
        "themes": [],
        "analytic_lens": [],
        "constituency": [],
        "parent_group_id": None,
        "stated_affiliations": [],
        "evidence": [],
        "tagged_at": None,
        "reviewed_at": None,
    }


def merge_records(
    roster_records: Iterable[Mapping[str, Any]],
    submissions: Iterable[Mapping[str, Any]] | None = None,
    name_corrections: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Return one cg-v2 record per roster organisation, sorted by group_id.

    Each submission row (keyed by ``group_id``) overwrites the base fields it carries. A name
    correction replaces ``name``; the old name joins ``name_alt``. Corrections for ids that are not
    in the roster are ignored here (the caller counts them). ``layer`` is always derived from
    ``plastics_centrality`` (V1), never taken from a submission.
    """
    by_id: dict[str, dict[str, Any]] = {}
    for entry in roster_records:
        missing = [key for key in ROSTER_KEYS if key not in entry]
        if missing:
            raise GroupsBuildError(f"roster record is missing {', '.join(missing)}")
        if entry["group_id"] in by_id:
            raise GroupsBuildError(f"duplicate roster group_id {entry['group_id']!r}")
        by_id[entry["group_id"]] = _base_record(entry)
    seen: set[str] = set()
    for row in submissions or []:
        group_id = row.get("group_id")
        if group_id not in by_id:
            raise GroupsBuildError(f"submission group_id {group_id!r} is not on the roster")
        if group_id in seen:
            raise GroupsBuildError(f"more than one submission row for {group_id!r}")
        seen.add(group_id)
        by_id[group_id].update(
            {key: copy.deepcopy(value) for key, value in row.items() if key != "group_id"}
        )
    for group_id, corrected in (name_corrections or {}).items():
        record = by_id.get(group_id)
        # Already corrected at the roster stage (or unchanged): nothing to do (idempotent).
        if record is None or record["name"] == corrected:
            continue
        previous = record["name"]
        record["name"] = corrected
        record["name_alt"] = [alt for alt in record["name_alt"] if alt != corrected]
        if previous != corrected and previous not in record["name_alt"]:
            record["name_alt"].append(previous)
    records = []
    for group_id in sorted(by_id):
        record = by_id[group_id]
        record["layer"] = derive_layer(record["plastics_centrality"])
        records.append(record)
    return records


def chapter_problems(records: Iterable[Mapping[str, Any]]) -> list[str]:
    """Return problems with chapter_branch records (rule moved from CG-4).

    A chapter_branch whose parent is known (a ``member_of`` affiliation with a roster target) must
    carry ``parent_group_id``. A set ``parent_group_id`` must not name the group itself.
    """
    problems = []
    for record in records:
        if record.get("entity_type") != "chapter_branch":
            continue
        group_id = record["group_id"]
        parent = record.get("parent_group_id")
        if parent is not None and parent == group_id:
            problems.append(f"CHAPTER: {group_id}: parent_group_id points at the group itself")
        stated_parent = any(
            affiliation.get("relation") == "member_of" and affiliation.get("target_group_id")
            for affiliation in record.get("stated_affiliations") or []
        )
        if parent is None and stated_parent:
            problems.append(
                f"CHAPTER: {group_id}: chapter_branch with a stated parent needs parent_group_id"
            )
    return problems


# ---------------------------------------------------------------------------
# groups_tree.json (A4-D19)
# ---------------------------------------------------------------------------


def _new_branch(level: str, key: str) -> dict[str, Any]:
    label = UNKNOWN_LABEL if key == UNKNOWN_KEY else key
    return {"level": level, "key": key, "label": label, "branches": {}, "leaves": [], "untagged": 0}


def _descend(root: dict[str, Any], steps: Sequence[tuple[str, str]]) -> dict[str, Any]:
    node = root
    for level, key in steps:
        if key not in node["branches"]:
            node["branches"][key] = _new_branch(level, key)
        node = node["branches"][key]
    return node


def _group_leaf(record: Mapping[str, Any]) -> dict[str, Any]:
    return {"group_id": record["group_id"], "name": record["name"], "status": record["status"]}


def _position(level: str, key: str, orders: Mapping[str, Mapping[str, int]]) -> int:
    """Taxonomy position for controlled levels; alphabetical order (position 0) elsewhere."""
    order = orders.get(level)
    return order.get(key, len(order)) if order else 0


def _render(
    branch: Mapping[str, Any], node_id: str, orders: Mapping[str, Mapping[str, int]]
) -> tuple[dict[str, Any], set[str]]:
    children: list[dict[str, Any]] = []
    ids: set[str] = set()
    ordered = sorted(
        branch["branches"].values(),
        key=lambda child: (_position(child["level"], child["key"], orders), child["key"]),
    )
    for child in ordered:
        node, child_ids = _render(child, f"{node_id}/{child['key']}", orders)
        children.append(node)
        ids |= child_ids
    for leaf in sorted(branch["leaves"], key=lambda g: (g["name"], g["group_id"])):
        children.append(
            {
                "id": f"{node_id}/{leaf['group_id']}",
                "level": "group",
                "group_id": leaf["group_id"],
                "label": leaf["name"],
                "status": leaf["status"],
                "counts": {"tagged": 1, "roster": 1, "distinct": 1},
            }
        )
        ids.add(leaf["group_id"])
    if branch["untagged"]:
        count = branch["untagged"]
        children.append(
            {
                "id": f"{node_id}/{UNTAGGED_LEAF}",
                "level": UNTAGGED_LEAF,
                "label": f"Not yet tagged ({count})",
                "count": count,
                "counts": {"tagged": 0, "roster": count, "distinct": 0},
            }
        )
    # A multi-activity group may appear in several descendant branches. Counts at
    # every branch describe distinct organisations, not placements.
    untagged_count = sum(
        child["counts"]["roster"] - child["counts"]["tagged"] for child in children
    )
    counts = {
        "tagged": len(ids),
        "roster": len(ids) + untagged_count,
        "distinct": len(ids),
    }
    node = {
        "id": node_id,
        "level": branch["level"],
        "label": branch["label"],
        "counts": counts,
        "children": children,
    }
    return node, ids


def build_tree(
    records: Sequence[Mapping[str, Any]],
    vocab: Mapping[str, Sequence[str]],
    generated_from: str,
) -> dict[str, Any]:
    """Return the three hierarchies (A4-D19); each tagged group sits once in each of them.

    Untagged groups are never individual leaves: geography shows one "Not yet tagged" leaf per
    country, the activity-based hierarchies show one at the root.
    """
    tagged = [r for r in records if is_tagged(r)]
    orders = {
        "layer": _index(vocab, "layer"),
        "sector": _index(vocab, "sector"),
        "activity": _index(vocab, "primary_activities"),
        "centrality": _index(vocab, "plastics_centrality"),
    }
    roots = {name: _new_branch("root", name) for name in ("geography", "function", "centrality")}
    roots_all = {name: _new_branch("root", name) for name in ("function", "centrality")}
    roots["geography"]["label"] = "All roster organisations"
    geography_nodes = {}
    for record in records:
        geo_steps = [("region", record["region"]), ("country", record["country"] or UNKNOWN_KEY)]
        if is_tagged(record) and record["country"] == "US" and "US-CA" in record.get("places", []):
            geo_steps.append(("subnational", "US-CA"))
        geo = _descend(roots["geography"], geo_steps)
        geography_nodes[record["group_id"]] = geo
        if not is_tagged(record):
            geo["untagged"] += 1
            roots["function"]["untagged"] += 1
            roots["centrality"]["untagged"] += 1
            roots_all["function"]["untagged"] += 1
            roots_all["centrality"]["untagged"] += 1
    for record in tagged:
        activities = record["primary_activities"] or [UNKNOWN_KEY]
        principals = [activities[0]]
        geography_path = geography_nodes[record["group_id"]]
        _descend(
            geography_path,
            [("layer", record["layer"]), ("sector", record["sector"])],
        )["leaves"].append(_group_leaf(record))
        for function_root, centrality_root, selected_activities in (
            (roots["function"], roots["centrality"], principals),
            (roots_all["function"], roots_all["centrality"], activities),
        ):
            for activity in selected_activities:
                function_steps = [
                    ("layer", record["layer"]),
                    ("sector", record["sector"]),
                    ("activity", activity),
                ]
                centrality_steps = [
                    ("centrality", record["plastics_centrality"]),
                    ("activity", activity),
                ]
                _descend(function_root, function_steps)["leaves"].append(_group_leaf(record))
                _descend(centrality_root, centrality_steps)["leaves"].append(_group_leaf(record))
    hierarchies = {}
    for name, root in roots.items():
        hierarchies[name], _ = _render(root, name, orders)
    hierarchies_all = {}
    for name, root in roots_all.items():
        hierarchies_all[name], _ = _render(root, name, orders)
    return {
        **_meta(generated_from, len(tagged), len(records), DERIVED_SCHEMAS["groups_tree.json"]),
        "default_hierarchy": "geography",
        "hierarchies": hierarchies,
        "hierarchies_all_activities": hierarchies_all,
    }


# ---------------------------------------------------------------------------
# groups_graph.json (V-NET): tagged groups only
# ---------------------------------------------------------------------------

GRAPH_EDGE_TYPES = ("assignment", "affiliation", "co_occurrence")
GRAPH_LAYOUT_EDGE_TYPES = ("assignment", "affiliation")
GRAPH_LAYOUT_SEED = 42
GRAPH_LAYOUT_ITERATIONS = 200


def _graph_layout(
    node_ids: Sequence[str], edges: Sequence[Mapping[str, Any]]
) -> dict[str, tuple[float, float]]:
    """Build-time ForceAtlas2 positions in [-1, 1], rounded to 4 decimals (V-NET).

    Only assignment and affiliation edges pull on the layout; co-occurrence never does. The start
    layout is a seeded gauss draw over the sorted node ids, so the result is deterministic.
    """
    if not node_ids:
        return {}
    if len(node_ids) == 1:
        return {node_ids[0]: (0.0, 0.0)}
    import networkx as nx  # lazy, as in atlas.build.network

    from atlas.build.network import forceatlas2_positions

    graph = nx.Graph()
    graph.add_nodes_from(node_ids)
    graph.add_edges_from(
        (e["source"], e["target"]) for e in edges if e["edge_type"] in GRAPH_LAYOUT_EDGE_TYPES
    )
    rng = random.Random(GRAPH_LAYOUT_SEED)
    start = {node: (rng.gauss(0.0, 1.0), rng.gauss(0.0, 1.0)) for node in node_ids}
    positions = forceatlas2_positions(graph, start, iterations=GRAPH_LAYOUT_ITERATIONS)
    return {node: (round(x, 4), round(y, 4)) for node, (x, y) in positions.items()}


def build_graph(
    records: Sequence[Mapping[str, Any]],
    vocab: Mapping[str, Sequence[str]],
    generated_from: str,
) -> dict[str, Any]:
    """Return the bipartite assignment graph, stated affiliations and tag co-occurrence.

    Only tagged groups become nodes. Facet nodes (activity, theme, place) exist only when a tagged
    group uses them. An affiliation edge needs a quoted stated affiliation and, for a roster target,
    a tagged target; an untagged roster target is never drawn. External targets become ghost nodes.
    Every node carries a build-time ForceAtlas2 ``x``/``y`` (assignment and affiliation edges only),
    described by the top-level ``layout`` key; the schema string is unchanged.
    """
    tagged = [r for r in records if is_tagged(r)]
    tagged_ids = {r["group_id"] for r in tagged}
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def facet_node(kind: str, value: str) -> str:
        node_id = f"{kind}:{value}"
        nodes.setdefault(node_id, {"id": node_id, "type": kind, "label": value})
        return node_id

    for record in tagged:
        group_id = record["group_id"]
        nodes[group_id] = {
            "id": group_id,
            "type": "group",
            "label": record["name"],
            "layer": record["layer"],
            "sector": record["sector"],
            "plastics_centrality": record["plastics_centrality"],
            "status": record["status"],
        }
        for kind, values in (
            ("activity", record["primary_activities"]),
            ("theme", record["themes"]),
            ("place", record["places"]),
        ):
            for value in values:
                edges.append(
                    {
                        "edge_type": "assignment",
                        "source": group_id,
                        "target": facet_node(kind, value),
                        "facet": kind,
                    }
                )
        for affiliation in record["stated_affiliations"]:
            target = affiliation.get("target_group_id")
            if target is None:
                target_id = facet_node("external", affiliation["target_name"])
                nodes[target_id]["type"] = "external"
            elif target in tagged_ids and target != group_id:
                target_id = target
            else:
                continue  # an untagged roster group is never drawn
            relation = affiliation["relation"]
            evidence = affiliation["evidence"]
            edges.append(
                {
                    "edge_type": "affiliation",
                    "source": group_id,
                    "target": target_id,
                    "relation": relation,
                    "directed": relation != "partner_of",
                    "url": evidence["url"],
                    "quote": evidence["quote"],
                }
            )
    activity_order = _index(vocab, "primary_activities")
    pair_counts: Counter[tuple[str, str]] = Counter()
    for record in tagged:
        acts = sorted(set(record["primary_activities"]), key=activity_order.__getitem__)
        pair_counts.update(combinations(acts, 2))
    for (first, second), weight in sorted(pair_counts.items()):
        edges.append(
            {
                "edge_type": "co_occurrence",
                "source": f"activity:{first}",
                "target": f"activity:{second}",
                "weight": weight,
            }
        )
    degree: Counter[str] = Counter()
    for edge in edges:
        if edge["edge_type"] != "co_occurrence":
            degree[edge["source"]] += 1
            degree[edge["target"]] += 1
    for node_id, node in nodes.items():
        node["degree"] = degree[node_id]
    positions = _graph_layout(sorted(nodes), edges)
    for node_id, node in nodes.items():
        node["x"], node["y"] = positions[node_id]
    edges.sort(
        key=lambda e: (
            e["edge_type"],
            e["source"],
            e["target"],
            e.get("facet", ""),
            e.get("relation", ""),
        )
    )
    return {
        **_meta(generated_from, len(tagged), len(records), DERIVED_SCHEMAS["groups_graph.json"]),
        "edge_types": list(GRAPH_EDGE_TYPES),
        "layout": {
            "algorithm": "ForceAtlas2 (networkx)",
            "seed": GRAPH_LAYOUT_SEED,
            "iterations": GRAPH_LAYOUT_ITERATIONS,
            "edge_types": list(GRAPH_LAYOUT_EDGE_TYPES),
        },
        "caution": (
            "The view reflects tagged groups only; absence of edges reflects missing data. "
            "Co-occurrence of tags is not a partnership."
        ),
        "nodes": [nodes[node_id] for node_id in sorted(nodes)],
        "edges": edges,
    }


# ---------------------------------------------------------------------------
# coverage.json and precision_card.json (V-COV, V-EVID)
# ---------------------------------------------------------------------------


def build_coverage(
    roster_records: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
    vocab: Mapping[str, Sequence[str]],
    generated_from: str,
) -> dict[str, Any]:
    """Return roster and status counts per region, country and ambassador region."""
    by_id = {record["group_id"]: record for record in records}
    statuses = vocab["status"]

    def section(key_of: Any) -> dict[str, dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for entry in roster_records:
            bucket = buckets.setdefault(
                key_of(entry),
                {"roster": 0, "tagged": 0, "status": {status: 0 for status in statuses}},
            )
            record = by_id[entry["group_id"]]
            bucket["roster"] += 1
            bucket["status"][record["status"]] += 1
            if is_tagged(record):
                bucket["tagged"] += 1
        return buckets

    tagged = [r for r in records if is_tagged(r)]
    languages: Counter[str] = Counter()
    for record in tagged:
        languages.update(record["website_languages"])
    return {
        **_meta(generated_from, len(tagged), len(records), DERIVED_SCHEMAS["coverage.json"]),
        "roster_total": len(records),
        "tagged_total": len(tagged),
        "by_region": section(lambda e: e["region"]),
        "by_country": section(lambda e: e["country"] or UNKNOWN_KEY),
        "by_ambassador_region": section(
            lambda e: e.get("ambassador_region") or NO_AMBASSADOR_REGION
        ),
        "weekly_tagged": [],
        "languages": dict(sorted(languages.items())),
    }


def build_precision(
    records: Sequence[Mapping[str, Any]],
    generated_from: str,
    vocab: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    """Return the per-facet precision card (section 7.4); no agreement without a sample."""
    tagged = [r for r in records if is_tagged(r)]
    facets: dict[str, dict[str, Any]] = {}
    for facet in TIER1_FACETS:
        with_value = [r for r in tagged if r[facet] not in (None, [])]
        with_evidence = [r for r in tagged if any(e["facet"] == facet for e in r["evidence"])]
        reviewed = [r for r in with_value if r["reviewed_at"] is not None]
        facets[facet] = {
            "tagged_n": len(with_value),
            "with_evidence_n": len(with_evidence),
            "reviewed_n": len(reviewed),
            "agreement": None,
            "agreement_reason": "no double-tagged sample yet",
        }
    reasons = {reason: 0 for reason in vocab["cannot_determine_reason"]}
    for record in records:
        if record["status"] == "cannot_determine":
            reasons[record["cannot_determine_reason"]] += 1
    by_region: dict[str, dict[str, Any]] = {}
    for record in records:
        bucket = by_region.setdefault(record["region"], {"tagged": 0, "roster": 0})
        bucket["roster"] += 1
        bucket["tagged"] += int(is_tagged(record))
    for bucket in by_region.values():
        bucket["coverage"] = round(bucket["tagged"] / bucket["roster"], 4)
    return {
        **_meta(generated_from, len(tagged), len(records), DERIVED_SCHEMAS["precision_card.json"]),
        "tier1_facets": list(TIER1_FACETS),
        "facets": facets,
        "cannot_determine_reasons": reasons,
        "coverage_by_region": dict(sorted(by_region.items())),
    }


# ---------------------------------------------------------------------------
# flows.json (V-SANKEY, V-PART, V-COOC)
# ---------------------------------------------------------------------------

SANKEY_STAGES = ("sector", "centrality", "activity")


def check_flow_conservation(
    nodes: Sequence[Mapping[str, Any]],
    links: Sequence[Mapping[str, Any]],
    total: int,
    stages: Sequence[str] = SANKEY_STAGES,
) -> list[str]:
    """Return problems with a staged flow: each stage carries ``total`` and inflow equals outflow.

    Links must join consecutive stages, have a positive value and reference known nodes.
    """
    stage_of = {node["id"]: node["stage"] for node in nodes}
    problems = []
    for link in links:
        source, target = stage_of.get(link["source"]), stage_of.get(link["target"])
        if source is None or target is None:
            problems.append(f"flow: link {link['source']}->{link['target']} has an unknown node")
        elif stages.index(target) != stages.index(source) + 1:
            problems.append(f"flow: link {link['source']}->{link['target']} skips a stage")
        if link["value"] <= 0:
            problems.append(f"flow: link {link['source']}->{link['target']} has no groups")
    for index in range(len(stages) - 1):
        out_total = sum(v["value"] for v in links if stage_of.get(v["source"]) == stages[index])
        in_total = sum(v["value"] for v in links if stage_of.get(v["target"]) == stages[index + 1])
        if out_total != total or in_total != total:
            problems.append(
                f"flow: {stages[index]}->{stages[index + 1]} totals {out_total}/{in_total}, "
                f"expected {total}"
            )
    for node in nodes:
        if node["stage"] in stages[1:-1]:
            inflow = sum(v["value"] for v in links if v["target"] == node["id"])
            outflow = sum(v["value"] for v in links if v["source"] == node["id"])
            if inflow != outflow:
                problems.append(f"flow: {node['id']} in {inflow} differs from out {outflow}")
    return problems


def build_flows(
    records: Sequence[Mapping[str, Any]],
    vocab: Mapping[str, Sequence[str]],
    generated_from: str,
) -> dict[str, Any]:
    """Return Sankey links (principal activity only), participation and activity combinations."""
    tagged = [r for r in records if is_tagged(r)]
    total = len(tagged)
    sector_order = _index(vocab, "sector")
    centrality_order = _index(vocab, "plastics_centrality")
    activity_order = _index(vocab, "primary_activities")
    first_links: Counter[tuple[str, str]] = Counter()
    second_links: Counter[tuple[str, str]] = Counter()
    for record in tagged:
        first_links[(record["sector"], record["plastics_centrality"])] += 1
        second_links[(record["plastics_centrality"], record["primary_activities"][0])] += 1
    nodes = []
    for stage, values, order in (
        ("sector", {r["sector"] for r in tagged}, sector_order),
        ("centrality", {r["plastics_centrality"] for r in tagged}, centrality_order),
        ("activity", {r["primary_activities"][0] for r in tagged}, activity_order),
    ):
        for value in sorted(values, key=order.__getitem__):
            nodes.append({"id": f"{stage}:{value}", "stage": stage, "label": value})
    first = sorted(
        first_links.items(), key=lambda i: (sector_order[i[0][0]], centrality_order[i[0][1]])
    )
    second = sorted(
        second_links.items(), key=lambda i: (centrality_order[i[0][0]], activity_order[i[0][1]])
    )
    links = [
        {"source": f"sector:{s}", "target": f"centrality:{c}", "value": n} for (s, c), n in first
    ] + [
        {"source": f"centrality:{c}", "target": f"activity:{a}", "value": n} for (c, a), n in second
    ]
    problems = check_flow_conservation(nodes, links, total)

    rm = [r for r in tagged if "research_monitoring" in r["primary_activities"]]
    f5_counts = {value: 0 for value in vocab["participation_in_science"]}
    f5_counts["not_set"] = 0
    for record in rm:
        f5_counts[record["participation_in_science"] or "not_set"] += 1

    combos = Counter(
        tuple(sorted(set(r["primary_activities"]), key=activity_order.__getitem__)) for r in tagged
    )
    kept = sorted(
        ((c, n) for c, n in combos.items() if n >= MIN_COMBINATION_GROUPS),
        key=lambda item: (-item[1], item[0]),
    )
    rest = [(c, n) for c, n in combos.items() if n < MIN_COMBINATION_GROUPS]
    other_groups = sum(n for _, n in rest)
    if sum(n for _, n in kept) + other_groups != total:
        problems.append("flow: activity combinations do not sum to the tagged total")
    if problems:
        raise GroupsBuildError("; ".join(problems))
    return {
        **_meta(generated_from, total, len(records), DERIVED_SCHEMAS["flows.json"]),
        "sankey": {"stages": list(SANKEY_STAGES), "nodes": nodes, "links": links},
        "participation": {
            "research_monitoring_n": len(rm),
            "with_f5_value_n": sum(1 for r in rm if r["participation_in_science"]),
            "counts": f5_counts,
        },
        "activity_combinations": {
            "min_group_size": MIN_COMBINATION_GROUPS,
            "ordering": "by frequency of tag combinations",
            "combinations": [{"activities": list(c), "groups": n} for c, n in kept],
            "other": {"combinations": len(rest), "groups": other_groups},
        },
    }


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def public_output_problems(outputs: Mapping[str, bytes]) -> list[str]:
    """Return problems for strings that must never be published (V8, V9, V14)."""
    problems = []
    for name, data in outputs.items():
        text = data.decode("utf-8")
        if EMAIL_RE.search(text):
            problems.append(f"{name}: contains an email-pattern string (V8)")
        if FORBIDDEN_RE.search(text):
            problems.append(f"{name}: contains an ambassador id or excluded/ambiguous count")
    return problems


def build_groups(
    roster: Mapping[str, Any],
    submissions: Iterable[Mapping[str, Any]] | None = None,
    taxonomy: Mapping[str, Sequence[str]] | None = None,
    name_corrections: Mapping[str, str] | None = None,
) -> dict[str, bytes]:
    """Return file name -> deterministic bytes for the six group files.

    ``roster`` is the parsed roster.json (``retrieved_at`` and ``records``). ``name_corrections``
    maps group_id to the corrected display name. Raises ``GroupsBuildError`` when the inputs or any
    built record fail validation.
    """
    vocab = dict(taxonomy) if taxonomy is not None else load_taxonomy()
    generated_from = roster["retrieved_at"]
    records = merge_records(roster["records"], submissions, name_corrections)
    problems = validate_groups(records, taxonomy=vocab) + chapter_problems(records)
    if problems:
        shown = "; ".join(problems[:20])
        raise GroupsBuildError(f"{len(problems)} problem(s): {shown}")
    tagged = sum(1 for r in records if is_tagged(r))
    documents: dict[str, Any] = {
        GROUPS_FILE: {
            "schema": GROUPS_SCHEMA,
            **_meta(generated_from, tagged, len(records), GROUPS_SCHEMA),
            "groups": records,
        },
        "groups_tree.json": build_tree(records, vocab, generated_from),
        "groups_graph.json": build_graph(records, vocab, generated_from),
        "coverage.json": build_coverage(roster["records"], records, vocab, generated_from),
        "flows.json": build_flows(records, vocab, generated_from),
        "precision_card.json": build_precision(records, generated_from, vocab),
    }
    outputs = {name: to_bytes(document) for name, document in documents.items()}
    leaks = public_output_problems(outputs)
    if leaks:
        raise GroupsBuildError("; ".join(leaks))
    return outputs
