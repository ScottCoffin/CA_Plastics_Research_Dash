"""AT-1 repeat audit: sample works that query v3 adds over v2 for owner labelling.

For each institution stratum in docs/QUERY_AUDIT_REVIEW.csv, draw a seeded random
sample of works matching ``(v3 additions) NOT (v2 terms) NOT (v3 exclusions)``,
restricted to that institution and v3's type exclusions. Writes
docs/QUERY_AUDIT_REVIEW_V3.csv with the same columns as the first audit (one row
per work). Free-plan OpenAlex calls are cost-logged; one request per stratum.
Label with the review app and its --csv option (see docs/QUERY_AUDIT.md).
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from run_at1_audit import _abstract_from_index  # noqa: E402

from atlas.ingest.openalex import (  # noqa: E402
    OPENALEX_BASE,
    _request_json,
    load_openalex_key,
)
from atlas.query import load_query_config, render_query, type_filters  # noqa: E402
from atlas.query_audit_review import REVIEW_CSV, load_review  # noqa: E402
from atlas.util.cost import ApiCostLogger  # noqa: E402

OUT_CSV = Path("docs/QUERY_AUDIT_REVIEW_V3.csv")


def added_only_filter(v2: dict, v3: dict) -> str:
    """Search filter for works v3 matches and v2 does not (before type filters)."""
    added = {
        "core_terms": [t for t in v3["core_terms"] if t not in v2["core_terms"]],
        "qualified_terms": [q for q in v3["qualified_terms"] if q not in v2["qualified_terms"]],
        "exclusions": [],
    }
    v2_positive = render_query(v2, include_exclusions=False)
    v3_excluded = render_query({**added, "exclusions": v3["exclusions"]}).split(" NOT ", 1)[1]
    expression = (
        f"{render_query(added, include_exclusions=False)} NOT {v2_positive} NOT {v3_excluded}"
    )
    field = v3.get("openalex", {}).get("field", "title_and_abstract.search")
    return f"{field}:{expression}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-stratum", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20261110)
    parser.add_argument("--output", type=Path, default=OUT_CSV)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise SystemExit(f"{args.output} exists; it may hold labels. Remove it deliberately first.")
    v2 = load_query_config()
    v3 = load_query_config("config/queries_v3.yml")
    search = added_only_filter(v2, v3)
    first = load_review(REVIEW_CSV)
    strata: dict[str, str] = {}
    for row in first.rows:
        strata.setdefault(row["institution_id"], row["institution_name"])
    load_openalex_key()
    logger = ApiCostLogger("at1-repeat-sample")
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for institution_id, name in strata.items():
        filters = [search, f"institutions.id:{institution_id}", *type_filters(v3)]
        params = {
            "filter": ",".join(filters),
            "sample": args.per_stratum,
            "seed": args.seed,
            "per-page": args.per_stratum,
            "select": "id,title,doi,publication_date,abstract_inverted_index",
        }
        body = _request_json(
            f"{OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}", logger=logger
        )
        for work in body.get("results", []):
            work_url = str(work.get("id") or "")
            work_id = work_url.rsplit("/", 1)[-1]
            if not work_id or work_id in seen:
                continue
            seen.add(work_id)
            doi = str(work.get("doi") or "")
            rows.append(
                {
                    "institution_id": institution_id,
                    "institution_name": name,
                    "work_id": work_id,
                    "work_url": work_url,
                    "title": str(work.get("title") or ""),
                    "publication_date": str(work.get("publication_date") or ""),
                    "doi_url": doi if doi.startswith("https://doi.org/") else "",
                    "query_version": v3["version"] + " (added over v2)",
                    "source_query": search,
                    "abstract_excerpt": _abstract_from_index(work.get("abstract_inverted_index")),
                    "duplicate_across_strata": "",
                    "review_label": "",
                    "reviewer": "",
                    "noise_terms": "",
                }
            )
        print(f"{name}: {len(body.get('results', []))} sampled")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=first.header, lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    args.output.write_bytes(buffer.getvalue().encode("utf-8"))
    print(f"wrote {args.output}: {len(rows)} works; requests {logger.request_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
