"""Tests for the groups build and derived files (Add-on A4, CG-9).

Synthetic roster: five organisations. Two are tagged (one core, one adjacent), one is
cannot_determine (not tagged) and two are untagged. Nothing here reads the committed data except
the final --check test.
"""

from __future__ import annotations

import copy
import csv
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest

from atlas.groups.build import (
    OUTPUT_FILES,
    GroupsBuildError,
    build_groups,
    check_flow_conservation,
    denominator_note,
)
from atlas.groups.schema import validate_groups

REPO = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO / "scripts" / "build_groups.py"
DATE = "2026-11-26"
CORE, ADJ, CD, UNTAGGED_US, UNTAGGED_BE = "cg_core", "cg_adj", "cg_cd", "cg_us_u", "cg_be_u"
TAGGED_IDS = {CORE, ADJ}
UNTAGGED_IDS = {CD, UNTAGGED_US, UNTAGGED_BE}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _entry(
    group_id: str,
    name: str,
    country: str | None,
    region: str,
    ambassador_region: str | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    return {
        "group_id": group_id,
        "name": name,
        "name_alt": [],
        "country": country,
        "region": region,
        "ambassador_region": ambassador_region,
        "url": url,
        "bffp_listed": True,
        "bffp_listed_asof": DATE,
        "org_status": "source_declared_org",
        "roster_retrieved_at": DATE,
    }


ROSTER: dict[str, Any] = {
    "schema": "cg-roster-v1",
    "retrieved_at": DATE,
    "source": "synthetic",
    "source_url": "https://example.org/members",
    "records": [
        _entry(CORE, "Core Clean Org", "US", "Northern America", None, "http://core.example.org"),
        _entry(ADJ, "Adjacent Fund", "FR", "Western Europe"),
        _entry(CD, "Unknown Group", "US", "Northern America"),
        _entry(UNTAGGED_US, "Plain Group", "US", "Northern America"),
        _entry(UNTAGGED_BE, "Belgian Group", "BE", "Western Europe", "belgium"),
    ],
}


def _evidence(facet: str, quote: str | None = "We remove plastic litter from beaches.") -> dict:
    return {
        "facet": facet,
        "url": "https://example.org/about",
        "accessed_at": DATE,
        "quote": quote,
        "not_stated": quote is None,
        "note": None,
    }


def _core_row() -> dict[str, Any]:
    return {
        "group_id": CORE,
        "status": "ambassador_tagged",
        "entity_type": "organisation",
        "sector": "ngo_civil_society",
        "plastics_centrality": "primary",
        "primary_activities": ["cleanup_removal", "education_awareness"],
        "geographic_scope": "local",
        "places": ["US-CA"],
        "themes": ["marine_litter"],
        "website_languages": ["en"],
        "tagged_at": DATE,
        "evidence": [_evidence("plastics_centrality"), _evidence("primary_activities")],
        "stated_affiliations": [
            {
                "target_group_id": ADJ,
                "target_name": None,
                "relation": "member_of",
                "evidence": {
                    "url": "https://example.org/about",
                    "accessed_at": DATE,
                    "quote": "We are a member of the adjacent fund.",
                    "not_stated": False,
                },
            },
            {
                "target_group_id": None,
                "target_name": "Example Network",
                "relation": "partner_of",
                "evidence": {
                    "url": "https://example.org/partners",
                    "accessed_at": DATE,
                    "quote": "Partner: Example Network.",
                    "not_stated": False,
                },
            },
        ],
    }


def _adj_row() -> dict[str, Any]:
    return {
        "group_id": ADJ,
        "status": "reviewed",
        "entity_type": "organisation",
        "sector": "foundation",
        "plastics_centrality": "incidental",
        "primary_activities": ["funding_grantmaking"],
        "geographic_scope": "national",
        "places": ["FR"],
        "themes": ["marine_litter"],
        "website_languages": ["fr"],
        "tagged_at": DATE,
        "reviewed_at": DATE,
        "evidence": [_evidence("plastics_centrality"), _evidence("primary_activities")],
    }


def _cd_row() -> dict[str, Any]:
    return {
        "group_id": CD,
        "status": "cannot_determine",
        "cannot_determine_reason": "no_web_presence",
        "plastics_centrality": "cannot_determine",
        "evidence": [_evidence("plastics_centrality", quote=None)],
    }


SUBMISSIONS = [_core_row(), _adj_row(), _cd_row()]


def _build(submissions: list[dict[str, Any]] | None = SUBMISSIONS) -> dict[str, bytes]:
    return build_groups(copy.deepcopy(ROSTER), copy.deepcopy(submissions))


def _json(outputs: Mapping[str, bytes], name: str) -> Any:
    return json.loads(outputs[name].decode("utf-8"))


def _walk(node: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    yield node
    for child in node.get("children", []):
        yield from _walk(child)


def _leaves(hierarchy: Mapping[str, Any], level: str) -> list[Mapping[str, Any]]:
    return [node for node in _walk(hierarchy) if node["level"] == level]


# ---------------------------------------------------------------------------
# groups.json and shared contract
# ---------------------------------------------------------------------------


def test_six_files_carry_schema_generated_from_and_denominator_note() -> None:
    outputs = _build()
    assert set(outputs) == set(OUTPUT_FILES)
    expected_schemas = {
        "groups.json": "cg-v2",
        "groups_tree.json": "cg-tree-v1",
        "groups_graph.json": "cg-graph-v1",
        "coverage.json": "cg-coverage-v1",
        "flows.json": "cg-flows-v1",
        "precision_card.json": "cg-precision-v1",
    }
    note = (
        "Based on 2 of 5 roster organisations tagged (40.0%). "
        "Tagged groups are not a random sample."
    )
    for name, schema in expected_schemas.items():
        document = _json(outputs, name)
        assert document["schema"] == schema, name
        assert document["generated_from"] == DATE, name
        assert document["denominator_note"] == note, name


def test_denominator_note_wording() -> None:
    assert denominator_note(0, 2708).startswith(
        "Based on 0 of 2708 roster organisations tagged (0.0%)."
    )
    assert denominator_note(0, 0).startswith("Based on 0 of 0 roster organisations tagged (0.0%).")


def test_groups_json_without_submissions_is_all_untagged_and_valid() -> None:
    document = _json(_build(None), "groups.json")
    records = document["groups"]
    assert len(records) == 5
    assert validate_groups(records) == []
    for record in records:
        assert record["status"] == "unlabelled"
        assert record["layer"] == "untagged"
        assert record["evidence"] == []
        assert record["primary_activities"] == []
        assert record["bffp_listed"] is True
        assert record["source"] == "bffp_roster"
    belgian = next(r for r in records if r["group_id"] == UNTAGGED_BE)
    assert belgian["places"] == ["BE"]
    assert "ambassador_region" not in belgian


def test_submission_merge_derives_layer_and_drops_non_https_urls() -> None:
    records = _json(_build(), "groups.json")["groups"]
    by_id = {r["group_id"]: r for r in records}
    assert by_id[CORE]["layer"] == "core"
    assert by_id[ADJ]["layer"] == "adjacent"
    assert by_id[CD]["layer"] == "untagged"
    assert by_id[CORE]["url"] == "http://core.example.org"  # http sites are kept (2026-11-26)
    assert validate_groups(records) == []


def test_bad_submission_fails_the_build() -> None:
    bad = _core_row()
    bad["evidence"][0]["quote"] = " ".join(["word"] * 30)
    with pytest.raises(GroupsBuildError, match="V3"):
        _build([bad, _adj_row(), _cd_row()])


def test_submission_with_personal_field_fails_the_build() -> None:
    bad = _core_row()
    bad["ambassador_id"] = "amb_123"
    with pytest.raises(GroupsBuildError, match="V9"):
        _build([bad, _adj_row(), _cd_row()])


def test_submission_for_unknown_or_duplicate_group_fails() -> None:
    unknown = dict(_adj_row(), group_id="cg_missing")
    with pytest.raises(GroupsBuildError, match="not on the roster"):
        _build([unknown])
    with pytest.raises(GroupsBuildError, match="more than one"):
        _build([_adj_row(), _adj_row()])


def test_chapter_branch_needs_parent_when_a_member_of_parent_is_stated() -> None:
    chapter = _adj_row()
    chapter["entity_type"] = "chapter_branch"
    chapter["stated_affiliations"] = [
        {
            "target_group_id": CORE,
            "target_name": None,
            "relation": "member_of",
            "evidence": {
                "url": "https://example.org/about",
                "accessed_at": DATE,
                "quote": "A chapter of the core group.",
                "not_stated": False,
            },
        }
    ]
    with pytest.raises(GroupsBuildError, match="CHAPTER"):
        _build([_core_row(), chapter, _cd_row()])
    chapter["parent_group_id"] = CORE
    outputs = _build([_core_row(), chapter, _cd_row()])
    chapter_out = next(r for r in _json(outputs, "groups.json")["groups"] if r["group_id"] == ADJ)
    assert chapter_out["parent_group_id"] == CORE


def test_build_is_deterministic_and_lf_terminated() -> None:
    first, second = _build(), _build()
    assert first == second
    for name, data in first.items():
        assert data.endswith(b"\n") and not data.endswith(b"\n\n"), name
        assert b"\r" not in data, name


# ---------------------------------------------------------------------------
# groups_tree.json (T-TREE)
# ---------------------------------------------------------------------------


def test_each_tagged_group_is_placed_once_in_each_hierarchy() -> None:
    tree = _json(_build(), "groups_tree.json")
    for name, hierarchy in tree["hierarchies"].items():
        placed = Counter(leaf["group_id"] for leaf in _leaves(hierarchy, "group"))
        assert placed == Counter({CORE: 1, ADJ: 1}), name


def test_untagged_groups_appear_only_as_aggregated_counts() -> None:
    tree = _json(_build(), "groups_tree.json")
    for name, hierarchy in tree["hierarchies"].items():
        leaf_ids = {leaf.get("group_id") for leaf in _walk(hierarchy)}
        assert not (leaf_ids & UNTAGGED_IDS), name
        aggregates = _leaves(hierarchy, "not_yet_tagged")
        assert all("children" not in leaf and "group_id" not in leaf for leaf in aggregates)
        assert sum(leaf["count"] for leaf in aggregates) == 3, name  # cd, untagged US and BE


def test_tree_counts_are_tagged_roster_and_distinct() -> None:
    tree = _json(_build(), "groups_tree.json")
    for name, hierarchy in tree["hierarchies"].items():
        assert hierarchy["counts"] == {"tagged": 2, "roster": 5, "distinct": 2}, name
    geography = tree["hierarchies"]["geography"]
    countries = {node["id"].split("/")[-1]: node for node in _leaves(geography, "country")}
    assert countries["US"]["counts"] == {"tagged": 1, "roster": 3, "distinct": 1}
    assert countries["FR"]["counts"] == {"tagged": 1, "roster": 1, "distinct": 1}
    assert countries["BE"]["counts"] == {"tagged": 0, "roster": 1, "distinct": 0}
    assert tree["default_hierarchy"] == "geography"


# ---------------------------------------------------------------------------
# groups_graph.json (T-GRAPH)
# ---------------------------------------------------------------------------


def test_graph_has_no_untagged_nodes_and_edges_are_tagged_only() -> None:
    graph = _json(_build(), "groups_graph.json")
    node_ids = {node["id"] for node in graph["nodes"]}
    assert not (node_ids & UNTAGGED_IDS)
    group_nodes = {node["id"] for node in graph["nodes"] if node["type"] == "group"}
    assert group_nodes == TAGGED_IDS
    for edge in graph["edges"]:
        assert edge["source"] in node_ids and edge["target"] in node_ids


def test_group_to_group_edges_need_a_quoted_stated_affiliation() -> None:
    graph = _json(_build(), "groups_graph.json")
    group_ids = {node["id"] for node in graph["nodes"] if node["type"] == "group"}
    group_edges = [
        e for e in graph["edges"] if e["source"] in group_ids and e["target"] in group_ids
    ]
    assert [e["edge_type"] for e in group_edges] == ["affiliation"]
    assert group_edges[0]["quote"] == "We are a member of the adjacent fund."
    assert group_edges[0]["relation"] == "member_of" and group_edges[0]["directed"] is True
    assert all(e["quote"] for e in graph["edges"] if e["edge_type"] == "affiliation")


def test_graph_external_ghost_and_co_occurrence() -> None:
    graph = _json(_build(), "groups_graph.json")
    kinds = {node["id"]: node["type"] for node in graph["nodes"]}
    assert kinds["external:Example Network"] == "external"
    assert set(graph["edge_types"]) == {"assignment", "affiliation", "co_occurrence"}
    co = [e for e in graph["edges"] if e["edge_type"] == "co_occurrence"]
    assert {(e["source"], e["target"], e["weight"]) for e in co} == {
        ("activity:education_awareness", "activity:cleanup_removal", 1)
    }
    assert "activity:funding_grantmaking" in kinds


def test_graph_is_empty_but_valid_without_tags() -> None:
    graph = _json(_build(None), "groups_graph.json")
    assert graph["nodes"] == [] and graph["edges"] == []


# ---------------------------------------------------------------------------
# flows.json (T-SANKEY)
# ---------------------------------------------------------------------------


def test_flows_conserve_totals_at_every_stage() -> None:
    flows = _json(_build(), "flows.json")
    sankey = flows["sankey"]
    assert check_flow_conservation(sankey["nodes"], sankey["links"], 2) == []
    into_centrality = sum(
        link["value"] for link in sankey["links"] if link["target"].startswith("centrality:")
    )
    assert into_centrality == 2
    assert flows["activity_combinations"]["other"] == {"combinations": 2, "groups": 2}


def test_conservation_helper_detects_a_broken_flow() -> None:
    nodes = [
        {"id": "sector:a", "stage": "sector"},
        {"id": "centrality:b", "stage": "centrality"},
        {"id": "activity:c", "stage": "activity"},
    ]
    links = [
        {"source": "sector:a", "target": "centrality:b", "value": 2},
        {"source": "centrality:b", "target": "activity:c", "value": 1},
    ]
    problems = check_flow_conservation(nodes, links, 2)
    assert any("centrality:b" in p for p in problems)


def test_flows_are_empty_but_valid_without_tags() -> None:
    flows = _json(_build(None), "flows.json")
    assert flows["sankey"]["links"] == []
    assert check_flow_conservation(flows["sankey"]["nodes"], flows["sankey"]["links"], 0) == []
    assert flows["participation"]["research_monitoring_n"] == 0


# ---------------------------------------------------------------------------
# coverage.json (T-COV) and precision_card.json (T-PRI)
# ---------------------------------------------------------------------------


def test_coverage_denominators_equal_roster_counts() -> None:
    coverage = _json(_build(), "coverage.json")
    assert coverage["roster_total"] == 5 and coverage["tagged_total"] == 2
    for section in ("by_region", "by_country", "by_ambassador_region"):
        assert sum(bucket["roster"] for bucket in coverage[section].values()) == 5, section
        for bucket in coverage[section].values():
            assert sum(bucket["status"].values()) == bucket["roster"], section
    assert coverage["by_ambassador_region"]["belgium"]["roster"] == 1
    assert coverage["by_ambassador_region"]["none"]["roster"] == 4
    assert coverage["by_region"]["Northern America"]["status"]["cannot_determine"] == 1
    assert coverage["weekly_tagged"] == []
    assert coverage["languages"] == {"en": 1, "fr": 1}


def test_precision_card_counts_and_refuses_agreement_without_a_sample() -> None:
    card = _json(_build(), "precision_card.json")
    entity = card["facets"]["entity_type"]
    assert entity["tagged_n"] == 2
    assert card["facets"]["plastics_centrality"]["with_evidence_n"] == 2
    assert card["facets"]["plastics_centrality"]["reviewed_n"] == 1
    for facet in card["tier1_facets"]:
        assert card["facets"][facet]["agreement"] is None
        assert card["facets"][facet]["agreement_reason"] == "no double-tagged sample yet"
    assert card["cannot_determine_reasons"]["no_web_presence"] == 1
    assert card["coverage_by_region"]["Northern America"] == {
        "tagged": 1,
        "roster": 3,
        "coverage": 0.3333,
    }


# ---------------------------------------------------------------------------
# Publication rules (V8, V9, V14)
# ---------------------------------------------------------------------------


def test_no_outputs_carry_ambassador_ids_emails_or_excluded_counts() -> None:
    for name, data in _build().items():
        text = data.decode("utf-8")
        assert "ambassador_id" not in text, name
        assert not re.search(r"excluded|ambiguous", text, re.IGNORECASE), name
        assert not EMAIL_RE.search(text), name


# ---------------------------------------------------------------------------
# Committed files (--check)
# ---------------------------------------------------------------------------


def test_check_passes_against_the_committed_files() -> None:
    result = subprocess.run(
        [sys.executable, str(BUILD_SCRIPT), "--check"],
        capture_output=True,
        text=True,
        cwd=REPO,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Curated submissions (CG-6b): curation/group_tags.csv and group_affiliations.csv
# ---------------------------------------------------------------------------


def _load_script(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


BUILD = _load_script("build_groups", BUILD_SCRIPT)
EXPORT = _load_script("ambassador_export_pr", REPO / "scripts" / "ambassador_export_pr.py")
TAG_HEADER = EXPORT.GROUP_TAG_COLUMNS
AFFILIATION_HEADER = EXPORT.GROUP_AFFILIATION_COLUMNS
# 2026-11-26T10:00:00Z in milliseconds (the export's decided_at).
DECIDED_AT = 1795687200000


def _evidence_columns(facet: str, quote: str = "We remove plastic litter from beaches.") -> dict:
    return {
        f"evidence_{facet}_url": "https://example.org/about",
        f"evidence_{facet}_accessed_at": DATE,
        f"evidence_{facet}_quote": quote,
        f"evidence_{facet}_not_stated": "false",
        f"evidence_{facet}_note": "",
    }


CORE_TAG: dict[str, str] = {
    "group_id": CORE,
    "status": "ambassador_tagged",
    "entity_type": "organisation",
    "sector": "ngo_civil_society",
    "plastics_centrality": "primary",
    "primary_activities": "cleanup_removal;education_awareness",
    "geographic_scope": "local",
    "places": "US-CA",
    "website_languages": "en",
    "themes": "marine_litter",
    "tagged_at": DATE,
    "credit": "a local ambassador",
    **_evidence_columns("plastics_centrality"),
    **_evidence_columns("primary_activities", "We run beach clean-ups."),
}
CORE_AFFILIATION: dict[str, str] = {
    "group_id": CORE,
    "target_name": "Example Network",
    "relation": "member_of",
    "evidence_url": "https://example.org/partners",
    "evidence_accessed_at": DATE,
    "evidence_quote": "We are a member of Example Network.",
}
CORE_PAYLOAD: dict[str, Any] = {
    "group_id": CORE,
    "status": "ambassador_tagged",
    "entity_type": "organisation",
    "sector": "ngo_civil_society",
    "plastics_centrality": "primary",
    "primary_activities": ["cleanup_removal", "education_awareness"],
    "geographic_scope": "local",
    "places": ["US-CA"],
    "website_languages": ["en"],
    "themes": ["marine_litter"],
    "evidence": [
        {
            "facet": "plastics_centrality",
            "url": "https://example.org/about",
            "accessed_at": DATE,
            "quote": "We remove plastic litter from beaches.",
            "not_stated": False,
        },
        {
            "facet": "primary_activities",
            "url": "https://example.org/about",
            "accessed_at": DATE,
            "quote": "We run beach clean-ups.",
            "not_stated": False,
        },
    ],
    "stated_affiliations": [
        {
            "target_name": "Example Network",
            "relation": "member_of",
            "evidence": {
                "url": "https://example.org/partners",
                "accessed_at": DATE,
                "quote": "We are a member of Example Network.",
            },
        }
    ],
}


def _write_rows(path: Path, header: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(header), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in header})


def _curation(root: Path, tags: list[dict] = (), affiliations: list[dict] = ()) -> Path:
    curation = root / "curation"
    curation.mkdir(parents=True, exist_ok=True)
    _write_rows(curation / "group_tags.csv", TAG_HEADER, list(tags))
    _write_rows(curation / "group_affiliations.csv", AFFILIATION_HEADER, list(affiliations))
    return curation


def _record(outputs: Mapping[str, bytes], group_id: str) -> dict:
    groups = _json(outputs, "groups.json")["groups"]
    return next(g for g in groups if g["group_id"] == group_id)


def test_committed_curation_headers_match_the_export_contract() -> None:
    for name, header in (
        ("group_tags.csv", TAG_HEADER),
        ("group_affiliations.csv", AFFILIATION_HEADER),
    ):
        first = (REPO / "curation" / name).read_text(encoding="utf-8").splitlines()[0]
        assert first == ",".join(header), name


def test_header_only_curation_gives_the_same_bytes_as_no_curation(tmp_path: Path) -> None:
    outputs = BUILD.build_outputs(copy.deepcopy(ROSTER), _curation(tmp_path))
    assert outputs == _build(None)


def test_tagged_row_is_ingested_as_tagged_not_reviewed(tmp_path: Path) -> None:
    outputs = BUILD.build_outputs(
        copy.deepcopy(ROSTER), _curation(tmp_path, tags=[CORE_TAG], affiliations=[CORE_AFFILIATION])
    )
    record = _record(outputs, CORE)
    assert record["status"] == "ambassador_tagged"
    assert record["sector"] == "ngo_civil_society"
    assert record["primary_activities"] == ["cleanup_removal", "education_awareness"]
    assert record["places"] == ["US-CA"]
    assert record["tagged_at"] == DATE
    assert record["reviewed_at"] is None
    assert record["layer"] == "core"
    assert [e["facet"] for e in record["evidence"]] == [
        "plastics_centrality",
        "primary_activities",
    ]
    # Credit and the not_an_organisation flag are curation columns, never published fields.
    assert "credit" not in record and "not_an_organisation" not in record


def test_affiliation_rows_attach_to_their_group(tmp_path: Path) -> None:
    outputs = BUILD.build_outputs(
        copy.deepcopy(ROSTER), _curation(tmp_path, tags=[CORE_TAG], affiliations=[CORE_AFFILIATION])
    )
    [stated] = _record(outputs, CORE)["stated_affiliations"]
    assert stated["target_name"] == "Example Network"
    assert stated["relation"] == "member_of"
    assert stated["evidence"] == {
        "url": "https://example.org/partners",
        "accessed_at": DATE,
        "quote": "We are a member of Example Network.",
        "not_stated": False,
    }


def test_cannot_determine_row_is_ingested_as_untagged_with_its_reason(tmp_path: Path) -> None:
    row = {
        "group_id": CD,
        "status": "cannot_determine",
        "cannot_determine_reason": "dead_link",
        "tagged_at": DATE,
        "credit": "a local ambassador",
    }
    outputs = BUILD.build_outputs(copy.deepcopy(ROSTER), _curation(tmp_path, tags=[row]))
    record = _record(outputs, CD)
    assert record["status"] == "cannot_determine"
    assert record["cannot_determine_reason"] == "dead_link"
    assert record["layer"] == "untagged"
    assert record["evidence"] == []


def test_not_an_organisation_removes_the_group_from_every_output(tmp_path: Path) -> None:
    flag = {
        "group_id": ADJ,
        "status": "cannot_determine",
        "cannot_determine_reason": "not_an_organisation",
        "not_an_organisation": "true",
        "tagged_at": DATE,
    }
    outputs = BUILD.build_outputs(copy.deepcopy(ROSTER), _curation(tmp_path, tags=[flag]))
    groups = _json(outputs, "groups.json")["groups"]
    assert ADJ not in {g["group_id"] for g in groups}
    assert len(groups) == len(ROSTER["records"]) - 1
    for name, data in outputs.items():
        assert ADJ.encode() not in data, name
        assert b"Adjacent Fund" not in data, name


def test_rows_for_unknown_groups_are_skipped_with_a_reason(tmp_path: Path, capsys) -> None:
    unknown = "cg_0000000000000000"
    outputs = BUILD.build_outputs(
        copy.deepcopy(ROSTER),
        _curation(
            tmp_path / "with_rows",
            tags=[{**CORE_TAG, "group_id": unknown}],
            affiliations=[{**CORE_AFFILIATION, "group_id": unknown}],
        ),
    )
    out = capsys.readouterr().out
    assert f"skip group_tags row: group_id {unknown!r} is not on the roster" in out
    assert f"skip group_affiliations row: group_id {unknown!r} has no tag row" in out
    assert outputs == _build(None)


def test_malformed_flag_in_the_curation_csv_fails_the_build(tmp_path: Path) -> None:
    row = {**CORE_TAG, "not_an_organisation": "yes"}
    with pytest.raises(GroupsBuildError, match="expected true, false or blank"):
        BUILD.build_outputs(copy.deepcopy(ROSTER), _curation(tmp_path, tags=[row]))


def test_export_csv_round_trips_into_the_build(tmp_path: Path) -> None:
    # The export accepts only cg_ plus 16 hex digits (worker GROUP_ID_RE), so the roster copy
    # gives the first synthetic organisation a real-format id.
    real_id = "cg_0123456789abcdef"
    roster = copy.deepcopy(ROSTER)
    roster["records"][0]["group_id"] = real_id
    body = {
        "ok": True,
        "submissions": [
            {
                "id": 1,
                "region": "norway",
                "stream": "knowledge",
                "kind": "group_tag",
                "payload": {**CORE_PAYLOAD, "group_id": real_id},
                "decided_at": DECIDED_AT,
                "credit_name": "Ada Example",
            }
        ],
        "case_answers": [],
        "institutions": [],
    }
    export = tmp_path / "export.json"
    export.write_text(json.dumps(body), encoding="utf-8")
    args = [
        "--input",
        str(export),
        "--since-file",
        str(tmp_path / "state.json"),
        "--labels-file",
        str(tmp_path / "labels.csv"),
        "--additions-file",
        str(tmp_path / "additions.csv"),
        "--regions-dir",
        str(tmp_path / "regions"),
        "--group-tags-file",
        str(tmp_path / "group_tags.csv"),
        "--group-affiliations-file",
        str(tmp_path / "group_affiliations.csv"),
        "--group-suggestions-file",
        str(tmp_path / "group_suggestions.csv"),
    ]
    assert EXPORT.main(args) == 0
    outputs = BUILD.build_outputs(roster, tmp_path)
    record = _record(outputs, real_id)
    assert record["sector"] == "ngo_civil_society"
    assert record["tagged_at"] == DATE
    assert record["evidence"][0]["quote"] == "We remove plastic litter from beaches."
    assert record["stated_affiliations"][0]["target_name"] == "Example Network"
    # The approving ambassador's credit stays in the curation CSV and is never published.
    assert all(b"Ada Example" not in data for data in outputs.values())
