"""Revisit triggers for the deferred Observable Framework migration (AT-5/AT-6)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _module():
    spec = importlib.util.spec_from_file_location(
        "check_framework_triggers", ROOT / "scripts" / "check_framework_triggers.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


BASE = {
    "works": 1424,
    "initial_gzip_bytes": 464_531,
    "a2_visual_tasks_done": [],
    "em5_started": False,
    "index_html_bytes": 170_000,
    "pages": ["index.html", "sem.html", "grants.html", "status.html"],
}


def test_quiet_today_and_each_trigger_fires() -> None:
    m = _module()
    assert m.fired(BASE) == []
    assert m.fired({**BASE, "works": 10_001})[0].startswith("T1")
    assert m.fired({**BASE, "initial_gzip_bytes": 1_500_001})[0].startswith("T2")
    assert m.fired({**BASE, "a2_visual_tasks_done": ["EM-8"]})[0].startswith("T3")
    assert m.fired({**BASE, "em5_started": True})[0].startswith("T3")
    assert m.fired({**BASE, "pages": ["a.html"] * 7})[0].startswith("T4")


def test_measures_committed_site() -> None:
    m = _module()
    measured = m.measure()
    assert measured["works"] > 0 and measured["initial_gzip_bytes"] > 0
    assert m.main([]) == 0
