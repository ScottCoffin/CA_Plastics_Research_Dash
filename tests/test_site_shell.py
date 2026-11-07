import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_site_shell_exposes_accessible_tabs_and_hash_state() -> None:
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert '<a class="skip-link" href="#main-content">' in html
    assert html.count('role="tab"') == 5
    assert html.count('role="tabpanel"') == 5
    assert "window.location.hash" in html
    assert "text/csv;charset=utf-8" in html
    assert "@media (max-width" in html


def test_committed_site_data_has_the_shell_inputs() -> None:
    data = ROOT / "site" / "data"
    index = json.loads((data / "index.json").read_text(encoding="utf-8"))
    institutions = json.loads((data / "institutions.json").read_text(encoding="utf-8"))
    assert index["schema_version"] == "s3.1"
    assert index["authors"] and index["works"]
    assert institutions["institutions"]
