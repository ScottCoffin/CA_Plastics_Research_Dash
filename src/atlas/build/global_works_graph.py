"""Global WORKS graph (BQ-V.1 slice 3): k-nearest-neighbour similarity on title and abstract.

Input: the ignored raw global store (``data/raw/openalex_global/pages``). A work is a candidate
when a pollution-core v0 term matches its title or abstract (the backbone rule of
``atlas.build.global_graphs``) and its title or abstract text is non-empty. The latest raw page
holding a work decides whether it is a candidate.

Candidates are sorted by (cited-by count desc, OpenAlex id); the first ``WORKS_NODE_CAP`` are
embedded (BAAI/bge-small-en-v1.5 by default, L2-normalised, so dot product = cosine). Each node
keeps its ``KNN_K`` most similar other nodes (ties: lower node index); edges are the union of those
pairs, weighted by the cosine rounded to 3 decimals. The phone graph is the first
``WORKS_PHONE_NODE_CAP`` nodes with its own kNN (``PHONE_KNN_K``) computed inside that subset.

Only ids, titles (truncated), years, citation counts and an embedding-quality flag are written.
Abstracts and texts are held in memory for embedding only and are never written.

Communities: seeded Louvain (networkx) on the desktop graph. Layout: ``community_layout`` from
``atlas.build.global_graphs`` (same ForceAtlas2 settings as the other global graphs).
"""

from __future__ import annotations

import gzip
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atlas.analytics.denominators import load_pollution_core
from atlas.build.global_graphs import (
    DESKTOP_EDGE_BUDGET,
    EDGE_FIELDS,
    FORBIDDEN_KEYS,
    LAYOUT_FORMAT,
    LAYOUT_ITERATIONS,
    LAYOUT_METHOD,
    PHONE_EDGE_BUDGET,
    SCHEMA_VERSION,
    SCREENING_STATUS,
    SEED,
    GraphBuild,
    _abstract_text,
    _forbidden_key_hits,
    _iter_works,
    _json_bytes,
    _ordered_pages,
    _pack_positions,
    _short_id,
    backbone_pattern,
    community_layout,
)
from atlas.nlp.active_relevance import DEFAULT_MODEL, Embedder, embed_cached

GRAPH_NAME = "works"
PHONE_GRAPH_NAME = "works_phone"
WORKS_NODE_CAP = 15_000
WORKS_PHONE_NODE_CAP = 5_000
KNN_K = 5
PHONE_KNN_K = 3
KNN_BLOCK_ROWS = 2048
TITLE_MAX_CHARS = 160
MAX_DESKTOP_GZIP_BYTES = 2_000_000
WORKS_NODE_FIELDS = ("id", "title", "year", "cited_by_count", "embedding_quality", "community")
WORKS_FORBIDDEN_KEYS = FORBIDDEN_KEYS | {"abstract", "text"}
DEFAULT_CACHE_PATH = Path("data/interim/embeddings/global_works_bge_small.npz")
FILE_NAMES = {
    GRAPH_NAME: "works.json",
    PHONE_GRAPH_NAME: "works_phone.json",
    "layout": "layout_works.bin",
    "manifest": "works_manifest.json",
}
WORKS_WHAT_THIS_IS = (
    "Similarity graph of unscreened global OpenAlex query hits on the pollution-core backbone "
    "(plastic query version in this manifest). A node is a work; an edge joins two works whose "
    "title-and-abstract embeddings are among each other's most similar works, and its weight is "
    "their cosine similarity. It is not a citation network, not a screened corpus and not a "
    "measure of quality. It holds no abstracts, author names, author IDs, ORCIDs or institution "
    "strings. The desktop file holds the 15,000 most cited backbone works; the phone file is the "
    "first 5,000 of them."
)
SELECTION_RULE = (
    "A work is a candidate when a pollution-core v0 term matches its title or abstract (whole "
    "word, case-insensitive) and its title or abstract is non-empty. The latest raw page holding "
    "a work decides it. Candidates are sorted by cited-by count (most first, ties by OpenAlex id); "
    "the first 15,000 are embedded and kept."
)
SIMILARITY_RULE = (
    f"Text is the title and abstract. Embeddings come from {DEFAULT_MODEL} (an English model), "
    "L2-normalised; similarity is the cosine. Each node keeps its 5 most similar other nodes "
    "(ties: lower node index); edges are the union of those pairs, weight rounded to 3 decimals. "
    "The phone file recomputes the 3 most similar nodes inside its 5,000 nodes alone. Over the "
    "BQ-V.0 edge budget (desktop 60,000, phone 15,000), the weakest edges (ties: higher node "
    "indices first) are dropped while both ends keep another edge."
)
QUALITY_RULE = (
    "embedding_quality is ok when the language is en and low otherwise. The model is English-only, "
    "so non-English works are kept and marked low rather than dropped."
)
COMMUNITY_METHOD = (
    "Louvain (networkx) on the weighted kNN graph, seed 42; community 0 is the largest. Negative "
    "similarities are clipped to 0 for community detection only."
)
TITLE_RULE = (
    "title is the stored title, truncated to 160 characters (159 plus an ellipsis when longer)."
)


class EmbeddingCacheIncomplete(RuntimeError):
    """Raised by the check-mode embedder when a vector is missing from the cache."""


@dataclass(frozen=True)
class WorkCandidate:
    """One backbone work with text. ``text`` is held in memory for embedding and never written."""

    id: str
    title: str
    publication_year: int | None
    cited_by_count: int
    language: str | None
    text: str


@dataclass(frozen=True)
class WorkRead:
    candidates: tuple[WorkCandidate, ...]
    works_distinct: int
    pages: int
    query_version: str
    query_hash: str
    generated_at: str


def _candidate(work_id: str, work: Mapping[str, Any], pattern: Any) -> WorkCandidate | None:
    title = str(work.get("title") or "").strip()
    abstract = _abstract_text(work.get("abstract_inverted_index"))
    text = f"{title} {abstract}".strip()
    if not text or not pattern.search(text):
        return None
    year = work.get("publication_year")
    cited = work.get("cited_by_count")
    language = work.get("language")
    language_text = language.strip() if isinstance(language, str) else ""
    return WorkCandidate(
        id=work_id,
        title=title,
        publication_year=year if isinstance(year, int) and not isinstance(year, bool) else None,
        cited_by_count=cited if isinstance(cited, int) and not isinstance(cited, bool) else 0,
        language=language_text or None,
        text=text,
    )


def read_works(raw_dir: str | Path, core_terms: Sequence[str]) -> WorkRead:
    """Backbone candidates with text; pages in fetch-time order, so the latest page wins."""
    headers, query_version, query_hash = _ordered_pages(raw_dir)
    pattern = backbone_pattern(core_terms)
    latest: dict[str, WorkCandidate] = {}
    seen: set[str] = set()
    for _, path in headers:
        for work in _iter_works(path):
            work_id = _short_id(work.get("id"))
            if work_id is None:
                continue
            seen.add(work_id)
            candidate = _candidate(work_id, work, pattern)
            if candidate is None:
                latest.pop(work_id, None)
            else:
                latest[work_id] = candidate
    return WorkRead(
        candidates=tuple(latest[i] for i in sorted(latest)),
        works_distinct=len(seen),
        pages=len(headers),
        query_version=query_version,
        query_hash=query_hash,
        generated_at=str(max(str(h.get("fetched_utc") or "") for h, _ in headers)),
    )


def ordered_candidates(candidates: Sequence[WorkCandidate]) -> list[WorkCandidate]:
    """Cited-by count descending, then OpenAlex id; the desktop and phone sets are prefixes."""
    return sorted(candidates, key=lambda c: (-c.cited_by_count, c.id))


def _unit_rows(matrix: Any) -> Any:
    import numpy as np

    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


def knn_edges(
    vectors: Any,
    k: int,
    *,
    block_rows: int = KNN_BLOCK_ROWS,
) -> list[tuple[int, int, float]]:
    """Undirected union of each node's k most similar other nodes, as (a, b, weight), a < b.

    ``vectors`` are L2-normalised rows, so the dot product is the cosine. Ties go to the lower
    node index. Similarities are computed in blocks of ``block_rows`` rows to bound memory.
    The weight is the cosine rounded to 3 decimals, taken from the lower node's row when both
    rows select the pair.
    """
    import numpy as np

    if k < 1:
        raise ValueError("k must be at least 1")
    n = int(vectors.shape[0])
    if n < 2:
        return []
    kk = min(k, n - 1)
    weights: dict[tuple[int, int], float] = {}
    for start in range(0, n, block_rows):
        stop = min(start + block_rows, n)
        sims = vectors[start:stop] @ vectors.T
        for local, node in enumerate(range(start, stop)):
            row = sims[local].astype(np.float64)
            row[node] = -np.inf
            kth = np.partition(row, n - kk)[n - kk]
            above = np.flatnonzero(row > kth)
            ties = np.flatnonzero(row == kth)[: kk - above.size]
            for other in np.concatenate((above, ties)).tolist():
                key = (min(node, other), max(node, other))
                if key not in weights or node == key[0]:
                    weights[key] = round(float(row[other]), 3)
    return [(a, b, w) for (a, b), w in sorted(weights.items())]


def fit_budget(edges: list[tuple[int, int, float]], budget: int) -> list[tuple[int, int, float]]:
    """Drop the weakest edges until ``len(edges) <= budget``, never leaving a node without one.

    Weakest first; ties drop the pair with the higher indices first. Edges whose removal would
    isolate an end are kept, so the result can stay above the budget. Output keeps input order.
    """
    if len(edges) <= budget:
        return edges
    degree: dict[int, int] = {}
    for a, b, _ in edges:
        degree[a] = degree.get(a, 0) + 1
        degree[b] = degree.get(b, 0) + 1
    order = sorted(range(len(edges)), key=lambda i: (edges[i][2], -edges[i][0], -edges[i][1]))
    dropped: set[int] = set()
    excess = len(edges) - budget
    for i in order:
        if len(dropped) >= excess:
            break
        a, b, _ = edges[i]
        if degree[a] > 1 and degree[b] > 1:
            degree[a] -= 1
            degree[b] -= 1
            dropped.add(i)
    return [edge for i, edge in enumerate(edges) if i not in dropped]


def display_title(title: str) -> str:
    if len(title) <= TITLE_MAX_CHARS:
        return title
    return title[: TITLE_MAX_CHARS - 1] + "…"


def embedding_quality(language: str | None) -> str:
    return "ok" if language == "en" else "low"


def _no_embedding(texts: Sequence[str]) -> Any:
    raise EmbeddingCacheIncomplete(f"{len(texts)} text(s) missing from the embedding cache")


def _lazy_sentence_transformer(texts: Sequence[str]) -> Any:
    """Default embedder: the model is imported and loaded only when a vector is missing."""
    from atlas.nlp.active_relevance import sentence_transformer_embedder

    return sentence_transformer_embedder(DEFAULT_MODEL)(texts)


def _works_payload(
    name: str,
    members: Sequence[WorkCandidate],
    communities: Sequence[int],
    edges: Sequence[tuple[int, int, float]],
) -> dict[str, Any]:
    rows = [
        [
            c.id,
            display_title(c.title),
            c.publication_year,
            c.cited_by_count,
            embedding_quality(c.language),
            communities[i],
        ]
        for i, c in enumerate(members)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "graph": name,
        "screening_status": SCREENING_STATUS,
        # Same shape as institutions.json and authors.json, so the graph viewer reads it as is.
        "communities": len(set(communities)),
        "nodes": {"fields": list(WORKS_NODE_FIELDS), "rows": rows},
        "edges": {"fields": list(EDGE_FIELDS), "rows": [[a, b, w] for a, b, w in edges]},
    }


def build_works_graph(
    raw_dir: str | Path,
    *,
    embedder: Embedder | None = None,
    cache_path: str | Path | None = None,
    node_cap: int = WORKS_NODE_CAP,
    phone_cap: int = WORKS_PHONE_NODE_CAP,
    k: int = KNN_K,
    phone_k: int = PHONE_KNN_K,
    layout_iterations: int = LAYOUT_ITERATIONS,
    pollution_core: Mapping[str, Any] | None = None,
) -> GraphBuild:
    """Serialised works graph files and manifest from the raw store.

    ``embedder=None`` loads the sentence-transformers model, only when the cache lacks a vector.
    """
    import networkx as nx

    core = pollution_core if pollution_core is not None else load_pollution_core()
    read = read_works(raw_dir, list(core["core_terms"]))
    if not read.candidates:
        raise ValueError("no backbone works with text in the raw store")
    ordered = ordered_candidates(read.candidates)
    desktop = ordered[:node_cap]
    phone = desktop[:phone_cap]

    cache = DEFAULT_CACHE_PATH if cache_path is None else Path(cache_path)
    cache.parent.mkdir(parents=True, exist_ok=True)
    import numpy as np

    encoder = embedder if embedder is not None else _lazy_sentence_transformer
    vectors, _ = embed_cached({c.id: c.text for c in desktop}, encoder, cache)
    matrix = _unit_rows(np.stack([np.asarray(vectors[c.id], dtype=np.float32) for c in desktop]))
    count = len(desktop)
    desktop_edges = fit_budget(knn_edges(matrix, k), DESKTOP_EDGE_BUDGET)
    phone_edges = fit_budget(knn_edges(matrix[: len(phone)], phone_k), PHONE_EDGE_BUDGET)

    graph = nx.Graph()
    graph.add_nodes_from(range(count))
    graph.add_weighted_edges_from((a, b, max(w, 0.0)) for a, b, w in desktop_edges)
    louvain = nx.algorithms.community.louvain_communities(graph, weight="weight", seed=SEED)
    ordered_comm = sorted((sorted(c) for c in louvain), key=lambda c: (-len(c), c[0]))
    community_of = {node: index for index, members in enumerate(ordered_comm) for node in members}
    communities = [community_of[i] for i in range(count)]
    positions = community_layout(count, desktop_edges, ordered_comm, iterations=layout_iterations)

    desktop_payload = _works_payload(GRAPH_NAME, desktop, communities, desktop_edges)
    phone_payload = _works_payload(PHONE_GRAPH_NAME, phone, communities[: len(phone)], phone_edges)
    files = {
        GRAPH_NAME: _json_bytes(desktop_payload),
        PHONE_GRAPH_NAME: _json_bytes(phone_payload),
        "layout": _pack_positions(positions),
    }
    low = sum(1 for c in desktop if embedding_quality(c.language) == "low")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "query_version": read.query_version,
        "query_hash": read.query_hash,
        "generated_at": read.generated_at,
        "screening_status": SCREENING_STATUS,
        "model": DEFAULT_MODEL,
        "k": k,
        "phone_k": phone_k,
        "caps": {"desktop_node_cap": node_cap, "phone_node_cap": phone_cap},
        "counts": {
            "works_distinct": read.works_distinct,
            "candidates": len(read.candidates),
            "desktop_nodes": count,
            "phone_nodes": len(phone),
            "desktop_edges": len(desktop_edges),
            "phone_edges": len(phone_edges),
            "communities": len(ordered_comm),
            "low_quality_nodes": low,
        },
        "source": {"raw_pages": read.pages},
        "seed": SEED,
        "what_this_is": WORKS_WHAT_THIS_IS,
        "selection_rule": SELECTION_RULE,
        "similarity_rule": SIMILARITY_RULE,
        "quality_rule": QUALITY_RULE,
        "title_rule": TITLE_RULE,
        "community_method": COMMUNITY_METHOD,
        "layout_method": LAYOUT_METHOD,
        "layout_iterations": layout_iterations,
        "layout_format": LAYOUT_FORMAT,
        # Per-graph entries in the shape of graphs_manifest.json `graphs`, for the viewer.
        "graphs": {
            GRAPH_NAME: {
                "file": FILE_NAMES[GRAPH_NAME],
                "layout_file": FILE_NAMES["layout"],
                "nodes": count,
                "edges": len(desktop_edges),
                "communities": len(ordered_comm),
            },
            PHONE_GRAPH_NAME: {
                "file": FILE_NAMES[PHONE_GRAPH_NAME],
                "layout_file": FILE_NAMES["layout"],
                "nodes": len(phone),
                "edges": len(phone_edges),
                "communities": len(set(communities[: len(phone)])),
            },
        },
        "files": {
            name: {"bytes": len(data), "gzip_bytes": len(gzip.compress(data, mtime=0))}
            for name, data in (
                (FILE_NAMES[GRAPH_NAME], files[GRAPH_NAME]),
                (FILE_NAMES[PHONE_GRAPH_NAME], files[PHONE_GRAPH_NAME]),
                (FILE_NAMES["layout"], files["layout"]),
            )
        },
    }
    files["manifest"] = _json_bytes(manifest)
    return GraphBuild(files=files, manifest=manifest)


def rebuild_for_check(raw_dir: str | Path, cache_path: str | Path) -> GraphBuild | None:
    """Rebuild from the raw store and the cache only; None when any vector is not cached.

    The embedder raises instead of embedding, so no model is loaded and nothing is written.
    """
    try:
        return build_works_graph(raw_dir, embedder=_no_embedding, cache_path=cache_path)
    except EmbeddingCacheIncomplete:
        return None


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("not a JSON object")
    return data


def check_works_outputs(out_dir: str | Path) -> list[str]:
    """Schema, cap, count, edge and size problems in the works files (empty when all pass)."""
    out = Path(out_dir)
    paths = {key: out / name for key, name in FILE_NAMES.items()}
    missing = [str(p) for p in paths.values() if not p.exists()]
    if missing:
        return [f"missing: {', '.join(missing)}"]
    problems: list[str] = []
    try:
        manifest = _load_json(paths["manifest"])
        desktop = _load_json(paths[GRAPH_NAME])
        phone = _load_json(paths[PHONE_GRAPH_NAME])
    except (OSError, ValueError) as error:
        return [f"unreadable works file: {error}"]
    if manifest.get("schema_version") != SCHEMA_VERSION:
        problems.append("manifest schema_version is not bqv-v1")
    if manifest.get("screening_status") != SCREENING_STATUS:
        problems.append("manifest screening_status is not unscreened_query_hit")
    counts = manifest.get("counts") or {}
    files = manifest.get("files") or {}
    layout_size = paths["layout"].stat().st_size
    if files.get(FILE_NAMES["layout"], {}).get("bytes") != layout_size:
        problems.append("manifest layout bytes are stale")

    desk_rows = (desktop.get("nodes") or {}).get("rows") or []
    phone_rows = (phone.get("nodes") or {}).get("rows") or []
    for key, payload, rows, cap, k_value in (
        (GRAPH_NAME, desktop, desk_rows, WORKS_NODE_CAP, manifest.get("k")),
        (PHONE_GRAPH_NAME, phone, phone_rows, WORKS_PHONE_NODE_CAP, manifest.get("phone_k")),
    ):
        if payload.get("schema_version") != SCHEMA_VERSION or payload.get("graph") != key:
            problems.append(f"{key}: schema or graph name mismatch")
        if payload.get("screening_status") != SCREENING_STATUS:
            problems.append(f"{key}: screening_status mismatch")
        if (payload.get("nodes") or {}).get("fields") != list(WORKS_NODE_FIELDS):
            problems.append(f"{key}: nodes.fields mismatch")
        if (payload.get("edges") or {}).get("fields") != list(EDGE_FIELDS):
            problems.append(f"{key}: edges.fields mismatch")
        entry = (manifest.get("graphs") or {}).get(key) or {}
        if entry.get("nodes") != len(rows) or entry.get("file") != FILE_NAMES[key]:
            problems.append(f"{key}: manifest graphs entry is stale")
        if len(rows) > cap:
            problems.append(f"{key}: {len(rows)} nodes break cap {cap}")
        if not all(isinstance(r, list) and len(r) == len(WORKS_NODE_FIELDS) for r in rows):
            problems.append(f"{key}: node rows do not match node_fields")
        elif any(len(str(r[1])) > TITLE_MAX_CHARS for r in rows):
            problems.append(f"{key}: title longer than {TITLE_MAX_CHARS} characters")
        elif any(r[4] not in ("ok", "low") for r in rows):
            problems.append(f"{key}: embedding_quality must be ok or low")
        edges = (payload.get("edges") or {}).get("rows") or []
        n = len(rows)
        if any(not (isinstance(e, list) and len(e) == 3 and 0 <= e[0] < e[1] < n) for e in edges):
            problems.append(f"{key}: edge index out of range or not source < target")
        degree = [0] * n
        for a, b, _ in edges:
            if 0 <= a < n and 0 <= b < n:
                degree[a] += 1
                degree[b] += 1
        # The edge budget may trim a node below k neighbours, never below one.
        if isinstance(k_value, int) and n > 1 and min(degree) < 1:
            problems.append(f"{key}: a node has no edge")
        forbidden = sorted(_forbidden_key_hits(payload))
        if forbidden:
            problems.append(f"{key}: forbidden fields {forbidden}")
        data = paths[key].read_bytes()
        if files.get(FILE_NAMES[key], {}).get("bytes") != len(data):
            problems.append(f"{key}: manifest bytes are stale")
    if manifest.get("model") != DEFAULT_MODEL:
        problems.append("manifest model is not the default model")
    if _forbidden_key_hits(manifest):
        problems.append("manifest has forbidden fields")

    desk_ids = [r[0] for r in desk_rows]
    if [r[0] for r in phone_rows] != desk_ids[: len(phone_rows)]:
        problems.append("phone nodes are not the first desktop nodes")
    if layout_size != 8 * len(desk_rows):
        problems.append("layout file length does not match 8 bytes per node")
    if len(gzip.compress(paths[GRAPH_NAME].read_bytes(), mtime=0)) > MAX_DESKTOP_GZIP_BYTES:
        problems.append("desktop works.json gzip is over the size limit")

    expected = {
        "desktop_nodes": len(desk_rows),
        "phone_nodes": len(phone_rows),
        "desktop_edges": len((desktop.get("edges") or {}).get("rows") or []),
        "phone_edges": len((phone.get("edges") or {}).get("rows") or []),
        "communities": len({r[5] for r in desk_rows}),
        "low_quality_nodes": sum(1 for r in desk_rows if r[4] == "low"),
    }
    for name, value in expected.items():
        if counts.get(name) != value:
            problems.append(f"manifest count {name} does not match the files")
    return problems
