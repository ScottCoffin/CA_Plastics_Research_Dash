"""Tests for S8.7 program-number (ALN 11.999) USAspending capture.  Fakes only; no network."""

from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest
import yaml

from atlas.ingest.grants import usaspending as us
from atlas.ingest.grants.dedupe import run_dedupe

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/s8_7_noaa_mdp.json"
QUERIES = ROOT / "config/queries.yml"
TAXONOMY = ROOT / "config/taxonomy.yml"
SCRIPT = ROOT / "scripts/ingest_usaspending.py"
TODAY = date(2026, 11, 9)
WINDOW_START = "2014-10-01"
WINDOW_END = "2026-09-30"


@pytest.fixture(scope="module")
def records() -> list[dict[str, Any]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["results"]


@pytest.fixture(scope="module")
def configs() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        yaml.safe_load(QUERIES.read_text(encoding="utf-8")),
        yaml.safe_load(TAXONOMY.read_text(encoding="utf-8")),
    )


def _no_sleep(_seconds: float) -> None:
    return None


def _recording_transport(records, bodies: list[dict[str, Any]], *, by_location: bool = True):
    """Serve one page per sweep.  With ``by_location`` only CA-matching records are returned."""

    def transport(path: str, body: dict[str, Any]) -> tuple[int, str]:
        assert path == us.SEARCH_PATH
        bodies.append(body)
        filters = body["filters"]
        served = list(records)
        if by_location:
            if "recipient_locations" in filters:
                served = [r for r in served if r.get("Recipient State Code") == "CA"]
            else:
                served = [r for r in served if r.get("Place of Performance State Code") == "CA"]
        items = [dict(r) for r in served[(body["page"] - 1) * body["limit"] :][: body["limit"]]]
        has_next = body["page"] * body["limit"] < len(served)
        return 200, json.dumps({"results": items, "page_metadata": {"hasNext": has_next}})

    return transport


def _program_run(tmp_path: Path, transport, configs, **overrides):
    query_config, taxonomy = configs
    options: dict[str, Any] = {
        "program_number": us.NOAA_MDP_ALN,
        "output": tmp_path / "usaspending.parquet",
        "state_path": tmp_path / "usaspending_state.json",
        "query_config": query_config,
        "taxonomy": taxonomy,
        "transport": transport,
        "max_requests": 50,
        "start_fy": 2015,
        "end_fy": 2026,
        "sleep": _no_sleep,
        "clock": lambda: 0.0,
    }
    options.update(overrides)
    return us.run_program_ingest(**options)


def _keyword_run(tmp_path: Path, transport, configs):
    query_config, taxonomy = configs
    return us.run_ingest(
        mode="incremental",
        output=tmp_path / "usaspending.parquet",
        state_path=tmp_path / "usaspending_state.json",
        query_config=query_config,
        taxonomy=taxonomy,
        transport=transport,
        max_requests=50,
        today=TODAY,
        sleep=_no_sleep,
        clock=lambda: 0.0,
    )


def _rows(path: Path) -> list[dict[str, Any]]:
    return pq.read_table(path).to_pylist()


def _state(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_program_filters_use_aln_without_keywords() -> None:
    start, end = us.program_window(2015, 2026)
    filters = us.build_program_filters("11.999", "ca_recipient", start, end)
    assert filters["program_numbers"] == ["11.999"]
    assert "keywords" not in filters
    assert filters["award_type_codes"] == ["02", "03", "04", "05"]
    assert filters["time_period"] == [{"start_date": WINDOW_START, "end_date": WINDOW_END}]
    assert filters["recipient_locations"] == [{"country": "USA", "state": "CA"}]
    pop = us.build_program_filters("11.999", "ca_pop", start, end)
    assert "place_of_performance_locations" in pop and "recipient_locations" not in pop


def test_program_window_and_validation() -> None:
    assert us.program_window(2015, 2027) == (date(2014, 10, 1), date(2027, 9, 30))
    with pytest.raises(ValueError):
        us.program_window(2016, 2015)
    with pytest.raises(ValueError):
        us.build_program_filters("11.9", "ca_pop", date(2014, 10, 1), date(2026, 9, 30))
    with pytest.raises(ValueError):
        us.build_program_filters("11.999", "agencies", date(2014, 10, 1), date(2026, 9, 30))


def test_both_sweeps_send_the_program_filter(tmp_path: Path, records, configs) -> None:
    bodies: list[dict[str, Any]] = []
    summary = _program_run(tmp_path, _recording_transport(records, bodies), configs)
    assert summary["status"] == "ok"
    assert summary["requests"] == 2
    assert [("recipient_locations" in b["filters"]) for b in bodies] == [True, False]
    assert all(b["filters"]["program_numbers"] == ["11.999"] for b in bodies)
    assert set(summary["records_fetched"]) == {
        "program_11.999:ca_recipient",
        "program_11.999:ca_pop",
    }


def test_rows_are_ca_only_fy2015_plus_and_keep_fixture_keys(
    tmp_path: Path, records, configs
) -> None:
    bodies: list[dict[str, Any]] = []
    summary = _program_run(tmp_path, _recording_transport(records, bodies), configs)
    rows = _rows(tmp_path / "usaspending.parquet")
    keys = {row["grant_key"] for row in rows}
    assert len(keys) == len(rows) == summary["rows_written"] == len(records)
    by_award = {row["source_award_id"]: row for row in rows}
    for record in records:
        assert record["Recipient State Code"] == "CA" or (
            record["Place of Performance State Code"] == "CA"
        )
        row = by_award[record["generated_internal_id"]]
        assert row["source"] == "usaspending"
        assert row["end"] is None or row["end"] >= date(2014, 10, 1)
    blank = by_award["ASST_NON_NA26NOS9990200_1305"]
    assert blank["title"] == "Award NA26NOS9990200"
    assert all(row["funder"] == "Department of Commerce" for row in rows)


def test_award_seen_in_both_sweeps_is_one_row_with_both_tags(
    tmp_path: Path, records, configs
) -> None:
    bodies: list[dict[str, Any]] = []
    _program_run(tmp_path, _recording_transport(records, bodies, by_location=False), configs)
    rows = _rows(tmp_path / "usaspending.parquet")
    assert len(rows) == len(records)
    provenance = _state(tmp_path / "usaspending_state.json")["provenance"]
    first = rows[0]["grant_key"]
    assert provenance[first] == ["program_11.999:ca_pop", "program_11.999:ca_recipient"]


def test_keyword_duplicate_merges_to_one_row_and_survives_reruns(
    tmp_path: Path, records, configs
) -> None:
    shared = records[0]
    keyword_transport = _recording_transport([shared], [], by_location=False)
    _keyword_run(tmp_path, keyword_transport, configs)
    assert len(_rows(tmp_path / "usaspending.parquet")) == 1

    bodies: list[dict[str, Any]] = []
    _program_run(tmp_path, _recording_transport(records, bodies, by_location=False), configs)
    rows = _rows(tmp_path / "usaspending.parquet")
    assert len(rows) == len(records)
    assert len({row["grant_key"] for row in rows}) == len(records)

    # A keyword rerun that finds nothing must not drop program-only rows.
    _keyword_run(tmp_path, _recording_transport([], [], by_location=False), configs)
    assert len(_rows(tmp_path / "usaspending.parquet")) == len(records)
    provenance = _state(tmp_path / "usaspending_state.json")["provenance"]
    shared_key = next(
        row["grant_key"]
        for row in rows
        if row["source_award_id"] == shared["generated_internal_id"]
    )
    assert all(tag.startswith("program_") for tag in provenance[shared_key])


def test_dedupe_reads_the_single_table_without_error(tmp_path: Path, records, configs) -> None:
    _program_run(tmp_path, _recording_transport(records, [], by_location=False), configs)
    summary = run_dedupe(interim_dir=tmp_path, report_out=tmp_path / "report.md")
    assert summary["input_rows"] == len(records)
    assert summary["map_rows"] == len(records)


def test_failed_program_run_defers_and_writes_nothing(tmp_path: Path, configs) -> None:
    def failing(_path: str, _body: dict[str, Any]) -> tuple[int, str]:
        return 400, "bad request"

    summary = _program_run(tmp_path, failing, configs)
    assert summary["status"] == "deferred"
    assert not (tmp_path / "usaspending.parquet").exists()
    assert not (tmp_path / "usaspending_state.json").exists()


def test_program_dry_run_plan_makes_no_calls() -> None:
    plan = us.program_dry_run_plan(
        program_number="11.999", start_fy=2015, end_fy=2026, max_requests=5
    )
    assert plan["units"] == 2
    assert plan["window"] == {"start_date": WINDOW_START, "end_date": WINDOW_END}
    assert [
        request["first_page"]["filters"]["program_numbers"] for request in plan["requests"]
    ] == [
        ["11.999"],
        ["11.999"],
    ]


def _load_script():
    spec = importlib.util.spec_from_file_location("ingest_usaspending", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_program_dry_run_prints_plan(capsys: pytest.CaptureFixture[str]) -> None:
    module = _load_script()
    code = module.main(
        ["--program", "11.999", "--start-fy", "2015", "--end-fy", "2026", "--dry-run"]
    )
    assert code == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["program_number"] == "11.999"
    assert plan["units"] == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["--program", "11.9"],
        ["--program", "11.999", "--bulk", "--backfill"],
        ["--incremental", "--start-fy", "2015"],
        ["--program", "11.999", "--start-fy", "2020", "--end-fy", "2015"],
    ],
)
def test_cli_rejects_bad_program_options(argv: list[str]) -> None:
    module = _load_script()
    with pytest.raises(SystemExit) as error:
        module.main(argv)
    assert error.value.code == 2
