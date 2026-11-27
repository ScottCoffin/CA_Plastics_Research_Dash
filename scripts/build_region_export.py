"""GP-5: California-schema institution payloads for one non-default registry region.

Writes ``site/data/<slug>/institutions.json``, ``index.json`` and
``institution_works/<inst_id>.json`` from the ignored global partition
(``data/processed/global``, built by ``scripts/partition_global.py``).
Offline: no network. The module is ``atlas.build.region_export``.

``--check`` validates the committed files (key sets, schema_version, references). When the partition
exists it also rebuilds the payloads and fails if a committed file is stale; without it, it prints
SKIP for the staleness check. ``generated_at`` is reused from the committed file, so a rebuild is
byte-identical.

Usage:
    py -3.14 scripts/build_region_export.py --region norway          # write
    py -3.14 scripts/build_region_export.py --region belgium --check # validate; exit 1 on problems
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.build.region_export import (  # noqa: E402
    DEFAULT_RAW_DIR,
    REGION_BUDGET_BYTES,
    build_region_export,
    compare_export,
    existing_generated_at,
    read_inputs,
    validate_structure,
    write_bundle,
    write_export,
)
from atlas.regions.registry import DEFAULT_REGISTRY_PATH, load_registry  # noqa: E402
from atlas.regions.scope import DEFAULT_REGION_SLUG, country_codes, region_data_dir  # noqa: E402

PARTITION = ROOT / "data" / "processed" / "global"
PARTITION_FILES = (
    "works.parquet",
    "work_regions.parquet",
    "authorships.parquet",
    "institutions.parquet",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--region", required=True, help="registry slug (not california)")
    parser.add_argument("--check", action="store_true", help="validate; exit 1 on problems")
    parser.add_argument("--partition-dir", type=Path, default=PARTITION)
    parser.add_argument(
        "--raw-dir", type=Path, default=DEFAULT_RAW_DIR, help="raw pages (labeller abstracts)"
    )
    parser.add_argument("--out-dir", type=Path, help="default: the region's site_data_dir")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY_PATH)
    args = parser.parse_args(argv)

    try:
        region = load_registry(args.registry).get(args.region)
    except KeyError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if region.slug == DEFAULT_REGION_SLUG:
        print("ERROR: california keeps its own pipeline (build_export_site.py)", file=sys.stderr)
        return 2
    try:
        codes = country_codes(region)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if len(codes) != 1:
        print(
            f"ERROR: region {region.slug!r} needs exactly one country code, got {codes}",
            file=sys.stderr,
        )
        return 2
    iso = codes[0]
    out_dir = args.out_dir or region_data_dir(region)
    partition_ready = all((args.partition_dir / name).is_file() for name in PARTITION_FILES)
    raw_ready = (args.raw_dir / "pages").is_dir()

    if args.check:
        problems = validate_structure(out_dir) if out_dir.is_dir() else [f"missing {out_dir}"]
        if not (out_dir / "bundle" / "manifest.json").is_file():
            problems.append("missing bundle/manifest.json (run without --check)")
        if partition_ready and raw_ready and not problems:
            export = build_region_export(
                region.slug,
                iso,
                read_inputs(args.partition_dir, iso, raw_dir=args.raw_dir),
                existing_generated_at(out_dir) or _now(),
            )
            problems += compare_export(out_dir, export)
        elif not (partition_ready and raw_ready):
            print("SKIP: staleness check (partition or raw pages not built)")
        for problem in problems:
            print(f"FAIL: {problem}")
        if problems:
            return 1
        print(f"PASS: {region.slug} structure valid")
        return 0

    if not partition_ready:
        print(
            f"ERROR: partition not found under {args.partition_dir}; run partition_global.py",
            file=sys.stderr,
        )
        return 1
    if not raw_ready:
        print(f"ERROR: raw pages not found under {args.raw_dir}/pages", file=sys.stderr)
        return 1
    export = build_region_export(
        region.slug,
        iso,
        read_inputs(args.partition_dir, iso, raw_dir=args.raw_dir),
        existing_generated_at(out_dir) or _now(),
    )
    sizes = write_export(out_dir, export)
    write_bundle(out_dir, export.index["generated_at"])
    sizes.update({f"bundle/{name}": size for name, size in _bundle_sizes(out_dir).items()})
    total = sum(sizes.values())
    print(
        f"{region.slug} ({iso}): {len(export.institutions['institutions'])} institutions, "
        f"{export.index['counts']['works']} works, {export.index['counts']['authors']} authors"
    )
    print(f"wrote {len(sizes)} files, {total} bytes under {out_dir}")
    if total > REGION_BUDGET_BYTES:
        print(f"FLAG: {total} bytes is above the {REGION_BUDGET_BYTES}-byte Pages budget")
    return 0


def _bundle_sizes(out_dir: Path) -> dict[str, int]:
    folder = out_dir / "bundle"
    return {
        path.relative_to(folder).as_posix(): path.stat().st_size
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
