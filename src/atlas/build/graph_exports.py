"""Graph exports (BQ-V.6): GEXF and GraphML copies of the committed graph files.

Inputs (committed, offline): the desktop global graphs ``institutions.json`` and ``authors.json``
with their ``layout_*.bin`` positions and ``graphs_manifest.json`` (BQ-V.1), and the expert
network file ``network.json`` (passed in as ``network_path``). Outputs go to ``exports/``: one GEXF
and one GraphML file per graph, and ``exports/manifest.json``. A file above
``GZIP_THRESHOLD_BYTES`` (5 MB) is committed gzipped only (``*.gz``, about 1 MB instead of 10 to
12 MB); the manifest records the uncompressed size and hash. The phone subsets are not exported.

Only the attributes in ``NODE_FIELD_MAP`` (and the expert node name, works and community) are
written: no emails, affiliation strings, ORCIDs or institution lists.

Determinism: nodes sorted by id, edges by endpoint ids, positions rounded to four decimals, gzip
with mtime 0, and the GEXF ``lastmodifieddate`` set to the date of ``generated_at`` (networkx would
otherwise write today's date).
The GEXF creator line is pinned so networkx versions give identical bytes.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx

SCHEMA_VERSION = "bqv6-v1"
LICENCE = "CC BY-NC 4.0 derived from OpenAlex (CC0)"
SCREENING_NOTE = "unscreened search hits: not screened for relevance and not a measure of quality"
GZIP_THRESHOLD_BYTES = 5_000_000
POSITION_DECIMALS = 4
FORMATS = ("gexf", "graphml")
MANIFEST_NAME = "manifest.json"
GLOBAL_STEMS = ("institutions", "authors")
CALIFORNIA_STEM = "california_network"
NODE_FIELD_MAP = {
    "display_name": "label",
    "country_code": "country",
    "ror": "ror",
    "type": "type",
    "works": "works",
    "community": "community",
}
FORBIDDEN_ATTRIBUTES = frozenset(
    {
        "email",
        "emails",
        "affiliation",
        "affiliations",
        "raw_affiliation_strings",
        "orcid",
        "observed_orcids",
        "institutions",
        "institution_ids",
        "primary_affiliations",
        "current_in_ca",
    }
)
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class ExportGraph:
    """A graph ready to serialise: nodes and edges sorted, metadata in a fixed order."""

    stem: str
    nodes: tuple[dict[str, Any], ...]  # each has "id", "x", "y" and whitelisted attributes
    edges: tuple[tuple[str, str, int | float], ...]
    metadata: tuple[tuple[str, str], ...]
    generated_at: str


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _layout(path: Path, count: int) -> list[tuple[float, float]]:
    raw = path.read_bytes()
    if len(raw) != 8 * count:
        raise ValueError(f"{path.name}: {len(raw)} bytes, expected {8 * count} for {count} nodes")
    values = struct.unpack(f"<{2 * count}f", raw)
    return [
        (
            round(float(values[2 * i]), POSITION_DECIMALS),
            round(float(values[2 * i + 1]), POSITION_DECIMALS),
        )
        for i in range(count)
    ]


def _metadata(source: str, generated_at: str, what_this_is: str) -> tuple[tuple[str, str], ...]:
    return (
        ("source", source),
        ("generated_at", generated_at),
        ("licence", LICENCE),
        ("screening", SCREENING_NOTE),
        ("what_this_is", what_this_is),
    )


def _assemble(
    stem: str,
    records: list[dict[str, Any]],
    positions: list[tuple[float, float]],
    edges: list[tuple[str, str, int | float]],
    metadata: tuple[tuple[str, str], ...],
    generated_at: str,
) -> ExportGraph:
    nodes = []
    for record, (x, y) in zip(records, positions, strict=True):
        node: dict[str, Any] = {"id": str(record["id"]), "x": x, "y": y}
        for field, attribute in NODE_FIELD_MAP.items():
            value = record.get(field)
            if value is not None:
                node[attribute] = value
        if FORBIDDEN_ATTRIBUTES & set(node):
            raise ValueError(f"{stem}: forbidden attribute in export")
        nodes.append(node)
    nodes.sort(key=lambda node: node["id"])
    ids = {node["id"] for node in nodes}
    normalised = []
    for source, target, weight in edges:
        if source not in ids or target not in ids:
            raise ValueError(f"{stem}: edge {source}-{target} has an endpoint outside the nodes")
        low, high = sorted((source, target))
        normalised.append((low, high, weight))
    normalised.sort()
    return ExportGraph(
        stem=stem,
        nodes=tuple(nodes),
        edges=tuple(normalised),
        metadata=metadata,
        generated_at=generated_at,
    )


def _global_graph(
    stem: str,
    graphs_dir: Path,
    graph_name: str,
    layout_name: str,
    what_this_is: str,
    manifest: dict[str, Any],
) -> ExportGraph:
    payload = _read_json(graphs_dir / f"{graph_name}.json")
    fields = payload["nodes"]["fields"]
    rows = payload["nodes"]["rows"]
    if payload["edges"]["fields"] != ["source", "target", "weight"]:
        raise ValueError(f"{graph_name}.json: unexpected edge fields")
    records = [dict(zip(fields, row, strict=True)) for row in rows]
    ids = [str(record["id"]) for record in records]
    positions = _layout(graphs_dir / layout_name, len(rows))
    edges = [
        (ids[source], ids[target], weight) for source, target, weight in payload["edges"]["rows"]
    ]
    source = f"site/data/global/graphs/{graph_name}.json (schema {payload['schema_version']})"
    return _assemble(
        stem,
        records,
        positions,
        edges,
        _metadata(source, manifest["generated_at"], what_this_is),
        manifest["generated_at"],
    )


def _california_graph(network_path: Path) -> ExportGraph:
    payload = _read_json(network_path)
    records = []
    positions = []
    for node in payload["nodes"]:
        records.append(
            {
                "id": node["id"],
                "display_name": node["name"],
                "works": node["plastic_works"],
                "community": node["community"],
            }
        )
        positions.append(
            (round(float(node["x"]), POSITION_DECIMALS), round(float(node["y"]), POSITION_DECIMALS))
        )
    edges = [(edge["source"], edge["target"], edge["weight"]) for edge in payload["edges"]]
    what_this_is = (
        "Co-authorship network of experts on plastic-related works (the expert "
        "index). An edge joins two experts who share such a work; its weight is the number of "
        "shared works. Built from unscreened search hits. Names are public OpenAlex names. "
        "Positions are a seeded ForceAtlas2 layout scaled to [-1, 1]."
    )
    source = f"{network_path.name} (schema {payload['schema_version']})"
    return _assemble(
        CALIFORNIA_STEM,
        records,
        positions,
        edges,
        _metadata(source, payload["generated_at"], what_this_is),
        payload["generated_at"],
    )


def _to_networkx(graph: ExportGraph, fmt: str) -> nx.Graph:
    result = nx.Graph()
    result.graph.update(dict(graph.metadata))
    for node in graph.nodes:
        attributes = {key: value for key, value in node.items() if key not in ("id", "x", "y")}
        if fmt == "gexf":
            attributes["viz"] = {"position": {"x": node["x"], "y": node["y"], "z": 0.0}}
        else:
            attributes["x"] = node["x"]
            attributes["y"] = node["y"]
        result.add_node(node["id"], **attributes)
    for source, target, weight in graph.edges:
        result.add_edge(source, target, weight=weight)
    return result


def _serialise(graph: ExportGraph, fmt: str) -> bytes:
    networkx_graph = _to_networkx(graph, fmt)
    buffer = io.BytesIO()
    if fmt == "gexf":
        nx.write_gexf(networkx_graph, buffer)
        raw = buffer.getvalue()
        pinned = graph.generated_at[:10].encode("ascii")
        if not DATE_RE.fullmatch(pinned.decode("ascii")):
            raise ValueError(f"{graph.stem}: generated_at does not start with a date")
        raw = re.sub(
            rb'lastmodifieddate="[^"]*"', b'lastmodifieddate="' + pinned + b'"', raw, count=1
        )
        # Pin the creator: CI's lock (networkx 3.6) and local installs (3.7) must give the
        # same bytes, otherwise --check reports stale files on one of them.
        raw = re.sub(
            rb"<creator>[^<]*</creator>", b"<creator>Plastiverse Live (networkx)</creator>", raw
        )
        return raw
    nx.write_graphml(networkx_graph, buffer)
    return buffer.getvalue()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_exports(graphs_dir: Path, network_path: Path | None) -> dict[str, bytes]:
    """Return every export file as ``{relative name: bytes}``, including the manifest."""
    manifest = _read_json(graphs_dir / "graphs_manifest.json")
    graphs = [
        _global_graph(
            "institutions",
            graphs_dir,
            "institutions",
            "layout_institutions.bin",
            manifest["what_this_is_and_is_not"],
            manifest,
        ),
        _global_graph(
            "authors",
            graphs_dir,
            "authors",
            "layout_authors.bin",
            manifest["author_graph"]["what_this_is_and_is_not"],
            manifest,
        ),
    ]
    if network_path is not None:
        graphs.append(_california_graph(network_path))

    files: dict[str, bytes] = {}
    entries = []
    for graph in graphs:
        for fmt in FORMATS:
            raw = _serialise(graph, fmt)
            name = f"{graph.stem}.{fmt}"
            entry: dict[str, Any] = {
                "graph": graph.stem,
                "format": fmt,
                "nodes": len(graph.nodes),
                "edges": len(graph.edges),
                "uncompressed_bytes": len(raw),
                "uncompressed_sha256": _sha256(raw),
            }
            if len(raw) > GZIP_THRESHOLD_BYTES:
                # Large files are committed gzipped only (mtime 0, so the bytes are stable).
                name = f"{name}.gz"
                data = gzip.compress(raw, compresslevel=9, mtime=0)
                entry["gzip"] = True
            else:
                data = raw
                entry["gzip"] = False
            files[name] = data
            entry.update({"file": name, "bytes": len(data), "sha256": _sha256(data)})
            entries.append(entry)
    export_manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": manifest["generated_at"],
        "licence": LICENCE,
        "screening": SCREENING_NOTE,
        "formats": list(FORMATS),
        "gzip_threshold_bytes": GZIP_THRESHOLD_BYTES,
        "note": (
            "Derived copies of the global graphs and the expert network file. "
            "Node attributes are a whitelist (label, works, community, country, type, ror); "
            "no emails, affiliations or ORCIDs."
        ),
        "files": entries,
    }
    files[MANIFEST_NAME] = (
        json.dumps(export_manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    return files


def write_exports(out_dir: Path, files: dict[str, bytes]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (out_dir / name).write_bytes(data)


def check_exports(out_dir: Path, files: dict[str, bytes]) -> list[str]:
    """Names that are missing, different from the rebuild, or unexpected in ``out_dir``."""
    stale = [
        name
        for name, data in sorted(files.items())
        if not (out_dir / name).exists() or (out_dir / name).read_bytes() != data
    ]
    if out_dir.exists():
        for path in sorted(out_dir.iterdir()):
            if (
                path.is_file()
                and path.name not in files
                and path.suffix in {".gexf", ".graphml", ".gz", ".json"}
            ):
                stale.append(f"unexpected {path.name}")
    return stale
