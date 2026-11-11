from pathlib import Path

from atlas.ingest import orcid as oc

PERSON = {
    "biography": {"content": "  Studies   microplastics.\n" + "x" * 2000},
    "emails": {"email": [{"email": "someone@example.edu"}]},
    "keywords": {"keyword": [{"content": "microplastics"}, {"content": " "}, {"content": "water"}]},
    "researcher-urls": {
        "researcher-url": [
            {"url-name": "Lab", "url": {"value": "https://lab.example.edu"}},
            {"url-name": "Bad", "url": {"value": "javascript:alert(1)"}},
            {"url-name": "Mail", "url": {"value": "mailto:a@b.c"}},
            {"url-name": "Plain", "url": {"value": "http://x.example.org/p"}},
        ]
    },
}


def _emp(name, region, country, start, end, ror=None):
    dis = (
        {
            "disambiguation-source": "ROR",
            "disambiguated-organization-identifier": f"https://ror.org/{ror}",
        }
        if ror
        else None
    )
    return {
        "employment-summary": {
            "organization": {
                "name": name,
                "address": {"city": "X", "region": region, "country": country},
                "disambiguated-organization": dis,
            },
            "start-date": {"year": {"value": str(start)}} if start else None,
            "end-date": {"year": {"value": str(end)}} if end else None,
            "role-title": "Prof",
        }
    }


EMPS = {
    "affiliation-group": [
        {"summaries": [_emp("UC Davis", "California", "US", 2015, None, "05rrcem69")]},
        {"summaries": [_emp("MIT", "MA", "US", 2005, 2014)]},
        {"summaries": [_emp("Stanford", "", "US", 2001, 2004, "00f54p054")]},
        {"summaries": [_emp("Undated", "CA", "US", None, None)]},
    ]
}


def test_strip_sensitive_removes_emails() -> None:
    clean = oc.strip_sensitive(PERSON)
    assert "emails" not in clean
    assert "someone@example.edu" not in str(clean)
    assert "biography" in clean


def test_bio_truncation_and_whitespace() -> None:
    bio = oc.parse_biography(PERSON)
    assert bio.startswith("Studies microplastics.")
    assert len(bio) <= oc.BIO_MAX
    assert oc.parse_biography({}) == ""


def test_keywords_and_url_scheme_filter() -> None:
    assert oc.parse_keywords(PERSON) == ["microplastics", "water"]
    urls = oc.parse_researcher_urls(PERSON)
    assert [u["url"] for u in urls] == ["https://lab.example.edu", "http://x.example.org/p"]


def test_parse_employments_and_ca_detection() -> None:
    emps = oc.parse_employments(EMPS)
    assert len(emps) == 4
    assert emps[0]["ror"] == "05rrcem69" and emps[0]["start_year"] == 2015
    assert emps[1]["end_year"] == 2014
    ca_rors = {"05rrcem69", "00f54p054"}
    assert oc.is_ca_employment(emps[0], ca_rors)
    assert not oc.is_ca_employment(emps[1], ca_rors)
    assert oc.is_ca_employment(emps[2], ca_rors)  # ROR match, no region
    assert oc.is_ca_employment(emps[3], set())  # region "CA"
    assert oc.ca_employment_years(emps, ca_rors) == [[2015, None], [2001, 2004]]


def test_carry_forward_classifier() -> None:
    emps = oc.parse_employments(EMPS)
    ca = oc.ca_employment_years(emps, {"05rrcem69", "00f54p054"})
    assert oc.classify_carry_forward(2020, emps, ca) == "confirmed"
    assert oc.classify_carry_forward(2014, emps, ca) == "confirmed"  # +/-1 year slack
    assert oc.classify_carry_forward(2010, emps, ca) == "contradicted"
    assert oc.classify_carry_forward(None, emps, ca) == "no_evidence"
    assert oc.classify_carry_forward(2010, [], []) == "no_evidence"
    undated = oc.parse_employments(
        {"affiliation-group": [{"summaries": [_emp("A", "CA", "US", None, None)]}]}
    )
    assert oc.classify_carry_forward(2010, undated, []) == "no_evidence"


def test_doi_normalization_and_works() -> None:
    assert oc.normalize_doi("https://doi.org/10.1000/ABC.1") == "10.1000/abc.1"
    assert oc.normalize_doi("doi:10.1/X") == "10.1/x"
    assert oc.normalize_doi("not a doi") == ""
    works = {
        "group": [
            {
                "external-ids": {
                    "external-id": [
                        {"external-id-type": "doi", "external-id-value": "HTTPS://DOI.ORG/10.5/A"},
                        {"external-id-type": "pmid", "external-id-value": "1"},
                    ]
                },
                "work-summary": [{"publication-date": {"year": {"value": "2021"}}}],
            },
            {
                "external-ids": {
                    "external-id": [{"external-id-type": "doi", "external-id-value": "10.5/a"}]
                }
            },
        ]
    }
    assert oc.parse_work_dois(works) == [("10.5/a", 2021)]


def test_orcid_and_ror_ids() -> None:
    assert oc.normalize_orcid("https://orcid.org/0000-0003-4902-6511") == "0000-0003-4902-6511"
    assert oc.normalize_orcid("") == ""
    assert oc.normalize_ror("https://ror.org/05rrcem69") == "05rrcem69"
    assert oc.normalize_ror("junk") == ""


def test_cache_freshness(tmp_path: Path) -> None:
    p = oc.cache_path(tmp_path, "0000-0000-0000-0001", "person")
    assert not oc.cache_fresh(p, 30)
    oc.write_cache(p, {"a": 1})
    assert oc.cache_fresh(p, 30)
    assert not oc.cache_fresh(p, 30, now=p.stat().st_mtime + 31 * 86400)
    assert oc.read_cache(p) == {"a": 1}


def test_client_request_cap() -> None:
    client = oc.OrcidClient(max_requests=0)
    try:
        client.get_json("x/person")
    except oc.BudgetExhausted:
        return
    raise AssertionError("cap not enforced")


def test_search_payload_email_stripped() -> None:
    payload = {"expanded-result": [{"orcid-id": "0000-0000-0000-0001", "email": ["a@b.edu"]}]}
    clean = oc.strip_search_payload(payload)
    assert "a@b.edu" not in str(clean)
    assert oc.parse_ror_search(clean)[0]["orcid"] == "0000-0000-0000-0001"


def test_biography_redacts_email_addresses() -> None:
    from atlas.ingest.orcid import parse_biography

    bio = parse_biography({"biography": {"content": "Contact me at jane.doe@example.edu please."}})
    assert "@" not in bio and "[email removed]" in bio
