"""Tests for the owner-only expert contact builder (S9.6a). Synthetic fixtures only."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from atlas.outreach.contacts import (
    CONTACT_FIELDS,
    contacts_from_openalex_works,
    extract_emails,
    merge_opt_outs,
    write_contacts,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "build_outreach_contacts.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("build_outreach_contacts", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _work(*authorships: dict) -> dict:
    return {"id": "https://openalex.org/W1", "authorships": list(authorships)}


def _authorship(author_id: str, *affiliations: str) -> dict:
    return {
        "author": {"id": f"https://openalex.org/{author_id}", "display_name": "Synthetic"},
        "raw_affiliation_strings": list(affiliations),
    }


def test_extract_emails_lowercases_dedupes_and_keeps_order() -> None:
    text = (
        "Electronic address: Jane.Doe@Uni-Fixture.edu. Also jane.doe@uni-fixture.edu; "
        "second: alex@lab-fixture.org"
    )
    assert extract_emails(text) == ["jane.doe@uni-fixture.edu", "alex@lab-fixture.org"]


@pytest.mark.parametrize(
    "text",
    [
        "contact noreply@uni-fixture.edu",
        "no-reply@uni-fixture.edu",
        "someone@example.com",
        "someone@mail.example.org",
        "logo@2x.png",
        "icon@photo.jpg",
    ],
)
def test_extract_emails_rejects_placeholders_and_images(text: str) -> None:
    assert extract_emails(text) == []


def test_extract_emails_handles_empty_text() -> None:
    assert extract_emails("") == []
    assert extract_emails("no address here") == []


def test_emails_are_assigned_only_to_their_own_authorship() -> None:
    works = [
        _work(
            _authorship("A100", "Dept Chem, UC Fixture. jane@uni-fixture.edu"),
            _authorship("A200", "Dept Civil, UC Fixture"),
            _authorship("A300", "Lab X. alex@lab-fixture.org"),
        ),
        _work(_authorship("A200", "Other place. kim@uni-fixture.edu")),
    ]
    result = contacts_from_openalex_works(works, {"A100", "A200", "A300"})
    assert result == {
        "A100": {"jane@uni-fixture.edu"},
        "A200": {"kim@uni-fixture.edu"},
        "A300": {"alex@lab-fixture.org"},
    }


def test_coauthor_without_email_gets_nothing_from_neighbour() -> None:
    works = [
        _work(
            _authorship("A100", "Lab. jane@uni-fixture.edu"),
            _authorship("A200", "Lab, no contact details"),
        )
    ]
    result = contacts_from_openalex_works(works, {"A200"})
    assert result == {}


def test_non_expert_and_malformed_entries_are_ignored() -> None:
    works = [
        "not a dict",
        {"authorships": "not a list"},
        _work(
            _authorship("A999", "Lab. outsider@uni-fixture.edu"),
            {"author": None, "raw_affiliation_strings": ["x@uni-fixture.edu"]},
            {"author": {"id": "https://openalex.org/A100"}, "raw_affiliation_strings": "bad"},
            {"author": {"id": "https://openalex.org/A100"}, "raw_affiliation_strings": [7]},
        ),
    ]
    assert contacts_from_openalex_works(works, {"A100"}) == {}


def test_write_contacts_accepts_path_inside_private_dir(tmp_path: Path) -> None:
    root = tmp_path
    out = root / "data" / "private" / "outreach_contacts.csv"
    rows = [
        {
            "author_id": "A100",
            "name": "Synthetic One",
            "email": "jane@uni-fixture.edu",
            "source": "openalex_affiliation",
            "first_seen_utc": "2026-11-12T00:00:00Z",
            "extra": "dropped",
        }
    ]
    assert write_contacts(out, rows, root=root) == 1
    with out.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == CONTACT_FIELDS
        assert [dict(r) for r in reader] == [
            {
                "author_id": "A100",
                "name": "Synthetic One",
                "email": "jane@uni-fixture.edu",
                "source": "openalex_affiliation",
                "first_seen_utc": "2026-11-12T00:00:00Z",
            }
        ]


@pytest.mark.parametrize(
    "relative",
    [
        "elsewhere/outreach_contacts.csv",
        "data/outreach_contacts.csv",
        "data/private",
        "data/private/../public/outreach_contacts.csv",
        "data/private2/outreach_contacts.csv",
    ],
)
def test_write_contacts_refuses_paths_outside_private_dir(tmp_path: Path, relative: str) -> None:
    root = tmp_path
    with pytest.raises(ValueError):
        write_contacts(root / relative, [], root=root)
    assert not (root / "elsewhere").exists()
    assert not (root / "data" / "public").exists()


def test_write_contacts_default_root_refuses_tmp_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_contacts(tmp_path / "outreach_contacts.csv", [])


def test_merge_opt_outs_removes_by_email_and_author(tmp_path: Path) -> None:
    opt_out = tmp_path / "outreach_optout.csv"
    opt_out.write_text(
        "email,author_id\nJane@Uni-Fixture.edu,\n,https://openalex.org/A300\n",
        encoding="utf-8",
    )
    rows = [
        {"author_id": "A100", "email": "jane@uni-fixture.edu"},
        {"author_id": "A200", "email": "kim@uni-fixture.edu"},
        {"author_id": "A300", "email": "alex@lab-fixture.org"},
        {"author_id": "A300", "email": "second@lab-fixture.org"},
    ]
    kept, removed = merge_opt_outs(rows, opt_out)
    assert removed == 3
    assert kept == [{"author_id": "A200", "email": "kim@uni-fixture.edu"}]


def test_merge_opt_outs_missing_file_removes_nothing(tmp_path: Path) -> None:
    rows = [{"author_id": "A100", "email": "jane@uni-fixture.edu"}]
    kept, removed = merge_opt_outs(rows, tmp_path / "absent.csv")
    assert removed == 0
    assert kept == rows


def _synthetic_snapshot(root: Path) -> None:
    raw = root / "data" / "raw" / "openalex_works"
    raw.mkdir(parents=True)
    page = {
        "results": [
            _work(
                _authorship("A100", "Lab. jane@uni-fixture.edu"),
                _authorship("A200", "Lab. kim@uni-fixture.edu"),
            )
        ]
    }
    (raw / "page_1.json").write_text(json.dumps(page), encoding="utf-8")
    bare = [_work(_authorship("A300", "Lab. alex@lab-fixture.org"))]
    (raw / "bare_list.json").write_text(json.dumps(bare), encoding="utf-8")
    (raw / "broken.json").write_text("{not json", encoding="utf-8")
    index = {
        "authors": [
            {"author_id": "A100", "name": "Jane Synthetic"},
            {"author_id": "https://openalex.org/A200", "name": "Kim Synthetic"},
            {"author_id": "A300", "name": "Alex Synthetic"},
            {"author_id": "A400", "name": "Synthetic Four"},
        ]
    }
    (root / "site" / "data").mkdir(parents=True)
    (root / "site" / "data" / "index.json").write_text(json.dumps(index), encoding="utf-8")
    private = root / "data" / "private"
    private.mkdir(parents=True)
    (private / "outreach_optout.csv").write_text("email\nkim@uni-fixture.edu\n", encoding="utf-8")


def test_script_writes_contacts_and_prints_counts_only(tmp_path: Path, capsys) -> None:
    _synthetic_snapshot(tmp_path)
    script = _load_script()
    assert script.main([], root=tmp_path) == 0

    out = capsys.readouterr().out
    assert "@" not in out
    assert out.splitlines() == [
        "experts total: 4",
        "experts with >=1 email: 2",
        "emails total: 2",
        "opt-outs removed: 1",
    ]

    written = tmp_path / "data" / "private" / "outreach_contacts.csv"
    with written.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {(r["author_id"], r["email"]) for r in rows} == {
        ("A100", "jane@uni-fixture.edu"),
        ("A300", "alex@lab-fixture.org"),
    }


def test_script_dry_run_writes_nothing(tmp_path: Path, capsys) -> None:
    _synthetic_snapshot(tmp_path)
    script = _load_script()
    assert script.main(["--dry-run"], root=tmp_path) == 0

    out = capsys.readouterr().out
    assert "@" not in out
    assert "emails total: 2" in out
    assert not (tmp_path / "data" / "private" / "outreach_contacts.csv").exists()


def test_email_matches_name() -> None:
    from atlas.outreach.contacts import email_matches_name

    assert email_matches_name("jdoe@ucdavis.edu", "Jane Doe")
    assert email_matches_name("chelsea.rochman@utoronto.ca", "Chelsea M. Rochman")
    assert email_matches_name("crochman@x.edu", "Chelsea Rochman")
    assert not email_matches_name("someone.else@x.edu", "Chelsea Rochman")
    assert email_matches_name("munoz@x.edu", "Ana Muñoz")
