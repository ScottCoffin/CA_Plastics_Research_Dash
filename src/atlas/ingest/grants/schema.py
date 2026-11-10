"""Grant table schema (S8.1, spec C3) and the stable grant key.

The column order below is the C3 field order and must not change without an
ADR, because downstream exports and tests depend on it.

``grant_key`` is part of the public contract: it is derived from the source
name and the source's own award identifier, and the algorithm must never
change once any table has been written.  Changing it would orphan every
previously exported grant row.
"""

from __future__ import annotations

import hashlib

import pyarrow as pa

GRANT_COLUMNS: tuple[str, ...] = (
    "grant_key",
    "source",
    "source_award_id",
    "title",
    "abstract",
    "pi_names",
    "org",
    "org_ror",
    "org_state",
    "start",
    "end",
    "amount",
    "currency",
    "funder",
    "program",
    "funder_chain",
    "url",
    "plastic_related",
    "domain_tags",
    "ca_led",
    "ca_sampling_flag",
)

REQUIRED_COLUMNS: tuple[str, ...] = ("grant_key", "source", "source_award_id", "title")
LIST_COLUMNS: tuple[str, ...] = ("pi_names", "funder_chain", "domain_tags")
DATE_COLUMNS: tuple[str, ...] = ("start", "end")
BOOL_COLUMNS: tuple[str, ...] = ("plastic_related", "ca_led", "ca_sampling_flag")
FLOAT_COLUMNS: tuple[str, ...] = ("amount",)
STRING_COLUMNS: tuple[str, ...] = tuple(
    column
    for column in GRANT_COLUMNS
    if column not in {*LIST_COLUMNS, *DATE_COLUMNS, *BOOL_COLUMNS, *FLOAT_COLUMNS}
)

GRANT_SCHEMA = pa.schema(
    [
        pa.field("grant_key", pa.string(), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("source_award_id", pa.string(), nullable=False),
        pa.field("title", pa.string(), nullable=False),
        pa.field("abstract", pa.string()),
        pa.field("pi_names", pa.list_(pa.string())),
        pa.field("org", pa.string()),
        pa.field("org_ror", pa.string()),
        pa.field("org_state", pa.string()),
        pa.field("start", pa.date32()),
        pa.field("end", pa.date32()),
        pa.field("amount", pa.float64()),
        pa.field("currency", pa.string()),
        pa.field("funder", pa.string()),
        pa.field("program", pa.string()),
        pa.field("funder_chain", pa.list_(pa.string())),
        pa.field("url", pa.string()),
        # Nullable booleans: null means unknown.  Never coerce unknown to False.
        pa.field("plastic_related", pa.bool_()),
        pa.field("domain_tags", pa.list_(pa.string())),
        pa.field("ca_led", pa.bool_()),
        pa.field("ca_sampling_flag", pa.bool_()),
    ]
)


def require_text(value: object, field: str) -> str:
    """Return a stripped non-empty string or raise ``ValueError``."""

    text = value.strip() if isinstance(value, str) else ""
    if not text:
        raise ValueError(f"{field} is required and must be a non-blank string")
    return text


def grant_key(source: str, source_award_id: str) -> str:
    """Return the stable 16-hex-character key for one source award.

    The key is the first 16 hex characters of the SHA-256 digest of
    ``f"{source}\\x1f{source_award_id}"`` after stripping both parts.  The unit
    separator (U+001F) keeps the two parts from colliding.  Matching is
    case-sensitive: award identifiers are not casefolded.

    This algorithm is frozen.  Do not change the separator, the hash, the
    truncation, or the stripping without a new key version.
    """

    source_text = require_text(source, "source")
    award_text = require_text(source_award_id, "source_award_id")
    digest = hashlib.sha256(f"{source_text}\x1f{award_text}".encode()).hexdigest()
    return digest[:16]
