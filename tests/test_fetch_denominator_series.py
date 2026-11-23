"""Offline tests for scripts/fetch_denominator_series.py (BQ-2.2 global-denominator counts).

OpenAlex is replaced by a fake that writes its spend to the real ApiCostLogger, so the budget logic
runs as it does live. Nothing here touches the network, reads .env, or writes outside tmp_path.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.parse
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from atlas.analytics.denominators import (
    FETCH_SERIES,
    POLLUTION_CORE_PATH,
    cache_key,
    fetch_series_filters,
    filter_digest,
    load_pollution_core,
)
from atlas.ingest.openalex import OpenAlexPlanError, OpenAlexRateLimitError
from atlas.query import _term, load_query_config, openalex_filter, type_filters

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "config" / "queries.yml"
POLLUTION_CORE = POLLUTION_CORE_PATH
CONFIG = load_query_config(QUERIES)
SERIES_IDS = ("A-all", "A-article_review", "B-all", "B-article_review")
NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
ENTRY_KEYS = {
    "series_id",
    "query_version",
    "filter_digest",
    "filter",
    "fetched_at",
    "source",
    "by_year",
    "stale",
    "stale_reason",
}


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered first: the script's dataclass looks its module up in sys.modules.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


fds = _load("fetch_denominator_series", ROOT / "scripts" / "fetch_denominator_series.py")
ftg = _load("fetch_trend_global", ROOT / "scripts" / "fetch_trend_global.py")


def _real_now() -> datetime:
    return datetime.now(UTC)


def _ago(days: float) -> datetime:
    return _real_now() - timedelta(days=days)


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any unexpected OpenAlex call, and never read the real .env."""

    def _no_call(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the test must not call OpenAlex")

    monkeypatch.setattr(fds, "_request_json", _no_call)
    monkeypatch.setattr(fds, "load_openalex_key", lambda *args, **kwargs: None)


class FakeOpenAlex:
    """Stands in for the shared request path and writes each attempt to the real logger.

    Call i answers ``{2024: 100 + i, 2025: 200 + i, unknown: 9}`` (the unknown key is dropped).
    ``refuse_on`` raises ``refuse`` on that call index, after logging a rate-limited attempt with no
    credit header. ``fail_on`` raises a generic failure on that index.
    """

    def __init__(
        self,
        *,
        refuse_on: int | None = None,
        refuse: Exception | None = None,
        fail_on: int | None = None,
        credits: int = 10,
    ) -> None:
        self.urls: list[str] = []
        self.refuse_on = refuse_on
        self.refuse = refuse
        self.fail_on = fail_on
        self.credits = credits

    def __call__(self, url: str, *, logger: Any, attempts: int = 4) -> dict[str, Any]:
        index = len(self.urls)
        self.urls.append(url)
        if index == self.refuse_on:
            logger.record(
                source="openalex",
                method="GET",
                url=url,
                status_code=429,
                credits=0,
                credits_known=False,
            )
            assert self.refuse is not None
            raise self.refuse
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
        return {
            "meta": {"count": 1},
            "group_by": [
                {"key": "2024", "count": 100 + index},
                {"key": "2025", "count": 200 + index},
                {"key": "unknown", "count": 9},
            ],
        }


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


def _args(
    tmp_path: Path, cache: Path, *, budget: Path | None = None, extra: list[str] | None = None
):
    budget = budget or _write_budget(tmp_path / "budget.yml")
    return [
        "--config",
        str(QUERIES),
        "--cache",
        str(cache),
        "--usage-log",
        str(tmp_path / "api_usage.jsonl"),
        "--budget",
        str(budget),
        *(extra or []),
    ]


def _digest(series_id: str) -> str:
    return filter_digest(fetch_series_filters(CONFIG, series_id))


def _entry(
    series_id: str,
    fetched: datetime,
    *,
    version: str | None = None,
    by_year: dict[str, int] | None = None,
    stale: bool = False,
    reason: str | None = None,
) -> dict[str, Any]:
    filters = fetch_series_filters(CONFIG, series_id)
    return {
        "series_id": series_id,
        "query_version": version or CONFIG["version"],
        "filter_digest": filter_digest(filters),
        "filter": ",".join(filters),
        "fetched_at": fetched.isoformat(timespec="seconds"),
        "source": fds.SOURCE,
        "by_year": by_year or {"2024": 1, "2025": 2},
        "stale": stale,
        "stale_reason": reason,
    }


def _write_cache(path: Path, entries: list[dict[str, Any]]) -> None:
    payload = {
        "schema_version": fds.CACHE_SCHEMA,
        "source": fds.SOURCE,
        "entries": {
            cache_key(e["series_id"], e["query_version"], e["filter_digest"]): e for e in entries
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _read_entries(path: Path) -> dict[str, dict[str, Any]]:
    """The cache entries keyed by series id (versions and digests are checked elsewhere)."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return {entry["series_id"]: entry for entry in payload["entries"].values()}


def _params(url: str) -> dict[str, list[str]]:
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)


def _filter(url: str) -> str:
    return _params(url)["filter"][0]


def _requests() -> dict[str, Any]:
    return {request.series_id: request for request in fds.build_requests(CONFIG)}


def _run_summary(usage_log: Path) -> dict[str, Any]:
    lines = usage_log.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if '"run_summary"' in line][-1]


# --- request planning: filters, URLs, language ----------------------------------------------------


def test_series_are_the_four_fetch_series_in_order():
    assert tuple(FETCH_SERIES) == SERIES_IDS
    assert list(_requests()) == list(SERIES_IDS)


def test_a_all_sends_the_same_filter_as_fetch_trend_global():
    trend_url = ftg.build_url(CONFIG)
    assert _filter(_requests()["A-all"].url) == _filter(trend_url)


def test_b_uses_only_the_pollution_core_v0_terms_with_the_same_exclusions_and_types():
    a_filter = _filter(_requests()["A-all"].url)
    b_filter = _filter(_requests()["B-all"].url)
    core = load_pollution_core(POLLUTION_CORE)

    # Exact clause: the v0 terms rendered like the query, plus the query's exclusions and types.
    expected_query = {**CONFIG, "core_terms": core["core_terms"], "qualified_terms": []}
    expected = [openalex_filter(expected_query), *type_filters(CONFIG)]
    assert b_filter == ",".join(expected)

    for term in core["core_terms"]:
        assert _term(term) in b_filter
    # Lifecycle terms and the qualified context clauses are absent from B, present in A.
    for term in core["excluded_lifecycle_terms"]:
        assert _term(term) not in b_filter
    for qualified in CONFIG["qualified_terms"]:
        clause = f"({_term(qualified['term'])} AND ("
        assert clause in a_filter
        assert clause not in b_filter
    assert " NOT (" in b_filter  # the query's own exclusions stay, so B is inside A
    for slug in CONFIG["exclude_types"]:
        assert f"type:!{slug}" in b_filter
    assert b_filter.startswith("title_and_abstract.search:(")


def test_no_series_has_a_language_filter():
    for request in _requests().values():
        assert set(_params(request.url)) == {"filter", "group_by"}
        assert "language" not in request.url.lower()


def test_the_article_review_clause_is_only_in_the_sensitivity_series():
    for series_id, request in _requests().items():
        text = _filter(request.url)
        present = "type:article|review" in text
        assert present is series_id.endswith("article_review")
        assert text.count("type:article|review") == (1 if present else 0)


def test_every_request_is_a_publication_year_group_under_the_url_limit():
    for request in _requests().values():
        parts = urllib.parse.urlsplit(request.url)
        assert parts.path == "/works"
        assert _params(request.url)["group_by"] == ["publication_year"]
        assert len(request.url) < 8000
        assert len(request.url) < fds.MAX_URL_CHARS


def test_each_series_has_its_own_filter_digest():
    digests = {request.digest for request in _requests().values()}
    assert len(digests) == len(SERIES_IDS)


def test_an_overlong_request_is_refused():
    long_config = {**CONFIG, "core_terms": [f"term{i:05d}x" for i in range(2000)]}
    with pytest.raises(fds.FetchError, match="limit"):
        fds.build_requests(long_config)


# --- cache freshness and query-version invalidation -----------------------------------------------


@pytest.mark.parametrize(
    ("days", "version", "digest", "stale", "expected"),
    [
        (1, "plastic-v3.1", "D", False, True),
        (29, "plastic-v3.1", "D", False, True),
        (31, "plastic-v3.1", "D", False, False),  # older than 30 days
        (1, "plastic-v3.0", "D", False, False),  # a query version change invalidates
        (1, "plastic-v3.1", "X", False, False),  # a filter change invalidates
        (1, "plastic-v3.1", "D", True, False),  # a flagged entry is always refetched
    ],
)
def test_cache_is_fresh_for_30_days_per_query_version_and_filter(
    days: int, version: str, digest: str, stale: bool, expected: bool
) -> None:
    entry = {
        "query_version": "plastic-v3.1",
        "filter_digest": "D",
        "fetched_at": (NOW - timedelta(days=days)).isoformat(),
        "stale": stale,
    }
    assert fds.is_fresh(entry, query_version=version, digest=digest, now=NOW) is expected
    assert fds.is_fresh(None, query_version=version, digest=digest, now=NOW) is False


def test_cache_keys_hold_series_version_and_digest():
    key = cache_key("B-all", "plastic-v3.1", _digest("B-all"))
    assert key == f"B-all|plastic-v3.1|{_digest('B-all')}"
    assert key != cache_key("B-all", "plastic-v3.0", _digest("B-all"))
    assert key != cache_key("A-all", "plastic-v3.1", _digest("B-all"))


# --- runs through the fake request path -----------------------------------------------------------


def test_a_run_makes_four_calls_and_writes_four_entries(tmp_path, monkeypatch):
    fake = FakeOpenAlex()
    monkeypatch.setattr(fds, "_request_json", fake)
    cache = tmp_path / "data" / "interim" / "denominator_series_cache.json"

    assert fds.main(_args(tmp_path, cache)) == 0

    assert sorted(fake.urls) == sorted(request.url for request in _requests().values())
    entries = _read_entries(cache)
    assert set(entries) == set(SERIES_IDS)
    for entry in entries.values():
        assert set(entry) == ENTRY_KEYS
        assert entry["stale"] is False and entry["stale_reason"] is None
        assert list(entry["by_year"]) == ["2024", "2025"]  # the unknown key is dropped
        assert entry["query_version"] == CONFIG["version"]
    assert cache.read_bytes().endswith(b"}\n") and b"\r\n" not in cache.read_bytes()
    summary = _run_summary(tmp_path / "api_usage.jsonl")
    assert summary["request_count"] == 4
    assert summary["credits_total"] == 40.0


def test_a_fresh_cache_skips_every_call(tmp_path, monkeypatch, capsys):
    cache = tmp_path / "cache.json"
    _write_cache(cache, [_entry(sid, _ago(1)) for sid in SERIES_IDS])
    fake = FakeOpenAlex()
    monkeypatch.setattr(fds, "_request_json", fake)

    assert fds.main(_args(tmp_path, cache)) == 0

    assert fake.urls == []
    out = capsys.readouterr().out
    assert out.count(": cached") == 4
    assert "nothing written" in out


def test_only_the_aged_series_is_refetched(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    fresh_at = _ago(1)
    _write_cache(
        cache,
        [
            _entry("A-all", fresh_at),
            _entry("A-article_review", fresh_at),
            _entry("B-all", _ago(45)),
            _entry("B-article_review", fresh_at),
        ],
    )
    fake = FakeOpenAlex()
    monkeypatch.setattr(fds, "_request_json", fake)

    assert fds.main(_args(tmp_path, cache)) == 0

    assert fake.urls == [_requests()["B-all"].url]
    entries = _read_entries(cache)
    assert entries["A-all"]["fetched_at"] == fresh_at.isoformat(timespec="seconds")
    assert entries["B-all"]["by_year"] == {"2024": 100, "2025": 200}


def test_a_query_version_change_refetches_all_four(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    _write_cache(cache, [_entry(sid, _ago(1), version="plastic-v3.0") for sid in SERIES_IDS])
    fake = FakeOpenAlex()
    monkeypatch.setattr(fds, "_request_json", fake)

    assert fds.main(_args(tmp_path, cache)) == 0

    assert len(fake.urls) == 4
    payload = json.loads(cache.read_text(encoding="utf-8"))
    versions = {entry["query_version"] for entry in payload["entries"].values()}
    assert versions == {"plastic-v3.0", CONFIG["version"]}


def test_force_refetches_fresh_entries(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    _write_cache(cache, [_entry(sid, _ago(1)) for sid in SERIES_IDS])
    fake = FakeOpenAlex()
    monkeypatch.setattr(fds, "_request_json", fake)

    assert fds.main(_args(tmp_path, cache, extra=["--force"])) == 0

    assert len(fake.urls) == 4


def test_dry_run_prints_four_urls_and_makes_no_call(tmp_path, monkeypatch, capsys):
    def _never(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("a dry run must not load the key or call OpenAlex")

    monkeypatch.setattr(fds, "load_openalex_key", _never)
    cache = tmp_path / "cache.json"

    assert fds.main(_args(tmp_path, cache, extra=["--dry-run"])) == 0

    out = capsys.readouterr().out
    assert "no call made" in out
    assert "cache missing" in out
    assert "api_key" not in out
    assert not cache.exists()
    for request in _requests().values():
        assert fds.redact(request.url) in out


def test_an_unreadable_cache_is_replaced_not_trusted(tmp_path, monkeypatch, capsys):
    cache = tmp_path / "cache.json"
    cache.write_text("{not json", encoding="utf-8")
    fake = FakeOpenAlex()
    monkeypatch.setattr(fds, "_request_json", fake)

    assert fds.main(_args(tmp_path, cache)) == 0

    assert len(fake.urls) == 4
    assert "unreadable" in capsys.readouterr().out
    assert set(_read_entries(cache)) == set(SERIES_IDS)


# --- refusals: stale marking, exit codes, --allow-stale -------------------------------------------


@pytest.mark.parametrize(
    "refusal",
    [
        OpenAlexRateLimitError("OpenAlex returned HTTP 429: Rate limit exceeded"),
        OpenAlexPlanError("plan upgrade required", filters=("from_updated_date",)),
    ],
)
def test_a_refused_refresh_marks_cached_values_stale_and_exits_nonzero(
    tmp_path, monkeypatch, capsys, refusal
):
    cache = tmp_path / "cache.json"
    old = _ago(40)
    _write_cache(
        cache,
        [
            _entry("A-all", old, by_year={"2025": 23450}),
            _entry("A-article_review", _ago(1)),
            _entry("B-all", _ago(1)),
            _entry("B-article_review", _ago(1)),
        ],
    )
    fake = FakeOpenAlex(refuse_on=0, refuse=refusal)
    monkeypatch.setattr(fds, "_request_json", fake)

    assert fds.main(_args(tmp_path, cache)) == 1

    assert len(fake.urls) == 1  # the run stops at the refusal; no further calls
    entry = _read_entries(cache)["A-all"]
    assert entry["stale"] is True
    assert "refused" in entry["stale_reason"]
    assert entry["by_year"] == {"2025": 23450}  # the old values are kept, flagged
    assert entry["fetched_at"] == old.isoformat(timespec="seconds")
    assert "stale" in capsys.readouterr().err


def test_allow_stale_exits_zero_when_every_refused_series_has_values(tmp_path, monkeypatch, capsys):
    cache = tmp_path / "cache.json"
    _write_cache(cache, [_entry("A-all", _ago(40)), *[_entry(s, _ago(1)) for s in SERIES_IDS[1:]]])
    fake = FakeOpenAlex(refuse_on=0, refuse=OpenAlexRateLimitError("HTTP 429"))
    monkeypatch.setattr(fds, "_request_json", fake)

    assert fds.main(_args(tmp_path, cache, extra=["--allow-stale"])) == 0

    assert _read_entries(cache)["A-all"]["stale"] is True
    err = capsys.readouterr().err
    assert "warning" in err and "exiting 0" in err


def test_allow_stale_still_fails_when_a_refused_series_has_no_values(tmp_path, monkeypatch, capsys):
    cache = tmp_path / "cache.json"
    fake = FakeOpenAlex(refuse_on=0, refuse=OpenAlexRateLimitError("HTTP 429"))
    monkeypatch.setattr(fds, "_request_json", fake)

    assert fds.main(_args(tmp_path, cache, extra=["--allow-stale"])) == 1

    assert not cache.exists()  # nothing to flag, so nothing is written
    assert "no cached values for A-all" in capsys.readouterr().err


def test_a_budget_guard_stop_is_a_refusal_not_a_failure(tmp_path, monkeypatch, capsys):
    # The first call costs 10 credits. The second would reserve 10 more, which passes the 15-credit
    # abort threshold, so the guard stops the run after the first series is refreshed.
    cache = tmp_path / "cache.json"
    _write_cache(
        cache,
        [
            _entry("A-all", _ago(40)),
            _entry("A-article_review", _ago(40)),
            _entry("B-all", _ago(1)),
            _entry("B-article_review", _ago(1)),
        ],
    )
    fake = FakeOpenAlex()
    monkeypatch.setattr(fds, "_request_json", fake)
    budget = _write_budget(tmp_path / "budget.yml", abort_credits=15)

    assert fds.main(_args(tmp_path, cache, budget=budget)) == 1

    assert len(fake.urls) == 1
    entries = _read_entries(cache)
    assert entries["A-all"]["stale"] is False  # refreshed before the stop
    assert entries["A-article_review"]["stale"] is True
    assert "budget guard" in entries["A-article_review"]["stale_reason"]
    assert "budget guard" in capsys.readouterr().err


def test_the_run_credit_cap_stops_before_the_fourth_series(tmp_path, monkeypatch, capsys):
    # Each call costs 30 credits. After three calls (90 spent) the worst case of a fourth call
    # (30 more) would pass the 100-credit run cap, so the fourth series is refused.
    cache = tmp_path / "cache.json"
    _write_cache(cache, [_entry(sid, _ago(40)) for sid in SERIES_IDS])
    fake = FakeOpenAlex(credits=30)
    monkeypatch.setattr(fds, "_request_json", fake)

    assert fds.main(_args(tmp_path, cache, extra=["--allow-stale"])) == 0

    assert len(fake.urls) == 3
    assert _read_entries(cache)["B-article_review"]["stale"] is True
    assert "run credit cap" in _read_entries(cache)["B-article_review"]["stale_reason"]
    assert "exiting 0" in capsys.readouterr().err
    assert _run_summary(tmp_path / "api_usage.jsonl")["credits_total"] == 90.0


def test_a_generic_failure_exits_nonzero_even_with_allow_stale(tmp_path, monkeypatch, capsys):
    cache = tmp_path / "cache.json"
    _write_cache(cache, [_entry(sid, _ago(40)) for sid in SERIES_IDS])
    fake = FakeOpenAlex(fail_on=0)
    monkeypatch.setattr(fds, "_request_json", fake)

    assert fds.main(_args(tmp_path, cache, extra=["--allow-stale"])) == 1

    assert len(fake.urls) == 1
    entries = _read_entries(cache)
    assert all(entry["stale"] is True for entry in entries.values())  # none was refreshed
    assert "HTTP 500" in capsys.readouterr().err


def test_a_run_with_no_refusal_never_marks_anything_stale(tmp_path, monkeypatch):
    cache = tmp_path / "cache.json"
    _write_cache(cache, [_entry(sid, _ago(1)) for sid in SERIES_IDS[:3]])
    monkeypatch.setattr(fds, "_request_json", FakeOpenAlex())

    assert fds.main(_args(tmp_path, cache, extra=["--allow-stale"])) == 0

    assert all(entry["stale"] is False for entry in _read_entries(cache).values())


# --- helpers --------------------------------------------------------------------------------------


def test_works_by_year_sums_repeats_and_drops_non_year_keys():
    body = {
        "group_by": [
            {"key": "2024", "count": 2},
            {"key": "2024", "count": 3},
            {"key": "unknown", "count": 9},
        ]
    }
    assert fds.works_by_year(body) == {2024: 5}


def test_redact_hides_any_api_key():
    url = "https://api.openalex.org/works?api_key=SECRET123&group_by=publication_year"
    assert fds.redact(url) == (
        "https://api.openalex.org/works?api_key=REDACTED&group_by=publication_year"
    )
