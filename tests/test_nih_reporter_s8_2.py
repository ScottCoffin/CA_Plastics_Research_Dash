"""Offline tests for the S8.2 NIH RePORTER ingester.

Every test uses the trimmed live fixture and an injected fake transport.  No test
touches the network.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
import yaml

from atlas.ingest.grants import (
    GRANT_SCHEMA,
    grant_key,
    normalize_grant,
    validate_grants,
    write_grants_parquet,
)
from atlas.ingest.grants import nih_reporter as nr

FIXTURE = Path("tests/fixtures/s8_2_nih_reporter.json")
QUERIES = Path("config/queries.yml")
TAXONOMY = Path("config/taxonomy.yml")
TODAY = date(2026, 11, 10)  # FY2027 is current, FY2026 is previous.
NOW = datetime(2026, 11, 10, tzinfo=UTC)


@pytest.fixture
def query_config() -> dict[str, Any]:
    return yaml.safe_load(QUERIES.read_text(encoding="utf-8"))


@pytest.fixture
def taxonomy() -> dict[str, Any]:
    return yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))


@pytest.fixture
def records() -> list[dict[str, Any]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["results"]


class FakeTransport:
    """Mimics the API: filters by org_states, pages by offset and limit, reports meta.total."""

    def __init__(
        self,
        records: list[dict[str, Any]],
        *,
        statuses: list[int] | None = None,
        total: int | None = None,
    ) -> None:
        self.records = records
        self.statuses = list(statuses or [])
        self.total = total
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, body: dict[str, Any]) -> tuple[int, str]:
        self.bodies.append(json.loads(json.dumps(body)))
        if self.statuses:
            status = self.statuses.pop(0)
            if status != 200:
                return status, "{}"
        criteria = body["criteria"]
        fiscal_year = criteria["fiscal_years"][0]
        items = [dict(record, fiscal_year=fiscal_year) for record in self.records]
        if "org_states" in criteria:
            items = [
                item
                for item in items
                if (item.get("organization") or {}).get("org_state") in criteria["org_states"]
            ]
        total = len(items) if self.total is None else self.total
        page = items[body["offset"] : body["offset"] + body["limit"]]
        return 200, json.dumps({"meta": {"total": total}, "results": page})


def _no_sleep(_seconds: float) -> None:
    return None


def _run(tmp_path: Path, transport: Any, query_config: Any, taxonomy: Any, **kwargs: Any):
    options: dict[str, Any] = {
        "mode": "backfill",
        "output": tmp_path / "nih_reporter.parquet",
        "state_path": tmp_path / "nih_reporter_state.json",
        "query_config": query_config,
        "taxonomy": taxonomy,
        "transport": transport,
        "max_requests": 100,
        "today": TODAY,
        "now": NOW,
        "sleep": _no_sleep,
        "clock": lambda: 0.0,
    }
    options.update(kwargs)
    return nr.run_ingest(**options)


def _seed_prior_output(
    tmp_path: Path, query_config: dict[str, Any], taxonomy: dict[str, Any], record: dict[str, Any]
) -> dict[str, Any]:
    """Write one 2024 grant as prior output with matching state and provenance."""

    row = normalize_grant(
        nr.to_raw_grant(record), source=nr.SOURCE, query_config=query_config, taxonomy=taxonomy
    )
    output = tmp_path / "nih_reporter.parquet"
    write_grants_parquet([row], output)
    state = {
        "schema_version": nr.STATE_VERSION,
        "search_groups": nr.search_text_groups(query_config["core_terms"]),
        "completed": {"2024:terms": "2025-01-01T00:00:00+00:00"},
        "provenance": {row["grant_key"]: ["2024:terms"]},
        "last_run_utc": "2025-01-01T00:00:00+00:00",
        "last_run": {},
    }
    (tmp_path / "nih_reporter_state.json").write_text(json.dumps(state), encoding="utf-8")
    return row


def test_search_text_is_plural_aware_and_under_limit(query_config):
    groups = nr.search_text_groups(query_config["core_terms"])
    assert groups, "term set must produce at least one group"
    assert all(len(group) <= nr.MAX_SEARCH_TEXT_CHARS for group in groups)
    joined = " OR ".join(groups)
    for phrase in ("microplastic", "microplastics", "nanoplastics", "plastic pellet"):
        assert f'"{phrase}"' in joined


def test_search_text_groups_split_when_over_limit():
    phrases = nr.search_phrases(["alpha beta", "gamma delta", "epsilon"])
    groups = nr.search_text_groups(["alpha beta", "gamma delta", "epsilon"], max_chars=40)
    assert len(groups) > 1
    assert all(len(group) <= 40 for group in groups)
    for phrase in phrases:
        assert any(f'"{phrase}"' in group for group in groups)


def test_fiscal_year_window_boundaries():
    assert nr.fiscal_year_of(date(2026, 9, 30)) == 2026
    assert nr.fiscal_year_of(date(2026, 10, 1)) == 2027
    assert nr.fiscal_years_for("incremental", date(2026, 11, 10)) == [2027, 2026]
    assert nr.fiscal_years_for("incremental", date(2026, 9, 30)) == [2026, 2025]
    backfill = nr.fiscal_years_for("backfill", TODAY)
    assert len(backfill) == 15
    assert backfill[0] == 2027 and backfill[-1] == 2013


def test_request_body_shapes():
    ca = nr.build_body("ca", 2027, '"microplastic"', 0, 500)
    assert ca["criteria"]["org_states"] == ["CA"]
    assert ca["criteria"]["fiscal_years"] == [2027]
    assert ca["criteria"]["advanced_text_search"] == {
        "operator": "advanced",
        "search_field": "projecttitle,abstracttext,terms",
        "search_text": '"microplastic"',
    }
    assert ca["limit"] == 500 and ca["offset"] == 0
    terms = nr.build_body("terms", 2027, '"microplastic"', 500, 500)
    assert "org_states" not in terms["criteria"]
    assert terms["offset"] == 500


def test_mapping_fixture_rows_validate(records, query_config, taxonomy):
    raw = nr.to_raw_grant(records[0])
    assert raw is not None
    row = normalize_grant(raw, source=nr.SOURCE, query_config=query_config, taxonomy=taxonomy)
    assert row["source"] == "nih_reporter"
    assert row["source_award_id"] == str(records[0]["appl_id"])
    assert row["grant_key"] == grant_key("nih_reporter", str(records[0]["appl_id"]))
    assert row["funder"] == "NIH"
    assert row["funder_chain"] == ["NIH", records[0]["agency_ic_admin"]["abbreviation"]]
    assert row["amount"] == float(records[0]["award_amount"])
    assert row["currency"] == "USD"
    assert row["start"].isoformat() == records[0]["project_start_date"][:10]
    assert row["url"] == records[0]["project_detail_url"]
    assert row["org_state"] == records[0]["organization"]["org_state"]

    rows, skipped = nr.normalize_records(
        records + [{"project_title": "no id"}], query_config=query_config, taxonomy=taxonomy
    )
    assert skipped == 1
    assert len(rows) == len({record["appl_id"] for record in records})
    validate_grants(rows.values())


def test_pagination_collects_every_page(records):
    transport = FakeTransport(records)
    client = nr.ReporterClient(transport, max_requests=50, sleep=_no_sleep, clock=lambda: 0.0)
    fetched = nr.fetch_unit(client, fiscal_year=2024, sweep="terms", groups=['"x"'], page_size=5)
    assert len(fetched) == len(records)
    assert [body["offset"] for body in transport.bodies] == list(
        range(0, math.ceil(len(records) / 5) * 5, 5)
    )


def test_offset_ceiling_is_detected_before_paging(records):
    transport = FakeTransport(records, total=nr.MAX_RECORDS + 1)
    client = nr.ReporterClient(transport, max_requests=50, sleep=_no_sleep, clock=lambda: 0.0)
    with pytest.raises(nr.CeilingExceeded):
        nr.fetch_unit(client, fiscal_year=2024, sweep="terms", groups=['"x"'])
    assert len(transport.bodies) == 1


def test_backfill_dedupes_across_sweeps_and_tracks_provenance(
    tmp_path, records, query_config, taxonomy
):
    ca_record = dict(
        records[0],
        appl_id=9000001,
        project_title="Synthetic California microplastics project",
        organization=dict(records[0]["organization"], org_state="CA"),
    )
    transport = FakeTransport(records + [ca_record])
    summary = _run(tmp_path, transport, query_config, taxonomy)
    assert summary["status"] == "ok"
    assert summary["units_completed"] == 30
    assert summary["units_planned"] == 30

    rows = pq.read_table(tmp_path / "nih_reporter.parquet").to_pylist()
    keys = [row["grant_key"] for row in rows]
    assert len(keys) == len(set(keys))
    assert len(rows) == len({record["appl_id"] for record in records + [ca_record]})

    state = json.loads((tmp_path / "nih_reporter_state.json").read_text(encoding="utf-8"))
    ca_key = grant_key("nih_reporter", "9000001")
    assert "2027:ca" in state["provenance"][ca_key]
    assert "2027:terms" in state["provenance"][ca_key]
    other = grant_key("nih_reporter", str(records[0]["appl_id"]))
    assert all(tag.endswith(":terms") for tag in state["provenance"][other])
    assert len(state["provenance"][other]) == 15


def test_backfill_request_cap_is_enforced_and_resumes(tmp_path, records, query_config, taxonomy):
    transport = FakeTransport(records)
    summary = _run(tmp_path, transport, query_config, taxonomy, max_requests=3)
    assert len(transport.bodies) == 3
    assert summary["status"] == "partial"
    assert summary["units_completed"] == 3
    assert summary["rows_written"] > 0

    resumed = FakeTransport(records)
    summary = _run(tmp_path, resumed, query_config, taxonomy, max_requests=100)
    assert summary["status"] == "ok"
    assert len(resumed.bodies) == 27
    assert summary["units_completed"] == 27


def test_incremental_refetches_only_current_and_previous_fy(
    tmp_path, records, query_config, taxonomy
):
    old = dict(records[0], appl_id=9000002)
    prior = _seed_prior_output(tmp_path, query_config, taxonomy, old)
    transport = FakeTransport(records)
    summary = _run(tmp_path, transport, query_config, taxonomy, mode="incremental")
    assert summary["status"] == "ok"
    fiscal_years = {body["criteria"]["fiscal_years"][0] for body in transport.bodies}
    assert fiscal_years == {2027, 2026}
    assert len(transport.bodies) == 4
    keys = {
        row["grant_key"] for row in pq.read_table(tmp_path / "nih_reporter.parquet").to_pylist()
    }
    assert prior["grant_key"] in keys


def test_http_error_preserves_prior_output(tmp_path, records, query_config, taxonomy):
    _seed_prior_output(tmp_path, query_config, taxonomy, dict(records[0], appl_id=9000002))
    output = tmp_path / "nih_reporter.parquet"
    state_path = tmp_path / "nih_reporter_state.json"
    before_output = output.read_bytes()
    before_state = state_path.read_bytes()
    transport = FakeTransport(records, statuses=[500] * 20)
    summary = _run(tmp_path, transport, query_config, taxonomy, mode="incremental")
    assert summary["status"] == "deferred"
    assert len(transport.bodies) == nr.MAX_RETRIES + 1
    assert output.read_bytes() == before_output
    assert state_path.read_bytes() == before_state


def test_offset_ceiling_defers_without_writing(tmp_path, records, query_config, taxonomy):
    transport = FakeTransport(records, total=nr.MAX_RECORDS + 1)
    summary = _run(tmp_path, transport, query_config, taxonomy, mode="incremental")
    assert summary["status"] == "deferred"
    assert not (tmp_path / "nih_reporter.parquet").exists()
    assert not (tmp_path / "nih_reporter_state.json").exists()


def test_retry_recovers_from_rate_limit(tmp_path, records, query_config, taxonomy):
    transport = FakeTransport(records, statuses=[429])
    summary = _run(tmp_path, transport, query_config, taxonomy, mode="incremental", max_requests=10)
    assert summary["status"] == "ok"
    assert len(transport.bodies) == 5


def test_dry_run_plan_makes_no_requests_or_writes(tmp_path, query_config):
    plan = nr.dry_run_plan(
        mode="incremental",
        today=TODAY,
        query_config=query_config,
        state_path=tmp_path / "missing_state.json",
        max_requests=10,
    )
    assert plan["units"] == 4
    assert plan["planned_requests_at_least"] == 4
    assert {
        request["first_page"]["criteria"]["fiscal_years"][0] for request in plan["requests"]
    } == {
        2027,
        2026,
    }
    assert list(tmp_path.iterdir()) == []


def test_output_schema_matches_c3(tmp_path, records, query_config, taxonomy):
    _run(tmp_path, FakeTransport(records), query_config, taxonomy, mode="incremental")
    table = pq.read_table(tmp_path / "nih_reporter.parquet")
    assert table.schema.equals(GRANT_SCHEMA)
