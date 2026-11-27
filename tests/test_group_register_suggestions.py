"""IRS EO BMF register suggestions (GRP-ENRICH slice 3): matching, NTEE hints, cache and --check.

All tests are offline. They write a small EO BMF style CSV fixture into tmp_path, replace the
network fetch with a fake, and never read data/raw or call the py launcher (CI is Linux).
"""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from atlas.groups.schema import load_taxonomy

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_group_register_suggestions.py"
TODAY = "2026-11-26"
TODAY_YEAR = 2026
HEADER = [
    "EIN", "NAME", "ICO", "STREET", "CITY", "STATE", "ZIP", "GROUP", "SUBSECTION", "AFFILIATION",
    "CLASSIFICATION", "RULING", "DEDUCTIBILITY", "FOUNDATION", "ACTIVITY", "ORGANIZATION",
    "STATUS", "TAX_PERIOD", "ASSET_CD", "INCOME_CD", "FILING_REQ_CD", "PF_FILING_REQ_CD",
    "ACCT_PD", "ASSET_AMT", "INCOME_AMT", "REVENUE_AMT", "NTEE_CD", "SORT_NAME",
]  # fmt: skip


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_group_register_suggestions", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bgr = _load()


def _rec(gid: str, name: str, country: str = "US", alt: list[str] | None = None) -> dict[str, Any]:
    return {"group_id": gid, "name": name, "country": country, "name_alt": alt or [], "url": None}


def _irs(
    ein: str,
    name: str,
    state: str = "CA",
    city: str = "SAN FRANCISCO",
    ruling: str = "199912",
    ntee: str = "C20",
) -> dict[str, str]:
    row = {column: "" for column in HEADER}
    row.update(
        EIN=ein, NAME=name, CITY=city, STATE=state, RULING=ruling, NTEE_CD=ntee,
        SORT_NAME=name.lower(),
    )  # fmt: skip
    return row


def _write_snapshot(snapshot: Path, rows: list[dict[str, str]], complete: bool = True) -> Path:
    """Write rows into eo_ca.csv under snapshot (optionally with the completion marker)."""
    snapshot.mkdir(parents=True, exist_ok=True)
    with (snapshot / "eo_ca.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)
    if complete:
        (snapshot / bgr.COMPLETE_MARKER).write_text("eo_ca.csv\n", encoding="utf-8")
    return snapshot


def _match(records: list[dict[str, Any]], rows: list[dict[str, str]]) -> dict[str, Any]:
    groups, _ = bgr.match_groups(records, rows, TODAY_YEAR)
    return groups


def test_exact_match_after_normalisation_reports_register_fields():
    recs = [_rec("cg_green", "Green Coalition Inc.")]
    rows = [_irs("123456789", "GREEN COALITION INC", ruling="199912", ntee="C01")]
    groups = _match(recs, rows)
    assert groups == {
        "cg_green": {
            "register": "irs_eo_bmf",
            "ein": "123456789",
            "registered_name": "GREEN COALITION INC",
            "city": "SAN FRANCISCO",
            "state": "CA",
            "ruling_year": 1999,
            "ntee_code": "C01",
            "ntee_major": "C",
            "sector_hint": "ngo_civil_society",
            "activity_hints": ["advocacy_campaigning"],
        }
    }


def test_ampersand_reads_as_and_and_foundation_is_kept():
    recs = [_rec("cg_pp", "Paper & Plastics Foundation"), _rec("cg_other", "Paper Plastics")]
    rows = [_irs("111111111", "PAPER AND PLASTICS FOUNDATION", ntee="T22")]
    groups = _match(recs, rows)
    assert set(groups) == {"cg_pp"}
    assert groups["cg_pp"]["sector_hint"] == "foundation"


def test_group_with_two_eins_is_dropped_and_counted():
    recs = [_rec("cg_dup", "Green Alliance")]
    rows = [_irs("111111111", "GREEN ALLIANCE"), _irs("222222222", "GREEN ALLIANCE", state="NY")]
    groups, stats = bgr.match_groups(recs, rows, TODAY_YEAR)
    assert groups == {}
    assert stats["ambiguous_group"] == 1


def test_ein_matching_two_groups_is_dropped_for_both_groups():
    recs = [_rec("cg_a", "Clean Shore"), _rec("cg_b", "Clean Shore.")]
    rows = [_irs("333333333", "CLEAN SHORE")]
    groups, stats = bgr.match_groups(recs, rows, TODAY_YEAR)
    assert groups == {}
    assert stats["ambiguous_ein"] == 2


def test_non_us_roster_records_are_ignored():
    recs = [_rec("cg_gb", "Green Coalition", country="GB"), _rec("cg_af", "Green Coalition", "AF")]
    rows = [_irs("123456789", "GREEN COALITION")]
    assert _match(recs, rows) == {}


def test_alternate_names_are_not_used():
    recs = [_rec("cg_alt", "Plastic Free Town", alt=["Green Coalition"])]
    rows = [_irs("123456789", "GREEN COALITION")]
    assert _match(recs, rows) == {}


def test_rows_without_a_valid_ein_or_with_a_missing_ntee_still_match_safely():
    recs = [_rec("cg_bad", "Bad EIN Org"), _rec("cg_none", "No Code Org")]
    rows = [_irs("12-3", "BAD EIN ORG"), _irs("444444444", "NO CODE ORG", ntee="")]
    groups = _match(recs, rows)
    assert set(groups) == {"cg_none"}
    entry = groups["cg_none"]
    assert entry["ntee_code"] is None and entry["ntee_major"] is None
    assert entry["sector_hint"] is None and entry["activity_hints"] == []


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("C27", ("ngo_civil_society", ("waste_management_recycling",))),
        ("C60", ("ngo_civil_society", ("education_awareness",))),
        ("C01", ("ngo_civil_society", ("advocacy_campaigning",))),
        ("C05", ("ngo_civil_society", ("research_monitoring",))),
        ("C270", ("ngo_civil_society", ("waste_management_recycling",))),
        ("C30", ("ngo_civil_society", ())),
        ("C32", ("ngo_civil_society", ())),
        ("C34", ("ngo_civil_society", ())),
        ("C36", ("ngo_civil_society", ())),
        ("C99", ("ngo_civil_society", ())),
        ("B40", ("academia_research", ())),
        ("B50", ("academia_research", ())),
        ("B12", (None, ())),
        ("T22", ("foundation", ())),
        ("A23", (None, ())),
        (None, (None, ())),
    ],
)
def test_ntee_mapping_table(code, expected):
    assert bgr.ntee_hints(code) == expected


def test_hints_come_only_from_the_vocabulary():
    taxonomy = load_taxonomy()
    sectors = set(taxonomy["sector"])
    activities = set(taxonomy["primary_activities"])
    assert set(bgr.NTEE_MAJOR_SECTOR.values()) <= sectors
    assert {"academia_research"} <= sectors
    assert {hint for hints in bgr.NTEE_ACTIVITY.values() for hint in hints} <= activities
    assert bgr.SECTORS == sectors and bgr.ACTIVITIES == activities


def test_ruling_year_is_read_from_yyyymm_and_rejects_implausible_values():
    assert bgr._ruling_year("199912", TODAY_YEAR) == 1999
    assert bgr._ruling_year("000000", TODAY_YEAR) is None
    assert bgr._ruling_year("299912", TODAY_YEAR) is None
    assert bgr._ruling_year("", TODAY_YEAR) is None


def _valid_doc(**item_overrides: Any) -> dict[str, Any]:
    item = {
        "register": "irs_eo_bmf",
        "ein": "123456789",
        "registered_name": "GREEN COALITION INC",
        "city": "SAN FRANCISCO",
        "state": "CA",
        "ruling_year": 1999,
        "ntee_code": "C01",
        "ntee_major": "C",
        "sector_hint": "ngo_civil_society",
        "activity_hints": ["advocacy_campaigning"],
    }
    item.update(item_overrides)
    return {
        "schema": bgr.SCHEMA,
        "source": bgr.SOURCE,
        "retrieved_at": TODAY,
        "groups": {"cg_green": item},
    }


def test_validate_accepts_a_good_document():
    assert bgr.validate(_valid_doc(), {"cg_green"}, TODAY_YEAR) == []


@pytest.mark.parametrize(
    "override",
    [
        {"ein": "12345"},
        {"sector_hint": "not_a_sector"},
        {"activity_hints": ["not_an_activity"]},
        {"activity_hints": ["advocacy_campaigning", "advocacy_campaigning"]},
        {"ntee_major": "T"},
        {"state": "California"},
        {"ruling_year": 3000},
        {"register": "other"},
    ],
)
def test_validate_rejects_bad_items(override):
    errors = bgr.validate(_valid_doc(**override), {"cg_green"}, TODAY_YEAR)
    assert errors


def test_validate_rejects_unknown_roster_id_and_bad_schema():
    doc = _valid_doc()
    errors = bgr.validate(doc, {"cg_other"}, TODAY_YEAR)
    assert any("not a roster group_id" in e for e in errors)
    doc["schema"] = "cg-suggestions-v1"
    assert any("schema must be" in e for e in bgr.validate(doc, {"cg_green"}, TODAY_YEAR))


def test_output_is_deterministic_and_order_independent():
    recs = [_rec("cg_a", "Alpha Org"), _rec("cg_b", "Beta Org")]
    rows = [_irs("111111111", "ALPHA ORG", ntee="C27"), _irs("222222222", "BETA ORG", ntee="B40")]
    first, _ = bgr.render(recs, rows, None, TODAY)
    second, _ = bgr.render(list(reversed(recs)), list(reversed(rows)), None, TODAY)
    assert bgr.to_bytes(first) == bgr.to_bytes(second)
    assert bgr.to_bytes(first).endswith(b"}\n")


def test_retrieved_at_is_kept_when_groups_unchanged_and_moves_when_they_change():
    recs = [_rec("cg_a", "Alpha Org")]
    rows = [_irs("111111111", "ALPHA ORG")]
    committed, _ = bgr.render(recs, rows, None, "2026-11-01")
    assert committed["retrieved_at"] == "2026-11-01"
    same, _ = bgr.render(recs, rows, committed, TODAY)
    assert same["retrieved_at"] == "2026-11-01"
    changed, _ = bgr.render(recs, [], committed, TODAY)
    assert changed["retrieved_at"] == TODAY
    assert changed["groups"] == {}


def _point_paths(monkeypatch, tmp_path: Path, records: list[dict[str, Any]]) -> Path:
    roster = tmp_path / "roster.json"
    roster.write_text(json.dumps({"records": records}), encoding="utf-8")
    out = tmp_path / "register_suggestions.json"
    monkeypatch.setattr(bgr, "ROSTER_PATH", roster)
    monkeypatch.setattr(bgr, "OUTPUT_PATH", out)
    monkeypatch.setattr(bgr, "RAW_DIR", tmp_path / "no_cache")
    return out


def test_check_passes_without_cache_and_fails_on_bad_file(tmp_path, monkeypatch):
    out = _point_paths(monkeypatch, tmp_path, [_rec("cg_a", "Example Org")])
    doc = {"schema": bgr.SCHEMA, "source": bgr.SOURCE, "retrieved_at": TODAY, "groups": {}}
    out.write_bytes(bgr.to_bytes(doc))
    assert bgr.main(["--check"]) == 0
    doc["groups"] = {"cg_a": {"register": "irs_eo_bmf", "ein": "x"}}
    out.write_bytes(bgr.to_bytes(doc))
    assert bgr.main(["--check"]) == 1


def test_check_fails_when_the_committed_file_is_missing(tmp_path, monkeypatch):
    _point_paths(monkeypatch, tmp_path, [_rec("cg_a", "Example Org")])
    assert bgr.main(["--check"]) == 1


def test_check_rebuilds_from_a_complete_cache_and_detects_drift(tmp_path, monkeypatch):
    records = [_rec("cg_green", "Green Coalition")]
    rows = [_irs("123456789", "GREEN COALITION", ntee="C27")]
    out = _point_paths(monkeypatch, tmp_path, records)
    raw = tmp_path / "raw"
    monkeypatch.setattr(bgr, "RAW_DIR", raw)
    _write_snapshot(raw / "2026-11-20", rows)
    doc, _ = bgr.render(records, rows, None, "2026-11-20")
    out.write_bytes(bgr.to_bytes(doc))
    assert bgr.main(["--check"]) == 0
    out.write_bytes(bgr.to_bytes({**doc, "groups": {}}))
    assert bgr.main(["--check"]) == 1


def test_offline_uses_the_newest_complete_snapshot_only(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    _write_snapshot(raw / "2026-11-01", [_irs("111111111", "OLD ORG")])
    _write_snapshot(raw / "2026-11-30", [_irs("222222222", "NEW ORG")], complete=False)
    assert bgr.latest_snapshot(raw).name == "2026-11-01"
    _write_snapshot(raw / "2026-11-15", [_irs("333333333", "MID ORG")])
    assert bgr.latest_snapshot(raw).name == "2026-11-15"
    assert bgr.latest_snapshot(tmp_path / "absent") is None


def test_offline_without_a_snapshot_stops_with_exit_2(tmp_path, monkeypatch):
    _point_paths(monkeypatch, tmp_path, [_rec("cg_a", "Example Org")])
    assert bgr.main(["--offline"]) == 2


def test_discover_state_files_excludes_regions_and_needs_fifty():
    names = [f"eo_{code}.csv" for code in ("ca", "ny", "tx")] + ["eo1.csv"]
    html = "".join(f'href="/pub/irs-soi/{n}"' for n in names).encode()
    with pytest.raises(bgr.RegisterError):
        bgr.discover_state_files(html)  # fewer than 50 state files
    many = [f"eo_{a}{b}.csv" for a in "abcdefghij" for b in "abcde"]
    html_many = "".join(f'href="/pub/irs-soi/{n}"' for n in many + ["eo1.csv"]).encode()
    found = bgr.discover_state_files(html_many)
    assert len(found) == 50 and "eo1.csv" not in found


def test_download_is_paced_skips_cached_files_and_rejects_non_csv(tmp_path):
    calls: list[str] = []
    sleeps: list[float] = []

    def fake_fetch(url: str) -> bytes:
        calls.append(url)
        return b"EIN,NAME\n123456789,EXAMPLE\n"

    snapshot = tmp_path / "2026-11-26"
    bgr.download_snapshot(
        snapshot, ["eo_ca.csv", "eo_ny.csv"], fetch=fake_fetch, sleep=sleeps.append
    )
    assert calls == [bgr.FILE_URL + "eo_ca.csv", bgr.FILE_URL + "eo_ny.csv"]
    assert sleeps == [bgr.PAUSE, bgr.PAUSE]
    assert (snapshot / bgr.COMPLETE_MARKER).exists()

    calls.clear()
    bgr.download_snapshot(
        snapshot, ["eo_ca.csv", "eo_ny.csv"], fetch=fake_fetch, sleep=sleeps.append
    )
    assert calls == []

    def html_fetch(url: str) -> bytes:
        return b"<html>error</html>"

    with pytest.raises(bgr.RegisterError):
        bgr.download_snapshot(
            tmp_path / "bad", ["eo_ca.csv"], fetch=html_fetch, sleep=lambda s: None
        )
    assert not (tmp_path / "bad" / "eo_ca.csv").exists()
