"""BQ-R2: glossary entries and the Further reading list (A3 section 9).

Offline checks on committed source files only. Each new term has one anchor, a citation line,
a link where a URL is given, at most two sentences, and no "expert" wording. DOIs must match the
Atlas source registers, and the reading list links works without copying their text.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLOSSARY = ROOT / "framework" / "src" / "california" / "glossary.md"
RESOURCES = ROOT / "framework" / "src" / "california" / "resources.md"
A3_SOURCES = ROOT / "docs" / "A3_SOURCES.md"
A2_SPEC = ROOT / "docs" / "add_on_spec_2.md"

# term id -> link fragments the entry must carry (empty when the citation is plain text).
NEW_TERMS: dict[str, tuple[str, ...]] = {
    "corporate-imperialism": ("https://doi.org/10.1016/j.marpol.2024.106078",),
    "deficit-model-of-knowledge": ("https://www.ncbi.nlm.nih.gov/books/NBK582037/",),
    "descriptive-vs-prescriptive-norms": ("https://www.ncbi.nlm.nih.gov/books/NBK582037/",),
    "environmental-justice": ("https://19january2017snapshot.epa.gov/",),
    "extended-producer-responsibility": ("https://doi.org/10.1787/9789264256385-en",),
    "garbage-patch": ("https://marinedebris.noaa.gov/info/patch.html",),
    "mnps": ("#nanoplastic-size-conventions",),
    "nanoplastic-size-conventions": ("https://doi.org/10.1016/j.jhazmat.2026.144102",),
    "safe-and-sustainable-by-design": ("https://eur-lex.europa.eu/",),
    "scalar-mismatch": ("https://www.ncbi.nlm.nih.gov/books/NBK582037/",),
    "scoping-review": (),
    "slow-violence": (),
    "systematic-evidence-map": ("https://doi.org/10.1002/cl2.1402",),
    "umbrella-review": (),
    "waste-as-a-dynamic-social-construction": ("https://www.ncbi.nlm.nih.gov/books/NBK582037/",),
    "waste-colonialism": (
        "https://doi.org/10.1016/j.marpol.2024.106078",
        "https://www.basel.int/",
        "https://discardstudies.com/",
    ),
    "waste-trade": ("https://www.basel.int/",),
}

REGISTER_DOIS = (
    "10.1016/j.marpol.2024.106078",  # Peryman et al. 2024
    "10.1016/j.jhazmat.2026.144102",  # Ortiz-Balsero et al. 2026
    "10.1002/cl2.1402",  # Campbell et al. 2024 (repo reference list)
    "10.1177/03058298261464283",  # Ashworth 2026
    "10.2458/jpe.2401",  # Fuller et al. 2022
    "10.1038/s41538-025-00470-3",  # Zimmermann et al. 2025
    "10.1186/s12940-026-01282-y",  # Tran et al. 2026
    "10.1186/s12876-026-05475-0",  # Özkan Vardar and Vardar 2026
    "10.1093/etojnl/vgag148",  # Zuanazzi et al. 2026
)

PAPER_LABELS = (
    "Ashworth (2026)",
    "Foellmer et al. (2022)",
    "Fuller et al. (2022)",
    "Zimmermann et al. (2025)",
    "Tran et al. (2026)",
    "Özkan Vardar and Vardar (2026)",
    "Zuanazzi et al. (2026)",
    "Ortiz-Balsero et al. (2026)",
)
BOOK_LABELS = (
    "Liboiron and Lepawsky (2022)",
    "Reno (2016)",
    "Lepawsky (2018)",
    "MacBride (2012)",
    "Liboiron (2021)",
)
FORBIDDEN_TASK_ID = re.compile(r"\b(?:BQ|A3|EM|UX|AT|VD|PLAT|NOR|MAIL|GA)-[A-Z0-9]")


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _entry(markup: str, term: str) -> str:
    match = re.search(rf'<dt id="{re.escape(term)}">.*?</dt>\s*<dd>(.*?)</dd>', markup, re.DOTALL)
    assert match, f"{term}: no dt/dd pair"
    return match.group(1)


def _reading_section(markup: str) -> str:
    match = re.search(r'<section class="resources-further-reading">(.*?)</section>', markup, re.S)
    assert match, "Further reading section is missing from resources.md"
    return match.group(1)


def _plain(markup: str) -> str:
    return re.sub(r"<[^>]+>", "", markup)


def test_each_new_term_has_one_anchor() -> None:
    markup = _text(GLOSSARY)
    for term in NEW_TERMS:
        assert markup.count(f'<dt id="{term}">') == 1, term


def test_each_new_entry_has_a_source_line_and_its_links() -> None:
    markup = _text(GLOSSARY)
    for term, fragments in NEW_TERMS.items():
        block = _entry(markup, term)
        assert "<small>Source:" in block, term
        for fragment in fragments:
            assert fragment in block, f"{term}: missing {fragment}"


def test_internal_anchor_links_point_to_existing_terms() -> None:
    markup = _text(GLOSSARY)
    for term in NEW_TERMS:
        for target in re.findall(r'href="#([^"]+)"', _entry(markup, term)):
            assert markup.count(f'<dt id="{target}">') == 1, f"{term} links to {target}"


def test_definitions_are_one_or_two_sentences() -> None:
    markup = _text(GLOSSARY)
    for term in NEW_TERMS:
        first = re.search(r"<p>(.*?)</p>", _entry(markup, term), re.DOTALL)
        assert first, term
        sentences = [s for s in re.split(r"(?<=[.!?])\s+", _plain(first.group(1)).strip()) if s]
        assert 1 <= len(sentences) <= 2, term


def test_no_expert_wording_in_glossary_or_reading_list() -> None:
    assert not re.search(r"\bexperts?\b", _text(GLOSSARY), re.IGNORECASE)
    assert not re.search(r"\bexperts?\b", _text(RESOURCES), re.IGNORECASE)


def test_no_internal_task_ids_or_spec_references() -> None:
    for path in (GLOSSARY, RESOURCES):
        text = _text(path)
        assert not FORBIDDEN_TASK_ID.search(text), path.name
        assert "Section 5" not in text, path.name
        assert not re.search(r"\bA3\b", text), path.name


def test_new_definitions_have_no_quotation_marks() -> None:
    markup = _text(GLOSSARY)
    for term in NEW_TERMS:
        assert not re.search(r'["“”]', _plain(_entry(markup, term))), term


def test_register_dois_appear_in_source_registers() -> None:
    registers = _text(A3_SOURCES) + _text(A2_SPEC)
    public = _text(GLOSSARY) + _text(RESOURCES)
    for doi in REGISTER_DOIS:
        assert doi in registers, f"{doi} is not in docs/A3_SOURCES.md or the A2 reference list"
        assert doi in public, f"{doi} is not linked on a public page"


def test_further_reading_lists_each_work_as_link_only_citation() -> None:
    page = _text(RESOURCES)
    section = _reading_section(page)
    for label in (*PAPER_LABELS, *BOOK_LABELS):
        assert label in section, label
    assert "https://discardstudies.com/" in section
    assert "Reuse terms not verified." in section
    assert "978-92-890-5802-5" in section
    assert "https://www.ncbi.nlm.nih.gov/books/NBK582037/" in section
    assert "CC BY-NC-SA 3.0 IGO" in section
    assert "CC BY-NC-ND 4.0" in section


def test_resource_cards_still_mount_below_the_reading_list_anchor() -> None:
    page = _text(RESOURCES)
    assert page.index('<div id="resources-root"></div>') < page.index("Further reading")
    assert "mountResources();" in page
