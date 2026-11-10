from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.build import status as st
from scripts.build_status_page import main as build_main
from scripts.record_run_status import main as record_main

ROOT = Path(__file__).resolve().parents[1]
GENERATED = "2026-11-09T12:00:00Z"


def _record(i: int, *, core: float = 0.94, works_total: int = 194, added: int = 0) -> dict:
    return {
        "run_at_utc": f"2026-11-{i + 1:02d}T10:00:00Z",
        "workflow": "ingest_works",
        "run_id": str(1000 + i),
        "status": "ok",
        "works_total": works_total,
        "works_added": added,
        "labels_total": works_total,
        "label_rates": {
            "plastic_core": core,
            "plastic_tier2": 0.0,
            "not_plastic": 0.05,
            "needs_review": 0.0,
            "ca_led": 0.45,
            "ca_any_author": 1.0,
        },
        "api_spend": None,
    }


def _stable(n: int = 8) -> list[dict]:
    return [_record(i, added=1) for i in range(n)]


def _write_history(path: Path, records: list[dict]) -> Path:
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records), "utf-8")
    return path


def _tables(tmp_path: Path, n_works: int = 4) -> tuple[Path, Path]:
    labels = pa.table(
        {
            "plastic_related": [True, True, False, True][:n_works],
            "plastic_tier": ["core", "chemicals-in-plastics", "none", "core"][:n_works],
            "needs_review": [False, True, False, False][:n_works],
        }
    )
    works = pa.table(
        {
            "ca_led": [True, False, False, True][:n_works],
            "ca_any_author": [True, True, False, True][:n_works],
        }
    )
    labels_path = tmp_path / "work_labels.parquet"
    works_path = tmp_path / "works.parquet"
    pq.write_table(labels, labels_path)
    pq.write_table(works, works_path)
    return labels_path, works_path


def test_stable_history_raises_no_alarm() -> None:
    drift = st.detect_drift(_stable(), st.DEFAULT_THRESHOLDS)
    assert drift["status"] == "clear"
    assert drift["alarms"] == []


def test_label_rate_drift_alarm() -> None:
    history = _stable(7) + [_record(7, core=0.80)]
    drift = st.detect_drift(history)
    assert drift["status"] == "alarm"
    metrics = {a["metric"] for a in drift["alarms"]}
    assert metrics == {"label_rate.plastic_core"}
    alarm = drift["alarms"][0]
    assert alarm["latest"] == 0.8
    assert alarm["baseline"] == 0.94
    assert alarm["threshold"] == 0.05


def test_count_drop_alarm() -> None:
    history = _stable(7) + [_record(7, works_total=190, added=0)]
    drift = st.detect_drift(history)
    assert drift["status"] == "alarm"
    assert any(a["metric"] == "works_total" for a in drift["alarms"])


def test_works_added_outside_band_alarm() -> None:
    history = _stable(7) + [_record(7, works_total=650, added=500)]
    drift = st.detect_drift(history)
    assert any(a["metric"] == "works_added" for a in drift["alarms"])


def test_insufficient_history_is_not_an_alarm() -> None:
    drift = st.detect_drift([_record(0)])
    assert drift["status"] == "insufficient_history"
    assert drift["alarms"] == []


def test_deferred_runs_do_not_count_as_baseline() -> None:
    deferred = _record(7, core=0.10)
    deferred["status"] = "deferred"
    drift = st.detect_drift(_stable(7) + [deferred])
    assert drift["status"] == "clear"


def test_runs_api_failure_is_skipped(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def boom(*_args, **_kwargs):
        raise urllib.error.URLError("network down")

    assert st.fetch_actions_runs("owner/repo", "token", opener=boom) is None
    assert st.fetch_actions_runs("not-a-repo", "token", opener=boom) is None

    monkeypatch.setattr(st.urllib.request, "urlopen", boom)
    history = _write_history(tmp_path / "h.jsonl", _stable(3))
    out = tmp_path / "status.json"
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    assert build_main(["--history", str(history), "--output", str(out)]) == 0
    payload = json.loads(out.read_text("utf-8"))
    assert payload["actions_status"] == "unavailable"
    assert payload["actions_runs"] == []


def test_runs_api_success_is_normalized() -> None:
    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self) -> bytes:
            body = {"workflow_runs": [{"id": 7, "name": "Daily", "run_number": 3, "extra": 1}]}
            return json.dumps(body).encode("utf-8")

    runs = st.fetch_actions_runs("owner/repo", "token", opener=lambda *a, **k: _Response())
    assert runs is not None
    assert runs[0]["id"] == 7
    assert "extra" not in runs[0]


def test_payload_is_deterministic_and_has_schema(tmp_path: Path) -> None:
    history = _stable(25)
    drift = st.detect_drift(history)
    first = st.build_payload(history, generated_at=GENERATED, drift=drift)
    second = st.build_payload(history, generated_at=GENERATED, drift=drift)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert len(first["recent_runs"]) == st.RECENT_RUN_LIMIT
    assert first["last_success_by_workflow"]["ingest_works"]["run_id"] == "1024"
    assert first["deltas"]["compared_with_run_at_utc"] == history[-2]["run_at_utc"]
    assert first["spend"]["runs_with_spend"] == 0
    assert set(first["label_rates_series"]) == set(st.LABEL_RATE_KEYS)


def test_record_from_parquet_and_spend(tmp_path: Path) -> None:
    labels_path, works_path = _tables(tmp_path)
    labels, works = st.load_parquet_tables(labels_path, works_path)
    usage = [
        {"record_type": "request", "run_id": "r1", "cost_usd": 0.1, "credits": 1},
        {"record_type": "run_summary", "run_id": "r1", "credits_total": 5.0, "cost_usd_total": 0.5},
    ]
    record = st.build_run_record(
        run_at_utc=GENERATED,
        workflow="ingest_works",
        run_id="r1",
        status="ok",
        labels=labels,
        works=works,
        usage_rows=usage,
        previous_works_total=2,
    )
    assert record["works_total"] == 4
    assert record["works_added"] == 2
    assert record["labels_total"] == 4
    assert record["label_rates"]["plastic_core"] == 0.5
    assert record["label_rates"]["plastic_tier2"] == 0.25
    assert record["label_rates"]["not_plastic"] == 0.25
    assert record["label_rates"]["needs_review"] == 0.25
    assert record["label_rates"]["ca_led"] == 0.5
    assert record["label_rates"]["ca_any_author"] == 0.75
    assert record["api_spend"] == {"credits": 5.0, "cost_usd": 0.5}


def test_record_script_appends_atomically(tmp_path: Path) -> None:
    labels_path, works_path = _tables(tmp_path)
    history = tmp_path / "status_history.jsonl"
    common = ["--history", str(history), "--labels", str(labels_path), "--works", str(works_path)]
    usage = tmp_path / "missing_usage.jsonl"
    args = ["--usage-log", str(usage), *common]
    assert record_main(["--workflow", "seed", "--run-id", "local", "--status", "ok", *args]) == 0
    assert (
        record_main(["--workflow", "ingest_works", "--run-id", "9", "--status", "deferred", *args])
        == 0
    )
    records = st.read_history(history)
    assert [r["workflow"] for r in records] == ["seed", "ingest_works"]
    assert records[1]["works_added"] == 0
    assert not list(tmp_path.glob("*.tmp"))


def test_invalid_status_is_rejected(tmp_path: Path) -> None:
    labels_path, works_path = _tables(tmp_path)
    labels, works = st.load_parquet_tables(labels_path, works_path)
    with pytest.raises(ValueError):
        st.build_run_record(
            run_at_utc=GENERATED,
            workflow="x",
            run_id="1",
            status="success",
            labels=labels,
            works=works,
            usage_rows=[],
            previous_works_total=None,
        )


def test_committed_seed_history_parses() -> None:
    records = st.read_history(ROOT / "data" / "processed" / "status_history.jsonl")
    assert records, "seed record missing"
    assert records[0]["workflow"] == "seed"
    assert records[0]["status"] == "ok"


def test_spend_since_window_and_works_added_floor() -> None:
    from atlas.build import status as st

    rows = [
        {
            "record_type": "run_summary",
            "run_id": "openalex-works-1",
            "timestamp_utc": "2026-11-10T05:00:00Z",
            "credits_total": 5,
            "cost_usd_total": 0.0005,
        },
        {
            "record_type": "run_summary",
            "run_id": "openalex-works-2",
            "timestamp_utc": "2026-11-10T07:00:00Z",
            "credits_total": 7,
            "cost_usd_total": 0.0007,
        },
    ]
    assert st.spend_for_run(rows, "42", since="2026-11-10T06:00:00Z") == {
        "credits": 7.0,
        "cost_usd": 0.0007,
    }
    assert st.spend_for_run(rows, "42") is None
    assert st.DEFAULT_THRESHOLDS["works_added_floor"] == 50
