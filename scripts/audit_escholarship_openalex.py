"""S2.5: measure eScholarship coverage through OpenAlex (no eScholarship requests).

eScholarship's GraphQL read API has no keyword search, and its web portal is behind a
bot screen. OpenAlex indexes eScholarship as a repository source (S4306400115), so one
budget-guarded query (eScholarship location AND the active plastics query AND the type
exclusions) lists the UC deposits our query would admit. The script compares them with
the raw corpus and the California gate and writes counts only. Nothing is merged.

    PYTHONPATH=src py -3.14 scripts/audit_escholarship_openalex.py --max-credits 1500
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import urllib.parse
from pathlib import Path

import pyarrow.parquet as pq

from atlas.ingest import europepmc_audit as audit
from atlas.ingest import openalex as oa
from atlas.query import load_query_config, openalex_filter, type_filters

ESCHOLARSHIP_SOURCE = "S4306400115"
RAW = Path("data/interim/works_raw.parquet")
PER_PAGE = 200


def page_url(config: dict, page: int) -> str:
    filters = [
        f"locations.source.id:{ESCHOLARSHIP_SOURCE}",
        openalex_filter(config),
        *type_filters(config),
    ]
    params = {"filter": ",".join(filters), "per-page": PER_PAGE, "page": page}
    return f"{oa.OPENALEX_BASE}/works?{urllib.parse.urlencode(params)}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-credits", type=float, default=1500)
    parser.add_argument("--out", type=Path, default=Path("scratch/escholarship_openalex.json"))
    args = parser.parse_args()

    config = load_query_config()
    oa.load_openalex_key()
    run_id = "escholarship-openalex-audit"
    first = audit.fetch_openalex_urls(
        [page_url(config, 1)], run_id=f"{run_id}-p1", max_credits=args.max_credits
    )
    total = int(first["meta"].get("count") or 0)
    pages = math.ceil(total / PER_PAGE)
    rest = audit.fetch_openalex_urls(
        [page_url(config, p) for p in range(2, pages + 1)],
        run_id=f"{run_id}-rest",
        max_credits=args.max_credits,
    )
    works = first["works"] + rest["works"]
    raw_ids = {
        oa.compact_openalex_id(r["openalex_id"])
        for r in pq.read_table(RAW, columns=["openalex_id"]).to_pylist()
    }
    inst = set(oa.load_institution_ids())
    missing = [w for w in works if oa.compact_openalex_id(w.get("id")) not in raw_ids]
    missing_ca = [w for w in missing if audit.keep_for_corpus(w, inst)]
    no_affiliation = [
        w
        for w in missing
        if not any(
            (a or {}).get("institutions") or (a or {}).get("raw_affiliation_strings")
            for a in w.get("authorships") or []
        )
    ]
    result = {
        "query_version": config.get("version"),
        "escholarship_query_matches": total,
        "fetched": len(works),
        "in_raw_corpus": len(works) - len(missing),
        "missing": len(missing),
        "missing_passing_ca_gate": len(missing_ca),
        "missing_without_any_affiliation": len(no_affiliation),
        "missing_by_type": dict(collections.Counter(w.get("type") for w in missing)),
        "missing_by_decade": dict(
            collections.Counter(f"{(w.get('publication_year') or 0) // 10 * 10}s" for w in missing)
        ),
        "credits": first["credits"] + rest["credits"],
        "requests": first["requests"] + rest["requests"],
        "missing_ids": sorted(oa.compact_openalex_id(w.get("id")) for w in missing),
        "missing_ca_ids": sorted(oa.compact_openalex_id(w.get("id")) for w in missing_ca),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print({k: v for k, v in result.items() if not k.endswith("_ids")})


if __name__ == "__main__":
    main()
