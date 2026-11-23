"""Offline tests for scripts/review_pubmed_misses_app.py and scripts/fetch_pubmed_miss_text.py.

Every test works on tmp copies of the triage sheet and text cache. The real sheet is never written,
and nothing here touches the network. The failure taxonomy is read, never written.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import sys
import urllib.error
import urllib.parse
from pathlib import Path
from types import ModuleType

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "scripts" / "review_pubmed_misses_app.py"
FETCH = ROOT / "scripts" / "fetch_pubmed_miss_text.py"
TAXONOMY = ROOT / "config" / "failure_taxonomy.yml"
SHEET_COLUMNS = (
    "pmid",
    "doi",
    "pub_year",
    "reference_sets",
    "in_normalized_corpus",
    "atlas_work_id",
    "triage_class",
    "note",
    "reviewer",
    "reviewed_at",
)
TRIAGE_FIELDS = ("triage_class", "note", "reviewer", "reviewed_at")
PMIDS = ("1001", "1002", "1003")


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _app() -> ModuleType:
    # The app imports streamlit at module level; CI does not install it (review apps run locally).
    pytest.importorskip("streamlit")
    return _load("review_pubmed_misses_app", APP)


def _fetch() -> ModuleType:
    return _load("fetch_pubmed_miss_text", FETCH)


def _taxonomy_ids() -> list[str]:
    data = yaml.safe_load(TAXONOMY.read_text(encoding="utf-8"))
    return [str(item["id"]) for item in data["classes"]]


def _write_sheet(path: Path, pmids: tuple[str, ...] = PMIDS) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SHEET_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for pmid in pmids:
            writer.writerow(
                {
                    "pmid": pmid,
                    "doi": f"10.1000/{pmid}",
                    "pub_year": "2019",
                    "reference_sets": "r2",
                    "in_normalized_corpus": "false",
                    "atlas_work_id": "",
                    "triage_class": "",
                    "note": "",
                    "reviewer": "",
                    "reviewed_at": "",
                }
            )
    return path


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_texts(path: Path, pmids: tuple[str, ...] = PMIDS) -> Path:
    records = {
        pmid: {
            "title": f"Microplastics record {pmid}",
            "abstract": f"Plastic debris in soil {pmid}.",
        }
        for pmid in pmids
    }
    path.write_text(json.dumps({"schema_version": 1, "records": records}), encoding="utf-8")
    return path


def _ids_in(url: str) -> list[str]:
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["id"][0].split(",")


def _xml_for(pmids: list[str]) -> bytes:
    articles = "".join(
        f"<PubmedArticle><MedlineCitation><PMID>{pmid}</PMID><Article>"
        f"<ArticleTitle>Title {pmid}</ArticleTitle>"
        f"<Abstract><AbstractText>Abstract {pmid}</AbstractText></Abstract>"
        "</Article></MedlineCitation></PubmedArticle>"
        for pmid in pmids
    )
    return f"<PubmedArticleSet>{articles}</PubmedArticleSet>".encode()


# --- Failure classes and the save helper ------------------------------------------------------


def test_app_module_imports_without_running_streamlit() -> None:
    pytest.importorskip("streamlit")
    assert callable(_app().main)


def test_classes_come_from_the_taxonomy_in_file_order() -> None:
    classes = _app().load_classes(TAXONOMY)
    assert [cls.id for cls in classes] == _taxonomy_ids()
    assert all(cls.label and cls.definition for cls in classes)
    assert {cls.direction for cls in classes} <= {
        "false_negative",
        "either",
        "false_positive",
        "not_an_error",
    }


def test_load_classes_refuses_an_unknown_direction(tmp_path: Path) -> None:
    path = tmp_path / "taxonomy.yml"
    path.write_text(
        "version: x\nclasses:\n  - id: a\n    label: A\n    direction: sideways\n"
        "    definition: d\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="sideways"):
        _app().load_classes(path)


def test_record_decision_writes_only_one_rows_triage_fields(tmp_path: Path) -> None:
    app = _app()
    sheet = _write_sheet(tmp_path / "triage.csv")
    before_rows = _read_rows(sheet)
    before_lines = sheet.read_bytes().decode("utf-8").splitlines()
    first_class = _taxonomy_ids()[0]

    app.record_decision(
        sheet,
        "1002",
        first_class,
        "  checked  ",
        "SC",
        class_ids=_taxonomy_ids(),
        reviewed_at="2026-11-22T10:00:00Z",
    )

    raw = sheet.read_bytes().decode("utf-8")
    after_lines = raw.splitlines()
    assert "\r" not in raw and raw.endswith("\n")
    assert after_lines[0] == before_lines[0]
    assert after_lines[1] == before_lines[1]
    assert after_lines[3] == before_lines[3]
    after_rows = _read_rows(sheet)
    assert len(after_rows) == len(before_rows)
    assert after_rows[0] == before_rows[0] and after_rows[2] == before_rows[2]
    changed = after_rows[1]
    assert changed["triage_class"] == first_class
    assert changed["note"] == "checked"
    assert changed["reviewer"] == "SC"
    assert changed["reviewed_at"] == "2026-11-22T10:00:00Z"
    for column in SHEET_COLUMNS:
        if column not in TRIAGE_FIELDS:
            assert changed[column] == before_rows[1][column]


def test_other_needs_a_note_and_is_saved_without_a_class(tmp_path: Path) -> None:
    app = _app()
    sheet = _write_sheet(tmp_path / "triage.csv")
    before = sheet.read_bytes()
    with pytest.raises(ValueError, match="note"):
        app.record_decision(sheet, "1001", "", "  ", "SC", class_ids=_taxonomy_ids())
    assert sheet.read_bytes() == before

    app.record_decision(sheet, "1001", "", "Not about plastics.", "SC", class_ids=_taxonomy_ids())
    row = _read_rows(sheet)[0]
    assert row["triage_class"] == ""
    assert row["note"] == "Not about plastics."
    assert app.is_decided(row)


@pytest.mark.parametrize(
    ("triage_class", "reviewer", "pmid", "message"),
    [
        ("not_a_class", "SC", "1001", "not a class"),
        ("__FIRST__", "   ", "1001", "initials"),
        ("__FIRST__", "SC", "9999", "not in"),
    ],
)
def test_refused_decisions_leave_the_sheet_untouched(
    tmp_path: Path, triage_class: str, reviewer: str, pmid: str, message: str
) -> None:
    app = _app()
    sheet = _write_sheet(tmp_path / "triage.csv")
    before = sheet.read_bytes()
    if triage_class == "__FIRST__":
        triage_class = _taxonomy_ids()[0]
    with pytest.raises(ValueError, match=message):
        app.record_decision(sheet, pmid, triage_class, "", reviewer, class_ids=_taxonomy_ids())
    assert sheet.read_bytes() == before


def test_is_decided_counts_a_class_or_a_timestamp() -> None:
    app = _app()
    base = {"triage_class": "", "reviewed_at": ""}
    assert not app.is_decided(base)
    assert app.is_decided({**base, "triage_class": "litter_beetles"})
    assert app.is_decided({**base, "reviewed_at": "2026-11-22T10:00:00Z"})


# --- EFetch text (scripts/fetch_pubmed_miss_text.py) ------------------------------------------

EFETCH_XML = b"""<?xml version="1.0" ?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">111</PMID>
      <Article>
        <ArticleTitle>Soil <i>microplastics</i> and
          fibres.</ArticleTitle>
        <Abstract>
          <AbstractText Label="BACKGROUND">Plastic   debris.</AbstractText>
          <AbstractText Label="METHODS">We sampled soil.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>222</PMID>
      <Article><ArticleTitle>No abstract here</ArticleTitle></Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>
"""


def test_parse_efetch_reads_title_and_labelled_abstract() -> None:
    records = _fetch().parse_efetch(EFETCH_XML)
    assert records == {
        "111": {
            "title": "Soil microplastics and fibres.",
            "abstract": "BACKGROUND: Plastic debris.\nMETHODS: We sampled soil.",
        },
        "222": {"title": "No abstract here", "abstract": ""},
    }


def test_parse_efetch_refuses_a_non_xml_or_error_response() -> None:
    fetch = _fetch()
    with pytest.raises(fetch.FetchError, match="not XML"):
        fetch.parse_efetch(b"<html>")
    with pytest.raises(fetch.FetchError, match="Bad id"):
        fetch.parse_efetch(b"<eFetchResult><ERROR>Bad id</ERROR></eFetchResult>")


def test_efetch_url_names_the_tool_and_adds_contact_only_when_set() -> None:
    fetch = _fetch()
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(fetch.efetch_url(["1", "2"], {})).query)
    assert query == {
        "db": ["pubmed"],
        "retmode": ["xml"],
        "id": ["1,2"],
        "tool": ["ca-plastics-research-atlas"],
    }
    url = fetch.efetch_url(["1"], {"NCBI_EMAIL": "owner@example.org", "NCBI_API_KEY": "key"})
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert query["email"] == ["owner@example.org"]
    assert query["api_key"] == ["key"]


def test_batches_send_at_most_200_ids_per_call() -> None:
    fetch = _fetch()
    calls: list[str] = []

    def opener(url: str) -> bytes:
        calls.append(url)
        return _xml_for(_ids_in(url))

    pmids = [str(number) for number in range(1, 451)]
    records = fetch.fetch_records(pmids, environ={}, opener=opener, sleep=lambda _: None)
    assert len(calls) == 3
    assert all(len(_ids_in(url)) <= 200 for url in calls)
    assert len(records) == 450


def test_server_errors_are_retried_and_client_errors_are_not() -> None:
    fetch = _fetch()
    attempts: list[str] = []
    sleeps: list[float] = []

    def busy_then_ok(url: str) -> bytes:
        attempts.append(url)
        if len(attempts) == 1:
            raise urllib.error.HTTPError(url, 503, "busy", None, None)
        return _xml_for(_ids_in(url))

    records = fetch.fetch_records(["1"], environ={}, opener=busy_then_ok, sleep=sleeps.append)
    assert set(records) == {"1"}
    assert len(attempts) == 2 and sleeps == [2.0]

    refused: list[str] = []

    def bad_request(url: str) -> bytes:
        refused.append(url)
        raise urllib.error.HTTPError(url, 400, "bad", None, None)

    with pytest.raises(fetch.FetchError, match="HTTP 400"):
        fetch.fetch_records(["1"], environ={}, opener=bad_request, sleep=lambda _: None)
    assert len(refused) == 1


def test_main_fetches_only_what_is_missing_and_then_stops(tmp_path: Path) -> None:
    fetch = _fetch()
    sheet = _write_sheet(tmp_path / "triage.csv")
    out = tmp_path / "miss_text.json"
    out.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": {"1001": {"title": "Old title", "abstract": "Old abstract"}},
                "not_returned": [],
            }
        ),
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def opener(url: str) -> bytes:
        calls.append(_ids_in(url))
        return _xml_for(_ids_in(url))

    args = ["--sheet", str(sheet), "--out", str(out)]
    assert fetch.main(args, opener=opener, environ={}, sleep=lambda _: None) == 0
    assert calls == [["1002", "1003"]]
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["records"]["1001"]["title"] == "Old title"
    assert payload["records"]["1002"] == {"title": "Title 1002", "abstract": "Abstract 1002"}
    assert payload["not_returned"] == []

    assert fetch.main(args, opener=opener, environ={}, sleep=lambda _: None) == 0
    assert calls == [["1002", "1003"]]


def test_pmids_ncbi_does_not_return_are_recorded_and_not_refetched(tmp_path: Path) -> None:
    fetch = _fetch()
    sheet = _write_sheet(tmp_path / "triage.csv")
    out = tmp_path / "miss_text.json"
    calls: list[list[str]] = []

    def only_first(url: str) -> bytes:
        calls.append(_ids_in(url))
        return _xml_for([pmid for pmid in _ids_in(url) if pmid == "1001"])

    args = ["--sheet", str(sheet), "--out", str(out)]
    assert fetch.main(args, opener=only_first, environ={}, sleep=lambda _: None) == 0
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["not_returned"] == ["1002", "1003"]
    assert fetch.main(args, opener=only_first, environ={}, sleep=lambda _: None) == 0
    assert len(calls) == 1


def test_sheet_pmids_must_be_numeric_and_unique(tmp_path: Path) -> None:
    fetch = _fetch()
    sheet = _write_sheet(tmp_path / "triage.csv", pmids=("1001", "1001"))
    with pytest.raises(fetch.FetchError, match="more than once"):
        fetch.read_sheet_pmids(sheet)


# --- The Streamlit app (AppTest, tmp copies only) ---------------------------------------------


def _app_test(monkeypatch: pytest.MonkeyPatch, sheet: Path, texts: Path):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(sys, "argv", [str(APP), "--csv", str(sheet), "--text", str(texts)])
    return AppTest.from_file(str(APP), default_timeout=60)


def test_each_taxonomy_class_and_other_has_a_button_with_its_definition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _write_sheet(tmp_path / "triage.csv")
    texts = _write_texts(tmp_path / "miss_text.json")
    at = _app_test(monkeypatch, sheet, texts).run()
    assert not at.exception
    assert at.subheader[0].value == "PMID 1001"
    classes = _app().load_classes(TAXONOMY)
    for cls in classes:
        assert at.button(key=f"cls_1001_{cls.id}").proto.help == cls.definition
    assert at.button(key="other_1001").proto.help
    assert {cls.id for cls in classes} == set(_taxonomy_ids())


def test_buttons_stay_disabled_until_initials_are_entered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _write_sheet(tmp_path / "triage.csv")
    texts = _write_texts(tmp_path / "miss_text.json")
    at = _app_test(monkeypatch, sheet, texts).run()
    first = _taxonomy_ids()[0]
    assert at.button(key=f"cls_1001_{first}").disabled
    assert at.button(key="other_1001").disabled
    at.sidebar.text_input(key="reviewer").input("SC").run()
    assert not at.button(key=f"cls_1001_{first}").disabled


def test_one_click_saves_one_row_and_moves_to_the_next_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _write_sheet(tmp_path / "triage.csv")
    texts = _write_texts(tmp_path / "miss_text.json")
    before = _read_rows(sheet)
    at = _app_test(monkeypatch, sheet, texts).run()
    at.sidebar.text_input(key="reviewer").input("SC").run()
    first = _taxonomy_ids()[0]
    at.button(key=f"cls_1001_{first}").click().run()
    assert not at.exception
    after = _read_rows(sheet)
    assert after[0]["triage_class"] == first
    assert after[0]["reviewer"] == "SC"
    assert after[0]["reviewed_at"].endswith("Z")
    assert after[1:] == before[1:]
    assert at.subheader[0].value == "PMID 1002"


def test_other_without_a_note_is_refused_then_saves_with_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _write_sheet(tmp_path / "triage.csv")
    texts = _write_texts(tmp_path / "miss_text.json")
    before = sheet.read_bytes()
    at = _app_test(monkeypatch, sheet, texts).run()
    at.sidebar.text_input(key="reviewer").input("SC").run()
    at.button(key="other_1001").click().run()
    assert at.error[0].value == "Write a note before choosing Other."
    assert sheet.read_bytes() == before

    at.text_input(key="note_1001").input("Not about plastics.").run()
    at.button(key="other_1001").click().run()
    assert not at.exception
    row = _read_rows(sheet)[0]
    assert row["triage_class"] == ""
    assert row["note"] == "Not about plastics."
    assert row["reviewer"] == "SC"
    assert at.subheader[0].value == "PMID 1002"


def test_all_view_lets_the_owner_change_an_earlier_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _write_sheet(tmp_path / "triage.csv")
    texts = _write_texts(tmp_path / "miss_text.json")
    at = _app_test(monkeypatch, sheet, texts).run()
    at.sidebar.text_input(key="reviewer").input("SC").run()
    ids = _taxonomy_ids()
    at.button(key=f"cls_1001_{ids[0]}").click().run()
    assert at.subheader[0].value == "PMID 1002"

    at.sidebar.selectbox[0].set_value("All").run()
    at.button(key="prev").click().run()
    assert at.subheader[0].value == "PMID 1001"
    at.button(key=f"cls_1001_{ids[1]}").click().run()
    assert _read_rows(sheet)[0]["triage_class"] == ids[1]


def test_missing_cache_shows_the_fetch_instruction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _write_sheet(tmp_path / "triage.csv")
    at = _app_test(monkeypatch, sheet, tmp_path / "absent.json").run()
    assert "fetch_pubmed_miss_text.py" in at.error[0].value


def test_a_case_without_cached_text_still_opens_with_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _write_sheet(tmp_path / "triage.csv")
    texts = _write_texts(tmp_path / "miss_text.json", pmids=("1002", "1003"))
    at = _app_test(monkeypatch, sheet, texts).run()
    assert not at.exception
    assert at.subheader[0].value == "PMID 1001"
    assert any("No title or abstract cached" in warning.value for warning in at.warning)


def test_matched_terms_are_highlighted_in_the_title_and_abstract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _write_sheet(tmp_path / "triage.csv")
    texts = _write_texts(tmp_path / "miss_text.json")
    at = _app_test(monkeypatch, sheet, texts).run()
    rendered = " ".join(element.proto.body for element in at.get("html"))
    plain = " ".join(re.sub(r"<[^>]+>", "", rendered).split())
    assert "Microplastics record 1001" in plain
    assert "Plastic debris in soil 1001." in plain
    assert "<mark" in rendered
