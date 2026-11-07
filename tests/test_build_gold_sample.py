"""Input validation tests for the S4.2 sample builder."""

from __future__ import annotations

import pytest

from scripts.build_gold_sample import _load_gazetteer_hit_ids


def test_gazetteer_hit_csv_requires_work_id_header(tmp_path) -> None:
    path = tmp_path / "hits.csv"
    path.write_text("openalex_id\nW123\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must include a work_id header"):
        _load_gazetteer_hit_ids(path)


def test_gazetteer_hit_csv_trims_and_ignores_blank_ids(tmp_path) -> None:
    path = tmp_path / "hits.csv"
    path.write_text("work_id,source\n W123 ,gazetteer\n,empty\n", encoding="utf-8")
    assert _load_gazetteer_hit_ids(path) == {"W123"}
