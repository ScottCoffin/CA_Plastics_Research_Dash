"""S2.6: repair OpenAlex authorships whose author ID is null (offline, synthetic records)."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.build.curation import SUPPRESSIONS_HEADER
from atlas.ingest.author_repair import (
    ATTACH_HEADER,
    ORCID_IDS_HEADER,
    build_orcid_index,
    load_attach_rows,
    load_orcid_author_ids,
    normalize_name,
    repair_author_ids,
)
from atlas.ingest.normalize import normalize_records

ROOT = Path(__file__).resolve().parents[1]
WAGNER = "A5072641519"
CDPH = "I1336788258"
OTHER = "I2000000002"
ORCID = "0000-0003-4337-622X"
ORCID_B = "0000-0001-0000-0002"


def _author(author_id: str | None, name: str, orcid: str | None = None) -> dict[str, Any]:
    return {
        "id": f"https://openalex.org/{author_id}" if author_id else None,
        "display_name": name,
        "orcid": f"https://orcid.org/{orcid}" if orcid else None,
    }


def _authorship(
    author_id: str | None,
    name: str,
    *,
    orcid: str | None = None,
    institutions: tuple[str, ...] = (),
) -> dict[str, Any]:
    return {
        "author": _author(author_id, name, orcid),
        "institutions": [{"id": f"https://openalex.org/{inst}"} for inst in institutions],
    }


def _works(**works: list[Any]) -> dict[str, dict[str, Any]]:
    return {
        work_id: {"id": f"https://openalex.org/{work_id}", "authorships": authorships}
        for work_id, authorships in works.items()
    }


def _attach(work_id: str, name: str, target: str) -> dict[str, str]:
    return {
        "work_id": work_id,
        "author_name": name,
        "to_author_id": target,
        "reason": "test",
        "reviewed_by": "SC",
        "reviewed_at": "2026-11-15",
    }


def _counts(**values: int) -> dict[str, int]:
    counts = {"curated": 0, "orcid": 0, "name_institution": 0, "unresolved": 0}
    counts.update(values)
    return counts


def test_curated_row_attaches_null_authorship_by_full_name() -> None:
    works = _works(W1=[_authorship(None, "Jeff Wagner")])
    resolved, counts = repair_author_ids(works, {}, [_attach("W1", "Jeff Wagner", WAGNER)])
    assert resolved == {("W1", 0): (WAGNER, "curated")}
    assert counts == _counts(curated=1)


def test_curated_name_must_match_the_full_name() -> None:
    works = _works(W1=[_authorship(None, "Jeff Wagner")])
    resolved, counts = repair_author_ids(works, {}, [_attach("W1", "J. Wagner", WAGNER)])
    assert resolved == {}
    assert counts == _counts(unresolved=1)


def test_curated_row_needs_a_target_and_a_matching_work() -> None:
    works = _works(W1=[_authorship(None, "Jeff Wagner")], W2=[_authorship(None, "Jeff Wagner")])
    rows = [_attach("W1", "Jeff Wagner", ""), _attach("W9", "Jeff Wagner", WAGNER)]
    resolved, counts = repair_author_ids(works, {}, rows)
    assert resolved == {}
    assert counts == _counts(unresolved=2)


def test_curated_row_beats_orcid() -> None:
    works = _works(
        W1=[_authorship(None, "Jeff Wagner", orcid=ORCID)],
        W2=[_authorship(WAGNER, "Jeff Wagner", orcid=ORCID)],
    )
    resolved, counts = repair_author_ids(works, {}, [_attach("W1", "Jeff Wagner", "A9000000001")])
    assert resolved == {("W1", 0): ("A9000000001", "curated")}
    assert counts == _counts(curated=1)


def test_orcid_index_fills_null_authorship() -> None:
    works = _works(
        W1=[_authorship(WAGNER, "Jeff Wagner", orcid=ORCID)],
        W2=[_authorship(None, "Jeff Wagner", orcid=ORCID)],
    )
    resolved, counts = repair_author_ids(works, {}, [])
    assert resolved == {("W2", 0): (WAGNER, "orcid")}
    assert counts == _counts(orcid=1)


def test_repair_never_duplicates_an_author_on_the_same_work() -> None:
    works = _works(
        W1=[
            _authorship(WAGNER, "Jeff Wagner", orcid=ORCID),
            _authorship(None, "Jeff Wagner", orcid=ORCID),
        ],
        W2=[
            _authorship(None, "Jeff Wagner", orcid=ORCID),
            _authorship(None, "J. Wagner", orcid=ORCID),
        ],
    )
    resolved, counts = repair_author_ids(works, {}, [])
    assert resolved == {("W2", 0): (WAGNER, "orcid")}
    assert counts == _counts(orcid=1, unresolved=2)


def test_orcid_csv_wins_over_the_raw_index() -> None:
    works = _works(
        W1=[_authorship(WAGNER, "Jeff Wagner", orcid=ORCID)],
        W2=[_authorship(None, "Jeff Wagner", orcid=ORCID)],
    )
    resolved, _ = repair_author_ids(works, {ORCID: "A9000000002"}, [])
    assert resolved == {("W2", 0): ("A9000000002", "orcid")}


def test_ambiguous_raw_orcid_is_not_used_but_the_csv_can_resolve_it() -> None:
    works = _works(
        W1=[_authorship(WAGNER, "Jeff Wagner", orcid=ORCID)],
        W2=[_authorship("A9000000003", "Jeff Wagner", orcid=ORCID)],
        W3=[_authorship(None, "Someone Else", orcid=ORCID)],
    )
    assert build_orcid_index(works) == {}
    resolved, counts = repair_author_ids(works, {}, [])
    assert resolved == {}
    assert counts == _counts(unresolved=1)
    resolved, _ = repair_author_ids(works, {ORCID: "A9000000004"}, [])
    assert resolved == {("W3", 0): ("A9000000004", "orcid")}


def test_blank_csv_author_id_is_ignored_and_the_index_still_applies() -> None:
    works = _works(
        W1=[_authorship(WAGNER, "Jeff Wagner", orcid=ORCID)],
        W2=[_authorship(None, "Jeff Wagner", orcid=ORCID)],
    )
    resolved, _ = repair_author_ids(works, {ORCID: ""}, [])
    assert resolved == {("W2", 0): (WAGNER, "orcid")}


def test_orcid_url_prefix_and_case_are_ignored() -> None:
    works = _works(
        W1=[_authorship(WAGNER, "Jeff Wagner", orcid=ORCID)],
        W2=[_authorship(None, "Jeff Wagner", orcid="0000-0003-4337-622x")],
    )
    resolved, _ = repair_author_ids(works, {}, [])
    assert resolved == {("W2", 0): (WAGNER, "orcid")}
    resolved, _ = repair_author_ids(
        works, {"https://orcid.org/0000-0003-4337-622x": "A9000000005"}, []
    )
    assert resolved == {("W2", 0): ("A9000000005", "orcid")}


def test_name_and_institution_attaches_when_exactly_one_author_matches() -> None:
    works = _works(
        W1=[_authorship(WAGNER, "Jeff Wagner", institutions=(CDPH,))],
        W2=[_authorship(None, "Jeff Wagner", institutions=(CDPH,))],
    )
    resolved, counts = repair_author_ids(works, {}, [])
    assert resolved == {("W2", 0): (WAGNER, "name_institution")}
    assert counts == _counts(name_institution=1)


def test_name_and_institution_ambiguity_stays_unresolved() -> None:
    works = _works(
        W1=[_authorship(WAGNER, "Jeff Wagner", institutions=(CDPH,))],
        W2=[_authorship("A9000000006", "Jeff Wagner", institutions=(CDPH,))],
        W3=[_authorship(None, "Jeff Wagner", institutions=(CDPH,))],
    )
    resolved, counts = repair_author_ids(works, {}, [])
    assert resolved == {}
    assert counts == _counts(unresolved=1)


def test_name_and_institution_counts_candidates_across_institutions() -> None:
    works = _works(
        W1=[_authorship(WAGNER, "Jeff Wagner", institutions=(CDPH,))],
        W2=[_authorship("A9000000006", "Jeff Wagner", institutions=(OTHER,))],
        W3=[_authorship(None, "Jeff Wagner", institutions=(CDPH, OTHER))],
        W4=[_authorship(None, "Jeff Wagner", institutions=(CDPH, "I3000000003"))],
    )
    resolved, counts = repair_author_ids(works, {}, [])
    assert resolved == {("W4", 0): (WAGNER, "name_institution")}
    assert counts == _counts(name_institution=1, unresolved=1)


def test_name_variants_do_not_match() -> None:
    works = _works(
        W1=[_authorship(WAGNER, "Jeff Wagner", institutions=(CDPH,))],
        W2=[_authorship(None, "J. Wagner", institutions=(CDPH,))],
        W3=[_authorship(None, "Jeffrey Wagner", institutions=(CDPH,))],
    )
    resolved, counts = repair_author_ids(works, {}, [])
    assert resolved == {}
    assert counts == _counts(unresolved=2)


def test_name_and_institution_needs_a_shared_institution() -> None:
    works = _works(
        W1=[_authorship(WAGNER, "Jeff Wagner", institutions=(OTHER,))],
        W2=[_authorship(None, "Jeff Wagner", institutions=(CDPH,))],
    )
    resolved, counts = repair_author_ids(works, {}, [])
    assert resolved == {}
    assert counts == _counts(unresolved=1)


def test_orcid_fill_enables_a_name_and_institution_attach_on_another_work() -> None:
    works = _works(
        # No institution here, so this ID contributes no name+institution pair by itself.
        W1=[_authorship(WAGNER, "Jeff Wagner", orcid=ORCID)],
        # Filled through the ORCID index; its institution then makes the pair known.
        W2=[_authorship(None, "Jeff Wagner", orcid=ORCID, institutions=(CDPH,))],
        W3=[_authorship(None, "Jeff Wagner", institutions=(CDPH,))],
    )
    resolved, counts = repair_author_ids(works, {}, [])
    assert resolved == {
        ("W2", 0): (WAGNER, "orcid"),
        ("W3", 0): (WAGNER, "name_institution"),
    }
    assert counts == _counts(orcid=1, name_institution=1)


def test_name_and_institution_fills_do_not_feed_further_fills() -> None:
    works = _works(
        W1=[_authorship(WAGNER, "Jeff Wagner", institutions=(CDPH,))],
        W2=[_authorship(None, "Jeff Wagner", institutions=(CDPH, OTHER))],
        W3=[_authorship(None, "Jeff Wagner", institutions=(OTHER,))],
    )
    resolved, counts = repair_author_ids(works, {}, [])
    assert resolved == {("W2", 0): (WAGNER, "name_institution")}
    assert counts == _counts(name_institution=1, unresolved=1)


def test_authorships_without_identifiers_stay_unresolved() -> None:
    works = _works(
        W1=[_authorship(None, ""), _authorship(None, "Nobody Known", institutions=(CDPH,))]
    )
    resolved, counts = repair_author_ids(works, {}, [])
    assert resolved == {}
    assert counts == _counts(unresolved=2)


def test_keys_follow_the_authorship_position_including_non_mapping_entries() -> None:
    works = _works(
        W1=[None, _authorship(WAGNER, "Jeff Wagner"), _authorship(None, "Jeff Wagner")],
    )
    resolved, _ = repair_author_ids(works, {}, [_attach("W1", "Jeff Wagner", "A9000000007")])
    assert resolved == {("W1", 2): ("A9000000007", "curated")}


def test_missing_or_header_only_curation_files_mean_empty_input(tmp_path: Path) -> None:
    assert load_attach_rows(tmp_path / "missing.csv") == []
    assert load_orcid_author_ids(None) == {}
    header_only = tmp_path / "orcid.csv"
    header_only.write_text(",".join(ORCID_IDS_HEADER) + "\n", encoding="utf-8")
    assert load_orcid_author_ids(header_only) == {}


def test_loaders_drop_blank_author_ids(tmp_path: Path) -> None:
    orcid_path = tmp_path / "orcid.csv"
    _write_csv(
        orcid_path,
        ORCID_IDS_HEADER,
        [
            {"orcid": ORCID, "author_id": " A9000000008 ", "display_name": "", "fetched_at": ""},
            {"orcid": ORCID_B, "author_id": "", "display_name": "", "fetched_at": ""},
        ],
    )
    assert load_orcid_author_ids(orcid_path) == {ORCID: "A9000000008"}
    attach_path = tmp_path / "attach.csv"
    _write_csv(attach_path, ATTACH_HEADER, [_attach("W1", "Jeff Wagner", WAGNER)])
    assert load_attach_rows(attach_path)[0]["to_author_id"] == WAGNER


def _write_csv(path: Path, header: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _registry(tmp_path: Path) -> Path:
    path = tmp_path / "institutions.parquet"
    rows = [
        {
            "openalex_id": f"https://openalex.org/{CDPH}",
            "display_name": "CDPH",
            "region": "California",
            "country_code": "US",
        },
        {
            "openalex_id": f"https://openalex.org/{OTHER}",
            "display_name": "Other University",
            "region": "Oregon",
            "country_code": "US",
        },
    ]
    pq.write_table(pa.Table.from_pylist(rows), path)
    return path


def _record(work_id: str, title: str, *authorships: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": f"https://openalex.org/{work_id}",
        "title": title,
        "publication_year": 2024,
        "type": "article",
        "authorships": list(authorships),
    }


def _normalize(
    tmp_path: Path,
    works: list[dict[str, Any]],
    *,
    attach: list[dict[str, str]] | None = None,
    orcid_rows: dict[str, str] | None = None,
    suppressed: tuple[str, ...] = (),
):
    attach_path = tmp_path / "author_attach.csv"
    _write_csv(attach_path, ATTACH_HEADER, attach or [])
    orcid_path = tmp_path / "orcid_author_ids.csv"
    _write_csv(
        orcid_path,
        ORCID_IDS_HEADER,
        [
            {"orcid": key, "author_id": value, "display_name": "", "fetched_at": ""}
            for key, value in (orcid_rows or {}).items()
        ],
    )
    suppressions_path = tmp_path / "suppressions.csv"
    _write_csv(
        suppressions_path,
        SUPPRESSIONS_HEADER,
        [
            {
                "kind": "author",
                "id": author,
                "reason": "test",
                "requested_at": "2026-11-15",
                "reviewed_by": "SC",
            }
            for author in suppressed
        ],
    )
    return normalize_records(
        works,
        institution_path=_registry(tmp_path),
        output_dir=tmp_path / "normalized",
        qc_path=tmp_path / "normalization_qc.md",
        source="synthetic",
        author_overrides_path=tmp_path / "no_overrides.csv",
        suppressions_path=suppressions_path,
        generated_at="test",
        state_agencies_path=None,
        escholarship_path=None,
        orcid_profiles_path=None,
        author_attach_path=attach_path,
        orcid_author_ids_path=orcid_path,
    )


def test_author_id_source_values_in_normalized_output(tmp_path: Path) -> None:
    works = [
        _record("W1", "Alpha study", _authorship(WAGNER, "Jeff Wagner", institutions=(CDPH,))),
        _record("W2", "Beta study", _authorship(None, "Curated Person")),
        _record("W3", "Gamma study", _authorship(None, "Orcid Person", orcid=ORCID_B)),
        _record("W4", "Delta study", _authorship("A9000000008", "Orcid Person", orcid=ORCID_B)),
        _record("W5", "Epsilon study", _authorship(None, "Jeff Wagner", institutions=(CDPH,))),
        _record("W6", "Zeta study", _authorship(None, "Nobody Known")),
    ]
    result = _normalize(
        tmp_path,
        works,
        attach=[_attach("W2", "Curated Person", "A9000000009")],
    )
    rows = pq.read_table(result.output_dir / "authorships.parquet").to_pylist()
    by_work = {row["work_id"]: (row["author_id"], row["author_id_source"]) for row in rows}
    assert by_work == {
        "W1": (WAGNER, "openalex"),
        "W2": ("A9000000009", "curated"),
        "W3": ("A9000000008", "orcid"),
        "W4": ("A9000000008", "openalex"),
        "W5": (WAGNER, "name_institution"),
        "W6": ("", ""),
    }
    assert result.metrics["null_author_ids"] == 4
    assert result.author_id_repairs == {
        "null_author_ids_after_repair": 1,
        "author_ids_repaired_curated": 1,
        "author_ids_repaired_orcid": 1,
        "author_ids_repaired_name_institution": 1,
    }
    qc = result.qc_path.read_text(encoding="utf-8")
    assert "| Authorships with null author IDs | 4 |" in qc
    assert "| Authorships with null author IDs after repair | 1 |" in qc


def test_suppressed_author_stays_suppressed_after_repair(tmp_path: Path) -> None:
    works = [
        _record("W1", "Alpha study", _authorship("A9000000010", "Suppressed Person", orcid=ORCID)),
        _record("W2", "Beta study", _authorship(None, "Suppressed Person", orcid=ORCID)),
        _record("W3", "Gamma study", _authorship(None, "Other Person")),
    ]
    result = _normalize(tmp_path, works, suppressed=("A9000000010",))
    rows = pq.read_table(result.output_dir / "authorships.parquet").to_pylist()
    assert [row["work_id"] for row in rows] == ["W3"]
    assert all(row["author_id"] != "A9000000010" for row in rows)
    authors = pq.read_table(result.output_dir / "authors.parquet").to_pylist()
    assert all(row["author_id"] != "A9000000010" for row in authors)


def _load_build_author_merges():
    spec = importlib.util.spec_from_file_location(
        "build_author_merges", ROOT / "scripts" / "build_author_merges.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_author_merges_uses_the_shared_normalize_name() -> None:
    assert _load_build_author_merges().normalize_name is normalize_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Andrew B. Gray", "andrew b gray"),
        ("Andrew Gray", "andrew gray"),
        ("José Ñandú", "jose nandu"),
        ("Jean-Luc Picard", "jean luc picard"),
        ("Ana‐Maria", "ana maria"),
        ("  O'Brien,  Dr. ", "o brien dr"),
        ("", ""),
    ],
)
def test_normalize_name_is_unchanged(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


def test_build_author_merges_rule_is_unchanged() -> None:
    merges = _load_build_author_merges()
    authors = [
        {"author_id": "A1", "name": "Andrew B. Gray", "ca_works_count": 2},
        {"author_id": "A2", "name": "andrew b gray", "ca_works_count": 0},
        {"author_id": "A3", "name": "Andrew Gray", "ca_works_count": 1},
    ]
    authorships = [
        {"work_id": "W1", "author_id": "A1", "institution_ids": ["I1"]},
        {"work_id": "W2", "author_id": "A2", "institution_ids": ["I1"]},
        {"work_id": "W3", "author_id": "A3", "institution_ids": ["I1"]},
    ]
    assert merges.merge_rows(authors, authorships) == [
        {
            "from_author_id": "A2",
            "to_author_id": "A1",
            "reason": "auto: same name and institution (andrew b gray)",
            "reviewed_by": "SC (rule)",
            "reviewed_at": "2026-11-11",
        }
    ]
