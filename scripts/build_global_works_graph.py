"""Write site/data/global/graphs/: the global works similarity graph (BQ-V.1 slice 3).

Usage: py -3.14 scripts/build_global_works_graph.py [--check] [--raw-dir DIR] [--out-dir DIR]
       [--cache FILE]
Build mode embeds any uncached works with the local bge-small model and writes works.json,
works_phone.json, layout_works.bin and works_manifest.json.
--check validates the committed files (schema, caps, counts, sizes). When the ignored raw store
and the embedding cache are present it also rebuilds from the cache in memory and fails if a
committed file is stale. The check never embeds: if any vector is missing from the cache it
prints a SKIP line and exits 0, so --check needs no model download.
Needs networkx and numpy. Runtime is dominated by ForceAtlas2 per community.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.build.global_works_graph import (  # noqa: E402
    DEFAULT_CACHE_PATH,
    FILE_NAMES,
    build_works_graph,
    check_works_outputs,
    rebuild_for_check,
)
from atlas.ingest.global_partition import NoRawStoreError  # noqa: E402

DEFAULT_RAW_DIR = ROOT / "data" / "raw" / "openalex_global"
DEFAULT_OUT_DIR = ROOT / "site" / "data" / "global" / "graphs"
DEFAULT_CACHE = ROOT / DEFAULT_CACHE_PATH


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--cache", default=str(DEFAULT_CACHE))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    out_dir = Path(args.out_dir)
    cache = Path(args.cache)

    if args.check:
        problems = check_works_outputs(out_dir)
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        if problems:
            return 1
        print(f"{out_dir}: schema and caps OK")
        if not cache.exists():
            print(f"SKIP staleness: embedding cache absent ({cache})")
            return 0
        try:
            build = rebuild_for_check(args.raw_dir, cache)
        except NoRawStoreError:
            print("SKIP staleness: raw store absent (data/raw/openalex_global/pages)")
            return 0
        if build is None:
            print("SKIP staleness: embedding cache incomplete")
            return 0
        stale = [
            name
            for key, name in FILE_NAMES.items()
            if not (out_dir / name).exists() or (out_dir / name).read_bytes() != build.files[key]
        ]
        if stale:
            print(
                f"stale: {', '.join(stale)}; rerun scripts/build_global_works_graph.py",
                file=sys.stderr,
            )
            return 1
        print(f"{out_dir}: current with the raw store and cache")
        return 0

    try:
        build = build_works_graph(args.raw_dir, cache_path=cache)
    except NoRawStoreError as error:
        print(f"no raw store: {error}", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    for key, name in FILE_NAMES.items():
        (out_dir / name).write_bytes(build.files[key])
    for key, name in FILE_NAMES.items():
        print(f"{name}: {len(build.files[key])} bytes")
    for name, entry in build.manifest["files"].items():
        print(f"{name}: gzip {entry['gzip_bytes']} bytes")
    counts = build.manifest["counts"]
    print(
        f"{counts['desktop_nodes']} nodes, {counts['desktop_edges']} edges, "
        f"{counts['phone_nodes']} phone nodes, {counts['phone_edges']} phone edges, "
        f"{counts['communities']} communities, {counts['low_quality_nodes']} low quality"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
