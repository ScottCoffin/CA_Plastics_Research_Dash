"""PubMed coverage library and CLI (BQ-S9 part A). Offline: every request goes to a fake opener.

An autouse fixture replaces ``urllib.request.urlopen`` so a stray live call fails the test.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from atlas.qc.pubmed import (
    ROW_FIELDS,
    DatePartition,
    EUtilsClient,
    EUtilsError,
    PartitionError,
    QuerySyntaxError,
    affiliation_clause,
    build_terms,
    coverage,
    partition_dates,
    read_query,
    read_query_file,
    run_reference_set,
    split_include_chunks,
    split_top_level_or,
)

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "qc_pubmed_coverage.py"
R1 = ROOT / "config" / "pubmed" / "r1_include.txt"
R2 = ROOT / "config" / "pubmed" / "r2_include.txt"
CONTACT = "tester@example.invalid"
KEY = "not-a-real-key-123"

MANIFEST_KEYS = {
    "schema",
    "reference_set",
    "affiliation",
    "query_text",
    "query_hash",
    "query_translation",
    "run_timestamp",
    "script_version",
    "parameters",
    "chunks",
    "total_unique_pmids",
}
CHUNK_KEYS = {"chunk_id", "query_text", "query_translation", "count", "partitions"}
PARTITION_KEYS = {"start", "end", "count", "retrieved"}
PARAMETER_KEYS = {
    "start",
    "end",
    "cap",
    "margin",
    "threshold",
    "rps",
    "tool",
    "api_key_used",
    "cache_used",
}


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network call attempted in an offline test")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)


class FakeClock:
    """Records sleeps and advances a fake clock by the same amount, so no real waiting happens."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self) -> float:
        return self.now


class ScriptedOpener:
    """Returns scripted replies in order. An exception instance is raised instead of returned."""

    def __init__(self, *replies: bytes | BaseException) -> None:
        self.replies = list(replies)
        self.urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        reply = self.replies.pop(0)
        if isinstance(reply, BaseException):
            raise reply
        return reply


class FakePubMed:
    """In-memory PubMed. ESearch counts and lists PMIDs by pdat window; ESummary gives DOI and year.

    The term is recorded in the query translation but not interpreted, so every chunk sees the
    same records.
    """

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records
        self.urls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.urls.append(url)
        parts = urllib.parse.urlsplit(url)
        query = dict(urllib.parse.parse_qsl(parts.query))
        if parts.path.endswith("/esearch.fcgi"):
            low, high = query["mindate"], query["maxdate"]
            hits = [r["pmid"] for r in self.records if low <= r["date"] <= high]
            body: dict[str, Any] = {
                "esearchresult": {
                    "count": str(len(hits)),
                    "querytranslation": f"translated({query['term']})",
                    "idlist": hits[: int(query["retmax"])],
                }
            }
        else:
            by_id = {r["pmid"]: r for r in self.records}
            uids = query["id"].split(",")
            result: dict[str, Any] = {"uids": uids}
            for pmid in uids:
                record = by_id[pmid]
                articleids = [{"idtype": "pubmed", "value": pmid}]
                if record.get("doi"):
                    articleids.append({"idtype": "doi", "value": record["doi"]})
                result[pmid] = {
                    "uid": pmid,
                    "pubdate": f"{record['year']} Jan",
                    "sortpubdate": f"{record['year']}/01/01 00:00",
                    "articleids": articleids,
                }
            body = {"result": result}
        return json.dumps(body).encode("utf-8")


def _count_reply(count: int, translation: str = "t") -> bytes:
    body = {"esearchresult": {"count": str(count), "querytranslation": translation}}
    return json.dumps(body).encode("utf-8")


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.invalid/", code, "status", None, None)


def make_client(opener: Any, clock: FakeClock | None = None, **kwargs: Any) -> EUtilsClient:
    fake_clock = clock or FakeClock()
    return EUtilsClient(opener=opener, sleep=fake_clock.sleep, clock=fake_clock.clock, **kwargs)


def _day_counts(per_day: dict[str, int]) -> Any:
    def count_fn(start: str, end: str) -> int:
        return sum(n for day, n in per_day.items() if start <= day <= end)

    return count_fn


def _window_records() -> list[dict[str, Any]]:
    """120 records, four per day across January 2020; every second record has a DOI."""
    records = []
    for i in range(120):
        records.append(
            {
                "pmid": str(1000 + i),
                "date": f"2020/01/{1 + i // 4:02d}",
                "year": 2020,
                "doi": f"10.1000/fake.{i}" if i % 2 == 0 else None,
            }
        )
    return records


def _load_cli() -> Any:
    spec = importlib.util.spec_from_file_location("qc_pubmed_coverage", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- Query splitting ----------------------------------------------------------------------------


def test_split_keeps_nested_groups_intact() -> None:
    query = "(a OR (b OR (c OR d))) OR e"
    assert split_top_level_or(query) == ["(a OR (b OR (c OR d)))", "e"]


def test_split_ignores_or_inside_double_quotes() -> None:
    assert split_top_level_or('"plastic OR polymer"[tiab] OR debris') == [
        '"plastic OR polymer"[tiab]',
        "debris",
    ]


def test_split_accepts_lowercase_and_mixed_case_or() -> None:
    assert split_top_level_or("microplastic or nanoplastic Or debris") == [
        "microplastic",
        "nanoplastic",
        "debris",
    ]


def test_escaped_quote_does_not_close_a_phrase_and_escaped_paren_is_literal() -> None:
    assert split_top_level_or(r'"a \" OR b"[tiab] OR c') == [r'"a \" OR b"[tiab]', "c"]
    assert split_top_level_or(r"a\(b OR c") == [r"a\(b", "c"]


def test_or_inside_a_word_is_not_an_operator() -> None:
    assert split_top_level_or("ORDER colorOR") == ["ORDER colorOR"]
    assert split_top_level_or("color OR colour OR ORDER") == ["color", "colour", "ORDER"]


@pytest.mark.parametrize(
    "query",
    [
        "(A OR B",  # unbalanced: missing close
        "A OR B)",  # unbalanced: extra close
        '"A OR B',  # unterminated quote
        "A\\",  # dangling escape
        "A OR",  # empty operand at the end
        "OR B",  # empty operand at the start
        "A OR OR B",  # empty operand in the middle
        "   ",  # empty query
    ],
)
def test_splitter_rejects_unsafe_text(query: str) -> None:
    with pytest.raises(QuerySyntaxError):
        split_top_level_or(query)


def test_chunks_unwrap_one_outer_group_only() -> None:
    assert split_include_chunks('("a"[tiab] OR "b"[tiab])') == ['"a"[tiab]', '"b"[tiab]']
    assert split_include_chunks('(("a" OR "b") OR c)') == ['("a" OR "b")', "c"]
    assert split_include_chunks("(a) AND (b)") == ["(a) AND (b)"]


def test_build_terms_adds_exclusion_to_each_chunk_and_affiliation_once() -> None:
    whole, chunks = build_terms('("a"[tiab] OR "b"[tiab])', "retracted[pt]", "California")
    assert len(chunks) == 2
    assert all(term.endswith("AND California[ad]") for term in chunks)
    assert all("NOT (retracted[pt])" in term for term in chunks)
    assert whole.count("California[ad]") == 1


def test_affiliation_clause_quotes_multiword_names_and_rejects_syntax() -> None:
    assert affiliation_clause(None) is None
    assert affiliation_clause("California") == "California[ad]"
    assert affiliation_clause("University of California") == '"University of California"[ad]'
    with pytest.raises(ValueError):
        affiliation_clause("Cal(ifornia")


def test_read_query_normalises_whitespace_comments_and_exclusion(tmp_path: Path) -> None:
    include = tmp_path / "include.txt"
    include.write_text("# note\n(a  OR\n\n b)\n", encoding="utf-8")
    exclude = tmp_path / "exclude.txt"
    exclude.write_text("  retracted[pt]\n", encoding="utf-8")
    assert read_query(include) == "(a OR b)"
    assert read_query(include, exclude) == "((a OR b)) NOT (retracted[pt])"


def test_empty_exclude_file_means_no_exclusion(tmp_path: Path) -> None:
    include = tmp_path / "include.txt"
    include.write_text("a", encoding="utf-8")
    exclude = tmp_path / "exclude.txt"
    exclude.write_text("# nothing excluded yet\n", encoding="utf-8")
    assert read_query(include, exclude) == "a"


def test_read_query_rejects_unbalanced_include(tmp_path: Path) -> None:
    include = tmp_path / "include.txt"
    include.write_text("(a OR b", encoding="utf-8")
    with pytest.raises(QuerySyntaxError, match="include"):
        read_query(include)


def test_r2_include_is_the_core_terms_as_tiab_phrases() -> None:
    core = yaml.safe_load((ROOT / "config" / "queries.yml").read_text(encoding="utf-8"))
    terms = core["core_terms"]
    assert split_include_chunks(read_query_file(R2)) == [f'"{term}"[tiab]' for term in terms]


def test_r1_include_is_the_microplastics_mesh_term() -> None:
    assert read_query_file(R1) == '"Microplastics"[MeSH Terms]'


# --- Date bisection -----------------------------------------------------------------------------


def test_partition_bisects_until_each_window_is_under_threshold() -> None:
    per_day = {f"2020/01/{day:02d}": 10 for day in range(1, 32)}
    partitions = partition_dates(
        _day_counts(per_day), "2020/01/01", "2020/01/31", cap=100, margin=10
    )
    assert partitions == [
        DatePartition("2020/01/01", "2020/01/08", 80),
        DatePartition("2020/01/09", "2020/01/16", 80),
        DatePartition("2020/01/17", "2020/01/24", 80),
        DatePartition("2020/01/25", "2020/01/31", 70),
    ]


def test_partition_keeps_a_window_under_threshold_without_splitting() -> None:
    calls: list[tuple[str, str]] = []

    def count_fn(start: str, end: str) -> int:
        calls.append((start, end))
        return 5

    partitions = partition_dates(count_fn, "2020/01/01", "2020/12/31", cap=100, margin=10)
    assert partitions == [DatePartition("2020/01/01", "2020/12/31", 5)]
    assert calls == [("2020/01/01", "2020/12/31")]


def test_single_day_above_cap_raises_partition_error() -> None:
    with pytest.raises(PartitionError, match="2020/03/05"):
        partition_dates(
            _day_counts({"2020/03/05": 500}), "2020/03/01", "2020/03/31", cap=100, margin=10
        )


def test_single_day_between_threshold_and_cap_is_kept() -> None:
    partitions = partition_dates(
        _day_counts({"2020/03/05": 95}), "2020/03/05", "2020/03/05", cap=100, margin=10
    )
    assert partitions == [DatePartition("2020/03/05", "2020/03/05", 95)]


@pytest.mark.parametrize("cap, margin", [(0, 0), (10_001, 0), (100, 100), (100, -1)])
def test_invalid_cap_or_margin_is_rejected(cap: int, margin: int) -> None:
    with pytest.raises(ValueError):
        partition_dates(lambda s, e: 0, "2020/01/01", "2020/01/02", cap=cap, margin=margin)


def test_start_after_end_is_rejected() -> None:
    with pytest.raises(ValueError):
        partition_dates(lambda s, e: 0, "2020/02/01", "2020/01/01")


# --- Client: retries, rate limit, contact parameters, cache -------------------------------------


def test_429_then_success_retries_once_with_backoff() -> None:
    clock = FakeClock()
    opener = ScriptedOpener(_http_error(429), _count_reply(7, "t"))
    client = make_client(opener, clock)
    assert client.count("x", "2020/01/01", "2020/01/31") == (7, "t")
    assert len(opener.urls) == 2
    assert clock.sleeps == [1.0]


def test_backoff_doubles_and_gives_up_after_max_retries() -> None:
    clock = FakeClock()
    opener = ScriptedOpener(
        _http_error(503), urllib.error.URLError("reset"), _http_error(429), _http_error(500)
    )
    client = make_client(opener, clock, max_retries=3)
    with pytest.raises(EUtilsError, match="4 attempts"):
        client.count("x", "2020/01/01", "2020/01/31")
    assert len(opener.urls) == 4
    assert clock.sleeps == [1.0, 2.0, 4.0]


def test_client_error_fails_without_retry() -> None:
    opener = ScriptedOpener(_http_error(400))
    client = make_client(opener)
    with pytest.raises(EUtilsError, match="HTTP 400"):
        client.count("x", "2020/01/01", "2020/01/31")
    assert len(opener.urls) == 1


def test_rate_limit_is_capped_by_key_setting() -> None:
    with pytest.raises(ValueError):
        EUtilsClient(opener=ScriptedOpener(), rps=4)
    with pytest.raises(ValueError):
        EUtilsClient(opener=ScriptedOpener(), rps=0)
    EUtilsClient(opener=ScriptedOpener(), rps=10, api_key=KEY)


def test_contact_email_is_sent_only_when_supplied() -> None:
    with_email = ScriptedOpener(_count_reply(1))
    make_client(with_email, email=CONTACT).count("x", "2020/01/01", "2020/01/01")
    assert f"email={urllib.parse.quote_plus(CONTACT)}" in with_email.urls[0]

    without = ScriptedOpener(_count_reply(1))
    make_client(without).count("x", "2020/01/01", "2020/01/01")
    assert "email=" not in without.urls[0]
    assert "api_key=" not in without.urls[0]
    assert "tool=ca-plastics-research-atlas" in without.urls[0]


def test_count_cache_reuses_the_stored_result(tmp_path: Path) -> None:
    opener = ScriptedOpener(_count_reply(42, "cached"))
    client = make_client(opener, cache_dir=tmp_path / "cache")
    assert client.count("term", "2020/01/01", "2020/01/31") == (42, "cached")
    assert client.count("term", "2020/01/01", "2020/01/31") == (42, "cached")
    assert len(opener.urls) == 1


def test_doi_years_reads_doi_and_year_and_marks_missing_records() -> None:
    payload = {
        "result": {
            "uids": ["1", "2"],
            "1": {
                "pubdate": "2019 Mar 4",
                "articleids": [
                    {"idtype": "pubmed", "value": "1"},
                    {"idtype": "doi", "value": "10.1/ABC"},
                ],
            },
        }
    }
    client = make_client(ScriptedOpener(json.dumps(payload).encode("utf-8")))
    assert client.doi_years(["1", "2"]) == {"1": ("10.1/ABC", 2019), "2": (None, None)}


# --- Reference-set run and manifest -------------------------------------------------------------


def test_run_partitions_chunks_unions_pmids_and_builds_a_complete_manifest(
    tmp_path: Path,
) -> None:
    include = tmp_path / "include.txt"
    include.write_text('("plastic"[tiab] OR "debris"[tiab])', encoding="utf-8")
    fake = FakePubMed(_window_records())
    client = make_client(fake, rps=10, api_key=KEY, email=CONTACT)

    rows, manifest = run_reference_set(
        "r9",
        include_path=include,
        exclude_path=None,
        affiliation="California",
        client=client,
        start="2020/01/01",
        end="2020/01/31",
        cap=20,
        margin=5,
        now=datetime(2026, 11, 22, tzinfo=UTC),
    )

    assert set(manifest) == MANIFEST_KEYS
    assert manifest["schema"] == "bqs-pm-manifest-v1"
    assert manifest["reference_set"] == "r9"
    assert manifest["affiliation"] == "California"
    assert manifest["query_text"].endswith("AND California[ad]")
    assert manifest["query_hash"] == hashlib.sha256(manifest["query_text"].encode()).hexdigest()
    assert manifest["query_translation"].startswith("translated(")
    assert manifest["run_timestamp"] == "2026-11-22T00:00:00+00:00"
    assert set(manifest["parameters"]) == PARAMETER_KEYS
    assert manifest["parameters"]["threshold"] == 15
    assert manifest["parameters"]["api_key_used"] is True
    assert manifest["parameters"]["cache_used"] is False

    assert len(manifest["chunks"]) == 2
    for chunk in manifest["chunks"]:
        assert set(chunk) == CHUNK_KEYS
        assert chunk["count"] == 120
        partitions = chunk["partitions"]
        assert len(partitions) > 1
        assert all(set(part) == PARTITION_KEYS for part in partitions)
        assert all(part["count"] <= 15 for part in partitions)
        assert sum(part["retrieved"] for part in partitions) == 120
        assert partitions[0]["start"] == "2020/01/01"
        assert partitions[-1]["end"] == "2020/01/31"
        for before, after in zip(partitions, partitions[1:], strict=False):
            gap = datetime.strptime(after["start"], "%Y/%m/%d") - datetime.strptime(
                before["end"], "%Y/%m/%d"
            )
            assert gap.days == 1

    assert manifest["total_unique_pmids"] == len(rows) == 120
    assert [row["pmid"] for row in rows[:2]] == ["1000", "1001"]
    assert all(set(row) == set(ROW_FIELDS) for row in rows)
    assert all(row["chunk_id"] == "c001" for row in rows)
    first = rows[0]
    assert (first["doi"], first["pub_year"]) == ("10.1000/fake.0", 2020)
    assert rows[1]["doi"] is None

    serialised = json.dumps(manifest) + "".join(json.dumps(row) for row in rows)
    assert CONTACT not in serialised
    assert KEY not in serialised
    assert all(f"email={urllib.parse.quote_plus(CONTACT)}" in url for url in fake.urls)


def test_count_and_partition_calls_are_all_on_the_full_window(tmp_path: Path) -> None:
    include = tmp_path / "include.txt"
    include.write_text('"plastic"[tiab]', encoding="utf-8")
    fake = FakePubMed(_window_records())
    client = make_client(fake)
    rows, manifest = run_reference_set(
        "r9",
        include_path=include,
        exclude_path=None,
        affiliation=None,
        client=client,
        start="2020/01/01",
        end="2020/01/31",
        cap=200,
        margin=10,
    )
    assert manifest["affiliation"] is None
    assert manifest["chunks"][0]["partitions"] == [
        {"start": "2020/01/01", "end": "2020/01/31", "count": 120, "retrieved": 120}
    ]
    assert len(rows) == 120


# --- Coverage join ------------------------------------------------------------------------------


def test_coverage_joins_by_pmid_then_doi_and_reports_rate_and_years() -> None:
    reference = [
        {"pmid": "1", "doi": "10.1/a", "pub_year": 2020},
        {"pmid": "2", "doi": "10.1/b", "pub_year": 2021},
        {"pmid": "3", "doi": "10.1/c", "pub_year": 2021},
        {"pmid": "4", "doi": None, "pub_year": 2020},
    ]
    atlas = [
        {"pmid": "1", "doi": "10.1/a", "year": 2020},
        {"pmid": None, "doi": "https://doi.org/10.1/B", "year": 2021},
        {"pmid": "9", "doi": None, "year": 2020},
        {"pmid": None, "doi": None, "year": 2022},
        {"pmid": "77", "doi": "10.1/C", "year": 2021},  # PMID misses, DOI fallback hits
    ]
    result = coverage(reference, atlas)
    assert result["reference_total"] == 4
    assert result["covered_total"] == 3
    assert result["coverage"] == pytest.approx(0.75)
    assert result["matched_by_pmid"] == 1
    assert result["matched_by_doi"] == 2
    assert result["atlas_works_total"] == 5
    assert result["atlas_works_with_pmid"] == 3
    assert result["join_rate"] == pytest.approx(0.6)
    assert result["atlas_works_matched"] == 3
    assert result["by_year"]["2020"] == {
        "reference_total": 2,
        "covered_total": 1,
        "coverage": 0.5,
    }
    assert result["by_year"]["2021"] == {
        "reference_total": 2,
        "covered_total": 2,
        "coverage": 1.0,
    }


def test_coverage_with_no_rows_reports_none_not_zero() -> None:
    result = coverage([], [])
    assert result["coverage"] is None
    assert result["join_rate"] is None
    assert result["by_year"] == {}


# --- Script (CLI) -------------------------------------------------------------------------------


def test_cli_dry_run_prints_plan_and_makes_no_call(tmp_path: Path, capsys: Any) -> None:
    cli = _load_cli()
    fake = FakePubMed([])
    out_dir = tmp_path / "out"
    rc = cli.main(
        [
            "--reference-set",
            "r1",
            "--affiliation",
            "California",
            "--out-dir",
            str(out_dir),
        ],
        env={"NCBI_EMAIL": CONTACT, "NCBI_API_KEY": KEY},
        opener=fake,
    )
    assert rc == 0
    assert fake.urls == []
    assert not out_dir.exists()
    out = capsys.readouterr().out
    assert "dry run" in out
    assert "c001: " in out and "AND California[ad]" in out
    assert "email=REDACTED" in out and "api_key=REDACTED" in out
    assert CONTACT not in out and KEY not in out


def test_cli_dry_run_without_contact_values_reports_them_as_unset(capsys: Any) -> None:
    cli = _load_cli()
    assert cli.main(["--reference-set", "r2", "--affiliation", "California"], env={}) == 0
    out = capsys.readouterr().out
    assert "OR chunks: 38" in out
    assert "contact email: not set" in out
    assert "email=" not in out.split("example request")[1]


def test_cli_rejects_dry_run_with_live(capsys: Any) -> None:
    cli = _load_cli()
    with pytest.raises(SystemExit):
        cli.main(["--reference-set", "r1", "--dry-run", "--live"], env={})
    capsys.readouterr()


def test_cli_live_writes_outputs_without_contact_values(
    tmp_path: Path, capsys: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    cli = _load_cli()
    fake = FakePubMed(_window_records())
    out_dir = tmp_path / "out"
    rc = cli.main(
        [
            "--reference-set",
            "r1",
            "--affiliation",
            "California",
            "--live",
            "--no-cache",
            "--start",
            "2020/01/01",
            "--end",
            "2020/01/31",
            "--out-dir",
            str(out_dir),
        ],
        env={"NCBI_EMAIL": CONTACT, "NCBI_API_KEY": KEY},
        opener=fake,
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert CONTACT not in out and KEY not in out

    csv_text = (out_dir / "r1_california_pmids.csv").read_text(encoding="utf-8")
    manifest_text = (out_dir / "r1_california_manifest.json").read_text(encoding="utf-8")
    for text in (csv_text, manifest_text):
        assert CONTACT not in text
        assert KEY not in text

    lines = csv_text.splitlines()
    assert lines[0] == "pmid,doi,pub_year,chunk_id,partition"
    assert len(lines) == 121
    manifest = json.loads(manifest_text)
    assert manifest["total_unique_pmids"] == 120
    assert manifest["parameters"]["api_key_used"] is True
    assert fake.urls
    assert all(f"email={urllib.parse.quote_plus(CONTACT)}" in url for url in fake.urls)
    assert all(f"api_key={KEY}" in url for url in fake.urls)


def test_cli_without_contact_env_sends_no_email(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    cli = _load_cli()
    fake = FakePubMed(_window_records())
    rc = cli.main(
        [
            "--reference-set",
            "r1",
            "--live",
            "--no-cache",
            "--start",
            "2020/01/01",
            "--end",
            "2020/01/31",
            "--out-dir",
            str(tmp_path / "out"),
        ],
        env={},
        opener=fake,
    )
    assert rc == 0
    assert fake.urls
    assert all("email=" not in url and "api_key=" not in url for url in fake.urls)


def test_cli_reports_a_partition_error_without_a_traceback(
    tmp_path: Path, capsys: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    cli = _load_cli()
    heavy_day = [
        {"pmid": str(5000 + i), "date": "2020/01/05", "year": 2020, "doi": None} for i in range(30)
    ]
    rc = cli.main(
        [
            "--reference-set",
            "r1",
            "--live",
            "--no-cache",
            "--start",
            "2020/01/01",
            "--end",
            "2020/01/31",
            "--cap",
            "20",
            "--margin",
            "5",
            "--out-dir",
            str(tmp_path / "out"),
        ],
        env={},
        opener=FakePubMed(heavy_day),
    )
    assert rc == 1
    assert "2020/01/05" in capsys.readouterr().err
