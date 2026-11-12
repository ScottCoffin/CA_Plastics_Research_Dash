"""AT-5 Framework shell: static guardrails and the local preview layout (no Node needed)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_static_guardrails_pass() -> None:
    check = _load("check_at5")
    assert check.static_problems() == []


def test_nav_covers_the_classic_tabs() -> None:
    check = _load("check_at5")
    assert {"experts", "institutions", "monitoring", "funding", "about"} <= set(
        check.config_pages()
    )


def test_build_report_flags_external_hosts_and_root_paths(tmp_path: Path) -> None:
    check = _load("check_at5")
    for page in ["index", *check.config_pages()]:
        (tmp_path / f"{page}.html").write_text("<main>ok</main>", encoding="utf-8")
    (tmp_path / "about.html").write_text(
        '<link rel="stylesheet" href="https://fonts.googleapis.com/x">'
        '<script src="/_observablehq/client.js"></script>',
        encoding="utf-8",
    )
    problems, payloads = check.build_report(tmp_path)
    assert any("fonts.googleapis.com" in p for p in problems)
    assert any("root-absolute" in p for p in problems)
    assert set(payloads) == {"index", *check.config_pages()}


def test_preview_maps_app_to_dist_and_rest_to_site(tmp_path: Path) -> None:
    preview = _load("serve_framework_preview")
    site, dist = tmp_path / "site", tmp_path / "dist"
    (site / "data").mkdir(parents=True)
    dist.mkdir()
    (site / "index.html").write_text("classic", encoding="utf-8")
    (site / "data" / "x.json").write_text("{}", encoding="utf-8")
    (dist / "index.html").write_text("app", encoding="utf-8")
    (dist / "funding.html").write_text("funding", encoding="utf-8")
    p = preview.PREFIX
    assert preview.resolve(f"{p}/", site, dist) == (site / "index.html").resolve()
    assert preview.resolve(f"{p}/data/x.json", site, dist) == (site / "data" / "x.json").resolve()
    assert preview.resolve(f"{p}/app/", site, dist) == (dist / "index.html").resolve()
    assert preview.resolve(f"{p}/app/funding", site, dist) == (dist / "funding.html").resolve()
    assert preview.resolve(f"{p}/../secret", site, dist) is None
    assert preview.resolve("/elsewhere", site, dist) is None
