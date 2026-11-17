"""Tests for the OPC Solutions track (Add-on A2 §7 Part A, EM-17): loader, validator, JSON."""

from __future__ import annotations

import copy
import importlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
COMMITTED = ROOT / "site" / "data" / "opc_actions.json"
REVIEW_SHEET = ROOT / "curation" / "opc_mapping_review.csv"
REVIEW_APP = SCRIPTS / "review_opc_mapping_app.py"
sys.path.insert(0, str(ROOT / "src"))

from atlas.opc_actions import (  # noqa: E402
    DISCLAIMER,
    REVIEW_COLUMNS,
    OpcActionsError,
    apply_review,
    blank_review_rows,
    init_review_sheet,
    load_actions,
    read_review,
    topic_keys,
    validate_actions,
)

SPEC_DISCLAIMER = (
    "The Global Plastic Laws Database is an educational and research resource and should not "
    "be regarded as fully comprehensive or completely up to date for legal purposes."
)
# A small topic set for inline fixtures; the real keys come from site/assets/topics.js.
FIXTURE_TOPICS = frozenset({"air", "wastewater_and_treatment", "plastic_associated_chemicals"})
FIXTURE_CODES = [
    f"2A.{objective}.{number}"
    for objective, count in ((1, 9), (2, 9), (3, 4))
    for number in range(1, count + 1)
]


def _action(code: str) -> dict[str, Any]:
    return {
        "code": code,
        "objective": int(code[3]),
        "group": "Test group",
        "summary": "Carry out a test action.",
        "deadline_as_stated": "by 2023",
        "deadline_year": 2023,
        "pdf_page": 22,
        "gpl_topics": ["reduction"],
        "atlas": {"q": "reduction"},
    }


def _fixture() -> dict[str, Any]:
    """A valid 22-action mapping with a three-objective structure."""
    return {
        "source": {
            "label": "Test strategy",
            "url": "https://example.gov/strategy",
            "adopted": "23 February 2022",
        },
        "mapping_status": "draft",
        "gpl": {
            "name": "Global Plastic Laws",
            "steward": "Test steward",
            "base_url": "https://www.globalplasticlaws.org",
            "california_search_url": "https://www.globalplasticlaws.org/search?search=california",
            "disclaimer": DISCLAIMER,
            "topics": {"reduction": "Reduction"},
        },
        "objectives": [
            {"id": 1, "name": "One"},
            {"id": 2, "name": "Two"},
            {"id": 3, "name": "Three"},
        ],
        "actions": [_action(code) for code in FIXTURE_CODES],
    }


def _builder() -> ModuleType:
    sys.path.insert(0, str(SCRIPTS))
    try:
        return importlib.import_module("build_opc_actions_json")
    finally:
        sys.path.remove(str(SCRIPTS))


def _payload() -> dict[str, Any]:
    return json.loads(COMMITTED.read_text(encoding="utf-8"))


# Curated file (real data, read only).


def test_curated_file_has_22_actions_and_draft_mapping() -> None:
    data = load_actions()
    assert len(data["actions"]) == 22
    assert data["mapping_status"] == "draft"
    assert [o["id"] for o in data["objectives"]] == [1, 2, 3]


def test_disclaimer_is_the_spec_sentence() -> None:
    assert DISCLAIMER == SPEC_DISCLAIMER
    assert load_actions()["gpl"]["disclaimer"] == SPEC_DISCLAIMER


def test_codes_are_unique_and_objectives_match_codes() -> None:
    actions = load_actions()["actions"]
    codes = [a["code"] for a in actions]
    assert len(set(codes)) == 22
    assert all(re.fullmatch(r"2A\.[123]\.\d", code) for code in codes)
    assert all(int(a["code"][3]) == a["objective"] for a in actions)


def test_deadlines_are_quoted_verbatim() -> None:
    by_code = {a["code"]: a for a in load_actions()["actions"]}
    assert by_code["2A.1.1"]["deadline_as_stated"] == "by 2022"
    assert by_code["2A.2.1"]["deadline_as_stated"] == "beginning in 2022"
    assert by_code["2A.2.3"]["deadline_as_stated"] == "adopted or reissued after December 31, 2023"
    assert by_code["2A.2.6"]["deadline_year"] == 2030


def test_real_topic_keys_are_read_from_topics_js() -> None:
    keys = topic_keys()
    assert "wastewater_and_treatment" in keys
    assert "plastic_associated_chemicals" in keys
    # Matrix labels in topics.js are strings, not topic objects, so they are not topic keys.
    assert "marine" not in keys


def test_every_atlas_topic_and_gpl_slug_is_known() -> None:
    data = load_actions()
    keys = topic_keys()
    for action in data["actions"]:
        if "topic" in action["atlas"]:
            assert action["atlas"]["topic"] in keys, action["code"]
        for slug in action["gpl_topics"]:
            assert slug in data["gpl"]["topics"], action["code"]


def test_topic_keys_rejects_a_file_without_topics(tmp_path: Path) -> None:
    empty = tmp_path / "topics.js"
    empty.write_text('const MATRICES = {\n  marine: "Marine"\n};\n', encoding="utf-8")
    with pytest.raises(OpcActionsError, match="no topic keys"):
        topic_keys(empty)


def test_topic_keys_reads_only_topic_objects(tmp_path: Path) -> None:
    sample = tmp_path / "topics.js"
    sample.write_text(
        "const TOPICS = {\n"
        '    air: { label: "Air", color: "#e34948", order: 8 },\n'
        "    plastic_associated_chemicals: {\n"
        '      label: "Plastic-associated chemicals"\n'
        "    }\n"
        "  };\n"
        "const MATRICES = {\n"
        '    marine: "Marine"\n'
        "  };\n",
        encoding="utf-8",
    )
    assert topic_keys(sample) == frozenset({"air", "plastic_associated_chemicals"})


# Validator with small inline fixtures.


def test_fixture_happy_path_and_allowed_wording() -> None:
    data = _fixture()
    # "enforcement" describes an action the Strategy asks for, so it is allowed.
    data["actions"][0]["summary"] = "Prioritise enforcement of discharge prohibitions."
    assert validate_actions(data, FIXTURE_TOPICS) is data


def _mutate_disclaimer(data: dict[str, Any]) -> None:
    data["gpl"]["disclaimer"] = DISCLAIMER.rstrip(".")


def _mutate_action(index: int, **changes: Any):
    def mutate(data: dict[str, Any]) -> None:
        data["actions"][index].update(changes)

    return mutate


FAILURES = [
    pytest.param(lambda d: d.update(mapping_status="approved"), "mapping_status", id="status"),
    pytest.param(_mutate_disclaimer, "disclaimer", id="disclaimer"),
    pytest.param(
        lambda d: d["source"].update(url="http://example.gov/strategy"), "https", id="http-source"
    ),
    pytest.param(lambda d: d.pop("objectives"), "missing top-level", id="missing-top-level"),
    pytest.param(lambda d: d["actions"].pop(), "exactly 22", id="21-actions"),
    pytest.param(
        lambda d: d["actions"][1].update(code="2A.1.1"), "duplicate code", id="duplicate-code"
    ),
    pytest.param(_mutate_action(0, code="2A.4.1"), "code must match", id="bad-code"),
    pytest.param(_mutate_action(0, objective=4), "not in objectives", id="unknown-objective"),
    pytest.param(_mutate_action(0, objective=2), "disagree", id="objective-mismatch"),
    pytest.param(
        lambda d: d["objectives"].append({"id": 1, "name": "Again"}), "unique", id="dup-objective"
    ),
    pytest.param(
        _mutate_action(0, deadline_as_stated="by 2031", deadline_year=2031),
        "deadline_year must be",
        id="year-out-of-range",
    ),
    pytest.param(_mutate_action(0, deadline_year=2024), "does not match", id="year-mismatch"),
    pytest.param(_mutate_action(0, deadline_year=True), "deadline_year must be", id="bool-year"),
    pytest.param(
        _mutate_action(0, deadline_as_stated="in 2023"),
        "deadline_as_stated must start",
        id="deadline-prefix",
    ),
    pytest.param(_mutate_action(0, pdf_page=0), "pdf_page", id="pdf-page"),
    pytest.param(
        _mutate_action(0, gpl_topics=["nope"]), "not in gpl.topics", id="unknown-gpl-slug"
    ),
    pytest.param(
        _mutate_action(0, gpl_topics=["reduction", "reduction"]),
        "repeats a slug",
        id="repeated-slug",
    ),
    pytest.param(
        _mutate_action(0, atlas={"q": "x", "topic": "air"}),
        "exactly one of q or topic",
        id="both-atlas-keys",
    ),
    pytest.param(
        _mutate_action(0, atlas={"topic": "marine"}),
        "not in site/assets/topics.js",
        id="unknown-atlas-topic",
    ),
    pytest.param(_mutate_action(0, atlas={"q": "   "}), "atlas.q", id="empty-atlas-q"),
    pytest.param(_mutate_action(0, summary="x" * 201), "200 characters", id="summary-too-long"),
    pytest.param(
        _mutate_action(0, summary="Sanctions were enforced in 2023."),
        "must not claim",
        id="enforced-claim",
    ),
    pytest.param(
        _mutate_action(0, summary="Bans are effective in reducing litter."),
        "must not claim",
        id="effect-claim",
    ),
    pytest.param(
        _mutate_action(0, summary="Implemented in 2023."), "must not claim", id="implemented"
    ),
    pytest.param(
        lambda d: d["actions"][0].pop("pdf_page"), "missing keys", id="missing-action-key"
    ),
    pytest.param(lambda d: d["gpl"].update(topics={}), "must not be empty", id="no-gpl-topics"),
]


@pytest.mark.parametrize(("mutate", "match"), FAILURES)
def test_invalid_fixture_is_rejected(mutate, match: str) -> None:
    data = _fixture()
    mutate(data)
    with pytest.raises(OpcActionsError, match=match):
        validate_actions(data, FIXTURE_TOPICS)


def test_rejects_a_non_mapping() -> None:
    with pytest.raises(OpcActionsError, match="must be a mapping"):
        validate_actions(["not", "a", "mapping"], FIXTURE_TOPICS)


def test_load_actions_rejects_an_invalid_file(tmp_path: Path) -> None:
    data = _fixture()
    data["actions"][0]["summary"] = "Carry out a test action; this is implemented."
    path = tmp_path / "opc.yml"
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    sample_topics = tmp_path / "topics.js"
    sample_topics.write_text('const TOPICS = {\n    air: { label: "Air" },\n};\n', encoding="utf-8")
    with pytest.raises(OpcActionsError, match="must not claim"):
        load_actions(path, sample_topics)


# Committed JSON.


def test_committed_json_is_not_stale(tmp_path: Path) -> None:
    builder = _builder()
    assert builder.main(["--check"]) == 0
    stale = tmp_path / "opc_actions.json"
    stale.write_text(COMMITTED.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert builder.main(["--check", "--output", str(stale)]) == 1
    assert builder.main(["--check", "--output", str(tmp_path / "missing.json")]) == 1


def test_committed_json_carries_the_panel_contract() -> None:
    payload = _payload()
    assert payload["schema_version"] == "em17.v1"
    # Draft until every row of the owner review sheet has a decision (EAT-9); then owner_reviewed.
    reviewed = all(row.get("decision") for row in read_review())
    assert payload["mapping_status"] == ("owner_reviewed" if reviewed else "draft")
    assert payload["gpl"]["disclaimer"] == SPEC_DISCLAIMER
    assert payload["strategy"]["adopted"] == "23 February 2022"
    assert payload["strategy"]["url"].startswith("https://")
    assert payload["gpl"]["base_url"].startswith("https://")
    assert payload["gpl"]["california_search_url"].startswith("https://")
    assert len(payload["actions"]) == 22
    assert [o["id"] for o in payload["objectives"]] == [1, 2, 3]
    keys = {
        "code",
        "objective",
        "group",
        "summary",
        "deadline_as_stated",
        "deadline_year",
        "pdf_page",
        "gpl_topics",
        "atlas",
    }
    for action in payload["actions"]:
        assert set(action) == keys, action["code"]


def test_committed_json_has_no_internal_vocabulary() -> None:
    text = COMMITTED.read_text(encoding="utf-8")
    assert not re.search(r"\bEM-\d+\b", text)
    assert "[INF]" not in text
    assert not re.search(r"\bA2\b", text)
    assert "\r" not in text


# Owner review (EM-17b): the sheet, apply_review and the review app.


def _codes() -> list[str]:
    return [action["code"] for action in load_actions()["actions"]]


def _review(decisions: dict[str, tuple[str, str]] | None = None) -> list[dict[str, str]]:
    """A review sheet with one row per action; ``decisions`` maps code to (decision, topics)."""
    rows = blank_review_rows(load_actions())
    for row in rows:
        decision, topics = (decisions or {}).get(row["code"], ("", ""))
        row.update(decision=decision, owner_gpl_topics=topics)
    return rows


def _by_code(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {action["code"]: action for action in data["actions"]}


def _blank_sheet(tmp_path: Path) -> Path:
    sheet = tmp_path / "opc_mapping_review.csv"
    init_review_sheet(sheet)
    return sheet


def _row(sheet: Path, code: str) -> dict[str, str]:
    return next(row for row in read_review(sheet) if row["code"] == code)


def test_blank_review_keeps_every_draft_topic_list_and_status() -> None:
    data = load_actions()
    applied = apply_review(data, blank_review_rows(data))
    assert applied["actions"] == data["actions"]
    assert applied["mapping_status"] == "draft"


def test_accept_keeps_the_draft_topics() -> None:
    applied = apply_review(load_actions(), _review({"2A.2.4": ("accept", "")}))
    assert _by_code(applied)["2A.2.4"]["gpl_topics"] == [
        "product-manufacturing",
        "maritime-sources",
    ]


def test_change_takes_the_owner_topics_in_sheet_order() -> None:
    sheet = _review({"2A.1.1": ("change", "microplastics;reduction")})
    applied = apply_review(load_actions(), sheet)
    assert _by_code(applied)["2A.1.1"]["gpl_topics"] == ["microplastics", "reduction"]


def test_none_clears_the_topics() -> None:
    applied = apply_review(load_actions(), _review({"2A.1.1": ("none", "")}))
    assert _by_code(applied)["2A.1.1"]["gpl_topics"] == []


def test_partial_review_stays_draft_and_leaves_other_rows_alone() -> None:
    data = load_actions()
    applied = apply_review(data, _review({"2A.1.1": ("none", "")}))
    assert applied["mapping_status"] == "draft"
    assert _by_code(applied)["2A.1.2"]["gpl_topics"] == _by_code(data)["2A.1.2"]["gpl_topics"]


def test_a_decision_on_all_22_actions_marks_the_mapping_owner_reviewed() -> None:
    data = load_actions()
    applied = apply_review(data, _review({code: ("accept", "") for code in _codes()}))
    assert applied["mapping_status"] == "owner_reviewed"
    assert applied["actions"] == data["actions"]


def test_apply_review_does_not_change_its_input() -> None:
    data = load_actions()
    before = copy.deepcopy(data)
    apply_review(data, _review({"2A.1.1": ("none", "")}))
    assert data == before


REVIEW_FAILURES = [
    pytest.param(
        lambda: _review({"2A.1.1": ("change", "nope")}), "not in gpl.topics", id="unknown-slug"
    ),
    pytest.param(
        lambda: _review({"2A.1.1": ("change", "reduction;reduction")}),
        "repeats a slug",
        id="repeated-slug",
    ),
    pytest.param(
        lambda: _review({"2A.1.1": ("change", "")}), "at least one topic", id="change-no-topics"
    ),
    pytest.param(
        lambda: _review({"2A.1.1": ("none", "reduction")}),
        "only used with decision change",
        id="topics-without-change",
    ),
    pytest.param(
        lambda: _review({"2A.1.1": ("approve", "")}), "decision must be", id="unknown-decision"
    ),
    pytest.param(
        lambda: _review() + [{"code": "2A.9.9", "decision": "accept", "owner_gpl_topics": ""}],
        "unknown action code",
        id="unknown-code",
    ),
    pytest.param(
        lambda: _review() + [dict(_review()[0])], "listed more than once", id="duplicate-code"
    ),
]


@pytest.mark.parametrize(("sheet", "match"), REVIEW_FAILURES)
def test_bad_review_rows_are_rejected(sheet, match: str) -> None:
    with pytest.raises(OpcActionsError, match=match):
        apply_review(load_actions(), sheet())


def test_init_writes_a_blank_lf_sheet_with_every_code(tmp_path: Path) -> None:
    sheet = _blank_sheet(tmp_path)
    raw = sheet.read_bytes()
    assert b"\r" not in raw
    assert raw.splitlines()[0] == ",".join(REVIEW_COLUMNS).encode("ascii")
    rows = read_review(sheet)
    assert [row["code"] for row in rows] == _codes()
    assert all(row["decision"] == "" for row in rows)


def test_init_never_overwrites_a_sheet_with_owner_input(tmp_path: Path) -> None:
    sheet = _blank_sheet(tmp_path)
    decided = sheet.read_bytes().replace(b"2A.1.1,,,,,", b"2A.1.1,accept,,,MK,2026-11-17T12:00:00Z")
    sheet.write_bytes(decided)
    with pytest.raises(OpcActionsError, match="not overwritten"):
        init_review_sheet(sheet)
    assert sheet.read_bytes() == decided


def test_committed_review_sheet_has_one_lf_row_per_code() -> None:
    assert b"\r" not in REVIEW_SHEET.read_bytes()
    rows = read_review(REVIEW_SHEET)
    assert [row["code"] for row in rows] == _codes()
    apply_review(load_actions(), rows)


def test_blank_review_sheet_keeps_the_committed_json_byte_identical(tmp_path: Path) -> None:
    sheet = _blank_sheet(tmp_path)
    assert _builder().main(["--check", "--review", str(sheet)]) == 0


def test_completed_review_changes_the_built_json() -> None:
    builder = _builder()
    rows = _review({code: ("accept", "") for code in _codes()})
    text = builder.render(builder.build_payload(review=rows))
    assert '"mapping_status": "owner_reviewed"' in text
    assert text != COMMITTED.read_text(encoding="utf-8")


def _review_app_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("review_opc_mapping_app", REVIEW_APP)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_review_app_module_imports_without_running_streamlit() -> None:
    pytest.importorskip("streamlit")
    assert callable(_review_app_module().main)


def _app_test(sheet: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(sys, "argv", [str(REVIEW_APP), "--csv", str(sheet)])
    return AppTest.from_file(str(REVIEW_APP), default_timeout=60)


def test_review_app_shows_the_first_action_and_writes_nothing_without_initials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _blank_sheet(tmp_path)
    before = sheet.read_bytes()
    at = _app_test(sheet, monkeypatch).run()
    assert not at.exception
    assert at.subheader[0].value.startswith("2A.1.1")
    assert at.button(key="accept_2A.1.1").disabled
    assert sheet.read_bytes() == before


def test_one_click_saves_the_decision_with_initials_and_advances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _blank_sheet(tmp_path)
    at = _app_test(sheet, monkeypatch).run()
    at.sidebar.text_input(key="reviewer").input("MK").run()
    at.button(key="accept_2A.1.1").click().run()
    assert not at.exception
    row = _row(sheet, "2A.1.1")
    assert (row["decision"], row["owner_gpl_topics"], row["reviewer"]) == ("accept", "", "MK")
    assert row["reviewed_at"].endswith("Z")
    assert at.subheader[0].value.startswith("2A.1.2")


def test_changed_topics_are_saved_as_slugs_in_gpl_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _blank_sheet(tmp_path)
    at = _app_test(sheet, monkeypatch).run()
    at.sidebar.text_input(key="reviewer").input("MK").run()
    at.multiselect(key="topics_2A.1.1").set_value(["Reduction", "Microplastics"]).run()
    at.button(key="change_2A.1.1").click().run()
    row = _row(sheet, "2A.1.1")
    assert (row["decision"], row["owner_gpl_topics"]) == ("change", "microplastics;reduction")


def test_no_topic_fits_saves_an_empty_topic_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _blank_sheet(tmp_path)
    at = _app_test(sheet, monkeypatch).run()
    at.sidebar.text_input(key="reviewer").input("MK").run()
    at.button(key="none_2A.1.1").click().run()
    row = _row(sheet, "2A.1.1")
    assert (row["decision"], row["owner_gpl_topics"]) == ("none", "")
