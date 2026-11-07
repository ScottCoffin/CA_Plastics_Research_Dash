"""Build attributed, short JATS fixtures from license-verified local XML cache."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from atlas.fulltext.cache import _license_blocks
from atlas.fulltext.jats import _parse_xml_document, parse_jats

SCRATCH = Path("scratch/s6_2_real")
OUTPUT = Path("tests/fixtures/s6_2_real_article_fragments.json")
PROVENANCE = Path("docs/api_notes/europepmc_s6_2_fixture_provenance.json")
METADATA_SEARCH = (
    "https://www.ebi.ac.uk/europepmc/webservices/rest/search?"
    "query=PMCID%3APMC13543028+OR+PMCID%3APMC13608240+OR+PMCID%3APMC13572291+OR+"
    "PMCID%3APMC13683851+OR+PMCID%3APMC13578043+OR+PMCID%3APMC13590715+OR+"
    "PMCID%3APMC13630796+OR+PMCID%3APMC13239238+OR+PMCID%3APMC13400951+OR+"
    "PMCID%3APMC13680302&format=json&pageSize=20&resultType=core"
)
ATTRIBUTION = {
    "PMC13543028": "Xie J, Gowen A, Xu JL.",
    "PMC13608240": "Rais B, Vafa A, Dayel FFB, Rashid S.",
    "PMC13572291": "Liu D, Morikawa S, Izumi R, Kurozumi S, Kiyose M, Shimizu M.",
    "PMC13683851": "Nishter Z, Gang L, Zahid A, Naveed WA, Gul R, Hameed A, Khan WU, Elzein IM.",
    "PMC13578043": "Umurhan Y, Limbu TB, Phan T.",
    "PMC13590715": "Zhang Y, Hussain K, Tang X, Lan T, Yan C, Li Y, Wu Y, Li J, Gao X.",
    "PMC13630796": "Santos NGR, Pinho KFB, Reis ICS, Luvizotto-Santos R, Jorge MB.",
    "PMC13239238": (
        "de Freitas BS, Guimarães GDA, Perotti GF, de Moraes BR, Ando RA, Hattori GY, Sant'Anna BS."
    ),
    "PMC13400951": "Reaves M, Ruffell H, O'Neill T, Gaw S.",
    "PMC13680302": (
        "Guimarães GDA, da Fonseca RV, de Moraes BR, Ando RA, de Azevedo Rodrigues IJ, "
        "Perotti GF, Sant'Anna BS, Hattori GY."
    ),
}


def _license_confirmed(record: dict[str, object], xml: bytes) -> list[str]:
    metadata_license = str(record.get("metadata_license", "")).casefold()
    if metadata_license not in {"cc by", "cc0", "cc0-1.0"}:
        raise ValueError(f"unapproved metadata license: {record['pmcid']}")
    try:
        blocks = _license_blocks(xml)
    except ValueError as error:
        raise ValueError(
            f"selected-copy JATS license block did not confirm license: {record['pmcid']}"
        ) from error
    joined = " ".join(block.casefold() for block in blocks)
    if metadata_license == "cc by" and not (
        "creative commons attribution" in joined or "creativecommons.org/licenses/by/" in joined
    ):
        raise ValueError(
            f"selected-copy JATS license class does not match CC BY: {record['pmcid']}"
        )
    if metadata_license.startswith("cc0") and not any(
        token in joined for token in ("cc0", "publicdomain/zero")
    ):
        raise ValueError(f"selected-copy JATS license class does not match CC0: {record['pmcid']}")
    return list(blocks)


def _short_fragment(
    pmcid: str, source_xml: bytes, selected: list[tuple[str, dict[str, str]]]
) -> tuple[str, bool]:
    source_root = _parse_xml_document(source_xml)
    parents = {child: parent for parent in source_root.iter() for child in parent}
    article = ET.Element("article")
    front = ET.SubElement(article, "front")
    metadata = ET.SubElement(front, "article-meta")
    ET.SubElement(metadata, "article-id", {"pub-id-type": "pmc"}).text = pmcid
    body = ET.SubElement(article, "body")
    clones: dict[ET.Element, ET.Element] = {}
    has_nested = False
    for _target, row in selected:
        source_sec = next(
            (
                node
                for node in source_root.iter()
                if node.tag.rsplit("}", 1)[-1].casefold() == "sec"
                and node.attrib.get("id", "") == row["section_id"]
                and any(
                    child.tag.rsplit("}", 1)[-1].casefold() == "title"
                    and " ".join(" ".join(child.itertext()).split()) == row["title"]
                    for child in node
                )
            ),
            None,
        )
        if source_sec is None:
            raise ValueError(f"source section not found: {pmcid} {row['title']}")
        path = [source_sec]
        parent = parents.get(source_sec)
        while parent is not None:
            if parent.tag.rsplit("}", 1)[-1].casefold() == "sec":
                path.append(parent)
            parent = parents.get(parent)
        path.reverse()
        has_nested = has_nested or len(path) > 1
        target_parent = body
        for original in path:
            clone = clones.get(original)
            if clone is None:
                attrs = {
                    key: original.attrib[key]
                    for key in ("id", "sec-type")
                    if original.attrib.get(key)
                }
                clone = ET.SubElement(target_parent, "sec", attrs)
                title = next(
                    (
                        child
                        for child in original
                        if child.tag.rsplit("}", 1)[-1].casefold() == "title"
                    ),
                    None,
                )
                if title is not None:
                    ET.SubElement(clone, "title").text = " ".join(
                        " ".join(title.itertext()).split()
                    )
                clones[original] = clone
            target_parent = clone
        ET.SubElement(target_parent, "p").text = row["evidence"][:180]
    return ET.tostring(article, encoding="unicode"), has_nested


def main() -> int:
    source = json.loads((SCRATCH / "provenance.json").read_text(encoding="utf-8"))
    if len(source.get("selected", [])) != 10:
        raise ValueError("scratch provenance must contain exactly ten accepted article copies")
    fixtures = []
    provenance = {
        "candidate_discovery_search_url": source["metadata_search_url"],
        "metadata_search_url": METADATA_SEARCH,
        "text_endpoint": "https://www.ebi.ac.uk/europepmc/webservices/rest/{PMCID}/fullTextXML",
        "fixture_policy": (
            "At most two target-section excerpts per source work, at most 180 chars each; "
            "no full article XML committed."
        ),
        "articles": [],
        "rejected_license_candidates": [
            {
                "pmcid": item["pmcid"],
                "metadata_license": item["metadata_license"],
                "selected_copy_license_blocks": item.get("xml_licenses", []),
                "reason": item["reason"],
            }
            for item in source.get("rejected", [])
        ],
        "full_article_target_coverage": {
            "methods": 0,
            "study_area": 0,
            "sampling": 0,
            "data_availability": 0,
        },
        "articles_with_any_target": 0,
        "articles_without_target_sections": [],
    }
    for record in source["selected"]:
        pmcid = str(record["pmcid"])
        if pmcid not in ATTRIBUTION:
            raise ValueError(f"no attribution metadata for {pmcid}")
        path = Path(str(record["local_path"]))
        xml = path.read_bytes()
        license_blocks = _license_confirmed(record, xml)
        result = parse_jats(xml, max_chars=180)
        counts = {target: len(rows) for target, rows in result["sections"].items()}
        for target, count in counts.items():
            provenance["full_article_target_coverage"][target] += int(count > 0)
        if any(counts.values()):
            provenance["articles_with_any_target"] += 1
        else:
            provenance["articles_without_target_sections"].append(pmcid)
        candidates = []
        for target in ("methods", "study_area", "sampling", "data_availability"):
            if result["sections"][target]:
                candidates.append((target, result["sections"][target][0]))
            if len(candidates) == 2:
                break
        article_url = f"https://europepmc.org/articles/{pmcid}"
        doi_url = f"https://doi.org/{record['doi']}" if record.get("doi") else ""
        fragment, has_nested = _short_fragment(pmcid, xml, candidates)
        fixtures.append(
            {
                "article_id": pmcid,
                "pmcid": pmcid,
                "doi": record.get("doi", ""),
                "title": record["title"],
                "authors": ATTRIBUTION[pmcid],
                "license": record["metadata_license"],
                "source_url": article_url,
                "attribution": (
                    f"{ATTRIBUTION[pmcid]} {str(record['title']).rstrip('. ')}. "
                    f"Europe PMC record {article_url}."
                ),
                "xml": fragment,
                "has_nested_section_structure": has_nested,
                "expected_sections": [
                    {"target": target, "section_id": row["section_id"], "title": row["title"]}
                    for target, row in candidates
                ],
                "expected_fallback": result["fallback"],
            }
        )
        provenance["articles"].append(
            {
                "pmcid": pmcid,
                "doi": record.get("doi", ""),
                "title": record["title"],
                "authors": ATTRIBUTION[pmcid],
                "metadata_license": record["metadata_license"],
                "metadata_license_source": METADATA_SEARCH,
                "selected_copy_jats_license_blocks": license_blocks,
                "fulltext_source_url": record["source_url"],
                "attribution_url": article_url,
                "doi_url": doi_url,
                "fulltext_sha256": hashlib.sha256(xml).hexdigest(),
                "fulltext_bytes_local_ignored_cache": len(xml),
                "fixture_targets": [target for target, _ in candidates],
                "full_article_target_section_counts": counts,
                "full_article_fallback": result["fallback"],
                "fixture_snippet_char_limit": 180,
                "fixture_snippet_count": len(candidates),
            }
        )
    OUTPUT.write_text(json.dumps(fixtures, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    PROVENANCE.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"Built {len(fixtures)} real-article JATS fixtures; verified selected-copy licenses; "
        "no full XML copied."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
