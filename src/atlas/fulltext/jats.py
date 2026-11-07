"""Extract short, section-level evidence from Europe PMC JATS XML.

This module deliberately accepts XML supplied by the caller. Fetching, license
checks, and caching belong to the locator/cache boundary, not the parser.
"""

from __future__ import annotations

import codecs
import re
import xml.etree.ElementTree as ET
from html.entities import html5

from defusedxml import ElementTree as DEFUSED_ET
from defusedxml.common import DefusedXmlException


class JATSParseError(ValueError):
    """Raised when input is malformed or is not a JATS article."""


_TARGETS = ("methods", "study_area", "sampling", "data_availability")
_LABELS = {
    "methods": (
        "method",
        "methods",
        "materials and methods",
        "methodology",
        "experimental procedures",
    ),
    "study_area": (
        "study area",
        "study site",
        "study region",
        "site description",
        "sampling location",
    ),
    "sampling": (
        "sampling",
        "sample collection",
        "sampling procedure",
        "field sampling",
        "specimen collection",
    ),
    "data_availability": (
        "data availability",
        "availability of data",
        "data and materials availability",
        "data sharing",
    ),
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _bounded(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    snippet = value[:limit]
    return snippet.rsplit(" ", 1)[0] if " " in snippet else snippet


def _text(node: ET.Element) -> str:
    return _clean(" ".join(part for part in node.itertext() if part and part.strip()))


def _norm_heading(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _decode_xml(raw: str | bytes) -> str:
    """Decode XML bytes by BOM/signature and the declared encoding."""
    if isinstance(raw, str):
        text = raw
    else:
        encoding: str | None = None
        if raw.startswith(codecs.BOM_UTF32_BE):
            encoding = "utf-32-be"
        elif raw.startswith(codecs.BOM_UTF32_LE):
            encoding = "utf-32-le"
        elif raw.startswith(codecs.BOM_UTF8):
            encoding = "utf-8-sig"
        elif raw.startswith(codecs.BOM_UTF16_BE):
            encoding = "utf-16-be"
        elif raw.startswith(codecs.BOM_UTF16_LE):
            encoding = "utf-16-le"
        elif raw.startswith(b"\x00\x00\x00<"):
            encoding = "utf-32-be"
        elif raw.startswith(b"<\x00\x00\x00"):
            encoding = "utf-32-le"
        elif raw.startswith(b"\x00<\x00?"):
            encoding = "utf-16-be"
        elif raw.startswith(b"<\x00?\x00"):
            encoding = "utf-16-le"
        declared_encoding = None
        if encoding is None:
            declaration_bytes = (
                raw[len(codecs.BOM_UTF8) :] if raw.startswith(codecs.BOM_UTF8) else raw
            )
            declaration_match = re.match(
                rb"\s*<\?xml\b.*?\?>", declaration_bytes[:1024], flags=re.IGNORECASE | re.DOTALL
            )
            if declaration_match:
                encoding_match = re.search(
                    rb"\bencoding\s*=\s*(['\"])([^'\"]+)\1",
                    declaration_match.group(0),
                    flags=re.IGNORECASE,
                )
                if encoding_match:
                    try:
                        declared_encoding = encoding_match.group(2).decode("ascii")
                    except UnicodeDecodeError as error:
                        raise JATSParseError("XML encoding name is not ASCII") from error
        if encoding is None:
            encoding = declared_encoding or "utf-8"
        try:
            text = raw.decode(encoding)
        except (LookupError, UnicodeError) as error:
            raise JATSParseError(f"could not decode XML as {encoding}") from error
        text = text.lstrip("\ufeff")
        declaration = re.match(r"\s*<\?xml\b.*?\?>", text, flags=re.IGNORECASE | re.DOTALL)
        if declaration:
            encoding_match = re.search(
                r"\bencoding\s*=\s*(['\"])([^'\"]+)\1",
                declaration.group(0),
                flags=re.IGNORECASE,
            )
            if encoding_match:
                declared = encoding_match.group(2)
                normalized = declared.casefold().replace("_", "-")
                detected = encoding.casefold().replace("_", "-")
                compatible = {detected}
                if detected == "utf-8-sig":
                    compatible.add("utf-8")
                if detected.startswith("utf-16-"):
                    compatible.add("utf-16")
                if detected.startswith("utf-32-"):
                    compatible.add("utf-32")
                if encoding != "utf-8" and normalized not in compatible:
                    raise JATSParseError("XML encoding declaration conflicts with byte signature")
                try:
                    codecs.lookup(declared)
                except LookupError as error:
                    raise JATSParseError(f"unknown XML encoding: {declared}") from error
            text = text[declaration.end() :]
    text = text.lstrip("\ufeff")
    declaration = re.match(r"\s*<\?xml\b.*?\?>", text, flags=re.IGNORECASE | re.DOTALL)
    if declaration:
        text = text[declaration.end() :]
    return text


def _map_external_entities(text: str) -> str:
    """Map common DTD-provided names without changing comments or CDATA."""
    known = {name[:-1]: value for name, value in html5.items() if name.endswith(";")}
    predefined = {"amp", "lt", "gt", "apos", "quot"}

    def entity(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in predefined:
            return match.group(0)
        value = known.get(name)
        if value is None:
            return f"&amp;{name};"
        return "".join(f"&#{ord(char)};" for char in value)

    output: list[str] = []
    cursor = 0
    while cursor < len(text):
        literal_end = None
        if text.startswith("<!--", cursor):
            marker = "<!--"
            closing = "-->"
        elif text.startswith("<![CDATA[", cursor):
            marker = "<![CDATA["
            closing = "]]>"
        elif text.startswith("<!DOCTYPE", cursor):
            quote = ""
            depth = 0
            index = cursor + len("<!DOCTYPE")
            while index < len(text):
                char = text[index]
                if quote:
                    if char == quote:
                        quote = ""
                elif char in "\"'":
                    quote = char
                elif char == "[":
                    depth += 1
                elif char == "]":
                    depth = max(0, depth - 1)
                elif char == ">" and depth == 0:
                    literal_end = index + 1
                    break
                index += 1
            if literal_end is None:
                output.append(text[cursor:])
                break
            output.append(text[cursor:literal_end])
            cursor = literal_end
            continue
        else:
            entity_match = re.match(r"&([A-Za-z][A-Za-z0-9]+);", text[cursor:])
            if entity_match:
                output.append(entity(entity_match))
                cursor += entity_match.end()
            else:
                output.append(text[cursor])
                cursor += 1
            continue

        closing_start = text.find(closing, cursor + len(marker))
        if closing_start < 0:
            output.append(text[cursor:])
            break
        literal_end = closing_start + len(closing)
        output.append(text[cursor:literal_end])
        cursor = literal_end
    return "".join(output)


def _reject_internal_subset(text: str) -> None:
    """Reject DTD internal subsets while skipping XML prolog comments/PIs."""
    cursor = 0
    while cursor < len(text):
        if text[cursor].isspace():
            cursor += 1
        elif text.startswith("<!--", cursor):
            end = text.find("-->", cursor + 4)
            if end < 0:
                return  # The hardened parser reports the unterminated comment.
            cursor = end + 3
        elif text.startswith("<?", cursor):
            end = text.find("?>", cursor + 2)
            if end < 0:
                return
            cursor = end + 2
        elif text.startswith("<!DOCTYPE", cursor):
            quote = ""
            index = cursor + len("<!DOCTYPE")
            while index < len(text):
                char = text[index]
                if quote:
                    if char == quote:
                        quote = ""
                elif char in "\"'":
                    quote = char
                elif char == "[":
                    raise JATSParseError("internal DTD subsets are not accepted")
                elif char == ">":
                    return
                index += 1
            return
        else:
            return


def _parse_xml_document(xml: str | bytes) -> ET.Element:
    """Parse XML with entity expansion and external access disabled."""
    decoded = _decode_xml(xml)
    _reject_internal_subset(decoded)
    safe_bytes = _map_external_entities(decoded).encode("utf-8")
    try:
        return DEFUSED_ET.fromstring(
            safe_bytes,
            forbid_dtd=False,
            forbid_entities=True,
            forbid_external=True,
        )
    except (ET.ParseError, DefusedXmlException) as error:
        raise JATSParseError(f"invalid or unsafe XML: {error}") from error


def _heading(sec: ET.Element) -> str:
    for child in sec:
        if _local(child.tag) == "title":
            return _text(child)
    return ""


def _classify(sec: ET.Element) -> tuple[str, int] | None:
    title = _norm_heading(_heading(sec))
    sec_type = _norm_heading(sec.attrib.get("sec-type", ""))
    for target, labels in _LABELS.items():
        for label in labels:
            key = _norm_heading(label)
            if title == key:
                return target, 3
            if sec_type == key or sec_type.replace(" ", "-") == key.replace(" ", "-"):
                return target, 2
        if target == "methods" and (
            title.startswith(
                (
                    "star methods",
                    "methods",
                    "method ",
                    "material and method",
                    "materials and method",
                )
            )
            or "method" in sec_type
        ):
            return target, 1
        if target == "study_area" and title.startswith(
            ("study area", "study region", "study site", "study location")
        ):
            return target, 1
        if target == "sampling" and (
            "sampling" in title or "sample collection" in title or "specimen collection" in title
        ):
            return target, 1
        if target == "data_availability" and (
            ("data" in title and "avail" in title) or ("data" in sec_type and "avail" in sec_type)
        ):
            return target, 1
    return None


def _own_paragraphs(sec: ET.Element) -> str:
    """Collect paragraphs here and through nested sections with no target label."""
    chunks: list[str] = []

    def walk(node: ET.Element) -> None:
        for child in node:
            kind = _local(child.tag)
            if kind == "sec":
                if _classify(child) is not None:
                    continue
                walk(child)
                continue
            if kind == "p":
                value = _text(child)
                if value:
                    chunks.append(value)
                continue
            walk(child)

    walk(sec)
    return _clean(" ".join(chunks))


def parse_jats(xml: str | bytes, *, max_chars: int = 1200) -> dict[str, object]:
    """Return matched section snippets with source IDs and headings.

    ``max_chars`` bounds each evidence snippet. A standalone external DOCTYPE
    is stripped without retrieval; internal DTD subsets and entity declarations
    are rejected before ElementTree parsing. Missing targets are empty lists.
    """
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    root = _parse_xml_document(xml)
    if _local(root.tag) != "article":
        raise JATSParseError("expected JATS article root")

    results: dict[str, list[dict[str, str]]] = {name: [] for name in _TARGETS}
    for sec in root.iter():
        if _local(sec.tag) != "sec":
            continue
        match = _classify(sec)
        if match is None:
            continue
        target, score = match
        text = _own_paragraphs(sec)
        if not text:
            continue
        results[target].append(
            {
                "section_id": sec.attrib.get("id", ""),
                "title": _heading(sec),
                "sec_type": sec.attrib.get("sec-type", ""),
                "evidence": _bounded(text, max_chars),
                "truncated": str(len(text) > max_chars).lower(),
                "match_score": str(score),
            }
        )
    return {"sections": results, "fallback": "" if any(results.values()) else "no_target_sections"}
