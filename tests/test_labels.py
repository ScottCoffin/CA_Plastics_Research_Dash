import json
from pathlib import Path

import pyarrow.parquet as pq

from atlas.ingest.normalize import normalize_fixture
from atlas.nlp.labels import WORK_LABELS_SCHEMA, classify_plastic_text, label_records

FIXTURE = Path(__file__).parent / "fixtures" / "s2_3_openalex_works.json"
INSTITUTIONS = Path("data/processed/institutions.parquet")


def _fixture_records() -> list[dict]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return payload


def test_rule_ordering_and_qualified_terms() -> None:
    import yaml

    query_config = yaml.safe_load(Path("config/queries.yml").read_text(encoding="utf-8"))
    assert classify_plastic_text("microfiber without context", query_config).related is False
    assert classify_plastic_text("microfiber textile laundry", query_config).tier == "core"
    excluded = classify_plastic_text("microplastic strain deformation", query_config)
    assert excluded.related is False
    assert excluded.hits == ("exclude:microplastic strain",)


def test_labels_join_topics_and_are_one_row_per_work(tmp_path: Path) -> None:
    records = _fixture_records()
    normalized_result = normalize_fixture(
        FIXTURE,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "normalized",
        qc_path=tmp_path / "normalization_qc.md",
        generated_at="test",
    )
    normalized = pq.read_table(normalized_result.output_dir / "works.parquet").to_pylist()
    output = tmp_path / "work_labels.parquet"
    result = label_records(
        normalized,
        records,
        output_path=output,
        qc_path=tmp_path / "labels_qc.md",
        generated_at="test",
        source="test fixture",
    )
    table = pq.read_table(output)
    assert table.schema.equals(WORK_LABELS_SCHEMA)
    rows = table.to_pylist()
    assert [row["work_id"] for row in rows] == sorted(row["work_id"] for row in rows)
    assert len(rows) == len(normalized) == 5
    by_id = {row["work_id"]: row for row in rows}
    assert by_id["W9000000201"]["plastic_related"] is True
    assert by_id["W9000000202"]["plastic_related"] is True
    assert by_id["W9000000204"]["plastic_related"] is False
    assert by_id["W9000000205"]["plastic_tier"] == "chemicals-in-plastics"
    assert by_id["W9000000201"]["openalex_topic_names"] == ["Environmental science"]
    assert by_id["W9000000201"]["label_source"] == "rule"
    assert by_id["W9000000201"]["confidence"] is None
    assert "matrix:marine" in by_id["W9000000201"]["facet_tags"]
    assert result.metrics["missing_raw_work_rows"] == 0
    assert result.metrics["missing_topic_rows"] == 0


def test_missing_raw_and_topic_rows_are_retained_and_counted(tmp_path: Path) -> None:
    records = _fixture_records()
    records = [row for row in records if not row["id"].endswith("0205")]
    records[0]["topics"] = []
    normalized_result = normalize_fixture(
        FIXTURE,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "normalized",
        qc_path=tmp_path / "normalization_qc.md",
    )
    result = label_records(
        pq.read_table(normalized_result.output_dir / "works.parquet").to_pylist(),
        records,
        output_path=tmp_path / "work_labels.parquet",
        qc_path=tmp_path / "labels_qc.md",
        source="partial fixture",
    )
    assert result.metrics["label_rows"] == 5
    assert result.metrics["missing_raw_work_rows"] == 1
    assert result.metrics["missing_topic_rows"] == 2
    assert result.metrics["topic_id_rows"] == (
        result.metrics["matched_topic_rows"] + result.metrics["missing_topic_rows"]
    )
    assert "Missing raw work rows | 1" in result.qc_path.read_text(encoding="utf-8")
