"""VD-6a: Experts adopts the shared page, filters, and result components."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
PAGE = SRC / "california" / "experts.md"
COMPONENT = SRC / "components" / "experts.js"
CSS = SRC / "components" / "experts.css"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_expert_filter_ids_names_and_hash_interface_are_preserved() -> None:
    page = _read(PAGE)
    component = _read(COMPONENT)
    controls = {
        "expert-search": "search",
        "tag-filter": "tag",
        "institution-type-filter": "institution_type",
        "expert-sort": "sort",
        "institution-filter": "institution",
        "now-filter": "now",
        "early-filter": "early",
        "year-from": "year_from",
        "year-to": "year_to",
        "ca-basis-filter": "ca_basis",
        "oa-filter": "oa",
    }
    for control_id, name in controls.items():
        assert f'id="{control_id}"' in page
        assert f'name="{name}"' in page
    for value in (
        "plastic_citations",
        "plastic_works",
        "rising",
        "m_quotient",
        "h_index",
        "cited_by",
        "ca_works",
        "ca",
        "outside",
        "unknown",
        "ca-led",
        "ca-sampled",
        "both",
        "ca-affiliated",
        "none",
        "oa",
        "closed",
    ):
        assert f'value="{value}"' in page
    assert 'min="1900" max="2100" placeholder="Any"' in page
    assert 'type="search" autocomplete="off" placeholder="e.g. Rochman, UC Davis"' in page
    filter_ids = [
        "expert-search",
        "institution-type-filter",
        "institution-filter",
        "tag-filter",
        "year-from",
        "year-to",
        "ca-basis-filter",
        "oa-filter",
        "now-filter",
        "expert-sort",
        "early-filter",
    ]
    declaration = "FILTER_IDS = [" + ", ".join(f'"{item}"' for item in filter_ids) + "]"
    assert declaration in component
    assert "parseExpertHash(window.location.hash)" in component
    assert "formatExpertHash(state.filters)" in component
    assert 'id="expert-state"' in page and 'id="expert-list"' in page


def test_primary_and_more_filter_membership_matches_the_design() -> None:
    page = _read(PAGE)
    more_start = page.index('<details id="expert-more-filters"')
    more_end = page.index("</details>", more_start)
    primary = page[:more_start]
    more = page[more_start:more_end]
    for control_id in ("expert-search", "tag-filter", "institution-type-filter", "expert-sort"):
        assert control_id in primary
        assert control_id not in more
    for control_id in (
        "institution-filter",
        "now-filter",
        "early-filter",
        "year-from",
        "year-to",
        "ca-basis-filter",
        "oa-filter",
    ):
        assert control_id in more
        assert control_id not in primary
    assert "More filters <span>(7)</span>" in more
    assert 'class="atlas-filters__more"' in page
    assert "HIDDEN_FILTERS" in _read(COMPONENT)
    assert '$("expert-more-filters").open = true' in _read(COMPONENT)


def test_active_filters_have_labelled_removal_controls() -> None:
    page = _read(PAGE)
    component = _read(COMPONENT)
    css = _read(CSS)
    assert 'id="expert-active-filters" class="atlas-active-filters"' in page
    assert 'class="atlas-filter-chip"' in component
    assert 'aria-label="Remove ${escapeHtml(label)} filter"' in component
    assert 'addEventListener("click", (event) => {' in component
    assert "removeActiveFilter(button.dataset.filter)" in component
    assert (
        "#experts-root .atlas-filter-chip button { min-width: 1.5rem; min-height: 1.5rem; }" in css
    )


def test_shared_page_results_actions_and_term_disclosure_are_used() -> None:
    page = _read(PAGE)
    assert 'class="atlas-page-head experts-page-head"' in page
    assert '${icon("person")} Explore' in page
    assert page.count("<h1>") == 1
    assert 'class="atlas-result-line"' in page
    assert 'class="data-note volume-caption"' in page
    assert "Counts show volume, not strength" in page
    assert 'id="export-csv" class="atlas-btn atlas-btn--primary"' in page
    assert 'id="reset-filters" class="atlas-btn atlas-btn--secondary"' in page
    assert 'class="atlas-disclosure term-help"' in page


def test_rows_are_compact_and_drawer_uses_shared_components() -> None:
    page = _read(PAGE)
    component = _read(COMPONENT)
    css = _read(CSS)
    assert "window.innerWidth >= 900 ? 124 : 224" in component
    assert 'card.classList.add("atlas-card")' in component
    assert "margin-bottom: 0.15rem" in css
    assert "#experts-root .atlas-filters { margin: 0.25rem 0 0.1rem; }" in css
    assert '#experts-root .atlas-field label[for="now-filter"] a' in css
    assert "#experts-root .expert-metrics a" in css
    assert css.count("min-height: 24px;") >= 2
    assert "font: 600 1.05rem / 1.1 var(--atlas-font-display)" in css
    assert "color: var(--atlas-muted); font-size: 0.78rem" in css
    assert 'class="atlas-page-head drawer-header"' in page
    assert 'id="drawer-close" class="atlas-btn atlas-btn--secondary"' in page
    assert 'id="drawer-issue-link" class="atlas-btn atlas-btn--ghost"' in page
    assert 'className = "atlas-table-wrap"' in component
    assert 'table.className = "atlas-table drawer-stats"' in component
    assert 'classList.add("atlas-btn", "atlas-btn--primary")' in component
