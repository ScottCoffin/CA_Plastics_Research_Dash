from __future__ import annotations

import json

import pytest

from atlas.build.monitoring import (
    PRIVATE_SAMPLE_FIELDS,
    build_monitoring_payload,
    require_private_output_outside_site,
)


def registry() -> dict:
    return {
        "datasets": [
            {
                "id": "example",
                "seed_eligible": True,
                "name": "Example source",
                "steward": "Example steward",
                "entity_type": "dataset",
                "status": "verified source page",
                "region": "California coast",
                "sample_matrix": ["surface water"],
                "plastic_classes": ["microplastics"],
                "access_tier": "A",
                "url": "https://example.org/data",
                "access_method": "Public download",
                "format": ["CSV"],
                "cadence": "Irregular",
                "license": "Rights review required",
                "provenance_type": "dataset_record",
                "provenance_url": "https://example.org/source",
                "provenance_note": "A real source citation note.",
                "last_checked": "2026-11-09",
            }
        ]
    }


def test_public_payload_keeps_citations_and_never_includes_sample_rows() -> None:
    payload = build_monitoring_payload(registry(), generated_at="fixed")
    assert payload["publication_mode"] == "public_catalogue"
    assert payload["sample_count"] == 0
    assert payload["samples"] == []
    assert payload["datasets"][0]["url"] == "https://example.org/data"
    assert payload["datasets"][0]["provenance_url"] == "https://example.org/source"
    assert payload["datasets"][0]["citation"] == "A real source citation note."
    assert payload["datasets"][0]["contributor_in_ca"] is None


def test_public_mode_rejects_measurements_without_explicit_private_flag() -> None:
    with pytest.raises(PermissionError, match="private-preview"):
        build_monitoring_payload(registry(), samples=[{"sample_id": "synthetic"}])


def test_private_preview_is_tagged_and_strips_qc_only_fields() -> None:
    sample = {
        "sample_id": "synthetic-1",
        "dataset_id": "example",
        "lat": 37.7,
        "lon": -122.4,
        "date": "2020-01-01",
        "matrix": "surface water",
        "method": "net tow",
        "concentration_value": 2.0,
        "concentration_unit": "particles/L",
        "source_row_provenance": [{"row": 4}],
        "license_evidence": {"sensitive": "omit"},
    }
    payload = build_monitoring_payload(
        registry(), samples=[sample], private_preview=True, generated_at="fixed"
    )
    assert payload["publication_mode"] == "private_preview"
    assert payload["sample_count"] == 1
    assert payload["datasets"][0]["measurement_status"] == "private_local_preview_rights_unresolved"
    assert set(payload["samples"][0]) <= set(PRIVATE_SAMPLE_FIELDS)
    assert "source_row_provenance" not in json.dumps(payload)
    assert "license_evidence" not in json.dumps(payload)


def test_private_preview_rejects_unknown_dataset_and_empty_payload() -> None:
    with pytest.raises(ValueError, match="unknown registry"):
        build_monitoring_payload(
            registry(), samples=[{"sample_id": "x", "dataset_id": "missing"}], private_preview=True
        )
    with pytest.raises(ValueError, match="no local samples"):
        build_monitoring_payload(registry(), private_preview=True)


def test_private_output_rejects_public_tree_and_relative_alias(tmp_path) -> None:
    site = tmp_path / "site"
    (site / "data").mkdir(parents=True)
    with pytest.raises(ValueError, match="outside the public site"):
        require_private_output_outside_site(site / "data" / "monitoring.json", site_root=site)
    with pytest.raises(ValueError, match="outside the public site"):
        require_private_output_outside_site(
            site / "data" / ".." / "monitoring.json", site_root=site
        )
    assert (
        require_private_output_outside_site(
            tmp_path / "ignored" / "monitoring.json", site_root=site
        )
        == (tmp_path / "ignored" / "monitoring.json").resolve()
    )
