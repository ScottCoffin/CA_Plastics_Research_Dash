"""Daily runner: a query-version change triggers a full, replacing backfill."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run_daily_works.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_daily_works", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("recorded", "expected_start", "expected_replace"),
    [("plastic-v2-candidate", 1950, True), (None, 1950, True), ("plastic-v3.1", None, False)],
)
def test_version_change_starts_replacing_backfill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    recorded: str | None,
    expected_start: int | None,
    expected_replace: bool,
) -> None:
    runner = _load_runner()
    high_water = tmp_path / "hw.json"
    state = {"schema_version": 1, "last_publication_date": "2026-11-04"}
    if recorded is not None:
        state["query_version"] = recorded
    high_water.write_text(json.dumps(state), encoding="utf-8")
    seen: dict = {}

    def fake_run(**kwargs):
        seen.update(kwargs)
        return {"status": "deferred", "reason": "budget_exceeded"}

    monkeypatch.setattr(runner, "load_openalex_key", lambda: None)
    monkeypatch.setattr(runner, "load_institution_ids", lambda path: ["I1"])
    monkeypatch.setattr(runner, "run_daily_ingest", fake_run)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    runner.main(["--high-water", str(high_water), "--output", str(tmp_path / "w.parquet")])
    assert seen["start_year"] == expected_start
    assert seen["replace_output"] is expected_replace
    if expected_replace:
        # Without an explicit end year ingest_live would pull 1950 only and replace
        # the whole table with it.
        assert seen["end_year"] is not None and seen["end_year"] >= 2026
    else:
        assert seen["end_year"] is None


def test_year_range_uses_one_window_per_unit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from atlas.ingest import openalex

    urls: list[str] = []

    def fake_request(url, *, logger, **_):
        urls.append(url)
        logger._request_metrics.append(
            {"credits_known": True, "credits": 10, "cost_known": True, "cost_usd": 0.001}
        )
        return {"results": [], "meta": {"next_cursor": None}}

    monkeypatch.setattr(openalex, "_request_json", fake_request)
    monkeypatch.setattr(openalex, "always_include_filters", lambda config: [])
    paths = openalex.OpenAlexPaths(
        raw_dir=tmp_path / "raw",
        output_parquet=tmp_path / "w.parquet",
        high_water_mark=tmp_path / "hw.json",
        usage_log=tmp_path / "usage.jsonl",
    )
    openalex.ingest_live(
        institution_ids=["I1"], paths=paths, start_year=1950, end_year=2027, replace_output=True
    )
    assert len(urls) == 1
    assert "from_publication_date%3A1950-01-01" in urls[0]
    assert "to_publication_date%3A2027-12-31" in urls[0]
