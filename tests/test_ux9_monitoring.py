from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VIEW_MODULE = (ROOT / "framework" / "src" / "components" / "monitoring_view.js").as_uri()
PAGE = ROOT / "framework" / "src" / "monitoring.md"
COMPONENT = ROOT / "framework" / "src" / "components" / "monitoring.js"

# Node ES-module script: imports the Framework helpers and asserts the UX-9 behaviour.
NODE_CHECK = r"""
import assert from "node:assert/strict";
import {
  monitoringView, samplesCsv, formatSampleDate, licenceGloss, licenceGlosses,
  licenceGlossFallback, sharedUnit
} from VIEW_URL;

const datasets = [
  {id: "ds1", citation: 'Lab Team 2020. "Sample survey", Dataset.',
    publication_license: {id: "CC-BY-4.0"}},
  {id: "ds2", citation: "Ocean Team 2021. Report.", publication_license: null},
  {id: "ds3", citation: "Other 2022.", publication_license: {id: "fair-use-factual-values"}}
];
const sharedRows = [
  {dataset_id: "ds1", date: "2020-01-02T10:00:00Z", matrix: "surface water",
    in_ca_land: true, in_ca_state_waters: false, method: "manta, 333 um",
    particle_count: 3, concentration_value: 1.5, concentration_unit: "particles/L",
    citation: 'Lab Team 2020. "Sample survey", Dataset.'},
  {dataset_id: "ds2", date: "2021-03", matrix: "fish", in_ca_land: false,
    in_ca_state_waters: false, method: "dissection", particle_count: null,
    concentration_value: 2, concentration_unit: "particles/L"},
  {dataset_id: "ds1", date: "2020-02-31", matrix: "", in_ca_land: false,
    in_ca_state_waters: true, method: "manta", particle_count: 0,
    concentration_value: 0, concentration_unit: "particles/L"}
];
const mixedRows = [
  ...sharedRows,
  {dataset_id: "ds3", date: "2022-05-06", matrix: "sediment", in_ca_land: true,
    in_ca_state_waters: false, method: "grab", particle_count: 7,
    concentration_value: 0.4, concentration_unit: "particles/g",
    deposition_rate_value: 9, deposition_rate_unit: "particles/m2/day"}
];

// Dates: timestamps trim to the day; partial dates stay as recorded;
// invalid or missing dates read "Unknown date".
assert.deepEqual(
  [
    formatSampleDate({date: "2020-01-02T10:00:00Z"}),
    formatSampleDate({date: "2021-03"}),
    formatSampleDate({date: "2024"}),
    formatSampleDate({date: "2020-02-31"}),
    formatSampleDate({date: null}),
    formatSampleDate({date: "not-a-date"})
  ],
  ["2020-01-02", "2021-03", "2024", "Unknown date", "Unknown date", "Unknown date"]
);

// Units: one shared value goes in the header; mixed, blank or empty input returns null.
assert.equal(sharedUnit(sharedRows, "concentration_unit"), "particles/L");
assert.equal(sharedUnit(mixedRows, "concentration_unit"), null);
assert.equal(sharedUnit([], "concentration_unit"), null);
assert.equal(
  sharedUnit([{concentration_unit: null}, {concentration_unit: ""}], "concentration_unit"),
  null
);

// Glosses: every mapped id has text; unknown and missing ids use the fallback.
for (const id of Object.keys(licenceGlosses)) assert.ok(licenceGlosses[id].length > 20, id);
assert.ok(licenceGloss("CC-BY-4.0").startsWith("Creative Commons Attribution 4.0"));
assert.ok(licenceGloss("ODC-BY").startsWith("Open Data Commons Attribution"));
assert.ok(licenceGloss("fair-use-factual-values").startsWith(
  "Factual values reported in a publication, shown under fair use"));
assert.equal(licenceGloss("made-up-licence"), licenceGlossFallback);
assert.equal(licenceGloss(null), "Reuse terms not recorded; check the source");

// CSV with a shared unit: comment block, unit in the header, RFC 4180 quoting, CRLF endings.
const csv = samplesCsv(sharedRows, datasets, "2026-11-12");
assert.ok(csv.endsWith("\r\n"));
const lines = csv.split("\r\n").slice(0, -1);
const headerIndex = lines.findIndex((line) => line.startsWith("Date,"));
assert.ok(headerIndex > 0);
assert.ok(lines.slice(0, headerIndex).every((line) => line.startsWith("# ")));
assert.ok(lines.includes('# Source citation: Lab Team 2020. "Sample survey", Dataset.'));
assert.ok(lines.includes("# Source citation: Ocean Team 2021. Report."));
assert.ok(lines.includes("# Licence CC-BY-4.0: " + licenceGloss("CC-BY-4.0")));
assert.ok(lines.includes("# Licence not recorded: " + licenceGlossFallback));
assert.ok(lines.includes("# Downloaded from the CA Plastics Research Atlas on 2026-11-12."));
assert.equal(lines[headerIndex],
  "Date,Matrix,Region,Method,Particle count,Concentration (particles/L)," +
  "Deposition rate,Citation,Dataset ID,Licence");
const dataLines = lines.slice(headerIndex + 1);
assert.equal(dataLines.length, sharedRows.length);
assert.equal(dataLines[0],
  '2020-01-02,surface water,land,"manta, 333 um",3,1.5,,' +
  '"Lab Team 2020. ""Sample survey"", Dataset.",ds1,CC-BY-4.0');
assert.equal(dataLines[1],
  "2021-03,fish,outside,dissection,,2,,Ocean Team 2021. Report.,ds2,not recorded");
assert.equal(dataLines[2],
  'Unknown date,Unknown matrix,state_waters,manta,0,0,,' +
  '"Lab Team 2020. ""Sample survey"", Dataset.",ds1,CC-BY-4.0');

// Mixed units: no unit in the header; the unit column carries each row's own unit.
const mixed = samplesCsv(mixedRows, datasets, "2026-11-12").split("\r\n");
const mixedHeader = mixed.find((line) => line.startsWith("Date,"));
assert.equal(mixedHeader,
  "Date,Matrix,Region,Method,Particle count,Concentration,Concentration unit," +
  "Deposition rate,Deposition rate unit,Citation,Dataset ID,Licence");
assert.ok(mixed.some((line) => line.includes(",0.4,particles/g,")));

// Filter rows only: the CSV holds the filtered rows and nothing else.
const filtered = monitoringView.filterSamples(mixedRows, new Set(["ds1", "ds2", "ds3"]),
  {matrix: "fish", year: "", region: "", contributor: ""});
assert.equal(filtered.length, 1);
const filteredCsv = samplesCsv(filtered, datasets, "2026-11-12");
assert.ok(!filteredCsv.includes("sediment"));
assert.ok(!filteredCsv.includes("Lab Team"));
assert.ok(filteredCsv.includes("Ocean Team 2021. Report."));
assert.equal(filteredCsv.split("\r\n").filter((line) => line.startsWith("2021-03,")).length, 1);

console.log(JSON.stringify({ok: true, rows: filtered.length}));
"""


def test_ux9_monitoring_helpers_runtime() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for the UX-9 helper checks; install Node.js 20+.")
    code = NODE_CHECK.replace("VIEW_URL", json.dumps(VIEW_MODULE))
    result = subprocess.run(
        [node, "--input-type=module", "-e", code],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout.strip().splitlines()[-1]) == {"ok": True, "rows": 1}


def test_ux9_page_has_download_control_and_glossary_hooks() -> None:
    page = PAGE.read_text(encoding="utf-8")
    component = COMPONENT.read_text(encoding="utf-8")
    assert 'id="monitoring-download-csv"' in page
    assert "Download observations (CSV)" in page
    assert "./glossary#licences" in component
    assert "./glossary#access-tiers" in component
    assert "What do these mean?" in component
    assert "samplesCsv(rows, state.data.datasets" in component
    assert "URL.createObjectURL" in component
    assert "ca-plastics-observations-${today}.csv" in component
