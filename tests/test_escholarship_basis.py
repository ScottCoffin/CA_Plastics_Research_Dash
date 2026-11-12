"""ESCH-CA: eScholarship UC evidence as a California basis (atlas.ingest.normalize)."""

from __future__ import annotations

from atlas.ingest.normalize import CA_BASIS_ESCHOLARSHIP, _apply_escholarship, _name_key


def _row(work_id: str, author_id: str, basis: str = "") -> dict:
    return {"work_id": work_id, "author_id": author_id, "ca_basis": basis}


def test_name_key_matches_both_name_orders() -> None:
    assert _name_key("Rochman, Chelsea M") == _name_key("Chelsea M. Rochman") == "rochman c"


def test_sole_thesis_author_and_known_ca_coauthor_get_the_basis() -> None:
    works = [{"work_id": "W1"}, {"work_id": "W2"}, {"work_id": "W3"}]
    authorships = [
        _row("W1", "A1"),  # sole author of a UC thesis
        _row("W2", "A2"),  # known CA expert, name listed on the deposit
        _row("W2", "A3"),  # unknown co-author: stays empty
        _row("W3", "A4"),  # UC-hosted journal: no evidence passed in
    ]
    state = {
        "A1": {"name": "Miriam C. Goldstein", "ca_works": set()},
        "A2": {"name": "Randy A. Dahlgren", "ca_works": {"W9"}},
        "A3": {"name": "Mingzhu Fang", "ca_works": set()},
        "A4": {"name": "Someone Else", "ca_works": {"W8"}},
    }
    evidence = {
        "W1": {"ca_evidence": "etd", "author_names": ["Goldstein, Miriam Chanita"]},
        "W2": {
            "ca_evidence": "uc_oa_policy",
            "author_names": ["Fang, Mingzhu", "Dahlgren, Randy A"],
        },
    }
    flagged = _apply_escholarship(works, authorships, state, evidence)
    assert flagged == {"W1", "W2"}
    assert [r["ca_basis"] for r in authorships] == [
        CA_BASIS_ESCHOLARSHIP,
        CA_BASIS_ESCHOLARSHIP,
        "",
        "",
    ]
    assert "W2" in state["A2"]["ca_works"] and "W1" in state["A1"]["ca_works"]


def test_existing_basis_is_never_overwritten() -> None:
    authorships = [_row("W1", "A1", "registry")]
    state = {"A1": {"name": "A B", "ca_works": {"W1"}}}
    _apply_escholarship(
        [{"work_id": "W1"}], authorships, state, {"W1": {"ca_evidence": "etd", "author_names": []}}
    )
    assert authorships[0]["ca_basis"] == "registry"


def test_redact_emails() -> None:
    from atlas.ingest.normalize import redact_emails

    text = "The 5 Gyres Institute, Santa Monica, CA, USA. vmf713@uri.edu"
    assert redact_emails(text) == "The 5 Gyres Institute, Santa Monica, CA, USA. [email removed]"
    assert redact_emails("") == ""


def test_raw_rows_never_store_emails() -> None:
    from atlas.ingest.openalex import _row_from_work

    work = {
        "id": "https://openalex.org/W1",
        "authorships": [{"raw_affiliation_strings": ["5 Gyres, Santa Monica, CA. a.b@uri.edu"]}],
    }
    row = _row_from_work(work, run_id="t", fetched_at_utc="2026-11-12")
    assert "@uri.edu" not in row["raw_json"] and "[email removed]" in row["raw_json"]
