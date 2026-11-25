"""Global institution co-occurrence graph (BQ-V.1 slice 1; data only, no author-level output).

Input: the ignored raw global store (``data/raw/openalex_global/pages``). Each work's distinct
institutions (over all authorships) are its node set. Two institutions share an edge for every
work on which both appear; the edge weight is that count. Works with more than
``MAX_INSTITUTIONS_PER_WORK`` institutions still count toward node works, but add no edges.

The graph is restricted to its largest connected component, then to the ``NODE_CAP`` institutions
with the most works. Communities are seeded Louvain (networkx). Positions are ForceAtlas2
(networkx, with the same settings as ``atlas.build.network``), run per community and the
communities packed on a sunflower spiral, so the layout is cheap enough for 20k nodes.

Determinism: nodes are sorted by (works desc, id); edges by node index; all seeds are fixed.
No person-level data (authors, ORCID, names) is read or written.
"""

from __future__ import annotations

import gzip
import json
import math
import random
import struct
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

from atlas.build.network import forceatlas2_positions
from atlas.ingest.global_partition import NoRawStoreError, raw_page_paths

SCHEMA_VERSION = "bqv-v1"
GRAPH_NAME = "institutions"
PHONE_GRAPH_NAME = "institutions_phone"
SCREENING_STATUS = "unscreened_query_hit"
NODE_CAP = 20_000
PHONE_NODE_CAP = 5_000
MAX_INSTITUTIONS_PER_WORK = 50
SEED = 42
LAYOUT_ITERATIONS = 150
LAYOUT_SCALING_RATIO = 10.0
DESKTOP_EDGE_BUDGET = 60_000
PHONE_EDGE_BUDGET = 15_000
DESKTOP_START_K = 8
PHONE_START_K = 3
POSITION_DECIMALS = 4
NODE_FIELDS = ("id", "display_name", "ror", "country_code", "type", "works", "community")
EDGE_FIELDS = ("source", "target", "weight")
FILE_NAMES = {
    GRAPH_NAME: "institutions.json",
    PHONE_GRAPH_NAME: "institutions_phone.json",
    "layout": "layout_institutions.bin",
    "manifest": "graphs_manifest.json",
}
WHAT_THIS_IS = (
    "Institution co-occurrence graph from the unscreened global OpenAlex query hits (plastic "
    "query version in this manifest). A node is an institution; an edge joins two institutions "
    "that appear on the same work, and its weight is the number of such works. It is not a "
    "screened corpus and not a measure of collaboration quality. It holds no person-level data: "
    "no author names, author IDs or ORCIDs. Works with more than 50 institutions count toward "
    "node works but add no edges. Only the largest connected component is kept, then the 20,000 "
    "institutions with the most works (and the edges among them). The phone file is the first "
    "5,000 of those nodes."
)
EDGE_RULE = (
    f"Edges come from works with 2 to {MAX_INSTITUTIONS_PER_WORK} distinct institutions; weight is "
    "the number of shared works. Works above the cap add to node works only."
)
COMPONENT_RULE = (
    "Largest connected component of the edge graph (ties: the component with the smallest "
    "institution id), then the top nodes by works (ties by id) within it."
)
THINNING_RULE = (
    "Per node keep its k strongest edges (ties: the other node's works, then id) and keep the "
    "union. If over budget, drop weight-1 edges (last index first) that leave both ends with an "
    "edge. If still over budget, lower k by one and repeat. Desktop: budget 60,000 edges, k "
    "starts at 8. Phone: budget 15,000, k starts at 3, applied to the phone subset alone. Every "
    "node keeps its strongest edge. Communities and layout use the thinned desktop graph."
)
COMMUNITY_METHOD = (
    "Louvain (networkx) on the weighted kept graph, seed 42; community 0 is the largest."
)
LAYOUT_METHOD = (
    "ForceAtlas2 (networkx, scaling ratio 10, strong gravity 0.05, node mass 1 + weighted degree) "
    "run separately inside each Louvain community for the stated iterations, starting from seeded "
    "random points; each community is scaled by the square root of its size and the communities "
    "are placed on a sunflower spiral (largest at the centre); the whole layout is scaled to "
    "[-1, 1]. Edges between communities do not shape the layout."
)
LAYOUT_FORMAT = (
    "little-endian float32 pairs (x, y) in node order; node i occupies bytes 8*i to 8*i+7. "
    "The phone graph uses the first phone-cap entries."
)


@dataclass(frozen=True)
class RawSummary:
    pages: int
    works: int
    works_with_institutions: int
    institutions_seen: int
    query_version: str
    query_hash: str
    generated_at: str


@dataclass(frozen=True)
class GraphBuild:
    """Serialised output: file bytes keyed by ``FILE_NAMES`` keys, plus the parsed manifest."""

    files: dict[str, bytes]
    manifest: dict[str, Any]


def _short_id(value: object) -> str | None:
    """'https://openalex.org/I123' -> 'I123'; anything else empty or non-text -> None."""
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().rstrip("/").rsplit("/", 1)[-1] or None


def _read_header(path: Path) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        header = json.loads(handle.readline())
    if not isinstance(header, dict) or header.get("record_type") != "page_header":
        raise ValueError(f"{path}: first line is not a page_header record")
    return header


def _iter_works(path: Path) -> Iterator[Mapping[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        handle.readline()
        for line in handle:
            if line.strip():
                yield json.loads(line)


def read_raw_works(
    raw_dir: str | Path,
) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[Any, ...]], RawSummary]:
    """Distinct institutions per work (latest page wins) and institution attributes.

    Returns ``(work_id -> sorted institution ids, institution id -> (name, ror, country, type),
    summary)``. Pages are read in fetch-time order, so a later page replaces an earlier copy of
    the same work.
    """
    paths = raw_page_paths(raw_dir)
    if not paths:
        raise NoRawStoreError(f"no raw pages under {raw_dir}")
    headers = sorted(
        ((_read_header(path), path) for path in paths),
        key=lambda item: (str(item[0].get("fetched_utc") or ""), item[1].name),
    )
    versions = {(str(h.get("query_version")), str(h.get("query_hash"))) for h, _ in headers}
    if len(versions) != 1:
        raise ValueError(f"raw pages mix query versions: {sorted(versions)}")
    query_version, query_hash = next(iter(versions))

    works_insts: dict[str, tuple[str, ...]] = {}
    info: dict[str, tuple[Any, ...]] = {}
    for _, path in headers:
        for work in _iter_works(path):
            work_id = _short_id(work.get("id"))
            if work_id is None:
                continue
            ids: set[str] = set()
            for authorship in work.get("authorships") or []:
                for inst in (authorship or {}).get("institutions") or []:
                    inst_id = _short_id((inst or {}).get("id"))
                    if inst_id is None:
                        continue
                    ids.add(inst_id)
                    info[inst_id] = (
                        inst.get("display_name"),
                        inst.get("ror"),
                        inst.get("country_code"),
                        inst.get("type"),
                    )
            works_insts[work_id] = tuple(sorted(ids))
    with_inst = {w: ids for w, ids in works_insts.items() if ids}
    summary = RawSummary(
        pages=len(paths),
        works=len(works_insts),
        works_with_institutions=len(with_inst),
        institutions_seen=len(info),
        query_version=query_version,
        query_hash=query_hash,
        generated_at=str(max(str(h.get("fetched_utc") or "") for h, _ in headers)),
    )
    return with_inst, info, summary


def co_occurrence(
    works_insts: Mapping[str, Sequence[str]],
    max_institutions: int = MAX_INSTITUTIONS_PER_WORK,
) -> tuple[Counter[str], Counter[tuple[str, str]]]:
    """Works per institution, and shared-work counts per institution pair (a < b)."""
    works: Counter[str] = Counter()
    edges: Counter[tuple[str, str]] = Counter()
    for ids in works_insts.values():
        works.update(ids)
        if 2 <= len(ids) <= max_institutions:
            edges.update(combinations(sorted(ids), 2))
    return works, edges


def _component_nodes(nodes: Sequence[str], edges: Mapping[tuple[str, str], int]) -> set[str]:
    import networkx as nx  # lazy, as in atlas.build.network

    graph = nx.Graph()
    graph.add_nodes_from(sorted(nodes))
    graph.add_edges_from(edges)
    components = sorted(
        (sorted(c) for c in nx.connected_components(graph)), key=lambda c: (-len(c), c[0])
    )
    return set(components[0]) if components else set()


def _unit_fit(points: Mapping[int, tuple[float, float]]) -> dict[int, tuple[float, float]]:
    xs = [x for x, _ in points.values()]
    ys = [y for _, y in points.values()]
    cx = (max(xs) + min(xs)) / 2
    cy = (max(ys) + min(ys)) / 2
    half = max(max(xs) - min(xs), max(ys) - min(ys)) / 2 or 1.0
    return {k: ((x - cx) / half, (y - cy) / half) for k, (x, y) in points.items()}


def community_layout(
    size: int,
    edges: Sequence[tuple[int, int, float]],
    communities: Sequence[Sequence[int]],
    *,
    iterations: int,
) -> list[tuple[float, float]]:
    """Positions for nodes ``0..size-1``: ForceAtlas2 inside each community, then packed.

    ``communities`` lists node indices, largest community first (community k = index k).
    """
    import networkx as nx  # lazy, as in atlas.build.network

    graph = nx.Graph()
    graph.add_nodes_from(range(size))
    graph.add_weighted_edges_from(edges)
    rng = random.Random(SEED)
    golden = math.pi * (3.0 - math.sqrt(5.0))
    largest = max((len(c) for c in communities), default=1)
    spacing = 2.0 * math.sqrt(largest)
    positions: dict[int, tuple[float, float]] = {}
    for k, members in enumerate(communities):
        nodes = sorted(members)
        if len(nodes) == 1:
            local = {nodes[0]: (0.0, 0.0)}
        else:
            sub = graph.subgraph(nodes).copy()
            start = {n: (rng.gauss(0.0, 1.0), rng.gauss(0.0, 1.0)) for n in nodes}
            local = forceatlas2_positions(sub, start, iterations=iterations)
        scale = math.sqrt(len(nodes))
        radius = spacing * math.sqrt(k)
        cx, cy = radius * math.cos(k * golden), radius * math.sin(k * golden)
        for node, (x, y) in local.items():
            positions[node] = (cx + scale * x, cy + scale * y)
    fitted = _unit_fit(positions)
    return [fitted[i] for i in range(size)]


def thin_edges(
    edges: Sequence[tuple[int, int, int]],
    node_count: int,
    *,
    budget: int,
    start_k: int,
) -> tuple[list[tuple[int, int, int]], dict[str, Any]]:
    """Deterministic thinning to at most ``budget`` edges (node indices, a < b, weights).

    For each node its ``k`` strongest edges are kept (ties: the other node's index, which is
    works-descending then id), and the union is kept. If the union is over budget, weight-1
    edges are dropped (last index first), but never one whose endpoint would lose its last edge.
    If still over budget, ``k`` drops by one and the rule runs again. Every node with an edge
    keeps at least its strongest edge.
    """
    if start_k < 1:
        raise ValueError("start_k must be at least 1")
    weight = {(a, b): w for a, b, w in edges}
    total = sum(weight.values())
    incident: list[list[tuple[int, int]]] = [[] for _ in range(node_count)]
    for a, b, w in edges:
        incident[a].append((-w, b))
        incident[b].append((-w, a))
    for ranked in incident:
        ranked.sort()
    kept: set[tuple[int, int]] = set()
    dropped = 0
    k = start_k
    for k in range(start_k, 0, -1):
        kept = set()
        for node in range(node_count):
            for _, other in incident[node][:k]:
                kept.add((min(node, other), max(node, other)))
        dropped = 0
        if len(kept) > budget:
            degree: Counter[int] = Counter()
            for a, b in kept:
                degree[a] += 1
                degree[b] += 1
            for a, b in sorted(kept, reverse=True):
                if len(kept) <= budget:
                    break
                if weight[(a, b)] == 1 and degree[a] > 1 and degree[b] > 1:
                    kept.discard((a, b))
                    degree[a] -= 1
                    degree[b] -= 1
                    dropped += 1
        if len(kept) <= budget:
            break
    if len(kept) > budget:
        raise ValueError(f"cannot reach edge budget {budget} with k >= 1 ({len(kept)} edges)")
    rows = sorted((a, b, weight[(a, b)]) for a, b in kept)
    retained = sum(w for _, _, w in rows)
    info = {
        "budget": budget,
        "start_k": start_k,
        "k_used": k,
        "edges_before": len(edges),
        "edges_after": len(rows),
        "weight_one_dropped": dropped,
        "weight_retained_share": round(retained / total, 4) if total else 0.0,
        "components_after": _component_count(node_count, rows),
    }
    return rows, info


def _component_count(node_count: int, edges: Sequence[tuple[int, int, int]]) -> int:
    """Connected components among nodes that have at least one edge."""
    import networkx as nx  # lazy, as in atlas.build.network

    graph = nx.Graph()
    graph.add_nodes_from(range(node_count))
    graph.add_edges_from((a, b) for a, b, _ in edges)
    return sum(1 for c in nx.connected_components(graph) if len(c) > 1)


def build_institution_graph(
    works_insts: Mapping[str, Sequence[str]],
    *,
    node_cap: int = NODE_CAP,
    max_institutions: int = MAX_INSTITUTIONS_PER_WORK,
    layout_iterations: int = LAYOUT_ITERATIONS,
    edge_budget: int = DESKTOP_EDGE_BUDGET,
    start_k: int = DESKTOP_START_K,
) -> dict[str, Any]:
    """Kept nodes (canonical order), thinned edges, communities and positions."""
    import networkx as nx  # lazy, as in atlas.build.network

    works, edges = co_occurrence(works_insts, max_institutions)
    component = _component_nodes(list(works), edges)
    kept_ids = sorted(component, key=lambda i: (-works[i], i))[:node_cap]
    index = {inst: i for i, inst in enumerate(kept_ids)}
    kept_edges = sorted(
        (min(index[a], index[b]), max(index[a], index[b]), w)
        for (a, b), w in edges.items()
        if a in index and b in index
    )
    thinned, thinning = thin_edges(kept_edges, len(kept_ids), budget=edge_budget, start_k=start_k)
    graph = nx.Graph()
    graph.add_nodes_from(range(len(kept_ids)))
    graph.add_weighted_edges_from(thinned)
    louvain = nx.algorithms.community.louvain_communities(graph, weight="weight", seed=SEED)
    ordered = sorted((sorted(c) for c in louvain), key=lambda c: (-len(c), c[0]))
    community_of = {node: k for k, members in enumerate(ordered) for node in members}
    positions = community_layout(len(kept_ids), thinned, ordered, iterations=layout_iterations)
    return {
        "ids": kept_ids,
        "works": [works[i] for i in kept_ids],
        "edges_unthinned": kept_edges,
        "edges": thinned,
        "thinning": thinning,
        "community": [community_of[i] for i in range(len(kept_ids))],
        "communities": len(ordered),
        "positions": positions,
        "component_nodes": len(component),
        "edge_pairs_total": len(edges),
    }


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return (text + "\n").encode("utf-8")


def _graph_payload(
    name: str,
    built: Mapping[str, Any],
    info: Mapping[str, tuple[Any, ...]],
    count: int,
    edges: Sequence[tuple[int, int, int]],
) -> dict[str, Any]:
    """Compact JSON for the first ``count`` nodes (canonical order) and the given edges."""
    node_rows = []
    for i in range(count):
        inst_id = built["ids"][i]
        name_, ror, country, kind = info[inst_id]
        node_rows.append(
            [inst_id, name_, ror, country, kind, built["works"][i], built["community"][i]]
        )
    edge_rows = [[a, b, w] for a, b, w in edges if a < count and b < count]
    return {
        "schema_version": SCHEMA_VERSION,
        "graph": name,
        "nodes": {"fields": list(NODE_FIELDS), "rows": node_rows},
        "edges": {"fields": list(EDGE_FIELDS), "rows": edge_rows},
        "communities": built["communities"],
    }


def _pack_positions(positions: Sequence[tuple[float, float]]) -> bytes:
    flat: list[float] = []
    for x, y in positions:
        flat.append(round(x, POSITION_DECIMALS))
        flat.append(round(y, POSITION_DECIMALS))
    return struct.pack(f"<{len(flat)}f", *flat)


def build_graphs(
    raw_dir: str | Path,
    *,
    node_cap: int = NODE_CAP,
    phone_cap: int = PHONE_NODE_CAP,
    max_institutions: int = MAX_INSTITUTIONS_PER_WORK,
    layout_iterations: int = LAYOUT_ITERATIONS,
    edge_budget: int = DESKTOP_EDGE_BUDGET,
    start_k: int = DESKTOP_START_K,
    phone_edge_budget: int = PHONE_EDGE_BUDGET,
    phone_start_k: int = PHONE_START_K,
) -> GraphBuild:
    """Build every file of the institutions graph set from the raw store."""
    works_insts, info, summary = read_raw_works(raw_dir)
    if not works_insts:
        raise ValueError("no works with institutions in the raw store")
    built = build_institution_graph(
        works_insts,
        node_cap=node_cap,
        max_institutions=max_institutions,
        layout_iterations=layout_iterations,
        edge_budget=edge_budget,
        start_k=start_k,
    )
    count = len(built["ids"])
    phone_count = min(phone_cap, count)
    phone_pairs = [e for e in built["edges_unthinned"] if e[0] < phone_count and e[1] < phone_count]
    phone_edges, phone_thinning = thin_edges(
        phone_pairs, phone_count, budget=phone_edge_budget, start_k=phone_start_k
    )
    full = _graph_payload(GRAPH_NAME, built, info, count, built["edges"])
    phone = _graph_payload(PHONE_GRAPH_NAME, built, info, phone_count, phone_edges)
    layout = _pack_positions(built["positions"])
    files = {
        GRAPH_NAME: _json_bytes(full),
        PHONE_GRAPH_NAME: _json_bytes(phone),
        "layout": layout,
    }
    sizes = {key: len(value) for key, value in files.items()}
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": summary.generated_at,
        "query_version": summary.query_version,
        "query_hash": summary.query_hash,
        "screening_status": SCREENING_STATUS,
        "what_this_is_and_is_not": WHAT_THIS_IS,
        "source": {
            "raw_pages": summary.pages,
            "works_distinct": summary.works,
            "works_with_institutions": summary.works_with_institutions,
            "institutions_seen": summary.institutions_seen,
            "component_institutions": built["component_nodes"],
            "institution_pairs_with_edges": built["edge_pairs_total"],
        },
        "caps": {
            "node_cap": node_cap,
            "phone_node_cap": phone_cap,
            "max_institutions_per_work_for_edges": max_institutions,
            "edge_rule": EDGE_RULE,
            "component_rule": COMPONENT_RULE,
            "edge_budget": edge_budget,
            "phone_edge_budget": phone_edge_budget,
            "thinning_rule": THINNING_RULE,
        },
        "seed": SEED,
        "graphs": {
            GRAPH_NAME: {
                "file": FILE_NAMES[GRAPH_NAME],
                "bytes": sizes[GRAPH_NAME],
                "nodes": count,
                "edges": len(built["edges"]),
                "thinning": built["thinning"],
                "communities": built["communities"],
                "community_method": COMMUNITY_METHOD,
                "layout_file": FILE_NAMES["layout"],
                "layout_bytes": sizes["layout"],
                "layout_method": LAYOUT_METHOD,
                "layout_iterations": layout_iterations,
                "layout_format": LAYOUT_FORMAT,
            },
            PHONE_GRAPH_NAME: {
                "file": FILE_NAMES[PHONE_GRAPH_NAME],
                "bytes": sizes[PHONE_GRAPH_NAME],
                "nodes": phone_count,
                "edges": len(phone_edges),
                "thinning": phone_thinning,
                "communities": built["communities"],
                "layout_file": FILE_NAMES["layout"],
                "layout_entries": f"the first {phone_count} entries of the layout file",
            },
        },
    }
    files["manifest"] = _json_bytes(manifest)
    return GraphBuild(files=files, manifest=manifest)


def check_outputs(out_dir: str | Path) -> list[str]:
    """Schema, cap and size problems in the committed files (empty list when all pass)."""
    out = Path(out_dir)
    problems: list[str] = []
    paths = {key: out / name for key, name in FILE_NAMES.items()}
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        return [f"missing: {', '.join(missing)}"]
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        problems.append("manifest schema_version is not bqv-v1")
    if manifest.get("screening_status") != SCREENING_STATUS:
        problems.append("manifest screening_status is not unscreened_query_hit")
    layout_size = paths["layout"].stat().st_size
    for graph_key, cap in ((GRAPH_NAME, NODE_CAP), (PHONE_GRAPH_NAME, PHONE_NODE_CAP)):
        payload = json.loads(paths[graph_key].read_text(encoding="utf-8"))
        rows = payload["nodes"]["rows"]
        entry = manifest["graphs"][graph_key]
        if payload.get("schema_version") != SCHEMA_VERSION or payload["nodes"]["fields"] != list(
            NODE_FIELDS
        ):
            problems.append(f"{graph_key}: schema mismatch")
        if len(rows) > cap or len(rows) != entry["nodes"]:
            problems.append(f"{graph_key}: node count {len(rows)} breaks cap {cap} or manifest")
        if paths[graph_key].stat().st_size != entry["bytes"]:
            problems.append(f"{graph_key}: manifest bytes are stale")
        for a, b, _ in payload["edges"]["rows"]:
            if not (0 <= a < len(rows) and 0 <= b < len(rows)) or a >= b:
                problems.append(f"{graph_key}: edge {a}-{b} out of range or unordered")
                break
    full = manifest["graphs"][GRAPH_NAME]
    if layout_size != 8 * full["nodes"] or full["layout_bytes"] != layout_size:
        problems.append("layout file length does not match 8 bytes per node")
    return problems
