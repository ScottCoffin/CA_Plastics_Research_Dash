"""Checks for the public ambassadors page (AMB-1 slice 1).

Helpers run in node (tests/framework_ambassadors_runtime.mjs). The static parts read the sources
as text. No network: the page loads nothing from a CDN, and the region index matches its build.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
COMPONENTS = SRC / "components"
PAGE = SRC / "ambassadors.md"
TERMS_PAGE = SRC / "ambassador_terms.md"
TERMS_DOC = ROOT / "docs" / "AMBASSADOR_TERMS.md"
BUILD = ROOT / "scripts" / "build_ambassador_regions.py"
RUNTIME_CHECK = ROOT / "tests" / "framework_ambassadors_runtime.mjs"
REGIONS_JSON = ROOT / "site" / "data" / "global" / "ambassador_regions.json"
ASSETS = [
    PAGE,
    TERMS_PAGE,
    COMPONENTS / "ambassadors.js",
    COMPONENTS / "ambassadors.css",
    COMPONENTS / "ambassador_badge.js",
    COMPONENTS / "world_map.js",
]
CDN = re.compile(r"https?://(?:cdn\.|unpkg\.|[\w.-]*jsdelivr|d3js\.org|cdnjs\.)", re.IGNORECASE)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normal(text: str) -> str:
    """Markdown text as plain words: bold markers removed, whitespace collapsed."""
    return re.sub(r"\s+", " ", text.replace("**", "")).strip()


def test_ambassador_helpers_runtime() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for tests/framework_ambassadors_runtime.mjs")
    result = subprocess.run(
        [node, str(RUNTIME_CHECK)], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_no_cdn_script_or_stylesheet_loads() -> None:
    for path in ASSETS:
        text = _text(path)
        assert not CDN.search(text), f"{path.name} loads from a CDN"
        assert "<script src" not in text.lower(), path.name


def test_sign_up_is_a_live_orcid_link_not_a_disabled_button() -> None:
    # Slice 2a: the hero and the how-it-works section link to the Worker's ORCID start route.
    page = _text(PAGE)
    assert "Sign-in opens soon" not in page
    assert not re.findall(r"<button[^>]*>[^<]*Sign[- ]in[^<]*</button>", page)
    links = re.findall(r"<a [^>]*>[^<]*Sign up with ORCID</a>", page)
    assert len(links) == 2, links
    assert "https://api.plastiverse.live/orcid/start" in page


def test_region_index_is_current_and_lists_only_real_regions() -> None:
    result = subprocess.run(
        [sys.executable, str(BUILD), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    data = json.loads(REGIONS_JSON.read_text(encoding="utf-8"))
    assert data["schema"] == "amb-regions-v1"
    assert [r["slug"] for r in data["regions"]] == ["belgium", "california", "norway"]
    assert all(r["status"] == "open_to_ambassadors" for r in data["regions"])


def test_terms_page_keeps_every_sentence_of_the_approved_terms() -> None:
    doc = _text(TERMS_DOC).split("\n")
    body = doc[1:]  # the title line
    status = next(i for i, line in enumerate(body) if line.startswith("Status:"))
    end = next(i for i in range(status, len(body)) if body[i].strip() == "")
    approved = _normal("\n".join(body[end + 1 :]))
    page = _normal(_text(TERMS_PAGE))
    sentences = [s for s in re.split(r"(?<=[.])\s+(?=[A-Z0-9])", approved) if len(s) > 20]
    assert len(sentences) >= 15
    missing = [s for s in sentences if s not in page]
    assert not missing, missing[:3]


def test_terms_page_is_public_and_registered() -> None:
    page = _text(TERMS_PAGE)
    assert "# Ambassador contribution terms" in page
    assert "H48" not in page, "the approval reference is internal"
    check = _text(ROOT / "scripts" / "check_at5.py")
    assert '"ambassador_terms.md"' in check and '"ambassadors.md"' in check
    postbuild = _text(ROOT / "framework" / "scripts" / "postbuild.mjs")
    assert "  ambassadors: " in postbuild and "  ambassador_terms: " in postbuild


def test_shared_map_module_is_used_by_explore_and_the_ambassadors_page() -> None:
    explore = _text(COMPONENTS / "explore.js")
    ambassadors = _text(COMPONENTS / "ambassadors.js")
    assert 'from "./world_map.js"' in explore
    assert 'from "./world_map.js"' in ambassadors
    assert "attachMapGestures(" in explore and "attachMapGestures(" in ambassadors
    # The projection and the gesture rules live once, in world_map.js.
    assert "function neRad(" not in explore
    assert "function neRad(" in _text(COMPONENTS / "world_map.js")


def test_public_text_avoids_expert_and_internal_vocabulary() -> None:
    for path in (PAGE, TERMS_PAGE):
        text = _text(path)
        visible = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        assert not re.search(r"\bexperts?\b", visible, re.IGNORECASE), path.name
        assert not re.search(r"\bEM-\d+\b|\bA[123]-|\bH\d{2}\b", visible), path.name


def test_badge_is_one_component_with_the_required_accessible_name() -> None:
    badge = _text(COMPONENTS / "ambassador_badge.js")
    assert "Plastiverse Live ambassador for ${name}" in badge
    assert 'role="img"' in badge
    assert "Ambassador" in badge and "·" in badge
    # The landing explainer and any [data-amb] element share the same component.
    assert "mountBadges" in _text(COMPONENTS / "ambassadors.js")
    assert 'data-amb="Norway"' in _text(PAGE)


def test_eligibility_checker_puts_place_and_institution_on_one_row() -> None:
    css = _text(COMPONENTS / "ambassadors.css")
    assert re.search(
        r"@media \(min-width: 700px\)\s*\{\s*\.am \.check-row \{ grid-template-columns", css
    )
    assert 'id="amb-check-place"' in _text(PAGE) and 'id="amb-check-q"' in _text(PAGE)


def test_search_states_the_fifteen_thousand_threshold_plainly() -> None:
    page = _text(PAGE)
    assert "15,000 people or more" in page
    assert "state, province or county" in page


def test_signed_in_mode_switch_hides_the_recruiting_sections() -> None:
    """Owner 2026-11-26: a signed-in ambassador sees only the dashboard.

    The recruiting sections stay in the markup and data-mode hides them (checking and dashboard), so
    signed-out visitors keep the page as it was.
    """
    page = _text(PAGE)
    assert '<div class="am" data-mode="checking">' in page
    assert page.count('class="sec recruit"') + page.count('class="hero recruit"') == 5
    for heading in (
        "Become a local ambassador",
        "Regions on the world map",
        "What ambassadors do",
        "How it works",
    ):
        assert heading in page
    css = _text(COMPONENTS / "ambassadors.css")
    assert '.am[data-mode="checking"] .recruit, .am[data-mode="dashboard"] .recruit' in css
    signup = _text(COMPONENTS / "ambassador_signup.js")
    assert "export function pageMode(me)" in signup
    assert "pageMode(me)" in signup and "setPageMode(mode)" in signup
    assert "only-checking" in page and "ws-skel" in page
