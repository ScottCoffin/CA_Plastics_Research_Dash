"""S2.6: look up OpenAlex author IDs for null-ID ORCIDs (offline; _request_json is stubbed)."""

from __future__ import annotations

import csv
import importlib.util
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from atlas.ingest.openalex import OPENALEX_BASE, OpenAlexRateLimitError
from atlas.util.budget import OpenAlexBudget

ROOT = Path(__file__).resolve().parents[1]
HEADER = ["orcid", "author_id", "display_name", "fetched_at"]
WAGNER_ORCID = "0000-0003-4337-622X"
KNOWN_ORCID = "0000-0001-0000-0003"  # already in the CSV, with an author ID
PENDING_A = "0000-0001-0000-0002"
PENDING_B = "0000-0001-0000-0004"
NOT_FOUND_MESSAGE = "OpenAlex returned HTTP 404: Author not found"


def _module():
    spec = importlib.util.spec_from_file_location(
        "fetch_orcid_author_ids", ROOT / "scripts" / "fetch_orcid_author_ids.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _authorship(author_id: str | None, name: str, orcid: str | None = None) -> dict[str, Any]:
    return {
        "author": {
            "id": f"https://openalex.org/{author_id}" if author_id else None,
            "display_name": name,
            "orcid": f"https://orcid.org/{orcid}" if orcid else None,
        },
        "institutions": [],
    }


def _raw(tmp_path: Path) -> Path:
    works = {
        "W1": [_authorship("A5072641519", "Jeff Wagner", WAGNER_ORCID)],
        # Null ID, but the raw works already map this ORCID to one ID: not fetched.
        "W2": [_authorship(None, "Jeff Wagner", WAGNER_ORCID)],
        "W3": [_authorship(None, "Pending A", PENDING_A)],
        # Null ID, ORCID already in the CSV: not fetched.
        "W4": [_authorship(None, "Known B", KNOWN_ORCID)],
        "W5": [_authorship(None, "Pending B", PENDING_B)],
        # Authorship has an ID, so it is not a null-ID authorship.
        "W6": [_authorship("A9000000020", "Has Id", "0000-0001-0000-0005")],
        "W7": [_authorship(None, "No Orcid")],
        "W8": [_authorship(None, "Bad Orcid", "not-an-orcid")],
    }
    path = tmp_path / "works_raw.parquet"
    rows = [
        {"raw_json": json.dumps({"id": f"https://openalex.org/{wid}", "authorships": auths})}
        for wid, auths in works.items()
    ]
    pq.write_table(pa.Table.from_pylist(rows), path)
    return path


def _output(tmp_path: Path, rows: list[dict[str, str]] | None = None) -> Path:
    path = tmp_path / "orcid_author_ids.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows or [])
    return path


def _known_row() -> dict[str, str]:
    return {
        "orcid": KNOWN_ORCID,
        "author_id": "A9000000030",
        "display_name": "Known B",
        "fetched_at": "2026-11-10T00:00:00+00:00",
    }


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _unlimited_budget():
    return OpenAlexBudget(
        max_cost_usd=None,
        max_credits=None,
        cost_per_credit_usd=Decimal("0.0001"),
        reserve_cost_usd=Decimal(0),
        reserve_credits=Decimal(0),
    )


class _Reservations:
    """Budget stand-in that allows a fixed number of requests, then reports a stop."""

    cost_per_credit_usd = Decimal("0.0001")

    def __init__(self, allowed: int) -> None:
        self.left = allowed

    def reserve_error(self, *, cost_usd: Decimal, credits: Decimal) -> str | None:
        if self.left <= 0:
            return "OpenAlex credit limit lacks reserve for the next planned request"
        self.left -= 1
        return None


def _args(tmp_path: Path, output: Path, *extra: str) -> list[str]:
    return [
        "--raw",
        str(_raw(tmp_path)),
        "--output",
        str(output),
        "--usage-log",
        str(tmp_path / "usage.jsonl"),
        *extra,
    ]


def _forbid(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("no network call or key read is allowed here")


def test_dry_run_lists_only_unknown_null_id_orcids(tmp_path, monkeypatch, capsys) -> None:
    module = _module()
    monkeypatch.setattr(module, "_request_json", _forbid)
    monkeypatch.setattr(module, "load_openalex_key", _forbid)
    output = _output(tmp_path, [_known_row()])
    before = output.read_bytes()
    assert module.main(_args(tmp_path, output, "--dry-run")) == 0
    assert capsys.readouterr().out.split() == [PENDING_A, PENDING_B]
    assert output.read_bytes() == before


def test_lookups_write_found_and_not_found_rows_then_skip_them(tmp_path, monkeypatch) -> None:
    module = _module()
    calls: list[str] = []

    def fake(url: str, *, logger: object, **_kwargs: object) -> dict[str, Any]:
        calls.append(url)
        if url.endswith(PENDING_A):
            return {
                "id": "https://openalex.org/A8888888881",
                "display_name": "Pending A, Jr",
                "orcid": f"https://orcid.org/{PENDING_A}",
            }
        raise RuntimeError(NOT_FOUND_MESSAGE)

    monkeypatch.setattr(module, "_request_json", fake)
    monkeypatch.setattr(module, "load_openalex_key", lambda: None)
    monkeypatch.setattr(module, "resolve_openalex_budget", lambda **_kw: _unlimited_budget())
    output = _output(tmp_path, [_known_row()])
    assert module.main(_args(tmp_path, output)) == 0
    assert calls == [
        f"{OPENALEX_BASE}/authors/orcid:{PENDING_A}",
        f"{OPENALEX_BASE}/authors/orcid:{PENDING_B}",
    ]
    rows = _read(output)
    assert [row["orcid"] for row in rows] == [PENDING_A, KNOWN_ORCID, PENDING_B]
    assert rows[0]["author_id"] == "A8888888881"
    assert rows[0]["display_name"] == "Pending A, Jr"
    assert rows[1] == _known_row()
    assert rows[2]["author_id"] == "" and rows[2]["display_name"] == ""
    for row in rows:
        stamp = datetime.fromisoformat(row["fetched_at"])
        assert stamp.utcoffset() == timedelta(0) and stamp.tzinfo is not None
    assert b"\r" not in output.read_bytes()

    calls.clear()
    assert module.main(_args(tmp_path, output)) == 0
    assert calls == []


def test_limit_caps_the_number_of_lookups(tmp_path, monkeypatch) -> None:
    module = _module()
    calls: list[str] = []

    def fake(url: str, *, logger: object, **_kwargs: object) -> dict[str, Any]:
        calls.append(url)
        raise RuntimeError(NOT_FOUND_MESSAGE)

    monkeypatch.setattr(module, "_request_json", fake)
    monkeypatch.setattr(module, "load_openalex_key", lambda: None)
    monkeypatch.setattr(module, "resolve_openalex_budget", lambda **_kw: _unlimited_budget())
    output = _output(tmp_path)
    assert module.main(_args(tmp_path, output, "--limit", "1")) == 0
    assert calls == [f"{OPENALEX_BASE}/authors/orcid:{PENDING_A}"]
    assert [row["orcid"] for row in _read(output)] == [PENDING_A]


def test_budget_stop_keeps_progress_and_the_next_run_resumes(tmp_path, monkeypatch, capsys) -> None:
    module = _module()
    calls: list[str] = []

    def fake(url: str, *, logger: object, **_kwargs: object) -> dict[str, Any]:
        calls.append(url)
        return {"id": f"https://openalex.org/A{len(calls)}", "display_name": "x"}

    monkeypatch.setattr(module, "_request_json", fake)
    monkeypatch.setattr(module, "load_openalex_key", lambda: None)
    output = _output(tmp_path, [_known_row()])
    monkeypatch.setattr(module, "resolve_openalex_budget", lambda **_kw: _Reservations(1))
    assert module.main(_args(tmp_path, output)) == 0
    assert "deferred" in capsys.readouterr().out
    assert [row["orcid"] for row in _read(output)] == [PENDING_A, KNOWN_ORCID]

    monkeypatch.setattr(module, "resolve_openalex_budget", lambda **_kw: _unlimited_budget())
    assert module.main(_args(tmp_path, output)) == 0
    assert [row["orcid"] for row in _read(output)] == [PENDING_A, KNOWN_ORCID, PENDING_B]
    assert len(calls) == 2


def test_rate_limit_stop_keeps_the_rows_already_written(tmp_path, monkeypatch) -> None:
    module = _module()

    def fake(url: str, *, logger: object, **_kwargs: object) -> dict[str, Any]:
        if url.endswith(PENDING_B):
            raise OpenAlexRateLimitError("OpenAlex returned HTTP 429: slow down")
        return {"id": "https://openalex.org/A7777777771", "display_name": "Pending A"}

    monkeypatch.setattr(module, "_request_json", fake)
    monkeypatch.setattr(module, "load_openalex_key", lambda: None)
    monkeypatch.setattr(module, "resolve_openalex_budget", lambda **_kw: _unlimited_budget())
    output = _output(tmp_path, [_known_row()])
    assert module.main(_args(tmp_path, output)) == 0
    rows = _read(output)
    assert [(row["orcid"], row["author_id"]) for row in rows] == [
        (PENDING_A, "A7777777771"),
        (KNOWN_ORCID, "A9000000030"),
    ]


def test_a_record_for_another_orcid_is_not_attached(tmp_path) -> None:
    module = _module()
    body = {"id": "https://openalex.org/A1", "orcid": "https://orcid.org/0000-0009-0000-0000"}
    row = module.author_row(body, PENDING_A, "2026-11-15T00:00:00+00:00")
    assert row["author_id"] == ""
    assert module.author_row(None, PENDING_A, "t")["author_id"] == ""


def test_missing_raw_file_fails_without_a_lookup(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "_request_json", _forbid)
    output = _output(tmp_path)
    args = ["--raw", str(tmp_path / "absent.parquet"), "--output", str(output)]
    assert module.main(args) == 1
