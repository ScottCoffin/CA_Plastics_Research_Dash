"""Tests for the BFFP roster extractor and build script (Add-on A4, CG-2; T-EXT, T-RAW, T-MAN).

Fixtures only. The fetcher is a fake; no test makes a network request.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from atlas.groups import admission, roster

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures" / "groups"
SAMPLE = FIXTURES / "bffp_members_org_sample.json"
TRUNCATED = FIXTURES / "bffp_members_org_truncated.json"
EXCLUDED_NAMES = ("Zara Quillfeather", "Ilse Morrowind")
AMBIGUOUS_NAME = "Pieter Dunmore"
TODAY = dt.date(2026, 11, 26)
NOW = dt.datetime(2026, 11, 26, 12, 0, tzinfo=dt.UTC)


class FakeFetcher:
    """Returns scripted responses; an Exception instance is raised instead of returned."""

    def __init__(self, *responses: tuple[int, bytes] | Exception) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, url: str, user_agent: str) -> tuple[int, bytes]:
        self.calls.append((url, user_agent))
        item = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(item, Exception):
            raise item
        return item


def _body(rows: list[dict[str, str]]) -> bytes:
    return json.dumps({"error": 0, "data": rows}).encode("utf-8")


def _sample_body() -> bytes:
    return SAMPLE.read_bytes()


def _no_sleep(_: float) -> None:
    return None


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "build_groups_roster", REPO / "scripts" / "build_groups_roster.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build_script = _load_script()


def _paths(base: Path) -> object:
    return build_script.Paths(
        raw_root=base / "raw",
        site_dir=base / "site",
        interim_dir=base / "interim",
        curation_dir=base / "curation",
    )


# ---------------------------------------------------------------------------
# Allow-list and parsing (T-EXT)
# ---------------------------------------------------------------------------


def test_parse_keeps_only_the_allow_list() -> None:
    entries = roster.parse_members_org(_sample_body())
    assert entries, "sample fixture must yield entries"
    for entry in entries:
        assert set(vars(entry)) == {"organization", "country", "website"}
    assert entries[0].country == "Mainland China"


def test_parse_drops_membership_type() -> None:
    body = _body([{"organization": "Example Reef Society", "country": "Norway", "type": "cm"}])
    (entry,) = roster.parse_members_org(body)
    assert not hasattr(entry, "type")
    assert "cm" not in repr(entry)


def test_parse_rejects_error_payload() -> None:
    with pytest.raises(roster.RosterFetchError):
        roster.parse_members_org(b'{"error": 1, "data": []}')


def test_parse_rejects_payload_without_organization_field() -> None:
    body = _body([{"country": "Norway", "website": "example.no"}])
    with pytest.raises(roster.RosterStructureError):
        roster.parse_members_org(body)


# ---------------------------------------------------------------------------
# Politeness and the raw cache (T-RAW)
# ---------------------------------------------------------------------------


def test_single_request_with_identified_user_agent(tmp_path: Path) -> None:
    fetcher = FakeFetcher((200, _sample_body()))
    source = roster.BffpPublicSource(tmp_path, fetcher, today=TODAY, sleep=_no_sleep)
    entries = source.fetch()
    assert len(fetcher.calls) == 1
    url, agent = fetcher.calls[0]
    assert url == roster.BFFP_MEMBERS_ORG_URL
    assert agent == "PlastiverseLive-Research (+https://plastiverse.live)"
    assert "@" not in agent
    assert len(entries) == len(roster.parse_members_org(_sample_body()))


@pytest.mark.parametrize("status", [403, 429])
def test_stops_without_retry_on_403_and_429(tmp_path: Path, status: int) -> None:
    fetcher = FakeFetcher((status, b""))
    source = roster.BffpPublicSource(tmp_path, fetcher, today=TODAY, sleep=_no_sleep)
    with pytest.raises(roster.RosterFetchError):
        source.fetch()
    assert len(fetcher.calls) == 1
    assert not (tmp_path / TODAY.isoformat()).exists()


def test_network_errors_retried_at_most_twice(tmp_path: Path) -> None:
    sleeps: list[float] = []
    fetcher = FakeFetcher(OSError("reset"), OSError("reset"), (200, _sample_body()))
    source = roster.BffpPublicSource(tmp_path, fetcher, today=TODAY, sleep=sleeps.append)
    source.fetch()
    assert len(fetcher.calls) == 3
    assert len(sleeps) == 2
    assert source.request_count == 3


def test_gives_up_after_two_retries(tmp_path: Path) -> None:
    fetcher = FakeFetcher(OSError("down"), OSError("down"), OSError("down"))
    source = roster.BffpPublicSource(tmp_path, fetcher, today=TODAY, sleep=_no_sleep)
    with pytest.raises(roster.RosterFetchError):
        source.fetch()
    assert len(fetcher.calls) == 3


def test_writes_raw_body_with_sha256_manifest(tmp_path: Path) -> None:
    import hashlib

    body = _sample_body()
    source = roster.BffpPublicSource(
        tmp_path, FakeFetcher((200, body)), today=TODAY, sleep=_no_sleep
    )
    source.fetch()
    day_dir = tmp_path / TODAY.isoformat()
    assert (day_dir / roster.RAW_FILE_NAME).read_bytes() == body
    manifest = json.loads((day_dir / roster.MANIFEST_FILE_NAME).read_text(encoding="utf-8"))
    assert manifest["sha256"] == hashlib.sha256(body).hexdigest()


def test_reuses_todays_cache_without_a_request(tmp_path: Path) -> None:
    first = roster.BffpPublicSource(
        tmp_path, FakeFetcher((200, _sample_body())), today=TODAY, sleep=_no_sleep
    )
    first.fetch()
    second_fetcher = FakeFetcher((200, b"{}"))
    second = roster.BffpPublicSource(tmp_path, second_fetcher, today=TODAY, sleep=_no_sleep)
    entries = second.fetch()
    assert second_fetcher.calls == []
    assert len(entries) == len(roster.parse_members_org(_sample_body()))


def test_cache_that_does_not_match_its_manifest_is_refused(tmp_path: Path) -> None:
    source = roster.BffpPublicSource(
        tmp_path, FakeFetcher((200, _sample_body())), today=TODAY, sleep=_no_sleep
    )
    source.fetch()
    (tmp_path / TODAY.isoformat() / roster.RAW_FILE_NAME).write_bytes(_body([]))
    again = roster.BffpPublicSource(tmp_path, FakeFetcher(), today=TODAY, sleep=_no_sleep)
    with pytest.raises(roster.RosterFetchError):
        again.fetch()


def test_purge_removes_only_dated_folders_older_than_thirty_days(tmp_path: Path) -> None:
    old = tmp_path / "2026-10-01"
    recent = tmp_path / "2026-11-20"
    keep_name = tmp_path / "notes"
    for folder in (old, recent, keep_name):
        folder.mkdir()
    removed = roster.purge_raw_cache(tmp_path, NOW, max_age_days=30)
    assert removed == ["2026-10-01"]
    assert not old.exists()
    assert recent.exists()
    assert keep_name.exists()


def test_csv_source_keeps_allow_list_and_needs_organization(tmp_path: Path) -> None:
    good = tmp_path / "export.csv"
    good.write_text(
        "organization,country,website,type,extra\n"
        "Example Reef Society,Norway,example-reef.no,cm,ignored\n",
        encoding="utf-8",
    )
    (entry,) = roster.CsvFileSource(good).fetch()
    assert (entry.organization, entry.country, entry.website) == (
        "Example Reef Society",
        "Norway",
        "example-reef.no",
    )
    bad = tmp_path / "bad.csv"
    bad.write_text("name,country\nExample,Norway\n", encoding="utf-8")
    with pytest.raises(roster.RosterStructureError):
        roster.CsvFileSource(bad).fetch()


# ---------------------------------------------------------------------------
# Structural-change guard (T-MAN)
# ---------------------------------------------------------------------------


def test_guard_trips_on_a_drop_over_twenty_percent() -> None:
    with pytest.raises(roster.RosterStructureError):
        roster.check_structural_change(7, 10)


def test_guard_allows_small_drop_first_run_and_acknowledged_drop() -> None:
    roster.check_structural_change(9, 10)
    roster.check_structural_change(50, None)
    roster.check_structural_change(7, 10, acknowledge_drop=True)


# ---------------------------------------------------------------------------
# Build script: manifests, privacy, stability and --check (T-MAN, T-EXT)
# ---------------------------------------------------------------------------


def _all_files_text(base: Path, skip: Path) -> dict[Path, str]:
    texts: dict[Path, str] = {}
    for path in base.rglob("*"):
        if path.is_file() and skip not in path.parents:
            texts[path] = path.read_text(encoding="utf-8")
    return texts


def test_build_from_input_writes_public_and_local_files(tmp_path: Path, capsys) -> None:
    paths = _paths(tmp_path)
    code = build_script.main(["--input", str(SAMPLE)], paths=paths, today=TODAY)
    assert code == 0
    roster_payload = json.loads((paths.site_dir / "roster.json").read_text(encoding="utf-8"))
    assert roster_payload["schema"] == "cg-roster-v1"
    assert set(roster_payload) == {"schema", "retrieved_at", "source", "source_url", "records"}
    for record in roster_payload["records"]:
        assert set(record) == set(build_script.PUBLIC_RECORD_KEYS)
        assert record["org_status"] in (
            "source_declared_org",
            "heuristic_org",
            "human_confirmed_org",
        )
    manifest = json.loads((paths.site_dir / "roster_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest) == set(build_script.PUBLIC_MANIFEST_KEYS)
    assert manifest["source_urls"] == [roster.BFFP_MEMBERS_ORG_URL]
    assert (paths.interim_dir / "roster_quarantine.csv").exists()
    assert (paths.interim_dir / "dupe_review.csv").exists()
    local = json.loads((paths.interim_dir / "roster_manifest.local.json").read_text("utf-8"))
    assert local["entries_fetched"] == len(roster.parse_members_org(_sample_body()))
    assert local["excluded"] == 2
    assert local["ambiguous"] == 1


def test_only_admitted_statuses_reach_the_public_roster(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    build_script.main(["--input", str(SAMPLE)], paths=paths, today=TODAY)
    payload = json.loads((paths.site_dir / "roster.json").read_text(encoding="utf-8"))
    statuses = {r["org_status"] for r in payload["records"]}
    assert statuses <= {"source_declared_org", "heuristic_org", "human_confirmed_org"}
    names = {r["name"] for r in payload["records"]}
    assert AMBIGUOUS_NAME not in names


def test_approved_not_organisation_is_removed_from_roster_and_manifest(
    tmp_path: Path, capsys
) -> None:
    paths = _paths(tmp_path)
    build_script.main(["--input", str(SAMPLE)], paths=paths, today=TODAY)
    roster_path = paths.site_dir / "roster.json"
    before = json.loads(roster_path.read_text(encoding="utf-8"))
    removed_id = before["records"][0]["group_id"]
    paths.curation_dir.mkdir()
    (paths.curation_dir / "group_tags.csv").write_text(
        f"group_id,not_an_organisation\n{removed_id},true\n", encoding="utf-8"
    )
    assert build_script.main(["--input", str(SAMPLE)], paths=paths, today=TODAY) == 0
    output = capsys.readouterr().out
    after = json.loads(roster_path.read_text(encoding="utf-8"))
    manifest = json.loads((paths.site_dir / "roster_manifest.json").read_text(encoding="utf-8"))
    assert removed_id not in {record["group_id"] for record in after["records"]}
    assert sum(manifest["admitted_by_org_status"].values()) == len(after["records"])
    assert output == "OK: roster files written\n" * 2
    assert len(output) < 100


def test_apply_curation_updates_committed_roster_without_raw_cache(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    build_script.main(["--input", str(SAMPLE)], paths=paths, today=TODAY)
    payload = json.loads((paths.site_dir / "roster.json").read_text(encoding="utf-8"))
    removed_id = payload["records"][0]["group_id"]
    paths.curation_dir.mkdir()
    (paths.curation_dir / "group_tags.csv").write_text(
        f"group_id,not_an_organisation\n{removed_id},true\n", encoding="utf-8"
    )
    assert build_script.main(["--apply-curation"], paths=paths, today=TODAY) == 0
    assert build_script.main(["--check"], paths=paths, today=TODAY) == 0


def test_excluded_and_ambiguous_names_appear_in_no_written_file(tmp_path: Path, capsys) -> None:
    paths = _paths(tmp_path)
    build_script.main(["--input", str(SAMPLE)], paths=paths, today=TODAY)
    captured = capsys.readouterr()
    texts = _all_files_text(tmp_path, skip=paths.raw_root)
    assert texts, "the build should write files"
    for name in EXCLUDED_NAMES:
        for path, text in texts.items():
            assert name not in text, f"{name} found in {path.name}"
        assert name not in captured.out + captured.err


def test_public_manifest_has_no_total_or_excluded_counts(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    build_script.main(["--input", str(SAMPLE)], paths=paths, today=TODAY)
    manifest = json.loads((paths.site_dir / "roster_manifest.json").read_text(encoding="utf-8"))
    for key in manifest:
        for part in ("total", "exclud", "ambig", "fetch"):
            assert part not in key
    assert "excluded" not in json.dumps(manifest) and "ambiguous" not in json.dumps(manifest)


def test_group_ids_are_stable_across_two_builds(tmp_path: Path) -> None:
    first = _paths(tmp_path / "one")
    second = _paths(tmp_path / "two")
    build_script.main(["--input", str(SAMPLE)], paths=first, today=TODAY)
    build_script.main(["--input", str(SAMPLE)], paths=second, today=TODAY)
    one = json.loads((first.site_dir / "roster.json").read_text(encoding="utf-8"))
    two = json.loads((second.site_dir / "roster.json").read_text(encoding="utf-8"))
    assert [r["group_id"] for r in one["records"]] == [r["group_id"] for r in two["records"]]
    assert one["records"] == two["records"]


def test_guard_trips_on_truncated_fixture_and_acknowledgement_allows_it(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    assert build_script.main(["--input", str(SAMPLE)], paths=paths, today=TODAY) == 0
    before = (paths.site_dir / "roster.json").read_text(encoding="utf-8")
    code = build_script.main(["--input", str(TRUNCATED)], paths=paths, today=TODAY)
    assert code == 2
    assert (paths.site_dir / "roster.json").read_text(encoding="utf-8") == before
    code = build_script.main(
        ["--input", str(TRUNCATED), "--acknowledge-drop"], paths=paths, today=TODAY
    )
    assert code == 0


def test_fetch_path_uses_the_injected_fetcher_and_writes_raw_cache(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    fetcher = FakeFetcher((200, _sample_body()))
    code = build_script.main(["--fetch"], paths=paths, fetcher=fetcher, today=TODAY)
    assert code == 0
    assert len(fetcher.calls) == 1
    assert (paths.raw_root / TODAY.isoformat() / roster.RAW_FILE_NAME).exists()
    local = json.loads((paths.interim_dir / "roster_manifest.local.json").read_text("utf-8"))
    assert local["request_count"] == 1
    assert local["status_counts"] == {"200": 1}


def test_fetch_refused_returns_failure_without_output(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    code = build_script.main(["--fetch"], paths=paths, fetcher=FakeFetcher((403, b"")), today=TODAY)
    assert code == 1
    assert not (paths.site_dir / "roster.json").exists()


def test_build_without_any_input_fails_cleanly(tmp_path: Path) -> None:
    assert build_script.main([], paths=_paths(tmp_path), today=TODAY) == 1


def test_check_passes_on_committed_structure_and_skips_without_raw_cache(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    build_script.main(["--input", str(SAMPLE)], paths=paths, today=TODAY)
    assert build_script.main(["--check"], paths=paths, today=TODAY) == 0


def test_check_fails_when_a_record_is_not_admitted(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    build_script.main(["--input", str(SAMPLE)], paths=paths, today=TODAY)
    path = paths.site_dir / "roster.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"][0]["org_status"] = "ambiguous"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert build_script.main(["--check"], paths=paths, today=TODAY) == 1


def test_check_fails_on_email_like_string(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    build_script.main(["--input", str(SAMPLE)], paths=paths, today=TODAY)
    path = paths.site_dir / "roster.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"][0]["name_alt"] = ["contact someone@example.org"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert build_script.main(["--check"], paths=paths, today=TODAY) == 1


def test_check_rebuilds_and_compares_when_raw_cache_exists(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    build_script.main(
        ["--fetch"], paths=paths, fetcher=FakeFetcher((200, _sample_body())), today=TODAY
    )
    assert build_script.main(["--check"], paths=paths, today=TODAY) == 0
    path = paths.site_dir / "roster.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["records"][0]["name"] = "Example Changed Name"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert build_script.main(["--check"], paths=paths, today=TODAY) == 1


def test_fetch_defaults_to_the_page_fetcher() -> None:
    script = (Path(__file__).resolve().parents[1] / "scripts" / "build_groups_roster.py").read_text(
        encoding="utf-8"
    )
    assert "fetcher or roster.page_fetcher" in script


def test_page_fetcher_waits_for_the_page_request_and_sets_no_origin() -> None:
    import inspect

    from atlas.groups import roster as roster_module

    source = inspect.getsource(roster_module.page_fetcher)
    assert "expect_response" in source and "BFFP_ABOUT_URL" in source
    # The Origin header is never set by hand; the page makes its own request.
    assert "Origin" not in source.replace("Origin not allowed", "")
    assert "extra_http_headers" not in source


# ---------------------------------------------------------------------------
# Roster QC (CG-ROSTER-QC): placeholders, automatic merge, reviewed curation
# ---------------------------------------------------------------------------

QC_CSV = (
    "organization,country,website,type\n"
    "a tip: tap,Germany,https://atiptap.org/,cm\n"
    "a tip: tap e.V.,Germany,https://www.atiptap.org,cm\n"
    "-,Indonesia,,cm\n"
    "Example Reef Society,Norway,https://example-reef.no,cm\n"
)
REEF_ID = admission.group_id_for("Example Reef Society", "NO", "example-reef.no")


def _qc_curation(base: Path, *, correction: str | None = None) -> Path:
    curation = base / "curation"
    curation.mkdir(parents=True, exist_ok=True)
    (curation / "group_merges.csv").write_text(
        "group_id_keep,group_id_drop,decided_at,decision\n", encoding="utf-8"
    )
    lines = ["group_id,name,submitted_at"]
    if correction is not None:
        lines.append(f"{REEF_ID},{correction},2026-11-26T10:00:00Z")
    (curation / "group_name_corrections.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return curation


def test_qc_build_merges_quarantines_and_applies_a_name_correction(tmp_path: Path) -> None:
    source = tmp_path / "export.csv"
    source.write_text(QC_CSV, encoding="utf-8")
    paths = _paths(tmp_path)
    _qc_curation(tmp_path, correction="Example Reef Society (Norway)")
    code = build_script.main(["--input", str(source)], paths=paths, today=TODAY)
    assert code == 0
    payload = json.loads((paths.site_dir / "roster.json").read_text(encoding="utf-8"))
    names = {r["group_id"]: r for r in payload["records"]}
    assert len(names) == 2
    assert all(any(c.isalnum() for c in r["name"]) for r in payload["records"])
    german = [r for r in payload["records"] if r["country"] == "DE"]
    assert [r["name"] for r in german] == ["a tip: tap e.V."]
    assert german[0]["name_alt"] == ["a tip: tap"]
    reef = names[REEF_ID]
    assert reef["name"] == "Example Reef Society (Norway)"
    assert reef["name_alt"] == ["Example Reef Society"]
    local = json.loads((paths.interim_dir / "roster_manifest.local.json").read_text("utf-8"))
    assert local["placeholders_quarantined"] == 1
    assert local["auto_merged_records"] == 1
    assert "auto_merges.csv" not in json.dumps(payload)
    assert (paths.interim_dir / "auto_merges.csv").exists()


def test_qc_check_passes_after_a_rebuild_with_curation(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw" / TODAY.isoformat()
    raw_root.mkdir(parents=True)
    (raw_root / roster.RAW_FILE_NAME).write_text(
        json.dumps(
            {
                "error": 0,
                "data": [
                    {
                        "organization": "Example Reef Society",
                        "country": "Norway",
                        "website": "https://example-reef.no",
                        "type": "cm",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    paths = _paths(tmp_path)
    _qc_curation(tmp_path, correction="Example Reef Society (Norway)")
    assert (
        build_script.main(
            ["--input", str(raw_root / roster.RAW_FILE_NAME)], paths=paths, today=TODAY
        )
        == 0
    )
    assert build_script.main([], paths=paths, today=TODAY) == 0


def test_qc_invalid_name_correction_fails_without_writing(tmp_path: Path, capsys) -> None:
    source = tmp_path / "export.csv"
    source.write_text(QC_CSV, encoding="utf-8")
    paths = _paths(tmp_path)
    curation = _qc_curation(tmp_path)
    (curation / "group_name_corrections.csv").write_text(
        f"group_id,name,submitted_at\n{REEF_ID},,2026-11-26T10:00:00Z\n", encoding="utf-8"
    )
    code = build_script.main(["--input", str(source)], paths=paths, today=TODAY)
    assert code == 1
    assert not (paths.site_dir / "roster.json").exists()
    assert "invalid group curation" in capsys.readouterr().err


def _write_export(path: Path, *rows: tuple[str, str, str]) -> Path:
    path.write_text(
        "organization,country,website\n"
        + "".join(f"{name},{country},{url}\n" for name, country, url in rows),
        encoding="utf-8",
    )
    return path


def test_incremental_preserves_established_identity_and_adds_new_admission(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    source = _write_export(
        tmp_path / "first.csv", ("Example Reef Society", "Norway", "https://old.no")
    )
    assert (
        build_script.main(["--input", str(source), "--incremental"], paths=paths, today=TODAY) == 0
    )
    payload_path = paths.site_dir / "roster.json"
    payload = json.loads(payload_path.read_text("utf-8"))
    established = payload["records"][0]
    established["name_alt"] = ["Example Reef Network"]
    established["group_id"] = "cg_1234567890abcdef"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    changed = _write_export(
        tmp_path / "second.csv",
        ("Example Reef Network", "Norway", "https://new.no"),
        ("New Coast Alliance", "Belgium", "https://new-coast.be"),
    )
    assert (
        build_script.main(
            ["--input", str(changed), "--incremental"],
            paths=paths,
            today=TODAY + dt.timedelta(days=1),
        )
        == 0
    )
    result = json.loads(payload_path.read_text("utf-8"))
    old = next(row for row in result["records"] if row["group_id"] == "cg_1234567890abcdef")
    assert old["name"] == established["name"]
    assert old["url"] == established["url"]
    assert old["roster_retrieved_at"] == established["roster_retrieved_at"]
    assert any(row["name"] == "New Coast Alliance" for row in result["records"])


def test_incremental_applies_name_and_not_org_curation_and_is_idempotent(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    source = _write_export(
        tmp_path / "export.csv",
        ("Example Reef Society", "Norway", "https://example-reef.no"),
        ("Example Bay Network", "Belgium", "https://example-bay.be"),
    )
    assert (
        build_script.main(["--input", str(source), "--incremental"], paths=paths, today=TODAY) == 0
    )
    payload = json.loads((paths.site_dir / "roster.json").read_text("utf-8"))
    ids = {row["name"]: row["group_id"] for row in payload["records"]}
    paths.curation_dir.mkdir()
    (paths.curation_dir / "group_tags.csv").write_text(
        f"group_id,not_an_organisation\n{ids['Example Bay Network']},true\n", encoding="utf-8"
    )
    (paths.curation_dir / "group_name_corrections.csv").write_text(
        "group_id,name,submitted_at\n"
        f"{ids['Example Reef Society']},Curated Reef Name,2026-11-26T00:00:00Z\n",
        encoding="utf-8",
    )
    assert (
        build_script.main(["--input", str(source), "--incremental"], paths=paths, today=TODAY) == 0
    )
    public_path = paths.site_dir / "roster.json"
    assert (
        build_script.main(
            ["--input", str(source), "--incremental"],
            paths=paths,
            today=TODAY + dt.timedelta(days=1),
        )
        == 0
    )
    before = public_path.read_bytes()
    assert (
        build_script.main(
            ["--input", str(source), "--incremental"],
            paths=paths,
            today=TODAY + dt.timedelta(days=1),
        )
        == 0
    )
    assert public_path.read_bytes() == before
    rows = json.loads(before)["records"]
    assert [row["name"] for row in rows] == ["Curated Reef Name"]
    assert build_script.main(["--check", "--incremental"], paths=paths) == 0


def test_incremental_guard_and_duplicate_check_leave_public_files_unchanged(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    assert (
        build_script.main(["--input", str(SAMPLE), "--incremental"], paths=paths, today=TODAY) == 0
    )
    roster_path = paths.site_dir / "roster.json"
    manifest_path = paths.site_dir / "roster_manifest.json"
    before = (roster_path.read_bytes(), manifest_path.read_bytes())
    assert (
        build_script.main(["--input", str(TRUNCATED), "--incremental"], paths=paths, today=TODAY)
        == 2
    )
    assert (roster_path.read_bytes(), manifest_path.read_bytes()) == before
    payload = json.loads(roster_path.read_text("utf-8"))
    payload["records"].append(dict(payload["records"][0]))
    roster_path.write_text(json.dumps(payload), encoding="utf-8")
    assert build_script.main(["--check", "--incremental"], paths=paths) == 1


def test_incremental_respects_reviewed_distinct_groups_with_same_name(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    name = "Example Reef Society"
    first = _write_export(tmp_path / "first.csv", (name, "Norway", "https://old.no"))
    assert build_script.main(["--input", str(first)], paths=paths, today=TODAY) == 0
    old_id = admission.group_id_for(name, "NO", "old.no")
    new_id = admission.group_id_for(name, "NO", "new.no")
    paths.curation_dir.mkdir()
    (paths.curation_dir / "group_merges.csv").write_text(
        f"group_id_keep,group_id_drop,decided_at,decision\n{old_id},{new_id},2026-11-26,different\n",
        encoding="utf-8",
    )
    second = _write_export(
        tmp_path / "second.csv",
        (name, "Norway", "https://old.no"),
        (name, "Norway", "https://new.no"),
    )
    assert (
        build_script.main(["--input", str(second), "--incremental"], paths=paths, today=TODAY) == 0
    )
    payload = json.loads((paths.site_dir / "roster.json").read_text(encoding="utf-8"))
    assert {row["group_id"] for row in payload["records"]} == {old_id, new_id}


def test_incremental_alias_only_change_keeps_public_bytes_and_rejects_corrupt_base(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    first = _write_export(
        tmp_path / "first.csv", ("Example Reef Society", "Norway", "https://old.no")
    )
    assert (
        build_script.main(["--input", str(first), "--incremental"], paths=paths, today=TODAY) == 0
    )
    roster_path = paths.site_dir / "roster.json"
    payload = json.loads(roster_path.read_text("utf-8"))
    row = payload["records"][0]
    row["name_alt"] = ["Example Reef Network"]
    roster_path.write_bytes((json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode())
    payload_path = paths.site_dir / "roster_manifest.json"
    before = (roster_path.read_bytes(), payload_path.read_bytes())
    changed = _write_export(
        tmp_path / "changed.csv", ("Example Reef Network", "Norway", "https://new.no")
    )
    assert (
        build_script.main(
            ["--input", str(changed), "--incremental"],
            paths=paths,
            today=TODAY + dt.timedelta(days=7),
        )
        == 0
    )
    assert (roster_path.read_bytes(), payload_path.read_bytes()) == before
    roster_path.write_text("{broken", encoding="utf-8")
    before_manifest = payload_path.read_bytes()
    assert (
        build_script.main(
            ["--input", str(changed), "--incremental"],
            paths=paths,
            today=TODAY + dt.timedelta(days=8),
        )
        == 1
    )
    assert roster_path.read_text(encoding="utf-8") == "{broken"
    assert payload_path.read_bytes() == before_manifest
