"""Region registry loader (PLAT-3 slice 1).

Reads ``regions/_registry.yml`` and validates it strictly. Nothing calls this yet; later
slices wire ``--region`` and the site to it. Pure stdlib plus PyYAML.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

SCHEMA_VERSION = 1
TIERS = frozenset({"root", "A", "B", "C"})
STATUSES = frozenset({"active", "planned", "retired"})
REGION_KEYS = frozenset({"slug", "name", "tier", "parent", "status", "predicate"})
OPTIONAL_REGION_KEYS = frozenset({"site_data_dir"})
SITE_DATA_ROOT = PurePosixPath("site/data")
PREDICATE_LIST_KEYS = (
    "ror_subdivision_codes",
    "country_codes",
    "institution_region_names",
    "raw_affiliation_terms",
    "ca_basis_values",
)
PREDICATE_KEYS = frozenset(
    {"openalex_institution_filter", "institution_registry", *PREDICATE_LIST_KEYS}
)
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]*$")
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "regions" / "_registry.yml"


@dataclass(frozen=True)
class Predicate:
    """Which authorships and institutions belong to a region. Empty fields are unused."""

    openalex_institution_filter: str | None = None
    # Repo-relative Parquet with an ``openalex_id`` column (PLAT-4b slice 2); None means unused.
    institution_registry: str | None = None
    ror_subdivision_codes: tuple[str, ...] = ()
    country_codes: tuple[str, ...] = ()
    institution_region_names: tuple[str, ...] = ()
    raw_affiliation_terms: tuple[str, ...] = ()
    ca_basis_values: tuple[str, ...] = ()


@dataclass(frozen=True)
class Region:
    slug: str
    name: str
    tier: str
    parent: str | None
    status: str
    predicate: Predicate | None = field(default=None)
    # Repo-relative data folder (PLAT-3 slice 3). None means the default site/data/<slug>.
    site_data_dir: str | None = field(default=None)


@dataclass(frozen=True)
class Registry:
    schema_version: int
    regions: tuple[Region, ...]

    def get(self, slug: str) -> Region:
        for region in self.regions:
            if region.slug == slug:
                return region
        raise KeyError(f"unknown region slug: {slug!r}")

    def by_tier(self, tier: str | None = None) -> tuple[Region, ...]:
        if tier is None:
            return self.regions
        if tier not in TIERS:
            raise ValueError(f"unknown tier {tier!r}; expected one of {sorted(TIERS)}")
        return tuple(region for region in self.regions if region.tier == tier)


def _fail(where: str, message: str) -> ValueError:
    return ValueError(f"region registry {where}: {message}")


def _check_keys(
    where: str, mapping: Any, allowed: frozenset[str], required: frozenset[str]
) -> None:
    if not isinstance(mapping, dict):
        raise _fail(where, f"expected a mapping, got {type(mapping).__name__}")
    unknown = set(mapping) - allowed
    if unknown:
        raise _fail(where, f"unknown keys {sorted(unknown)}")
    missing = required - set(mapping)
    if missing:
        raise _fail(where, f"missing keys {sorted(missing)}")


def _parse_institution_registry(where: str, raw: Any) -> str | None:
    """Validate an optional ``institution_registry``: repo-relative, ``.parquet``, no ``..``."""
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise _fail(where, "institution_registry must be a non-empty string or null")
    if "\\" in raw or ":" in raw:
        raise _fail(where, f"institution_registry {raw!r} must use forward slashes and no drive")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise _fail(where, f"institution_registry {raw!r} must be repo-relative, no '..'")
    if path.suffix != ".parquet":
        raise _fail(where, f"institution_registry {raw!r} must be a .parquet file")
    return str(path)


def _parse_predicate(where: str, raw: Any) -> Predicate:
    _check_keys(where, raw, PREDICATE_KEYS, frozenset())
    filter_value = raw.get("openalex_institution_filter")
    if filter_value is not None and (not isinstance(filter_value, str) or not filter_value):
        raise _fail(where, "openalex_institution_filter must be a non-empty string or null")
    registry_path = _parse_institution_registry(where, raw.get("institution_registry"))
    lists: dict[str, tuple[str, ...]] = {}
    for key in PREDICATE_LIST_KEYS:
        value = raw.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
            raise _fail(where, f"{key} must be a list of non-empty strings")
        lists[key] = tuple(value)
    return Predicate(
        openalex_institution_filter=filter_value, institution_registry=registry_path, **lists
    )


def _parse_site_data_dir(where: str, raw: Any) -> str | None:
    """Validate an optional ``site_data_dir``: repo-relative, inside ``site/data``, no ``..``."""
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise _fail(where, "site_data_dir must be a non-empty string or absent")
    if "\\" in raw or ":" in raw:
        raise _fail(where, f"site_data_dir {raw!r} must use forward slashes and no drive")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        raise _fail(where, f"site_data_dir {raw!r} must be relative and must not contain '..'")
    if path.parts[: len(SITE_DATA_ROOT.parts)] != SITE_DATA_ROOT.parts:
        raise _fail(where, f"site_data_dir {raw!r} must stay under site/data")
    return str(path)


def parse_registry(data: Any) -> Registry:
    """Validate an already-loaded registry mapping and return it."""
    if not isinstance(data, dict):
        raise _fail("file", f"expected a mapping at top level, got {type(data).__name__}")
    top_keys = frozenset({"schema_version", "regions"})
    _check_keys("file", data, top_keys, top_keys)
    if data["schema_version"] != SCHEMA_VERSION:
        raise _fail(
            "file", f"schema_version must be {SCHEMA_VERSION}, got {data['schema_version']!r}"
        )
    entries = data["regions"]
    if not isinstance(entries, list) or not entries:
        raise _fail("file", "regions must be a non-empty list")

    slugs: set[str] = set()
    raw_regions: list[tuple[str, dict[str, Any]]] = []
    for index, entry in enumerate(entries):
        where = f"regions[{index}]"
        _check_keys(where, entry, REGION_KEYS | OPTIONAL_REGION_KEYS, REGION_KEYS)
        slug = entry["slug"]
        if not isinstance(slug, str) or not SLUG_RE.match(slug):
            raise _fail(where, f"slug {slug!r} must be lowercase letters, digits or hyphens")
        where = f"region {slug!r}"
        if slug in slugs:
            raise _fail(where, "duplicate slug")
        slugs.add(slug)
        raw_regions.append((where, entry))

    regions: list[Region] = []
    for where, entry in raw_regions:
        name = entry["name"]
        if not isinstance(name, str) or not name.strip():
            raise _fail(where, "name must be a non-empty string")
        if entry["tier"] not in TIERS:
            raise _fail(where, f"tier {entry['tier']!r} must be one of {sorted(TIERS)}")
        if entry["status"] not in STATUSES:
            raise _fail(where, f"status {entry['status']!r} must be one of {sorted(STATUSES)}")
        parent = entry["parent"]
        if parent is not None:
            if not isinstance(parent, str) or parent not in slugs:
                raise _fail(where, f"unknown parent {parent!r}")
            if parent == entry["slug"]:
                raise _fail(where, "a region cannot be its own parent")
        if entry["tier"] == "root":
            if parent is not None:
                raise _fail(where, "root tier must have parent null")
            if entry["predicate"] is not None:
                raise _fail(where, "root tier must have predicate null")
            predicate = None
        else:
            if entry["predicate"] is None:
                raise _fail(where, f"tier {entry['tier']} needs a predicate")
            predicate = _parse_predicate(where, entry["predicate"])
        regions.append(
            Region(
                slug=entry["slug"],
                name=name,
                tier=entry["tier"],
                parent=parent,
                status=entry["status"],
                predicate=predicate,
                site_data_dir=_parse_site_data_dir(where, entry.get("site_data_dir")),
            )
        )
    return Registry(schema_version=SCHEMA_VERSION, regions=tuple(regions))


def load_registry(path: Path | str = DEFAULT_REGISTRY_PATH) -> Registry:
    """Load and validate the region registry YAML at ``path``."""
    text = Path(path).read_text(encoding="utf-8")
    return parse_registry(yaml.safe_load(text))


def get_region(slug: str, path: Path | str = DEFAULT_REGISTRY_PATH) -> Region:
    """Return the region with ``slug`` from the registry at ``path``."""
    return load_registry(path).get(slug)


def regions(
    tier: str | None = None, path: Path | str = DEFAULT_REGISTRY_PATH
) -> tuple[Region, ...]:
    """Every region in the registry, optionally filtered to one tier."""
    return load_registry(path).by_tier(tier)
