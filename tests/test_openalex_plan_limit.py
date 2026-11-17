"""HTTP 403 "Plan upgrade required" is a plan error that names the paid filter (2026-11-17).

Offline: ``urlopen`` is replaced by a fake that raises ``urllib.error.HTTPError``. The fake
logger stands in for ``ApiCostLogger``; ``metadata=False`` mimics a bare 403 without credit
headers, which raises ``OpenAlexUsageMetadataError`` in the real logger.
"""

from __future__ import annotations

import io
import urllib.error
import urllib.parse
from email.message import Message

import pytest

from atlas.ingest import openalex
from atlas.util.cost import OpenAlexUsageMetadataError

PLAN_BODY = b'{"message": "Plan upgrade required: daily sync needs the Member+ or Partner plan."}'
FREE_URL = "https://api.openalex.org/works?" + urllib.parse.urlencode(
    {
        "filter": "institutions.id:I1|I2,from_publication_date:2026-10-02,"
        "to_publication_date:2026-11-11",
        "per-page": 100,
        "cursor": "*",
    }
)
PAID_URL = "https://api.openalex.org/works?" + urllib.parse.urlencode(
    {
        "filter": "institutions.id:I1,from_updated_date:2026-11-01,to_publication_date:2026-11-11",
        "per-page": 100,
        "cursor": "*",
    }
)


class _Logger:
    def __init__(self, *, metadata: bool) -> None:
        self.metadata = metadata
        self.calls = 0

    def record_openalex_response(self, **_: object) -> None:
        self.calls += 1
        if not self.metadata:
            raise OpenAlexUsageMetadataError("OpenAlex response omitted valid credit usage")


def _reject(
    monkeypatch: pytest.MonkeyPatch,
    *,
    status: int,
    body: bytes,
    headers: dict[str, str] | None = None,
    calls: list[int] | None = None,
) -> None:
    def fake_urlopen(request, timeout):
        if calls is not None:
            calls.append(1)
        message = Message()
        for key, value in (headers or {}).items():
            message[key] = value
        raise urllib.error.HTTPError(
            request.full_url, status, "rejected", message, io.BytesIO(body)
        )

    monkeypatch.setattr(openalex.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(openalex, "_throttle", lambda: None)
    monkeypatch.setattr(openalex, "_last_rejection_line", None)


def test_plan_limit_with_credit_headers_is_a_plan_error_naming_the_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    _reject(
        monkeypatch,
        status=403,
        body=PLAN_BODY,
        headers={"X-RateLimit-Credits-Used": "0"},
        calls=calls,
    )
    logger = _Logger(metadata=True)
    with pytest.raises(openalex.OpenAlexPlanError) as info:
        openalex._request_json(PAID_URL, logger=logger)
    assert isinstance(info.value, RuntimeError)
    assert info.value.filters == ("from_updated_date",)
    assert "filter from_updated_date" in str(info.value)
    assert "from_publication_date" not in str(info.value)
    assert len(calls) == 1 and logger.calls == 1  # never retried


def test_bare_plan_limit_403_is_still_a_plan_error_not_a_metadata_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reject(monkeypatch, status=403, body=PLAN_BODY)
    with pytest.raises(openalex.OpenAlexPlanError, match="from_updated_date") as info:
        openalex._request_json(PAID_URL, logger=_Logger(metadata=False))
    assert not isinstance(info.value, OpenAlexUsageMetadataError)


def test_other_bare_403_keeps_the_metadata_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _reject(monkeypatch, status=403, body=b"<html>blocked</html>")
    with pytest.raises(OpenAlexUsageMetadataError):
        openalex._request_json(FREE_URL, logger=_Logger(metadata=False))


def test_other_403_with_credits_stays_a_generic_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    _reject(
        monkeypatch,
        status=403,
        body=b'{"message": "Forbidden for this key"}',
        headers={"X-RateLimit-Credits-Used": "0"},
    )
    with pytest.raises(RuntimeError, match="OpenAlex returned HTTP 403: Forbidden") as info:
        openalex._request_json(FREE_URL, logger=_Logger(metadata=True))
    assert not isinstance(info.value, openalex.OpenAlexPlanError)


def test_paid_filter_is_named_even_among_free_filters() -> None:
    assert openalex._filter_names(PAID_URL) == [
        "institutions.id",
        "from_updated_date",
        "to_publication_date",
    ]
    error = openalex._plan_limit_error(PAID_URL, "Plan upgrade required")
    assert error.filters == ("from_updated_date",)


def test_plan_error_without_a_paid_filter_names_the_request_filters() -> None:
    error = openalex._plan_limit_error(FREE_URL, "Plan upgrade required")
    assert error.filters == ("institutions.id", "from_publication_date", "to_publication_date")


def test_rejection_line_and_error_never_carry_the_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    canary = "CANARY_PLAN_KEY_98765"
    monkeypatch.setenv("OPENALEX_API_KEY", canary)
    _reject(
        monkeypatch,
        status=403,
        body=f'{{"message": "Plan upgrade required; key {canary} api_key={canary}"}}'.encode(),
        headers={"X-RateLimit-Credits-Used": "0"},
    )
    with pytest.raises(openalex.OpenAlexPlanError) as info:
        openalex._request_json(PAID_URL, logger=_Logger(metadata=True))
    line = openalex.last_rejection_line()
    assert line is not None and line.startswith("OpenAlex HTTP 403")
    assert canary not in line and canary not in str(info.value)
    assert "<redacted>" in line


def test_rate_limit_429_is_not_reclassified_as_a_plan_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(openalex.FALLBACK_KEY_VAR, raising=False)
    monkeypatch.setattr(openalex, "_active_key_var", openalex.PRIMARY_KEY_VAR)
    _reject(
        monkeypatch,
        status=429,
        body=b'{"message": "Rate limit exceeded"}',
        headers={"X-RateLimit-Credits-Used": "0"},
    )
    with pytest.raises(openalex.OpenAlexRateLimitError):
        openalex._request_json(FREE_URL, logger=_Logger(metadata=True))
    assert openalex.last_rejection_line() is None


def test_redact_secrets_replaces_configured_key_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(openalex.PRIMARY_KEY_VAR, "PRIMARY_CANARY_1")
    monkeypatch.setenv(openalex.FALLBACK_KEY_VAR, "FALLBACK_CANARY_2")
    text = "a PRIMARY_CANARY_1 b FALLBACK_CANARY_2 c api_key=abc Bearer tok"
    redacted = openalex.redact_secrets(text)
    assert "CANARY" not in redacted and "api_key=abc" not in redacted and "tok" not in redacted
    assert redacted.count("<redacted>") == 4
