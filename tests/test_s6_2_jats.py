from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas.fulltext.jats import JATSParseError, parse_jats

FIXTURE = Path(__file__).parent / "fixtures" / "s6_2_jats_articles.json"
REAL_FIXTURE = Path(__file__).parent / "fixtures" / "s6_2_real_article_fragments.json"


@pytest.mark.parametrize(
    "record", json.loads(FIXTURE.read_text(encoding="utf-8")), ids=lambda row: row["article_id"]
)
def test_jats_parser_contract_on_ten_synthetic_article_fixtures(record: dict[str, object]) -> None:
    result = parse_jats(str(record["xml"]))
    sections = result["sections"]
    for target, expected_id in record["expected"].items():
        rows = sections[target]
        if expected_id:
            assert any(row["section_id"] == expected_id for row in rows)
            assert all(row["evidence"] and row["title"] for row in rows)
        else:
            assert rows == []
    assert result["fallback"] == (
        "no_target_sections" if record["article_id"] == "synthetic-10" else ""
    )


def test_jats_parser_bounds_evidence_and_marks_truncation() -> None:
    result = parse_jats(
        "<article><body><sec id='m'><title>Methods</title><p>abcdef</p></sec></body></article>",
        max_chars=3,
    )
    row = result["sections"]["methods"][0]
    assert row["evidence"] == "abc"
    assert row["truncated"] == "true"


def test_jats_parser_strips_external_doctype_and_maps_standard_entities_locally() -> None:
    xml = (
        '<!DOCTYPE article PUBLIC "-//NLM//DTD JATS 1.4//EN" "remote.dtd">'
        "<article><body><sec id='m'><title>Methods</title>"
        "<p>&alpha; &amp; &beta;</p></sec></body></article>"
    )
    result = parse_jats(xml)
    assert result["sections"]["methods"][0]["evidence"] == "\u03b1 & \u03b2"


def test_jats_parser_honors_declared_latin1_encoding() -> None:
    text = (
        '<?xml version="1.0" encoding="ISO-8859-1"?>'
        "<article><body><sec><title>Methods</title><p>Caf\u00e9 samples</p></sec></body></article>"
    )
    result = parse_jats(text.encode("iso-8859-1"))
    assert result["sections"]["methods"][0]["evidence"] == "Caf\u00e9 samples"


def test_jats_parser_honors_utf8_bom_and_declared_encoding() -> None:
    text = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<article><body><sec><title>Methods</title><p>bounded</p></sec></body></article>"
    )
    result = parse_jats(b"\xef\xbb\xbf" + text.encode("utf-8"))
    assert result["sections"]["methods"][0]["evidence"] == "bounded"


def test_jats_parser_honors_utf16_bom_and_generic_encoding() -> None:
    text = (
        '<?xml version="1.0" encoding="UTF-16"?>'
        "<article><body><sec><title>Methods</title><p>bounded</p></sec></body></article>"
    )
    result = parse_jats(b"\xff\xfe" + text.encode("utf-16-le"))
    assert result["sections"]["methods"][0]["evidence"] == "bounded"


def test_jats_parser_honors_utf16_signature_without_bom() -> None:
    text = (
        '<?xml version="1.0" encoding="UTF-16"?>'
        "<article><body><sec><title>Methods</title><p>bounded</p></sec></body></article>"
    )
    result = parse_jats(text.encode("utf-16-be"))
    assert result["sections"]["methods"][0]["evidence"] == "bounded"


def test_jats_parser_ignores_entity_tokens_inside_xml_comments() -> None:
    xml = (
        "<article><!-- literal <!ENTITY fake 'text'> and <!DOCTYPE marker> -->"
        "<body><sec><title>Methods</title><p>safe</p></sec></body></article>"
    )
    assert parse_jats(xml)["sections"]["methods"][0]["evidence"] == "safe"


def test_external_doctype_after_comment_prolog_is_preserved_without_resolution() -> None:
    xml = (
        "<!-- <!DOCTYPE article [<!ENTITY fake 'comment'>]> -->"
        '<!DOCTYPE article SYSTEM "file:///does-not-exist.dtd">'
        "<article><body><sec><title>Methods</title><p>&alpha;</p></sec></body></article>"
    )
    assert parse_jats(xml)["sections"]["methods"][0]["evidence"] == "\u03b1"


def test_internal_entity_subset_cannot_be_hidden_by_comment_cdata_tokens() -> None:
    xml = (
        "<!-- <![CDATA[ -->"
        "<!DOCTYPE article [<!ENTITY x 'EXPANDED'>]>"
        "<!-- ]]> -->"
        "<article><body><sec><title>Methods</title><p>&x;</p></sec></body></article>"
    )
    with pytest.raises(JATSParseError):
        parse_jats(xml)


def test_cdata_markup_tokens_remain_literal_document_content() -> None:
    xml = (
        "<article><body><p><![CDATA[<!DOCTYPE article [<!ENTITY x 'z'>]> &x;]]></p>"
        "<sec><title>Methods</title><p>safe</p></sec></body></article>"
    )
    assert parse_jats(xml)["sections"]["methods"][0]["evidence"] == "safe"


@pytest.mark.parametrize(
    "xml",
    [
        "<article>",
        "<book/>",
        "<!DOCTYPE article [<!ENTITY x SYSTEM 'file:///etc/passwd'>]><article/>",
        "<!-- prolog --><!DOCTYPE article [<!-- subset comment --><!ENTITY x 'text'>]><article/>",
        "<!DOCTYPE article [<!ELEMENT article ANY>]><article/>",
    ],
)
def test_jats_parser_rejects_invalid_nonarticle_or_entity_input(xml: str) -> None:
    with pytest.raises(JATSParseError):
        parse_jats(xml)


@pytest.mark.parametrize(
    "record",
    json.loads(REAL_FIXTURE.read_text(encoding="utf-8")),
    ids=lambda row: row["pmcid"],
)
def test_jats_parser_real_cc_by_article_fragments(record: dict[str, object]) -> None:
    assert record["license"] == "cc by"
    assert record["source_url"].startswith("https://europepmc.org/articles/PMC")
    assert record["attribution"] and record["doi"]
    parsed = parse_jats(str(record["xml"]))
    for expected in record["expected_sections"]:
        rows = parsed["sections"][expected["target"]]
        assert any(
            row["section_id"] == expected["section_id"] and row["title"] == expected["title"]
            for row in rows
        )
    assert parsed["fallback"] == record["expected_fallback"]


def test_real_article_fixture_set_preserves_a_nested_section_path() -> None:
    records = json.loads(REAL_FIXTURE.read_text(encoding="utf-8"))
    nested = [record for record in records if record["has_nested_section_structure"]]
    assert nested
    assert any("<sec" in record["xml"] and "</sec><sec" not in record["xml"] for record in nested)
