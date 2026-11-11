from __future__ import annotations

import urllib.parse

import pytest

from atlas.ingest.openalex import build_works_url
from atlas.query import (
    always_include_filters,
    load_query_config,
    openalex_filter,
    type_filters,
)

V3 = "config/queries_v3.yml"


def _filters(url: str) -> list[str]:
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["filter"][0].split(",")


def test_v3_config_loads_with_type_exclusions_and_moore_rule() -> None:
    config = load_query_config(V3)
    assert config["version"] == "plastic-v3-candidate"
    assert type_filters(config) == [
        "type:!erratum",
        "type:!peer-review",
        "type:!retraction",
        "type:!paratext",
    ]
    scopes = always_include_filters(config)
    assert any("Moore Institute for Plastic Pollution Research" in s for s in scopes)
    # "microplasticity" stems onto "microplastic" in OpenAlex and must never be excluded.
    assert "microplasticity" not in config["exclusions"]
    assert "macroplastic" in config["core_terms"]


def test_v2_archive_is_unchanged_by_the_new_keys() -> None:
    config = load_query_config("config/queries_v2.yml")
    assert config["version"] == "plastic-v2-candidate"
    assert type_filters(config) == [] and always_include_filters(config) == []


def test_active_config_is_promoted_v3_1() -> None:
    config = load_query_config()
    assert config["version"] == "plastic-v3.1" and config["status"] == "active"
    assert type_filters(config) == type_filters(load_query_config(V3))
    assert always_include_filters(config) == always_include_filters(load_query_config(V3))
    terms = {item["term"]: item["any_context"] for item in config["qualified_terms"]}
    # Repeat audit (docs/QUERY_AUDIT.md): unqualified trash and bioplastic were noise.
    assert "trash" not in terms and "bioplastic" in terms
    assert "bioplastic" not in config["core_terms"]
    assert "trash" not in terms["litter"]


def test_institution_and_scope_requests() -> None:
    config = load_query_config(V3)
    inst = _filters(build_works_url(config, ["I1", "I2"], start_date="2024-01-01"))
    assert inst[0] == openalex_filter(config).split(",")[0] or inst[0].startswith(
        "title_and_abstract.search:"
    )
    assert "institutions.id:I1|I2" in inst and "type:!erratum" in inst
    scope = always_include_filters(config)[0]
    moore = _filters(build_works_url(config, [], scope_filter=scope, start_date="2024-01-01"))
    assert moore[0] == scope
    assert not any(f.startswith(("title_and_abstract", "institutions.id")) for f in moore)
    assert "type:!paratext" in moore and "from_publication_date:2024-01-01" in moore
    with pytest.raises(ValueError, match="no institution or author IDs"):
        build_works_url(config, ["I1"], scope_filter=scope)
    with pytest.raises(ValueError, match="at least one institution"):
        build_works_url(config, [])


def test_invalid_new_keys_are_rejected() -> None:
    with pytest.raises(ValueError, match="type slugs"):
        type_filters({"exclude_types": ["erratum", "Bad Type"]})
    with pytest.raises(ValueError, match="reason"):
        always_include_filters({"always_include": [{"filter": "raw_affiliation_strings.search:x"}]})
    with pytest.raises(ValueError, match="raw_affiliation_strings"):
        always_include_filters(
            {"always_include": [{"filter": "institutions.id:I1", "reason": "x"}]}
        )
