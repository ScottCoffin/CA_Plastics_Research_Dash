"""Offline acceptance check for S8.8 (SWRCB FAAST awarded proposals).

No network calls. Runs the ingest script against the saved fixtures in a temporary directory,
checks the output schema and privacy rule, and checks that the API note is committed.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

from atlas.ingest.grants import GRANT_COLUMNS, validate_grants
from atlas.ingest.grants.faast import KEYWORDS, SOURCE

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/s8_8_faast"
NOTE = ROOT / "docs/api_notes/faast.md"
CONTACT_TOKENS = ("Jane Synthetic", "jane.synthetic", "example.invalid", "555-010-0199")


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def main() -> int:
    if len(KEYWORDS) != 8:
        _fail(f"expected 8 keywords, found {len(KEYWORDS)}")
    if not FIXTURES.is_dir():
        _fail("S8.8 fixture directory is missing")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        output = work / "swrcb_faast.parquet"
        status = work / "status.json"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/ingest_faast.py"),
                "--html-fixture-dir",
                str(FIXTURES),
                "--output",
                str(output),
                "--status",
                str(status),
                "--raw-dir",
                str(work / "raw"),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
            check=False,
        )
        if result.returncode != 0:
            _fail(f"ingest_faast.py exited {result.returncode}")
        summary = json.loads(result.stdout.strip().splitlines()[-1])
        if summary.get("status") != "ok" or summary.get("requests") != 0:
            _fail(f"fixture run was not ok offline: {summary.get('status')}")
        if summary.get("output_rows", 0) < 1:
            _fail("fixture run produced no rows")
        table = pq.read_table(output)
        if table.column_names != list(GRANT_COLUMNS):
            _fail("output columns do not match GRANT_COLUMNS")
        rows = table.to_pylist()
        validate_grants(rows)
        if {row["source"] for row in rows} != {SOURCE}:
            _fail("output source is not swrcb_faast")
        blob = json.dumps(rows, default=str) + status.read_text(encoding="utf-8")
        for token in CONTACT_TOKENS:
            if token in blob:
                _fail("a contact token leaked into the output or status")
        if re.search(r"@|\d{3}-\d{3}-\d{4}", blob):
            _fail("an email or phone pattern leaked into the output or status")
    if not NOTE.exists():
        _fail("docs/api_notes/faast.md is missing")
    print("OK: S8.8 FAAST offline checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
