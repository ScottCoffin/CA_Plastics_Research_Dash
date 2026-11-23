"""PubMed coverage check against reference sets (BQ-S9 part A, ADR-A3-PUBMED).

Coverage asks what share of PubMed reference records (for example, California-affiliated
microplastics papers) appears in a list of Atlas works. PubMed is not a query source for the
Atlas corpus, and nothing here changes Atlas works.

The client calls NCBI E-utilities (ESearch for counts and PMIDs, ESummary for DOI and year) with
the standard library only. The contact email is sent only when the caller supplies it (the CLI
reads ``NCBI_EMAIL``). Neither the email nor the API key is written to outputs; the manifest
records only whether an API key was used.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, NamedTuple

SCRIPT_VERSION = "qc_pubmed_coverage.v1"
MANIFEST_SCHEMA = "bqs-pm-manifest-v1"
EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL_NAME = "ca-plastics-research-atlas"
ESEARCH_MAX = 10_000
DEFAULT_CAP = 10_000
DEFAULT_MARGIN = 500
RPS_WITHOUT_KEY = 3.0
RPS_WITH_KEY = 10.0
SUMMARY_BATCH = 200
DATE_FORMAT = "%Y/%m/%d"
ROW_FIELDS = ("pmid", "doi", "pub_year", "chunk_id", "partition")

DoiYear = tuple[str | None, int | None]
CountFn = Callable[[str, str], int]


class QuerySyntaxError(ValueError):
    """The query cannot be split safely: unbalanced parentheses or quotes, or an empty operand."""


class PartitionError(RuntimeError):
    """A single publication day holds more records than one ESearch call can return."""


class EUtilsError(RuntimeError):
    """NCBI E-utilities failed after retries, or returned a response that cannot be used."""


class DatePartition(NamedTuple):
    """One retrievable publication-date window (YYYY/MM/DD bounds, inclusive) and its count."""

    start: str
    end: str
    count: int


# --- Query text ---------------------------------------------------------------------------------

_WHITESPACE = re.compile(r"\s+")
_OR_LEFT = frozenset(' \t\r\n()"]')
_OR_RIGHT = frozenset(' \t\r\n("')
_AFFILIATION = re.compile(r"[A-Za-z][A-Za-z .-]*")


def read_query_file(path: Path | str) -> str:
    """Return one query file as a single line: comment lines (starting ``#``) dropped."""
    text = Path(path).read_text(encoding="utf-8")
    kept = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    return _WHITESPACE.sub(" ", " ".join(kept)).strip()


def read_query(include_path: Path | str, exclude_path: Path | str | None = None) -> str:
    """Combine include and exclude query files as ``(include) NOT (exclude)``.

    With no exclude text the include query is returned unchanged. An empty exclude file means no
    exclusion. Both texts are checked for balanced parentheses and quotes.
    """
    include = read_query_file(include_path)
    exclude = read_query_file(exclude_path) if exclude_path is not None else ""
    return _combine(include, exclude)


def _combine(include: str, exclude: str) -> str:
    _check(include, "include")
    if not exclude:
        return include
    _check(exclude, "exclude")
    return f"({include}) NOT ({exclude})"


def _check(text: str, label: str) -> None:
    try:
        split_top_level_or(text)
    except QuerySyntaxError as error:
        raise QuerySyntaxError(f"{label} query: {error}") from None


def _top_level_or_spans(query: str) -> list[tuple[int, int]]:
    """Return ``(start, end)`` of each OR operator outside parentheses and double quotes.

    A backslash escapes the next character, so ``\\(`` and ``\\"`` are literal. The operator is
    case-insensitive and must stand alone (``color`` and ``ORDER`` are not operators).
    """
    spans: list[tuple[int, int]] = []
    depth = 0
    in_quote = False
    i = 0
    while i < len(query):
        ch = query[i]
        if ch == "\\":
            if i + 1 == len(query):
                raise QuerySyntaxError("dangling backslash at the end of the query")
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
            if depth < 0:
                raise QuerySyntaxError(f"unbalanced ')' at character {i}")
        elif depth == 0 and query[i : i + 2].upper() == "OR" and _or_boundary(query, i):
            spans.append((i, i + 2))
            i += 2
            continue
        i += 1
    if in_quote:
        raise QuerySyntaxError("unterminated double quote")
    if depth:
        raise QuerySyntaxError("unbalanced '(' with no closing ')'")
    return spans


def _or_boundary(query: str, i: int) -> bool:
    left_ok = i == 0 or query[i - 1] in _OR_LEFT
    right = i + 2
    right_ok = right == len(query) or query[right] in _OR_RIGHT
    return left_ok and right_ok


def split_top_level_or(query: str) -> list[str]:
    """Split a query at top-level OR only, respecting parentheses, quotes and escapes.

    Raises ``QuerySyntaxError`` on unbalanced parentheses or quotes, a dangling escape, an empty
    query, or an OR with an empty operand.
    """
    if not query.strip():
        raise QuerySyntaxError("query is empty")
    parts: list[str] = []
    start = 0
    for left, right in _top_level_or_spans(query):
        parts.append(query[start:left])
        start = right
    parts.append(query[start:])
    cleaned = [part.strip() for part in parts]
    if not all(cleaned):
        raise QuerySyntaxError("OR with an empty operand")
    return cleaned


def split_include_chunks(query: str) -> list[str]:
    """Split the include query into OR chunks, first removing one outer parenthesised group.

    The reference include files wrap their OR list in parentheses, so a plain top-level split
    would return one chunk. Each chunk is then combined with the exclude text by the caller.
    """
    parts = split_top_level_or(query)
    if len(parts) == 1 and _wrapped_in_parentheses(parts[0]):
        return split_include_chunks(parts[0][1:-1])
    return parts


def _wrapped_in_parentheses(text: str) -> bool:
    if not (text.startswith("(") and text.endswith(")")):
        return False
    depth = 0
    in_quote = False
    i = 0
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
                return i == len(text) - 1
        i += 1
    return False


def affiliation_clause(affiliation: str | None) -> str | None:
    """Return the PubMed ``[ad]`` clause for an affiliation, e.g. ``California[ad]``."""
    if affiliation is None:
        return None
    value = affiliation.strip()
    if not _AFFILIATION.fullmatch(value):
        raise ValueError("affiliation must be letters, spaces, periods or hyphens, e.g. California")
    return f'"{value}"[ad]' if " " in value else f"{value}[ad]"


def compose_term(core: str, affiliation: str | None) -> str:
    """Add the affiliation restriction, if any, as ``(core) AND California[ad]``."""
    clause = affiliation_clause(affiliation)
    return core if clause is None else f"({core}) AND {clause}"


def build_terms(include: str, exclude: str, affiliation: str | None) -> tuple[str, list[str]]:
    """Return the whole-query PubMed term and one term per OR chunk of the include query."""
    whole = compose_term(_combine(include, exclude), affiliation)
    chunks = split_include_chunks(include)
    chunk_terms = [compose_term(_combine(chunk, exclude), affiliation) for chunk in chunks]
    return whole, chunk_terms


# --- Dates and count-first partitioning ---------------------------------------------------------


def parse_day(value: str) -> date:
    """Parse a ``YYYY/MM/DD`` publication date."""
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except ValueError:
        raise ValueError(f"date must be YYYY/MM/DD, got {value!r}") from None


def format_day(day: date) -> str:
    """Format a date as ``YYYY/MM/DD``, the form E-utilities expects."""
    return day.strftime(DATE_FORMAT)


def retrieval_threshold(cap: int, margin: int) -> int:
    """Return the largest partition count that is retrieved without splitting further."""
    if not 1 <= cap <= ESEARCH_MAX:
        raise ValueError(f"cap must be between 1 and {ESEARCH_MAX}")
    if not 0 <= margin < cap:
        raise ValueError("margin must be at least 0 and smaller than cap")
    return cap - margin


def partition_dates(
    count_fn: CountFn,
    start: str,
    end: str,
    cap: int = DEFAULT_CAP,
    margin: int = DEFAULT_MARGIN,
) -> list[DatePartition]:
    """Bisect the ``start``..``end`` window until each partition is retrievable.

    ``count_fn(start, end)`` returns the record count for a ``YYYY/MM/DD`` window. A window is
    kept when its count is at most ``cap - margin``. A single day above that threshold is kept if
    it fits under ``cap``; a single day above ``cap`` raises ``PartitionError``. Partitions are
    returned in date order and cover the whole window without gaps.
    """
    threshold = retrieval_threshold(cap, margin)
    first, last = parse_day(start), parse_day(end)
    if first > last:
        raise ValueError("start must not be after end")
    partitions: list[DatePartition] = []
    root_count = count_fn(format_day(first), format_day(last))
    _bisect(count_fn, first, last, root_count, threshold, cap, partitions)
    return partitions


def _bisect(
    count_fn: CountFn,
    first: date,
    last: date,
    count: int,
    threshold: int,
    cap: int,
    out: list[DatePartition],
) -> None:
    if count <= threshold:
        out.append(DatePartition(format_day(first), format_day(last), count))
        return
    if first == last:
        if count <= cap:
            out.append(DatePartition(format_day(first), format_day(last), count))
            return
        raise PartitionError(
            f"{format_day(first)} alone has {count} records, above the retrieval cap of {cap}; "
            "narrow the query so that one day fits"
        )
    middle = first + timedelta(days=(last - first).days // 2)
    left_count = count_fn(format_day(first), format_day(middle))
    _bisect(count_fn, first, middle, left_count, threshold, cap, out)
    right_first = middle + timedelta(days=1)
    right_count = count_fn(format_day(right_first), format_day(last))
    _bisect(count_fn, right_first, last, right_count, threshold, cap, out)


# --- E-utilities client -------------------------------------------------------------------------


class EUtilsClient:
    """E-utilities client with a request-rate limit, retries with exponential backoff, and a cache.

    ``opener`` maps a full request URL to response bytes; the default uses urllib. ``sleep`` and
    ``clock`` are injectable so tests run without waiting. The cache stores parsed results keyed by
    a hash of the query text plus the date window, so a repeated run makes no request.
    """

    def __init__(
        self,
        *,
        opener: Callable[[str], bytes] | None = None,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
        rps: float = RPS_WITHOUT_KEY,
        api_key: str | None = None,
        email: str | None = None,
        tool: str = TOOL_NAME,
        cache_dir: Path | None = None,
        max_retries: int = 4,
        backoff_base: float = 1.0,
        timeout: float = 60.0,
    ) -> None:
        limit = RPS_WITH_KEY if api_key else RPS_WITHOUT_KEY
        if not 0 < rps <= limit:
            raise ValueError(f"rps must be above 0 and at most {limit:g} for this key setting")
        self.rps = float(rps)
        self.api_key = api_key or None
        self.email = email or None
        self.tool = tool
        self.cache_dir = cache_dir
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._timeout = timeout
        self._opener = self._urlopen if opener is None else opener
        self._sleep = time.sleep if sleep is None else sleep
        self._clock = time.monotonic if clock is None else clock
        self._interval = 1.0 / self.rps
        self._next_slot = -math.inf

    def _urlopen(self, url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=self._timeout) as response:
            return response.read()

    def build_url(
        self, endpoint: str, params: Mapping[str, object], *, redact: bool = False
    ) -> str:
        """Return the request URL with the tool name and any contact or key parameters.

        ``redact=True`` replaces the email and API key with ``REDACTED`` for display.
        """
        query: dict[str, object] = {**params, "tool": self.tool}
        if self.email is not None:
            query["email"] = "REDACTED" if redact else self.email
        if self.api_key is not None:
            query["api_key"] = "REDACTED" if redact else self.api_key
        return f"{EUTILS_BASE}/{endpoint}.fcgi?{urllib.parse.urlencode(query)}"

    def count(self, term: str, mindate: str, maxdate: str) -> tuple[int, str]:
        """Return ``(count, query translation)`` for a publication-date window (pdat)."""
        name = _cache_name("count", term, mindate, maxdate)
        cached = self._cache_read(name)
        if cached is None:
            result = self._esearch(term, mindate, maxdate, retmax=0)
            if "count" not in result:
                raise EUtilsError("ESearch response had no count")
            cached = {
                "count": int(result["count"]),
                "translation": str(result.get("querytranslation") or ""),
            }
            self._cache_write(name, cached)
        return int(cached["count"]), str(cached["translation"])

    def pmids(self, term: str, mindate: str, maxdate: str, retmax: int = ESEARCH_MAX) -> list[str]:
        """Return up to ``retmax`` PMIDs for a publication-date window (pdat)."""
        if not 1 <= retmax <= ESEARCH_MAX:
            raise ValueError(f"retmax must be between 1 and {ESEARCH_MAX}")
        name = _cache_name("pmids", term, mindate, maxdate, extra=f"_r{retmax}")
        cached = self._cache_read(name)
        if cached is None:
            result = self._esearch(term, mindate, maxdate, retmax=retmax)
            cached = {"idlist": [str(pmid) for pmid in result.get("idlist") or []]}
            self._cache_write(name, cached)
        return list(cached["idlist"])

    def doi_years(self, pmids: Iterable[str]) -> dict[str, DoiYear]:
        """Return ``{pmid: (doi, year)}`` from ESummary in batches.

        Records missing from the response map to ``(None, None)``.
        """
        ids = list(dict.fromkeys(str(pmid) for pmid in pmids))
        found: dict[str, DoiYear] = {}
        for offset in range(0, len(ids), SUMMARY_BATCH):
            found.update(self._summaries(ids[offset : offset + SUMMARY_BATCH]))
        return {pmid: found.get(pmid, (None, None)) for pmid in ids}

    def _esearch(self, term: str, mindate: str, maxdate: str, *, retmax: int) -> dict[str, Any]:
        payload = self._get_json(
            "esearch",
            {
                "db": "pubmed",
                "term": term,
                "datetype": "pdat",
                "mindate": mindate,
                "maxdate": maxdate,
                "retmode": "json",
                "retmax": retmax,
                "retstart": 0,
            },
        )
        result = payload.get("esearchresult")
        if not isinstance(result, dict):
            raise EUtilsError("ESearch response had no esearchresult object")
        if "ERROR" in result:
            raise EUtilsError(f"ESearch rejected the query: {result['ERROR']}")
        return result

    def _summaries(self, batch: list[str]) -> dict[str, DoiYear]:
        digest = hashlib.sha256(",".join(batch).encode("utf-8")).hexdigest()
        name = f"esummary_{digest}.json"
        cached = self._cache_read(name)
        if cached is None:
            payload = self._get_json(
                "esummary", {"db": "pubmed", "id": ",".join(batch), "retmode": "json"}
            )
            records = payload.get("result")
            if not isinstance(records, dict):
                raise EUtilsError("ESummary response had no result object")
            cached = {}
            for pmid in batch:
                record = records.get(pmid)
                if isinstance(record, dict):
                    cached[pmid] = [_record_doi(record), _record_year(record)]
                else:
                    cached[pmid] = [None, None]
            self._cache_write(name, cached)
        return {pmid: (pair[0], pair[1]) for pmid, pair in cached.items()}

    def _get_json(self, endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        raw = self._fetch(self.build_url(endpoint, params))
        try:
            payload = json.loads(raw)
        except ValueError:
            raise EUtilsError(f"{endpoint} response was not JSON") from None
        if not isinstance(payload, dict):
            raise EUtilsError(f"{endpoint} response was not a JSON object")
        return payload

    def _fetch(self, url: str) -> bytes:
        """Fetch with rate limiting. Retries HTTP 429, 5xx and network errors with backoff.

        Error messages never include the URL, so the email and API key cannot leak through them.
        """
        attempts = self.max_retries + 1
        reason = "no attempt made"
        for attempt in range(attempts):
            self._throttle()
            try:
                return self._opener(url)
            except urllib.error.HTTPError as error:
                if error.code != 429 and error.code < 500:
                    raise EUtilsError(f"NCBI returned HTTP {error.code}") from None
                reason = f"HTTP {error.code}"
            except OSError as error:
                reason = type(error).__name__
            if attempt + 1 < attempts:
                self._sleep(self.backoff_base * 2**attempt)
        raise EUtilsError(f"NCBI request failed after {attempts} attempts ({reason})")

    def _throttle(self) -> None:
        now = self._clock()
        wait = self._next_slot - now
        if wait > 0:
            self._sleep(wait)
            now = self._clock()
        self._next_slot = now + self._interval

    def _cache_read(self, name: str) -> dict[str, Any] | None:
        if self.cache_dir is None:
            return None
        path = self.cache_dir / name
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _cache_write(self, name: str, payload: Mapping[str, Any]) -> None:
        if self.cache_dir is None:
            return
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / name).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _cache_name(op: str, term: str, mindate: str, maxdate: str, extra: str = "") -> str:
    digest = hashlib.sha256(term.encode("utf-8")).hexdigest()
    window = f"{mindate.replace('/', '-')}_{maxdate.replace('/', '-')}"
    return f"{op}_{digest}_{window}{extra}.json"


def _record_doi(record: Mapping[str, Any]) -> str | None:
    for article in record.get("articleids") or []:
        if isinstance(article, dict) and article.get("idtype") == "doi" and article.get("value"):
            return str(article["value"]).strip() or None
    return None


def _record_year(record: Mapping[str, Any]) -> int | None:
    for field in ("sortpubdate", "pubdate"):
        match = re.search(r"(\d{4})", str(record.get(field) or ""))
        if match:
            return int(match.group(1))
    return None


# --- Reference-set run --------------------------------------------------------------------------


def _count_partitions(
    client: EUtilsClient, term: str, start: str, end: str, cap: int, margin: int
) -> tuple[list[DatePartition], str]:
    """Partition one chunk's window; return the partitions and the root query translation."""
    translations: dict[tuple[str, str], str] = {}

    def count_fn(first: str, last: str) -> int:
        count, translation = client.count(term, first, last)
        translations.setdefault((first, last), translation)
        return count

    partitions = partition_dates(count_fn, start, end, cap=cap, margin=margin)
    return partitions, translations[(start, end)]


def run_reference_set(
    reference_set: str,
    *,
    include_path: Path | str,
    exclude_path: Path | str | None,
    affiliation: str | None,
    client: EUtilsClient,
    start: str,
    end: str,
    cap: int = DEFAULT_CAP,
    margin: int = DEFAULT_MARGIN,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Retrieve the reference PMIDs for one set and return ``(rows, manifest)``.

    Each OR chunk of the include query is partitioned by publication date so every partition is
    under ``cap - margin`` records, then each partition's PMIDs are fetched. Rows hold unique PMIDs
    in numeric order; ``chunk_id`` and ``partition`` name the first chunk and partition that
    returned the PMID. Nothing is written to disk.
    """
    threshold = retrieval_threshold(cap, margin)
    first, last = parse_day(start), parse_day(end)
    if first > last:
        raise ValueError("start must not be after end")
    window_start, window_end = format_day(first), format_day(last)

    include = read_query_file(include_path)
    exclude = read_query_file(exclude_path) if exclude_path is not None else ""
    whole_term, chunk_terms = build_terms(include, exclude, affiliation)
    _, whole_translation = client.count(whole_term, window_start, window_end)

    chunk_records: list[dict[str, Any]] = []
    hits: list[tuple[str, str, str]] = []
    for index, term in enumerate(chunk_terms, start=1):
        chunk_id = f"c{index:03d}"
        partitions, translation = _count_partitions(
            client, term, window_start, window_end, cap, margin
        )
        partition_records: list[dict[str, Any]] = []
        for part in partitions:
            pmids = client.pmids(term, part.start, part.end)
            label = f"{part.start}..{part.end}"
            partition_records.append(
                {"start": part.start, "end": part.end, "count": part.count, "retrieved": len(pmids)}
            )
            hits.extend((chunk_id, label, pmid) for pmid in pmids)
        chunk_records.append(
            {
                "chunk_id": chunk_id,
                "query_text": term,
                "query_translation": translation,
                "count": sum(part.count for part in partitions),
                "partitions": partition_records,
            }
        )

    first_seen: dict[str, tuple[str, str]] = {}
    for chunk_id, label, pmid in hits:
        first_seen.setdefault(pmid, (chunk_id, label))
    ordered = sorted(first_seen, key=int)
    details = client.doi_years(ordered)
    rows: list[dict[str, Any]] = []
    for pmid in ordered:
        doi, year = details.get(pmid, (None, None))
        chunk_id, label = first_seen[pmid]
        rows.append(
            {"pmid": pmid, "doi": doi, "pub_year": year, "chunk_id": chunk_id, "partition": label}
        )

    stamp = datetime.now(UTC) if now is None else now
    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "reference_set": reference_set,
        "affiliation": affiliation,
        "query_text": whole_term,
        "query_hash": hashlib.sha256(whole_term.encode("utf-8")).hexdigest(),
        "query_translation": whole_translation,
        "run_timestamp": stamp.isoformat(timespec="seconds"),
        "script_version": SCRIPT_VERSION,
        "parameters": {
            "start": window_start,
            "end": window_end,
            "cap": cap,
            "margin": margin,
            "threshold": threshold,
            "rps": client.rps,
            "tool": client.tool,
            "api_key_used": client.api_key is not None,
            "cache_used": client.cache_dir is not None,
        },
        "chunks": chunk_records,
        "total_unique_pmids": len(rows),
    }
    return rows, manifest


# --- Coverage -----------------------------------------------------------------------------------

_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)


def _norm_pmid(value: object) -> str | None:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if value is None:
        return None
    text = str(value).strip()
    return text if text.isdigit() else None


def _norm_doi(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = _DOI_PREFIX.sub("", value.strip()).strip().lower()
    return text or None


def _year_key(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return text if text.isdigit() else "unknown"


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def coverage(
    reference_rows: Iterable[Mapping[str, Any]], atlas_works: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    """Coverage of PubMed reference records by Atlas works, joined by PMID then DOI.

    A reference record is covered when its PMID is an Atlas work's PMID; otherwise it is covered
    when its DOI (lowercased, ``https://doi.org/`` stripped) matches an Atlas work's DOI. Atlas
    works with a null PMID still join by DOI. ``join_rate`` is the share of Atlas works that carry
    a PMID at all.
    """
    reference: dict[str, Mapping[str, Any]] = {}
    for row in reference_rows:
        pmid = _norm_pmid(row.get("pmid"))
        if pmid is not None:
            reference.setdefault(pmid, row)
    ref_dois = {_norm_doi(row.get("doi")) for row in reference.values()}
    ref_dois.discard(None)

    works = list(atlas_works)
    atlas_pmids: set[str] = set()
    atlas_dois: set[str] = set()
    with_pmid = 0
    atlas_matched = 0
    for work in works:
        pmid = _norm_pmid(work.get("pmid"))
        doi = _norm_doi(work.get("doi"))
        if pmid is not None:
            atlas_pmids.add(pmid)
            with_pmid += 1
        if doi is not None:
            atlas_dois.add(doi)
        if pmid in reference or doi in ref_dois:
            atlas_matched += 1

    by_year: dict[str, dict[str, int]] = {}
    matched_by_pmid = 0
    matched_by_doi = 0
    for pmid, row in reference.items():
        doi = _norm_doi(row.get("doi"))
        bucket = by_year.setdefault(_year_key(row.get("pub_year")), {"ref": 0, "covered": 0})
        bucket["ref"] += 1
        if pmid in atlas_pmids:
            matched_by_pmid += 1
            bucket["covered"] += 1
        elif doi is not None and doi in atlas_dois:
            matched_by_doi += 1
            bucket["covered"] += 1

    covered_total = matched_by_pmid + matched_by_doi
    years = sorted(by_year, key=lambda key: (key == "unknown", key))
    return {
        "reference_total": len(reference),
        "covered_total": covered_total,
        "coverage": _ratio(covered_total, len(reference)),
        "matched_by_pmid": matched_by_pmid,
        "matched_by_doi": matched_by_doi,
        "atlas_works_total": len(works),
        "atlas_works_with_pmid": with_pmid,
        "join_rate": _ratio(with_pmid, len(works)),
        "atlas_works_matched": atlas_matched,
        "by_year": {
            year: {
                "reference_total": by_year[year]["ref"],
                "covered_total": by_year[year]["covered"],
                "coverage": _ratio(by_year[year]["covered"], by_year[year]["ref"]),
            }
            for year in years
        },
    }
