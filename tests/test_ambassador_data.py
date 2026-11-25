"""Ambassador data (AMB-1 step 1): domains, eligibility, overrides, case queues and privacy.

Builds small synthetic regions under ``tmp_path`` (the ignored inputs are never read here).
"""

from __future__ import annotations

import gzip
import json
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from atlas.build.ambassadors import (
    CASE_KINDS,
    ELIGIBLE_TYPES,
    MIN_WORKS,
    FetchLimitError,
    RorValues,
    affiliation_acronyms,
    build_region,
    fetch_openalex,
    fetch_ror,
    inputs_present,
    is_free_mail,
    load_alias_rules,
    load_corpus,
    load_overrides,
    load_ror_domains,
    missing_domain_cache,
    prefix_aliases,
    read_cache,
    registrable_domain,
    resolve_domains,
    ror_names,
    validate_outputs,
)
from atlas.regions.registry import Predicate, Region

GENERATED = "2026-01-01T00:00:00Z"


def _norway() -> Region:
    return Region(
        slug="norway",
        name="Norway",
        tier="A",
        parent=None,
        status="planned",
        predicate=Predicate(country_codes=("NO",)),
        site_data_dir="site/data/norway",
    )


def _work(work_id: str, language: str, institutions: list[dict], **extra: object) -> dict:
    authorship = {
        "countries": extra.pop("countries", ["NO"]),
        "raw_affiliation_strings": extra.pop("affiliations", ["Some lab, Norway"]),
        "institutions": institutions,
    }
    return {
        "id": f"https://openalex.org/{work_id}",
        "title": extra.pop("title", f"Microplastics study {work_id}"),
        "language": language,
        "authorships": [authorship],
        **extra,
    }


def _inst(inst_id: str, name: str, type_: str, country: str = "NO", **extra: object) -> dict:
    return {
        "id": f"https://openalex.org/{inst_id}",
        "display_name": name,
        "type": type_,
        "country_code": country,
        "ror": extra.pop("ror", None),
        **extra,
    }


def _write_global(root: Path, works: list[dict], languages: dict[str, str]) -> None:
    (root / "data/processed/global").mkdir(parents=True)
    pq.write_table(
        pa.table(
            {
                "work_id": list(languages),
                "language": list(languages.values()),
            }
        ),
        root / "data/processed/global/works.parquet",
    )
    pages = root / "data/raw/openalex_global/pages"
    pages.mkdir(parents=True)
    with gzip.open(pages / "0001.jsonl.gz", "wt", encoding="utf-8") as handle:
        handle.write('{"page_header": true}\n')
        for work in works:
            handle.write(json.dumps(work) + "\n")


@pytest.fixture()
def country_root(tmp_path: Path) -> Path:
    """Norway fixture: eligible, too-small, wrong-type, foreign and local-language cases."""
    niva = _inst("I1", "NIVA", "facility", ror="https://ror.org/01abc")
    works: list[dict] = []
    languages: dict[str, str] = {}
    for n in range(1, 4):  # three works: meets MIN_WORKS
        wid = f"W{n}"
        works.append(_work(wid, "en", [_inst("I10", "Uni Nord", "education")]))
        languages[wid] = "en"
    works.append(
        _work("W20", "nb", [_inst("I11", "Ocean Lab", "nonprofit")], title="Mikroplast i fjorden")
    )
    languages["W20"] = "nb"
    for n in (21, 22):  # two works: below MIN_WORKS
        works.append(_work(f"W{n}", "en", [_inst("I12", "Small Co", "education")]))
        languages[f"W{n}"] = "en"
    for n in (30, 31, 32, 33, 34):  # five company works: not eligible
        works.append(_work(f"W{n}", "en", [_inst("I13", "Plastics Ltd", "company")]))
        languages[f"W{n}"] = "en"
    for n in (40, 41, 42):  # niva: homepage on a subdomain, facility
        works.append(
            _work(
                f"W{n}",
                "en",
                [{**niva, "homepage_url": "https://bio.www.niva.no/"}],
                affiliations=["NIVA, Oslo, Norway"],
            )
        )
        languages[f"W{n}"] = "en"
    works.append(
        _work(
            "W50",
            "en",
            [_inst("I90", "Foreign Univ", "education", country="US")],
            countries=["NO"],
            affiliations=["Foreign Univ; contact a.b@example.no", "Bergen, Norway"],
        )
    )
    languages["W50"] = "en"
    _write_global(tmp_path, works, languages)
    return tmp_path


def _rows(institutions: dict) -> dict[str, dict]:
    return {row["id"]: row for row in institutions["institutions"]}


def test_registrable_domain_handles_subdomains_and_two_level_suffixes() -> None:
    assert registrable_domain("bio.uio.no") == "uio.no"
    assert registrable_domain("https://www.ntnu.no/en/?x=1") == "ntnu.no"
    assert registrable_domain("https://user@lab.ucla.edu:8443/") == "ucla.edu"
    assert registrable_domain("waterboards.ca.gov") == "waterboards.ca.gov"
    assert registrable_domain("sub.dtsc.ca.gov") == "dtsc.ca.gov"
    assert registrable_domain("noaa.gov") == "noaa.gov"
    assert registrable_domain("ca.gov") is None
    assert registrable_domain("no") is None
    assert registrable_domain("127.0.0.1") is None
    assert registrable_domain("") is None


def test_free_mail_and_generic_domains_are_refused() -> None:
    for domain in ("gmail.com", "outlook.com", "proton.me", "gmx.de", "yahoo.co.uk", "web.de"):
        assert is_free_mail(domain), domain
    assert not is_free_mail("uio.no")
    assert not is_free_mail("liveocean.org")


def test_add_override_for_free_mail_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "ambassador_domains.csv"
    path.write_text("institution_id,domain,action,note\nI1,gmail.com,add,bad\n", encoding="utf-8")
    with pytest.raises(ValueError, match="free-mail"):
        load_overrides(path)


def test_override_header_and_rows_are_validated(tmp_path: Path) -> None:
    path = tmp_path / "ambassador_domains.csv"
    path.write_text("institution_id,domain,action\nI1,x.no,add\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        load_overrides(path)
    path.write_text("institution_id,domain,action,note\nX1,x.no,add,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="institution_id"):
        load_overrides(path)
    assert load_overrides(tmp_path / "missing.csv") == {}


def test_country_rules_type_filter_and_minimum_works(country_root: Path) -> None:
    institutions, _ = build_region(_norway(), country_root, GENERATED)
    rows = _rows(institutions)
    assert set(rows) == {"I10", "I1"}
    assert "I11" not in rows  # one work
    assert "I12" not in rows  # two works
    assert "I13" not in rows  # company
    assert "I90" not in rows  # not in the region's country
    assert rows["I10"]["works"] == 3
    assert set(ELIGIBLE_TYPES) >= {rows[i]["type"] for i in rows}
    assert MIN_WORKS == 3


def test_ror_dump_gives_domains_and_homepage_is_second(country_root: Path) -> None:
    raw = country_root / "data/raw"
    (raw / "ror-v2.json").write_text(
        json.dumps(
            [
                {
                    "id": "https://ror.org/01abc",
                    "domains": ["niva.no"],
                    "links": [{"type": "website", "value": "https://www.niva.no/"}],
                }
            ]
        ),
        encoding="utf-8",
    )
    assert load_ror_domains(raw) == {
        "01abc": RorValues(domains=("niva.no",), websites=("https://www.niva.no/",))
    }
    institutions, _ = build_region(_norway(), country_root, GENERATED)
    niva = _rows(institutions)["I1"]
    assert niva["domains"] == ["niva.no"]
    assert niva["needs_domain"] is False
    assert _rows(institutions)["I10"]["needs_domain"] is True


def test_overrides_add_and_remove(country_root: Path) -> None:
    override = country_root / "regions/norway/ambassador_domains.csv"
    override.parent.mkdir(parents=True)
    override.write_text(
        "institution_id,domain,action,note\n"
        "I10,uni-nord.no,add,owner check\n"
        "I1,niva.no,add,\n"
        "I1,niva.no,remove,wrong domain\n",
        encoding="utf-8",
    )
    institutions, _ = build_region(_norway(), country_root, GENERATED)
    rows = _rows(institutions)
    assert rows["I10"]["domains"] == ["uni-nord.no"]
    assert rows["I10"]["needs_domain"] is False
    assert rows["I1"]["domains"] == []
    assert rows["I1"]["needs_domain"] is True


def test_institutions_are_sorted_by_works(country_root: Path) -> None:
    institutions, _ = build_region(_norway(), country_root, GENERATED)
    counts = [row["works"] for row in institutions["institutions"]]
    assert counts == sorted(counts, reverse=True)


def test_local_language_case_and_outputs_pass_validation(country_root: Path) -> None:
    institutions, cases = build_region(_norway(), country_root, GENERATED)
    assert validate_outputs(institutions, cases, "norway") == []
    language = [c for c in cases["cases"] if c["kind"] == "local_language_relevance"]
    assert [c["evidence"]["title"] for c in language] == ["Mikroplast i fjorden"]
    assert set(cases["counts"]) == set(CASE_KINDS)


def test_affiliation_signal_case_drops_contact_text(country_root: Path) -> None:
    _, cases = build_region(_norway(), country_root, GENERATED)
    region_cases = [c for c in cases["cases"] if c["kind"] == "institution_in_region"]
    foreign = [c for c in region_cases if c["evidence"]["institution_id"] == "I90"]
    assert len(foreign) == 1
    assert foreign[0]["current_value"] == "not in region"
    assert foreign[0]["evidence"]["affiliation_examples"] == ["Bergen, Norway"]
    assert 'affiliation mentions "Norway"' in foreign[0]["evidence"]["signals"]


def test_case_ids_are_stable_across_rebuilds(country_root: Path) -> None:
    first = build_region(_norway(), country_root, "2026-01-01T00:00:00Z")[1]
    second = build_region(_norway(), country_root, "2026-06-01T00:00:00Z")[1]
    assert [c["case_id"] for c in first["cases"]] == [c["case_id"] for c in second["cases"]]
    assert first["cases"][0]["case_id"].startswith("amb-")
    ids = {c["case_id"] for c in first["cases"]}
    assert len(ids) == len(first["cases"])


def test_outputs_have_no_people_abstracts_or_contacts(country_root: Path) -> None:
    institutions, cases = build_region(_norway(), country_root, GENERATED)
    text = json.dumps(institutions) + json.dumps(cases)
    assert "@" not in text
    assert '"abstract' not in text
    for key in ("orcid", "email", "author_name", "raw_author_name", "contact"):
        assert f'"{key}"' not in text
    assert validate_outputs(institutions, cases, "norway") == []


def test_validator_flags_forbidden_keys_and_bad_domains() -> None:
    institutions = {
        "schema": "amb-v1",
        "region": "norway",
        "institutions": [
            {
                "id": "I1",
                "name": "X",
                "type": "education",
                "works": 3,
                "domains": ["gmail.com"],
                "needs_domain": False,
                "acronyms": [],
                "aliases": [],
                "email": "a@b.no",
            }
        ],
    }
    cases = {"schema": "amb-cases-v1", "region": "norway", "cases": []}
    problems = validate_outputs(institutions, cases, "norway")
    assert any("forbidden key 'email'" in p for p in problems)
    assert any("bad domain" in p or "keys" in p for p in problems)


def test_registry_path_uses_ca_basis_and_raw_affiliation_only(tmp_path: Path) -> None:
    """Curated corpus: registry rows give the type; raw-affiliation-only institutions get a case."""
    region = Region(
        slug="california",
        name="California",
        tier="A",
        parent=None,
        status="active",
        predicate=Predicate(
            institution_registry="data/processed/institutions.parquet",
            institution_region_names=("California",),
            country_codes=("US",),
            ca_basis_values=("registry", "raw_affiliation"),
        ),
        site_data_dir="site/data/california",
    )
    (tmp_path / "data/processed/normalized").mkdir(parents=True)
    (tmp_path / "data/processed/global").mkdir(parents=True)
    pq.write_table(
        pa.table(
            {
                "openalex_id": ["I1", "I2"],
                "display_name": ["Uni West", "Other Place"],
                "ror_id": ["01abc", ""],
                "openalex_type": ["education", None],
                "country_code": ["US", "US"],
                "region": ["California", "Oregon"],
            }
        ),
        tmp_path / "data/processed/institutions.parquet",
    )
    rows = []
    for n in range(3):
        rows.append(
            {
                "work_id": f"W{n}",
                "institution_ids": ["I1"],
                "raw_affiliation": "Uni West, CA",
                "ca_basis": "registry",
            }
        )
    for n in range(3):
        rows.append(
            {
                "work_id": f"W{n + 10}",
                "institution_ids": ["I9"],
                "raw_affiliation": "Other Lab, California, USA",
                "ca_basis": "raw_affiliation",
            }
        )
    pq.write_table(
        pa.Table.from_pylist(rows),
        tmp_path / "data/processed/normalized/authorships.parquet",
    )
    pq.write_table(
        pa.table({"work_id": ["W0", "W10"], "title": ["A title", "Other title"]}),
        tmp_path / "data/processed/normalized/works.parquet",
    )
    pq.write_table(
        pa.table({"work_id": ["W0", "W10"], "language": ["en", "es"]}),
        tmp_path / "data/processed/global/works.parquet",
    )
    institutions, cases = build_region(region, tmp_path, GENERATED)
    assert [r["id"] for r in institutions["institutions"]] == ["I1"]
    assert institutions["institutions"][0]["type"] == "education"
    raw_only = [c for c in cases["cases"] if c["evidence"].get("institution_id") == "I9"]
    assert {c["kind"] for c in raw_only} == {"institution_in_region", "institution_type"}
    in_region = next(c for c in raw_only if c["kind"] == "institution_in_region")
    assert in_region["evidence"]["signals"] == ["matched only by raw affiliation"]
    assert in_region["evidence"]["affiliation_examples"] == ["Other Lab, California, USA"]
    language = [c for c in cases["cases"] if c["kind"] == "local_language_relevance"]
    assert [c["evidence"]["language"] for c in language] == ["es"]
    assert cases["counts"]["local_terms"] == 0


def test_inputs_absent_means_staleness_is_skipped(tmp_path: Path) -> None:
    assert inputs_present(_norway(), tmp_path) is False


# --- domain precedence, cache and the fetch mode (offline; the HTTP layer is faked) ----------

TODAY = "2026-01-02"


class _Logger:
    """Stands in for ApiCostLogger: only the totals the fetch guard reads."""

    def __init__(self, credits: str = "0") -> None:
        self.credits_total = Decimal(credits)
        self.cost_usd_total = Decimal(0)


class _Budget:
    def __init__(self, error: str | None = None) -> None:
        self.error = error

    def reserve_error(self, *, cost_usd: Decimal, credits: Decimal) -> str | None:
        return self.error


def test_domain_precedence_ror_then_homepage_then_website() -> None:
    ror = RorValues(domains=("ror.no",), websites=("https://site.no/",))
    assert resolve_domains(["https://home.no/"], ror, []) == ["ror.no"]
    assert resolve_domains(["https://www.home.no/"], RorValues(), []) == ["home.no"]
    assert resolve_domains([], RorValues(websites=("https://site.no/",)), []) == ["site.no"]
    # Groups are not merged: a usable ROR domain hides the homepage host.
    assert resolve_domains(["home.no"], RorValues(domains=("ror.no",)), []) == ["ror.no"]


def test_free_mail_in_a_group_falls_through_to_the_next_group() -> None:
    ror = RorValues(domains=("gmail.com",))
    assert resolve_domains(["https://home.no/"], ror, []) == ["home.no"]


def test_overrides_apply_after_precedence() -> None:
    ror = RorValues(domains=("ror.no",))
    overrides = [
        _override("remove", "ror.no"),
        _override("add", "owner.no"),
    ]
    assert resolve_domains([], ror, overrides) == ["owner.no"]


def _override(action: str, domain: str):
    from atlas.build.ambassadors import Override

    return Override(action, domain, "")


def _write_entry(root: Path, inst_id: str, entry: dict) -> None:
    folder = root / "data/interim/ambassador_domains"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{inst_id}.json").write_text(json.dumps(entry), encoding="utf-8")


def test_cached_ror_domains_feed_the_build(country_root: Path) -> None:
    _write_entry(
        country_root,
        "I1",
        {
            "institution_id": "I1",
            "openalex": {"fetched": TODAY, "found": True, "homepage_url": None, "ror": "01abc"},
            "ror": {
                "ror_id": "01abc",
                "fetched": TODAY,
                "found": True,
                "domains": ["niva.no"],
                "websites": [],
            },
        },
    )
    institutions, _ = build_region(_norway(), country_root, GENERATED)
    niva = _rows(institutions)["I1"]
    assert niva["domains"] == ["niva.no"]
    assert niva["needs_domain"] is False


def test_fetch_openalex_batches_by_100_and_reuses_the_cache(tmp_path: Path) -> None:
    ids = [f"I{n}" for n in range(1, 251)]
    urls: list[str] = []

    def fake_request(url: str, *, logger: object) -> dict:
        urls.append(url)
        batch = url.split("filter=openalex_id:")[1].split("&")[0].split("|")
        results = [
            {
                "id": f"https://openalex.org/{i}",
                "display_name": f"Inst {i}",
                "homepage_url": f"https://www.inst{i}.no/",
                "ror": None,
            }
            for i in batch
            if int(i[1:]) % 2 == 0
        ]
        return {"results": results}

    logger = _Logger()
    calls = fetch_openalex(
        ids, tmp_path, logger=logger, budget=_Budget(), request_json=fake_request, today=TODAY
    )
    assert calls == 3
    assert [len(u.split("filter=openalex_id:")[1].split("&")[0].split("|")) for u in urls] == [
        100,
        100,
        50,
    ]
    assert all("select=id,display_name,homepage_url,ror" in u for u in urls)
    assert all("per-page=100" in u for u in urls)
    cached = read_cache(tmp_path, ids)
    assert len(cached) == 250
    assert cached["I2"]["openalex"]["found"] is True
    assert cached["I2"]["openalex"]["fetched"] == TODAY
    assert cached["I1"]["openalex"]["found"] is False
    assert cached["I2"]["openalex"]["homepage_url"] == "https://www.instI2.no/"

    # A rerun reuses every cached record: no request at all.
    urls.clear()
    assert (
        fetch_openalex(
            ids, tmp_path, logger=logger, budget=_Budget(), request_json=fake_request, today=TODAY
        )
        == 0
    )
    assert urls == []


def test_fetch_ror_one_request_per_unique_id_with_one_second_pacing(tmp_path: Path) -> None:
    requested: list[str] = []
    slept: list[float] = []

    def fake_get(url: str) -> dict | None:
        requested.append(url)
        if url.endswith("/0notfound"):
            return None
        return {
            "id": url.rsplit("/", 1)[-1],
            "domains": ["ror-domain.no"],
            "links": [{"type": "website", "value": "https://www.ror-domain.no/"}],
        }

    ror_by_id = {"I1": "0abcdefgh", "I2": "0abcdefgh", "I3": "0notfound"}
    calls = fetch_ror(ror_by_id, tmp_path, get_json=fake_get, sleep=slept.append, today=TODAY)
    assert calls == 2
    assert requested == [
        "https://api.ror.org/v2/organizations/0abcdefgh",
        "https://api.ror.org/v2/organizations/0notfound",
    ]
    assert slept == [1.0]  # one pause between the two requests
    cached = read_cache(tmp_path, ror_by_id)
    assert cached["I1"]["ror"]["domains"] == ["ror-domain.no"]
    assert cached["I2"]["ror"]["domains"] == ["ror-domain.no"]
    assert cached["I3"]["ror"]["found"] is False
    assert cached["I1"]["ror"]["fetched"] == TODAY


def test_openalex_credit_cap_stops_before_the_call(tmp_path: Path) -> None:
    def must_not_call(url: str, *, logger: object) -> dict:
        raise AssertionError("no request may be made past the cap")

    with pytest.raises(FetchLimitError, match="credit cap"):
        fetch_openalex(
            ["I1"],
            tmp_path,
            logger=_Logger("20"),
            budget=_Budget(),
            request_json=must_not_call,
            today=TODAY,
        )


def test_daily_budget_guard_stops_before_the_call(tmp_path: Path) -> None:
    def must_not_call(url: str, *, logger: object) -> dict:
        raise AssertionError("no request may be made when the budget guard refuses")

    with pytest.raises(FetchLimitError, match="cost limit"):
        fetch_openalex(
            ["I1"],
            tmp_path,
            logger=_Logger(),
            budget=_Budget("OpenAlex cost limit"),
            request_json=must_not_call,
            today=TODAY,
        )


def test_missing_domain_cache_lists_unfetched_institutions(country_root: Path) -> None:
    corpus = load_corpus(_norway(), country_root)
    missing = missing_domain_cache(country_root, corpus)
    assert "I1" in missing and "I10" in missing  # nothing cached yet
    _write_entry(country_root, "I10", {"openalex": {"fetched": TODAY, "found": True, "ror": ""}})
    _write_entry(
        country_root, "I1", {"openalex": {"fetched": TODAY, "found": True, "ror": "01abc"}}
    )
    missing = missing_domain_cache(country_root, corpus)
    assert "I10" not in missing
    assert "I1" in missing  # its ROR id is known but the ROR record is not cached


def test_check_never_uses_the_network(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib.util
    import urllib.request

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("--check must not use the network")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_ambassador_data.py"
    spec = importlib.util.spec_from_file_location("build_ambassador_data", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.main(["--check", "--slug", "california"]) == 0
    with pytest.raises(SystemExit):
        module.main(["--check", "--fetch-domains"])


def test_acronyms_come_from_bracketed_names_in_raw_affiliations() -> None:
    raw = [
        "Norwegian Institute for Water Research (NIVA), Gaustadalleen 21, Oslo, Norway",
        "Department of Biology, Norwegian University of Science and Technology (NTNU), Trondheim",
        "Flanders Marine Institute (VLIZ), InnovOcean site, Ostend, Belgium",
    ]
    assert affiliation_acronyms(raw, "Norwegian Institute for Water Research") == {"NIVA"}
    assert affiliation_acronyms(raw, "Norwegian University of Science and Technology") == {"NTNU"}
    assert affiliation_acronyms(raw, "Flanders Marine Institute") == {"VLIZ"}
    # The name must match exactly: a different institution does not take the acronym.
    assert affiliation_acronyms(raw, "Norwegian Institute") == set()
    # Lower-case words in brackets are not acronyms.
    assert affiliation_acronyms(["Lab (see note), Oslo"], "Lab") == set()


def test_uc_campus_names_get_the_uc_alias() -> None:
    rules = load_alias_rules(Path(__file__).resolve().parents[1], "california")
    assert prefix_aliases("University of California, Davis", rules) == {"UC Davis"}
    assert prefix_aliases("University of California San Diego", rules) == set()
    assert prefix_aliases("Ghent University", rules) == set()
    assert load_alias_rules(Path(__file__).resolve().parents[1], "norway") == ()


def test_ror_names_keep_acronyms_aliases_and_labels_only() -> None:
    record = {
        "names": [
            {"value": "NIVA", "types": ["acronym"]},
            {"value": "Norwegian Institute for Water Research", "types": ["ror_display", "label"]},
            {"value": "Vannforsk", "types": ["alias"]},
            {"value": "Other", "types": ["ror_display"]},
            {"value": "", "types": ["alias"]},
        ]
    }
    assert ror_names(record) == [
        {"value": "NIVA", "types": ["acronym"]},
        {"value": "Norwegian Institute for Water Research", "types": ["label"]},
        {"value": "Vannforsk", "types": ["alias"]},
    ]


def test_validator_requires_acronym_and_alias_lists_of_strings() -> None:
    row = {
        "id": "I1",
        "name": "X",
        "type": "education",
        "works": 3,
        "domains": ["x.no"],
        "needs_domain": False,
        "acronyms": "NIVA",
        "aliases": [],
    }
    institutions = {"schema": "amb-v1", "region": "norway", "institutions": [row]}
    cases = {"schema": "amb-cases-v1", "region": "norway", "cases": []}
    problems = validate_outputs(institutions, cases, "norway")
    assert any("acronyms must be a list of strings" in p for p in problems)
