from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_design_tokens", ROOT / "scripts" / "check_design_tokens.py"
)
assert SPEC is not None and SPEC.loader is not None
check_design_tokens = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_design_tokens)


def test_token_stylesheet_is_excluded_from_the_literal_ratchet() -> None:
    count, problems = check_design_tokens.audit_stylesheets(
        {
            "style.css": ".facet { color: #0b3d31; }",
            "design/tokens.css": ":root { --atlas-ink: #abcdef; }",
        }
    )

    assert count == 1
    assert problems == []


def test_checker_rejects_new_colours_outside_tokens() -> None:
    _, problems = check_design_tokens.audit_stylesheets(
        {"style.css": ".facet { color: #0b3d31; background: #abcdef; }"}
    )

    assert any("new unapproved hex colours: #abcdef" in problem for problem in problems)


def test_checker_rejects_more_uses_than_the_file_baseline() -> None:
    _, problems = check_design_tokens.audit_stylesheets(
        {"style.css": ".facet { color: #0b3d31; border-color: #0b3d31; }"}
    )

    assert any("2 hex uses exceeds baseline 1" in problem for problem in problems)


def test_checker_rejects_hex_colours_in_new_stylesheets() -> None:
    _, problems = check_design_tokens.audit_stylesheets(
        {"components/new.css": ".new { color: #123456; }"}
    )

    assert any("has no VD-1 baseline" in problem for problem in problems)


def test_checker_enforces_the_global_ceiling() -> None:
    baseline = {"sample.css": (2, frozenset({"#000", "#fff"}))}
    _, problems = check_design_tokens.audit_stylesheets(
        {"sample.css": ".a { color: #000; background: #fff; }"},
        baseline=baseline,
        max_total=1,
    )

    assert any("2 Framework stylesheet hex uses exceeds limit 1" in problem for problem in problems)


def test_tokens_are_imported_after_theme_and_running_links_stay_underlined() -> None:
    style = (ROOT / "framework" / "src" / "style.css").read_text(encoding="utf-8")
    tokens = (ROOT / "framework" / "src" / "design" / "tokens.css").read_text(encoding="utf-8")

    assert style.index('url("observablehq:theme-air.css")') < style.index(
        'url("./design/tokens.css")'
    )
    assert "#observablehq-main p a" in style
    assert "text-decoration: underline;" in style
    assert "--theme-foreground-focus: var(--atlas-brand);" in tokens
    assert "--theme-foreground-muted: var(--atlas-muted);" in tokens


def test_required_sequential_ramp_is_centralized_in_tokens() -> None:
    tokens = (ROOT / "framework" / "src" / "design" / "tokens.css").read_text(encoding="utf-8")
    expected = {
        "--seq-100": "#e3f2ed",
        "--seq-200": "#b9e0d3",
        "--seq-300": "#86c7b2",
        "--seq-400": "#4fa68c",
        "--seq-500": "#23876d",
        "--seq-600": "#0e6e56",
        "--seq-700": "#043e32",
    }

    for name, value in expected.items():
        assert f"{name}: {value};" in tokens


def test_async_foundation_surfaces_reserve_viewport_space() -> None:
    style = (ROOT / "framework" / "src" / "style.css").read_text(encoding="utf-8")
    institution = (ROOT / "framework" / "src" / "components" / "institution.css").read_text(
        encoding="utf-8"
    )

    assert ".atlas-stats { min-height: 10rem; }" in style
    assert ".atlas-stats { min-height: 31rem; }" in style
    assert "min-height: calc(100vh - 6rem);" in institution
