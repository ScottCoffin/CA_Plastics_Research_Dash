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


# The live baselines are all 0 since VD-17, so the mechanism tests use their own baseline.
MECHANISM_BASELINE = {"style.css": (1, frozenset({"#0b3d31"}))}


def test_token_stylesheet_is_excluded_from_the_literal_ratchet() -> None:
    count, problems = check_design_tokens.audit_stylesheets(
        {
            "style.css": ".facet { color: #0b3d31; }",
            "design/tokens.css": ":root { --atlas-ink: #abcdef; }",
        },
        baseline=MECHANISM_BASELINE,
        max_total=292,
    )

    assert count == 1
    assert problems == []


def test_checker_rejects_new_colours_outside_tokens() -> None:
    _, problems = check_design_tokens.audit_stylesheets(
        {"style.css": ".facet { color: #0b3d31; background: #abcdef; }"},
        baseline=MECHANISM_BASELINE,
        max_total=292,
    )

    assert any("new unapproved hex colours: #abcdef" in problem for problem in problems)


def test_checker_rejects_more_uses_than_the_file_baseline() -> None:
    _, problems = check_design_tokens.audit_stylesheets(
        {"style.css": ".facet { color: #0b3d31; border-color: #0b3d31; }"},
        baseline=MECHANISM_BASELINE,
        max_total=292,
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
        "--seq-100": "#e6e8ef",
        "--seq-200": "#c3c8db",
        "--seq-300": "#97a0c2",
        "--seq-400": "#6a77a6",
        "--seq-500": "#444f86",
        "--seq-600": "#2e3a6d",
        "--seq-700": "#1a2448",
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


def test_policy_timeline_reserves_successful_payload_height() -> None:
    policy = (ROOT / "framework" / "src" / "components" / "policy.css").read_text(encoding="utf-8")

    # Re-measured 2026-11-17 after the Policy text went full width.
    for value in ("56rem", "63rem", "75rem", "86rem", "110rem", "137rem"):
        assert f"min-height: {value};" in policy


def test_archivo_is_one_self_hosted_variable_face() -> None:
    tokens = (ROOT / "framework" / "src" / "design" / "tokens.css").read_text(encoding="utf-8")
    config = (ROOT / "framework" / "observablehq.config.js").read_text(encoding="utf-8")
    fonts = ROOT / "site" / "assets" / "fonts"

    # VD-25a: one variable face (wght 400-800, wdth trimmed to 75-100 for the 60 KB font budget)
    # replaces the two Barlow faces.
    assert config.count("@font-face {") == 1
    assert config.count('font-family: "Archivo";') == 1
    assert "font-weight: 400 800;" in config
    assert "font-stretch: 75% 100%;" in config
    assert "font-display: swap;" in config
    assert 'url("./assets/fonts/Archivo-Variable-latin.woff2") format("woff2")' in config
    assert "unicode-range: U+0000-00FF" in config
    assert "Barlow" not in config
    assert "@font-face" not in tokens
    assert "fonts.googleapis.com" not in f"{config}\n{tokens}"
    assert "fonts.gstatic.com" not in f"{config}\n{tokens}"
    assert (fonts / "Archivo-Variable-latin.woff2").is_file()
    assert (fonts / "OFL-Archivo.txt").is_file()
    # Lead decision (VD-25): axes trimmed to fit the 60 KB FONT_TRANSFER_LIMIT in
    # scripts/design_snapshots.py rather than raising the limit.
    assert (fonts / "Archivo-Variable-latin.woff2").stat().st_size <= 60 * 1024
    assert '--atlas-font-display: "Archivo"' in tokens
    assert "Palatino Linotype" not in tokens
    assert "Times New Roman" not in tokens
    assert 'rel="preload"' not in config
    assert 'rel="icon"' in config
    assert not (ROOT / "framework" / "src" / "assets" / "fonts").exists()


def test_type_scale_and_surface_tokens_are_applied() -> None:
    tokens = (ROOT / "framework" / "src" / "design" / "tokens.css").read_text(encoding="utf-8")
    style = (ROOT / "framework" / "src" / "style.css").read_text(encoding="utf-8")
    expected = {
        "--atlas-type-hero-size": "clamp(2rem, 1.3rem + 2.2vw, 2.9rem)",
        "--atlas-type-page-size": "clamp(2.16rem, 1.68rem + 1.68vw, 2.88rem)",
        "--atlas-type-section-size": "1.58rem",
        "--atlas-type-subsection-size": "1.3rem",
        "--atlas-type-eyebrow-size": "0.75rem",
        "--atlas-type-body-size": "1rem",
        "--atlas-type-small-size": "0.875rem",
        "--atlas-type-caption-size": "0.82rem",
        "--atlas-type-stat-size": "2rem",
        "--atlas-type-table-size": "0.9rem",
        "--atlas-type-id-size": "0.82rem",
    }

    for name, value in expected.items():
        assert f"{name}: {value};" in tokens
    assert "font: 400 var(--atlas-type-body-size) / 1.6 var(--atlas-font-body);" in tokens
    assert "font-size: var(--atlas-type-page-size);" in tokens
    assert "font-size: var(--atlas-type-hero-size);" in tokens
    assert "font-weight: 650;" in tokens
    assert "font-size: var(--atlas-type-eyebrow-size);" in tokens
    assert "line-height: 1.2;" in tokens
    assert "font-size: var(--atlas-type-caption-size);" in tokens
    assert "background-color: var(--atlas-page);" in tokens
    assert "--atlas-page: #ece7dc;" in tokens
    assert "--atlas-surface: #f6f3ec;" in tokens
    assert ".card { background-color: var(--atlas-surface); }" in style
    assert "background-color: var(--atlas-surface);" in style
    assert "--theme-background: var(--atlas-page);" in tokens
    assert "--theme-background-alt: var(--atlas-surface);" in tokens
    assert "#observablehq-main p { max-width: 70ch; }" in style
    assert "prefers-reduced-motion: reduce" in style
    assert "transition: none !important;" in style
    assert "animation: none !important;" in style
