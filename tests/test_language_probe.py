"""Offline tests for scripts/fetch_language_probe.py (BQ-S4 native-language probe, A3 §5.7)."""

from __future__ import annotations

import importlib.util
import json
import urllib.parse
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMMITTED = ROOT / "site" / "data" / "global" / "language_probe.json"
VOCABULARY = ROOT / "config" / "search_vocabulary_v1.yml"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "fetch_language_probe", ROOT / "scripts" / "fetch_language_probe.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


flp = _load_module()
Responder = Callable[..., dict[str, Any]]


@pytest.fixture(scope="module")
def committed() -> dict[str, Any]:
    return json.loads(COMMITTED.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows() -> list[dict[str, Any]]:
    return flp.load_vocabulary_rows(VOCABULARY)


def _text(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False).lower()


def _append_spend(usage_log: Path, *, credits: int, cost_usd: str) -> None:
    """Write one logged OpenAlex request from today (UTC), as the shared client does."""

    record = {
        "record_type": "request",
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "run_id": "test-prior-spend",
        "source": "openalex",
        "method": "GET",
        "url": "https://api.openalex.org/works",
        "status_code": 200,
        "credits": credits,
        "cost_usd": float(cost_usd),
        "credits_known": True,
        "cost_known": True,
    }
    usage_log.parent.mkdir(parents=True, exist_ok=True)
    with usage_log.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")


def _ok_body(body: Mapping[str, Any]) -> Responder:
    """A fake _request_json that charges 10 credits per request, as the search filters do."""

    def _fake(url: str, *, logger: Any, attempts: int = 4, timeout: int = 60) -> dict[str, Any]:
        result = dict(body)
        logger.record_openalex_response(
            method="GET",
            url=url,
            status_code=200,
            headers={"X-RateLimit-Credits-Used": "10"},
            body=result,
        )
        return result

    return _fake


def _fake_openalex(
    url: str, *, logger: Any, attempts: int = 4, timeout: int = 60
) -> dict[str, Any]:
    """Answer each probe request shape so the whole pipeline runs without the network."""

    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    flt = query["filter"][0]
    if flt.startswith("ids.openalex:"):
        ids = flt.split(",", 1)[0].removeprefix("ids.openalex:").split("|")
        # Stand-in for the v3.1 query: works with an even numeric suffix are "retrieved".
        results = [{"id": f"https://openalex.org/{wid}"} for wid in ids if int(wid[1:]) % 2 == 0]
        body: dict[str, Any] = {"meta": {"count": len(results)}, "results": results}
    else:
        index = next(i for i, ts in enumerate(flp.TERM_SETS) if flp.term_query(ts.terms) in flt)
        ts = flp.TERM_SETS[index]
        count = 40 + 7 * index
        if "sample" in query:
            results = []
            for k in range(min(count, flp.SAMPLE_LIMIT)):
                language = ("en", None, ts.languages[0])[k % 3]
                results.append(
                    {
                        "id": f"https://openalex.org/W{1000 * (index + 1) + k}",
                        "display_name": f"Title {ts.id} {k}",
                        "language": language,
                        "publication_year": 2020 + k % 5,
                        "primary_location": {"source": {"display_name": "Venue"}},
                    }
                )
            body = {"meta": {"count": count}, "results": results}
        elif "group_by" in query:
            # OpenAlex keys are URLs, and works with no language are left out of the groups.
            groups = [
                {"key": f"https://openalex.org/languages/{ts.languages[0]}", "count": count - 3},
            ]
            body = {"meta": {"count": count}, "group_by": groups}
        else:
            body = {"meta": {"count": count}, "results": []}
    logger.record_openalex_response(
        method="GET",
        url=url,
        status_code=200,
        headers={"X-RateLimit-Credits-Used": "10"},
        body=body,
    )
    return body


def _no_network(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    raise AssertionError("the offline run must not call OpenAlex")


def _config() -> dict[str, Any]:
    return flp.load_query_config(ROOT / "config" / "queries.yml")


def _probe(tmp_path: Path, *, offline: bool) -> Any:
    return flp.Probe(
        offline=offline,
        force=False,
        cache_dir=tmp_path / "cache",
        usage_log=tmp_path / "usage.jsonl",
        budget_path=flp.DEFAULT_BUDGET,
    )


# --- committed file -------------------------------------------------------------------------


def test_language_label_takes_the_code_from_the_openalex_key() -> None:
    assert flp.language_label("https://openalex.org/languages/zh") == "zh"
    assert flp.language_label("en") == "en"
    assert flp.language_label(None) == "unlabelled"
    assert flp.language_label("https://openalex.org/languages/unknown") == "unlabelled"


def test_group_counts_reports_the_unlabelled_remainder() -> None:
    body = {
        "meta": {"count": 10},
        "group_by": [
            {"key": "https://openalex.org/languages/de", "count": 6},
            {"key": "https://openalex.org/languages/en", "count": 1},
        ],
    }
    assert flp._group_counts(body) == {"de": 6, "unlabelled": 3, "en": 1}
    with pytest.raises(flp.FetchError, match="more works"):
        flp._group_counts({"meta": {"count": 2}, "group_by": [{"key": "en", "count": 3}]})


def test_committed_file_passes_bqs_v1_validation(committed: dict[str, Any], rows: list) -> None:
    assert flp.validate_payload(committed, rows) == []


def test_schema_version_and_top_level_keys(committed: dict[str, Any]) -> None:
    assert committed["schema_version"] == "bqs-v1"
    assert set(committed) == flp.TOP_LEVEL_KEYS
    assert committed["query_version"] == "plastic-v3.1"
    assert datetime.fromisoformat(committed["generated_at"])


@pytest.mark.parametrize("set_id", [ts.id for ts in flp.TERM_SETS])
def test_every_term_set_has_the_fields(committed: dict[str, Any], set_id: str) -> None:
    record = next(r for r in committed["term_sets"] if r["id"] == set_id)
    assert set(record) == flp.SET_KEYS
    for item in record["sample"]:
        assert set(item) == flp.SAMPLE_KEYS


def test_sample_size_is_at_most_fifty(committed: dict[str, Any]) -> None:
    for record in committed["term_sets"]:
        assert record["sample_size"] == len(record["sample"])
        assert record["sample_size"] <= 50


def test_cost_is_under_the_acceptance_limit(committed: dict[str, Any]) -> None:
    cost = committed["cost"]
    assert cost["credits"] >= 0
    assert cost["usd"] < 0.10
    assert cost["usd"] <= float(flp.RUN_CAP_USD)


def test_caveats_cover_the_required_points(committed: dict[str, Any]) -> None:
    text = " ".join(committed["caveats"]).lower()
    for phrase in (
        "english titles",
        "céspedes et al. 2025",
        "language labels",
        "public-communication",
    ):
        assert phrase in text


def test_not_covered_names_the_gaps(committed: dict[str, Any]) -> None:
    text = " ".join(committed["not_covered"]).lower()
    for language in ("italian", "arabic", "turkish", "indonesian", "hindi", "dutch", "polish"):
        assert language in text


def test_no_abstract_keys_are_published(committed: dict[str, Any]) -> None:
    def keys(value: object) -> list[str]:
        if isinstance(value, dict):
            return [k for k in value if "abstract" in k.lower()] + [
                found for v in value.values() for found in keys(v)
            ]
        if isinstance(value, list):
            return [found for v in value for found in keys(v)]
        return []

    assert keys(committed) == []


def test_no_recall_wording_in_the_file(committed: dict[str, Any]) -> None:
    assert "recall" not in _text(committed)


def test_method_avoids_the_word_expert(committed: dict[str, Any]) -> None:
    assert "expert" not in committed["method"].lower()


def test_committed_term_strings_match_the_register(committed: dict[str, Any], rows: list) -> None:
    assert flp.vocabulary_problems(rows) == []
    assert [r["id"] for r in committed["term_sets"]] == [ts.id for ts in flp.TERM_SETS]


def test_italian_is_skipped_without_a_term_string(committed: dict[str, Any]) -> None:
    assert all("it" not in r["languages"] for r in committed["term_sets"])


# --- validation and register cross-check ---------------------------------------------------


def test_register_mismatch_is_reported(rows: list) -> None:
    changed = [dict(row) for row in rows]
    for row in changed:
        if row.get("term") == "微塑料":
            row["language"] = "en"
    problems = flp.vocabulary_problems(changed)
    assert any("微塑料" in problem and "registered as 'en'" in problem for problem in problems)

    missing = [row for row in rows if row.get("term") != "Nanoplastik"]
    problems = flp.vocabulary_problems(missing)
    assert any(
        "Nanoplastik" in problem and "not in the search vocabulary" in problem
        for problem in problems
    )


@pytest.mark.parametrize(
    "tamper",
    [
        lambda p: p["cost"].update({"usd": 0.2}),
        lambda p: p.update({"method": p["method"] + " Expert view."}),
        lambda p: p.update({"method": p["method"] + " Overlap is a recall figure."}),
        lambda p: p["term_sets"][0]["sample"][0].update({"abstract": "text"}),
        lambda p: p["term_sets"][0].update({"sample_size": 51}),
    ],
)
def test_validation_flags_tampered_files(committed: dict[str, Any], rows: list, tamper) -> None:
    payload = json.loads(json.dumps(committed))
    tamper(payload)
    assert flp.validate_payload(payload, rows)


# --- budget guard, cache and pipeline (no network) -----------------------------------------


def test_run_cap_refuses_the_next_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    probe = _probe(tmp_path, offline=False)
    _append_spend(tmp_path / "usage.jsonl", credits=895, cost_usd="0.0895")
    monkeypatch.setattr(flp, "_request_json", _no_network)
    with pytest.raises(flp.BudgetRefused, match="run cap"):
        probe.get("https://api.openalex.org/works?per_page=1", kind="count", set_id="t")


def test_spend_before_the_run_does_not_count_against_the_run_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _append_spend(tmp_path / "usage.jsonl", credits=5000, cost_usd="0.5")
    probe = _probe(tmp_path, offline=False)
    monkeypatch.setattr(flp, "_request_json", _ok_body({"meta": {"count": 0}, "results": []}))
    entry = probe.get("https://api.openalex.org/works?per_page=1", kind="count", set_id="t")
    assert entry is not None
    assert Decimal(entry["credits"]) == Decimal(10)


def test_offline_run_without_cache_fails_before_any_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(flp, "_request_json", _no_network)
    probe = _probe(tmp_path, offline=True)
    with pytest.raises(flp.CacheMiss):
        flp.build_payload(probe, _config(), generated_at="2026-11-22T00:00:00+00:00")


def test_overlap_request_is_split_when_the_url_is_too_long(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config()
    v31 = [flp.openalex_filter(config), *flp.type_filters(config)]
    ids = [f"W{2000000000 + i * 7919}" for i in range(50)]
    full = flp.works_url(
        {
            "filter": "ids.openalex:" + "|".join(ids) + "," + ",".join(v31),
            "per_page": 50,
            "select": "id",
        }
    )
    monkeypatch.setattr(flp, "MAX_URL_CHARS", len(full) - 1)
    seen: list[str] = []

    def _fake(url: str, *, logger: Any, attempts: int = 4, timeout: int = 60) -> dict[str, Any]:
        seen.append(url)
        return _fake_openalex(url, logger=logger)

    monkeypatch.setattr(flp, "_request_json", _fake)
    probe = _probe(tmp_path, offline=False)
    hits = flp._overlap_hits(probe, v31, ids, "t")
    assert len(seen) == 2
    assert all(len(url) < len(full) for url in seen)
    assert hits == {wid for wid in ids if int(wid[1:]) % 2 == 0}
    assert 0 < len(hits) < len(ids)


def test_build_then_offline_rebuild_reproduces_the_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list
) -> None:
    config = _config()
    monkeypatch.setattr(flp, "_request_json", _fake_openalex)
    live = flp.build_payload(
        _probe(tmp_path, offline=False), config, generated_at="2026-11-22T00:00:00+00:00"
    )
    assert flp.validate_payload(live, rows) == []
    assert live["cost"] == {"credits": 640, "usd": 0.064}
    assert all(r["language_label_counts"] is not None for r in live["term_sets"])

    monkeypatch.setattr(flp, "_request_json", _no_network)
    rebuilt = flp.build_payload(
        _probe(tmp_path, offline=True), config, generated_at="2026-11-23T00:00:00+00:00"
    )
    assert {k: v for k, v in rebuilt.items() if k != "generated_at"} == {
        k: v for k, v in live.items() if k != "generated_at"
    }


def test_optional_language_request_is_skipped_when_the_budget_is_short(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list
) -> None:
    # 48 essential requests cost USD 0.048; the 16 optional group_by requests would pass the cap.
    monkeypatch.setattr(flp, "RUN_CAP_USD", Decimal("0.0485"))
    monkeypatch.setattr(flp, "_request_json", _fake_openalex)
    payload = flp.build_payload(
        _probe(tmp_path, offline=False), _config(), generated_at="2026-11-22T00:00:00+00:00"
    )
    assert all(r["language_label_counts"] is None for r in payload["term_sets"])
    assert all(r["sample_size"] == min(r["count"], 50) for r in payload["term_sets"])
    assert payload["cost"] == {"credits": 480, "usd": 0.048}
    assert flp.validate_payload(payload, rows) == []
