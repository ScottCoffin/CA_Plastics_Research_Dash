"""Region registry and predicates (PLAT-3 slice 1). See docs/PLATFORM_ARCHITECTURE.md."""

from atlas.regions.registry import (
    DEFAULT_REGISTRY_PATH,
    Predicate,
    Region,
    Registry,
    get_region,
    load_registry,
    parse_registry,
    regions,
)

__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "Predicate",
    "Region",
    "Registry",
    "get_region",
    "load_registry",
    "parse_registry",
    "regions",
]
