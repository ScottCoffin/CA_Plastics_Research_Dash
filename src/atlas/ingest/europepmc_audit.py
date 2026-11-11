"""Europe PMC recall audit (S2.5b).

Fetches California-affiliated Europe PMC records on plastics terms as a benchmark,
diffs their DOIs against the corpus, and fetches the missing DOIs from OpenAlex under
the active query filter so they can be merged through the normal ingest path.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from atlas.ingest import openalex as oa
from atlas.query import openalex_filter, type_filters
from atlas.util.budget import (
    conservative_request_cost,
    daily_logged_usage,
    resolve_openalex_budget,
)
from atlas.util.cost import ApiCostLogger

EPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
EPMC_USER_AGENT = "Mozilla/5.0 (compatible; research-audit)"
EPMC_QUERY = (
    'AFF:"California" AND (microplastic* OR nanoplastic* OR "plastic debris" '
    'OR "plastic pollution" OR "tire wear")'
)
EPMC_MIN_INTERVAL = 0.25  # at most 4 requests per second
DOI_BATCH_SIZE = 50

Fetcher = Callable[[str], dict[str, Any]]


def normalize_doi(value: object) -> str:
    """Lowercase a DOI and strip resolver prefixes; empty string when absent."""

    text = str(value or "").strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "doi:"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text.strip()


def epmc_url(query: str, *, cursor: str = "*", page_size: int = 1000) -> str:
    params = {
        "query": query,
        "format": "json",
        "pageSize": page_size,
        "resultType": "lite",
        "cursorMark": cursor,
    }
    return f"{EPMC_SEARCH}?{urllib.parse.urlencode(params)}"


def _http_get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": EPMC_USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        body = json.load(response)
    if not isinstance(body, dict):
        raise ValueError("Europe PMC response must be a JSON object")
    return body


def fetch_benchmark(
    query: str = EPMC_QUERY,
    *,
    fetcher: Fetcher = _http_get_json,
    cache_dir: Path | None = None,
    sleep: Callable[[float], None] = time.sleep,
    max_pages: int = 50,
) -> list[dict[str, Any]]:
    """Cursor-page the Europe PMC search; optionally cache each raw page as JSON."""

    records: list[dict[str, Any]] = []
    cursor = "*"
    for page in range(max_pages):
        body = fetcher(epmc_url(query, cursor=cursor))
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / f"page_{page:03d}.json").write_text(json.dumps(body), encoding="utf-8")
        results = (body.get("resultList") or {}).get("result") or []
        records.extend(r for r in results if isinstance(r, Mapping))
        next_cursor = body.get("nextCursorMark")
        if not results or not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        sleep(EPMC_MIN_INTERVAL)
    return records


def benchmark_dois(records: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map normalized DOI to one Europe PMC record (records without a DOI are dropped)."""

    out: dict[str, dict[str, Any]] = {}
    for record in records:
        doi = normalize_doi(record.get("doi"))
        if doi:
            out.setdefault(doi, dict(record))
    return out


def missing_dois(bench: Iterable[str], corpus: Iterable[str]) -> list[str]:
    known = set(corpus)
    return sorted({doi for doi in bench if doi not in known})


def is_queryable_doi(doi: str) -> bool:
    """OpenAlex filters split on commas and pipes, so those DOIs cannot be batched."""

    return bool(doi) and "," not in doi and "|" not in doi


def doi_batches(dois: Sequence[str], size: int = DOI_BATCH_SIZE) -> list[list[str]]:
    if not 1 <= size <= DOI_BATCH_SIZE:
        raise ValueError("DOI batches hold at most 50 DOIs")
    return [list(dois[i : i + size]) for i in range(0, len(dois), size)]


def build_doi_url(config: Mapping[str, Any], batch: Sequence[str], *, per_page: int = 100) -> str:
    """One OpenAlex works request: DOI list AND active query AND type filters."""

    if not batch or len(batch) > DOI_BATCH_SIZE:
        raise ValueError("batch must hold 1 to 50 DOIs")
    filters = [
        "doi:" + "|".join(f"https://doi.org/{doi}" for doi in batch),
        openalex_filter(config),
        *type_filters(config),
    ]
    params = {"filter": ",".join(filters), "per-page": per_page}
    return f"{oa.OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"


def keep_for_corpus(work: Mapping[str, Any], institution_ids: set[str]) -> bool:
    """Gate before merge: a CA raw affiliation (strict matcher) or a registry institution."""

    if oa.keep_raw_affiliation_work(work):
        return True
    for authorship in work.get("authorships") or []:
        for inst in (authorship or {}).get("institutions") or []:
            if oa.compact_openalex_id(inst.get("id")) in institution_ids:
                return True
    return False


def fetch_openalex_by_doi(
    batches: Sequence[Sequence[str]],
    *,
    config: Mapping[str, Any],
    run_id: str,
    max_credits: float,
    budget_path: str | Path = "config/budget.yml",
    usage_log: str | Path = "data/logs/api_usage.jsonl",
    raw_dir: Path = Path("data/raw/openalex_works"),
) -> dict[str, Any]:
    """Run DOI batches through the OpenAlex client and budget guard.

    Returns the matched works and credit use; raises OpenAlexBudgetError when the guard
    stops the run (nothing is merged by this function).
    """

    budget = resolve_openalex_budget(budget_path, max_credits=max_credits)
    prior_cost, prior_credits = daily_logged_usage(
        usage_log, cost_per_credit_usd=budget.cost_per_credit_usd
    )
    cost_total = Decimal(0)
    credits_total = Decimal(0)
    works: list[dict[str, Any]] = []
    requests = 0
    with ApiCostLogger(run_id, usage_log) as logger:
        for batch in batches:
            error = budget.reserve_error(
                cost_usd=prior_cost + cost_total, credits=prior_credits + credits_total
            )
            if error:
                raise oa.OpenAlexBudgetError(f"{error}; no records merged")
            url = build_doi_url(config, batch)
            before = len(logger.request_metrics)
            body = oa._request_json(url, logger=logger)
            for record in logger.request_metrics[before:]:
                if record["credits_known"] is not True:
                    raise oa.OpenAlexUsageMetadataError("unknown credit usage")
                credits = Decimal(str(record["credits"]))
                credits_total += credits
                cost_total += conservative_request_cost(
                    record["cost_usd"] if record["cost_known"] else None,
                    credits,
                    budget.cost_per_credit_usd,
                    meta_cost_known=record["cost_known"] is True,
                )
            overrun = budget.actual_error(
                cost_usd=prior_cost + cost_total, credits=prior_credits + credits_total
            )
            if overrun:
                raise oa.OpenAlexBudgetError(f"{overrun}; no records merged")
            requests += 1
            raw_dir.mkdir(parents=True, exist_ok=True)
            oa._write_snapshot(
                oa._snapshot_path(raw_dir, run_id, requests),
                run_id=run_id,
                request_number=requests,
                url=url,
                body=body,
            )
            results = body.get("results")
            if not isinstance(results, list):
                raise ValueError("OpenAlex response results must be a list")
            works.extend(w for w in results if isinstance(w, dict))
    return {"works": works, "requests": requests, "credits": float(credits_total)}


def merge_works(
    works: Iterable[Mapping[str, Any]], *, run_id: str, output: Path
) -> tuple[int, int]:
    """Merge works into the raw Parquet via the ingester's atomic merge (dedupe by id).

    Returns (new ids added, total rows).
    """

    fetched_at = datetime.now(UTC).isoformat()
    new_rows = [oa._row_from_work(w, run_id=run_id, fetched_at_utc=fetched_at) for w in works]
    existing = oa._read_rows(output)
    existing_ids = {oa.compact_openalex_id(r.get("openalex_id")) for r in existing}
    merged = oa._merge_rows(existing, new_rows)
    oa._atomic_write_parquet(output, merged)
    added = len({r["openalex_id"] for r in new_rows} - existing_ids)
    return added, len(merged)


def build_report(
    *,
    query: str,
    date: str,
    total: int,
    with_doi: int,
    in_corpus: int,
    in_corpus_ca: int,
    published: int,
    missing: int,
    matched: int = 0,
    not_in_openalex: int = 0,
    failed_query: int = 0,
    rejected_gate: int = 0,
    credits: float = 0.0,
) -> dict[str, Any]:
    def share(n: int) -> float:
        return round(n / with_doi, 4) if with_doi else 0.0

    return {
        "query": query,
        "date": date,
        "total": total,
        "with_doi": with_doi,
        "in_corpus": in_corpus,
        "in_corpus_ca": in_corpus_ca,
        "published_on_site": published,
        "missing": missing,
        "openalex_matched": matched,
        "not_in_openalex": not_in_openalex,
        "failed_query": failed_query,
        "rejected_gate": rejected_gate,
        "recall_in_corpus": share(in_corpus),
        "recall_ca_in_corpus": share(in_corpus_ca),
        "credits": credits,
    }
