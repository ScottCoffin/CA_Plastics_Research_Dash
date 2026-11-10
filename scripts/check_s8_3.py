"""Offline acceptance checks for the S8.3 NSF Award Search ingester.

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
from atlas.ingest.grants import nsf_awards as ns

FIXTURE = Path("tests/fixtures/s8_3_nsf_awards.json")
QUERIES = Path("config/queries.yml")
TAXONOMY = Path("config/taxonomy.yml")


def _fake_transport(records: list[dict[str, Any]]):
    def transport(params: dict[str, Any]) -> tuple[int, str]:
        start = datetime.strptime(params["dateStart"], "%m/%d/%Y").date()
        end = datetime.strptime(params["dateEnd"], "%m/%d/%Y").date()
        items = [
            record
            for record in records
            if start <= datetime.strptime(record["date"], "%m/%d/%Y").date() <= end
            and ("awardeeStateCode" not in params or record["awardeeStateCode"] == "CA")
            and ("perfStateCode" not in params or record["perfStateCode"] == "CA")
        ]
        body: dict[str, Any] = {"metadata": {"totalCount": len(items), "rpp": params["rpp"]}}
        if items:
            body["award"] = items[params["offset"] : params["offset"] + params["rpp"]]
        return 200, json.dumps({"response": body})

    return transport


def main() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records = payload["results"]
    assert 0 < len(records) <= 30, "fixture must hold at most 30 records"
    assert payload["endpoint"] == "https://api.nsf.gov/services/v1/awards.json"

    query_config = yaml.safe_load(QUERIES.read_text(encoding="utf-8"))
    taxonomy = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    groups = ns.keyword_groups(query_config["core_terms"])
    assert all(group.count('"') in (0, 2) for group in groups)
    assert sum(group.count('"') == 2 for group in groups) >= 1
    for group in groups:
        assert " OR " not in group or group.count('"') == 0, "one quoted phrase per query"

    rows, skipped = ns.normalize_records(records, query_config=query_config, taxonomy=taxonomy)
    assert skipped == 0
    validate_grants(rows.values())

    assert ns.fiscal_window(2027) == ("10/01/2026", "09/30/2027")
    assert ns.plan_units("incremental", date(2026, 11, 9), {}) == [
        (2027, "ca"),
        (2027, "terms"),
        (2026, "ca"),
        (2026, "terms"),
    ]
    assert len(ns.fiscal_years_for("backfill", date(2026, 11, 9))) == 15

    with tempfile.TemporaryDirectory(prefix="s8-3-acceptance-") as directory:
        base = Path(directory)
        summary = ns.run_ingest(
            mode="incremental",
            output=base / "nsf_awards.parquet",
            state_path=base / "nsf_awards_state.json",
            query_config=query_config,
            taxonomy=taxonomy,
            transport=_fake_transport(records),
            max_requests=2000,
            today=date(2026, 11, 9),
            now=datetime(2026, 11, 9, tzinfo=UTC),
            sleep=lambda _seconds: None,
            clock=lambda: 0.0,
        )
        assert summary["status"] == "ok", summary
        assert summary["units_completed"] == 4, summary
        table = pq.read_table(base / "nsf_awards.parquet")
        assert table.schema.equals(GRANT_SCHEMA)
        assert table.num_rows == summary["rows_written"] > 0, summary

    print("S8.3 check passed.")


if __name__ == "__main__":
    main()
