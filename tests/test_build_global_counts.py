"""Offline tests for scripts/build_global_counts.py (PLAT-2a global country counts).

No test touches the network or reads .env. OpenAlex calls are replaced by a fake that writes its
spend to the real ApiCostLogger, so the run-level budget logic is exercised as it runs live.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import urllib.parse
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "plat2a_group_by_countries.json"
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
TOTAL, RECENT, WEEK = "total_by_country", "recent_5y_by_country", "new_this_week_by_country"
TOP_KEYS = {
    "query_version",
    "fetched_at",
    "source",
    "total_by_country",
    "recent_5y_by_country",
    "new_this_week_by_country",
    "countries_with_works",
    "truncated_windows",
    "totals",
}


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "build_global_counts", ROOT / "scripts" / "build_global_counts.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Dataclasses look the module up in sys.modules while it is being executed.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bgc = _load_module()


@pytest.fixture
def config() -> dict[str, Any]:
    return bgc.load_query_config(ROOT / "config" / "queries.yml")


@pytest.fixture
def recorded() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any unexpected OpenAlex call, and never read the real .env."""

    def _no_call(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the test must not call OpenAlex")

    monkeypatch.setattr(bgc, "_request_json", _no_call)
    monkeypatch.setattr(bgc, "load_openalex_key", lambda *args, **kwargs: None)


def _code(key: str) -> str:
    """The alpha-2 code for a group key, which may be a bare code or an OpenAlex URI."""

    return key.rsplit("/", 1)[-1].upper()


def _expected(groups: list[dict[str, Any]]) -> dict[str, int]:
    return {_code(group["key"]): group["count"] for group in groups}


def _window_of(filter_value: str) -> str:
    if "from_publication_date:" in filter_value:
        return WEEK
    if "publication_year:" in filter_value:
        return RECENT
    return TOTAL


class FakeOpenAlex:
    """Stands in for the shared request path: serves canned bodies and records the spend."""

    def __init__(self, bodies: dict[str, dict[str, Any]], credits: int = 10) -> None:
        self.bodies = bodies
        self.credits = credits
        self.urls: list[str] = []

    def __call__(self, url: str, *, logger: Any, attempts: int = 4) -> dict[str, Any]:
        self.urls.append(url)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        logger.record(
            source="openalex",
            method="GET",
            url=url,
            status_code=200,
            credits=self.credits,
            cost_usd=Decimal(self.credits) * Decimal("0.0001"),
        )
        return self.bodies[_window_of(query["filter"][0])]


def _bodies(recorded: dict[str, Any]) -> dict[str, dict[str, Any]]:
    groups = recorded["group_by"]
    return {
        TOTAL: recorded,
        RECENT: {"meta": {"count": 600}, "group_by": groups[:3]},
        WEEK: {
            "meta": {"count": 7},
            "group_by": [{"key": "US", "count": 4}, {"key": "IN", "count": 2}],
        },
    }


def _run(tmp_path: Path, budget_path: Path | None = None) -> Any:
    kwargs: dict[str, Any] = {
        "usage_log": tmp_path / "api_usage.jsonl",
        "raw_dir": tmp_path / "raw",
        "now": NOW,
    }
    if budget_path is not None:
        kwargs["budget_path"] = budget_path
    return bgc.BudgetedRun(**kwargs)


def _write_budget(path: Path, *, abort_usd: str = "0.95", abort_credits: int = 9500) -> Path:
    path.write_text(
        "\n".join(
            [
                "daily_ceiling_usd: 1.0",
                f"abort_threshold_usd: {abort_usd}",
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


def _cli_args(tmp_path: Path, output: Path) -> list[str]:
    return [
        "--config",
        str(ROOT / "config" / "queries.yml"),
        "--output",
        str(output),
        "--usage-log",
        str(tmp_path / "api_usage.jsonl"),
        "--raw-dir",
        str(tmp_path / "raw"),
    ]


def test_windows_cover_all_years_five_years_and_seven_days() -> None:
    windows = bgc.windows(NOW)
    assert [window.name for window in windows] == [TOTAL, RECENT, WEEK]
    assert windows[0].extra_filters == ()
    # The current year and the four before it.
    assert windows[1].extra_filters == ("publication_year:2022|2023|2024|2025|2026",)
    # Seven calendar days, today included: 2026-11-11 through 2026-11-17.
    assert windows[2].extra_filters == ("from_publication_date:2026-11-11",)


def test_urls_use_the_active_query_group_by_and_only_free_filters(config: dict[str, Any]) -> None:
    for window in bgc.windows(NOW):
        url = bgc.build_url(config, window)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        filters = query["filter"][0]
        assert query["group_by"] == ["authorships.countries"]
        assert query["per_page"] == [str(bgc.GROUP_LIMIT)]
        assert "page" not in query
        assert bgc.openalex_filter(config) in filters
        for part in bgc.type_filters(config):
            assert part in filters
        for paid in ("from_updated_date", "from_created_date", "to_updated_date"):
            assert paid not in filters
        assert len(url) <= bgc.MAX_URL_CHARS


def test_redact_hides_any_api_key() -> None:
    url = "https://api.openalex.org/works?api_key=SECRET123&group_by=authorships.countries"
    redacted = bgc.redact(url)
    assert "SECRET123" not in redacted
    assert "api_key=REDACTED&group_by=authorships.countries" in redacted


def test_country_counts_accepts_codes_and_uris_and_reports_others() -> None:
    body = {
        "group_by": [
            {"key": "US", "count": 5},
            {"key": "https://openalex.org/countries/fr", "count": 3},
            {"key": "unknown", "count": 9},
            {"key": "", "count": 1},
        ]
    }
    counts, skipped = bgc.country_counts(body)
    assert counts == {"US": 5, "FR": 3}
    assert skipped == ["unknown", ""]


def test_works_total_needs_an_integer_meta_count() -> None:
    assert bgc.works_total({"meta": {"count": 1000}}) == 1000
    with pytest.raises(bgc.FetchError, match="meta.count"):
        bgc.works_total({"meta": {}})
    with pytest.raises(bgc.FetchError, match="meta.count"):
        bgc.works_total({"meta": {"count": True}})


def test_recorded_response_parses_to_the_same_counts(recorded: dict[str, Any]) -> None:
    counts, skipped = bgc.country_counts(recorded)
    assert skipped == []
    assert all(re.fullmatch(r"[A-Z]{2}", code) for code in counts)
    assert counts == _expected(recorded["group_by"])
    assert sum(counts.values()) == sum(group["count"] for group in recorded["group_by"])
    assert len(recorded["group_by"]) <= 200
    assert bgc.works_total(recorded) > 0


def test_is_fresh_needs_the_same_version_and_under_seven_days() -> None:
    cache = {"query_version": "plastic-v3.1", "fetched_at": (NOW - timedelta(days=6)).isoformat()}
    assert bgc.is_fresh(cache, "plastic-v3.1", NOW)
    assert not bgc.is_fresh(cache, "plastic-v3.2", NOW)
    stale = {"query_version": "plastic-v3.1", "fetched_at": (NOW - timedelta(days=8)).isoformat()}
    assert not bgc.is_fresh(stale, "plastic-v3.1", NOW)
    assert not bgc.is_fresh(None, "plastic-v3.1", NOW)


def test_a_full_group_limit_is_flagged_as_truncated(
    tmp_path: Path, config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    codes = [a + b for a in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for b in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    full = {"meta": {"count": 5000}, "group_by": [{"key": c, "count": 1} for c in codes[:200]]}
    fake = FakeOpenAlex({TOTAL: full})
    monkeypatch.setattr(bgc, "_request_json", fake)
    run = _run(tmp_path)
    try:
        result = run.window_counts(config, bgc.windows(NOW)[0])
    finally:
        run.close()
    assert result.truncated is True
    assert len(result.counts) == 200
    assert result.works == 5000
    assert len(fake.urls) == 1  # no page 2: OpenAlex refuses it


def test_fewer_than_the_group_limit_is_complete(
    tmp_path: Path, config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    codes = [a + b for a in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for b in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"]
    short = {"meta": {"count": 900}, "group_by": [{"key": c, "count": 1} for c in codes[:199]]}
    monkeypatch.setattr(bgc, "_request_json", FakeOpenAlex({TOTAL: short}))
    run = _run(tmp_path)
    try:
        result = run.window_counts(config, bgc.windows(NOW)[0])
    finally:
        run.close()
    assert result.truncated is False
    assert len(result.counts) == 199


def test_a_run_never_starts_a_request_that_could_pass_60_credits(
    tmp_path: Path, config: dict[str, Any], monkeypatch: pytest.MonkeyPatch, recorded: dict
) -> None:
    # Each request costs 20 credits. After two, the spend is 40, and a third could take the
    # run to 70 in the worst case (3 attempts x 10), so it must not start.
    fake = FakeOpenAlex(_bodies(recorded), credits=20)
    monkeypatch.setattr(bgc, "_request_json", fake)
    run = _run(tmp_path)
    url = bgc.build_url(config, bgc.windows(NOW)[0])
    try:
        run.get(url, "a")
        run.get(url, "b")
        with pytest.raises(bgc.FetchError, match="run credit cap"):
            run.get(url, "c")
    finally:
        run.close()
    assert run.requests == 2
    assert run.spent_credits == Decimal(40)
    assert len(fake.urls) == 2


def test_the_fifth_request_is_refused(
    tmp_path: Path, config: dict[str, Any], monkeypatch: pytest.MonkeyPatch, recorded: dict
) -> None:
    fake = FakeOpenAlex(_bodies(recorded), credits=10)
    monkeypatch.setattr(bgc, "_request_json", fake)
    run = _run(tmp_path)
    url = bgc.build_url(config, bgc.windows(NOW)[0])
    try:
        for label in ("a", "b", "c", "d"):
            run.get(url, label)
        with pytest.raises(bgc.FetchError, match="request cap of 4"):
            run.get(url, "e")
    finally:
        run.close()
    assert len(fake.urls) == 4
    assert run.spent_credits == Decimal(40)


def test_unknown_credits_are_charged_as_a_full_attempt(tmp_path: Path) -> None:
    run = _run(tmp_path)
    try:
        run.logger.record(
            source="openalex",
            method="GET",
            url="https://api.openalex.org/works",
            status_code=429,
            credits=0,
            credits_known=False,
        )
        run._charge()
    finally:
        run.close()
    assert run.spent_credits == bgc.ATTEMPT_CREDITS


def test_the_daily_guard_blocks_before_any_request(
    tmp_path: Path, config: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Today's logged usage is 9,495 credits. With the 10-credit reserve, the 9,500 abort
    # threshold is exceeded, so the first request must not start.
    usage = tmp_path / "api_usage.jsonl"
    usage.write_text(
        json.dumps(
            {
                "record_type": "request",
                "source": "openalex",
                "url": "https://api.openalex.org/works",
                "timestamp_utc": datetime.now(UTC).isoformat(),
                "status_code": 200,
                "credits": 9495,
                "cost_usd": 0.9495,
                "credits_known": True,
                "cost_known": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    budget = _write_budget(tmp_path / "budget.yml", abort_usd="5.0", abort_credits=9500)
    fake = FakeOpenAlex({})
    monkeypatch.setattr(bgc, "_request_json", fake)
    run = bgc.BudgetedRun(usage_log=usage, raw_dir=tmp_path / "raw", now=NOW, budget_path=budget)
    try:
        with pytest.raises(bgc.FetchError, match="budget guard"):
            run.get(bgc.build_url(config, bgc.windows(NOW)[0]), "a")
    finally:
        run.close()
    assert fake.urls == []


def test_main_writes_the_payload_and_stays_under_the_run_cap(
    tmp_path: Path,
    config: dict[str, Any],
    recorded: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeOpenAlex(_bodies(recorded))
    monkeypatch.setattr(bgc, "_request_json", fake)
    out = tmp_path / "out" / "global_counts.json"

    assert bgc.main(_cli_args(tmp_path, out)) == 0

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert set(payload) == TOP_KEYS
    assert payload["query_version"] == config["version"]
    total = _expected(recorded["group_by"])
    assert payload[TOTAL] == dict(sorted(total.items()))
    assert payload["countries_with_works"] == len(total)
    truncated = [TOTAL] if len(recorded["group_by"]) >= bgc.GROUP_LIMIT else []
    assert payload["truncated_windows"] == truncated
    assert payload["totals"] == {"works_all": recorded["meta"]["count"], "works_week": 7}
    assert payload[WEEK] == {"IN": 2, "US": 4}
    assert payload[RECENT] == dict(sorted(_expected(recorded["group_by"][:3]).items()))
    assert len(fake.urls) == 3
    assert (tmp_path / "raw" / f"{TOTAL}.json").exists()
    usage = tmp_path / "api_usage.jsonl"
    summary = [
        json.loads(line)
        for line in usage.read_text(encoding="utf-8").splitlines()
        if '"run_summary"' in line
    ][-1]
    assert summary["credits_total"] == 30.0
    assert summary["request_count"] == 3


def test_main_serves_a_fresh_cache_without_a_call(
    tmp_path: Path,
    config: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = tmp_path / "global_counts.json"
    out.write_text(
        json.dumps(
            {
                "query_version": config["version"],
                "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
        ),
        encoding="utf-8",
    )
    assert bgc.main(["--config", str(ROOT / "config" / "queries.yml"), "--output", str(out)]) == 0
    assert "cached" in capsys.readouterr().out


def test_main_force_refetches_a_fresh_cache(
    tmp_path: Path,
    config: dict[str, Any],
    recorded: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = tmp_path / "global_counts.json"
    out.write_text(
        json.dumps(
            {
                "query_version": config["version"],
                "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            }
        ),
        encoding="utf-8",
    )
    fake = FakeOpenAlex(_bodies(recorded))
    monkeypatch.setattr(bgc, "_request_json", fake)
    assert bgc.main([*_cli_args(tmp_path, out), "--force"]) == 0
    assert len(fake.urls) == 3


def test_dry_run_prints_redacted_urls_and_makes_no_call(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "global_counts.json"
    assert bgc.main(["--dry-run", "--output", str(out)]) == 0
    text = capsys.readouterr().out
    assert text.count("group_by=authorships.countries") == 3
    assert "api_key" not in text
    assert "no call made" in text
    assert not out.exists()


def test_empty_total_writes_nothing(
    tmp_path: Path,
    recorded: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bodies = _bodies(recorded)
    bodies[TOTAL] = {"meta": {"count": 0}, "group_by": []}
    monkeypatch.setattr(bgc, "_request_json", FakeOpenAlex(bodies))
    out = tmp_path / "global_counts.json"
    assert bgc.main(_cli_args(tmp_path, out)) == 1
    assert not out.exists()
    assert "no file written" in capsys.readouterr().err
