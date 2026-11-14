// Runtime checks for the Evidence Map heatmap model (EV-HEATMAP).
// The pure helpers live in framework/src/components/ev_heatmap_model.js.
import assert from "node:assert/strict";
import {
  NO_MATRIX_KEY,
  cellKey,
  colorFor,
  contrastRatio,
  escapeHtml,
  heatmapCells,
  colSelected,
  labelSummary,
  pruneSelection,
  rowSelected,
  selectedIds,
  textInk,
  toggleCell,
  toggleCol,
  toggleRow,
  yearBins
} from "../framework/src/components/ev_heatmap_model.js";

const cell = (model, row, col) => model.cells.find((c) => c.row === row && c.col === col);

// Multi-tag counting: a work counts once in each (topic, matrix) cell it matches.
{
  const rows = [
    {work_id: "W1", year: 2021, domain_tags: ["occurrence_and_monitoring", "air"], facet_tags: ["matrix:marine", "matrix:freshwater"]},
    {work_id: "W2", year: 2022, domain_tags: ["occurrence_and_monitoring"], facet_tags: ["matrix:marine"]},
    {work_id: "W1", year: 2021, domain_tags: ["occurrence_and_monitoring"], facet_tags: ["matrix:marine"]}
  ];
  const model = heatmapCells(rows, "topic-matrix");
  // Every known topic keeps a row, in display order, so the grid does not change shape when filters change.
  assert.deepEqual(model.rows, [
    "occurrence_and_monitoring",
    "fate_transport_and_sorption",
    "soil_and_agriculture",
    "analytical_methods",
    "ecotoxicology_and_trophic_transfer",
    "wastewater_and_treatment",
    "human_exposure_and_health_risk",
    "air",
    "risk_assessment",
    "plastisphere"
  ]);
  assert.deepEqual(model.cols.map((c) => c.key), ["matrix:marine", "matrix:freshwater", "matrix:soil_and_agriculture", "matrix:food_and_drink", "matrix:air", "matrix:wastewater", NO_MATRIX_KEY]);
  assert.equal(cell(model, "occurrence_and_monitoring", "matrix:marine").count, 2);
  assert.deepEqual(cell(model, "occurrence_and_monitoring", "matrix:marine").ids.sort(), ["W1", "W2"]);
  assert.equal(cell(model, "occurrence_and_monitoring", "matrix:freshwater").count, 1);
  assert.equal(cell(model, "air", "matrix:marine").count, 1);
  assert.equal(cell(model, "air", "matrix:freshwater").count, 1);
  assert.equal(model.max, 2);
}

// Matrix columns come first and the "No matrix tag" column is last; works without a matrix land there.
{
  const rows = [
    {work_id: "A", year: 2020, domain_tags: ["air"], facet_tags: ["matrix:air"]},
    {work_id: "B", year: 2020, domain_tags: ["air"], facet_tags: []},
    {work_id: "C", year: 2020, domain_tags: ["air"], facet_tags: ["other_facet"]},
    {work_id: "D", year: 2020, domain_tags: ["air"]}
  ];
  const model = heatmapCells(rows, "topic-matrix");
  const last = model.cols[model.cols.length - 1];
  assert.equal(last.key, NO_MATRIX_KEY);
  assert.equal(last.label, "No matrix tag");
  assert.deepEqual(cell(model, "air", NO_MATRIX_KEY).ids.sort(), ["B", "C", "D"]);
  assert.equal(cell(model, "air", "matrix:air").count, 1);
  assert.equal(model.cols.filter((c) => c.key === NO_MATRIX_KEY).length, 1);
}

// Empty input: no rows, no columns beyond the fixed "No matrix tag", every count zero.
{
  const model = heatmapCells([], "topic-matrix");
  assert.equal(model.rows.length, 10);
  assert.equal(model.cells.length, model.rows.length * model.cols.length);
  assert.ok(model.cells.every((c) => c.count === 0 && c.ids.length === 0));
  assert.equal(model.max, 0);
  assert.deepEqual(heatmapCells([], "topic-year").cols, []);
}

// Year bins: aligned to 5-year starts, from the earliest to the latest year; a partial last bin is labelled to the latest year.
{
  const bins = yearBins([2002, 2026, 2011]);
  assert.deepEqual(bins.map((b) => b.label), ["2000–2004", "2005–2009", "2010–2014", "2015–2019", "2020–2024", "2025–2026"]);
  assert.deepEqual(bins.map((b) => b.key), ["2000", "2005", "2010", "2015", "2020", "2025"]);
  assert.deepEqual(yearBins([2024]).map((b) => b.label), ["2020–2024"]);
  assert.deepEqual(yearBins([2026]).map((b) => b.label), ["2025–2026"]);
  assert.deepEqual(yearBins([2025]).map((b) => b.label), ["2025"]);
  assert.deepEqual(yearBins([]), []);
}

// Topic x time counts: a work lands in its own bin and counts once per topic.
{
  const rows = [
    {work_id: "P", year: 2025, domain_tags: ["air", "air"], facet_tags: []},
    {work_id: "Q", year: 2026, domain_tags: ["air"], facet_tags: ["matrix:marine"]},
    {work_id: "R", year: "2001", domain_tags: ["air"], facet_tags: []},
    {work_id: "S", year: null, domain_tags: ["air"], facet_tags: []}
  ];
  const model = heatmapCells(rows, "topic-year");
  assert.deepEqual(model.cols.map((c) => c.label), ["2000–2004", "2005–2009", "2010–2014", "2015–2019", "2020–2024", "2025–2026"]);
  assert.deepEqual(cell(model, "air", "2025").ids, ["P", "Q"]);
  assert.equal(cell(model, "air", "2025").count, 2);
  assert.deepEqual(cell(model, "air", "2000").ids, ["R"]);
  assert.equal(cell(model, "air", "2010").count, 0);
  assert.equal(model.max, 2);
  assert.equal(model.cells.reduce((sum, c) => sum + c.count, 0), 3);
}

// Unknown mode is rejected.
assert.throws(() => heatmapCells([], "topic-size"));

// colorFor: zero is the near-white empty fill and distinct from 1; luminance never rises as the count grows.
{
  assert.equal(colorFor(0, 10), "#f4f7f6");
  assert.equal(colorFor(0, 0), "#f4f7f6");
  assert.notEqual(colorFor(1, 10), "#f4f7f6");
  const lum = (hex) => {
    const n = parseInt(hex.slice(1), 16);
    const lin = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => {
      const c = v / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    });
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
  };
  let previous = Infinity;
  for (let count = 1; count <= 40; count += 1) {
    const fill = colorFor(count, 40);
    assert.match(fill, /^#[0-9a-f]{6}$/);
    assert.ok(lum(fill) <= previous, `luminance rose at count ${count}`);
    previous = lum(fill);
  }
  assert.equal(colorFor(40, 40), "#0b4d48");
}

// textInk: black or white text reaches 4.5:1 on every fill in the ramp and on a grey sweep.
{
  for (let count = 0; count <= 60; count += 1) {
    const fill = colorFor(count, 60);
    const ink = textInk(fill);
    assert.ok([ "#000000", "#ffffff" ].includes(ink));
    const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
    assert.ok(contrastRatio(hex(fill), hex(ink)) >= 4.5, `low contrast for ${fill} with ${ink}`);
  }
  for (let v = 0; v <= 255; v += 1) {
    const hex = v.toString(16).padStart(2, "0");
    const fill = `#${hex}${hex}${hex}`;
    const ink = textInk(fill);
    const rgb = [v, v, v];
    const inkRgb = ink === "#000000" ? [0, 0, 0] : [255, 255, 255];
    assert.ok(contrastRatio(rgb, inkRgb) >= 4.5, `low contrast for grey ${fill}`);
  }
  assert.equal(textInk("#f4f7f6"), "#000000");
  assert.equal(textInk("#0b4d48"), "#ffffff");
}

// escapeHtml neutralises markup characters.
assert.equal(escapeHtml(`<a href="x">&'`), "&lt;a href=&quot;x&quot;&gt;&amp;&#39;");
assert.equal(escapeHtml(null), "");
assert.equal(escapeHtml(0), "0");

// Selection: cells toggle, rows toggle every non-empty cell, selections are unions, and zero cells never count.
{
  const rows = [
    {work_id: "A", year: 2021, domain_tags: ["air"], facet_tags: ["matrix:marine"]},
    {work_id: "B", year: 2021, domain_tags: ["air"], facet_tags: ["matrix:freshwater"]},
    {work_id: "C", year: 2022, domain_tags: ["plastisphere"], facet_tags: ["matrix:marine"]},
    {work_id: "D", year: 2022, domain_tags: ["plastisphere"], facet_tags: []}
  ];
  const model = heatmapCells(rows, "topic-matrix");
  const airMarine = cellKey("air", "matrix:marine");
  const plastiMarine = cellKey("plastisphere", "matrix:marine");
  const plastiNone = cellKey("plastisphere", NO_MATRIX_KEY);

  // Cell toggle: on, then off; the input set is never mutated.
  const empty = new Set();
  const on = toggleCell(empty, airMarine);
  assert.deepEqual([...on], [airMarine]);
  assert.equal(empty.size, 0);
  assert.equal(toggleCell(on, airMarine).size, 0);

  // Union of two cells, in model order, and no duplicates when a work sits in two selected cells.
  const union = toggleCell(toggleCell(empty, airMarine), plastiMarine);
  assert.deepEqual(selectedIds(model, union).sort(), ["A", "C"]);
  assert.deepEqual(selectedIds(model, toggleCell(union, plastiNone)).sort(), ["A", "C", "D"]);
  assert.deepEqual(selectedIds(model, empty), []);

  // Row toggle selects every non-empty cell in the row; a second toggle clears them all.
  const airRow = toggleRow(empty, model, "air");
  assert.deepEqual(selectedIds(model, airRow).sort(), ["A", "B"]);
  assert.equal(rowSelected(airRow, model, "air"), true);
  assert.equal(rowSelected(airRow, model, "plastisphere"), false);
  assert.equal(toggleRow(airRow, model, "air").size, 0);

  // A partly selected row: the header completes it first (aria-pressed stays false until every cell is in).
  const partial = toggleCell(empty, airMarine);
  assert.equal(rowSelected(partial, model, "air"), false);
  const completed = toggleRow(partial, model, "air");
  assert.equal(rowSelected(completed, model, "air"), true);
  assert.equal(toggleRow(completed, model, "air").size, 0);

  // A row with no works cannot be selected.
  assert.equal(toggleRow(empty, model, "soil_and_agriculture").size, 0);
  assert.equal(rowSelected(empty, model, "soil_and_agriculture"), false);

  // Zero cells are never selected: a stray key for an empty cell is pruned and adds no ids.
  const stray = new Set([cellKey("air", "matrix:air"), airMarine]);
  assert.deepEqual([...pruneSelection(stray, model)], [airMarine]);
  assert.deepEqual(selectedIds(model, stray), ["A"]);
  assert.equal(pruneSelection(union, null).size, 0);

  // Filter change: a selected cell that no longer has works is dropped; a surviving cell stays.
  const narrowed = heatmapCells(rows.filter((r) => r.work_id !== "C"), "topic-matrix");
  assert.deepEqual([...pruneSelection(union, narrowed)], [airMarine]);
  assert.equal(pruneSelection(union, heatmapCells([], "topic-matrix")).size, 0);
}

// Column selection (matrix and period headers): mirrors the row helpers.
{
  const rows = [
    {work_id: "A", year: 2021, domain_tags: ["air"], facet_tags: ["matrix:marine"]},
    {work_id: "B", year: 2021, domain_tags: ["plastisphere"], facet_tags: ["matrix:marine"]},
    {work_id: "C", year: 2022, domain_tags: ["air"], facet_tags: ["matrix:freshwater"]},
    {work_id: "D", year: 2022, domain_tags: ["air"], facet_tags: []}
  ];
  const model = heatmapCells(rows, "topic-matrix");
  const empty = new Set();

  // Toggling a column selects every non-empty cell in it, and a second toggle clears them.
  const marine = toggleCol(empty, model, "matrix:marine");
  assert.deepEqual(selectedIds(model, marine).sort(), ["A", "B"]);
  assert.equal(colSelected(marine, model, "matrix:marine"), true);
  assert.equal(colSelected(marine, model, "matrix:freshwater"), false);
  assert.equal(toggleCol(marine, model, "matrix:marine").size, 0);
  assert.equal(empty.size, 0);

  // A partly selected column is completed first, so aria-pressed stays false until every cell is in.
  const partial = toggleCell(empty, cellKey("air", "matrix:marine"));
  assert.equal(colSelected(partial, model, "matrix:marine"), false);
  const completed = toggleCol(partial, model, "matrix:marine");
  assert.equal(colSelected(completed, model, "matrix:marine"), true);
  assert.deepEqual(selectedIds(model, completed).sort(), ["A", "B"]);

  // Column and row selections combine as a union.
  const both = toggleCol(toggleRow(empty, model, "air"), model, "matrix:marine");
  assert.deepEqual(selectedIds(model, both).sort(), ["A", "B", "C", "D"]);

  // An empty column (no works) cannot be selected; the no-matrix column holds only D.
  assert.equal(toggleCol(empty, model, "matrix:air").size, 0);
  assert.equal(colSelected(empty, model, "matrix:air"), false);
  assert.deepEqual(selectedIds(model, toggleCol(empty, model, NO_MATRIX_KEY)), ["D"]);

  // Period columns use the same helpers. All four works fall in the 2020-2024 bin.
  const yearModel = heatmapCells(rows, "topic-year");
  const bin = toggleCol(empty, yearModel, "2020");
  assert.deepEqual(selectedIds(yearModel, bin).sort(), ["A", "B", "C", "D"]);
  assert.equal(colSelected(bin, yearModel, "2020"), true);
  assert.equal(colSelected(bin, yearModel, "2025"), false);
  assert.equal(toggleCol(bin, yearModel, "2020").size, 0);
  // A period with no works cannot be selected.
  assert.equal(toggleCol(empty, yearModel, "2025").size, 0);
}

// labelSummary: the first two labels, then how many are left over.
assert.equal(labelSummary([]), "");
assert.equal(labelSummary(["A × B"]), "A × B");
assert.equal(labelSummary(["A × B", "C × D"]), "A × B, C × D");
assert.equal(labelSummary(["A × B", "C × D", "E × F"]), "A × B, C × D (+1 more)");
assert.equal(labelSummary(["1", "2", "3", "4", "5"]), "1, 2 (+3 more)");

console.log("framework_ev_heatmap_runtime: all checks passed");
