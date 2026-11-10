from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("check_s10_2", REPO / "scripts" / "check_s10_2.py")
check = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(check)


def test_required_governance_files_exist():
    assert check.check_required_files(REPO) == []


def test_citation_cff_parses_with_required_keys():
    assert check.check_citation(REPO) == []


def test_citation_cff_uses_mit_and_site_url():
    import yaml

    data = yaml.safe_load((REPO / "CITATION.cff").read_text(encoding="utf-8"))
    assert data["cff-version"] == "1.2.0"
    assert data["license"] == "MIT"
    assert data["url"] == "https://plastiverse.live/"


def test_checklist_evidence_links_resolve():
    assert check.check_checklist(REPO) == []


def test_checklist_signoff_cells_are_blank():
    rows = check.checklist_rows(REPO)
    assert rows, "checklist has no data rows"
    assert all(cells[3] == "" and cells[4] == "" for cells in rows)


def test_data_dictionary_names_every_public_payload():
    assert check.check_dictionary(REPO) == []


def test_expected_dictionary_names_cover_site_data():
    names = check.expected_dictionary_names(REPO)
    for top in ("index.json", "aggregates.json", "grants.json", "monitoring.json"):
        assert top in names
    assert "feed.xml" in names


def test_privacy_scan_is_clean_for_public_payloads():
    counts, hits = check.privacy_scan(REPO)
    assert counts["files"] >= 1
    assert hits == [], "privacy scan found matches; report the field, not the value"


def test_regex_flags_synthetic_email_and_phone_without_echoing_values():
    email = "reach me at person@example.org"
    phone = "call 555-123-4567 today"
    assert check.EMAIL_RE.search(email)
    assert check.PHONE_RE.search(phone)
    assert not check.EMAIL_RE.search("doi 10.1016/j.marpolbul.2020.111111")
    assert not check.PHONE_RE.search("year 2026-09-20 value 607,490")


def test_scan_file_reports_field_path_not_value(tmp_path):
    payload = {"authors": [{"name": "Jane Roe", "contact": "jane@example.org"}]}
    repo = tmp_path
    (repo / "site" / "data").mkdir(parents=True)
    target = repo / "site" / "data" / "sample.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    hits = check.scan_file(target, repo)
    assert hits == [("site/data/sample.json", "authors[].contact", "email")]
    assert all("jane@example.org" not in str(hit) for hit in hits)


def test_scan_feed_text_detects_phone(tmp_path):
    repo = tmp_path
    (repo / "site").mkdir()
    feed = repo / "site" / "feed.xml"
    feed.write_text("<feed><summary>call 555-123-4567</summary></feed>", encoding="utf-8")
    hits = check.scan_file(feed, repo)
    assert ("site/feed.xml", "feed text", "phone") in hits


def test_missing_citation_is_reported(tmp_path):
    (tmp_path / "CITATION.cff").write_text("title: only a title\n", encoding="utf-8")
    errors = check.check_citation(tmp_path)
    assert any("cff-version" not in e and "missing key: authors" in e for e in errors)


@pytest.mark.parametrize("name", ["docs/CORRECTIONS.md", "docs/PRIVACY_REVIEW.md"])
def test_governance_docs_are_nonempty(name):
    assert len((REPO / name).read_text(encoding="utf-8").strip()) > 200
