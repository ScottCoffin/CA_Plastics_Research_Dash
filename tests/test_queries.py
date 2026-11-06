from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas.query import (
    QueryCacheError,
    load_query_config,
    openalex_url,
    read_count_cache,
    render_query,
    write_count_cache,
)


def test_owner_query_renders_from_structured_terms() -> None:
    config = load_query_config()
    rendered = render_query(config)
    supplied = " ".join(config["openalex"]["query_expression"].split())
    assert rendered == supplied
    assert "microfiber" in rendered and "optical" not in rendered
    assert "microplastic strain" in rendered


def test_openalex_filter_is_encoded_as_one_value() -> None:
    config = load_query_config()
    url = openalex_url(config, per_page=1, group_by="publication_year")
    assert " " not in url and '"' not in url and "(" not in url
    assert "filter=title_and_abstract.search%3A" in url


def test_count_cache_rejects_legacy_and_mismatched_payloads(tmp_path: Path) -> None:
    config = load_query_config()
    rendered = render_query(config)
    legacy = tmp_path / "legacy.json"
    legacy.write_text("123\n", encoding="utf-8")
    with pytest.raises(QueryCacheError):
        read_count_cache(legacy, query_version=config["version"], rendered_query=rendered)

    cache = tmp_path / "count.json"
    write_count_cache(cache, config=config, rendered_query=rendered, count=12)
    loaded = read_count_cache(cache, query_version=config["version"], rendered_query=rendered)
    assert loaded["count"] == 12
    payload = json.loads(cache.read_text(encoding="utf-8"))
    payload["query_version"] = "old-version"
    cache.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(QueryCacheError):
        read_count_cache(cache, query_version=config["version"], rendered_query=rendered)
