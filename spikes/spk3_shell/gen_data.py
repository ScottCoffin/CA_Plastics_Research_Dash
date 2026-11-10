"""Write seeded synthetic atlas-shaped works JSON for the SPK-3 shell bench.

Usage: py -3.14 spikes/spk3_shell/gen_data.py [--out DIR]

Writes syn30k.json and syn100k.json (default out: scratch/spk3/data, gitignored).
Records mirror the works block of site/data/index.json, plus two fields the
fixture lacks (institution_type, oa) so both bench apps can facet on them.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

SEED = 20261109
SIZES = (30_000, 100_000)
DOMAIN = [
    "ecotox",
    "policy",
    "health",
    "fate",
    "monitoring",
    "recycling",
    "biodegradation",
    "sources",
]
FACET = ["ca-science", "water", "air", "soil", "food", "policy-brief"]
INST = ["academic", "government", "industry", "ngo", "unknown"]
STUDY = ["field", "lab", "review", "modeling"]
REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "scratch" / "spk3" / "data"


def make_work(i: int, rng: random.Random) -> dict:
    ca_led = rng.random() < 0.2
    return {
        "work_id": f"W{i:07d}",
        "year": rng.randint(2000, 2026),
        "title": f"Synthetic microplastics study {i}",
        "type": rng.choice(["article", "report", "preprint"]),
        "study_type": rng.choice(STUDY),
        "plastic_tier": rng.choice(["A", "B", "C"]),
        "domain_tags": rng.sample(DOMAIN, rng.randint(0, 3)),
        "facet_tags": rng.sample(FACET, rng.randint(0, 2)),
        "institution_ids": [rng.randint(1, 500) for _ in range(rng.randint(0, 3))],
        "author_ids": [f"A{rng.randint(1, 50_000):06d}" for _ in range(rng.randint(1, 4))],
        "cited_by_count": int(rng.expovariate(1 / 12)),
        "ca_led": ca_led,
        "ca_any_author": ca_led or rng.random() < 0.25,
        "plastic_related": True,
        "needs_review": rng.random() < 0.05,
        "institution_type": rng.choice(INST),
        "oa": rng.random() < 0.45,
    }


def build(n: int) -> dict:
    rng = random.Random(SEED + n)
    return {"schema_version": "s3.1-synthetic", "works": [make_work(i, rng) for i in range(n)]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for n in SIZES:
        path = args.out / f"syn{n // 1000}k.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(build(n), fh, ensure_ascii=False, separators=(",", ":"))
        print(f"{path.name}: {n} records, {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
