"""Scope values read from the region registry by the engine (PLAT-3 slice 2).

Every helper takes an optional ``region``; ``None`` means the default region
(``california``), so existing call sites keep today's behaviour. The registry is read
once for the default region and cached. CLIs read the registry at call time so tests can
point them at a tmp-path registry through ``REGISTRY_PATH``.
"""

from __future__ import annotations

import argparse
from functools import cache
from pathlib import Path

from atlas.regions.registry import (
    DEFAULT_REGISTRY_PATH,
    REPO_ROOT,
    SITE_DATA_ROOT,
    Predicate,
    Region,
    get_region,
    load_registry,
)

DEFAULT_REGION_SLUG = "california"
# Commands accept only these slugs for now; other registered regions are rejected (PLAT-3).
SUPPORTED_REGION_SLUGS = frozenset({DEFAULT_REGION_SLUG})
REGISTRY_PATH: Path = DEFAULT_REGISTRY_PATH


@cache
def default_region() -> Region:
    """The default region from the registry (cached)."""
    return get_region(DEFAULT_REGION_SLUG)


def resolve_region(region: Region | None = None) -> Region:
    return default_region() if region is None else region


def _predicate(region: Region | None) -> Predicate:
    resolved = resolve_region(region)
    if resolved.predicate is None:
        raise ValueError(f"region {resolved.slug!r} has no predicate (root tier)")
    return resolved.predicate


def region_data_dir(region: Region | None = None) -> Path:
    """Absolute folder for the region's public site payloads (PLAT-3 slice 3).

    The registry's ``site_data_dir`` (repo-relative, validated to sit under ``site/data``)
    wins. A region without it gets ``site/data/<slug>``. California sets ``site/data``.
    """
    resolved = resolve_region(region)
    relative = resolved.site_data_dir or str(SITE_DATA_ROOT / resolved.slug)
    return REPO_ROOT / relative


def institution_filter(region: Region | None = None) -> str:
    """OpenAlex ``/institutions`` filter for the region's institution seed."""
    value = _predicate(region).openalex_institution_filter
    if value is None:
        raise ValueError(f"region {resolve_region(region).slug!r} has no institution filter")
    return value


def institution_region_names(region: Region | None = None) -> tuple[str, ...]:
    """Values of an institution's region (OpenAlex ``geo.region``) that belong to the region."""
    return _predicate(region).institution_region_names


def ror_subdivision_codes(region: Region | None = None) -> tuple[str, ...]:
    """GeoNames ``country_subdivision_code`` values on a ROR location that belong to the region."""
    return _predicate(region).ror_subdivision_codes


def country_codes(region: Region | None = None) -> tuple[str, ...]:
    """Country codes (ISO 3166-1 alpha-2) whose institutions can carry the region flag."""
    return _predicate(region).country_codes


def raw_affiliation_search_term(region: Region | None = None) -> str:
    """The region-wide raw-affiliation search term. By convention the first listed term."""
    terms = _predicate(region).raw_affiliation_terms
    if not terms:
        raise ValueError(f"region {resolve_region(region).slug!r} has no raw affiliation terms")
    return terms[0]


def add_region_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION_SLUG,
        metavar="SLUG",
        help=f"region slug from regions/_registry.yml (default {DEFAULT_REGION_SLUG}; "
        "only california is supported today)",
    )


def resolve_cli_region(parser: argparse.ArgumentParser, slug: str) -> Region:
    """Return the registry region for a CLI ``--region`` value, or exit 2 via ``parser.error``."""
    try:
        region = load_registry(REGISTRY_PATH).get(slug)
    except KeyError as error:
        parser.error(str(error.args[0]))
    if slug not in SUPPORTED_REGION_SLUGS:
        parser.error(f"region {slug} is registered but not yet supported by this command (PLAT-3)")
    return region
