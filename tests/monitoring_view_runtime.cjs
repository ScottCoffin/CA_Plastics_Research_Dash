"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const html = fs.readFileSync(path.join(__dirname, "..", "site", "index.html"), "utf8");
const helperBlock = html.match(/<script id="monitoring-view-helpers">([\s\S]*?)<\/script>/);
assert.ok(helperBlock, "the page must include the runtime monitoring view helpers");

const context = vm.createContext({});
vm.runInContext(helperBlock[1], context, { filename: "monitoring-view-helpers.js" });
context.rows = [
  { id: "zero-coordinate", dataset_id: "sf", lat: 0, lon: 0, matrix: "surface water", date: "2020-01-02", particle_count: 0, concentration_value: 0, in_ca_land: false, in_ca_state_waters: false },
  { id: "null-coordinate", dataset_id: "sf", lat: null, lon: -122.4, matrix: "surface water", date: "2020-01-03" },
  { id: "missing-coordinate", dataset_id: "sf", lon: -122.4, matrix: "surface water", date: "2020-01-04" },
  { id: "blank-coordinate", dataset_id: "sf", lat: " ", lon: "-122.4", matrix: "surface water", date: "2020-01-05" },
  { id: "nonfinite-coordinate", dataset_id: "sf", lat: "Infinity", lon: -122.4, matrix: "surface water", date: "2020-01-06" },
  { id: "latitude-out-of-range", dataset_id: "sf", lat: 90.01, lon: 0, matrix: "surface water", date: "2020-01-07" },
  { id: "longitude-out-of-range", dataset_id: "sf", lat: 0, lon: 180.01, matrix: "surface water", date: "2020-01-08" },
  { id: "blank-matrix-bad-date", dataset_id: "sf", lat: 37.7, lon: -122.4, matrix: "  ", date: "not-a-date", particle_count: 3 },
  { id: "missing-matrix-bad-calendar", dataset_id: "sf", lat: 37.8, lon: -122.5, date: "2020-02-31", particle_count: 1 },
  { id: "missing-date", dataset_id: "sf", lat: 37.9, lon: -122.6, matrix: "", date: null }
];

const result = JSON.parse(vm.runInContext(`JSON.stringify((() => {
  const view = monitoringView;
  const allowed = new Set(["sf"]);
  const noFilters = { matrix: "", year: "", region: "", contributor: "" };
  return {
    coordinateIds: rows.filter((row) => view.coordinates(row) !== null).map((row) => row.id),
    locatedIds: view.locatedSamples(rows).map((item) => item.row.id),
    filterOptions: view.filterOptions(rows),
    zeroCoordinates: view.coordinates(rows[0]),
    unknownMatrixIds: view.filterSamples(rows, allowed, { ...noFilters, matrix: view.unknownMatrix }).map((row) => row.id),
    unknownDateIds: view.filterSamples(rows, allowed, { ...noFilters, year: view.unknownYear }).map((row) => row.id),
    year2020Ids: view.filterSamples(rows, allowed, { ...noFilters, year: "2020" }).map((row) => row.id),
    zeroValues: [view.displayValue(rows[0].particle_count, "unknown"), view.displayValue(rows[0].concentration_value, "not available")],
    zeroMatrix: view.matrix({ matrix: "  " }),
    invalidYears: [view.year({ date: null }), view.year({ date: "not-a-date" }), view.year({ date: "2020-02-31" }), view.year({ date: "2024-13" })],
    partialYears: [view.year({ date: "2024" }), view.year({ date: "2024-01" }), view.year({ date: "2024-12" })]
  };
})())`, context));

assert.deepEqual(result.coordinateIds, ["zero-coordinate", "blank-matrix-bad-date", "missing-matrix-bad-calendar", "missing-date"]);
assert.deepEqual(result.locatedIds, result.coordinateIds);
assert.deepEqual(result.filterOptions, { matrices: ["surface water"], years: ["2020"], hasUnknownMatrix: true, hasUnknownYear: true });
assert.deepEqual(result.zeroCoordinates, [0, 0]);
assert.deepEqual(result.unknownMatrixIds, ["blank-matrix-bad-date", "missing-matrix-bad-calendar", "missing-date"]);
assert.deepEqual(result.unknownDateIds, ["blank-matrix-bad-date", "missing-matrix-bad-calendar", "missing-date"]);
assert.deepEqual(result.year2020Ids, ["zero-coordinate", "null-coordinate", "missing-coordinate", "blank-coordinate", "nonfinite-coordinate", "latitude-out-of-range", "longitude-out-of-range"]);
assert.deepEqual(result.zeroValues, ["0", "0"]);
assert.equal(result.zeroMatrix, null);
assert.deepEqual(result.invalidYears, [null, null, null, null]);
assert.deepEqual(result.partialYears, ["2024", "2024", "2024"]);

const mapResult = JSON.parse(vm.runInContext(`JSON.stringify((() => {
  const near = { lat: 37.8, lon: -122.4 };
  const located = [
    { row: { id: "a", matrix: "fish", date: "2020-01-02", method: "m" }, coordinates: [near.lat, near.lon] },
    { row: { id: "b", matrix: "sediment", date: "2020-01-03", method: "m" }, coordinates: [near.lat, near.lon] },
    { row: { id: "c", matrix: "fish", date: "2020-01-04", method: "m" }, coordinates: [37.8, -122.4] },
    { row: { id: "far", matrix: "fish", date: "2020-01-05", method: "m" }, coordinates: [34.0, -118.2] }
  ];
  return {
    statewideWidth: monitoringMap.viewBox("statewide").width > 8,
    sfBayWidth: monitoringMap.viewBox("sf_bay").width < 1.2,
    path: monitoringMap.pathData({ type: "MultiPolygon", coordinates: [[[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]] }),
    clusters: monitoringMap.clusters(located, "sf_bay").map((c) => ({ n: c.rows.length, mixed: c.mixed, color: c.color })),
    legend: monitoringMap.legend(located, "sf_bay"),
    legendStatewide: monitoringMap.legend(located, "statewide"),
    colorFish: monitoringMap.colorFor("fish"),
    colorOther: monitoringMap.colorFor("novel matrix")
  };
})())`, context));

assert.equal(mapResult.statewideWidth, true);
assert.equal(mapResult.sfBayWidth, true);
const cosRounded = String(Math.round(Math.cos(37.25 * Math.PI / 180) * 100) / 100);
assert.equal(mapResult.path, `M0 0L${cosRounded} 0L${cosRounded} -1L0 -1L0 0Z`);
assert.deepEqual(mapResult.clusters, [{ n: 3, mixed: true, color: "#ffffff" }]);
assert.deepEqual(mapResult.legend, [["sediment", 1], ["fish", 2]]);
assert.deepEqual(mapResult.legendStatewide, [["sediment", 1], ["fish", 3]]);
assert.equal(mapResult.colorFish, "#2e7d32");
assert.equal(mapResult.colorOther, "#6b7177");
console.log("Monitoring view runtime checks passed: coordinates, zero values, unknown matrices and dates.");
