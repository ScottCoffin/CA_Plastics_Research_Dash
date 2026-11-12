"""Expert contact discovery for owner-sent outreach (S9.6a).

Pure functions: no network, and the only file this module writes is a CSV inside
``<repo>/data/private/`` (gitignored). Emails are personal data. Callers must never
print or log them; the build script prints counts only.
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTACT_FIELDS = ["author_id", "name", "email", "source", "first_seen_utc"]
OPENALEX_PREFIXES = ("https://openalex.org/", "http://openalex.org/")

# Same shape as the redaction regex in atlas.ingest.normalize.
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
PLACEHOLDER_DOMAINS = ("example.com", "example.org", "example.net", "localhost")
PLACEHOLDER_SUFFIXES = (".example", ".invalid", ".localhost", ".test")
NOREPLY_LOCALS = frozenset({"noreply", "no-reply", "donotreply", "do-not-reply"})
IMAGE_EXTENSIONS = frozenset({"png", "jpg", "jpeg", "gif", "svg", "webp", "bmp", "tif", "tiff"})


def short_openalex_id(value: object) -> str | None:
    """Return the short OpenAlex id (``A123...``) from a short or URL form, else None."""

    if not isinstance(value, str):
        return None
    short = value.strip()
    for prefix in OPENALEX_PREFIXES:
        if short.startswith(prefix):
            short = short[len(prefix) :]
            break
    return short or None


def _is_placeholder(email: str) -> bool:
    local, _, domain = email.partition("@")
    if local in NOREPLY_LOCALS:
        return True
    if any(domain == d or domain.endswith("." + d) for d in PLACEHOLDER_DOMAINS):
        return True
    if domain.endswith(PLACEHOLDER_SUFFIXES):
        return True
    # Catches image references such as "logo@2x.png".
    return domain.rsplit(".", 1)[-1] in IMAGE_EXTENSIONS


def extract_emails(text: str) -> list[str]:
    """Return lowercased, deduplicated, non-placeholder emails in order of appearance."""

    if not text:
        return []
    found: dict[str, None] = {}
    for match in EMAIL_RE.finditer(text):
        email = match.group(0).lower().lstrip(".")
        if not _is_placeholder(email):
            found[email] = None
    return list(found)


def contacts_from_openalex_works(
    works: Iterable[dict], expert_ids: set[str]
) -> dict[str, set[str]]:
    """Map expert author id to emails found on that author's own authorship.

    Emails are read only from an authorship's ``raw_affiliation_strings``, so an
    address is never assigned to a co-author. Experts with no email are omitted.
    """

    wanted = {short for short in (short_openalex_id(i) for i in expert_ids) if short}
    found: dict[str, set[str]] = defaultdict(set)
    for work in works:
        if not isinstance(work, dict):
            continue
        authorships = work.get("authorships")
        if not isinstance(authorships, list):
            continue
        for authorship in authorships:
            if not isinstance(authorship, dict):
                continue
            author = authorship.get("author")
            author_id = short_openalex_id(author.get("id")) if isinstance(author, dict) else None
            if author_id is None or author_id not in wanted:
                continue
            affiliations = authorship.get("raw_affiliation_strings")
            if not isinstance(affiliations, list):
                continue
            for text in affiliations:
                if isinstance(text, str):
                    found[author_id].update(extract_emails(text))
    return {author_id: emails for author_id, emails in found.items() if emails}


def private_dir(root: Path = REPO_ROOT) -> Path:
    """Return the resolved ``<root>/data/private`` directory."""

    return (Path(root) / "data" / "private").resolve()


def write_contacts(path: str | Path, rows: Iterable[dict], root: Path = REPO_ROOT) -> int:
    """Write contact rows to ``path``, which must lie strictly inside ``data/private/``.

    Returns the number of rows written. Raises ValueError before creating anything
    when the resolved path is outside that directory.
    """

    private = private_dir(root)
    target = Path(path).resolve()
    if target == private or not target.is_relative_to(private):
        raise ValueError("contact lists may only be written inside data/private/")
    materialised = list(rows)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=CONTACT_FIELDS, lineterminator="\n", extrasaction="ignore"
        )
        writer.writeheader()
        for row in materialised:
            writer.writerow(row)
    return len(materialised)


def load_opt_outs(opt_out_path: str | Path) -> tuple[set[str], set[str]]:
    """Return (opted-out emails, opted-out short author ids). A missing file means none."""

    path = Path(opt_out_path)
    emails: set[str] = set()
    author_ids: set[str] = set()
    if not path.exists():
        return emails, author_ids
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            email = (row.get("email") or "").strip().lower()
            if email:
                emails.add(email)
            author_id = short_openalex_id(row.get("author_id"))
            if author_id:
                author_ids.add(author_id)
    return emails, author_ids


def merge_opt_outs(rows: Iterable[dict], opt_out_path: str | Path) -> tuple[list[dict], int]:
    """Drop rows whose email or author is opted out. Returns (kept rows, rows removed)."""

    emails, author_ids = load_opt_outs(opt_out_path)
    kept: list[dict] = []
    removed = 0
    for row in rows:
        email = str(row.get("email") or "").lower()
        author_id = short_openalex_id(row.get("author_id"))
        if email in emails or (author_id is not None and author_id in author_ids):
            removed += 1
            continue
        kept.append(row)
    return kept, removed


def _fold(text: str) -> str:
    import unicodedata

    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "".join(ch for ch in plain.lower() if ch.isalpha() or ch.isspace())


def email_matches_name(email: str, name: str) -> bool:
    """True when the email's local part contains the surname or first name (>= 3 letters).

    OpenAlex often copies the corresponding author's address into every co-author's
    raw affiliation string, so an address is kept only when it plausibly belongs to
    this expert (no guessed addresses; docs/OUTREACH.md guardrails).
    """
    local = "".join(ch for ch in email.split("@", 1)[0].lower() if ch.isalpha())
    tokens = [t for t in _fold(name).split() if len(t) >= 3]
    if not local or not tokens:
        return False
    return any(t in local for t in (tokens[0], tokens[-1]))
