"""Search-term highlighting for the Streamlit review apps (atlas.review_highlight)."""

from __future__ import annotations

from pathlib import Path

from atlas import review_highlight as hl
from atlas.ingest.grants.normalize import STRONG_ABSTRACT_RE
from atlas.query import load_query_config

ROOT = Path(__file__).resolve().parents[1]

CONFIG = {
    "core_terms": ["microplastic", "plastic debris", "marine debris"],
    "qualified_terms": [{"term": "tire wear", "any_context": ["stormwater", "particles"]}],
    "tier_2_terms": ["phthalate"],
    "exclusions": ["plastic deformation"],
}


def _kinds(text: str, rules: list[hl.Rule]) -> list[tuple[str, str]]:
    live = hl.active_rules(rules, text)
    return [(h.kind, text[h.start : h.end]) for h in hl.find_hits(text, live)]


def test_core_plural_hyphen_and_case() -> None:
    rules = hl.build_rules([CONFIG], include_stem=False)
    text = "Microplastics and marine-debris and Plastic  debris"
    assert _kinds(text, rules) == [
        ("core", "Microplastics"),
        ("core", "marine-debris"),
        ("core", "Plastic  debris"),
    ]


def test_qualified_term_needs_context_anywhere_in_record() -> None:
    rules = hl.build_rules([CONFIG], include_stem=False)
    assert _kinds("tire wear on roads", rules) == []
    title, abstract = "Tire wear in rivers", "Stormwater carried them."
    live = hl.active_rules(rules, title, abstract)
    assert [(h.kind, h.label) for h in hl.find_hits(title, live)] == [("qualified", "tire wear")]
    assert [h.kind for h in hl.find_hits(abstract, live)] == ["context"]


def test_exclusion_wins_overlap_and_stem_marks_noise() -> None:
    rules = hl.build_rules([CONFIG])
    text = "Plastic deformation and plasticity of microplastics"
    assert _kinds(text, rules) == [
        ("exclusion", "Plastic deformation"),
        ("stem", "plasticity"),
        ("core", "microplastics"),
    ]


def test_html_is_escaped_and_marks_are_added() -> None:
    rules = hl.build_rules([CONFIG])
    out = hl.highlight_html("<b>x</b> & $5 microplastic", rules)
    assert "<b>" not in out
    assert "&lt;b&gt;x&lt;/b&gt; &amp; $5 " in out
    assert out.count("<mark ") == 1 and "core search term: microplastic" in out


def test_record_blocks_summary_and_empty_abstract() -> None:
    rules = hl.build_rules([CONFIG])
    blocks = hl.record_blocks("Microplastic sources", None, rules, empty="No abstract.")
    assert "microplastic</mark>" in blocks.summary
    assert "No abstract." in blocks.abstract
    none = hl.record_blocks("Ocean currents", "Nothing here.", rules, empty="-")
    assert "none in title or abstract" in none.summary


def test_grant_rules_strong_regex_and_keywords() -> None:
    rules = hl.build_rules(
        [CONFIG],
        extra=[
            hl.regex_rule("core", "strong abstract term", STRONG_ABSTRACT_RE),
            *hl.keyword_rules(["litter", "6PPD"]),
        ],
    )
    text = "Tyre wear particles, litter and 6PPD"
    kinds = _kinds(text, rules)
    assert ("core", "Tyre wear particles") in kinds
    assert ("keyword", "litter") in kinds and ("keyword", "6PPD") in kinds


def test_live_query_configs_compile() -> None:
    for name in ("queries.yml", "queries_v3.yml", "queries_v2.yml"):
        path = ROOT / "config" / name
        if path.exists():
            rules = hl.build_rules([load_query_config(path)])
            assert any(r.kind == "core" for r in rules)
            assert hl.highlight_html("Microplastic pollution in rivers", rules).count("<mark") >= 1
