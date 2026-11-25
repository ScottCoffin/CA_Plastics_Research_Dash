"""VD-34: journal metrics script (scripts/fetch_journal_metrics.py); live calls are stubbed."""

from __future__ import annotations

import copy
import importlib.util
import json
import urllib.parse
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fetch_journal_metrics.py"
OUTPUT = ROOT / "site" / "data" / "california" / "journal_metrics.json"


def _load_script():
    spec = importlib.util.spec_from_file_location("fetch_journal_metrics", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


fjm = _load_script()

GENERATED = "2026-11-17T00:00:00+00:00"


def _sources() -> dict:
    return {
        "S1": {
            "display_name": "Journal A",
            "issn_l": "1111-1111",
            "type": "journal",
            "summary_stats": {"2yr_mean_citedness": 4.25, "h_index": 30},
        },
        "S2": {
            "display_name": "Repository of B",
            "issn_l": None,
            "type": "repository",
            "summary_stats": {"2yr_mean_citedness": 9.0, "h_index": 5},
        },
        "S3": {
            "display_name": "Journal D",
            "issn_l": "3333-3333",
            "type": "journal",
            "summary_stats": {"2yr_mean_citedness": None, "h_index": None},
        },
        "S4": {
            "display_name": "journal d ",
            "issn_l": "4444-4444",
            "type": "journal",
            "summary_stats": {"2yr_mean_citedness": 1.0, "h_index": 2},
        },
    }


def _works() -> dict[str, str]:
    return {
        "W1": "Journal A",
        "W2": "Journal A",
        "W3": "Journal B",
        "W4": "Journal C",
        "W5": "",
        "W6": "Journal D",
        "W7": "Journal D",
        "W8": "Journal D",
    }


def _primary() -> dict[str, str | None]:
    return {
        "W1": "S1",
        "W2": "S1",
        "W3": "S2",
        "W4": None,
        "W5": "S1",
        "W6": "S3",
        "W7": "S4",
        "W8": "S4",
    }


def _by_name(payload: dict) -> dict:
    """The journals list keyed by name, for reading."""
    return {
        item["name"]: {k: v for k, v in item.items() if k != "name"} for item in payload["journals"]
    }


def _entry(payload: dict, name: str) -> dict:
    """The journals list item for name, for editing in place."""
    return next(item for item in payload["journals"] if item["name"] == name)


def _payload() -> dict:
    return fjm.build_payload(_works(), _primary(), _sources(), generated_at=GENERATED)


def test_request_urls_batch_ids_and_select_only_needed_fields() -> None:
    works = fjm.works_url(["W1", "W2"])
    sources = fjm.sources_url(["S1", "S2"])
    works_query = urllib.parse.parse_qs(urllib.parse.urlsplit(works).query)
    sources_query = urllib.parse.parse_qs(urllib.parse.urlsplit(sources).query)
    assert works.startswith("https://api.openalex.org/works?")
    assert works_query["filter"] == ["openalex:W1|W2"]
    assert works_query["select"] == ["id,primary_location"]
    assert works_query["per-page"] == ["100"]
    assert sources.startswith("https://api.openalex.org/sources?")
    assert sources_query["filter"] == ["openalex:S1|S2"]
    assert sources_query["select"] == ["id,display_name,issn_l,summary_stats,type"]


def test_batches_never_exceed_one_hundred_ids() -> None:
    ids = [f"W{i}" for i in range(1915)]
    batches = fjm._batches(ids)
    assert len(batches) == 20
    assert max(len(batch) for batch in batches) == 100
    assert [item for batch in batches for item in batch] == ids


def test_build_joins_by_display_name_and_takes_the_majority_source() -> None:
    payload = _payload()
    journals = _by_name(payload)
    assert set(journals) == {"Journal A", "Journal B", "Journal D"}
    assert journals["Journal A"] == {
        "source_id": "S1",
        "issn_l": "1111-1111",
        "two_yr_mean_citedness": 4.25,
        "h_index": 30,
        "type": "journal",
    }
    # Journal D's works sit in S3 (one) and S4 (two): S4 wins, and its name matches once trimmed
    # and case-folded, so it is not a mismatch.
    assert journals["Journal D"]["source_id"] == "S4"
    assert journals["Journal D"]["two_yr_mean_citedness"] == 1.0
    assert payload["ambiguous_journals"] == [
        {"journal": "Journal D", "source_id": "S4", "other_source_ids": ["S3"]}
    ]


def test_mismatched_venue_keeps_its_id_but_withholds_metrics() -> None:
    payload = _payload()
    entry = _by_name(payload)["Journal B"]
    assert entry == {
        "source_id": "S2",
        "issn_l": None,
        "two_yr_mean_citedness": None,
        "h_index": None,
        "type": None,
    }
    assert payload["name_mismatches"] == [
        {"journal": "Journal B", "openalex_display_name": "Repository of B", "source_id": "S2"}
    ]


def test_unresolved_names_are_listed_and_counted() -> None:
    payload = _payload()
    assert payload["unmatched_journals"] == ["Journal C"]
    assert payload["coverage"] == {
        "works": 8,
        "works_with_source": 7,
        "journals": 4,
        "journals_with_source": 3,
        "journals_with_metric": 2,
    }
    assert fjm.check_payload(payload, {"Journal A", "Journal B", "Journal C", "Journal D"}) == []


def test_check_rejects_bad_values_and_notes_new_journals() -> None:
    names = {"Journal A", "Journal B", "Journal C", "Journal D"}
    good = _payload()

    def problems(mutate) -> list[str]:
        payload = copy.deepcopy(good)
        mutate(payload)
        return fjm.check_payload(payload, names)

    assert any(
        "finite number" in p
        for p in problems(lambda d: _entry(d, "Journal A").update(two_yr_mean_citedness=-1.0))
    )
    assert any(
        "source_id" in p for p in problems(lambda d: _entry(d, "Journal A").update(source_id="X1"))
    )
    assert any("exactly" in p for p in problems(lambda d: _entry(d, "Journal A").pop("type")))
    assert any(
        "withheld" in p
        for p in problems(lambda d: _entry(d, "Journal B").update(two_yr_mean_citedness=9.0))
    )
    # A journal new in the daily export is a note, not an error (it shows no value until the
    # workflow refreshes the file after the export).
    assert fjm.check_payload(good, names | {"Journal Z"}) == []
    assert "1 works_detail journals not yet in the file" in fjm.staleness(
        good, names | {"Journal Z"}
    )
    assert fjm.staleness(good, names) is None
    assert any("schema_version" in p for p in problems(lambda d: d.update(schema_version=2)))
    assert any(
        "coverage" in p for p in problems(lambda d: d["coverage"].update(journals_with_metric=99))
    )


def _write_fixtures(tmp_path: Path, *, with_raw: bool = True) -> dict[str, Path]:
    detail = tmp_path / "works_detail.json"
    detail.write_text(
        json.dumps(
            {
                "schema_version": "x",
                "works": [
                    {"work_id": work_id, "journal": name, "plastic_related": True}
                    for work_id, name in _works().items()
                ],
            }
        ),
        encoding="utf-8",
    )
    raw = tmp_path / "raw.json"
    if with_raw:
        raw.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "fetched_at_utc": GENERATED,
                    "works": _primary(),
                    "sources": _sources(),
                }
            ),
            encoding="utf-8",
        )
    return {"works-detail": detail, "raw": raw, "output": tmp_path / "out.json"}


def test_offline_rebuild_writes_a_valid_file_without_network(tmp_path: Path, monkeypatch) -> None:
    def no_network(*_args, **_kwargs):
        raise AssertionError("offline mode must not call OpenAlex")

    monkeypatch.setattr(fjm, "_request_json", no_network)
    paths = _write_fixtures(tmp_path)
    argv = ["--offline"] + [f"--{name}={path}" for name, path in paths.items()]
    assert fjm.main(argv) == 0
    written = json.loads(paths["output"].read_text(encoding="utf-8"))
    assert _entry(written, "Journal A")["two_yr_mean_citedness"] == 4.25
    assert fjm.check_payload(written, {"Journal A", "Journal B", "Journal C", "Journal D"}) == []
    assert (
        fjm.main(
            ["--check", f"--output={paths['output']}", f"--works-detail={paths['works-detail']}"]
        )
        == 0
    )


def test_offline_without_a_raw_cache_stops_with_status_two(tmp_path: Path) -> None:
    paths = _write_fixtures(tmp_path, with_raw=False)
    argv = ["--offline"] + [f"--{name}={path}" for name, path in paths.items()]
    assert fjm.main(argv) == 2
    assert not paths["output"].exists()


def test_live_run_stops_before_any_request_when_the_cap_is_zero(
    tmp_path: Path, monkeypatch
) -> None:
    def no_network(*_args, **_kwargs):
        raise AssertionError("a zero credit cap must stop before the first request")

    monkeypatch.setattr(fjm, "_request_json", no_network)
    monkeypatch.setattr(fjm, "load_openalex_key", lambda *_args, **_kwargs: None)
    monkeypatch.chdir(ROOT)
    with pytest.raises(fjm.Stop):
        fjm.fetch_live(
            _works(),
            usage_log=tmp_path / "usage.jsonl",
            max_credits=Decimal(0),
            fetched_at=GENERATED,
        )


def test_committed_journal_metrics_file_passes_the_check() -> None:
    assert OUTPUT.exists(), "run scripts/fetch_journal_metrics.py once (live) to create the file"
    assert fjm.main(["--check"]) == 0
    payload = json.loads(OUTPUT.read_text(encoding="utf-8"))
    assert payload["source"] == "OpenAlex sources summary_stats"
    assert payload["schema_version"] == 1
