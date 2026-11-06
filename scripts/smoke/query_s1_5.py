"""S1.5 OpenAlex query, count, and audit runner."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote_plus, urlsplit

from atlas.query import (
    load_query_config,
    openalex_filter,
    openalex_url,
    read_count_cache,
    render_query,
    write_count_cache,
)
from atlas.util.cost import ApiCostLogger

USER_AGENT = "CA-Plastics-Research-Atlas/0.1 (S1.5 query smoke; contact via GitHub)"
UCSF_ID = "I180670191"
SLAC_ID = "I2801935854"


def _load_local_key(path: Path = Path(".env")) -> None:
    if os.environ.get("OPENALEX_API_KEY") or not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        name, value = line.split("=", 1)
        if name.strip() in {"OPENALEX_API_KEY", "OPEN_ALEX_API_KEY"}:
            os.environ["OPENALEX_API_KEY"] = value.strip().strip('"').strip("'")
            return


def request_json(url: str, logger: ApiCostLogger) -> tuple[int, dict[str, str], dict[str, Any]]:
    headers = {"User-Agent": USER_AGENT}
    if os.environ.get("OPENALEX_API_KEY"):
        headers["Authorization"] = f"Bearer {os.environ['OPENALEX_API_KEY']}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = response.status
            headers_out = dict(response.headers.items())
            body = json.load(response)
    except urllib.error.HTTPError as error:
        status = error.code
        headers_out = dict(error.headers.items())
        body = json.loads(error.read().decode("utf-8"))
    logger.record_openalex_response(
        method="GET", url=url, status_code=status, headers=headers_out, body=body
    )
    return status, headers_out, body


def _assert_encoded(url: str, filter_value: str) -> None:
    raw_query = urlsplit(url).query
    assert " " not in raw_query and '"' not in raw_query and "(" not in raw_query
    parsed = parse_qs(raw_query)
    assert parsed["filter"][0] == filter_value
    assert unquote_plus(raw_query) != raw_query


def _abstract_text(work: dict[str, Any]) -> str:
    index = work.get("abstract_inverted_index") or {}
    words: list[tuple[int, str]] = []
    for word, positions in index.items():
        words.extend((int(position), word) for position in positions)
    return " ".join(word for _, word in sorted(words))


def _sample_record(work: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": work.get("id"),
        "doi": work.get("doi"),
        "title": work.get("title"),
        "publication_year": work.get("publication_year"),
        "abstract": _abstract_text(work)[:1200],
    }


def _sample_url(config: dict[str, Any], extra_filters: list[str] | None = None) -> str:
    return openalex_url(
        config,
        extra_filters=extra_filters,
        per_page=10,
        sort="cited_by_count:desc",
        select="id,doi,title,publication_year,abstract_inverted_index",
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    _load_local_key()
    config = load_query_config(args.config)
    rendered_query = render_query(config)
    filter_value = openalex_filter(config)
    encoded_url = openalex_url(config, per_page=1, group_by="publication_year")
    _assert_encoded(encoded_url, filter_value)
    positive_url = openalex_url(
        config, per_page=1, group_by="publication_year", include_exclusions=False
    )
    cache_error: str | None = None
    try:
        read_count_cache(args.cache, query_version=config["version"], rendered_query=rendered_query)
    except ValueError as error:
        cache_error = str(error)

    with ApiCostLogger(args.run_id, args.usage_log) as logger:
        status, _, count_body = request_json(encoded_url, logger)
        assert status == 200, count_body
        count = int(count_body["meta"]["count"])
        assert isinstance(count_body.get("group_by"), list)
        assert count_body["meta"].get("groups_count", 0) > 0

        positive_status, _, positive_body = request_json(positive_url, logger)
        assert positive_status == 200, positive_body
        positive_count = int(positive_body["meta"]["count"])
        assert positive_count >= count

        samples: dict[str, list[dict[str, Any]]] = {}
        for label, institution_id in (("ucsf", UCSF_ID), ("slac", SLAC_ID)):
            status, _, body = request_json(
                _sample_url(config, [f"institutions.id:{institution_id}"]), logger
            )
            assert status == 200, body
            samples[label] = [_sample_record(work) for work in body.get("results", [])]
        status, _, body = request_json(_sample_url(config), logger)
        assert status == 200, body
        samples["global"] = [_sample_record(work) for work in body.get("results", [])]
        known = json.loads(args.known.read_text(encoding="utf-8"))
        known_ids = [item["id"].rsplit("/", 1)[-1] for item in known]
        recall_status, _, recall_body = request_json(
            _sample_url(config, [f"openalex_id:{'|'.join(known_ids)}"]), logger
        )
        assert recall_status == 200, recall_body
        matched_ids = {work["id"].rsplit("/", 1)[-1] for work in recall_body.get("results", [])}
        usage = logger.close()

    cache_payload = write_count_cache(
        args.cache,
        config=config,
        rendered_query=rendered_query,
        count=count,
        usage=usage,
    )
    result = {
        "timestamp_utc": cache_payload["timestamp_utc"],
        "query_version": config["version"],
        "field": config["openalex"]["field"],
        "rendered_query": rendered_query,
        "count": count,
        "positive_count_without_exclusions": positive_count,
        "boolean_exclusions_reduced_count": positive_count >= count,
        "group_by": {
            "groups_count": count_body["meta"].get("groups_count"),
            "sample_groups": count_body.get("group_by", [])[:3],
        },
        "cache": {"path": str(args.cache), "replaced_invalid_cache": cache_error},
        "authenticated": bool(os.environ.get("OPENALEX_API_KEY")),
        "usage": usage,
        "samples": samples,
        "recall": {
            "known": known,
            "matched_ids": sorted(matched_ids),
            "all_known_matched": set(known_ids) <= matched_ids,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: result[key] for key in ("timestamp_utc", "query_version", "count", "usage")},
            indent=2,
        )
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/queries.yml"))
    parser.add_argument(
        "--cache", type=Path, default=Path("data/interim/openalex_query_counts.json")
    )
    parser.add_argument("--output", type=Path, default=Path("data/interim/s1_5_audit.json"))
    parser.add_argument("--usage-log", type=Path, default=Path("data/logs/api_usage.jsonl"))
    parser.add_argument(
        "--run-id", default=f"query-s1-5-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    )
    parser.add_argument(
        "--known", type=Path, default=Path("tests/fixtures/s1_5_known_relevant.json")
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
