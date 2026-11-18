"""UX-32: CSS rules behind the remaining WCAG 2.5.8 and 2.4.7 rows from the UX-19 assisted pass."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _rule(css: str, selector: str) -> str:
    """Body of the rule whose selector is exactly `selector`."""
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, f"missing rule: {selector}"
    return match.group(1)


def _prop(body: str, name: str) -> str:
    match = re.search(rf"(?:^|;|\s){name}\s*:\s*([^;]+)", body)
    assert match, f"missing property {name} in: {body.strip()}"
    return match.group(1).strip()


def _px(value: str) -> float:
    match = re.fullmatch(r"([\d.]+)(px|rem)", value.strip())
    assert match, value
    return float(match.group(1)) * (16 if match.group(2) == "rem" else 1)


def test_sidebar_checkbox_is_not_a_target_and_menu_button_still_drives_it() -> None:
    body = _rule(_read("framework/src/design/shell.css"), "#observablehq-sidebar-toggle")
    assert _prop(body, "display") == "none"
    config = _read("framework/observablehq.config.js")
    assert 'closest("#atlas-menu-button")' in config
    assert "t.click()" in config


def test_tier_name_buttons_keep_a_24px_minimum_height() -> None:
    css = _read("framework/src/components/institutions.css")
    assert _px(_prop(_rule(css, "#institutions-root .tier-name"), "min-height")) >= 24


def test_marker_groups_show_a_focus_outline_on_keyboard_focus() -> None:
    for rel, root in (
        ("framework/src/components/institutions.css", "#institutions-root"),
        ("framework/src/components/monitoring.css", "#monitoring-root"),
    ):
        css = _read(rel)
        assert "outline: 3px solid" in _rule(css, f"{root} .monitoring-marker:focus-visible"), rel
        assert css.index(f"{root} .monitoring-marker:focus {{") < css.index(
            f"{root} .monitoring-marker:focus-visible {{"
        ), f"{rel}: focus-visible outline must come after the :focus reset"


def test_publication_sort_buttons_keep_a_24px_minimum_height() -> None:
    css = _read("framework/src/components/ev_table.css")
    assert _px(_prop(_rule(css, ".ev-table-root .ev-sort"), "min-height")) >= 24


def test_institution_leads_table_expert_links_are_padded_to_24px() -> None:
    css = _read("framework/src/components/institution.css")
    assert _px(_prop(_rule(css, "#institution-root th a"), "min-height")) >= 24


def test_funding_topn_range_slider_is_24px_tall() -> None:
    css = _read("framework/src/components/funding_viz.css")
    assert _px(_prop(_rule(css, '.fv-topn input[type="range"]'), "height")) >= 24


def test_expert_page_back_link_and_plastic_checkbox_are_24px() -> None:
    html = _read("site/california/expert.html")
    assert _px(_prop(_rule(html, ".crumbs a"), "min-height")) >= 24
    body = _rule(html, '.field input[type="checkbox"]')
    assert _px(_prop(body, "width")) >= 24
    assert _px(_prop(body, "height")) >= 24


def test_expert_page_metrics_list_holds_only_div_groups() -> None:
    html = _read("site/california/expert.html")
    pattern = r'\$\("metrics"\)\.innerHTML = tiles\.map\(\(t\) => `(.*?)`\)\.join'
    match = re.search(pattern, html, re.S)
    assert match, "metrics template not found"
    markup = match.group(1)
    assert markup.startswith('<div class="metric"><dt>')
    assert markup.endswith("</dd></div>")
    # The note lives inside the dd; a <small> sibling would be invalid directly under the div group.
    assert "</dd>${" not in markup


def test_tier_name_column_keeps_a_minimum_width() -> None:
    css = (ROOT / "framework" / "src" / "components" / "institutions.css").read_text(
        encoding="utf-8"
    )
    assert "grid-template-columns: minmax(11rem, 2.2fr)" in css
    assert "#institutions-root .tier-row > * { min-width: 0;" in css


def test_funding_award_title_links_keep_a_24px_target() -> None:
    css = (ROOT / "framework" / "src" / "components" / "funding.css").read_text(encoding="utf-8")
    assert (
        "#funding-root .grants-table tbody th a { display: inline-block; min-height: 1.5rem;" in css
    )
