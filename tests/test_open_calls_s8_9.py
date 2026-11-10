from __future__ import annotations

import json
import urllib.error
from datetime import date
from pathlib import Path

import pytest
import yaml

from atlas.ingest.grants import open_calls as oc
from scripts.build_open_calls import main as build_main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "s8_9_grants_portal.csv"
TODAY = date(2026, 11, 9)
GENERATED = "2026-11-09T12:00:00Z"


@pytest.fixture(scope="module")
def query_config() -> dict:
    return yaml.safe_load((ROOT / "config" / "queries.yml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows() -> list[dict[str, str]]:
    return oc.parse_csv(oc.decode_csv(FIXTURE.read_bytes()))


def _payload(rows, query_config):
    return oc.build_payload(rows, query_config=query_config, today=TODAY, generated_at=GENERATED)


def test_fixture_has_expected_size_and_columns(rows):
    assert 0 < len(rows) <= 15
    assert {"Status", "ApplicationDeadline", "GrantURL"} <= set(rows[0])


def test_selects_only_open_plastic_calls_in_deadline_order(rows, query_config):
    payload, counts = _payload(rows, query_config)
    assert counts == {"rows": 14, "open": 11, "plastic_open": 7}
    assert [c["portal_id"] for c in payload["calls"]] == [
        "P-007",  # deadline is today: included
        "P-003",
        "P-001",
        "P-012",
        "P-013",
        "P-002",  # ongoing calls follow dated calls, by title
        "P-010",
    ]


def test_excluded_rows_are_absent(rows, query_config):
    payload, _ = _payload(rows, query_config)
    ids = {c["portal_id"] for c in payload["calls"]}
    # closed, past deadline, blank deadline, non-plastic, and query exclusion
    assert ids.isdisjoint({"P-004", "P-005", "P-006", "P-008", "P-009", "P-011", "P-014"})


def test_payload_shape_and_fields(rows, query_config):
    payload, _ = _payload(rows, query_config)
    assert set(payload) == {"generated_at", "source_url", "licence", "calls"}
    assert payload["licence"] == "Other (Public Domain)"
    assert payload["source_url"] == oc.SOURCE_URL
    first = payload["calls"][0]
    assert set(first) == {
        "portal_id",
        "title",
        "agency",
        "deadline",
        "status",
        "url",
        "categories",
        "est_funding",
    }
    assert first["deadline"] == "2026-11-09"
    assert first["url"] == "https://example.test/grants/7"
    assert first["est_funding"] is None
    assert first["categories"] == ["Environment & Water"]
    ongoing = [c for c in payload["calls"] if c["deadline"] == "ongoing"]
    assert [c["status"] for c in ongoing] == ["forecasted", "active"]
    assert all(c["url"] and c["agency"] for c in payload["calls"])


def test_keyword_only_and_classifier_matches_are_both_kept(rows, query_config):
    titles = {c["portal_id"]: c["title"] for c in _payload(rows, query_config)[0]["calls"]}
    assert titles["P-002"] == "Marine Debris Cleanup Grants"  # funding term only
    assert titles["P-012"] == "Microfiber Textile Laundry Filters"  # classifier qualified term


def test_is_open_boundaries(query_config):
    base = {"Status": "active", "ApplicationDeadline": "2026-11-09 23:59:00"}
    assert oc.is_open(base, TODAY)
    assert not oc.is_open({**base, "ApplicationDeadline": "2026-11-08 23:59:00"}, TODAY)
    assert not oc.is_open({**base, "ApplicationDeadline": ""}, TODAY)
    assert not oc.is_open({**base, "Status": "closed"}, TODAY)
    assert oc.is_open({**base, "ApplicationDeadline": "Ongoing"}, TODAY)


def test_normalise_deadline_variants():
    assert oc.normalise_deadline("2027-01-02 17:00:00") == "2027-01-02"
    assert oc.normalise_deadline("ongoing") == "ongoing"
    assert oc.normalise_deadline("2027-02-30 00:00:00") is None
    assert oc.normalise_deadline("TBD") is None


def test_exclusions_override_funding_terms(query_config):
    row = {"Title": "Microplastic strain deformation", "Status": "active"}
    assert oc.is_plastic(row, query_config) is False


def test_parse_rejects_missing_columns():
    with pytest.raises(ValueError, match="missing columns"):
        oc.parse_csv("PortalID,Title\nP-1,Only title\n")


def test_decode_falls_back_to_cp1252():
    assert oc.decode_csv("Water — Recycling".encode("cp1252")) == "Water — Recycling"


def test_fetch_failure_is_deferred_and_keeps_existing_output(tmp_path, query_config):
    output = tmp_path / "open_calls.json"
    output.write_text('{"calls": []}\n', encoding="utf-8")

    def failing_opener(*_args, **_kwargs):
        raise urllib.error.URLError("offline")

    def fetch():
        return oc.fetch_csv(opener=failing_opener)

    summary = oc.refresh(
        output=output,
        query_config=query_config,
        today=TODAY,
        generated_at=GENERATED,
        fetch=fetch,
    )
    assert summary["status"] == "deferred"
    assert output.read_text(encoding="utf-8") == '{"calls": []}\n'


def test_unusable_csv_is_deferred(tmp_path, query_config):
    bad = tmp_path / "bad.csv"
    bad.write_text("not,the,right\nheader,here,x\n", encoding="utf-8")
    output = tmp_path / "out.json"
    summary = oc.refresh(
        output=output,
        query_config=query_config,
        today=TODAY,
        generated_at=GENERATED,
        csv_path=bad,
    )
    assert summary["status"] == "deferred"
    assert not output.exists()


def test_script_writes_deterministic_json_from_local_csv(tmp_path, capsys):
    output = tmp_path / "open_calls.json"
    assert build_main(["--csv", str(FIXTURE), "--output", str(output)]) == 0
    first = output.read_bytes()
    assert build_main(["--csv", str(FIXTURE), "--output", str(output)]) == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert len(payload["calls"]) == 7
    assert b"\r\n" not in first
    assert '"status": "written"' in capsys.readouterr().out


def test_script_defers_without_writing_on_fetch_failure(tmp_path, monkeypatch, capsys):
    output = tmp_path / "open_calls.json"
    output.write_text("{}\n", encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise oc.FetchError("fetch failed: URLError")

    monkeypatch.setattr(oc, "fetch_csv", boom)
    assert build_main(["--output", str(output)]) == 0
    assert output.read_text(encoding="utf-8") == "{}\n"
    assert "status: deferred" in capsys.readouterr().out
