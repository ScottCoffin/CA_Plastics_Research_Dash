"""Focused tests for the CEDEN concentration enrichment (S7.8a) on a synthetic fixture."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from atlas.ingest.monitoring.ceden import (
    CEDEN_CITATION_SUFFIX,
    CEDEN_SOURCE_LABEL,
    aggregate_by_sample,
    build_search_url,
    consistency_report,
    enrich_samples,
    fetch_ceden_microplastics,
    load_owner_export,
    summarize_enrichment,
)

FIXTURE = Path(__file__).parent / "fixtures" / "s7_8_ceden.json"
BASE = "San Francisco Estuary Institute and 5 Gyres Institute; CC BY 4.0"


def _records() -> list[dict[str, Any]]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return list(payload["records"])


def _workbook() -> list[dict[str, Any]]:
    def row(sample_id, value, unit, code, date, lat, lon):
        return {
            "sample_id": sample_id,
            "concentration_value": value,
            "concentration_unit": unit,
            "citation": BASE,
            "date": date,
            "lat": lat,
            "lon": lon,
            "matrix_source_code": code,
        }

    return [
        row("TEST-SW-KEEP-01", 0.5, "particles/L", "manta", "2017-11-16T00:00:00", 37.9, -122.4),
        row("TEST-SW-FILL-02", None, "particles/L", "sw", "2014-08-07T00:00:00", 37.8, -122.3),
        row("TEST-SED-FILL-03", None, "particles/g", "sed", "2015-03-02T00:00:00", 38.0, -122.5),
        row("TEST-SW-BLANK-04", None, "particles/L", None, "2016-05-10T00:00:00", 37.7, -122.2),
        row("TEST-EFF-QA-05", None, "particles/L", "eff", "2016-06-01T00:00:00", 37.6, -122.1),
        row(
            "TEST-SW-PLACEHOLDER-06", None, "particles/L", None, "2000-01-01T00:00:00", 37.5, -122.0
        ),
        row("TEST-SW-MISMATCH-07", 0.9, "particles/L", "eff", "2017-01-06T00:00:00", 37.6, -121.9),
        row("TEST-WB-BLANK-08", 0.2, "particles/L", None, "2018-01-01T00:00:00", 37.0, -121.0),
    ]


def _aggregate() -> dict[str, dict[str, Any]]:
    return aggregate_by_sample(_records())


def _enriched() -> dict[str, dict[str, Any]]:
    workbook = [row for row in _workbook() if row["sample_id"] != "TEST-SW-MISMATCH-07"]
    rows = enrich_samples(workbook, _aggregate())
    return {row["sample_id"]: row for row in rows}


def test_aggregate_sums_results_across_analytes_and_size_fractions() -> None:
    summary = _aggregate()["TEST-SW-KEEP-01"]
    assert summary["concentration_value"] == pytest.approx(0.5)
    assert summary["concentration_unit"] == "particles/L"
    assert summary["analyte_count"] == 2
    assert summary["size_fractions"] == [">125 to 355 um", ">355 um"]
    assert summary["sample_date"] == "2017-11-16"
    assert _aggregate()["TEST-SED-FILL-03"]["concentration_value"] == pytest.approx(3.5)
    assert _aggregate()["TEST-SED-FILL-03"]["concentration_unit"] == "particles/g"


def test_qa_flags_from_isqa_sample_type_and_blank_name() -> None:
    summaries = _aggregate()
    assert summaries["TEST-SW-KEEP-01"]["is_qa"] is False
    assert summaries["TEST-SW-BLANK-04"]["is_qa"] is True
    assert summaries["TEST-SW-BLANK-04"]["sample_type_codes"] == ["FieldBlank"]
    assert summaries["TEST-EFF-QA-05"]["is_qa"] is True
    enriched = _enriched()
    assert enriched["TEST-WB-BLANK-08"]["qa_sample"] is True
    assert enriched["TEST-SW-KEEP-01"]["qa_sample"] is False


def test_mixed_units_within_one_sample_raise() -> None:
    records = _records()
    records[1] = {**records[1], "Unit": "particles/g"}
    with pytest.raises(ValueError, match="TEST-SW-KEEP-01"):
        aggregate_by_sample(records)


def test_enrich_keeps_matching_workbook_concentration_without_source_or_citation() -> None:
    kept = _enriched()["TEST-SW-KEEP-01"]
    assert kept["concentration_value"] == 0.5
    assert "concentration_source" not in kept
    assert kept["citation"] == BASE


def test_enrich_fills_null_concentration_with_source_label_and_citation_suffix() -> None:
    filled = _enriched()["TEST-SW-FILL-02"]
    assert filled["concentration_value"] == pytest.approx(0.35)
    assert filled["concentration_unit"] == "particles/L"
    assert filled["concentration_source"] == CEDEN_SOURCE_LABEL
    assert filled["citation"] == BASE + CEDEN_CITATION_SUFFIX


def test_citation_suffix_only_on_filled_rows() -> None:
    enriched = _enriched()
    assert enriched["TEST-WB-BLANK-08"]["citation"] == BASE
    assert enriched["TEST-SW-KEEP-01"]["citation"] == BASE
    for sample_id in ("TEST-SW-FILL-02", "TEST-SED-FILL-03", "TEST-SW-BLANK-04"):
        assert enriched[sample_id]["citation"].endswith(CEDEN_CITATION_SUFFIX)
    assert enriched["TEST-SW-PLACEHOLDER-06"]["concentration_value"] == pytest.approx(0.05)


def test_mismatched_workbook_concentration_raises() -> None:
    with pytest.raises(ValueError, match="TEST-SW-MISMATCH-07"):
        enrich_samples(_workbook(), _aggregate())


def test_rel_tol_sets_keep_threshold_for_rounded_ceden_results() -> None:
    workbook = [
        {
            "sample_id": "TEST-SW-KEEP-01",
            "concentration_value": 0.5 * (1 + 1e-7),
            "concentration_unit": "particles/L",
            "citation": BASE,
        }
    ]
    with pytest.raises(ValueError, match="TEST-SW-KEEP-01"):
        enrich_samples(workbook, _aggregate(), rel_tol=1e-9)
    # Default 1e-5: CEDEN results carry 6-8 significant digits.
    kept = enrich_samples(workbook, _aggregate())[0]
    assert kept["concentration_value"] == pytest.approx(0.5 * (1 + 1e-7))
    assert "concentration_source" not in kept


def test_enrich_does_not_drop_rows_and_summarizes_counts() -> None:
    workbook = [row for row in _workbook() if row["sample_id"] != "TEST-SW-MISMATCH-07"]
    ceden = _aggregate()
    del ceden["TEST-SW-MISMATCH-07"]
    enriched = enrich_samples(workbook, ceden)
    assert len(enriched) == len(workbook)
    counts = summarize_enrichment(workbook, enriched, ceden)
    assert counts["matched"] == 6
    assert counts["kept_workbook_concentration"] == 1
    assert counts["filled_from_ceden"] == 5
    assert counts["qa_samples"] == 3  # BLANK-04 (type + name), EFF-QA-05 (ISQA), WB-BLANK-08
    assert counts["ceden_unmatched"] == 0


def test_consistency_report_counts_without_dropping() -> None:
    report = consistency_report(_workbook(), _aggregate())
    assert report["matched"] == 7
    assert report["date_same_day"] == 5
    assert report["date_skipped_placeholder"] == 1
    assert report["date_different_day"] == 1
    assert report["location_within_1km"] == 6
    assert report["location_beyond_1km"] == 1
    assert report["matrix_consistent"] == 4
    assert report["matrix_inconsistent"] == 1
    assert report["matrix_not_comparable"] == 2


def test_fetch_paginates_with_filters_and_throttles() -> None:
    records = _records()
    seen: list[str] = []
    sleeps: list[float] = []
    pages: list[tuple[str, int]] = []

    def transport(url: str) -> dict[str, Any]:
        seen.append(url)
        query = parse_qs(urlparse(url).query)
        offset, limit = int(query["offset"][0]), int(query["limit"][0])
        return {
            "success": True,
            "result": {"total": len(records), "records": records[offset : offset + limit]},
        }

    result = fetch_ceden_microplastics(
        transport,
        resource_ids={"2018": "res-1"},
        page_size=4,
        page_sink=lambda year, offset, payload: pages.append((year, offset)),
        sleep=sleeps.append,
    )
    assert len(result) == len(records)
    assert len(seen) == 3
    assert pages == [("2018", 0), ("2018", 4), ("2018", 8)]
    assert sleeps == [0.3, 0.3]
    query = parse_qs(urlparse(seen[0]).query)
    assert query["resource_id"] == ["res-1"]
    assert json.loads(query["filters"][0]) == {
        "Unit": ["particles/L", "particles/g"],
        "ParentProject": "Regional Monitoring Program-Microplastics",
    }
    assert "facets" not in seen[0]


def test_fetch_raises_on_unsuccessful_response() -> None:
    with pytest.raises(RuntimeError, match="failed"):
        fetch_ceden_microplastics(
            lambda url: {"success": False, "result": {}},
            resource_ids={"2018": "res-1"},
            sleep=lambda s: None,
        )


def test_build_search_url_uses_list_filters() -> None:
    url = build_search_url("res-9", 2000, limit=1000)
    query = parse_qs(urlparse(url).query)
    assert query["offset"] == ["2000"]
    assert query["limit"] == ["1000"]


def test_owner_export_loader_gives_same_aggregate(tmp_path: Path) -> None:
    path = tmp_path / "export.tsv"
    fields = [
        "SAMPLEID",
        "ISQA",
        "SAMPLETYPECODE",
        "MATRIXNAME",
        "ANALYTE",
        "UNIT",
        "RESULT",
        "SAMPLEDATE",
        "STATIONCODE",
        "LATITUDE",
        "LONGITUDE",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        for record in _records():
            writer.writerow(
                {
                    "SAMPLEID": record["SampleID"],
                    "ISQA": record["ISQA"],
                    "SAMPLETYPECODE": record["SampleTypeCode"],
                    "MATRIXNAME": record["MatrixName"],
                    "ANALYTE": record["Analyte"],
                    "UNIT": record["Unit"],
                    "RESULT": record["Result"],
                    "SAMPLEDATE": "8/7/2014 12:00:00 AM",
                    "STATIONCODE": record["StationCode"],
                    "LATITUDE": record["Latitude"],
                    "LONGITUDE": record["Longitude"],
                }
            )
    exported = aggregate_by_sample(load_owner_export(path))
    live = _aggregate()
    assert set(exported) == set(live)
    for sample_id in live:
        assert exported[sample_id]["concentration_value"] == pytest.approx(
            live[sample_id]["concentration_value"]
        )
        assert exported[sample_id]["is_qa"] == live[sample_id]["is_qa"]
