"""Tests for scripts/ambassador_export_pr.py (AMB-1 step 4).

Offline: a saved export JSON or a fake urlopen.

Each test works on copies under tmp_path; regions/*/region.yml in the repository is never touched.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import shutil
from datetime import datetime
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ambassador_export_pr.py"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ambassador_export"
TOKEN = "tok-SECRET-123-do-not-print"


def _load_module():
    spec = importlib.util.spec_from_file_location("ambassador_export_pr", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


MOD = _load_module()


@pytest.fixture
def work(tmp_path: Path) -> Path:
    (tmp_path / "regions" / "norway").mkdir(parents=True)
    shutil.copy(FIXTURES / "region.yml", tmp_path / "regions" / "norway" / "region.yml")
    (tmp_path / "curation").mkdir()
    (tmp_path / "curation" / "ambassador_export_state.json").write_text('{"since": 0}\n', "utf-8")
    (tmp_path / "curation" / "ambassador_labels.csv").write_text(
        "region,case_id,answer,correct_value,answered_at_iso,source\n", "utf-8"
    )
    (tmp_path / "curation" / "ambassador_institution_additions.csv").write_text(
        "region,name,url,domain,institution_type,approved_at_iso,source\n", "utf-8"
    )
    (tmp_path / "curation" / "group_double_tags.csv").write_text(DOUBLE_TAG_HEADER, "utf-8")
    (tmp_path / "curation" / "group_reviews.csv").write_text(REVIEW_HEADER, "utf-8")
    shutil.copy(FIXTURES / "export.json", tmp_path / "export.json")
    return tmp_path


DOUBLE_TAG_HEADER = "group_id,facet,value_a,value_b\n"
REVIEW_HEADER = "group_id,facet,outcome,reason_code,reviewed_at\n"


def _args(root: Path, *extra: str) -> list[str]:
    return [
        "--input",
        str(root / "export.json"),
        "--since-file",
        str(root / "curation" / "ambassador_export_state.json"),
        "--labels-file",
        str(root / "curation" / "ambassador_labels.csv"),
        "--additions-file",
        str(root / "curation" / "ambassador_institution_additions.csv"),
        "--regions-dir",
        str(root / "regions"),
        "--group-tags-file",
        str(root / "curation" / "group_tags.csv"),
        "--group-affiliations-file",
        str(root / "curation" / "group_affiliations.csv"),
        "--group-suggestions-file",
        str(root / "curation" / "group_suggestions.csv"),
        "--group-name-corrections-file",
        str(root / "curation" / "group_name_corrections.csv"),
        "--group-double-tags-file",
        str(root / "curation" / "group_double_tags.csv"),
        "--group-reviews-file",
        str(root / "curation" / "group_reviews.csv"),
        *extra,
    ]


def _region(root: Path) -> dict:
    return yaml.safe_load((root / "regions" / "norway" / "region.yml").read_text("utf-8"))


def _section(data: dict, section_id: str) -> list[dict]:
    return next(s for s in data["sections"] if s["id"] == section_id)["items"]


def _state(root: Path) -> dict:
    return json.loads((root / "curation" / "ambassador_export_state.json").read_text("utf-8"))


def _labels(root: Path) -> list[dict]:
    with (root / "curation" / "ambassador_labels.csv").open(encoding="utf-8", newline="") as h:
        return list(csv.DictReader(h))


def test_confirm_sets_status_and_credit(work: Path, capsys) -> None:
    assert MOD.main(_args(work)) == 0
    funding = _section(_region(work), "funding")
    assert funding[0]["status"] == "confirmed"
    assert funding[0]["note"] == "URL not checked Confirmed by Ada Example."
    assert funding[1]["status"] == "to_confirm"


def test_confirm_without_credit_adds_no_note(work: Path) -> None:
    assert MOD.main(_args(work)) == 0
    # Submission 6 (correct) has no credit, so its note stays as it was.
    policy = _section(_region(work), "policy")
    assert policy[0]["note"] == "No URL given"


def test_knowledge_appends_draft_items(work: Path) -> None:
    assert MOD.main(_args(work)) == 0
    data = _region(work)
    funding = _section(data, "funding")
    added = funding[-1]
    assert added == {
        "name": "Example Fund",
        "url": "https://fund.example/",
        "kind": "funder",
        "status": "draft",
        "note": "Funds plastics work.",
    }
    networks = _section(data, "research_networks")
    community = networks[-1]
    assert community["name"] == "Coast Volunteers"
    assert community["kind"] == "community"
    assert community["status"] == "draft"
    assert community["note"] == "Beach clean-ups. Suggested by Ben Example."


def test_invalid_url_is_skipped_with_reason(work: Path, capsys) -> None:
    assert MOD.main(_args(work)) == 0
    assert "skip submission 3: invalid url (https only)" in capsys.readouterr().out
    assert all(i["name"] != "Plain http policy" for i in _section(_region(work), "policy"))


def test_not_relevant_marks_in_place_and_correct_renames(work: Path) -> None:
    before = [i["name"] for i in _section(_region(work), "monitoring")]
    assert MOD.main(_args(work)) == 0
    data = _region(work)
    monitoring = _section(data, "monitoring")
    # Marked, not removed, so every item keeps its position (item ids are positions).
    assert [i["name"] for i in monitoring] == before
    kept = [i["name"] for i in monitoring if i["status"] != "not_relevant"]
    assert kept == ["Norwegian Environment Agency"]
    policy = _section(data, "policy")[0]
    assert policy["name"] == "National plastics strategy 2026"
    assert policy["status"] == "confirmed"


def test_consensus_rows_are_deduplicated_newest_wins(work: Path) -> None:
    assert MOD.main(_args(work)) == 0
    rows = _labels(work)
    assert len(rows) == 2
    by_case = {r["case_id"]: r for r in rows}
    assert by_case["amb-0123456789ab"]["answer"] == "no"
    assert by_case["amb-0123456789ab"]["correct_value"] == "2"
    assert by_case["amb-0123456789ab"]["answered_at_iso"] == "1970-01-01T00:00:04Z"
    assert by_case["amb-ba9876543210"]["answered_at_iso"] == "1970-01-01T00:00:03Z"
    assert {r["source"] for r in rows} == {"ambassador_consensus"}


def test_watermark_advances_after_success(work: Path) -> None:
    assert MOD.main(_args(work)) == 0
    assert _state(work)["since"] == 4000


def test_watermark_stays_when_write_fails(work: Path, monkeypatch, capsys) -> None:
    def broken(path, labels):
        raise OSError("disk full")

    monkeypatch.setattr(MOD, "write_labels", broken)
    assert MOD.main(_args(work)) == 1
    assert _state(work) == {"since": 0}
    assert "file operation failed" in capsys.readouterr().out


def test_second_run_is_idempotent(work: Path) -> None:
    assert MOD.main(_args(work)) == 0
    region_text = (work / "regions" / "norway" / "region.yml").read_text("utf-8")
    labels_text = (work / "curation" / "ambassador_labels.csv").read_text("utf-8")
    assert MOD.main(_args(work)) == 0
    assert (work / "regions" / "norway" / "region.yml").read_text("utf-8") == region_text
    assert (work / "curation" / "ambassador_labels.csv").read_text("utf-8") == labels_text
    assert _state(work)["since"] == 4000


def test_region_comments_and_untouched_lines_keep_their_bytes(work: Path) -> None:
    original = (FIXTURES / "region.yml").read_text("utf-8").splitlines()
    assert MOD.main(_args(work)) == 0
    new = (work / "regions" / "norway" / "region.yml").read_text("utf-8").splitlines()
    assert new[0] == original[0]
    assert "# Small region.yml fixture" in new[0]
    assert "    needs: A local collaborator to confirm the funders." in new


def test_dry_run_writes_nothing(work: Path, capsys) -> None:
    paths = [
        work / "regions" / "norway" / "region.yml",
        work / "curation" / "ambassador_labels.csv",
        work / "curation" / "ambassador_export_state.json",
    ]
    before = [p.read_bytes() for p in paths]
    assert MOD.main(_args(work, "--dry-run")) == 0
    assert [p.read_bytes() for p in paths] == before
    assert "dry run: nothing written" in capsys.readouterr().out


def test_fetch_uses_bearer_token_and_never_prints_it(work: Path, monkeypatch, capsys) -> None:
    seen: dict[str, str] = {}
    body = (FIXTURES / "export.json").read_bytes()

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return body

    def fake_urlopen(request, timeout=None):
        seen["auth"] = request.get_header("Authorization")
        seen["url"] = request.full_url
        return _Response()

    monkeypatch.setenv(MOD.TOKEN_ENV, TOKEN)
    monkeypatch.setattr(MOD.urllib.request, "urlopen", fake_urlopen)
    args = [a for a in _args(work) if a not in ("--input", str(work / "export.json"))]
    assert MOD.main(args) == 0
    assert seen["auth"] == f"Bearer {TOKEN}"
    assert seen["url"] == "https://api.plastiverse.live/export/approved?since=0"
    captured = capsys.readouterr()
    assert TOKEN not in captured.out and TOKEN not in captured.err
    assert _state(work)["since"] == 4000


def test_missing_token_refuses_to_call_the_api(work: Path, monkeypatch, capsys) -> None:
    monkeypatch.delenv(MOD.TOKEN_ENV, raising=False)
    args = [a for a in _args(work) if a not in ("--input", str(work / "export.json"))]
    assert MOD.main(args) == 2
    assert "AMB_EXPORT_TOKEN is not set" in capsys.readouterr().err
    assert _state(work) == {"since": 0}


def test_locate_item_accepts_section_id_and_kind(work: Path) -> None:
    data = _region(work)
    section, item = MOD.locate_item(data, "norway:funder:1", "norway")
    assert item["name"] == "Handelens Miljofond"
    section, item = MOD.locate_item(data, "norway:monitoring:0", "norway")
    assert section["id"] == "monitoring" and item["name"] == "Norwegian Environment Agency"
    assert MOD.locate_item(data, "belgium:funder:0", "norway") is None


def _additions(root: Path) -> list[dict]:
    path = root / "curation" / "ambassador_institution_additions.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _export_with(root: Path, institutions: list[dict]) -> list[str]:
    export = json.loads((FIXTURES / "export.json").read_text("utf-8"))
    export["institutions"] = institutions
    path = root / "later.json"
    path.write_text(json.dumps(export), "utf-8")
    return ["--input", str(path), *_args(root)[2:]]


def test_approved_institutions_are_written_deduped_and_counted(work: Path, tmp_path: Path) -> None:
    summary = tmp_path / "summary.md"
    assert MOD.main(_args(work, "--summary-file", str(summary))) == 0
    rows = _additions(work)
    assert [(r["domain"], r["name"]) for r in rows] == [
        ("agency.no", "Agency"),
        ("fixture-lab.no", "Fixture Lab"),
    ]
    lab = rows[1]
    assert lab["region"] == "norway"
    assert lab["url"] == "https://fixture-lab.no/"
    assert lab["institution_type"] == "education"
    assert lab["approved_at_iso"] == "1970-01-01T00:00:02Z"
    assert lab["source"] == "approved_proposal"
    assert "| norway | institution | 2 |" in summary.read_text("utf-8")


def test_invalid_and_older_institutions_are_skipped_with_a_reason(work: Path, capsys) -> None:
    assert MOD.main(_args(work)) == 0
    out = capsys.readouterr().out
    assert "skip institution 102: older than the stored addition for this domain" in out
    assert "skip institution 103: invalid domain" in out
    assert "skip institution 104: invalid name" in out
    assert "skip institution 106: no regions/<slug>/region.yml for this region" in out


def test_newer_decision_replaces_the_stored_addition(work: Path) -> None:
    assert MOD.main(_args(work)) == 0
    later = [
        {
            "id": 201,
            "region": "norway",
            "name": "Fixture Lab renamed",
            "url": None,
            "domain": "fixture-lab.no",
            "institution_type": "facility",
            "decided_at": 4100,
        }
    ]
    assert MOD.main(_export_with(work, later)) == 0
    lab = [r for r in _additions(work) if r["domain"] == "fixture-lab.no"]
    assert len(lab) == 1
    assert lab[0]["name"] == "Fixture Lab renamed"
    assert lab[0]["url"] == ""
    assert lab[0]["institution_type"] == "facility"


def test_missing_institutions_key_is_fine(work: Path, tmp_path: Path) -> None:
    export = json.loads((FIXTURES / "export.json").read_text("utf-8"))
    del export["institutions"]
    path = tmp_path / "no_institutions.json"
    path.write_text(json.dumps(export), "utf-8")
    assert MOD.main(["--input", str(path), *_args(work)[2:]]) == 0
    assert _additions(work) == []
    assert _state(work)["since"] == 4000


def test_second_run_is_idempotent_for_institutions(work: Path) -> None:
    assert MOD.main(_args(work)) == 0
    path = work / "curation" / "ambassador_institution_additions.csv"
    first = path.read_text("utf-8")
    assert MOD.main(_args(work)) == 0
    assert path.read_text("utf-8") == first


def test_dry_run_leaves_the_additions_file_alone(work: Path, capsys) -> None:
    path = work / "curation" / "ambassador_institution_additions.csv"
    before = path.read_bytes()
    assert MOD.main(_args(work, "--dry-run")) == 0
    assert path.read_bytes() == before
    assert "skip institution 103: invalid domain" in capsys.readouterr().out


# ---------------------------------------------------------------- group curation (CG-6b)

GROUP_A = "cg_0123456789abcdef"
GROUP_B = "cg_fedcba9876543210"
AMBASSADOR_ID = "amb_SECRET_4242"


def _ms(day: str, hour: int = 10) -> int:
    return int(datetime.fromisoformat(f"{day}T{hour:02d}:00:00+00:00").timestamp() * 1000)


def _tag(group_id: str = GROUP_A, **overrides) -> dict:
    payload = {
        "group_id": group_id,
        "status": "ambassador_tagged",
        "entity_type": "organisation",
        "sector": "ngo_civil_society",
        "plastics_centrality": "primary",
        "primary_activities": ["cleanup_removal", "education_awareness"],
        "geographic_scope": "local",
        "places": ["US-CA"],
        "website_languages": ["en"],
        "themes": ["marine_litter"],
        "evidence": [
            {
                "facet": "plastics_centrality",
                "url": "https://example.org/about",
                "accessed_at": "2026-11-20",
                "quote": "We remove plastic litter from California beaches.",
                "not_stated": False,
            },
            {
                "facet": "primary_activities",
                "url": "https://example.org/about",
                "accessed_at": "2026-11-20",
                "quote": "We run beach clean-ups.",
                "not_stated": False,
            },
        ],
        "stated_affiliations": [
            {
                "target_name": "Example Network",
                "relation": "member_of",
                "evidence": {
                    "url": "https://example.org/partners",
                    "accessed_at": "2026-11-20",
                    "quote": "We are a member of Example Network.",
                },
            }
        ],
    }
    payload.update(overrides)
    return payload


def _sub(
    sub_id: int, kind: str, payload: dict, decided_at: int, credit: str | None = "Ada Example"
) -> dict:
    return {
        "id": sub_id,
        "region": "norway",
        "stream": "knowledge",
        "kind": kind,
        "payload": payload,
        "decided_at": decided_at,
        "credit_name": credit,
        "ambassador_id": AMBASSADOR_ID,
    }


def _export(root: Path, submissions: list[dict]) -> int:
    body = {"ok": True, "submissions": submissions, "case_answers": [], "institutions": []}
    (root / "export.json").write_text(json.dumps(body), "utf-8")
    return MOD.main(_args(root))


def _csv_of(root: Path, name: str) -> list[dict]:
    with (root / "curation" / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_group_kinds_never_touch_region_yml(work: Path) -> None:
    region = work / "regions" / "norway" / "region.yml"
    before = region.read_bytes()
    assert (
        _export(
            work,
            [
                _sub(1, "group_tag", _tag(), _ms("2026-11-20")),
                _sub(
                    2,
                    "group_suggest",
                    {
                        "name": "Coast Coalition",
                        "url": "https://coast.example.org",
                        "country": "no",
                        "note": "Found on a municipal page.",
                    },
                    _ms("2026-11-21"),
                ),
            ],
        )
        == 0
    )
    assert region.read_bytes() == before
    assert len(_csv_of(work, "group_tags.csv")) == 1
    [suggestion] = _csv_of(work, "group_suggestions.csv")
    assert suggestion["country"] == "NO"


def test_newest_tag_wins_within_one_export(work: Path, capsys) -> None:
    assert (
        _export(
            work,
            [
                _sub(7, "group_tag", _tag(sector="ngo_civil_society"), _ms("2026-11-22")),
                _sub(8, "group_tag", _tag(sector="foundation"), _ms("2026-11-20")),
            ],
        )
        == 0
    )
    [row] = _csv_of(work, "group_tags.csv")
    assert row["sector"] == "ngo_civil_society"
    assert row["tagged_at"] == "2026-11-22"
    assert "skip submission 8: older than the stored tag for this group" in capsys.readouterr().out


def test_later_export_replaces_the_group_tag_and_its_affiliations(work: Path) -> None:
    assert _export(work, [_sub(1, "group_tag", _tag(), _ms("2026-11-20"))]) == 0
    assert len(_csv_of(work, "group_affiliations.csv")) == 1
    newer = _tag(sector="foundation")
    del newer["stated_affiliations"]
    assert _export(work, [_sub(2, "group_tag", newer, _ms("2026-11-25"))]) == 0
    rows = _csv_of(work, "group_tags.csv")
    assert [(r["group_id"], r["sector"], r["tagged_at"]) for r in rows] == [
        (GROUP_A, "foundation", "2026-11-25")
    ]
    assert _csv_of(work, "group_affiliations.csv") == []


def test_no_ambassador_id_or_email_reaches_the_csvs(work: Path) -> None:
    assert (
        _export(
            work,
            [
                _sub(1, "group_tag", _tag(), _ms("2026-11-20")),
                _sub(2, "group_tag", _tag(GROUP_B), _ms("2026-11-20"), credit=None),
                _sub(
                    3,
                    "group_suggest",
                    {"name": "Coast Group", "url": "https://coast.example.org"},
                    _ms("2026-11-20"),
                ),
            ],
        )
        == 0
    )
    for name in ("group_tags.csv", "group_affiliations.csv", "group_suggestions.csv"):
        text = (work / "curation" / name).read_text("utf-8")
        assert AMBASSADOR_ID not in text
        assert "@" not in text
    credits = {r["group_id"]: r["credit"] for r in _csv_of(work, "group_tags.csv")}
    assert credits == {GROUP_A: "Ada Example", GROUP_B: "a local ambassador"}


def test_invalid_group_rows_are_skipped_with_reason(work: Path, capsys) -> None:
    evidence = _tag()["evidence"]
    email_quote = {**evidence[0], "quote": "Write to info@example.org for details."}
    assert (
        _export(
            work,
            [
                _sub(1, "group_tag", _tag(GROUP_B, sector="not_a_sector"), _ms("2026-11-20")),
                _sub(2, "group_tag", _tag(GROUP_B, evidence=[evidence[0]]), _ms("2026-11-20")),
                _sub(
                    3,
                    "group_tag",
                    _tag(GROUP_B, evidence=[email_quote, evidence[1]]),
                    _ms("2026-11-20"),
                ),
                _sub(
                    4,
                    "group_suggest",
                    {"name": "Coast Group", "url": "https://coast.example.org", "country": "USA"},
                    _ms("2026-11-20"),
                ),
                _sub(5, "group_tag", _tag(), _ms("2026-11-20")),
            ],
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "skip submission 1: invalid sector" in out
    assert "skip submission 2: invalid evidence" in out
    assert "skip submission 3: invalid email" in out
    assert "skip submission 4: invalid country" in out
    assert [r["group_id"] for r in _csv_of(work, "group_tags.csv")] == [GROUP_A]
    assert not (work / "curation" / "group_suggestions.csv").exists()


def test_affiliations_and_suggestions_are_written(work: Path) -> None:
    suggestion = {
        "name": "Coast Group",
        "url": "https://coast.example.org",
        "country": "no",
        "note": "Found on a municipal page.",
    }
    assert (
        _export(
            work,
            [
                _sub(1, "group_tag", _tag(), _ms("2026-11-20")),
                _sub(2, "group_suggest", suggestion, _ms("2026-11-21")),
            ],
        )
        == 0
    )
    [aff] = _csv_of(work, "group_affiliations.csv")
    assert aff["group_id"] == GROUP_A
    assert aff["target_name"] == "Example Network"
    assert aff["relation"] == "member_of"
    assert aff["evidence_quote"] == "We are a member of Example Network."
    [row] = _csv_of(work, "group_suggestions.csv")
    assert row["name"] == "Coast Group"
    assert row["country"] == "NO"
    assert row["suggested_at"] == "2026-11-21"


def test_not_an_organisation_row_is_exported_without_facets(work: Path, capsys) -> None:
    flag = {
        "group_id": GROUP_A,
        "status": "cannot_determine",
        "cannot_determine_reason": "not_an_organisation",
        "not_an_organisation": True,
    }
    assert (
        _export(
            work,
            [
                _sub(1, "group_tag", flag, _ms("2026-11-20")),
                _sub(2, "group_tag", _tag(GROUP_B, not_an_organisation=True), _ms("2026-11-20")),
            ],
        )
        == 0
    )
    assert "skip submission 2: invalid entity_type" in capsys.readouterr().out
    [row] = _csv_of(work, "group_tags.csv")
    assert row["not_an_organisation"] == "true"
    assert row["cannot_determine_reason"] == "not_an_organisation"
    assert row["sector"] == ""


def _names(root: Path) -> list[dict]:
    path = root / "curation" / "group_name_corrections.csv"
    return _csv_of(root, "group_name_corrections.csv") if path.exists() else []


def test_approved_name_correction_is_written_to_its_own_csv(work: Path) -> None:
    assert (
        _export(
            work,
            [
                _sub(
                    1,
                    "group_tag",
                    _tag(name_correction="  Coastal Cleanup Collective "),
                    _ms("2026-11-20"),
                )
            ],
        )
        == 0
    )
    assert _names(work) == [
        {"group_id": GROUP_A, "name": "Coastal Cleanup Collective", "submitted_at": "2026-11-20"}
    ]
    [row] = _csv_of(work, "group_tags.csv")
    assert "name_correction" not in row


def test_name_correction_is_kept_for_cannot_determine(work: Path) -> None:
    tag = {
        "group_id": GROUP_A,
        "status": "cannot_determine",
        "cannot_determine_reason": "no_web_presence",
        "name_correction": "Real Group Name",
    }
    assert _export(work, [_sub(1, "group_tag", tag, _ms("2026-11-20"))]) == 0
    assert _names(work) == [
        {"group_id": GROUP_A, "name": "Real Group Name", "submitted_at": "2026-11-20"}
    ]


def test_non_organisation_removal_clears_only_its_name_correction(work: Path) -> None:
    assert (
        _export(
            work,
            [
                _sub(1, "group_tag", _tag(name_correction="Old Display Name"), _ms("2026-11-20")),
                _sub(
                    2, "group_tag", _tag(GROUP_B, name_correction="Other Group"), _ms("2026-11-20")
                ),
            ],
        )
        == 0
    )
    removal = {
        "group_id": GROUP_A,
        "status": "cannot_determine",
        "cannot_determine_reason": "not_an_organisation",
        "not_an_organisation": True,
        "name_correction": "Personal Name",
    }
    assert _export(work, [_sub(3, "group_tag", removal, _ms("2026-11-21"))]) == 0
    assert _names(work) == [
        {"group_id": GROUP_B, "name": "Other Group", "submitted_at": "2026-11-20"}
    ]


def test_latest_name_correction_wins(work: Path) -> None:
    assert (
        _export(
            work,
            [
                _sub(1, "group_tag", _tag(name_correction="Older Name"), _ms("2026-11-20")),
                _sub(2, "group_tag", _tag(name_correction="Newer Name"), _ms("2026-11-22")),
                _sub(3, "group_tag", _tag(GROUP_B), _ms("2026-11-23")),
            ],
        )
        == 0
    )
    assert _names(work) == [
        {"group_id": GROUP_A, "name": "Newer Name", "submitted_at": "2026-11-22"}
    ]


def test_invalid_name_correction_is_skipped_with_reason(work: Path, capsys) -> None:
    assert (
        _export(
            work,
            [
                _sub(1, "group_tag", _tag(name_correction=""), _ms("2026-11-20")),
                _sub(2, "group_tag", _tag(name_correction="<i>Name</i>"), _ms("2026-11-20")),
                _sub(
                    3, "group_tag", _tag(name_correction="write ada@example.org"), _ms("2026-11-20")
                ),
                _sub(4, "group_tag", _tag(name_correction=7), _ms("2026-11-20")),
            ],
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "skip submission 1: invalid name_correction" in out
    assert "skip submission 2: invalid name_correction" in out
    assert "skip submission 3: invalid name_correction" in out
    assert "skip submission 4: invalid name_correction" in out
    assert _names(work) == []
    assert not (work / "curation" / "group_tags.csv").exists()


def test_name_corrections_file_is_not_written_when_there_are_none(work: Path) -> None:
    assert _export(work, [_sub(1, "group_tag", _tag(), _ms("2026-11-20"))]) == 0
    assert (work / "curation" / "group_name_corrections.csv").exists() is False


# ---------------------------------------------------------------- group pairs and reviews (CG-7b)

TIER1 = ("entity_type", "sector", "plastics_centrality", "primary_activities", "geographic_scope")


def _side(**overrides) -> dict:
    side = {
        "entity_type": "organisation",
        "sector": "ngo_civil_society",
        "plastics_centrality": "primary",
        "primary_activities": ["advocacy_campaigning", "education_awareness"],
        "geographic_scope": "local",
    }
    side.update(overrides)
    return side


def _pair(group_id: str = GROUP_A, paired_at: int | None = None, **overrides) -> dict:
    item = {
        "group_id": group_id,
        "region": "california",
        "paired_at": _ms("2026-11-24") if paired_at is None else paired_at,
        "value_a": _side(),
        "value_b": _side(),
    }
    item.update(overrides)
    return item


def _review(group_id: str = GROUP_A, facet: str = "sector", **overrides) -> dict:
    item = {
        "group_id": group_id,
        "region": "california",
        "facet": facet,
        "outcome": "agree",
        "reason_code": None,
        "original_value": "ngo_civil_society",
        "reviewed_value": "ngo_civil_society",
        "reviewed_at": _ms("2026-11-25"),
    }
    item.update(overrides)
    return item


def _group_export(root: Path, pairs=None, reviews=None, *extra: str) -> int:
    body: dict = {"ok": True, "submissions": [], "case_answers": [], "institutions": []}
    if pairs is not None:
        body["group_pairs"] = pairs
    if reviews is not None:
        body["group_reviews"] = reviews
    (root / "export.json").write_text(json.dumps(body), "utf-8")
    return MOD.main(_args(root, *extra))


def _text(root: Path, name: str) -> str:
    return (root / "curation" / name).read_text("utf-8")


def test_pairs_are_written_as_five_tier1_rows(work: Path) -> None:
    assert _group_export(work, [_pair()]) == 0
    rows = _csv_of(work, "group_double_tags.csv")
    assert [r["facet"] for r in rows] == list(TIER1)
    assert all(r["group_id"] == GROUP_A for r in rows)
    by_facet = {r["facet"]: r for r in rows}
    assert by_facet["primary_activities"]["value_a"] == "advocacy_campaigning;education_awareness"
    assert by_facet["primary_activities"]["value_b"] == "advocacy_campaigning;education_awareness"
    assert by_facet["sector"]["value_a"] == "ngo_civil_society"


def test_later_export_replaces_a_pair(work: Path) -> None:
    assert _group_export(work, [_pair()]) == 0
    newer = _pair(paired_at=_ms("2026-11-26"), value_b=_side(sector="foundation"))
    assert _group_export(work, [newer]) == 0
    rows = {r["facet"]: r for r in _csv_of(work, "group_double_tags.csv")}
    assert len(rows) == 5
    assert rows["sector"]["value_b"] == "foundation"


def test_pairs_in_one_export_keep_the_later_paired_at(work: Path) -> None:
    later = _pair(paired_at=_ms("2026-11-26"), value_b=_side(sector="foundation"))
    earlier = _pair(paired_at=_ms("2026-11-24"), value_b=_side(sector="government"))
    assert _group_export(work, [later, earlier]) == 0
    rows = {r["facet"]: r for r in _csv_of(work, "group_double_tags.csv")}
    assert rows["sector"]["value_b"] == "foundation"


def test_reviews_agree_and_edit_are_written_with_iso_time(work: Path) -> None:
    edit = _review(
        GROUP_B,
        "sector",
        outcome="edit",
        reason_code="evidence_contradicts",
        original_value="ngo_civil_society",
        reviewed_value="foundation",
        reviewed_at=_ms("2026-11-25", 14),
    )
    agree = _review(GROUP_A, "geographic_scope", original_value="local", reviewed_value="local")
    assert _group_export(work, None, [edit, agree]) == 0
    rows = _csv_of(work, "group_reviews.csv")
    assert [(r["group_id"], r["facet"]) for r in rows] == [
        (GROUP_A, "geographic_scope"),
        (GROUP_B, "sector"),
    ]
    assert rows[0] == {
        "group_id": GROUP_A,
        "facet": "geographic_scope",
        "outcome": "agree",
        "reason_code": "",
        "reviewed_at": "2026-11-25T10:00:00Z",
        "reviewed_value": "local",
    }
    assert rows[1]["outcome"] == "edit"
    assert rows[1]["reason_code"] == "evidence_contradicts"
    assert rows[1]["reviewed_at"] == "2026-11-25T14:00:00Z"
    assert rows[1]["reviewed_value"] == "foundation"


def test_newest_review_wins_and_an_older_one_is_skipped(work: Path, capsys) -> None:
    newer = _review(
        outcome="edit",
        reason_code="slip",
        reviewed_value="foundation",
        reviewed_at=_ms("2026-11-26"),
    )
    older = _review(outcome="agree", reviewed_at=_ms("2026-11-20"))
    assert _group_export(work, None, [newer, older]) == 0
    [row] = _csv_of(work, "group_reviews.csv")
    assert (row["outcome"], row["reason_code"]) == ("edit", "slip")
    out = capsys.readouterr().out
    assert "skip group review: older than the stored review for this facet" in out


REVIEW_COLUMNS_LINE = "group_id,facet,outcome,reason_code,reviewed_at,reviewed_value"


def test_reviews_write_the_reviewed_value_column(work: Path) -> None:
    review = _review(outcome="edit", reason_code="guide_rule", reviewed_value="foundation")
    assert _group_export(work, None, [review]) == 0
    assert _text(work, "group_reviews.csv").splitlines()[0] == REVIEW_COLUMNS_LINE
    [row] = _csv_of(work, "group_reviews.csv")
    assert row["reviewed_value"] == "foundation"


def test_agree_writes_the_joined_activities_as_reviewed_value(work: Path) -> None:
    activities = ["advocacy_campaigning", "education_awareness"]
    review = _review(
        facet="primary_activities",
        original_value=activities,
        reviewed_value=activities,
    )
    assert _group_export(work, None, [review]) == 0
    [row] = _csv_of(work, "group_reviews.csv")
    assert row["outcome"] == "agree"
    assert row["reviewed_value"] == "advocacy_campaigning;education_awareness"


def test_five_column_review_file_is_upgraded_and_keeps_its_rows(work: Path) -> None:
    old_row = f"{GROUP_A},sector,agree,,{MOD.iso_from_ms(_ms('2026-11-20'))}"
    (work / "curation" / "group_reviews.csv").write_text(
        "group_id,facet,outcome,reason_code,reviewed_at\n" + old_row + "\n", "utf-8"
    )
    review = _review(facet="geographic_scope", original_value="local", reviewed_value="local")
    assert _group_export(work, None, [review]) == 0
    assert _text(work, "group_reviews.csv").splitlines()[0] == REVIEW_COLUMNS_LINE
    rows = {row["facet"]: row for row in _csv_of(work, "group_reviews.csv")}
    assert set(rows) == {"sector", "geographic_scope"}
    assert rows["sector"]["reviewed_value"] == ""
    assert rows["geographic_scope"]["reviewed_value"] == "local"


@pytest.mark.parametrize(
    ("pair_mutation", "review_mutation", "reason"),
    [
        ({"value_b": _side(sector="not_a_sector")}, None, "invalid sector in value_b"),
        (
            {"value_a": {k: v for k, v in _side().items() if k != "sector"}},
            None,
            "value_a is missing sector",
        ),
        (
            {"value_a": _side(primary_activities=["other", "other"])},
            None,
            "invalid primary_activities in value_a",
        ),
        (
            None,
            {"outcome": "edit", "reason_code": None, "reviewed_value": "foundation"},
            "edit needs a reason_code from review_reason",
        ),
        (
            None,
            {"outcome": "edit", "reason_code": "not_a_reason", "reviewed_value": "foundation"},
            "edit needs a reason_code from review_reason",
        ),
        (
            None,
            {"outcome": "agree", "reason_code": "slip"},
            "agree must not carry a reason_code",
        ),
        (
            None,
            {"outcome": "edit", "reason_code": "slip", "reviewed_value": "ngo_civil_society"},
            "edit needs reviewed_value different from original_value",
        ),
        (None, {"facet": "legal_form"}, "invalid facet"),
    ],
)
def test_invalid_pair_and_review_items_are_skipped_with_a_reason(
    work: Path, capsys, pair_mutation, review_mutation, reason
) -> None:
    pairs = [_pair(**pair_mutation)] if pair_mutation else None
    reviews = [_review(**review_mutation)] if review_mutation else None
    assert _group_export(work, pairs, reviews) == 0
    kind = "pair" if pairs else "review"
    assert f"skip group {kind}: {reason}" in capsys.readouterr().out
    assert _text(work, "group_double_tags.csv") == DOUBLE_TAG_HEADER
    assert _text(work, "group_reviews.csv") == REVIEW_HEADER


def test_invalid_group_id_and_missing_time_are_skipped(work: Path, capsys) -> None:
    bad = _pair("cg_NOT_A_HEX_ID!!!!")
    no_time = {k: v for k, v in _pair().items() if k != "paired_at"}
    assert _group_export(work, [bad, no_time]) == 0
    out = capsys.readouterr().out
    assert "skip group pair: invalid group_id" in out
    assert "skip group pair: invalid paired_at" in out
    assert _text(work, "group_double_tags.csv") == DOUBLE_TAG_HEADER


def test_missing_group_keys_leave_both_files_byte_identical(work: Path) -> None:
    names = ("group_double_tags.csv", "group_reviews.csv")
    before = {name: (work / "curation" / name).read_bytes() for name in names}
    assert _group_export(work) == 0
    for name in names:
        assert (work / "curation" / name).read_bytes() == before[name]


def test_group_pairs_and_reviews_hold_no_ambassador_id_or_email(work: Path) -> None:
    pair = _pair(ambassador_id=AMBASSADOR_ID, credit_name="Ada Example")
    review = _review(
        outcome="edit",
        reason_code="other",
        reviewed_value="foundation",
        note="write to info@example.org",
        ambassador_id=AMBASSADOR_ID,
    )
    assert _group_export(work, [pair], [review]) == 0
    for name in ("group_double_tags.csv", "group_reviews.csv"):
        text = _text(work, name)
        assert AMBASSADOR_ID not in text
        assert "ambassador" not in text.lower()
        assert "@" not in text
        assert "Ada Example" not in text


def test_dry_run_writes_no_group_pair_or_review_files(work: Path, capsys) -> None:
    body = {
        "ok": True,
        "submissions": [],
        "case_answers": [],
        "institutions": [],
        "group_pairs": [_pair()],
        "group_reviews": [_review()],
    }
    (work / "export.json").write_text(json.dumps(body), "utf-8")
    assert MOD.main(_args(work, "--dry-run")) == 0
    assert _text(work, "group_double_tags.csv") == DOUBLE_TAG_HEADER
    assert _text(work, "group_reviews.csv") == REVIEW_HEADER
    assert _state(work)["since"] == 0
    assert "dry run: nothing written" in capsys.readouterr().out


def test_watermark_advances_to_the_newest_paired_or_reviewed_time(work: Path) -> None:
    pair = _pair(paired_at=_ms("2026-11-22"))
    review = _review(reviewed_at=_ms("2026-11-25", 16))
    assert _group_export(work, [pair], [review]) == 0
    assert _state(work)["since"] == _ms("2026-11-25", 16)


def test_group_pairs_before_the_watermark_are_not_reapplied(work: Path) -> None:
    state = {"since": _ms("2026-11-25"), "boundary_ids": []}
    (work / "curation" / "ambassador_export_state.json").write_text(json.dumps(state), "utf-8")
    assert _group_export(work, [_pair(paired_at=_ms("2026-11-20"))]) == 0
    assert _text(work, "group_double_tags.csv") == DOUBLE_TAG_HEADER


def test_summary_counts_group_pairs_and_reviews(work: Path) -> None:
    summary = work / "summary.md"
    reviews = [
        _review(),
        _review(facet="geographic_scope", original_value="local", reviewed_value="local"),
    ]
    code = _group_export(work, [_pair()], reviews, "--summary-file", str(summary))
    assert code == 0
    text = summary.read_text("utf-8")
    assert "| groups | group_pair | 1 |" in text
    assert "| groups | group_review | 2 |" in text


def test_group_loaders_in_build_groups_accept_the_written_files(work: Path) -> None:
    review = _review(outcome="edit", reason_code="guide_rule", reviewed_value="foundation")
    assert _group_export(work, [_pair()], [review]) == 0
    spec = importlib.util.spec_from_file_location(
        "build_groups", REPO_ROOT / "scripts" / "build_groups.py"
    )
    assert spec is not None and spec.loader is not None
    build_groups = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_groups)
    doubles = build_groups.load_double_tags(work / "curation")
    reviews = build_groups.load_reviews(work / "curation")
    assert [r["facet"] for r in doubles] == list(TIER1)
    assert [(r["outcome"], r["reason_code"]) for r in reviews] == [("edit", "guide_rule")]


def test_tier1_order_matches_the_group_build() -> None:
    from atlas.groups.build import TIER1_FACETS

    assert tuple(MOD.GROUP_TIER1) == tuple(TIER1_FACETS) == TIER1
