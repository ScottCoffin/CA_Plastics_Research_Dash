from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_CHECK = ROOT / "tests" / "framework_evidence_runtime.mjs"
FW_SRC = ROOT / "framework" / "src"


def test_framework_evidence_runtime_helpers() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for tests/framework_evidence_runtime.mjs; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    # Shared helpers are gitignored copies of site/assets; create them as `npm run build` does.
    sync = ROOT / "framework" / "scripts" / "sync_shared.mjs"
    subprocess.run([node, str(sync)], cwd=ROOT, check=True, capture_output=True)
    subprocess.run([node, str(RUNTIME_CHECK)], cwd=ROOT, check=True)


def test_works_drawer_is_gone():
    page = (FW_SRC / "evidence.md").read_text(encoding="utf-8")
    source = (FW_SRC / "components" / "evidence.js").read_text(encoding="utf-8")
    css = (FW_SRC / "components" / "evidence.css").read_text(encoding="utf-8")
    for text in (page, source, css):
        assert "evidence-drawer" not in text
        assert "evidence-show-works" not in text
        assert "openWorksDrawer" not in text
        assert "works_index.json" not in text
        assert "loadWorks" not in text
        assert "ev-drawer" not in text
    assert "<dialog" not in page


def test_page_lists_plastic_related_works_only():
    page = (FW_SRC / "evidence.md").read_text(encoding="utf-8")
    source = (FW_SRC / "components" / "evidence.js").read_text(encoding="utf-8")
    model = (FW_SRC / "components" / "evidence_model.js").read_text(encoding="utf-8")
    assert "The page lists plastic-related works only." in page
    assert "plastic relevance" not in page
    assert '"Plastic-related"' not in source
    assert "PLASTIC_ONLY" in model and "sel = {plastic: [...PLASTIC_ONLY.plastic]}" in model
    assert "plastic" not in model.split("FACET_KEYS = ")[1].split("\n")[0]
    assert "row.plastic_related === true" in source


def test_heatmap_cells_narrow_the_publication_table():
    page = (FW_SRC / "evidence.md").read_text(encoding="utf-8")
    source = (FW_SRC / "components" / "evidence.js").read_text(encoding="utf-8")
    table = (FW_SRC / "components" / "ev_table.js").read_text(encoding="utf-8")
    assert "selecting heatmap cells narrows the publication table" in page.lower()
    assert "app.heatIds.has(id)" in source
    assert "Select heatmap cells or topic names to narrow this table." in table
    assert '<select data-role="tag"' not in table


def test_selection_banner_sits_above_publication_table() -> None:
    page = (FW_SRC / "evidence.md").read_text(encoding="utf-8")
    banner = (
        '<div id="ev-table-selection" class="ev-table-selection ev-table-root" '
        'role="status" aria-live="polite" hidden></div>'
    )
    assert banner in page
    # The banner comes directly before the table container, and the table heading can take focus.
    assert f'<div class="atlas-chart__body">{banner}<div id="ev-table">' in page
    assert '<h2 id="ev-table-heading" tabindex="-1">' in page
    assert '<h2 id="ev-heatmap-heading" tabindex="-1">' in page


def test_headline_and_banner_name_the_heatmap_selection() -> None:
    source = (FW_SRC / "components" / "evidence.js").read_text(encoding="utf-8")
    assert "distinct works match" in source
    assert "in the heatmap selection (listed under Publications)" in source
    assert "Showing " in source and "from your heatmap selection" in source
    assert "Clear heatmap selection" in source
    assert "heatmap.clear()" in source or "heatmap.clear();" in source
    assert "labelSummary" in source


def test_public_copy_has_no_internal_ids() -> None:
    for name in ("evidence.md",):
        text = (FW_SRC / name).read_text(encoding="utf-8")
        assert not re.search(r"UX-\d+|EM-\d+|S\d+\.\d+|TODO", text), name
    for name in ("evidence.js", "components/ev_heatmap.js"):
        text = (FW_SRC / "components" / name.split("/")[-1]).read_text(encoding="utf-8")
        visible = re.findall(r"`[^`]*`|\"[^\"]*\"", text)
        assert not any(re.search(r"UX-\d+|EM-\d+|S\d+\.\d+|TODO", s) for s in visible), name


def test_journal_filter_is_wired_into_the_shared_state() -> None:
    model = (FW_SRC / "components" / "evidence_model.js").read_text(encoding="utf-8")
    source = (FW_SRC / "components" / "evidence.js").read_text(encoding="utf-8")
    facet_keys = (
        'FACET_KEYS = ["topic", "ca_led", "sector", "type", "oa", "institution", "journal"]'
    )
    assert facet_keys in model
    assert 'export const JOURNAL_FACET = "journal";' in model
    # The journal bit-set rides on the AT-4 extra bits: counts, heatmap, trend and table agree.
    assert "journalBits(app.index.workIds, app.journalOf, labels, app.index.W)" in source
    assert "andBits(text, journalFilterBits())" in source
    assert "const journals = impossible ? new Map() : tallyJournals(" in source
    assert 'search.dataset.role = "journal-search";' in source
    # Journal names are not bundle labels, so selectionFor keeps them out of the engine's selection.
    assert "if (key !== JOURNAL_FACET) sel[key] = labels;" in model


def test_journal_metrics_load_is_optional_and_only_the_evidence_table_shows_the_column() -> None:
    source = (FW_SRC / "components" / "evidence.js").read_text(encoding="utf-8")
    table = (FW_SRC / "components" / "ev_table.js").read_text(encoding="utf-8")
    institution = (FW_SRC / "components" / "institution.js").read_text(encoding="utf-8")
    assert 'loadJson("journal_metrics.json", {optional: true})' in source
    assert "attachJournalMetrics(plasticWorks, journals)" in source
    assert "metricsColumn: true" in source
    assert "metricsColumn" not in institution
    assert (
        'const METRIC_OPTION = ["two_yr_mean_citedness", "2-yr mean citedness (OpenAlex)"];'
        in table
    )
    assert 'data-sort="${METRIC_OPTION[0]}"' in table
    assert "2-yr mean citedness (OpenAlex)" in table
    assert 'href="./glossary#two-year-mean-citedness"' in table


def _read_fw(*parts: str) -> str:
    return (FW_SRC.joinpath(*parts)).read_text(encoding="utf-8")


def test_impact_factor_is_always_qualified_as_the_open_analogue() -> None:
    texts = {
        "evidence.md": _read_fw("evidence.md"),
        "evidence.js": _read_fw("components", "evidence.js"),
        "ev_table.js": _read_fw("components", "ev_table.js"),
        "ev_table_model.js": _read_fw("components", "ev_table_model.js"),
        "glossary.md": _read_fw("glossary.md"),
    }
    for name, text in texts.items():
        # The glossary names Clarivate's proprietary metric only to say the Atlas does not use it.
        text = text.replace("Clarivate's Journal Impact Factor", "")
        for match in re.finditer(r"impact factor", text, flags=re.IGNORECASE):
            before = text[max(0, match.start() - 40) : match.start()]
            assert "open analogue of the " in before, f"{name}: unqualified 'impact factor'"


def test_recent_box_text_fills_the_box() -> None:
    css = (FW_SRC / "components" / "evidence.css").read_text(encoding="utf-8")
    assert "#evidence-root .ev-recent :is(h2, p, ul, ol, li) { max-width: none; }" in css
