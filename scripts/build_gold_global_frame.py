"""Freeze the global gold-sampling frame with frozen strata (BQ-G3).

Run from the repository root. Reads the ignored global ingest (data/processed/global/works.parquet,
work_regions.parquet, and the raw OpenAlex pages) plus committed config. Abstracts are rebuilt from
abstract_inverted_index in memory and never written. Gold label files are never opened.

Outputs: curation/gold_global_frame_v1.csv (ids, block, theme, score, band, stratum, rand key) and
curation/gold_global_frame_v1.json (manifest with N_h, seed, model version, hashes, exclusions).
``--check`` validates the committed frame against its manifest and, when the ignored inputs are
present and unchanged, rebuilds it and compares bytes; otherwise it reports SKIP for the rebuild.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_s4_2 import assert_guide_examples_excluded  # noqa: E402

from atlas.ingest.global_partition import raw_page_paths  # noqa: E402
from atlas.ingest.normalize import _abstract_from_inverted_index  # noqa: E402
from atlas.nlp import gold_frame as gf  # noqa: E402
from atlas.query import load_query_config  # noqa: E402

SCHEMA = "gold-global-frame-v1"
OUT_CSV = Path("curation/gold_global_frame_v1.csv.gz")
PLAIN_CSV = Path("curation/gold_global_frame_v1.csv")
OUT_JSON = Path("curation/gold_global_frame_v1.json")
WORKS = Path("data/processed/global/works.parquet")
WORK_REGIONS = Path("data/processed/global/work_regions.parquet")
RAW_DIR = Path("data/raw/openalex_global")
GUIDE_EXAMPLES = Path("curation/a3_guide_examples.csv")
REGISTER = Path("config/search_vocabulary_v1.yml")
V32 = Path("config/queries_v32_candidate.yml")
POLLUTION_CORE = Path("config/pollution_core_v0.yml")
QUERIES = Path("config/queries.yml")
LANGUAGE_PROBE = Path("site/data/global/language_probe.json")
GUIDE_ADDENDUM = Path("docs/LABELING_GUIDE_A3_ADDENDUM.md")
CONFIG_FILES = (
    QUERIES,
    V32,
    POLLUTION_CORE,
    REGISTER,
    GUIDE_EXAMPLES,
    LANGUAGE_PROBE,
    GUIDE_ADDENDUM,
)


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _registry_ids(path: Path) -> set[str]:
    table = pq.read_table(path, columns=["work_id", "region_kind", "region_code"]).to_pylist()
    return {
        row["work_id"]
        for row in table
        if row["region_kind"] == "registry_region" and row["region_code"] == "california"
    }


def _load_universe(path: Path) -> dict[str, dict[str, str]]:
    rows = pq.read_table(path, columns=["work_id", "doi", "title", "language"]).to_pylist()
    universe: dict[str, dict[str, str]] = {}
    for row in rows:
        universe.setdefault(
            row["work_id"],
            {
                "doi": row["doi"] or "",
                "title": row["title"] or "",
                "language": row["language"] or "",
            },
        )
    return universe


def _input_hashes(pages: list[Path], page_hashes: list[tuple[str, str]]) -> dict[str, Any]:
    combined = gf.sha256_bytes("".join(f"{n} {h}\n" for n, h in page_hashes).encode())
    hashes: dict[str, Any] = {
        WORKS.as_posix(): gf.sha256_file(WORKS),
        WORK_REGIONS.as_posix(): gf.sha256_file(WORK_REGIONS),
        "data/raw/openalex_global/pages (sorted per-file sha256)": combined,
        "raw_page_files": len(pages),
    }
    for path in CONFIG_FILES:
        hashes[path.as_posix()] = gf.sha256_file(path)
    return hashes


def build_frame(seed: int = gf.GLOBAL_FRAME_SEED) -> tuple[list[gf.FrameWork], dict[str, Any]]:
    """Score every work in the global ingest and return the population plus manifest parts."""
    universe = _load_universe(WORKS)
    registry = _registry_ids(WORK_REGIONS)
    guides = _load_csv(GUIDE_EXAMPLES)
    guide_ids, guide_dois = gf.guide_example_ids(guides)
    excluded = {
        work_id
        for work_id, row in universe.items()
        if gf.is_guide_example(work_id, row["doi"], guide_ids, guide_dois)
    }
    queries = load_query_config(QUERIES)
    v32 = yaml.safe_load(V32.read_text(encoding="utf-8"))
    register = yaml.safe_load(REGISTER.read_text(encoding="utf-8"))
    pollution = yaml.safe_load(POLLUTION_CORE.read_text(encoding="utf-8"))
    score_rules = gf.load_score_rules(queries)
    theme_rules = gf.load_theme_rules(v32, register, pollution)

    pages = raw_page_paths(RAW_DIR)
    page_hashes: list[tuple[str, str]] = []
    scored: dict[str, tuple[int, str]] = {}
    population = [work_id for work_id in universe if work_id not in excluded]
    wanted = set(population)
    for path in pages:
        data = path.read_bytes()
        page_hashes.append((path.name, gf.sha256_bytes(data)))
        lines = gzip.decompress(data).decode("utf-8").splitlines()
        for line in lines[1:]:
            if not line.strip():
                continue
            record = json.loads(line)
            work_id = str(record.get("id") or "").rsplit("/", 1)[-1]
            if work_id not in wanted or work_id in scored:
                continue
            title = universe[work_id]["title"]
            abstract = _abstract_from_inverted_index(record.get("abstract_inverted_index"))
            points = gf.rule_points(title, abstract, score_rules)
            theme = gf.assign_theme(title, abstract, theme_rules)
            scored[work_id] = (points, theme)

    missing_abstract = [work_id for work_id in population if work_id not in scored]
    for work_id in missing_abstract:
        title = universe[work_id]["title"]
        points = gf.rule_points(title, "", score_rules)
        scored[work_id] = (points, gf.assign_theme(title, "", theme_rules))

    keys = gf.rand_keys(population, seed)
    frame: list[gf.FrameWork] = []
    for work_id in sorted(population):
        row = universe[work_id]
        score = gf.rule_score(scored[work_id][0])
        block = gf.assign_block(work_id, row["language"], registry)
        frame.append(
            gf.FrameWork(
                work_id=work_id,
                doi=row["doi"],
                block=block,
                theme_group=gf.frame_theme_group(block, scored[work_id][1]),
                score=score,
                band=gf.band_for(score),
                rand_key=keys[work_id],
            )
        )
    parts = {
        "universe_works": len(universe),
        "guide_example_excluded": sorted(excluded),
        "guide_examples_rows": sum(1 for row in guides if row.get("role") == "guide_example"),
        "missing_abstract_works": len(missing_abstract),
        "missing_language_works": sum(1 for w in population if not universe[w]["language"]),
        "input_hashes": _input_hashes(pages, page_hashes),
        "score_snapshot": gf.score_snapshot_sha256((r.work_id, r.score) for r in frame),
    }
    return frame, parts


def _strata(frame: list[gf.FrameWork]) -> list[dict[str, Any]]:
    counts = Counter(gf.stratum_id(r.block, r.theme_group, r.band) for r in frame)
    rows = []
    for stratum in gf.all_strata():
        block, theme, band = stratum.split("|")
        rows.append(
            {
                "stratum": stratum,
                "block": block,
                "theme_group": theme,
                "band": band,
                "N_h": counts.get(stratum, 0),
            }
        )
    return rows


def build_outputs(seed: int = gf.GLOBAL_FRAME_SEED) -> tuple[bytes, bytes, dict[str, Any]]:
    """Return (gzip frame bytes, uncompressed CSV bytes, manifest) for the whole population."""
    frame, parts = build_frame(seed)
    csv_bytes = gf.render_frame_csv(frame)
    gz_bytes = gf.gzip_bytes(csv_bytes)
    strata = _strata(frame)
    for row in strata:
        row["rows_in_csv"] = row["N_h"]
    zero = Counter(r.block for r in frame if r.score == 0)
    manifest = {
        "schema": SCHEMA,
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "seed": seed,
        "model_version": gf.MODEL_VERSION,
        "score_definition": (
            "points = 2 per core term in title + 1 per core term in abstract (queries.yml "
            "core_terms) + 1 per qualified term with a context + 1 per tier_2_terms hit; "
            "0 if any exclusions hit; score = min(1, points / 4), 4 decimals"
        ),
        "band_thresholds": {
            "low": "< 0.34 (includes zero score)",
            "medium": "0.34 to < 0.67",
            "high": ">= 0.67",
        },
        "stratum_scheme": (
            "global_english: theme x band (low incl. zero, medium, high) for pollution-core, "
            "lifecycle-and-society, other, plus one lens-candidate stratum (band all); "
            "registry_region and global_non_english: theme only (band all), lens merged into "
            "lifecycle-and-society. 16 strata."
        ),
        "score_snapshot_sha256": parts["score_snapshot"],
        "frame_file": OUT_CSV.as_posix(),
        "frame_sha256": gf.sha256_bytes(gz_bytes),
        "frame_uncompressed_sha256": gf.sha256_bytes(csv_bytes),
        "frame_rows": len(frame),
        "csv_row_policy": "all_works",
        "csv_bytes": len(csv_bytes),
        "gz_bytes": len(gz_bytes),
        "population_works": len(frame),
        "universe_works": parts["universe_works"],
        "guide_examples_checked": parts["guide_examples_rows"],
        "guide_example_exclusion_count": len(parts["guide_example_excluded"]),
        "missing_abstract_works": parts["missing_abstract_works"],
        "missing_language_works": parts["missing_language_works"],
        "zero_score_works_by_block": {b: zero.get(b, 0) for b in gf.BLOCKS},
        "strata": strata,
        "block_totals": {b: sum(1 for r in frame if r.block == b) for b in gf.BLOCKS},
        "input_hashes": parts["input_hashes"],
    }
    return gz_bytes, csv_bytes, manifest


def check(rebuild: bool = True) -> list[str]:
    """Validate committed outputs; return human-readable notes. Raises AssertionError on drift."""
    notes: list[str] = []
    manifest = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    gz_bytes = OUT_CSV.read_bytes()
    csv_bytes = gzip.decompress(gz_bytes)
    assert manifest["schema"] == SCHEMA
    assert manifest["frame_sha256"] == gf.sha256_bytes(gz_bytes), "frame .csv.gz hash drifted"
    assert manifest["frame_uncompressed_sha256"] == gf.sha256_bytes(csv_bytes), (
        "frame CSV hash drifted"
    )
    assert manifest["gz_bytes"] == len(gz_bytes)
    assert manifest["csv_bytes"] == len(csv_bytes)
    assert not PLAIN_CSV.exists(), "plain CSV must not sit next to the gzip frame"
    reader = csv.DictReader(io.StringIO(csv_bytes.decode("utf-8")))
    assert tuple(reader.fieldnames or ()) == gf.FRAME_COLUMNS, "unexpected frame columns"
    rows = list(reader)
    assert len(rows) == manifest["frame_rows"]
    assert len({r["work_id"] for r in rows}) == len(rows), "duplicate work_id in frame"
    legal = set(gf.all_strata())
    counts: Counter[str] = Counter()
    for r in rows:
        score = float(r["score"])
        assert r["band"] == gf.band_for(score), f"band mismatch for {r['work_id']}"
        assert r["block"] in gf.BLOCKS and r["theme_group"] in gf.THEME_GROUPS
        assert not (r["block"] != gf.BLOCK_GLOBAL_EN and r["theme_group"] == gf.THEME_LENS)
        stratum = gf.stratum_id(r["block"], r["theme_group"], r["band"])
        assert r["stratum"] == stratum and stratum in legal, f"stratum mismatch for {r['work_id']}"
        counts[stratum] += 1
    assert len(manifest["strata"]) == len(legal) == 16
    for row in manifest["strata"]:
        assert counts.get(row["stratum"], 0) == row["rows_in_csv"], f"count drift {row['stratum']}"
    assert sum(counts.values()) == len(rows)
    assert any(float(r["score"]) == 0.0 for r in rows), "zero-score works must be present"
    guides = _load_csv(GUIDE_EXAMPLES)
    checked = assert_guide_examples_excluded(guides, {"gold_global_frame_v1": rows}, {})
    notes.append(f"{checked} guide examples (by work_id or DOI) absent from the global frame")
    notes.append(f"frame sha256 (gzip and uncompressed) matches manifest ({len(rows)} rows)")
    if not rebuild:
        return notes
    if not (WORKS.exists() and WORK_REGIONS.exists() and RAW_DIR.exists()):
        notes.append("SKIP rebuild: ignored global inputs absent; manifest and frame verified")
        return notes
    current = {
        p: gf.sha256_file(Path(p))
        for p in (WORKS.as_posix(), WORK_REGIONS.as_posix(), *(c.as_posix() for c in CONFIG_FILES))
    }
    if any(manifest["input_hashes"].get(p) != h for p, h in current.items()):
        notes.append(
            "corpus or config changed since freeze; committed frame verified against manifest"
        )
        return notes
    rebuilt_gz, rebuilt_csv, _ = build_outputs(manifest["seed"])
    assert rebuilt_csv == csv_bytes, "global frame CSV does not match deterministic rebuild"
    assert rebuilt_gz == gz_bytes, "global frame gzip does not match deterministic rebuild"
    notes.append("rebuild matched (gzip and uncompressed, byte for byte)")
    return notes


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="validate committed outputs")
    args = parser.parse_args(argv)
    if args.check:
        for note in check():
            print(f"BQ-G3 frame check: {note}")
        return
    gz_bytes, _, manifest = build_outputs()
    OUT_CSV.write_bytes(gz_bytes)
    PLAIN_CSV.unlink(missing_ok=True)
    OUT_JSON.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT_CSV} ({len(gz_bytes)} bytes gz, {manifest['frame_rows']} rows)")


if __name__ == "__main__":
    main()
