"""VD-32: Related resources icons, steward links and the card grid (owner request 2026-11-17).

Offline only: the fetch script's network calls are replaced by stubs; the committed icon files,
registry and JSON are read, never written.
"""

from __future__ import annotations

import copy
import io
import json
import re
import sys
from pathlib import Path

import pytest
import yaml
from PIL import Image

from atlas import linkouts

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SITE = ROOT / "site"
ICON_DIR = SITE / "assets" / "linkouts"
ICONS_YML = ROOT / "config" / "linkout_icons.yml"
COMMITTED = SITE / "data" / "california" / "linkouts.json"
INSTITUTIONS = SITE / "data" / "california" / "institutions.json"
CSS = ROOT / "framework" / "src" / "components" / "resources.css"
JS = ROOT / "framework" / "src" / "components" / "resources.js"

# Steward IDs recorded only for exact or unambiguous name matches (see config/linkouts.yml).
EXPECTED_INST_NAMES = {
    "LO-2": ("I11006740", "Southern California Coastal Water Research Project"),
    "LO-3": ("I4210157891", "NOAA National Centers for Environmental Information"),
    "LO-7": ("I4405287357", "Eric and Wendy Schmidt Center for Data Science & Environment"),
    "LO-10": ("I1290230355", "California Department of Toxic Substances Control"),
    "LO-11": ("I1290230355", "California Department of Toxic Substances Control"),
    "LO-12": ("I1290230355", "California Department of Toxic Substances Control"),
    "LO-13": ("I84218800", "University of California, Davis"),
}
# Stewards left as plain text: no Atlas institution with that exact name, or an ambiguous one.
UNMATCHED = {"LO-1", "LO-4", "LO-5", "LO-6", "LO-8", "LO-9"}
# VD-35 owner-chosen DTSC logo; the i0.wp.com copy returned 404, so the origin file is recorded.
DTSC_URL = "https://pfasproject.com/wp-content/uploads/2021/02/SCP_DTSC_Logo_T.png"


@pytest.fixture(scope="module")
def fetch_module():
    sys.path.insert(0, str(SCRIPTS))
    try:
        import fetch_linkout_icons

        return fetch_linkout_icons
    finally:
        sys.path.remove(str(SCRIPTS))


@pytest.fixture(scope="module")
def build_module():
    sys.path.insert(0, str(SCRIPTS))
    try:
        import build_linkouts_json

        return build_linkouts_json
    finally:
        sys.path.remove(str(SCRIPTS))


def _registry() -> dict:
    return linkouts.load_registry(ROOT / "config" / "linkouts.yml")


def _icon_records() -> list[dict]:
    return yaml.safe_load(ICONS_YML.read_text(encoding="utf-8"))["icons"]


def _png_bytes(size, color, background=None) -> bytes:
    image = Image.new("RGBA", size, background or color)
    if background is not None:
        image.paste(color, (size[0] // 4, size[1] // 4, 3 * size[0] // 4, 3 * size[1] // 4))
    out = io.BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


# --- committed icon files and records -------------------------------------------------------


def test_icon_records_follow_registry_order_and_explain_every_gap():
    registry_ids = [entry["id"] for entry in _registry()["entries"]]
    records = _icon_records()
    assert [row["id"] for row in records] == registry_ids
    for row in records:
        if row["path"] is None:
            assert row.get("error") or row.get("skip_reason"), f"{row['id']} has no reason"
        assert re.fullmatch(r"[A-Z0-9]{1,3}", row["initials"]), row["id"]


def test_stored_icons_are_small_square_and_self_contained(fetch_module):
    for row in _icon_records():
        if row["path"] is None:
            continue
        path = SITE / row["path"]
        assert path.is_file(), row["id"]
        assert row["path"] == f"assets/linkouts/{row['id'].lower()}.{row['format']}"
        if path.suffix == ".png":
            with Image.open(path) as image:
                assert image.size == (64, 64), row["id"]
                assert image.mode == "RGBA", row["id"]
        else:
            fetch_module.validate_svg(path.read_bytes())


def test_no_orphan_icon_files_and_no_skipped_cards():
    referenced = {row["path"] for row in _icon_records() if row["path"]}
    on_disk = {f"assets/linkouts/{p.name}" for p in ICON_DIR.iterdir() if p.is_file()}
    assert on_disk == referenced
    assert len(referenced) == 13
    assert [row["id"] for row in _icon_records() if row.get("skip_reason")] == []


def test_committed_json_carries_icon_initials_and_steward_ids():
    payload = json.loads(COMMITTED.read_text(encoding="utf-8"))
    records = {row["id"]: row for row in _icon_records()}
    registry = {entry["id"]: entry for entry in _registry()["entries"]}
    for entry in payload["entries"]:
        eid = entry["id"]
        assert entry["icon"] == records[eid]["path"], eid
        assert entry["initials"] == records[eid]["initials"], eid
        assert entry["steward_inst_id"] == registry[eid].get("steward_inst_id"), eid


def test_every_card_has_an_icon_and_owner_choices_are_recorded():
    rows = {row["id"]: row for row in _icon_records()}
    assert all(row["path"] for row in rows.values())
    assert rows["LO-1"]["source_kind"] == "apple-touch-icon"
    assert [row["source_kind"] for row in rows.values() if row["id"] == "LO-13"] == [
        "research network logo (NET-1)"
    ]
    # VD-35 owner choices: LO-2 is a local file, LO-9 and LO-10..12 are URLs.
    assert rows["LO-2"]["source_kind"] == "owner_file"
    assert rows["LO-2"]["icon_url"] is None
    assert rows["LO-2"]["note"] == "owner-supplied 2026-11-17"
    assert rows["LO-9"]["skip_reason"] is None
    assert rows["LO-9"]["source_kind"] == "owner_url"
    assert rows["LO-9"]["icon_url"].endswith("/One4All/reference/figures/One4All.jpg")
    for eid in ("LO-10", "LO-11", "LO-12"):
        assert rows[eid]["source_kind"] == "owner_url", eid
        assert rows[eid]["icon_url"] == DTSC_URL, eid
        assert rows[eid]["note"].startswith("owner-chosen 2026-11-17"), eid
    dtsc_bytes = {
        (ICON_DIR / f"{eid.lower()}.png").read_bytes() for eid in ("LO-10", "LO-11", "LO-12")
    }
    assert len(dtsc_bytes) == 1, "one download serves all three DTSC cards"


# --- steward links -------------------------------------------------------------------------


def test_steward_ids_are_exact_institution_matches():
    institutions = {
        row["inst_id"]: row["name"]
        for row in json.loads(INSTITUTIONS.read_text(encoding="utf-8"))["institutions"]
    }
    entries = {entry["id"]: entry for entry in _registry()["entries"]}
    for eid, (inst_id, name) in EXPECTED_INST_NAMES.items():
        assert entries[eid].get("steward_inst_id") == inst_id, eid
        assert institutions[inst_id] == name, eid
    for eid in UNMATCHED:
        assert "steward_inst_id" not in entries[eid], eid


# --- build script ----------------------------------------------------------------------------


def _write_icons(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "linkout_icons.yml"
    path.write_text(yaml.safe_dump({"icons": rows}, sort_keys=False), encoding="utf-8")
    return path


def test_build_loader_accepts_the_committed_records(build_module):
    icons = build_module.load_icons()
    assert set(icons) == {entry["id"] for entry in _registry()["entries"]}


@pytest.mark.parametrize(
    ("row", "message"),
    [
        ({"id": "LO-1", "initials": "pc", "path": None}, "initials"),
        ({"id": "LO-1", "initials": "PC", "path": "assets/linkouts/../x.png"}, "path must be"),
        ({"id": "LO-1", "initials": "PC", "path": "assets/networks/x.png"}, "path must be"),
        ({"id": "LO-1", "initials": "PC", "path": "assets/linkouts/missing.png"}, "missing"),
        ({"initials": "PC", "path": None}, "needs an id"),
    ],
)
def test_build_loader_rejects_bad_records(build_module, tmp_path, row, message):
    path = _write_icons(tmp_path, [row])
    with pytest.raises(ValueError, match=message):
        build_module.load_icons(path)


def test_build_loader_rejects_duplicates(build_module, tmp_path):
    row = {"id": "LO-1", "initials": "PC", "path": None}
    path = _write_icons(tmp_path, [dict(row), dict(row)])
    with pytest.raises(ValueError, match="duplicate"):
        build_module.load_icons(path)


def test_build_payload_needs_an_icon_record_and_a_valid_institution_id(build_module):
    registry = _registry()
    icons = build_module.load_icons()
    without = {key: value for key, value in icons.items() if key != "LO-4"}
    with pytest.raises(ValueError, match="LO-4: no icon record"):
        build_module.build_payload(registry, without)
    bad = copy.deepcopy(registry)
    next(e for e in bad["entries"] if e["id"] == "LO-2")["steward_inst_id"] = "not an id"
    with pytest.raises(ValueError, match="steward_inst_id"):
        build_module.build_payload(bad, icons)


# --- fetch helpers (offline) -----------------------------------------------------------------


def test_icon_candidates_prefer_touch_icons_then_largest_rel_icon(fetch_module):
    html = (
        '<link rel="icon" href="/fav32.png" sizes="32x32">'
        '<link rel="apple-touch-icon" href="/apple-180.png" sizes="180x180">'
        '<link rel="apple-touch-icon" href="/apple-120.png" sizes="120x120">'
        '<link rel="shortcut icon" href="/vector.svg" type="image/svg+xml">'
        '<link rel="mask-icon" href="/mask.svg" color="#000">'
        '<link rel="stylesheet" href="/site.css">'
    )
    assert fetch_module.icon_candidates(html, "https://ex.org/home") == [
        ("apple-touch-icon", "https://ex.org/apple-180.png"),
        ("apple-touch-icon", "https://ex.org/apple-120.png"),
        ("rel-icon", "https://ex.org/vector.svg"),
        ("rel-icon", "https://ex.org/fav32.png"),
        ("favicon.ico", "https://ex.org/favicon.ico"),
    ]


def test_icon_size_and_origin_helpers(fetch_module):
    assert fetch_module._icon_size("16x16 32x32", "", "a.png") == 32
    assert fetch_module._icon_size("", "image/svg+xml", "a.svg") == fetch_module.SCALABLE
    assert fetch_module._icon_size("", "", "a.png") == 0
    assert fetch_module.origin("https://a.example.org/c/d?x=1") == "https://a.example.org/"


def test_svg_validation_accepts_clean_and_rejects_active_or_external(fetch_module):
    clean = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 4">'
        b'<rect width="4" height="4"/></svg>'
    )
    fetch_module.validate_svg(clean)
    bad = [
        b"<svg><script>alert(1)</script></svg>",
        b'<svg onload="x()"></svg>',
        b'<svg><image href="https://example.org/a.png"/></svg>',
        b"<svg><style>@import url(x.css);</style></svg>",
        b'<!DOCTYPE svg [<!ENTITY x "y">]><svg/>',
        b"<html></html>",
        b"<svg>",
    ]
    for data in bad:
        with pytest.raises(fetch_module.IconError):
            fetch_module.validate_svg(data)


def test_raster_to_png_fits_a_64_square_with_transparent_letterbox(fetch_module):
    wide = _png_bytes((200, 100), (200, 30, 30, 255))
    with Image.open(io.BytesIO(fetch_module.raster_to_png(wide))) as out:
        assert out.size == (64, 64)
        assert out.mode == "RGBA"
        assert out.getpixel((0, 0))[3] == 0
        assert out.getpixel((32, 32))[3] == 255


def test_raster_to_png_makes_a_white_corner_background_transparent(fetch_module):
    white_ground = _png_bytes((32, 32), (200, 30, 30, 255), background=(255, 255, 255, 255))
    with Image.open(io.BytesIO(fetch_module.raster_to_png(white_ground))) as out:
        assert out.getpixel((0, 0))[3] == 0
        assert out.getpixel((32, 32))[:3] == (200, 30, 30)
        assert out.getpixel((32, 32))[3] == 255


def test_unreadable_bytes_are_an_icon_error(fetch_module):
    with pytest.raises(fetch_module.IconError):
        fetch_module.raster_to_png(b"<html>not an image</html>")


def test_default_initials_and_network_logo_lookup(fetch_module):
    assert fetch_module.default_initials("SCCWRP") == "SC"
    assert fetch_module.default_initials("Eric and Wendy Schmidt Center") == "EW"
    assert (
        fetch_module.default_initials("managed by Plastic Pollution Coalition, with key partners")
        == "PP"
    )
    networks = yaml.safe_load((ROOT / "config" / "research_networks.yml").read_text("utf-8"))[
        "networks"
    ]
    entry = _registry()["entries"][12]
    assert entry["id"] == "LO-13"
    found = fetch_module.network_logo_for(entry["root_url"], networks)
    assert found is not None and found["id"] == "NET-1"
    assert fetch_module.network_logo_for("https://example.org/", networks) is None


def _offline_fetches(fetch_module, monkeypatch) -> dict[str, list[str]]:
    """Replace the homepage search and the owner download with failing stubs; returns the calls."""
    calls: dict[str, list[str]] = {"attempt": [], "owner": []}

    def offline_attempt(entry, network, today, icon_page):
        calls["attempt"].append(entry["id"])
        raise OSError("offline for this test")

    def offline_owner(source):
        calls["owner"].append(source)
        raise OSError("offline for this test")

    monkeypatch.setattr(fetch_module, "attempt", offline_attempt)
    monkeypatch.setattr(fetch_module, "_owner_bytes", offline_owner)
    monkeypatch.setattr(fetch_module, "_remove_icon", lambda eid: None)
    return calls


def _captured_writes(fetch_module, monkeypatch) -> dict[str, list[dict]]:
    written: dict[str, list[dict]] = {}
    monkeypatch.setattr(
        fetch_module, "write_records", lambda rows, path=None: written.update(rows=rows)
    )
    return written


def _redirect_storage(fetch_module, monkeypatch, root: Path) -> Path:
    """Store icons under a temporary site folder instead of the committed one."""
    icon_dir = root / "assets" / "linkouts"
    monkeypatch.setattr(fetch_module, "SITE_DIR", root)
    monkeypatch.setattr(fetch_module, "ICON_DIR", icon_dir)
    return icon_dir


def test_main_keeps_existing_files_without_network(fetch_module, monkeypatch):
    calls = _offline_fetches(fetch_module, monkeypatch)
    written = _captured_writes(fetch_module, monkeypatch)
    assert fetch_module.main([]) == 0
    assert calls == {"attempt": [], "owner": []}, "every card with a file is kept"
    rows = {row["id"]: row for row in written["rows"]}
    assert rows["LO-1"]["path"] == "assets/linkouts/lo-1.png"
    assert rows["LO-9"]["path"] == "assets/linkouts/lo-9.png"
    assert rows["LO-9"]["skip_reason"] is None


def test_main_only_refetches_the_named_owner_card(fetch_module, monkeypatch):
    calls = _offline_fetches(fetch_module, monkeypatch)
    written = _captured_writes(fetch_module, monkeypatch)
    assert fetch_module.main(["--refresh", "--only", "lo-12"]) == 0
    assert calls == {"attempt": [], "owner": [DTSC_URL]}, "owner_source replaces the search"
    rows = {row["id"]: row for row in written["rows"]}
    assert rows["LO-12"]["path"] == "assets/linkouts/lo-12.png", "a failed refresh keeps the file"
    assert "offline" in rows["LO-12"]["error"]
    assert rows["LO-12"]["note"].startswith("owner-chosen 2026-11-17"), "the note is kept"
    assert rows["LO-1"]["path"] == "assets/linkouts/lo-1.png", "other cards keep their files"


def test_owner_url_is_downloaded_once_per_run_and_stored_as_png(
    fetch_module, monkeypatch, tmp_path
):
    icon_dir = _redirect_storage(fetch_module, monkeypatch, tmp_path)
    monkeypatch.setattr(fetch_module, "POLITE_DELAY_SECONDS", 0)
    downloads: list[str] = []

    def fake_get(url, limit, *, truncate=False):
        downloads.append(url)
        return _png_bytes((120, 60), (30, 90, 200, 255)), url

    monkeypatch.setattr(fetch_module, "_get", fake_get)
    cache: dict[str, bytes] = {}
    results = [
        fetch_module.owner_attempt(
            {"id": eid}, {"owner_source": DTSC_URL, "icon_page": None}, "2026-11-17", cache
        )
        for eid in ("LO-10", "LO-11", "LO-12")
    ]
    assert downloads == [DTSC_URL], "one download serves all three cards"
    for result in results:
        assert result["source_kind"] == "owner_url"
        assert result["icon_url"] == DTSC_URL
        assert result["page_url"] is None
    for eid in ("LO-10", "LO-11", "LO-12"):
        with Image.open(icon_dir / f"{eid.lower()}.png") as image:
            assert image.size == (64, 64) and image.mode == "RGBA"


def test_owner_file_is_converted_and_recorded_without_a_url(fetch_module, monkeypatch, tmp_path):
    icon_dir = _redirect_storage(fetch_module, monkeypatch, tmp_path)
    source = tmp_path / "logo.png"
    source.write_bytes(_png_bytes((438, 438), (10, 20, 30, 255)))
    fields = fetch_module.owner_attempt(
        {"id": "LO-2"}, {"owner_source": str(source), "icon_page": None}, "2026-11-17", {}
    )
    assert fields["path"] == "assets/linkouts/lo-2.png"
    assert fields["source_kind"] == "owner_file"
    assert fields["icon_url"] is None and fields["page_url"] is None
    with Image.open(icon_dir / "lo-2.png") as image:
        assert image.size == (64, 64)


def test_missing_owner_file_error_names_only_the_file(fetch_module, tmp_path):
    missing = tmp_path / "folder" / "gone.png"
    with pytest.raises(fetch_module.IconError, match="gone.png") as info:
        fetch_module._owner_bytes(str(missing))
    assert str(tmp_path) not in str(info.value)


# --- layout and page source ----------------------------------------------------------------


def test_card_grid_is_full_width_auto_fill_and_text_is_not_capped():
    css = CSS.read_text(encoding="utf-8")
    assert "grid-template-columns: repeat(auto-fill, minmax(min(100%, 20rem), 1fr))" in css
    assert "auto-fit" not in css
    # Framework caps every <ul> at 600px (blockquote, ol, ul); the card list must lift that cap.
    list_rule = re.search(r"#resources-root \.rs-list \{([^}]*)\}", css)
    assert list_rule and "max-width: none;" in list_rule.group(1)
    assert "#resources-root .rs-card p { max-width: none; }" in css
    assert re.search(r"#[0-9a-fA-F]{3,8}\b", css) is None, "colours come from tokens.css"


def test_icon_markup_is_decorative_lazy_and_sized():
    js = JS.read_text(encoding="utf-8")
    assert 'img.alt = "";' in js
    assert 'img.loading = "lazy";' in js
    assert "img.width = ICON_SIZE;" in js and "img.height = ICON_SIZE;" in js
    assert 'plane.setAttribute("aria-hidden", "true");' in js
    assert "innerHTML" not in js
    assert "steward_inst_id" in js and "institutionHref(entry.steward_inst_id)" in js
