"""Public roster QC candidates for the ambassador tagging form (AMB-ROSTER-QC).

Pure functions. ``build_roster_qc`` returns the cg-roster-qc-v1 document from the roster
records and the reviewed curation rows. The document carries group ids and reason codes only:
never a name or a URL, because the form looks the names up in roster.json.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from atlas.groups import admission

SCHEMA = "cg-roster-qc-v1"
URL_START_RE = re.compile(r"^(?:https?://|www\.)", re.IGNORECASE)
DOMAIN_RE = re.compile(r"(?:[a-z0-9-]+\.)+[a-z]{2,}", re.IGNORECASE)
SUSPECT_CODES = (
    "double_question_mark",
    "broken_character",
    "backtick",
    "web_address",
    "domain_only",
    "short_one_case",
)
PAIR_REASON_CODES = {"same registrable domain": "same_domain", "similar name": "similar_name"}


def suspect_codes(name: str) -> list[str]:
    """Reason codes (from SUSPECT_CODES, in that order) for a name that looks wrong."""
    text = name.strip()
    codes: list[str] = []
    if "??" in text:
        codes.append("double_question_mark")
    if "�" in text:
        codes.append("broken_character")
    if "`" in text:
        codes.append("backtick")
    if "://" in text or URL_START_RE.match(text):
        codes.append("web_address")
    elif DOMAIN_RE.fullmatch(text):
        codes.append("domain_only")
    short = len(text) <= 3 and any(ch.isalpha() for ch in text)
    if short and (text == text.lower() or text == text.upper()):
        codes.append("short_one_case")
    return codes


def candidate_pairs(
    records: Iterable[Mapping[str, Any]], merges: Iterable[Mapping[str, str]]
) -> list[dict[str, str]]:
    """Same-domain and similar-name pairs, a < b by group id, minus every decided pair."""
    copies = [
        {**record, "_domain": admission.registrable_domain(record.get("url"))} for record in records
    ]
    suppressed = admission.decided_pairs(merges)
    pairs = []
    for pair in admission._near_duplicates(copies, suppressed):
        first, second = sorted((pair["group_id_a"], pair["group_id_b"]))
        pairs.append({"a": first, "b": second, "reason": PAIR_REASON_CODES[pair["reason"]]})
    return sorted(pairs, key=lambda p: (p["a"], p["b"]))


def suspect_entries(
    records: Iterable[Mapping[str, Any]], corrected: Iterable[str]
) -> list[dict[str, Any]]:
    """Group ids with suspect-name reason codes, sorted by id; corrected ids are skipped."""
    skip = set(corrected)
    entries = []
    for record in sorted(records, key=lambda r: r["group_id"]):
        if record["group_id"] in skip:
            continue
        codes = suspect_codes(record["name"])
        if codes:
            entries.append({"group_id": record["group_id"], "reasons": codes})
    return entries


def build_roster_qc(
    roster: Mapping[str, Any],
    merges: Iterable[Mapping[str, str]],
    corrections: Mapping[str, str],
) -> dict[str, Any]:
    """The cg-roster-qc-v1 document. ``corrections`` maps group id to an approved name."""
    records = list(roster["records"])
    return {
        "schema": SCHEMA,
        "generated_from": roster.get("generated_at") or roster["retrieved_at"],
        "pairs": candidate_pairs(records, list(merges)),
        "suspect_names": suspect_entries(records, corrections.keys()),
    }
