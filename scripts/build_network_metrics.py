"""Write site/data/california/network_metrics.json, the collaboration-structure metrics (BQ-3.2).

Usage: py -3.14 scripts/build_network_metrics.py [--check] [--null-replicates R]
Reads only committed site files (offline). --check rebuilds in memory and fails when the
committed file differs from the rebuild; generated_at is the only field it ignores.
--null-replicates sets the number of degree-preserving null replicates per window (BQ-3.3; default
100, 0 leaves out the null_model block). The default build takes about 17 minutes, mostly for
the G-I all-years and 2021-2025 windows. --check recomputes everything except the null block, whose
shape and R it checks; add --check-null to recompute and compare it too (slow).
Needs networkx (a declared project dependency).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.analytics.network_metrics import build_metrics, comparable  # noqa: E402
from atlas.analytics.network_null import DEFAULT_REPLICATES, build_null_block  # noqa: E402


def _load_institutions(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("institutions", payload) if isinstance(payload, dict) else payload
    return list(rows)


def _index_build_timestamp(metadata_path: Path, index: dict) -> str:
    """The index build time from build_metadata.json, else the index's own generated_at."""
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if isinstance(metadata, dict) and metadata.get("generated_at"):
            return str(metadata["generated_at"])
    return str(index.get("generated_at") or "")


def _null_block_problem(block: object, replicates: int) -> str | None:
    """Shape check of a committed null_model block (cheap; no recompute)."""
    if not replicates:
        return "present although --null-replicates is 0" if block is not None else None
    if not isinstance(block, dict):
        return "is missing; rerun scripts/build_network_metrics.py"
    missing = [key for key in ("method", "replicates", "seed", "graphs") if key not in block]
    if missing:
        return f"lacks {', '.join(missing)}"
    if block["replicates"] != replicates:
        return f"has R={block['replicates']}, expected R={replicates}"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    site_data = ROOT / "site" / "data" / "california"
    parser.add_argument("--index", default=str(site_data / "index.json"))
    parser.add_argument("--institutions", default=str(site_data / "institutions.json"))
    parser.add_argument("--metadata", default=str(site_data / "build_metadata.json"))
    parser.add_argument("--out", default=str(site_data / "network_metrics.json"))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--null-replicates", type=int, default=DEFAULT_REPLICATES)
    parser.add_argument(
        "--check-null", action="store_true", help="with --check, also recompute the null block"
    )
    args = parser.parse_args(argv)
    if args.null_replicates < 0:
        parser.error("--null-replicates must be 0 or more")

    index = json.loads(Path(args.index).read_text(encoding="utf-8"))
    institutions = _load_institutions(Path(args.institutions))
    payload = build_metrics(
        index,
        institutions,
        index_build_timestamp=_index_build_timestamp(Path(args.metadata), index),
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    out = Path(args.out)
    # The null block takes ~17 min at R=100, so --check compares it only with --check-null.
    if args.null_replicates and (not args.check or args.check_null):
        payload["null_model"] = build_null_block(index, replicates=args.null_replicates)
    if args.check:
        if not out.exists():
            print(f"{out} is missing; run scripts/build_network_metrics.py", file=sys.stderr)
            return 1
        committed = json.loads(out.read_text(encoding="utf-8"))
        if not args.check_null:
            problem = _null_block_problem(committed.get("null_model"), args.null_replicates)
            if problem:
                print(f"{out}: null_model {problem}", file=sys.stderr)
                return 1
            committed = {k: v for k, v in committed.items() if k != "null_model"}
        if comparable(committed) != comparable(payload):
            print(f"{out} is stale; rerun scripts/build_network_metrics.py", file=sys.stderr)
            return 1
        print(f"{out} is current" + ("" if args.check_null else " (null_model checked for shape)"))
        return 0
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    out.write_bytes(text.encode("utf-8"))
    graphs = payload["graphs"]
    all_authors = graphs["authors"]["windows"][0]
    all_institutions = graphs["institutions"]["windows"][0]
    print(
        f"network metrics: authors {all_authors['nodes']} nodes, {all_authors['edges']} edges; "
        f"institutions {all_institutions['nodes']} nodes, {all_institutions['edges']} edges "
        f"-> {out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
