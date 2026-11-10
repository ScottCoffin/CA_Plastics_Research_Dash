"""S8.9 acceptance check: open funding-calls payload, pipeline self-test, and panel markup.

Offline only.  Validates ``site/data/open_calls.json`` (schema, sort order, open status
and deadlines relative to its own snapshot date), runs the fixture CSV through the
selection pipeline, and confirms the Funding panel markup and workflow step exist.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.ingest.grants import open_calls as oc  # noqa: E402

PAYLOAD = ROOT / "site" / "data" / "open_calls.json"
FIXTURE = ROOT / "tests" / "fixtures" / "s8_9_grants_portal.csv"
INDEX = ROOT / "site" / "index.html"
WORKFLOW = ROOT / ".github" / "workflows" / "build_deploy.yml"
CALL_KEYS = {
    "portal_id",
    "title",
    "agency",
    "deadline",
    "status",
    "url",
    "categories",
    "est_funding",
}
PANEL_MARKERS = {
    "Funding panel": 'id="panel-funding"',
    "open calls heading": "Open funding calls",
    "status region": 'id="open-calls-status"',
    "list container": 'id="open-calls"',
    "lazy loader": 'fetch("data/open_calls.json"',
    "tab hook": 'if (state.tab === "funding") showOpenCalls();',
    "public-domain note": (
        "Source: California Grants Portal (public domain), refreshed daily; "
        "calls are opportunities, not awards"
    ),
    "empty state": "No open plastic-related calls right now",
}


def _check_payload() -> dict:
    assert PAYLOAD.exists(), f"missing {PAYLOAD}; run scripts/build_open_calls.py"
    payload = json.loads(PAYLOAD.read_text(encoding="utf-8"))
    assert set(payload) == {"generated_at", "source_url", "licence", "calls"}, "payload keys"
    assert payload["source_url"] == oc.SOURCE_URL, "source_url must match the module constant"
    assert payload["licence"] == oc.LICENCE, "licence must be the portal's public-domain statement"
    assert isinstance(payload["calls"], list), "calls must be a list"
    # Same calendar basis as the builder: California standard time (UTC-8).
    generated = datetime.fromisoformat(payload["generated_at"].replace("Z", "+00:00"))
    snapshot = (generated - timedelta(hours=8)).date()
    seen: set[str] = set()
    keys: list[tuple] = []
    for call in payload["calls"]:
        assert set(call) == CALL_KEYS, f"call keys differ: {sorted(call)}"
        assert call["status"] in oc.OPEN_STATUSES, f"not an open status: {call['status']}"
        assert call["title"] and call["agency"], "title and agency are required"
        assert call["portal_id"] not in seen, f"duplicate portal_id {call['portal_id']}"
        seen.add(call["portal_id"])
        deadline = call["deadline"]
        if deadline == oc.ONGOING:
            ordering = (True, "", call["title"].casefold(), call["portal_id"])
        else:
            parsed = date.fromisoformat(deadline)  # raises if not ISO
            assert parsed >= snapshot, f"deadline {deadline} is before snapshot {snapshot}"
            ordering = (False, deadline, call["title"].casefold(), call["portal_id"])
        keys.append(ordering)
    assert keys == sorted(keys), "calls must be sorted by deadline, ongoing last"
    return payload


def _check_pipeline() -> None:
    query_config = yaml.safe_load((ROOT / "config" / "queries.yml").read_text(encoding="utf-8"))
    rows = oc.parse_csv(oc.decode_csv(FIXTURE.read_bytes()))
    payload, counts = oc.build_payload(
        rows,
        query_config=query_config,
        today=date(2026, 11, 9),
        generated_at="2026-11-09T00:00:00Z",
    )
    assert counts == {"rows": 14, "open": 11, "plastic_open": 7}, f"fixture counts {counts}"
    assert [c["portal_id"] for c in payload["calls"]] == [
        "P-007",
        "P-003",
        "P-001",
        "P-012",
        "P-013",
        "P-002",
        "P-010",
    ], "fixture selection changed"


def _check_panel() -> None:
    html = INDEX.read_text(encoding="utf-8")
    for label, marker in PANEL_MARKERS.items():
        assert marker in html, f"Funding panel is missing {label}: {marker}"
    assert "Funding catalogue coming next" not in html, "stub text should be replaced by the panel"
    assert len(re.findall(r'role="tab"', html)) == 5, "tab count must stay at five"
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["build"]["steps"]
    names = [s.get("name") for s in steps]
    assert "Refresh open funding calls" in names, "workflow step is missing"
    step = steps[names.index("Refresh open funding calls")]
    assert step.get("continue-on-error") is True, "refresh step must be continue-on-error"
    assert names.index("Refresh open funding calls") < names.index("Upload static site")


def main() -> None:
    payload = _check_payload()
    _check_pipeline()
    _check_panel()
    print(f"S8.9 open calls ok: {len(payload['calls'])} calls, generated {payload['generated_at']}")


if __name__ == "__main__":
    main()
