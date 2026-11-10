"""Offline acceptance checks for the S8.4 USAspending ingester.

Uses the trimmed live fixture and an in-process fake transport.  Makes no network calls.
"""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

from atlas.ingest.grants import GRANT_SCHEMA, validate_grants
from atlas.ingest.grants import usaspending as us

FIXTURE = Path("tests/fixtures/s8_4_usaspending.json")
QUERIES = Path("config/queries.yml")
TAXONOMY = Path("config/taxonomy.yml")


def _fake_transport(records: list[dict[str, Any]]):
    def transport(path: str, body: dict[str, Any]) -> tuple[int, str]:
        assert path == us.SEARCH_PATH, path
        page, limit = body["page"], body["limit"]
        items = [dict(record) for record in records[(page - 1) * limit : page * limit]]
        has_next = page * limit < len(records)
        payload = {
            "limit": limit,
            "results": items,
            "page_metadata": {"page": page, "hasNext": has_next},
        }
        return 200, json.dumps(payload)

    return transport


def main() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records = payload["results"]
    assert 0 < len(records) <= 30, "fixture must hold at most 30 records"
    assert payload["endpoint"] == "https://api.usaspending.gov/api/v2/search/spending_by_award/"

    assert "plastic" not in us.USASPENDING_TERMS and "polymer" not in us.USASPENDING_TERMS
    assert "microplastic" in us.USASPENDING_TERMS
    body = us.build_body("ca_recipient", 2025, 1)
    assert body["filters"]["award_type_codes"] == ["02", "03", "04", "05"]
    assert body["filters"]["time_period"] == [
        {"start_date": "2024-10-01", "end_date": "2025-09-30"}
    ]
    assert body["limit"] <= 100

    taxonomy = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    query_config = yaml.safe_load(QUERIES.read_text(encoding="utf-8"))
    rows, skipped = us.normalize_records(records, query_config=query_config, taxonomy=taxonomy)
    assert skipped == 0
    validate_grants(rows.values())
    assert all(row["source"] == "usaspending" for row in rows.values())

    assert us.fiscal_year_bounds(2027) == (date(2026, 10, 1), date(2027, 9, 30))
    assert us.plan_units("incremental", date(2026, 11, 9), {}) == [
        (2027, "ca_recipient"),
        (2027, "ca_pop"),
        (2026, "ca_recipient"),
        (2026, "ca_pop"),
    ]

    with tempfile.TemporaryDirectory(prefix="s8-4-acceptance-") as directory:
        base = Path(directory)
        summary = us.run_ingest(
            mode="incremental",
            output=base / "usaspending.parquet",
            state_path=base / "usaspending_state.json",
            query_config=query_config,
            taxonomy=taxonomy,
            transport=_fake_transport(records),
            max_requests=10,
            today=date(2026, 11, 9),
            now=datetime(2026, 11, 9, tzinfo=UTC),
            sleep=lambda _seconds: None,
            clock=lambda: 0.0,
        )
        assert summary["status"] == "ok", summary
        assert summary["requests"] == 4, summary
        table = pq.read_table(base / "usaspending.parquet")
        assert table.schema.equals(GRANT_SCHEMA)
        # Both sweeps return the same awards, so dedupe must keep one row per award.
        assert table.num_rows == len(rows), (table.num_rows, len(rows))

    print("S8.4 check passed.")


if __name__ == "__main__":
    main()
