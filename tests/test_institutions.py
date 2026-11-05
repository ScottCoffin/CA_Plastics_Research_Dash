from __future__ import annotations

import csv
import os
from pathlib import Path

import pytest

from atlas.ingest.institutions import (
    build_rows,
    classify_atlas_type,
    load_overrides,
    required_name_is_present,
)
from scripts.build_institutions import load_openalex_key


@pytest.mark.parametrize(
    ("name", "ror_types", "lineage", "expected"),
    [
        ("UC Davis", ["education"], ["University of California"], "UC"),
        ("Cal Poly Humboldt", ["education"], ["California State University"], "CSU"),
        ("Foothill Community College", ["education"], [], "community-college"),
        ("United States Geological Survey", ["government"], [], "federal"),
        ("California Department of Water Resources", ["government"], [], "state-agency"),
        ("City of Sacramento", ["government"], [], "local-agency"),
        ("Stanford University", ["education"], [], "private"),
        ("Example Corporation", ["company"], [], "company"),
    ],
)
def test_classify_atlas_type(name, ror_types, lineage, expected):
    record = {"display_name": name, "ror_record": {"types": ror_types}}
    assert classify_atlas_type(record, lineage)[0] == expected


def test_override_schema_and_precedence(tmp_path: Path):
    path = tmp_path / "overrides.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["inst_id", "field", "value", "reason", "reviewed_by", "reviewed_at"])
        writer.writerow(["I1", "atlas_type", "nonprofit/NGO", "known", "owner", "2026-11-05"])
    overrides = load_overrides(path)
    records = [
        {
            "id": "https://openalex.org/I1",
            "display_name": "Example Corporation",
            "ror": None,
            "type": "company",
            "lineage": [],
            "geo": {"country_code": "US", "region": "California", "city": "Davis"},
            "works_count": 2,
        }
    ]
    row = build_rows(records, {}, {"I1": 1}, overrides)[0]
    assert row["atlas_type"] == "nonprofit/NGO"
    assert row["classification_rule"] == "manual-override"


def test_invalid_atlas_type_override(tmp_path: Path):
    path = tmp_path / "overrides.csv"
    path.write_text(
        "inst_id,field,value,reason,reviewed_by,reviewed_at\nI1,atlas_type,unknown,,,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid atlas_type"):
        load_overrides(path)


def test_load_openalex_key_from_dotenv(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text("OTHER=value\nOPENALEX_API_KEY='secret-test-value'\n", encoding="utf-8")
    load_openalex_key(path)
    assert os.environ["OPENALEX_API_KEY"] == "secret-test-value"


def test_load_openalex_key_from_bare_file(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text("secret-test=value\n", encoding="utf-8")
    load_openalex_key(path)
    assert os.environ["OPENALEX_API_KEY"] == "secret-test=value"


def test_load_openalex_key_from_local_alias(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text('OPEN_ALEX_API_KEY="secret-test-value"\n', encoding="utf-8")
    load_openalex_key(path)
    assert os.environ["OPENALEX_API_KEY"] == "secret-test-value"


def test_required_name_aliases_accept_openalex_canonical_names():
    records = [
        {"display_name": "University of California San Diego"},
        {"display_name": "California Maritime Academy"},
    ]
    assert required_name_is_present("University of California, San Diego", records)
    assert required_name_is_present("California State University Maritime Academy", records)
