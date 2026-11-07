from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from atlas.fulltext import cache as cache_module
from atlas.fulltext.cache import FulltextCacheError, fetch_jats_cached

_XML = (
    b"<article><front><article-meta>"
    b"<article-id pub-id-type='pmc'>PMC12345</article-id>"
    b"<permissions><license><license-p>Creative Commons Attribution 4.0 "
    b"International License (CC BY)</license-p></license></permissions>"
    b"</article-meta></front><body><sec><title>Methods</title>"
    b"<p>Cached evidence.</p></sec></body></article>"
)


def _locator(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "work_id": "W1",
        "source_type": "xml",
        "locator_url": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12345/fullTextXML",
        "pmcid": "PMC12345",
        "license": "cc-by-4.0",
        "license_provenance": "OpenAlex selected PMC copy",
        "license_status": "permissive",
        "processing_allowed": True,
        "storage_decision": "cache_only",
    }
    row.update(overrides)
    return row


def test_cache_fetches_once_then_reuses_hash_and_license_verified_copy(tmp_path: Path) -> None:
    calls: list[str] = []

    def fetcher(url: str, **kwargs: object) -> bytes:
        calls.append(url)
        assert kwargs == {"timeout": 20.0, "max_bytes": 10 * 1024 * 1024}
        return _XML

    locator = _locator()
    path = fetch_jats_cached(
        locator, cache_dir=tmp_path, fetcher=fetcher, minimum_interval=0, now=100
    )
    assert path.read_bytes() == _XML
    manifest = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    assert manifest["content_sha256"] == hashlib.sha256(_XML).hexdigest()
    assert manifest["source_url"] == locator["locator_url"]
    assert manifest["license"] == locator["license"]
    assert manifest["license_provenance"] == locator["license_provenance"]
    assert (
        fetch_jats_cached(locator, cache_dir=tmp_path, fetcher=fetcher, minimum_interval=0, now=101)
        == path
    )
    assert len(calls) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"processing_allowed": False},
        {"license_status": "review"},
        {"storage_decision": "do_not_cache"},
        {"source_type": "pdf"},
        {"locator_url": "https://example.org/PMC12345/fullTextXML"},
    ],
)
def test_cache_refuses_ineligible_or_untrusted_locators(
    tmp_path: Path, changes: dict[str, object]
) -> None:
    def forbidden_fetcher(*_args: object, **_kwargs: object) -> bytes:
        raise AssertionError("ineligible locators must not fetch")

    with pytest.raises(FulltextCacheError):
        fetch_jats_cached(
            _locator(**changes), cache_dir=tmp_path, fetcher=forbidden_fetcher, minimum_interval=0
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "payload",
    [
        _XML.replace(b"PMC12345", b"PMC54321"),
        _XML.replace(
            b"Creative Commons Attribution 4.0 International License (CC BY)",
            b"All rights reserved",
        ),
        _XML.replace(b"CC BY)", b"CC BY-NC-ND)"),
    ],
)
def test_cache_never_persists_wrong_id_or_unconfirmed_license(
    tmp_path: Path, payload: bytes
) -> None:
    with pytest.raises(FulltextCacheError):
        fetch_jats_cached(
            _locator(),
            cache_dir=tmp_path,
            fetcher=lambda *_args, **_kwargs: payload,
            minimum_interval=0,
        )
    assert list(tmp_path.iterdir()) == []


def test_cache_rejects_internal_subset_hidden_by_comment_cdata_tokens(tmp_path: Path) -> None:
    attack = b"<!-- <![CDATA[ --><!DOCTYPE article [<!ENTITY x 'EXPANDED'>]><!-- ]]> -->"
    payload = attack + _XML.replace(b"Cached evidence.", b"&x;")
    with pytest.raises(FulltextCacheError, match="internal DTD subsets are not accepted"):
        fetch_jats_cached(
            _locator(),
            cache_dir=tmp_path,
            fetcher=lambda *_args, **_kwargs: payload,
            minimum_interval=0,
        )
    assert list(tmp_path.iterdir()) == []


def test_cache_hash_mismatch_forces_a_fresh_fetch(tmp_path: Path) -> None:
    calls = 0

    def fetcher(_url: str, **_kwargs: object) -> bytes:
        nonlocal calls
        calls += 1
        return _XML

    path = fetch_jats_cached(
        _locator(), cache_dir=tmp_path, fetcher=fetcher, minimum_interval=0, now=100
    )
    path.write_bytes(_XML + b" ")
    fetch_jats_cached(_locator(), cache_dir=tmp_path, fetcher=fetcher, minimum_interval=0, now=101)
    assert calls == 2
    assert path.read_bytes() == _XML


def test_cache_license_sidecar_must_match_license_evidence_in_xml(tmp_path: Path) -> None:
    calls = 0

    def fetcher(_url: str, **_kwargs: object) -> bytes:
        nonlocal calls
        calls += 1
        return _XML

    path = fetch_jats_cached(
        _locator(), cache_dir=tmp_path, fetcher=fetcher, minimum_interval=0, now=100
    )
    sidecar = path.with_suffix(".json")
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    metadata["selected_copy_license_blocks"] = ["forged CC BY evidence"]
    sidecar.write_text(json.dumps(metadata), encoding="utf-8")
    fetch_jats_cached(_locator(), cache_dir=tmp_path, fetcher=fetcher, minimum_interval=0, now=101)
    assert calls == 2
    updated = json.loads(sidecar.read_text(encoding="utf-8"))
    assert updated["selected_copy_license_blocks"] == [
        "Creative Commons Attribution 4.0 International License (CC BY)"
    ]


@pytest.mark.parametrize(
    "fetched_at",
    [float("nan"), float("inf"), float("-inf"), 103.0],
    ids=["nan", "positive-infinity", "negative-infinity", "future"],
)
def test_cache_rejects_nonfinite_or_future_timestamps(tmp_path: Path, fetched_at: float) -> None:
    calls = 0

    def fetcher(_url: str, **_kwargs: object) -> bytes:
        nonlocal calls
        calls += 1
        return _XML

    path = fetch_jats_cached(
        _locator(), cache_dir=tmp_path, fetcher=fetcher, minimum_interval=0, now=100
    )
    sidecar = path.with_suffix(".json")
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    metadata["fetched_at_epoch"] = fetched_at
    sidecar.write_text(json.dumps(metadata), encoding="utf-8")
    fetch_jats_cached(_locator(), cache_dir=tmp_path, fetcher=fetcher, minimum_interval=0, now=102)
    assert calls == 2


@pytest.mark.parametrize("now", [float("nan"), float("inf"), float("-inf")])
def test_cache_rejects_nonfinite_current_timestamp(tmp_path: Path, now: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        fetch_jats_cached(
            _locator(),
            cache_dir=tmp_path,
            fetcher=lambda *_args, **_kwargs: _XML,
            minimum_interval=0,
            now=now,
        )
    assert list(tmp_path.iterdir()) == []


def test_cache_rejects_nonfinite_age(tmp_path: Path) -> None:
    path = fetch_jats_cached(
        _locator(),
        cache_dir=tmp_path,
        fetcher=lambda *_args, **_kwargs: _XML,
        minimum_interval=0,
        now=100,
    )
    sidecar = path.with_suffix(".json")
    metadata = json.loads(sidecar.read_text(encoding="utf-8"))
    metadata["fetched_at_epoch"] = -1e308
    sidecar.write_text(json.dumps(metadata), encoding="utf-8")
    assert not cache_module._valid_cache(
        path,
        sidecar,
        work_id="W1",
        pmcid="PMC12345",
        license_label="cc-by-4.0",
        license_provenance="OpenAlex selected PMC copy",
        source=_locator()["locator_url"],
        now=1e308,
        max_age_days=30,
    )


def test_http_fetch_rejects_redirect_without_contacting_destination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12345/fullTextXML"
    destination = "https://attacker.example/fullTextXML"
    requested: list[str] = []
    destination_call = Mock()

    class MockOpener:
        def __init__(self, handler: object) -> None:
            self.handler = handler

        def open(self, request: Request, *, timeout: float) -> object:
            requested.append(request.full_url)
            redirected = self.handler.redirect_request(
                request, None, 302, "Found", {"Location": destination}, destination
            )
            if redirected is not None:
                destination_call(redirected)
            raise HTTPError(request.full_url, 302, "redirect blocked", {}, None)

    monkeypatch.setattr(cache_module, "build_opener", lambda handler: MockOpener(handler))
    with pytest.raises(FulltextCacheError, match="HTTP 302"):
        cache_module._fetch_http(source, timeout=2, max_bytes=1000)
    assert requested == [source]
    destination_call.assert_not_called()


def test_cache_confirms_license_uri_from_jats_license_attribute(tmp_path: Path) -> None:
    payload = _XML.replace(
        b"<license>",
        b'<license xmlns:xlink="http://www.w3.org/1999/xlink" '
        b'xlink:href="https://creativecommons.org/licenses/by/4.0/">',
    ).replace(b"Creative Commons Attribution 4.0 International License (CC BY)", b"")
    path = fetch_jats_cached(
        _locator(),
        cache_dir=tmp_path,
        fetcher=lambda *_args, **_kwargs: payload,
        minimum_interval=0,
    )
    assert path.read_bytes() == payload


def test_cache_expiration_forces_a_fresh_fetch(tmp_path: Path) -> None:
    calls = 0

    def fetcher(_url: str, **_kwargs: object) -> bytes:
        nonlocal calls
        calls += 1
        return _XML

    fetch_jats_cached(_locator(), cache_dir=tmp_path, fetcher=fetcher, minimum_interval=0, now=100)
    fetch_jats_cached(
        _locator(),
        cache_dir=tmp_path,
        fetcher=fetcher,
        minimum_interval=0,
        now=100 + 31 * 86400,
    )
    assert calls == 2
