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

// Interactive map: zoom clamping, re-clustering on zoom, and the legend toggle helper.
const interactiveResult = JSON.parse(vm.runInContext(`JSON.stringify((() => {
  const sw = monitoringMap.viewBox("statewide");
  let zoomed = sw;
  for (let i = 0; i < 200; i += 1) zoomed = monitoringMap.zoomView(zoomed, 1.5);
  const zoomedOut = monitoringMap.zoomView(sw, 0.01);
  const panned = monitoringMap.panView(sw, 1000, -1000);
  const centre = (view) => [view.x + view.width / 2, view.y + view.height / 2];
  const [px, py] = centre(panned);
  const inside = px >= sw.x && px <= sw.x + sw.width && py >= sw.y && py <= sw.y + sw.height;
  const aspectKept = Math.abs(zoomed.height / zoomed.width - sw.height / sw.width) < 1e-9;

  // Two points 0.1 statewide cells apart, inside one statewide cell but in different cells at 8x.
  const cell = sw.width / 12;
  const k = Math.floor(sw.x / cell) + 3;
  const x0 = (k + 0.2) * cell;
  const x1 = x0 + 0.1 * cell;
  const lonOf = (x) => x / monitoringMap.cosMid;
  const pair = [
    { row: { id: "p0", matrix: "fish", date: "2020-01-02", method: "m" }, coordinates: [37.0, lonOf(x0)] },
    { row: { id: "p1", matrix: "fish", date: "2020-01-03", method: "m" }, coordinates: [37.0, lonOf(x1)] }
  ];
  const width8 = sw.width / 8;
  const height8 = sw.height / 8;
  const view8 = { x: x0 - width8 / 2, y: -37.0 - height8 / 2, width: width8, height: height8 };

  // Legend toggle: hidden matrices leave the map, but the legend keeps counting them.
  const mixed = [
    { row: { id: "f", matrix: "fish", date: "2020-01-02", method: "m" }, coordinates: [37.8, -122.4] },
    { row: { id: "s", matrix: "sediment", date: "2020-01-03", method: "m" }, coordinates: [37.8, -122.4] },
    { row: { id: "f2", matrix: "fish", date: "2020-01-04", method: "m" }, coordinates: [37.8, -122.41] }
  ];
  const hidden = new Set(["sediment"]);
  const shownAfterToggle = monitoringMap.visibleSamples(mixed, hidden).map((item) => item.row.id);
  const mapMatrices = [...new Set(monitoringMap.clusters(monitoringMap.visibleSamples(mixed, hidden), "statewide").flatMap((c) => [...c.matrices.keys()]))];

  return {
    minWidthRatio: zoomed.width / (sw.width / 40),
    maxZoomScale: monitoringMap.zoomScale(zoomed),
    zoomedOutIsStatewide: Math.abs(zoomedOut.width - sw.width) < 1e-9,
    panInside: inside,
    aspectKept,
    statewideClusters: monitoringMap.clusters(pair, "statewide").length,
    zoomedClusters: monitoringMap.clusters(pair, "statewide", view8).length,
    zoomedRows: monitoringMap.clusters(pair, "statewide", view8).map((c) => c.rows.length),
    shownAfterToggle,
    mapMatrices,
    legendCounts: monitoringMap.legend(mixed, "statewide")
  };
})())`, context));

assert.ok(Math.abs(interactiveResult.minWidthRatio - 1) < 1e-9, "zoom-in must stop at 40x the statewide width");
assert.ok(Math.abs(interactiveResult.maxZoomScale - 40) < 1e-9, "zoom scale must cap at 40x");
assert.equal(interactiveResult.zoomedOutIsStatewide, true, "zoom-out must stop at the statewide width (1x)");
assert.equal(interactiveResult.panInside, true, "panning must keep the view centre inside the statewide extent");
assert.equal(interactiveResult.aspectKept, true, "zoom must keep the view aspect ratio");
assert.equal(interactiveResult.statewideClusters, 1, "points in one statewide cell share a cluster");
assert.equal(interactiveResult.zoomedClusters, 2, "the same points split into two clusters at 8x");
assert.deepEqual(interactiveResult.zoomedRows, [1, 1]);
assert.deepEqual(interactiveResult.shownAfterToggle, ["f", "f2"], "hiding sediment removes it from the drawn markers");
assert.deepEqual(interactiveResult.mapMatrices, ["fish"]);
assert.deepEqual(interactiveResult.legendCounts, [["sediment", 1], ["fish", 2]], "legend counts ignore the hidden state (palette order)");
console.log("Monitoring view runtime checks passed: coordinates, zero values, unknown matrices and dates.");
