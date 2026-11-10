"""Evidence-backed work-to-grant links (S9.1).

Matchers, in precedence order:

1. ``openalex-award``: an OpenAlex ``awards`` entry whose ``funder_award_id``
   normalizes to a grant of the same funder family. NSF uses the 7-digit award
   id. NIH uses the core project number (for example ``R01ES012345``), resolved
   to RePORTER ``appl_id`` values through a cached lookup.
2. ``acknowledgement-match``: an exact normalized award id found in cached
   acknowledgement or funding text. No such text is cached yet, so this matcher
   currently yields no links.
3. ``fixed-string``: a required acknowledgement phrase (for example COAST).

Uncertain candidates (funder family disagrees with the grant source) are kept
out of the links and returned separately for review.
"""

from __future__ import annotations

import json
import random
import re
import time
import unicodedata
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

USER_AGENT = "ca-plastics-atlas/0.1 (research dashboard)"
REPORTER_URL = "https://api.reporter.nih.gov/v2/projects/search"
REPORTER_BATCH = 50
REPORTER_PAGE = 500
MIN_REQUEST_INTERVAL = 1.1

# TODO(S9.1): the COAST required acknowledgement name is not recorded anywhere in
# the repo (csucoast.org was unreachable on 2026-11-09). Set the exact phrase here
# once the owner or the COAST award letters provide it.
COAST_ACK_PHRASE: str | None = None
COAST_SOURCE = "csu_coast"

NSF_FUNDER_IDS = frozenset(
    {
        "https://openalex.org/F4320306076",  # National Science Foundation
        "https://openalex.org/F4320337367",  # Division of Materials Research
    }
)
NSF_FUNDER_NAME_RE = re.compile(r"National Science Foundation|\bNSF\b|Division of", re.I)
NIH_FUNDER_NAME_RE = re.compile(
    r"National Institutes? of Health|National (?:Institute|Cancer|Heart|Center|Library|Eye)"
    r"|\bNIH\b|NIEHS",
    re.I,
)

EVIDENCE_PRECEDENCE = {
    "openalex-award": 0,
    "acknowledgement-match": 1,
    "fixed-string": 2,
}
ACK_SECTIONS = ("acknowledgements", "acknowledgments", "funding")

_SEPARATORS = re.compile(r"[\s\-‐-―−/#_.]+")
_NSF_ID = re.compile(r"^(?:[A-Z]{2,4})?(\d{7})$")
_NIH_CORE = re.compile(r"^\d?([A-Z]{1,2}\d{1,2}[A-Z]{2}\d{6})")
_ACK_NIH = re.compile(r"(?<![A-Za-z0-9])\d?[A-Za-z]{1,2}\s?\d{1,2}\s?-?[A-Za-z]{2}\s?-?\d{6}(?!\d)")
_ACK_NSF = re.compile(
    r"(?:NSF|National Science Foundation)[^.;\n]{0,120}?(?<!\d)(\d{7})(?!\d)", re.I
)


@dataclass(frozen=True)
class AwardId:
    """A normalized award identifier. ``family`` and ``key`` are None when unrecognized."""

    raw: str
    family: str | None
    key: str | None


@dataclass(frozen=True)
class Link:
    work_id: str
    grant_key: str
    grant_source: str
    evidence_type: str
    evidence_value: str
    confidence: str


@dataclass(frozen=True)
class ReviewCandidate:
    work_id: str
    grant_key: str
    evidence_type: str
    evidence_value: str
    reason: str


def compact_award_id(raw: str) -> str:
    """Drop spaces, hyphens, slashes and other separators; upper-case the rest."""
    text = unicodedata.normalize("NFKC", raw or "")
    return _SEPARATORS.sub("", text).upper()


def normalize_award_id(raw: str) -> AwardId:
    """Return the funder family and grant key for an award id string.

    NSF: 7 digits with an optional 2-4 letter prefix (``DMR-2128556`` -> 2128556).
    NIH: optional leading digit, activity code, institute code and 6-digit serial,
    with any suffix dropped (``1r01es036575-01a1`` -> ``R01ES036575``).
    """
    compact = compact_award_id(raw)
    nsf = _NSF_ID.match(compact)
    if nsf:
        return AwardId(raw, "nsf", nsf.group(1))
    nih = _NIH_CORE.match(compact)
    if nih:
        return AwardId(raw, "nih", nih.group(1))
    return AwardId(raw, None, None)


def build_grant_index(rows: Iterable[Mapping[str, Any]]) -> dict[tuple[str, str], list[str]]:
    """Index grant keys by ``("nsf", award_id)`` and ``("nih", appl_id)``.

    Each row needs ``grant_key``, ``source`` and ``source_award_id``. Rows are
    expected to carry the representative key after deduplication.
    """
    index: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        source = row.get("source")
        award = str(row.get("source_award_id") or "").strip()
        if not award:
            continue
        if source == "nsf_awards":
            family = "nsf"
        elif source == "nih_reporter":
            family = "nih"
        else:
            continue
        index.setdefault((family, award), set()).add(str(row["grant_key"]))
    return {key: sorted(values) for key, values in index.items()}


def _chunks(items: Sequence[str], size: int) -> list[list[str]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def load_lookup(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): [str(v) for v in vals] for k, vals in data.items()}


def _save_lookup(path: Path, mapping: Mapping[str, list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(dict(sorted(mapping.items())), indent=2, sort_keys=True)
    path.write_text(text + "\n", encoding="utf-8")


def reporter_transport(body: Mapping[str, Any], *, timeout: float = 60.0) -> tuple[int, str]:
    """POST one RePORTER search. Only ``api.reporter.nih.gov`` is contacted."""
    request = urllib.request.Request(
        REPORTER_URL,
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")


def resolve_nih_core_nums(
    core_nums: Iterable[str],
    *,
    cache_path: Path,
    transport: Callable[[Mapping[str, Any]], tuple[int, str]] = reporter_transport,
    max_requests: int = 60,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, list[str]]:
    """Map NIH core project numbers to RePORTER ``appl_id`` values.

    Results are cached in ``cache_path`` (an empty list means RePORTER returned no
    record). Numbers not resolved within ``max_requests`` are absent from the
    returned mapping. Raises ``RuntimeError`` on a non-200 response.
    """
    cache = load_lookup(cache_path)
    pending = sorted({n for n in core_nums if n not in cache})
    used = 0
    for batch in _chunks(pending, REPORTER_BATCH):
        wanted = set(batch)
        found: dict[str, list[str]] = {n: [] for n in batch}
        offset = 0
        complete = False
        while used < max_requests:
            if used:
                sleep(MIN_REQUEST_INTERVAL)
            body = {
                "criteria": {"project_nums": batch},
                "offset": offset,
                "limit": REPORTER_PAGE,
            }
            status, text = transport(body)
            used += 1
            if status != 200:
                raise RuntimeError(f"RePORTER returned HTTP {status}")
            payload = json.loads(text)
            rows = payload.get("results") or []
            for row in rows:
                raw_num = row.get("project_num") or row.get("core_project_num") or ""
                core = normalize_award_id(str(raw_num)).key
                appl = row.get("appl_id")
                if core in wanted and appl is not None:
                    found[core].append(str(appl))
            offset += len(rows)
            total = int((payload.get("meta") or {}).get("total") or 0)
            if not rows or offset >= total:
                complete = True
                break
        if not complete:
            # Budget exhausted: leave this batch and the rest unresolved.
            break
        for core in batch:
            cache[core] = sorted(set(found[core]))
        _save_lookup(cache_path, cache)
    return {n: cache[n] for n in core_nums if n in cache}


def _keys_for(
    family: str,
    key: str,
    index: Mapping[tuple[str, str], list[str]],
    lookup: Mapping[str, list[str]],
) -> list[str]:
    if family == "nsf":
        return list(index.get(("nsf", key), []))
    appl_ids = lookup.get(key, [])
    return sorted({g for a in appl_ids for g in index.get(("nih", a), [])})


def match_openalex_awards(
    work_id: str,
    awards: Sequence[Mapping[str, Any]],
    index: Mapping[tuple[str, str], list[str]],
    lookup: Mapping[str, list[str]],
    grant_source: Mapping[str, str],
) -> tuple[list[Link], list[ReviewCandidate]]:
    links: list[Link] = []
    review: list[ReviewCandidate] = []
    for award in awards:
        raw = str(award.get("funder_award_id") or "").strip()
        aid = normalize_award_id(raw)
        if aid.family is None or aid.key is None:
            continue
        keys = _keys_for(aid.family, aid.key, index, lookup)
        if not keys:
            continue
        funder_name = str(award.get("funder_display_name") or "")
        funder_id = str(award.get("funder_id") or "")
        if aid.family == "nsf":
            plausible = funder_id in NSF_FUNDER_IDS or bool(NSF_FUNDER_NAME_RE.search(funder_name))
        else:
            plausible = bool(NIH_FUNDER_NAME_RE.search(funder_name))
        for key in keys:
            if plausible:
                links.append(
                    Link(
                        work_id,
                        key,
                        grant_source.get(key, ""),
                        "openalex-award",
                        raw,
                        "high",
                    )
                )
            else:
                review.append(
                    ReviewCandidate(
                        work_id,
                        key,
                        "openalex-award",
                        raw,
                        f"{aid.family} award id under funder {funder_name or funder_id!r}",
                    )
                )
    return links, review


def _ack_candidates(text: str) -> list[tuple[str, str, str]]:
    """Return ``(family, key, raw)`` candidates from acknowledgement text."""
    out: list[tuple[str, str, str]] = []
    for match in _ACK_NIH.finditer(text):
        aid = normalize_award_id(match.group(0))
        if aid.family == "nih" and aid.key:
            out.append(("nih", aid.key, match.group(0).strip()))
    for match in _ACK_NSF.finditer(text):
        out.append(("nsf", match.group(1), match.group(1)))
    return out


def match_acknowledgements(
    work_id: str,
    texts: Sequence[str],
    index: Mapping[tuple[str, str], list[str]],
    lookup: Mapping[str, list[str]],
    grant_source: Mapping[str, str],
) -> list[Link]:
    links: dict[str, Link] = {}
    for text in texts:
        for family, key, raw in _ack_candidates(text):
            for grant_key in _keys_for(family, key, index, lookup):
                links.setdefault(
                    grant_key,
                    Link(
                        work_id,
                        grant_key,
                        grant_source.get(grant_key, ""),
                        "acknowledgement-match",
                        raw,
                        "high",
                    ),
                )
    return list(links.values())


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).casefold()


def match_fixed_strings(
    work_id: str,
    texts: Sequence[str],
    phrase: str | None,
    target_keys: Sequence[str],
    grant_source: Mapping[str, str],
) -> list[Link]:
    if not phrase or not target_keys:
        return []
    needle = _squash(phrase)
    if not any(needle in _squash(t) for t in texts):
        return []
    return [
        Link(work_id, key, grant_source.get(key, ""), "fixed-string", phrase, "high")
        for key in sorted(target_keys)
    ]


def combine_links(links: Iterable[Link]) -> list[Link]:
    """Keep one link per (work, grant), using the strongest evidence type."""
    best: dict[tuple[str, str], Link] = {}
    for link in links:
        key = (link.work_id, link.grant_key)
        current = best.get(key)
        if current is None or (
            EVIDENCE_PRECEDENCE[link.evidence_type] < EVIDENCE_PRECEDENCE[current.evidence_type]
        ):
            best[key] = link
    return sorted(best.values(), key=lambda link: (link.work_id, link.grant_key))


def sample_links(links: Sequence[Link], n: int, seed: int) -> list[Link]:
    """Deterministic sample of up to ``n`` links, independent of input order."""
    ordered = sorted(links, key=lambda link: (link.work_id, link.grant_key))
    if len(ordered) <= n:
        return ordered
    return sorted(
        random.Random(seed).sample(ordered, n), key=lambda link: (link.work_id, link.grant_key)
    )


def work_awards(raw_json: str) -> list[dict[str, Any]]:
    data = json.loads(raw_json)
    return [a for a in (data.get("awards") or []) if isinstance(a, dict)]


def load_cached_ack_texts(cache_dir: Path) -> dict[str, list[str]]:
    """Collect acknowledgement and funding text from cached full-text results.

    The cached parser output currently stores only methods, study-area, sampling
    and data-availability sections, so this returns an empty mapping today.
    """
    texts: dict[str, list[str]] = {}
    if not cache_dir.is_dir():
        return texts
    for path in sorted(cache_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        work_id = str(data.get("work_id") or "")
        sections = (data.get("result") or {}).get("sections") or {}
        for name in ACK_SECTIONS:
            for entry in sections.get(name) or []:
                text = entry.get("text", "") if isinstance(entry, dict) else str(entry)
                if work_id and text:
                    texts.setdefault(work_id, []).append(text)
    return texts
