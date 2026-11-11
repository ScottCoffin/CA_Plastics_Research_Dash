"""S8.10 acceptance check: grants export payload, size budget, and Funding panel markup.

Offline only. Validates the committed ``site/data/grants.json`` (schema, privacy, sort
order, aggregate totals, gzip budget) and confirms the Funding awards panel exists while
the S8.9 "Open funding calls" panel remains intact below it.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from atlas.build import grants_export as ge  # noqa: E402

PAYLOAD = ROOT / "site" / "data" / "grants.json"
INDEX = ROOT / "site" / "index.html"
TOP_KEYS = {
    "schema_version",
    "generated_at",
    "caveat",
    "sector_labels",
    "counts",
    "sources",
    "columns",
    "rows",
    "aggregates",
}
FORBIDDEN_KEY_PARTS = ("abstract", "email")
GZIP_LIMIT_BYTES = 1_000_000  # slim grants export budget (S8.10)
INITIAL_PAYLOAD_LIMIT = 3 * 1024 * 1024  # C5 initial payload budget
PANEL_MARKERS = {
    "awards panel": 'id="grants-heading"',
    "filters form": 'id="grants-filters"',
    "status region": 'id="grants-status"',
    "year chart": 'id="grants-chart-year"',
    "institution chart": 'id="grants-chart-institution"',
    "table container": 'id="grants-table"',
    "csv button": 'id="grants-csv"',
    "amount basis note": 'id="grants-basis"',
    "lazy loader": 'const GRANTS_FILE = "data/grants.json";',
    "tab hook": 'if (state.tab === "funding") showFunding();',
    "caveat text": "not comparable or additive across sources",
    "open calls heading": 'id="open-calls-heading"',
    "open calls loader": 'fetch("data/open_calls.json"',
    "open calls tab hook": 'if (state.tab === "funding") showOpenCalls();',
}


def _check_payload() -> dict:
    assert PAYLOAD.exists(), f"missing {PAYLOAD}; run scripts/build_grants_export.py"
    raw = PAYLOAD.read_bytes()
    assert raw == ge.serialize(json.loads(raw)), "grants.json must be compact sorted ASCII JSON"
    gzip_bytes = len(gzip.compress(raw, compresslevel=9, mtime=0))
    assert gzip_bytes < GZIP_LIMIT_BYTES, f"gzip {gzip_bytes} bytes exceeds {GZIP_LIMIT_BYTES}"
    assert gzip_bytes < INITIAL_PAYLOAD_LIMIT, "initial payload budget exceeded"

    payload = json.loads(raw)
    assert set(payload) == TOP_KEYS, f"top-level keys differ: {sorted(payload)}"
    assert payload["schema_version"] == ge.SCHEMA_VERSION
    assert payload["caveat"] == ge.CAVEAT, "caveat text must match the module constant"
    assert payload["columns"] == list(ge.ROW_KEYS), "columns must match ROW_KEYS"

    rows = payload["rows"]
    assert payload["counts"]["exported_rows"] == len(rows), "exported_rows must match rows"
    keys = [(row["start"] or "9999-12-31", row["grant_key"]) for row in rows]
    assert keys == sorted(keys), "rows must be sorted by (start, grant_key)"
    assert len({row["grant_key"] for row in rows}) == len(rows), "grant_key must be unique"
    for row in rows:
        assert set(row) == set(ge.ROW_KEYS), f"row keys differ for {row.get('grant_key')}"
        for key in row:
            assert not any(part in key.lower() for part in FORBIDDEN_KEY_PARTS), key
        assert row["funder_type"] in ("federal", "state", "other"), row["funder_type"]
        assert row["amount_basis"], "every row needs an amount basis"
        assert row["plastic_related"] in (True, False, None), (
            "plastic_related must be nullable bool"
        )
        assert row["ca_led"] in (True, False, None), "ca_led must be nullable bool"
        assert len(row["pi_names"]) <= ge.PI_LIMIT, "pi_names capped at PI_LIMIT"

    assert sum(info["rows"] for info in payload["sources"].values()) == len(rows)
    dated = [row for row in rows if row["fiscal_year"] is not None]
    assert payload["counts"]["undated_rows"] == len(rows) - len(dated)
    by_year = payload["aggregates"]["by_year_funder_type"]
    assert sum(item["count"] for item in by_year) == len(dated), (
        "by_year counts must total dated rows"
    )
    by_type = payload["aggregates"]["by_institution_type"]
    assert sum(item["count"] for item in by_type) == len(rows), "institution counts must total rows"
    amount_total = round(sum(row["amount"] or 0 for row in rows), 2)
    assert round(sum(item["amount_sum"] for item in by_type), 2) == amount_total
    return payload


def _check_panel() -> None:
    html = INDEX.read_text(encoding="utf-8")
    for label, marker in PANEL_MARKERS.items():
        assert marker in html, f"Funding panel marker missing: {label}"
    assert html.index('id="grants-heading"') < html.index('id="open-calls-heading"'), (
        "awards section must sit above the S8.9 open-calls section"
    )
    assert html.index('id="panel-funding"') < html.index('id="grants-heading"')


def main() -> int:
    payload = _check_payload()
    _check_panel()
    print(
        f"S8.10 check passed: {len(payload['rows'])} grant rows, "
        f"{len(payload['sources'])} sources, Funding panel markup present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
