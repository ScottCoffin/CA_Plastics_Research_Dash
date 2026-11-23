"""Native-language probe of OpenAlex (BQ-S4, Add-on A3 §5.7).

Each A3 §5.7 term set is one OR-group of the strings registered in
``config/search_vocabulary_v1.yml``. For each set the probe asks OpenAlex for the number of
works whose title or abstract matches it, the language labels of those works (one optional
``group_by=language`` request), a fixed-seed random sample of up to 50 works, and which sampled
works the main v3.1 query also retrieves (the overlap on the sample).

Writes ``site/data/language_probe.json`` (schema ``bqs-v1``). Every OpenAlex request goes through
the shared client and budget guard, as in ``scripts/fetch_trend_global.py``. Responses are cached
under ``data/interim/language_probe/`` (gitignored), so a rerun with the cache spends nothing.

Usage:
    py -3.14 scripts/fetch_language_probe.py                    # cached where possible, else live
    py -3.14 scripts/fetch_language_probe.py --offline          # cache only; no network
    py -3.14 scripts/fetch_language_probe.py --force            # refetch every request
    py -3.14 scripts/fetch_language_probe.py --check            # validate the committed file only
    py -3.14 scripts/fetch_language_probe.py --offline --check  # also rebuild from the cache
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, NamedTuple

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from atlas.ingest.openalex import (  # noqa: E402
    OPENALEX_BASE,
    _request_json,
    compact_openalex_id,
    load_openalex_key,
)
from atlas.query import load_query_config, openalex_filter, type_filters  # noqa: E402
from atlas.util.budget import (  # noqa: E402
    GATEWAY_STATUSES,
    UNKNOWN_429_CREDITS,
    conservative_request_cost,
    daily_logged_usage,
    resolve_openalex_budget,
)
from atlas.util.cost import ApiCostLogger  # noqa: E402

SCHEMA_VERSION = "bqs-v1"
VOCABULARY_VERSION = "search_vocabulary_v1"
A3_PROBE_SOURCE = "A3 §5.7"
SAMPLE_SEED = 20261122
SAMPLE_LIMIT = 50
SAMPLE_SELECT = "id,display_name,language,publication_year,primary_location"
# Run-level ceiling on logged OpenAlex spend (USD), stricter than the daily budget.
RUN_CAP_USD = Decimal("0.09")
MAX_HTTP_ATTEMPTS = 3
MAX_URL_CHARS = 8000
MISSING_LANGUAGE = "unlabelled"
SOURCE_TEXT = (
    "OpenAlex works API: title_and_abstract.search counts, group_by=language, a fixed-seed "
    "sample (sample and seed), and an ids.openalex overlap check against the main query"
)
DEFAULT_OUTPUT = ROOT / "site" / "data" / "language_probe.json"
DEFAULT_CONFIG = ROOT / "config" / "queries.yml"
DEFAULT_VOCABULARY = ROOT / "config" / "search_vocabulary_v1.yml"
DEFAULT_BUDGET = ROOT / "config" / "budget.yml"
DEFAULT_CACHE_DIR = ROOT / "data" / "interim" / "language_probe"
DEFAULT_USAGE_LOG = ROOT / "data" / "logs" / "api_usage.jsonl"


class FetchError(RuntimeError):
    """A request, budget, cache or validation failure: nothing is written."""


class BudgetRefused(FetchError):
    """The budget guard refused a request before it was sent."""


class CacheMiss(FetchError):
    """An offline run needs a response that is not in the cache."""


class TermSet(NamedTuple):
    """One A3 §5.7 probe: registered strings joined as one OR-group."""

    id: str
    languages: tuple[str, ...]
    terms: tuple[str, ...]
    a3_count: int


# Strings are the registered rows of config/search_vocabulary_v1.yml (A3 §5.7 probe rows).
# validate_payload checks every string, its language and its A3 probe count against the register.
TERM_SETS: tuple[TermSet, ...] = (
    TermSet("zh-microplastic", ("zh",), ("微塑料",), 2025),
    TermSet("zh-nanoplastic", ("zh",), ("纳米塑料",), 364),
    TermSet("zh-plastic-pollution", ("zh",), ("塑料污染",), 606),
    TermSet("ja-microplastic", ("ja",), ("マイクロプラスチック",), 347),
    TermSet("ja-nanoplastic", ("ja",), ("ナノプラスチック",), 9),
    TermSet("ko-fine-plastic", ("ko",), ("미세플라스틱",), 133),
    TermSet("ko-microplastic", ("ko",), ("마이크로플라스틱",), 5),
    TermSet("de-microplastic", ("de",), ("Mikroplastik",), 1663),
    TermSet("de-nanoplastic", ("de",), ("Nanoplastik",), 63),
    TermSet(
        "de-plastic-waste-pollution",
        ("de",),
        ("Plastikmüll", "Kunststoffabfälle", "Plastikverschmutzung"),
        268,
    ),
    TermSet("es-pt-microplastic", ("es", "pt"), ("microplásticos",), 1817),
    TermSet(
        "es-marine-litter-pollution",
        ("es",),
        ("basura marina", "contaminación por plásticos", "residuos plásticos"),
        1738,
    ),
    TermSet("fr-microplastic", ("fr",), ("microplastiques",), 523),
    TermSet(
        "fr-plastic-waste-pollution",
        ("fr",),
        ("déchets plastiques", "pollution plastique", "nanoplastiques"),
        645,
    ),
    TermSet("ru-microplastic", ("ru",), ("микропластик",), 178),
    TermSet(
        "no-da-plastic-pollution",
        ("no", "da"),
        ("mikroplast", "plastforurensning", "marint søppel"),
        98,
    ),
)

METHOD = (
    "Each term set is one OR-group of the strings registered for it in the project's search "
    "vocabulary register (the native-language probe rows only). For each set the probe asks "
    "OpenAlex for: the number of works whose title or abstract matches the group (count); how "
    "those works are labelled by language (language_label_counts, one request per set, skipped "
    "when the budget guard would refuse it); and a random sample of up to 50 works, drawn with the "
    "fixed seed 20261122 (sample). Each sampled work is then checked against the main plastics "
    "query, plastic-v3.1 with its type exclusions, to show which sampled works the main query "
    "also retrieves (sample_in_v31). That is an overlap on the sample only: a share of the "
    "sample, not a completeness rate for either query. Every request goes through the project's "
    "OpenAlex client and budget guard, and no paid filters are used. Cost is OpenAlex's reported "
    "credits at USD 0.0001 per credit, using for each request the larger of the reported cost and "
    "the credit price. Responses are cached, so the file can be rebuilt without network access."
)

CAVEATS: tuple[str, ...] = (
    "Many non-English papers have English titles and abstracts. A match on a native-language "
    "term shows that the string appears in OpenAlex's indexed title or abstract. It does not show "
    "the paper's own language, and sample titles are OpenAlex metadata, which can be translated.",
    "OpenAlex language labels are imperfect. The project's planning notes cite Céspedes et al. "
    "2025 for false positives among declared-language labels. That source has not been checked "
    "against its text, so no error rate is claimed here. The counts use OpenAlex's labels as "
    "given.",
    "Native-language hits include public-communication items, which are written for the public "
    "rather than as research articles. The term counts do not exclude document types; the overlap "
    "check applies the project's type exclusions.",
    "OpenAlex's search matches stemmed word forms. The project's query notes record this for "
    "English terms (for example, 'microplasticity' matches 'microplastic'). The native-language "
    "strings were not tested for it, so a count may include related forms.",
    "Some strings are spelled the same in other languages, so a set can contain works in other "
    "languages. For example, OpenAlex's labels for the German Mikroplastik set include Indonesian "
    "and Turkish works, which use the same word. The counts are not restricted to the labelled "
    "language; language_label_counts shows the split.",
    "The 纳米塑料 set has mixed senses. The vocabulary register notes a 2001 materials article "
    "among its hits, so the count includes works outside plastic pollution research.",
    "microplásticos is one set for Spanish and Portuguese, and the Norwegian and Danish strings "
    "are one set. OpenAlex counts are not split by language there. The register labels these "
    "strings Spanish or Norwegian only; no Portuguese or Danish strings are registered.",
    "Counts are OpenAlex totals taken on the run date, under the search form described in the "
    "method. The A3 probe counts (2026-11-18) are shown for comparison. Most sets agree with them "
    "within about 7 per cent. The Chinese, Russian and Norwegian and Danish sets differ by much "
    "more, and index growth does not explain that. This probe does not confirm the search form "
    "behind the A3 figures, so compare the counts with them with care.",
    "Each sample is a fixed-seed random draw of up to 50 works. Where a term set has 50 or fewer "
    "works, the sample is the whole set, so the share describes that set. Shares from samples of "
    "this size carry wide uncertainty.",
    "The overlap is measured on the sample only. It shows how many sampled works the main plastics "
    "query (plastic-v3.1) also retrieves. It is a share of the sample, not a completeness rate for "
    "either query.",
    "The probe does not read abstracts. No person has checked the language or topic of any "
    "sampled work.",
    "Only the registered strings are searched. A term that is not in the register, a translation "
    "or a transliteration is not counted, so these counts are not totals for native-language "
    "literature.",
)

NOT_COVERED: tuple[str, ...] = (
    "Lifecycle-and-society and lens terms in any language, for example waste-colonialism, justice "
    "and transboundary-trade terms.",
    "Arabic, Turkish, Indonesian, Hindi, Dutch, Polish and other languages: no term strings are "
    "registered for them, so they are not searched as languages. Works in these languages can "
    "still match a registered string that is spelled the same (see the caveats).",
    "Italian. The A3 probe gives a count of 85 but no term string, so Italian was not run.",
    "Local-language terms registered for testing outside this probe (for example cartoneros and "
    "Te Moananui) were not run.",
)

TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "generated_at",
        "query_version",
        "vocabulary_version",
        "source",
        "sample_seed",
        "sample_limit",
        "method",
        "cost",
        "term_sets",
        "caveats",
        "not_covered",
    }
)
SET_KEYS = frozenset(
    {
        "id",
        "languages",
        "terms",
        "query",
        "a3_count_2026_11_18",
        "count",
        "language_label_counts",
        "fetched_at",
        "sample_seed",
        "sample",
        "sample_size",
        "sample_in_v31",
        "sample_language_label_counts",
    }
)
SAMPLE_KEYS = frozenset({"id", "title", "language", "year", "venue", "in_v31"})
CAVEAT_THEMES = ("english", "céspedes", "label", "public")
NOT_COVERED_THEMES = ("italian", "arabic", "turkish", "indonesian", "hindi", "dutch", "polish")
EXPERT_WORD = re.compile(r"\bexperts?\b", re.IGNORECASE)


def term_query(terms: Sequence[str]) -> str:
    """One OR-group of quoted phrases, as OpenAlex boolean search syntax."""

    return "(" + " OR ".join(f'"{term}"' for term in terms) + ")"


def works_url(params: Mapping[str, object]) -> str:
    return f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"


def language_label(value: object) -> str:
    """OpenAlex language code (``en``, not its ``https://openalex.org/languages/en`` key)."""

    text = str(value or "").strip().rstrip("/").rsplit("/", 1)[-1]
    return text if text and text.lower() not in {"unknown", "null", "none"} else MISSING_LANGUAGE


def _sorted_counts(counts: Mapping[str, int]) -> dict[str, int]:
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _leading_count(text: object) -> int | None:
    match = re.match(r"\s*(\d[\d,]*)", str(text or ""))
    return int(match.group(1).replace(",", "")) if match else None


def load_vocabulary_rows(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = data.get("terms") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise FetchError(f"{path.name} has no terms list")
    return [row for row in rows if isinstance(row, dict)]


def vocabulary_problems(
    rows: Sequence[Mapping[str, Any]], term_sets: Sequence[TermSet] = TERM_SETS
) -> list[str]:
    """Mismatches between the probe term sets and the registered rows (empty when they agree)."""

    by_term: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        by_term.setdefault(str(row.get("term")), row)
    problems: list[str] = []
    for ts in term_sets:
        for term in ts.terms:
            row = by_term.get(term)
            if row is None:
                problems.append(f"{ts.id}: {term} is not in the search vocabulary register")
                continue
            if row.get("language") not in ts.languages:
                problems.append(
                    f"{ts.id}: {term} is registered as {row.get('language')!r}, "
                    f"not in {list(ts.languages)}"
                )
            if _leading_count(row.get("probe_count_and_date")) != ts.a3_count:
                problems.append(
                    f"{ts.id}: {term} probe count {row.get('probe_count_and_date')!r} "
                    f"differs from {ts.a3_count}"
                )
    used = {term for ts in term_sets for term in ts.terms}
    for row in rows:
        if row.get("source") == A3_PROBE_SOURCE and row.get("term") not in used:
            problems.append(f"A3 §5.7 register row {row.get('term')} has no term set")
    return problems


def cache_path(cache_dir: Path, kind: str, url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return cache_dir / f"{kind}-{digest}.json"


def read_entry(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FetchError(f"unreadable cache entry {path.name}") from exc
    if not isinstance(entry, dict) or not isinstance(entry.get("body"), dict):
        raise FetchError(f"malformed cache entry {path.name}")
    return entry


def write_entry(path: Path, entry: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(entry, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def accounted(
    metrics: Sequence[Mapping[str, Any]], cost_per_credit_usd: Decimal
) -> tuple[Decimal, Decimal]:
    """Credits and conservative USD for the attempts of one request (budget-guard rules)."""

    credits_total = Decimal(0)
    cost_total = Decimal(0)
    for metric in metrics:
        if metric.get("credits_known"):
            credits = Decimal(str(metric["credits"]))
            cost_total += conservative_request_cost(
                metric["cost_usd"],
                credits,
                cost_per_credit_usd,
                meta_cost_known=bool(metric.get("cost_known")),
            )
        else:
            if metric.get("status_code") not in (429, *GATEWAY_STATUSES):
                raise FetchError("OpenAlex returned no usable credit count for a request")
            credits = UNKNOWN_429_CREDITS
            cost_total += credits * cost_per_credit_usd
        credits_total += credits
    return credits_total, cost_total


class Probe:
    """Cache-first, budget-guarded access to the OpenAlex works endpoint."""

    def __init__(
        self,
        *,
        offline: bool,
        force: bool,
        cache_dir: Path,
        usage_log: Path,
        budget_path: Path,
    ) -> None:
        self.offline = offline
        self.force = force
        self.cache_dir = cache_dir
        self.usage_log = usage_log
        self.used: dict[Path, dict[str, Any]] = {}
        self.fresh_requests = 0
        self.budget = None
        self.baseline_cost = Decimal(0)
        if not offline:
            try:
                self.budget = resolve_openalex_budget(budget_path)
            except ValueError as exc:
                raise FetchError(f"budget configuration: {exc}") from exc
            # Spend already logged today counts against the daily ceilings only; the run cap
            # measures what this run logs after this point.
            self.baseline_cost, _ = daily_logged_usage(
                usage_log, cost_per_credit_usd=self.budget.cost_per_credit_usd
            )

    def _run_spend(self) -> Decimal:
        assert self.budget is not None
        cost, _ = daily_logged_usage(
            self.usage_log, cost_per_credit_usd=self.budget.cost_per_credit_usd
        )
        return cost - self.baseline_cost

    def _preflight(self) -> None:
        assert self.budget is not None
        cost, credits = daily_logged_usage(
            self.usage_log, cost_per_credit_usd=self.budget.cost_per_credit_usd
        )
        error = self.budget.reserve_error(cost_usd=cost, credits=credits)
        if error:
            raise BudgetRefused(f"budget guard: {error}")
        spent = cost - self.baseline_cost
        if spent + self.budget.reserve_cost_usd > RUN_CAP_USD:
            raise BudgetRefused(
                f"run cap: this run has logged USD {spent:.4f}; the next request would pass "
                f"USD {RUN_CAP_USD}"
            )

    def get(
        self, url: str, *, kind: str, set_id: str, optional: bool = False
    ) -> dict[str, Any] | None:
        """Return the cached or freshly fetched entry, or None for an optional skipped request."""

        path = cache_path(self.cache_dir, kind, url)
        entry = None if self.force else read_entry(path)
        if entry is None:
            entry = self._fetch(url, path, kind=kind, set_id=set_id, optional=optional)
            if entry is None:
                return None
        self.used[path] = entry
        return entry

    def require(self, url: str, *, kind: str, set_id: str) -> dict[str, Any]:
        entry = self.get(url, kind=kind, set_id=set_id)
        if entry is None:
            raise FetchError(f"{set_id}: no {kind} response")
        return entry

    def _fetch(
        self, url: str, path: Path, *, kind: str, set_id: str, optional: bool
    ) -> dict[str, Any] | None:
        if self.offline:
            if optional:
                return None
            raise CacheMiss(f"no cached {kind} response for {set_id}; run once without --offline")
        try:
            self._preflight()
        except BudgetRefused:
            if optional:
                return None
            raise
        fetched_at = datetime.now(UTC).isoformat(timespec="seconds")
        try:
            with ApiCostLogger(
                f"language-probe-{kind}-{set_id}-{fetched_at}", self.usage_log
            ) as logger:
                body = _request_json(url, logger=logger, attempts=MAX_HTTP_ATTEMPTS)
        except Exception as exc:  # OpenAlex errors, usage-metadata errors, network errors
            raise FetchError(f"OpenAlex request failed ({kind}, {set_id}): {exc}") from exc
        assert self.budget is not None
        credits, cost = accounted(logger.request_metrics, self.budget.cost_per_credit_usd)
        entry = {
            "kind": kind,
            "set_id": set_id,
            "url": url,
            "fetched_at": fetched_at,
            "credits": str(credits),
            "cost_usd": str(cost),
            "body": body,
        }
        write_entry(path, entry)
        self.fresh_requests += 1
        spent = self._run_spend()
        if spent > RUN_CAP_USD:
            raise FetchError(
                f"run cap: this run has logged USD {spent:.4f}, above USD {RUN_CAP_USD}"
            )
        return entry


def _results(entry: Mapping[str, Any], set_id: str) -> list[Any]:
    results = entry["body"].get("results")
    if not isinstance(results, list):
        raise FetchError(f"{set_id}: OpenAlex response has no results list")
    return results


def _meta_count(entry: Mapping[str, Any], set_id: str) -> int:
    meta = entry["body"].get("meta")
    count = meta.get("count") if isinstance(meta, dict) else None
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise FetchError(f"{set_id}: OpenAlex response has no work count")
    return count


def _sample_row(item: Mapping[str, Any]) -> dict[str, Any]:
    location = item.get("primary_location")
    source = location.get("source") if isinstance(location, Mapping) else None
    venue = source.get("display_name") if isinstance(source, Mapping) else None
    return {
        "id": compact_openalex_id(item.get("id")),
        "title": item.get("display_name") or None,
        "language": item.get("language") or None,
        "year": item.get("publication_year"),
        "venue": venue or None,
    }


def _overlap_hits(
    probe: Probe, v31_filters: Sequence[str], ids: Sequence[str], set_id: str
) -> set[str]:
    """Which of these works the v3.1 query also retrieves (split in two if the URL is too long)."""

    if not ids:
        return set()
    url = works_url(
        {
            "filter": "ids.openalex:" + "|".join(ids) + "," + ",".join(v31_filters),
            "per_page": SAMPLE_LIMIT,
            "select": "id",
        }
    )
    if len(url) > MAX_URL_CHARS:
        if len(ids) == 1:
            raise FetchError(f"{set_id}: overlap request exceeds {MAX_URL_CHARS} characters")
        half = len(ids) // 2
        return _overlap_hits(probe, v31_filters, ids[:half], set_id) | _overlap_hits(
            probe, v31_filters, ids[half:], set_id
        )
    entry = probe.require(url, kind="overlap", set_id=set_id)
    results = _results(entry, set_id)
    meta = entry["body"].get("meta") or {}
    if int(meta.get("count") or 0) > len(results):
        raise FetchError(f"{set_id}: overlap result spans more than one page")
    return {compact_openalex_id(row.get("id")) for row in results if isinstance(row, Mapping)}


def _group_counts(body: Mapping[str, Any]) -> dict[str, int]:
    """Language counts for the whole set. OpenAlex omits works with no language from group_by,
    so the remainder up to meta.count is reported as unlabelled."""

    counts: dict[str, int] = {}
    for group in body.get("group_by") or []:
        label = language_label(group.get("key"))
        counts[label] = counts.get(label, 0) + int(group.get("count") or 0)
    meta = body.get("meta")
    total = int(meta.get("count") or 0) if isinstance(meta, Mapping) else 0
    grouped = sum(counts.values())
    if grouped > total:
        raise FetchError("language groups add up to more works than the count")
    if grouped < total:
        counts[MISSING_LANGUAGE] = counts.get(MISSING_LANGUAGE, 0) + total - grouped
    return _sorted_counts(counts)


def _sample_language_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = language_label(row.get("language"))
        counts[label] = counts.get(label, 0) + 1
    return _sorted_counts(counts)


def build_payload(probe: Probe, config: Mapping[str, Any], *, generated_at: str) -> dict[str, Any]:
    """Run (or read from cache) every request and assemble the bqs-v1 payload."""

    v31_filters = [openalex_filter(config), *type_filters(config)]
    records: list[dict[str, Any]] = []
    searches: list[str] = []
    for ts in TERM_SETS:
        query = term_query(ts.terms)
        search = f"title_and_abstract.search:{query}"
        count_entry = probe.require(
            works_url({"filter": search, "per_page": 1, "select": "id"}),
            kind="count",
            set_id=ts.id,
        )
        count = _meta_count(count_entry, ts.id)
        sample_entry = probe.require(
            works_url(
                {
                    "filter": search,
                    "sample": SAMPLE_LIMIT,
                    "seed": SAMPLE_SEED,
                    "per_page": SAMPLE_LIMIT,
                    "select": SAMPLE_SELECT,
                }
            ),
            kind="sample",
            set_id=ts.id,
        )
        sample = [_sample_row(item) for item in _results(sample_entry, ts.id)]
        hits = _overlap_hits(probe, v31_filters, [row["id"] for row in sample], ts.id)
        for row in sample:
            row["in_v31"] = row["id"] in hits
        records.append(
            {
                "id": ts.id,
                "languages": list(ts.languages),
                "terms": list(ts.terms),
                "query": query,
                "a3_count_2026_11_18": ts.a3_count,
                "count": count,
                "language_label_counts": None,
                "fetched_at": count_entry["fetched_at"],
                "sample_seed": SAMPLE_SEED,
                "sample": sample,
                "sample_size": len(sample),
                "sample_in_v31": sum(1 for row in sample if row["in_v31"]),
                "sample_language_label_counts": _sample_language_counts(sample),
            }
        )
        searches.append(search)
    # Optional: language labels for the whole set. Requested last, so the essential requests
    # are never displaced by the budget; a refused request leaves the field null.
    for record, search in zip(records, searches, strict=True):
        entry = probe.get(
            works_url({"filter": search, "group_by": "language"}),
            kind="languages",
            set_id=record["id"],
            optional=True,
        )
        if entry is not None:
            record["language_label_counts"] = _group_counts(entry["body"])
    credits = sum((Decimal(entry["credits"]) for entry in probe.used.values()), Decimal(0))
    usd = sum((Decimal(entry["cost_usd"]) for entry in probe.used.values()), Decimal(0))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "query_version": str(config["version"]),
        "vocabulary_version": VOCABULARY_VERSION,
        "source": SOURCE_TEXT,
        "sample_seed": SAMPLE_SEED,
        "sample_limit": SAMPLE_LIMIT,
        "method": METHOD,
        "cost": {"credits": int(credits), "usd": round(float(usd), 4)},
        "term_sets": records,
        "caveats": list(CAVEATS),
        "not_covered": list(NOT_COVERED),
    }


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_iso(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def _abstract_keys(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            if "abstract" in str(key).lower():
                found.append(str(key))
            found.extend(_abstract_keys(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_abstract_keys(item))
    return found


def _mentions(items: Sequence[str], word: str) -> bool:
    return word.lower() in " ".join(items).lower()


def _set_problems(record: object, ts: TermSet) -> list[str]:
    if not isinstance(record, Mapping):
        return [f"{ts.id}: term set is not an object"]
    problems: list[str] = []
    missing = sorted(SET_KEYS - set(record))
    extra = sorted(set(record) - SET_KEYS)
    if missing or extra:
        problems.append(f"{ts.id}: keys differ (missing {missing}, extra {extra})")
    expected = {
        "languages": list(ts.languages),
        "terms": list(ts.terms),
        "query": term_query(ts.terms),
        "a3_count_2026_11_18": ts.a3_count,
        "sample_seed": SAMPLE_SEED,
    }
    for name, value in expected.items():
        if record.get(name) != value:
            problems.append(f"{ts.id}: {name} does not match the probe definition")
    count = record.get("count")
    size = record.get("sample_size")
    sample = record.get("sample")
    if not _is_count(count):
        problems.append(f"{ts.id}: count must be a non-negative integer")
    if not isinstance(sample, list):
        problems.append(f"{ts.id}: sample must be a list")
        sample = []
    if not _is_count(size) or size != len(sample) or size > SAMPLE_LIMIT:
        problems.append(
            f"{ts.id}: sample_size must equal len(sample) and be at most {SAMPLE_LIMIT}"
        )
    if _is_count(count) and size != min(count, SAMPLE_LIMIT):
        problems.append(f"{ts.id}: sample_size must be min(count, {SAMPLE_LIMIT})")
    in_v31 = 0
    seen: set[str] = set()
    for item in sample:
        if not isinstance(item, Mapping) or set(item) != SAMPLE_KEYS:
            problems.append(f"{ts.id}: sample item keys must be {sorted(SAMPLE_KEYS)}")
            continue
        work_id = str(item.get("id") or "")
        if not work_id.startswith("W") or work_id in seen:
            problems.append(f"{ts.id}: sample ids must be unique OpenAlex work ids")
        seen.add(work_id)
        if not isinstance(item.get("in_v31"), bool):
            problems.append(f"{ts.id}: in_v31 must be a boolean")
        elif item["in_v31"]:
            in_v31 += 1
        if not (item.get("title") is None or isinstance(item.get("title"), str)):
            problems.append(f"{ts.id}: title must be text or null")
        if not (item.get("language") is None or isinstance(item.get("language"), str)):
            problems.append(f"{ts.id}: language must be text or null")
        if not (item.get("venue") is None or isinstance(item.get("venue"), str)):
            problems.append(f"{ts.id}: venue must be text or null")
        year = item.get("year")
        if not (year is None or _is_count(year)):
            problems.append(f"{ts.id}: year must be an integer or null")
    if record.get("sample_in_v31") != in_v31:
        problems.append(f"{ts.id}: sample_in_v31 does not match the sample flags")
    labels = record.get("language_label_counts")
    if labels is not None:
        if not isinstance(labels, Mapping) or not all(_is_count(v) for v in labels.values()):
            problems.append(f"{ts.id}: language_label_counts must map labels to counts")
        elif _is_count(count) and sum(labels.values()) != count:
            problems.append(f"{ts.id}: language_label_counts must sum to count")
    sample_labels = record.get("sample_language_label_counts")
    if not isinstance(sample_labels, Mapping) or not all(
        _is_count(v) for v in sample_labels.values()
    ):
        problems.append(f"{ts.id}: sample_language_label_counts must map labels to counts")
    elif sum(sample_labels.values()) != len(sample):
        problems.append(f"{ts.id}: sample_language_label_counts must sum to the sample")
    if not _is_iso(record.get("fetched_at")):
        problems.append(f"{ts.id}: fetched_at must be an ISO 8601 timestamp")
    return problems


def _cost_problems(cost: object) -> list[str]:
    if not isinstance(cost, Mapping) or set(cost) != {"credits", "usd"}:
        return ["cost must hold credits and usd"]
    problems: list[str] = []
    if not _is_count(cost["credits"]):
        problems.append("cost.credits must be a non-negative integer")
    usd = cost["usd"]
    if isinstance(usd, bool) or not isinstance(usd, int | float) or not 0 <= usd < 0.10:
        problems.append("cost.usd must be at least 0 and under USD 0.10")
    return problems


def validate_payload(payload: object, vocabulary_rows: Sequence[Mapping[str, Any]]) -> list[str]:
    """Problems with a bqs-v1 payload; an empty list means it passes."""

    if not isinstance(payload, Mapping):
        return ["payload is not a JSON object"]
    problems: list[str] = []
    if set(payload) != TOP_LEVEL_KEYS:
        problems.append(f"top-level keys differ: {sorted(set(payload) ^ TOP_LEVEL_KEYS)}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version must be {SCHEMA_VERSION!r}")
    if not _is_iso(payload.get("generated_at")):
        problems.append("generated_at must be an ISO 8601 timestamp")
    if payload.get("sample_seed") != SAMPLE_SEED or payload.get("sample_limit") != SAMPLE_LIMIT:
        problems.append("sample_seed and sample_limit do not match the probe definition")
    problems.extend(_cost_problems(payload.get("cost")))
    problems.extend(vocabulary_problems(vocabulary_rows))

    method = payload.get("method")
    caveats = payload.get("caveats")
    not_covered = payload.get("not_covered")
    if not isinstance(method, str) or not method.strip():
        problems.append("method must be non-empty text")
    if not isinstance(caveats, list) or not caveats or not all(isinstance(c, str) for c in caveats):
        problems.append("caveats must be a non-empty list of text")
        caveats = []
    if not isinstance(not_covered, list) or not all(isinstance(n, str) for n in not_covered):
        problems.append("not_covered must be a list of text")
        not_covered = []
    prose = [method if isinstance(method, str) else "", *caveats, *not_covered]
    for text in prose:
        if EXPERT_WORD.search(text):
            problems.append("method, caveats and not_covered must not use the word 'expert'")
            break
    for theme in CAVEAT_THEMES:
        if not _mentions(caveats, theme):
            problems.append(f"caveats must mention {theme!r}")
    for theme in NOT_COVERED_THEMES:
        if not _mentions(not_covered, theme):
            problems.append(f"not_covered must name {theme!r}")
    if "recall" in json.dumps(payload, ensure_ascii=False).lower():
        problems.append("the word 'recall' appears; describe the overlap as a share of the sample")
    abstract_keys = _abstract_keys(payload)
    if abstract_keys:
        problems.append(f"abstract keys must not be published: {sorted(set(abstract_keys))}")

    sets = payload.get("term_sets")
    set_ids: list[object] = []
    if isinstance(sets, list):
        set_ids = [s.get("id") if isinstance(s, Mapping) else None for s in sets]
    if not isinstance(sets, list) or set_ids != [ts.id for ts in TERM_SETS]:
        problems.append("term_sets must hold the A3 §5.7 probe sets in TERM_SETS order")
        return problems
    for record, ts in zip(sets, TERM_SETS, strict=True):
        problems.extend(_set_problems(record, ts))
    return problems


def _comparable(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "generated_at"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    """Atomic write with LF line endings and a trailing newline."""

    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text.encode("utf-8"))
    tmp.replace(path)


def _check(args: argparse.Namespace, rows: Sequence[Mapping[str, Any]]) -> int:
    try:
        committed = json.loads(args.output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read {args.output}: {exc}", file=sys.stderr)
        return 1
    problems = validate_payload(committed, rows)
    if args.offline and not problems:
        try:
            config = load_query_config(args.config)
            probe = Probe(
                offline=True,
                force=False,
                cache_dir=args.cache_dir,
                usage_log=args.usage_log,
                budget_path=args.budget,
            )
            rebuilt = build_payload(probe, config, generated_at=str(committed["generated_at"]))
        except FetchError as exc:
            problems.append(f"offline rebuild failed: {exc}")
        else:
            if _comparable(rebuilt) != _comparable(committed):
                problems.append("committed data differ from a rebuild of the cached responses")
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}", file=sys.stderr)
        return 1
    mode = "validated and rebuilt from cache" if args.offline else "validated"
    print(
        f"OK: {args.output.name} {mode}: {len(committed['term_sets'])} term sets, "
        f"{committed['cost']['credits']} credits, USD {committed['cost']['usd']}"
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--offline", action="store_true", help="use cached responses only")
    parser.add_argument("--check", action="store_true", help="validate the committed file only")
    parser.add_argument("--force", action="store_true", help="refetch every request")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--vocabulary", type=Path, default=DEFAULT_VOCABULARY)
    parser.add_argument("--budget", type=Path, default=DEFAULT_BUDGET)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--usage-log", type=Path, default=DEFAULT_USAGE_LOG)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        rows = load_vocabulary_rows(args.vocabulary)
    except (OSError, yaml.YAMLError, FetchError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.check:
        return _check(args, rows)
    problems = vocabulary_problems(rows)
    if problems:
        for problem in problems:
            print(f"error: {problem}; no request made, no file written", file=sys.stderr)
        return 1
    try:
        config = load_query_config(args.config)
        if not args.offline:
            load_openalex_key(ROOT / ".env")
        probe = Probe(
            offline=args.offline,
            force=args.force,
            cache_dir=args.cache_dir,
            usage_log=args.usage_log,
            budget_path=args.budget,
        )
        payload = build_payload(probe, config, generated_at=_now())
    except (FetchError, OSError, ValueError) as exc:
        print(f"error: {exc}; no file written", file=sys.stderr)
        return 1
    problems = validate_payload(payload, rows)
    if problems:
        for problem in problems:
            print(f"error: {problem}; no file written", file=sys.stderr)
        return 1
    write_json(args.output, payload)
    for record in payload["term_sets"]:
        print(
            f"{record['id']}: count {record['count']} (A3 {record['a3_count_2026_11_18']}); "
            f"sample {record['sample_size']}, in v3.1 {record['sample_in_v31']}"
        )
    skipped = [r["id"] for r in payload["term_sets"] if r["language_label_counts"] is None]
    if skipped:
        print(f"language_label_counts skipped (budget or offline): {', '.join(skipped)}")
    print(
        f"wrote {args.output.name}: {probe.fresh_requests} new request(s), "
        f"{len(probe.used) - probe.fresh_requests} from cache; cost {payload['cost']['credits']} "
        f"credits, USD {payload['cost']['usd']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
