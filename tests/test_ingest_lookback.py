"""Incremental ingest re-reads a window before the high-water mark (owner report 2026-11-17).

OpenAlex indexed W7226023234 (doi 10.1021/acsestwater.6c01560) on 2026-11-14 with publication
date 2026-11-13; a run starting at the previous day's high-water mark can miss such works.

2026-11-17: the lookback also widens after a gap with no successful run, so a string of failed
days is re-read on the next success.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from atlas.ingest import openalex

NOW = datetime(2026, 11, 17, 10, 0, tzinfo=UTC)


def test_incremental_start_subtracts_the_lookback() -> None:
    assert openalex.INCREMENTAL_LOOKBACK_DAYS == 30
    assert openalex.incremental_start("2026-11-16") == "2026-10-17"
    assert openalex.incremental_start("2026-11-16", lookback_days=0) == "2026-11-16"
    assert openalex.incremental_start("2026-03-01T00:00:00", lookback_days=1) == "2026-02-28"


def test_negative_lookback_is_rejected() -> None:
    with pytest.raises(ValueError):
        openalex.incremental_start("2026-11-16", lookback_days=-1)


def test_high_water_mark_never_moves_backwards() -> None:
    assert openalex._later_date("2026-10-20", "2026-11-16") == "2026-11-16"
    assert openalex._later_date("2026-11-17", "2026-11-16") == "2026-11-17"
    assert openalex._later_date(None, "2026-11-16") == "2026-11-16"
    assert openalex._later_date(None, None) is None


def test_rejection_summary_redacts_keys_and_names_firewall_headers() -> None:
    raw = b'{"error": "Forbidden", "message": "bad key api_key=SECRET123 or Bearer SECRET456"}'
    line = openalex._rejection_summary(403, {"CF-RAY": "abc", "Server": "cloudflare"}, raw)
    assert "SECRET" not in line
    assert "cf-ray=abc" in line and "server=cloudflare" in line
    assert line.startswith("OpenAlex HTTP 403")


@pytest.mark.parametrize(
    ("last_success", "expected"),
    [
        # A run an hour ago keeps the 30-day base.
        ("2026-11-17T09:00:00+00:00", 30),
        # A 40-day gap widens to the gap plus 7 days of indexing lag.
        ("2026-10-08T10:00:00+00:00", 47),
        # A two-year gap is capped at 366 days.
        ("2024-11-17T10:00:00+00:00", 366),
        # Missing or unreadable timestamps keep the base.
        (None, 30),
        ("", 30),
        ("not-a-date", 30),
        (12345, 30),
    ],
)
def test_effective_lookback_days(last_success: object, expected: int) -> None:
    assert openalex.effective_lookback_days(last_success, NOW) == expected


def test_naive_timestamp_is_read_as_utc() -> None:
    assert openalex.effective_lookback_days("2026-10-08T10:00:00", NOW) == 47


def test_base_lookback_must_stay_within_a_year() -> None:
    with pytest.raises(ValueError):
        openalex.effective_lookback_days(None, NOW, base=367)
    with pytest.raises(ValueError):
        openalex.effective_lookback_days(None, NOW, base=-1)


def _fake_works_request(urls: list[str]):
    def fake_request(url, *, logger, **_):
        urls.append(url)
        logger._request_metrics.append(
            {"credits_known": True, "credits": 10, "cost_known": True, "cost_usd": 0.001}
        )
        return {"results": [], "meta": {"next_cursor": None}}

    return fake_request


def _paths(tmp_path):
    return openalex.OpenAlexPaths(
        raw_dir=tmp_path / "raw",
        output_parquet=tmp_path / "w.parquet",
        high_water_mark=tmp_path / "hw.json",
        usage_log=tmp_path / "usage.jsonl",
    )


def _stale_state(days_since_success: int) -> dict:
    last_success = datetime.now(UTC) - timedelta(days=days_since_success)
    return {
        "schema_version": openalex.HIGH_WATER_SCHEMA_VERSION,
        "last_publication_date": "2026-11-01",
        "last_successful_run_utc": last_success.isoformat(),
    }


def test_ingest_widens_the_lookback_after_a_gap_and_records_it(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    urls: list[str] = []
    monkeypatch.setattr(openalex, "_request_json", _fake_works_request(urls))
    monkeypatch.setattr(openalex, "always_include_filters", lambda config: [])
    paths = _paths(tmp_path)
    paths.high_water_mark.write_text(json.dumps(_stale_state(40)), encoding="utf-8")

    summary = openalex.ingest_live(
        institution_ids=["I1"], paths=paths, publication_date_cap="2026-11-11"
    )

    expected_from = openalex.incremental_start("2026-11-01", 47)
    assert summary["lookback_days"] == 47
    assert summary["incremental_from"] == expected_from
    assert f"from_publication_date%3A{expected_from}" in urls[0]
    state = json.loads(paths.high_water_mark.read_text(encoding="utf-8"))
    assert state["lookback_days"] == 47
    assert state["incremental_from"] == expected_from


def test_recent_incremental_run_keeps_the_thirty_day_lookback(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    urls: list[str] = []
    monkeypatch.setattr(openalex, "_request_json", _fake_works_request(urls))
    monkeypatch.setattr(openalex, "always_include_filters", lambda config: [])
    paths = _paths(tmp_path)
    paths.high_water_mark.write_text(json.dumps(_stale_state(0)), encoding="utf-8")

    summary = openalex.ingest_live(
        institution_ids=["I1"], paths=paths, publication_date_cap="2026-11-11"
    )

    assert summary["lookback_days"] == 30
    assert summary["incremental_from"] == "2026-10-02"
    assert "from_publication_date%3A2026-10-02" in urls[0]


def test_backfill_records_no_lookback(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    urls: list[str] = []
    monkeypatch.setattr(openalex, "_request_json", _fake_works_request(urls))
    monkeypatch.setattr(openalex, "always_include_filters", lambda config: [])
    paths = _paths(tmp_path)

    summary = openalex.ingest_live(
        institution_ids=["I1"], paths=paths, start_year=2026, end_year=2026
    )

    assert summary["lookback_days"] is None
    assert summary["incremental_from"] is None
    state = json.loads(paths.high_water_mark.read_text(encoding="utf-8"))
    assert state["lookback_days"] is None


def test_failed_run_keeps_the_mark_so_the_next_success_rereads_the_gap(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(openalex, "always_include_filters", lambda config: [])
    paths = _paths(tmp_path)
    state = _stale_state(40)
    paths.high_water_mark.write_text(json.dumps(state), encoding="utf-8")
    before = paths.high_water_mark.read_bytes()

    def failing_request(url, *, logger, **_):
        raise openalex.OpenAlexPlanError("OpenAlex plan upgrade required (HTTP 403)")

    monkeypatch.setattr(openalex, "_request_json", failing_request)
    with pytest.raises(openalex.OpenAlexPlanError):
        openalex.ingest_live(institution_ids=["I1"], paths=paths, publication_date_cap="2026-11-11")
    assert paths.high_water_mark.read_bytes() == before

    urls: list[str] = []
    monkeypatch.setattr(openalex, "_request_json", _fake_works_request(urls))
    summary = openalex.ingest_live(
        institution_ids=["I1"], paths=paths, publication_date_cap="2026-11-11"
    )
    # The unchanged last successful run still sets the widened window for the retry.
    assert summary["lookback_days"] == 47
    assert f"from_publication_date%3A{openalex.incremental_start('2026-11-01', 47)}" in urls[0]
