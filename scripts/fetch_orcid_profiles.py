"""Fetch ORCID public profiles for the expert list and build the enrichment outputs.

Live calls go to pub.orcid.org only (CC0 data, no key). ``--offline`` rebuilds every
output from the raw cache under data/raw/orcid/ without any request.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.ingest import orcid as oc  # noqa: E402

INDEX_JSON = ROOT / "site" / "data" / "index.json"
INSTITUTIONS_JSON = ROOT / "site" / "data" / "institutions.json"
INST_PARQUET = ROOT / "data" / "processed" / "institutions.parquet"
AUTHORSHIPS = ROOT / "data" / "processed" / "normalized" / "authorships.parquet"
WORKS = ROOT / "data" / "processed" / "normalized" / "works.parquet"
RAW = ROOT / "data" / "raw" / "orcid"
RAW_ROR = RAW / "_ror"
OUT_PARQUET = ROOT / "data" / "processed" / "orcid_profiles.parquet"
MISSING_CSV = ROOT / "data" / "interim" / "orcid_missing_dois.csv"
CANDIDATES_CSV = ROOT / "data" / "interim" / "orcid_ror_candidates.csv"
REPORT = ROOT / "docs" / "api_notes" / "orcid_enrichment.md"

EMP_TYPE = pa.struct(
    [
        ("org", pa.string()),
        ("ror", pa.string()),
        ("city", pa.string()),
        ("region", pa.string()),
        ("country", pa.string()),
        ("start_year", pa.int32()),
        ("end_year", pa.int32()),
        ("role", pa.string()),
    ]
)
SCHEMA = pa.schema(
    [
        ("author_id", pa.string()),
        ("orcid", pa.string()),
        ("biography", pa.string()),
        ("keywords", pa.list_(pa.string())),
        ("researcher_urls", pa.list_(pa.struct([("name", pa.string()), ("url", pa.string())]))),
        ("employments", pa.list_(EMP_TYPE)),
        ("ca_employment_years", pa.list_(pa.list_(pa.int32()))),
        ("orcid_dois", pa.list_(pa.string())),
        ("fetched_at", pa.string()),
    ]
)


def load_experts() -> list[dict[str, str]]:
    data = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    out = []
    for a in data["authors"]:
        out.append(
            {
                "author_id": a["author_id"],
                "name": a.get("name", ""),
                "orcid": oc.normalize_orcid(a.get("orcid")),
            }
        )
    return out


def load_ca_rors() -> set[str]:
    rors: set[str] = set()
    inst = pq.read_table(INST_PARQUET, columns=["ror_id", "region"]).to_pylist()
    rors.update(oc.normalize_ror(r["ror_id"]) for r in inst if r["region"] == "California")
    for i in json.loads(INSTITUTIONS_JSON.read_text(encoding="utf-8"))["institutions"]:
        if i.get("ca_flag"):
            rors.add(oc.normalize_ror(i.get("ror")))
    rors.discard("")
    return rors


def fetch_all(experts: list[dict[str, str]], client: oc.OrcidClient, refresh_days: float) -> None:
    todo = [e["orcid"] for e in experts if e["orcid"]]
    seen: set[str] = set()
    todo = [o for o in todo if not (o in seen or seen.add(o))]
    done = 0
    t0 = time.time()

    def work(orcid: str) -> list[int]:
        try:
            return oc.fetch_expert(client, RAW, orcid, refresh_days)
        except oc.BudgetExhausted:
            return [-1]

    with ThreadPoolExecutor(max_workers=4) as pool:
        for codes in pool.map(work, todo):
            done += 1
            if -1 in codes:
                print("request cap reached; stopping fetch")
                break
            if done % 200 == 0:
                print(
                    f"  {done}/{len(todo)} experts, {client.requests} requests, "
                    f"{time.time() - t0:.0f}s",
                    flush=True,
                )


def build_rows(
    experts: list[dict[str, str]], ca_rors: set[str]
) -> tuple[list[dict], dict[str, list[tuple[str, int | None]]]]:
    rows: list[dict] = []
    dois_by_author: dict[str, list[tuple[str, int | None]]] = {}
    for e in sorted(experts, key=lambda x: x["author_id"]):
        orcid = e["orcid"]
        if not orcid:
            continue
        person_path = oc.cache_path(RAW, orcid, "person")
        person = oc.read_cache(person_path)
        if person is None or "_status" in person:
            continue
        emp_payload = oc.read_cache(oc.cache_path(RAW, orcid, "employments")) or {}
        works_payload = oc.read_cache(oc.cache_path(RAW, orcid, "works")) or {}
        emps = oc.parse_employments(emp_payload) if "_status" not in emp_payload else []
        works = oc.parse_work_dois(works_payload) if "_status" not in works_payload else []
        fetched = datetime.fromtimestamp(int(person_path.stat().st_mtime), UTC)
        rows.append(
            {
                "author_id": e["author_id"],
                "orcid": orcid,
                "biography": oc.parse_biography(person),
                "keywords": oc.parse_keywords(person),
                "researcher_urls": oc.parse_researcher_urls(person),
                "employments": emps,
                "ca_employment_years": oc.ca_employment_years(emps, ca_rors),
                "orcid_dois": [d for d, _ in works],
                "fetched_at": fetched.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
        dois_by_author[e["author_id"]] = works
    return rows, dois_by_author


def write_parquet(rows: list[dict]) -> None:
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), OUT_PARQUET, compression="zstd")


def carry_forward(
    rows: list[dict], experts: list[dict[str, str]]
) -> tuple[dict[str, int], list[dict]]:
    prof = {r["author_id"]: r for r in rows}
    a = pq.read_table(AUTHORSHIPS, columns=["work_id", "author_id", "author_name", "ca_basis"])
    w = pq.read_table(WORKS, columns=["work_id", "year"]).to_pylist()
    year = {x["work_id"]: x["year"] for x in w}
    has_orcid = {e["author_id"] for e in experts if e["orcid"]}
    counts = {
        "confirmed": 0,
        "contradicted": 0,
        "no_evidence": 0,
        "no_orcid": 0,
        "orcid_no_dated_employment": 0,
    }
    contradicted: list[dict] = []
    for r in a.to_pylist():
        if r["ca_basis"] != "author_carry_forward":
            continue
        p = prof.get(r["author_id"])
        y = year.get(r["work_id"])
        if p is None:
            counts["no_evidence"] += 1
            counts[
                "no_orcid" if r["author_id"] not in has_orcid else "orcid_no_dated_employment"
            ] += 1
            continue
        res = oc.classify_carry_forward(y, p["employments"], p["ca_employment_years"])
        counts[res] += 1
        if res == "no_evidence":
            counts["orcid_no_dated_employment"] += 1
        if res == "contradicted":
            summ = "; ".join(
                f"{e['org']} ({e['region'] or e['country'] or '?'}) "
                f"{e['start_year'] or '?'}-{e['end_year'] or 'present'}"
                for e in p["employments"][:4]
            )
            contradicted.append(
                {"name": r["author_name"], "year": y, "summary": summ, "work_id": r["work_id"]}
            )
    return counts, contradicted


def missing_dois(dois_by_author: dict[str, list[tuple[str, int | None]]]) -> list[tuple]:
    corpus = {oc.normalize_doi(x["doi"]) for x in pq.read_table(WORKS, columns=["doi"]).to_pylist()}
    out = []
    for aid in sorted(dois_by_author):
        for doi, yr in dois_by_author[aid]:
            if doi not in corpus:
                out.append((aid, doi, yr if yr is not None else ""))
    MISSING_CSV.parent.mkdir(parents=True, exist_ok=True)
    with MISSING_CSV.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["author_id", "doi", "year"])
        wr.writerows(out)
    return out


def top_ca_rors(n: int) -> list[tuple[str, str, int]]:
    a = pq.read_table(AUTHORSHIPS, columns=["work_id", "institution_ids"]).to_pylist()
    works: dict[str, set[str]] = {}
    for r in a:
        for i in r["institution_ids"] or []:
            works.setdefault(i, set()).add(r["work_id"])
    inst = {
        r["openalex_id"]: r
        for r in pq.read_table(
            INST_PARQUET, columns=["openalex_id", "display_name", "ror_id", "region"]
        ).to_pylist()
    }
    ranked = sorted(works.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    out = []
    for iid, ws in ranked:
        rec = inst.get(iid)
        ror = oc.normalize_ror(rec["ror_id"]) if rec else ""
        if rec and rec["region"] == "California" and ror:
            out.append((ror, rec["display_name"], len(ws)))
        if len(out) == n:
            break
    return out


def discover(
    n: int, client: oc.OrcidClient | None, refresh_days: float, expert_orcids: set[str]
) -> tuple[list[tuple[str, str, int, int, int]], int]:
    rows: list[tuple[str, str, int, int, int]] = []
    candidates: dict[str, dict] = {}
    for ror, name, wcount in top_ca_rors(n):
        path = RAW_ROR / f"{ror}.json"
        if client is not None and not oc.cache_fresh(path, refresh_days):
            code, payload = client.get_json(oc.ror_search_url(ror))
            if code == 200:
                oc.write_cache(path, oc.strip_search_payload(payload))
        payload = oc.read_cache(path)
        if payload is None:
            continue
        found = oc.parse_ror_search(payload)
        new = [f for f in found if f["orcid"] not in expert_orcids]
        for f in new:
            c = candidates.setdefault(f["orcid"], {**f, "rors": []})
            c["rors"].append(ror)
        rows.append((name, ror, wcount, len(found), len(new)))
    CANDIDATES_CSV.parent.mkdir(parents=True, exist_ok=True)
    with CANDIDATES_CSV.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["orcid", "given_names", "family_names", "institution", "ror_ids"])
        for o in sorted(candidates):
            c = candidates[o]
            wr.writerow(
                [o, c["given_names"], c["family_names"], c["institution"], "|".join(c["rors"])]
            )
    return rows, len(candidates)


def pct(n: int, d: int) -> str:
    return f"{n} ({100 * n / d:.1f}%)" if d else f"{n}"


def write_report(
    experts: list[dict[str, str]],
    rows: list[dict],
    cf: tuple[dict[str, int], list[dict]],
    missing: list[tuple],
    disc: tuple[list, int] | None,
    requests: int,
) -> None:
    n_orcid = sum(1 for e in experts if e["orcid"])
    n = len(rows)
    cov = {
        "biography": sum(1 for r in rows if r["biography"]),
        "keywords": sum(1 for r in rows if r["keywords"]),
        "researcher URLs": sum(1 for r in rows if r["researcher_urls"]),
        "employments": sum(1 for r in rows if r["employments"]),
        "any CA employment (dated)": sum(1 for r in rows if r["ca_employment_years"]),
        "any CA employment (incl. undated)": sum(
            1
            for r in rows
            if any(oc.is_ca_employment(e, load_ca_rors_cached()) for e in r["employments"])
        ),
        "ORCID works with a DOI": sum(1 for r in rows if r["orcid_dois"]),
    }
    counts, contradicted = cf
    total_cf = counts["confirmed"] + counts["contradicted"] + counts["no_evidence"]
    lines = [
        "# ORCID enrichment (S2.5c, feeding S9.5)",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d} by `scripts/fetch_orcid_profiles.py` from the "
        "ORCID "
        "public API (CC0, no key). Raw JSON is cached in `data/raw/orcid/` (gitignored); the "
        "`emails` section of `/person` is dropped before caching and nothing contact-related is "
        "stored. Requests this run: " + str(requests) + " (0 in `--offline` mode).",
        "",
        "## a. Coverage",
        "",
        f"Experts: {len(experts)}; with an ORCID: {n_orcid}; profiles fetched and readable: {n}.",
        "",
        "| Field | Experts with data (of profiles read) |",
        "|---|---|",
    ]
    lines += [f"| {k} | {pct(v, n)} |" for k, v in cov.items()]
    lines += [
        "",
        "Dated CA employment keeps employments that have a start or end year and that are in "
        "California (US region CA/California, or a ROR matching a California institution).",
        "",
        "## b. Carry-forward check (CA-CARRY)",
        "",
        f"`author_carry_forward` authorships: {total_cf}. Work year within a dated California "
        "employment (+/-1 year; open end = present) is confirmed. Contradicted means the author "
        "has dated employments but none in California cover the year.",
        "",
        f"- confirmed: {pct(counts['confirmed'], total_cf)}",
        f"- contradicted: {pct(counts['contradicted'], total_cf)}",
        f"- no evidence: {pct(counts['no_evidence'], total_cf)} "
        f"(author has no ORCID: {counts['no_orcid']}; ORCID without dated employments or work "
        f"year: {counts['orcid_no_dated_employment']})",
        "",
        "Contradicted examples (up to 15):",
        "",
    ]
    for c in contradicted[:15]:
        lines.append(f"- {c['name']}, work year {c['year']}: {c['summary']}")
    if not contradicted:
        lines.append("- none")
    lines += [
        "",
        "This is evidence for a later rule decision; normalize is unchanged.",
        "",
        "## c. ORCID works not in the corpus",
        "",
        f"DOIs on experts' ORCID records missing from works.parquet: {len(missing)} "
        f"({len({m[1] for m in missing})} distinct) across {len({m[0] for m in missing})} experts. "
        "These are mostly the experts' unrelated publications (the corpus is a plastics query), "
        "so the list needs an OpenAlex DOI+query match, which costs credits. Saved to "
        "`data/interim/orcid_missing_dois.csv`. Nothing was ingested.",
        "",
        "## d. ROR discovery",
        "",
    ]
    if disc is None:
        lines.append("Not run (no `--discover-ror`, no cache).")
    else:
        drows, ncand = disc
        lines += [
            f"Top {len(drows)} California institutions by works in the corpus, ORCID "
            "`expanded-search` by ROR, first 200 results each. "
            f"Distinct ORCID researchers not on the expert list: {ncand} "
            "(`data/interim/orcid_ror_candidates.csv`).",
            "",
            "| Institution | ROR | Corpus works | Results (<=200) | Not on expert list |",
            "|---|---|---|---|---|",
        ]
        lines += [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in drows]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


_CA_RORS: set[str] | None = None


def load_ca_rors_cached() -> set[str]:
    global _CA_RORS
    if _CA_RORS is None:
        _CA_RORS = load_ca_rors()
    return _CA_RORS


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="only the first N experts with an ORCID")
    ap.add_argument("--max-requests", type=int, default=6000)
    ap.add_argument("--refresh-days", type=float, default=30)
    ap.add_argument("--discover-ror", type=int, default=0, metavar="N")
    ap.add_argument("--offline", action="store_true", help="rebuild from the cache only")
    args = ap.parse_args()

    experts_all = load_experts()
    experts = experts_all
    if args.limit:
        with_orcid = [e for e in experts_all if e["orcid"]][: args.limit]
        experts = with_orcid
    ca_rors = load_ca_rors()
    client = None if args.offline else oc.OrcidClient(max_requests=args.max_requests)
    t0 = time.time()
    if client is not None:
        fetch_all(experts, client, args.refresh_days)
    rows, dois = build_rows(experts, ca_rors)
    write_parquet(rows)
    print(f"profiles: {len(rows)} -> {OUT_PARQUET.relative_to(ROOT)}")
    cf = carry_forward(rows, experts_all)
    missing = missing_dois(dois)
    disc = None
    if args.discover_ror or args.offline:
        n = args.discover_ror or 30
        disc = discover(
            n, client, args.refresh_days, {e["orcid"] for e in experts_all if e["orcid"]}
        )
        if not disc[0]:
            disc = None
    write_report(experts_all, rows, cf, missing, disc, client.requests if client else 0)
    print(f"requests: {client.requests if client else 0}; elapsed {time.time() - t0:.0f}s")
    print(f"carry-forward: {cf[0]}; missing DOIs: {len(missing)}")
    if disc:
        print(f"ROR candidates: {disc[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
