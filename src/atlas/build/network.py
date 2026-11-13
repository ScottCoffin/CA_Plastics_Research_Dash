"""Expert collaboration network (S9.4, spec Part E): co-authorship graph of California experts.

Built from the public ``site/data/index.json`` only (no raw data), so the result is
reproducible from committed files. Edge weight = number of co-authored plastic-related works
(Newman fractional counting optional). Louvain communities and a spring layout use fixed
seeds, so reruns give the same clusters and positions. ``networkx`` is imported lazily: it is
not yet a declared project dependency (QUESTIONS S9.4-DEP).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from itertools import combinations
from typing import Any

SCHEMA_VERSION = "s9.4-v1"
DEFAULT_NODE_CAP = 400
SEED = 42


def _plastic_works(works: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [w for w in works if w.get("plastic_related") is True]


def select_nodes(
    authors: Iterable[Mapping[str, Any]],
    works: Iterable[Mapping[str, Any]],
    cap: int = DEFAULT_NODE_CAP,
) -> list[str]:
    """Top ``cap`` experts by co-authored-or-not plastic works in the corpus, then citations.

    Only experts with at least one plastic-related work that has another Atlas expert on it
    are eligible (an isolated node carries no collaboration information).
    """
    collaborative: Counter[str] = Counter()
    for work in _plastic_works(works):
        ids = sorted({str(a) for a in work.get("author_ids") or [] if a})
        if len(ids) < 2:
            continue
        for author_id in ids:
            collaborative[author_id] += 1
    ranked = sorted(
        (a for a in authors if collaborative.get(str(a.get("author_id"))) or 0),
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


def build_network(
    index: Mapping[str, Any],
    institutions: Iterable[Mapping[str, Any]] = (),
    *,
    cap: int = DEFAULT_NODE_CAP,
    fractional: bool = False,
    generated_at: str = "",
) -> dict[str, Any]:
    """Network payload for ``site/data/network.json``."""
    import networkx as nx  # lazy: optional until S9.4-DEP is answered

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
    positions = nx.spring_layout(graph, weight="weight", seed=SEED, iterations=200)
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
            "layout": "spring layout (networkx), seed 42",
            "networkx": nx.__version__,
        },
        "communities": len(ordered),
        "nodes": node_rows,
        "edges": edge_rows,
    }
