"""S10.1 acceptance check: status history, status payload, status page, and workflow wiring.

Offline only. Validates ``data/processed/status_history.jsonl`` (parses, known statuses),
``site/data/status.json`` (schema), ``site/status.html`` (alarm region, data source, no
external assets), the single About-tab link in ``site/index.html``, and YAML parsing of
both edited workflows.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.build import status as st  # noqa: E402

HISTORY = ROOT / "data" / "processed" / "status_history.jsonl"
PAYLOAD = ROOT / "site" / "data" / "status.json"
PAGE = ROOT / "site" / "status.html"
INDEX = ROOT / "site" / "index.html"
WORKFLOWS = [
    ROOT / ".github" / "workflows" / "ingest_works.yml",
    ROOT / ".github" / "workflows" / "build_deploy.yml",
]
PAYLOAD_KEYS = {
    "generated_at",
    "drift_status",
    "history_records",
    "last_success_by_workflow",
    "recent_runs",
    "deltas",
    "spend",
    "label_rates_series",
    "alarms",
    "actions_status",
    "actions_runs",
}
PAGE_MARKERS = {
    "alarm region": 'id="drift-alarms"',
    "alert role": 'role="alert"',
    "no-alarm text": "No drift alarms",
    "insufficient note": "Insufficient history",
    "data source": "data/status.json",
    "sparkline": "polyline",
}


def check_history() -> list[str]:
    errors: list[str] = []
    if not HISTORY.exists():
        return [f"missing {HISTORY.relative_to(ROOT)}"]
    try:
        records = st.read_history(HISTORY)
    except ValueError as exc:
        return [str(exc)]
    if not records:
        errors.append("history has no records")
    elif records[0]["workflow"] != "seed":
        errors.append("first history record should be the seed record")
    return errors


def check_payload() -> list[str]:
    errors: list[str] = []
    if not PAYLOAD.exists():
        return [f"missing {PAYLOAD.relative_to(ROOT)}; run scripts/build_status_page.py"]
    payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    missing = PAYLOAD_KEYS - set(payload)
    if missing:
        errors.append(f"status.json missing keys: {sorted(missing)}")
    if not isinstance(payload.get("recent_runs"), list) or len(payload["recent_runs"]) > 20:
        errors.append("recent_runs must be a list of at most 20 entries")
    if not isinstance(payload.get("alarms"), list):
        errors.append("alarms must be a list")
    series = payload.get("label_rates_series", {})
    if set(series) != set(st.LABEL_RATE_KEYS):
        errors.append("label_rates_series keys do not match label rate keys")
    return errors


def check_page() -> list[str]:
    if not PAGE.exists():
        return [f"missing {PAGE.relative_to(ROOT)}"]
    text = PAGE.read_text(encoding="utf-8")
    errors = [
        f"status.html missing {name}" for name, marker in PAGE_MARKERS.items() if marker not in text
    ]
    if re.search(r"<(script|link)[^>]+(src|href)=\"https?://", text):
        errors.append("status.html must not load external assets")
    return errors


def check_index_link() -> list[str]:
    text = INDEX.read_text(encoding="utf-8")
    anchors = re.findall(r'<a[^>]+href="status\.html"', text)
    if len(anchors) != 1:
        return [f"index.html should link status.html exactly once, found {len(anchors)}"]
    about = text[text.index('id="panel-about"') :]
    if 'href="status.html"' not in about:
        return ["status.html link is not inside the About panel"]
    return []


def check_workflows() -> list[str]:
    errors: list[str] = []
    for path in WORKFLOWS:
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"{path.name} does not parse: {type(exc).__name__}")
    ingest = (ROOT / ".github" / "workflows" / "ingest_works.yml").read_text(encoding="utf-8")
    deploy = (ROOT / ".github" / "workflows" / "build_deploy.yml").read_text(encoding="utf-8")
    if "scripts/record_run_status.py" not in ingest:
        errors.append("ingest_works.yml missing Record run status step")
    if "data/processed/status_history.jsonl" not in ingest:
        errors.append("ingest_works.yml does not commit status_history.jsonl")
    if "scripts/build_status_page.py" not in deploy:
        errors.append("build_deploy.yml missing Build status page step")
    if not re.search(r"permissions:\n(?:  .*\n)*?  actions: read", deploy):
        errors.append("build_deploy.yml missing actions: read permission")
    return errors


def main() -> int:
    errors = (
        check_history() + check_payload() + check_page() + check_index_link() + check_workflows()
    )
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("S10.1 status checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
