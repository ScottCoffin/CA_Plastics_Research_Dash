"""Normalize source-agnostic grant records into the S8.1 grant schema.

Plastic relevance and domain tags are PROVISIONAL.  They reuse the S2.3 rule
labels (``classify_plastic_text`` and ``_taxonomy_tags``) until the shared
S5.1 classifier exists.  The candidate query in ``config/queries.yml`` is not
promoted by this module.

Plastic relevance for a grant is decided by ``grant_plastic_decision``.  A core
term in the title makes a grant plastic-related.  A core term that appears only
in the abstract does not: such a grant is recorded as not plastic-related
(basis ``abstract_mention_only``) unless a reviewed decision in
``curation/grant_relevance.csv`` says otherwise.  Reviewed decisions are applied
at export time (``atlas.build.grants_export``), not during ingest.
"""

from __future__ import annotations

import math
import re
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from atlas.ingest.grants.schema import (
    BOOL_COLUMNS,
    DATE_COLUMNS,
    FLOAT_COLUMNS,
    GRANT_COLUMNS,
    GRANT_SCHEMA,
    LIST_COLUMNS,
    REQUIRED_COLUMNS,
    STRING_COLUMNS,
    grant_key,
    require_text,
)
from atlas.ingest.normalize import compact_id
from atlas.nlp.labels import _taxonomy_tags, classify_plastic_text

_DATE_PATTERN = re.compile(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?")
_STATE_PATTERN = re.compile(r"[A-Za-z]{2}")
_CURRENCY_PATTERN = re.compile(r"[A-Za-z]{3}")
TITLE_RULE_MAX_CHARS = 250


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _names(value: object, field: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field} must be a list of strings")
    return [text for text in (_optional_text(item) for item in value) if text is not None]


def _parse_date(value: object, field: str) -> date | None:
    """Parse yyyy-mm-dd, yyyy-mm (first day), or yyyy (January 1)."""

    if isinstance(value, datetime):
        raise ValueError(f"{field} must be a date, not a datetime")
    if isinstance(value, date):
        return value
    text = _optional_text(value)
    if text is None:
        return None
    match = _DATE_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError(f"{field} must be yyyy, yyyy-mm, or yyyy-mm-dd: {text!r}")
    year, month, day = int(match[1]), int(match[2] or 1), int(match[3] or 1)
    try:
        return date(year, month, day)
    except ValueError as error:
        raise ValueError(f"{field} is not a valid calendar date: {text!r}") from error


def _amount(value: object) -> float | None:
    if isinstance(value, bool):
        raise ValueError("amount must be a number, not a boolean")
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).strip().replace("$", "").replace(",", "").strip()
        if not text:
            return None
        try:
            number = float(text)
        except ValueError as error:
            raise ValueError(f"amount is not a number: {value!r}") from error
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"amount must be finite and non-negative: {value!r}")
    return number


def _state(value: object) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    if _STATE_PATTERN.fullmatch(text) is None:
        raise ValueError(f"org_state must be a two-letter code: {text!r}")
    return text.upper()


def _currency(value: object) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    if _CURRENCY_PATTERN.fullmatch(text) is None:
        raise ValueError(f"currency must be an ISO-4217 code: {text!r}")
    return text.upper()


def grant_plastic_decision(
    title: str | None,
    abstract: str | None,
    query_config: Mapping[str, Any],
    overrides: Mapping[str, bool] | None = None,
    grant_key: str | None = None,
) -> tuple[bool, str]:
    """Return ``(plastic_related, basis)`` for one grant.

    ``basis`` is one of:

    * ``reviewed``: ``grant_key`` is in ``overrides``; the reviewed value wins.
    * ``title``: the title (at most ``TITLE_RULE_MAX_CHARS`` characters) matches
      a core rule.
    * ``abstract_mention_only``: only the title plus abstract matches. Unreviewed
      abstract-only mentions are not plastic-related.
    * ``none``: no match.
    """

    if overrides is not None and grant_key is not None and grant_key in overrides:
        return bool(overrides[grant_key]), "reviewed"
    title_text = _optional_text(title) or ""
    abstract_text = _optional_text(abstract) or ""
    if (
        len(title_text) <= TITLE_RULE_MAX_CHARS
        and classify_plastic_text(title_text, query_config).related
    ):
        return True, "title"
    full_text = " ".join(part for part in (title_text, abstract_text) if part)
    if classify_plastic_text(full_text, query_config).related:
        return False, "abstract_mention_only"
    return False, "none"


def normalize_grant(
    raw: Mapping[str, Any],
    *,
    source: str,
    query_config: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
) -> dict[str, Any]:
    """Map one source-agnostic raw grant record onto the S8.1 schema.

    ``raw`` uses the C3 field names (except ``grant_key``, which is derived)
    and may include an optional ``abstract``.  Unknown or blank optional fields
    become ``None`` (or ``[]`` for lists).  Raises ``ValueError`` for missing
    required fields and for malformed dates, amounts, states, or currencies.
    """

    source_text = require_text(source, "source")
    award_id = require_text(raw.get("source_award_id"), "source_award_id")
    title = require_text(raw.get("title"), "title")
    abstract = _optional_text(raw.get("abstract"))
    org_state = _state(raw.get("org_state"))
    start = _parse_date(raw.get("start"), "start")
    end = _parse_date(raw.get("end"), "end")
    text = " ".join(part for part in (title, abstract) if part is not None)
    plastic_related, _basis = grant_plastic_decision(title, abstract, query_config)
    domain_tags, _facets = _taxonomy_tags(text, [], taxonomy)
    return {
        "grant_key": grant_key(source_text, award_id),
        "source": source_text,
        "source_award_id": award_id,
        "title": title,
        "abstract": abstract,
        "pi_names": _names(raw.get("pi_names"), "pi_names"),
        "org": _optional_text(raw.get("org")),
        "org_ror": compact_id(_optional_text(raw.get("org_ror")) or "") or None,
        "org_state": org_state,
        "start": start,
        "end": end,
        "amount": _amount(raw.get("amount")),
        "currency": _currency(raw.get("currency")),
        "funder": _optional_text(raw.get("funder")),
        "program": _optional_text(raw.get("program")),
        "funder_chain": _names(raw.get("funder_chain"), "funder_chain"),
        "url": _optional_text(raw.get("url")),
        "plastic_related": plastic_related,
        "domain_tags": list(domain_tags),
        "ca_led": None if org_state is None else org_state == "CA",
        "ca_sampling_flag": None,
    }


def _is_text(value: object) -> bool:
    return isinstance(value, str)


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(_is_text(item) for item in value)


def _row_problems(row: Mapping[str, Any], label: str) -> list[str]:
    problems: list[str] = []
    missing = [column for column in GRANT_COLUMNS if column not in row]
    extra = sorted(set(row) - set(GRANT_COLUMNS))
    if missing:
        problems.append(f"{label}: missing columns {missing}")
    if extra:
        problems.append(f"{label}: unexpected columns {extra}")

    for column in REQUIRED_COLUMNS:
        value = row.get(column)
        if not _is_text(value) or not value.strip():
            problems.append(f"{label}: {column} is required")
    for column in STRING_COLUMNS:
        value = row.get(column)
        if value is not None and not _is_text(value):
            problems.append(f"{label}: {column} must be a string or null")
    for column in LIST_COLUMNS:
        value = row.get(column)
        if value is not None and not _is_string_list(value):
            problems.append(f"{label}: {column} must be a list of strings")
    for column in DATE_COLUMNS:
        value = row.get(column)
        if value is not None and not (isinstance(value, date) and not isinstance(value, datetime)):
            problems.append(f"{label}: {column} must be a date or null")
    for column in BOOL_COLUMNS:
        value = row.get(column)
        if value is not None and not isinstance(value, bool):
            problems.append(f"{label}: {column} must be a boolean or null")
    for column in FLOAT_COLUMNS:
        value = row.get(column)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            problems.append(f"{label}: {column} must be a number or null")
        elif not math.isfinite(value) or value < 0:
            problems.append(f"{label}: {column} must be finite and non-negative")
    currency = row.get("currency")
    if _is_text(currency) and _CURRENCY_PATTERN.fullmatch(currency) is None:
        problems.append(f"{label}: currency must be an ISO-4217 code")
    state = row.get("org_state")
    if _is_text(state) and _STATE_PATTERN.fullmatch(state) is None:
        problems.append(f"{label}: org_state must be a two-letter code")

    source = row.get("source")
    award_id = row.get("source_award_id")
    key = row.get("grant_key")
    if (
        _is_text(source)
        and source.strip()
        and _is_text(award_id)
        and award_id.strip()
        and _is_text(key)
        and key != grant_key(source, award_id)
    ):
        problems.append(f"{label}: grant_key does not match source and source_award_id")
    return problems


def validate_grants(rows: Iterable[Mapping[str, Any]]) -> None:
    """Raise ``ValueError`` listing every schema problem in ``rows``."""

    materialized = list(rows)
    problems: list[str] = []
    first_seen: dict[str, int] = {}
    for index, row in enumerate(materialized):
        label = f"row {index}"
        if not isinstance(row, Mapping):
            problems.append(f"{label}: must be a mapping")
            continue
        problems.extend(_row_problems(row, label))
        key = row.get("grant_key")
        if _is_text(key) and key:
            if key in first_seen:
                problems.append(
                    f"{label}: duplicate grant_key {key} (first seen at row {first_seen[key]})"
                )
            else:
                first_seen[key] = index
    if problems:
        raise ValueError("invalid grant rows:\n" + "\n".join(problems))
    try:
        pa.Table.from_pylist(materialized, schema=GRANT_SCHEMA)
    except (pa.ArrowException, TypeError, ValueError) as error:
        raise ValueError(f"grant rows do not convert to GRANT_SCHEMA: {error}") from error


def write_grants_parquet(rows: Iterable[Mapping[str, Any]], path: str | Path) -> None:
    """Validate ``rows`` and atomically write them sorted by ``grant_key``."""

    materialized = list(rows)
    validate_grants(materialized)
    ordered = sorted(materialized, key=lambda row: row["grant_key"])
    table = pa.Table.from_pylist(
        [{column: row[column] for column in GRANT_COLUMNS} for row in ordered],
        schema=GRANT_SCHEMA,
    )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".parquet", prefix=f".{target.stem}-", dir=target.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
    try:
        pq.write_table(table, temporary, compression="zstd")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
