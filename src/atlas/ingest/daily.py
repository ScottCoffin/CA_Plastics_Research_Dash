"""Guarded daily orchestration for the OpenAlex works refresh."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from atlas.ingest.openalex import (
    OpenAlexBudgetError,
    OpenAlexPaths,
    OpenAlexRateLimitError,
    ingest_live,
)


def run_daily_ingest(
    *,
    institution_ids: Sequence[str],
    config_path: str | Path = "config/queries.yml",
    paths: OpenAlexPaths = OpenAlexPaths(),
    start_year: int | None = None,
    end_year: int | None = None,
    updated_since: str | None = None,
    allow_candidate: bool = False,
    max_pages: int | None = None,
    max_credits: float | None = None,
    max_cost_usd: float | None = None,
    replace_output: bool = False,
    anchor_author_ids: Sequence[str] | None = None,
    raw_affiliation_scope: bool = False,
    publication_date_cap: str | None = None,
    ingest: Callable[..., Mapping[str, Any]] = ingest_live,
) -> dict[str, Any]:
    """Run one refresh and convert expected budget stops into a clean outcome.

    A rate-limited or budget-stopped run deliberately leaves the existing
    Parquet and high-water state untouched. The next scheduled invocation can
    therefore retry the same inclusive boundary without a recovery command.
    Unexpected errors are allowed to propagate and fail CI visibly.
    """

    try:
        result = ingest(
            config_path=config_path,
            institution_ids=institution_ids,
            paths=paths,
            start_year=start_year,
            end_year=end_year,
            updated_since=updated_since,
            max_pages=max_pages,
            allow_candidate=allow_candidate,
            max_credits=max_credits,
            max_cost_usd=max_cost_usd,
            **({"replace_output": True} if replace_output else {}),
            **({"anchor_author_ids": anchor_author_ids} if anchor_author_ids else {}),
            **({"raw_affiliation_scope": True} if raw_affiliation_scope else {}),
            # Owner AT11-WINDOW: the daily runner caps publication dates at yesterday UTC.
            **({"publication_date_cap": publication_date_cap} if publication_date_cap else {}),
        )
    except OpenAlexRateLimitError as error:
        return {
            "status": "deferred",
            "reason": "rate_limited",
            "message": str(error),
            "retry_after": error.retry_after,
        }
    except OpenAlexBudgetError as error:
        return {"status": "deferred", "reason": "budget_exceeded", "message": str(error)}
    return {"status": "success", **dict(result)}
