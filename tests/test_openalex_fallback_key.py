"""Fallback OpenAlex key: used once the primary daily allowance is exhausted."""

from __future__ import annotations

import io
import json
import urllib.error

import pytest

from atlas.ingest import openalex
from atlas.util.budget import resolve_openalex_budget


class _Logger:
    def __init__(self) -> None:
        self.calls = []

    def record_openalex_response(self, **kwargs) -> None:
        self.calls.append(kwargs["status_code"])


class _Response(io.BytesIO):
    status = 200
    headers = {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_daily_429_switches_to_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENALEX_API_KEY", "primary-key")
    monkeypatch.setenv("OPENALEX_API_KEY_ALT", "fallback-key")
    monkeypatch.setattr(openalex, "_active_key_var", openalex.PRIMARY_KEY_VAR)
    monkeypatch.setattr(openalex, "_throttle", lambda: None)
    seen = []

    def fake_urlopen(request, timeout):
        seen.append(request.get_header("Authorization"))
        if len(seen) == 1:
            body = json.dumps({"message": "Daily budget exhausted"}).encode()
            raise urllib.error.HTTPError(request.full_url, 429, "x", {}, io.BytesIO(body))
        return _Response(json.dumps({"results": []}).encode())

    monkeypatch.setattr(openalex.urllib.request, "urlopen", fake_urlopen)
    assert openalex._request_json("https://api.openalex.org/works", logger=_Logger()) == {
        "results": []
    }
    assert seen == ["Bearer primary-key", "Bearer fallback-key"]


def test_no_fallback_key_still_defers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENALEX_API_KEY", "primary-key")
    monkeypatch.delenv("OPENALEX_API_KEY_ALT", raising=False)
    monkeypatch.setattr(openalex, "_active_key_var", openalex.PRIMARY_KEY_VAR)
    monkeypatch.setattr(openalex, "_throttle", lambda: None)

    def fake_urlopen(request, timeout):
        body = json.dumps({"message": "Daily budget exhausted"}).encode()
        raise urllib.error.HTTPError(request.full_url, 429, "x", {}, io.BytesIO(body))

    monkeypatch.setattr(openalex.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(openalex.OpenAlexRateLimitError):
        openalex._request_json("https://api.openalex.org/works", logger=_Logger())


def test_budget_scales_with_fallback_key(tmp_path) -> None:
    config = tmp_path / "budget.yml"
    config.write_text(
        "daily_ceiling_usd: 1.0\nabort_threshold_usd: 0.95\n"
        "daily_ceiling_credits: 10000\nabort_threshold_credits: 9500\n",
        encoding="utf-8",
    )
    one = resolve_openalex_budget(config, environ={})
    two = resolve_openalex_budget(config, environ={"OPENALEX_API_KEY_ALT": "x"})
    assert one.max_cost_usd * 2 == two.max_cost_usd
    assert one.max_credits * 2 == two.max_credits
