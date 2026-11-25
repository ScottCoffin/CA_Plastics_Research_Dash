"""Region data folders (PLAT-3 slice 3): site_data_dir validation, region_data_dir, threading.

Every write goes to tmp_path. REPO_ROOT is pointed at a tmp repo so that defaults never touch
the real site/data/.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

from atlas.build.export_site import export_site
from atlas.ingest import daily
from atlas.ingest.normalize import normalize_fixture
from atlas.regions import scope
from atlas.regions.registry import REPO_ROOT, Region, get_region, parse_registry

REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "scripts" / "run_daily_works.py"
FIXTURE = Path("tests/fixtures/s2_2_openalex_works.json")
INSTITUTIONS = Path("data/processed/institutions.parquet")


def _doc(site_data_dir: object = "absent", slug: str = "california") -> dict:
    """A minimal valid registry: global root plus one Tier A region with a predicate."""
    region: dict = {
        "slug": slug,
        "name": "Test region",
        "tier": "A",
        "parent": None,
        "status": "active",
        "predicate": {"country_codes": ["US"]},
    }
    if site_data_dir != "absent":
        region["site_data_dir"] = site_data_dir
    return {
        "schema_version": 1,
        "regions": [
            {
                "slug": "global",
                "name": "Global",
                "tier": "root",
                "parent": None,
                "status": "active",
                "predicate": None,
            },
            region,
        ],
    }


def _region(site_data_dir: object = "absent", slug: str = "norway") -> Region:
    return parse_registry(_doc(site_data_dir, slug=slug)).get(slug)


# --- default and explicit folders -------------------------------------------------------


def test_california_data_dir_is_site_data_california() -> None:
    assert (
        scope.region_data_dir(get_region("california"))
        == REPO_ROOT / "site" / "data" / "california"
    )
    assert scope.region_data_dir() == scope.region_data_dir(get_region("california"))


def test_region_without_field_defaults_to_slug_folder() -> None:
    region = _region()
    assert region.site_data_dir is None
    assert scope.region_data_dir(region) == REPO_ROOT / "site" / "data" / "norway"


def test_explicit_field_is_used_and_normalised() -> None:
    region = _region("site/data/norway/")
    assert region.site_data_dir == "site/data/norway"
    assert scope.region_data_dir(region) == REPO_ROOT / "site" / "data" / "norway"


def test_real_registry_california_field_is_site_data_california() -> None:
    assert get_region("california").site_data_dir == "site/data/california"


def test_region_yml_data_dir_matches_registry_field() -> None:
    config = yaml.safe_load((REPO / "regions" / "california" / "region.yml").read_text("utf-8"))
    assert config["data_dir"].rstrip("/") == get_region("california").site_data_dir


# --- validation --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "../outside",
        "site/data/../../etc",
        "site/data/../other",
        "/abs/site/data",
        "C:/site/data",
        "site\\data\\norway",
        "site/other",
        "site",
        "public/data/norway",
        "",
        "   ",
        42,
    ],
)
def test_invalid_site_data_dir_is_rejected(value: object) -> None:
    with pytest.raises(ValueError, match="site_data_dir"):
        parse_registry(_doc(value))


def test_absolute_path_under_repo_site_data_is_rejected() -> None:
    absolute = (REPO_ROOT / "site" / "data" / "norway").as_posix()
    with pytest.raises(ValueError, match="site_data_dir"):
        parse_registry(_doc(absolute))


def test_site_data_root_itself_is_allowed() -> None:
    assert _region("site/data").site_data_dir == "site/data"


# --- export: explicit output wins, region default is byte-identical for california -------


def _normalized(tmp_path: Path):
    return normalize_fixture(
        FIXTURE,
        institution_path=INSTITUTIONS,
        output_dir=tmp_path / "normalized",
        qc_path=tmp_path / "qc.md",
        generated_at="test",
    )


def _export(normalized, **kwargs):
    return export_site(
        works_path=normalized.output_dir / "works.parquet",
        authors_path=normalized.output_dir / "authors.parquet",
        authorships_path=normalized.output_dir / "authorships.parquet",
        institutions_path=normalized.output_dir / "institutions.parquet",
        generated_at="test",
        ca_authors_only=False,
        **kwargs,
    )


def _tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_california_default_region_output_is_byte_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_repo = tmp_path / "repo"
    monkeypatch.setattr(scope, "REPO_ROOT", fake_repo)
    normalized = _normalized(tmp_path)

    default = _export(normalized, region=None)
    explicit = _export(normalized, region=get_region("california"))

    assert default.output_dir == fake_repo / "site" / "data" / "california"
    assert explicit.output_dir == default.output_dir
    trees = _tree(default.output_dir)
    assert trees and "index.json" in trees
    assert trees == _tree(explicit.output_dir)


def test_explicit_output_dir_beats_region_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_repo = tmp_path / "repo"
    monkeypatch.setattr(scope, "REPO_ROOT", fake_repo)
    normalized = _normalized(tmp_path)

    result = _export(normalized, output_dir=tmp_path / "explicit", region=_region())

    assert result.output_dir == tmp_path / "explicit"
    assert (tmp_path / "explicit" / "index.json").is_file()
    assert not (fake_repo / "site" / "data" / "norway").exists()


def test_region_without_field_exports_to_slug_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_repo = tmp_path / "repo"
    monkeypatch.setattr(scope, "REPO_ROOT", fake_repo)
    normalized = _normalized(tmp_path)

    result = _export(normalized, region=_region())

    assert result.output_dir == fake_repo / "site" / "data" / "norway"
    assert (result.output_dir / "index.json").is_file()


# --- daily runner: region is passed through only when given -----------------------------


def test_run_daily_ingest_passes_region_only_when_given() -> None:
    calls: list[dict] = []

    def fake_ingest(**kwargs):
        calls.append(kwargs)
        return {"run_id": "r"}

    daily.run_daily_ingest(institution_ids=["I1"], ingest=fake_ingest)
    daily.run_daily_ingest(
        institution_ids=["I1"], ingest=fake_ingest, region=get_region("california")
    )
    assert "region" not in calls[0]
    assert calls[1]["region"].slug == "california"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_daily_works", RUNNER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_run_daily_works_passes_california_region(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _load_runner()
    seen: dict = {}

    def fake_run(**kwargs):
        seen.update(kwargs)
        return {"status": "deferred", "reason": "budget_exceeded"}

    monkeypatch.setattr(runner, "load_openalex_key", lambda: None)
    monkeypatch.setattr(runner, "load_institution_ids", lambda path: ["I1"])
    monkeypatch.setattr(runner, "run_daily_ingest", fake_run)
    runner.main(
        [
            "--high-water",
            str(tmp_path / "hw.json"),
            "--output",
            str(tmp_path / "w.parquet"),
            "--authors-parquet",
            str(tmp_path / "missing_authors.parquet"),
        ]
    )
    assert seen["region"].slug == "california"
