"""Build bit-mask facet files for the SPK-4 spike (Add-on A1, Appendix C).

Stdlib only. For a seeded synthetic corpus, writes into one directory:

  works_index.json  ordered work_id list; record i <-> bit i
  facets.json       {facet: [{label, id, count}]}; id = index of the label's bit-set
  facets.bin        header (magic "BMF1", version, N, number of sets; uint32 LE)
                    followed by one little-endian Uint32Array of ceil(N/32) words per id
  works.csv         flat table used by run_spike.py to build the Mosaic Parquet

Label precedence: a human annotation, when present, is the definite 0/1 value;
otherwise the model label is its confidence thresholded at 0.5. The confidence
array itself is not written (see docs/SPK_4_FACETS.md, caveats).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import struct
import sys
from pathlib import Path

SEED = 20261109
MAGIC = b"BMF1"
VERSION = 1
HEADER = struct.Struct("<4sIII")

YEARS = [str(y) for y in range(1990, 2027)]
INST_TYPES = [
    "University",
    "Government",
    "NGO",
    "Industry",
    "Consultancy",
    "Research institute",
    "Other",
]
INST_TYPE_W = [5, 3, 2, 1, 1, 2, 1]
N_INSTITUTIONS = 150
INSTITUTIONS = [f"Institution {k:03d}" for k in range(1, N_INSTITUTIONS + 1)]
CA_BASIS = ["Statewide", "Regional", "Local", "Non-CA"]
CA_BASIS_W = [4, 3, 2, 1]
OA_STATUS = ["Gold", "Green", "Hybrid", "Bronze", "Closed"]
OA_STATUS_W = [2, 3, 2, 1, 4]
STUDY_TYPES = [
    "Field survey",
    "Lab experiment",
    "Modelling",
    "Review",
    "Meta-analysis",
    "Case study",
    "Policy analysis",
    "Survey",
    "Monitoring",
    "Sampling campaign",
    "Life-cycle assessment",
    "Market analysis",
    "Interview",
    "Experiment",
    "Other",
]
# Single-word labels: each becomes a comp_<label> boolean column in the Parquet.
COMPARTMENTS = [
    "water",
    "sediment",
    "air",
    "soil",
    "biota",
    "wastewater",
    "stormwater",
    "landfill",
    "fish",
    "bird",
    "mammal",
    "drinking_water",
]
COMPARTMENT_P = [0.30, 0.25, 0.20, 0.20, 0.15, 0.15, 0.12, 0.10, 0.10, 0.08, 0.05, 0.05]
DOMAINS = [
    "marine",
    "freshwater",
    "health",
    "policy",
    "recycling",
    "materials",
    "economics",
    "waste",
]
DOMAIN_P = [0.08, 0.10, 0.14, 0.18, 0.20, 0.24, 0.28, 0.34]
FLAGS = {"pdf": 0.7, "peer_reviewed": 0.6, "dataset": 0.15, "code": 0.1, "multi_country": 0.25}


def facet_defs() -> list[tuple[str, list[str]]]:
    """The 20 facets: 7 categorical/multi, 8 domain tags, 5 flags."""
    defs = [
        ("year", YEARS),
        ("institution_type", INST_TYPES),
        ("institution", INSTITUTIONS),
        ("ca_basis", CA_BASIS),
        ("oa_status", OA_STATUS),
        ("study_type", STUDY_TYPES),
        ("compartment", COMPARTMENTS),
    ]
    defs += [(f"dom_{d}", ["yes"]) for d in DOMAINS]
    defs += [(f"flag_{f}", ["yes"]) for f in FLAGS]
    return defs


def generate(n: int, seed: int = SEED) -> list[dict]:
    """Seeded synthetic works. Each record holds resolved facet values."""
    rng = random.Random(seed)
    year_w = [1 + 0.3 * i for i in range(len(YEARS))]
    inst_w = [1 / (k + 1) ** 1.1 for k in range(N_INSTITUTIONS)]
    records = []
    for i in range(n):
        cat = {
            "year": rng.choices(YEARS, year_w)[0],
            "institution_type": rng.choices(INST_TYPES, INST_TYPE_W)[0],
            "institution": INSTITUTIONS[rng.choices(range(N_INSTITUTIONS), inst_w)[0]],
            "ca_basis": rng.choices(CA_BASIS, CA_BASIS_W)[0],
            "oa_status": rng.choices(OA_STATUS, OA_STATUS_W)[0],
            "study_type": rng.choice(STUDY_TYPES),
        }
        multi = {c for c, p in zip(COMPARTMENTS, COMPARTMENT_P) if rng.random() < p}
        bools = set()
        for d, p in zip(DOMAINS, DOMAIN_P):
            truth = rng.random() < p
            # Model confidence is a noisy score around the truth; a 5% human
            # annotation subset supersedes the model label (Appendix C precedence).
            confidence = min(1.0, max(0.0, 0.5 + (0.35 if truth else -0.35) + rng.gauss(0, 0.2)))
            human = truth if rng.random() < 0.05 else None
            model = confidence >= 0.5
            resolved = human if human is not None else model
            if resolved:
                bools.add(f"dom_{d}")
        for f, p in FLAGS.items():
            if rng.random() < p:
                bools.add(f"flag_{f}")
        records.append({"work_id": f"W{i + 1:06d}", "cat": cat, "multi": multi, "bools": bools})
    return records


def record_labels(rec: dict) -> list[tuple[str, str]]:
    """(facet, label) pairs that are true for one record."""
    out = list(rec["cat"].items())
    out += [("compartment", c) for c in rec["multi"]]
    out += [(b, "yes") for b in rec["bools"]]
    return out


def build(records: list[dict]):
    """Return (facets dict, raw bit-set bytes, words per set, number of sets)."""
    defs = facet_defs()
    ids: dict[tuple[str, str], int] = {}
    for facet, labels in defs:
        for lab in labels:
            ids[(facet, lab)] = len(ids)
    n = len(records)
    words = math.ceil(n / 32)
    stride = words * 4
    body = bytearray(len(ids) * stride)
    counts = [0] * len(ids)
    for i, rec in enumerate(records):
        byte, mask = i >> 3, 1 << (i & 7)
        for key in record_labels(rec):
            s = ids[key]
            body[s * stride + byte] |= mask
            counts[s] += 1
    facets = {
        facet: [
            {"label": lab, "id": ids[(facet, lab)], "count": counts[ids[(facet, lab)]]}
            for lab in labels
        ]
        for facet, labels in defs
    }
    return facets, bytes(body), words, len(ids)


def write_csv(records: list[dict], path: Path) -> None:
    """Flat table for DuckDB: categorical columns plus one boolean per label."""
    cat_cols = list(records[0]["cat"].keys())
    cols = ["work_id", *cat_cols]
    cols += [f"comp_{c}" for c in COMPARTMENTS]
    cols += [f"dom_{d}" for d in DOMAINS] + [f"flag_{f}" for f in FLAGS]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for rec in records:
            row = [rec["work_id"], *(rec["cat"][c] for c in cat_cols)]
            row += ["true" if c in rec["multi"] else "false" for c in COMPARTMENTS]
            row += ["true" if f"dom_{d}" in rec["bools"] else "false" for d in DOMAINS]
            row += ["true" if f"flag_{f}" in rec["bools"] else "false" for f in FLAGS]
            w.writerow(row)


def write_dataset(n: int, out: Path, seed: int = SEED):
    """Write all bit-mask files plus works.csv for N works into `out`."""
    out.mkdir(parents=True, exist_ok=True)
    records = generate(n, seed)
    facets, body, words, nsets = build(records)
    ids = [r["work_id"] for r in records]
    (out / "works_index.json").write_text(json.dumps(ids, separators=(",", ":")), encoding="utf-8")
    (out / "facets.json").write_text(json.dumps(facets, separators=(",", ":")), encoding="utf-8")
    (out / "facets.bin").write_bytes(HEADER.pack(MAGIC, VERSION, n, nsets) + body)
    write_csv(records, out / "works.csv")
    return records, facets


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    _, facets = write_dataset(args.n, args.out)
    nsets = sum(len(v) for v in facets.values())
    print(json.dumps({"n": args.n, "facets": len(facets), "sets": nsets, "out": str(args.out)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
