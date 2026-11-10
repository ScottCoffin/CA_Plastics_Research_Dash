"""Write ``site/data/status.json`` for ``site/status.html`` (S10.1).

Reads the history log and, when ``GITHUB_TOKEN`` and ``GITHUB_REPOSITORY`` are set, the
recent Actions runs. A failed runs request is recorded as ``actions_status: unavailable``
and never fails the build.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from atlas.build.status import (
    DEFAULT_CONFIG,
    DEFAULT_HISTORY,
    build_payload,
    detect_drift,
    fetch_actions_runs,
    load_thresholds,
    read_history,
    utc_now_iso,
    write_payload,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=Path("site/data/status.json"))
    args = parser.parse_args(argv)

    history = read_history(args.history)
    drift = detect_drift(history, load_thresholds(args.config))

    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    actions_runs: list[dict] = []
    actions_status = "skipped"
    if token and repo:
        fetched = fetch_actions_runs(repo, token)
        actions_status = "ok" if fetched is not None else "unavailable"
        actions_runs = fetched or []

    payload = build_payload(
        history,
        generated_at=utc_now_iso(),
        drift=drift,
        actions_runs=actions_runs,
        actions_status=actions_status,
    )
    write_payload(args.output, payload)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "drift_status": drift["status"],
                "alarms": len(drift["alarms"]),
                "history_records": len(history),
                "actions_status": actions_status,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
