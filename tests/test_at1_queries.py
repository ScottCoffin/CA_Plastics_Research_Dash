"""Offline checks for legacy ranking and the explicit AT-1 audit mode."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from atlas.ingest import institutions


class DummyLogger:
    pass


def test_default_mode_preserves_legacy_query_without_v2_dependency(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    seen = []

    def request(url, **kwargs):
        seen.append(url)
        params = parse_qs(urlsplit(url).query)
        assert params["search"] == ["plastic"]
        assert "title_and_abstract.search" not in params["filter"][0]
        return {"group_by": [{"key": "I1", "count": 8}]}, {}

    monkeypatch.setattr(institutions, "_request_json", request)
    production_cache = tmp_path / "production.json"
    assert institutions.plastic_work_counts(
        ["I1", "I1"], production_cache, DummyLogger(), authenticated=False
    ) == {"I1": 8}
    assert len(seen) == 1
    assert json.loads(production_cache.read_text(encoding="utf-8")) == {"I1": 8}
    assert not (tmp_path / "config" / "query_v2.txt").exists()


def test_audit_mode_requires_explicit_paths_and_version(tmp_path):
    with pytest.raises(ValueError, match="requires explicit"):
        institutions.plastic_work_counts(
            ["I1"],
            tmp_path / "production.json",
            DummyLogger(),
            authenticated=False,
            query_mode="audit",
        )


def test_audit_query_and_cache_resolved_alias_is_rejected_without_overwrite(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "folder").mkdir()
    query_file = tmp_path / "query.txt"
    original = b"title_and_abstract.search:(microplastic)\n"
    query_file.write_bytes(original)
    monkeypatch.setattr(
        institutions,
        "_request_json",
        lambda *args, **kwargs: pytest.fail("path collision must fail before a request"),
    )
    with pytest.raises(ValueError, match="resolve to different files"):
        institutions.plastic_work_counts(
            ["I1"],
            tmp_path / "production.json",
            DummyLogger(),
            authenticated=False,
            query_mode="audit",
            query_version="plastic-v2",
            query_path=Path("query.txt"),
            audit_cache_path=Path("folder/../query.txt"),
        )
    assert query_file.read_bytes() == original


def test_audit_filter_is_fully_encoded_and_cache_is_separate(monkeypatch, tmp_path):
    query_path = tmp_path / "query_v2.txt"
    query_text = 'title_and_abstract.search:(microplastic OR "plastic pollution")'
    query_path.write_text(query_text, encoding="utf-8")
    production_cache = tmp_path / "production.json"
    audit_cache = tmp_path / "audit.json"
    calls = []

    def request(url, **kwargs):
        calls.append(url)
        raw_query = urlsplit(url).query
        assert "%28" in raw_query and "%20" in raw_query and "%22" in raw_query
        params = parse_qs(raw_query)
        assert "search" not in params
        filter_value = params["filter"][0]
        assert filter_value.startswith("title_and_abstract.search:(microplastic OR")
        assert "institutions.id:I1|I2" in filter_value
        return {"group_by": [{"key": "https://openalex.org/I1", "count": 7}]}, {}

    monkeypatch.setattr(institutions, "_request_json", request)
    args = {
        "query_mode": "audit",
        "query_version": "plastic-v2",
        "query_path": query_path,
        "audit_cache_path": audit_cache,
    }
    result = institutions.plastic_work_counts(
        ["I1", "I2", "I1"], production_cache, DummyLogger(), authenticated=False, **args
    )
    assert result == {"I1": 7, "I2": 0}
    assert len(calls) == 1
    payload = json.loads(audit_cache.read_text(encoding="utf-8"))
    assert payload == {
        "query_version": "plastic-v2",
        "query": query_text,
        "counts": result,
    }
    assert not production_cache.exists()

    def no_request(*args, **kwargs):
        raise AssertionError("matching complete audit cache should be reused")

    monkeypatch.setattr(institutions, "_request_json", no_request)
    assert (
        institutions.plastic_work_counts(
            ["I1", "I2", "I1"], production_cache, DummyLogger(), authenticated=False, **args
        )
        == result
    )


@pytest.mark.parametrize("bad_count", [True, 3.5, "4", -1])
def test_api_counts_reject_non_integer_or_negative_values(monkeypatch, tmp_path, bad_count):
    monkeypatch.setattr(
        institutions,
        "_request_json",
        lambda *args, **kwargs: ({"group_by": [{"key": "I1", "count": bad_count}]}, {}),
    )
    with pytest.raises(ValueError, match="invalid work count"):
        institutions.plastic_work_counts(
            ["I1"], tmp_path / "production.json", DummyLogger(), authenticated=False
        )


@pytest.mark.parametrize("bad_count", [True, 3.5])
def test_audit_cache_rejects_bool_and_float_counts(monkeypatch, tmp_path, bad_count):
    query_path = tmp_path / "query.txt"
    query_text = "title_and_abstract.search:(microplastic)"
    query_path.write_text(query_text, encoding="utf-8")
    production_cache = tmp_path / "production.json"
    audit_cache = tmp_path / "audit.json"
    audit_cache.write_text(
        json.dumps(
            {
                "query_version": "plastic-v2",
                "query": query_text,
                "counts": {"I1": bad_count},
            }
        ),
        encoding="utf-8",
    )
    seen = []

    def request(url, **kwargs):
        seen.append(url)
        return {"group_by": [{"key": "I1", "count": 4}]}, {}

    monkeypatch.setattr(institutions, "_request_json", request)
    assert institutions.plastic_work_counts(
        ["I1"],
        production_cache,
        DummyLogger(),
        authenticated=False,
        query_mode="audit",
        query_version="plastic-v2",
        query_path=query_path,
        audit_cache_path=audit_cache,
    ) == {"I1": 4}
    assert len(seen) == 1


@pytest.mark.parametrize(
    ("cached_version", "cached_query", "cached_counts"),
    [
        ("old-version", "title_and_abstract.search:(microplastic)", {"I1": 99}),
        ("plastic-v2", "title_and_abstract.search:(nanoplastic)", {"I1": 99}),
        ("plastic-v2", "title_and_abstract.search:(microplastic)", {"I1": 99}),
    ],
)
def test_audit_cache_rejects_mismatch_or_missing_ids(
    monkeypatch, tmp_path, cached_version, cached_query, cached_counts
):
    query_path = tmp_path / "query.txt"
    query_text = "title_and_abstract.search:(microplastic)"
    query_path.write_text(query_text, encoding="utf-8")
    audit_cache = tmp_path / "audit.json"
    audit_cache.write_text(
        json.dumps(
            {
                "query_version": cached_version,
                "query": cached_query,
                "counts": cached_counts,
            }
        ),
        encoding="utf-8",
    )
    seen = []

    def request(url, **kwargs):
        seen.append(url)
        return {"group_by": [{"key": "I2", "count": 4}]}, {}

    monkeypatch.setattr(institutions, "_request_json", request)
    result = institutions.plastic_work_counts(
        ["I1", "I2"],
        tmp_path / "production.json",
        DummyLogger(),
        authenticated=False,
        query_mode="audit",
        query_version="plastic-v2",
        query_path=query_path,
        audit_cache_path=audit_cache,
    )
    assert result == {"I1": 0, "I2": 4}
    assert len(seen) == 1
