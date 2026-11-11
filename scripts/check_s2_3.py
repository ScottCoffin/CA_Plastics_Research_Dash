"""Machine acceptance checks for S2.3 provisional work labels."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

from atlas.ingest.normalize import normalize_fixture
from atlas.nlp.labels import WORK_LABELS_SCHEMA, classify_plastic_text, label_records

FIXTURE = Path("tests/fixtures/s2_3_openalex_works.json")
INSTITUTIONS = Path("data/processed/institutions.parquet")
PROTECTED_FILES = (
    Path(".agent/QUESTIONS.md"),
    Path("data/processed/institution_review_top100.csv"),
    Path("data/processed/institutions.parquet"),
    Path("docs/institutions_qc.md"),
    Path("docs/AWARDS_DATA.md"),
)


def _digest(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture() -> list[dict]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert isinstance(payload, list) and 0 < len(payload) <= 200
    return payload


def main() -> None:
    before = {path: _digest(path) for path in PROTECTED_FILES}
    records = _fixture()
    with tempfile.TemporaryDirectory(prefix="s2-3-acceptance-") as directory:
        root = Path(directory)
        normalized_result = normalize_fixture(
            FIXTURE,
            institution_path=INSTITUTIONS,
            output_dir=root / "normalized",
            qc_path=root / "normalization_qc.md",
            generated_at="acceptance",
        )
        normalized = pq.read_table(normalized_result.output_dir / "works.parquet").to_pylist()
        first = label_records(
            normalized,
            records,
            output_path=root / "labels-1.parquet",
            qc_path=root / "labels-1.md",
            source="S2.3 fixture",
            generated_at="acceptance",
        )
        second = label_records(
            normalized,
            records,
            output_path=root / "labels-2.parquet",
            qc_path=root / "labels-2.md",
            source="S2.3 fixture",
            generated_at="acceptance",
        )
        first_rows = pq.read_table(first.output_path).to_pylist()
        second_rows = pq.read_table(second.output_path).to_pylist()
        assert pq.read_table(first.output_path).schema.equals(WORK_LABELS_SCHEMA)
        assert first_rows == second_rows
        assert first.qc_path.read_text(encoding="utf-8") == second.qc_path.read_text(
            encoding="utf-8"
        )
        assert [row["work_id"] for row in first_rows] == sorted(
            row["work_id"] for row in first_rows
        )
        assert len(first_rows) == len(normalized) == len({row["work_id"] for row in first_rows})
        assert all(row["label_source"] == "rule" for row in first_rows)
        assert all(row["model_version"] == "plastic-v3.1-rule-v1" for row in first_rows)
        assert all(row["confidence"] is None for row in first_rows)
        by_id = {row["work_id"]: row for row in first_rows}
        assert by_id["W9000000201"]["plastic_related"] is True
        assert by_id["W9000000201"]["openalex_topic_names"] == ["Environmental science"]
        assert by_id["W9000000202"]["plastic_related"] is True
        assert by_id["W9000000204"]["plastic_related"] is False
        assert by_id["W9000000205"]["plastic_tier"] == "chemicals-in-plastics"
        assert first.metrics["normalized_work_rows"] == first.metrics["label_rows"]
        assert (
            first.metrics["raw_work_rows"] + first.metrics["missing_raw_work_rows"]
            == first.metrics["normalized_work_rows"]
        )
        assert (
            first.metrics["topic_id_rows"]
            == first.metrics["matched_topic_rows"] + first.metrics["missing_topic_rows"]
        )
        qc = first.qc_path.read_text(encoding="utf-8")
        assert "Missing raw work rows | 0" in qc
        assert "Missing raw topic-name rows | 0" in qc
        assert "label_source=rule" in qc

        # Exercise missing-source retention and the ordered rule contract.
        partial = [row for row in records if not row["id"].endswith("0205")]
        partial[0]["topics"] = []
        missing = label_records(
            normalized,
            partial,
            output_path=root / "labels-missing.parquet",
            qc_path=root / "labels-missing.md",
            source="partial fixture",
        )
        assert missing.metrics["label_rows"] == len(normalized)
        assert missing.metrics["missing_raw_work_rows"] == 1
        assert missing.metrics["missing_topic_rows"] == 2

    import yaml

    query_config = yaml.safe_load(Path("config/queries.yml").read_text(encoding="utf-8"))
    assert classify_plastic_text("microfiber without context", query_config).related is False
    assert classify_plastic_text("microfiber textile laundry", query_config).related is True
    assert classify_plastic_text("microplastic strain deformation", query_config).related is False
    after = {path: _digest(path) for path in PROTECTED_FILES}
    assert before == after, "S2.3 changed a protected pre-existing artifact"
    print(
        "S2.3 acceptance passed: deterministic labels, ordered rules, topic coverage, "
        "and immutability verified"
    )


if __name__ == "__main__":
    main()
