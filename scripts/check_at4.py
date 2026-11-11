"""Acceptance checks for the AT-4 serving bundle (offline, committed bundle only).

(a) landing payload (works_index.json + facets.json + facets.bin, gzip) <= 3,000,000 bytes
(b) no public Parquet column name contains "abstract"; every Parquet file reads with pyarrow
(c) node runs site/assets/facets.js against the bundle for 25 seeded selections (with search
    tokens); totals, label counts and selected ids equal a Python reference computed from
    site/data/index.json (OA from the bundle's public works Parquet)
(d) institution tiers: non-decreasing in rank order; each member's rank_lo <= its leader's rank_hi

Exit 1 on any failure. Does not read data/processed.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import pyarrow.parquet as pq  # noqa: E402

from atlas.build.bundle import gzip_bytes, run_node_cases  # noqa: E402

LANDING_LIMIT = 3_000_000
N_CASES = 25
SEED = 20261111
UNKNOWN = "unknown"


def _reference_labels(work: dict, is_oa, ca_types: dict[str, str]) -> dict[str, set[str]]:
    """Independent label derivation from index.json fields (see Appendix C facet list)."""
    year = work.get("year")
    plastic = work.get("plastic_related")
    ca_ids = {i for i in work.get("institution_ids") or [] if i in ca_types}
    sectors = {ca_types[i] for i in ca_ids if ca_types[i]}
    oa = UNKNOWN if is_oa is None else ("open" if is_oa else "closed")
    return {
        "year": {UNKNOWN if year is None else str(year)},
        "type": {work.get("type") or UNKNOWN},
        "topic": {t for t in work.get("domain_tags") or [] if t},
        "plastic": {"unlabelled" if plastic is None else ("yes" if plastic else "no")},
        "ca_led": {"yes" if work.get("ca_led") else "no"},
        "institution": ca_ids,
        "sector": sectors,
        "oa": {oa},
    }


def _reference_case(works, labels_of, titles, sel, tokens, facet_labels):
    def base_ok(i: int, skip: str | None) -> bool:
        for facet, chosen in sel.items():
            if facet == skip or not chosen:
                continue
            if not any(label in labels_of[i][facet] for label in chosen):
                return False
        return all(tok in titles[i] for tok in tokens or [])

    selected = [i for i in range(len(works)) if base_ok(i, None)]
    counts = {f"{facet}|{label}": 0 for facet, labels in facet_labels.items() for label in labels}
    for facet in facet_labels:
        base = [i for i in range(len(works)) if base_ok(i, facet)]
        for i in base:
            for label in labels_of[i][facet]:
                counts[f"{facet}|{label}"] += 1
    return {
        "total": len(selected),
        "counts": counts,
        "ids": [works[i]["work_id"] for i in selected],
    }


def _sample_cases(rng: random.Random, facet_labels: dict[str, list[str]], titles: list[str]):
    names = sorted(facet_labels)
    cases = []
    for _ in range(N_CASES):
        sel = {}
        for facet in rng.sample(names, rng.choice([0, 1, 2, 3])):
            chosen = facet_labels[facet]
            if chosen:
                sel[facet] = rng.sample(chosen, rng.randint(1, min(3, len(chosen))))
        roll = rng.random()
        if roll < 0.5:
            words = titles[rng.randrange(len(titles))].split()
            tokens = (
                [w.lower() for w in rng.sample(words, min(len(words), rng.randint(1, 2)))]
                if words
                else []
            )
            query = " ".join(tokens) if tokens else ""
        elif roll < 0.6:
            query = ""
        else:
            query = None
        cases.append({"sel": sel, "query": query})
    return cases


def _check_landing(bundle: Path) -> tuple[bool, str]:
    names = ["works_index.json", "facets.json", "facets.bin"]
    total = sum(gzip_bytes((bundle / n).read_bytes()) for n in names)
    ok = total <= LANDING_LIMIT
    return ok, f"landing gzip bytes {total} (limit {LANDING_LIMIT})"


def _check_parquet(bundle: Path, manifest: dict) -> tuple[bool, str]:
    paths = sorted((bundle / "parquet").glob("*.parquet"))
    if not paths:
        return False, "no Parquet files under parquet/"
    problems = []
    for path in paths:
        try:
            table = pq.ParquetFile(path).read()
        except Exception as exc:  # noqa: BLE001 - report any read failure
            problems.append(f"{path.name} unreadable: {exc}")
            continue
        bad = [c for c in table.column_names if "abstract" in c.lower()]
        if bad:
            problems.append(f"{path.name} has abstract column(s): {bad}")
    expected = {"works.parquet"}
    if manifest["inputs"]["analytics_parquet_copied"]:
        expected |= {"inst_counts.parquet", "inst_tiers.parquet", "year_tag.parquet"}
    missing = sorted(expected - {p.name for p in paths})
    if missing:
        problems.append(f"missing expected Parquet: {missing}")
    if problems:
        return False, "; ".join(problems)
    return True, f"{len(paths)} Parquet files readable, no abstract column"


def _check_round_trip(bundle: Path, index_path: Path) -> tuple[bool, str]:
    node = shutil.which("node")
    if node is None:
        return False, "node not found on PATH (required for the facets.js round trip)"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    works = sorted(index["works"], key=lambda w: w["work_id"])
    works_index = json.loads((bundle / "works_index.json").read_text(encoding="utf-8"))
    if works_index["work_ids"] != [w["work_id"] for w in works]:
        return False, "works_index.json work_ids do not match index.json order"
    facets = json.loads((bundle / "facets.json").read_text(encoding="utf-8"))
    facet_labels = {f: [e["label"] for e in entries] for f, entries in facets.items()}
    ca_types = {e["label"]: e["atlas_type"] for e in facets["institution"]}

    oa_rows = pq.read_table(
        bundle / "parquet" / "works.parquet", columns=["work_id", "is_oa"]
    ).to_pylist()
    is_oa = {r["work_id"]: r["is_oa"] for r in oa_rows}
    labels_of = [_reference_labels(w, is_oa.get(w["work_id"]), ca_types) for w in works]
    titles = [(w.get("title") or "").lower() for w in works]

    rng = random.Random(SEED)
    cases = _sample_cases(rng, facet_labels, [w.get("title") or "" for w in works])
    got = run_node_cases(bundle, cases, node)
    failures = []
    for k, (case, res) in enumerate(zip(cases, got)):
        tokens = None if case["query"] is None else case["query"].lower().split()
        ref = _reference_case(works, labels_of, titles, case["sel"], tokens, facet_labels)
        if res["total"] != ref["total"]:
            failures.append(f"case {k}: total {res['total']} != {ref['total']}")
        if res["counts"] != ref["counts"]:
            diff = [key for key in ref["counts"] if res["counts"].get(key) != ref["counts"][key]]
            failures.append(f"case {k}: {len(diff)} label counts differ (e.g. {diff[:3]})")
        if res["ids"] != ref["ids"]:
            failures.append(f"case {k}: selected ids differ")
    if len(got) != len(cases):
        failures.append(f"node returned {len(got)} results for {len(cases)} cases")
    if failures:
        return False, "; ".join(failures[:5])
    return True, f"{len(cases)} node cases match the Python reference (totals, counts, ids)"


def _check_tiers(bundle: Path, manifest: dict) -> tuple[bool | None, str]:
    if not manifest["inputs"]["analytics_parquet_copied"]:
        return None, "SKIP: bundle built without analytics (no inst_tiers)"
    tiers = json.loads((bundle / "inst_tiers.json").read_text(encoding="utf-8"))["tiers"]
    ordered = sorted(tiers, key=lambda r: (r["rank_frac"], r["inst_id"]))
    problems = []
    previous = 0
    leader: dict | None = None
    for row in ordered:
        if row["tier"] < previous:
            problems.append(f"{row['inst_id']}: tier {row['tier']} decreases after {previous}")
        if row["tier"] != previous:
            leader = row
            previous = row["tier"]
        elif row["rank_lo"] > leader["rank_hi"]:
            problems.append(
                f"{row['inst_id']}: rank_lo {row['rank_lo']} > leader rank_hi {leader['rank_hi']}"
            )
    if problems:
        return False, "; ".join(problems[:5])
    n_tiers = len({r["tier"] for r in tiers})
    return True, f"{len(tiers)} institutions in {n_tiers} tiers; invariants hold"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bundle-dir", type=Path, default=REPO / "site/data/bundle")
    ap.add_argument("--index", type=Path, default=REPO / "site/data/index.json")
    args = ap.parse_args(argv)
    bundle = args.bundle_dir
    if not (bundle / "manifest.json").exists():
        print(f"FAIL bundle: {bundle} has no manifest.json; run scripts/build_bundle.py")
        return 1
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))

    results = [
        ("a landing size", *_check_landing(bundle)),
        ("b parquet", *_check_parquet(bundle, manifest)),
        ("c round trip", *_check_round_trip(bundle, args.index)),
        ("d tiers", *_check_tiers(bundle, manifest)),
    ]
    failed = False
    for name, ok, message in results:
        if ok is None:
            print(f"SKIP {name}: {message}")
            continue
        print(f"{'PASS' if ok else 'FAIL'} {name}: {message}")
        failed = failed or not ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
