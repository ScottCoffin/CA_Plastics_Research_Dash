"""Near-duplicate collapse during S2.2 normalization (AT-1 dedupe)."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from atlas.ingest.normalize import (
    _collapse_near_duplicates,
    collapse_near_duplicates,
    normalize_records,
    title_key,
)

TITLE = "Microplastic embossing process for polymer surfaces"


def _work(
    work_id: str,
    *,
    title: str = TITLE,
    year: int | None = 2020,
    type_: str = "article",
    doi: str = "",
    pub_date: str = "",
) -> dict:
    return {
        "work_id": work_id,
        "title": title,
        "year": year,
        "type": type_,
        "doi": doi,
        "pub_date": pub_date,
    }


def _ids(kept: list[dict]) -> list[str]:
    return sorted(row["work_id"] for row in kept)


def test_title_key_strips_punctuation_case_and_truncates() -> None:
    assert title_key("Microplastic  Embossing: Process!") == "microplasticembossingprocess"
    assert len(title_key("a" * 100)) == 60


def test_preprint_article_pair_collapses_to_article() -> None:
    kept, rows = collapse_near_duplicates(
        [_work("W2", type_="preprint", year=2021), _work("W1", year=2021)]
    )
    assert _ids(kept) == ["W1"]
    assert kept[0]["duplicate_work_ids"] == ["W2"]
    assert rows == [
        {
            "work_id": "W2",
            "duplicate_of": "W1",
            "title_key": title_key(TITLE),
            "reason": "same_title_key_within_year_window",
        }
    ]


def test_type_preference_order() -> None:
    order = [
        "article",
        "review",
        "book-chapter",
        "book",
        "conference-paper",
        "report",
        "preprint",
        "dataset",
    ]
    for index, preferred in enumerate(order[:-1]):
        worse = order[index + 1]
        kept, _ = collapse_near_duplicates(
            [_work("W1", type_=worse, year=2020), _work("W2", type_=preferred, year=2020)]
        )
        assert _ids(kept) == ["W2"], (preferred, worse)


def test_type_preference_is_before_doi_and_date() -> None:
    kept, _ = collapse_near_duplicates(
        [
            _work("W1", type_="book", doi="10.1/x", pub_date="2000-01-01", year=2020),
            _work("W2", type_="article", doi="", pub_date="2025-01-01", year=2020),
        ]
    )
    assert _ids(kept) == ["W2"]


def test_doi_preferred_within_same_type() -> None:
    kept, _ = collapse_near_duplicates(
        [
            _work("W1", type_="preprint", doi="", year=2024),
            _work("W2", type_="preprint", doi="10.1/abc", year=2024),
        ]
    )
    assert _ids(kept) == ["W2"]


def test_earlier_publication_date_preferred_then_lowest_work_id() -> None:
    kept, _ = collapse_near_duplicates(
        [
            _work("W3", pub_date="2020-05-01", year=2020, doi="10.1/a"),
            _work("W2", pub_date="2020-02-01", year=2020, doi="10.1/a"),
            _work("W1", pub_date="", year=2020, doi="10.1/a"),
        ]
    )
    assert _ids(kept) == ["W2"]
    tied, _ = collapse_near_duplicates(
        [_work("W9", year=2020), _work("W4", year=2020), _work("W7", year=2020)]
    )
    assert _ids(tied) == ["W4"]
    assert tied[0]["duplicate_work_ids"] == ["W7", "W9"]


def test_year_window_allows_one_year_and_chains() -> None:
    kept, _ = collapse_near_duplicates(
        [_work("W1", year=2020), _work("W2", year=2021), _work("W3", year=2022)]
    )
    # 2020-2021 and 2021-2022 chain into one cluster.
    assert _ids(kept) == ["W1"]


def test_year_gap_of_two_is_not_collapsed() -> None:
    kept, rows = collapse_near_duplicates(
        [_work("W1", year=2020), _work("W2", year=2022, type_="preprint")]
    )
    assert _ids(kept) == ["W1", "W2"]
    assert rows == []


def test_missing_year_is_not_collapsed() -> None:
    kept, rows = collapse_near_duplicates(
        [_work("W1", year=None), _work("W2", year=None, type_="preprint")]
    )
    assert _ids(kept) == ["W1", "W2"]
    assert rows == []


def test_short_title_key_is_skipped() -> None:
    short = "Short title here"  # key "shorttitlehere" is 14 characters
    assert len(title_key(short)) < 20
    kept, rows = collapse_near_duplicates(
        [_work("W1", title=short), _work("W2", title=short, type_="preprint")]
    )
    assert _ids(kept) == ["W1", "W2"]
    assert rows == []


def test_distinct_article_dois_are_not_collapsed() -> None:
    result = _collapse_near_duplicates(
        [
            _work("W1", doi="10.1/one", year=2020),
            _work("W2", doi="10.1/two", year=2020),
        ]
    )
    assert _ids(result.kept) == ["W1", "W2"]
    assert result.duplicate_rows == []
    assert result.skipped_distinct_doi == 1


def test_article_with_distinct_doi_still_collapses_into_non_article() -> None:
    # Only article-article pairs with different DOIs are protected.
    kept, rows = collapse_near_duplicates(
        [
            _work("W1", doi="10.1/one", year=2020),
            _work("W2", doi="10.1/two", year=2020, type_="preprint"),
        ]
    )
    assert _ids(kept) == ["W1"]
    assert rows[0]["duplicate_of"] == "W1"


def test_same_article_doi_case_insensitive_collapses() -> None:
    kept, _ = collapse_near_duplicates(
        [
            _work("W1", doi="10.1/ONE", year=2020),
            _work("W2", doi="10.1/one", year=2020),
        ]
    )
    assert _ids(kept) == ["W1"]


def test_pair_blocked_by_doi_still_merges_into_other_keeper() -> None:
    kept, rows = collapse_near_duplicates(
        [
            _work("W1", doi="10.1/one", year=2020),
            _work("W2", doi="10.1/two", year=2020),
            _work("W3", doi="", year=2020, type_="preprint"),
        ]
    )
    assert _ids(kept) == ["W1", "W2"]
    assert [row["work_id"] for row in rows] == ["W3"]
    assert rows[0]["duplicate_of"] == "W1"


def test_authorships_repointed_and_deduped(tmp_path: Path) -> None:
    fixture = [
        {
            "id": "https://openalex.org/W100",
            "title": TITLE,
            "publication_year": 2021,
            "publication_date": "2021-06-01",
            "type": "article",
            "doi": "https://doi.org/10.1/article",
            "authorships": [
                {
                    "author": {"id": "https://openalex.org/A1", "display_name": "Ada"},
                    "author_position": "first",
                    "institutions": [],
                    "raw_affiliation_strings": ["Univ X"],
                },
            ],
        },
        {
            "id": "https://openalex.org/W200",
            "title": TITLE,
            "publication_year": 2021,
            "publication_date": "2021-01-01",
            "type": "preprint",
            "doi": "",
            "authorships": [
                {
                    "author": {"id": "https://openalex.org/A1", "display_name": "Ada"},
                    "author_position": "first",
                    "institutions": [],
                    "raw_affiliation_strings": ["Univ X"],
                },
                {
                    "author": {"id": "https://openalex.org/A2", "display_name": "Bo"},
                    "author_position": "last",
                    "institutions": [],
                    "raw_affiliation_strings": ["Univ Y"],
                },
            ],
        },
    ]
    result = normalize_records(
        fixture,
        institution_path=Path("data/processed/institutions.parquet"),
        output_dir=tmp_path / "processed",
        qc_path=tmp_path / "qc.md",
        source="test",
        author_overrides_path=tmp_path / "missing_overrides.csv",
        generated_at="test",
    )
    works = pq.read_table(result.output_dir / "works.parquet").to_pylist()
    assert [row["work_id"] for row in works] == ["W100"]
    assert works[0]["duplicate_work_ids"] == ["W200"]
    authorships = pq.read_table(result.output_dir / "authorships.parquet").to_pylist()
    pairs = sorted((row["work_id"], row["author_id"]) for row in authorships)
    assert pairs == [("W100", "A1"), ("W100", "A2")]
    assert result.metrics["works"] == 1
    assert result.metrics["near_duplicates_collapsed"] == 1
    assert result.metrics["near_duplicate_groups"] == 1
    assert result.metrics["skipped_same_title_distinct_doi"] == 0
    authors = {
        row["author_id"]: row
        for row in pq.read_table(result.output_dir / "authors.parquet").to_pylist()
    }
    assert authors["A2"]["first_year"] == 2021
    report = result.qc_path.read_text(encoding="utf-8")
    assert "Near-duplicate works collapsed into a kept work | 1" in report
