"""UX-12: policy timeline date formatting and acronym expansion on the Policy page."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
POLICY_JS = ROOT / "framework" / "src" / "components" / "policy.js"
POLICY_MD = ROOT / "framework" / "src" / "policy.md"
SYNC = ROOT / "framework" / "scripts" / "sync_shared.mjs"

# Each term must be expanded with <abbr title="...">TERM</abbr> at its first use on the page.
EXPANSIONS = {
    "DTSC": "Department of Toxic Substances Control",
    "OPC": "Ocean Protection Council",
    "Candidate Chemicals list": "Safer Consumer Products",
    "Priority Product": "Safer Consumer Products",
    "Work Plan": "Priority Product Work Plan",
}

NODE_SCRIPT = """
import {{formatDate, renderTimeline}} from {policy_url};
const e = (id, dateAsStated, dateIso, kind) => ({{
  id, date_as_stated: dateAsStated, date_iso: dateIso, event: "e",
  source_label: "s", source_url: null, kind
}});
const out = {{
  full: formatDate("2025-11-12"),
  fullSingleDigit: formatDate("2026-10-01"),
  month: formatDate("2025-11"),
  year: formatDate("2025"),
  invalidMonth: formatDate("2025-13"),
  invalidDay: formatDate("2025-02-30"),
  leapDay: formatDate("2024-02-29"),
  garbage: formatDate("12 Nov 2025"),
  empty: formatDate(""),
  missing: formatDate(undefined),
  html: renderTimeline({{entries: [
    e("a", "1 October 2026", "2026-10-01", "effective"),
    e("b", "November 2025", "2025-11", "background"),
    e("c", "2025", "2025", ""),
    e("d", "someday", "not-a-date", "")
  ]}})
}};
process.stdout.write(JSON.stringify(out));
"""


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for the policy formatter test; "
            "install Node.js 20 or newer and ensure `node` is on PATH."
        )
    return node


def _run_node_formatter(tmp_path: Path) -> dict:
    node = _node()
    # Shared helpers are gitignored copies of site/assets; create them as `npm run build` does.
    subprocess.run([node, str(SYNC)], cwd=ROOT, check=True, capture_output=True)
    script = tmp_path / "policy_format_check.mjs"
    script.write_text(
        NODE_SCRIPT.format(policy_url=json.dumps(POLICY_JS.as_uri())), encoding="utf-8"
    )
    result = subprocess.run(
        [node, str(script)], cwd=tmp_path, check=True, capture_output=True, text=True
    )
    return json.loads(result.stdout)


def test_formatdate_full_month_year_and_fallbacks(tmp_path: Path) -> None:
    out = _run_node_formatter(tmp_path)
    assert out["full"] == "12 Nov 2025"
    assert out["fullSingleDigit"] == "1 Oct 2026"
    assert out["month"] == "Nov 2025"
    assert out["year"] == "2025"
    assert out["leapDay"] == "29 Feb 2024"
    for key in ("invalidMonth", "invalidDay", "garbage", "empty", "missing"):
        assert out[key] is None, key


def test_timeline_html_uses_prose_dates_with_machine_datetime(tmp_path: Path) -> None:
    html = _run_node_formatter(tmp_path)["html"]
    assert '<time datetime="2026-10-01">1 Oct 2026</time>' in html
    assert '<time datetime="2025-11">Nov 2025</time>' in html
    assert '<time datetime="2025">2025</time>' in html
    # Unusable date_iso falls back to the date as DTSC states it.
    assert '<p class="pol-date">someday</p>' in html


def test_policy_md_expands_each_term_at_first_use() -> None:
    md = POLICY_MD.read_text(encoding="utf-8")
    for term, expansion in EXPANSIONS.items():
        first = re.search(re.escape(term), md)
        assert first is not None, f"{term} is not on the Policy page"
        abbr = re.search(r'<abbr title="([^"]+)">' + re.escape(term) + "</abbr>", md)
        assert abbr is not None, f"{term} has no <abbr> expansion"
        assert abbr.start() <= first.start(), f"{term} is used before it is expanded"
        assert expansion in abbr.group(1), f"{term} expansion does not name: {expansion}"
    # The spelled-out form of DTSC appears in the intro text, not only in the title attribute.
    assert "The Department of Toxic Substances Control" in md
    assert "Ocean Protection Council" in md
