"""Offline checks for the BQ-G3 global gold-sampling frame: rules, strata and exclusions."""

from __future__ import annotations

import csv
import gzip
import io
import json
from pathlib import Path

import pytest

from atlas.nlp import gold_frame as gf
from scripts import build_gold_global_frame as builder
from scripts.check_s4_2 import assert_guide_examples_excluded

ROOT = Path(__file__).resolve().parents[1]


def _queries() -> dict:
    return {
        "core_terms": ["microplastic", "plastic debris"],
        "qualified_terms": [{"term": "microfiber", "any_context": ["tire wear"]}],
        "exclusions": ["microplastic strain"],
    }


def _score_rules() -> gf.ScoreRules:
    queries = _queries()
    queries["tier_2_terms"] = ["BPA"]
    return gf.load_score_rules(queries)


def _theme_rules() -> gf.ThemeRules:
    v32 = {
        "anchor_phrases": ["plastic waste", "plastic packaging"],
        "themes": {"waste_colonialism_lens": {"terms": ["waste colonialism"]}},
    }
    register = {
        "terms": [
            {"term": "waste pickers", "group": "lifecycle_and_society", "handling": "co_term"},
            {
                "term": "Indigenous knowledge",
                "group": "lifecycle_and_society",
                "handling": "title_only",
            },
            {"term": "waste flows", "group": "lifecycle_and_society", "handling": "exclude"},
        ]
    }
    pollution = {"core_terms": ["marine debris"]}
    return gf.load_theme_rules(v32, register, pollution)


def test_block_assignment_uses_registry_then_language() -> None:
    registry = {"W1"}
    assert gf.assign_block("W1", "fr", registry) == gf.BLOCK_REGISTRY
    assert gf.assign_block("W2", "en", registry) == gf.BLOCK_GLOBAL_EN
    assert gf.assign_block("W3", "pt", registry) == gf.BLOCK_GLOBAL_NON_EN
    assert gf.assign_block("W4", None, registry) == gf.BLOCK_GLOBAL_NON_EN


def test_theme_precedence_lens_over_lifecycle_over_pollution() -> None:
    rules = _theme_rules()
    both = "waste colonialism and waste pickers in plastic waste"
    assert gf.assign_theme("", both, rules) == gf.THEME_LENS
    lifecycle = gf.assign_theme("plastic waste and waste pickers", "", rules)
    assert lifecycle == gf.THEME_LIFECYCLE
    assert gf.assign_theme("marine debris", "", rules) == gf.THEME_POLLUTION
    assert gf.assign_theme("unrelated", "text", rules) == gf.THEME_OTHER


def test_lifecycle_needs_anchor_and_title_only_needs_title() -> None:
    rules = _theme_rules()
    # Lifecycle term without an anchor does not qualify.
    assert gf.assign_theme("waste pickers", "", rules) == gf.THEME_OTHER
    # Title-only term counts only in the title, and still needs an anchor.
    assert (
        gf.assign_theme("", "Indigenous knowledge and plastic packaging", rules) == gf.THEME_OTHER
    )
    assert (
        gf.assign_theme("Indigenous knowledge and plastic packaging", "", rules)
        == gf.THEME_LIFECYCLE
    )


def test_rule_points_weight_title_over_abstract_and_exclusions_zero() -> None:
    rules = _score_rules()
    assert gf.rule_points("microplastic study", "", rules) == 2
    assert gf.rule_points("", "microplastic study", rules) == 1
    assert gf.rule_points("microplastic study", "microplastic again", rules) == 3
    assert gf.rule_points("microfiber from tire wear", "", rules) == 1
    assert gf.rule_points("BPA in toys", "", rules) == 1
    assert gf.rule_points("microplastic strain test", "", rules) == 0


def test_score_and_band_boundaries() -> None:
    assert gf.rule_score(0) == 0.0
    assert gf.rule_score(1) == 0.25
    assert gf.rule_score(2) == 0.5
    assert gf.rule_score(9) == 1.0
    assert gf.band_for(0.0) == "low"
    assert gf.band_for(0.2499) == "low"
    assert gf.band_for(0.34) == "medium"
    assert gf.band_for(0.5) == "medium"
    assert gf.band_for(0.67) == "high"
    assert gf.band_for(1.0) == "high"


def test_rand_keys_deterministic_by_seed_and_order_free() -> None:
    ids = ["W3", "W1", "W2"]
    first = gf.rand_keys(ids, seed=7)
    assert first == gf.rand_keys(list(reversed(ids)), seed=7)
    assert first != gf.rand_keys(ids, seed=8)
    assert set(first) == set(ids)
    assert all(0.0 <= value < 1.0 for value in first.values())


def test_score_snapshot_hash_is_order_free() -> None:
    pairs = [("W2", 0.5), ("W1", 0.0)]
    assert gf.score_snapshot_sha256(pairs) == gf.score_snapshot_sha256(reversed(pairs))
    assert gf.score_snapshot_sha256(pairs) != gf.score_snapshot_sha256([("W2", 0.25), ("W1", 0.0)])


def test_guide_example_exclusion_by_work_id_and_doi() -> None:
    guides = [
        {"work_id": "W9", "doi": "https://doi.org/10.1/ABC", "role": "guide_example"},
        {"work_id": "", "doi": "", "role": "guide_example"},
        {"work_id": "W5", "doi": "", "role": "gold"},
    ]
    ids, dois = gf.guide_example_ids(guides)
    assert ids == {"W9"} and dois == {"10.1/abc"}
    assert gf.is_guide_example("W9", "", ids, dois)
    assert gf.is_guide_example("W7", "10.1/ABC", ids, dois)
    assert not gf.is_guide_example("W5", "", ids, dois)
    assert not gf.is_guide_example("W6", "", ids, dois)


def test_guide_assert_fails_on_frame_leak() -> None:
    guides = [{"work_id": "W9", "doi": "10.1/x", "role": "guide_example"}]
    frame = [{"work_id": "W9", "doi": "", "block": "registry_region"}]
    with pytest.raises(AssertionError, match="W9"):
        assert_guide_examples_excluded(guides, {"gold_global_frame_v1": frame}, {})
    clean = [{"work_id": "W1", "doi": "10.9/other"}]
    assert assert_guide_examples_excluded(guides, {"gold_global_frame_v1": clean}, {}) == 1


def test_frame_csv_has_identifiers_only_and_quotes_commas() -> None:
    row = gf.FrameWork(
        work_id="W1",
        doi="10.1/x,y",
        block=gf.BLOCK_GLOBAL_EN,
        theme_group=gf.THEME_OTHER,
        score=0.5,
        band="medium",
        rand_key=0.25,
    )
    text = gf.render_frame_csv([row]).decode("utf-8")
    header = next(csv.reader(io.StringIO(text)))
    assert header == list(gf.FRAME_COLUMNS)
    assert "title" not in header and "abstract" not in header
    parsed = list(csv.DictReader(io.StringIO(text)))
    assert parsed[0]["doi"] == "10.1/x,y"
    assert parsed[0]["stratum"] == "global_english|other|medium"
    assert parsed[0]["rand_key"] == "0.2500000000000000"


def test_check_skips_rebuild_without_ignored_inputs(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(builder, "WORKS", tmp_path / "missing_works.parquet")
    notes = builder.check(rebuild=True)
    assert any(note.startswith("SKIP rebuild") for note in notes)


def test_sixteen_strata_and_block_theme_mapping() -> None:
    strata = gf.all_strata()
    assert len(strata) == len(set(strata)) == 16
    assert "global_english|lens-candidate|all" in strata
    assert "registry_region|pollution-core|all" in strata
    assert "global_non_english|other|all" in strata
    assert not any(s.startswith("registry_region|lens") for s in strata)
    # Outside global English the lens stratum is merged into lifecycle.
    assert gf.frame_theme_group(gf.BLOCK_REGISTRY, gf.THEME_LENS) == gf.THEME_LIFECYCLE
    assert gf.frame_theme_group(gf.BLOCK_GLOBAL_NON_EN, gf.THEME_LENS) == gf.THEME_LIFECYCLE
    assert gf.frame_theme_group(gf.BLOCK_GLOBAL_EN, gf.THEME_LENS) == gf.THEME_LENS
    assert gf.stratum_id(gf.BLOCK_GLOBAL_EN, gf.THEME_POLLUTION, "low") == (
        "global_english|pollution-core|low"
    )
    assert gf.stratum_id(gf.BLOCK_REGISTRY, gf.THEME_OTHER, "high") == "registry_region|other|all"


def test_zero_score_works_stay_in_low_band() -> None:
    assert gf.rule_score(0) == 0.0
    assert gf.band_for(gf.rule_score(0)) == "low"
    row = gf.FrameWork(
        work_id="W0",
        doi="",
        block=gf.BLOCK_GLOBAL_EN,
        theme_group=gf.THEME_OTHER,
        score=0.0,
        band="low",
        rand_key=0.5,
    )
    text = gf.render_frame_csv([row]).decode("utf-8")
    parsed = list(csv.DictReader(io.StringIO(text)))
    assert parsed[0]["score"] == "0.0000"
    assert parsed[0]["stratum"] == "global_english|other|low"


def test_gzip_is_deterministic_with_zero_mtime() -> None:
    data = gf.render_frame_csv(
        [gf.FrameWork("W1", "", gf.BLOCK_REGISTRY, gf.THEME_OTHER, 0.0, "low", 0.1)]
    )
    first = gf.gzip_bytes(data)
    assert first == gf.gzip_bytes(data)
    assert first[4:8] == b"\x00\x00\x00\x00"
    assert gzip.decompress(first) == data


def test_committed_frame_matches_manifest_and_guide_exclusion() -> None:
    frame_path = ROOT / builder.OUT_CSV
    manifest_path = ROOT / builder.OUT_JSON
    if not frame_path.exists() or not manifest_path.exists():
        pytest.skip("global frame not yet committed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    gz_bytes = frame_path.read_bytes()
    assert manifest["frame_sha256"] == gf.sha256_bytes(gz_bytes)
    csv_bytes = gzip.decompress(gz_bytes)
    assert manifest["frame_uncompressed_sha256"] == gf.sha256_bytes(csv_bytes)
    assert not (ROOT / builder.PLAIN_CSV).exists()
    assert manifest["model_version"] == "rules-v3.1-proxy"
    assert manifest["seed"] == gf.GLOBAL_FRAME_SEED
    rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
    assert "title" not in rows[0] and "abstract" not in rows[0]
    assert len(manifest["strata"]) == 16
    guides = builder._load_csv(ROOT / builder.GUIDE_EXAMPLES)
    assert assert_guide_examples_excluded(guides, {"frame": rows}, {}) >= 0
