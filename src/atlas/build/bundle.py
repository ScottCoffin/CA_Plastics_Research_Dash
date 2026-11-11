"""Public, abstract-free serving bundle (Add-on A1 Appendix C, AT-4).

Inputs: the published site/data/index.json works, optionally the normalized works and
institutions Parquet (never their abstract column), and optionally the AT-3 analytics
tables. Outputs go into one directory: works_index.json, facets.json, facets.bin,
inst_tiers.json, and parquet/*.parquet. The build writes a sibling staging directory and
swaps it in, so a failed build never leaves a half-written bundle behind.

Bit layout: work i (position in work_id order) is bit (i & 31) of word (i >> 5) of its set,
words are uint32 little-endian, and each set occupies ceil(N / 32) words.
"""

from __future__ import annotations

import gzip
import json
import shutil
import struct
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[3]
FACETS_JS = REPO / "site" / "assets" / "facets.js"
SCHEMA = "at4.v1"
MAGIC = b"BMF1"
VERSION = 1
HEADER = struct.Struct("<4sIII")
UNKNOWN = "unknown"
FACET_ORDER = ("year", "type", "topic", "plastic", "ca_led", "institution", "sector", "oa")
ANALYTICS_FILES = ("inst_counts.parquet", "inst_stability.parquet", "year_tag.parquet")
TIER_METHOD = (
    "Institutions are walked in rank_frac order (ties broken by inst_id); the first leads "
    "tier 1, and each next institution joins the current tier while its rank_lo is at most "
    "the tier leader's rank_hi, otherwise it starts a new tier and becomes the leader."
)
WORKS_SCHEMA = pa.schema(
    [
        ("work_id", pa.string()),
        ("doi", pa.string()),
        ("title", pa.string()),
        ("year", pa.int64()),
        ("type", pa.string()),
        ("journal", pa.string()),
        ("is_oa", pa.bool_()),
        ("oa_status", pa.string()),
        ("cited_by_count", pa.int64()),
        ("plastic_related", pa.bool_()),
        ("ca_led", pa.bool_()),
        ("domain_tags", pa.list_(pa.string())),
        ("institution_ids", pa.list_(pa.string())),
    ]
)
TIER_SCHEMA = pa.schema(
    [
        ("inst_id", pa.string()),
        ("name", pa.string()),
        ("atlas_type", pa.string()),
        ("tier", pa.int64()),
        ("works_full", pa.int64()),
        ("works_frac", pa.float64()),
        ("frac_lo", pa.float64()),
        ("frac_hi", pa.float64()),
        ("rank_frac", pa.int64()),
        ("rank_lo", pa.int64()),
        ("rank_hi", pa.int64()),
    ]
)


# ---------------------------------------------------------------- labels


def year_label(year: int | None) -> str:
    return UNKNOWN if year is None else str(int(year))


def plastic_label(value: bool | None) -> str:
    return "unlabelled" if value is None else ("yes" if value else "no")


def oa_label(is_oa: bool | None) -> str:
    return UNKNOWN if is_oa is None else ("open" if is_oa else "closed")


def work_labels(
    work: dict[str, Any], ca_inst: dict[str, dict], is_oa: bool | None
) -> dict[str, list[str]]:
    """Facet labels that apply to one published work (multi-valued facets may repeat)."""
    ca_ids = [i for i in work.get("institution_ids") or [] if i in ca_inst]
    sectors = {ca_inst[i]["atlas_type"] for i in ca_ids if ca_inst[i]["atlas_type"]}
    return {
        "year": [year_label(work.get("year"))],
        "type": [work.get("type") or UNKNOWN],
        "topic": sorted({t for t in work.get("domain_tags") or [] if t}),
        "plastic": [plastic_label(work.get("plastic_related"))],
        "ca_led": ["yes" if work.get("ca_led") else "no"],
        "institution": sorted(set(ca_ids)),
        "sector": sorted(sectors),
        "oa": [oa_label(is_oa)],
    }


def _label_sort_key(facet: str, label: str) -> tuple:
    if facet == "year":
        return (1, 0, "") if label == UNKNOWN else (0, int(label), label)
    return (0, 0, label)


# ---------------------------------------------------------------- bit-sets


def pack_bitsets(members: list[list[int]], n: int) -> bytes:
    """Pack one bit-set per member list (positions 0..n-1) into little-endian uint32 words."""
    words = -(-n // 32)
    mat = np.zeros((len(members), words * 32), dtype=bool)
    for s, idx in enumerate(members):
        if idx:
            mat[s, np.asarray(idx, dtype=np.int64)] = True
    return np.packbits(mat, axis=1, bitorder="little").tobytes()


def encode_facets_bin(n: int, nsets: int, body: bytes) -> bytes:
    return HEADER.pack(MAGIC, VERSION, n, nsets) + body


def assign_tiers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group institutions into rank-range tiers (see TIER_METHOD). Returns rows with `tier`."""
    ordered = sorted(rows, key=lambda r: (r["rank_frac"], r["inst_id"]))
    out: list[dict[str, Any]] = []
    tier = 0
    leader_hi: int | None = None
    for row in ordered:
        if leader_hi is None or row["rank_lo"] > leader_hi:
            tier += 1
            leader_hi = row["rank_hi"]
        out.append({**row, "tier": tier})
    return out


# ---------------------------------------------------------------- helpers


def gzip_bytes(data: bytes) -> int:
    return len(gzip.compress(data, compresslevel=9, mtime=0))


def _dump(obj: Any) -> bytes:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def _sql_path(path: Path) -> str:
    return "'" + path.as_posix().replace("'", "''") + "'"


def _copy(con: duckdb.DuckDBPyConnection, select_sql: str, dest: Path) -> None:
    con.execute(f"COPY ({select_sql}) TO {_sql_path(dest)} (FORMAT PARQUET, COMPRESSION zstd)")


def load_index(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    works = sorted(data["works"], key=lambda w: w["work_id"])
    ids = [w["work_id"] for w in works]
    if len(set(ids)) != len(ids):
        raise ValueError(f"duplicate work_id in {path}")
    return works


def load_normalized(normalized_dir: Path | None, used: list[str], skipped: list[dict]):
    """Return (oa map by work_id, CA institution map by inst_id), recording what was used."""
    oa: dict[str, dict[str, Any]] = {}
    ca: dict[str, dict[str, Any]] = {}
    if normalized_dir is None:
        skipped.append({"input": "normalized", "reason": "no --normalized-dir given"})
        return oa, ca
    works_path = normalized_dir / "works.parquet"
    if works_path.exists():
        rows = pq.read_table(
            works_path, columns=["work_id", "doi", "journal", "is_oa", "oa_status"]
        ).to_pylist()
        oa = {r["work_id"]: r for r in rows}
        used.append("normalized/works.parquet (doi, journal, is_oa, oa_status only)")
    else:
        skipped.append({"input": "normalized/works.parquet", "reason": "absent"})
    inst_path = normalized_dir / "institutions.parquet"
    if inst_path.exists():
        rows = pq.read_table(
            inst_path, columns=["inst_id", "name", "atlas_type", "ca_flag"]
        ).to_pylist()
        ca = {
            r["inst_id"]: {"name": r["name"] or r["inst_id"], "atlas_type": r["atlas_type"]}
            for r in rows
            if r["ca_flag"]
        }
        used.append("normalized/institutions.parquet (CA institutions)")
    else:
        skipped.append(
            {
                "input": "normalized/institutions.parquet",
                "reason": "absent; institution and sector facets empty",
            }
        )
    return oa, ca


def load_analytics(analytics_dir: Path | None, used: list[str], skipped: list[dict]) -> dict | None:
    """Return the three AT-3 tables when all are present, else None (recorded as skipped)."""
    if analytics_dir is None or not all((analytics_dir / f).exists() for f in ANALYTICS_FILES):
        reason = (
            "no analytics directory given" if analytics_dir is None else "analytics tables absent"
        )
        skipped.append(
            {"input": "analytics", "reason": f"{reason}; no inst_tiers or analytics Parquet"}
        )
        return None
    used.extend(f"analytics/{f}" for f in ANALYTICS_FILES)
    counts = pq.read_table(analytics_dir / "inst_counts.parquet").to_pylist()
    stability = pq.read_table(analytics_dir / "inst_stability.parquet").to_pylist()
    return {"counts": counts, "stability": stability, "dir": analytics_dir}


def build_tier_rows(analytics: dict) -> list[dict[str, Any]]:
    by_id = {r["inst_id"]: r for r in analytics["counts"]}
    rows = []
    for s in analytics["stability"]:
        c = by_id.get(s["inst_id"], {})
        rows.append(
            {
                "inst_id": s["inst_id"],
                "name": c.get("name"),
                "atlas_type": c.get("atlas_type"),
                "works_full": c.get("works_full"),
                "works_frac": s["works_frac"],
                "frac_lo": s["frac_lo"],
                "frac_hi": s["frac_hi"],
                "rank_frac": s["rank_frac"],
                "rank_lo": s["rank_lo"],
                "rank_hi": s["rank_hi"],
            }
        )
    return assign_tiers(rows)


# ---------------------------------------------------------------- build


def build_facets(works: list[dict[str, Any]], oa: dict, ca: dict):
    """Return (facets dict for JSON, packed bit-set body, number of sets)."""
    members: dict[str, dict[str, list[int]]] = {f: {} for f in FACET_ORDER}
    for pos, work in enumerate(works):
        is_oa = oa.get(work["work_id"], {}).get("is_oa")
        for facet, labels in work_labels(work, ca, is_oa).items():
            for label in labels:
                members[facet].setdefault(label, []).append(pos)

    facets: dict[str, list[dict[str, Any]]] = {}
    ordered_sets: list[list[int]] = []
    for facet in FACET_ORDER:
        entries = []
        labels = sorted(members[facet], key=lambda lab: _label_sort_key(facet, lab))
        if facet == "institution":
            labels = sorted(labels, key=lambda lab: (ca[lab]["name"], lab))
        for label in labels:
            idx = members[facet][label]
            entry: dict[str, Any] = {"label": label, "id": len(ordered_sets), "count": len(idx)}
            if facet == "institution":
                entry["name"] = ca[label]["name"]
                entry["atlas_type"] = ca[label]["atlas_type"]
            entries.append(entry)
            ordered_sets.append(idx)
        facets[facet] = entries
    body = pack_bitsets(ordered_sets, len(works))
    return facets, body, len(ordered_sets)


def build_bundle(
    index_path: Path,
    output_dir: Path,
    *,
    normalized_dir: Path | None = None,
    analytics_dir: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Write the serving bundle into output_dir (atomic swap) and return the manifest."""
    stamp = generated_at or datetime.now(UTC).isoformat(timespec="seconds")
    used: list[str] = [str(index_path.name) + " (published works)"]
    skipped: list[dict] = []
    works = load_index(index_path)
    oa, ca = load_normalized(normalized_dir, used, skipped)
    analytics = load_analytics(analytics_dir, used, skipped)
    facets, body, nsets = build_facets(works, oa, ca)

    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent))
    try:
        _write_bundle(staging, works, oa, facets, body, nsets, analytics, stamp)
        manifest = _write_manifest(staging, works, facets, analytics, used, skipped, stamp)
        _swap_in(staging, output_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return manifest


def _write_bundle(staging, works, oa, facets, body, nsets, analytics, stamp) -> None:
    n = len(works)
    (staging / "parquet").mkdir()
    (staging / "works_index.json").write_bytes(
        _dump(
            {
                "schema": SCHEMA,
                "titles": [w.get("title") or "" for w in works],
                "work_ids": [w["work_id"] for w in works],
                "years": [w.get("year") for w in works],
            }
        )
    )
    (staging / "facets.json").write_bytes(_dump(facets))
    (staging / "facets.bin").write_bytes(encode_facets_bin(n, nsets, body))

    con = duckdb.connect()
    try:
        rows = [
            {
                "work_id": w["work_id"],
                "doi": oa.get(w["work_id"], {}).get("doi"),
                "title": w.get("title"),
                "year": w.get("year"),
                "type": w.get("type"),
                "journal": oa.get(w["work_id"], {}).get("journal"),
                "is_oa": oa.get(w["work_id"], {}).get("is_oa"),
                "oa_status": oa.get(w["work_id"], {}).get("oa_status"),
                "cited_by_count": w.get("cited_by_count"),
                "plastic_related": w.get("plastic_related"),
                "ca_led": w.get("ca_led"),
                "domain_tags": sorted({t for t in w.get("domain_tags") or [] if t}),
                "institution_ids": list(w.get("institution_ids") or []),
            }
            for w in works
        ]
        con.register("works_tbl", pa.Table.from_pylist(rows, schema=WORKS_SCHEMA))
        _copy(con, "SELECT * FROM works_tbl", staging / "parquet" / "works.parquet")

        if analytics is not None:
            tiers = build_tier_rows(analytics)
            (staging / "inst_tiers.json").write_bytes(
                _dump({"generated_at": stamp, "method": TIER_METHOD, "tiers": tiers})
            )
            con.register("tiers_tbl", pa.Table.from_pylist(tiers, schema=TIER_SCHEMA))
            _copy(con, "SELECT * FROM tiers_tbl", staging / "parquet" / "inst_tiers.parquet")
            for name in ("inst_counts", "year_tag"):
                src = analytics["dir"] / f"{name}.parquet"
                _copy(
                    con,
                    f"SELECT * FROM read_parquet({_sql_path(src)})",
                    staging / "parquet" / f"{name}.parquet",
                )
    finally:
        con.close()


def _write_manifest(staging, works, facets, analytics, used, skipped, stamp) -> dict[str, Any]:
    files: dict[str, dict[str, int]] = {}
    for path in sorted(p for p in staging.rglob("*") if p.is_file()):
        rel = path.relative_to(staging).as_posix()
        data = path.read_bytes()
        files[rel] = {"raw_bytes": len(data), "gzip_bytes": gzip_bytes(data)}
    landing = ["works_index.json", "facets.json", "facets.bin"]
    manifest = {
        "schema": SCHEMA,
        "generated_at": stamp,
        "n_works": len(works),
        "facet_label_counts": {
            facet: {e["label"]: e["count"] for e in entries} for facet, entries in facets.items()
        },
        "files": files,
        "landing_files": landing,
        "landing_gzip_bytes": sum(files[f]["gzip_bytes"] for f in landing),
        "inputs": {
            "used": used,
            "skipped": skipped,
            "analytics_parquet_copied": analytics is not None,
        },
    }
    (staging / "manifest.json").write_bytes(_dump(manifest))
    return manifest


def _swap_in(staging: Path, final: Path) -> None:
    backup = None
    if final.exists():
        backup = final.with_name(final.name + ".previous")
        if backup.exists():
            shutil.rmtree(backup)
        final.rename(backup)
    try:
        staging.rename(final)
    except BaseException:
        if backup is not None:
            backup.rename(final)
        raise
    if backup is not None:
        shutil.rmtree(backup)


# ---------------------------------------------------------------- node runner

NODE_RUNNER = r"""
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const [, , bundleDir, facetsJs, casesPath] = process.argv;
const { BitmaskIndex } = require(facetsJs);
const read = (name) => fs.readFileSync(path.join(bundleDir, name));
const bin = read("facets.bin");
const buf = bin.buffer.slice(bin.byteOffset, bin.byteOffset + bin.byteLength);
const facets = JSON.parse(read("facets.json"));
const works = JSON.parse(read("works_index.json"));
const idx = new BitmaskIndex(facets, buf, works);
const cases = JSON.parse(fs.readFileSync(casesPath, "utf8"));
const out = cases.map((c) => {
  const extra = c.query === null ? null : idx.searchBits(c.query);
  const r = idx.counts(c.sel, extra);
  return { total: r.total, counts: r.counts, ids: idx.selectedIds(c.sel, extra) };
});
process.stdout.write(JSON.stringify(out));
"""


def run_node_cases(
    bundle_dir: Path, cases: list[dict[str, Any]], node: str
) -> list[dict[str, Any]]:
    """Run facets.js in node over selection cases; each case has `sel` and `query` (or null)."""
    with tempfile.TemporaryDirectory() as tmp:
        runner = Path(tmp) / "facets_runner.cjs"
        cases_file = Path(tmp) / "cases.json"
        runner.write_text(NODE_RUNNER, encoding="utf-8")
        cases_file.write_text(json.dumps(cases), encoding="utf-8")
        proc = subprocess.run(
            [node, str(runner), str(bundle_dir), str(FACETS_JS), str(cases_file)],
            capture_output=True,
            text=True,
            check=True,
        )
    return json.loads(proc.stdout)
