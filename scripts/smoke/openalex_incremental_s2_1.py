"""Verify OpenAlex publication-date and updated-since filter behavior."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from atlas.ingest.openalex import OPENALEX_BASE, load_openalex_key
from atlas.util.cost import ApiCostLogger


def request(url: str, logger: ApiCostLogger) -> tuple[int, dict[str, Any], str]:
    req = urllib.request.Request(
        url, headers={"User-Agent": "CA-Plastics-Research-Atlas/0.1 (S2.1 smoke)"}
    )
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = json.load(response)
            headers = dict(response.headers.items())
            logger.record_openalex_response(
                method="GET", url=url, status_code=response.status, headers=headers, body=body
            )
            return response.status, body, "accepted"
    except urllib.error.HTTPError as error:
        headers = dict(error.headers.items())
        try:
            body = json.loads(error.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            body = {}
        logger.record_openalex_response(
            method="GET", url=url, status_code=error.code, headers=headers, body=body
        )
        return error.code, body, str(body.get("message") or body.get("error") or "rejected")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usage-log", type=Path, default=Path("data/logs/api_usage.jsonl"))
    parser.add_argument("--institution", default="I97018004")
    args = parser.parse_args()
    load_openalex_key()
    filters = {
        "publication_window": (
            f"institutions.id:{args.institution},from_publication_date:2024-01-01,"
            "to_publication_date:2024-12-31"
        ),
        "updated_since": f"institutions.id:{args.institution},from_updated_date:2024-01-01",
    }
    results: dict[str, dict[str, Any]] = {}
    run_id = "openalex-s2-1-filter-smoke"
    with ApiCostLogger(run_id, args.usage_log) as logger:
        for name, filter_value in filters.items():
            params = {"filter": filter_value, "per-page": 1, "cursor": "*"}
            url = f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"
            status, body, message = request(url, logger)
            results[name] = {
                "status": status,
                "count": body.get("meta", {}).get("count") if isinstance(body, dict) else None,
                "message": message,
            }
    print(json.dumps(results, indent=2, sort_keys=True))
    if results["publication_window"]["status"] != 200:
        raise SystemExit("publication-date filter smoke failed")
    if results["updated_since"]["status"] not in {200, 429}:
        raise SystemExit("updated-since filter returned an unexpected status")


if __name__ == "__main__":
    main()
