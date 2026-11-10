"""Offline acceptance check for Add-on A2 EM-1 (vocabularies and Need Ledger)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COUNTS = {
    "compartment": 12,
    "waterbody_type": 7,
    "pathway": 6,
    "source_category": 7,
    "product_type": 32,
    "size_subclass": 4,
    "rwqcb_region": 12,
    "policy_driver": 4,
    "keyword_flags": 20,
}
DISCREPANCY = '13" as a documented source discrepancy'


def fail(message: str) -> None:
    print(f"EM-1 check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(*args: str) -> None:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, check=False)
    if result.returncode != 0:
        fail(f"{' '.join(args)} exited {result.returncode}")


def main() -> int:
    taxonomy = yaml.safe_load((ROOT / "config/taxonomy.yml").read_text(encoding="utf-8"))
    a2 = taxonomy.get("add_on_a2") or fail("config/taxonomy.yml has no add_on_a2 block")
    for key, count in EXPECTED_COUNTS.items():
        if len(a2.get(key) or []) != count:
            fail(f"add_on_a2.{key} has {len(a2.get(key) or [])} values, expected {count}")
    if len(a2["study_type"]["values"]) != 15:
        fail("add_on_a2.study_type.values must have 15 values (A2 §3)")
    if a2["size_class"]["values"] != ["macro", "micro", "nano", "unspecified"]:
        fail("add_on_a2.size_class.values differ from A2 §4")

    rules = yaml.safe_load((ROOT / "config/a2_keyword_rules.yml").read_text(encoding="utf-8"))
    if set(rules["keyword_flags"]) != set(a2["keyword_flags"]):
        fail("config/a2_keyword_rules.yml keyword_flags differ from the taxonomy")
    if set(rules["product_type"]) != set(a2["product_type"]):
        fail("config/a2_keyword_rules.yml product_type differs from the taxonomy")
    for section in ("keyword_flags", "product_type"):
        for name, rule in rules[section].items():
            for key in ("any", "require_any", "exclude"):
                for pattern in rule.get(key, []):
                    try:
                        re.compile(pattern)
                    except re.error as exc:
                        fail(f"{section}.{name}.{key} pattern does not compile: {exc}")

    qc = (ROOT / "docs/need_ledger_qc.md").read_text(encoding="utf-8")
    if DISCREPANCY not in qc:
        fail("docs/need_ledger_qc.md does not record the 13/14 discrepancy")
    if not (ROOT / "docs/LABELING_GUIDE_A2_ADDENDUM.md").is_file():
        fail("missing docs/LABELING_GUIDE_A2_ADDENDUM.md")

    run("scripts/build_need_ledger.py", "--check")
    run("scripts/check_a2_scaffold.py")
    run("scripts/check_need_ledger_quotes.py")
    print("EM-1 check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
