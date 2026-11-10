"""Offline acceptance checks for the S8.2 NIH RePORTER ingester.

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
from atlas.ingest.grants import nih_reporter as nr

FIXTURE = Path("tests/fixtures/s8_2_nih_reporter.json")
QUERIES = Path("config/queries.yml")
TAXONOMY = Path("config/taxonomy.yml")


def _fake_transport(records: list[dict[str, Any]]):
    def transport(body: dict[str, Any]) -> tuple[int, str]:
        criteria = body["criteria"]
        fiscal_year = criteria["fiscal_years"][0]
        items = [dict(record, fiscal_year=fiscal_year) for record in records]
        if "org_states" in criteria:
            items = [
                item
                for item in items
                if (item.get("organization") or {}).get("org_state") in criteria["org_states"]
            ]
        page = items[body["offset"] : body["offset"] + body["limit"]]
        return 200, json.dumps({"meta": {"total": len(items)}, "results": page})

    return transport


def main() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records = payload["results"]
    assert 0 < len(records) <= 30, "fixture must hold at most 30 records"
    assert payload["endpoint"] == "https://api.reporter.nih.gov/v2/projects/search"

    query_config = yaml.safe_load(QUERIES.read_text(encoding="utf-8"))
    taxonomy = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    groups = nr.search_text_groups(query_config["core_terms"])
    assert all(len(group) <= nr.MAX_SEARCH_TEXT_CHARS for group in groups)
    for term in query_config["core_terms"]:
        assert any(f'"{term}"' in group for group in groups), term

    rows, skipped = nr.normalize_records(records, query_config=query_config, taxonomy=taxonomy)
    assert skipped == 0
    validate_grants(rows.values())

    assert nr.fiscal_years_for("incremental", date(2026, 11, 10)) == [2027, 2026]
    assert len(nr.fiscal_years_for("backfill", date(2026, 11, 10))) == 15

    with tempfile.TemporaryDirectory(prefix="s8-2-acceptance-") as directory:
        base = Path(directory)
        summary = nr.run_ingest(
            mode="incremental",
            output=base / "nih_reporter.parquet",
            state_path=base / "nih_reporter_state.json",
            query_config=query_config,
            taxonomy=taxonomy,
            transport=_fake_transport(records),
            max_requests=10,
            today=date(2026, 11, 10),
            now=datetime(2026, 11, 10, tzinfo=UTC),
            sleep=lambda _seconds: None,
            clock=lambda: 0.0,
        )
        assert summary["status"] == "ok", summary
        assert summary["requests"] == 4, summary
        table = pq.read_table(base / "nih_reporter.parquet")
        assert table.schema.equals(GRANT_SCHEMA)
        assert table.num_rows == len(rows)

    print("S8.2 check passed.")


if __name__ == "__main__":
    main()
