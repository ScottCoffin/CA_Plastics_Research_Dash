"""Offline acceptance checks for S8.7 (NOAA Marine Debris Program, ALN 11.999, USAspending).

Uses the synthetic fixture and in-process fake transports.  Makes no network calls.
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
from atlas.ingest.grants.dedupe import run_dedupe

FIXTURE = Path("tests/fixtures/s8_7_noaa_mdp.json")
QUERIES = Path("config/queries.yml")
TAXONOMY = Path("config/taxonomy.yml")
WINDOW_FLOOR = date(2014, 10, 1)  # first day of FY2015


def _is_ca(record: dict[str, Any]) -> bool:
    return "CA" in (
        record.get("Recipient State Code"),
        record.get("Place of Performance State Code"),
    )


def _program_transport(records: list[dict[str, Any]], bodies: list[dict[str, Any]]):
    """Serve the sweep's own location filter, as the live API does."""

    def transport(path: str, body: dict[str, Any]) -> tuple[int, str]:
        assert path == us.SEARCH_PATH, path
        bodies.append(body)
        filters = body["filters"]
        field = (
            "Recipient State Code"
            if "recipient_locations" in filters
            else "Place of Performance State Code"
        )
        served = [record for record in records if record.get(field) == "CA"]
        page, limit = body["page"], body["limit"]
        items = [dict(record) for record in served[(page - 1) * limit : page * limit]]
        has_next = page * limit < len(served)
        payload = {"results": items, "page_metadata": {"page": page, "hasNext": has_next}}
        return 200, json.dumps(payload)

    return transport


def _keyword_transport(records: list[dict[str, Any]]):
    def transport(path: str, body: dict[str, Any]) -> tuple[int, str]:
        assert path == us.SEARCH_PATH, path
        served = [dict(record) for record in records]
        payload = {"results": served, "page_metadata": {"page": 1, "hasNext": False}}
        return 200, json.dumps(payload)

    return transport


def _no_sleep(_seconds: float) -> None:
    return None


def main() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records = payload["results"]
    assert 0 < len(records) <= 20, "fixture must hold at most 20 records"

    body = us.build_program_filters(us.NOAA_MDP_ALN, "ca_pop", *us.program_window(2015, 2026))
    assert body["program_numbers"] == ["11.999"]
    assert "keywords" not in body
    assert body["time_period"] == [{"start_date": "2014-10-01", "end_date": "2026-09-30"}]
    assert body["award_type_codes"] == ["02", "03", "04", "05"]

    taxonomy = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    query_config = yaml.safe_load(QUERIES.read_text(encoding="utf-8"))
    options: dict[str, Any] = {
        "query_config": query_config,
        "taxonomy": taxonomy,
        "max_requests": 10,
        "sleep": _no_sleep,
        "clock": lambda: 0.0,
    }

    with tempfile.TemporaryDirectory(prefix="s8-7-acceptance-") as directory:
        base = Path(directory)
        output = base / "usaspending.parquet"
        state = base / "usaspending_state.json"

        # CA-only: every served award is CA by recipient or place of performance.
        bodies: list[dict[str, Any]] = []
        summary = us.run_program_ingest(
            program_number=us.NOAA_MDP_ALN,
            output=output,
            state_path=state,
            transport=_program_transport(records, bodies),
            start_fy=2015,
            end_fy=2026,
            now=datetime(2026, 11, 10, tzinfo=UTC),
            **options,
        )
        assert summary["status"] == "ok", summary
        assert summary["requests"] == 2, summary
        assert all(b["filters"]["program_numbers"] == ["11.999"] for b in bodies)
        expected_ca = [record for record in records if _is_ca(record)]
        assert len(expected_ca) == len(records), "fixture must be CA-only"

        table = pq.read_table(output)
        assert table.schema.equals(GRANT_SCHEMA)
        rows = table.to_pylist()
        validate_grants(rows)
        assert len(rows) == len(records), (len(rows), len(records))

        # FY2015+: the API matches awards whose period overlaps the window, so every
        # kept row must end on or after 1 October 2014.
        assert all(row["end"] is None or row["end"] >= WINDOW_FLOOR for row in rows)
        assert all(row["source"] == "usaspending" for row in rows)

        # Stable keys: the same award gets the same grant_key in keyword mode.
        shared = records[0]
        keyword_output = base / "keyword" / "usaspending.parquet"
        keyword_state = base / "keyword" / "usaspending_state.json"
        us.run_ingest(
            mode="incremental",
            output=keyword_output,
            state_path=keyword_state,
            query_config=query_config,
            taxonomy=taxonomy,
            transport=_keyword_transport([shared]),
            max_requests=10,
            today=date(2026, 11, 9),
            sleep=_no_sleep,
            clock=lambda: 0.0,
        )
        keyword_keys = {row["grant_key"] for row in pq.read_table(keyword_output).to_pylist()}
        program_keys = {row["grant_key"] for row in rows}
        assert keyword_keys <= program_keys and len(keyword_keys) == 1

        # Merge: the keyword duplicate of the shared award collapses to one row.
        merged_output = base / "merged" / "usaspending.parquet"
        merged_state = base / "merged" / "usaspending_state.json"
        us.run_ingest(
            mode="incremental",
            output=merged_output,
            state_path=merged_state,
            query_config=query_config,
            taxonomy=taxonomy,
            transport=_keyword_transport([shared]),
            max_requests=10,
            today=date(2026, 11, 9),
            sleep=_no_sleep,
            clock=lambda: 0.0,
        )
        us.run_program_ingest(
            program_number=us.NOAA_MDP_ALN,
            output=merged_output,
            state_path=merged_state,
            transport=_program_transport(records, []),
            start_fy=2015,
            end_fy=2026,
            **options,
        )
        merged_rows = pq.read_table(merged_output).to_pylist()
        assert len(merged_rows) == len(records), (len(merged_rows), len(records))
        assert len({row["grant_key"] for row in merged_rows}) == len(records)

        # Dedupe reads one table, so no duplicate-key error is raised.
        dedupe = run_dedupe(interim_dir=base / "merged", report_out=base / "report.md")
        assert dedupe["input_rows"] == len(records), dedupe
        assert dedupe["map_rows"] == len(records), dedupe

    print("S8.7 check passed.")


if __name__ == "__main__":
    main()
