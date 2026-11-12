"""Offline tests for scripts/fetch_trend_global.py (EM-7 global counts for the trend panel)."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMITTED = ROOT / "site" / "data" / "trend_global.json"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "fetch_trend_global", ROOT / "scripts" / "fetch_trend_global.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ftg = _load_module()


@pytest.fixture
def config() -> dict[str, Any]:
    return ftg.load_query_config(ROOT / "config" / "queries.yml")


@pytest.fixture
def fake_request(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    """Replace the OpenAlex call; record each URL and return a two-year group_by body."""

    calls: dict[str, Any] = {
        "urls": [],
        "body": {
            "group_by": [
                {"key": "2019", "count": 4},
                {"key": "2020", "count": 6},
                {"key": "unknown", "count": 9},
            ]
        },
    }

    def _fake(url: str, usage_log: Path) -> dict[str, Any]:
        calls["urls"].append(url)
        return calls["body"]

    monkeypatch.setattr(ftg, "fetch", _fake)
    calls["output"] = tmp_path / "trend_global.json"
    calls["log"] = tmp_path / "api_usage.jsonl"
    return calls


def _cache_file(path: Path, version: str, fetched: datetime) -> None:
    payload = {
        "schema_version": "em7.v1",
        "query_version": version,
        "fetched_at": fetched.isoformat(timespec="seconds"),
        "source": ftg.SOURCE,
        "by_year": {"2019": 4},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _run(fake: dict[str, Any], config_path: Path, *extra: str) -> int:
    return ftg.main(
        [
            "--config",
            str(config_path),
            "--output",
            str(fake["output"]),
            "--usage-log",
            str(fake["log"]),
            *extra,
        ]
    )


def test_cache_hit_skips_the_call(
    fake_request: dict[str, Any], config: dict[str, Any], capsys: pytest.CaptureFixture[str]
) -> None:
    _cache_file(fake_request["output"], config["version"], datetime.now(UTC))
    assert _run(fake_request, ROOT / "config" / "queries.yml") == 0
    assert fake_request["urls"] == []
    assert "cached" in capsys.readouterr().out


def test_version_change_triggers_a_call(
    fake_request: dict[str, Any], config: dict[str, Any]
) -> None:
    _cache_file(fake_request["output"], "plastic-v2", datetime.now(UTC))
    assert _run(fake_request, ROOT / "config" / "queries.yml") == 0
    assert len(fake_request["urls"]) == 1


def test_stale_cache_triggers_a_call(fake_request: dict[str, Any], config: dict[str, Any]) -> None:
    old = datetime.now(UTC) - timedelta(days=31)
    _cache_file(fake_request["output"], config["version"], old)
    assert _run(fake_request, ROOT / "config" / "queries.yml") == 0
    assert len(fake_request["urls"]) == 1


def test_force_refetches_a_fresh_cache(
    fake_request: dict[str, Any], config: dict[str, Any]
) -> None:
    _cache_file(fake_request["output"], config["version"], datetime.now(UTC))
    assert _run(fake_request, ROOT / "config" / "queries.yml", "--force") == 0
    assert len(fake_request["urls"]) == 1


def test_dry_run_makes_no_call(fake_request: dict[str, Any]) -> None:
    assert _run(fake_request, ROOT / "config" / "queries.yml", "--dry-run") == 0
    assert fake_request["urls"] == []
    assert not fake_request["output"].exists()


def test_output_shape_and_url(fake_request: dict[str, Any]) -> None:
    assert _run(fake_request, ROOT / "config" / "queries.yml") == 0
    payload = json.loads(fake_request["output"].read_text(encoding="utf-8"))
    assert set(payload) == {"schema_version", "query_version", "fetched_at", "source", "by_year"}
    assert payload["schema_version"] == "em7.v1"
    assert payload["query_version"] == "plastic-v3.1"
    assert payload["by_year"] == {"2019": 4, "2020": 6}
    assert list(payload["by_year"]) == sorted(payload["by_year"])
    assert datetime.fromisoformat(payload["fetched_at"]).tzinfo is not None
    assert fake_request["output"].read_bytes().endswith(b"}\n")
    assert b"\r\n" not in fake_request["output"].read_bytes()
    url = fake_request["urls"][0]
    assert "group_by=publication_year" in url
    assert "title_and_abstract.search" in url
    assert "institutions.id" not in url and "authorships" not in url


def test_failed_request_writes_no_file(
    monkeypatch: pytest.MonkeyPatch,
    fake_request: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    def _boom(url: str, usage_log: Path) -> dict[str, Any]:
        raise ftg.FetchError("OpenAlex request failed: HTTP 500")

    monkeypatch.setattr(ftg, "fetch", _boom)
    assert _run(fake_request, ROOT / "config" / "queries.yml") == 1
    assert not fake_request["output"].exists()
    assert "no file written" in capsys.readouterr().err


def test_redact_hides_api_key() -> None:
    assert ftg.redact("https://x/works?api_key=SECRET&group_by=x") == (
        "https://x/works?api_key=REDACTED&group_by=x"
    )


def test_url_too_long_is_refused(config: dict[str, Any]) -> None:
    long_config = {**config, "core_terms": [f"term{i:05d}x" for i in range(2000)]}
    with pytest.raises(ftg.FetchError, match="limit"):
        ftg.build_url(long_config)


def test_committed_file_matches_active_query_version(config: dict[str, Any]) -> None:
    if not COMMITTED.exists():
        pytest.skip("site/data/trend_global.json not committed yet")
    payload = json.loads(COMMITTED.read_text(encoding="utf-8"))
    assert payload["query_version"] == config["version"]
    assert payload["schema_version"] == "em7.v1"
    assert all(key.isdigit() for key in payload["by_year"])
