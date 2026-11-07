from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_about_page_has_exact_disclaimer_and_correction_route() -> None:
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert "Independent project; not an official OEHHA or State product." in html
    assert 'id="about-freshness"' in html
    assert "docs/METHODS.md" in html
    assert "issues/new?title=Atlas%20data%20correction" in html


def test_about_view_model_uses_build_metadata_for_fixture_and_live_counts() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_s3_5.py")],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "About renderer runtime checks passed" in result.stdout
