"""BQ-S2 candidate plastic-v3.2: rendering, parenthesis checks, URL limits and register rules."""

from __future__ import annotations

import hashlib
import importlib.util
import re
import sys
from pathlib import Path

import pytest
import yaml

from atlas.query import load_query_config, render_query
from atlas.query_v32 import (
    MAX_URL_CHARS,
    UrlTooLongError,
    base_config,
    check_url_length,
    is_fully_parenthesised,
    load_candidate,
    operator_count,
    plan,
    theme_config,
    works_url,
    wrapped,
)

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "config" / "queries_v32_candidate.yml"
V31 = ROOT / "config" / "queries.yml"
REGISTER = ROOT / "config" / "search_vocabulary_v1.yml"
# sha256 of config/queries.yml at BQ-S2 (the active v3.1 query must not change).
V31_SHA256 = "ef2cb1515864d3e5fd4fe3af6a0b29634daac8246ce6be38937d8f7f684a4425"
# A3 section 5.2 anchor list, verbatim (singular and plural as spelled in the spec).
A3_ANCHORS = {
    "plastic waste",
    "plastic pollution",
    "plastic debris",
    "plastic litter",
    "plastic bag",
    "plastic bags",
    "plastic bottle",
    "plastic bottles",
    "plastic packaging",
    "plastic products",
    "plastic production",
    "plastic recycling",
    "single-use plastic",
    "single-use plastics",
    "microplastic",
    "microplastics",
    "bioplastic",
    "bioplastics",
    "biodegradable plastic",
    "biodegradable plastics",
    "compostable plastic",
    "compostable plastics",
    "plastics industry",
}
ALLOWED_GROUPS = {
    "pollution",
    "particle_descriptors",
    "lifecycle_and_society",
    "pollution_health_toxicology",
    "lens_evidence",
}
ALLOWED_HANDLING = {"qualified", "co_term", "title_only"}


@pytest.fixture(scope="module")
def candidate() -> dict:
    return load_candidate(str(CANDIDATE))


@pytest.fixture(scope="module")
def v31() -> dict:
    return load_query_config(str(V31))


@pytest.fixture(scope="module")
def register() -> dict[str, dict]:
    rows = yaml.safe_load(REGISTER.read_text(encoding="utf-8"))["terms"]
    return {row["term"]: row for row in rows if row["language"] == "en"}


@pytest.fixture(scope="module")
def requests(candidate: dict, v31: dict):
    return plan(candidate, v31).requests()


def _phrases(expression: str) -> set[str]:
    """Quoted phrases and bare words of an expression, operators removed."""

    found = {a or b for a, b in re.findall(r'"([^"]*)"|([^\s()"]+)', expression)}
    return {value.lower() for value in found} - {"and", "or", "not"}


def test_checker_rejects_unwrapped_mix_and_accepts_nested_groups() -> None:
    assert not is_fully_parenthesised("a OR b AND c")
    assert is_fully_parenthesised("((a OR b) AND (c))")
    assert not is_fully_parenthesised("(a) NOT (b)")
    assert is_fully_parenthesised("((a) NOT (b))")
    assert not is_fully_parenthesised("((a OR b)")
    assert not is_fully_parenthesised("(a OR)")
    assert is_fully_parenthesised('("plastic waste" AND (microplastic OR "a b"))')


def test_operator_count_ignores_quoted_operator_words() -> None:
    assert operator_count("((a OR b) AND (c))") == 2
    assert operator_count('("a AND b" OR c)') == 1
    assert operator_count("((a) NOT (b))") == 1


def test_every_rendered_request_is_fully_parenthesised(candidate: dict, requests) -> None:
    assert requests
    for request in requests:
        assert is_fully_parenthesised(request.expression), request.label
    assert is_fully_parenthesised(wrapped(candidate))


def test_no_request_url_exceeds_limit(candidate: dict, requests) -> None:
    assert MAX_URL_CHARS == 8000
    for request in requests:
        assert len(request.url) <= MAX_URL_CHARS, request.label


def test_check_url_length_raises_above_limit() -> None:
    assert check_url_length("x" * MAX_URL_CHARS).startswith("x")
    with pytest.raises(UrlTooLongError):
        check_url_length("x" * (MAX_URL_CHARS + 1))


def test_combined_request_fits_and_themes_are_kept(candidate: dict, v31: dict) -> None:
    query_plan = plan(candidate, v31)
    assert query_plan.combined_length <= MAX_URL_CHARS
    assert query_plan.combined is not None
    assert query_plan.base is None
    assert query_plan.combined.length <= MAX_URL_CHARS
    assert {r.label for r in query_plan.themes} == {
        f"theme:{name}" for name, block in candidate["themes"].items() if block["terms"]
    }


def test_title_requests_use_title_field_only(candidate: dict, v31: dict) -> None:
    query_plan = plan(candidate, v31)
    assert [r.field for r in query_plan.titles] == ["title.search"]
    for request in query_plan.themes:
        assert request.field == "title_and_abstract.search"
        assert "title.search" not in request.url


def test_v31_config_unchanged() -> None:
    digest = hashlib.sha256(V31.read_bytes()).hexdigest()
    assert digest == V31_SHA256


def test_v31_terms_copied_into_candidate(candidate: dict, v31: dict) -> None:
    assert set(v31["core_terms"]) <= set(candidate["core_terms"])
    v31_names = {row["term"] for row in v31["qualified_terms"]}
    candidate_names = {
        row["term"] for row in candidate["qualified_terms"] if "register_term" not in row
    }
    assert v31_names == candidate_names
    assert set(v31["exclusions"]) <= set(candidate["exclusions"])


def test_candidate_metadata_and_promotion(candidate: dict) -> None:
    assert candidate["version"] == "plastic-v3.2-candidate"
    assert candidate["status"] == "candidate"
    assert candidate["promotion"]["status"] == "not promoted"
    assert "precision" in candidate["promotion"]["rule"]


def test_added_rows_back_reference_the_register(candidate: dict, register: dict) -> None:
    added = [row for row in candidate["qualified_terms"] if "register_term" in row]
    added += candidate.get("title_only_terms", [])
    # 60 qualified + 4 title-only; "recycler" removed in lead review (stem collision).
    assert len(added) == 60 + 4
    for row in added:
        reg = register[row["register_term"]]
        assert row["term"] == row["register_term"]
        assert reg["tier"] in {"A", "B"}, row["term"]
        assert reg["in_v31"] is False, row["term"]
        assert reg["handling"] in ALLOWED_HANDLING, row["term"]
        assert reg["group"] in ALLOWED_GROUPS, row["term"]
        assert row["theme"] in candidate["themes"], row["term"]
        assert row["tier"] == reg["tier"] and row["handling"] == reg["handling"]


def test_stem_collision_terms_are_not_rendered(candidate: dict) -> None:
    # OpenAlex stems "recycler" to "recycl": alone with the anchors it matched 23,264 works
    # (lead probe 2026-11-25, docs/QUERY_V32_CANDIDATE.md), i.e. every anchored recycling work.
    rendered = [row["term"].lower() for row in candidate["qualified_terms"]]
    rendered += [row["term"].lower() for row in candidate.get("title_only_terms", [])]
    themed = [t.lower() for theme in candidate["themes"].values() for t in theme["terms"]]
    assert "recycler" not in rendered
    assert "recycler" not in themed


def test_anchor_required_rows_carry_the_anchor_context(candidate: dict, register: dict) -> None:
    anchors = set(candidate["anchor_phrases"])
    assert anchors == A3_ANCHORS
    for row in candidate["qualified_terms"]:
        if "register_term" in row and "context_source" not in row:
            assert register[row["register_term"]]["anchor_required"] is True
            assert set(row["any_context"]) == A3_ANCHORS


def test_microfibre_uses_the_v31_microfiber_context(candidate: dict, v31: dict) -> None:
    (row,) = [r for r in candidate["qualified_terms"] if r.get("register_term") == "microfibre"]
    (v31_row,) = [q for q in v31["qualified_terms"] if q["term"] == "microfiber"]
    assert row["any_context"] == v31_row["any_context"]
    assert "context_source" in row


def test_bare_plastic_words_and_petrochemical_are_never_anchors(candidate: dict) -> None:
    for word in ("plastic", "plastics", "petrochemical", "petrochemical plastics"):
        assert word not in candidate["anchor_phrases"]
    added = [row for row in candidate["qualified_terms"] if "register_term" in row]
    for row in added + candidate["title_only_terms"]:
        assert "plastic" not in row["any_context"]
        assert "plastics" not in row["any_context"]
        assert "petrochemical" not in row["any_context"]


def test_excluded_register_rows_are_never_rendered(candidate: dict, register: dict) -> None:
    forbidden = {
        name.lower()
        for name, reg in register.items()
        if reg["tier"] in {"C", "D", "never_standalone"}
        or reg["handling"] in {"lens_evidence", "exclude"}
        or name in {"MP", "NP"}
    }
    forbidden -= {phrase.lower() for phrase in A3_ANCHORS}
    added = {row["term"].lower() for row in candidate["qualified_terms"] if "register_term" in row}
    added |= {row["term"].lower() for row in candidate["title_only_terms"]}
    assert not (forbidden & added)
    for name in theme_names(candidate):
        sub = theme_config(candidate, name)
        assert not (forbidden & _phrases(render_query(sub, include_exclusions=False)))


def theme_names(candidate: dict) -> list[str]:
    return [name for name, block in candidate["themes"].items() if block["terms"]]


def test_section_5_1_exclusions_are_present(candidate: dict) -> None:
    assert "perpendicular anisotropy" in candidate["exclusions"]
    assert "microplastic kinetics" in candidate["exclusions"]
    for request in plan(candidate, load_query_config(str(V31))).requests():
        if request.kind == "theme":
            assert '"perpendicular anisotropy"' in request.expression


def test_themes_block_matches_rows(candidate: dict) -> None:
    rows = {(r["theme"], r["term"]) for r in candidate["qualified_terms"] if "register_term" in r}
    listed = {
        (theme, name) for theme, block in candidate["themes"].items() for name in block["terms"]
    }
    assert rows == listed
    title_rows = {(r["theme"], r["term"]) for r in candidate["title_only_terms"]}
    title_listed = {
        (theme, name)
        for theme, block in candidate["themes"].items()
        for name in block["title_only"]
    }
    assert title_rows == title_listed


def test_title_only_terms_stay_out_of_title_and_abstract(candidate: dict, v31: dict) -> None:
    title_terms = {row["term"] for row in candidate["title_only_terms"]}
    assert title_terms
    for request in plan(candidate, v31).requests():
        if request.field == "title_and_abstract.search":
            for name in title_terms:
                assert f'"{name}"' not in request.expression


def test_base_positive_render_equals_v31(candidate: dict, v31: dict) -> None:
    candidate_base = render_query(base_config(candidate), include_exclusions=False)
    assert candidate_base == render_query(v31, include_exclusions=False)


def test_works_url_carries_count_shape(candidate: dict) -> None:
    url = works_url("(a)", field="title.search", config=candidate)
    assert url.startswith("https://api.openalex.org/works?")
    assert "per_page=1" in url
    assert "type%3A%21erratum" in url


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "count_query_v32_candidate", ROOT / "scripts" / "count_query_v32_candidate.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_dry_run_makes_no_call(capsys: pytest.CaptureFixture[str]) -> None:
    script = _load_script()
    assert script.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "no call made" in out
    assert "combined expression:" in out
    assert "theme:tyre_pellets_and_debris" in out


def test_offline_without_cache_fails_and_writes_nothing(tmp_path: Path) -> None:
    script = _load_script()
    output = tmp_path / "counts.json"
    code = script.main(
        ["--offline", "--cache-dir", str(tmp_path / "cache"), "--output", str(output)]
    )
    assert code == 1
    assert not output.exists()


def _evaluate(expression: str, present: set[str]) -> bool:
    """Tiny evaluator: a phrase is true when it is in ``present``; AND/OR/NOT per group."""

    tokens = re.findall(r'\(|\)|"[^"]*"|[^\s()"]+', expression)

    def run(pos: int) -> tuple[bool, int]:
        values: list[bool] = []
        ops: set[str] = set()
        while pos < len(tokens) and tokens[pos] != ")":
            token = tokens[pos]
            if token in {"AND", "OR", "NOT"}:
                ops.add(token)
                pos += 1
                continue
            if token == "(":
                value, pos = run(pos + 1)
                pos += 1  # the closing parenthesis
            else:
                value = token.strip('"') in present
                pos += 1
            values.append(value)
        if not ops:
            return values[0], pos
        (op,) = ops
        if op == "AND":
            return all(values), pos
        if op == "OR":
            return any(values), pos
        return values[0] and not values[1], pos

    result, end = run(1)  # tokens[0] is the outer "("
    assert end == len(tokens) - 1
    return result


def test_factored_rendering_is_logically_identical_to_per_term() -> None:
    from atlas.query import render_query
    from atlas.query_v32 import factored_expression

    config = {
        "core_terms": ["core"],
        "qualified_terms": [
            {"term": "A", "any_context": ["c1", "c2"]},
            {"term": "B", "any_context": ["c1", "c2"]},
            {"term": "C", "any_context": ["c3"]},
            {"term": "D", "any_context": ["c1", "c2"]},
        ],
        "exclusions": [],
    }
    per_term = render_query(config, include_exclusions=False)
    factored = factored_expression(config, include_exclusions=False)
    assert factored != per_term
    assert "((A OR B OR D) AND (c1 OR c2))" in factored
    assert is_fully_parenthesised(f"({factored})")
    names = ["core", "A", "B", "C", "D", "c1", "c2", "c3"]
    for mask in range(2 ** len(names)):
        present = {name for bit, name in enumerate(names) if mask >> bit & 1}
        assert _evaluate(f"({per_term})", present) == _evaluate(f"({factored})", present), present
