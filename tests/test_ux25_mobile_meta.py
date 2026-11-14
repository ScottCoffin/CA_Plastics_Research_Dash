"""UX-25: per-page meta descriptions, the favicon head option, and the mobile CSS guards."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT / "framework"
PAGES = {
    "index",
    "experts",
    "network",
    "institutions",
    "institution",
    "monitoring",
    "funding",
    "evidence",
    "policy",
    "resources",
    "about",
    "glossary",
}
SAMPLE = (
    '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    "<title>x</title></head><body></body></html>"
)


def _postbuild(expr: str) -> str:
    """Evaluate an expression with postbuild.mjs imported as module `m`, returning stdout."""
    module = (FW / "scripts" / "postbuild.mjs").resolve().as_uri()
    script = f"const m = await import({json.dumps(module)}); process.stdout.write(String({expr}));"
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=FW,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _descriptions() -> dict[str, str]:
    return json.loads(_postbuild("JSON.stringify(m.PAGE_DESCRIPTIONS)"))


def test_every_app_page_has_a_plain_language_description():
    descriptions = _descriptions()
    assert set(descriptions) == PAGES
    for page, text in descriptions.items():
        assert 50 <= len(text) <= 160, page
        assert text.endswith("."), page
        assert not re.search(r"\b(UX|EM|AT|S\d)-\d", text), page


def test_fix_html_inserts_one_description_into_head():
    html = _postbuild(f"m.fixHtml({json.dumps(SAMPLE)}, 'evidence')")
    assert html.count('<meta name="description" content="') == 1
    head = html.split("</head>")[0]
    assert '<meta name="description"' in head
    assert _descriptions()["evidence"] in head


def test_fix_html_is_idempotent_for_descriptions():
    once = _postbuild(f"m.fixHtml({json.dumps(SAMPLE)}, 'funding')")
    twice = _postbuild(f"m.fixHtml({json.dumps(once)}, 'funding')")
    assert once == twice


def test_fix_html_keeps_an_existing_description():
    existing = SAMPLE.replace("<title>", '<meta name="description" content="Custom."><title>')
    html = _postbuild(f"m.fixHtml({json.dumps(existing)}, 'about')")
    assert html.count('name="description"') == 1
    assert 'content="Custom."' in html


def test_fix_html_without_a_known_page_adds_no_description():
    html = _postbuild(f"m.fixHtml({json.dumps(SAMPLE)}, 'not-a-page')")
    assert 'name="description"' not in html


def test_fix_html_escapes_attribute_text():
    html = _postbuild(f"m.addDescription({json.dumps(SAMPLE)}, 'index')")
    assert "&quot;" not in html  # plain text descriptions need no escaping
    assert _postbuild("m.addDescription('<head></head>', 'index')").count('name="description"') == 1


def test_favicon_is_declared_in_framework_head_option():
    config = (FW / "observablehq.config.js").read_text(encoding="utf-8")
    assert re.search(r"^\s*head:\s*`", config, re.MULTILINE)
    assert 'rel="icon"' in config
    assert "data:image/svg+xml" in config


@pytest.mark.parametrize(
    ("css", "selector"),
    [
        ("evidence.css", '#evidence-root .ev-option input[type="checkbox"]'),
        ("funding.css", '.grants-field input[type="number"]'),
        ("funding.css", '.grants-check input[type="checkbox"]'),
        ("monitoring.css", "#monitoring-root table a"),
        ("resources.css", "#resources-root .rs-card a"),
    ],
)
def test_touch_target_rules_present(css: str, selector: str):
    text = (FW / "src" / "components" / css).read_text(encoding="utf-8")
    assert selector in text


def test_evidence_layout_column_can_shrink_below_content_width():
    text = (FW / "src" / "components" / "evidence.css").read_text(encoding="utf-8")
    assert "grid-template-columns: minmax(0, 1fr); } }" in text
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);" in text
