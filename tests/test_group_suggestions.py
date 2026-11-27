"""Wikidata group suggestions (GRP-ENRICH slice 1): matching, determinism, cache and --check.

All tests are offline: a fake client answers the batched lookups from a small in-memory
knowledge base, and the HTTP layer is replaced by a fake POST function.
"""

from __future__ import annotations

import importlib.util
import json
import re
import urllib.error
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build_group_suggestions.py"
TODAY = "2026-11-26"
TODAY_YEAR = 2026
ENTITY = "http://www.wikidata.org/entity/"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_group_suggestions", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bgs = _load()


class FakeClient:
    """Answers the WikidataClient lookups from a dict of items (see _item)."""

    def __init__(self, items: dict[str, dict[str, Any]], isos: dict[str, str] | None = None):
        self.items = items
        self.isos = isos or {}

    def domain_rows(self, hosts):
        wanted = set(hosts)
        return [
            (qid, web)
            for qid, item in sorted(self.items.items())
            for web in item.get("P856", [])
            if bgs._host(web) in wanted
        ]

    def label_rows(self, literals):
        wanted = set(literals)
        return [
            (qid, name)
            for qid, item in sorted(self.items.items())
            for name in item.get("names", [])
            if name in wanted
        ]

    def organisation_types(self, qids):
        return {q for q in qids if self.items.get(q, {}).get("org")}

    def values(self, prop, qids):
        out = {}
        for q in qids:
            if prop == "P297":
                if q in self.isos:
                    out[q] = [self.isos[q]]
                continue
            vals = self.items.get(q, {}).get(prop, [])
            if prop in ("P17", "P31"):
                vals = [ENTITY + v for v in vals]
            if vals:
                out[q] = list(vals)
        return out

    def english_labels(self, qids):
        return {q: self.items[q]["label"] for q in qids if self.items.get(q, {}).get("label")}


def _item(names=(), org=False, country=None, web=(), year=None, types=(), label=None):
    item: dict[str, Any] = {"names": list(names), "org": org}
    if country:
        item["P17"] = [country]
    if web:
        item["P856"] = list(web)
    if year:
        item["P571"] = [f"+{year}-01-01T00:00:00Z"]
    if types:
        item["P31"] = list(types)
    if label:
        item["label"] = label
    return item


def _rec(gid, name, country="US", url=None, alts=()):
    return {"group_id": gid, "name": name, "name_alt": list(alts), "country": country, "url": url}


KB = {
    "Q163740": _item(org=True, label="nonprofit organization"),
    "Q486972": _item(label="human settlement"),
    "Q1": _item(names=["Example Org"], web=["https://example.org/"], year=1999, types=["Q163740"]),
    "Q2": _item(names=["Green Coalition"], country="Q30", types=["Q163740"]),
    "Q3": _item(names=["Lake Town"], country="Q30", types=["Q486972"]),
    "Q4": _item(names=["Harbour Trust"], country="Q30", types=["Q163740"]),
    "Q5": _item(names=["Clean Seas"], country="Q30", types=["Q163740"]),
    "Q6": _item(names=["Clean Seas"], country="Q30", types=["Q163740"]),
    "Q7": _item(names=["Afro Group"], country="Q889", types=["Q163740"]),
    "Q8": _item(
        names=["Shared Name"], country="Q30", web=["https://shared.org/"], types=["Q163740"]
    ),
    "Q9": _item(names=["Fb Page"], web=["https://facebook.com/x"]),
}
ISOS = {"Q30": "US", "Q889": "AF", "Q40": "GB"}


def _build(records, items=KB, isos=ISOS):
    return bgs.build_groups(records, FakeClient(items, isos), TODAY_YEAR)


def test_domain_match_uses_registrable_domain_and_reports_fields():
    recs = [_rec("cg_a", "Example Org", "US", "https://www.example.org/about")]
    groups, stats = _build(recs)
    assert groups == {
        "cg_a": {
            "qid": "Q1",
            "match": "website",
            "website": "https://example.org/",
            "inception_year": 1999,
            "types": ["Q163740"],
            "type_labels": ["nonprofit organization"],
        }
    }
    assert stats["website"] == 1


def test_label_match_needs_roster_country_and_organisation_type():
    recs = [
        _rec("cg_ok", "Green Coalition", "US"),
        _rec("cg_country", "Harbour Trust", "GB"),  # item is US-registered (P17 Q30)
        _rec("cg_org", "Lake Town", "US"),  # item is not an organisation
    ]
    groups, _ = _build(recs)
    assert set(groups) == {"cg_ok"}
    assert groups["cg_ok"]["match"] == "label"
    assert groups["cg_ok"]["qid"] == "Q2"


def test_af_and_missing_country_never_label_match():
    recs = [_rec("cg_af", "Afro Group", "AF"), _rec("cg_none", "Afro Group", None)]
    groups, _ = _build(recs)
    assert groups == {}


def test_ambiguous_label_and_shared_items_are_dropped():
    # Two items carry the same English label: ambiguous, so no suggestion.
    groups, stats = _build([_rec("cg_clean", "Clean Seas", "US")])
    assert groups == {}
    assert stats["ambiguous_label"] == 1
    # Two groups on the same website both match Q8: both dropped.
    recs = [
        _rec("cg_s1", "Shared One", "US", "https://shared.org/a"),
        _rec("cg_s2", "Shared Two", "US", "https://www.shared.org/"),
    ]
    groups, stats = _build(recs)
    assert groups == {}
    assert stats["shared_item_dropped"] == 2


def test_social_host_is_skipped_for_website_matching():
    recs = [_rec("cg_fb", "Fb Page", "US", "https://facebook.com/x")]
    groups, _ = _build(recs)
    assert groups == {}


def test_output_is_deterministic_and_order_independent():
    recs = [
        _rec("cg_a", "Example Org", "US", "https://example.org/"),
        _rec("cg_ok", "Green Coalition", "US"),
    ]
    first = bgs.to_bytes(bgs.render(recs, FakeClient(KB, ISOS), None, TODAY)[0])
    second = bgs.to_bytes(bgs.render(list(reversed(recs)), FakeClient(KB, ISOS), None, TODAY)[0])
    assert first == second
    assert first.endswith(b"\n") and b"\r" not in first


def test_validate_catches_bad_qid_and_unknown_group():
    doc = {
        "schema": bgs.SCHEMA,
        "source": bgs.SOURCE,
        "retrieved_at": TODAY,
        "groups": {
            "cg_known": {
                "qid": "X12",
                "match": "website",
                "website": None,
                "inception_year": None,
                "types": [],
                "type_labels": [],
            },
            "cg_ghost": {
                "qid": "Q5",
                "match": "label",
                "website": None,
                "inception_year": None,
                "types": [],
                "type_labels": [],
            },
        },
    }
    errors = bgs.validate(doc, {"cg_known"}, TODAY_YEAR)
    assert any("qid must match" in e for e in errors)
    assert any("cg_ghost" in e and "not a roster group_id" in e for e in errors)
    assert bgs.validate(doc | {"groups": {}}, {"cg_known"}, TODAY_YEAR) == []


def test_validate_rejects_bad_year_and_website():
    item = {
        "qid": "Q1",
        "match": "website",
        "website": "ftp://x.org",
        "inception_year": 1700,
        "types": [],
        "type_labels": [],
    }
    doc = {
        "schema": bgs.SCHEMA,
        "source": bgs.SOURCE,
        "retrieved_at": TODAY,
        "groups": {"cg_a": item},
    }
    errors = bgs.validate(doc, {"cg_a"}, TODAY_YEAR)
    assert any("website" in e for e in errors)
    assert any("inception_year" in e for e in errors)


def test_retrieved_at_is_kept_when_groups_unchanged_and_moves_when_they_change():
    recs = [_rec("cg_ok", "Green Coalition", "US")]
    committed_doc, _ = bgs.render(recs, FakeClient(KB, ISOS), None, "2026-11-01")
    assert committed_doc["retrieved_at"] == "2026-11-01"
    same, _ = bgs.render(recs, FakeClient(KB, ISOS), committed_doc, TODAY)
    assert same["retrieved_at"] == "2026-11-01"
    changed, _ = bgs.render([], FakeClient(KB, ISOS), committed_doc, TODAY)
    assert changed["retrieved_at"] == TODAY
    assert changed["groups"] == {}


def test_client_caches_responses_and_offline_reports_a_miss(tmp_path):
    calls = []

    def post(query):
        calls.append(query)
        return {
            "results": {
                "bindings": [
                    {"item": {"value": ENTITY + "Q1"}, "web": {"value": "https://example.org/"}}
                ]
            }
        }

    client = bgs.WikidataClient(cache_dir=tmp_path, post=post, sleep=lambda s: None)
    first = client.domain_rows(["example.org"])
    again = bgs.WikidataClient(cache_dir=tmp_path, post=post, sleep=lambda s: None)
    assert again.domain_rows(["example.org"]) == first == [("Q1", "https://example.org/")]
    assert len(calls) == 1
    offline = bgs.WikidataClient(cache_dir=tmp_path, offline=True, post=post)
    with pytest.raises(bgs.CacheMiss):
        offline.domain_rows(["other.org"])


def test_domain_queries_are_batched_at_fifty_hosts(tmp_path):
    calls = []

    def post(query):
        calls.append(query)
        return {"results": {"bindings": []}}

    client = bgs.WikidataClient(cache_dir=tmp_path, post=post, sleep=lambda s: None)
    client.domain_rows([f"site{i}.org" for i in range(120)])
    assert len(calls) == 3


def test_rate_limit_is_retried_once_then_stops(tmp_path):
    sleeps = []

    def always_429(query):
        raise urllib.error.HTTPError(
            "https://query.wikidata.org/sparql", 429, "Too Many", None, None
        )

    client = bgs.WikidataClient(
        cache_dir=tmp_path, post=always_429, sleep=sleeps.append, clock=lambda: 1000.0
    )
    with pytest.raises(bgs.RateLimited):
        client.sparql("SELECT 1")
    assert 60 in sleeps and not list(tmp_path.glob("*.json"))


def test_check_passes_without_cache_and_fails_on_bad_file(tmp_path, monkeypatch):
    roster = tmp_path / "roster.json"
    roster.write_text(
        json.dumps({"records": [_rec("cg_a", "Example Org", "US")]}), encoding="utf-8"
    )
    out = tmp_path / "suggestions.json"
    monkeypatch.setattr(bgs, "ROSTER_PATH", roster)
    monkeypatch.setattr(bgs, "OUTPUT_PATH", out)
    monkeypatch.setattr(bgs, "CACHE_DIR", tmp_path / "no_cache")
    doc = {"schema": bgs.SCHEMA, "source": bgs.SOURCE, "retrieved_at": TODAY, "groups": {}}
    out.write_bytes(bgs.to_bytes(doc))
    assert bgs.main(["--check"]) == 0
    doc["groups"] = {
        "cg_a": {
            "qid": "bad",
            "match": "label",
            "website": None,
            "inception_year": None,
            "types": [],
            "type_labels": [],
        }
    }
    out.write_bytes(bgs.to_bytes(doc))
    assert bgs.main(["--check"]) == 1


def test_organisation_types_walks_parents_and_survives_cycles(tmp_path):
    edges = {"Q1": ["Q2"], "Q2": ["Q43229"], "Q3": ["Q5"], "Q5": ["Q3"]}

    def post(query):
        subjects = re.findall(r"wd:(Q\d+)", re.search(r"VALUES \?t \{ (.*?) \}", query).group(1))
        rows = [
            {"t": {"value": ENTITY + t}, "p": {"value": ENTITY + p}}
            for t in subjects
            for p in edges.get(t, [])
        ]
        return {"results": {"bindings": rows}}

    client = bgs.WikidataClient(cache_dir=tmp_path, post=post, sleep=lambda s: None)
    assert client.organisation_types(["Q1", "Q3"]) == {"Q1"}


def test_label_matches_need_organisation_type_labels() -> None:
    """Name matches skip places, vessels, elections and local government (lead review)."""
    assert bgs.label_types_ok(["nonprofit organization"])
    assert bgs.label_types_ok(["public university", "facility"])
    assert not bgs.label_types_ok(["municipality of Brazil"])
    assert not bgs.label_types_ok(["caravel", "ship replica"])
    assert not bgs.label_types_ok(["parish council", "organization"])
    assert not bgs.label_types_ok(["electoral list"])
    assert not bgs.label_types_ok(["facility"])
    assert not bgs.label_types_ok([])
