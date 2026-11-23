"""Replay published PubMed review search strings and measure overlap with the Atlas v3.1 query.

BQ-S10 (A3 section 5.11, section 5.10.1). Count-only: nothing retrieves records, abstracts or
included-study lists. Each review string is read verbatim from
``config/pubmed/review_strings/<review_id>.txt``; its ``#`` header holds the source, licence,
search date and published count. One review per run.

The dry run (default) makes no network call. It parses the string, reports the top-level structure
and runs the duplicate check: repeated terms inside one OR block after normalising case, quotes,
parentheses and whitespace. A string with an unmatched parenthesis is analysed on a copy with that
parenthesis removed; PubMed counts always use the string as published.

``--live`` (NCBI E-utilities is free; OpenAlex goes through the budget guard):
  1. ESearch count of the string as published, with no date limit (1800/01/01 to 3000/12/31).
  2. Counts of each AND block alone, of the positive part without NOT, and of the string limited
     to the original search date. A deduplicated string is counted only if duplicates exist.
  3. A fixed-seed sample of up to 200 PMIDs from the review's PubMed set (seed 20261122).
  4. OpenAlex: how many sample PMIDs exist in OpenAlex (ids.pmid filter), and how many the Atlas
     v3.1 query retrieves (the title_and_abstract filter and type exclusions rendered as in
     scripts/fetch_trend_global.py, without the CA scope). Task-wide cap: 120 OpenAlex credits.
Results merge into docs/api_notes/bq_s10_replay.json, one entry per review.

Usage:
    py -3.14 scripts/replay_review_strings.py --review tran_2026           # dry run, no network
    py -3.14 scripts/replay_review_strings.py --review tran_2026 --live    # one live run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import urllib.parse
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.ingest.openalex import (  # noqa: E402
    OPENALEX_BASE,
    _request_json,
    load_openalex_key,
)
from atlas.qc.pubmed import (  # noqa: E402
    DEFAULT_MARGIN,
    ESEARCH_MAX,
    RPS_WITH_KEY,
    RPS_WITHOUT_KEY,
    EUtilsClient,
    EUtilsError,
    QuerySyntaxError,
    format_day,
    partition_dates,
    read_query_file,
    split_top_level_or,
)
from atlas.query import load_query_config, openalex_filter, type_filters  # noqa: E402
from atlas.util.budget import (  # noqa: E402
    OpenAlexBudget,
    daily_logged_usage,
    resolve_openalex_budget,
)
from atlas.util.cost import ApiCostLogger  # noqa: E402

SCRIPT_VERSION = "bq_s10_replay.v1"
SCHEMA = "bq-s10-replay.v1"
REVIEW_DIR = ROOT / "config" / "pubmed" / "review_strings"
DEFAULT_OUT = ROOT / "docs" / "api_notes" / "bq_s10_replay.json"
DEFAULT_CACHE_DIR = ROOT / "scratch" / "bqs10" / "ncbi_cache"
DEFAULT_USAGE_LOG = ROOT / "data" / "logs" / "api_usage.jsonl"
V31_CONFIG = ROOT / "config" / "queries.yml"
V31_VERSION = "plastic-v3.1"
WINDOW_START = "1800/01/01"
WINDOW_END = "3000/12/31"
SEED = "20261122"
SAMPLE_SIZE = 200
PMID_BATCH = 50
PUBMED_URL = "https://pubmed.ncbi.nlm.nih.gov/"
OPENALEX_ATTEMPTS = 3
MAX_URL_CHARS = 8000
MAX_PAGES = 20
TASK_RUN_PREFIX = "bq-s10-"
TASK_CREDIT_CAP = 120
CREDIT_RESERVE_PER_CALL = 10
WILSON_Z = 1.959963984540054
REVIEW_ID_PATTERN = re.compile(r"[a-z0-9_]+")
HEADER_PATTERN = re.compile(r"#\s*([a-z_]+):\s*(.*)")
PMID_DIGITS = re.compile(r"[0-9]+")
REQUIRED_HEADER = (
    "citation",
    "source",
    "licence",
    "search_date",
    "search_date_source",
    "published_count",
    "published_count_source",
    "included_study_list",
    "transcription",
)
# Reviews named in the brief whose string is not in the repo or Zotero: status only, no replay.
UNAVAILABLE_REVIEWS = {
    "ortiz_balsero_2026": "not available: supplementary Text S1 not in Zotero; owner to supply",
}

_LEFT_OF_KEYWORD = frozenset(' \t\r\n()"]')
_RIGHT_OF_KEYWORD = frozenset(' \t\r\n("')
_QUOTE_CHARS = str.maketrans({'"': "", "“": "", "”": ""})


class ReplayError(RuntimeError):
    """A review string, count or OpenAlex request cannot be used; nothing is written."""


@dataclass(frozen=True)
class ReviewString:
    review_id: str
    path: Path
    header: Mapping[str, str]
    query: str  # as published: comment lines dropped, whitespace collapsed

    def value(self, key: str) -> str:
        if key not in self.header:
            raise ReplayError(f"{self.path.name}: header key {key!r} is missing")
        return self.header[key]


@dataclass(frozen=True)
class Structure:
    repaired_query: str
    repairs: tuple[dict[str, Any], ...]
    positive: str
    exclusion: str | None
    blocks: tuple[str, ...]
    operands: tuple[tuple[str, ...], ...]


# --- Review files -------------------------------------------------------------------------------


def load_review(review_id: str, review_dir: Path | None = None) -> ReviewString:
    """Read one review string and its header. The body is the query text as published."""
    if not REVIEW_ID_PATTERN.fullmatch(review_id):
        raise ReplayError("review id must use lowercase letters, digits and underscores")
    directory = REVIEW_DIR if review_dir is None else review_dir
    path = directory / f"{review_id}.txt"
    if not path.exists():
        raise ReplayError(f"no review string file for {review_id}: {path.name}")
    header: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = HEADER_PATTERN.match(line)
        if match:
            header[match.group(1)] = match.group(2).strip()
    missing = [key for key in REQUIRED_HEADER if not header.get(key)]
    if missing or header.get("review_id") != review_id:
        raise ReplayError(f"{path.name}: header needs review_id and {', '.join(REQUIRED_HEADER)}")
    query = read_query_file(path)
    if not query:
        raise ReplayError(f"{path.name}: no query text after the header")
    return ReviewString(review_id=review_id, path=path, header=header, query=query)


def _rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


# --- Parsing ------------------------------------------------------------------------------------


def _keyword_spans(query: str, word: str) -> list[tuple[int, int]]:
    """Spans of AND, OR or NOT (any case) outside parentheses and double quotes, standing alone."""
    spans: list[tuple[int, int]] = []
    depth = 0
    in_quote = False
    width = len(word)
    i = 0
    while i < len(query):
        ch = query[i]
        if ch == "\\":
            i += 2
            continue
        if in_quote:
            in_quote = ch != '"'
        elif ch == '"':
            in_quote = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and query[i : i + width].upper() == word:
            right = i + width
            left_ok = i == 0 or query[i - 1] in _LEFT_OF_KEYWORD
            right_ok = right == len(query) or query[right] in _RIGHT_OF_KEYWORD
            if left_ok and right_ok:
                spans.append((i, right))
                i = right
                continue
        i += 1
    return spans


def split_top(query: str, word: str) -> list[str]:
    """Split at top-level AND, OR or NOT; each part is stripped."""
    parts: list[str] = []
    start = 0
    for left, right in _keyword_spans(query, word):
        parts.append(query[start:left].strip())
        start = right
    parts.append(query[start:].strip())
    return parts


def _matching_close(text: str, open_at: int) -> int:
    depth = 0
    in_quote = False
    i = open_at
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if in_quote:
            in_quote = ch != '"'
        elif ch == '"':
            in_quote = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _strip_outer(text: str) -> str:
    """Remove parentheses that wrap the whole text, repeatedly."""
    text = text.strip()
    while text.startswith("(") and _matching_close(text, 0) == len(text) - 1:
        text = text[1:-1].strip()
    return text


def and_blocks(text: str) -> list[str]:
    """Top-level AND blocks, flattened through redundant wrapping parentheses."""
    stripped = _strip_outer(text)
    parts = split_top(stripped, "AND")
    if len(parts) == 1:
        return [stripped]
    blocks: list[str] = []
    for part in parts:
        if not part:
            raise ReplayError("AND with an empty operand")
        blocks.extend(and_blocks(part))
    return blocks


def or_operands(block: str) -> list[str]:
    """Top-level OR operands of one AND block (nested groups stay whole)."""
    operands = split_top(_strip_outer(block), "OR")
    if not all(operands):
        raise ReplayError("OR with an empty operand")
    return operands


def local_parse_error(query: str) -> str | None:
    """The atlas splitter's complaint about the string as published, or None when it parses."""
    try:
        split_top_level_or(query)
    except QuerySyntaxError as error:
        return str(error)
    return None


def balance_repair(query: str) -> tuple[str, list[dict[str, Any]]]:
    """Drop unmatched closing parentheses so the structure can be analysed.

    Only ``)`` can be dropped; an unmatched ``(`` or an open quote raises ``ReplayError``. The
    removed characters are returned with their context so the repair is visible in the output.
    """
    stack: list[int] = []
    unmatched: set[int] = set()
    in_quote = False
    i = 0
    while i < len(query):
        ch = query[i]
        if ch == "\\":
            i += 2
            continue
        if in_quote:
            in_quote = ch != '"'
        elif ch == '"':
            in_quote = True
        elif ch == "(":
            stack.append(i)
        elif ch == ")":
            if stack:
                stack.pop()
            else:
                unmatched.add(i)
        i += 1
    if in_quote:
        raise ReplayError("unterminated double quote; the string cannot be analysed")
    if stack:
        raise ReplayError("unmatched opening parenthesis; the string cannot be repaired")
    repairs = [
        {"character": ")", "index": index, "context": query[max(0, index - 60) : index + 12]}
        for index in sorted(unmatched)
    ]
    repaired = "".join(ch for index, ch in enumerate(query) if index not in unmatched)
    return repaired, repairs


def analyse(query: str) -> Structure:
    """Top-level structure of a query: positive AND blocks, OR operands and the NOT clause."""
    repaired, repairs = balance_repair(query)
    parts = split_top(repaired, "NOT")
    if len(parts) > 2:
        raise ReplayError("more than one top-level NOT; the replay supports one NOT clause")
    positive = _strip_outer(parts[0])
    if not positive:
        raise ReplayError("the string has no positive part before NOT")
    exclusion = None
    if len(parts) == 2:
        exclusion = _strip_outer(parts[1])
        if len(split_top(exclusion, "AND")) > 1:
            raise ReplayError("AND after NOT is not supported by this replay")
    blocks = and_blocks(positive)
    operands = [or_operands(block) for block in blocks]
    return Structure(
        repaired_query=repaired,
        repairs=tuple(repairs),
        positive=positive,
        exclusion=exclusion,
        blocks=tuple(blocks),
        operands=tuple(tuple(ops) for ops in operands),
    )


# --- Duplicate check ----------------------------------------------------------------------------


def term_key(term: str) -> str:
    """Normalised form of one OR operand: no quotes or parentheses, lower case, single spaces."""
    text = term.translate(_QUOTE_CHARS).replace("(", " ").replace(")", " ")
    text = re.sub(r"\s+\[", "[", text)
    return " ".join(text.split()).lower()


def repeated_terms(operands: Sequence[str]) -> list[dict[str, Any]]:
    """Operands that repeat within one OR block after normalisation, with their raw forms."""
    groups: dict[str, list[str]] = {}
    for term in operands:
        groups.setdefault(term_key(term), []).append(term)
    return [
        {"term": key, "times": len(raw), "raw_forms": sorted(set(raw))}
        for key, raw in groups.items()
        if len(raw) > 1
    ]


def dedupe(operands: Sequence[str]) -> list[str]:
    """Keep the first occurrence of each normalised operand."""
    seen: set[str] = set()
    kept: list[str] = []
    for term in operands:
        key = term_key(term)
        if key not in seen:
            seen.add(key)
            kept.append(term)
    return kept


def canonical_query(structure: Structure) -> str:
    """The deduplicated query, rebuilt as AND-ed OR blocks with the NOT clause last."""
    blocks = [f"({' OR '.join(dedupe(ops))})" for ops in structure.operands]
    positive = " AND ".join(blocks)
    if structure.exclusion is None:
        return positive
    return f"({positive}) NOT ({structure.exclusion})"


def structure_report(structure: Structure, local_error: str | None) -> dict[str, Any]:
    blocks = []
    for number, (text, ops) in enumerate(zip(structure.blocks, structure.operands), start=1):
        repeated = repeated_terms(ops)
        blocks.append(
            {
                "block": number,
                "operands_raw": len(ops),
                "operands_deduplicated": len(dedupe(ops)),
                "repeated": repeated,
                "preview": text[:100],
            }
        )
    return {
        "local_parse_as_published": local_error or "ok",
        "repairs": list(structure.repairs),
        "and_blocks": len(structure.blocks),
        "not_clause": structure.exclusion is not None,
        "blocks": blocks,
        "operands_raw_total": sum(len(ops) for ops in structure.operands),
        "operands_deduplicated_total": sum(len(dedupe(ops)) for ops in structure.operands),
        "duplicates_found": sum(len(block["repeated"]) for block in blocks),
    }


# --- Dates, PMIDs and sampling ------------------------------------------------------------------


def retrieve_pmids(client: Any, term: str, start: str, end: str, total: int) -> list[str]:
    """Every PMID for the term in the window, numeric order. Splits by date above 10,000 records."""
    if total <= ESEARCH_MAX:
        pmids = client.pmids(term, start, end, retmax=ESEARCH_MAX)
        if len(pmids) != total:
            raise ReplayError(f"PubMed returned {len(pmids)} PMIDs for a count of {total}")
        return sorted(set(pmids), key=int)
    partitions = partition_dates(
        lambda first, last: client.count(term, first, last)[0],
        start,
        end,
        cap=ESEARCH_MAX,
        margin=DEFAULT_MARGIN,
    )
    found: set[str] = set()
    for part in partitions:
        ids = client.pmids(term, part.start, part.end, retmax=ESEARCH_MAX)
        if len(ids) != part.count:
            raise ReplayError(f"PubMed returned {len(ids)} PMIDs for a count of {part.count}")
        found.update(ids)
    return sorted(found, key=int)


def sample_pmids(pmids: Iterable[str], seed: str = SEED, size: int = SAMPLE_SIZE) -> list[str]:
    """The first ``size`` PMIDs in sha256(seed:pmid) order; same input, same sample."""
    unique = sorted({str(pmid) for pmid in pmids}, key=int)
    ranked = sorted(unique, key=lambda pmid: hashlib.sha256(f"{seed}:{pmid}".encode()).hexdigest())
    return ranked[:size]


def wilson_interval(successes: int, n: int, z: float = WILSON_Z) -> tuple[float, float] | None:
    """Wilson score interval for a proportion (95 per cent by default); None when n is 0."""
    if n <= 0:
        return None
    if not 0 <= successes <= n:
        raise ValueError("successes must be between 0 and n")
    p = successes / n
    z2 = z * z
    denominator = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denominator
    return max(0.0, centre - half), min(1.0, centre + half)


def _share(successes: int, n: int) -> dict[str, Any]:
    interval = wilson_interval(successes, n)
    return {
        "count": successes,
        "share": None if n == 0 else round(successes / n, 4),
        "wilson95": None if interval is None else [round(interval[0], 4), round(interval[1], 4)],
    }


def overlap_summary(sample_n: int, in_openalex: int, v31_retrieved: int) -> dict[str, Any]:
    """Shares over the sample: in OpenAlex at all, and retrieved by the v3.1 query."""
    return {
        "sample": sample_n,
        "in_openalex": _share(in_openalex, sample_n),
        "v31_retrieved": _share(v31_retrieved, sample_n),
        "v31_share_of_in_openalex": None
        if in_openalex == 0
        else round(v31_retrieved / in_openalex, 4),
    }


# --- OpenAlex -----------------------------------------------------------------------------------


def v31_filter_parts(config: Mapping[str, Any]) -> list[str]:
    """The v3.1 filters as scripts/fetch_trend_global.py build_url renders them (no CA scope)."""
    return [openalex_filter(config), *type_filters(config)]


def _work_pmid(work: Mapping[str, Any]) -> str | None:
    ids = work.get("ids")
    if not isinstance(ids, Mapping):
        return None
    match = re.search(r"([0-9]+)/?$", str(ids.get("pmid") or "").strip())
    return match.group(1) if match else None


def _paged_pmids(
    get: Callable[[str, str], Mapping[str, Any]], filter_value: str, label: str
) -> set[str]:
    found: set[str] = set()
    for page in range(1, MAX_PAGES + 1):
        params = {
            "filter": filter_value,
            "select": "id,ids",
            "per_page": PMID_BATCH,
            "page": page,
        }
        url = f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"
        if len(url) > MAX_URL_CHARS:
            raise ReplayError(f"request URL is {len(url)} characters; limit is {MAX_URL_CHARS}")
        body = get(url, f"{label}-p{page}")
        results = body.get("results") or []
        for work in results:
            if isinstance(work, Mapping):
                pmid = _work_pmid(work)
                if pmid:
                    found.add(pmid)
        total = int((body.get("meta") or {}).get("count") or 0)
        if not results or page * PMID_BATCH >= total:
            return found
    raise ReplayError(f"OpenAlex returned more than {MAX_PAGES} pages for one batch")


def openalex_hits(
    get: Callable[[str, str], Mapping[str, Any]],
    pmids: Sequence[str],
    extra_filters: Sequence[str],
    label: str,
) -> set[str]:
    """PMIDs among ``pmids`` that OpenAlex returns for the ids.pmid filter (plus extra filters)."""
    hits: set[str] = set()
    for index, start in enumerate(range(0, len(pmids), PMID_BATCH), start=1):
        batch = pmids[start : start + PMID_BATCH]
        id_filter = "ids.pmid:" + "|".join(f"{PUBMED_URL}{pmid}" for pmid in batch)
        filter_value = ",".join([id_filter, *extra_filters])
        hits |= _paged_pmids(get, filter_value, f"{label}-{index:02d}")
    return hits & set(pmids)


class OpenAlexGuard:
    """One OpenAlex request at a time through the shared path and the daily budget guard.

    Mirrors scripts/fetch_trend_global.py fetch(): daily reserve check, ApiCostLogger per request,
    ``_request_json``. Refuses a request that would take this task past 120 logged credits.
    """

    def __init__(self, usage_log: Path, budget: OpenAlexBudget | None = None) -> None:
        self.usage_log = usage_log
        self.budget = (
            resolve_openalex_budget(ROOT / "config" / "budget.yml") if budget is None else budget
        )
        self.credits_used = Decimal(0)
        self.calls = 0

    def __call__(self, url: str, label: str) -> dict[str, Any]:
        logged = task_credits_logged(self.usage_log)
        if logged + CREDIT_RESERVE_PER_CALL > TASK_CREDIT_CAP:
            raise ReplayError(
                f"task OpenAlex credit cap {TASK_CREDIT_CAP} would be exceeded; "
                f"{logged} credits already logged for this task"
            )
        prior_cost, prior_credits = daily_logged_usage(
            self.usage_log, cost_per_credit_usd=self.budget.cost_per_credit_usd
        )
        error = self.budget.reserve_error(cost_usd=prior_cost, credits=prior_credits)
        if error:
            raise ReplayError(f"budget guard: {error}")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        try:
            with ApiCostLogger(f"{TASK_RUN_PREFIX}{label}-{stamp}", self.usage_log) as logger:
                body = _request_json(url, logger=logger, attempts=OPENALEX_ATTEMPTS)
        except Exception as error:  # OpenAlex, usage-metadata and network errors
            raise ReplayError(f"OpenAlex request failed: {error}") from error
        self.credits_used += logger.credits_total
        self.calls += 1
        return body


def task_credits_logged(path: Path) -> Decimal:
    """Credits logged by earlier bq-s10 requests (all days), so retries cannot pass the cap."""
    if not path.exists():
        return Decimal(0)
    total = Decimal(0)
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            record = json.loads(line)
            if (
                isinstance(record, dict)
                and record.get("record_type") == "request"
                and str(record.get("run_id", "")).startswith(TASK_RUN_PREFIX)
            ):
                total += Decimal(str(record.get("credits") or 0))
    return total


# --- Replay -------------------------------------------------------------------------------------


def entry_date_count(client: Any, term: str, search_date: date) -> int:
    """Count of records entered in PubMed (Entrez date) up to the original search date.

    EUtilsClient.count always sends datetype=pdat, so this one ESearch goes through its private
    ``_get_json``. A record in PubMed on the search date has an Entrez date on or before it; a
    publication-date cut can drop records whose print date is later.
    """
    payload = client._get_json(
        "esearch",
        {
            "db": "pubmed",
            "term": term,
            "datetype": "edat",
            "mindate": WINDOW_START,
            "maxdate": format_day(search_date),
            "retmode": "json",
            "retmax": 0,
            "retstart": 0,
        },
    )
    result = payload.get("esearchresult")
    if not isinstance(result, dict) or "count" not in result or "ERROR" in result:
        raise ReplayError("ESearch (Entrez date) returned no count")
    return int(result["count"])


def replay_review(
    review: ReviewString,
    *,
    client: Any,
    openalex: Callable[[str, str], Mapping[str, Any]],
    today: date,
) -> dict[str, Any]:
    """Count the string as published, its blocks and sample; then check OpenAlex."""
    local_error = local_parse_error(review.query)
    structure = analyse(review.query)
    search_date = date.fromisoformat(review.value("search_date"))
    published = int(review.value("published_count"))

    count_query = review.query
    fallback_reason = None
    try:
        total, translation = client.count(count_query, WINDOW_START, WINDOW_END)
    except EUtilsError as error:
        if structure.repaired_query == review.query:
            raise
        fallback_reason = str(error)
        count_query = structure.repaired_query
        total, translation = client.count(count_query, WINDOW_START, WINDOW_END)

    to_date, _ = client.count(count_query, WINDOW_START, format_day(search_date))
    entrez_to_date = entry_date_count(client, count_query, search_date)
    blocks = []
    report = structure_report(structure, local_error)
    for block, block_report in zip(structure.blocks, report["blocks"]):
        block_count, _ = client.count(f"({block})", WINDOW_START, WINDOW_END)
        blocks.append({**block_report, "count": block_count})
    positive_count = None
    if structure.exclusion is not None:
        positive_count, _ = client.count(f"({structure.positive})", WINDOW_START, WINDOW_END)
    deduplicated = None
    if report["duplicates_found"]:
        dedup_query = canonical_query(structure)
        dedup_count, _ = client.count(dedup_query, WINDOW_START, WINDOW_END)
        deduplicated = {"count": dedup_count, "equal_to_string_count": dedup_count == total}

    pmids = retrieve_pmids(client, count_query, WINDOW_START, WINDOW_END, total)
    sample = sample_pmids(pmids)
    in_openalex = 0
    v31_retrieved = 0
    openalex_calls_note = None
    if sample:
        config = load_query_config(V31_CONFIG)
        if str(config.get("version")) != V31_VERSION:
            raise ReplayError(
                f"{V31_CONFIG.name} is {config.get('version')}, expected {V31_VERSION}"
            )
        present = openalex_hits(openalex, sample, [], "exists")
        if not present:
            raise ReplayError(
                "no sample PMID matched in OpenAlex; check the ids.pmid filter before re-running"
            )
        retrieved = openalex_hits(openalex, sample, v31_filter_parts(config), "v31")
        in_openalex = len(present)
        v31_retrieved = len(retrieved)
    else:
        openalex_calls_note = "no PMIDs retrieved; no OpenAlex check made"

    entry: dict[str, Any] = {
        "status": "replayed",
        "citation": review.value("citation"),
        "source": review.value("source"),
        "string_file": _rel(review.path),
        "string_sha256": hashlib.sha256(review.query.encode("utf-8")).hexdigest(),
        "licence": review.value("licence"),
        "included_study_list": review.value("included_study_list"),
        "published": {
            "pubmed_count": published,
            "search_date": search_date.isoformat(),
            "search_date_source": review.value("search_date_source"),
            "count_source": review.value("published_count_source"),
        },
        "replay": {
            "date": today.isoformat(),
            "date_window": f"{WINDOW_START}..{WINDOW_END} (no date limit in the string)",
            "as_published_count": total,
            "translation": translation,
            "count_query": "as_published" if fallback_reason is None else "repaired",
            "as_published_error": fallback_reason,
            "count_to_search_date": {
                "datetype": "pdat",
                "window": f"{WINDOW_START}..{format_day(search_date)}",
                "count": to_date,
            },
            "entry_date_to_search_date": {
                "datetype": "edat",
                "window": f"{WINDOW_START}..{format_day(search_date)}",
                "count": entrez_to_date,
                "date": today.isoformat(),
            },
            "positive_only_count": positive_count,
            "deduplicated": deduplicated,
            "blocks": blocks,
        },
        "structure": {key: value for key, value in report.items() if key != "blocks"},
        "sample": {
            "seed": SEED,
            "method": "sha256(seed:pmid) order over the sorted PMID set; first 200",
            "pmids_in_review_set": len(pmids),
            "sample_drawn": len(sample),
        },
        "openalex": {
            "v31_query_version": V31_VERSION,
            "note": openalex_calls_note,
            **overlap_summary(len(sample), in_openalex, v31_retrieved),
        },
    }
    return entry


# --- Output -------------------------------------------------------------------------------------


def write_result(
    path: Path,
    review_id: str,
    entry: Mapping[str, Any],
    *,
    generated_utc: str,
    secrets: Sequence[str],
) -> None:
    """Merge one review's entry into the machine copy; other reviews are kept."""
    reviews: dict[str, Any] = {}
    if path.exists():
        reviews = dict(json.loads(path.read_text(encoding="utf-8")).get("reviews") or {})
    reviews[review_id] = dict(entry)
    for unavailable, reason in UNAVAILABLE_REVIEWS.items():
        reviews.setdefault(unavailable, {"status": "not replayed", "reason": reason})
    doc = {
        "schema": SCHEMA,
        "script_version": SCRIPT_VERSION,
        "generated_utc": generated_utc,
        "v31_query_version": V31_VERSION,
        "seed": SEED,
        "sample_size": SAMPLE_SIZE,
        "reviews": dict(sorted(reviews.items())),
    }
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    for secret in secrets:
        if secret and secret in text:
            raise ReplayError("a contact value or API key would be written; nothing saved")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def add_entry_date_counts(
    entry: Mapping[str, Any], review: ReviewString, client: Any, today: date
) -> dict[str, Any]:
    """Add the Entrez-date count to an entry from an earlier live run (count only, no OpenAlex)."""
    updated = json.loads(json.dumps(entry))
    replay_block = updated["replay"]
    search_date = date.fromisoformat(updated["published"]["search_date"])
    query = (
        review.query
        if replay_block["count_query"] == "as_published"
        else analyse(review.query).repaired_query
    )
    replay_block.setdefault("count_to_search_date", {}).setdefault("datetype", "pdat")
    replay_block["entry_date_to_search_date"] = {
        "datetype": "edat",
        "window": f"{WINDOW_START}..{format_day(search_date)}",
        "count": entry_date_count(client, query, search_date),
        "date": today.isoformat(),
    }
    return updated


def _print_dry_run(review: ReviewString) -> None:
    structure = analyse(review.query)
    report = structure_report(structure, local_parse_error(review.query))
    print(f"review: {review.review_id} ({_rel(review.path)})")
    print(f"string: {len(review.query)} characters, as published (no PubMed call made)")
    print(f"local parse as published: {report['local_parse_as_published']}")
    for repair in report["repairs"]:
        print(
            f"structure repair (counts use the string as published): removed "
            f"{repair['character']!r} at character {repair['index']}: ...{repair['context']}..."
        )
    print(
        f"top level: {report['and_blocks']} AND block(s); "
        f"NOT clause: {'yes' if report['not_clause'] else 'no'}"
    )
    for block in report["blocks"]:
        print(
            f"  block {block['block']}: {block['operands_raw']} OR operand(s) raw, "
            f"{block['operands_deduplicated']} after normalising"
        )
    print(
        f"operands: {report['operands_raw_total']} raw, "
        f"{report['operands_deduplicated_total']} after normalising"
    )
    if report["duplicates_found"]:
        print("DUPLICATE CHECK: repeated terms found")
        for block in report["blocks"]:
            for repeated in block["repeated"]:
                forms = " | ".join(repeated["raw_forms"])
                print(f"  block {block['block']}: {repeated['times']} x {forms}")
    else:
        print("DUPLICATE CHECK: no term repeats within an OR block after normalising")
    print("dry run: no network call made; use --live for PubMed counts and the OpenAlex check")


def _ncbi_client(args: argparse.Namespace) -> tuple[EUtilsClient, str | None, str | None]:
    environ = os.environ
    api_key = environ.get("NCBI_API_KEY") or None
    email = environ.get("NCBI_EMAIL") or None
    rps = RPS_WITH_KEY if api_key else RPS_WITHOUT_KEY
    client = EUtilsClient(api_key=api_key, email=email, rps=rps, cache_dir=args.cache_dir)
    return client, email, api_key


def _run_entry_date(review: ReviewString, args: argparse.Namespace) -> int:
    """Add the Entrez-date count to this review's existing live entry. No OpenAlex call."""
    if not args.out.exists():
        raise ReplayError(f"{_rel(args.out)} does not exist; run --live first")
    doc = json.loads(args.out.read_text(encoding="utf-8"))
    entry = (doc.get("reviews") or {}).get(review.review_id)
    if not entry or entry.get("status") != "replayed":
        raise ReplayError(f"no live entry for {review.review_id}; run --live first")
    client, email, api_key = _ncbi_client(args)
    now = datetime.now(UTC)
    updated = add_entry_date_counts(entry, review, client, now.date())
    write_result(
        args.out,
        review.review_id,
        updated,
        generated_utc=now.isoformat(timespec="seconds"),
        secrets=[email or "", api_key or ""],
    )
    edat = updated["replay"]["entry_date_to_search_date"]["count"]
    pdat = updated["replay"]["count_to_search_date"]["count"]
    published = updated["published"]["pubmed_count"]
    print(
        f"{review.review_id}: entered by {updated['published']['search_date']}: {edat} "
        f"(publication-date cut {pdat}; published {published}); no OpenAlex call"
    )
    print(f"wrote {_rel(args.out)}")
    return 0


def _run_live(review: ReviewString, args: argparse.Namespace) -> int:
    client, email, api_key = _ncbi_client(args)
    load_openalex_key()
    guard = OpenAlexGuard(args.usage_log)
    now = datetime.now(UTC)
    entry = replay_review(review, client=client, openalex=guard, today=now.date())
    entry["openalex"]["calls"] = guard.calls
    entry["openalex"]["credits"] = int(guard.credits_used)
    write_result(
        args.out,
        review.review_id,
        entry,
        generated_utc=now.isoformat(timespec="seconds"),
        secrets=[email or "", api_key or ""],
    )
    replay = entry["replay"]
    openalex = entry["openalex"]
    print(
        f"{review.review_id}: as published {replay['as_published_count']} records today "
        f"(published {entry['published']['pubmed_count']} on {entry['published']['search_date']})"
    )
    print("  blocks: " + ", ".join(str(block["count"]) for block in replay["blocks"]))
    print(
        f"  sample {entry['sample']['sample_drawn']} of "
        f"{entry['sample']['pmids_in_review_set']} PMIDs"
    )
    print(
        f"  in OpenAlex {openalex.get('in_openalex', {}).get('count')}; "
        f"v3.1 retrieved {openalex.get('v31_retrieved', {}).get('count')}; "
        f"credits {openalex['credits']} over {openalex['calls']} call(s)"
    )
    print(f"wrote {_rel(args.out)}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--review", required=True, help="review id, e.g. tran_2026")
    parser.add_argument(
        "--live", action="store_true", help="count on PubMed and run the OpenAlex overlap check"
    )
    parser.add_argument(
        "--entry-date-only",
        action="store_true",
        help="add the Entrez-date count to this review's existing live entry (no OpenAlex)",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="machine copy (JSON)")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="NCBI cache")
    parser.add_argument(
        "--usage-log", type=Path, default=DEFAULT_USAGE_LOG, help="OpenAlex usage log (JSONL)"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.review in UNAVAILABLE_REVIEWS:
        print(f"{args.review}: {UNAVAILABLE_REVIEWS[args.review]}; nothing to replay")
        return 2
    try:
        review = load_review(args.review)
        if args.entry_date_only:
            return _run_entry_date(review, args)
        if not args.live:
            _print_dry_run(review)
            return 0
        return _run_live(review, args)
    except (ReplayError, QuerySyntaxError, EUtilsError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
