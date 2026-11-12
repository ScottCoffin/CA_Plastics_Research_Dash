"""UX-4 (owner spec): evidence map shows its honest state (static source checks)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FW_SRC = ROOT / "framework" / "src"
PAGE = FW_SRC / "evidence.md"
SCRIPT = FW_SRC / "components" / "evidence.js"


def test_placeholder_sections_are_removed():
    html = PAGE.read_text(encoding="utf-8")
    assert "ev-placeholder" not in html
    assert 'id="ev-v1-heading"' not in html
    assert 'id="ev-v2-heading"' not in html
    assert 'id="ev-v5-heading"' not in html


def test_exactly_one_in_development_notice():
    html = PAGE.read_text(encoding="utf-8")
    assert len(re.findall(r'<p class="ev-notice">', html)) == 1
    assert len(re.findall(r"In development", html)) == 1


def test_no_h3_headings_in_evidence_page():
    html = PAGE.read_text(encoding="utf-8")
    assert not re.search(r"<h3[\s>]", html), "section headings must be h2 under the h1"
    assert len(re.findall(r"^# ", html, flags=re.MULTILINE)) == 1


def test_evidence_js_has_failed_state_and_retry_handler():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "Could not load the evidence data." in source
    assert 'retry.textContent = "Retry";' in source
    assert re.search(r'retry\.addEventListener\("click",\s*\(\)\s*=>\s*loadBundle\(\)\)', source)


def test_evidence_js_reports_loaded_count():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "Loaded ${formatCount(index.N)} works." in source
