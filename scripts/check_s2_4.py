"""Machine acceptance checks for the guarded daily works workflow."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

from atlas.ingest.daily import run_daily_ingest
from atlas.ingest.openalex import OpenAlexBudgetError, OpenAlexPaths, OpenAlexRateLimitError

WORKFLOW = Path(".github/workflows/ingest_works.yml")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for required in (
        "schedule:",
        "workflow_dispatch:",
        "ENABLE_DATA_COMMITS == 'true'",
        "OPENALEX_API_KEY",
        "steps.refresh.outputs.status == 'success'",
    ):
        assert required in workflow, f"workflow is missing {required!r}"

    with tempfile.TemporaryDirectory(prefix="s2-4-acceptance-") as directory:
        root = Path(directory)
        state = root / "high_water.json"
        state.write_text(json.dumps({"schema_version": 1, "last_run": "before"}), encoding="utf-8")
        before = _digest(state)
        paths = OpenAlexPaths(
            raw_dir=root / "raw",
            output_parquet=root / "works.parquet",
            high_water_mark=state,
            usage_log=root / "usage.jsonl",
        )

        def rate_limited(**_: object) -> dict[str, object]:
            raise OpenAlexRateLimitError("simulated 429", retry_after="60")

        deferred = run_daily_ingest(institution_ids=["I1"], paths=paths, ingest=rate_limited)
        assert deferred == {
            "status": "deferred",
            "reason": "rate_limited",
            "message": "simulated 429",
            "retry_after": "60",
        }
        assert _digest(state) == before, "429 must not advance high-water state"

        def budget_stopped(**_: object) -> dict[str, object]:
            raise OpenAlexBudgetError("simulated budget stop")

        budget = run_daily_ingest(institution_ids=["I1"], paths=paths, ingest=budget_stopped)
        assert budget["status"] == "deferred" and budget["reason"] == "budget_exceeded"

        resumed = run_daily_ingest(
            institution_ids=["I1"],
            paths=paths,
            ingest=lambda **_: {"fetched": 1, "rows_written": 1},
        )
        assert resumed["status"] == "success"

    print("S2.4 acceptance passed: workflow guards and resumable 429/budget stops verified")


if __name__ == "__main__":
    main()
