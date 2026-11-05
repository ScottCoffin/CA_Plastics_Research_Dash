"""Append-only API request and run-cost accounting.

The logger deliberately stores a redacted URL and a small set of scalar fields.
Response bodies, credentials, and arbitrary headers do not belong in the usage
log.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DEFAULT_USAGE_LOG = Path("data/logs/api_usage.jsonl")
_SENSITIVE_QUERY_FIELDS = frozenset({"api_key", "apikey", "access_token", "key", "token"})


def redact_url(url: str) -> str:
    """Return *url* with common credential query parameters redacted."""

    parts = urlsplit(url)
    query = [
        (name, "[REDACTED]" if name.casefold() in _SENSITIVE_QUERY_FIELDS else value)
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _decimal(value: object, *, default: Decimal = Decimal(0)) -> Decimal:
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _header(headers: Mapping[str, object], name: str) -> object | None:
    wanted = name.casefold()
    return next((value for key, value in headers.items() if key.casefold() == wanted), None)


class ApiCostLogger:
    """Write one JSONL record per request and one aggregate per completed run."""

    def __init__(self, run_id: str, path: str | Path = DEFAULT_USAGE_LOG) -> None:
        if not run_id.strip():
            raise ValueError("run_id must not be empty")
        self.run_id = run_id
        self.path = Path(path)
        self.request_count = 0
        self.credits_total = Decimal(0)
        self.cost_usd_total = Decimal(0)
        self._closed = False
        self._summary: dict[str, object] | None = None

    def _append(self, record: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            stream.write("\n")

    def record(
        self,
        *,
        source: str,
        method: str,
        url: str,
        status_code: int,
        credits: int | float | str = 0,
        cost_usd: int | float | str = 0,
    ) -> None:
        """Append a request record and update this run's in-memory totals."""

        if self._closed:
            raise RuntimeError("cannot record a request after the run summary")
        credit_value = _decimal(credits)
        cost_value = _decimal(cost_usd)
        self.request_count += 1
        self.credits_total += credit_value
        self.cost_usd_total += cost_value
        self._append(
            {
                "record_type": "request",
                "timestamp_utc": datetime.now(UTC).isoformat(),
                "run_id": self.run_id,
                "source": source,
                "method": method.upper(),
                "url": redact_url(url),
                "status_code": status_code,
                "credits": float(credit_value),
                "cost_usd": float(cost_value),
            }
        )

    def record_openalex_response(
        self,
        *,
        method: str,
        url: str,
        status_code: int,
        headers: Mapping[str, object],
        body: Mapping[str, object] | None,
    ) -> None:
        """Record OpenAlex's observed credit header and response cost metadata."""

        meta = body.get("meta", {}) if body else {}
        if not isinstance(meta, Mapping):
            meta = {}
        self.record(
            source="openalex",
            method=method,
            url=url,
            status_code=status_code,
            credits=_header(headers, "X-RateLimit-Credits-Used") or 0,
            cost_usd=meta.get("cost_usd", 0),
        )

    def close(self) -> dict[str, object]:
        """Append and return the aggregate run summary; repeated calls are harmless."""

        if self._summary is None:
            self._summary = {
                "record_type": "run_summary",
                "timestamp_utc": datetime.now(UTC).isoformat(),
                "run_id": self.run_id,
                "request_count": self.request_count,
                "credits_total": float(self.credits_total),
                "cost_usd_total": float(self.cost_usd_total),
            }
        if not self._closed:
            self._append(self._summary)
            self._closed = True
        return self._summary

    def __enter__(self) -> ApiCostLogger:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
