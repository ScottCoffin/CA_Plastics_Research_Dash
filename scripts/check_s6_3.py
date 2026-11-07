"""Focused S6.3 contract check; no external GROBID or documents required."""

from __future__ import annotations

from atlas.fulltext.grobid import extract_pdf, parse_tei


def main() -> int:
    tei = b"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
    <div type="methods"><head>Methods</head><p>Samples were collected.</p></div>
    </body></text></TEI>"""
    assert parse_tei(tei)["sections"]["methods"][0]["evidence"] == "Samples were collected."
    timeout_result = extract_pdf(
        b"%PDF-1.7\nfixture",
        grobid=lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("test timeout")),
        fallback=lambda pdf, *, max_chars: {
            "sections": {"methods": [], "study_area": [], "sampling": [], "data_availability": []},
            "fallback": "no_target_sections",
        },
    )
    assert timeout_result["failure_category"] == "grobid_timeout"
    assert timeout_result["extractor"] == "pdfminer"
    malformed = extract_pdf(b"bad")
    assert malformed["failure_category"] == "malformed_pdf"
    print("S6.3 focused acceptance passed (TEI, malformed PDF, timeout fallback)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
