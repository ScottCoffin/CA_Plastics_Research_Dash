import copy
import http.server
import threading
from pathlib import Path

import pytest

from atlas import linkouts

REPO = Path(__file__).resolve().parents[1]
DESCRIPTIONS = {
    "LO-1": "plastic legislation that has been passed around the world",
    "LO-2": "a living resource, new studies can be added at any time",
    "LO-3": "a global database of microplastics observations in marine settings",
    "LO-4": "a global database of surface microplastics",
    "LO-5": "datasets available on plastics across the lifecycle",
    "LO-6": "an interactive registry that maps plastics data across more than 193 countries",
    "LO-7": "predicts the impact of potential interventions",
    "LO-8": "a curated and evolving directory of plastics research tools & resources",
    "LO-9": (
        "an open-source portal and toolkit designed to make microplastics data Findable, "
        "Accessible, Interoperable, and Reusable (FAIR)"
    ),
}


def _registry() -> dict:
    return linkouts.load_registry(REPO / "config" / "linkouts.yml")


def _mutated(mutate) -> list[str]:
    data = copy.deepcopy(_registry())
    mutate(data)
    return linkouts.validate_registry(data)


def test_real_registry_is_valid_with_quoted_descriptions():
    data = _registry()
    assert linkouts.validate_registry(data) == []
    by_id = {entry["id"]: entry for entry in data["entries"]}
    assert set(by_id) == set(linkouts.EXPECTED_IDS)
    assert len(data["entries"]) == len(linkouts.EXPECTED_IDS)
    for eid, text in DESCRIPTIONS.items():
        assert by_id[eid]["description"] == text
    assert by_id["LO-1"]["terms_status"] == "recorded"
    assert by_id["LO-1"]["terms"] == "Global Plastic Laws. All rights reserved."
    assert by_id["LO-3"]["update_model"] == "Data Update Frequency Quarterly"
    assert by_id["LO-8"]["disclosure"].startswith("The Atlas owner is a co-founder")
    assert by_id["LO-9"]["url_status"] == "owner_confirmed"
    assert all(entry["reuse_mode"] == "link_only" for entry in data["entries"])
    assert all(entry["last_checked"] is None for entry in data["entries"])
    assert "minderoo" not in str(data).lower()


def _drop_entry(data):
    data["entries"] = [e for e in data["entries"] if e["id"] != "LO-5"]


def _duplicate(data):
    data["entries"][1]["id"] = "LO-1"


def _set(eid, key, value):
    def mutate(data):
        next(e for e in data["entries"] if e["id"] == eid)[key] = value

    return mutate


def _add_minderoo(data):
    data["entries"][0]["name"] = "Minderoo Plastic Health Map"


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (_drop_entry, "missing id LO-5"),
        (_duplicate, "duplicate id LO-1"),
        (_set("LO-2", "reuse_mode", "mirror"), "reuse_mode must be link_only"),
        (_set("LO-3", "root_url", "http://www.ncei.noaa.gov/products/microplastics"), "https"),
        (_set("LO-4", "terms_status", "recorded"), "terms_status"),
        (_set("LO-1", "terms_status", "not recorded"), "terms_status"),
        (_set("LO-6", "last_checked", "2026-11-10T00:00:00Z"), "last_checked"),
        (_set("LO-8", "disclosure", "Owner is a co-founder."), "disclosure"),
        (_set("LO-1", "root_url", None), "root_url may be null"),
        (
            _set(
                "LO-1",
                "deep_link_templates",
                [{"template": "search", "evidence_url": "https://x.org/"}],
            ),
            "start with '/'",
        ),
        (_set("LO-7", "url_status", "maybe"), "url_status"),
        (_add_minderoo, "Minderoo"),
        (lambda d: d["entries"].append({**d["entries"][0], "id": "LO-13"}), "unexpected id LO-13"),
    ],
)
def test_validation_rejects_bad_registry(mutate, expected):
    errors = _mutated(mutate)
    assert errors, "expected a validation error"
    assert any(expected in error for error in errors), errors


def test_null_root_allowed_only_when_unavailable():
    errors = _mutated(
        lambda d: next(e for e in d["entries"] if e["id"] == "LO-12").update(
            root_url=None, url_status="unavailable"
        )
    )
    assert errors == []


def test_fake_transport_head_ok_makes_no_get():
    calls: list[tuple[str, str]] = []

    def transport(method, url):
        calls.append((method, url))
        return 200, None

    result = linkouts.check_links(["https://a.example/", "https://a.example/"], transport)
    assert list(result) == ["https://a.example/"]
    assert result["https://a.example/"] == {
        "method": "HEAD",
        "status": 200,
        "location": None,
        "error": None,
        "ok": True,
        "outcome": "ok",
    }
    assert calls == [("HEAD", "https://a.example/")]


@pytest.mark.parametrize("head_status", [405, 403, 501])
def test_head_refusal_falls_back_to_get(head_status):
    def transport(method, url):
        return (head_status, None) if method == "HEAD" else (200, None)

    record = linkouts.check_links(["https://b.example/"], transport)["https://b.example/"]
    assert record["method"] == "GET"
    assert record["status"] == 200
    assert record["ok"] is True


def test_redirect_is_reported_not_followed():
    calls: list[tuple[str, str]] = []

    def transport(method, url):
        calls.append((method, url))
        return 301, "https://new.example/page"

    record = linkouts.check_links(["https://c.example/old"], transport)["https://c.example/old"]
    assert record["status"] == 301
    assert record["location"] == "https://new.example/page"
    assert record["ok"] is False
    assert calls == [("HEAD", "https://c.example/old")]


def test_network_error_is_recorded_not_raised():
    def transport(method, url):
        raise OSError("timed out")

    record = linkouts.check_links(["https://d.example/"], transport)["https://d.example/"]
    assert record["status"] is None
    assert record["ok"] is False
    assert "timed out" in record["error"]


def test_workers_user_agent_and_timeout_constants():
    assert linkouts.MAX_WORKERS == 3
    assert linkouts.TIMEOUT_SECONDS == 10
    assert linkouts.MAX_BODY_BYTES == 1024
    assert linkouts.USER_AGENT == "ca-plastics-atlas/0.1 (research dashboard)"


class _Handler(http.server.BaseHTTPRequestHandler):
    def _respond(self):
        if self.path == "/moved":
            self.send_response(301)
            self.send_header("Location", "https://elsewhere.example/")
        elif self.command == "HEAD":
            self.send_response(405)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
        self.end_headers()
        if self.command == "GET":
            self.wfile.write(b"x" * 4096)

    do_HEAD = _respond
    do_GET = _respond

    def log_message(self, *args):  # keep test output quiet
        pass


def test_urllib_transport_reports_redirect_and_falls_back_on_405():
    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        moved = linkouts.check_links([f"{base}/moved"], linkouts.urllib_transport)
        assert moved[f"{base}/moved"]["status"] == 301
        assert moved[f"{base}/moved"]["location"] == "https://elsewhere.example/"
        ok = linkouts.check_links([f"{base}/page"], linkouts.urllib_transport)
        assert ok[f"{base}/page"] == {
            "method": "GET",
            "status": 200,
            "location": None,
            "error": None,
            "ok": True,
            "outcome": "ok",
        }
    finally:
        server.shutdown()
        server.server_close()


def test_timeline_urls_included_when_file_present(tmp_path):
    timeline = tmp_path / "dtsc_timeline.yml"
    timeline.write_text(
        "entries:\n"
        '  - id: "T1"\n'
        '    source_url: "https://dtsc.example/one"\n'
        '  - id: "T2"\n'
        "    source_url: null\n"
        '  - id: "T3"\n'
        '    source_url: "https://dtsc.example/one"\n'
        '  - id: "T4"\n'
        '    source_url: "https://dtsc.example/two"\n',
        encoding="utf-8",
    )
    assert linkouts.timeline_source_urls(timeline) == [
        "https://dtsc.example/one",
        "https://dtsc.example/two",
    ]
    seen: list[str] = []

    def transport(method, url):
        if method == "HEAD":
            seen.append(url)
        return 200, None

    out = tmp_path / "linkouts_check.json"
    payload = linkouts.run_live(timeline_path=timeline, output_path=out, transport=transport)
    assert "https://dtsc.example/one" in seen
    assert "https://dtsc.example/two" in seen
    assert set(payload["timeline"]) == {"https://dtsc.example/one", "https://dtsc.example/two"}


def test_timeline_absent_or_bad_url(tmp_path):
    assert linkouts.timeline_source_urls(tmp_path / "missing.yml") == []
    bad = tmp_path / "bad.yml"
    bad.write_text('entries:\n  - source_url: "http://insecure.example/"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="https"):
        linkouts.timeline_source_urls(bad)


def test_run_live_writes_json_and_leaves_yaml_unchanged(tmp_path):
    registry_path = REPO / "config" / "linkouts.yml"
    before = registry_path.read_bytes()
    out = tmp_path / "api_notes" / "linkouts_check.json"

    def transport(method, url):
        return 200, None

    payload = linkouts.run_live(
        registry_path=registry_path,
        timeline_path=tmp_path / "none.yml",
        output_path=out,
        transport=transport,
    )
    assert registry_path.read_bytes() == before
    assert out.exists()
    assert set(payload["entries"]) == set(linkouts.EXPECTED_IDS)
    # LO-12 and LO-9 URLs were confirmed by the owner in a browser (2026-11-10); dtsc.ca.gov
    # answers 403 to automated clients (2026-11-11), which is not evidence a page is gone.
    assert payload["entries"]["LO-12"]["url_status"] == "owner_confirmed"
    assert payload["entries"]["LO-12"]["root_url"].startswith("https://dtsc.ca.gov/")
    assert payload["entries"]["LO-9"]["url_status"] == "owner_confirmed"
    assert payload["entries"]["LO-1"]["last_checked"] == payload["checked_at"]
    assert payload["entries"]["LO-1"]["ok"] is True


def test_workflow_runs_linkout_check_after_ceden_and_allowlists_output():
    workflow = (REPO / ".github" / "workflows" / "source_watch_s7_6.yml").read_text(
        encoding="utf-8"
    )
    ceden = workflow.index("python scripts/watch_ceden_microplastics.py")
    step = workflow.index("python scripts/check_linkouts.py --live")
    guard = workflow.index("Explain disabled commit guard")
    assert ceden < step < guard
    assert "PYTHONPATH: src" in workflow[step - 200 : step]
    assert "pip install -c requirements/lock.txt pytest pyyaml" in workflow
    allow = next(line for line in workflow.splitlines() if "git add --" in line)
    assert "docs/api_notes/linkouts_check.json" in allow
    assert "config/" not in allow
