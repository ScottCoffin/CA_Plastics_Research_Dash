"""OpenAlex boolean-operator limit: more than 5 operators is throttled, not refused.

Repo fact (MEMORY "Verified API facts", OpenAlex 2026-11-11; owner rule A3-C1, which
overrides Add-on A3 section 5.9): a title_and_abstract.search with more than 5 boolean
operators costs 10 credits per call and is limited to 5 requests per second. Over the
limit OpenAlex returns HTTP 429 with "wait 1s". The shared client paces requests
(_throttle) and retries that burst 429 after a wait (_request_json).

Everything is mocked: no network, no real sleeping, no API key.
"""

from __future__ import annotations

import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from atlas.ingest import openalex
from atlas.query import load_query_config, openalex_filter

# Six OR operators: more than the five that trigger the burst limit.
OVER_LIMIT_QUERY = "title_and_abstract.search:(a OR b OR c OR d OR e OR f OR g)"
URL = f"{openalex.OPENALEX_BASE}/works?" + urllib.parse.urlencode({"filter": OVER_LIMIT_QUERY})
BURST_BODY = b'{"message":"Rate limit exceeded, please wait 1s"}'
OPERATOR = re.compile(r"\b(?:AND|OR|NOT)\b")


class _Logger:
    def __init__(self) -> None:
        self.status_codes: list[int] = []

    def record_openalex_response(self, **kwargs) -> None:
        self.status_codes.append(kwargs["status_code"])


class _Response(io.BytesIO):
    status = 200
    headers: dict[str, str] = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Clock:
    """Fake monotonic clock; sleep() advances it and records each delay."""

    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []
        self.sends: list[float] = []  # clock time at each request that reached urlopen

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _burst_429(request: urllib.request.Request) -> urllib.error.HTTPError:
    body = io.BytesIO(BURST_BODY)
    return urllib.error.HTTPError(request.full_url, 429, "Too Many Requests", {}, body)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    fake = _Clock()
    # Swap the module's time reference so the real clock and real sleep are never used.
    fake_time = SimpleNamespace(monotonic=fake.monotonic, sleep=fake.sleep)
    monkeypatch.setattr(openalex, "time", fake_time)
    monkeypatch.setattr(openalex, "_last_request_at", 0.0)
    return fake


def test_over_limit_fixture_has_more_than_five_operators() -> None:
    assert len(OPERATOR.findall(OVER_LIMIT_QUERY)) == 6


def test_active_query_exceeds_the_operator_limit() -> None:
    # Every caller that renders config/queries.yml sends a search over the limit.
    root = Path(__file__).resolve().parents[1]
    config = load_query_config(root / "config" / "queries.yml")
    assert len(OPERATOR.findall(openalex_filter(config))) > 5


def test_burst_429_on_over_limit_search_is_retried_and_succeeds(
    monkeypatch: pytest.MonkeyPatch, clock: _Clock
) -> None:
    urls: list[str] = []

    def fake_urlopen(request, timeout):
        urls.append(request.full_url)
        clock.sends.append(clock.now)
        if len(urls) == 1:
            raise _burst_429(request)
        return _Response(json.dumps({"meta": {"count": 42}, "results": []}).encode())

    logger = _Logger()
    monkeypatch.setattr(openalex.urllib.request, "urlopen", fake_urlopen)
    body = openalex._request_json(URL, logger=logger)

    assert body["meta"]["count"] == 42
    assert len(urls) == 2
    # The same over-limit query is re-sent unchanged; it is not split.
    assert urls == [URL, URL]
    assert logger.status_codes == [429, 200]
    assert max(clock.sleeps) >= 1.0  # the burst wait before the retry
    gaps = [later - earlier for earlier, later in zip(clock.sends, clock.sends[1:])]
    assert all(gap >= openalex.MIN_REQUEST_INTERVAL_SECONDS for gap in gaps)


def test_persistent_burst_429_backs_off_then_defers_the_run(
    monkeypatch: pytest.MonkeyPatch, clock: _Clock
) -> None:
    calls = 0

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        raise _burst_429(request)

    monkeypatch.setattr(openalex.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(openalex.OpenAlexRateLimitError):
        openalex._request_json(URL, logger=_Logger())
    # Default attempts=4: waits of 1 s, 2 s and 4 s, then the run is deferred.
    assert calls == 4
    assert clock.sleeps == [1.0, 2.0, 4.0]


def test_throttle_keeps_consecutive_requests_apart(clock: _Clock) -> None:
    for _ in range(4):
        openalex._throttle()
        clock.sends.append(clock.now)
    gaps = [later - earlier for earlier, later in zip(clock.sends, clock.sends[1:])]
    assert all(gap >= openalex.MIN_REQUEST_INTERVAL_SECONDS - 1e-9 for gap in gaps)
    assert clock.sleeps == pytest.approx([0.25, 0.25, 0.25])


def test_throttle_does_not_delay_a_request_that_is_already_spaced(clock: _Clock) -> None:
    openalex._throttle()
    clock.now += 0.5
    openalex._throttle()
    assert clock.sleeps == []


@pytest.mark.parametrize(
    ("message", "is_burst"),
    [
        ("Rate limit exceeded, please wait 1s", True),
        ("queries with more than 5 operators are limited to 5 requests per second", True),
        ("Please Wait 1s and retry", True),
        ("Daily budget exhausted", False),
    ],
)
def test_burst_limit_message_detection(message: str, is_burst: bool) -> None:
    assert openalex._is_burst_limit(message) is is_burst
