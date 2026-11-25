"""Region registry loader and validation (PLAT-3 slice 1)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from atlas.regions import get_region, load_registry, regions
from atlas.regions.registry import DEFAULT_REGISTRY_PATH, parse_registry

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_REGION_YML = REPO_ROOT / "regions" / "california" / "region.yml"


def _doc(**overrides: object) -> dict:
    """A minimal valid registry; overrides replace top-level or region-0 keys."""
    base = {
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
            {
                "slug": "norway",
                "name": "Norway",
                "tier": "A",
                "parent": "global",
                "status": "planned",
                "predicate": {"ror_subdivision_codes": ["NO-03"]},
            },
        ],
    }
    base.update(overrides)
    return base


def _write(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "_registry.yml"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _region(data: dict, index: int, **changes: object) -> dict:
    entry = dict(data["regions"][index])
    entry.update(changes)
    data["regions"][index] = entry
    return data


def test_real_registry_has_global_and_california() -> None:
    registry = load_registry(DEFAULT_REGISTRY_PATH)
    assert registry.schema_version == 1
    slugs = [region.slug for region in registry.regions]
    assert slugs == ["global", "california"]

    california = get_region("california")
    assert california.tier == "A"
    assert california.status == "active"
    assert california.parent is None
    assert california.predicate is not None
    predicate = california.predicate
    assert predicate.openalex_institution_filter == "geo.region:California"
    assert predicate.ror_subdivision_codes == ("CA",)
    assert predicate.country_codes == ("US",)
    assert predicate.institution_region_names == ("California",)
    assert "California" in predicate.raw_affiliation_terms
    assert predicate.ca_basis_values == (
        "registry",
        "raw_affiliation",
        "author_carry_forward",
        "escholarship",
    )


def test_global_is_root_without_predicate() -> None:
    global_region = get_region("global")
    assert global_region.tier == "root"
    assert global_region.predicate is None


def test_regions_filters_by_tier() -> None:
    assert [r.slug for r in regions(tier="A")] == ["california"]
    assert [r.slug for r in regions(tier="root")] == ["global"]
    assert [r.slug for r in regions(tier="C")] == []
    with pytest.raises(ValueError, match="unknown tier"):
        regions(tier="Z")


def test_unknown_slug_raises_key_error() -> None:
    with pytest.raises(KeyError, match="unknown region slug"):
        get_region("atlantis")


def test_region_yml_matches_registry() -> None:
    config = yaml.safe_load(REAL_REGION_YML.read_text(encoding="utf-8"))
    california = get_region("california")
    assert config["slug"] == california.slug
    assert config["tier"] == california.tier
    assert config["site_path"] == "/california/"
    assert config["data_dir"] == "site/data/"
    assert (REPO_ROOT / config["outline_asset"]).is_file()
    for adapter in config["adapters"]:
        assert (REPO_ROOT / adapter["module"]).is_file(), adapter["module"]


def test_valid_fixture_parses(tmp_path: Path) -> None:
    registry = load_registry(_write(tmp_path, _doc()))
    norway = registry.get("norway")
    assert norway.parent == "global"
    assert norway.predicate.ror_subdivision_codes == ("NO-03",)
    assert norway.predicate.openalex_institution_filter is None


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.update(extra=1), "unknown keys"),
        (lambda d: d.update(schema_version=2), "schema_version must be 1"),
        (lambda d: _region(d, 1, slug="global"), "duplicate slug"),
        (lambda d: _region(d, 1, parent="mars"), "unknown parent"),
        (lambda d: _region(d, 1, parent="norway"), "cannot be its own parent"),
        (lambda d: _region(d, 1, tier="D"), "tier 'D'"),
        (lambda d: _region(d, 1, status="live"), "status 'live'"),
        (lambda d: _region(d, 1, extra_key="x"), "unknown keys"),
        (lambda d: _region(d, 1, predicate=None), "needs a predicate"),
        (lambda d: _region(d, 1, predicate={"country": ["NO"]}), "unknown keys"),
        (lambda d: _region(d, 1, predicate={"country_codes": "NO"}), "list of non-empty"),
        (lambda d: _region(d, 0, predicate={}), "root tier must have predicate null"),
        (lambda d: _region(d, 0, parent="norway"), "root tier must have parent null"),
        (lambda d: _region(d, 1, slug="Norway!"), "must be lowercase"),
        (lambda d: _region(d, 1, predicate={"institution_registry": ""}), "non-empty string"),
        (
            lambda d: _region(d, 1, predicate={"institution_registry": "/abs/x.parquet"}),
            "repo-relative",
        ),
        (
            lambda d: _region(d, 1, predicate={"institution_registry": "../x.parquet"}),
            "repo-relative",
        ),
        (
            lambda d: _region(d, 1, predicate={"institution_registry": "data\\x.parquet"}),
            "forward slashes",
        ),
        (
            lambda d: _region(d, 1, predicate={"institution_registry": "data/x.csv"}),
            "must be a .parquet file",
        ),
        (lambda d: d.update(regions=[]), "non-empty list"),
    ],
)
def test_invalid_fixture_is_rejected(tmp_path: Path, mutate, message: str) -> None:
    data = _doc()
    mutate(data)
    with pytest.raises(ValueError, match=message):
        load_registry(_write(tmp_path, data))


def test_missing_key_is_rejected(tmp_path: Path) -> None:
    data = _doc()
    del data["regions"][1]["status"]
    with pytest.raises(ValueError, match="missing keys"):
        load_registry(_write(tmp_path, data))


def test_top_level_must_be_mapping() -> None:
    with pytest.raises(ValueError, match="expected a mapping"):
        parse_registry(["global"])


def test_institution_registry_is_optional_and_parsed(tmp_path: Path) -> None:
    data = _doc()
    _region(data, 1, predicate={"country_codes": ["NO"], "institution_registry": "data/x.parquet"})
    norway = load_registry(_write(tmp_path, data)).get("norway")
    assert norway.predicate.institution_registry == "data/x.parquet"
    plain = load_registry(_write(tmp_path, _doc())).get("norway")
    assert plain.predicate.institution_registry is None


def test_california_predicate_names_committed_institution_registry() -> None:
    predicate = get_region("california").predicate
    assert predicate.institution_registry == "data/processed/institutions.parquet"
