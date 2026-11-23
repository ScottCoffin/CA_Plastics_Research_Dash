"""PubMed review-string replay (BQ-S10). Offline: every request goes to a fake.

An autouse fixture makes ``urllib.request.urlopen`` and the OpenAlex request path fail, so a stray
live call fails the test rather than spending credits or calling NCBI.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from atlas.qc.pubmed import EUtilsError, parse_day
from atlas.query import load_query_config

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "replay_review_strings.py"
FETCH_TREND = ROOT / "scripts" / "fetch_trend_global.py"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


replay = _load("replay_review_strings", SCRIPT)
fetch_trend = _load("fetch_trend_global_for_bqs10", FETCH_TREND)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network call attempted")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(replay, "_request_json", refuse)


def _header(review_id: str, search_date: str = "2026-03-05", published: int = 10) -> str:
    keys = {
        "review_id": review_id,
        "citation": "Test review (2026)",
        "source": "synthetic fixture",
        "licence": "not applicable (synthetic)",
        "search_date": search_date,
        "search_date_source": "synthetic",
        "published_count": str(published),
        "published_count_source": "synthetic",
        "included_study_list": "not applicable",
        "transcription": "synthetic",
    }
    return "".join(f"# {key}: {value}\n" for key, value in keys.items()) + "# string:\n"


def _write_review(directory: Path, review_id: str, body: str, **kwargs: Any) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{review_id}.txt").write_text(
        _header(review_id, **kwargs) + body + "\n", encoding="utf-8"
    )


# --- Duplicate check ----------------------------------------------------------------------------


def test_term_key_normalises_case_quotes_and_whitespace() -> None:
    reference = replay.term_key("microplastic*[tiab]")
    assert replay.term_key('"Microplastic*"[tiab]') == reference
    assert replay.term_key("MICROPLASTIC*[TIAB]") == reference
    assert replay.term_key("micro   plastic*[tiab]") == replay.term_key("micro plastic*[tiab]")
    assert replay.term_key("micro plastic* [tiab]") == replay.term_key("micro plastic*[tiab]")
    assert replay.term_key('("plastic particle*"[tiab]') == replay.term_key(
        "plastic particle*[tiab]"
    )


def test_field_tags_keep_terms_apart() -> None:
    assert replay.term_key("microplastics[MeSH Terms]") != replay.term_key(
        "microplastics[All Fields]"
    )


def test_repeated_terms_reported_with_raw_forms_and_deduplicated() -> None:
    operands = [
        "microplastic*[tiab]",
        '"Microplastic*"[tiab]',
        "nanoplastic*[tiab]",
        "microplastic*  [tiab]",
    ]
    repeated = replay.repeated_terms(operands)
    assert len(repeated) == 1
    assert repeated[0]["times"] == 3
    assert repeated[0]["raw_forms"] == sorted(
        {"microplastic*[tiab]", '"Microplastic*"[tiab]', "microplastic*  [tiab]"}
    )
    assert replay.dedupe(operands) == ["microplastic*[tiab]", "nanoplastic*[tiab]"]


def test_same_term_in_different_blocks_is_not_a_duplicate() -> None:
    report = replay.structure_report(
        replay.analyse("(a[tiab] OR b[tiab]) AND (a[tiab] OR c[tiab])"), None
    )
    assert report["duplicates_found"] == 0


def test_structure_report_counts_raw_and_deduplicated_operands() -> None:
    query = (
        '(microplastic*[tiab] OR "Microplastic*"[tiab] OR gut[tiab]) '
        "AND (toxic*[tiab] OR toxic*[tiab]) NOT (review[Publication Type])"
    )
    report = replay.structure_report(replay.analyse(query), None)
    assert report["and_blocks"] == 2
    assert report["not_clause"] is True
    assert report["operands_raw_total"] == 5
    assert report["operands_deduplicated_total"] == 3
    assert report["duplicates_found"] == 2


def test_canonical_query_dedupes_and_keeps_not_last() -> None:
    structure = replay.analyse("(a[tiab] OR A[tiab] OR b[tiab]) AND (c[tiab]) NOT (d[tiab])")
    assert replay.canonical_query(structure) == (
        "((a[tiab] OR b[tiab]) AND (c[tiab])) NOT (d[tiab])"
    )


# --- Shipped review strings ---------------------------------------------------------------------


def test_ozkan_string_has_three_blocks_and_no_duplicates() -> None:
    review = replay.load_review("ozkan_vardar_2026")
    assert review.query.startswith("(microplastic*[tiab] OR micro-plastic*[tiab]")
    assert "#" not in review.query
    structure = replay.analyse(review.query)
    assert replay.local_parse_error(review.query) is None
    assert [len(ops) for ops in structure.operands] == [9, 7, 7]
    assert structure.exclusion is None
    report = replay.structure_report(structure, None)
    assert report["operands_raw_total"] == 23
    assert report["duplicates_found"] == 0


def test_tran_string_is_unbalanced_as_published_and_repair_drops_one_parenthesis() -> None:
    review = replay.load_review("tran_2026")
    assert review.query.count("(") == 7
    assert review.query.count(")") == 8
    error = replay.local_parse_error(review.query)
    assert error is not None and error.startswith("unbalanced ')'")

    repaired, repairs = replay.balance_repair(review.query)
    assert len(repairs) == 1
    assert repairs[0]["character"] == ")"
    assert len(repaired) == len(review.query) - 1
    assert repaired.count("(") == repaired.count(")")

    structure = replay.analyse(review.query)
    assert [len(ops) for ops in structure.operands] == [9, 6, 6]
    assert structure.exclusion is not None
    assert "review[Publication Type]" in structure.exclusion
    assert replay.structure_report(structure, error)["duplicates_found"] == 0


def test_balance_repair_leaves_balanced_text_alone_and_refuses_open_parenthesis() -> None:
    assert replay.balance_repair("(a OR b) NOT (c)") == ("(a OR b) NOT (c)", [])
    with pytest.raises(replay.ReplayError, match="unmatched opening"):
        replay.balance_repair("((a OR b)")
    with pytest.raises(replay.ReplayError, match="unterminated"):
        replay.balance_repair('(a OR "b)')


def test_load_review_reads_header_and_body_only(tmp_path: Path) -> None:
    _write_review(tmp_path, "fixture_2026", "(gut[tiab] OR colon[tiab])")
    review = replay.load_review("fixture_2026", tmp_path)
    assert review.header["published_count"] == "10"
    assert review.query == "(gut[tiab] OR colon[tiab])"


def test_load_review_rejects_unknown_or_mismatched_files(tmp_path: Path) -> None:
    with pytest.raises(replay.ReplayError, match="no review string file"):
        replay.load_review("missing_2026", tmp_path)
    with pytest.raises(replay.ReplayError, match="lowercase"):
        replay.load_review("Bad-Name", tmp_path)
    _write_review(tmp_path, "other_2026", "(gut[tiab])")
    (tmp_path / "wrong_2026.txt").write_text(
        (tmp_path / "other_2026.txt").read_text(encoding="utf-8"), encoding="utf-8"
    )
    with pytest.raises(replay.ReplayError, match="header needs review_id"):
        replay.load_review("wrong_2026", tmp_path)


# --- Dry run (no network) -----------------------------------------------------------------------


@pytest.mark.parametrize("review_id", ["ozkan_vardar_2026", "tran_2026"])
def test_dry_run_makes_no_network_call(review_id: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert replay.main(["--review", review_id]) == 0
    out = capsys.readouterr().out
    assert "no network call made" in out
    assert "DUPLICATE CHECK" in out


def test_dry_run_reports_duplicates_from_a_review_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(replay, "REVIEW_DIR", tmp_path)
    _write_review(tmp_path, "dup_2026", '(gut[tiab] OR "Gut"[tiab]) AND (toxic*[tiab])')
    assert replay.main(["--review", "dup_2026"]) == 0
    out = capsys.readouterr().out
    assert "DUPLICATE CHECK: repeated terms found" in out
    assert "block 1: 2 x" in out


def test_unavailable_review_is_not_replayed(capsys: pytest.CaptureFixture[str]) -> None:
    assert replay.main(["--review", "ortiz_balsero_2026"]) == 2
    assert "not available" in capsys.readouterr().out


def test_missing_review_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert replay.main(["--review", "nothing_2026"]) == 1
    assert "no review string file" in capsys.readouterr().err


# --- Sampling, Wilson and overlap math ----------------------------------------------------------


def test_sample_is_deterministic_and_independent_of_input_order() -> None:
    pmids = [str(value) for value in range(1000, 1600)]
    first = replay.sample_pmids(pmids)
    assert first == replay.sample_pmids(list(reversed(pmids)))
    assert first == replay.sample_pmids(pmids + pmids[:50])
    assert len(first) == replay.SAMPLE_SIZE
    assert set(first) <= set(pmids)
    assert first != sorted(pmids, key=int)[: replay.SAMPLE_SIZE]


def test_sample_changes_with_seed_and_returns_all_when_small() -> None:
    pmids = [str(value) for value in range(1000, 1600)]
    assert replay.sample_pmids(pmids, seed="other-seed") != replay.sample_pmids(pmids)
    small = pmids[:50]
    assert sorted(replay.sample_pmids(small), key=int) == small


def test_wilson_interval_known_values() -> None:
    low, high = replay.wilson_interval(0, 10)
    assert low == 0.0
    assert high == pytest.approx(0.2775, abs=1e-3)
    low, high = replay.wilson_interval(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-3)
    assert high == pytest.approx(0.7634, abs=1e-3)
    low, high = replay.wilson_interval(200, 200)
    assert low == pytest.approx(0.9812, abs=1e-3)
    assert high == pytest.approx(1.0)
    assert replay.wilson_interval(0, 0) is None
    with pytest.raises(ValueError):
        replay.wilson_interval(11, 10)


def test_overlap_summary_shares_and_intervals() -> None:
    summary = replay.overlap_summary(200, 150, 120)
    assert summary["in_openalex"]["count"] == 150
    assert summary["in_openalex"]["share"] == 0.75
    assert summary["v31_retrieved"]["share"] == 0.6
    assert summary["v31_share_of_in_openalex"] == 0.8
    assert summary["v31_retrieved"]["wilson95"][0] < 0.6 < summary["v31_retrieved"]["wilson95"][1]
    empty = replay.overlap_summary(0, 0, 0)
    assert empty["in_openalex"]["share"] is None
    assert empty["v31_share_of_in_openalex"] is None


def test_pmid_is_read_from_openalex_ids() -> None:
    assert replay._work_pmid({"ids": {"pmid": "https://pubmed.ncbi.nlm.nih.gov/12345"}}) == "12345"
    assert replay._work_pmid({"ids": {"pmid": None}}) is None
    assert replay._work_pmid({}) is None


# --- Counting and OpenAlex (fakes) --------------------------------------------------------------


class FakeClient:
    """Stands in for EUtilsClient: count and pmids for a fixed PMID list."""

    def __init__(
        self, pmids: list[str], *, fail_on: str | None = None, entry_count: int | None = None
    ) -> None:
        self._pmids = pmids
        self._fail_on = fail_on
        self._entry_count = len(pmids) if entry_count is None else entry_count
        self.counts: list[tuple[str, str, str]] = []
        self.entrez_calls: list[dict[str, Any]] = []

    def _get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        assert endpoint == "esearch"
        self.entrez_calls.append(params)
        return {"esearchresult": {"count": str(self._entry_count)}}

    def count(self, term: str, first: str, last: str) -> tuple[int, str]:
        self.counts.append((term, first, last))
        if self._fail_on is not None and term == self._fail_on:
            raise EUtilsError("ESearch rejected the query")
        if last == replay.WINDOW_END:
            return len(self._pmids), "fake translation"
        return 500, "fake translation"

    def pmids(self, term: str, first: str, last: str, retmax: int) -> list[str]:
        assert len(self._pmids) <= retmax
        return list(self._pmids)


def _fake_openalex(in_openalex: set[str], v31: set[str]) -> tuple[Any, list[str]]:
    seen_labels: list[str] = []

    def get(url: str, label: str) -> dict[str, Any]:
        seen_labels.append(label)
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        filter_value = query["filter"][0]
        pmids = re.findall(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", filter_value)
        allowed = v31 if "title_and_abstract.search" in filter_value else in_openalex
        results = [
            {"id": f"https://openalex.org/W{pmid}", "ids": {"pmid": f"{replay.PUBMED_URL}{pmid}"}}
            for pmid in pmids
            if pmid in allowed
        ]
        return {"meta": {"count": len(results)}, "results": results}

    return get, seen_labels


def test_openalex_checks_batch_by_fifty_and_apply_v31_filters() -> None:
    sample = [str(value) for value in range(5000, 5200)]
    config = load_query_config(replay.V31_CONFIG)
    get, labels = _fake_openalex(set(sample), set(sample[::2]))
    in_openalex = replay.openalex_hits(get, sample, [], "exists")
    retrieved = replay.openalex_hits(get, sample, replay.v31_filter_parts(config), "v31")
    assert in_openalex == set(sample)
    assert retrieved == set(sample[::2])
    assert len(labels) == 8  # 200 PMIDs in batches of 50, twice


def test_v31_filter_matches_fetch_trend_global_build_url() -> None:
    config = load_query_config(replay.V31_CONFIG)
    assert config["version"] == replay.V31_VERSION
    url = fetch_trend.build_url(config)
    filter_value = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["filter"][0]
    assert filter_value == ",".join(replay.v31_filter_parts(config))


def test_task_credit_cap_refuses_before_any_request(tmp_path: Path) -> None:
    usage = tmp_path / "usage.jsonl"
    usage.write_text(
        json.dumps(
            {
                "record_type": "request",
                "source": "openalex",
                "run_id": "bq-s10-x-1",
                "credits": 115.0,
                "url": "https://api.openalex.org/works",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    other = {
        "record_type": "request",
        "source": "openalex",
        "run_id": "trend-global-1",
        "credits": 500.0,
        "url": "https://api.openalex.org/works",
    }
    usage.write_text(usage.read_text(encoding="utf-8") + json.dumps(other) + "\n", encoding="utf-8")
    assert replay.task_credits_logged(usage) == Decimal("115")
    budget = replay.OpenAlexBudget(
        max_cost_usd=Decimal("1"),
        max_credits=Decimal(10000),
        cost_per_credit_usd=Decimal("0.0001"),
        reserve_cost_usd=Decimal("0.001"),
        reserve_credits=Decimal(10),
    )
    guard = replay.OpenAlexGuard(usage, budget=budget)
    with pytest.raises(replay.ReplayError, match="credit cap"):
        guard("https://api.openalex.org/works?filter=x", "v31-01")
    assert guard.calls == 0


def test_retrieve_pmids_splits_by_date_above_the_cap() -> None:
    first_day = date(2000, 1, 1)
    per_day = {
        first_day + timedelta(days=offset): [
            str(100000 + 300 * offset + index) for index in range(300)
        ]
        for offset in range(40)
    }

    class DateClient:
        def count(self, term: str, first: str, last: str) -> tuple[int, str]:
            return sum(len(ids) for day, ids in self._window(first, last)), "t"

        def pmids(self, term: str, first: str, last: str, retmax: int) -> list[str]:
            assert retmax == replay.ESEARCH_MAX
            ids = [pmid for _, day_ids in self._window(first, last) for pmid in day_ids]
            assert len(ids) <= retmax
            return ids

        @staticmethod
        def _window(first: str, last: str) -> list[tuple[date, list[str]]]:
            low, high = parse_day(first), parse_day(last)
            return [(day, ids) for day, ids in per_day.items() if low <= day <= high]

    everything = {pmid for ids in per_day.values() for pmid in ids}
    total = len(everything)
    assert total > replay.ESEARCH_MAX
    found = replay.retrieve_pmids(DateClient(), "x", "2000/01/01", "2000/02/09", total)
    assert set(found) == everything
    assert len(found) == total


def _entry(review_id: str, client: FakeClient, openalex: Any) -> dict[str, Any]:
    review = replay.load_review(review_id)
    return replay.replay_review(review, client=client, openalex=openalex, today=date(2026, 11, 22))


def test_replay_entry_for_ozkan_with_fake_pubmed_and_openalex() -> None:
    pmids = [str(value) for value in range(20000000, 20001411)]
    sample = set(replay.sample_pmids(pmids))
    get, _ = _fake_openalex(sample, {pmid for pmid in sample if int(pmid) % 2 == 0})
    entry = _entry("ozkan_vardar_2026", FakeClient(pmids), get)
    assert entry["published"]["pubmed_count"] == 1089
    assert entry["replay"]["as_published_count"] == 1411
    assert entry["replay"]["count_query"] == "as_published"
    assert len(entry["replay"]["blocks"]) == 3
    assert entry["replay"]["deduplicated"] is None
    assert entry["replay"]["count_to_search_date"]["window"].endswith("2026/03/05")
    assert entry["replay"]["entry_date_to_search_date"]["count"] == 1411
    assert entry["sample"]["sample_drawn"] == 200
    assert entry["openalex"]["in_openalex"]["count"] == 200
    assert entry["openalex"]["v31_retrieved"]["count"] == sum(
        1 for pmid in sample if int(pmid) % 2 == 0
    )


def test_replay_entry_for_tran_counts_the_positive_part_and_records_the_repair() -> None:
    pmids = [str(value) for value in range(30000000, 30002284)]
    sample = set(replay.sample_pmids(pmids))
    get, _ = _fake_openalex(sample, set())
    entry = _entry("tran_2026", FakeClient(pmids), get)
    assert entry["published"]["pubmed_count"] == 2199
    assert entry["replay"]["positive_only_count"] is not None
    assert len(entry["structure"]["repairs"]) == 1
    assert entry["structure"]["local_parse_as_published"].startswith("unbalanced")
    assert entry["openalex"]["v31_retrieved"]["count"] == 0
    assert entry["openalex"]["v31_share_of_in_openalex"] == 0.0


def test_replay_falls_back_to_repaired_string_only_when_pubmed_rejects_the_original() -> None:
    review = replay.load_review("tran_2026")
    repaired = replay.balance_repair(review.query)[0]
    pmids = [str(value) for value in range(30000000, 30000100)]
    sample = set(replay.sample_pmids(pmids))
    get, _ = _fake_openalex(sample, sample)
    entry = _entry("tran_2026", FakeClient(pmids, fail_on=review.query), get)
    assert entry["replay"]["count_query"] == "repaired"
    assert "rejected" in entry["replay"]["as_published_error"]
    assert repaired != review.query


def test_entry_date_count_uses_entrez_dates_up_to_the_search_date() -> None:
    client = FakeClient(["1", "2"], entry_count=1800)
    count = replay.entry_date_count(client, "gut[tiab]", date(2024, 12, 26))
    assert count == 1800
    assert client.entrez_calls[0]["datetype"] == "edat"
    assert client.entrez_calls[0]["maxdate"] == "2024/12/26"
    assert client.entrez_calls[0]["retmax"] == 0


def test_entry_date_addition_labels_the_publication_date_count_and_keeps_the_rest() -> None:
    pmids = [str(value) for value in range(40000000, 40000010)]
    review = replay.load_review("ozkan_vardar_2026")
    legacy = {
        "published": {"pubmed_count": 1089, "search_date": "2026-03-05"},
        "replay": {
            "count_query": "as_published",
            "count_to_search_date": {"window": "1800/01/01..2026/03/05", "count": 1128},
        },
    }
    updated = replay.add_entry_date_counts(
        legacy, review, FakeClient(pmids, entry_count=1100), date(2026, 11, 22)
    )
    assert updated["replay"]["count_to_search_date"]["datetype"] == "pdat"
    assert updated["replay"]["count_to_search_date"]["count"] == 1128
    edat = updated["replay"]["entry_date_to_search_date"]
    assert edat["count"] == 1100 and edat["datetype"] == "edat"
    assert "entry_date_to_search_date" not in legacy["replay"]  # input is not changed


def test_replay_counts_the_deduplicated_string_when_terms_repeat(tmp_path: Path) -> None:
    _write_review(tmp_path, "dup_2026", '(gut[tiab] OR "Gut"[tiab]) AND (toxic*[tiab])')
    review = replay.load_review("dup_2026", tmp_path)
    pmids = [str(value) for value in range(50000000, 50000040)]
    sample = set(replay.sample_pmids(pmids))
    get, _ = _fake_openalex(sample, sample)
    entry = replay.replay_review(
        review, client=FakeClient(pmids), openalex=get, today=date(2026, 11, 22)
    )
    assert entry["structure"]["duplicates_found"] == 1
    assert entry["replay"]["deduplicated"] == {"count": 40, "equal_to_string_count": True}


def test_openalex_guard_returns_the_body_and_counts_the_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def fake_request(url: str, *, logger: object, attempts: int) -> dict[str, Any]:
        calls.append(url)
        return {"meta": {"count": 0}, "results": []}

    monkeypatch.setattr(replay, "_request_json", fake_request)
    budget = replay.OpenAlexBudget(
        max_cost_usd=Decimal("1"),
        max_credits=Decimal(10000),
        cost_per_credit_usd=Decimal("0.0001"),
        reserve_cost_usd=Decimal("0.001"),
        reserve_credits=Decimal(10),
    )
    guard = replay.OpenAlexGuard(tmp_path / "usage.jsonl", budget=budget)
    body = guard("https://api.openalex.org/works?filter=x", "exists-01")
    assert body == {"meta": {"count": 0}, "results": []}
    assert guard.calls == 1
    assert calls == ["https://api.openalex.org/works?filter=x"]


def test_write_result_merges_reviews_and_refuses_contact_values(tmp_path: Path) -> None:
    out = tmp_path / "bq_s10_replay.json"
    replay.write_result(out, "first_2026", {"status": "replayed"}, generated_utc="t", secrets=[])
    replay.write_result(out, "second_2026", {"status": "replayed"}, generated_utc="t", secrets=[])
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert set(doc["reviews"]) == {"first_2026", "second_2026", "ortiz_balsero_2026"}
    assert doc["reviews"]["ortiz_balsero_2026"]["status"] == "not replayed"
    assert doc["seed"] == "20261122"
    with pytest.raises(replay.ReplayError, match="contact value"):
        replay.write_result(
            out,
            "third_2026",
            {"note": "a@example.org"},
            generated_utc="t",
            secrets=["a@example.org"],
        )
    assert "third_2026" not in json.loads(out.read_text(encoding="utf-8"))["reviews"]
