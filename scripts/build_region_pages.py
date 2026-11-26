"""Region page payloads: ``site/data/<slug>/region.json`` (schema region-v1, REG-1).

Covers every registry region with status ``planned`` or ``active`` and a ``country_codes``
predicate. The default region (California, REG-CA) is built from the ``registry_regions`` block
of countries.json and the registry-matched works, with page iso ``US-CA``; other regions use
their country entry. Country numbers come from ``site/data/global/countries.json``; institutions,
researchers and partner countries come from the ignored global partition and raw pages; local
sections come from ``regions/<slug>/region.yml``. Offline.

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
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, NamedTuple

import pyarrow.parquet as pq
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.build.region_pages import (  # noqa: E402
    AMBASSADORS,
    PAGE_STATUS,
    SCHEMA_VERSION,
    SCREENING_STATUS,
    TOP_TOPICS,
    WHAT_THIS_IS,
    WHAT_THIS_IS_NOT,
    build_region_payload,
    build_sections,
    encode,
    institutions_block,
    partners_block,
    read_work_countries,
    researchers_block,
    scan_authorships,
    series_block,
    stats_block,
    unconfirmed_items,
    validate_config,
    validate_payload,
)
from atlas.ingest.global_partition import raw_page_paths  # noqa: E402
from atlas.regions.registry import Region, load_registry  # noqa: E402
from atlas.regions.scope import (  # noqa: E402
    DEFAULT_REGION_SLUG,
    region_institution_ids,
)

PARTITION = ROOT / "data" / "processed" / "global"
DEFAULT_WORKS = PARTITION / "works.parquet"
DEFAULT_REGIONS = PARTITION / "work_regions.parquet"
DEFAULT_RAW = ROOT / "data" / "raw" / "openalex_global"
COUNTRIES = ROOT / "site" / "data" / "global" / "countries.json"
EXPLORE = ROOT / "site" / "data" / "global" / "explore.json"
REGION_FILE = "region.json"
# The default region's page is a US subdivision: its country entry is "US" (predicate), but the
# page and its countries.json block are keyed by the ISO 3166-2 code.
DEFAULT_PAGE_ISO = "US-CA"
DEFAULT_COUNTRY = "US"
REGISTRY_BLOCK = "registry_regions"
REGISTRY_KIND = "registry_region"


def _is_default(region: Region) -> bool:
    return region.slug == DEFAULT_REGION_SLUG


def eligible_regions() -> list[Region]:
    """Planned or active regions with one country code (the default region included)."""
    found: list[Region] = []
    for region in load_registry().regions:
        if region.tier == "root":
            continue
        if region.status not in ("planned", "active"):
            continue
        if region.predicate is None or len(region.predicate.country_codes) != 1:
            continue
        found.append(region)
    return found


def _iso(region: Region) -> str:
    if _is_default(region):
        return DEFAULT_PAGE_ISO
    assert region.predicate is not None
    return region.predicate.country_codes[0]


def _config_path(region: Region) -> Path:
    return ROOT / "regions" / region.slug / "region.yml"


# region-v1 keys that validate_config accepts. California's region.yml also holds site and adapter
# wiring (site_path, adapters, ...); those keys are left out before validation, so the library
# stays strict and Norway and Belgium (which have only these keys) load exactly as before.
CONFIG_KEYS = (
    "schema_version",
    "slug",
    "name",
    "iso",
    "tier",
    "languages",
    "local_search_terms",
    "sections",
)


def _load_config(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return validate_config(raw)  # raises RegionConfigError with the usual message
    return validate_config({key: raw[key] for key in CONFIG_KEYS if key in raw})


def _output_path(region: Region) -> Path:
    return ROOT / (region.site_data_dir or f"site/data/{region.slug}") / REGION_FILE


def _country_names() -> dict[str, str]:
    if not EXPLORE.is_file():
        return {}
    countries = json.loads(EXPLORE.read_text(encoding="utf-8")).get("countries") or []
    return {str(c["iso"]): str(c["name"]) for c in countries if c.get("iso") and c.get("name")}


def _read_regions_rows(path: Path) -> list[dict]:
    return pq.read_table(path, columns=["work_id", "region_kind", "region_code"]).to_pylist()


def _registry_entry(countries: Mapping[str, Any], slug: str) -> dict[str, Any] | None:
    """The countries.json ``registry_regions`` block for a registry region slug, if any."""
    return next(
        (r for r in countries.get(REGISTRY_BLOCK) or [] if r.get("region") == slug),
        None,
    )


def _validation_view(region: Region, countries: Mapping[str, Any]) -> Mapping[str, Any]:
    """countries.json shaped so ``validate_payload`` can find the region's page ISO."""
    if not _is_default(region):
        return countries
    entry = _registry_entry(countries, region.slug)
    if entry is None:
        return countries
    return {**countries, "countries": [{**entry, "iso": DEFAULT_PAGE_ISO}]}


class _Inputs(NamedTuple):
    work_countries: dict[str, frozenset[str]]
    authorships: dict[str, list[dict[str, Any]]]
    registry_works: frozenset[str]
    registry_institutions: frozenset[str]


def _partition_inputs(regions: list[Region]) -> _Inputs:
    """Country and registry work sets from the partition; authorships from raw pages."""
    rows = _read_regions_rows(DEFAULT_REGIONS)
    work_countries = read_work_countries(rows)
    registry_works = frozenset(
        r["work_id"]
        for r in rows
        if r["region_kind"] == REGISTRY_KIND and r["region_code"] == DEFAULT_REGION_SLUG
    )
    registry_institutions: frozenset[str] = frozenset()
    wanted: set[str] = set()
    for region in regions:
        if _is_default(region):
            wanted |= registry_works
            registry_institutions = region_institution_ids(region)
        else:
            code = _iso(region)
            wanted |= {w for w, codes in work_countries.items() if code in codes}
    authorships = scan_authorships(raw_page_paths(DEFAULT_RAW), wanted)
    return _Inputs(work_countries, authorships, registry_works, registry_institutions)


def build_california_payload(
    *,
    region: Region,
    config: Mapping[str, Any],
    countries_payload: Mapping[str, Any],
    work_countries: Mapping[str, frozenset[str]],
    authorships: Mapping[str, list[dict[str, Any]]],
    registry_works: Iterable[str],
    registry_institutions: frozenset[str],
    names: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """The region-v1 payload for the default region, counted over its registry-matched works.

    Institutions are the California registry institutions on those works; researchers and
    partner countries use the US country code, as the country pages do. Raises KeyError when
    countries.json has no ``registry_regions`` block for the region.
    """
    entry = _registry_entry(countries_payload, region.slug)
    if entry is None:
        raise KeyError(f"countries.json has no {REGISTRY_BLOCK} entry for {region.slug}")
    work_ids = frozenset(registry_works)
    # Keep only California registry institutions on each work (the institutions "in" the region).
    ca_authorships = {
        work_id: [
            {
                **authorship,
                "institutions": [
                    inst
                    for inst in authorship["institutions"]
                    if inst["id"] in registry_institutions
                ],
            }
            for authorship in authorships.get(work_id, [])
        ]
        for work_id in work_ids
    }
    topics = [
        {"id": t["id"], "name": t["name"], "count": t["count"]}
        for t in (entry.get("top_primary_topics") or [])[:TOP_TOPICS]
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": countries_payload["generated_at"],
        "slug": region.slug,
        "name": region.name,
        "iso": DEFAULT_PAGE_ISO,
        "status": PAGE_STATUS,
        "screening_status": SCREENING_STATUS,
        "what_this_is_and_is_not": {"is": WHAT_THIS_IS, "is_not": WHAT_THIS_IS_NOT},
        "stats": stats_block(
            entry,
            int(countries_payload["years"]["last_complete"]),
            int(entry["works_with_pmid"]),
        ),
        "works_by_year": series_block(entry),
        "top_topics": topics,
        "top_institutions": institutions_block(DEFAULT_COUNTRY, work_ids, ca_authorships),
        "top_researchers": researchers_block(DEFAULT_COUNTRY, work_ids, authorships),
        "partner_countries": partners_block(DEFAULT_COUNTRY, work_ids, work_countries, names or {}),
        "sections": build_sections(config, region.slug),
        "ambassadors": dict(AMBASSADORS),
    }


def _render(region: Region, countries: dict, inputs: _Inputs) -> str:
    config = _load_config(_config_path(region))
    if _is_default(region):
        payload = build_california_payload(
            region=region,
            config=config,
            countries_payload=countries,
            work_countries=inputs.work_countries,
            authorships=inputs.authorships,
            registry_works=inputs.registry_works,
            registry_institutions=inputs.registry_institutions,
            names=_country_names(),
        )
    else:
        payload = build_region_payload(
            slug=region.slug,
            name=region.name,
            iso=_iso(region),
            config=config,
            countries_payload=countries,
            work_countries=inputs.work_countries,
            authorships=inputs.authorships,
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

    inputs_present = DEFAULT_WORKS.is_file() and DEFAULT_REGIONS.is_file()
    if not inputs_present:
        print(
            f"ERROR: missing partition under {PARTITION}; run scripts/partition_global.py",
            file=sys.stderr,
        )
        return 1
    inputs = _partition_inputs(regions)
    for region in regions:
        text = _render(region, countries, inputs)
        payload = json.loads(text)
        problems = validate_payload(payload, _validation_view(region, countries))
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
    available = (
        DEFAULT_WORKS.is_file() and DEFAULT_REGIONS.is_file() and raw_page_paths(DEFAULT_RAW)
    )
    inputs = _partition_inputs(regions) if available else None
    for region in regions:
        out = _output_path(region)
        label = region.slug
        if not out.is_file():
            print(f"FAIL: {label}: missing {out.relative_to(ROOT).as_posix()}")
            failed = True
            continue
        try:
            _load_config(_config_path(region))
        except (ValueError, OSError) as exc:
            print(f"FAIL: {label}: region.yml: {exc}")
            failed = True
            continue
        committed = json.loads(out.read_text(encoding="utf-8"))
        problems = validate_payload(committed, _validation_view(region, countries))
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
        if inputs is not None:
            if out.read_text(encoding="utf-8") != _render(region, countries, inputs):
                print(f"FAIL: {label}: region.json is stale; rerun scripts/build_region_pages.py")
                failed = True
            else:
                print(f"PASS: {label}: freshness")
    if inputs is None:
        print(f"SKIP: staleness; no partition or raw pages under {PARTITION} and {DEFAULT_RAW}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
