"""BQ-2.4: site/data/denominators.json builder, --check, ratio rules, schema, text, V-4 helpers."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts" / "build_denominators_json.py"
PUBLIC_JSON = ROOT / "site" / "data" / "denominators.json"
MODEL_JS = ROOT / "framework" / "src" / "components" / "v4_trend_model.js"
PAGE_SOURCES = [
    ROOT / "framework" / "src" / "components" / "v4_trend.js",
    ROOT / "framework" / "src" / "components" / "explore.js",
    ROOT / "framework" / "src" / "california" / "evidence.md",
]


def _load_builder():
    spec = importlib.util.spec_from_file_location("build_denominators_json", BUILDER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


builder = _load_builder()
NOT_SEPARATED = "not separated: the OpenAlex group_by cannot exclude them; included in count"


def _years(
    counts: dict[int, int], partial: set[int] = frozenset(), retracted: bool = True
) -> list[dict[str, Any]]:
    return [
        {
            "year": year,
            "count": count,
            "retracted": 0 if retracted else None,
            "partial_year": year in partial,
        }
        for year, count in sorted(counts.items())
    ]


def make_source() -> dict[str, Any]:
    """A small synthetic denominator_series.v1 input (2019 and 2020 complete, 2021 partial)."""
    all_unit = (
        "OpenAlex records by publication year; exclude_types removed; "
        "duplicates not collapsed; retracted-flagged records included"
    )
    art_unit = (
        "OpenAlex records of type article or review by publication year; "
        "exclude_types removed; duplicates not collapsed; retracted-flagged records included"
    )
    partial = {2021}
    series = {
        "A": {
            "label": "internal label A3 section 5.3",
            "counting_unit": all_unit,
            "scope": "global",
            "source": "data/interim/denominator_series_cache.json",
            "status": "available",
            "sensitivity": "all",
            "comparable_with": ["B", "C"],
            "beside_only": False,
            "retractions": NOT_SEPARATED,
            "undated": 0,
            "years": _years({2019: 100, 2020: 200, 2021: 50}, partial, retracted=False),
        },
        "A-article_review": {
            "counting_unit": art_unit,
            "scope": "global",
            "source": "data/interim/denominator_series_cache.json",
            "status": "available",
            "sensitivity": "article_review",
            "comparable_with": ["B-article_review"],
            "beside_only": False,
            "retractions": NOT_SEPARATED,
            "undated": 0,
            "years": _years({2019: 80, 2020: 150, 2021: 40}, partial, retracted=False),
        },
        "B": {
            "counting_unit": all_unit,
            "scope": "global",
            "source": "data/interim/denominator_series_cache.json",
            "status": "available",
            "sensitivity": "all",
            "comparable_with": ["A"],
            "beside_only": False,
            "retractions": NOT_SEPARATED,
            "undated": 0,
            "years": _years({2019: 30, 2020: 90, 2021: 20}, partial, retracted=False),
        },
        "B-article_review": {
            "counting_unit": art_unit,
            "scope": "global",
            "source": "data/interim/denominator_series_cache.json",
            "status": "available",
            "sensitivity": "article_review",
            "comparable_with": ["A-article_review"],
            "beside_only": False,
            "retractions": NOT_SEPARATED,
            "undated": 0,
            "years": _years({2019: 20, 2020: 60, 2021: 10}, partial, retracted=False),
        },
        "C": {
            "counting_unit": all_unit,
            "scope": "california",
            "source": "data/processed/normalized/works.parquet",
            "status": "available",
            "sensitivity": "all",
            "comparable_with": ["A"],
            "beside_only": False,
            "retractions": "separate column; included in count",
            "undated": 0,
            "route_records": {"query": 10},
            "years": [
                {"year": 2019, "count": 2, "retracted": 0, "partial_year": False, "other_route": 0},
                {"year": 2020, "count": 6, "retracted": 1, "partial_year": False, "other_route": 1},
                {"year": 2021, "count": 1, "retracted": 0, "partial_year": True, "other_route": 0},
            ],
        },
        "D": {
            "counting_unit": "curated published works by publication year; one row per work",
            "scope": "california",
            "source": "site/data/index.json",
            "status": "available",
            "sensitivity": "all",
            "comparable_with": [],
            "beside_only": True,
            "retractions": "separate column; included in count",
            "undated": 0,
            "years": [
                {"year": 2019, "count": 1, "retracted": 0, "partial_year": False},
                {"year": 2020, "count": 3, "retracted": 0, "partial_year": False},
                {"year": 2021, "count": 0, "retracted": 0, "partial_year": True},
            ],
        },
    }
    window = {"requested_start": 2019, "start": 2019, "end": 2020, "base_year": 2019, "years": 2}
    trend = {
        "n_years": 2,
        "zero_years_skipped": [],
        "slope": 0.5,
        "slope_se": 0.0,
        "df": 0,
        "t_crit": None,
        "cagr": 0.6487,
        "ci95": None,
        "note": "two years: no interval",
    }
    metrics = {
        "schema_version": "denominator_series.metrics.v1",
        "as_of": "2026-11-25",
        "window": window,
        "partial_years_excluded": [2021],
        "ci_level": 0.95,
        "method": {"unit": "Counts are OpenAlex records by publication year."},
        "series": {
            sid: {"basis": "test", "beside_only": sid == "D", "years": [], "trend": trend}
            for sid in series
        },
        "shares": {
            name: {
                "numerator": num,
                "denominator": den,
                "basis": "test",
                "years": [],
                "trend": trend,
            }
            for name, (num, den) in {
                "B/A": ("B", "A"),
                "C/A": ("C", "A"),
                "B-article_review/A-article_review": ("B-article_review", "A-article_review"),
            }.items()
        },
    }
    return {
        "schema_version": "denominator_series.v1",
        "as_of": "2026-11-25",
        "last_complete_year": 2020,
        "query_version": "plastic-v3.1",
        "series": series,
        "not_computed": {
            "B2": {"status": "waits_for", "waits_for": "BQ-S3", "counting_unit": "test"}
        },
        "ratio_pairs": [["A", "B"], ["A", "C"], ["A-article_review", "B-article_review"]],
        "metrics": metrics,
        "inputs": {"denominator_cache": {"path": "data/interim/x.json", "sha256": "0"}},
    }


def _write(path: Path, source: dict[str, Any]) -> Path:
    path.write_text(json.dumps(source, indent=2), encoding="utf-8")
    return path


def _build(tmp_path: Path, source: dict[str, Any]) -> tuple[Path, Path]:
    inp = _write(tmp_path / "denominator_series.json", source)
    out = tmp_path / "denominators.json"
    assert builder.main(["--input", str(inp), "--output", str(out)]) == 0
    return inp, out


def test_builder_writes_public_file_from_synthetic_input(tmp_path: Path) -> None:
    _, out = _build(tmp_path, make_source())
    raw = out.read_bytes()
    assert b"\r\n" not in raw and raw.endswith(b"\n")
    payload = json.loads(raw)
    assert payload["schema_version"] == "bq2-v1"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", payload["generated_at"])
    assert payload["version"] == {
        "query_version": "plastic-v3.1",
        "as_of": "2026-11-25",
        "last_complete_year": 2020,
        "window_start": 2019,
        "window_end": 2020,
    }
    assert [row["id"] for row in payload["series"]] == [
        "A",
        "A-article_review",
        "B",
        "B-article_review",
        "C",
        "D",
    ]
    assert payload["not_computed"] == [
        {"id": "B2", "label": builder.NOT_COMPUTED_LABELS["B2"], "status": "not computed"}
    ]
    # Plain labels only: the internal dependency name from the input must not be copied.
    assert "BQ-S3" not in raw.decode("utf-8") and "A3 section" not in raw.decode("utf-8")
    # Stable output: rendering again gives the same bytes.
    assert builder.render(payload) == raw


def test_series_years_keep_partial_flag_and_counts(tmp_path: Path) -> None:
    _, out = _build(tmp_path, make_source())
    payload = json.loads(out.read_text(encoding="utf-8"))
    c = next(row for row in payload["series"] if row["id"] == "C")
    assert c["years"][1] == {"year": 2020, "count": 6, "retracted": 1, "partial_year": False}
    assert c["years"][2]["partial_year"] is True
    assert c["retraction_split"] is True
    a = next(row for row in payload["series"] if row["id"] == "A")
    assert a["retraction_split"] is False
    assert a["years"][0]["retracted"] is None


def test_ratio_pairs_are_only_like_for_like_shares(tmp_path: Path) -> None:
    _, out = _build(tmp_path, make_source())
    payload = json.loads(out.read_text(encoding="utf-8"))
    ids = [row["id"] for row in payload["ratio_pairs"]]
    assert ids == ["B/A", "C/A", "B-article_review/A-article_review"]
    assert set(payload["metrics"]["shares"]) == set(ids)
    for row in payload["ratio_pairs"]:
        assert "D" not in (row["numerator"], row["denominator"])
        assert "B2" not in (row["numerator"], row["denominator"])


def test_builder_refuses_pairs_with_d_or_b2_or_mixed_units() -> None:
    source = make_source()
    with_d = copy.deepcopy(source)
    with_d["ratio_pairs"].append(["A", "D"])
    with pytest.raises(ValueError, match="do not match the allowed pairs"):
        builder.build_payload(with_d, generated_at="2026-11-25T00:00:00Z", input_sha256="0")

    with_b2 = copy.deepcopy(source)
    with_b2["ratio_pairs"].append(["A", "B2"])
    with pytest.raises(ValueError, match="do not match the allowed pairs"):
        builder.build_payload(with_b2, generated_at="2026-11-25T00:00:00Z", input_sha256="0")

    mixed = copy.deepcopy(source)
    mixed["series"]["B"]["sensitivity"] = "article_review"
    with pytest.raises(ValueError, match="mixes counting units or sensitivities"):
        builder.build_payload(mixed, generated_at="2026-11-25T00:00:00Z", input_sha256="0")


def test_builder_rejects_unknown_input_series_and_schema() -> None:
    source = make_source()
    source["series"]["E"] = copy.deepcopy(source["series"]["A"])
    with pytest.raises(ValueError, match="unknown input series"):
        builder.build_payload(source, generated_at="2026-11-25T00:00:00Z", input_sha256="0")
    bad = make_source()
    bad["schema_version"] = "denominator_series.v0"
    with pytest.raises(ValueError, match="schema_version"):
        builder.build_payload(bad, generated_at="2026-11-25T00:00:00Z", input_sha256="0")


def test_check_passes_after_build_and_skips_without_input(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    inp, out = _build(tmp_path, make_source())
    assert builder.main(["--check", "--input", str(inp), "--output", str(out)]) == 0
    inp.unlink()
    assert builder.main(["--check", "--input", str(inp), "--output", str(out)]) == 0
    assert "SKIP" in capsys.readouterr().out


def test_check_reports_stale_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    inp, out = _build(tmp_path, make_source())
    changed = make_source()
    changed["series"]["A"]["years"][0]["count"] = 101
    _write(inp, changed)
    assert builder.main(["--check", "--input", str(inp), "--output", str(out)]) == 1
    assert "STALE" in capsys.readouterr().out


def test_check_rejects_invalid_committed_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    inp, out = _build(tmp_path, make_source())
    payload = json.loads(out.read_text(encoding="utf-8"))
    payload["ratio_pairs"][0]["id"] = "D/A"
    payload["ratio_pairs"][0]["numerator"] = "D"
    out.write_text(json.dumps(payload), encoding="utf-8")
    assert builder.main(["--check", "--input", str(inp), "--output", str(out)]) == 1
    assert "not an allowed pair" in capsys.readouterr().out


def test_check_fails_when_committed_file_is_missing(tmp_path: Path) -> None:
    assert (
        builder.main(
            ["--check", "--output", str(tmp_path / "missing.json"), "--input", str(tmp_path / "x")]
        )
        == 1
    )


def test_committed_public_file_is_valid() -> None:
    payload = json.loads(PUBLIC_JSON.read_text(encoding="utf-8"))
    assert builder.check_payload(payload) == []
    assert set(payload) == {
        "generated_at",
        "metrics",
        "not_computed",
        "ratio_pairs",
        "schema_version",
        "series",
        "source",
        "version",
        "what_this_is_and_is_not",
    }
    assert payload["schema_version"] == "bq2-v1"
    assert payload["what_this_is_and_is_not"]["is_not"]
    for row in payload["series"]:
        assert set(row) == {
            "id",
            "label",
            "counting_unit",
            "sensitivity",
            "beside_only",
            "comparable_with",
            "retraction_split",
            "undated_records",
            "years",
        }
    assert all(row["id"] != "B2" for row in payload["series"])
    d = next(row for row in payload["series"] if row["id"] == "D")
    assert d["beside_only"] is True and d["comparable_with"] == []


def test_check_mode_on_committed_file_exits_zero() -> None:
    assert builder.main(["--check"]) == 0


def test_no_web_of_science_totals_in_public_text() -> None:
    forbidden_numbers = ["18,863", "29,928"]
    wos_total = re.compile(r"Web of Science[^.\n]{0,40}\d", re.IGNORECASE)
    texts = {str(PUBLIC_JSON): PUBLIC_JSON.read_text(encoding="utf-8")}
    for path in PAGE_SOURCES:
        texts[str(path)] = path.read_text(encoding="utf-8")
    for name, text in texts.items():
        for number in forbidden_numbers:
            assert number not in text, f"{number} found in {name}"
        assert not wos_total.search(text), f"Web of Science total in {name}"


def test_public_text_uses_plain_terms() -> None:
    internal = re.compile(r"BQ-\d|EM-\d|\bA3\b|\bexperts?\b", re.IGNORECASE)
    assert not internal.search(PUBLIC_JSON.read_text(encoding="utf-8"))
    assert not internal.search(
        (ROOT / "framework" / "src" / "california" / "evidence.md").read_text(encoding="utf-8")
    )


def test_public_file_is_listed_for_public_text_check() -> None:
    text = (ROOT / "scripts" / "check_public_text.py").read_text(encoding="utf-8")
    assert '"site/data/denominators.json"' in text


RUNTIME_SCRIPT = """
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {
  caShare,
  countsByYear,
  denominatorShare,
  readDenominators
} from "MODEL_URL";

const payload = JSON.parse(readFileSync(process.argv[2], "utf8"));

// readDenominators accepts only the bq2-v1 schema with the A and C series.
assert.equal(readDenominators(payload), payload);
assert.equal(readDenominators({...payload, schema_version: "bq1-v1"}), null);
assert.equal(readDenominators(null), null);
assert.equal(readDenominators({schema_version: "bq2-v1", series: {A: {years: []}}}), null);

// countsByYear leaves out partial years; a missing series gives an empty map.
const aCounts = countsByYear(payload, "A");
assert.equal(aCounts[2019], 100);
assert.equal(aCounts[2021], undefined);
assert.deepEqual(countsByYear(payload, "Z"), {});

// denominatorShare divides C by A, only for complete years, and never uses D.
const cA = denominatorShare(payload, "C", "A");
assert.deepEqual(cA.map((row) => row.year), [2019, 2020]);
assert.equal(cA[0].corpus, 2);
assert.equal(cA[0].global, 100);
assert.equal(cA[0].share, 0.02);
assert.deepEqual(cA, caShare(countsByYear(payload, "C"), countsByYear(payload, "A")));
const bA = denominatorShare(payload, "B", "A");
assert.equal(bA.at(-1).share, 90 / 200);

// The committed file: the latest complete year of C/A and no partial year in the share rows.
const committed = JSON.parse(readFileSync(process.argv[3], "utf8"));
const rows = denominatorShare(committed, "C", "A");
assert.ok(rows.length > 0);
assert.ok(rows.every((row) => row.year <= committed.version.last_complete_year));
assert.equal(rows.at(-1).year, committed.version.last_complete_year);
assert.ok(rows.every((row) => row.global > 0));
console.log("ok", rows.at(-1).year, rows.at(-1).share.toFixed(4));
"""


def test_node_runtime_helpers_for_v4_share(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for the BQ-2.4 runtime test; install Node.js 20 or newer.")
    source = make_source()
    inp = _write(tmp_path / "denominator_series.json", source)
    synthetic = tmp_path / "synthetic_denominators.json"
    assert builder.main(["--input", str(inp), "--output", str(synthetic)]) == 0
    script = tmp_path / "bq24_runtime.mjs"
    script.write_text(RUNTIME_SCRIPT.replace("MODEL_URL", MODEL_JS.as_uri()), encoding="utf-8")
    result = subprocess.run(
        [node, str(script), str(synthetic), str(PUBLIC_JSON)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("ok 2025")
