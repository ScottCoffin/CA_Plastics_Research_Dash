"""Bounded live smoke checks for the OpenAlex contracts used by S1.1."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas.util.cost import ApiCostLogger

BASE_URL = "https://api.openalex.org"
USER_AGENT = "CA-Plastics-Research-Atlas/0.1 (S1.1 smoke test)"
TEST_INSTITUTION_ID = "I97018004"  # Stanford University


def request_json(
    path: str,
    params: dict[str, object],
    logger: ApiCostLogger,
) -> tuple[str, int, dict[str, str], dict[str, Any]]:
    query = urllib.parse.urlencode(params, safe=':,|*"')
    url = f"{BASE_URL}{path}?{query}"
    headers = {"User-Agent": USER_AGENT}
    api_key = os.environ.get("OPENALEX_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.load(response)
            response_headers = dict(response.headers.items())
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
        response_headers = dict(error.headers.items())
        body = json.loads(error.read().decode("utf-8"))
    logger.record_openalex_response(
        method="GET", url=url, status_code=status, headers=response_headers, body=body
    )
    return url, status, response_headers, body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--usage-log", type=Path, default=Path("data/logs/api_usage.jsonl"))
    args = parser.parse_args()
    run_id = f"openalex-smoke-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"

    with ApiCostLogger(run_id, args.usage_log) as logger:
        page_ids: list[set[str]] = []
        institution_count = 0
        for page in (1, 2):
            _, status, _, body = request_json(
                "/institutions",
                {"filter": "geo.region:California", "per_page": 2, "page": page},
                logger,
            )
            assert status == 200
            assert body["meta"]["page"] == page
            assert all(item["geo"]["region"] == "California" for item in body["results"])
            institution_count = body["meta"]["count"]
            page_ids.append({item["id"] for item in body["results"]})
        assert page_ids[0].isdisjoint(page_ids[1])

        filter_counts: dict[str, int] = {}
        for field in ("institutions.id", "authorships.institutions.id"):
            _, status, _, body = request_json(
                "/works",
                {"filter": f"{field}:{TEST_INSTITUTION_ID}", "per_page": 1, "cursor": "*"},
                logger,
            )
            assert status == 200
            assert body["meta"]["next_cursor"]
            filter_counts[field] = body["meta"]["count"]
        assert len(set(filter_counts.values())) == 1

        batch_results: dict[int, dict[str, object]] = {}
        for size in (100, 101):
            ids = "|".join([TEST_INSTITUTION_ID] * size)
            url, status, _, body = request_json(
                "/works", {"filter": f"institutions.id:{ids}", "per_page": 1}, logger
            )
            batch_results[size] = {
                "status": status,
                "url_bytes": len(url.encode("utf-8")),
                "message": body.get("message"),
            }
        assert batch_results[100]["status"] == 200
        assert batch_results[101]["status"] == 400
        assert "100 or below" in str(batch_results[101]["message"])

        summary = logger.close()

    print(
        json.dumps(
            {
                "california_region_value": "California",
                "california_institution_count": institution_count,
                "pagination": (
                    "page/per_page for bounded institution smoke; cursor initialized for works"
                ),
                "works_filter_counts": filter_counts,
                "institution_id_batch_results": batch_results,
                "authenticated": bool(os.environ.get("OPENALEX_API_KEY")),
                "usage": summary,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
