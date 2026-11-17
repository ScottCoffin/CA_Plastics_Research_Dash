// Runtime checks for the Funding visualization model (framework/src/components/funding_viz_model.js)
// and the markup builders in funding_viz.js. Topic labels come from the shared AtlasTopics helper,
// loaded from site/assets/topics.js the same way the browser loads it.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {
  HEAT_SEP,
  HEAT_START,
  agencyColor,
  agencyOrder,
  buildHeat,
  buildSankey,
  buildSectorTopic,
  filterByHeatSelection,
  focusOfNode,
  heatCellKey,
  heatColOf,
  heatFill,
  inkFor,
  layoutSankey,
  liveSectorTopicKeys,
  liveTopicYearKeys,
  niceMax,
  pruneHeatSelection,
  sectorTopicKeysOf,
  tileMetrics,
  toggleHeatCell,
  topOrgs,
  topicYearKeysOf,
  viewRows,
  yearCounts
} from "../framework/src/components/funding_viz_model.js";
import {
  heatTableHtml,
  matrixTableHtml,
  orgListHtml,
  sankeySvg,
  sankeyTableHtml,
  tilesHtml,
  yearChartSvg,
  yearTableHtml
} from "../framework/src/components/funding_viz.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
(0, eval)(fs.readFileSync(path.join(ROOT, "site", "assets", "topics.js"), "utf8"));
const T = globalThis.AtlasTopics;
assert.ok(T && T.TOPICS, "shared topic helper must load");

// Deterministic fixture: every field is chosen by index, so failures reproduce exactly.
const base = {
  domain_tags: [], funder_agency: "", funder: "", funder_type: "federal", sector: "academia", org: "", org_state: "",
  fiscal_year: null, amount: null, currency: "USD", amount_basis: "", url: "", program: "", title: "", ca_led: false,
  plastic_related: true, pi_names: [], start: "", end: ""
};
function fixture(n = 90) {
  const sectors = ["academia", "government", "nonprofit", "industry", "unknown", "jpa"];
  const orgs = ["UC Davis", "uc davis", "Scripps Institution of Oceanography", "SJSU", "CSU Long Beach", "Stanford University",
    "CalTech", "Aquarium of the Pacific", "State Water Board", "Heal the Bay", "Ocean Protection Council", ""];
  const agencies = [["NSF", "federal"], ["NIH", "federal"], ["CA State Water Board", "state"], ["Local Dept X", "other"], ["", "federal"]];
  const topics = [[], ["air"], ["air", "occurrence_and_monitoring"], ["wastewater_and_treatment"], ["plastisphere", "risk_assessment"],
    ["analytical_methods", "matrix:marine"], ["zz_custom_tag"]];
  const years = [null, 2008, 2011, 2012, 2014, 2019, 2023, 2025];
  const out = [];
  for (let i = 0; i < n; i++) {
    const [agency, type] = agencies[(i * 7) % agencies.length];
    let amount = i % 4 === 0 ? null : 1000 * (((i * 37) % 97) + 1);
    if (i % 13 === 0 && i % 4 !== 0) amount = 0;
    out.push({
      ...base,
      grant_key: `g${i}`,
      title: `Award ${i}`,
      org: orgs[(i * 3 + Math.floor(i / 7)) % orgs.length],
      sector: sectors[(i * 11) % sectors.length],
      funder_agency: agency,
      funder: agency || "Fund",
      funder_type: type,
      fiscal_year: years[(i * 5) % years.length],
      amount,
      ca_led: i % 3 === 0,
      domain_tags: topics[(i * 5) % topics.length]
    });
  }
  return out;
}
const RAW = fixture();
const LABELS = {academia: "Academia", government: "Government", nonprofit: "Nonprofit & research institute"};
const close = (a, b) => Math.abs(a - b) <= 1e-6 * Math.max(1, Math.abs(a), Math.abs(b));
const V = viewRows(RAW, T);

// viewRows: derived fields, and the input rows are left unchanged.
{
  const before = JSON.stringify(RAW);
  const rows = viewRows(RAW, T);
  assert.equal(JSON.stringify(RAW), before, "viewRows must not mutate its input");
  assert.equal(rows.length, RAW.length);
  const uc = rows.filter((r) => r.orgKey === "uc davis");
  assert.ok(uc.length > 1, "two spellings of one organisation share a key");
  assert.equal(new Set(uc.map((r) => r.orgName)).size, 1, "one display name per organisation");
  assert.equal(rows[0].agency, RAW[0].funder_agency || RAW[0].funder || "Unknown funder");
  const untagged = rows.find((r) => r.topics[0] === "__untagged__");
  assert.ok(untagged, "awards with no topic are Untagged");
  assert.ok(rows.every((r) => r.topics.every((t) => !t.startsWith("matrix:"))), "matrix tags are not topics");
  assert.ok(rows.every((r) => r.amount === null || r.amount > 0), "zero amounts count as no amount");
}

// Sankey conservation: flow into every middle node equals its value, and flow out equals its value.
function checkConservation(graph) {
  const last = graph.ncols - 1;
  graph.nodes.forEach((n) => {
    const inn = graph.links.filter((l) => l.target === n.id).reduce((s, l) => s + l.value, 0);
    const out = graph.links.filter((l) => l.source === n.id).reduce((s, l) => s + l.value, 0);
    if (n.col > 0) assert.ok(close(inn, n.value), `${n.id}: inflow ${inn} != value ${n.value}`);
    if (n.col < last) assert.ok(close(out, n.value), `${n.id}: outflow ${out} != value ${n.value}`);
  });
}
for (const opts of [
  {mode: "awards", topN: 6, orgs: true},
  {mode: "awards", topN: 3, orgs: false},
  {mode: "amount", topN: 4, orgs: true},
  {mode: "amount", topN: 15, orgs: false}
]) {
  const graph = buildSankey(V, {...opts, T});
  checkConservation(graph);
  assert.ok(graph.nodes.length > 0, `graph for ${JSON.stringify(opts)} has nodes`);
  const withAmount = V.filter((r) => r.amount !== null);
  if (opts.mode === "awards") {
    assert.ok(close(graph.total, V.length), "awards mode: the first column adds up to the award count");
  } else {
    assert.ok(close(graph.total, withAmount.reduce((s, r) => s + r.amount, 0)), "amount mode: total is the reported amount");
    assert.equal(graph.excluded, V.length - withAmount.length, "amount mode: awards without an amount are excluded");
  }
}

// Organisation cap: at most topN organisation blocks per sector; the rest sit in "Other" blocks.
for (const topN of [3, 15]) {
  const graph = buildSankey(V, {mode: "awards", topN, orgs: true, T});
  const perSector = new Map();
  graph.nodes.filter((n) => n.type === "org").forEach((n) => perSector.set(n.sector, (perSector.get(n.sector) || 0) + 1));
  perSector.forEach((count, sector) => assert.ok(count <= topN, `${sector}: ${count} organisation blocks exceed ${topN}`));
  assert.ok(perSector.size > 0, "some sector has organisation blocks");
  const others = graph.nodes.filter((n) => n.type === "other");
  if (topN === 3) assert.ok(others.length > 0, "organisations beyond the cap fall into an Other block");
}

// Layout: positions stay inside the canvas; the graph itself is not changed by layout.
{
  const graph = buildSankey(V, {mode: "awards", topN: 6, orgs: true, T});
  const L = layoutSankey(graph, {width: 900, height: 480, marginLeft: 120, marginRight: 190});
  assert.equal(graph.nodes[0].x, undefined, "layout works on copies");
  L.nodes.forEach((n) => {
    assert.ok(n.x >= 0 && n.x + n.w <= 900, `node ${n.id} inside the width`);
    assert.ok(n.h > 0, `node ${n.id} has height`);
  });
  L.links.forEach((l) => assert.match(l.d, /^M[\d.]+,[\d.]+C/));
  assert.ok(L.height >= 480);
}

// Year series: every dated award is counted once, undated awards are counted apart, years are contiguous.
{
  const order = agencyOrder(V);
  const yc = yearCounts(V, order);
  const total = yc.years.reduce((s, y) => s + y.total, 0);
  assert.equal(total + yc.undated, V.length, "year totals plus undated equal the row count");
  assert.equal(yc.undated, V.filter((r) => r.fy === null).length);
  yc.years.forEach((y, i) => {
    assert.equal(y.total, y.segs.reduce((s, x) => s + x.n, 0), `segments add up for ${y.year}`);
    if (i > 0) assert.equal(y.year, yc.years[i - 1].year + 1, "years are contiguous");
  });
  assert.equal(yc.max, Math.max(...yc.years.map((y) => y.total)));
}

// Topic by fiscal year and sector by topic: each award counts once per topic it carries.
{
  const heat = buildHeat(V, T);
  const dated = V.filter((r) => r.fy !== null);
  const heatSum = heat.rows.reduce((s, r) => s + r.total, 0);
  assert.equal(heatSum, dated.reduce((s, r) => s + r.topics.length, 0));
  assert.equal(heat.cols[0], "pre", "years before the heat start share the pre column");
  const years = heat.cols.filter((c) => c !== "pre");
  assert.ok(years.every((y) => y >= HEAT_START), "dated columns start at the heat start year");
  years.forEach((y, i) => {
    if (i > 0) assert.equal(y, years[i - 1] + 1, "heat columns are consecutive years");
  });
  assert.ok(heat.rows.every((r) => r.counts.length === heat.cols.length));
  assert.ok(heat.rows.some((r) => r.key === "zz_custom_tag"), "topics outside the shared list still appear");

  const matrix = buildSectorTopic(V, T);
  const gridSum = matrix.grid.flat().reduce((a, b) => a + b, 0);
  assert.equal(gridSum, V.reduce((s, r) => s + r.topics.length, 0));
  assert.ok(matrix.sectors.every((s) => V.some((r) => r.sector === s)));
}

// Organisation ranking, tile metrics and small helpers.
{
  const top = topOrgs(V, 12);
  assert.ok(top.length <= 12);
  for (let i = 1; i < top.length; i++) assert.ok(top[i - 1].n >= top[i].n, "ranked by awards");
  const m = tileMetrics(V);
  assert.equal(m.awards, V.length);
  assert.ok(m.caShare >= 0 && m.caShare <= 1);
  assert.equal(m.withAmt + m.noAmt, V.length);
  assert.equal(niceMax(0), 1);
  assert.equal(niceMax(12), 20);
  assert.equal(niceMax(7), 10);
  assert.equal(heatFill(0, 5), "#e2dccf");
  assert.equal(heatFill(5, 5), "#1a2448");
  assert.notEqual(heatFill(1, 5), "#e2dccf");
  assert.equal(agencyColor("NSF"), "#0072B2");
  assert.equal(agencyColor("CA State Water Board"), "#8a969c");
  assert.equal(agencyColor("Unlisted agency"), "#8a969c");
  assert.equal(inkFor("#ffffff"), "#000000");
  assert.equal(inkFor("#000000"), "#ffffff");
  assert.equal(HEAT_START, 2012);
}

// Markup: tables and charts keep their text alternatives; amount titles carry the not-comparable caveat.
{
  const graph = buildSankey(V, {mode: "awards", topN: 6, orgs: true, T});
  const svg = sankeySvg(graph, 900, {T, amount: false});
  assert.match(svg, /^<svg /);
  assert.match(svg, /role="group" aria-labelledby="fv-sankey-title"/);
  assert.equal(svg.includes('role="img"'), false, "the Sankey is a group, so its focusable blocks stay reachable");
  assert.equal((svg.match(/class="fv-link"/g) || []).length, graph.links.length);
  const table = sankeyTableHtml(graph, false);
  assert.equal((table.match(/<tr>/g) || []).length, graph.links.length + 1, "one table row per ribbon plus the header");

  const amountGraph = buildSankey(V, {mode: "amount", topN: 6, orgs: true, T});
  const amountSvg = sankeySvg(amountGraph, 900, {T, amount: true});
  const titles = [...amountSvg.matchAll(/<title>([^<]*)<\/title>/g)].map((m) => m[1]);
  const reported = titles.filter((t) => t.includes("reported"));
  assert.ok(reported.length > 0);
  reported.forEach((t) => assert.ok(t.includes("source bases differ"), t));

  const yc = yearCounts(V, agencyOrder(V));
  const yearSvg = yearChartSvg(yc, 600);
  assert.match(yearSvg, /role="img"/);
  assert.equal(yearSvg.includes("NaN"), false, "year chart has no NaN coordinates");
  assert.match(yearTableHtml(yc, agencyOrder(V)), /<th scope="col" class="num">Total<\/th>/);
  assert.match(heatTableHtml(buildHeat(V, T), T), /role="region"/);
  assert.match(matrixTableHtml(buildSectorTopic(V, T), LABELS, T), /<caption/);
  assert.match(orgListHtml(topOrgs(V, 3), LABELS), /<ol class="fv-orgs-list">/);
  assert.match(orgListHtml([], LABELS), /No awards match/);
  assert.match(tilesHtml(tileMetrics(V)), /California-led/);
  assert.equal(svg.includes("NaN"), false, "Sankey has no NaN coordinates");
}

// Drill-down model: a focus keeps only the awards that pass through one block. The organisation cap is set
// from all awards first, so organisation and "Other" blocks match the unfocused graph.
{
  const opts = {mode: "awards", topN: 3, orgs: true, T};
  const full = buildSankey(V, opts);
  assert.deepEqual(buildSankey(V, {...opts, focus: null}), full, "no focus gives the unfocused graph");
  const fullIds = new Set(full.nodes.map((n) => n.id));
  for (const type of ["agency", "sector", "topic", "org", "other"]) {
    const node = full.nodes.find((n) => n.type === type);
    assert.ok(node, `unfocused graph has a ${type} block`);
    const focus = focusOfNode(node);
    assert.deepEqual(focus, {id: node.id, type: node.type, key: node.key, sector: node.sector ?? null, name: node.name});
    const graph = buildSankey(V, {...opts, focus});
    const hit = graph.nodes.find((n) => n.id === node.id);
    assert.ok(hit, `${type}: the focused block is kept`);
    const column = graph.nodes.filter((n) => n.col === hit.col);
    assert.deepEqual(column.map((n) => n.id), [node.id], `${type}: only the focused block is in its column`);
    assert.equal(hit.count, node.count, `${type}: the focused block keeps its award count`);
    graph.nodes.forEach((n) => {
      if (n.type === "org" || n.type === "other") assert.ok(fullIds.has(n.id), `${type}: ${n.id} is a block of the unfocused graph`);
    });
    checkConservation(graph);
    assert.equal(sankeySvg(graph, 900, {T, focusId: node.id}).includes("NaN"), false, `${type}: focused Sankey has no NaN`);
    if (type === "agency") {
      const rows = V.filter((r) => r.agency === node.key);
      assert.equal(hit.count, rows.length, "agency: count is the agency's awards");
      assert.equal(graph.awardCount, rows.length, "agency: awardCount is the agency's awards");
    }
    if (type === "topic") {
      const rows = V.filter((r) => r.topics.includes(node.key));
      assert.deepEqual(graph.nodes.filter((n) => n.col === graph.ncols - 1).map((n) => n.id), [node.id], "topic: the last column holds only the topic");
      assert.equal(hit.count, rows.length, "topic: count is the awards with that topic");
      assert.equal(graph.awardCount, rows.length, "topic: awardCount is the awards with that topic");
    }
    if (type === "org" || type === "other") {
      assert.deepEqual(graph.nodes.filter((n) => n.type === "sector").map((n) => n.key), [node.sector], `${type}: one sector`);
    }
  }
  for (const focus of [
    {id: "a:No such agency", type: "agency", key: "No such agency", sector: null, name: "No such agency"},
    {id: "t:not_a_topic", type: "topic", key: "not_a_topic", sector: null, name: "Not a topic"}
  ]) {
    const none = buildSankey(V, {...opts, focus});
    assert.equal(none.nodes.length, 0, `${focus.type}: an unknown key leaves no blocks`);
    assert.equal(none.links.length, 0, `${focus.type}: an unknown key leaves no ribbons`);
    assert.equal(none.awardCount, 0);
  }
  const amountOpts = {mode: "amount", topN: 3, orgs: true, T};
  const sector = buildSankey(V, amountOpts).nodes.find((n) => n.type === "sector");
  const amountFocused = buildSankey(V, {...amountOpts, focus: focusOfNode(sector)});
  assert.equal(amountFocused.excluded, V.length - V.filter((r) => r.amount !== null).length, "excluded counts the whole input");
  checkConservation(amountFocused);
}

// Focused Sankey markup: one pressed block carries is-focus, and every block is a labelled button.
{
  const graph = buildSankey(V, {mode: "awards", topN: 3, orgs: true, T});
  const agency = graph.nodes.find((n) => n.type === "agency");
  const focused = buildSankey(V, {mode: "awards", topN: 3, orgs: true, T, focus: focusOfNode(agency)});
  const svg = sankeySvg(focused, 900, {T, focusId: agency.id});
  assert.equal((svg.match(/aria-pressed="true"/g) || []).length, 1, "exactly one block is pressed");
  assert.match(svg, /<g class="fv-node is-focus"[^>]*aria-pressed="true"/, "the pressed block is the focused one");
  assert.equal((svg.match(/role="button"/g) || []).length, focused.nodes.length, "every block is a button");
  assert.match(svg, /Selected\. Press Enter to show all flows\./);
  const plain = sankeySvg(graph, 900, {T});
  assert.equal(plain.includes("is-focus"), false, "no block is marked without a focus");
  assert.equal((plain.match(/aria-pressed="false"/g) || []).length, graph.nodes.length, "unfocused blocks are not pressed");
  assert.match(plain, /Press Enter to show only flows through this block\./);
}

// Heatmap selection. A live cell selects exactly the awards its count reports; several cells in one heatmap
// combine as a union; the two heatmaps combine as an intersection; undated awards never match a year cell.
{
  assert.equal(heatColOf(null), null, "undated awards have no year column");
  assert.equal(heatColOf(HEAT_START - 1), "pre", "years before HEAT_START share the pre column");
  assert.equal(heatColOf(HEAT_START), HEAT_START);

  const heat = buildHeat(V, T);
  const matrix = buildSectorTopic(V, T);
  const topicYearLive = liveTopicYearKeys(heat);
  const sectorTopicLive = liveSectorTopicKeys(matrix);
  assert.ok(topicYearLive.length > 1 && sectorTopicLive.length > 1, "the fixture has live cells in both heatmaps");
  // Live keys are exactly the cells with a count.
  assert.equal(topicYearLive.length, heat.rows.flatMap((r) => r.counts).filter((n) => n > 0).length);
  assert.equal(sectorTopicLive.length, matrix.grid.flat().filter((n) => n > 0).length);

  // Every topic x year cell (zero cells too) selects as many awards as its count, and each one is in that topic and year.
  heat.rows.forEach((r) => heat.cols.forEach((col, i) => {
    const shown = filterByHeatSelection(V, {topicYear: new Set([heatCellKey(r.key, col)])});
    assert.equal(shown.length, r.counts[i], `topic x year ${r.key}/${col} selects its count`);
    shown.forEach((row) => {
      assert.ok(row.topics.includes(r.key) && row.fy !== null && heatColOf(row.fy) === col, `${r.key}/${col}: award in the cell`);
    });
  }));
  // Every sector x topic cell selects as many awards as its count.
  matrix.sectors.forEach((s, i) => matrix.topics.forEach((t, j) => {
    const shown = filterByHeatSelection(V, {sectorTopic: new Set([heatCellKey(s, t)])});
    assert.equal(shown.length, matrix.grid[i][j], `sector x topic ${s}/${t} selects its count`);
    shown.forEach((row) => assert.ok(row.sector === s && row.topics.includes(t), `${s}/${t}: award in the cell`));
  }));

  // Selecting every live cell of a heatmap leaves every award that has that heatmap's dimension.
  assert.equal(filterByHeatSelection(V, {topicYear: new Set(topicYearLive)}).length, V.filter((r) => r.fy !== null).length);
  assert.equal(filterByHeatSelection(V, {sectorTopic: new Set(sectorTopicLive)}).length, V.length);

  // No selection returns the input itself.
  assert.equal(filterByHeatSelection(V, {}), V);
  assert.equal(filterByHeatSelection(V, {topicYear: new Set(), sectorTopic: new Set()}), V);

  // OR within one heatmap: two cells show the union of their awards, with no duplicates.
  const [a, b] = topicYearLive;
  const [ta, ca] = a.split(HEAT_SEP);
  const [tb, cb] = b.split(HEAT_SEP);
  const inCell = (r, t, c) => r.fy !== null && r.topics.includes(t) && String(r.fy < HEAT_START ? "pre" : r.fy) === c;
  const expectedUnion = V.filter((r) => inCell(r, ta, ca) || inCell(r, tb, cb)).map((r) => r.grant_key);
  const union = filterByHeatSelection(V, {topicYear: new Set([a, b])}).map((r) => r.grant_key);
  assert.deepEqual(union, expectedUnion, "two topic x year cells combine as a union, in input order");
  assert.equal(new Set(union).size, union.length, "no award is listed twice");

  // AND across heatmaps: an award must sit in a selected cell of each heatmap that has a selection.
  const [sector, topic] = sectorTopicLive[0].split(HEAT_SEP);
  const cross = filterByHeatSelection(V, {topicYear: new Set([a]), sectorTopic: new Set([sectorTopicLive[0]])});
  const expectedCross = V.filter((r) => inCell(r, ta, ca) && r.sector === sector && r.topics.includes(topic)).map((r) => r.grant_key);
  assert.deepEqual(cross.map((r) => r.grant_key), expectedCross, "the two heatmaps combine as an intersection");
  assert.ok(cross.every((r) => topicYearKeysOf(r).includes(a) && sectorTopicKeysOf(r).includes(sectorTopicLive[0])));

  // Toggle: a click adds a cell, a second click removes it; the input set is not changed.
  const empty = new Set();
  const once = toggleHeatCell(empty, a);
  assert.deepEqual([...once], [a]);
  assert.equal(empty.size, 0, "toggle returns a new set");
  assert.equal(toggleHeatCell(once, a).size, 0, "a selected cell is cleared by a second click");
  assert.deepEqual([...toggleHeatCell(once, b)], [a, b], "a second cell is added to the first");

  // Prune: a selected cell that is no longer live (after a filter change) is dropped.
  assert.deepEqual([...pruneHeatSelection(new Set([a, `x${HEAT_SEP}2030`]), topicYearLive)], [a]);
  assert.equal(pruneHeatSelection(new Set(), topicYearLive).size, 0);
}

// Markup: a chart cell is a button with aria-pressed; empty cells are disabled; the table pane has no buttons.
{
  const heat = buildHeat(V, T);
  const liveRow = heat.rows.find((r) => r.counts.some((n) => n > 0));
  const liveCol = heat.cols[liveRow.counts.findIndex((n) => n > 0)];
  const html = heatTableHtml(heat, T, {selected: new Set([heatCellKey(liveRow.key, liveCol)])});
  const cells = heat.rows.length * heat.cols.length;
  assert.equal((html.match(/<button type="button" class="fv-cell"/g) || []).length, cells, "every cell is a button");
  assert.equal((html.match(/aria-pressed="true"/g) || []).length, 1, "exactly the selected cell is pressed");
  assert.match(html, /data-heat="topic-year"/);
  const empty = heat.rows.flatMap((r) => r.counts).filter((n) => n === 0).length;
  assert.equal((html.match(/ disabled aria-label=/g) || []).length, empty, "empty cells are disabled");
  if (empty) assert.match(html, /: no awards"/, "an empty cell is announced as having no awards");
  assert.equal(heatTableHtml(heat, T, {plain: true}).includes("<button"), false, "the table pane is plain numbers");

  const matrix = buildSectorTopic(V, T);
  const sector = matrix.sectors[0];
  const topic = matrix.topics.find((t, j) => matrix.grid[0][j] > 0);
  const mhtml = matrixTableHtml(matrix, LABELS, T, {selected: new Set([heatCellKey(sector, topic)])});
  assert.equal((mhtml.match(/aria-pressed="true"/g) || []).length, 1, "one pressed matrix cell");
  assert.match(mhtml, /data-heat="sector-topic"/);
  assert.equal(matrixTableHtml(matrix, LABELS, T, {plain: true}).includes("<button"), false);

  // The Sankey table has one class hook per name cell, so the page CSS can give the From and To columns room.
  const graph = buildSankey(V, {mode: "awards", topN: 6, orgs: true, T});
  const table = sankeyTableHtml(graph, false);
  assert.match(table, /^<table class="fv-sankey-table">/);
  assert.equal((table.match(/<td class="fv-name">/g) || []).length, graph.links.length * 2);
}

console.log("framework funding visualization runtime checks passed");
