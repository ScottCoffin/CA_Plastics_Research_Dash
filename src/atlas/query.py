"""Versioned OpenAlex query rendering and count-cache validation."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import yaml


class QueryCacheError(ValueError):
    """Raised when a count cache is not tied to the requested query."""


def load_query_config(path: str | Path = "config/queries.yml") -> dict[str, Any]:
    """Load and validate the structured plastics-query configuration."""

    config = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("query configuration must be a mapping")
    for key in ("version", "core_terms", "qualified_terms", "tier_2_terms", "exclusions"):
        if key not in config:
            raise ValueError(f"query configuration is missing {key!r}")
    if not isinstance(config["version"], str) or not config["version"].strip():
        raise ValueError("query version must be a non-empty string")
    if not isinstance(config["qualified_terms"], list):
        raise ValueError("qualified_terms must be a list")
    return config


def _term(term: str) -> str:
    """Format one configured term for OpenAlex Boolean filter syntax."""

    if not isinstance(term, str) or not term.strip():
        raise ValueError("query terms must be non-empty strings")
    value = term.strip()
    return value if re.fullmatch(r"[A-Za-z0-9]+", value) else f'"{value}"'


def render_query(config: Mapping[str, Any], *, include_exclusions: bool = True) -> str:
    """Render the configured core query without maintaining a second term list."""

    positive = [_term(term) for term in config["core_terms"]]
    for qualified in config["qualified_terms"]:
        if not isinstance(qualified, Mapping):
            raise ValueError("each qualified term must be a mapping")
        term = _term(qualified["term"])
        contexts = [_term(value) for value in qualified["any_context"]]
        if not contexts:
            raise ValueError(f"qualified term has no context: {qualified['term']!r}")
        positive.append(f"({term} AND ({' OR '.join(contexts)}))")
    expression = f"({' OR '.join(positive)})"
    if include_exclusions:
        exclusions = [_term(term) for term in config["exclusions"]]
        if exclusions:
            expression += f" NOT ({' OR '.join(exclusions)})"
    return expression


def openalex_filter(config: Mapping[str, Any], *, include_exclusions: bool = True) -> str:
    """Return the complete OpenAlex filter value for the configured field."""

    field = config.get("openalex", {}).get("field", "title_and_abstract.search")
    return f"{field}:{render_query(config, include_exclusions=include_exclusions)}"


_TYPE_SLUG = re.compile(r"[a-z][a-z-]*")


def type_filters(config: Mapping[str, Any]) -> list[str]:
    """OpenAlex filters dropping non-research types (``exclude_types``, AT-1 v3).

    Each type becomes its own ``type:!<slug>`` filter; OpenAlex ANDs repeated keys
    (verified 2026-11-10). Configs without the key (v2) return no filters.
    """
    types = config.get("exclude_types") or []
    if not isinstance(types, list) or not all(
        isinstance(t, str) and _TYPE_SLUG.fullmatch(t) for t in types
    ):
        raise ValueError("exclude_types must be a list of OpenAlex type slugs")
    return [f"type:!{slug}" for slug in types]


def always_include_filters(config: Mapping[str, Any]) -> list[str]:
    """Scope filters whose works are ingested regardless of terms and institutions.

    Used for owner-designated groups with no usable OpenAlex institution record
    (Moore Institute for Plastic Pollution Research, AT-1 v3). Each entry needs a
    ``filter`` on ``raw_affiliation_strings.search`` and a ``reason``.
    """
    entries = config.get("always_include") or []
    if not isinstance(entries, list):
        raise ValueError("always_include must be a list")
    filters = []
    for entry in entries:
        if not isinstance(entry, Mapping) or not str(entry.get("reason") or "").strip():
            raise ValueError("each always_include entry needs a filter and a reason")
        value = str(entry.get("filter") or "")
        if not value.startswith("raw_affiliation_strings.search:") or "," in value:
            raise ValueError("always_include filters must be one raw_affiliation_strings.search")
        filters.append(value)
    return filters


def openalex_url(
    config: Mapping[str, Any],
    *,
    extra_filters: list[str] | None = None,
    include_exclusions: bool = True,
    **params: object,
) -> str:
    """Build a fully encoded OpenAlex works URL."""

    filters = [
        openalex_filter(config, include_exclusions=include_exclusions),
        *type_filters(config),
    ]
    filters.extend(extra_filters or [])
    query_params: dict[str, object] = {"filter": ",".join(filters), **params}
    return "https://api.openalex.org/works?" + urlencode(query_params)


def read_count_cache(
    path: str | Path,
    *,
    query_version: str,
    rendered_query: str,
) -> dict[str, Any] | None:
    """Read only a cache carrying the exact current query identity.

    A legacy scalar cache or a cache from another query is deliberately rejected
    rather than silently reused. The next successful count run overwrites it.
    """

    cache_path = Path(path)
    if not cache_path.exists():
        return None
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise QueryCacheError(f"invalid count cache: {cache_path}") from error
    if not isinstance(payload, Mapping):
        raise QueryCacheError("legacy flat count cache has no query identity")
    if payload.get("query_version") != query_version:
        raise QueryCacheError("count cache query_version does not match")
    if payload.get("rendered_query") != rendered_query:
        raise QueryCacheError("count cache rendered_query does not match")
    if not isinstance(payload.get("count"), int) or payload["count"] < 0:
        raise QueryCacheError("count cache count must be a non-negative integer")
    return dict(payload)


def write_count_cache(
    path: str | Path,
    *,
    config: Mapping[str, Any],
    rendered_query: str,
    count: int,
    timestamp_utc: str | None = None,
    usage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Write a versioned count cache and return its JSON-serializable payload."""

    payload: dict[str, Any] = {
        "query_version": config["version"],
        "query_field": config.get("openalex", {}).get("field", "title_and_abstract.search"),
        "rendered_query": rendered_query,
        "scope": "core",
        "count": int(count),
        "timestamp_utc": timestamp_utc or datetime.now(UTC).isoformat(),
        "source": "OpenAlex works meta.count",
    }
    if usage is not None:
        payload["usage"] = dict(usage)
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload
