import json
from pathlib import Path
from urllib.error import HTTPError
from io import BytesIO

import pytest

from atlas import source_watchlist as watch


def _paths(tmp_path):
    status = tmp_path / "status.json"
    docs = tmp_path / "SOURCES.md"
    docs.write_text(
        "manual before\n" + watch.START + "\nold generated\n" + watch.END + "\nmanual after\n"
    )
    return status, docs


def test_run_is_deterministic_preserves_manual_text_and_tracks_change(tmp_path, monkeypatch):
    fixture = Path("tests/fixtures/source_watch_s7_6/watch.json")
    status, docs = _paths(tmp_path)
    results = iter(
        [
            {
                "http_status": 403,
                "method": "HEAD",
                "bytes_read": 0,
                "access_status": "unavailable_or_restricted",
            },
            {"http_status": 200, "method": "HEAD", "bytes_read": 0, "access_status": "reachable"},
        ]
    )
    monkeypatch.setattr(watch, "probe", lambda _url: next(results))
    first = watch.run(fixture, status, docs, "2026-11-09T00:00:00+00:00")
    assert first["sources"]["ceden_2_microplastics"]["change"] == "baseline"
    assert len(first["history"]) == 1
    second = watch.run(fixture, status, docs, "2026-11-16T00:00:00+00:00")
    item = second["sources"]["ceden_2_microplastics"]
    assert item["change"] == "access_or_metadata_changed"
    assert item["tier"] == "C" and item["status"] == "manual_review"
    assert len(second["history"]) == 2
    text = docs.read_text()
    assert text.startswith("manual before\n") and text.endswith("\nmanual after\n")
    assert "403" not in "".join(first["sources"]["ceden_2_microplastics"].keys())
    persisted = json.loads(status.read_text())
    assert persisted["checked_at"] == "2026-11-16T00:00:00+00:00"


def test_rejects_duplicate_ids_and_private_or_unapproved_url(monkeypatch):
    monkeypatch.setattr(
        watch.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("8.8.8.8", 443))],
    )
    watch._validate_url("https://ceden.org/")
    for url in ("http://ceden.org", "https://example.org", "https://ceden.org@127.0.0.1"):
        with pytest.raises(ValueError):
            watch._validate_url(url)


def test_watchlist_unique_identity_and_limit(tmp_path, monkeypatch):
    fixture = tmp_path / "watch.json"
    status, docs = _paths(tmp_path)
    src = {
        "id": "x",
        "name": "X",
        "reason": "R",
        "next_review": "2027-01-01",
        "url": "https://ceden.org/",
    }
    fixture.write_text(json.dumps({"sources": [src, src]}))
    with pytest.raises(ValueError, match="unique"):
        watch.run(fixture, status, docs, "2026-11-09")
    fixture.write_text(json.dumps({"sources": [dict(src, id=str(i)) for i in range(51)]}))
    with pytest.raises(ValueError, match="50"):
        watch.run(fixture, status, docs, "2026-11-09")


def test_probe_range_fallback_reads_only_cap_and_reports_failures(monkeypatch):
    monkeypatch.setattr(watch, "_validate_url", lambda _url: None)
    seen = []

    class Response:
        status = 206
        headers = {"ETag": "fixture"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, limit):
            seen.append(limit)
            return b"x" * limit

    class Opener:
        def open(self, request, timeout):
            assert timeout == watch.TIMEOUT_SECONDS
            if request.method == "HEAD":
                raise HTTPError(request.full_url, 405, "no head", {}, BytesIO())
            assert request.get_header("Range") == f"bytes=0-{watch.MAX_BODY_BYTES - 1}"
            return Response()

    monkeypatch.setattr(watch.urllib.request, "build_opener", lambda *_args: Opener())
    result = watch.probe("https://ceden.org/")
    assert result["http_status"] == 206 and result["bytes_read"] == watch.MAX_BODY_BYTES
    assert seen == [watch.MAX_BODY_BYTES]

    class TimeoutOpener:
        def open(self, *_args, **_kwargs):
            raise TimeoutError()

    monkeypatch.setattr(watch.urllib.request, "build_opener", lambda *_args: TimeoutOpener())
    result = watch.probe("https://ceden.org/")
    assert result["http_status"] is None and result["error"] == "TimeoutError"


def test_workflow_guard_and_staging_are_narrow():
    workflow = Path(".github/workflows/source_watch_s7_6.yml").read_text()
    assert "vars.ENABLE_DATA_COMMITS == 'true'" in workflow
    assert "git add -- docs/SOURCES.md docs/api_notes/source_watch_s7_6.json" in workflow
    assert "data/" not in workflow
