"""Offline tests for scripts/fetch_evidence_cells.py (PLAT-2b landing evidence-cell counts).

No test touches the network or reads .env. OpenAlex calls are replaced by a fake that writes its
spend to the real ApiCostLogger, so the budget logic runs as it does live.
"""

from __future__ import annotations

import importlib.util
import json
import urllib.parse
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "config" / "queries.yml"
CELLS = ROOT / "config" / "evidence_cells.yml"
NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)
TOP_KEYS = {
    "schema_version",
    "query_version",
    "cells_version",
    "fetched_at",
    "source",
    "note",
    "gap_share",
    "rows",
    "columns",
    "counts",
    "max",
    "row_field",
}
CELL_COUNT = 30  # 5 rows x 6 columns


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "fetch_evidence_cells", ROOT / "scripts" / "fetch_evidence_cells.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fec = _load_module()


@pytest.fixture
def config() -> dict[str, Any]:
    return fec.load_query_config(QUERIES)


@pytest.fixture
def cells() -> dict[str, Any]:
    return fec.load_cells_config(CELLS)


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any unexpected OpenAlex call, and never read the real .env."""

    def _no_call(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the test must not call OpenAlex")

    monkeypatch.setattr(fec, "_request_json", _no_call)
    monkeypatch.setattr(fec, "load_openalex_key", lambda *args, **kwargs: None)


class FakeOpenAlex:
    """Stands in for the shared request path: records each URL and writes its spend.

    Request ``i`` (in row-major order) returns ``100 + i`` unless ``constant`` is set.
    """

    def __init__(
        self, *, fail_on: int | None = None, constant: int | None = None, credits: int = 10
    ) -> None:
        self.urls: list[str] = []
        self.fail_on = fail_on
        self.constant = constant
        self.credits = credits

    def __call__(self, url: str, *, logger: Any, attempts: int = 4) -> dict[str, Any]:
        index = len(self.urls)
        self.urls.append(url)
        logger.record(
            source="openalex",
            method="GET",
            url=url,
            status_code=200,
            credits=self.credits,
            cost_usd=Decimal(self.credits) * Decimal("0.0001"),
        )
        if index == self.fail_on:
            raise RuntimeError("HTTP 500")
        count = self.constant if self.constant is not None else 100 + index
        return {"meta": {"count": count}, "results": []}


def _write_budget(path: Path, *, abort_credits: int = 9500) -> Path:
    path.write_text(
        "\n".join(
            [
                "daily_ceiling_usd: 1.0",
                "abort_threshold_usd: 0.95",
                "daily_ceiling_credits: 10000",
                f"abort_threshold_credits: {abort_credits}",
                "cost_per_credit_usd: 0.0001",
                "planned_request_reserve_usd: 0.001",
                "planned_request_reserve_credits: 10",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _cli_args(tmp_path: Path, output: Path, budget: Path | None = None) -> list[str]:
    budget = budget or _write_budget(tmp_path / "budget.yml")
    return [
        "--config",
        str(QUERIES),
        "--cells",
        str(CELLS),
        "--output",
        str(output),
        "--usage-log",
        str(tmp_path / "api_usage.jsonl"),
        "--budget",
        str(budget),
    ]


def _filter_of(url: str) -> str:
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["filter"][0]


def _write_cache(path: Path, *, query_version: str, cells_version: str, fetched: datetime) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "query_version": query_version,
        "cells_version": cells_version,
        "fetched_at": fetched.isoformat(timespec="seconds"),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_each_cell_filter_joins_the_query_row_and_column_once(
    config: dict[str, Any], cells: dict[str, Any]
) -> None:
    query = fec.render_query(config)
    grid = fec.cell_urls(config, cells)
    for r, row in enumerate(cells["rows"]):
        for c, column in enumerate(cells["columns"]):
            filter_value = _filter_of(grid[r][c])
            row_terms = " OR ".join(fec._term(term) for term in row["terms"])
            column_terms = " OR ".join(fec._term(term) for term in column["terms"])
            parts = filter_value.split(",")
            if cells.get("row_field") == "title.search":
                # v2: the row is a second filter on the title, ANDed in the same request.
                assert parts[0] == f"title_and_abstract.search:({query}) AND ({column_terms})"
                assert parts[1] == f"title.search:({row_terms})"
            else:
                assert parts[0] == (
                    f"title_and_abstract.search:({query}) AND ({row_terms}) AND ({column_terms})"
                )
            assert filter_value.count("title_and_abstract.search:") == 1
            expected_title_filters = 1 if cells.get("row_field") == "title.search" else 0
            assert filter_value.count("title.search:") == expected_title_filters
            for slug in config["exclude_types"]:
                assert f"type:!{slug}" in filter_value


def test_every_cell_is_one_count_request_with_free_parameters(
    config: dict[str, Any], cells: dict[str, Any]
) -> None:
    grid = fec.cell_urls(config, cells)
    assert [len(row) for row in grid] == [6, 6, 6, 6, 6]
    for row in grid:
        for url in row:
            parts = urllib.parse.urlsplit(url)
            assert parts.path == "/works"
            query = urllib.parse.parse_qs(parts.query)
            assert set(query) == {"filter", "per-page", "select"}
            assert query["per-page"] == ["1"]
            assert query["select"] == ["id"]
            assert "from_updated_date" not in url
            assert "page" not in query
            assert len(url) <= fec.MAX_URL_CHARS


def test_an_overlong_cell_url_is_refused(config: dict[str, Any], cells: dict[str, Any]) -> None:
    long_config = {**config, "core_terms": [f"term{i:05d}x" for i in range(2000)]}
    with pytest.raises(fec.FetchError, match="limit"):
        fec.cell_urls(long_config, cells)


def test_the_committed_cell_file_has_the_five_rows_and_six_columns(cells: dict[str, Any]) -> None:
    assert [row["id"] for row in cells["rows"]] == list(fec.ROW_IDS)
    assert [column["id"] for column in cells["columns"]] == list(fec.COLUMN_IDS)
    assert len(cells["rows"]) * len(cells["columns"]) == CELL_COUNT


def _drop_effects(data: dict[str, Any]) -> None:
    data["rows"] = [row for row in data["rows"] if row["id"] != "effects"]


def _duplicate_ocean(data: dict[str, Any]) -> None:
    data["columns"][1]["id"] = "ocean"


def _empty_row_terms(data: dict[str, Any]) -> None:
    data["rows"][0]["terms"] = []


def _blank_column_term(data: dict[str, Any]) -> None:
    data["columns"][2]["terms"] = ["  "]


def _extra_column(data: dict[str, Any]) -> None:
    data["columns"].append({**data["columns"][0], "id": "lakes"})


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (_drop_effects, r"missing \['effects'\]"),
        (_duplicate_ocean, r"duplicate columns ids \['ocean'\]"),
        (_empty_row_terms, "non-empty list of terms"),
        (_blank_column_term, "non-empty list of terms"),
        (_extra_column, r"unexpected \['lakes'\]"),
    ],
)
def test_a_bad_cell_file_is_rejected(
    tmp_path: Path, mutate: Callable[[dict[str, Any]], None], message: str
) -> None:
    data = yaml.safe_load(CELLS.read_text(encoding="utf-8"))
    mutate(data)
    path = tmp_path / "evidence_cells.yml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        fec.load_cells_config(path)


@pytest.mark.parametrize(
    ("hours", "query_version", "cells_version", "expected"),
    [
        (1, "plastic-v3.1", "evidence-cells-v1", True),
        (19, "plastic-v3.1", "evidence-cells-v1", True),
        (21, "plastic-v3.1", "evidence-cells-v1", False),
        (1, "plastic-v3.2", "evidence-cells-v1", False),
        (1, "plastic-v3.1", "evidence-cells-v2", False),
    ],
)
def test_is_fresh_needs_both_versions_and_under_twenty_hours(
    hours: int, query_version: str, cells_version: str, expected: bool
) -> None:
    cache = {
        "query_version": "plastic-v3.1",
        "cells_version": "evidence-cells-v1",
        "fetched_at": (NOW - timedelta(hours=hours)).isoformat(),
    }
    result = fec.is_fresh(cache, query_version=query_version, cells_version=cells_version, now=NOW)
    assert result is expected
    assert not fec.is_fresh(None, query_version=query_version, cells_version=cells_version, now=NOW)


def test_works_count_needs_a_non_negative_integer_meta_count() -> None:
    assert fec.works_count({"meta": {"count": 0}}) == 0
    for body in ({}, {"meta": {}}, {"meta": {"count": True}}, {"meta": {"count": -1}}):
        with pytest.raises(fec.FetchError, match="meta.count"):
            fec.works_count(body)


def test_redact_hides_any_api_key() -> None:
    url = "https://api.openalex.org/works?api_key=SECRET123&select=id"
    assert fec.redact(url) == "https://api.openalex.org/works?api_key=REDACTED&select=id"


def test_thirty_cells_make_thirty_calls_and_write_the_grid(
    tmp_path: Path,
    config: dict[str, Any],
    cells: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeOpenAlex()
    monkeypatch.setattr(fec, "_request_json", fake)
    out = tmp_path / "out" / "evidence_cells.json"

    assert fec.main(_cli_args(tmp_path, out)) == 0

    assert len(fake.urls) == CELL_COUNT
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert set(payload) == TOP_KEYS
    assert payload["schema_version"] == "plat2b.v1"
    assert payload["query_version"] == config["version"]
    assert payload["cells_version"] == cells["version"]
    assert payload["gap_share"] == cells["gap_share"]
    assert payload["note"] == fec.NOTE
    assert payload["source"] == fec.SOURCE
    assert payload["rows"] == [
        {"id": row["id"], "label": row["label"], "short": row["short"]} for row in cells["rows"]
    ]
    assert [column["id"] for column in payload["columns"]] == list(fec.COLUMN_IDS)
    assert set(payload["columns"][0]) == {"id", "label", "short"}
    # Request i is cell (i // 6, i % 6), so the grid is row-major in config order.
    assert payload["counts"] == [[100 + r * 6 + c for c in range(6)] for r in range(5)]
    assert payload["max"] == 100 + CELL_COUNT - 1
    raw = out.read_bytes()
    assert raw.endswith(b"}\n") and b"\r\n" not in raw
    summary = [
        json.loads(line)
        for line in (tmp_path / "api_usage.jsonl").read_text(encoding="utf-8").splitlines()
        if '"run_summary"' in line
    ][-1]
    assert summary["run_id"].startswith("evidence-cells-")
    assert summary["request_count"] == CELL_COUNT
    assert summary["credits_total"] == 300.0


def test_a_fresh_matching_cache_skips_the_call(
    tmp_path: Path,
    config: dict[str, Any],
    cells: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeOpenAlex()
    monkeypatch.setattr(fec, "_request_json", fake)
    out = tmp_path / "evidence_cells.json"
    _write_cache(
        out,
        query_version=config["version"],
        cells_version=cells["version"],
        fetched=datetime.now(UTC),
    )
    assert fec.main(_cli_args(tmp_path, out)) == 0
    assert fake.urls == []
    assert "cached" in capsys.readouterr().out


def test_a_cache_older_than_twenty_hours_is_refetched(
    tmp_path: Path,
    config: dict[str, Any],
    cells: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeOpenAlex()
    monkeypatch.setattr(fec, "_request_json", fake)
    out = tmp_path / "evidence_cells.json"
    _write_cache(
        out,
        query_version=config["version"],
        cells_version=cells["version"],
        fetched=datetime.now(UTC) - timedelta(hours=21),
    )
    assert fec.main(_cli_args(tmp_path, out)) == 0
    assert len(fake.urls) == CELL_COUNT


def test_force_refetches_a_fresh_cache(
    tmp_path: Path,
    config: dict[str, Any],
    cells: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeOpenAlex()
    monkeypatch.setattr(fec, "_request_json", fake)
    out = tmp_path / "evidence_cells.json"
    _write_cache(
        out,
        query_version=config["version"],
        cells_version=cells["version"],
        fetched=datetime.now(UTC),
    )
    assert fec.main([*_cli_args(tmp_path, out), "--force"]) == 0
    assert len(fake.urls) == CELL_COUNT


def test_dry_run_prints_the_first_redacted_url_and_makes_no_call(
    tmp_path: Path,
    config: dict[str, Any],
    cells: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def _never(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("a dry run must not load the key or call OpenAlex")

    monkeypatch.setattr(fec, "load_openalex_key", _never)
    monkeypatch.setattr(fec, "_request_json", _never)
    out = tmp_path / "evidence_cells.json"
    assert fec.main(["--dry-run", "--output", str(out)]) == 0
    text = capsys.readouterr().out
    assert "30 cell URLs" in text
    assert fec.redact(fec.cell_urls(config, cells)[0][0]) in text
    assert "api_key" not in text
    assert "no call made" in text
    assert not out.exists()


def test_a_budget_stop_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Each call reserves 10 credits and costs 10. With a 95-credit abort threshold, the tenth
    # call's reserve would pass it, so nine calls run and the run stops with nothing written.
    fake = FakeOpenAlex()
    monkeypatch.setattr(fec, "_request_json", fake)
    out = tmp_path / "evidence_cells.json"
    budget = _write_budget(tmp_path / "budget.yml", abort_credits=95)
    assert fec.main(_cli_args(tmp_path, out, budget)) == 1
    assert not out.exists()
    assert "budget guard" in capsys.readouterr().err
    assert len(fake.urls) == 9


def test_one_failing_cell_writes_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeOpenAlex(fail_on=7)
    monkeypatch.setattr(fec, "_request_json", fake)
    out = tmp_path / "evidence_cells.json"
    assert fec.main(_cli_args(tmp_path, out)) == 1
    assert not out.exists()
    assert "no file written" in capsys.readouterr().err
    assert len(fake.urls) == 8  # the run stops at the first failure


def test_all_zero_counts_write_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(fec, "_request_json", FakeOpenAlex(constant=0))
    out = tmp_path / "evidence_cells.json"
    assert fec.main(_cli_args(tmp_path, out)) == 1
    assert not out.exists()
    assert "every cell count is zero" in capsys.readouterr().err


def test_a_bad_cell_file_stops_the_run_before_any_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bad = yaml.safe_load(CELLS.read_text(encoding="utf-8"))
    _drop_effects(bad)
    cells_path = tmp_path / "evidence_cells.yml"
    cells_path.write_text(yaml.safe_dump(bad, sort_keys=False), encoding="utf-8")
    fake = FakeOpenAlex()
    monkeypatch.setattr(fec, "_request_json", fake)
    out = tmp_path / "evidence_cells.json"
    args = [*_cli_args(tmp_path, out), "--cells", str(cells_path)]
    assert fec.main(args) == 1
    assert fake.urls == []
    assert not out.exists()
    assert "effects" in capsys.readouterr().err
