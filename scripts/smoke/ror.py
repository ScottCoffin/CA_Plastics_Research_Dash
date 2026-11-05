"""Bounded live smoke checks for the ROR v2 contracts used by S1.1."""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from atlas.util.cost import ApiCostLogger

BASE_URL = "https://api.ror.org/v2/organizations"
USER_AGENT = "CA-Plastics-Research-Atlas/0.1 (S1.1 smoke test)"
UC_BERKELEY_ROR = "01an7q238"


def request_json(
    path: str,
    params: dict[str, object] | None,
    logger: ApiCostLogger,
) -> tuple[int, dict[str, str], dict[str, Any]]:
    query = f"?{urllib.parse.urlencode(params, safe=':')}" if params else ""
    url = f"{BASE_URL}{path}{query}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.load(response)
        headers = dict(response.headers.items())
        status = response.status
    logger.record(source="ror", method="GET", url=url, status_code=status, credits=0, cost_usd=0)
    return status, headers, body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--usage-log", type=Path, default=Path("data/logs/api_usage.jsonl"))
    args = parser.parse_args()
    run_id = f"ror-smoke-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"

    with ApiCostLogger(run_id, args.usage_log) as logger:
        page_ids: list[set[str]] = []
        result_count = 0
        for page in (1, 2):
            status, _, body = request_json(
                "",
                {
                    "query.advanced": (
                        "locations.geonames_details.country_subdivision_name:California"
                    ),
                    "page": page,
                },
                logger,
            )
            assert status == 200
            assert len(body["items"]) == 20
            assert all(
                item["locations"][0]["geonames_details"]["country_subdivision_name"] == "California"
                for item in body["items"]
            )
            result_count = body["number_of_results"]
            page_ids.append({item["id"] for item in body["items"]})
        assert page_ids[0].isdisjoint(page_ids[1])

        status, headers, record = request_json(f"/{UC_BERKELEY_ROR}", None, logger)
        assert status == 200
        assert record["id"] == f"https://ror.org/{UC_BERKELEY_ROR}"
        location = record["locations"][0]["geonames_details"]
        assert location["country_subdivision_code"] == "CA"
        assert location["country_subdivision_name"] == "California"
        assert record["admin"]["last_modified"]["schema_version"] == "2.1"
        assert record["types"]
        summary = logger.close()

    print(
        json.dumps(
            {
                "api_version": "v2",
                "schema_version": "2.1",
                "california_advanced_query_results": result_count,
                "pagination": "page parameter; 20 records per page",
                "sample_id": record["id"],
                "sample_types": record["types"],
                "sample_location": location,
                "rate_limit_headers_observed": {
                    key: value for key, value in headers.items() if "ratelimit" in key.casefold()
                },
                "usage": summary,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
