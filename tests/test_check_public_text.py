"""Public-text guard: internal project vocabulary must not appear in visible page text."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "check_public_text", ROOT / "scripts" / "check_public_text.py"
)
assert _SPEC and _SPEC.loader
check_public_text = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_public_text)
main = check_public_text.main


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_seeded_internal_task_id_fails(tmp_path: Path) -> None:
    page = _write(tmp_path, "bad.html", "<html><body><p>Coming with EM-8.</p></body></html>")
    assert main([str(page)]) == 1


@pytest.mark.parametrize(
    "body",
    [
        "<html><body><!-- Coming with EM-8 --><p>Visible.</p></body></html>",
        "<html><body><script>var note = 'Coming with EM-8';</script></body></html>",
        "<html><head><style>/* EM-14 */ p { color: red; }</style></head><body></body></html>",
    ],
)
def test_comments_script_and_style_are_not_public_text(tmp_path: Path, body: str) -> None:
    page = _write(tmp_path, "hidden.html", body)
    assert main([str(page)]) == 0


def test_clean_sample_passes(tmp_path: Path) -> None:
    page = _write(
        tmp_path,
        "clean.html",
        "<html><body><p>In development.</p>"
        "<p>Example data loaded: sample data, not a current refresh.</p></body></html>",
    )
    assert main([str(page)]) == 0


@pytest.mark.parametrize(
    "phrase",
    [
        "from the same S3.1 export used by the Experts view",
        "(uploaded document; no URL)",
        "the mapping awaits owner review",
        "Definition pending owner review.",
        "TODO-OWNER: confirm each gloss",
        "Fixture snapshot loaded",
        "the plastic-v2-candidate query",
    ],
)
def test_each_forbidden_phrase_fails(tmp_path: Path, phrase: str) -> None:
    page = _write(tmp_path, "phrase.html", f"<html><body><p>{phrase}</p></body></html>")
    assert main([str(page)]) == 1


def test_json_string_values_are_checked(tmp_path: Path) -> None:
    data = {"entries": [{"source_label": "Plan (uploaded document; no URL)", "id": "dtsc-08"}]}
    bad = _write(tmp_path, "bad.json", json.dumps(data))
    assert main([str(bad)]) == 1
    clean = _write(tmp_path, "clean.json", json.dumps({"note": "Source document, not online."}))
    assert main([str(clean)]) == 0


def test_allow_glob_skips_matching_file(tmp_path: Path) -> None:
    page = _write(tmp_path, "draft_page.html", "<p>Coming with EM-8</p>")
    assert main([str(page), "--allow", "draft_*.html"]) == 0


def test_real_public_sources_pass() -> None:
    paths = [
        "site/index.html",
        "site/expert.html",
        "site/grants.html",
        "site/data/dtsc_timeline.json",
        "site/data/linkouts.json",
    ]
    assert main(paths) == 0
