import json
from pathlib import Path

from atlas import ceden_watch as watch

S76_BLOCK = "<!-- S7.6 WATCHLIST START -->\n\nold generated\n\n<!-- S7.6 WATCHLIST END -->"
MOORE = {
    "Program": "SF Bay Regional Monitoring for Water Quality",
    "ParentProject": "",
    "Project": "2017-2018 Microplastic Study - Moore Foundation",
}
NEW_STUDY = {"Program": "Other Program", "ParentProject": "", "Project": "New Study"}
RESOURCES = [
    {
        "id": "r2016",
        "name": "2016 CEDEN Water Chemistry Data",
        "datastore_active": True,
        "format": "CSV",
    },
    {
        "id": "r2017",
        "name": "2017 CEDEN Water Chemistry Data",
        "datastore_active": True,
        "format": "CSV",
    },
    {
        "id": "r2026",
        "name": "2026 CEDEN Water Chemistry Data",
        "datastore_active": True,
        "format": "CSV",
    },
    {"id": "rold", "name": "Retired CEDEN Data", "datastore_active": False, "format": "CSV"},
    {
        "id": "rzip",
        "name": "CEDEN Water Chemistry Data (Parquet File Format - All Years)",
        "datastore_active": True,
        "format": "ZIP",
    },
]


def _fixture(rows_2016=2, extra=()):
    records = [MOORE] * rows_2016 + list(extra)
    return {
        "package_show": {"result": {"resources": RESOURCES}},
        "datastore": {
            "r2016": {"total": len(records), "records": records},
            "r2017": {"total": 0, "records": []},
            "r2026": {"total": 0, "records": []},
        },
    }


def _paths(tmp_path):
    status = tmp_path / "ceden_watch.json"
    docs = tmp_path / "SOURCES.md"
    docs.write_text(
        "manual before\n\n" + S76_BLOCK + "\n\nmanual after\n",
        encoding="utf-8",
    )
    return status, docs


def _run(fixture, status, docs, when="2026-11-10T00:00:00+00:00"):
    return watch.run_watch(watch.offline_transport(fixture), when, status, docs)


def test_baseline_then_no_change_writes_block_and_keeps_surrounding_text(tmp_path):
    status, docs = _paths(tmp_path)
    first = _run(_fixture(), status, docs)
    assert first["resources"]["r2016"]["classification"] == "baseline"
    assert first["resources"]["r2017"]["classification"] == "baseline"
    assert "rold" not in first["resources"]
    assert first["resources"]["r2016"]["rows"] == 2
    assert first["resources"]["r2016"]["projects"] == {
        "SF Bay Regional Monitoring for Water Quality / "
        "2017-2018 Microplastic Study - Moore Foundation": 2
    }
    text = docs.read_text(encoding="utf-8")
    assert "Total microplastics rows across checked resources: 2." in text
    assert "| 2016 CEDEN Water Chemistry Data | 2 | 1 |" in text
    assert "New projects flagged: none." in text
    assert "not data quality, completeness, or reuse rights" in text
    assert "2017 CEDEN" not in text.split("S7.8 CEDEN WATCH START")[1]
    second = _run(_fixture(), status, docs, "2026-11-17T00:00:00+00:00")
    assert second["resources"]["r2016"]["classification"] == "no_change"
    assert len(second["history"]) == 1
    raw = status.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"}\n")
    # package_show, r2016 count and one project page, r2017 count, r2026 count
    assert json.loads(raw)["requests"] == 5


def test_new_project_is_flagged_and_listed(tmp_path):
    status, docs = _paths(tmp_path)
    _run(_fixture(), status, docs)
    result = _run(_fixture(extra=[NEW_STUDY]), status, docs, "2026-11-17T00:00:00+00:00")
    record = result["resources"]["r2016"]
    assert record["classification"] == "new_project"
    assert record["new_projects"] == ["Other Program / New Study"]
    text = docs.read_text(encoding="utf-8")
    assert "New projects flagged: 2016 CEDEN Water Chemistry Data: Other Program / New Study." in (
        text
    )


def test_row_increase_without_new_project_is_new_rows(tmp_path):
    status, docs = _paths(tmp_path)
    _run(_fixture(rows_2016=2), status, docs)
    result = _run(_fixture(rows_2016=5), status, docs, "2026-11-17T00:00:00+00:00")
    assert result["resources"]["r2016"]["classification"] == "new_rows"
    assert result["resources"]["r2016"]["new_projects"] == []


def test_failed_lookup_is_not_zero_and_keeps_last_good_value(tmp_path):
    status, docs = _paths(tmp_path)
    _run(_fixture(), status, docs)
    failing = _fixture()
    failing["datastore"]["r2016"] = {"error": True}
    failed = _run(failing, status, docs, "2026-11-17T00:00:00+00:00")
    record = failed["resources"]["r2016"]
    assert record["classification"] == "failed"
    assert record["rows"] is None and record["projects"] is None
    assert record["error"] == "FixtureError"
    assert record["good"]["rows"] == 2
    assert "Failed lookups (not treated as zero): 2016 CEDEN Water Chemistry Data" in (
        docs.read_text(encoding="utf-8")
    )
    recovered = _run(_fixture(), status, docs, "2026-11-24T00:00:00+00:00")
    assert recovered["resources"]["r2016"]["classification"] == "no_change"
    assert len(recovered["history"]) == 3


def test_block_replacement_is_idempotent_and_leaves_s76_block_alone(tmp_path):
    status, docs = _paths(tmp_path)
    _run(_fixture(), status, docs)
    _run(_fixture(rows_2016=3), status, docs, "2026-11-17T00:00:00+00:00")
    text = docs.read_text(encoding="utf-8")
    assert text.count(watch.START) == 1 and text.count(watch.END) == 1
    assert text.startswith("manual before\n\n" + S76_BLOCK + "\n\n<!-- S7.8 CEDEN WATCH START -->")
    assert text.endswith(watch.END + "\n\nmanual after\n")
    assert "Total microplastics rows across checked resources: 3." in text
    assert "Total microplastics rows across checked resources: 2." not in text


def test_request_budget_caps_requests_and_marks_overflow_as_failed(tmp_path):
    status, docs = _paths(tmp_path)
    many = [
        {"id": f"r{i:02d}", "name": f"Year {i:02d}", "datastore_active": True, "format": "CSV"}
        for i in range(45)
    ]
    fixture = {
        "package_show": {"result": {"resources": many}},
        "datastore": {r["id"]: {"total": 0, "records": []} for r in many},
    }
    result = _run(fixture, status, docs)
    assert result["requests"] == watch.MAX_REQUESTS
    errors = [r["error"] for r in result["resources"].values() if r["error"]]
    assert errors == ["RequestBudgetExceeded"] * 6
    assert all(r["rows"] is None for r in result["resources"].values() if r["error"])


def test_package_failure_keeps_prior_records_and_says_so(tmp_path):
    status, docs = _paths(tmp_path)
    _run(_fixture(), status, docs)
    broken = {"package_show": {"error": True}, "datastore": {}}
    result = _run(broken, status, docs, "2026-11-17T00:00:00+00:00")
    assert result["package_error"] == "FixtureError"
    assert result["resources"]["r2016"]["rows"] == 2
    text = docs.read_text(encoding="utf-8")
    assert "Resource listing failed (FixtureError)" in text
    assert text.count(watch.START) == 1


def test_history_is_capped_at_one_hundred(tmp_path):
    status, docs = _paths(tmp_path)
    old = {
        "history": [{"checked_at": f"t{i}", "digest": str(i)} for i in range(100)],
        "resources": {},
    }
    status.write_text(json.dumps(old), encoding="utf-8")
    result = _run(_fixture(), status, docs)
    assert len(result["history"]) == 100
    assert result["history"][-1]["digest"] != "99"


def test_fixture_cli_writes_to_given_paths(tmp_path):
    status, docs = _paths(tmp_path)
    fixture_path = tmp_path / "fixture.json"
    fixture_path.write_text(json.dumps(_fixture()), encoding="utf-8")
    result = watch.main(
        [
            "--offline-fixture",
            str(fixture_path),
            "--status-path",
            str(status),
            "--docs-path",
            str(docs),
        ]
    )
    assert result["resources"]["r2016"]["classification"] == "baseline"
    assert status.exists() and watch.START in docs.read_text(encoding="utf-8")


def test_live_transport_bounds_the_request_and_checks_success(monkeypatch):
    seen = {}

    class Body:
        def __init__(self, data):
            self.data = data

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, limit):
            return self.data[:limit]

    def fake_urlopen(request, timeout):
        seen["url"] = request.full_url
        seen["agent"] = request.get_header("User-agent")
        seen["timeout"] = timeout
        return Body(json.dumps({"success": True, "result": {"total": 3}}).encode())

    monkeypatch.setattr(watch.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(watch.time, "sleep", lambda _seconds: None)
    client = watch.DataCaTransport()
    result = client("datastore_search", {"resource_id": "r", "filters": watch.FILTERS, "limit": 0})
    assert result == {"total": 3}
    assert seen["url"].startswith(watch.API_BASE + "/datastore_search?")
    assert "particles%2Fm3" in seen["url"]
    assert seen["agent"] == "ca-plastics-atlas/0.1 (research dashboard)"
    assert seen["timeout"] == 30

    monkeypatch.setattr(
        watch.urllib.request,
        "urlopen",
        lambda request, timeout: Body(json.dumps({"success": False}).encode()),
    )
    try:
        client("package_show", {"id": watch.PACKAGE_ID})
    except ValueError as error:
        assert "success=false" in str(error)
    else:
        raise AssertionError("success=false must raise")


def test_workflow_adds_ceden_step_and_narrow_allowlist():
    workflow = Path(".github/workflows/source_watch_s7_6.yml").read_text(encoding="utf-8")
    assert (
        "git add -- docs/SOURCES.md docs/api_notes/source_watch_s7_6.json "
        "docs/api_notes/ceden_watch.json"
    ) in workflow
    assert "data/" not in workflow
    check = workflow.index("python scripts/check_source_watch_s7_6.py")
    step_start = workflow.rindex("- name:", 0, workflow.index("python scripts/watch_ceden"))
    guard = workflow.index("Explain disabled commit guard")
    assert check < step_start < guard
    assert "PYTHONPATH: src" in workflow[step_start:guard]
