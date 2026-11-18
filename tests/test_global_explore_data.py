"""Offline tests for the GA-2a explore data scripts.

Covers ``scripts/fetch_global_explore_sample.py`` and ``scripts/build_global_explore.py``. No test
touches the network or reads .env. The fetch runs only from synthetic raw files, and
``BudgetedRun`` is replaced by a stand-in that fails if it is constructed. The build runs on tiny
synthetic inputs in ``tmp_path``. The ``--check`` tests read the committed files and write nothing.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
GLOBAL = ROOT / "site" / "data" / "global"
COUNTS = GLOBAL / "global_counts.json"
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
TODAY = "2026-11-18"
PROFILES = {"US", "CN", "NO"}
FETCHED_AT = "2026-11-18T04:06:10+00:00"
# Sixteen codes with distinct totals; the top 15 by total get co-author lists.
SYNTH_CODES = "CN US NO AB CD EF GH IJ KL MN OP QR ST UV WX YZ".split()
SYNTH_TOTALS = {code: 1000 - 10 * i for i, code in enumerate(SYNTH_CODES)}


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Modules are looked up in sys.modules while they run, as in test_build_global_counts.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


fetch = _load("fetch_global_explore_sample", ROOT / "scripts" / "fetch_global_explore_sample.py")
build = _load("build_global_explore", ROOT / "scripts" / "build_global_explore.py")


class _ForbiddenRun:
    """Stands in for BudgetedRun. Constructing it means a network call would have been possible."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("the test must not construct BudgetedRun (no network)")


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch.g, "BudgetedRun", _ForbiddenRun)


def _config() -> dict[str, Any]:
    return fetch.g.load_query_config(fetch.g.DEFAULT_CONFIG)


def _labels(totals: Mapping[str, int]) -> list[str]:
    return [label for label, _ in fetch.plan(_config(), totals, NOW)]


def _argv(tmp_path: Path) -> list[str]:
    """CLI arguments that keep every path inside tmp_path (never the committed output)."""

    counts = tmp_path / "global_counts.json"
    if not counts.exists():
        counts.write_text(json.dumps({"total_by_country": SYNTH_TOTALS}), encoding="utf-8")
    return [
        "--counts",
        str(counts),
        "--output",
        str(tmp_path / "explore_sample.json"),
        "--raw-root",
        str(tmp_path / "raw"),
    ]


def _recent_body() -> dict[str, Any]:
    work = {
        "id": "https://openalex.org/W1",
        "doi": None,
        "display_name": "A plastics paper",
        "publication_date": "2026-11-01",
        "primary_location": {"source": {"display_name": "Journal X"}},
        "authorships": [{"author": {"display_name": "Ada"}, "countries": ["US"]}],
    }
    return {"meta": {"count": 12}, "results": [work]}


def _group_body() -> dict[str, Any]:
    group = {"key": "https://openalex.org/A1", "key_display_name": "Lab A", "count": 3}
    return {"meta": {"count": 12}, "group_by": [group]}


def _write_raw(raw_dir: Path, labels: Sequence[str]) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    for label in labels:
        body = _recent_body() if label.endswith("_recent") else _group_body()
        (raw_dir / f"{label}.json").write_text(json.dumps(body), encoding="utf-8")


def _expected_co_author_codes(totals: Mapping[str, int]) -> set[str]:
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:15]
    return {code for code, _ in ranked if code not in PROFILES}


def test_the_plan_has_35_requests_for_the_committed_counts() -> None:
    counts = json.loads(COUNTS.read_text(encoding="utf-8"))["total_by_country"]
    labels = _labels(counts)
    assert len(labels) == len(set(labels)) == 35
    assert labels[:4] == ["world_authors", "world_institutions", "world_topics", "world_recent"]
    assert {f"{code}_countries" for code in _expected_co_author_codes(counts)} <= set(labels)


def test_a_fresh_output_is_skipped_with_no_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "explore_sample.json"
    fetched = (NOW - timedelta(days=6)).isoformat(timespec="seconds")
    cached = {"query_version": _config()["version"], "fetched_at": fetched, "scopes": {}}
    out.write_text(json.dumps(cached), encoding="utf-8")
    assert fetch.main(_argv(tmp_path), now=NOW) == 0
    assert capsys.readouterr().out.strip() == "cached"
    assert json.loads(out.read_text(encoding="utf-8")) == cached
    assert not (tmp_path / "raw").exists()


def test_cached_raw_files_build_the_sample_with_zero_credits(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    labels = _labels(SYNTH_TOTALS)
    _write_raw(tmp_path / "raw" / TODAY, labels)
    assert fetch.main(_argv(tmp_path), now=NOW) == 0
    assert f"{len(labels)} cached raw files used, 0 requests, 0 credits" in capsys.readouterr().out

    raw_text = (tmp_path / "explore_sample.json").read_text(encoding="utf-8")
    assert raw_text.endswith("\n") and "\n" not in raw_text[:-1]  # compact, one line
    payload = json.loads(raw_text)
    assert list(payload) == ["query_version", "fetched_at", "scopes"]
    assert payload["query_version"] == _config()["version"]
    datetime.fromisoformat(payload["fetched_at"])

    expected = {"world"} | PROFILES | _expected_co_author_codes(SYNTH_TOTALS)
    assert set(payload["scopes"]) == expected
    world = payload["scopes"]["world"]
    assert set(world) == {"works", "authors", "institutions", "topics", "recent"}
    assert world["works"] == 12
    assert world["authors"] == [{"key": "A1", "name": "Lab A", "count": 3}]
    assert world["recent"] == [
        {
            "id": "W1",
            "doi": None,
            "title": "A plastics paper",
            "date": "2026-11-01",
            "source": "Journal X",
            "first_author": "Ada",
            "n_authors": 1,
            "countries": ["US"],
        }
    ]
    assert set(payload["scopes"]["US"]) == {
        "works",
        "authors",
        "institutions",
        "topics",
        "years",
        "countries",
        "recent",
    }
    assert set(payload["scopes"]["AB"]) == {"works", "countries"}


def test_force_rebuilds_a_fresh_output_from_cached_raw_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "explore_sample.json"
    fresh = (NOW - timedelta(days=1)).isoformat(timespec="seconds")
    out.write_text(
        json.dumps({"query_version": _config()["version"], "fetched_at": fresh}), encoding="utf-8"
    )
    _write_raw(tmp_path / "raw" / TODAY, _labels(SYNTH_TOTALS))
    assert fetch.main([*_argv(tmp_path), "--force"], now=NOW) == 0
    text = capsys.readouterr().out
    assert "cached raw files used, 0 requests, 0 credits" in text
    assert json.loads(out.read_text(encoding="utf-8"))["scopes"]


def test_a_stale_output_is_rebuilt_from_todays_raw_files(tmp_path: Path) -> None:
    out = tmp_path / "explore_sample.json"
    stale = (NOW - timedelta(days=8)).isoformat(timespec="seconds")
    out.write_text(
        json.dumps({"query_version": _config()["version"], "fetched_at": stale}), encoding="utf-8"
    )
    _write_raw(tmp_path / "raw" / TODAY, _labels(SYNTH_TOTALS))
    assert fetch.main(_argv(tmp_path), now=NOW) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["fetched_at"] != stale


def test_dry_run_lists_the_plan_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    labels = _labels(SYNTH_TOTALS)
    _write_raw(tmp_path / "raw" / TODAY, labels[:-2])
    assert fetch.main([*_argv(tmp_path), "--dry-run"], now=NOW) == 0
    text = capsys.readouterr().out
    assert f"{labels[0]}: cached" in text
    assert f"{labels[-1]}: to fetch" in text
    assert f"2 of {len(labels)} requests to send (about 20 credits)" in text
    assert not (tmp_path / "explore_sample.json").exists()


def test_a_fetch_error_exits_1_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    labels = _labels(SYNTH_TOTALS)
    _write_raw(tmp_path / "raw" / TODAY, labels[1:])
    caps: list[tuple[int, Decimal]] = []

    class FailingRun:
        """Records the caps in force during the run, then fails the first request."""

        def __init__(self, **kwargs: Any) -> None:
            self.requests = 0
            self.spent_credits = Decimal(0)

        def get(self, url: str, label: str) -> None:
            caps.append((fetch.g.MAX_REQUESTS, fetch.g.RUN_CREDIT_CAP))
            raise fetch.g.FetchError(f"OpenAlex request failed: {label}")

        def close(self) -> None:
            pass

    monkeypatch.setattr(fetch.g, "BudgetedRun", FailingRun)
    before = (fetch.g.MAX_REQUESTS, fetch.g.RUN_CREDIT_CAP)
    assert fetch.main(_argv(tmp_path), now=NOW) == 1
    assert f"OpenAlex request failed: {labels[0]}" in capsys.readouterr().err
    assert caps == [(1 + 2, Decimal(1 * 10 + 40))]  # one request planned: two spares, 40 credits
    assert not (tmp_path / "explore_sample.json").exists()
    assert (fetch.g.MAX_REQUESTS, fetch.g.RUN_CREDIT_CAP) == before


def _square(x0: float, y0: float, x1: float, y1: float) -> str:
    return f"M{x0},{y0} {x1},{y0} {x1},{y1} {x0},{y1}Z"


def _write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _synthetic(tmp_path: Path, *, trend: Any = None) -> dict[str, Path]:
    """A 4 x 4 raster. AA is the left half, BB the right half, and SM a sliver in the gap, so no
    cell centre falls in SM. The top-left two cells are California ('c')."""

    return {
        "raster": _write_json(
            tmp_path / "raster.json", {"cols": 4, "world": "ccxx|xxxx|xxxx|xxxx"}
        ),
        "world": _write_json(
            tmp_path / "world.json",
            {
                "w": 4.0,
                "crop": [0.0, 4.0],
                "countries": [
                    {"id": "1", "iso_a2": "AA", "name": "Alpha", "d": _square(0, 0, 2, 4)},
                    {"id": "2", "iso_a2": "BB", "name": "Beta", "d": _square(2.2, 0, 4, 4)},
                    {
                        "id": "3",
                        "iso_a2": "SM",
                        "name": "San Marino (map)",
                        "d": _square(2.05, 1.9, 2.15, 2.1),
                    },
                ],
            },
        ),
        "counts": _write_json(
            tmp_path / "counts.json",
            {
                "query_version": "plastic-v3.1",
                "fetched_at": FETCHED_AT,
                "totals": {"works_all": 1, "works_week": 0},
                "total_by_country": {"AA": 10, "BB": 20, "SM": 3, "US": 5, "AG": 4},
                "recent_5y_by_country": {"AA": 2},
                "new_this_week_by_country": {"BB": 1},
            },
        ),
        "trend": _write_json(
            tmp_path / "trend.json",
            trend or {"by_year": {"1960": 1, "1970": 2, "2026": 3, "2027": 4}},
        ),
        "sample": _write_json(
            tmp_path / "sample.json",
            {"query_version": "plastic-v3.1", "fetched_at": FETCHED_AT, "scopes": {}},
        ),
        "metadata": _write_json(tmp_path / "build_metadata.json", {"counts": {"works": 7}}),
    }


def test_a_small_country_with_no_cell_centre_takes_one_land_cell(tmp_path: Path) -> None:
    data = build.build(**_synthetic(tmp_path))
    by_iso = {c["iso"]: c for c in data["countries"]}
    sm = by_iso["SM"]
    assert sum(run[2] for run in sm["runs"]) == 1
    col, row = sm["runs"][0][0], sm["runs"][0][1]
    assert sm["bbox"] == [col, row, col + 1, row + 1]
    # 16 cells less the 2 California cells: the cell moved from a neighbour, none lost or added.
    land = [
        (run[0] + i, run[1]) for c in data["countries"] for run in c["runs"] for i in range(run[2])
    ]
    assert len(land) == len(set(land)) == 14


def test_california_cells_stay_separate_from_the_us(tmp_path: Path) -> None:
    data = build.build(**_synthetic(tmp_path))
    assert data["california"] == {"cells": [[0, 0], [1, 0]], "works": 7}
    by_iso = {c["iso"]: c for c in data["countries"]}
    assert "US-CA" not in by_iso
    assert by_iso["US"]["runs"] == []
    assert by_iso["US"]["bbox"] is None
    assert by_iso["US"]["works"] == 5


def test_names_resolve_in_order_fix_then_map_then_fixed_table_then_code() -> None:
    assert build.resolve_name("US", {"US": "United States of America"}) == "United States"
    assert build.resolve_name("DO", {"DO": "Dominican Rep."}) == "Dominican Republic"
    assert build.resolve_name("HK", {"HK": "Hong Kong SAR"}) == "Hong Kong SAR"
    assert build.resolve_name("AG", {}) == "Antigua and Barbuda"
    assert build.resolve_name("ZZ", {"ZZ": "Zedland"}) == "Zedland"
    assert build.resolve_name("ZZ", {}) == "ZZ"


def test_countries_in_the_build_take_their_names_from_the_chain(tmp_path: Path) -> None:
    data = build.build(**_synthetic(tmp_path))
    by_iso = {c["iso"]: c for c in data["countries"]}
    assert by_iso["US"]["name"] == "United States"
    assert by_iso["SM"]["name"] == "San Marino (map)"
    assert by_iso["AG"]["name"] == "Antigua and Barbuda"
    assert by_iso["AG"]["continent"] == "North America"
    assert by_iso["AG"]["bbox"] is None


def test_trend_years_run_from_1970_to_the_counts_year(tmp_path: Path) -> None:
    data = build.build(**_synthetic(tmp_path))
    # 1960 is before the first year; 2027 is after the counts file's year (2026).
    assert data["trend_world"] == {"1970": 2, "2026": 3}


def test_the_build_is_byte_identical_for_the_same_inputs(tmp_path: Path) -> None:
    paths = _synthetic(tmp_path)
    first = build.encode(build.build(**paths))
    assert build.encode(build.build(**paths)) == first
    assert first.endswith(b"\n") and b"\r" not in first
    payload = json.loads(first)
    assert list(payload) == [
        "grid",
        "countries",
        "california",
        "totals",
        "fetched_at",
        "query_version",
        "trend_world",
        "sample",
    ]
    assert payload["sample"] == json.loads(paths["sample"].read_text(encoding="utf-8"))


def test_check_passes_on_the_committed_explore_json() -> None:
    assert build.main(["--check"]) == 0


def test_check_fails_on_a_modified_copy(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    committed = (GLOBAL / "explore.json").read_bytes()
    marker = b'"query_version":"'
    assert marker in committed
    modified = tmp_path / "explore.json"
    modified.write_bytes(committed.replace(marker, marker + b"x", 1))
    assert build.main(["--check", "--output", str(modified)]) == 1
    assert capsys.readouterr().out.strip() == "stale"
    assert build.main(["--check", "--output", str(tmp_path / "absent.json")]) == 1
