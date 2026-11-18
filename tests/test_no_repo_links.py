"""VD-33: public pages link to no repository; corrections go to the project email address.

Owner 2026-11-17: "there should be no links to our repo on the site", and a correction
report should email theplastiverse@gmail.com instead of opening a GitHub issue.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from atlas.build import status as st

ROOT = Path(__file__).resolve().parents[1]
EMAIL = "theplastiverse@gmail.com"
FORBIDDEN = ("github.com/ScottCoffin", "issues/new")
MAILTO_ANCHOR = re.compile(r"<a\b[^>]*href=\"mailto:[^>]*>")


def _public_files() -> list[Path]:
    framework_src = [p for p in (ROOT / "framework" / "src").rglob("*") if p.is_file()]
    site = [
        *(ROOT / "site").glob("*.html"),
        *(ROOT / "site").glob("*.txt"),
        *(ROOT / "site" / "assets").glob("*.js"),
    ]
    builders = [
        ROOT / "src" / "atlas" / "build" / "seo.py",
        ROOT / "src" / "atlas" / "build" / "status.py",
    ]
    return [ROOT / "framework" / "observablehq.config.js", *framework_src, *site, *builders]


def _text(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="ignore")


def test_public_sources_link_to_no_repository() -> None:
    files = _public_files()
    assert any(path.name == "about.md" for path in files), "scan list is empty or wrong"
    hits = [
        f"{path.relative_to(ROOT).as_posix()}: {marker}"
        for path in files
        for marker in FORBIDDEN
        if marker.lower() in _text(path).lower()
    ]
    assert hits == []


def test_status_runs_drop_github_run_urls() -> None:
    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self) -> bytes:
            run = {
                "id": 7,
                "name": "Daily",
                "run_number": 3,
                "html_url": "https://github.com/ScottCoffin/CA_Plastics_Research_Dash/actions/runs/7",
            }
            return json.dumps({"workflow_runs": [run]}).encode("utf-8")

    runs = st.fetch_actions_runs("owner/repo", "token", opener=lambda *a, **k: _Response())
    assert runs is not None and runs[0]["name"] == "Daily"
    assert "html_url" not in runs[0]
    payload = st.build_payload(
        [], generated_at="2026-11-17T00:00:00+00:00", actions_runs=runs, actions_status="ok"
    )
    assert "github.com" not in json.dumps(payload)


def test_status_page_renders_run_names_as_text() -> None:
    page = (ROOT / "site" / "status.html").read_text(encoding="utf-8")
    assert "html_url" not in page
    assert 'esc(r.name) + " #"' in page


def test_footer_and_about_corrections_are_mailto_links_without_target() -> None:
    config = _text(ROOT / "framework" / "observablehq.config.js")
    about = _text(ROOT / "framework" / "src" / "california" / "about.md")
    authors = _text(ROOT / "framework" / "src" / "california" / "authors.md")
    classic = _text(ROOT / "site" / "index.html")
    assert (
        f'<a href="mailto:{EMAIL}?subject=Atlas%20data%20correction" rel="external">'
        "Report a correction</a>" in config
    )
    assert (
        f'<a href="mailto:{EMAIL}?subject=Atlas%20data%20correction" rel="external">'
        f"email {EMAIL}</a>" in about
    )
    assert '<a id="drawer-issue-link" class="atlas-btn atlas-btn--ghost" href="mailto:' in authors
    # Framework adds target="_blank" to every scheme link unless rel="external" opts it out.
    for name, text in (
        ("observablehq.config.js", config),
        ("about.md", about),
        ("authors.md", authors),
        ("index.html", classic),
    ):
        for anchor in MAILTO_ANCHOR.findall(text):
            assert "target=" not in anchor, f"{name}: mailto link must not open a new tab"
            if name != "index.html":
                assert 'rel="external"' in anchor, f"{name}: mailto link needs rel=external"


def test_methods_point_to_archive_and_licence_names_link_public_texts() -> None:
    about = _text(ROOT / "framework" / "src" / "california" / "about.md")
    classic = _text(ROOT / "site" / "index.html")
    for text in (about, classic):
        assert "https://doi.org/10.5281/zenodo.24124016" in text
        assert "Methods, data files and checksums are in each archived release" in text
        assert "docs/METHODS.md" not in text and "docs/SITE_DATA.md" not in text
    # The classic page has no licence block; only the Framework About page names the licences.
    assert "https://polyformproject.org/licenses/noncommercial/1.0.0" in about
    assert "LICENSE-DATA.md" not in about and "/blob/main/" not in about


def test_profile_correction_mail_link_names_the_expert() -> None:
    node = shutil.which("node")
    assert node, "Node.js is required to exercise experts_model.js"
    module = (ROOT / "framework" / "src" / "components" / "experts_model.js").as_uri()
    script = (
        f'import {{profileCorrectionUrl}} from "{module}";\n'
        'console.log(JSON.stringify([profileCorrectionUrl("Jane Doe", "A5000014168"), '
        'profileCorrectionUrl("", "A1")]));\n'
    )
    result = subprocess.run(
        [node, "--input-type=module", "-e", script],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [
        f"mailto:{EMAIL}?subject=Atlas%20correction%3A%20Jane%20Doe%20(A5000014168)",
        f"mailto:{EMAIL}?subject=Atlas%20correction%3A%20Researcher%20(A1)",
    ]
