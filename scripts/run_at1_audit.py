"""Run the bounded, free-only AT-1 baseline and human-review sample collection."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from atlas.util.budget import (  # noqa: E402
    OpenAlexBudget,
    conservative_request_cost,
    daily_logged_usage,
    resolve_openalex_budget,
)
from atlas.util.cost import ApiCostLogger, OpenAlexUsageMetadataError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api.openalex.org"
QUERY_VERSION = "plastic-v2"
MAX_COST_USD = Decimal("0.10")
MAX_CREDITS = Decimal("1000")
MAX_REQUESTS = 80
MAX_TIMEOUT_SECONDS = 30
MAX_RESET_HORIZON_SECONDS = 26 * 60 * 60
RESET_CLOCK_SKEW_SECONDS = 5 * 60
SAMPLE_SIZE = 25
TOP_INSTITUTIONS = 20
QUERY_PATH = ROOT / "config/query_v2.txt"
REVIEW_QUEUE = ROOT / "data/processed/institution_review_top100.csv"
REGISTRY_PATH = ROOT / "data/processed/institutions.parquet"
OWNER_CONFIRMATION = ROOT / "docs/api_notes/openalex_free_only_owner_confirmation_2026-11-09.md"
USAGE_LOG = ROOT / "data/logs/api_usage.jsonl"
PROGRESS_CACHE = ROOT / "data/interim/at1_query_v2_audit_progress.json"
OUTPUT_CSV = ROOT / "docs/QUERY_AUDIT_REVIEW.csv"
OUTPUT_JSON = ROOT / "docs/QUERY_AUDIT_COUNTS.json"

BASELINE_IDS = {
    "UCSF": "I180670191",
    "SLAC": "I2801935854",
    "UC Davis": "I84218800",
}
USER_AGENT = "CA-Plastics-Research-Atlas/0.1 (AT-1 audit; contact via GitHub)"
FREE_ONLY_CONFIRMATION = "I confirm free daily allowance only; no paid fallback."
EXPECTED_BASELINES = {"global": 98118, "UCSF": 25, "SLAC": 2, "UC Davis": 129}
_STATUS_FIELDS = frozenset(
    {
        "daily_budget_usd",
        "daily_used_usd",
        "daily_remaining_usd",
        "credits_limit",
        "credits_used",
        "credits_remaining",
        "prepaid_remaining_usd",
        "onetime_credits_balance",
        "onetime_credits_remaining",
        "resets_at",
        "resets_in_seconds",
        "resets_in_seconds_at_capture",
    }
)


class AuditStop(RuntimeError):
    """A fail-closed audit condition with sanitized evidence."""


def load_api_key(environ: Mapping[str, str] | None = None, env_path: Path | None = None) -> str:
    """Load only the supported .env aliases without printing or persisting them."""
    env = os.environ if environ is None else environ
    key = env.get("OPENALEX_API_KEY") or env.get("OPEN_ALEX_API_KEY")
    if key:
        return key.strip().strip('"').strip("'")
    source = env_path or ROOT / ".env"
    if source.exists():
        for line in source.read_text(encoding="utf-8-sig").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() in {"OPENALEX_API_KEY", "OPEN_ALEX_API_KEY"}:
                key = value.strip().strip('"').strip("'")
                if key:
                    return key
    raise AuditStop("no OpenAlex key found in process environment or .env alias")


def read_query(path: Path = QUERY_PATH) -> tuple[str, str]:
    """Return exact configured filter and expression after validating its field."""
    configured = path.read_text(encoding="utf-8").strip()
    field, separator, expression = configured.partition(":")
    if not separator or field != "title_and_abstract.search" or not expression:
        raise AuditStop("query file must contain title_and_abstract.search filter syntax")
    return configured, expression


def load_top_institutions(
    review_path: Path = REVIEW_QUEUE, registry_path: Path = REGISTRY_PATH
) -> list[dict[str, str]]:
    """Select the existing top-20 review-queue strata; verify IDs in the registry."""
    with review_path.open(encoding="utf-8-sig", newline="") as stream:
        review = sorted(csv.DictReader(stream), key=lambda row: int(row["review_rank"]))
    selected = review[:TOP_INSTITUTIONS]
    if len(selected) != TOP_INSTITUTIONS:
        raise AuditStop(f"review queue contains only {len(selected)} rows; expected 20")
    ids = [row["openalex_id"].strip().rsplit("/", 1)[-1] for row in selected]
    if len(set(ids)) != TOP_INSTITUTIONS:
        raise AuditStop("top-20 review queue contains duplicate institution IDs")
    # Read only the selected identifiers and name columns, not the full registry payload.
    table = pq.read_table(
        registry_path,
        columns=["openalex_id", "display_name"],
        filters=[("openalex_id", "in", ids)],
    )
    registry_rows = {
        row["openalex_id"].rsplit("/", 1)[-1]: row["display_name"] for row in table.to_pylist()
    }
    output: list[dict[str, str]] = []
    for row, institution_id in zip(selected, ids, strict=True):
        name = row["display_name"].strip()
        if registry_rows.get(institution_id) != name:
            raise AuditStop(f"review queue/registry name mismatch for {institution_id}")
        output.append({"institution_id": institution_id, "institution_name": name})
    return output


def _http_request(
    url: str,
    api_key: str,
    timeout: int = MAX_TIMEOUT_SECONDS,
) -> tuple[int, dict[str, Any], Mapping[str, object]]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    request.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
            if not isinstance(body, dict):
                raise ValueError("response must be a JSON object")
            return response.status, body, dict(response.headers.items())
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            body = {}
        return error.code, body if isinstance(body, dict) else {}, dict(error.headers.items())


def _meta_count(body: Mapping[str, Any], *, endpoint: str) -> int:
    meta = body.get("meta")
    count = meta.get("count") if isinstance(meta, Mapping) else None
    if type(count) is not int or count < 0:
        raise AuditStop(f"{endpoint}: response meta.count missing or invalid")
    return count


def _rate_limit_state(
    body: Mapping[str, Any], *, now: datetime | None = None
) -> dict[str, Decimal | str]:
    rate = body.get("rate_limit")
    if not isinstance(rate, Mapping):
        raise AuditStop("rate-limit preflight: expected rate_limit object missing")
    required = (
        "daily_budget_usd",
        "daily_remaining_usd",
        "credits_limit",
        "credits_remaining",
        "prepaid_remaining_usd",
        "onetime_credits_remaining",
    )
    values: dict[str, Decimal] = {}
    for name in required:
        try:
            value = Decimal(str(rate[name]))
        except (KeyError, InvalidOperation, TypeError, ValueError) as error:
            raise AuditStop(f"rate-limit preflight: {name} missing or invalid") from error
        if not value.is_finite() or value < 0:
            raise AuditStop(f"rate-limit preflight: {name} must be finite and non-negative")
        values[name] = value
    for name in ("daily_used_usd", "credits_used", "onetime_credits_balance"):
        raw = rate.get(name)
        if name == "onetime_credits_balance" and raw is None:
            raw = rate.get("onetime_credits_remaining")
        if raw is not None:
            try:
                value = Decimal(str(raw))
            except (InvalidOperation, TypeError, ValueError) as error:
                raise AuditStop(f"rate-limit preflight: {name} missing or invalid") from error
            if not value.is_finite() or value < 0:
                raise AuditStop(f"rate-limit preflight: {name} must be finite and non-negative")
            values[name] = value
    reset_at = rate.get("resets_at")
    if not isinstance(reset_at, str):
        raise AuditStop("rate-limit preflight: resets_at missing or invalid")
    try:
        reset_time = datetime.fromisoformat(reset_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise AuditStop("rate-limit preflight: resets_at missing or invalid") from error
    if reset_time.tzinfo is None or reset_time.utcoffset() is None:
        raise AuditStop("rate-limit preflight: resets_at must include timezone")
    reset_time = reset_time.astimezone(UTC)
    observed_at = now or datetime.now(UTC)
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("status validation clock must include timezone")
    observed_at = observed_at.astimezone(UTC)
    reset_delta = (reset_time - observed_at).total_seconds()
    if reset_delta < -RESET_CLOCK_SKEW_SECONDS or reset_delta > MAX_RESET_HORIZON_SECONDS:
        raise AuditStop("rate-limit preflight: reset time is stale or outside the daily window")
    values["resets_at"] = reset_time.isoformat()
    reset_seconds = rate.get("resets_in_seconds", rate.get("resets_in_seconds_at_capture"))
    if reset_seconds is None:
        # Some provider responses expose only resets_at. Derive a local
        # countdown from the observation clock; never require a local artifact
        # annotation to be present on the wire.
        reset_value = Decimal(str(reset_delta))
        values["reset_seconds_source"] = "derived_from_resets_at_and_observation_time"
    else:
        try:
            reset_value = Decimal(str(reset_seconds))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise AuditStop("rate-limit preflight: reset seconds invalid") from error
    if (
        not reset_value.is_finite()
        or reset_value < 0
        or reset_value > MAX_RESET_HORIZON_SECONDS
        or abs(reset_delta - float(reset_value)) > RESET_CLOCK_SKEW_SECONDS
    ):
        raise AuditStop("rate-limit preflight: reset seconds inconsistent with reset time")
    values["resets_in_seconds_at_capture"] = reset_value
    if (
        values["prepaid_remaining_usd"] != 0
        or values["onetime_credits_remaining"] != 0
        or values.get("onetime_credits_balance", Decimal(0)) != 0
    ):
        raise AuditStop("rate-limit preflight found a nonzero prepaid or one-time balance")
    if values["daily_budget_usd"] <= 0 or values["daily_budget_usd"] > 1:
        raise AuditStop("rate-limit preflight does not match the free daily budget ceiling")
    if values["credits_limit"] <= 0 or values["credits_limit"] > 10000:
        raise AuditStop("rate-limit preflight does not match the free daily credit ceiling")
    if values["daily_remaining_usd"] > values["daily_budget_usd"]:
        raise AuditStop("rate-limit preflight reports remaining USD above its daily budget")
    if values["credits_remaining"] > values["credits_limit"]:
        raise AuditStop("rate-limit preflight reports credits above its daily limit")
    if values["daily_remaining_usd"] <= 0 or values["credits_remaining"] <= 0:
        raise AuditStop("rate-limit preflight found no remaining free daily allowance")
    return values


def _status_schema_diagnostics(body: Mapping[str, Any]) -> dict[str, object]:
    """Describe response shape and safe known scalar values without raw-body logging."""
    safe_names = {"rate_limit", "meta", "error", "message"}
    top_level = {
        str(name): type(value).__name__
        for name, value in body.items()
        if isinstance(name, str) and name.casefold() in safe_names
    }
    rate = body.get("rate_limit")
    rate_fields: dict[str, dict[str, str]] = {}
    if isinstance(rate, Mapping):
        for name, value in rate.items():
            if not isinstance(name, str) or name not in _STATUS_FIELDS:
                continue
            item = {"type": type(value).__name__}
            if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                item["value"] = str(value)
            elif isinstance(value, str) and name == "resets_at" and len(value) <= 64:
                item["value"] = value
            rate_fields[name] = item
    return {"top_level_types": top_level, "rate_limit_fields": rate_fields}


def _abstract_from_index(index: object, *, limit: int = 600) -> str:
    if not isinstance(index, Mapping):
        return ""
    words: list[tuple[int, str]] = []
    for token, positions in index.items():
        if isinstance(token, str) and isinstance(positions, list):
            words.extend((position, token) for position in positions if type(position) is int)
    words.sort()
    text = " ".join(token for _, token in words)
    return text[:limit].rsplit(" ", 1)[0] if len(text) > limit else text


def _request_url(filter_value: str, **params: object) -> str:
    encoded_filter = urllib.parse.quote(filter_value, safe="")
    query = f"filter={encoded_filter}&{urllib.parse.urlencode(params)}"
    return f"{BASE}/works?{query}"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as stream:
        temporary = Path(stream.name)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        # Windows indexers can briefly deny replacement after a target write.
        # Retry only transient access denial, with a short fixed bound.
        for attempt in range(4):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)


def _empty_progress(query: str, institutions: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "query_version": QUERY_VERSION,
        "query": query,
        "query_sha256": hashlib.sha256(query.encode("utf-8")).hexdigest(),
        "institutions": institutions,
        "baselines": {},
        "samples": {},
    }


def _load_progress(path: Path, query: str, institutions: list[dict[str, str]]) -> dict[str, Any]:
    if not path.exists():
        return _empty_progress(query, institutions)
    try:
        progress = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AuditStop(f"progress cache is unreadable: {path}") from error
    if (
        not isinstance(progress, dict)
        or progress.get("schema_version") != 1
        or progress.get("query_version") != QUERY_VERSION
        or progress.get("query") != query
        or progress.get("query_sha256") != hashlib.sha256(query.encode("utf-8")).hexdigest()
        or progress.get("institutions") != institutions
        or not isinstance(progress.get("baselines"), dict)
        or not isinstance(progress.get("samples"), dict)
    ):
        raise AuditStop("progress cache identity or schema mismatch; no calls made")
    for name, count in progress["baselines"].items():
        if name not in EXPECTED_BASELINES or type(count) is not int or count < 0:
            raise AuditStop("progress cache contains an invalid baseline; no calls made")
    institution_by_id = {row["institution_id"]: row for row in institutions}
    for institution_id, sample in progress["samples"].items():
        if institution_id not in institution_by_id or not isinstance(sample, dict):
            raise AuditStop("progress cache contains an unknown stratum; no calls made")
        records = sample.get("records")
        total = sample.get("matching_work_count")
        response_count = sample.get("response_work_count")
        if (
            not isinstance(records, list)
            or len(records) > SAMPLE_SIZE
            or type(total) is not int
            or total < len(records)
            or type(response_count) is not int
            or response_count < len(records)
            or response_count > SAMPLE_SIZE
        ):
            raise AuditStop("progress cache contains an invalid sample; no calls made")
        work_ids: set[str] = set()
        for record in records:
            if (
                not isinstance(record, dict)
                or record.get("institution_id") != institution_id
                or record.get("institution_name")
                != institution_by_id[institution_id]["institution_name"]
                or record.get("query_version") != QUERY_VERSION
                or record.get("source_query") != query
                or not isinstance(record.get("work_id"), str)
                or record["work_id"] in work_ids
                or record.get("review_label") != ""
                or record.get("reviewer") != ""
            ):
                raise AuditStop(
                    "progress cache contains an invalid/duplicate work row; no calls made"
                )
            work_ids.add(record["work_id"])
    return progress


def _progress_outputs(
    progress: dict[str, Any],
    *,
    output_csv: Path,
    output_json: Path,
    run_id: str,
    request_count: int,
    run_credits: Decimal,
    run_cost: Decimal,
    status_state: Mapping[str, Decimal | str],
    progress_cache_path: Path,
) -> dict[str, Any]:
    flat_rows: list[dict[str, str]] = []
    per_institution: dict[str, dict[str, int]] = {}
    for institution in progress["institutions"]:
        institution_id = institution["institution_id"]
        sample = progress["samples"].get(institution_id)
        records = sample["records"] if sample else []
        per_institution[institution_id] = {
            "sampled_rows": len(records),
            "matching_work_count": sample["matching_work_count"] if sample else None,
            "shortfall": max(0, SAMPLE_SIZE - len(records)),
            "status": "complete" if sample else "pending",
        }
        flat_rows.extend(records)
    multiplicity = Counter(row["work_id"] for row in flat_rows)
    for row in flat_rows:
        row["duplicate_across_strata"] = "yes" if multiplicity[row["work_id"]] > 1 else "no"
    fieldnames = [
        "institution_id",
        "institution_name",
        "work_id",
        "work_url",
        "title",
        "publication_date",
        "doi_url",
        "query_version",
        "source_query",
        "abstract_excerpt",
        "duplicate_across_strata",
        "review_label",
        "reviewer",
        "noise_terms",
    ]
    from io import StringIO

    csv_buffer = StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(flat_rows)
    _atomic_write(output_csv, csv_buffer.getvalue())

    drift = {
        name: value / expected - 1
        for name, expected in EXPECTED_BASELINES.items()
        if (value := progress["baselines"].get(name)) is not None
    }
    within_10 = {name: abs(drift[name]) <= 0.10 for name in drift}
    shortfall_total = sum(row["shortfall"] for row in per_institution.values())
    sample_rows = len(flat_rows)
    unique_count = len(multiplicity)
    completed_strata = len(progress["samples"])
    result = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "query_version": QUERY_VERSION,
        "query": progress["query"],
        "query_sha256": progress["query_sha256"],
        "http_filter_accepted": "global" in progress["baselines"],
        "baselines": progress["baselines"],
        "expected_baselines": EXPECTED_BASELINES,
        "baseline_relative_drift": drift,
        "baseline_within_10_percent": within_10,
        "sample_strata_completed": completed_strata,
        "sample_strata_target": TOP_INSTITUTIONS,
        "sample_strata_pending": TOP_INSTITUTIONS - completed_strata,
        "sample_rows": sample_rows,
        "sample_row_target": TOP_INSTITUTIONS * SAMPLE_SIZE,
        "unique_work_ids": unique_count,
        "duplicate_work_id_rows": sample_rows - unique_count,
        "sample_shortfall_rows": shortfall_total,
        "per_institution": per_institution,
        "labelled_rows": 0,
        "label_status": "blank for owner/colleague review; no labels inferred",
        "request_count_this_run": request_count,
        "metered_credits_this_run": str(run_credits),
        "metered_accounted_cost_usd_this_run": str(run_cost),
        "rate_limit_preflight": {key: str(value) for key, value in status_state.items()},
        "sample_csv": str(output_csv.relative_to(ROOT))
        if output_csv.is_relative_to(ROOT)
        else "external",
        "progress_cache": str(progress_cache_path.relative_to(ROOT))
        if progress_cache_path.is_relative_to(ROOT)
        else "external",
    }
    result["collection_status"] = (
        "complete_500"
        if sample_rows == 500 and shortfall_total == 0 and completed_strata == TOP_INSTITUTIONS
        else "partial_with_shortfalls_or_pending_strata"
    )
    _atomic_write(output_json, json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def _validate_artifact_paths(
    *,
    progress_cache_path: Path,
    output_csv: Path,
    output_json: Path,
    query_path: Path,
    review_path: Path,
    registry_path: Path,
    usage_log: Path,
) -> None:
    """Reject resolved path aliases before reads, writes, or network calls."""
    paths = {
        "progress cache": progress_cache_path,
        "review CSV output": output_csv,
        "count JSON output": output_json,
        "query input": query_path,
        "review queue input": review_path,
        "registry input": registry_path,
        "usage log": usage_log,
    }
    seen: dict[Path, str] = {}
    for label, path in paths.items():
        resolved = path.resolve()
        if resolved in seen:
            raise AuditStop(f"artifact path collision: {label} aliases {seen[resolved]}")
        seen[resolved] = label


def run_audit(
    *,
    api_key: str,
    confirmation: str,
    request_fn: Callable[
        [str, str, int], tuple[int, dict[str, Any], Mapping[str, object]]
    ] = _http_request,
    query_path: Path = QUERY_PATH,
    review_path: Path = REVIEW_QUEUE,
    registry_path: Path = REGISTRY_PATH,
    usage_log: Path = USAGE_LOG,
    output_csv: Path = OUTPUT_CSV,
    output_json: Path = OUTPUT_JSON,
    progress_cache_path: Path = PROGRESS_CACHE,
    budget: OpenAlexBudget | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, Any]:
    """Resume bounded baselines and per-institution samples from validated progress."""
    _validate_artifact_paths(
        progress_cache_path=progress_cache_path,
        output_csv=output_csv,
        output_json=output_json,
        query_path=query_path,
        review_path=review_path,
        registry_path=registry_path,
        usage_log=usage_log,
    )
    if confirmation != FREE_ONLY_CONFIRMATION:
        raise AuditStop("explicit free-only/no-paid-fallback confirmation is required")
    if not OWNER_CONFIRMATION.exists():
        raise AuditStop("owner free-only confirmation artifact is missing")
    owner_confirmation = OWNER_CONFIRMATION.read_text(encoding="utf-8").casefold()
    if not all(term in owner_confirmation for term in ("free-only", "no prepaid", "no paid plan")):
        raise AuditStop("owner confirmation does not attest free-only/no-paid account policy")
    query_filter, _ = read_query(query_path)
    institutions = load_top_institutions(review_path, registry_path)
    progress = _load_progress(progress_cache_path, query_filter, institutions)
    budget = budget or resolve_openalex_budget(max_cost_usd=MAX_COST_USD, max_credits=MAX_CREDITS)
    if budget.max_cost_usd is None or budget.max_cost_usd > MAX_COST_USD:
        raise AuditStop("effective run USD cap exceeds USD 0.10")
    if budget.max_credits is None or budget.max_credits > MAX_CREDITS:
        raise AuditStop("effective run credit cap exceeds 1000")
    prior_cost, prior_credits = daily_logged_usage(
        usage_log, cost_per_credit_usd=budget.cost_per_credit_usd, day=now().astimezone(UTC).date()
    )

    run_id = "at1-audit-" + uuid.uuid4().hex[:12]
    run_cost = Decimal(0)
    run_credits = Decimal(0)
    attempts = 0
    unknown_accounting = False
    status_state: dict[str, Decimal | str] | None = None
    failures: list[str] = []

    with ApiCostLogger(run_id, usage_log) as logger:

        def get_account_balance() -> dict[str, Decimal | str]:
            """Make one status observation outside metered per-request accounting."""
            nonlocal attempts
            if attempts >= MAX_REQUESTS:
                raise AuditStop("maximum request count 80 reached")
            attempts += 1
            try:
                status, body, _headers = request_fn(
                    f"{BASE}/rate-limit", api_key, MAX_TIMEOUT_SECONDS
                )
            except Exception as error:
                logger.record_account_balance_snapshot(
                    url=f"{BASE}/rate-limit", status_code=0, snapshot=None
                )
                raise AuditStop(
                    f"rate-limit preflight: request failed ({type(error).__name__}); stopped"
                ) from None
            try:
                state = _rate_limit_state(body, now=now())
            except AuditStop:
                logger.record_account_balance_snapshot(
                    url=f"{BASE}/rate-limit",
                    status_code=status,
                    snapshot=None,
                    diagnostics=_status_schema_diagnostics(body),
                )
                raise
            logger.record_account_balance_snapshot(
                url=f"{BASE}/rate-limit", status_code=status, snapshot=state
            )
            if status >= 400:
                raise AuditStop(f"rate-limit preflight: HTTP {status}; stopped")
            return state

        def get_json(url: str, endpoint: str) -> dict[str, Any]:
            nonlocal attempts, run_cost, run_credits, unknown_accounting
            if attempts >= MAX_REQUESTS:
                raise AuditStop("maximum request count 80 reached")
            reserve_error = budget.reserve_error(
                cost_usd=prior_cost + run_cost,
                credits=prior_credits + run_credits,
            )
            if reserve_error:
                raise AuditStop(f"{endpoint}: {reserve_error}")
            if status_state is not None:
                if run_cost + budget.reserve_cost_usd > min(
                    MAX_COST_USD, status_state["daily_remaining_usd"]
                ):
                    raise AuditStop(
                        f"{endpoint}: provider daily USD headroom lacks request reserve"
                    )
                if run_credits + budget.reserve_credits > min(
                    MAX_CREDITS, status_state["credits_remaining"]
                ):
                    raise AuditStop(
                        f"{endpoint}: provider daily credit headroom lacks request reserve"
                    )
            attempts += 1
            started = time.monotonic()
            try:
                status, body, headers = request_fn(url, api_key, MAX_TIMEOUT_SECONDS)
            except Exception as error:
                # Record an unknown-cost attempted request and stop; never retry.
                unknown_accounting = True
                logger.record(
                    source="openalex",
                    method="GET",
                    url=url,
                    status_code=0,
                    credits=0,
                    cost_usd=0,
                    credits_known=False,
                    cost_known=False,
                )
                raise AuditStop(
                    f"{endpoint}: request failed ({type(error).__name__}); no retry"
                ) from None
            latency_ms = round((time.monotonic() - started) * 1000, 3)
            try:
                logger.record_openalex_response(
                    method="GET", url=url, status_code=status, headers=headers, body=body
                )
            except OpenAlexUsageMetadataError:
                unknown_accounting = True
                raise AuditStop(
                    f"{endpoint}: response missing valid credit header; stopped"
                ) from None
            credit_header = next(
                (
                    value
                    for key, value in headers.items()
                    if key.casefold() == "x-ratelimit-credits-used"
                ),
                None,
            )
            meta = body.get("meta")
            meta_cost = meta.get("cost_usd") if isinstance(meta, Mapping) else None
            try:
                credits = Decimal(str(credit_header))
                cost = conservative_request_cost(
                    meta_cost,
                    credits,
                    budget.cost_per_credit_usd,
                    meta_cost_known=meta_cost is not None,
                )
            except (InvalidOperation, TypeError, ValueError):
                raise AuditStop(f"{endpoint}: response cost metadata invalid; stopped") from None
            run_cost += cost
            run_credits += credits
            if status >= 400:
                raise AuditStop(f"{endpoint}: HTTP {status}; stopped without retry")
            overrun = budget.actual_error(
                cost_usd=prior_cost + run_cost,
                credits=prior_credits + run_credits,
            )
            if overrun:
                raise AuditStop(f"{endpoint}: {overrun}")
            if logger.request_metrics[-1]["status_code"] != status:
                raise AuditStop(f"{endpoint}: usage record mismatch after {latency_ms:.0f} ms")
            return body

        def persist_progress() -> dict[str, Any]:
            if status_state is None:
                raise AuditStop("cannot persist audit progress without a fresh balance snapshot")
            _atomic_write(
                progress_cache_path,
                json.dumps(progress, indent=2, sort_keys=True) + "\n",
            )
            return _progress_outputs(
                progress,
                output_csv=output_csv,
                output_json=output_json,
                run_id=run_id,
                request_count=attempts,
                run_credits=run_credits,
                run_cost=run_cost,
                status_state=status_state,
                progress_cache_path=progress_cache_path,
            )

        try:
            # Authenticated provider status is the mandatory live preflight.
            status_state = get_account_balance()
            available_usd = min(status_state["daily_remaining_usd"], MAX_COST_USD)
            available_credits = min(status_state["credits_remaining"], MAX_CREDITS)
            if (
                available_usd < budget.reserve_cost_usd
                or available_credits < budget.reserve_credits
            ):
                raise AuditStop("rate-limit preflight lacks reserve for a next request")

            # One global count proves filter acceptance and supplies the global baseline.
            if "global" not in progress["baselines"]:
                count_body = get_json(
                    _request_url(query_filter, per_page=1), "global baseline/filter acceptance"
                )
                progress["baselines"]["global"] = _meta_count(
                    count_body, endpoint="global baseline"
                )
                persist_progress()
            for label, institution_id in BASELINE_IDS.items():
                if label not in progress["baselines"]:
                    count_body = get_json(
                        _request_url(
                            f"{query_filter},institutions.id:{institution_id}", per_page=1
                        ),
                        f"{label} baseline",
                    )
                    progress["baselines"][label] = _meta_count(
                        count_body, endpoint=f"{label} baseline"
                    )
                    persist_progress()

            for institution in institutions:
                institution_id = institution["institution_id"]
                if institution_id in progress["samples"]:
                    continue
                url = _request_url(
                    f"{query_filter},institutions.id:{institution_id}",
                    per_page=SAMPLE_SIZE,
                    select="id,title,doi,publication_date,abstract_inverted_index",
                )
                body = get_json(url, f"sample {institution_id}")
                results = body.get("results")
                if not isinstance(results, list) or len(results) > SAMPLE_SIZE:
                    raise AuditStop(f"sample {institution_id}: malformed result page; stopped")
                matching_work_count = _meta_count(body, endpoint=f"sample {institution_id}")
                records: list[dict[str, str]] = []
                seen_work_ids: set[str] = set()
                for work in results:
                    if not isinstance(work, Mapping) or not isinstance(work.get("id"), str):
                        raise AuditStop(f"sample {institution_id}: malformed work record")
                    work_id = work["id"]
                    compact_work_id = work_id.rsplit("/", 1)[-1]
                    if not compact_work_id:
                        raise AuditStop(f"sample {institution_id}: empty work ID")
                    if compact_work_id in seen_work_ids:
                        continue
                    seen_work_ids.add(compact_work_id)
                    doi = str(work.get("doi") or "")
                    records.append(
                        {
                            "institution_id": institution_id,
                            "institution_name": institution["institution_name"],
                            "work_id": compact_work_id,
                            "work_url": work_id,
                            "title": str(work.get("title") or ""),
                            "publication_date": str(work.get("publication_date") or ""),
                            "doi_url": doi if doi.startswith("https://doi.org/") else "",
                            "query_version": QUERY_VERSION,
                            "source_query": query_filter,
                            "abstract_excerpt": _abstract_from_index(
                                work.get("abstract_inverted_index")
                            ),
                            "duplicate_across_strata": "",
                            "review_label": "",
                            "reviewer": "",
                            "noise_terms": "",
                        }
                    )
                if matching_work_count < len(records):
                    raise AuditStop(f"sample {institution_id}: count smaller than result list")
                progress["samples"][institution_id] = {
                    "records": records,
                    "matching_work_count": matching_work_count,
                    "response_work_count": len(results),
                }
                persist_progress()
            return persist_progress()
        except AuditStop as error:
            failures.append(str(error))
            raise
        finally:
            if failures:
                failure_path = usage_log.with_name("at1_audit_failure.jsonl")
                failure_path.parent.mkdir(parents=True, exist_ok=True)
                with failure_path.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(
                        json.dumps(
                            {
                                "run_id": run_id,
                                "timestamp_utc": now().astimezone(UTC).isoformat(),
                                "failure": failures[0],
                                "requests_attempted": attempts,
                                "accounting_known": not unknown_accounting,
                                "credits_total": (
                                    str(run_credits) if not unknown_accounting else None
                                ),
                                "accounted_cost_usd": (
                                    str(run_cost) if not unknown_accounting else None
                                ),
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="make the bounded authenticated audit")
    parser.add_argument("--confirm-free-only", action="store_true")
    parser.add_argument(
        "--offline-plan", action="store_true", help="show request plan without network"
    )
    args = parser.parse_args()
    if args.offline_plan:
        print(
            json.dumps(
                {
                    "request_cap": MAX_REQUESTS,
                    "usd_cap": str(MAX_COST_USD),
                    "credit_cap": str(MAX_CREDITS),
                    "planned_requests": 1 + 1 + len(BASELINE_IDS) + TOP_INSTITUTIONS,
                    "sample_rows": TOP_INSTITUTIONS * SAMPLE_SIZE,
                    "query_version": QUERY_VERSION,
                    "live": False,
                },
                indent=2,
            )
        )
        return 0
    if not args.live:
        parser.error("choose --offline-plan or --live")
    if not args.confirm_free_only:
        parser.error("live mode requires --confirm-free-only")
    try:
        result = run_audit(api_key=load_api_key(), confirmation=FREE_ONLY_CONFIRMATION)
    except AuditStop as error:
        print(f"AT-1 audit stopped: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
