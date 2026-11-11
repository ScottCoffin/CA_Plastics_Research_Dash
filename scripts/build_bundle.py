"""Build the public, abstract-free serving bundle (AT-4, Appendix C).

Examples:
  py -3.14 scripts/build_bundle.py
  py -3.14 scripts/build_bundle.py --output-dir scratch/bundle_try
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from atlas.build.bundle import build_bundle  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--index", type=Path, default=REPO / "site/data/index.json")
    ap.add_argument("--normalized-dir", type=Path, default=REPO / "data/processed/normalized")
    ap.add_argument("--analytics-dir", type=Path, default=REPO / "data/processed/analytics")
    ap.add_argument("--output-dir", type=Path, default=REPO / "site/data/bundle")
    args = ap.parse_args(argv)

    manifest = build_bundle(
        args.index,
        args.output_dir,
        normalized_dir=args.normalized_dir,
        analytics_dir=args.analytics_dir,
    )
    skipped = manifest["inputs"]["skipped"]
    total_raw = sum(f["raw_bytes"] for f in manifest["files"].values())
    total_gz = sum(f["gzip_bytes"] for f in manifest["files"].values())
    print(f"works: {manifest['n_works']}")
    labels = manifest["facet_label_counts"]
    print(f"facets: {len(labels)} ({sum(len(v) for v in labels.values())} labels)")
    print(f"landing gzip bytes: {manifest['landing_gzip_bytes']}")
    print(f"total raw bytes: {total_raw}; total gzip bytes: {total_gz}")
    print(f"files: {len(manifest['files'])} -> {args.output_dir}")
    for item in skipped:
        print(f"skipped: {item['input']} ({item['reason']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
