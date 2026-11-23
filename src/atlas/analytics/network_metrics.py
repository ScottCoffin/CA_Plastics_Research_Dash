"""Collaboration-structure metrics (BQ-3.2): author graph (G-A) and institution graph (G-I).

Built offline from committed site files. Plastic-related works in ``site/data/index.json`` are
split into year windows. In each window, G-A joins Atlas authors (the ``authors`` list) who are
listed together on a work, and G-I joins institutions listed together on a work (the work-level
``institution_ids``). Edge weight is the number of works in the window on which both ends are
listed. Louvain communities use a fixed seed, so the payload is deterministic for fixed inputs.

The payload holds aggregates only: no author ids, names or per-person values.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from itertools import combinations
from typing import Any

SCHEMA_VERSION = "bq3-v1"
SEED = 42
DECIMALS = 4
# (window id, first year, last year, partial). "all" holds every plastic-related work.
WINDOWS: tuple[tuple[str, int | None, int | None, bool], ...] = (
    ("all", None, None, False),
    ("2011-2015", 2011, 2015, False),
    ("2016-2020", 2016, 2020, False),
    ("2021-2025", 2021, 2025, False),
    ("2026", 2026, 2026, True),
)
# institutions.json gives every non-California institution the catch-all type "other", so that
# value is treated as unclassified and cross-sector is judged only where both ends have a sector.
UNCLASSIFIED_SECTORS = frozenset({"", "other"})
# Edge flags, in the order the classifier returns them.
FLAG_KEYS = ("cross_institution", "cross_sector", "out_of_region")

ASCERTAINMENT_NOTE = (
    "This build covers the California Atlas corpus only: the plastic-related works in the "
    "published index. The corpus is built around California authors; corpus.works_with_no_"
    "california_author counts plastic-related works in the file without one. Collaborators "
    "outside California appear only through works co-authored with California researchers. A "
    "co-author outside the Atlas authors list is therefore not a node, and a California author "
    "whose only plastic-related co-authors are outside that list is counted as an isolate. The "
    "metrics describe the collaboration structure around California plastics research as the "
    "Atlas records it. They do not describe the whole field and should not be compared with a "
    "graph built from a broader corpus."
)

DEFINITIONS = {
    "windows": (
        "Plastic-related works are grouped by publication year (year in index.json). 'all' holds "
        "every plastic-related work, including works before 2011 and works without a year. "
        "2011-2015, 2016-2020 and 2021-2025 are inclusive ranges. '2026' is partial: partial is "
        "true because the year was still running when the build ran. Works before 2011 appear "
        "only in 'all'."
    ),
    "author_graph": (
        "G-A. Nodes are Atlas authors (the authors list) listed on at least one plastic-related "
        "work in the window. An edge joins two such authors listed on the same work. Co-authors "
        "who are not in the authors list are not nodes and create no edges."
    ),
    "institution_graph": (
        "G-I. Nodes are institutions listed on at least one plastic-related work in the window "
        "(work-level institution_ids). An edge joins two institutions listed on the same work."
    ),
    "edge_weight": (
        "Number of plastic-related works in the window on which both ends are listed. Each work "
        "counts once per pair (co-authored work count, not fractional)."
    ),
    "nodes": "Nodes in the window graph, isolates included.",
    "edges": "Distinct pairs of nodes with at least one shared work in the window.",
    "components": ("Connected components of the window graph. Each isolate is its own component."),
    "components_with_edges": "Connected components with at least two nodes.",
    "giant_component": (
        "Largest connected component by node count. The share is its node count divided by all "
        "nodes."
    ),
    "density": (
        "Edges divided by all possible pairs, 2 x edges / (nodes x (nodes - 1)), isolates "
        "included. Null when there are fewer than two nodes."
    ),
    "average_clustering": (
        "Unweighted mean over all nodes of the local clustering coefficient: the share of a "
        "node's co-listed neighbour pairs that are themselves linked. A node with fewer than two "
        "neighbours, including every isolate, counts as 0 (networkx default)."
    ),
    "isolates": (
        "Nodes with no edge in the window. For authors: no other Atlas author on any "
        "plastic-related work dated in the window (single-author works, or works whose other "
        "authors are not in the authors list). For institutions: no other institution listed "
        "with it on any work in the window. The share is isolates divided by nodes."
    ),
    "degree": (
        "Number of distinct neighbours per node, unweighted, isolates included. Quantiles use "
        "linear interpolation between sorted values (min, 25th, median, 75th, 90th percentile, "
        "max)."
    ),
    "communities": (
        "Number of Louvain communities (networkx louvain_communities, edge weight as weight, "
        "seed 42) among the nodes that have at least one edge. Isolates are excluded."
    ),
    "modularity": (
        "Weighted Newman modularity of that Louvain partition, resolution 1. Null when the window "
        "has no edges. Isolates would not change it."
    ),
    "cross_institution": (
        "Share of edges whose two ends share no institution. Authors: no institution in common; "
        "an edge is considered only when both authors list an institution. Institutions: always "
        "1, because an institution edge joins two different institutions."
    ),
    "cross_sector": (
        "Share of edges whose two ends have different sectors. The sector is atlas_type in "
        "institutions.json; an author's sectors are those of their institutions, and the edge is "
        "cross-sector when the two authors share no sector. 'other' marks an institution without "
        "a sector (every non-California institution in the file carries it), so it is not used. "
        "An edge is considered only when both ends have a sector."
    ),
    "out_of_region": (
        "Share of edges with one end outside California: current_in_ca false for authors, "
        "ca_flag false for institutions. An edge is considered only when both ends are known "
        "(a null current_in_ca is not known)."
    ),
    "fractions": (
        "Each cross_institution, cross_sector and out_of_region object gives the fraction and "
        "edges_considered, the number of window edges where that flag can be evaluated. The "
        "fraction is null when no edge can be evaluated."
    ),
    "rounding": (
        "Fractions, density, clustering, modularity and quantiles are rounded to 4 decimal "
        "places. Counts are integers."
    ),
}

EdgeFlags = Callable[[str, str], tuple[bool | None, bool | None, bool | None]]


def plastic_works(works: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [w for w in works if w.get("plastic_related") is True]


def in_window(work: Mapping[str, Any], first: int | None, last: int | None) -> bool:
    """True for every work when ``first`` is None ('all'); otherwise a dated work in range."""
    if first is None:
        return True
    year = work.get("year")
    return isinstance(year, int) and first <= year <= (last if last is not None else first)


def _round(value: float) -> float:
    return round(float(value), DECIMALS)


def _share(part: int, whole: int) -> float | None:
    return _round(part / whole) if whole else None


def _flag(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _sector(row: Mapping[str, Any] | None) -> str | None:
    if not row:
        return None
    sector = str(row.get("atlas_type") or "").strip()
    return None if sector in UNCLASSIFIED_SECTORS else sector


def _quantiles(values: Sequence[int]) -> dict[str, float] | None:
    """Linear-interpolation quantiles of sorted ``values`` (numpy's default method)."""
    if not values:
        return None
    last = len(values) - 1

    def at(q: float) -> float:
        position = q * last
        low, high = math.floor(position), math.ceil(position)
        return _round(values[low] + (values[high] - values[low]) * (position - low))

    return {
        "min": at(0.0),
        "p25": at(0.25),
        "median": at(0.5),
        "p75": at(0.75),
        "p90": at(0.9),
        "max": at(1.0),
    }


def co_listed(
    works: Iterable[Mapping[str, Any]], members: Callable[[Mapping[str, Any]], set[str]]
) -> tuple[set[str], dict[tuple[str, str], int]]:
    """Nodes (every listed member) and ``{(a, b): works}`` for pairs listed on the same work."""
    nodes: set[str] = set()
    weights: dict[tuple[str, str], int] = {}
    for work in works:
        ids = sorted(members(work))
        nodes.update(ids)
        for pair in combinations(ids, 2):
            weights[pair] = weights.get(pair, 0) + 1
    return nodes, weights


def structure_metrics(
    nodes: set[str], weights: Mapping[tuple[str, str], int], classify: EdgeFlags
) -> dict[str, Any]:
    """Component, density, clustering, isolate, degree, community and edge-flag metrics."""
    import networkx as nx  # lazy: keeps module import cheap (networkx is a declared dependency)

    graph = nx.Graph()
    graph.add_nodes_from(sorted(nodes))
    graph.add_weighted_edges_from((a, b, w) for (a, b), w in sorted(weights.items()))
    n = graph.number_of_nodes()
    m = graph.number_of_edges()
    sizes = sorted((len(c) for c in nx.connected_components(graph)), reverse=True)
    degrees = sorted(d for _, d in graph.degree())
    isolates = sum(1 for d in degrees if d == 0)

    communities, modularity = 0, None
    if m:
        active = graph.subgraph([node for node, d in graph.degree() if d]).copy()
        partition = nx.community.louvain_communities(active, weight="weight", seed=SEED)
        communities = len(partition)
        modularity = _round(nx.community.modularity(active, partition, weight="weight"))

    considered = dict.fromkeys(FLAG_KEYS, 0)
    hits = dict.fromkeys(FLAG_KEYS, 0)
    for pair in weights:
        for key, flag in zip(FLAG_KEYS, classify(*pair), strict=True):
            if flag is None:
                continue
            considered[key] += 1
            hits[key] += int(flag)

    giant = sizes[0] if sizes else 0
    return {
        "nodes": n,
        "edges": m,
        "components": len(sizes),
        "components_with_edges": sum(1 for size in sizes if size >= 2),
        "giant_component_nodes": giant,
        "giant_component_share": _share(giant, n),
        "density": _round(2 * m / (n * (n - 1))) if n > 1 else None,
        "average_clustering": _round(nx.average_clustering(graph)) if n else None,
        "isolates": isolates,
        "isolate_share": _share(isolates, n),
        "degree": _quantiles(degrees),
        "communities": communities,
        "modularity": modularity,
        **{
            key: {
                "fraction": _share(hits[key], considered[key]),
                "edges_considered": considered[key],
            }
            for key in FLAG_KEYS
        },
    }


def _author_profiles(
    authors: Iterable[Mapping[str, Any]], institutions: Mapping[str, Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for author in authors:
        ids = {str(i) for i in author.get("institution_ids") or [] if i}
        sectors = {s for i in ids if (s := _sector(institutions.get(i)))}
        profiles[str(author.get("author_id"))] = {
            "institutions": ids,
            "sectors": sectors,
            "in_ca": _flag(author.get("current_in_ca")),
        }
    return profiles


def _author_flags(profiles: Mapping[str, Mapping[str, Any]]) -> EdgeFlags:
    def classify(a: str, b: str) -> tuple[bool | None, bool | None, bool | None]:
        pa, pb = profiles[a], profiles[b]
        ia, ib = pa["institutions"], pb["institutions"]
        sa, sb = pa["sectors"], pb["sectors"]
        cross_institution = ia.isdisjoint(ib) if ia and ib else None
        cross_sector = sa.isdisjoint(sb) if sa and sb else None
        if pa["in_ca"] is None or pb["in_ca"] is None:
            out_of_region = None
        else:
            out_of_region = not (pa["in_ca"] and pb["in_ca"])
        return cross_institution, cross_sector, out_of_region

    return classify


def _institution_flags(institutions: Mapping[str, Mapping[str, Any]]) -> EdgeFlags:
    def region(inst_id: str) -> bool | None:
        row = institutions.get(inst_id)
        return _flag(row.get("ca_flag")) if row else None

    def classify(a: str, b: str) -> tuple[bool | None, bool | None, bool | None]:
        sa, sb = _sector(institutions.get(a)), _sector(institutions.get(b))
        cross_sector = None if sa is None or sb is None else sa != sb
        ca_a, ca_b = region(a), region(b)
        out_of_region = None if ca_a is None or ca_b is None else not (ca_a and ca_b)
        # An institution edge always joins two different institutions, so this is 1 by construction.
        return True, cross_sector, out_of_region

    return classify


def _graph_windows(
    works: Sequence[Mapping[str, Any]],
    members: Callable[[Mapping[str, Any]], set[str]],
    classify: EdgeFlags,
) -> list[dict[str, Any]]:
    plastic = plastic_works(works)
    rows = []
    for window, first, last, partial in WINDOWS:
        subset = [w for w in plastic if in_window(w, first, last)]
        nodes, weights = co_listed(subset, members)
        row: dict[str, Any] = {
            "window": window,
            "years": None if first is None else [first, last if last is not None else first],
            "partial": partial,
            "works": len(subset),
        }
        row.update(structure_metrics(nodes, weights, classify))
        rows.append(row)
    return rows


def comparable(payload: Mapping[str, Any]) -> dict[str, Any]:
    """The payload without ``generated_at``, the only field --check ignores."""
    return {key: value for key, value in payload.items() if key != "generated_at"}


def build_metrics(
    index: Mapping[str, Any],
    institutions: Iterable[Mapping[str, Any]] = (),
    *,
    index_build_timestamp: str = "",
    generated_at: str = "",
) -> dict[str, Any]:
    """Payload for ``site/data/network_metrics.json`` (schema ``bq3-v1``)."""
    import networkx as nx  # lazy: keeps module import cheap (networkx is a declared dependency)

    authors = list(index.get("authors") or [])
    works = list(index.get("works") or [])
    inst_by_id = {str(i.get("inst_id")): i for i in institutions}
    corpus = {str(a.get("author_id")) for a in authors}
    plastic = plastic_works(works)

    def author_members(work: Mapping[str, Any]) -> set[str]:
        return {str(a) for a in work.get("author_ids") or [] if a} & corpus

    def institution_members(work: Mapping[str, Any]) -> set[str]:
        return {str(i) for i in work.get("institution_ids") or [] if i}

    author_rows = _graph_windows(
        works, author_members, _author_flags(_author_profiles(authors, inst_by_id))
    )
    institution_rows = _graph_windows(works, institution_members, _institution_flags(inst_by_id))
    years = [w.get("year") for w in plastic]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": {
            "index": "site/data/index.json",
            "index_build_timestamp": index_build_timestamp,
            "institutions": "site/data/institutions.json",
        },
        "method": {
            "edge_weight": DEFINITIONS["edge_weight"],
            "communities": "Louvain (networkx louvain_communities), seed 42",
            "rounding": DEFINITIONS["rounding"],
            "networkx": nx.__version__,
        },
        "ascertainment_note": ASCERTAINMENT_NOTE,
        "definitions": DEFINITIONS,
        "corpus": {
            "atlas_authors": len(corpus),
            "plastic_related_works": len(plastic),
            "works_in_year_windows": sum(
                1 for w in plastic if any(in_window(w, f, la) for _, f, la, _ in WINDOWS[1:])
            ),
            "works_before_2011": sum(1 for y in years if isinstance(y, int) and y < 2011),
            "works_without_year": sum(1 for y in years if not isinstance(y, int)),
            "works_with_no_california_author": sum(
                1 for w in plastic if w.get("ca_any_author") is not True
            ),
        },
        "graphs": {
            "authors": {
                "label": "G-A",
                "unit": "Atlas author",
                "windows": author_rows,
            },
            "institutions": {
                "label": "G-I",
                "unit": "institution",
                "windows": institution_rows,
            },
        },
    }
