"""Theme anchor sets for BQ-S6 (A3 section 5.8): known-relevant works used as recall anchors.

Each theme lists the DOIs that A3 section 5.8 names as known-relevant. ``--live`` fetches them
in one OpenAlex DOI list call (a plain filter, about 1 credit) through the shared client and
budget guard, then caches the raw response. The default mode rebuilds
``tests/fixtures/theme_anchors.json`` from that cache and ``works.parquet``; it makes no
network call.

Plastics-primary judgements are explicit: ``DECISIONS`` holds one per DOI. ``LEAD_DECISIONS``
overrides a builder judgement after it is made; each anchor row records who decided
(``decided_by``). The build checks that each quoted evidence string appears verbatim in the
work's title or abstract, and that every found work has a judgement. Abstracts are used for
that check only and are not written to the fixture.

Usage:
    py -3.14 scripts/build_theme_anchors.py --live   # one budgeted OpenAlex call (once)
    py -3.14 scripts/build_theme_anchors.py          # offline: rebuild the fixture from cache
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.ingest.europepmc_audit import normalize_doi  # noqa: E402
from atlas.ingest.openalex import (  # noqa: E402
    OPENALEX_BASE,
    _request_json,
    compact_openalex_id,
    load_openalex_key,
)
from atlas.util.budget import daily_logged_usage, resolve_openalex_budget  # noqa: E402
from atlas.util.cost import ApiCostLogger  # noqa: E402

SCHEMA_VERSION = "theme-anchors-v1"
RAW_SCHEMA_VERSION = "theme-anchors-raw-v1"
SOURCE = "A3 §5.8 BQ-S6"
NOTE = "anchors, not an estimate"
SELECT = (
    "id,doi,display_name,publication_year,primary_location,type,"
    "abstract_inverted_index,primary_topic"
)
# One list call carries every DOI, so the page size must cover the whole list.
PER_PAGE = 50
MAX_HTTP_ATTEMPTS = 3
MAX_EVIDENCE_WORDS = 30
NO_VENUE = "(no venue)"
RECENT_THEME = "reviews_2025_2026"
DEFAULT_RAW = ROOT / "data" / "interim" / "theme_anchors_raw.json"
DEFAULT_OUTPUT = ROOT / "tests" / "fixtures" / "theme_anchors.json"
DEFAULT_WORKS = ROOT / "data" / "processed" / "normalized" / "works.parquet"
DEFAULT_USAGE_LOG = ROOT / "data" / "logs" / "api_usage.jsonl"

# DOIs named in A3 section 5.8 (BQ-S6), grouped by theme. Order is the output order.
THEMES: dict[str, tuple[str, ...]] = {
    "waste_recycling": (
        "10.1126/science.1260352",
        "10.1126/sciadv.1700782",
        "10.1057/s41599-018-0212-7",
        "10.1126/science.adr3837",
        "10.1098/rstb.2008.0311",
        "10.1126/sciadv.aat0131",
    ),
    "policy": (
        "10.1016/j.gloenvcha.2018.05.002",
        "10.1016/j.marpolbul.2017.02.048",
        "10.1016/j.marpolbul.2018.10.001",
        "10.1007/s10640-006-9059-2",
        "10.1016/j.jclepro.2018.12.256",
    ),
    "behaviour": (
        "10.1057/s41599-021-00747-4",
        "10.1016/j.resconrec.2022.106219",
        "10.1016/j.wasman.2017.01.023",
    ),
    "lca_bioplastics": (
        "10.1038/s41578-021-00407-8",
        "10.1016/j.jclepro.2018.03.014",
        "10.1016/j.crgsc.2022.100273",
    ),
    "litter": (
        "10.5894/rgci194",
        "10.1038/s41598-018-22939-w",
    ),
    "ssbd": ("10.1038/s41893-025-01672-z",),
    "chemicals": (
        "10.1016/j.jhazmat.2017.10.014",
        "10.1016/j.cogsc.2021.100513",
    ),
    "waste_colonialism_justice": (
        "10.2458/jpe.2401",
        "10.1016/j.marpol.2024.106078",
        "10.1007/978-3-031-51358-9_1",
        "10.1016/j.marpol.2023.105785",
        "10.1017/plc.2023.16",
        "10.1017/plc.2025.10005",
    ),
    "labour_critique": (
        "10.1016/j.resconrec.2020.104685",
        "10.1007/s43615-021-00056-7",
        "10.1016/j.marpolbul.2020.111774",
        "10.1017/plc.2023.10",
    ),
    "book": ("10.1515/9781478021445",),
    "pollution_exposure_health": (
        "10.1038/s43016-020-00171-y",
        "10.1016/j.scitotenv.2019.05.405",
        "10.1016/j.scitotenv.2022.158699",
        "10.1038/s41893-020-00651-w",
    ),
    RECENT_THEME: (
        "10.1186/s12940-026-01282-y",
        "10.1186/s12876-026-05475-0",
        "10.1093/etojnl/vgag148",
        "10.1016/j.jhazmat.2026.144102",
        "10.1038/s41538-025-00470-3",
    ),
}


class Decision(NamedTuple):
    """One plastics-primary judgement, made from the title and abstract of a found work."""

    plastics_primary: bool | str  # True, False, or "unclear"
    evidence: str = ""  # verbatim from title or abstract; required when True
    reason: str = ""  # why the work is not an anchor; required when not True


# Anchors: plastics is the central subject. Evidence is copied verbatim from the title or
# abstract (checked at build time). Judgements were made by reading the cached records.
ANCHOR_EVIDENCE: dict[str, str] = {
    "10.1126/science.1260352": "Plastic waste inputs from land into the ocean",
    "10.1126/sciadv.1700782": "Production, use, and fate of all plastics ever made",
    "10.1057/s41599-018-0212-7": "Future scenarios of global plastic waste generation",
    "10.1126/science.adr3837": "Pathways to reduce global plastic waste mismanagement",
    "10.1098/rstb.2008.0311": "Plastics recycling: challenges and opportunities",
    "10.1126/sciadv.aat0131": "The Chinese import ban and its impact on global plastic waste trade",
    "10.1016/j.gloenvcha.2018.05.002": "global governance of plastic failing the oceans",
    "10.1016/j.marpolbul.2017.02.048": "International policies to reduce plastic marine pollution",
    "10.1016/j.marpolbul.2018.10.001": "Reducing marine pollution from single-use plastics",
    "10.1007/s10640-006-9059-2": "Lessons from the Irish plastic bags levy",
    "10.1016/j.jclepro.2018.12.256": "the problems posed by plastic products",
    "10.1057/s41599-021-00747-4": "Single-use plastic packaging in the Canadian food industry",
    "10.1016/j.resconrec.2022.106219": "alternatives to conventional plastic packaging",
    "10.1016/j.wasman.2017.01.023": "The Portuguese plastic carrier bag tax",
    "10.1038/s41578-021-00407-8": "Bioplastics for a circular economy",
    "10.1016/j.jclepro.2018.03.014": "Bio-based plastics - A review",
    "10.1016/j.crgsc.2022.100273": "Sustainability of biodegradable plastics",
    "10.5894/rgci194": "Quantity and type of plastic debris flowing from two urban rivers",
    "10.1038/s41598-018-22939-w": "Great Pacific Garbage Patch is rapidly accumulating plastic",
    "10.1016/j.jhazmat.2017.10.014": "An overview of chemical additives present in plastics",
    "10.1016/j.cogsc.2021.100513": "Enabling a circular economy for chemicals in plastics",
    "10.2458/jpe.2401": "Plastics pollution as waste colonialism in Te Moananui",
    "10.1016/j.marpol.2024.106078": "Plastic pollution as waste colonialism in Aotearoa",
    "10.1007/978-3-031-51358-9_1": "Plastic Waste Colonialism: A Typology of Global Toxicity",
    "10.1016/j.marpol.2023.105785": "treaty on plastic pollution",
    "10.1017/plc.2023.16": "participation of Indigenous peoples in plastics pollution governance",
    "10.1017/plc.2025.10005": "strict global controls on plastic waste trade",
    "10.1016/j.resconrec.2020.104685": "Building a circular plastics economy",
    "10.1007/s43615-021-00056-7": "Waste Pickers in the Recycled Plastics Supply Chain",
    "10.1016/j.marpolbul.2020.111774": "Biodegradable plastics: Green hope or greenwashing?",
    "10.1017/plc.2023.10": "Global Plastic Pollution and Informal Waste Pickers",
    "10.1515/9781478021445": "Focusing on plastic pollution",
    "10.1038/s43016-020-00171-y": "Microplastic release from the degradation of polypropylene",
    "10.1016/j.scitotenv.2019.05.405": "Microplastic abundance in atmospheric deposition",
    "10.1016/j.scitotenv.2022.158699": "Detection of various microplastics in placentas",
    "10.1038/s41893-020-00651-w": "Evaluating alternatives to plastic microbeads in cosmetics",
    "10.1186/s12940-026-01282-y": "Health impacts of micro- and nanoplastics in humans",
    "10.1186/s12876-026-05475-0": "biological effects of micro- and nanoplastics",
    "10.1093/etojnl/vgag148": "Umbrella review on micro and nanoplastics",
    "10.1016/j.jhazmat.2026.144102": "nano- and microplastic-induced neurotoxicity",
    "10.1038/s41538-025-00470-3": "Food contact articles as source of micro- and nanoplastics",
}

# Not anchors: a judgement with the reason it is excluded (before any lead override).
EXCLUDED_DECISIONS: dict[str, Decision] = {
    # Abstract is about BPA-analogue chemistry; plastics is named once, as BPA's use.
    "10.1038/s41893-025-01672-z": Decision(
        "unclear",
        reason=(
            "central subject is BPA-analogue chemistry for a polyester; plastics named once "
            "as BPA's use; see LEAD_DECISIONS"
        ),
    ),
}

DECISIONS: dict[str, Decision] = {
    **{doi: Decision(True, evidence) for doi, evidence in ANCHOR_EVIDENCE.items()},
    **EXCLUDED_DECISIONS,
}

# Lead decision (coordinator, 2026-11-22): the builder's "unclear" above is overridden. The
# polyester is a plastic polymer designed to replace BPA-based plastics, so it is
# plastics-primary under the chemicals-in-plastics tier. Evidence is checked verbatim like any
# other judgement, and the anchor row records decided_by "lead".
LEAD_DECISIONS: dict[str, dict[str, Any]] = {
    "10.1038/s41893-025-01672-z": {
        "plastics_primary": True,
        "evidence": (
            "Safe-and-sustainable-by-design approach to polyesters from non-oestrogenic bisphenols"
        ),
        "decided_by": "lead",
        "decided_at": "2026-11-22",
        "reason": (
            "designs a safer polyester (a plastic polymer) to replace BPA-based plastics; "
            "plastics-primary under the chemicals-in-plastics tier"
        ),
    },
}


class FetchError(RuntimeError):
    """A request or budget failure: nothing is cached."""


class BuildError(RuntimeError):
    """The cache or the judgements are inconsistent: nothing is written."""


def all_dois() -> list[str]:
    return [doi for dois in THEMES.values() for doi in dois]


def build_url(dois: list[str]) -> str:
    """One OpenAlex works request for a DOI list: plain filter, no title/abstract search."""

    if not 1 <= len(dois) <= PER_PAGE:
        raise ValueError(f"a DOI list call holds 1 to {PER_PAGE} DOIs, got {len(dois)}")
    doi_filter = "doi:" + "|".join(f"https://doi.org/{doi}" for doi in dois)
    params = {"filter": doi_filter, "select": SELECT, "per_page": PER_PAGE}
    return f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"


def fetch_live(dois: list[str], usage_log: Path, now: datetime) -> dict[str, Any]:
    """Run the single budgeted DOI list request; return the body and the credits it used."""

    budget = resolve_openalex_budget()
    prior_cost, prior_credits = daily_logged_usage(
        usage_log, cost_per_credit_usd=budget.cost_per_credit_usd
    )
    error = budget.reserve_error(cost_usd=prior_cost, credits=prior_credits)
    if error:
        raise FetchError(f"budget guard: {error}")
    url = build_url(dois)
    load_openalex_key()
    try:
        with ApiCostLogger("theme-anchors-" + now.isoformat(), usage_log) as logger:
            body = _request_json(url, logger=logger, attempts=MAX_HTTP_ATTEMPTS)
    except Exception as exc:  # OpenAlex errors, usage-metadata errors, network errors
        raise FetchError(f"OpenAlex request failed: {exc}") from exc
    _, after_credits = daily_logged_usage(usage_log, cost_per_credit_usd=budget.cost_per_credit_usd)
    return {
        "request_url": url,
        "credits_used": float(after_credits - prior_credits),
        "response": body,
    }


def abstract_text(inverted: object) -> str:
    """Rebuild abstract text from OpenAlex's inverted index; empty when absent."""

    if not isinstance(inverted, dict) or not inverted:
        return ""
    words: dict[int, str] = {}
    for word, positions in inverted.items():
        for position in positions or []:
            words[int(position)] = str(word)
    return " ".join(words[i] for i in sorted(words))


def squash(text: str) -> str:
    """Whitespace-collapsed, lower-cased text for verbatim checks."""

    return " ".join(text.split()).lower()


def check_decision(doi: str, decision: Decision, title: str, abstract: str) -> str | None:
    """Return a problem with one judgement, or None when it is consistent with the record."""

    primary, evidence, reason = decision
    if primary not in (True, False, "unclear"):
        return f"{doi}: plastics_primary must be true, false or 'unclear'"
    if primary is True:
        if not evidence.strip():
            return f"{doi}: an anchor needs plastics evidence"
        if len(evidence.split()) > MAX_EVIDENCE_WORDS:
            return f"{doi}: evidence is longer than {MAX_EVIDENCE_WORDS} words"
    elif not reason.strip():
        return f"{doi}: an excluded work needs a reason"
    if evidence.strip():
        haystack = squash(f"{title} {abstract}")
        if squash(evidence) not in haystack:
            return f"{doi}: evidence is not verbatim from the title or abstract"
    return None


def _miss_reason(theme: str) -> str:
    reason = "no OpenAlex record returned for this DOI; check DOI form / indexing lag"
    if theme == RECENT_THEME:
        reason += "; 2025-2026 item, so OpenAlex indexing lag is likely"
    return reason


def _work_fields(rec: dict[str, Any]) -> dict[str, Any]:
    source = (rec.get("primary_location") or {}).get("source") or {}
    return {
        "openalex_id": compact_openalex_id(rec.get("id")) or None,
        "title": rec.get("display_name") or None,
        "year": rec.get("publication_year"),
        "venue": source.get("display_name") or None,
        "type": rec.get("type") or None,
    }


def build_payload(
    cache: dict[str, Any],
    corpus_work_ids: set[str],
    corpus_dois: set[str],
) -> dict[str, Any]:
    """Classify every spec DOI from the cached response and the judgements in DECISIONS."""

    results = (cache.get("response") or {}).get("results") or []
    by_doi: dict[str, dict[str, Any]] = {}
    for rec in results:
        doi = normalize_doi(rec.get("doi"))
        if doi and doi not in by_doi:
            by_doi[doi] = rec

    problems: list[str] = []
    stale = sorted(set(DECISIONS) - set(all_dois()))
    if stale:
        problems.append(f"judgements for DOIs outside THEMES: {stale}")
    stale_lead = sorted(set(LEAD_DECISIONS) - set(all_dois()))
    if stale_lead:
        problems.append(f"lead decisions for DOIs outside THEMES: {stale_lead}")

    anchors: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    not_found: list[dict[str, Any]] = []
    for theme, dois in THEMES.items():
        for doi in dois:
            rec = by_doi.get(doi)
            if rec is None:
                not_found.append(
                    {
                        "theme": theme,
                        "doi": doi,
                        "openalex_id": None,
                        "title": None,
                        "year": None,
                        "venue": None,
                        "type": None,
                        "found_in_openalex": False,
                        "in_atlas_corpus": doi in corpus_dois,
                        "plastics_primary": "unclear",
                        "plastics_evidence": "",
                        "decided_by": None,
                        "miss_reason": _miss_reason(theme),
                    }
                )
                continue
            fields = _work_fields(rec)
            abstract = abstract_text(rec.get("abstract_inverted_index"))
            decision = DECISIONS.get(doi)
            if decision is None:
                problems.append(f"{doi}: found in OpenAlex but has no plastics judgement")
                continue
            decided_by = "builder"
            lead = LEAD_DECISIONS.get(doi)
            if lead is not None:
                if lead.get("decided_by") != "lead":
                    problems.append(f"{doi}: a lead decision must record decided_by 'lead'")
                    continue
                decision = Decision(lead["plastics_primary"], lead["evidence"], lead["reason"])
                decided_by = lead["decided_by"]
            problem = check_decision(doi, decision, fields["title"] or "", abstract)
            if problem:
                problems.append(problem)
                continue
            in_corpus = doi in corpus_dois or (
                fields["openalex_id"] is not None and fields["openalex_id"] in corpus_work_ids
            )
            row = {
                "theme": theme,
                "doi": doi,
                **fields,
                "found_in_openalex": True,
                "in_atlas_corpus": in_corpus,
                "plastics_primary": decision.plastics_primary,
                "plastics_evidence": decision.evidence,
                "decided_by": decided_by,
            }
            if decision.plastics_primary is True:
                anchors.append(row)
            else:
                excluded.append({**row, "exclusion_reason": decision.reason})
    if problems:
        raise BuildError("; ".join(problems))

    counts = Counter(row["venue"] or NO_VENUE for row in anchors)
    max_share = round(max(counts.values()) / len(anchors), 3) if anchors else 0.0
    return {
        "schema": SCHEMA_VERSION,
        "generated_at": cache["fetched_at"],
        "source": SOURCE,
        "note": NOTE,
        "anchors": anchors,
        "excluded": excluded,
        "not_found": not_found,
        "venue_distribution": dict(counts.most_common()),
        "max_venue_share": max_share,
    }


def load_corpus(path: Path) -> tuple[set[str], set[str]]:
    """Work ids and normalized DOIs in the atlas works table."""

    import pyarrow.parquet as pq

    table = pq.read_table(path, columns=["work_id", "doi"])
    work_ids: set[str] = set()
    dois: set[str] = set()
    for row in table.to_pylist():
        work_id = compact_openalex_id(row.get("work_id"))
        if work_id:
            work_ids.add(work_id)
        doi = normalize_doi(row.get("doi"))
        if doi:
            dois.add(doi)
    return work_ids, dois


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomic write with LF line endings and a trailing newline."""

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="one budgeted OpenAlex DOI call")
    parser.add_argument("--force", action="store_true", help="with --live, refetch over a cache")
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--works", type=Path, default=DEFAULT_WORKS)
    parser.add_argument("--usage-log", type=Path, default=DEFAULT_USAGE_LOG)
    args = parser.parse_args(argv)

    if args.live:
        if args.raw.exists() and not args.force:
            print(f"cache exists at {args.raw.name}; not calling OpenAlex (use --force)")
            return 1
        now = datetime.now(UTC)
        try:
            result = fetch_live(all_dois(), args.usage_log, now)
        except FetchError as exc:
            print(f"error: {exc}; no cache written", file=sys.stderr)
            return 1
        cache = {
            "schema": RAW_SCHEMA_VERSION,
            "fetched_at": now.isoformat(timespec="seconds"),
            "dois_requested": len(all_dois()),
            **result,
        }
        write_json(args.raw, cache)
        results = (result["response"] or {}).get("results") or []
        print(
            f"cached {len(results)} works for {len(all_dois())} DOIs; "
            f"credits used {result['credits_used']:g}"
        )
        return 0

    if not args.raw.exists():
        print(f"error: no cache at {args.raw}; run with --live once", file=sys.stderr)
        return 1
    cache = json.loads(args.raw.read_text(encoding="utf-8"))
    corpus_work_ids, corpus_dois = load_corpus(args.works)
    try:
        payload = build_payload(cache, corpus_work_ids, corpus_dois)
    except BuildError as exc:
        print(f"error: {exc}; no fixture written", file=sys.stderr)
        return 1
    write_json(args.output, payload)
    print(
        f"wrote {args.output.name}: {len(payload['anchors'])} anchors, "
        f"{len(payload['excluded'])} excluded, {len(payload['not_found'])} not found; "
        f"max venue share {payload['max_venue_share']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
