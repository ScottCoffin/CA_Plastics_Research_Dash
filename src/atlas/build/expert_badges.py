"""Expert profile badges (S9.3): funding and data stewardship evidence per expert.

Writes ``site/data/expert_badges.json``, read lazily by the full expert profile page.

* Funding: plastic-related grants in ``site/data/grants.json`` either linked to one of the
  expert's works (``data/processed/work_grant_links.parquet``, OpenAlex award IDs) or whose
  principal-investigator name matches the expert's name at a California organisation. Name
  keys are (first given name, family name) after folding accents; a key shared by two experts
  is never used. Whether a grant is active is decided by the page from its end date.
* Data stewardship: datasets the expert authored in DataCite (via ORCID,
  ``data/processed/expert_datacite_outputs.parquet``) that are plastic-related, one per
  dataset family (versions collapsed).

No free text is generated: badges only restate public records.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "s9.3-v1"
DATASET_ITEMS = 5
GRANT_FIELDS = ("grant_key", "title", "funder", "org", "start", "end", "url", "amount")


def name_key(name: str | None) -> tuple[str, str] | None:
    """(first given name, family name), lower-case, accents folded; None when too short."""
    text = unicodedata.normalize("NFKD", str(name or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    text = re.sub(r"[^a-z ,'-]", " ", text)
    if "," in text:
        family, given = (part.strip() for part in text.split(",", 1))
        text = f"{given} {family}"
    tokens = [t.strip("'-") for t in re.split(r"[\s-]+", text) if t.strip("'-")]
    long_tokens = [t for t in tokens if len(t) > 1]
    if len(long_tokens) < 2:
        return None
    return long_tokens[0], long_tokens[-1]


def _grant_summary(row: Mapping[str, Any], match: str) -> dict[str, Any]:
    summary = {field: row.get(field) for field in GRANT_FIELDS}
    summary["match"] = match
    return summary


def build_badges(
    authors: Sequence[Mapping[str, Any]],
    grants: Sequence[Mapping[str, Any]],
    work_grant_links: Iterable[Mapping[str, Any]] = (),
    datacite_outputs: Iterable[Mapping[str, Any]] = (),
) -> dict[str, dict[str, Any]]:
    """Return ``{author_id: {"grants": [...], "datasets": {...}}}`` for experts with any badge."""
    author_ids = {str(a.get("author_id")) for a in authors if a.get("author_id")}
    plastic_grants = {
        str(g["grant_key"]): g for g in grants if g.get("grant_key") and g.get("plastic_related")
    }

    keyed: dict[tuple[str, str], set[str]] = defaultdict(set)
    for author in authors:
        key = name_key(author.get("name"))
        if key and author.get("author_id"):
            keyed[key].add(str(author["author_id"]))

    found: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    works_to_authors: dict[str, set[str]] = defaultdict(set)
    for author in authors:
        for work_id in author.get("work_ids") or []:
            works_to_authors[str(work_id)].add(str(author.get("author_id")))
    for link in work_grant_links:
        grant = plastic_grants.get(str(link.get("grant_key")))
        if not grant:
            continue
        for author_id in works_to_authors.get(str(link.get("work_id")), ()):
            found[author_id][grant["grant_key"]] = _grant_summary(grant, "linked_work")
    for grant in plastic_grants.values():
        if grant.get("org_state") != "CA":
            continue
        for pi in grant.get("pi_names") or []:
            matches = keyed.get(name_key(pi) or ("", ""), set())
            if len(matches) != 1:
                continue
            (author_id,) = matches
            found[author_id].setdefault(grant["grant_key"], _grant_summary(grant, "pi_name"))

    datasets: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in datacite_outputs:
        author_id = str(row.get("author_id") or "")
        if author_id not in author_ids or row.get("plastic_related") is not True:
            continue
        if str(row.get("resource_type_general") or "").lower() != "dataset":
            continue
        family = str(row.get("family_doi") or row.get("doi") or "").lower()
        if not family:
            continue
        item = {
            "doi": row.get("doi"),
            "title": row.get("title"),
            "publisher": row.get("publisher"),
            "year": row.get("year"),
        }
        current = datasets[author_id].get(family)
        if current is None or (item["year"] or 0) > (current["year"] or 0):
            datasets[author_id][family] = item

    badges: dict[str, dict[str, Any]] = {}
    for author_id in sorted(set(found) | set(datasets)):
        entry: dict[str, Any] = {}
        if found.get(author_id):
            entry["grants"] = sorted(
                found[author_id].values(),
                key=lambda g: (str(g.get("end") or ""), str(g.get("grant_key"))),
                reverse=True,
            )
        if datasets.get(author_id):
            items = sorted(
                datasets[author_id].values(),
                key=lambda d: (-(d["year"] or 0), str(d.get("title") or "")),
            )
            entry["datasets"] = {"count": len(items), "items": items[:DATASET_ITEMS]}
        badges[author_id] = entry
    return badges


def write_badges(
    *,
    index_path: Path,
    grants_path: Path,
    out_path: Path,
    work_grant_links_path: Path | None = None,
    datacite_path: Path | None = None,
) -> dict[str, int]:
    import pyarrow.parquet as pq

    index = json.loads(index_path.read_text(encoding="utf-8"))
    grants_payload = json.loads(grants_path.read_text(encoding="utf-8"))
    grants = grants_payload.get("rows") or []
    links = (
        pq.read_table(work_grant_links_path).to_pylist()
        if work_grant_links_path and work_grant_links_path.exists()
        else []
    )
    outputs = (
        pq.read_table(
            datacite_path,
            columns=[
                "author_id",
                "doi",
                "title",
                "publisher",
                "year",
                "resource_type_general",
                "plastic_related",
                "family_doi",
            ],
        ).to_pylist()
        if datacite_path and datacite_path.exists()
        else []
    )
    badges = build_badges(index.get("authors") or [], grants, links, outputs)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": index.get("generated_at"),
        "method": {
            "funding": "plastic-related grants linked to the expert's works, or whose "
            "principal investigator's name matches the expert at a California organisation",
            "datasets": "plastic-related DataCite datasets the expert authored (ORCID), "
            "versions collapsed",
        },
        "experts": badges,
    }
    text = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(text.encode("utf-8"))
    return {
        "experts": len(badges),
        "with_grants": sum(1 for b in badges.values() if "grants" in b),
        "with_datasets": sum(1 for b in badges.values() if "datasets" in b),
    }
