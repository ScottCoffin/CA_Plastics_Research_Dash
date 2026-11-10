"""Tests for the S11.4 Atom digest feed (synthetic payloads; no network, no corpus data)."""

from __future__ import annotations

import copy
import random
import xml.etree.ElementTree as ET
from pathlib import Path

from atlas.build import feed as fd

ATOM = "{http://www.w3.org/2005/Atom}"
ROOT = Path(__file__).resolve().parents[1]


def _work(i: int, year: int = 2023, **overrides) -> dict:
    row = {
        "work_id": f"W{9000000000 + i}",
        "title": f"Plastic study {i}",
        "year": year,
        "type": "article",
        "plastic_related": True,
        "needs_review": False,
        "ca_any_author": True,
        "ca_led": False,
        "author_ids": ["A1"],
        "institution_ids": ["I1"],
    }
    row.update(overrides)
    return row


def _award(i: int, start: str | None = "2024-01-01", **overrides) -> dict:
    row = {
        "grant_key": f"{i:016x}",
        "source": "nsf_awards",
        "title": f"Award {i}",
        "start": start,
        "url": f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={i}",
        "funder": "NSF",
        "funder_chain": ["NSF", "CBET"],
        "org": "UNIVERSITY OF CALIFORNIA",
        "amount": 1000.0 + i,
        "currency": "USD",
        "amount_basis": "NSF estimatedTotalAmt.",
        "plastic_related": True,
    }
    row.update(overrides)
    return row


def _index(works: list[dict]) -> dict:
    return {
        "schema_version": "s3.1",
        "authors": [{"author_id": "A1", "name": "Alice California"}],
        "works": works,
    }


def _grants(rows: list[dict]) -> dict:
    return {"schema_version": "s8.10", "rows": rows}


def _parse(data: bytes) -> ET.Element:
    return ET.fromstring(data)


def _entries(root: ET.Element) -> list[ET.Element]:
    return root.findall(f"{ATOM}entry")


def _term(entry: ET.Element) -> str:
    return entry.find(f"{ATOM}category").get("term")


def test_output_is_well_formed_atom_utf8() -> None:
    data = fd.render_feed(_index([_work(1)]), _grants([_award(1)]))
    assert data.startswith(b'<?xml version="1.0" encoding="UTF-8"?>')
    root = _parse(data)
    assert root.tag == f"{ATOM}feed"
    assert root.find(f"{ATOM}id").text == fd.FEED_ID
    assert root.find(f"{ATOM}link[@rel='self']").get("href") == fd.FEED_URL
    data.decode("utf-8")


def test_paper_selection_rule_and_entry_fields() -> None:
    works = [
        _work(1),
        _work(2, ca_any_author=False, ca_led=True),
        _work(3, ca_any_author=False, ca_led=False),
        _work(4, plastic_related=False),
        _work(5, needs_review=True),
        _work(6, year=None),
    ]
    papers = fd.select_papers(_index(works))
    assert [p["id"].rsplit("/", 1)[1] for p in papers] == ["W9000000002", "W9000000001"]
    first = papers[1]
    assert first["link"] == "https://openalex.org/W9000000001"
    assert first["updated"] == "2023-01-01T00:00:00Z"
    assert first["id"] == "tag:scottcoff.in,2026:ca-plastics-atlas/work/W9000000001"
    assert "Alice California" in first["summary"]
    assert "Institutions on record: 1" in first["summary"]


def test_award_selection_rule_and_undated_exclusion() -> None:
    rows = [
        _award(1, plastic_related=True),
        _award(2, plastic_related=None),
        _award(3, plastic_related=False),
        _award(4, start=None),
        _award(5, start="not-a-date"),
    ]
    awards = fd.select_awards(_grants(rows))
    assert [a["id"].rsplit("/", 1)[1] for a in awards] == [f"{2:016x}", f"{1:016x}"]
    summary = awards[1]["summary"]
    assert "Funder: NSF > CBET" in summary
    assert "Amount: USD 1,001" in summary
    assert "Amount basis: NSF estimatedTotalAmt." in summary


def test_award_without_amount_is_reported_as_not_reported() -> None:
    awards = fd.select_awards(_grants([_award(1, amount=None)]))
    assert "Amount: not reported" in awards[0]["summary"]


def test_caps_at_thirty_each() -> None:
    works = [_work(i, year=1990 + i) for i in range(35)]
    rows = [_award(i, start=f"20{10 + i // 10:02d}-01-{1 + i % 28:02d}") for i in range(35)]
    root = _parse(fd.render_feed(_index(works), _grants(rows)))
    entries = _entries(root)
    assert len(entries) == 60
    assert sum(_term(e) == "paper" for e in entries) == 30
    assert sum(_term(e) == "award" for e in entries) == 30


def test_ordering_newest_first_and_feed_updated_is_max_entry_date() -> None:
    works = [_work(1, year=2019), _work(2, year=2025), _work(3, year=2022)]
    rows = [_award(1, start="2021-05-01"), _award(2, start="2026-02-01")]
    root = _parse(fd.render_feed(_index(works), _grants(rows)))
    entries = _entries(root)
    updated = [e.find(f"{ATOM}updated").text for e in entries]
    assert updated == sorted(updated, reverse=True)
    assert updated[0] == "2026-02-01T00:00:00Z"
    assert root.find(f"{ATOM}updated").text == "2026-02-01T00:00:00Z"


def test_feed_updated_falls_back_to_epoch_when_empty() -> None:
    root = _parse(fd.render_feed(_index([]), _grants([])))
    assert _entries(root) == []
    assert root.find(f"{ATOM}updated").text == fd.EPOCH


def test_titles_and_summaries_are_escaped_and_round_trip() -> None:
    nasty = "Microplastics & <tests> \"quoted\" 'single'"
    works = [_work(1, title=nasty)]
    rows = [_award(1, title=nasty, org="A & B <Lab>")]
    data = fd.render_feed(_index(works), _grants(rows))
    assert b"&amp;" in data and b"&lt;tests&gt;" in data
    root = _parse(data)
    titles = [e.find(f"{ATOM}title").text for e in _entries(root)]
    assert titles == [nasty, nasty]
    assert "A & B <Lab>" in _entries(root)[0].find(f"{ATOM}summary").text


def test_entry_ids_are_unique_tag_uris() -> None:
    works = [_work(1), _work(2)]
    rows = [_award(1), _award(2)]
    root = _parse(fd.render_feed(_index(works), _grants(rows)))
    ids = [e.find(f"{ATOM}id").text for e in _entries(root)]
    assert len(set(ids)) == len(ids) == 4
    assert all(i.startswith("tag:scottcoff.in,2026:") for i in ids)


def test_output_is_deterministic_across_input_order() -> None:
    works = [_work(i, year=2000 + i % 5) for i in range(12)]
    rows = [_award(i, start=f"2020-0{1 + i % 9}-15") for i in range(12)]
    first = fd.render_feed(_index(works), _grants(rows))
    assert fd.render_feed(_index(works), _grants(rows)) == first
    rng = random.Random(7)
    shuffled_works = copy.deepcopy(works)
    shuffled_rows = copy.deepcopy(rows)
    rng.shuffle(shuffled_works)
    rng.shuffle(shuffled_rows)
    assert fd.render_feed(_index(shuffled_works), _grants(shuffled_rows)) == first


def test_no_abstract_or_contact_text_is_emitted() -> None:
    secret = "SECRET ABSTRACT TEXT"
    work = _work(1, abstract=secret)
    row = _award(1, abstract=secret, email="person@example.org", pi_names=["Jane Doe"])
    data = fd.render_feed(_index([work]), _grants([row]))
    assert secret.encode() not in data
    assert b"person@example.org" not in data
    assert b"Jane Doe" not in data


def test_write_feed_on_site_payloads_is_well_formed(tmp_path: Path) -> None:
    output = tmp_path / "feed.xml"
    counts = fd.write_feed(
        ROOT / "site" / "data" / "index.json",
        ROOT / "site" / "data" / "grants.json",
        output,
    )
    root = _parse(output.read_bytes())
    entries = _entries(root)
    assert len(entries) == counts["entries"]
    assert counts["papers"] <= fd.MAX_PAPERS
    assert counts["awards"] <= fd.MAX_AWARDS
    assert counts["bytes"] == output.stat().st_size


def test_awards_after_payload_date_are_skipped() -> None:
    from atlas.build import feed

    payload = {
        "generated_at": "2026-11-10T07:00:56Z",
        "rows": [
            {"grant_key": "past", "title": "Past", "start": "2026-10-01", "plastic_related": True},
            {
                "grant_key": "future",
                "title": "Future",
                "start": "2027-03-15",
                "plastic_related": True,
            },
        ],
    }
    ids = [entry["id"] for entry in feed.select_awards(payload)]
    assert any(i.endswith("/past") for i in ids)
    assert not any(i.endswith("/future") for i in ids)
