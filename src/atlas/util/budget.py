"""Conservative, backward-compatible OpenAlex budget resolution."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

DEFAULT_BUDGET_PATH = Path("config/budget.yml")


def _decimal(value: object, *, field: str, allow_none: bool = True) -> Decimal | None:
    if value is None or value == "":
        if allow_none:
            return None
        raise ValueError(f"{field} must be a finite non-negative number")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a finite non-negative number") from error
    if not number.is_finite() or number < 0:
        raise ValueError(f"{field} must be a finite non-negative number")
    return number


def _strictest(*values: Decimal | None) -> Decimal | None:
    defined = [value for value in values if value is not None]
    return min(defined) if defined else None


def _utc_day(value: object, *, line_number: int) -> date:
    if not isinstance(value, str) or not value:
        raise ValueError(f"OpenAlex usage log line {line_number} has no ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(
            f"OpenAlex usage log line {line_number} has invalid ISO timestamp"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"OpenAlex usage log line {line_number} timestamp has no timezone")
    return parsed.astimezone(UTC).date()


@dataclass(frozen=True)
class OpenAlexBudget:
    """Effective per-run budget and preflight reserve resolved from all sources."""

    max_cost_usd: Decimal | None
    max_credits: Decimal | None
    cost_per_credit_usd: Decimal
    reserve_cost_usd: Decimal
    reserve_credits: Decimal

    def reserve_error(self, *, cost_usd: Decimal, credits: Decimal) -> str | None:
        if self.max_cost_usd is not None and cost_usd + self.reserve_cost_usd > self.max_cost_usd:
            return "OpenAlex cost limit lacks reserve for the next planned request"
        if self.max_credits is not None and credits + self.reserve_credits > self.max_credits:
            return "OpenAlex credit limit lacks reserve for the next planned request"
        return None

    def actual_error(self, *, cost_usd: Decimal, credits: Decimal) -> str | None:
        if self.max_cost_usd is not None and cost_usd > self.max_cost_usd:
            return "OpenAlex per-run cost budget exceeded after response"
        if self.max_credits is not None and credits > self.max_credits:
            return "OpenAlex per-run credit budget exceeded after response"
        return None


def resolve_openalex_budget(
    path: str | Path = DEFAULT_BUDGET_PATH,
    *,
    max_cost_usd: object = None,
    max_credits: object = None,
    environ: dict[str, str] | None = None,
) -> OpenAlexBudget:
    """Load measured defaults and choose the strictest configured/env/caller cap."""
    source = Path(path)
    raw: Any = {}
    if source.exists():
        raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("OpenAlex budget config must be a YAML mapping")
    env = os.environ if environ is None else environ

    def setting(name: str) -> Decimal | None:
        return _decimal(raw.get(name), field=name)

    daily_cost = setting("daily_ceiling_usd")
    abort_cost = setting("abort_threshold_usd")
    daily_credits = setting("daily_ceiling_credits")
    abort_credits = setting("abort_threshold_credits")
    env_cost = _decimal(env.get("OPENALEX_MAX_COST_USD"), field="OPENALEX_MAX_COST_USD")
    env_credits = _decimal(env.get("OPENALEX_MAX_CREDITS"), field="OPENALEX_MAX_CREDITS")
    cli_cost = _decimal(max_cost_usd, field="max_cost_usd")
    cli_credits = _decimal(max_credits, field="max_credits")
    effective_cost = _strictest(daily_cost, abort_cost, env_cost, cli_cost)
    effective_credits = _strictest(daily_credits, abort_credits, env_credits, cli_credits)
    if effective_cost is None or effective_credits is None:
        raise ValueError(
            "finite OpenAlex USD and credit limits are required from config, environment, or caller"
        )
    cost_per_credit = _decimal(
        raw.get("cost_per_credit_usd", "0.0001"),
        field="cost_per_credit_usd",
        allow_none=False,
    )
    if cost_per_credit <= 0:
        raise ValueError("cost_per_credit_usd must be positive")
    return OpenAlexBudget(
        max_cost_usd=effective_cost,
        max_credits=effective_credits,
        cost_per_credit_usd=cost_per_credit,
        reserve_cost_usd=_decimal(
            raw.get("planned_request_reserve_usd", "0"),
            field="planned_request_reserve_usd",
            allow_none=False,
        ),
        reserve_credits=_decimal(
            raw.get("planned_request_reserve_credits", "0"),
            field="planned_request_reserve_credits",
            allow_none=False,
        ),
    )


def conservative_request_cost(
    meta_cost_usd: object,
    credits: object,
    cost_per_credit_usd: Decimal,
    *,
    meta_cost_known: bool = True,
) -> Decimal:
    """Use whichever per-request USD measure is larger; never hide credit-only spend."""
    if cost_per_credit_usd <= 0:
        raise ValueError("cost_per_credit_usd must be positive")
    credit_count = _decimal(credits, field="credits", allow_none=False)
    metadata = (
        _decimal(meta_cost_usd, field="meta cost", allow_none=False)
        if meta_cost_known
        else Decimal(0)
    )
    return max(metadata, credit_count * cost_per_credit_usd)


def daily_logged_usage(
    path: str | Path,
    *,
    cost_per_credit_usd: Decimal,
    day: date | None = None,
) -> tuple[Decimal, Decimal]:
    """Conservatively sum this UTC day's logged OpenAlex request usage for rerun guards."""
    if cost_per_credit_usd <= 0:
        raise ValueError("cost_per_credit_usd must be positive")
    target = Path(path)
    if not target.exists():
        return Decimal(0), Decimal(0)
    selected_day = day or datetime.now(UTC).date()
    cost_total = Decimal(0)
    credits_total = Decimal(0)
    with target.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"invalid JSON in OpenAlex usage log at line {line_number}"
                ) from error
            if not isinstance(record, dict):
                continue
            if record.get("record_type") != "request" or record.get("source") != "openalex":
                continue
            # The documented authenticated /rate-limit endpoint reports account
            # usage, not the charge for this HTTP request. Exclude only that
            # exact provider endpoint from the metered-request subtotal; retain
            # its original ledger row as diagnostic evidence.
            if urlsplit(str(record.get("url", ""))).path.rstrip("/") == "/rate-limit":
                continue
            if _utc_day(record.get("timestamp_utc"), line_number=line_number) != selected_day:
                continue
            if record.get("credits_known", True) is not True:
                raise ValueError(
                    f"OpenAlex usage log line {line_number} has unknown credits; "
                    "refusing budget reset"
                )
            credits = _decimal(record.get("credits"), field="logged credits", allow_none=False)
            cost_known = record.get("cost_known", True) is True
            metadata_cost = (
                _decimal(record.get("cost_usd"), field="logged cost", allow_none=False)
                if cost_known
                else Decimal(0)
            )
            credits_total += credits
            cost_total += max(metadata_cost, credits * cost_per_credit_usd)
    return cost_total, credits_total
