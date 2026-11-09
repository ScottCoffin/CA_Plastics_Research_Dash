"""Validate S7.2 evidence; optional bounded URL smoke checks use no credentials."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from atlas.ingest.monitoring.sources import MAX_REQUESTS, read_bounded

REGISTRY = Path("config/datasets.yml")
EVIDENCE = Path("docs/api_notes/monitoring_sources_s7_2.json")


def validate() -> dict:
    registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    eligible = {row["id"]: row for row in registry["datasets"] if row["seed_eligible"]}
    sources = {row["id"]: row for row in evidence["sources"]}
    if set(eligible) != set(sources) or len(sources) != 15:
        raise ValueError("S7.2 evidence must cover the 15 eligible S7.1 identities exactly")
    for source_id, item in sources.items():
        if item["tier_decision"] != eligible[source_id]["access_tier"]:
            raise ValueError(f"{source_id}: evidence tier disagrees with registry")
        for field in (
            "access_method",
            "observed_format",
            "license_decision",
            "update_frequency",
            "tier_reason",
        ):
            if not item.get(field):
                raise ValueError(f"{source_id}: missing {field}")
        if item["tier_decision"] == "A" and not item.get("field_map"):
            raise ValueError(f"{source_id}: Tier A requires an observed field map")
    return evidence


def smoke(urls: list[str]) -> None:
    if len(urls) > MAX_REQUESTS:
        raise ValueError(f"request count exceeds {MAX_REQUESTS}")
    for url in urls:
        request = urllib.request.Request(url, headers={"User-Agent": "CA-Plastics-Atlas-S7.2/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                body = read_bounded(response)
                print(
                    f"{response.status}\t{response.headers.get('Content-Type')}\t{len(body)}\t{response.url}"
                )
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            print(f"ERROR\t{url}\t{exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-urls", action="store_true")
    args = parser.parse_args()
    evidence = validate()
    print(f"S7.2 evidence valid: {len(evidence['sources'])} eligible source decisions")
    if args.smoke_urls:
        registry = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        rows = [row for row in registry["datasets"] if row["seed_eligible"]]
        smoke([row["verification_url"] for row in rows])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
