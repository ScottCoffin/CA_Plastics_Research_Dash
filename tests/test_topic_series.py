"""Tests for the BQ-4.1 topic series layer on synthetic inputs (no repository data)."""

from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import pytest

from atlas.analytics.topic_series import (
    FRAMING_RULE,
    NO_LABELS_MESSAGE,
    CaWork,
    RelevanceInputs,
    SeriesInputs,
    build_series,
    ca_corpus,
    check_global_sums,
    read_snapshot,
    snapshot_rows,
    snapshot_sha256,
    works_from_snapshot,
    write_snapshot,
)
from atlas.build.curation import Curation

AS_OF = date(2026, 11, 25)  # last complete year 2025; 2026 is partial
TAXONOMY = {
    "domain_tags": [
        {"id": "air", "seed_concepts": ["airborne"]},
        {"id": "soil_and_agriculture", "seed_concepts": ["soil"]},
        {"id": "lca_and_sustainability", "status": "approved_no_seeds", "seed_concepts": []},
        {
            "id": "culture_media_and_discourse",
            "experimental": True,
            "status": "approved_no_seeds",
            "seed_concepts": [],
        },
    ],
    "facets": {"analytic_lens": {"values": ["waste_colonialism", "responsibility_shifting"]}},
}
QUERY = {
    "always_relevant_patterns": ["micro-?plastic"],
    "title_relevant_patterns": ["plastisphere"],
    "relevance_policy": {"tier2_survives_low_confidence_false": True},
}


def _work(work_id: str, year: int | None, *, ca: bool = True, title: str = "x") -> dict:
    return {
        "work_id": work_id,
        "year": year,
        "title": title,
        "abstract": "",
        "ca_any_author": ca,
    }


def _label(work_id: str, *, related: bool, tags=(), facets=(), tier="core") -> dict:
    return {
        "work_id": work_id,
        "plastic_related": related,
        "plastic_tier": tier if related else "",
        "domain_tags": list(tags),
        "facet_tags": list(facets),
    }


def _inputs(**overrides) -> SeriesInputs:
    base = {
        "works": [
            _work("W1", 2024),
            _work("W2", 2025),
            _work("W3", 2025),
            _work("W4", 2026),
            _work("W5", 2025, ca=False),
            _work("W6", 2025),
        ],
        "labels": [
            _label("W1", related=True, tags=["air", "soil_and_agriculture"]),
            _label("W2", related=True, tags=["air"]),
            _label("W3", related=True, tags=["air"]),
            _label("W4", related=True, tags=["air"]),
            _label("W5", related=True, tags=["air"]),
            _label("W6", related=False, tags=["air"]),
        ],
        "global_works": [],
        "taxonomy": TAXONOMY,
        "query_config": QUERY,
    }
    base.update(overrides)
    return SeriesInputs(**base)


def _payload(inputs: SeriesInputs, *, as_of: date = AS_OF) -> dict:
    corpus = ca_corpus(inputs)
    rows = snapshot_rows(corpus.works)
    return build_series(
        works=works_from_snapshot(rows),
        removed=corpus.removed,
        global_rows=inputs.global_works,
        taxonomy=inputs.taxonomy,
        as_of=as_of,
        snapshot={"content_sha256": snapshot_sha256(rows)},
        inputs={},
    )


def _tag(payload: dict, tag: str) -> dict:
    return next(t for t in payload["ca"]["tags"] if t["tag"] == tag)


def test_experimental_tags_are_excluded_from_series_and_snapshot():
    inputs = _inputs(
        labels=[
            _label("W1", related=True, tags=["air", "culture_media_and_discourse"]),
            _label("W2", related=True, tags=["culture_media_and_discourse"]),
        ]
    )
    payload = _payload(inputs)
    assert "culture_media_and_discourse" not in {t["tag"] for t in payload["ca"]["tags"]}
    assert payload["ca"]["tags_excluded"] == [
        {"tag": "culture_media_and_discourse", "reason": "experimental"}
    ]
    rows = snapshot_rows(ca_corpus(inputs).works)
    assert all(row["tag"] != "culture_media_and_discourse" for row in rows)


def test_seedless_tag_without_labels_is_reported_as_no_labels_yet():
    payload = _payload(_inputs())
    tag = _tag(payload, "lca_and_sustainability")
    assert tag["status"] == "no_labels_yet"
    assert tag["message"] == NO_LABELS_MESSAGE == "no labels yet"
    assert tag["total"] == 0
    assert all(row["count"] == 0 for row in tag["by_year"])
    assert _tag(payload, "air")["status"] == "labelled"


def test_partial_year_is_flagged_and_last_complete_year_excludes_it():
    payload = _payload(_inputs())
    assert payload["last_complete_year"] == 2025
    by_year = {row["year"]: row for row in _tag(payload, "air")["by_year"]}
    assert by_year[2025]["partial"] is False
    assert by_year[2026]["partial"] is True
    assert by_year[2026]["count"] == 1
    plastic = {row["year"]: row for row in payload["ca"]["plastic_related_by_year"]}
    assert plastic[2026]["partial"] is True


def test_share_uses_the_year_plastic_related_denominator():
    payload = _payload(_inputs())
    row = next(r for r in _tag(payload, "air")["by_year"] if r["year"] == 2025)
    # 2025 plastic-related CA works: W2, W3 (W5 is not CA, W6 is not plastic-related)
    assert row["count"] == 2
    assert row["share"] == 1.0


def test_label_source_sensitivity_variants_split_owner_and_rule():
    inputs = _inputs(
        works=[_work("W1", 2025), _work("W2", 2025), _work("W3", 2025)],
        labels=[
            _label("W1", related=True, tags=["air"]),
            _label("W2", related=True, tags=["air"]),
            _label("W3", related=True, tags=["air"]),
        ],
        curation=Curation(work_overrides={"W2": {"domain_tags": ["soil_and_agriculture"]}}),
    )
    payload = _payload(inputs)
    air = _tag(payload, "air")
    assert air["total"] == 2  # W2 moved to the owner tag set
    assert air["sensitivity"]["all_sources"]["total"] == 2
    assert air["sensitivity"]["rule_only"]["total"] == 2
    assert air["sensitivity"]["owner_model_only"]["total"] == 0
    soil = _tag(payload, "soil_and_agriculture")
    assert soil["total"] == 1
    assert soil["sensitivity"]["owner_model_only"]["total"] == 1
    assert soil["sensitivity"]["rule_only"]["total"] == 0


def test_snapshot_hash_is_stable_across_order_and_file_round_trip(tmp_path: Path):
    corpus = ca_corpus(_inputs())
    rows = snapshot_rows(corpus.works)
    sha = snapshot_sha256(rows)
    assert snapshot_sha256(list(reversed(rows))) == sha
    assert snapshot_sha256(snapshot_rows(ca_corpus(_inputs()).works)) == sha
    path = tmp_path / "labels_snapshot_v1.parquet"
    write_snapshot(path, rows)
    assert snapshot_sha256(read_snapshot(path)) == sha
    assert [dict(r) for r in read_snapshot(path)] == [dict(r) for r in rows]


def test_snapshot_hash_changes_when_a_label_changes():
    base = snapshot_rows(ca_corpus(_inputs()).works)
    changed_inputs = _inputs(
        labels=[_label("W1", related=True, tags=["soil_and_agriculture"])] + _inputs().labels[1:]
    )
    changed = snapshot_rows(ca_corpus(changed_inputs).works)
    assert snapshot_sha256(base) != snapshot_sha256(changed)


def test_snapshot_round_trip_rebuilds_the_same_works():
    works = ca_corpus(_inputs()).works
    rebuilt = works_from_snapshot(snapshot_rows(works))
    assert rebuilt == sorted(works, key=lambda w: w.work_id)
    assert all(isinstance(w, CaWork) for w in rebuilt)


def test_ca_precedence_owner_review_beats_rule_and_model_and_removals_apply():
    inputs = _inputs(
        works=[_work("W1", 2025), _work("W2", 2025), _work("W3", 2025), _work("W4", 2025)],
        labels=[
            _label("W1", related=False, tags=["air"]),  # owner says related
            _label("W2", related=False, tags=["air"]),  # model says related, owner reviewed
            _label("W3", related=True, tags=["air"]),  # excluded by curation
            _label("W4", related=False, tags=["air"]),  # always-relevant title rule
        ],
        relevance=RelevanceInputs(
            relevant={"W1": True, "W2": False},
            owner_reviewed=frozenset({"W1", "W2"}),
            model={"W1": False, "W2": True},
        ),
        curation=Curation(work_overrides={"W3": {"exclude": True}}),
    )
    corpus = ca_corpus(inputs)
    by_id = {w.work_id: w for w in corpus.works}
    assert by_id["W1"].plastic_related is True
    assert by_id["W2"].plastic_related is False
    assert "W3" not in by_id
    assert corpus.removed == 1
    assert by_id["W4"].plastic_related is False  # no title or always-relevant term in its text


def test_relevance_rules_title_and_always_relevant_apply_when_not_owner_reviewed():
    inputs = _inputs(
        works=[
            _work("W1", 2025, title="Microplastics in soil"),
            _work("W2", 2025, title="Plastisphere communities"),
            _work("W3", 2025, title="Unrelated"),
        ],
        labels=[_label(w, related=False, tags=["air"]) for w in ("W1", "W2", "W3")],
    )
    by_id = {w.work_id: w for w in ca_corpus(inputs).works}
    assert by_id["W1"].plastic_related is True
    assert by_id["W2"].plastic_related is True
    assert by_id["W3"].plastic_related is False


def test_tier2_chemicals_survive_low_confidence_false():
    inputs = _inputs(
        works=[_work("W1", 2025)],
        labels=[_label("W1", related=True, tags=["air"], tier="chemicals-in-plastics")],
        relevance=RelevanceInputs(relevant={"W1": False}, low_confidence_false=frozenset({"W1"})),
    )
    assert ca_corpus(inputs).works[0].plastic_related is True


def test_non_ca_works_and_undated_works_are_handled():
    inputs = _inputs(
        works=[_work("W1", None), _work("W2", 2025, ca=False), _work("W3", 2025)],
        labels=[_label(w, related=True, tags=["air"]) for w in ("W1", "W2", "W3")],
    )
    works = ca_corpus(inputs).works
    assert [w.work_id for w in works] == ["W1", "W3"]
    payload = _payload(inputs)
    assert payload["ca"]["undated_works"] == 1
    assert payload["ca"]["works"] == 2
    assert all(row["year"] is not None for row in payload["ca"]["plastic_related_by_year"])


def test_lens_block_says_no_lens_labels_yet_without_lens_labels():
    payload = _payload(_inputs())
    lens = payload["lens"]
    assert lens["status"] == "no_lens_labels_yet"
    assert lens["message"] == "no lens labels yet"
    assert lens["series"] == []
    assert FRAMING_RULE == (
        "a lens is counted only when the work itself uses the frame, with a quoted excerpt"
    )
    assert FRAMING_RULE in lens["framing_rule"]


def test_lens_series_counts_only_plastic_related_works_with_lens_labels():
    inputs = _inputs(
        labels=[
            _label("W1", related=True, tags=["air"], facets=["waste_colonialism"]),
            _label("W2", related=True, tags=["air"]),
            _label("W6", related=False, facets=["waste_colonialism"]),
        ],
    )
    lens = _payload(inputs)["lens"]
    assert lens["status"] == "labelled"
    assert [entry["lens"] for entry in lens["series"]] == ["waste_colonialism"]
    series = lens["series"][0]
    assert series["total"] == 1
    assert next(r for r in series["by_year"] if r["year"] == 2024)["count"] == 1


def _global_rows(topics: int, years=(2024, 2025, 2026)) -> list[dict]:
    rows: list[dict] = []
    for index in range(topics):
        for year in years:
            for _ in range(topics - index + (1 if year == 2026 else 0)):
                rows.append(
                    {
                        "publication_year": year,
                        "primary_topic_id": f"https://openalex.org/T{index}",
                        "primary_topic_name": f"Topic {index:02d}",
                    }
                )
    for _ in range(2):
        rows.append(
            {"publication_year": 2025, "primary_topic_id": None, "primary_topic_name": None}
        )
    return rows


def test_global_top_thirty_plus_other_sums_to_totals():
    rows = _global_rows(35)
    inputs = _inputs(global_works=rows)
    payload = _payload(inputs)
    glob = payload["global"]
    assert glob["screening"] == "unscreened query hits"
    assert glob["top_n"] == 30
    assert len(glob["topics"]) == 30
    assert glob["topics"][0]["topic"] == "Topic 00"
    assert glob["other"]["no_primary_topic_total"] == 2
    totals = {r["year"]: r["count"] for r in glob["total_by_year"]}
    assert totals[2025] == len([r for r in rows if r["publication_year"] == 2025])
    check_global_sums(glob)
    for year, total in totals.items():
        top = sum(
            next(r["count"] for r in topic["by_year"] if r["year"] == year)
            for topic in glob["topics"]
        )
        other = next(r["count"] for r in glob["other"]["by_year"] if r["year"] == year)
        assert top + other == total


def test_global_sum_check_raises_when_a_row_is_wrong():
    payload = _payload(_inputs(global_works=_global_rows(3)))
    broken = copy.deepcopy(payload["global"])
    broken["other"]["by_year"][0]["count"] += 1
    with pytest.raises(ValueError, match="do not sum"):
        check_global_sums(broken)


def test_partial_global_year_is_flagged():
    payload = _payload(_inputs(global_works=_global_rows(2)))
    flags = {r["year"]: r["partial"] for r in payload["global"]["total_by_year"]}
    assert flags[2025] is False
    assert flags[2026] is True
