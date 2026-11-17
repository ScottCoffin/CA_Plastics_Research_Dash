"""NOTIFY-AB: one ntfy alert after the daily refresh adds new California plastics papers."""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.error
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "notify_ntfy.py"
CONFIG = ROOT / "config" / "notifications.yml"
WORKFLOW = ROOT / ".github" / "workflows" / "ingest_works.yml"


def _load_script():
    spec = importlib.util.spec_from_file_location("notify_ntfy", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # dataclasses look the module up in sys.modules while the file executes.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


notify = _load_script()


def _row(work_id: str, *, title: str | None = None, year: int = 2025, plastic: Any = True) -> dict:
    return {
        "work_id": work_id,
        "title": f"Paper {work_id}" if title is None else title,
        "year": year,
        "plastic_related": plastic,
    }


class _Response:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


class FakeOpener:
    """Records each request instead of calling the network; raises ``error`` when given."""

    def __init__(self, *, error: BaseException | None = None, status: int = 200) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error = error
        self.status = status

    def __call__(self, request, timeout):
        self.calls.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "title": request.get_header("Title"),
                "click": request.get_header("Click"),
                "tags": request.get_header("Tags"),
                "body": request.data.decode("utf-8"),
                "timeout": timeout,
            }
        )
        if self.error is not None:
            raise self.error
        return _Response(self.status)


def _write_run(tmp_path: Path, previous: list[dict], current: list[dict]) -> tuple[Path, Path]:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(json.dumps({"schema_version": "s3.1", "works": previous}), encoding="utf-8")
    after.write_text(json.dumps({"schema_version": "s3.1", "works": current}), encoding="utf-8")
    return before, after


def test_only_plastic_works_absent_from_the_previous_file_are_new() -> None:
    previous = [_row("W1"), _row("W2", plastic=False)]
    current = [
        _row("W1"),
        _row("W2"),  # re-labelled plastic, but already published: not new
        _row("W3"),
        _row("W4", plastic=False),
        _row("W5", plastic=None),  # unreviewed label: not counted
        {"title": "no work id", "plastic_related": True},
    ]

    fresh = notify.new_plastic_works(current, previous)

    assert [row["work_id"] for row in fresh] == ["W3"]


def test_new_works_list_newest_year_first_then_by_title() -> None:
    current = [
        _row("W1", title="Beta", year=2024),
        _row("W2", title="alpha", year=2024),
        _row("W3", title="Gamma", year=2026),
    ]

    fresh = notify.new_plastic_works(current, [])

    assert [row["work_id"] for row in fresh] == ["W3", "W2", "W1"]


def test_message_counts_titles_and_truncates_to_ninety_characters() -> None:
    works = [_row(f"W{i}") for i in range(7)]

    title, body = notify.build_message(works, 5)

    assert title == "7 new California plastics papers"
    lines = body.splitlines()
    assert len(lines) == 6
    assert lines[0] == "- Paper W0"
    assert lines[-1] == "and 2 more"

    assert notify.build_message(works[:1], 5)[0] == "1 new California plastics paper"
    assert "more" not in notify.build_message(works[:5], 5)[1]

    long_title = "word " * 60
    _, body = notify.build_message([_row("W1", title=long_title)], 5)
    line = body.splitlines()[0]
    assert line.startswith("- ")
    assert len(line) - len("- ") <= 90
    assert line.endswith("…")


def test_dry_run_prints_the_request_and_sends_nothing(tmp_path: Path, capsys) -> None:
    before, after = _write_run(tmp_path, [_row("W1")], [_row("W1"), _row("W2", title="New one")])
    opener = FakeOpener()

    code = notify.main(
        ["--previous", str(before), "--current", str(after), "--dry-run"], opener=opener
    )

    out = capsys.readouterr().out
    assert code == 0
    assert opener.calls == []
    assert "POST https://ntfy.sh/plastiverse-california" in out
    assert "Title: 1 new California plastics paper" in out
    assert "Click: https://plastiverse.live/evidence#ev-recent" in out
    assert "Tags: microscope" in out
    assert "- New one" in out


def test_send_posts_one_message_with_click_and_tags(tmp_path: Path, capsys) -> None:
    before, after = _write_run(tmp_path, [], [_row("W1"), _row("W2"), _row("W3")])
    opener = FakeOpener()

    code = notify.main(["--previous", str(before), "--current", str(after)], opener=opener)

    assert code == 0
    assert len(opener.calls) == 1
    call = opener.calls[0]
    assert call["method"] == "POST"
    assert call["url"] == "https://ntfy.sh/plastiverse-california"
    assert call["title"] == "3 new California plastics papers"
    assert call["title"].isascii()
    assert call["click"] == "https://plastiverse.live/evidence#ev-recent"
    assert call["tags"] == "microscope"
    assert call["body"] == "- Paper W1\n- Paper W2\n- Paper W3"
    assert call["timeout"] == notify.TIMEOUT_SECONDS
    assert "Sent ntfy alert: 3 new California plastics papers" in capsys.readouterr().out


def test_no_new_works_posts_nothing(tmp_path: Path, capsys) -> None:
    rows = [_row("W1"), _row("W2", plastic=False)]
    before, after = _write_run(tmp_path, rows, rows)
    opener = FakeOpener()

    assert notify.main(["--previous", str(before), "--current", str(after)], opener=opener) == 0

    assert opener.calls == []
    assert "No new California plastics papers" in capsys.readouterr().out


@pytest.mark.parametrize(
    "error, status",
    [
        (urllib.error.URLError("offline"), None),
        (TimeoutError("timed out"), None),
        (None, 500),
    ],
)
def test_network_failure_is_a_warning_and_exit_zero(tmp_path: Path, capsys, error, status) -> None:
    before, after = _write_run(tmp_path, [], [_row("W1")])
    opener = FakeOpener(error=error, status=status or 200)

    code = notify.main(["--previous", str(before), "--current", str(after)], opener=opener)

    err = capsys.readouterr().err
    assert code == 0
    assert len(opener.calls) == 1
    assert "WARNING: ntfy alert not sent" in err


def test_missing_or_corrupt_inputs_warn_and_exit_zero(tmp_path: Path, capsys) -> None:
    _, after = _write_run(tmp_path, [], [_row("W1")])
    opener = FakeOpener()

    missing = tmp_path / "absent.json"
    assert notify.main(["--previous", str(missing), "--current", str(after)], opener=opener) == 0

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")
    assert notify.main(["--previous", str(corrupt), "--current", str(after)], opener=opener) == 0

    assert opener.calls == []
    assert "previous works file unreadable" in capsys.readouterr().err


def test_config_names_the_public_topic_and_limits() -> None:
    settings = notify.load_settings(CONFIG)

    assert settings == notify.Settings(
        topic="plastiverse-california", server="https://ntfy.sh", max_titles=5
    )


def test_config_rejects_unsafe_topic_server_and_limit(tmp_path: Path) -> None:
    def write(block: str) -> Path:
        path = tmp_path / "notifications.yml"
        path.write_text(f"ntfy:\n{block}", encoding="utf-8")
        return path

    with pytest.raises(ValueError, match="topic"):
        notify.load_settings(write("  topic: 'has a space'\n  server: https://ntfy.sh\n"))
    with pytest.raises(ValueError, match="https"):
        notify.load_settings(write("  topic: ok\n  server: http://example.test\n"))
    with pytest.raises(ValueError, match="max_titles"):
        notify.load_settings(write("  topic: ok\n  max_titles: 0\n"))


def test_workflow_alerts_only_after_the_data_commit_and_never_blocks() -> None:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["ingest"]["steps"]
    names = [step.get("name", "") for step in steps]
    commit = names.index("Commit generated outputs")
    alert = next(i for i, name in enumerate(names) if name.startswith("Notify new California"))

    assert alert == commit + 1
    step = steps[alert]
    assert step["continue-on-error"] is True
    assert "steps.refresh.outputs.status == 'success'" in step["if"]
    assert "vars.ENABLE_DATA_COMMITS == 'true'" in step["if"]
    assert "scripts/notify_ntfy.py --previous" in step["run"]
    assert "${{ github.sha }}" in step["env"]["RUN_SHA"]
