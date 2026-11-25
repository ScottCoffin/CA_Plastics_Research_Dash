"""Degree-preserving null model and profile sensitivity for the collaboration networks (BQ-3.3).

The null asks whether the observed clustering, modularity and giant-component share are higher
than chance, given how many collaborators each member has. Each replicate rewires the observed
graph by random double-edge swaps. A swap removes links (a, b) and (c, d) and adds (a, d) and
(c, b), so every member keeps the same number of links, and each link keeps its shared-work count.
The same statistic functions as BQ-3.2 (``structure_metrics``) are applied to every replicate.

The sensitivity block reruns the observed statistics after two changes to how profiles are
grouped: (a) merging author nodes with the same normalized display name inside one component
(an over-merge), and (b) splitting a seeded 5% of authors with two or more collaborators into two
nodes that share their works at random. The output holds aggregates only.

Pure functions; no I/O.
"""

from __future__ import annotations

import random
import re
import statistics
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

import networkx as nx

from atlas.analytics.network_metrics import (
    WINDOWS,
    co_listed,
    in_window,
    plastic_works,
    structure_metrics,
)

NULL_SEED = 42
DEFAULT_REPLICATES = 100
SWAP_FACTOR = 10  # successful swaps per replicate = SWAP_FACTOR x number of links
MAX_TRIES_FACTOR = 20  # attempts per replicate are capped at MAX_TRIES_FACTOR x swaps
SPLIT_SHARE = 0.05
SPLIT_MIN_DEGREE = 2
DECIMALS = 4
# BQ-3.2 statistic keys that the null compares.
STATISTICS = ("average_clustering", "modularity", "giant_component_share")
SPLIT_SUFFIX = "|split"

NULL_METHOD = (
    "For each window, the observed network is compared with random networks that keep the same "
    "number of collaborators for every member. Each random network is made by repeatedly "
    "choosing two links and swapping their ends, so that the links move between the same "
    "members in a new pairing. Each replicate uses its own fixed seed, derived from one base "
    "seed, so the results repeat exactly. The score is the same as in the window table."
)
NULL_READING = (
    "z says how many standard deviations the observed value is from the average of the random "
    "networks. A large positive z means the network is more clustered, or more divided into "
    "groups, than its number of collaborators alone would produce. A z near 0 means the value is "
    "typical of chance. The two-sided p counts how often a random network lies at least as far "
    "from the average as the observed value, with a +1 correction. A z is not given when the "
    "random networks all give the same value."
)
NULL_LIMITS = (
    "The null keeps each member's number of collaborators but ignores the work they share, so it "
    "is a test of structure given degree only. Profiles may be split or merged: two people may "
    "appear as one member, or one person as two. The sensitivity block shows how much the "
    "statistics move under a crude over-merge and under a random split. The network covers only "
    "the Atlas corpus, so the null describes that corpus, not the whole field."
)

NameMap = Mapping[str, str]


def replicate_seeds(seed: int, replicates: int) -> list[int]:
    """One integer seed per replicate, all derived from the single base seed."""
    rng = random.Random(seed)
    return [rng.getrandbits(32) for _ in range(replicates)]


def _ends_key(edge: tuple[Any, Any, Any]) -> tuple[str, str]:
    """Sort key for an edge that ignores which end comes first."""
    first, second = sorted(str(x) for x in edge[:2])
    return first, second


def double_edge_swap(
    graph: nx.Graph, *, nswap: int, max_tries: int, rng: random.Random
) -> tuple[nx.Graph, int, int]:
    """Degree-preserving swaps that carry each link's weight with it.

    Returns the swapped graph, the number of successful swaps and the number of attempts. A swap
    is rejected when it would create a self-loop or a link that already exists.
    """
    # Canonical order: the swap sequence must not depend on node or edge insertion order (which
    # follows set iteration, and so the hash seed, when the graph is built).
    edges = []
    for u, v, d in sorted(graph.edges(data=True), key=_ends_key):
        a, b = sorted((u, v), key=str)
        edges.append([a, b, d.get("weight", 1)])
    present = {frozenset((u, v)) for u, v, _ in edges}
    m = len(edges)
    done = tries = 0
    while m >= 2 and done < nswap and tries < max_tries:
        tries += 1
        i, j = rng.randrange(m), rng.randrange(m)
        if i == j:
            continue
        a, b, wa = edges[i]
        c, d, wc = edges[j]
        if rng.random() < 0.5:
            c, d = d, c
        # Replace (a, b) and (c, d) with (a, d) and (c, b).
        if a == d or c == b:
            continue
        new_one, new_two = frozenset((a, d)), frozenset((c, b))
        if new_one == new_two or new_one in present or new_two in present:
            continue
        present -= {frozenset((a, b)), frozenset((c, d))}
        present |= {new_one, new_two}
        edges[i] = [a, d, wa]
        edges[j] = [c, b, wc]
        done += 1
    swapped = nx.Graph()
    swapped.add_nodes_from(sorted(graph.nodes(), key=str))
    swapped.add_weighted_edges_from((u, v, w) for u, v, w in edges)
    return swapped, done, tries


def _nodes_and_weights(graph: nx.Graph) -> tuple[set[str], dict[tuple[str, str], int]]:
    """Nodes and ``{(a, b): works}`` with a < b, as ``co_listed`` gives them.

    The orientation of each pair must not follow graph insertion order: Louvain's neighbour order
    changes with it, which changes the modularity by a few thousandths.
    """
    nodes = {str(n) for n in graph.nodes()}
    weights: dict[tuple[str, str], int] = {}
    for u, v, d in graph.edges(data=True):
        pair = tuple(sorted((str(u), str(v))))
        weights[pair] = int(d.get("weight", 1))
    return nodes, weights


def _no_flags(*_pair: str) -> tuple[None, None, None]:
    """BQ-3.2 edge flags are not part of the null; every edge is left unjudged."""
    return None, None, None


def _statistics(graph: nx.Graph) -> dict[str, Any]:
    nodes, weights = _nodes_and_weights(graph)
    full = structure_metrics(nodes, weights, _no_flags)
    return {key: full[key] for key in STATISTICS} | {"nodes": full["nodes"]}


def _round_or_none(value: float | None) -> float | None:
    return None if value is None else round(value, DECIMALS)


def _summarize(observed: float | None, values: Sequence[float | None]) -> dict[str, Any]:
    """Null mean, sd, z and two-sided empirical p for one statistic."""
    usable = [v for v in values if v is not None]
    mean = statistics.fmean(usable) if usable else None
    sd = statistics.stdev(usable) if len(usable) >= 2 else None
    z = None
    if observed is not None and mean is not None and sd:
        z = (observed - mean) / sd
    p = None
    if observed is not None and mean is not None and usable:
        gap = abs(observed - mean)
        count = sum(1 for v in usable if abs(v - mean) >= gap - 1e-12)
        p = (count + 1) / (len(usable) + 1)
    return {
        "observed": _round_or_none(observed),
        "null_mean": _round_or_none(mean),
        "null_sd": _round_or_none(sd),
        "z": _round_or_none(z),
        "p_two_sided": _round_or_none(p),
        "replicates_used": len(usable),
    }


def null_model(
    graph: nx.Graph,
    *,
    replicates: int = DEFAULT_REPLICATES,
    seed: int = NULL_SEED,
) -> dict[str, Any]:
    """Observed statistics and degree-preserving null summaries for one weighted graph."""
    if replicates < 1:
        raise ValueError("replicates must be at least 1")
    observed = _statistics(graph)
    nswap = SWAP_FACTOR * graph.number_of_edges()
    max_tries = MAX_TRIES_FACTOR * nswap
    rows: dict[str, list[float | None]] = {key: [] for key in STATISTICS}
    successes: list[int] = []
    attempts: list[int] = []
    for replicate_seed in replicate_seeds(seed, replicates):
        swapped, done, tries = double_edge_swap(
            graph, nswap=nswap, max_tries=max_tries, rng=random.Random(replicate_seed)
        )
        stats = _statistics(swapped)
        for key in STATISTICS:
            rows[key].append(stats[key])
        successes.append(done)
        attempts.append(tries)
    return {
        "replicates": replicates,
        "seed": seed,
        "nswap": nswap,
        "max_tries": max_tries,
        "swaps_succeeded": {
            "min": min(successes),
            "mean": round(statistics.fmean(successes), 1),
            "max": max(successes),
        },
        "attempts_mean": round(statistics.fmean(attempts), 1),
        "nodes": observed["nodes"],
        "edges": graph.number_of_edges(),
        "statistics": {key: _summarize(observed[key], rows[key]) for key in STATISTICS},
    }


# --- profile sensitivity -----------------------------------------------------------------------


def _name_key(name: str) -> str:
    """Lower-case ASCII words only, so 'Jo  Smith.' and 'jo smith' match."""
    return " ".join(re.findall(r"[a-z0-9]+", name.lower()))


def _merge_map(graph: nx.Graph, names: NameMap) -> dict[str, str]:
    """Each node maps to the smallest id sharing its component and normalized name."""
    component_of: dict[str, int] = {}
    components = sorted(sorted(c) for c in nx.connected_components(graph))
    for index, component in enumerate(components):
        for node in component:
            component_of[node] = index
    groups: dict[tuple[int, str], list[str]] = {}
    for node in sorted(graph.nodes()):
        key = _name_key(names.get(node, ""))
        if key:
            groups.setdefault((component_of[node], key), []).append(node)
    mapping: dict[str, str] = {}
    for members in groups.values():
        for node in members:
            mapping[node] = members[0]
    return mapping


def _variant(
    works: Sequence[Sequence[str]],
    member_of: Callable[[str, int], str],
    *,
    nodes_key: str,
) -> dict[str, Any]:
    """Rebuild co-listing with each work's authors mapped through ``member_of``."""
    mapped = []
    for index, work in enumerate(works):
        mapped.append({member_of(author, index) for author in work})
    nodes, weights = co_listed(mapped, lambda ids: ids)
    graph = nx.Graph()
    graph.add_nodes_from(nodes)
    graph.add_weighted_edges_from((a, b, w) for (a, b), w in weights.items())
    stats = _statistics(graph)
    return {nodes_key: stats["nodes"], "statistics": {k: stats[k] for k in STATISTICS}}


def _delta(variant: Mapping[str, Any], observed: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in STATISTICS:
        a, b = variant["statistics"][key], observed["statistics"][key]
        out[key] = None if a is None or b is None else round(a - b, DECIMALS)
    return out


def profile_sensitivity(
    works: Sequence[Iterable[str]],
    names: NameMap,
    *,
    seed: int = NULL_SEED,
    split_share: float = SPLIT_SHARE,
) -> dict[str, Any]:
    """Observed statistics and their changes after merging or splitting author profiles.

    ``works`` lists the author ids on each plastic-related work, in a fixed order. Merging uses
    the observed components, so it cannot join people across components. Splitting picks
    authors with degree >= 2 at random (seeded), and gives each of their works to one copy or
    the other at random. Only aggregates are returned.
    """
    works = [sorted(set(w)) for w in works]
    base_nodes, base_weights = co_listed(works, lambda ids: set(ids))
    observed_graph = nx.Graph()
    observed_graph.add_nodes_from(base_nodes)
    observed_graph.add_weighted_edges_from((a, b, w) for (a, b), w in base_weights.items())
    observed = _variant(works, lambda author, _i: author, nodes_key="nodes")

    mapping = _merge_map(observed_graph, names)
    merged = _variant(works, lambda author, _i: mapping.get(author, author), nodes_key="nodes")

    rng = random.Random(seed)
    candidates = sorted(n for n, d in observed_graph.degree() if d >= SPLIT_MIN_DEGREE)
    k = round(split_share * len(candidates))
    chosen = set(rng.sample(candidates, k)) if k else set()

    def split_member(author: str, _index: int) -> str:
        if author in chosen and rng.random() < 0.5:
            return author + SPLIT_SUFFIX
        return author

    split = _variant(works, split_member, nodes_key="nodes")
    return {
        "seed": seed,
        "observed": observed,
        "merge_same_name_within_component": {
            **merged,
            "merged_away": observed["nodes"] - merged["nodes"],
            "delta": _delta(merged, observed),
        },
        "split_authors": {
            **split,
            "authors_split": len(chosen),
            "split_share": split_share,
            "delta": _delta(split, observed),
        },
    }


def build_null_block(
    index: Mapping[str, Any],
    *,
    replicates: int = DEFAULT_REPLICATES,
    seed: int = NULL_SEED,
) -> dict[str, Any]:
    """The ``null_model`` block for the region's network_metrics.json (aggregates only)."""
    authors = list(index.get("authors") or [])
    works = list(index.get("works") or [])
    corpus = {str(a.get("author_id")) for a in authors}
    names = {str(a.get("author_id")): str(a.get("name") or "") for a in authors}
    plastic = plastic_works(works)

    def author_members(work: Mapping[str, Any]) -> set[str]:
        return {str(a) for a in work.get("author_ids") or [] if a} & corpus

    def institution_members(work: Mapping[str, Any]) -> set[str]:
        return {str(i) for i in work.get("institution_ids") or [] if i}

    graph_specs = (
        ("authors", "G-A", author_members),
        ("institutions", "G-I", institution_members),
    )
    graphs: dict[str, Any] = {}
    for key, label, members in graph_specs:
        rows = []
        for window, first, last, _partial in WINDOWS:
            subset = [w for w in plastic if in_window(w, first, last)]
            nodes, weights = co_listed(subset, members)
            graph = nx.Graph()
            graph.add_nodes_from(nodes)
            graph.add_weighted_edges_from((a, b, w) for (a, b), w in weights.items())
            rows.append({"window": window, **null_model(graph, replicates=replicates, seed=seed)})
        graphs[key] = {"label": label, "windows": rows}

    all_author_works = [sorted(author_members(w)) for w in plastic]
    sensitivity = profile_sensitivity(all_author_works, names, seed=seed)
    return {
        "method": NULL_METHOD,
        "reading": NULL_READING,
        "limits": NULL_LIMITS,
        "replicates": replicates,
        "seed": seed,
        "graphs": graphs,
        "sensitivity": {
            "label": "G-A, all years",
            **sensitivity,
        },
    }
