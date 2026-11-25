"""Region page payloads: ``site/data/<slug>/region.json`` (schema region-v1, REG-1).

Covers every registry region with status ``planned`` or ``active`` and a ``country_codes``
predicate. The default region has its own pipeline and is skipped. Country numbers come from
``site/data/global/countries.json``; institutions, researchers and partner countries come from
the ignored global partition and raw pages; local sections come from ``regions/<slug>/region.yml``.
Offline.

``--check`` validates the committed files (schema, placeholder rule, privacy, wording, and that
the counts equal countries.json). When the ignored inputs exist it also rebuilds each file and
fails if the committed copy is stale; without them it prints SKIP for the staleness check.

Usage:
    py -3.14 scripts/build_region_pages.py                # write every eligible region
    py -3.14 scripts/build_region_pages.py --slug norway  # one region
    py -3.14 scripts/build_region_pages.py --check        # validate; exit 1 on problems
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.build.region_pages import (  # noqa: E402
    build_region_payload,
    encode,
    load_config,
    read_work_countries,
    scan_authorships,
    unconfirmed_items,
    validate_payload,
)
from atlas.ingest.global_partition import raw_page_paths  # noqa: E402
from atlas.regions.registry import Region, load_registry  # noqa: E402
from atlas.regions.scope import DEFAULT_REGION_SLUG  # noqa: E402

PARTITION = ROOT / "data" / "processed" / "global"
DEFAULT_WORKS = PARTITION / "works.parquet"
DEFAULT_REGIONS = PARTITION / "work_regions.parquet"
DEFAULT_RAW = ROOT / "data" / "raw" / "openalex_global"
COUNTRIES = ROOT / "site" / "data" / "global" / "countries.json"
EXPLORE = ROOT / "site" / "data" / "global" / "explore.json"
REGION_FILE = "region.json"


def eligible_regions() -> list[Region]:
    """Planned or active regions with one country code and not the default region."""
    found: list[Region] = []
    for region in load_registry().regions:
        if region.slug == DEFAULT_REGION_SLUG or region.tier == "root":
            continue
        if region.status not in ("planned", "active"):
            continue
        if region.predicate is None or len(region.predicate.country_codes) != 1:
            continue
        found.append(region)
    return found


def _iso(region: Region) -> str:
    assert region.predicate is not None
    return region.predicate.country_codes[0]


def _config_path(region: Region) -> Path:
    return ROOT / "regions" / region.slug / "region.yml"


def _output_path(region: Region) -> Path:
    return ROOT / (region.site_data_dir or f"site/data/{region.slug}") / REGION_FILE


def _country_names() -> dict[str, str]:
    if not EXPLORE.is_file():
        return {}
    countries = json.loads(EXPLORE.read_text(encoding="utf-8")).get("countries") or []
    return {str(c["iso"]): str(c["name"]) for c in countries if c.get("iso") and c.get("name")}


def _read_regions_rows(path: Path) -> list[dict]:
    return pq.read_table(path, columns=["work_id", "region_kind", "region_code"]).to_pylist()


def _partition_inputs(regions: list[Region]) -> tuple[dict, dict]:
    """(work_countries, authorships) for the wanted regions; authorships come from raw pages."""
    work_countries = read_work_countries(_read_regions_rows(DEFAULT_REGIONS))
    wanted = {w for w, codes in work_countries.items() if any(_iso(r) in codes for r in regions)}
    authorships = scan_authorships(raw_page_paths(DEFAULT_RAW), wanted)
    return work_countries, authorships


def _render(region: Region, countries: dict, work_countries: dict, authorships: dict) -> str:
    payload = build_region_payload(
        slug=region.slug,
        name=region.name,
        iso=_iso(region),
        config=load_config(_config_path(region)),
        countries_payload=countries,
        work_countries=work_countries,
        authorships=authorships,
        names=_country_names(),
    )
    return encode(payload)


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


def _select(regions: list[Region], slug: str | None) -> list[Region]:
    if slug is None:
        return regions
    chosen = [r for r in regions if r.slug == slug]
    if not chosen:
        known = ", ".join(r.slug for r in regions)
        raise SystemExit(f"ERROR: {slug!r} is not an eligible region (eligible: {known})")
    return chosen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--slug", help="one region slug (default: every eligible region)")
    parser.add_argument("--check", action="store_true", help="validate committed files")
    args = parser.parse_args(argv)

    if not COUNTRIES.is_file():
        print(f"ERROR: missing {COUNTRIES}; run scripts/build_tier_b.py", file=sys.stderr)
        return 1
    countries = json.loads(COUNTRIES.read_text(encoding="utf-8"))
    regions = _select(eligible_regions(), args.slug)

    if args.check:
        return _check(regions, countries)

    inputs = DEFAULT_WORKS.is_file() and DEFAULT_REGIONS.is_file()
    if not inputs:
        print(
            f"ERROR: missing partition under {PARTITION}; run scripts/partition_global.py",
            file=sys.stderr,
        )
        return 1
    work_countries, authorships = _partition_inputs(regions)
    for region in regions:
        text = _render(region, countries, work_countries, authorships)
        payload = json.loads(text)
        problems = validate_payload(payload, countries)
        if problems:
            for problem in problems[:20]:
                print(f"ERROR: {region.slug}: {problem}", file=sys.stderr)
            return 1
        out = _output_path(region)
        _write_atomic(out, text)
        stats = payload["stats"]
        print(
            f"wrote {out.relative_to(ROOT).as_posix()}: {len(text.encode('utf-8')):,} bytes, "
            f"{stats['works_total']} works, first year {stats['first_year']}, "
            f"{len(payload['top_institutions'])} institutions, "
            f"{len(payload['top_researchers'])} researchers, "
            f"{len(payload['partner_countries'])} partner countries, "
            f"{len(unconfirmed_items(payload['sections']))} items to confirm"
        )
    return 0


def _check(regions: list[Region], countries: dict) -> int:
    failed = False
    inputs = DEFAULT_WORKS.is_file() and DEFAULT_REGIONS.is_file() and raw_page_paths(DEFAULT_RAW)
    work_countries = authorships = None
    if inputs:
        work_countries, authorships = _partition_inputs(regions)
    for region in regions:
        out = _output_path(region)
        label = region.slug
        if not out.is_file():
            print(f"FAIL: {label}: missing {out.relative_to(ROOT).as_posix()}")
            failed = True
            continue
        try:
            load_config(_config_path(region))
        except (ValueError, OSError) as exc:
            print(f"FAIL: {label}: region.yml: {exc}")
            failed = True
            continue
        committed = json.loads(out.read_text(encoding="utf-8"))
        problems = validate_payload(committed, countries)
        if problems:
            for problem in problems[:20]:
                print(f"FAIL: {label}: {problem}")
            failed = True
            continue
        flagged = unconfirmed_items(committed["sections"])
        print(
            f"PASS: {label}: schema, placeholder rule, privacy and countries.json equality "
            f"({len(flagged)} items to confirm)"
        )
        if inputs:
            if out.read_text(encoding="utf-8") != _render(
                region, countries, work_countries, authorships
            ):
                print(f"FAIL: {label}: region.json is stale; rerun scripts/build_region_pages.py")
                failed = True
            else:
                print(f"PASS: {label}: freshness")
    if not inputs:
        print(f"SKIP: staleness; no partition or raw pages under {PARTITION} and {DEFAULT_RAW}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
