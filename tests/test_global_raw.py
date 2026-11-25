"""PLAT-4a global raw fetch: offline tests (HTTP layer patched at urlopen)."""

from __future__ import annotations

import gzip
import importlib.util
import io
import json
import urllib.error
import urllib.parse
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from atlas.ingest import global_raw, openalex
from atlas.ingest.global_raw import (
    StateMismatchError,
    build_global_url,
    dry_run,
    estimate_global,
    fetch_global,
    query_hash,
    year_windows,
)
from atlas.query import load_query_config, openalex_filter

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "queries.yml"
BUDGET = ROOT / "config" / "budget.yml"
NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
CREDIT_HEADER = "X-RateLimit-Credits-Used"


class FakeResponse:
    def __init__(self, body: dict[str, Any], credits: int) -> None:
        self._raw = json.dumps(body).encode("utf-8")
        self.status = 200
        self.headers = {CREDIT_HEADER: str(credits)}

    def read(self) -> bytes:
        return self._raw

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class FakeOpenAlex:
    """Scripted urlopen: each call pops the next scripted response (body or HTTP error)."""

    def __init__(self, script: list[Callable[[str], object]]) -> None:
        self.script = list(script)
        self.urls: list[str] = []

    def __call__(self, request: Any, timeout: int) -> object:
        url = request.full_url
        self.urls.append(url)
        if not self.script:
            raise AssertionError(f"unexpected request: {url}")
        return self.script.pop(0)(url)


def ok(body: dict[str, Any], credits: int = 10) -> Callable[[str], object]:
    return lambda url: FakeResponse(body, credits)


def rate_limited(message: str = "Daily limit reached") -> Callable[[str], object]:
    def raise_429(url: str) -> object:
        raise urllib.error.HTTPError(
            url, 429, "Too Many Requests", {}, io.BytesIO(json.dumps({"message": message}).encode())
        )

    return raise_429


def work(number: int, publication_date: str = "2025-03-01") -> dict[str, Any]:
    return {
        "id": f"https://openalex.org/W{number}",
        "publication_date": publication_date,
        "publication_year": int(publication_date[:4]),
        "ids": {
            "openalex": f"https://openalex.org/W{number}",
            "pmid": f"https://pubmed.ncbi.nlm.nih.gov/{number}",
        },
        "title": f"Work {number}",
    }


def page(works: list[dict[str, Any]], next_cursor: str | None, count: int = 0) -> dict[str, Any]:
    return {"meta": {"count": count, "next_cursor": next_cursor}, "results": works}


@pytest.fixture(autouse=True)
def no_sleep_or_throttle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openalex, "_throttle", lambda: None)
    monkeypatch.setattr(openalex.time, "sleep", lambda seconds: None)
    monkeypatch.delenv("OPENALEX_API_KEY_ALT", raising=False)
    monkeypatch.delenv("OPENALEX_MAX_COST_USD", raising=False)
    monkeypatch.delenv("OPENALEX_MAX_CREDITS", raising=False)


def install(monkeypatch: pytest.MonkeyPatch, script: list[Callable[[str], object]]) -> FakeOpenAlex:
    fake = FakeOpenAlex(script)
    monkeypatch.setattr(openalex.urllib.request, "urlopen", fake)
    return fake


def paths(tmp_path: Path) -> dict[str, Path]:
    return {"raw_dir": tmp_path / "raw", "usage_log": tmp_path / "logs" / "usage.jsonl"}


def run_estimate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, works: int = 250
) -> dict[str, Any]:
    install(monkeypatch, [ok(page([], None, count=works), credits=10)])
    return estimate_global(
        config_path=CONFIG,
        budget_path=BUDGET,
        start_year=2024,
        end_year=2025,
        now=NOW,
        **paths(tmp_path),
    )


def read_state(tmp_path: Path) -> dict[str, Any]:
    return json.loads((tmp_path / "raw" / "state.json").read_text(encoding="utf-8"))


def read_page(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def test_rendered_url_has_one_query_and_no_institution_or_paid_filter() -> None:
    config = load_query_config(CONFIG)
    url = build_global_url(config, start_date="2025-01-01", end_date="2025-12-31")
    decoded = urllib.parse.unquote_plus(url)
    assert openalex_filter(config) in decoded
    assert "institutions" not in decoded
    assert "raw_affiliation" not in decoded
    assert "authorships" not in decoded
    assert "from_updated_date" not in decoded
    assert "from_created_date" not in decoded
    assert "from_publication_date:2025-01-01" in decoded
    assert "to_publication_date:2025-12-31" in decoded
    assert decoded.count("title_and_abstract.search:") == 1


def test_year_windows_stop_at_yesterday_and_skip_future_years() -> None:
    windows = year_windows(2025, 2027, date(2026, 11, 25))
    assert windows[0] == {"year": 2025, "from": "2025-01-01", "to": "2025-12-31"}
    assert windows[1] == {"year": 2026, "from": "2026-01-01", "to": "2026-11-24"}
    assert [w["year"] for w in windows] == [2025, 2026]


def test_query_hash_changes_with_query_version_or_terms(tmp_path: Path) -> None:
    config = load_query_config(CONFIG)
    changed = dict(config, version="plastic-v9-test")
    assert query_hash(config) != query_hash(changed)
    edited = dict(config, core_terms=[*config["core_terms"], "extra term"])
    assert query_hash(config) != query_hash(edited)
    assert query_hash(config) == query_hash(load_query_config(CONFIG))


def test_estimate_records_count_pages_and_cost_before_paging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = install(monkeypatch, [ok(page([], None, count=250), credits=10)])
    result = estimate_global(
        config_path=CONFIG,
        budget_path=BUDGET,
        start_year=2024,
        end_year=2025,
        now=NOW,
        **paths(tmp_path),
    )
    assert len(fake.urls) == 1
    assert "per-page=1" in fake.urls[0]
    assert "institutions" not in urllib.parse.unquote_plus(fake.urls[0])
    assert result["works"] == 250
    assert result["pages_min"] == 3
    assert result["slices"] == 2
    assert result["pages_max"] == 5
    assert result["credits_per_page"] == 10.0
    assert result["usd_max"] == pytest.approx(0.005)
    saved = json.loads((tmp_path / "raw" / "estimate.json").read_text(encoding="utf-8"))
    assert saved["works"] == 250
    assert not (tmp_path / "raw" / "state.json").exists()


def test_paging_resumes_at_saved_cursor_after_credit_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_estimate(tmp_path, monkeypatch)
    first = [work(1), work(2)]
    install(
        monkeypatch,
        [
            ok(page(first, "cursor-2")),
            ok(page([work(3)], "cursor-3")),
        ],
    )
    # 20 credits: two 10-credit pages fit, a third would exceed the cap, so it stops.
    stopped = fetch_global(
        config_path=CONFIG,
        budget_path=BUDGET,
        start_year=2024,
        end_year=2025,
        now=NOW,
        max_credits=20,
        **paths(tmp_path),
    )
    assert stopped["status"] == "deferred"
    assert stopped["reason"] == "run_credit_cap"
    assert stopped["pages_this_run"] == 2
    state = read_state(tmp_path)
    assert state["slices"]["2024"]["cursor"] == "cursor-3"
    assert state["slices"]["2024"]["pages"] == 2
    assert state["pages_done"] == 2
    assert state["credits_total"] == pytest.approx(20.0)

    fake = install(
        monkeypatch,
        [
            ok(page([work(4, "2024-06-01")], None)),
            ok(page([work(5, "2025-02-02")], None)),
        ],
    )
    resumed = fetch_global(
        config_path=CONFIG,
        budget_path=BUDGET,
        start_year=2024,
        end_year=2025,
        now=NOW,
        max_credits=1000,
        **paths(tmp_path),
    )
    assert resumed["status"] == "success"
    assert "cursor=cursor-3" in fake.urls[0]
    assert resumed["slices_done"] == 2
    raw = tmp_path / "raw" / "pages"
    names = sorted(p.name for p in raw.iterdir())
    assert names == [
        "2024_00001.jsonl.gz",
        "2024_00002.jsonl.gz",
        "2024_00003.jsonl.gz",
        "2025_00001.jsonl.gz",
    ]
    rows = read_page(raw / "2024_00001.jsonl.gz")
    assert rows[0]["record_type"] == "page_header"
    assert rows[1]["ids"]["pmid"].endswith("/1")
    assert rows[1]["ids"]["openalex"] == "https://openalex.org/W1"


def test_completed_fetch_makes_no_request_on_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_estimate(tmp_path, monkeypatch)
    install(monkeypatch, [ok(page([work(1)], None)), ok(page([work(2, "2025-01-05")], None))])
    done = fetch_global(
        config_path=CONFIG,
        budget_path=BUDGET,
        start_year=2024,
        end_year=2025,
        now=NOW,
        max_credits=1000,
        **paths(tmp_path),
    )
    assert done["status"] == "success"
    fake = install(monkeypatch, [])
    again = fetch_global(
        config_path=CONFIG,
        budget_path=BUDGET,
        start_year=2024,
        end_year=2025,
        now=NOW,
        max_credits=1000,
        **paths(tmp_path),
    )
    assert again["status"] == "success"
    assert again["pages_this_run"] == 0
    assert fake.urls == []


def test_changed_query_hash_refuses_resume_unless_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_estimate(tmp_path, monkeypatch)
    install(monkeypatch, [ok(page([work(1)], "c2"))])
    fetch_global(
        config_path=CONFIG,
        budget_path=BUDGET,
        start_year=2024,
        end_year=2024,
        now=NOW,
        max_credits=10,
        **paths(tmp_path),
    )
    other = tmp_path / "queries_other.yml"
    text = CONFIG.read_text(encoding="utf-8").replace(
        "version: plastic-v3.1", "version: plastic-v9"
    )
    other.write_text(text, encoding="utf-8")
    fake = install(monkeypatch, [])
    with pytest.raises(StateMismatchError, match="--restart"):
        fetch_global(
            config_path=other,
            budget_path=BUDGET,
            start_year=2024,
            end_year=2024,
            now=NOW,
            max_credits=1000,
            **paths(tmp_path),
        )
    assert fake.urls == []

    install(monkeypatch, [ok(page([work(9)], None))])
    restarted = fetch_global(
        config_path=other,
        budget_path=BUDGET,
        start_year=2024,
        end_year=2024,
        now=NOW,
        max_credits=1000,
        restart=True,
        **paths(tmp_path),
    )
    assert restarted["status"] == "success"
    assert read_state(tmp_path)["query_version"] == "plastic-v9"
    raw = tmp_path / "raw"
    assert any(p.name.startswith("state.restart-") for p in raw.iterdir())
    assert any(p.name.startswith("pages.restart-") for p in raw.iterdir())


def test_daily_guard_stops_before_any_paging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_estimate(tmp_path, monkeypatch)
    usage = paths(tmp_path)["usage_log"]
    usage.parent.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).isoformat()
    # 9495 credits (USD 0.9495) already logged today: the next 10-credit call would pass USD 0.95.
    record = {
        "record_type": "request",
        "source": "openalex",
        "method": "GET",
        "timestamp_utc": today,
        "run_id": "earlier",
        "url": "https://api.openalex.org/works",
        "status_code": 200,
        "credits": 9495,
        "cost_usd": 0.9495,
        "credits_known": True,
        "cost_known": True,
    }
    usage.write_text(json.dumps(record) + "\n", encoding="utf-8")
    fake = install(monkeypatch, [])
    result = fetch_global(
        config_path=CONFIG,
        budget_path=BUDGET,
        start_year=2024,
        end_year=2025,
        now=NOW,
        max_credits=1000,
        **paths(tmp_path),
    )
    assert result["status"] == "deferred"
    assert result["reason"] == "budget_exceeded"
    assert fake.urls == []


def test_non_burst_429_defers_with_progress_saved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_estimate(tmp_path, monkeypatch)
    install(monkeypatch, [ok(page([work(1)], "c2")), rate_limited()])
    result = fetch_global(
        config_path=CONFIG,
        budget_path=BUDGET,
        start_year=2024,
        end_year=2025,
        now=NOW,
        max_credits=1000,
        **paths(tmp_path),
    )
    assert result["status"] == "deferred"
    assert result["reason"] == "rate_limited"
    state = read_state(tmp_path)
    assert state["pages_done"] == 1
    assert state["slices"]["2024"]["cursor"] == "c2"
    assert state["last_run"]["stop_reason"] == "rate_limited"


def unreachable(url: str) -> object:
    raise urllib.error.URLError("getaddrinfo failed")


def test_network_failure_on_page_two_defers_and_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_estimate(tmp_path, monkeypatch)
    # The request helper retries a transport failure 4 times before it gives up.
    install(monkeypatch, [ok(page([work(1)], "c2"))] + [unreachable] * 4)
    deferred = fetch_global(
        config_path=CONFIG,
        budget_path=BUDGET,
        start_year=2024,
        end_year=2025,
        now=NOW,
        max_credits=1000,
        **paths(tmp_path),
    )
    assert deferred["status"] == "deferred"
    assert deferred["reason"] == "network_error"
    assert deferred["pages_this_run"] == 1
    assert "http" not in deferred["message"].lower()
    assert (tmp_path / "raw" / "pages" / "2024_00001.jsonl.gz").exists()
    assert not (tmp_path / "raw" / "pages" / "2024_00002.jsonl.gz").exists()
    state = read_state(tmp_path)
    assert state["slices"]["2024"]["cursor"] == "c2"
    assert state["slices"]["2024"]["pages"] == 1
    assert state["pages_done"] == 1
    assert state["last_run"]["stop_reason"] == "network_error"

    fake = install(
        monkeypatch,
        [
            ok(page([work(2)], None)),
            ok(page([work(3, "2025-02-02")], None)),
        ],
    )
    resumed = fetch_global(
        config_path=CONFIG,
        budget_path=BUDGET,
        start_year=2024,
        end_year=2025,
        now=NOW,
        max_credits=1000,
        **paths(tmp_path),
    )
    assert resumed["status"] == "success"
    assert "cursor=c2" in fake.urls[0]
    assert resumed["slices_done"] == 2


def test_non_network_runtime_error_still_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_estimate(tmp_path, monkeypatch)

    def boom(url: str, **kwargs: Any) -> object:
        raise RuntimeError("OpenAlex request failed after 4 attempts")

    monkeypatch.setattr(global_raw, "_request_json", boom)
    with pytest.raises(RuntimeError, match="after 4 attempts"):
        fetch_global(
            config_path=CONFIG,
            budget_path=BUDGET,
            start_year=2024,
            end_year=2025,
            now=NOW,
            max_credits=1000,
            **paths(tmp_path),
        )


def test_http_error_is_not_treated_as_network_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_estimate(tmp_path, monkeypatch)

    def unauthorised(url: str) -> object:
        headers = {CREDIT_HEADER: "0"}
        raise urllib.error.HTTPError(url, 401, "Unauthorized", headers, io.BytesIO(b"{}"))

    install(monkeypatch, [unauthorised])
    with pytest.raises(RuntimeError, match="HTTP 401"):
        fetch_global(
            config_path=CONFIG,
            budget_path=BUDGET,
            start_year=2024,
            end_year=2025,
            now=NOW,
            max_credits=1000,
            **paths(tmp_path),
        )


def test_paging_refuses_without_recorded_estimate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = install(monkeypatch, [])
    with pytest.raises(StateMismatchError, match="--estimate"):
        fetch_global(
            config_path=CONFIG,
            budget_path=BUDGET,
            start_year=2024,
            end_year=2024,
            now=NOW,
            **paths(tmp_path),
        )
    assert fake.urls == []


def test_dry_run_prints_urls_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = install(monkeypatch, [])
    result = dry_run(config_path=CONFIG, start_year=2024, end_year=2025, now=NOW)
    assert fake.urls == []
    assert result["status"] == "dry_run"
    assert "per-page=100" in result["first_page_url"]
    assert "institutions" not in urllib.parse.unquote_plus(result["first_page_url"])


def test_cli_dry_run_exits_zero_without_network(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    script = ROOT / "scripts" / "fetch_global_raw.py"
    spec = importlib.util.spec_from_file_location("fetch_global_raw", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fake = install(monkeypatch, [])
    assert module.main(["--dry-run", "--config", str(CONFIG), "--start-year", "2024"]) == 0
    assert fake.urls == []
    assert "first_page_url" in capsys.readouterr().out
