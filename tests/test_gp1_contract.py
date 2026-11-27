"""Unit tests for the GP-1 California contract (scripts/check_gp1_contract.py).

Pure logic only: contract comparison, route discovery and the link-graph checker on tiny fixtures.
No browser and no network. Playwright is imported lazily by the script, so these run without it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def gp1():
    script = ROOT / "scripts" / "check_gp1_contract.py"
    spec = importlib.util.spec_from_file_location("check_gp1_contract", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _contract_routes() -> list[dict]:
    return [
        {
            "route": "/california/authors",
            "file": "california/authors.html",
            "selector": "#experts-root .expert-card",
            "recorded_count": 10,
            "min_count": 8,
            "recorded_main_chars": 5000,
            "min_main_chars": 2500,
        },
        {
            "route": "/california/search",
            "file": "california/search.html",
            "selector": "main h1",
            "recorded_count": 1,
            "min_count": 1,
            "recorded_main_chars": 257,
            "min_main_chars": 128,
        },
    ]


def _observed(**overrides) -> dict[str, dict]:
    base = {
        "/california/authors": {
            "selector": "#experts-root .expert-card",
            "count": 10,
            "main_chars": 5000,
            "status": 200,
            "page_errors": [],
            "overflow_390": 0,
        },
        "/california/search": {
            "selector": "main h1",
            "count": 1,
            "main_chars": 300,
            "status": 200,
            "page_errors": [],
            "overflow_390": 0,
        },
    }
    for route, changes in overrides.items():
        base[route] = {**base[route], **changes}
    return base


def test_minimum_counts_are_conservative(gp1):
    assert gp1.min_count(10) == 8
    assert gp1.min_count(1) == 1
    assert gp1.min_count(0) == 1
    assert gp1.min_text(257) == 128
    assert gp1.min_text(9000) == 4500


def test_dom_comparison_passes_on_matching_run(gp1):
    assert gp1.compare_dom(_contract_routes(), _observed()) == []


def test_dom_comparison_fails_below_minimum_count(gp1):
    problems = gp1.compare_dom(
        _contract_routes(), _observed(**{"/california/authors": {"count": 7}})
    )
    assert any("below the minimum 8" in p for p in problems)


def test_dom_comparison_fails_on_page_error_and_overflow(gp1):
    problems = gp1.compare_dom(
        _contract_routes(),
        _observed(**{"/california/authors": {"page_errors": ["boom"], "overflow_390": 12}}),
    )
    assert any("page error: boom" in p for p in problems)
    assert any("overflow at 390 px (12 px)" in p for p in problems)


def test_dom_comparison_fails_on_short_text_and_bad_status(gp1):
    problems = gp1.compare_dom(
        _contract_routes(), _observed(**{"/california/search": {"main_chars": 10, "status": 404}})
    )
    assert any("<main> text 10 chars" in p for p in problems)
    assert any("HTTP status 404" in p for p in problems)


def test_dom_comparison_fails_when_route_not_observed(gp1):
    observed = _observed()
    del observed["/california/search"]
    assert gp1.compare_dom(_contract_routes(), observed) == ["/california/search: not observed"]


def test_route_missing_from_site_is_reported(gp1, tmp_path):
    (tmp_path / "california").mkdir()
    (tmp_path / "california" / "authors.html").write_text("<html></html>", encoding="utf-8")
    assert gp1.missing_routes(_contract_routes(), tmp_path) == ["california/search.html"]


def test_california_routes_come_from_framework_sources(gp1, tmp_path):
    src = tmp_path / "framework" / "src" / "california"
    src.mkdir(parents=True)
    for name in ("index.md", "authors.md", "glossary.md"):
        (src / name).write_text("# page\n", encoding="utf-8")
    routes = gp1.california_routes(tmp_path)
    assert [r["route"] for r in routes] == [
        "/california/authors",
        "/california/glossary",
        "/california/",
        "/california/expert.html",
    ]
    assert routes[2]["file"] == "california/index.html"
    # Contract routes are authors and search; glossary, index and the classic page are new.
    assert gp1.new_source_routes(_contract_routes(), tmp_path) == [
        "/california/glossary",
        "/california/",
        "/california/expert.html",
    ]


def test_contract_links_allowlist_only_excuses_listed_breaks(gp1):
    report = {"broken": ["index.work->author: work W1 -> A9", "index.work->author: work W2 -> A8"]}
    contract_links = {"allowlist": ["index.work->author: work W1 -> A9"]}
    assert gp1.compare_links(contract_links, report) == [
        "broken link: index.work->author: work W2 -> A8"
    ]


def _tiny_data():
    index = {
        "authors": [
            {"author_id": "A1", "institution_ids": ["I1"], "work_ids": ["W1"]},
            {"author_id": "A2", "institution_ids": ["I1"], "work_ids": ["W1"]},
        ],
        "works": [{"work_id": "W1", "author_ids": ["A1", "A2", "A9"], "institution_ids": ["I1"]}],
    }
    institutions = [
        {
            "inst_id": "I1",
            "top_experts": [{"author_id": "A1", "in_atlas_index": True}],
        }
    ]
    institution_works = {
        "I1": {
            "experts": [
                {"author_id": "A2", "in_atlas_index": True},
                {"author_id": "A9", "in_atlas_index": False},
            ],
            "works": [
                {"work_id": "W1", "author_ids": ["A1", "A9"], "institution_ids": ["I1"]},
            ],
        }
    }
    author_files = {
        "A1": {
            "author": {"institution_ids": ["I1"], "work_ids": ["W1"]},
            "works": [{"work_id": "W1", "author_ids": ["A1", "A2"], "institution_ids": ["I1"]}],
        },
        "A2": {
            "author": {"institution_ids": ["I1"], "work_ids": ["W1"]},
            "works": [{"work_id": "W1", "author_ids": ["A1", "A2"], "institution_ids": ["I1"]}],
        },
    }
    return dict(
        index=index,
        institutions=institutions,
        institution_works=institution_works,
        author_files=author_files,
    )


def test_link_graph_clean_fixture_has_no_broken_links(gp1):
    report = gp1.check_link_graph(**_tiny_data())
    assert report["broken"] == []
    # Co-author A9 is not an indexed expert, so it is plain text and not a link.
    assert report["unlinked"]["index.work->author"] == 1
    assert report["unlinked"]["institution_works.work->author"] == 1
    assert report["unlinked"]["institution_works.expert (not indexed)"] == 1
    assert report["checked"]["index.work->author"] == 2
    assert report["info"]["institutions_without_profile_file"] == 0


def test_link_graph_reports_each_kind_of_broken_reference(gp1):
    data = _tiny_data()
    data["author_files"].pop("A2")  # indexed author without a file
    data["index"]["works"][0]["institution_ids"].append("I404")
    data["institution_works"]["I1"]["works"][0]["work_id"] = "W404"
    data["institutions"][0]["top_experts"].append({"author_id": "A7", "in_atlas_index": True})
    report = gp1.check_link_graph(**data)
    broken = "\n".join(report["broken"])
    assert "index.author->author_file: author A2 -> A2" in broken
    assert "index.work->institution: work W1 -> I404" in broken
    assert "institution_works.work->work: institution_works I1 -> W404" in broken
    assert "institutions.top_expert->author: institution I1 -> A7" in broken
    assert len(report["broken"]) == len(set(report["broken"]))


def test_link_graph_flags_profile_file_without_institution(gp1):
    data = _tiny_data()
    data["institution_works"]["I999"] = {"experts": [], "works": []}
    report = gp1.check_link_graph(**data)
    assert "institution_works.file->institution: institution_works I999 -> I999" in report["broken"]


def test_summary_counts_checked_references(gp1):
    summary = gp1.summarize_links(gp1.check_link_graph(**_tiny_data()))
    assert summary["broken"] == 0
    assert summary["total_checked"] == sum(summary["checked"].values())
    assert summary["allowlist"] == []
