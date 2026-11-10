"""Pipeline run status: history records, drift detection, and status-page payload (S10.1).

The history log ``data/processed/status_history.jsonl`` holds one JSON object per pipeline
run. Drift is judged only on ``status == "ok"`` records so that deferred or failed runs
(which leave the committed Parquet unchanged) do not distort the baselines.
"""

from __future__ import annotations

import json
import os
import statistics
import tempfile
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import yaml

STATUSES = ("ok", "deferred", "failed")
LABEL_RATE_KEYS = (
    "plastic_core",
    "plastic_tier2",
    "not_plastic",
    "needs_review",
    "ca_led",
    "ca_any_author",
)
LABEL_COLUMNS = ("plastic_related", "plastic_tier", "needs_review")
WORK_COLUMNS = ("ca_led", "ca_any_author")
RECORD_KEYS = (
    "run_at_utc",
    "workflow",
    "run_id",
    "status",
    "works_total",
    "works_added",
    "labels_total",
    "label_rates",
    "api_spend",
)
DEFAULT_THRESHOLDS: dict[str, float] = {
    "label_rate_max_abs_change": 0.05,
    "trailing_window": 7,
    "min_history": 2,
    "works_added_max_multiple": 3.0,
    "works_added_floor": 50,
    "count_drop_max_fraction": 0.01,
}
DEFAULT_HISTORY = Path("data/processed/status_history.jsonl")
DEFAULT_LABELS = Path("data/processed/work_labels.parquet")
DEFAULT_WORKS = Path("data/processed/normalized/works.parquet")
DEFAULT_USAGE_LOG = Path("data/logs/api_usage.jsonl")
DEFAULT_CONFIG = Path("config/status.yml")
RECENT_RUN_LIMIT = 20
ACTIONS_RUN_LIMIT = 30
ACTIONS_TIMEOUT_SECONDS = 15


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_thresholds(path: Path = DEFAULT_CONFIG) -> dict[str, float]:
    """Return drift thresholds from ``config/status.yml``, falling back to defaults."""
    thresholds = dict(DEFAULT_THRESHOLDS)
    if not path.exists():
        return thresholds
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"expected a YAML mapping in {path}")
    unknown = set(payload) - set(DEFAULT_THRESHOLDS)
    if unknown:
        raise ValueError(f"unknown status thresholds in {path}: {sorted(unknown)}")
    thresholds.update({key: float(value) for key, value in payload.items()})
    return thresholds


# ---------------------------------------------------------------------------
# Run records
# ---------------------------------------------------------------------------


def _count_true(column: pa.ChunkedArray) -> int:
    total = pc.sum(pc.cast(pc.fill_null(column, False), pa.int64())).as_py()
    return int(total or 0)


def _ratio(count: int, denominator: int) -> float | None:
    return round(count / denominator, 6) if denominator else None


def compute_label_rates(labels: pa.Table, works: pa.Table) -> dict[str, float | None]:
    """Compute label rates; label-based rates use the label table, CA rates the works table."""
    n_labels = labels.num_rows
    tier = labels.column("plastic_tier")
    rates: dict[str, float | None] = {
        "plastic_core": _ratio(_count_true(pc.equal(tier, "core")), n_labels),
        "plastic_tier2": _ratio(_count_true(pc.equal(tier, "chemicals-in-plastics")), n_labels),
        "not_plastic": _ratio(
            _count_true(pc.equal(labels.column("plastic_related"), False)), n_labels
        ),
        "needs_review": _ratio(_count_true(labels.column("needs_review")), n_labels),
        "ca_led": _ratio(_count_true(works.column("ca_led")), works.num_rows),
        "ca_any_author": _ratio(_count_true(works.column("ca_any_author")), works.num_rows),
    }
    return {key: rates[key] for key in LABEL_RATE_KEYS}


def load_parquet_tables(
    labels_path: Path = DEFAULT_LABELS, works_path: Path = DEFAULT_WORKS
) -> tuple[pa.Table, pa.Table]:
    """Read only the columns needed for status records."""
    labels = pq.read_table(labels_path, columns=list(LABEL_COLUMNS))
    works = pq.read_table(works_path, columns=list(WORK_COLUMNS))
    return labels, works


def load_usage_rows(path: Path = DEFAULT_USAGE_LOG) -> list[dict[str, Any]]:
    """Return parseable usage-log rows; malformed lines are skipped."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def spend_for_run(
    usage_rows: Sequence[Mapping[str, Any]], run_id: str, since: str | None = None
) -> dict[str, float] | None:
    """Sum this run's ``run_summary`` rows; ``None`` when there are none.

    Ingesters log their own run ids (for example ``openalex-works-<ts>``), not the
    GitHub run id, so a workflow passes ``since`` (its job start, ISO UTC) and every
    summary stamped at or after it counts. Without ``since`` the run id must match.
    """
    summaries = [
        row
        for row in usage_rows
        if row.get("record_type") == "run_summary"
        and (str(row.get("timestamp_utc") or "") >= since if since else row.get("run_id") == run_id)
    ]
    if not summaries:
        return None
    credits = sum(float(row.get("credits_total") or 0) for row in summaries)
    cost = sum(float(row.get("cost_usd_total") or 0) for row in summaries)
    return {"credits": round(credits, 6), "cost_usd": round(cost, 6)}


def build_run_record(
    *,
    run_at_utc: str,
    workflow: str,
    run_id: str,
    status: str,
    labels: pa.Table,
    works: pa.Table,
    usage_rows: Sequence[Mapping[str, Any]],
    previous_works_total: int | None,
    since: str | None = None,
) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, got {status!r}")
    works_total = works.num_rows
    works_added = (
        max(0, works_total - previous_works_total) if previous_works_total is not None else 0
    )
    return {
        "run_at_utc": run_at_utc,
        "workflow": workflow,
        "run_id": run_id,
        "status": status,
        "works_total": works_total,
        "works_added": works_added,
        "labels_total": labels.num_rows,
        "label_rates": compute_label_rates(labels, works),
        "api_spend": spend_for_run(usage_rows, run_id, since),
    }


# ---------------------------------------------------------------------------
# History log
# ---------------------------------------------------------------------------


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def read_history(path: Path = DEFAULT_HISTORY) -> list[dict[str, Any]]:
    """Parse the history log strictly; a missing file is an empty history."""
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: invalid JSON ({exc.msg})") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{number}: expected a JSON object")
        missing = [key for key in RECORD_KEYS if key not in record]
        if missing:
            raise ValueError(f"{path}:{number}: missing keys {missing}")
        if record["status"] not in STATUSES:
            raise ValueError(f"{path}:{number}: unknown status {record['status']!r}")
        records.append(record)
    return records


def append_record(path: Path, record: Mapping[str, Any]) -> None:
    """Append one record by rewriting the file through a temp file and ``os.replace``."""
    if record.get("status") not in STATUSES:
        raise ValueError(f"unknown status {record.get('status')!r}")
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    _atomic_write_text(path, existing + json.dumps(dict(record), sort_keys=True) + "\n")


def last_works_total(history: Sequence[Mapping[str, Any]]) -> int | None:
    for record in reversed(history):
        if isinstance(record.get("works_total"), int):
            return int(record["works_total"])
    return None


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


def _rate(record: Mapping[str, Any], key: str) -> float | None:
    value = (record.get("label_rates") or {}).get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _ints(records: Sequence[Mapping[str, Any]], field: str) -> list[int]:
    return [
        int(record[field])
        for record in records
        if isinstance(record.get(field), int) and not isinstance(record.get(field), bool)
    ]


def _alarm(metric: str, latest: float, baseline: float, threshold: float) -> dict[str, Any]:
    return {
        "metric": metric,
        "latest": round(float(latest), 6),
        "baseline": round(float(baseline), 6),
        "threshold": round(float(threshold), 6),
    }


def detect_drift(
    history: Sequence[Mapping[str, Any]], thresholds: Mapping[str, float] | None = None
) -> dict[str, Any]:
    """Compare the latest ``ok`` record with the median of up to ``trailing_window`` priors.

    Returns ``status`` as ``insufficient_history``, ``clear``, or ``alarm`` plus ``alarms``.
    """
    limits = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    ok = [record for record in history if record.get("status") == "ok"]
    if len(ok) < int(limits["min_history"]):
        return {"status": "insufficient_history", "alarms": [], "baseline_size": 0}

    latest = ok[-1]
    window = int(limits["trailing_window"])
    prior = ok[max(0, len(ok) - 1 - window) : -1]
    alarms: list[dict[str, Any]] = []

    max_change = float(limits["label_rate_max_abs_change"])
    for key in LABEL_RATE_KEYS:
        current = _rate(latest, key)
        baseline_values = [v for v in (_rate(r, key) for r in prior) if v is not None]
        if current is None or not baseline_values:
            continue
        baseline = statistics.median(baseline_values)
        if abs(current - baseline) > max_change:
            alarms.append(_alarm(f"label_rate.{key}", current, baseline, max_change))

    added_now = latest.get("works_added")
    added_base = _ints(prior, "works_added")
    if isinstance(added_now, int) and added_base:
        median_added = statistics.median(added_base)
        upper = max(
            float(limits["works_added_max_multiple"]) * median_added,
            float(limits.get("works_added_floor", 0)),
        )
        if not 0 <= added_now <= upper:
            alarms.append(_alarm("works_added", added_now, median_added, upper))

    drop_fraction = float(limits["count_drop_max_fraction"])
    for field in ("works_total", "labels_total"):
        current_count = latest.get(field)
        base_counts = _ints(prior, field)
        if not isinstance(current_count, int) or not base_counts:
            continue
        baseline = statistics.median(base_counts)
        floor = baseline * (1 - drop_fraction)
        if baseline > 0 and current_count < floor:
            alarms.append(_alarm(field, current_count, baseline, floor))

    return {
        "status": "alarm" if alarms else "clear",
        "alarms": alarms,
        "baseline_size": len(prior),
    }


# ---------------------------------------------------------------------------
# Actions runs (optional, best effort)
# ---------------------------------------------------------------------------


def fetch_actions_runs(
    repo: str,
    token: str,
    *,
    opener: Callable[..., Any] | None = None,
) -> list[dict[str, Any]] | None:
    """Return recent workflow runs, or ``None`` on any failure (never raises)."""
    if "/" not in repo or not token:
        return None
    open_url = opener or urllib.request.urlopen
    url = f"https://api.github.com/repos/{repo}/actions/runs?per_page={ACTIONS_RUN_LIMIT}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ca-plastics-research-atlas-status",
        },
    )
    try:
        with open_url(request, timeout=ACTIONS_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
        runs = payload.get("workflow_runs")
        if not isinstance(runs, list):
            return None
        return [_normalize_action_run(run) for run in runs[:ACTIONS_RUN_LIMIT] if run]
    except Exception:  # noqa: BLE001 - any network, auth, or parse failure is non-fatal
        return None


def _normalize_action_run(run: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": run.get("id"),
        "name": run.get("name"),
        "run_number": run.get("run_number"),
        "event": run.get("event"),
        "status": run.get("status"),
        "conclusion": run.get("conclusion"),
        "created_at": run.get("created_at"),
        "html_url": run.get("html_url"),
    }


# ---------------------------------------------------------------------------
# Page payload
# ---------------------------------------------------------------------------


def _run_row(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_at_utc": record["run_at_utc"],
        "workflow": record["workflow"],
        "run_id": record["run_id"],
        "status": record["status"],
        "works_total": record["works_total"],
        "works_added": record["works_added"],
        "labels_total": record["labels_total"],
        "api_spend": record["api_spend"],
    }


def _deltas(ok: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    if len(ok) < 2:
        return None
    previous, latest = ok[-2], ok[-1]
    rate_deltas: dict[str, float] = {}
    for key in LABEL_RATE_KEYS:
        current, before = _rate(latest, key), _rate(previous, key)
        if current is not None and before is not None:
            rate_deltas[key] = round(current - before, 6)
    return {
        "run_at_utc": latest["run_at_utc"],
        "compared_with_run_at_utc": previous["run_at_utc"],
        "works_total": latest["works_total"] - previous["works_total"],
        "labels_total": latest["labels_total"] - previous["labels_total"],
        "works_added": latest["works_added"],
        "label_rates": rate_deltas,
    }


def _spend(history: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    with_spend = [record for record in history if record.get("api_spend")]
    latest = with_spend[-1]["api_spend"] if with_spend else None
    return {
        "latest": latest,
        "total_credits": round(sum(r["api_spend"]["credits"] for r in with_spend), 6),
        "total_cost_usd": round(sum(r["api_spend"]["cost_usd"] for r in with_spend), 6),
        "runs_with_spend": len(with_spend),
    }


def build_payload(
    history: Sequence[Mapping[str, Any]],
    *,
    generated_at: str,
    drift: Mapping[str, Any] | None = None,
    actions_runs: Sequence[Mapping[str, Any]] | None = None,
    actions_status: str = "skipped",
) -> dict[str, Any]:
    """Build the ``site/data/status.json`` payload. Pure function of its inputs."""
    drift = drift if drift is not None else detect_drift(history)
    ok = [record for record in history if record.get("status") == "ok"]

    last_success: dict[str, Any] = {}
    for record in ok:  # history is append-ordered, so later records win
        last_success[record["workflow"]] = _run_row(record)

    series = {
        key: [
            {"run_at_utc": record["run_at_utc"], "value": _rate(record, key)}
            for record in history
            if _rate(record, key) is not None
        ]
        for key in LABEL_RATE_KEYS
    }

    return {
        "generated_at": generated_at,
        "drift_status": drift["status"],
        "history_records": len(history),
        "last_success_by_workflow": dict(sorted(last_success.items())),
        "recent_runs": [_run_row(r) for r in reversed(history)][:RECENT_RUN_LIMIT],
        "deltas": _deltas(ok),
        "spend": _spend(history),
        "label_rates_series": series,
        "alarms": list(drift["alarms"]),
        "actions_status": actions_status,
        "actions_runs": [dict(run) for run in (actions_runs or [])][:ACTIONS_RUN_LIMIT],
    }


def write_payload(path: Path, payload: Mapping[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    _atomic_write_text(path, text)
