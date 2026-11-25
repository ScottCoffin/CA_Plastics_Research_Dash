"""Region scope values come from the registry; California output is unchanged (PLAT-3 slice 2).

The URL literals below were captured from the code before slice 2 (same fixed config).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.ingest import institutions, normalize, openalex
from atlas.query import load_query_config
from atlas.regions import scope
from atlas.regions.registry import Predicate, Region, get_region

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"

FIXED_CONFIG = """version: test-v1
core_terms: [microplastic]
qualified_terms: []
tier_2_terms: []
exclusions: [cosmetic]
exclude_types: [paratext]
always_include: []
"""

# Captured from the unmodified code (slice 1 HEAD) with FIXED_CONFIG.
RAW_AFFILIATION_URL = (
    "https://api.openalex.org/works?filter=title_and_abstract.search%3A%28microplastic%29"
    "+NOT+%28cosmetic%29%2Craw_affiliation_strings.search%3ACalifornia%2Ctype%3A%21paratext"
    "&per-page=100&cursor=%2A"
)
INSTITUTION_WORKS_URL = (
    "https://api.openalex.org/works?filter=title_and_abstract.search%3A%28microplastic%29"
    "+NOT+%28cosmetic%29%2Cinstitutions.id%3AI1%7CI2%2Ctype%3A%21paratext"
    "%2Cfrom_publication_date%3A2020-01-01%2Cto_publication_date%3A2020-12-31"
    "&per-page=100&cursor=%2A"
)
SEED_URL = (
    "https://api.openalex.org/institutions?filter=geo.region:California"
    "&select=id,display_name,display_name_alternatives,ror,type,lineage,geo,works_count,"
    "updated_date&per_page=100&page=1"
)
GOVERNMENT_URL = (
    "https://api.openalex.org/institutions?filter=type:government,geo.region:California"
    "&select=id,display_name,display_name_alternatives,ror,type,lineage,geo,works_count,"
    "updated_date&per_page=100&page=1"
)


@pytest.fixture
def config(tmp_path: Path) -> dict:
    path = tmp_path / "queries.yml"
    path.write_text(FIXED_CONFIG, encoding="utf-8")
    return load_query_config(path)


def _norway() -> Region:
    return Region(
        slug="norway",
        name="Norway",
        tier="A",
        parent=None,
        status="planned",
        predicate=Predicate(
            openalex_institution_filter="geo.region:Norway",
            ror_subdivision_codes=("NO-03",),
            country_codes=("NO",),
            institution_region_names=("Norway",),
            raw_affiliation_terms=("Norway", "University of Oslo"),
        ),
    )


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# --- registry-derived values equal the previous literals ---------------------------------


def test_california_scope_values_match_previous_literals() -> None:
    assert scope.DEFAULT_REGION_SLUG == "california"
    assert scope.institution_filter() == "geo.region:California"
    assert scope.institution_region_names() == ("California",)
    assert scope.ror_subdivision_codes() == ("CA",)
    assert scope.country_codes() == ("US",)
    assert scope.raw_affiliation_search_term() == "California"
    assert openalex.RAW_AFFILIATION_TERM == "California"


def test_explicit_california_region_equals_default() -> None:
    region = get_region("california")
    assert scope.institution_filter(region) == scope.institution_filter()
    assert scope.raw_affiliation_search_term(region) == "California"


def test_region_without_predicate_is_rejected() -> None:
    root = get_region("global")
    with pytest.raises(ValueError, match="has no predicate"):
        scope.institution_filter(root)


def test_other_region_values_are_read_from_its_predicate() -> None:
    norway = _norway()
    assert scope.institution_filter(norway) == "geo.region:Norway"
    assert scope.ror_subdivision_codes(norway) == ("NO-03",)
    assert scope.raw_affiliation_search_term(norway) == "Norway"


# --- rendered URLs are byte-identical to the pre-change code -----------------------------


def test_raw_affiliation_works_url_is_byte_identical(config: dict) -> None:
    url = openalex.build_works_url(
        config, [], raw_affiliation_term=scope.raw_affiliation_search_term()
    )
    assert url == RAW_AFFILIATION_URL


def test_institution_works_url_is_byte_identical(config: dict) -> None:
    url = openalex.build_works_url(
        config, ["I1", "I2"], start_date="2020-01-01", end_date="2020-12-31"
    )
    assert url == INSTITUTION_WORKS_URL


def test_institution_seed_urls_are_byte_identical(tmp_path: Path) -> None:
    urls: list[str] = []

    def fake_request(url: str, *, source: str, logger: object) -> tuple[dict, None]:
        urls.append(url)
        return {"meta": {"count": 0}, "results": []}, None

    # Hermetic: the government supplement checks the daily usage log before each call; the
    # real log can already be at the daily stop (2026-11-25), so use an empty one.
    with (
        mock.patch.object(institutions, "_request_json", side_effect=fake_request),
        mock.patch.object(institutions, "DEFAULT_USAGE_LOG", tmp_path / "usage.jsonl"),
    ):
        institutions.pull_openalex_institutions(tmp_path / "seed.jsonl", mock.MagicMock())
        institutions.supplement_government_institutions(
            [], tmp_path / "gov.jsonl", mock.MagicMock()
        )
    assert urls == [SEED_URL, GOVERNMENT_URL]


# --- engine helpers honour an explicit region --------------------------------------------


def test_ror_location_uses_region_subdivision_codes() -> None:
    record = {
        "locations": [
            {"geonames_details": {"country_subdivision_code": "NY", "name": "NYC"}},
            {"geonames_details": {"country_subdivision_code": "CA", "name": "Davis"}},
        ]
    }
    assert institutions._ror_location(record)["name"] == "Davis"
    assert institutions._ror_location(record, _norway())["name"] == "NYC"
    norway_record = {
        "locations": [
            {"geonames_details": {"country_subdivision_code": "CA", "name": "Davis"}},
            {"geonames_details": {"country_subdivision_code": "NO-03", "name": "Oslo"}},
        ]
    }
    assert institutions._ror_location(norway_record, _norway())["name"] == "Oslo"


def test_ca_flag_uses_region_names_and_countries(tmp_path: Path) -> None:
    rows = [
        {"openalex_id": "https://openalex.org/I1", "region": "California", "country_code": "US"},
        {"openalex_id": "https://openalex.org/I2", "region": "California", "country_code": ""},
        {"openalex_id": "https://openalex.org/I3", "region": "California", "country_code": "MX"},
        {"openalex_id": "https://openalex.org/I4", "region": "Oregon", "country_code": "US"},
    ]
    path = tmp_path / "institutions.parquet"
    pq.write_table(
        pa.Table.from_pylist(
            [
                {
                    "openalex_id": r["openalex_id"],
                    "display_name": "x",
                    "ror_id": None,
                    "city": None,
                    "region": r["region"],
                    "country_code": r["country_code"],
                    "latitude": None,
                    "longitude": None,
                    "ror_types": [],
                    "atlas_type": "university",
                    "lineage": [],
                }
                for r in rows
            ]
        ),
        path,
    )
    default = normalize._read_registry(path)
    assert [default[k]["ca_flag"] for k in ("I1", "I2", "I3", "I4")] == [True, True, False, False]

    oregon = Region(
        slug="oregon",
        name="Oregon",
        tier="A",
        parent=None,
        status="planned",
        predicate=Predicate(institution_region_names=("Oregon",), country_codes=("US",)),
    )
    flagged = normalize._read_registry(path, oregon)
    assert [flagged[k]["ca_flag"] for k in ("I1", "I2", "I3", "I4")] == [False, False, False, True]


# --- CLIs: --region rejects unknown and unsupported slugs, accepts the default -----------


def _tmp_registry_with_norway(tmp_path: Path) -> Path:
    """The real registry plus a planned norway entry, in tmp_path only."""
    real = (REPO / "regions" / "_registry.yml").read_text(encoding="utf-8")
    norway = """
  - slug: norway
    name: Norway
    tier: A
    parent: null
    status: planned
    predicate:
      openalex_institution_filter: "geo.region:Norway"
      ror_subdivision_codes: []
      country_codes: ["NO"]
      institution_region_names: ["Norway"]
      raw_affiliation_terms: ["Norway"]
      ca_basis_values: []
"""
    path = tmp_path / "registry.yml"
    path.write_text(real + norway, encoding="utf-8")
    return path


@pytest.fixture
def tmp_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = _tmp_registry_with_norway(tmp_path)
    monkeypatch.setattr(scope, "REGISTRY_PATH", path)
    return path


def _stub_ingest(monkeypatch: pytest.MonkeyPatch, module, calls: list) -> None:
    monkeypatch.setattr(module, "load_openalex_key", lambda: None)
    monkeypatch.setattr(module, "load_institution_ids", lambda path: ["I1"])
    monkeypatch.setattr(module, "ingest_live", lambda **kw: calls.append(kw) or {"ok": True})


def test_ingest_openalex_rejects_unknown_region(monkeypatch, tmp_path: Path, capsys) -> None:
    module = _load_script("ingest_openalex")
    calls: list = []
    _stub_ingest(monkeypatch, module, calls)
    monkeypatch.setattr(
        sys, "argv", ["ingest_openalex", "--region", "norway", "--start-year", "2020"]
    )
    with pytest.raises(SystemExit) as exit_info:
        module.main()
    assert exit_info.value.code == 2
    assert "unknown region slug" in capsys.readouterr().err
    assert calls == []


def test_ingest_openalex_rejects_planned_region(monkeypatch, tmp_registry, capsys) -> None:
    module = _load_script("ingest_openalex")
    calls: list = []
    _stub_ingest(monkeypatch, module, calls)
    monkeypatch.setattr(
        sys, "argv", ["ingest_openalex", "--region", "norway", "--start-year", "2020"]
    )
    with pytest.raises(SystemExit) as exit_info:
        module.main()
    assert exit_info.value.code == 2
    assert (
        "region norway is registered but not yet supported by this command (PLAT-3)"
        in capsys.readouterr().err
    )
    assert calls == []


def test_ingest_openalex_accepts_default_region(monkeypatch) -> None:
    module = _load_script("ingest_openalex")
    calls: list = []
    _stub_ingest(monkeypatch, module, calls)
    monkeypatch.setattr(sys, "argv", ["ingest_openalex", "--start-year", "2020"])
    module.main()
    assert calls[0]["region"].slug == "california"


def test_run_daily_works_rejects_norway_and_accepts_default(monkeypatch, tmp_registry, capsys):
    module = _load_script("run_daily_works")
    monkeypatch.setattr(module, "load_openalex_key", lambda: None)
    monkeypatch.setattr(module, "load_institution_ids", lambda path: ["I1"])
    calls: list = []
    monkeypatch.setattr(
        module,
        "run_daily_ingest",
        lambda **kw: calls.append(kw) or {"status": "deferred", "reason": "x"},
    )
    base = ["--start-year", "2020", "--no-author-anchored", "--no-raw-affiliation-scope"]
    with pytest.raises(SystemExit) as exit_info:
        module.main([*base, "--region", "norway"])
    assert exit_info.value.code == 2
    assert "not yet supported by this command (PLAT-3)" in capsys.readouterr().err
    assert calls == []
    assert module.main(base) == 0
    assert len(calls) == 1


def test_build_export_site_rejects_norway_and_accepts_default(monkeypatch, tmp_registry, capsys):
    module = _load_script("build_export_site")
    exported: list = []
    monkeypatch.setattr(module, "load_expert_profiles", lambda *a: None)
    monkeypatch.setattr(
        module,
        "export_site",
        lambda **kw: (
            exported.append(kw)
            or SimpleNamespace(
                counts={"works": 0, "authors": 0, "institutions": 0},
                output_dir="x",
                metadata_path="y",
            )
        ),
    )
    monkeypatch.setattr(sys, "argv", ["build_export_site", "--region", "norway"])
    with pytest.raises(SystemExit) as exit_info:
        module.main()
    assert exit_info.value.code == 2
    assert "not yet supported" in capsys.readouterr().err
    assert exported == []
    monkeypatch.setattr(sys, "argv", ["build_export_site"])
    module.main()
    assert len(exported) == 1


def test_normalize_openalex_rejects_norway_and_accepts_default(monkeypatch, tmp_registry, capsys):
    module = _load_script("normalize_openalex")
    calls: list = []
    result = SimpleNamespace(metrics={"works": 0}, qc_path="qc")
    monkeypatch.setattr(module, "normalize_fixture", lambda path, **kw: calls.append(kw) or result)
    fixture = str(REPO / "tests" / "fixtures" / "s2_2_openalex_works.json")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "normalize_openalex",
            "--fixture",
            fixture,
            "--input",
            "nope.parquet",
            "--region",
            "norway",
        ],
    )
    with pytest.raises(SystemExit) as exit_info:
        module.main()
    assert exit_info.value.code == 2
    assert "not yet supported" in capsys.readouterr().err
    assert calls == []
    monkeypatch.setattr(
        sys, "argv", ["normalize_openalex", "--fixture", fixture, "--input", "nope.parquet"]
    )
    module.main()
    assert calls[0]["region"].slug == "california"
