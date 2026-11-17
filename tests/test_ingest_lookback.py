"""Incremental ingest re-reads a window before the high-water mark (owner report 2026-11-17).

OpenAlex indexed W7226023234 (doi 10.1021/acsestwater.6c01560) on 2026-11-14 with publication
date 2026-11-13; a run starting at the previous day's high-water mark can miss such works.
"""

from __future__ import annotations

import pytest

from atlas.ingest import openalex


def test_incremental_start_subtracts_the_lookback() -> None:
    assert openalex.INCREMENTAL_LOOKBACK_DAYS == 30
    assert openalex.incremental_start("2026-11-16") == "2026-10-17"
    assert openalex.incremental_start("2026-11-16", lookback_days=0) == "2026-11-16"
    assert openalex.incremental_start("2026-03-01T00:00:00", lookback_days=1) == "2026-02-28"


def test_negative_lookback_is_rejected() -> None:
    with pytest.raises(ValueError):
        openalex.incremental_start("2026-11-16", lookback_days=-1)


def test_high_water_mark_never_moves_backwards() -> None:
    assert openalex._later_date("2026-10-20", "2026-11-16") == "2026-11-16"
    assert openalex._later_date("2026-11-17", "2026-11-16") == "2026-11-17"
    assert openalex._later_date(None, "2026-11-16") == "2026-11-16"
    assert openalex._later_date(None, None) is None


def test_rejection_summary_redacts_keys_and_names_firewall_headers() -> None:
    raw = b'{"error": "Forbidden", "message": "bad key api_key=SECRET123 or Bearer SECRET456"}'
    line = openalex._rejection_summary(403, {"CF-RAY": "abc", "Server": "cloudflare"}, raw)
    assert "SECRET" not in line
    assert "cf-ray=abc" in line and "server=cloudflare" in line
    assert line.startswith("OpenAlex HTTP 403")
