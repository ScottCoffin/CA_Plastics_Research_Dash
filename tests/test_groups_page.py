"""Checks for the CG-13/CG-10 community groups page (/groups): wording, links, tree and styling.

Runs focused groups and tree runtime helpers (Node) and reads the page source statically.
No browser and no build: the rendered page is checked by the lead's browser pass.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "framework" / "src" / "groups.md"
MODULE = ROOT / "framework" / "src" / "components" / "groups.js"
STYLES = ROOT / "framework" / "src" / "components" / "groups.css"
RUNTIME = ROOT / "tests" / "framework_groups_runtime.mjs"
TREE_RUNTIME = ROOT / "tests" / "framework_groups_tree_runtime.mjs"
NETWORK_RUNTIME = ROOT / "tests" / "framework_groups_network_runtime.mjs"
NETWORK_MODEL = ROOT / "framework" / "src" / "components" / "groups_network_model.js"
NETWORK = ROOT / "framework" / "src" / "components" / "groups_network.js"
SCOPE_MAP = ROOT / "framework" / "src" / "components" / "groups_scope_map.js"
SCOPE_MAP_STYLES = ROOT / "framework" / "src" / "components" / "groups_scope_map.css"
CONTACT = "theplastiverse@gmail.com"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _visible_source(path: Path) -> str:
    """Source without comments (HTML comments in the page, // and /* */ in the modules)."""
    text = _read(path)
    if path.suffix == ".md":
        return HTML_COMMENT.sub("", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("//"))


def test_node_runtime_helpers_pass() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH (source ~/.bashrc puts it there)")
    result = subprocess.run(
        [node, str(RUNTIME)], cwd=ROOT, capture_output=True, text=True, timeout=120, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "all assertions passed" in result.stdout
    tree_result = subprocess.run(
        [node, str(TREE_RUNTIME)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert tree_result.returncode == 0, tree_result.stderr or tree_result.stdout
    assert "groups tree runtime assertions passed" in tree_result.stdout


def test_page_title_and_global_theme() -> None:
    text = _read(PAGE)
    assert text.startswith("---\n")
    assert "title: Community groups · Plastiverse Live" in text
    assert 'href="./components/groups.css"' in text
    assert 'import {mountGroupsScopePanels} from "./components/groups_scope_panels.js"' in text
    assert 'aria-current="page">Community groups' in text
    assert "PLASTIVERSE <b>LIVE</b>" in text
    assert '<g><line x1="20.60"' in text
    assert '<details class="gm-mobile-menu">' in text
    assert 'src="./assets/landing/logo_564.webp"' in text
    assert '<main id="main"' not in text


def test_interactive_scope_map_precedes_group_views() -> None:
    page = _visible_source(PAGE)
    assert 'id="groups-scope-map"' in page
    assert page.index('id="groups-scope-map"') < page.index('id="groups-scope-panels"')
    assert 'href="./components/groups_scope_map.css"' in page
    assert 'import {mountGroupsScopeMap} from "./components/groups_scope_map.js"' in page
    module = _read(SCOPE_MAP)
    assert "attachMapGestures(map" in module
    assert 'params.set("scope", selected.key)' in module
    assert 'currentHash().get("scope")' in module
    assert "onScope: updateForScope" in page


def test_map_has_count_legend_and_real_regional_atlas_links() -> None:
    module = _read(SCOPE_MAP)
    styles = _read(SCOPE_MAP_STYLES)
    assert 'aria-label="Groups listed by country"' in module
    assert "Groups listed by country</span>" in module
    assert 'rosterCount === 0 ? "zero"' in module and 'rosterCount < 25 ? "some" : "many"' in module
    assert ".gm-country--zero { fill: var(--pv-wash); }" in styles
    assert ".gm-country--many { fill: var(--pv-slate); }" in styles
    assert 'import {siteRoot} from "./atlas.js"' in module
    assert "new URL(`${prefix}institutions`, base).href" in module
    assert "new URL(`${prefix}evidence`, base).href" in module
    for region in ("california", "norway", "belgium"):
        assert (ROOT / "framework" / "src" / region / "index.md").is_file()
        assert (ROOT / "framework" / "src" / region / "institutions.md").is_file()
        assert (ROOT / "framework" / "src" / region / "evidence.md").is_file()


def test_lede_states_who_is_listed_and_what_not_yet_tagged_means() -> None:
    text = _visible_source(PAGE)
    assert "Break Free From Plastic" in text
    assert "volunteer ambassadors" in text.lower()
    assert "Only organisations are listed" in text
    assert "**Not yet tagged**" not in text
    assert "<b>Not yet tagged</b> means the group has not been tagged yet." in text
    assert "It never means the group has no plastics work." in text
    assert "The Atlas is independent of Break Free From Plastic." in text


METHODS_OPEN = (
    '<section class="gv-panel gv-root" aria-labelledby="gv-methods-title" id="gv-methods">'
)


def _methods_section() -> str:
    text = _visible_source(PAGE)
    start = text.index(METHODS_OPEN)
    return text[start : text.index("</section>", start)]


def test_methods_section_has_four_topics() -> None:
    section = _methods_section()
    assert '<h2 id="gv-methods-title">How this list is made</h2>' in section
    for topic in ("Source", "Organisations only", "Tags", "Corrections and removal"):
        assert f"<h3>{topic}</h3>" in section, topic
    attribution = (
        "This list of organisations was informed by Break Free From Plastic (BFFP), "
        "with permission."
    )
    assert attribution in section
    assert "within 14 days" in section
    for badge in ("Volunteer-tagged", "Reviewed", "Confirmed by group"):
        assert badge in section, badge


def test_methods_section_never_counts_exclusions() -> None:
    section = _methods_section()
    assert not re.search(r"\d\D{0,40}\b(excluded|left out)\b", section, re.IGNORECASE)
    assert not re.search(r"\b(excluded|left out)\b\D{0,40}\d", section, re.IGNORECASE)
    assert not re.search(r"\bexclusions?\b", section, re.IGNORECASE)


def test_independence_sentence_appears_once() -> None:
    sentence = "The Atlas is independent of Break Free From Plastic."
    assert _visible_source(PAGE).count(sentence) == 1


def test_methods_contact_matches_the_card_contact() -> None:
    assert f"<b>{CONTACT}</b>" in _methods_section()
    assert f'CONTACT_EMAIL = "{CONTACT}"' in _read(MODULE)


def test_card_correction_link_and_methods_link() -> None:
    module = _read(MODULE)
    assert 'rel="external"' in module
    assert "Suggest a correction or ask for removal" in module
    assert 'href="#gv-methods" data-close data-methods' in module
    assert 'document.getElementById("gv-methods")' in module


def test_provenance_wording_is_present() -> None:
    assert "Listed as a BFFP member as of " in _read(MODULE)


def test_no_excluded_count_wording() -> None:
    for path in (PAGE, MODULE):
        text = _visible_source(path).lower()
        assert not re.search(r"\bexcluded\b|\bexclusions?\b|\brejected\b", text), path.name


def test_no_score_sorting_and_only_name_or_country_sort_keys() -> None:
    for path in (PAGE, MODULE):
        assert "score" not in _visible_source(path).lower(), path.name
    module = _read(MODULE)
    assert re.search(r'SORT_KEYS = \["name", "country"\]', module)


def test_help_links_use_ambassadors_without_trailing_slash() -> None:
    for path in (PAGE, MODULE):
        text = _visible_source(path)
        assert "./ambassadors/" not in text, path.name
    assert 'href="./ambassadors"' in _read(MODULE)


def test_external_links_are_noopener_nofollow() -> None:
    module = _read(MODULE)
    assert module.count('rel="noopener nofollow"') >= 2


def test_only_the_public_contact_address_appears() -> None:
    found: set[str] = set()
    for path in (PAGE, MODULE):
        found |= set(EMAIL.findall(_visible_source(path)))
    assert found == {CONTACT}


def test_no_internal_vocabulary_in_visible_text() -> None:
    for path in (PAGE, MODULE):
        text = _visible_source(path)
        for term in ("cg-v2", "CG-13", "org_status"):
            assert term not in text, f"{term} in {path.name}"


def test_card_and_standing_note_wording() -> None:
    module = _read(MODULE)
    assert (
        "Tags were entered by volunteers from public sources and have not been verified "
        "by the group unless marked Confirmed." in module
    )
    assert "Suggest a correction" in module
    assert "data-close" in module and "showModal" in module


def test_status_labels_are_the_public_words() -> None:
    module = _read(MODULE)
    for label in (
        "Not yet tagged",
        "Volunteer-tagged",
        "Reviewed",
        "Confirmed by group",
    ):
        assert f'label: "{label}"' in module


def test_state_is_kept_in_the_url_hash() -> None:
    module = _read(MODULE)
    assert "history.replaceState" in module
    assert '"hashchange"' in module


def test_stylesheet_is_scoped_44px_and_token_only() -> None:
    css = re.sub(r"/\*.*?\*/", "", _read(STYLES), flags=re.DOTALL)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css), "no hex colours; use the --pv-* tokens"
    for match in re.finditer(r"([^{}]+)\{[^{}]*\}", css):
        selector = match.group(1).strip()
        for part in selector.split(","):
            assert part.strip().startswith(".gv"), f"unscoped selector: {part.strip()!r}"
    assert "min-height: 44px" in css
    assert ":focus-visible" in css


def test_page_source_has_no_inline_scripts_or_handlers() -> None:
    text = _read(PAGE)
    assert not re.search(r"\son[a-z]+=", text)
    assert "javascript:" not in text.lower()


def test_page_passes_the_group_list_not_the_file_object() -> None:
    page = (ROOT / "framework" / "src" / "groups.md").read_text(encoding="utf-8")
    # groups.json wraps the records in {"groups": [...]}; the object alone gave an empty table.
    # CG-12: the payload is fetched once and shared, so every consumer must unwrap the list.
    assert page.count('loadPayload("groups/groups.json"') == 1
    assert "const groupsAll = groupsPayload?.groups ?? []" in page
    assert (
        "const groups = ids ? groupsAll.filter((group) => ids.has(group.group_id)) : groupsAll"
        in page
    )


def test_table_wrapper_contains_hidden_labels() -> None:
    css = (ROOT / "framework" / "src" / "components" / "groups.css").read_text(encoding="utf-8")
    # Without position: relative the hidden labels widened the page at 390 px.
    assert ".gv .gv-table-wrap { position: relative; overflow-x: auto;" in css


def test_network_runtime_helpers_pass() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH (source ~/.bashrc puts it there)")
    result = subprocess.run(
        [node, str(NETWORK_RUNTIME)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "groups network runtime assertions passed" in result.stdout


def test_network_section_wording_and_hash_keys() -> None:
    page = _visible_source(PAGE)
    panels = _read(ROOT / "framework" / "src" / "components" / "groups_scope_panels.js")
    assert '<h2 id="gv-scope-network-title">Network</h2>' in panels
    assert 'id="groups-scope-network"' in panels
    assert "This view shows tagged groups only." in panels
    assert "graph: graphPayload" in page
    assert "scope, groups," in page
    module = _read(NETWORK)
    model = _read(NETWORK_MODEL)
    assert "No groups are tagged yet, so there is no network to draw." in module
    assert 'href="./ambassadors"' in module
    assert 'href="./ambassadors/"' not in module
    assert "Adjacent organisations (no stated plastics focus)" in module
    assert "co-occurrence of tags, not partnerships" in module
    assert "Size shows the number of tags, not importance." in module
    assert 'rel="noopener nofollow"' in module
    assert "<q>" in module
    assert "aria-hidden" in module
    assert "groups_graph.json" in _read(PAGE)
    # Every network hash key starts with "net", so groups.js and tree keys are untouched.
    keys = set(re.findall(r'"(net[a-z_]*)"', model))
    assert keys and all(key.startswith("net") for key in keys)
    assert not re.search(r'params\.(set|get|delete)\("(q|group|tree|page|status)"', model)


def test_network_visible_text_has_no_internal_ids() -> None:
    for path in (PAGE, NETWORK, NETWORK_MODEL):
        text = _visible_source(path)
        for term in ("CG-11", "CG-13", "V-NET", "T-GRAPH", "A4-", "BFFP-", "excluded"):
            assert term not in text, f"{term} in {path.name}"
    assert not re.search(r"scores?", _visible_source(NETWORK).lower())


def test_network_module_has_no_npm_import_in_model() -> None:
    model = _read(NETWORK_MODEL)
    assert "npm:" not in model
    assert "document" not in _visible_source(NETWORK_MODEL)
    assert 'import Graph from "npm:graphology@0.26.0";' in _read(NETWORK)
    assert 'import Sigma from "npm:sigma@3.0.3";' in _read(NETWORK)
