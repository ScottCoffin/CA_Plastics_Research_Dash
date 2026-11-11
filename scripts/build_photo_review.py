"""Write the owner review sheet for licensed Wikidata expert photos (S9.5).

Reads ``data/processed/expert_photos.parquet`` (``fetch_wikidata_photos.py``) and
writes ``curation/expert_photo_review.csv`` with one row per usable photo and blank
``owner_decision`` / ``owner_notes`` columns. Existing decisions are kept when the
sheet is regenerated. The owner opens each Commons link, checks the person, and
types ``approve`` or ``reject``. No image is downloaded.

    py -3.14 scripts/build_photo_review.py
"""

from __future__ import annotations

import csv
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "data" / "processed" / "expert_photos.parquet"
OUT = ROOT / "curation" / "expert_photo_review.csv"
FIELDS = [
    "author_id",
    "wikidata_label",
    "atlas_profile_url",
    "wikidata_url",
    "commons_page_url",
    "license_short",
    "credit",
    "owner_decision",
    "owner_notes",
]


def main() -> None:
    rows = [r for r in pq.read_table(PHOTOS).to_pylist() if r.get("usable")]
    previous: dict[str, dict[str, str]] = {}
    if OUT.exists():
        with OUT.open(encoding="utf-8", newline="") as handle:
            previous = {r["author_id"]: r for r in csv.DictReader(handle)}
    rows.sort(key=lambda r: str(r.get("wikidata_label") or ""))
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            author_id = str(row["author_id"])
            old = previous.get(author_id, {})
            writer.writerow(
                {
                    "author_id": author_id,
                    "wikidata_label": row.get("wikidata_label") or "",
                    "atlas_profile_url": f"https://plastiverse.live/#experts?author={author_id}",
                    "wikidata_url": f"https://www.wikidata.org/wiki/{row.get('wikidata_qid')}",
                    "commons_page_url": row.get("description_url") or "",
                    "license_short": row.get("license_short") or "",
                    "credit": " ".join(str(row.get("credit") or row.get("artist") or "").split()),
                    "owner_decision": old.get("owner_decision", ""),
                    "owner_notes": old.get("owner_notes", ""),
                }
            )
    print(f"wrote {OUT.relative_to(ROOT)} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
