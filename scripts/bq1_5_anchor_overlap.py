"""BQ-1.5 anchor overlap: which works found by independent routes does the v3.1 query retrieve?

Each anchor set is a set of relevant works that reached the Atlas by a route that did not apply
the v3.1 OpenAlex search, or that comes from an outside list. A set is probed by filtering
OpenAlex to its IDs (or DOIs) and combining the filter with the v3.1 title-and-abstract search,
the v3.1 type exclusions (as in ``fetch_trend_global.build_url``), no California scope and
``select=id``. The result is an anchor-overlap probe with a Wilson 95% interval for each set.
Sets are not random samples and are never pooled.

Route independence is read from ``source_run_id`` families (``atlas.analytics.denominators``).
Sets whose route applied the v3.1 search are listed as excluded and make no calls.

Usage:
    py -3.14 scripts/bq1_5_anchor_overlap.py            # live: reuse cache, fetch the rest
    py -3.14 scripts/bq1_5_anchor_overlap.py --offline  # rebuild the JSON from the cache only
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import urllib.parse
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.analytics.denominators import QUERY_ROUTES, route_family  # noqa: E402
from atlas.ingest.europepmc_audit import normalize_doi  # noqa: E402
from atlas.ingest.openalex import (  # noqa: E402
    OPENALEX_BASE,
    _request_json,
    compact_openalex_id,
    load_openalex_key,
)
from atlas.query import load_query_config, openalex_filter, type_filters  # noqa: E402
from atlas.regions.scope import region_data_dir  # noqa: E402
from atlas.util.budget import daily_logged_usage, resolve_openalex_budget  # noqa: E402
from atlas.util.cost import ApiCostLogger  # noqa: E402

SCHEMA_VERSION = "bq1_5_anchor_overlap.v1"
CONFIG = ROOT / "config" / "queries.yml"
WORKS_RAW = ROOT / "data" / "interim" / "works_raw.parquet"
NORMALIZED_WORKS = ROOT / "data" / "processed" / "normalized" / "works.parquet"
SITE_INDEX = region_data_dir() / "index.json"
PUBMED_PAYLOAD = region_data_dir() / "pubmed_coverage.json"
PUBMED_R1 = ROOT / "data" / "interim" / "pubmed" / "r1_california_pmids.csv"
WORK_RELEVANCE = ROOT / "curation" / "work_relevance.csv"
DATACITE_REVIEW = ROOT / "docs" / "S7_4_REAL_REVIEW.csv"
FIXTURE = ROOT / "tests" / "fixtures" / "s1_5_known_relevant.json"
CACHE_DIR = ROOT / "data" / "interim" / "bq1_5_anchor_overlap"
USAGE_LOG = ROOT / "data" / "logs" / "api_usage.jsonl"
OUT_JSON = ROOT / "docs" / "api_notes" / "bq1_5_anchor_overlap.json"

INPUT_FILES = {
    "config/queries.yml": CONFIG,
    "data/interim/works_raw.parquet": WORKS_RAW,
    "data/processed/normalized/works.parquet": NORMALIZED_WORKS,
    "site/data/california/index.json": SITE_INDEX,
    "site/data/california/pubmed_coverage.json": PUBMED_PAYLOAD,
    "data/interim/pubmed/r1_california_pmids.csv": PUBMED_R1,
    "curation/work_relevance.csv": WORK_RELEVANCE,
    "docs/S7_4_REAL_REVIEW.csv": DATACITE_REVIEW,
    "tests/fixtures/s1_5_known_relevant.json": FIXTURE,
}

BATCH_SIZE = 50
PER_PAGE = 50
PROBE_SELECT = "id"
LOOKUP_SELECT = "id,doi,title,type"
CREDIT_CAP = 150.0
# Reserved per call before it is made (config/budget.yml planned_request_reserve_credits).
RESERVE_CREDITS = 10.0
MAX_HTTP_ATTEMPTS = 3
MAX_URL_CHARS = 8000
WILSON_Z = 1.959963984540054
DOI_ONLY_ROUTES = frozenset({"orcid-doi-ingest", "ror-researcher-doi-ingest"})
OWNER_STATES = frozenset({"confirmed", "changed"})


class FetchError(RuntimeError):
    """A request, validation or budget failure: nothing is written."""


class CacheMiss(FetchError):
    """An offline rebuild needs a response that is not cached."""


class CreditCapError(FetchError):
    """The next call would take this analysis past the credit cap."""


# ---------------------------------------------------------------- routes and statistics


def route_kind(source_run_id: str) -> str:
    """``doi_only`` for ORCID/ROR DOI routes, ``query`` for routes that applied the v3.1 search."""

    family = route_family(source_run_id or "")
    if family in DOI_ONLY_ROUTES:
        return "doi_only"
    if family in QUERY_ROUTES:
        return "query"
    return "other"


def wilson_interval(successes: int, n: int) -> tuple[float | None, float | None]:
    """Wilson score interval at 95 percent, rounded to four places; None when n is zero."""

    if n <= 0:
        return None, None
    if not 0 <= successes <= n:
        raise ValueError(f"successes {successes} outside 0..{n}")
    z2 = WILSON_Z * WILSON_Z
    p = successes / n
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = WILSON_Z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


def batches(items: Sequence[str], size: int = BATCH_SIZE) -> list[list[str]]:
    """Split into consecutive batches of at most ``size`` (1 to 50) values."""

    if not 1 <= size <= BATCH_SIZE:
        raise ValueError(f"batch size must be 1 to {BATCH_SIZE}")
    values = list(items)
    return [values[start : start + size] for start in range(0, len(values), size)]


# ---------------------------------------------------------------- OpenAlex request text


def id_filter(ids: Sequence[str]) -> str:
    if not 1 <= len(ids) <= BATCH_SIZE:
        raise ValueError(f"1 to {BATCH_SIZE} OpenAlex IDs per call, got {len(ids)}")
    return "ids.openalex:" + "|".join(ids)


def doi_filter(dois: Sequence[str]) -> str:
    if not 1 <= len(dois) <= BATCH_SIZE:
        raise ValueError(f"1 to {BATCH_SIZE} DOIs per call, got {len(dois)}")
    return "doi:" + "|".join(f"https://doi.org/{doi}" for doi in dois)


def _works_url(filters: Sequence[str], select: str) -> str:
    params = {"filter": ",".join(filters), "select": select, "per-page": PER_PAGE}
    url = f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"
    if len(url) > MAX_URL_CHARS:
        raise ValueError(f"request URL is {len(url)} characters; limit is {MAX_URL_CHARS}")
    return url


def probe_url(config: Mapping[str, Any], anchor_filter: str) -> str:
    """The v3.1 search, its type exclusions, and the anchor filter; the order matches build_url."""

    return _works_url([openalex_filter(config), *type_filters(config), anchor_filter], PROBE_SELECT)


def lookup_url(anchor_filter: str) -> str:
    """Anchor filter alone (no search, no type filter): shows whether each anchor exists."""

    return _works_url([anchor_filter], LOOKUP_SELECT)


def query_fingerprint(config: Mapping[str, Any]) -> str:
    text = "|".join([openalex_filter(config), *type_filters(config)])
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- inputs


@dataclass
class Inputs:
    raw_rows: list[dict[str, str]]
    index: dict[str, dict[str, Any]]
    normalized: list[dict[str, Any]]
    relevance: dict[str, dict[str, str]]
    pubmed_r1: list[dict[str, str]]
    pubmed_found_published: int | None
    datacite: list[dict[str, str]]
    fixture: list[dict[str, Any]]
    input_sha256: dict[str, str] = field(default_factory=dict)


def _sha256(path: Path) -> str:
    # CRLF folded to LF so a Windows checkout and a CI checkout hash the same.
    data = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def load_inputs() -> Inputs:
    raw_rows = [
        {
            "openalex_id": compact_openalex_id(row["openalex_id"]),
            "source_run_id": row["source_run_id"] or "",
        }
        for row in pq.read_table(WORKS_RAW, columns=["openalex_id", "source_run_id"]).to_pylist()
    ]
    index = {
        work["work_id"]: work
        for work in json.loads(SITE_INDEX.read_text(encoding="utf-8"))["works"]
    }
    normalized = pq.read_table(NORMALIZED_WORKS, columns=["work_id", "doi", "pmid"]).to_pylist()
    relevance = {compact_openalex_id(row["work_id"]): row for row in _read_csv(WORK_RELEVANCE)}
    payload = json.loads(PUBMED_PAYLOAD.read_text(encoding="utf-8"))
    datacite = [
        {
            "doi": normalize_doi(row["dataset_doi"]),
            "title": row["title"],
            "resource_type": row["resource_type"],
        }
        for row in _read_csv(DATACITE_REVIEW)
        if row["agent_review_label"].strip() == "positive"
    ]
    return Inputs(
        raw_rows=raw_rows,
        index=index,
        normalized=normalized,
        relevance=relevance,
        pubmed_r1=_read_csv(PUBMED_R1),
        pubmed_found_published=payload["reference_sets"]["r1"].get("found_published"),
        datacite=datacite,
        fixture=json.loads(FIXTURE.read_text(encoding="utf-8")),
        input_sha256={name: _sha256(path) for name, path in INPUT_FILES.items()},
    )


# ---------------------------------------------------------------- anchor sets


@dataclass
class Anchor:
    openalex_id: str | None
    doi: str | None
    title: str
    work_type: str | None = None
    source_type: str | None = None
    tier: str | None = None
    relevance_group: str | None = None
    entered_via_query_route: bool | None = None


@dataclass
class AnchorSet:
    set_id: str
    route: str
    independence: str
    verdict: str
    anchors: list[Anchor] = field(default_factory=list)
    lookup_by: str | None = None  # "openalex" or "doi": resolve anchors before probing
    probe_by: str | None = None  # None: not probed
    excluded_reason: str | None = None
    subset_keys: dict[str, Callable[[Anchor], str]] = field(default_factory=dict)
    candidate_info: dict[str, Any] = field(default_factory=dict)


def relevance_group(row: Mapping[str, str] | None) -> str:
    """Where an anchor's plastic_related=true came from (precedence in export_site)."""

    if row is None:
        return "rule_only"
    if row.get("owner_review") in OWNER_STATES:
        return "owner_reviewed"
    if str(row.get("plastic_related", "")).strip().lower() == "true":
        return "model_true"
    return "rule_kept_after_model_false"


def _pmid(value: object) -> str:
    tail = str(value or "").strip().rstrip("/").rsplit("/", 1)[-1]
    return tail if tail.isdigit() else ""


def _candidate_info(inputs: Inputs, family: str) -> dict[str, Any]:
    rows = [row for row in inputs.raw_rows if route_family(row["source_run_id"]) == family]
    ids = {row["openalex_id"] for row in rows}
    published = [wid for wid in ids if wid in inputs.index]
    plastic = [wid for wid in published if inputs.index[wid].get("plastic_related") is True]
    return {
        "raw_rows": len(rows),
        "unique_openalex_ids": len(ids),
        "published": len(published),
        "published_plastic_related": len(plastic),
    }


def _orcid_set(inputs: Inputs) -> AnchorSet:
    ids = sorted(
        {
            row["openalex_id"]
            for row in inputs.raw_rows
            if route_kind(row["source_run_id"]) == "doi_only"
        }
    )
    anchors: list[Anchor] = []
    for wid in ids:
        work = inputs.index.get(wid)
        if work is None or work.get("plastic_related") is not True:
            continue
        anchors.append(
            Anchor(
                openalex_id=wid,
                doi=None,
                title=str(work.get("title") or ""),
                work_type=work.get("type"),
                tier=work.get("plastic_tier") or None,
                relevance_group=relevance_group(inputs.relevance.get(wid)),
            )
        )
    groups = defaultdict(int)
    for anchor in anchors:
        groups[anchor.relevance_group or ""] += 1
    independence = (
        "Route: independent of the search. These works were fetched by DOI only, with the v3.1 "
        "search switched off (scripts/ingest_orcid_dois.py, with_query=False). Selection: not "
        "independent of the vocabulary. Before merge each record had to pass a local rule built "
        "from the v3.1 core, qualified and exclusion terms plus tier-2 chemical terms "
        "(passes_query), so every anchor matches those terms. Of the "
        f"{len(anchors)} anchors, {groups['model_true']} are judged plastic-related by the "
        f"assisted model, {groups['owner_reviewed']} by owner review, "
        f"{groups['rule_kept_after_model_false']} are kept by the chemical-term rule after the "
        "model said not plastic-related, and "
        f"{groups['rule_only']} rest on the rule alone."
    )
    return AnchorSet(
        set_id="orcid_ror_doi",
        route=(
            "ORCID DOI ingest (source_run_id family orcid-doi-ingest) and ROR researcher DOI "
            "ingest (ror-researcher-doi-ingest); published and plastic_related true in the index"
        ),
        independence=independence,
        verdict=(
            "route independent of the search, but selection used the same term list: a "
            "consistency check, not independent coverage"
        ),
        anchors=anchors,
        probe_by="openalex",
        subset_keys={
            "by_relevance_group": lambda a: a.relevance_group or "",
            "by_plastic_tier": lambda a: a.tier or "",
        },
    )


def _excluded_query_route(
    inputs: Inputs, set_id: str, family: str, route: str, independence: str
) -> AnchorSet:
    return AnchorSet(
        set_id=set_id,
        route=route,
        independence=independence,
        verdict="not independent: the route applied the v3.1 query; skipped",
        excluded_reason="route applied the v3.1 query",
        candidate_info=_candidate_info(inputs, family),
    )


def _datacite_set(inputs: Inputs) -> AnchorSet:
    anchors = [
        Anchor(
            openalex_id=None,
            doi=row["doi"],
            title=row["title"],
            source_type=row["resource_type"],
        )
        for row in sorted(inputs.datacite, key=lambda row: row["doi"])
    ]
    return AnchorSet(
        set_id="datacite_positive",
        route=(
            "DataCite metadata search, S7.4 candidate review (docs/S7_4_REAL_REVIEW.csv, "
            "agent_review_label positive)"
        ),
        independence=(
            "Route: independent of OpenAlex (DataCite search). Relevance: agent text review of "
            "DataCite metadata and landing-page excerpts, not owner labels. The positives are "
            "DataCite Dataset records (five DOIs, three projects), not articles, and none has an "
            "Atlas work ID. DOIs are resolved in OpenAlex first; unresolved DOIs are listed and "
            "not counted."
        ),
        verdict=(
            "outside source, but dataset records rather than articles; reported beside the "
            "article sets, not pooled"
        ),
        anchors=anchors,
        lookup_by="doi",
        probe_by="doi",
    )


def _pubmed_set(inputs: Inputs) -> AnchorSet:
    pmid_to_work: dict[str, str] = {}
    doi_to_work: dict[str, str] = {}
    for row in inputs.normalized:
        wid = compact_openalex_id(row["work_id"])
        pmid = _pmid(row.get("pmid"))
        if pmid:
            pmid_to_work.setdefault(pmid, wid)
        doi = normalize_doi(row.get("doi"))
        if doi:
            doi_to_work.setdefault(doi, wid)
    query_entry: dict[str, bool] = defaultdict(bool)
    for row in inputs.raw_rows:
        if route_kind(row["source_run_id"]) == "query":
            query_entry[row["openalex_id"]] = True
    found: dict[str, None] = {}
    for row in inputs.pubmed_r1:
        wid = pmid_to_work.get(_pmid(row["pmid"]))
        if wid is None:
            wid = doi_to_work.get(normalize_doi(row["doi"]))
        if wid is not None and wid in inputs.index:
            found[wid] = None
    if inputs.pubmed_found_published is not None and inputs.pubmed_found_published != len(found):
        raise ValueError(
            f"PubMed join gives {len(found)} published works; the BQ-S9 payload says "
            f"{inputs.pubmed_found_published}"
        )
    anchors = []
    for wid in sorted(found):
        work = inputs.index[wid]
        anchors.append(
            Anchor(
                openalex_id=wid,
                doi=None,
                title=str(work.get("title") or ""),
                work_type=work.get("type"),
                tier=work.get("plastic_tier") or None,
                entered_via_query_route=query_entry[wid],
            )
        )
    via_query = sum(1 for anchor in anchors if anchor.entered_via_query_route)
    return AnchorSet(
        set_id="pubmed_r1_atlas",
        route=(
            'PubMed R1, "Microplastics"[MeSH Terms] AND California[ad] (BQ-S9, '
            "data/interim/pubmed/r1_california_pmids.csv), restricted to published Atlas works "
            "(PMID join, then DOI)"
        ),
        independence=(
            "Relevance: independent of the search (PubMed MeSH indexing). Membership: not "
            f"independent. Each anchor is a published Atlas work, and {via_query} of "
            f"{len(anchors)} entered the Atlas through the v3.1 query route, so membership in "
            "this set reflects the query. The probe checks consistency with the query, not an "
            "independent overlap."
        ),
        verdict="partly independent: membership conditioned on the query route (see subsets)",
        anchors=anchors,
        probe_by="openalex",
        subset_keys={
            "by_entry_route": lambda a: (
                "entered_via_v31_query_route"
                if a.entered_via_query_route
                else "not_via_v31_query_route"
            ),
        },
    )


def _fixture_set(inputs: Inputs) -> AnchorSet:
    anchors = [
        Anchor(
            openalex_id=compact_openalex_id(row["id"]),
            doi=None,
            title=str(row.get("title") or ""),
        )
        for row in inputs.fixture
    ]
    return AnchorSet(
        set_id="fixture_s1_5",
        route="tests/fixtures/s1_5_known_relevant.json (four literature-informed works)",
        independence=(
            "Outside list. The four works were chosen from the literature (see the basis field in "
            "the fixture), not through any Atlas route, so they do not depend on the query. They "
            "are microplastics works, not California-scoped. n = 4, so the interval is very wide."
        ),
        verdict="independent outside list; n = 4",
        anchors=anchors,
        lookup_by="openalex",
        probe_by="openalex",
    )


def build_sets(inputs: Inputs) -> list[AnchorSet]:
    """The seven BQ-1.5 sets in brief order. Pure: reads only ``inputs``."""

    return [
        _orcid_set(inputs),
        _excluded_query_route(
            inputs,
            "escholarship",
            "escholarship-ingest",
            "eScholarship ingest (escholarship-ingest)",
            (
                "Not independent. The candidates are OpenAlex records fetched with a location "
                "filter, the v3.1 search and the type exclusions (scripts/audit_escholarship_"
                "openalex.py); the ingest merges only those records (scripts/ingest_escholarship_"
                "works.py)."
            ),
        ),
        _excluded_query_route(
            inputs,
            "europepmc_audit",
            "europepmc-audit",
            "Europe PMC audit (europepmc-audit): DOI list resolved in OpenAlex",
            (
                "Not independent. The DOI lookups applied the v3.1 search: build_doi_url "
                "defaults to with_query=True (src/atlas/ingest/europepmc_audit.py), so only works "
                "that matched the query were merged. The Europe PMC benchmark is an outside list, "
                "but this route did not reach the Atlas independently, so it is not probed here."
            ),
        ),
        _datacite_set(inputs),
        _pubmed_set(inputs),
        _fixture_set(inputs),
        AnchorSet(
            set_id="plastiverse_overview",
            route="plastiverse.live overview page",
            independence=(
                "Not independent and not probed: the overview is the Atlas's own published output, "
                "built from the corpus that the query populates, so it cannot test the query "
                "against an outside source."
            ),
            verdict="not independent; skipped",
            excluded_reason="Atlas's own output",
        ),
    ]


# ---------------------------------------------------------------- calls


@dataclass(frozen=True)
class Call:
    set_id: str
    kind: str  # "lookup" (no search) or "probe" (v3.1 search)
    url: str
    n_keys: int


def _keys(anchor_set: AnchorSet, by: str) -> list[str]:
    if by == "doi":
        return [anchor.doi or "" for anchor in anchor_set.anchors]
    return [anchor.openalex_id or "" for anchor in anchor_set.anchors]


def _anchor_filter(by: str, keys: Sequence[str]) -> str:
    return doi_filter(keys) if by == "doi" else id_filter(keys)


def planned_calls(sets: Sequence[AnchorSet], config: Mapping[str, Any]) -> list[Call]:
    calls: list[Call] = []
    for anchor_set in sets:
        if anchor_set.probe_by is None:
            continue
        if anchor_set.lookup_by:
            for keys in batches(_keys(anchor_set, anchor_set.lookup_by)):
                url = lookup_url(_anchor_filter(anchor_set.lookup_by, keys))
                calls.append(Call(anchor_set.set_id, "lookup", url, len(keys)))
        for keys in batches(_keys(anchor_set, anchor_set.probe_by)):
            url = probe_url(config, _anchor_filter(anchor_set.probe_by, keys))
            calls.append(Call(anchor_set.set_id, "probe", url, len(keys)))
    return calls


def _digest(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


class CallCache:
    """One JSON file per request, named by set, kind and URL digest. Offline never calls out."""

    def __init__(self, directory: Path, *, offline: bool, usage_log: Path = USAGE_LOG) -> None:
        self.directory = Path(directory)
        self.offline = offline
        self.usage_log = Path(usage_log)

    def path(self, call: Call) -> Path:
        return self.directory / f"{call.set_id}_{call.kind}_{_digest(call.url)[:16]}.json"

    def load(self, call: Call) -> dict[str, Any] | None:
        path = self.path(call)
        if not path.exists():
            return None
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("url_sha256") != _digest(call.url):
            raise FetchError(f"cache file {path.name} does not match its URL")
        return record

    def write(
        self, call: Call, *, body: Mapping[str, Any], credits: float, fetched_at: str
    ) -> dict[str, Any]:
        record = {
            "schema_version": "bq1_5_call.v1",
            "set_id": call.set_id,
            "kind": call.kind,
            "n_keys": call.n_keys,
            "url": call.url,
            "url_sha256": _digest(call.url),
            "fetched_at": fetched_at,
            "credits": credits,
            "body": body,
        }
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path(call)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
        return record

    def fetch(self, call: Call) -> dict[str, Any]:
        """One budgeted request, the same sequence as fetch_trend_global.fetch."""

        budget = resolve_openalex_budget()
        prior_cost, prior_credits = daily_logged_usage(
            self.usage_log, cost_per_credit_usd=budget.cost_per_credit_usd
        )
        error = budget.reserve_error(cost_usd=prior_cost, credits=prior_credits)
        if error:
            raise FetchError(f"budget guard: {error}")
        load_openalex_key()
        fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
        try:
            with ApiCostLogger("bq1-5-anchor-overlap-" + fetched_at, self.usage_log) as logger:
                body = _request_json(call.url, logger=logger, attempts=MAX_HTTP_ATTEMPTS)
                credits = float(logger.request_metrics[-1]["credits"])
        except Exception as exc:  # OpenAlex errors, usage-metadata errors, network errors
            raise FetchError(f"OpenAlex request failed: {exc}") from exc
        results = body.get("results")
        count = (body.get("meta") or {}).get("count")
        if not isinstance(results, list):
            raise FetchError(f"{call.set_id} {call.kind}: response has no results list")
        if isinstance(count, int) and count > len(results):
            raise FetchError(f"{call.set_id} {call.kind}: response is paged; batch incomplete")
        return self.write(call, body=body, credits=credits, fetched_at=fetched_at)


def run_calls(calls: Sequence[Call], cache: CallCache) -> dict[str, dict[str, Any]]:
    """Cached responses first; then new calls, stopping before the credit cap would be passed."""

    records: dict[str, dict[str, Any]] = {}
    for call in calls:
        if call.url in records:
            continue
        cached = cache.load(call)
        if cached is not None:
            records[call.url] = cached
    spent = sum(record["credits"] for record in records.values())
    for call in calls:
        if call.url in records:
            continue
        if cache.offline:
            raise CacheMiss(f"offline: no cached response for {call.set_id} {call.kind}")
        if spent + RESERVE_CREDITS > CREDIT_CAP:
            raise CreditCapError(
                f"stopping before {call.set_id} {call.kind}: {spent:g} credits used, "
                f"cap {CREDIT_CAP:g}"
            )
        record = cache.fetch(call)
        records[call.url] = record
        spent += record["credits"]
    return records


# ---------------------------------------------------------------- scoring


def miss_reason(anchor: Anchor, config: Mapping[str, Any]) -> str:
    """A title-level hint only: the abstract and the index are not checked here."""

    text = anchor.title.lower()
    if anchor.work_type and anchor.work_type in set(config.get("exclude_types") or []):
        return f"type '{anchor.work_type}' is removed by the v3.1 type filter"
    for term in config.get("exclusions") or []:
        if str(term).lower() in text:
            return f"title has the exclusion phrase '{term}'"
    core = any(str(term).lower() in text for term in config["core_terms"])
    qualified = any(
        str(item["term"]).lower() in text
        and any(str(context).lower() in text for context in item["any_context"])
        for item in config.get("qualified_terms") or []
    )
    if core or qualified:
        return "title matches a v3.1 term but was not returned; cause not visible in title"
    if anchor.tier == "chemicals-in-plastics":
        return "matched on a tier-2 chemical term, which v3.1 does not search"
    return "no v3.1 core or qualified term in title (abstract not checked)"


def _summary(anchors: Sequence[Anchor], retrieved: set[str]) -> dict[str, Any]:
    n = len(anchors)
    hits = sum(1 for anchor in anchors if anchor.openalex_id in retrieved)
    low, high = wilson_interval(hits, n)
    return {
        "n_anchors": n,
        "n_retrieved_by_v31": hits,
        "share": round(hits / n, 4) if n else None,
        "wilson_low": low,
        "wilson_high": high,
    }


def _subsets(
    anchor_set: AnchorSet, anchors: Sequence[Anchor], retrieved: set[str]
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name, key_of in anchor_set.subset_keys.items():
        groups: dict[str, list[Anchor]] = defaultdict(list)
        for anchor in anchors:
            groups[key_of(anchor)].append(anchor)
        out[name] = {key: _summary(group, retrieved) for key, group in sorted(groups.items())}
    return out


def resolve_anchors(
    anchor_set: AnchorSet, lookup_bodies: Sequence[Mapping[str, Any]]
) -> tuple[list[Anchor], list[str]]:
    """Attach OpenAlex IDs (and types) to anchors found by lookup; return (resolved, unresolved)."""

    if not anchor_set.lookup_by:
        return sorted(anchor_set.anchors, key=lambda a: a.openalex_id or ""), []
    found: dict[str, dict[str, Any]] = {}
    for body in lookup_bodies:
        for work in body.get("results") or []:
            key = normalize_doi(work.get("doi")) if anchor_set.lookup_by == "doi" else ""
            if anchor_set.lookup_by == "openalex":
                key = compact_openalex_id(work.get("id"))
            if key and key not in found:
                found[key] = work
    resolved: list[Anchor] = []
    unresolved: list[str] = []
    for anchor in anchor_set.anchors:
        key = anchor.doi if anchor_set.lookup_by == "doi" else anchor.openalex_id
        work = found.get(key or "")
        if work is None:
            unresolved.append(key or "")
            continue
        resolved.append(
            replace(
                anchor,
                openalex_id=compact_openalex_id(work.get("id")),
                work_type=work.get("type") or anchor.work_type,
            )
        )
    return sorted(resolved, key=lambda a: a.openalex_id or ""), unresolved


def _miss_rows(anchors: Sequence[Anchor], retrieved: set[str], config: Mapping[str, Any]) -> list:
    return [
        {
            "id": anchor.openalex_id,
            "doi": anchor.doi,
            "title": anchor.title,
            "type": anchor.work_type,
            "reason": miss_reason(anchor, config),
        }
        for anchor in anchors
        if anchor.openalex_id not in retrieved
    ]


def _call_rows(calls: Sequence[Call], records: Mapping[str, Mapping[str, Any]]) -> list[dict]:
    return [
        {
            "kind": call.kind,
            "n_keys": call.n_keys,
            "url_sha256": _digest(call.url)[:16],
            "fetched_at": records[call.url]["fetched_at"],
            "credits": records[call.url]["credits"],
        }
        for call in calls
    ]


def _probed_payload(
    anchor_set: AnchorSet,
    calls: Sequence[Call],
    records: Mapping[str, Mapping[str, Any]],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    lookups = [records[c.url]["body"] for c in calls if c.kind == "lookup"]
    probe_ids: set[str] = set()
    for call in calls:
        if call.kind != "probe":
            continue
        for work in records[call.url]["body"].get("results") or []:
            probe_ids.add(compact_openalex_id(work.get("id")))
    anchors, unresolved = resolve_anchors(anchor_set, lookups)
    retrieved = {a.openalex_id for a in anchors if a.openalex_id in probe_ids}
    summary = _summary(anchors, retrieved)
    fetched = [records[c.url]["fetched_at"] for c in calls]
    return {
        "set_id": anchor_set.set_id,
        "status": "probed",
        "route": anchor_set.route,
        "independence": anchor_set.independence,
        "verdict": anchor_set.verdict,
        "anchor_key": anchor_set.probe_by,
        "n_candidates": len(anchor_set.anchors),
        **summary,
        "missed_ids": [a.openalex_id for a in anchors if a.openalex_id not in retrieved],
        "misses": _miss_rows(anchors, retrieved, config),
        "unresolved_in_openalex": unresolved,
        "subsets": _subsets(anchor_set, anchors, retrieved),
        "fetched_at": max(fetched) if fetched else None,
        "credits": round(sum(records[c.url]["credits"] for c in calls), 4),
        "calls": _call_rows(calls, records),
    }


def _excluded_payload(anchor_set: AnchorSet) -> dict[str, Any]:
    return {
        "set_id": anchor_set.set_id,
        "status": "excluded",
        "route": anchor_set.route,
        "independence": anchor_set.independence,
        "verdict": anchor_set.verdict,
        "excluded_reason": anchor_set.excluded_reason,
        "n_anchors": None,
        "n_retrieved_by_v31": None,
        "share": None,
        "wilson_low": None,
        "wilson_high": None,
        "missed_ids": None,
        "misses": None,
        "candidate_info": anchor_set.candidate_info or None,
        "fetched_at": None,
        "credits": 0,
        "calls": [],
    }


def build_payload(
    inputs: Inputs,
    config: Mapping[str, Any],
    sets: Sequence[AnchorSet],
    records: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """The JSON document. Deterministic: every timestamp and credit comes from the cached calls."""

    calls = planned_calls(sets, config)
    out_sets = []
    for anchor_set in sets:
        if anchor_set.probe_by is None:
            out_sets.append(_excluded_payload(anchor_set))
            continue
        own = [c for c in calls if c.set_id == anchor_set.set_id]
        out_sets.append(_probed_payload(anchor_set, own, records, config))
    unique_calls = {call.url: records[call.url]["credits"] for call in calls}
    return {
        "schema_version": SCHEMA_VERSION,
        "query_version": config["version"],
        "query_fingerprint_sha256": query_fingerprint(config),
        "query_search_scope": "title_and_abstract, no California scope",
        "type_filters": type_filters(config),
        "probe": {
            "select": PROBE_SELECT,
            "per_page": PER_PAGE,
            "batch_size": BATCH_SIZE,
            "reserved_credits_per_call": RESERVE_CREDITS,
        },
        "interval": {"method": "Wilson score", "level": 0.95, "z": round(WILSON_Z, 6)},
        "credit_cap": CREDIT_CAP,
        "credits_total": round(sum(unique_calls.values()), 4),
        "calls_total": len(unique_calls),
        "input_sha256": inputs.input_sha256,
        "caveats": [
            "Anchor sets are not random samples of any population. They are the relevant works "
            "that an independent route reached, or an outside list.",
            "An overlap is a probe of the v3.1 search on those works. It is not an estimate of "
            "how many relevant works the query finds.",
            "A miss can reflect scope (for example tier-2 chemical terms, which v3.1 does not "
            "search) or OpenAlex matching. The title-level reason is only a hint.",
            "Each probe asks OpenAlex only about the anchors listed in that call. It does not "
            "scan the corpus.",
            "Sets are reported separately and never pooled.",
        ],
        "sets": out_sets,
    }


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--offline",
        action="store_true",
        help="rebuild the JSON from cached responses only; no network",
    )
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    args = parser.parse_args(argv)

    config = load_query_config(CONFIG)
    inputs = load_inputs()
    sets = build_sets(inputs)
    calls = planned_calls(sets, config)
    cache = CallCache(args.cache_dir, offline=args.offline)
    try:
        records = run_calls(calls, cache)
    except FetchError as exc:
        print(f"error: {exc}; no file written", file=sys.stderr)
        return 1
    payload = build_payload(inputs, config, sets, records)
    write_json(OUT_JSON, payload)
    for entry in payload["sets"]:
        if entry["status"] == "probed":
            print(
                f"{entry['set_id']}: {entry['n_retrieved_by_v31']}/{entry['n_anchors']} "
                f"retrieved, credits {entry['credits']:g}"
            )
        else:
            print(f"{entry['set_id']}: excluded ({entry['excluded_reason']})")
    print(
        f"wrote {OUT_JSON.name}: {payload['calls_total']} calls, "
        f"{payload['credits_total']:g} credits"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
