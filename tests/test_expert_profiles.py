import csv
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from atlas.build.expert_profiles import BIO_MAX_CHARS, load_expert_profiles
from atlas.build.export_site import export_site
from atlas.ingest.normalize import normalize_fixture

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "s2_2_openalex_works.json"
INSTITUTIONS = ROOT / "data" / "processed" / "institutions.parquet"

PHOTO_HEADER = [
    "author_id",
    "wikidata_label",
    "atlas_profile_url",
    "wikidata_url",
    "commons_page_url",
    "license_short",
    "credit",
    "thumb_url",
    "owner_decision",
    "owner_notes",
]
THUMB = "https://upload.wikimedia.org/thumb/a.jpg"
COMMONS = "https://commons.wikimedia.org/wiki/File:A.jpg"


def _orcid_fixture(path: Path, rows: list[dict]) -> Path:
    schema = pa.schema(
        [
            ("author_id", pa.string()),
            ("orcid", pa.string()),
            ("biography", pa.string()),
            ("keywords", pa.list_(pa.string())),
            (
                "researcher_urls",
                pa.list_(pa.struct([("name", pa.string()), ("url", pa.string())])),
            ),
        ]
    )
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
    return path


def _photo_fixture(path: Path, rows: list[dict]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PHOTO_HEADER)
        writer.writeheader()
        for row in rows:
            base = {key: "" for key in PHOTO_HEADER}
            base.update(row)
            writer.writerow(base)
    return path


def _profile_row(author_id: str, **overrides) -> dict:
    row = {
        "author_id": author_id,
        "orcid": f"https://orcid.org/0000-0000-0000-{author_id[-4:]}",
        "biography": "",
        "keywords": [],
        "researcher_urls": [],
    }
    row.update(overrides)
    return row


def test_approved_photo_is_the_only_photo(tmp_path: Path) -> None:
    orcid = _orcid_fixture(
        tmp_path / "orcid.parquet",
        [_profile_row("A1", biography="Studies microplastics."), _profile_row("A2", biography="x")],
    )
    photos = _photo_fixture(
        tmp_path / "photos.csv",
        [
            {
                "author_id": "A1",
                "thumb_url": THUMB,
                "commons_page_url": COMMONS,
                "license_short": "CC BY-SA 3.0",
                "credit": "VRT",
                "owner_decision": " Approve ",
            },
            {
                "author_id": "A2",
                "thumb_url": THUMB,
                "commons_page_url": COMMONS,
                "license_short": "CC0",
                "credit": "Someone",
                "owner_decision": "reject",
            },
        ],
    )
    profiles = load_expert_profiles(orcid, photos)
    assert profiles["A1"]["photo"] == {
        "thumb_url": THUMB,
        "license": "CC BY-SA 3.0",
        "credit": "VRT",
        "source_url": COMMONS,
    }
    assert "photo" not in profiles["A2"]


def test_pending_photo_is_not_used(tmp_path: Path) -> None:
    orcid = _orcid_fixture(tmp_path / "orcid.parquet", [_profile_row("A1", biography="Bio.")])
    photos = _photo_fixture(
        tmp_path / "photos.csv",
        [{"author_id": "A1", "thumb_url": THUMB, "owner_decision": ""}],
    )
    assert "photo" not in load_expert_profiles(orcid, photos)["A1"]


def test_keywords_are_split_on_commas_and_deduped(tmp_path: Path) -> None:
    keywords = ["Biorefinery, lignocellulosic biomass, wastewater treatment", "biorefinery", " "]
    keywords += [f"term {i}" for i in range(20)]
    orcid = _orcid_fixture(tmp_path / "orcid.parquet", [_profile_row("A1", keywords=keywords)])
    found = load_expert_profiles(orcid, None)["A1"]["keywords"]
    assert found[:3] == ["Biorefinery", "lignocellulosic biomass", "wastewater treatment"]
    assert len(found) == 12
    assert len({k.casefold() for k in found}) == len(found)


def test_non_http_links_are_dropped_and_labels_fall_back_to_host(tmp_path: Path) -> None:
    links = [
        {"name": "", "url": "https://www.example.edu/lab"},
        {"name": "Lab page", "url": "http://example.org/x"},
        {"name": "Bad", "url": "javascript:alert(1)"},
        {"name": "Mail", "url": "mailto:someone@example.edu"},
        {"name": "Relative", "url": "/local/path"},
        {"name": None, "url": None},
    ]
    orcid = _orcid_fixture(tmp_path / "orcid.parquet", [_profile_row("A1", researcher_urls=links)])
    found = load_expert_profiles(orcid, None)["A1"]["links"]
    assert found == [
        {"label": "www.example.edu", "url": "https://www.example.edu/lab"},
        {"label": "Lab page", "url": "http://example.org/x"},
    ]


def test_contact_content_is_dropped(tmp_path: Path) -> None:
    bio = "Works on polymers. Contact someone@example.edu for data. Studies fibres."
    orcid = _orcid_fixture(
        tmp_path / "orcid.parquet",
        [
            _profile_row(
                "A1",
                biography=bio,
                keywords=["fibres", "write to a@b.org"],
                researcher_urls=[{"name": "Mail", "url": "mailto:x@example.edu"}],
            )
        ],
    )
    found = load_expert_profiles(orcid, None)["A1"]
    assert found["bio"] == "Works on polymers. Studies fibres."
    assert found["keywords"] == ["fibres"]
    assert found["links"] == []
    assert "@" not in json.dumps(found)


def test_bio_is_truncated_at_a_word_boundary(tmp_path: Path) -> None:
    long_bio = " ".join(f"word{i}" for i in range(300))
    orcid = _orcid_fixture(tmp_path / "orcid.parquet", [_profile_row("A1", biography=long_bio)])
    bio = load_expert_profiles(orcid, None)["A1"]["bio"]
    assert bio.endswith("…")
    assert len(bio) <= BIO_MAX_CHARS
    body = bio[:-1]
    assert long_bio.startswith(body)
    assert long_bio[len(body)] == " "


def test_authors_with_nothing_to_show_are_omitted(tmp_path: Path) -> None:
    orcid = _orcid_fixture(tmp_path / "orcid.parquet", [_profile_row("A1")])
    assert load_expert_profiles(orcid, None) == {}


def test_missing_inputs_give_empty_profiles(tmp_path: Path) -> None:
    assert load_expert_profiles(tmp_path / "none.parquet", tmp_path / "none.csv") == {}
    assert load_expert_profiles(None, "") == {}


def test_export_without_profiles_writes_no_profile_key(tmp_path: Path) -> None:
    normalized = normalize_fixture(
        FIXTURE,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "normalized",
        qc_path=tmp_path / "qc.md",
        generated_at="test",
    )
    kwargs = {
        "works_path": normalized.output_dir / "works.parquet",
        "authors_path": normalized.output_dir / "authors.parquet",
        "authorships_path": normalized.output_dir / "authorships.parquet",
        "institutions_path": normalized.output_dir / "institutions.parquet",
        "generated_at": "test",
        "ca_authors_only": False,
    }
    default = export_site(output_dir=tmp_path / "default", **kwargs)
    explicit = export_site(output_dir=tmp_path / "none", profiles=None, **kwargs)
    for path in sorted((default.output_dir / "authors").glob("*.json")):
        other = explicit.output_dir / "authors" / path.name
        assert path.read_bytes() == other.read_bytes()
        assert "profile" not in json.loads(path.read_text(encoding="utf-8"))


def test_export_adds_profile_only_for_profiled_author(tmp_path: Path) -> None:
    normalized = normalize_fixture(
        FIXTURE,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "normalized",
        qc_path=tmp_path / "qc.md",
        generated_at="test",
    )
    kwargs = {
        "works_path": normalized.output_dir / "works.parquet",
        "authors_path": normalized.output_dir / "authors.parquet",
        "authorships_path": normalized.output_dir / "authorships.parquet",
        "institutions_path": normalized.output_dir / "institutions.parquet",
        "generated_at": "test",
        "ca_authors_only": False,
    }
    first = export_site(output_dir=tmp_path / "probe", **kwargs)
    author_ids = sorted(path.stem for path in (first.output_dir / "authors").glob("*.json"))
    assert len(author_ids) >= 2
    target, other = author_ids[0], author_ids[1]
    profile = {"bio": "Studies plastics.", "keywords": ["polymers"], "links": []}
    result = export_site(output_dir=tmp_path / "site", profiles={target: profile}, **kwargs)
    detail = json.loads((result.output_dir / "authors" / f"{target}.json").read_text("utf-8"))
    assert detail["profile"] == profile
    assert set(detail) == {"schema_version", "author", "works", "profile"}
    untouched = json.loads((result.output_dir / "authors" / f"{other}.json").read_text("utf-8"))
    assert "profile" not in untouched


def test_site_drawer_renders_profile_html() -> None:
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert "function profileHtml" in html
    assert "${profileHtml(detail.profile, author.name)}" in html
