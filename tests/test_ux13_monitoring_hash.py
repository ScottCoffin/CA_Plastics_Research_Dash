from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VIEW_MODULE = (ROOT / "framework" / "src" / "components" / "monitoring_view.js").as_uri()
COMPONENT = ROOT / "framework" / "src" / "components" / "monitoring.js"

# Node ES-module script: round-trips the Monitoring filters through the URL hash (UX-13).
NODE_CHECK = r"""
import assert from "node:assert/strict";
import {monitoringHashFromFilters, monitoringParamsFromHash, monitoringView} from VIEW_URL;

const EMPTY = {tier: "", search: "", contributor: "", matrix: "", year: "", region: ""};
const filtersFrom = (overrides) => ({...EMPTY, ...overrides});

// All default -> empty hash, and an empty hash reads back as all defaults.
assert.equal(monitoringHashFromFilters(EMPTY), "");
assert.deepEqual(monitoringParamsFromHash(""), EMPTY);
assert.deepEqual(monitoringParamsFromHash("#"), EMPTY);

// Each key alone round-trips and appears in the hash under its short name.
const cases = [
  [{tier: "A"}, "#tier=A"],
  [{search: "sea water"}, "#q=sea+water"],
  [{contributor: "true"}, "#contrib=true"],
  [{contributor: "false"}, "#contrib=false"],
  [{matrix: "surface water"}, "#matrix=surface+water"],
  [{year: "2020"}, "#year=2020"],
  [{region: "state_waters"}, "#region=state_waters"],
  [{year: monitoringView.unknownYear}, "#year=__unknown__"],
  [{matrix: monitoringView.unknownMatrix}, "#matrix=__unknown__"]
];
for (const [overrides, hash] of cases) {
  const filters = filtersFrom(overrides);
  assert.equal(monitoringHashFromFilters(filters), hash);
  assert.deepEqual(monitoringParamsFromHash(hash), filters);
}

// Search text with spaces and '&' (and other reserved characters) survives the round trip.
const tricky = filtersFrom({
  search: "  Ocean & Bay / sea=1 #2  ", matrix: "fish & sediment", tier: "B", region: "land"
});
const hash = monitoringHashFromFilters(tricky);
assert.ok(hash.startsWith("#"));
assert.deepEqual(monitoringParamsFromHash(hash), {...tricky, search: "Ocean & Bay / sea=1 #2"});
assert.equal(monitoringParamsFromHash(hash).matrix, "fish & sediment");

// Full round trip with every key set.
const full = filtersFrom({
  tier: "C", search: "CEDEN lab", contributor: "true", matrix: "sediment", year: "2023",
  region: "outside"
});
assert.deepEqual(monitoringParamsFromHash(monitoringHashFromFilters(full)), full);

// Hash without a leading '#' is accepted too.
assert.deepEqual(monitoringParamsFromHash("tier=A"), filtersFrom({tier: "A"}));

// Unknown keys are ignored.
assert.deepEqual(monitoringParamsFromHash("#foo=bar&tier=A&sample=12"), filtersFrom({tier: "A"}));

// Bad years are ignored: non-numeric, wrong length, or a partial date.
for (const year of ["abc", "20x0", "202", "20200", "2020-01", "-2020"]) {
  assert.equal(monitoringParamsFromHash(`#year=${encodeURIComponent(year)}`).year, "", year);
}

// Bad contributor and region values are ignored.
assert.equal(monitoringParamsFromHash("#contrib=maybe").contributor, "");
assert.equal(monitoringParamsFromHash("#region=mars").region, "");

// Values are trimmed on read; a whitespace-only value counts as empty.
assert.deepEqual(
  monitoringParamsFromHash("#q=+%20river%20+&matrix=%20%20"),
  filtersFrom({search: "river", matrix: ""})
);

// Only the six filter keys are written, in a fixed order.
assert.equal(
  monitoringHashFromFilters(full),
  "#tier=C&q=CEDEN+lab&contrib=true&matrix=sediment&year=2023&region=outside"
);
console.log("monitoring hash round trip: ok");
"""


def test_ux13_monitoring_hash_round_trip(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node.js is required for the UX-13 monitoring hash test; ensure `node` is on PATH."
        )
    script = tmp_path / "ux13_monitoring_hash_check.mjs"
    script.write_text(NODE_CHECK.replace("VIEW_URL", f'"{VIEW_MODULE}"'), encoding="utf-8")
    subprocess.run([node, str(script)], cwd=ROOT, check=True)


def test_monitoring_page_writes_and_reads_hash() -> None:
    text = COMPONENT.read_text(encoding="utf-8")
    # Filter changes write the hash with replaceState (no history entries); hashchange re-reads it.
    assert "window.history.replaceState(" in text
    assert "monitoringHashFromFilters(state.filters)" in text
    assert re.search(r'window\.addEventListener\("hashchange",\s*onMonitoringHashChange\)', text)
    # The hash is read before the first render, and the map and facets stay out of it.
    assert text.index(
        "state.filters = monitoringParamsFromHash(window.location.hash)"
    ) < text.index("render();\n    writeMonitoringHash();")
    assert "history.pushState" not in text
