from __future__ import annotations

import hashlib
import json
import urllib.error

import pytest

from atlas.fulltext.grobid import PDFExtractionError, extract_pdf, extract_pdf_cached, parse_tei

TEI = b"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<div n="2" type="methods"><head>Materials and Methods</head>
<p>Samples were collected in Monterey Bay.</p></div>
<div n="3"><head>Study area</head><p>Stations were along the coast.</p></div>
<div n="4"><head>Data availability</head><p>Data are available at Zenodo.</p></div>
</body></text></TEI>"""
PDF = b"%PDF-1.7\nfixture"


def _text_pdf(lines: list[str]) -> bytes:
    commands = ["BT /F1 12 Tf 72 720 Td"]
    for line in lines:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.extend([f"({escaped}) Tj", "0 -18 Td"])
    commands.append("ET")
    stream = "\n".join(commands).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(pdf)


def test_grobid_tei_maps_sections_to_jats_result_shape():
    result = parse_tei(TEI)
    assert result["fallback"] == ""
    assert result["sections"]["methods"][0]["section_id"] == "2"
    assert result["sections"]["methods"][0]["evidence"] == "Samples were collected in Monterey Bay."
    assert result["sections"]["study_area"][0]["title"] == "Study area"
    assert result["sections"]["data_availability"][0]["match_score"] == "3"
    assert result["sections"]["sampling"] == []


def test_grobid_tei_does_not_classify_review_subheadings_by_keyword_alone():
    tei = b"""<TEI><text><body>
    <div><head>Translational relevance and methodological gaps</head><p>Review text.</p></div>
    <div><head>Climate-sensitive hydrology generates episodic exposure that
    steady-state sampling can miss</head><p>Review text.</p></div>
    </body></text></TEI>"""
    sections = parse_tei(tei)["sections"]
    assert sections["methods"] == []
    assert sections["sampling"] == []


def test_malformed_pdf_is_reported_without_calling_services():
    result = extract_pdf(b"not a pdf", grobid=lambda **_: pytest.fail("unexpected GROBID call"))
    assert result["failure_category"] == "malformed_pdf"
    assert result["extractor"] == "none"


def test_grobid_timeout_uses_pdfminer_fallback_and_preserves_category():
    def timeout(*args, **kwargs):
        raise TimeoutError("service timeout")

    def local_fallback(pdf, *, max_chars):
        return {
            "sections": {
                "methods": [{"title": "Methods", "evidence": "local text"}],
                "study_area": [],
                "sampling": [],
                "data_availability": [],
            },
            "fallback": "",
        }

    result = extract_pdf(PDF, grobid=timeout, fallback=local_fallback)
    assert result["extractor"] == "pdfminer"
    assert result["failure_category"] == "grobid_timeout"
    assert result["sections"]["methods"][0]["evidence"] == "local text"


def test_invalid_tei_falls_back_and_reports_failure_category():
    result = extract_pdf(
        PDF,
        grobid=lambda *args, **kwargs: b"<not-tei/>",
        fallback=lambda pdf, *, max_chars: {
            "sections": {"methods": [], "study_area": [], "sampling": [], "data_availability": []},
            "fallback": "no_target_sections",
        },
    )
    assert result["extractor"] == "pdfminer"
    assert result["failure_category"] == "invalid_tei"


def test_wrapped_url_timeout_is_counted_as_grobid_timeout():
    result = extract_pdf(
        PDF,
        grobid=lambda *args, **kwargs: (_ for _ in ()).throw(
            urllib.error.URLError(TimeoutError("socket timeout"))
        ),
        fallback=lambda pdf, *, max_chars: {
            "sections": {"methods": [], "study_area": [], "sampling": [], "data_availability": []},
            "fallback": "no_target_sections",
        },
    )
    assert result["failure_category"] == "grobid_timeout"


def test_pdfminer_does_not_promote_data_availability_sentence_to_heading():
    from atlas.fulltext.grobid import extract_pdfminer

    result = extract_pdfminer(
        _text_pdf(
            [
                "Methods",
                "Samples were collected in Monterey Bay.",
                "Data are available at Zenodo.",
                "Data are available in a related repository",
            ]
        )
    )
    methods = result["sections"]["methods"]
    assert len(methods) == 1
    assert "Data are available at Zenodo." in methods[0]["evidence"]
    assert "Data are available in a related repository" in methods[0]["evidence"]
    assert result["sections"]["data_availability"] == []


def test_pdfminer_does_not_classify_author_role_list_as_methods():
    from atlas.fulltext.grobid import extract_pdfminer

    result = extract_pdfminer(
        _text_pdf(
            [
                "Author contributions",
                "Methodology, Project administration, Visualization, Writing original draft.",
            ]
        )
    )
    assert result["sections"]["methods"] == []


def test_pdf_cache_requires_permissive_selected_copy_and_caches_only_derived_output(tmp_path):
    locator = {
        "work_id": "W123",
        "source_type": "pdf",
        "locator_url": "https://example.org/a.pdf",
        "license": "cc-by-4.0",
        "license_provenance": "OpenAlex best_oa_location.license",
        "license_status": "permissive",
        "processing_allowed": True,
        "storage_decision": "cache_only",
    }
    calls = []

    def fetch(url, *, timeout, max_bytes):
        calls.append(url)
        return PDF

    def grobid(pdf, *, base_url, timeout):
        return TEI

    first = extract_pdf_cached(
        locator,
        cache_dir=tmp_path,
        fetcher=fetch,
        grobid=grobid,
        minimum_interval=0,
        expected_pdf_sha256=hashlib.sha256(PDF).hexdigest(),
    )
    second = extract_pdf_cached(
        locator,
        cache_dir=tmp_path,
        fetcher=fetch,
        grobid=grobid,
        minimum_interval=0,
        expected_pdf_sha256=hashlib.sha256(PDF).hexdigest(),
    )
    assert first == second
    assert len(calls) == 1
    saved = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert "pdf_sha256" in saved
    assert "pdf_bytes" not in saved and "raw_pdf" not in saved
    saved["result_sha256"] = "0" * 64
    next(tmp_path.glob("*.json")).write_text(json.dumps(saved), encoding="utf-8")
    extract_pdf_cached(
        locator,
        cache_dir=tmp_path,
        fetcher=fetch,
        grobid=grobid,
        minimum_interval=0,
        expected_pdf_sha256=hashlib.sha256(PDF).hexdigest(),
    )
    assert len(calls) == 2
    locator["locator_url"] = "https://example.org/other.pdf"
    extract_pdf_cached(
        locator,
        cache_dir=tmp_path,
        fetcher=fetch,
        grobid=grobid,
        minimum_interval=0,
        expected_pdf_sha256=hashlib.sha256(PDF).hexdigest(),
    )
    assert len(calls) == 3
    locator["processing_allowed"] = False
    with pytest.raises(PDFExtractionError, match="does not allow"):
        extract_pdf_cached(locator, cache_dir=tmp_path, fetcher=fetch, minimum_interval=0)


def test_invalid_grobid_endpoint_is_rejected_before_pdf_fetch(tmp_path):
    locator = {
        "work_id": "W2",
        "source_type": "pdf",
        "locator_url": "https://example.org/a.pdf",
        "license": "cc-by-4.0",
        "license_provenance": "OpenAlex selected PDF license",
        "license_status": "permissive",
        "processing_allowed": True,
        "storage_decision": "cache_only",
    }
    calls = []
    with pytest.raises(PDFExtractionError, match="GROBID endpoint"):
        extract_pdf_cached(
            locator,
            cache_dir=tmp_path,
            grobid_url="https://remote.example:8070",
            fetcher=lambda *args, **kwargs: calls.append("fetched") or PDF,
            minimum_interval=0,
        )
    assert calls == []


def test_cache_rejects_a_fetched_pdf_that_differs_from_selected_hash(tmp_path):
    locator = {
        "work_id": "W3",
        "source_type": "pdf",
        "locator_url": "https://example.org/a.pdf",
        "license": "cc-by-4.0",
        "license_provenance": "OpenAlex selected PDF license",
        "license_status": "permissive",
        "processing_allowed": True,
        "storage_decision": "cache_only",
    }
    with pytest.raises(PDFExtractionError, match="hash does not match"):
        extract_pdf_cached(
            locator,
            cache_dir=tmp_path,
            fetcher=lambda *args, **kwargs: PDF,
            expected_pdf_sha256="0" * 64,
            minimum_interval=0,
        )


def test_pdf_source_dns_must_resolve_only_to_global_ips(monkeypatch):
    import socket

    from atlas.fulltext.grobid import _public_https_url

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443))],
    )
    with pytest.raises(PDFExtractionError, match="non-public"):
        _public_https_url("https://publisher.example/article.pdf")


def test_pdf_download_rejects_changed_final_url_even_if_transport_returns_bytes(monkeypatch):
    from atlas.fulltext import grobid

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def geturl(self):
            return "https://other.example/article.pdf"

        def read(self, limit):
            return PDF

    class Opener:
        def open(self, request, timeout):
            return Response()

    monkeypatch.setattr(grobid, "_public_https_url", lambda url: None)
    monkeypatch.setattr(grobid.urllib.request, "build_opener", lambda *args: Opener())
    with pytest.raises(PDFExtractionError, match="unexpected response"):
        grobid._fetch_pdf("https://publisher.example/article.pdf", timeout=5, max_bytes=1000)
