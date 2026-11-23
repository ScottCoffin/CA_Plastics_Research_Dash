"""Offline tests for scripts/bq1_5_anchor_overlap.py (BQ-1.5 anchor overlap).

No test calls the network. The end-to-end test builds a small synthetic input set and a fake
OpenAlex cache, then rebuilds the JSON offline twice and compares the bytes.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import sys
import urllib.parse
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "docs" / "api_notes" / "bq1_5_anchor_overlap.json"
OUT_MD = ROOT / "docs" / "BQ_1_5_ANCHOR_OVERLAP.md"
FETCHED_AT = "2026-11-22T12:00:00+00:00"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "bq1_5_anchor_overlap", ROOT / "scripts" / "bq1_5_anchor_overlap.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Dataclasses look the module up by name while it loads, so it must be registered first.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bq = _load_module()


@pytest.fixture(scope="module")
def config() -> dict[str, Any]:
    return bq.load_query_config(bq.CONFIG)


# ---------------------------------------------------------------- route classification


@pytest.mark.parametrize(
    ("source_run_id", "kind"),
    [
        ("orcid-doi-ingest-2026-11-10", "doi_only"),
        ("ror-researcher-doi-ingest-2026-11-10", "doi_only"),
        ("openalex-works-20261110T010203", "query"),
        ("europepmc-audit-2026-11-10", "query"),
        ("escholarship-ingest", "query"),
        ("mystery-route-1", "other"),
        ("", "other"),
    ],
)
def test_route_kind_follows_source_run_id_family(source_run_id: str, kind: str) -> None:
    assert bq.route_kind(source_run_id) == kind


def test_doi_only_routes_are_never_query_routes() -> None:
    assert bq.DOI_ONLY_ROUTES.isdisjoint(bq.QUERY_ROUTES)


def test_orcid_ingest_code_switches_the_search_off() -> None:
    text = (ROOT / "scripts" / "ingest_orcid_dois.py").read_text(encoding="utf-8")
    assert "with_query=False" in text


def test_europepmc_route_default_applies_the_search() -> None:
    from atlas.ingest import europepmc_audit

    default = inspect.signature(europepmc_audit.build_doi_url).parameters["with_query"].default
    assert default is True


def test_escholarship_route_filters_on_the_query() -> None:
    text = (ROOT / "scripts" / "audit_escholarship_openalex.py").read_text(encoding="utf-8")
    assert "openalex_filter(config)" in text
    assert "locations.source.id" in text


# ---------------------------------------------------------------- batching and filters


@pytest.mark.parametrize("count", [0, 1, 49, 50, 51, 120, 144, 163])
def test_batches_never_exceed_fifty(count: int) -> None:
    items = [f"W{i}" for i in range(count)]
    out = bq.batches(items)
    assert all(1 <= len(batch) <= 50 for batch in out)
    assert [item for batch in out for item in batch] == items
    assert len(out) == -(-count // 50)


@pytest.mark.parametrize("size", [0, 51])
def test_batches_reject_sizes_outside_one_to_fifty(size: int) -> None:
    with pytest.raises(ValueError):
        bq.batches(["W1"], size)


def test_anchor_filters_reject_more_than_fifty_keys() -> None:
    with pytest.raises(ValueError):
        bq.id_filter([f"W{i}" for i in range(51)])
    with pytest.raises(ValueError):
        bq.doi_filter([f"10.1/{i}" for i in range(51)])


def test_doi_filter_uses_the_doi_org_prefix() -> None:
    assert bq.doi_filter(["10.1/abc"]) == "doi:https://doi.org/10.1/abc"


def test_probe_url_is_the_v31_search_with_type_exclusions_and_ids(config) -> None:
    url = bq.probe_url(config, bq.id_filter(["W1", "W2"]))
    params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    expected = ",".join(
        [bq.openalex_filter(config), *bq.type_filters(config), "ids.openalex:W1|W2"]
    )
    assert params["filter"] == [expected]
    assert params["select"] == ["id"]
    assert params["per-page"] == ["50"]
    assert "group_by" not in params
    assert expected.count("title_and_abstract.search:") == 1
    # No California scope: the probe must not add an affiliation or institution filter.
    for scope in ("authorships", "institutions", "raw_affiliation", "locations"):
        assert scope not in expected


def test_lookup_url_has_no_search_or_type_filter() -> None:
    url = bq.lookup_url(bq.id_filter(["W1"]))
    params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert params["filter"] == ["ids.openalex:W1"]
    assert params["select"] == ["id,doi,title,type"]


# ---------------------------------------------------------------- statistics and reasons


@pytest.mark.parametrize(
    ("hits", "n", "low", "high"),
    [(0, 10, 0.0, 0.2775), (5, 10, 0.2366, 0.7634), (10, 10, 0.7225, 1.0)],
)
def test_wilson_interval_known_values(hits: int, n: int, low: float, high: float) -> None:
    assert bq.wilson_interval(hits, n) == (low, high)


def test_wilson_interval_brackets_the_share_and_handles_zero() -> None:
    for n in (1, 2, 7, 50, 163):
        for hits in range(n + 1):
            low, high = bq.wilson_interval(hits, n)
            assert 0.0 <= low <= hits / n <= high <= 1.0
    assert bq.wilson_interval(0, 0) == (None, None)
    with pytest.raises(ValueError):
        bq.wilson_interval(3, 2)


def test_relevance_group_follows_the_export_precedence() -> None:
    assert bq.relevance_group(None) == "rule_only"
    owner = {"owner_review": "confirmed", "plastic_related": "true"}
    assert bq.relevance_group(owner) == "owner_reviewed"
    model = {"owner_review": "pending", "plastic_related": "true"}
    assert bq.relevance_group(model) == "model_true"
    kept = {"owner_review": "pending", "plastic_related": "false"}
    assert bq.relevance_group(kept) == "rule_kept_after_model_false"


def test_miss_reason_names_the_visible_cause(config) -> None:
    gecko = bq.Anchor(openalex_id="W1", doi=None, title="Gecko adhesion on microplastic strain")
    assert "exclusion phrase" in bq.miss_reason(gecko, config)
    paratext = bq.Anchor(
        openalex_id="W2", doi=None, title="Microplastics in soils", work_type="paratext"
    )
    assert "type 'paratext'" in bq.miss_reason(paratext, config)
    chem = bq.Anchor(
        openalex_id="W3",
        doi=None,
        title="Phthalate exposure in house dust",
        tier="chemicals-in-plastics",
    )
    assert "tier-2 chemical" in bq.miss_reason(chem, config)
    plain = bq.Anchor(openalex_id="W4", doi=None, title="Ocean sediment chemistry")
    assert "no v3.1 core" in bq.miss_reason(plain, config)
    matched = bq.Anchor(openalex_id="W5", doi=None, title="Microplastics in soils")
    assert "not returned" in bq.miss_reason(matched, config)


# ---------------------------------------------------------------- end-to-end, offline


WORLD: dict[str, dict[str, Any]] = {
    "W100": {"doi": None, "title": "Microplastics in estuary sediment", "type": "article"},
    "W101": {"doi": None, "title": "Phthalate exposure in house dust", "type": "article"},
    "W102": {"doi": None, "title": "Plastic pollution in rivers", "type": "article"},
    "W103": {"doi": None, "title": "Ocean sediment chemistry", "type": "article"},
    "W200": {"doi": None, "title": "Microplastics in food", "type": "article"},
    "W201": {"doi": None, "title": "Microplastics in glaciers", "type": "article"},
    "W300": {"doi": "10.5281/zenodo.1", "title": "Microplastic data", "type": "dataset"},
}
RETRIEVED = {"W100", "W102", "W200", "W300"}


def _inputs() -> Any:
    index = {
        "W100": {
            "work_id": "W100",
            "title": WORLD["W100"]["title"],
            "type": "article",
            "plastic_related": True,
            "plastic_tier": "core",
        },
        "W101": {
            "work_id": "W101",
            "title": WORLD["W101"]["title"],
            "type": "article",
            "plastic_related": True,
            "plastic_tier": "chemicals-in-plastics",
        },
        "W102": {
            "work_id": "W102",
            "title": WORLD["W102"]["title"],
            "type": "article",
            "plastic_related": True,
            "plastic_tier": "core",
        },
        "W103": {
            "work_id": "W103",
            "title": WORLD["W103"]["title"],
            "type": "article",
            "plastic_related": False,
            "plastic_tier": "",
        },
    }
    return bq.Inputs(
        raw_rows=[
            {"openalex_id": "W100", "source_run_id": "orcid-doi-ingest-2026-11-10"},
            {"openalex_id": "W101", "source_run_id": "ror-researcher-doi-ingest-2026-11-10"},
            {"openalex_id": "W103", "source_run_id": "orcid-doi-ingest-2026-11-10"},
            {"openalex_id": "W102", "source_run_id": "openalex-works-20261110T000000"},
            {"openalex_id": "W104", "source_run_id": "escholarship-ingest"},
        ],
        index=index,
        normalized=[
            {"work_id": "W102", "doi": "https://doi.org/10.1/x", "pmid": "111"},
            {"work_id": "W100", "doi": None, "pmid": None},
        ],
        relevance={
            "W100": {"work_id": "W100", "plastic_related": "true", "owner_review": "pending"},
            "W101": {"work_id": "W101", "plastic_related": "false", "owner_review": "pending"},
        },
        pubmed_r1=[{"pmid": "111", "doi": "10.1/x"}, {"pmid": "999", "doi": "10.9/none"}],
        pubmed_found_published=1,
        datacite=[
            {"doi": "10.5281/zenodo.1", "title": "Microplastic data", "resource_type": "Dataset"},
            {"doi": "10.5281/zenodo.2", "title": "Plastic data", "resource_type": "Dataset"},
        ],
        fixture=[
            {"id": "https://openalex.org/W200", "title": WORLD["W200"]["title"]},
            {"id": "https://openalex.org/W201", "title": WORLD["W201"]["title"]},
        ],
        input_sha256={"synthetic": "0"},
    )


def _fake_response(url: str) -> dict[str, Any]:
    """What OpenAlex would return for the URL, given the synthetic world."""

    parts = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["filter"][0].split(",")
    anchor = next(part for part in parts if part.startswith(("ids.openalex:", "doi:")))
    searched = any(part.startswith("title_and_abstract.search:") for part in parts)
    value = anchor.split(":", 1)[1]
    if anchor.startswith("ids.openalex:"):
        keys = set(value.split("|"))
        hits = [wid for wid in WORLD if wid in keys]
    else:
        dois = {doi.removeprefix("https://doi.org/") for doi in value.split("|")}
        hits = [wid for wid, work in WORLD.items() if work["doi"] in dois]
    if searched:
        hits = [wid for wid in hits if wid in RETRIEVED]
    results = [
        {
            "id": f"https://openalex.org/{wid}",
            "doi": f"https://doi.org/{WORLD[wid]['doi']}" if WORLD[wid]["doi"] else None,
            "title": WORLD[wid]["title"],
            "type": WORLD[wid]["type"],
        }
        for wid in sorted(hits)
    ]
    return {"meta": {"count": len(results)}, "results": results}


def _seed(directory: Path, calls: list[Any]) -> None:
    cache = bq.CallCache(directory, offline=False)
    for call in calls:
        credits = 1.0 if call.kind == "lookup" else 10.0
        cache.write(call, body=_fake_response(call.url), credits=credits, fetched_at=FETCHED_AT)


def _rebuild(directory: Path, out: Path, config: dict[str, Any]) -> bytes:
    inputs = _inputs()
    sets = bq.build_sets(inputs)
    calls = bq.planned_calls(sets, config)
    records = bq.run_calls(calls, bq.CallCache(directory, offline=True))
    bq.write_json(out, bq.build_payload(inputs, config, sets, records))
    return out.read_bytes()


def test_offline_rebuild_is_reproducible_and_scores_each_set(
    tmp_path: Path, config: dict[str, Any]
) -> None:
    inputs = _inputs()
    sets = bq.build_sets(inputs)
    calls = bq.planned_calls(sets, config)
    assert len(calls) == 6  # two probe batches per probed set, plus lookups for the DOI and ID sets
    _seed(tmp_path, calls)

    first = _rebuild(tmp_path, tmp_path / "first.json", config)
    second = _rebuild(tmp_path, tmp_path / "second.json", config)
    assert first == second

    payload = json.loads(first)
    by_id = {entry["set_id"]: entry for entry in payload["sets"]}
    assert by_id["orcid_ror_doi"]["n_anchors"] == 2
    assert by_id["orcid_ror_doi"]["n_retrieved_by_v31"] == 1
    assert by_id["orcid_ror_doi"]["missed_ids"] == ["W101"]
    assert by_id["pubmed_r1_atlas"]["n_anchors"] == 1
    assert by_id["pubmed_r1_atlas"]["share"] == 1.0
    assert by_id["fixture_s1_5"]["missed_ids"] == ["W201"]
    assert by_id["datacite_positive"]["n_anchors"] == 1
    assert by_id["datacite_positive"]["unresolved_in_openalex"] == ["10.5281/zenodo.2"]
    assert by_id["escholarship"]["status"] == "excluded"
    assert by_id["escholarship"]["n_anchors"] is None
    assert payload["credits_total"] == 42.0
    assert payload["calls_total"] == 6


def test_offline_run_without_cache_makes_no_call_and_fails(tmp_path: Path, config) -> None:
    calls = bq.planned_calls(bq.build_sets(_inputs()), config)
    with pytest.raises(bq.CacheMiss):
        bq.run_calls(calls, bq.CallCache(tmp_path, offline=True))


def test_credit_cap_stops_before_the_next_call_would_pass_150(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = [
        bq.Call("synthetic", "probe", f"https://api.openalex.org/works?x={i}", 1) for i in range(20)
    ]

    def fake_fetch(self: Any, call: Any) -> dict[str, Any]:
        return self.write(
            call, body={"meta": {"count": 0}, "results": []}, credits=10.0, fetched_at=FETCHED_AT
        )

    monkeypatch.setattr(bq.CallCache, "fetch", fake_fetch)
    with pytest.raises(bq.CreditCapError):
        bq.run_calls(calls, bq.CallCache(tmp_path, offline=False))
    # 15 calls at 10 credits reach exactly 150; the sixteenth would pass the cap.
    assert len(list(tmp_path.glob("*.json"))) == 15


# ---------------------------------------------------------------- outputs


def test_synthetic_outputs_avoid_the_word_recall(tmp_path: Path, config) -> None:
    _seed(tmp_path, bq.planned_calls(bq.build_sets(_inputs()), config))
    text = _rebuild(tmp_path, tmp_path / "out.json", config).decode("utf-8")
    assert "recall" not in text.lower()


@pytest.mark.parametrize("path", [OUT_JSON, OUT_MD])
def test_committed_outputs_avoid_the_word_recall(path: Path) -> None:
    assert "recall" not in path.read_text(encoding="utf-8").lower()


def test_committed_json_lists_the_seven_sets_and_stays_under_the_cap() -> None:
    data = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    assert [entry["set_id"] for entry in data["sets"]] == [
        "orcid_ror_doi",
        "escholarship",
        "europepmc_audit",
        "datacite_positive",
        "pubmed_r1_atlas",
        "fixture_s1_5",
        "plastiverse_overview",
    ]
    assert data["credits_total"] <= data["credit_cap"] == 150
    for entry in data["sets"]:
        if entry["status"] != "probed":
            assert entry["n_anchors"] is None
            continue
        assert entry["n_retrieved_by_v31"] + len(entry["missed_ids"]) == entry["n_anchors"]
        if entry["n_anchors"]:
            assert entry["wilson_low"] <= entry["share"] <= entry["wilson_high"]
