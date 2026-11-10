"""Cross-table grant de-duplication (S8.6).

Reads every ``data/interim/grants/*.parquet`` grant table (nih_reporter, nsf_awards,
usaspending, ca_sea_grant, state_funders, and any later table with the C3 columns),
clusters records that describe the same award, and keeps one representative per
cluster. No input row is dropped: ``grants_dedupe_map.csv`` maps every ``grant_key``
to its cluster and representative.

Matching (all must hold):
- normalized title token Jaccard >= 0.5 and title similarity >= 0.8;
- title similarity >= 0.9, or a shared ``funder_chain`` entry (pass-through);
- no contradiction: different PI surnames when both sides have PIs, amounts differing
  by more than 10% when both are known, or starts more than 366 days apart;
- at least one supporting signal: shared PI surname, shared funder_chain entry,
  matching amount, or starts within 366 days.

Representative rule ("lowest-level project"): prefer a record that names PIs, then the
deepest ``funder_chain`` (closest to the performer), then the earlier entry in
``SOURCE_PRIORITY``. Clusters are connected components, so one chained pair can join
two groups; the overlap report counts cluster sizes so that effect is visible.
"""

from __future__ import annotations

import csv
import difflib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from itertools import combinations
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from atlas.ingest.grants.normalize import write_grants_parquet
from atlas.ingest.grants.schema import GRANT_COLUMNS

INTERIM_DIR = Path("data/interim/grants")
MERGED_NAME = "grants_merged.parquet"
MAP_NAME = "grants_dedupe_map.csv"
STATUS_NAME = "state_funders_status.json"
REPORT_PATH = Path("docs/grants_overlap_report.md")
SOURCE_PRIORITY: tuple[str, ...] = (
    "nih_reporter",
    "nsf_awards",
    "ca_sea_grant",
    "opc_council",
    "delta_science_tracker",
    "csu_coast",
    "scc_board",
    "usaspending",
)
TOKEN_MIN_JACCARD = 0.5
CHAIN_MIN_SIMILARITY = 0.8
TITLE_MIN_SIMILARITY = 0.9
AMOUNT_TOLERANCE = 0.10
DATE_WINDOW_DAYS = 366
MAP_FIELDS: tuple[str, ...] = (
    "grant_key",
    "table",
    "source",
    "source_award_id",
    "cluster_id",
    "representative_key",
    "is_representative",
    "cluster_size",
)
EXAMPLE_CLUSTERS = 10


@dataclass(frozen=True)
class _Item:
    index: int
    row: Mapping[str, Any]
    title: str
    tokens: frozenset[str]
    surnames: frozenset[str]
    chain: frozenset[str]
    amount: float | None
    start: date | None


@dataclass(frozen=True)
class ClusterResult:
    assignments: list[dict[str, Any]]


def _fold_text(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(re.findall(r"[a-z0-9]+", folded))


def _surnames(names: Sequence[str]) -> frozenset[str]:
    surnames: set[str] = set()
    for name in names:
        part = (
            name.split(",", 1)[0] if "," in name else (re.findall(r"[A-Za-z]+", name) or [""])[-1]
        )
        folded = _fold_text(part)
        if folded:
            surnames.add(folded.split()[-1])
    return frozenset(surnames)


def _prepare(index: int, row: Mapping[str, Any]) -> _Item:
    title = _fold_text(str(row.get("title") or ""))
    chain = frozenset(
        folded
        for folded in (_fold_text(str(name)) for name in row.get("funder_chain") or [])
        if folded
    )
    amount = row.get("amount")
    start = row.get("start")
    return _Item(
        index=index,
        row=row,
        title=title,
        tokens=frozenset(title.split()),
        surnames=_surnames([str(name) for name in row.get("pi_names") or []]),
        chain=chain,
        amount=float(amount) if amount is not None else None,
        start=start if isinstance(start, date) else None,
    )


def _amount_close(left: float, right: float) -> bool:
    top = max(left, right)
    return top == 0 or abs(left - right) / top <= AMOUNT_TOLERANCE


def compare_rows(left: Mapping[str, Any], right: Mapping[str, Any]) -> tuple[str, ...] | None:
    """Return the supporting signals if two rows describe one award, else ``None``."""

    return _compare(_prepare(0, left), _prepare(1, right))


def _compare(left: _Item, right: _Item) -> tuple[str, ...] | None:
    if not left.tokens or not right.tokens:
        return None
    jaccard = len(left.tokens & right.tokens) / len(left.tokens | right.tokens)
    if jaccard < TOKEN_MIN_JACCARD:
        return None
    similarity = difflib.SequenceMatcher(None, left.title, right.title).ratio()
    if similarity < CHAIN_MIN_SIMILARITY:
        return None
    shared_chain = bool(left.chain & right.chain)
    if similarity < TITLE_MIN_SIMILARITY and not shared_chain:
        return None
    if left.surnames and right.surnames and not (left.surnames & right.surnames):
        return None
    if (
        left.amount is not None
        and right.amount is not None
        and not _amount_close(left.amount, right.amount)
    ):
        return None
    if left.start and right.start and abs((left.start - right.start).days) > DATE_WINDOW_DAYS:
        return None
    signals: list[str] = []
    if left.surnames and right.surnames:
        signals.append("pi")
    if shared_chain:
        signals.append("funder_chain")
    if left.amount is not None and right.amount is not None:
        signals.append("amount")
    if left.start and right.start:
        signals.append("date")
    if not signals:
        return None
    return tuple(signals)


def _rank(item: _Item) -> tuple[int, int, int, str]:
    source = str(item.row.get("source") or "")
    priority = SOURCE_PRIORITY.index(source) if source in SOURCE_PRIORITY else len(SOURCE_PRIORITY)
    return (
        0 if item.surnames else 1,
        -len(item.row.get("funder_chain") or []),
        priority,
        str(item.row["grant_key"]),
    )


def cluster_rows(rows: Sequence[Mapping[str, Any]]) -> ClusterResult:
    """Cluster rows and pick one representative per cluster. Every input row is assigned."""

    keys = [str(row["grant_key"]) for row in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate grant_key in dedupe input")
    items = [_prepare(index, row) for index, row in enumerate(rows)]
    parent = list(range(len(items)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for left, right in combinations(items, 2):
        if _compare(left, right) is not None:
            root_left, root_right = find(left.index), find(right.index)
            if root_left != root_right:
                parent[max(root_left, root_right)] = min(root_left, root_right)

    groups: dict[int, list[_Item]] = defaultdict(list)
    for item in items:
        groups[find(item.index)].append(item)
    assignments: list[dict[str, Any]] = []
    for members in groups.values():
        representative = min(members, key=_rank)
        cluster_id = str(representative.row["grant_key"])
        for member in members:
            assignments.append(
                {
                    "grant_key": str(member.row["grant_key"]),
                    "table": str(member.row.get("_table") or ""),
                    "source": str(member.row.get("source") or ""),
                    "source_award_id": str(member.row.get("source_award_id") or ""),
                    "cluster_id": cluster_id,
                    "representative_key": cluster_id,
                    "is_representative": member is representative,
                    "cluster_size": len(members),
                }
            )
    assignments.sort(key=lambda entry: entry["grant_key"])
    return ClusterResult(assignments=assignments)


def load_grant_tables(directory: Path) -> list[dict[str, Any]]:
    """Read every grant parquet in ``directory``, tagging each row with its table name."""

    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.parquet")):
        if path.name == MERGED_NAME or path.name.startswith("."):
            continue
        table = pq.read_table(path)
        missing = [column for column in GRANT_COLUMNS if column not in table.column_names]
        if missing:
            raise ValueError(f"{path.name} is not a grant table: missing {missing}")
        for record in table.select(list(GRANT_COLUMNS)).to_pylist():
            record["_table"] = path.stem
            rows.append(record)
    return rows


def _gaps(status_path: Path) -> list[str]:
    if not status_path.exists():
        return []
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    gaps = [str(reason) for reason in payload.get("gaps", [])]
    return gaps


def render_report(
    rows: Sequence[Mapping[str, Any]], result: ClusterResult, gaps: Sequence[str]
) -> str:
    """Return the aggregate-only overlap report (no titles, abstracts, or names)."""

    rows_by_table = Counter(str(row["_table"]) for row in rows)
    kept_by_table = Counter(
        str(entry["table"]) for entry in result.assignments if entry["is_representative"]
    )
    members: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in result.assignments:
        members[entry["cluster_id"]].append(entry)
    cluster_count = len(members)
    multi = {cid: group for cid, group in members.items() if len(group) > 1}
    pair_counts: Counter[tuple[str, str]] = Counter()
    for group in multi.values():
        pairs = {
            tuple(sorted((left["source"], right["source"])))
            for left, right in combinations(group, 2)
        }
        pair_counts.update(pairs)
    size_counts = Counter(len(group) for group in members.values())
    examples = sorted(multi, key=lambda cid: (-len(multi[cid]), cid))[:EXAMPLE_CLUSTERS]

    lines = [
        "# Grant overlap report (S8.6)",
        "",
        "Generated by `scripts/dedupe_grants.py` from `data/interim/grants/*.parquet`.",
        "Aggregates only: no titles, abstracts, or PI names. Row-level mapping is in the",
        "git-ignored `data/interim/grants/grants_dedupe_map.csv`.",
        "",
        "## Inputs and outputs",
        "",
        "| table | rows | kept as representative |",
        "|---|---:|---:|",
    ]
    for table in sorted(rows_by_table):
        lines.append(f"| {table} | {rows_by_table[table]} | {kept_by_table.get(table, 0)} |")
    lines += [
        "",
        f"- Input rows: {len(rows)}",
        f"- Clusters (awards): {cluster_count}",
        f"- Multi-record clusters: {len(multi)}",
        f"- Rows folded into another cluster's representative: {len(rows) - cluster_count}",
        f"- Map rows written: {len(result.assignments)}",
        f"- Map covers every input row: {len(result.assignments) == len(rows)}",
        "",
        "## Matching rule",
        "",
        "A pair is one award when normalized title token Jaccard is at least 0.5 and title",
        "similarity is at least 0.9 (or at least 0.8 with a shared `funder_chain` entry). It",
        "is rejected on any contradiction: different PI surnames, amounts differing by more",
        "than 10%, or starts more than 366 days apart. It needs one supporting signal: shared",
        "PI surname, shared funder_chain entry, matching amount, or close start date.",
        "Representative: a record with PIs, then the deepest funder_chain, then source order.",
        "",
        "## Cluster counts by source pair",
        "",
        "Each multi-record cluster counts once per distinct source pair it contains.",
        "",
        "| source A | source B | clusters |",
        "|---|---|---:|",
    ]
    for (source_a, source_b), count in sorted(pair_counts.items()):
        lines.append(f"| {source_a} | {source_b} | {count} |")
    if not pair_counts:
        lines.append("| (none) | (none) | 0 |")
    lines += ["", "## Cluster sizes", "", "| records per cluster | clusters |", "|---:|---:|"]
    for size in sorted(size_counts):
        lines.append(f"| {size} | {size_counts[size]} |")
    lines += ["", "## Example cluster IDs", "", "Cluster ID is the representative `grant_key`."]
    lines += [f"- `{cid}` ({len(multi[cid])} records)" for cid in examples] or ["- (none)"]
    lines += ["", "## Source gaps", ""]
    lines += [f"- {gap}" for gap in gaps] or ["- (none recorded)"]
    lines.append("")
    return "\n".join(lines)


def run_dedupe(
    *,
    interim_dir: Path = INTERIM_DIR,
    merged_out: Path | None = None,
    map_out: Path | None = None,
    report_out: Path = REPORT_PATH,
    status_path: Path | None = None,
) -> dict[str, Any]:
    """Cluster every grant table and write the merged parquet, mapping CSV, and report."""

    merged_path = merged_out or interim_dir / MERGED_NAME
    map_path = map_out or interim_dir / MAP_NAME
    rows = load_grant_tables(interim_dir)
    result = cluster_rows(rows)
    by_key = {str(row["grant_key"]): row for row in rows}
    representatives = [
        {column: by_key[entry["grant_key"]][column] for column in GRANT_COLUMNS}
        for entry in result.assignments
        if entry["is_representative"]
    ]
    write_grants_parquet(representatives, merged_path)
    map_path.parent.mkdir(parents=True, exist_ok=True)
    with map_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(MAP_FIELDS))
        writer.writeheader()
        for entry in result.assignments:
            writer.writerow({field: entry[field] for field in MAP_FIELDS})
    gaps = _gaps(status_path or interim_dir / STATUS_NAME)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(render_report(rows, result, gaps), encoding="utf-8")
    clusters = {entry["cluster_id"] for entry in result.assignments}
    return {
        "input_rows": len(rows),
        "clusters": len(clusters),
        "multi_record_clusters": sum(
            1 for cid in clusters if sum(e["cluster_id"] == cid for e in result.assignments) > 1
        ),
        "representatives": len(representatives),
        "map_rows": len(result.assignments),
    }
