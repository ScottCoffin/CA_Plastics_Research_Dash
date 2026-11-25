"""Expert collaboration network (S9.4, spec Part E): co-authorship graph of California experts.

Built from the public region ``index.json`` only (no raw data), so the result is
reproducible from committed files. Edge weight = number of co-authored plastic-related works
(Newman fractional counting optional). Louvain communities and a seeded spring layout use fixed
seeds, so reruns give the same clusters. The stored positions are a ForceAtlas2 layout started
from that spring layout (VD-20), so the page shows clusters on first load. ``networkx`` is a
declared project dependency; it is imported inside the functions that use it to keep importing
this module cheap.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from itertools import combinations
from typing import Any

SCHEMA_VERSION = "s9.4-v1.1"
DEFAULT_NODE_CAP = 400
SEED = 42
# ForceAtlas2 settings mirror graphology's inferSettings(graph) (the page's own "Re-run layout"):
# scaling ratio 10, strong gravity 0.05, node mass 1 + weighted degree, linear attraction.
LAYOUT_ITERATIONS = 1000
LAYOUT_SCALING_RATIO = 10.0
LAYOUT_GRAVITY = 0.05
# Community labels (VD-20): only communities with at least LABEL_MIN_SIZE experts are labelled.
LABEL_MIN_SIZE = 4
INSTITUTION_MIN_SHARE = 0.35
INSTITUTION_MIN_COUNT = 2
TOPIC_MIN_SHARE = 0.4
TOPIC_MIN_LIFT = 1.15


def _plastic_works(works: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [w for w in works if w.get("plastic_related") is True]


def select_nodes(
    authors: Iterable[Mapping[str, Any]],
    works: Iterable[Mapping[str, Any]],
    cap: int = DEFAULT_NODE_CAP,
) -> list[str]:
    """Top ``cap`` experts by co-authored-or-not plastic works in the corpus, then citations.

    Only experts with at least one plastic-related work that has another Atlas expert on it
    are eligible (an isolated node carries no collaboration information). Co-authors that are
    not in ``authors`` do not count as collaborators.
    """
    experts = list(authors)
    expert_ids = {str(a.get("author_id")) for a in experts}
    collaborative: Counter[str] = Counter()
    for work in _plastic_works(works):
        ids = sorted({str(a) for a in work.get("author_ids") or [] if a} & expert_ids)
        if len(ids) < 2:
            continue
        for author_id in ids:
            collaborative[author_id] += 1
    ranked = sorted(
        (a for a in experts if collaborative.get(str(a.get("author_id"))) or 0),
        key=lambda a: (
            -int(a.get("ca_plastic_works_count") or 0),
            -int(a.get("plastic_citations") or 0),
            str(a.get("author_id")),
        ),
    )
    return [str(a["author_id"]) for a in ranked[:cap]]


def edge_years(
    works: Iterable[Mapping[str, Any]], nodes: Iterable[str], *, fractional: bool = False
) -> dict[tuple[str, str], dict[int, float]]:
    """``{(a, b): {year: weight}}`` for node pairs that co-authored plastic-related works."""
    keep = set(nodes)
    out: dict[tuple[str, str], dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for work in _plastic_works(works):
        year = work.get("year")
        if not isinstance(year, int):
            continue
        ids = sorted({str(a) for a in work.get("author_ids") or [] if a} & keep)
        if len(ids) < 2:
            continue
        share = 1.0 / (len(ids) - 1) if fractional else 1.0
        for a, b in combinations(ids, 2):
            out[(a, b)][year] += share
    return {key: dict(value) for key, value in out.items()}


def _normalise(points: Mapping[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    """Centre the points on their bounding box and scale so the larger side spans [-1, 1]."""
    if not points:
        return {}
    xs = [x for x, _ in points.values()]
    ys = [y for _, y in points.values()]
    if not all(math.isfinite(value) for value in (*xs, *ys)):
        raise ValueError("ForceAtlas2 produced non-finite positions")
    cx = (max(xs) + min(xs)) / 2
    cy = (max(ys) + min(ys)) / 2
    half = max(max(xs) - min(xs), max(ys) - min(ys)) / 2
    if half <= 0:
        half = 1.0
    return {node: ((x - cx) / half, (y - cy) / half) for node, (x, y) in points.items()}


def forceatlas2_positions(
    graph: Any, start: Mapping[str, Any], *, iterations: int = LAYOUT_ITERATIONS
) -> dict[str, tuple[float, float]]:
    """ForceAtlas2 layout of ``graph`` from the ``start`` positions, normalised to [-1, 1].

    Deterministic: the start layout is seeded and networkx adds no randomness once ``pos`` is given.
    """
    import networkx as nx  # lazy: keeps module import cheap (networkx is a declared dependency)

    if graph.number_of_nodes() == 0:
        return {}
    mass = {node: 1.0 + float(strength) for node, strength in graph.degree(weight="weight")}
    raw = nx.forceatlas2_layout(
        graph,
        pos=dict(start),
        max_iter=iterations,
        jitter_tolerance=1.0,
        scaling_ratio=LAYOUT_SCALING_RATIO,
        gravity=LAYOUT_GRAVITY,
        strong_gravity=True,
        linlog=False,
        node_mass=mass,
        weight="weight",
    )
    return _normalise({node: (float(xy[0]), float(xy[1])) for node, xy in raw.items()})


def _home_institution(row: Mapping[str, Any]) -> str | None:
    """First primary affiliation; without one, the first institution other than 'System'."""
    primary = row.get("primary_affiliations") or []
    if primary and str(primary[0]).strip():
        return str(primary[0]).strip()
    for name in row.get("institutions") or []:
        text = str(name).strip()
        if text and text != "System":
            return text
    return None


def _institution_label(group: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    size = len(group)
    counts = Counter(name for name in (_home_institution(row) for row in group) if name)
    if not counts:
        return None
    # Most members first, then by name, so ties are stable.
    name, count = min(counts.items(), key=lambda item: (-item[1], item[0]))
    if count < INSTITUTION_MIN_COUNT or count / size < INSTITUTION_MIN_SHARE:
        return None
    return {"name": name, "share": round(count / size, 3)}


def _topic_label(
    group: Sequence[Mapping[str, Any]], expert_tags: Mapping[str, int], total: int
) -> dict[str, Any] | None:
    size = len(group)
    counts = Counter(tag for row in group for tag in set(row.get("topics") or []))
    best: tuple[tuple[float, float, str], str, float, float] | None = None
    for tag, count in counts.items():
        share = count / size
        if share < TOPIC_MIN_SHARE:
            continue
        # Lift = share in the community / share across all experts; one division keeps ties exact.
        lift = (count * total) / (size * expert_tags[tag])
        key = (-lift, -share, tag)
        if best is None or key < best[0]:
            best = (key, tag, share, lift)
    if best is None or best[3] < TOPIC_MIN_LIFT:
        return None
    _, tag, share, lift = best
    return {"tag": tag, "share": round(share, 3), "lift": round(lift, 3)}


def community_labels(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Algorithmic cluster names (VD-20) for communities of at least LABEL_MIN_SIZE experts.

    ``rows`` are the network node rows (each carries ``community``, ``topics``,
    ``primary_affiliations`` and ``institutions``). Output is ordered by community index; a label
    that fails its threshold is ``None``, so the page keeps "Cluster n" for it.
    """
    members: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        members[int(row["community"])].append(row)
    total = len(rows)
    expert_tags: Counter[str] = Counter(tag for row in rows for tag in set(row.get("topics") or []))
    labels = []
    for community in sorted(members):
        group = members[community]
        if len(group) < LABEL_MIN_SIZE:
            continue
        labels.append(
            {
                "community": community,
                "size": len(group),
                "institution": _institution_label(group),
                "topic": _topic_label(group, expert_tags, total),
            }
        )
    return labels


COMMUNITY_LABELS_METHOD = (
    f"Communities of at least {LABEL_MIN_SIZE} authors, in community order. Institution: the most "
    "common first primary affiliation among members (a member without one counts its first "
    "institution other than 'System'), kept when at least "
    f"{INSTITUTION_MIN_SHARE:.0%} of members and at least {INSTITUTION_MIN_COUNT} share it. "
    f"Topic: among tags on at least {TOPIC_MIN_SHARE:.0%} of members' topics, the one with the "
    "highest lift (share in the community divided by share across all authors), ties by share "
    f"then tag, kept when lift is at least {TOPIC_MIN_LIFT}. A null field means no label passed."
)
LAYOUT_METHOD = (
    "ForceAtlas2 (networkx), started from the spring layout (seed 42) and run for "
    f"{LAYOUT_ITERATIONS} iterations with scaling ratio {LAYOUT_SCALING_RATIO:g}, strong gravity "
    f"{LAYOUT_GRAVITY:g} and node mass 1 + weighted degree (graphology inferSettings); "
    "coordinates centred and scaled to [-1, 1]."
)


def build_network(
    index: Mapping[str, Any],
    institutions: Iterable[Mapping[str, Any]] = (),
    *,
    cap: int = DEFAULT_NODE_CAP,
    fractional: bool = False,
    generated_at: str = "",
) -> dict[str, Any]:
    """Network payload for the region's ``network.json``."""
    import networkx as nx  # lazy: keeps module import cheap (networkx is a declared dependency)

    authors = list(index.get("authors") or [])
    works = list(index.get("works") or [])
    by_id = {str(a.get("author_id")): a for a in authors}
    nodes = select_nodes(authors, works, cap)
    edges = edge_years(works, nodes, fractional=fractional)

    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    for (a, b), years in sorted(edges.items()):
        graph.add_edge(a, b, weight=sum(years.values()))
    communities = nx.algorithms.community.louvain_communities(graph, weight="weight", seed=SEED)
    # Largest community first, so community 0 is the biggest and colours are stable.
    ordered = sorted(communities, key=lambda c: (-len(c), min(c)))
    community_of = {node: index_ for index_, members in enumerate(ordered) for node in members}
    start = nx.spring_layout(graph, weight="weight", seed=SEED, iterations=200)
    positions = forceatlas2_positions(graph, start)
    strength = dict(graph.degree(weight="weight"))

    # Topics per expert = tags on their plastic-related works (author rows carry none).
    topic_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for work in _plastic_works(works):
        for author_id in {str(a) for a in work.get("author_ids") or []}:
            topic_counts[author_id].update(str(t) for t in work.get("domain_tags") or [] if t)

    inst_type = {str(i.get("inst_id")): str(i.get("atlas_type") or "") for i in institutions}
    inst_name = {str(i.get("inst_id")): str(i.get("name") or "") for i in institutions}

    node_rows = []
    for node in nodes:
        author = by_id[node]
        x, y = positions[node]
        institution_ids = [str(i) for i in author.get("institution_ids") or []]
        sectors = sorted({inst_type[i] for i in institution_ids if inst_type.get(i)})
        node_rows.append(
            {
                "id": node,
                "name": author.get("name") or node,
                "x": round(float(x), 4),
                "y": round(float(y), 4),
                "community": community_of[node],
                "degree": graph.degree(node),
                "strength": round(float(strength[node]), 3),
                "plastic_works": int(author.get("ca_plastic_works_count") or 0),
                "topics": [t for t, _ in topic_counts[node].most_common(5)]
                or list(author.get("domain_tags") or []),
                "institution_ids": institution_ids,
                "institutions": [inst_name[i] for i in institution_ids if inst_name.get(i)],
                "sectors": sectors,
                "primary_affiliations": list(author.get("primary_affiliations") or []),
                "current_in_ca": author.get("current_in_ca"),
            }
        )
    edge_rows = [
        {
            "source": a,
            "target": b,
            "weight": round(sum(years.values()), 3),
            "years": {str(y): round(w, 3) for y, w in sorted(years.items())},
        }
        for (a, b), years in sorted(edges.items())
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at or str(index.get("generated_at") or ""),
        "method": {
            "edge_weight": "fractional (Newman)" if fractional else "co-authored works",
            "works": "plastic-related works in the Atlas export",
            "node_cap": cap,
            "community": "Louvain (networkx), seed 42",
            "layout": LAYOUT_METHOD,
            "community_labels": COMMUNITY_LABELS_METHOD,
            "networkx": nx.__version__,
        },
        "communities": len(ordered),
        "community_labels": community_labels(node_rows),
        "nodes": node_rows,
        "edges": edge_rows,
    }


def _weight(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def network_counts(network: Mapping[str, Any]) -> dict[str, int]:
    """Headline counts the Collaboration network page shows with its default filters (VD-13).

    Mirrors network.js: experts are the nodes with a string id; links are the edges whose two
    ends are listed experts, that are not self-loops, and whose total weight is at least 1
    (the page's default minimum of one shared work).
    """
    raw_nodes = network.get("nodes")
    raw_edges = network.get("edges")
    nodes = [
        node
        for node in (raw_nodes if isinstance(raw_nodes, list) else [])
        if isinstance(node, Mapping) and isinstance(node.get("id"), str)
    ]
    ids = {node["id"] for node in nodes}
    links = 0
    for edge in raw_edges if isinstance(raw_edges, list) else []:
        if not isinstance(edge, Mapping):
            continue
        source, target = edge.get("source"), edge.get("target")
        if not (isinstance(source, str) and isinstance(target, str)):
            continue
        if (
            source in ids
            and target in ids
            and source != target
            and _weight(edge.get("weight")) >= 1
        ):
            links += 1
    return {"network_experts": len(nodes), "network_links": links}
