"""S2.5(c): DOIs of ORCID researchers at California institutions who are not experts yet.

``data/interim/orcid_ror_candidates.csv`` (``fetch_orcid_profiles.py --discover-ror``)
lists ORCID researchers employed at the top California institutions (ORCID
expanded-search by ROR) who are not on the expert list. This script fetches each one's
public ORCID ``works`` list (pub.orcid.org, CC0, no key; 8 requests/s; cached under
gitignored ``data/raw/orcid/``; only the works endpoint, so no contact data) and writes
the distinct DOIs to ``data/interim/ror_researcher_dois.txt``. Then run
``ingest_orcid_dois.py --dois-file data/interim/ror_researcher_dois.txt``, which keeps
only works that pass the plastics rule and the California gate.

    PYTHONPATH=src py -3.14 scripts/fetch_ror_researcher_dois.py [--offline]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from atlas.ingest import orcid

CANDIDATES = Path("data/interim/orcid_ror_candidates.csv")
OUT = Path("data/interim/ror_researcher_dois.txt")
CACHE_ROOT = Path("data/raw/orcid")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="cache only; no requests")
    parser.add_argument("--max-requests", type=int, default=6000)
    parser.add_argument("--refresh-days", type=float, default=30)
    args = parser.parse_args()

    with CANDIDATES.open(encoding="utf-8", newline="") as handle:
        orcids = [orcid.normalize_orcid(row["orcid"]) for row in csv.DictReader(handle)]
    orcids = sorted({o for o in orcids if o})
    client = orcid.OrcidClient(max_requests=args.max_requests)
    fetched = failed = 0
    dois: set[str] = set()
    for value in orcids:
        if not args.offline:
            try:
                code = orcid.fetch_endpoint(client, CACHE_ROOT, value, "works", args.refresh_days)
            except orcid.BudgetExhausted:
                print("request cap reached; rerun to continue from the cache")
                break
            if code is not None:
                fetched += 1
                failed += code != 200
        payload = orcid.read_cache(orcid.cache_path(CACHE_ROOT, value, "works"))
        if payload and "_status" not in payload:
            dois.update(doi for doi, _year in orcid.parse_work_dois(payload) if doi)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(sorted(dois)) + "\n", encoding="utf-8")
    print(
        f"candidates {len(orcids)}; requests {client.requests} (fetched {fetched}, "
        f"non-200 {failed}); distinct DOIs {len(dois)} -> {OUT}"
    )


if __name__ == "__main__":
    main()
