"""VD-15: Policy, Related resources, About and Glossary open with the shared page header."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "framework" / "src"
ICONS = SRC / "components" / "shared" / "icons.js"
CONFIG = ROOT / "framework" / "observablehq.config.js"
SPRITE_IMPORT = 'import {injectIconSprite} from "../components/shared/icons.js";'
EYEBROW = re.compile(
    r'<p class="atlas-page-head__eyebrow"><svg class="icon" viewBox="0 0 24 24" '
    r'focusable="false" aria-hidden="true"><use href="#i-(\w+)"></use></svg> (\w+)</p>'
)

# page -> (nav group shown in the eyebrow, icon symbol for the route)
# PLAT-1: the context pages live in framework/src/california/ (keys are paths below src/).
PAGES = {
    "california/policy.md": ("Context", "scale"),
    "california/resources.md": ("Context", "link"),
    "california/about.md": ("Reference", "info"),
    "california/glossary.md": ("Reference", "book"),
}


def _read(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def _header(page: str) -> str:
    match = re.search(r'<header class="atlas-page-head">(.*?)</header>', page, re.S)
    assert match, 'page needs a static <header class="atlas-page-head">'
    return match.group(1)


def _nav_group(path: str) -> str:
    config = CONFIG.read_text(encoding="utf-8")
    for group, body in re.findall(r'\{name: "([^"]+)", pages: \[(.*?)\]\},', config, re.S):
        if f'path: "{path}"' in body:
            return group
    raise AssertionError(f"{path} is not listed in the nav config")


def _sentence_count(text: str) -> int:
    return len(re.findall(r"[.!?](?=\s|$)", text.strip()))


def test_each_context_page_opens_with_one_static_page_head() -> None:
    for name in PAGES:
        page = _read(name)
        header = _header(page)
        assert page.index('<header class="atlas-page-head">') < page.index("```js"), name
        assert page.count("<h1") == 1, f"{name} needs exactly one h1"
        assert "<h1>" in header, f"{name}: the h1 belongs inside the page head"
        assert not re.search(r"^# ", page, flags=re.MULTILINE), f"{name} keeps a markdown h1"
        lead = re.search(r'<p class="atlas-page-head__lead">(.*?)</p>', header, re.S)
        assert lead, f"{name} needs an atlas-page-head__lead"
        assert _sentence_count(lead.group(1)) <= 2, f"{name}: lead runs past two sentences"


def test_eyebrow_shows_the_nav_group_with_a_route_icon() -> None:
    icons = ICONS.read_text(encoding="utf-8")
    for name, (group, icon) in PAGES.items():
        match = EYEBROW.search(_header(_read(name)))
        assert match, f"{name} needs an eyebrow with an icon sprite reference"
        assert match.group(1) == icon, name
        assert match.group(2) == group, name
        assert _nav_group("/" + name.removesuffix(".md")) == group, name
        assert re.search(rf"(?m)^\s+{icon}: '", icons), f"#i-{icon} is not in the sprite"


def test_each_context_page_injects_the_icon_sprite_after_its_head() -> None:
    for name in PAGES:
        page = _read(name)
        assert SPRITE_IMPORT in page, name
        call = re.search(r"^injectIconSprite\(\);$", page, flags=re.MULTILINE)
        assert call, f"{name} must call injectIconSprite() in its script cell"
        assert call.start() > page.index('<header class="atlas-page-head">'), name


def test_do_not_regress_items_remain_visible() -> None:
    policy = _read("california/policy.md")
    assert "Reference information with outbound links" in _header(policy)
    assert 'id="policy-timeline"' in policy
    assert "Department of Toxic Substances Control" in policy

    resources = _read("california/resources.md")
    assert "does not copy, mirror or ingest their data" in _header(resources)
    assert "Descriptions are quoted as each steward states them." in resources

    about = _read("california/about.md")
    assert 'class="about-card about-limitations-card"' in about
    assert "no validated precision or recall is available yet" in about
    assert "10.5281/zenodo.24124016" in about
    assert "<h3>Corrections and source work</h3>" in about

    glossary = _read("california/glossary.md")
    ids = re.findall(r'<dt id="([^"]+)">', glossary)
    assert len(ids) == 34
    for term_id in ids:
        assert f'<a class="glossary-term-link" href="#{term_id}">' in glossary, term_id
