"""Offline tests for scripts/build_world_map.py (PLAT-2a landing world map).

The tests use a tiny synthetic TopoJSON fixture and never touch the network.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import urllib.request
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "plat2a_world_topology_mini.json"


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "build_world_map", ROOT / "scripts" / "build_world_map.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bwm = _load_module()


@pytest.fixture
def topology() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _no_network(*args: Any, **kwargs: Any) -> None:
    raise AssertionError("the test must not touch the network")


def test_equal_earth_origin_and_extent() -> None:
    assert bwm.equal_earth(0, 0) == pytest.approx((0.0, 0.0), abs=1e-12)
    # The published extent is rounded to four decimals, so allow 1e-3 units.
    assert bwm.equal_earth(180, 0)[0] == pytest.approx(bwm.EE_XM, abs=1e-3)
    assert bwm.equal_earth(0, 90)[1] == pytest.approx(bwm.EE_YM, abs=1e-3)


def test_projection_centre_and_edges() -> None:
    assert bwm.to_pixels(0, 0) == pytest.approx((500.0, bwm.HEIGHT / 2), abs=0.1)
    assert bwm.to_pixels(180, 0)[0] == pytest.approx(bwm.WIDTH, abs=0.5)
    assert bwm.to_pixels(0, 90)[1] == pytest.approx(0.0, abs=0.5)


def test_viewbox_matches_prototype() -> None:
    # .impeccable/sketches/src/geo/world.json uses w=1000.0 and h=486.7.
    assert bwm.WIDTH == 1000.0
    assert bwm.HEIGHT == 486.7


def test_decode_arcs_undoes_quantization() -> None:
    topo = {
        "transform": {"scale": [0.5, 2], "translate": [10, -20]},
        "arcs": [[[2, 1], [4, -1]]],
    }
    # Deltas accumulate before scaling: the second point is quantized (6, 0), not (4, -1).
    assert bwm.decode_arcs(topo) == [[(11.0, -18.0), (13.0, -20.0)]]


def test_decode_arcs_without_transform_uses_absolute_positions() -> None:
    assert bwm.decode_arcs({"arcs": [[[1, 2], [3, 4]]]}) == [[(1.0, 2.0), (3.0, 4.0)]]


def test_ring_coordinates_joins_arcs_and_reverses_negative_indices() -> None:
    arcs = [
        [(0.0, 0.0), (1.0, 0.0)],
        [(1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
    ]
    assert bwm.ring_coordinates(arcs, [0, 1]) == [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    # ~0 is arc 0 backwards; its first point repeats the previous arc's last point and is dropped.
    assert bwm.ring_coordinates(arcs, [1, ~0]) == [(1.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.0, 0.0)]


def test_unwrap_longitudes_keeps_antimeridian_ring_continuous() -> None:
    points = [(170.0, 0.0), (-170.0, 0.0), (-170.0, 10.0), (170.0, 10.0)]
    unwrapped = bwm.unwrap_longitudes(points)
    assert [lon for lon, _ in unwrapped] == [170.0, 190.0, 190.0, 170.0]
    assert [lat for _, lat in unwrapped] == [0.0, 0.0, 10.0, 10.0]


def test_ring_paths_copies_a_seam_crossing_ring() -> None:
    ring = [(170.0, 0.0), (-170.0, 0.0), (-170.0, 10.0), (170.0, 10.0), (170.0, 0.0)]
    paths = bwm.ring_paths(ring)
    # The ring itself, and a copy shifted by -360 degrees for the part past 180.
    assert len(paths) == 2
    assert all(path.startswith("M") and path.endswith("Z") for path in paths)
    assert bwm.path_bbox(paths[0])[2] > bwm.WIDTH
    assert bwm.path_bbox(paths[1])[0] < 0


def test_ring_paths_drops_tiny_rings_only() -> None:
    tiny = [(0.0, 0.0), (0.1, 0.0), (0.1, 0.1), (0.0, 0.0)]
    assert bwm.ring_paths(tiny) == []
    larger = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 0.0)]
    assert len(bwm.ring_paths(larger)) == 1


def test_ring_paths_step_thins_vertices() -> None:
    ring = [(float(lon), 0.0) for lon in range(10)]
    assert bwm.ring_paths(ring)[0].count("L") == 9
    # Every third vertex, plus the last one again: 0, 3, 6, 9, 9 gives four segments.
    assert bwm.ring_paths(ring, step=3)[0].count("L") == 4


def test_geometry_path_skips_other_geometry_types(topology: dict[str, Any]) -> None:
    arcs = bwm.decode_arcs(topology)
    assert bwm.geometry_path({"type": "Point", "arcs": [0]}, arcs) == ""


def test_build_payload_from_fixture_keeps_expected_countries(topology: dict[str, Any]) -> None:
    payload = bwm.build_payload(topology, topology)
    assert set(payload) == {
        "sphere",
        "crop",
        "w",
        "h",
        "countries",
        "ca",
        "ca_bbox",
        "source",
        "licence",
    }
    # Antarctica is dropped by id; the 0.1-degree speck has no visible outline.
    assert [country["id"] for country in payload["countries"]] == ["250", "840"]
    by_id = {country["id"]: country for country in payload["countries"]}
    assert by_id["250"]["name"] == "Testland"
    assert by_id["250"]["iso_a2"] == "FR"
    assert by_id["840"]["iso_a2"] == "US"
    assert by_id["250"]["d"].count("M") == 1
    assert by_id["840"]["d"].count("M") == 2  # the ring and its seam copy
    assert payload["ca"].count("M") == 1
    x0, y0, x1, y1 = payload["ca_bbox"]
    assert x0 < x1 and y0 < y1
    assert payload["sphere"].startswith("M")
    assert payload["licence"] == "Natural Earth, public domain"


def test_iso_table_is_well_formed() -> None:
    table = bwm.ISO_NUMERIC_TO_ALPHA2
    assert all(len(key) == 3 and key.isdigit() for key in table)
    assert all(len(value) == 2 and value.isalpha() and value.isupper() for value in table.values())
    assert len(set(table.values())) == len(table)
    assert table["250"] == "FR"
    assert table["840"] == "US"
    assert table["578"] == "NO"
    assert "010" not in table  # Antarctica is dropped, not mapped


def test_read_source_offline_never_downloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    with pytest.raises(bwm.WorldMapError, match="not cached"):
        bwm.read_source(
            bwm.COUNTRIES_URL, tmp_path / "missing.json", bwm.COUNTRIES_SHA256, offline=True
        )


def test_read_source_rejects_a_cached_file_that_fails_its_pin(tmp_path: Path) -> None:
    path = tmp_path / "countries-110m.json"
    path.write_bytes(FIXTURE.read_bytes())
    with pytest.raises(bwm.WorldMapError, match="does not match the pinned"):
        bwm.read_source(bwm.COUNTRIES_URL, path, bwm.COUNTRIES_SHA256, offline=True)


def test_read_source_accepts_a_cached_file_with_matching_pin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    path = tmp_path / "states-10m.json"
    path.write_bytes(FIXTURE.read_bytes())
    digest = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    loaded = bwm.read_source(bwm.STATES_URL, path, digest, offline=True)
    assert "states" in loaded["objects"]


def _stage_inputs(raw: Path) -> str:
    """Copy the fixture in as both cached inputs and return its digest for the pins."""

    (raw / "countries").mkdir(parents=True)
    (raw / "states").mkdir()
    shutil.copyfile(FIXTURE, raw / bwm.COUNTRIES_FILE)
    shutil.copyfile(FIXTURE, raw / bwm.STATES_FILE)
    return hashlib.sha256(FIXTURE.read_bytes()).hexdigest()


def test_main_offline_writes_identical_bytes_on_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    digest = _stage_inputs(tmp_path / "raw")
    monkeypatch.setattr(bwm, "COUNTRIES_SHA256", digest)
    monkeypatch.setattr(bwm, "STATES_SHA256", digest)
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    out = tmp_path / "out" / "world.json"
    argv = ["--offline", "--raw-dir", str(tmp_path / "raw"), "--output", str(out)]

    assert bwm.main(argv) == 0
    first = out.read_bytes()
    assert bwm.main(argv) == 0
    assert out.read_bytes() == first
    assert b"\r" not in first
    assert first.endswith(b"\n")
    assert json.loads(first)["w"] == 1000.0
    assert "2 countries" in capsys.readouterr().out


def test_main_offline_without_cache_fails_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    out = tmp_path / "world.json"
    argv = ["--offline", "--raw-dir", str(tmp_path / "empty"), "--output", str(out)]
    assert bwm.main(argv) == 1
    assert not out.exists()
