"""Machine acceptance checks for S1.5 query configuration and audit evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from atlas.query import (
    load_query_config,
    openalex_filter,
    openalex_url,
    read_count_cache,
    render_query,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cache", type=Path, default=Path("data/interim/openalex_query_counts.json")
    )
    parser.add_argument("--audit", type=Path, default=Path("docs/query_audit_s1_5.md"))
    args = parser.parse_args()

    config = load_query_config()
    rendered = render_query(config)
    assert config["version"] == "plastic-v2-candidate"
    assert config["status"] == "owner_supplied_candidate"
    assert config["core_terms"] and config["tier_2_terms"] and config["exclusions"]
    assert all(item["term"] and item["any_context"] for item in config["qualified_terms"])
    supplied = config["openalex"]["query_expression"].replace("\n", " ")
    assert rendered == " ".join(supplied.split())
    assert openalex_filter(config).startswith("title_and_abstract.search:")

    url = openalex_url(config, per_page=1, group_by="publication_year")
    query = urlsplit(url).query
    assert " " not in query and '"' not in query and "(" not in query
    assert parse_qs(query)["filter"][0] == openalex_filter(config)

    cache = read_count_cache(args.cache, query_version=config["version"], rendered_query=rendered)
    assert cache is not None and cache["count"] > 0
    assert cache.get("timestamp_utc")
    assert args.audit.exists()
    audit = args.audit.read_text(encoding="utf-8")
    for marker in ("Precision spot check", "Recall spot check", "UCSF", "SLAC", "Global"):
        assert marker in audit
    assert "PASS" in audit
    payload = json.loads(args.cache.read_text(encoding="utf-8"))
    assert payload["query_version"] == config["version"]
    assert payload["rendered_query"] == rendered
    print(f"S1.5 acceptance passed: count={cache['count']:,}, version={config['version']}")


if __name__ == "__main__":
    main()
