// Flows, participation and language views for the Community groups page. The pure helpers take the public
// flows.json (cg-flows-v1) and groups.json shapes and have no DOM access, so Node tests can load them.
// mountGroupsFlows draws the views with the Framework's Plot, which the caller passes in (no npm imports here).
import {GROUP_TAXONOMY} from "./ambassador_groups.js";
import {
  EMPTY_MESSAGE, NOT_RECORDED, SMALL_CELL, inkFor, labelFor, orderedKeys, taggedGroups,
} from "./groups_composition.js";
import {CHROME, SECONDARY, SEQ, rampFill} from "./shared/palette.js";

/** Tag combinations with fewer groups than this are grouped under "Other combinations" (as the builder does). */
export const MIN_COMBINATION_GROUPS = 3;
/** The three linked steps of the flow view, in order. Each step's kind names its taxonomy list. */
export const FLOW_STAGES = Object.freeze([
  Object.freeze({key: "sector", kind: "sector", label: "Sector"}),
  Object.freeze({key: "centrality", kind: "plastics_centrality", label: "How central plastics are"}),
  Object.freeze({key: "activity", kind: "primary_activities", label: "Main activity"}),
]);
/** The five participation models (contractual to collegial), then the two non-model values. */
export const PARTICIPATION_ORDER = Object.freeze([
  "contractual", "contributory", "collaborative", "co_created", "collegial", "not_applicable", "not_set",
]);
const RESEARCH = "research_monitoring";
const KIND_OF_STAGE = Object.freeze(Object.fromEntries(FLOW_STAGES.map((stage) => [stage.key, stage])));

const keyOf = (value) => (value === undefined || value === null ? "" : String(value));
const activitiesOf = (group) => (Array.isArray(group?.primary_activities) ? group.primary_activities : []);
const sectorOf = (group) => keyOf(group?.sector);
const pluralGroups = (n) => `${n} ${n === 1 ? "group" : "groups"}`;

/** Muted (sunken fill, axis ink) under SMALL_CELL, so the count still shows; otherwise a palette colour with its ink. */
export function styleFor(n, index) {
  if (n < SMALL_CELL) return {fill: CHROME.sunken, ink: CHROME.axis, small: true};
  const fill = SECONDARY[index % SECONDARY.length];
  return {fill, ink: inkFor(fill), small: false};
}

// ---- flow view: sector, then how central plastics are, then main activity ----

const valueOfNode = (node) => node.label ?? String(node.id).split(":").slice(1).join(":");

/**
 * One bar per stage. Segments are the groups at each value, in taxonomy order (not by size). The first stage
 * counts outgoing links and each later stage counts incoming links, so a bar's total is the groups passing that step.
 */
export function stageBars(flows) {
  const nodes = Array.isArray(flows?.sankey?.nodes) ? flows.sankey.nodes : [];
  const links = Array.isArray(flows?.sankey?.links) ? flows.sankey.links : [];
  return FLOW_STAGES.map((stage, stageIndex) => {
    const side = stageIndex === 0 ? "source" : "target";
    const values = nodes.filter((node) => node.stage === stage.key).map(valueOfNode);
    let x = 0;
    const segments = orderedKeys(GROUP_TAXONOMY[stage.kind], values).map((value, index) => {
      const id = `${stage.key}:${value}`;
      const n = links.filter((link) => link[side] === id).reduce((sum, link) => sum + link.value, 0);
      const segment = {
        id, stage: stage.key, value, label: labelFor(stage.kind, value), n, text: String(n),
        x1: x, x2: x + n, ...styleFor(n, index),
      };
      x += n;
      return segment;
    });
    return {key: stage.key, label: stage.label, total: x, segments};
  });
}

/** Conservation: every bar must add up to the tagged total. */
export function flowConservation(stages, total) {
  const totals = stages.map((stage) => stage.total);
  return {total, totals, ok: totals.every((t) => t === total)};
}

const nameOfNode = (id) => {
  const at = id.indexOf(":");
  const stage = KIND_OF_STAGE[id.slice(0, at)];
  return stage ? labelFor(stage.kind, id.slice(at + 1)) : id;
};

/** Rows for the from-to table: one per link, in the order the builder gives. */
export function flowRows(flows) {
  const links = Array.isArray(flows?.sankey?.links) ? flows.sankey.links : [];
  return links.map((link) => ({
    from: nameOfNode(link.source),
    to: nameOfNode(link.target),
    n: link.value,
    small: link.value < SMALL_CELL,
    text: String(link.value),
  }));
}

// ---- participation: research and monitoring groups, one small chart per sector ----

const participationOf = (group) =>
  PARTICIPATION_ORDER.includes(group?.participation_in_science) ? group.participation_in_science : "not_set";
export const participationLabel = (value) => (value === "not_set" ? NOT_RECORDED : labelFor("participation_in_science", value));

/**
 * Counts of tagged research and monitoring groups by sector and participation value. Every group is counted once,
 * in its sector; withValue counts groups with a participation value (Not applicable included).
 */
export function participationFacets(groups) {
  const researching = taggedGroups(groups).filter((group) => activitiesOf(group).includes(RESEARCH));
  const sectors = orderedKeys(GROUP_TAXONOMY.sector, researching.map(sectorOf));
  const facets = sectors.map((sector) => {
    const inSector = researching.filter((group) => sectorOf(group) === sector);
    const rows = PARTICIPATION_ORDER.map((value) => {
      const n = inSector.filter((group) => participationOf(group) === value).length;
      return {value, label: participationLabel(value), n, text: String(n), ...styleFor(n, 0)};
    });
    return {sector, label: labelFor("sector", sector), total: inSector.length, rows};
  });
  const withValue = researching.filter((group) => participationOf(group) !== "not_set").length;
  return {total: researching.length, withValue, facets};
}

// ---- activity combinations: ranked bars plus a dot key ----

/** Lexicographic order on two lists of taxonomy keys (the builder's tie-break). */
function compareLists(a, b) {
  for (let i = 0; i < Math.min(a.length, b.length); i += 1) {
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  }
  return a.length - b.length;
}

/**
 * Bars for the most frequent combinations, most common first. Any combination under MIN_COMBINATION_GROUPS
 * (even one the builder listed) moves into the "Other combinations" bar, so the bars always add up to the total.
 */
export function combinationRows(flows) {
  const block = flows?.activity_combinations || {};
  const minSize = Number.isFinite(block.min_group_size) ? block.min_group_size : MIN_COMBINATION_GROUPS;
  const listed = Array.isArray(block.combinations) ? block.combinations : [];
  const kept = listed
    .filter((combo) => combo.groups >= minSize)
    .map((combo) => ({activities: combo.activities, n: combo.groups}))
    .sort((a, b) => b.n - a.n || compareLists(a.activities, b.activities));
  const dropped = listed.filter((combo) => combo.groups < minSize);
  const other = {
    combinations: (block.other?.combinations ?? 0) + dropped.length,
    groups: (block.other?.groups ?? 0) + dropped.reduce((sum, combo) => sum + combo.groups, 0),
  };
  const rows = kept.map((combo, index) => ({
    key: String(index),
    activities: combo.activities,
    n: combo.n,
    label: combo.activities.map((activity) => labelFor("primary_activities", activity)).join(" + "),
    text: String(combo.n),
    ...styleFor(combo.n, 0),
  }));
  if (other.combinations > 0) {
    rows.push({
      key: "other", activities: [], n: other.groups, label: "Other combinations", text: String(other.groups),
      ...styleFor(other.groups, 0),
    });
  }
  return {minSize, rows, other, combinationCount: kept.length};
}

/** Row geometry for the combination panels: pixels above the first row (rotated activity labels) and below the last. */
export const COMBO_ROW_PX = 24;
export const COMBO_TOP_PX = 150;
export const COMBO_BOTTOM_PX = 36;

/**
 * Two panels that share one row geometry, so each combination sits on the same line in both: the dot key (one
 * column per activity; a filled dot when the combination has the activity, a light dot otherwise; a thin line
 * joins a row's filled dots) and the bars. Both carry the same yDomain, height and margins. Rows are indexed
 * 0 to n-1, top to bottom; the "other" row has no dots. Each bar's tip carries the full combination name.
 */
/** Horizontal room the -45° activity labels need beyond the last dot column. */
const DOT_LABEL_OVERHANG_PX = 110;

export function combinationPanels(rows) {
  const n = rows.length;
  const yDomain = [n - 0.5, -0.5];
  const shared = {
    yDomain,
    height: COMBO_TOP_PX + COMBO_BOTTOM_PX + n * COMBO_ROW_PX,
    marginTop: COMBO_TOP_PX,
    marginBottom: COMBO_BOTTOM_PX,
  };
  const columns = GROUP_TAXONOMY.primary_activities.filter((activity) => rows.some((row) => row.activities.includes(activity)));
  const dots = [];
  const joins = [];
  const bars = [];
  rows.forEach((row, index) => {
    const tip = `${row.label}: ${pluralGroups(row.n)}`;
    bars.push({row: index, n: row.n, text: row.text, fill: row.fill, tip, y1: index - 0.4, y2: index + 0.4});
    if (row.key === "other") return;
    const filled = [];
    columns.forEach((activity, col) => {
      const on = row.activities.includes(activity);
      if (on) filled.push(col);
      dots.push({row: index, col, on, fill: on ? CHROME.axis : CHROME.grid});
    });
    if (filled.length >= 2) joins.push({row: index, x1: filled[0], x2: filled.at(-1), y1: index - 0.05, y2: index + 0.05});
  });
  return {
    columns: columns.map((activity) => labelFor("primary_activities", activity)),
    dot: {...shared, dots, joins},
    bar: {...shared, bars, maxN: Math.max(0, ...rows.map((row) => row.n))},
  };
}

// ---- website languages by region (tagged groups only) ----

const LANGUAGE_NAMES = (() => {
  try {
    return new Intl.DisplayNames(["en"], {type: "language"});
  } catch {
    return null;
  }
})();

/** English name for an ISO 639-1 code, or the code itself when no name is known. */
export function languageName(code) {
  try {
    return LANGUAGE_NAMES?.of(code) || code;
  } catch {
    return code;
  }
}

const codesOf = (group) => [
  ...new Set((Array.isArray(group?.website_languages) ? group.website_languages : []).filter((code) => typeof code === "string" && code !== "")),
];

/**
 * Tagged groups by website language (rows) and region (columns). A group counts once for each language it lists.
 * Languages run from most to fewest groups; regions follow the order of appearance, with "Not recorded" last.
 */
export function languageRegionCounts(groups) {
  const tagged = taggedGroups(groups);
  const counts = new Map();
  const pairs = new Map();
  for (const group of tagged) {
    const region = keyOf(group.region);
    for (const code of codesOf(group)) {
      counts.set(code, (counts.get(code) || 0) + 1);
      const key = JSON.stringify([code, region]);
      pairs.set(key, (pairs.get(key) || 0) + 1);
    }
  }
  const codes = [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a) || (a < b ? -1 : a > b ? 1 : 0));
  const regions = orderedKeys([], tagged.map((group) => keyOf(group.region)));
  const max = Math.max(0, ...pairs.values());
  const cells = codes.flatMap((code) => regions.map((region) => {
    const n = pairs.get(JSON.stringify([code, region])) || 0;
    const small = n < SMALL_CELL;
    const fill = n === 0 ? SEQ[0] : small ? CHROME.sunken : rampFill(n / max);
    return {
      language: code, region: labelFor(null, region), n, small, fill,
      ink: small ? CHROME.axis : inkFor(fill), text: String(n),
      tip: `${languageName(code)}, ${labelFor(null, region)}: ${pluralGroups(n)}`,
    };
  }));
  return {
    total: tagged.length,
    languages: codes.map((code) => ({code, name: languageName(code), n: counts.get(code)})),
    regions: regions.map((region) => labelFor(null, region)),
    cells,
    noLanguage: tagged.filter((group) => codesOf(group).length === 0).length,
  };
}

/**
 * The language grid, transposed for reading: one row per region (only regions with a tagged group) and one column
 * per language. Every row has a cell for every column, so a count of zero is still shown.
 */
export function languagePanel(counts) {
  return {
    rows: counts.regions,
    columns: counts.languages.map((lang) => ({code: lang.code, name: lang.name, n: lang.n})),
    cells: counts.cells.map((cell) => ({...cell, row: cell.region, column: cell.language})),
  };
}

// ---- DOM rendering (mountGroupsFlows only) ----

const CHART_WIDTH = 300;

function node(doc, tag, className, text) {
  const el = doc.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

const emptyNote = (doc) => node(doc, "p", "groups-flows__empty", EMPTY_MESSAGE);

/** A horizontally scrolling wrapper must be keyboard reachable and named (axe scrollable-region-focusable). */
function scrollRegion(doc, className, label, ...children) {
  const region = node(doc, "div", className);
  region.tabIndex = 0;
  region.setAttribute("role", "region");
  region.setAttribute("aria-label", label);
  region.append(...children);
  return region;
}

function dataTable(doc, caption, headers, rows) {
  const table = node(doc, "table", "groups-flows__table");
  table.append(node(doc, "caption", "", caption));
  const head = node(doc, "tr");
  headers.forEach((text) => head.append(node(doc, "th", "", text)));
  const thead = node(doc, "thead");
  thead.append(head);
  const body = node(doc, "tbody");
  for (const row of rows) {
    const tr = node(doc, "tr");
    if (row.small) tr.className = "groups-flows__muted";
    row.cells.forEach((text, i) => tr.append(i === 0 ? node(doc, "th", "", text) : node(doc, "td", "", text)));
    body.append(tr);
  }
  table.append(thead, body);
  return scrollRegion(doc, "groups-flows__scroll", `${caption}, as a table`, table);
}

function detailsWith(doc, summary, open, ...children) {
  const details = node(doc, "details", "groups-flows__details");
  details.open = open;
  details.append(node(doc, "summary", "", summary), ...children);
  return details;
}

function sankeyFigure(doc, Plot, stages, total, width, caption) {
  const BAR = 0.6;
  const segments = stages.flatMap((stage, row) => stage.segments.map((seg) => ({
    ...seg, row, y1: row - BAR / 2, y2: row + BAR / 2, xm: (seg.x1 + seg.x2) / 2,
    tip: `${seg.label}: ${pluralGroups(seg.n)}`,
  })));
  const plot = Plot.plot({
    width,
    height: 60 + stages.length * 56,
    marginLeft: 170,
    marginRight: 12,
    marginTop: 8,
    marginBottom: 28,
    x: {domain: [0, total], axis: null},
    y: {domain: [stages.length - 0.5, -0.5], axis: null},
    color: {identity: true},
    marks: [
      Plot.axisY({ticks: stages.map((_, row) => row), tickFormat: (row) => stages[row].label, tickSize: 0, label: null, lineWidth: 8, fontSize: 12}),
      Plot.rect(segments, {x1: "x1", x2: "x2", y1: "y1", y2: "y2", fill: "fill", title: "tip"}),
      Plot.text(segments, {x: "xm", y: "row", text: "text", fill: "ink", fontSize: 11}),
    ],
  });
  plot.setAttribute("role", "img");
  plot.setAttribute("aria-label", caption);
  const figure = node(doc, "figure", "groups-flows__figure");
  figure.append(
    scrollRegion(doc, "groups-flows__chart", "How groups flow from sector to main activity", plot),
    node(doc, "figcaption", "groups-flows__summary", caption),
  );
  return figure;
}

function legendFor(doc, stages) {
  const wrap = node(doc, "div");
  for (const stage of stages) {
    wrap.append(node(doc, "h4", "", stage.label));
    const list = node(doc, "ul", "groups-flows__legend");
    for (const seg of stage.segments) {
      const item = node(doc, "li");
      const swatch = node(doc, "span", "groups-flows__swatch");
      swatch.style.background = seg.fill;
      item.append(swatch, doc.createTextNode(`${seg.label}: ${seg.n}`));
      list.append(item);
    }
    wrap.append(list);
  }
  return wrap;
}

function sankeySection(doc, groups, flows, Plot, width) {
  const section = node(doc, "section", "groups-flows__section");
  section.append(node(doc, "h3", "", "How groups flow from sector to main activity"));
  const total = taggedGroups(groups).length;
  if (total === 0) {
    section.append(emptyNote(doc));
    return section;
  }
  const stages = stageBars(flows);
  const check = flowConservation(stages, total);
  const caption = check.ok
    ? `Each bar adds up to ${total} tagged groups. Steps stay in the fixed taxonomy order, not by size. Segments with fewer than ${SMALL_CELL} groups are muted; their counts still show.`
    : `The flows do not add up to the ${total} tagged groups, so this chart may be out of date.`;
  if (Plot) section.append(sankeyFigure(doc, Plot, stages, total, width, caption));
  else section.append(node(doc, "p", "groups-flows__summary", caption));
  section.append(legendFor(doc, stages));
  const rows = flowRows(flows);
  section.append(detailsWith(doc, "Show the flows as a table", !Plot,
    rows.length
      ? dataTable(doc, "Groups moving from one step to the next", ["From", "To", "Groups"],
        rows.map((row) => ({small: row.small, cells: [row.from, row.to, row.text]})))
      : node(doc, "p", "groups-flows__note", "No flows are recorded yet.")));
  return section;
}

function participationSection(doc, groups, Plot, width) {
  const section = node(doc, "section", "groups-flows__section");
  section.append(node(doc, "h3", "", "How research groups take part in science"));
  const facets = participationFacets(groups);
  if (facets.total === 0) {
    section.append(emptyNote(doc));
    return section;
  }
  const caption = `${facets.withValue} of ${facets.total} groups tagged for research and monitoring carry a participation value; the rest are not recorded. The first five values are the five models, from contractual to collegial. Each chart is one sector, on the same scale.`;
  section.append(node(doc, "p", "groups-flows__summary", caption));
  const maxN = Math.max(1, ...facets.facets.flatMap((facet) => facet.rows.map((row) => row.n)));
  const multiples = node(doc, "div", "groups-flows__multiples");
  for (const facet of facets.facets) {
    const block = node(doc, "div", "groups-flows__multiple");
    block.append(node(doc, "h4", "", `${facet.label} (${pluralGroups(facet.total)})`));
    if (Plot) {
      const plot = Plot.plot({
        width: Math.min(CHART_WIDTH, width),
        marginLeft: 130,
        marginRight: 24,
        marginTop: 4,
        marginBottom: 28,
        x: {domain: [0, maxN], label: "Groups"},
        y: {domain: facet.rows.map((row) => row.label), label: null},
        color: {identity: true},
        marks: [
          Plot.barX(facet.rows, {x: "n", y: "label", fill: "fill", title: "label"}),
          Plot.text(facet.rows, {x: "n", y: "label", text: "text", dx: 4, textAnchor: "start", fill: CHROME.axis, fontSize: 11}),
        ],
      });
      plot.setAttribute("role", "img");
      plot.setAttribute("aria-label", `${facet.label}: groups by participation value`);
      block.append(scrollRegion(doc, "groups-flows__chart", `${facet.label}, participation values`, plot));
    }
    multiples.append(block);
  }
  section.append(multiples);
  const values = PARTICIPATION_ORDER.map((value, i) => ({
    small: false,
    cells: [participationLabel(value), ...facets.facets.map((facet) => String(facet.rows[i].n))],
  }));
  section.append(detailsWith(doc, "Show the counts as a table", !Plot,
    dataTable(doc, "Participation values by sector", ["Participation", ...facets.facets.map((facet) => facet.label)], values)));
  return section;
}

function combinationSection(doc, groups, flows, Plot, width) {
  const section = node(doc, "section", "groups-flows__section");
  section.append(node(doc, "h3", "", "Common combinations of activities"));
  if (taggedGroups(groups).length === 0) {
    section.append(emptyNote(doc));
    return section;
  }
  const combos = combinationRows(flows);
  if (!combos.rows.length) {
    section.append(node(doc, "p", "groups-flows__note", "No combinations of activities are recorded yet."));
    return section;
  }
  const caption = `Ordered by how often each combination of tags appears, most common first. Combinations with fewer than ${combos.minSize} groups are grouped under "Other combinations". Combinations are counted from every activity a group lists.`;
  section.append(node(doc, "p", "groups-flows__summary", caption));
  if (Plot) {
    const panels = combinationPanels(combos.rows);
    const dotPlot = Plot.plot({
      // Labels rotated -45° run up and to the right: reserve room past the last column so none is clipped.
      width: Math.max(120, 40 + panels.columns.length * 28 + DOT_LABEL_OVERHANG_PX),
      height: panels.dot.height,
      marginLeft: 12,
      marginRight: 12 + DOT_LABEL_OVERHANG_PX,
      marginTop: panels.dot.marginTop,
      marginBottom: panels.dot.marginBottom,
      x: {domain: [-0.5, Math.max(0, panels.columns.length - 0.5)], axis: null},
      y: {domain: panels.dot.yDomain, axis: null},
      color: {identity: true},
      marks: [
        Plot.axisX({
          anchor: "top", ticks: panels.columns.map((_, i) => i), tickFormat: (i) => panels.columns[i],
          tickRotate: -45, tickSize: 0, label: null, fontSize: 11,
        }),
        Plot.rect(panels.dot.joins, {x1: "x1", x2: "x2", y1: "y1", y2: "y2", fill: CHROME.axis, ariaHidden: true}),
        Plot.dot(panels.dot.dots, {x: "col", y: "row", fill: "fill", r: 5, ariaHidden: true}),
      ],
    });
    const barPlot = Plot.plot({
      width: 300,
      height: panels.bar.height,
      marginLeft: 4,
      marginRight: 40,
      marginTop: panels.bar.marginTop,
      marginBottom: panels.bar.marginBottom,
      x: {domain: [0, Math.max(1, panels.bar.maxN)], label: "Groups"},
      y: {domain: panels.bar.yDomain, axis: null},
      color: {identity: true},
      marks: [
        Plot.rect(panels.bar.bars, {x1: 0, x2: "n", y1: "y1", y2: "y2", fill: "fill", title: "tip"}),
        Plot.text(panels.bar.bars, {x: "n", y: "row", text: "text", dx: 4, textAnchor: "start", fill: CHROME.axis, fontSize: 11}),
      ],
    });
    dotPlot.setAttribute("role", "img");
    dotPlot.setAttribute("aria-label", "Dot key: the activities in each combination, one row per bar");
    barPlot.setAttribute("role", "img");
    barPlot.setAttribute("aria-label", caption);
    const pair = node(doc, "div", "groups-flows__pair");
    pair.append(dotPlot, barPlot);
    section.append(scrollRegion(doc, "groups-flows__chart", "Common combinations of activities", pair));
  }
  const rows = combos.rows.map((row) => ({small: row.n < SMALL_CELL, cells: [row.label, row.text]}));
  section.append(detailsWith(doc, "Show the combinations as a table", !Plot, dataTable(doc, "Common combinations", ["Combination", "Groups"], rows)));
  return section;
}

function languageSection(doc, groups, Plot, width) {
  const section = node(doc, "section", "groups-flows__section");
  section.append(node(doc, "h3", "", "Website languages by region"));
  const counts = languageRegionCounts(groups);
  if (counts.total === 0) {
    section.append(emptyNote(doc));
    return section;
  }
  if (!counts.languages.length) {
    section.append(node(doc, "p", "groups-flows__note", "No website languages are recorded for tagged groups yet."));
    return section;
  }
  const caption = `Tagged groups by region and website language. Language is recorded only for tagged groups, and ${counts.noLanguage} tagged ${counts.noLanguage === 1 ? "group has" : "groups have"} no language recorded. Cells with fewer than ${SMALL_CELL} groups are muted; every count is shown.`;
  section.append(node(doc, "p", "groups-flows__summary", caption));
  const panel = languagePanel(counts);
  const names = Object.fromEntries(panel.columns.map((col) => [col.code, col.name]));
  if (Plot) {
    const plot = Plot.plot({
      width,
      height: 56 + 8 + panel.rows.length * 26,
      marginLeft: 170,
      marginTop: 56,
      marginBottom: 8,
      x: {domain: panel.columns.map((col) => col.code), axis: null},
      y: {domain: panel.rows, axis: null},
      color: {identity: true},
      marks: [
        Plot.axisX({anchor: "top", ticks: panel.columns.map((col) => col.code), tickFormat: (code) => names[code], tickSize: 0, label: null, lineWidth: 6, fontSize: 11}),
        Plot.axisY({ticks: panel.rows, tickSize: 0, label: null, lineWidth: 12, fontSize: 11}),
        Plot.cell(panel.cells, {x: "column", y: "row", fill: "fill", inset: 1, title: "tip"}),
        Plot.text(panel.cells, {x: "column", y: "row", text: "text", fill: "ink", fontSize: 11}),
      ],
    });
    plot.setAttribute("role", "img");
    plot.setAttribute("aria-label", caption);
    section.append(scrollRegion(doc, "groups-flows__chart", "Website languages by region", plot));
  }
  const table = panel.rows.map((region) => ({
    small: false,
    cells: [region, ...panel.columns.map((col) => String(panel.cells.find((c) => c.row === region && c.column === col.code).n))],
  }));
  section.append(detailsWith(doc, "Show the counts as a table", !Plot,
    dataTable(doc, "Website languages by region", ["Region", ...panel.columns.map((col) => col.name)], table)));
  return section;
}

/**
 * Draws the four sections into el: flows, participation, combinations and languages. Plot is the Framework's
 * global, passed in by the page. Without Plot each view falls back to its text summary and table. The page
 * passes groups (groups.json groups) and flows (flows.json); the coverage payload is accepted for the shared
 * call but language counts come from groups.json, which holds the same tagged languages.
 */
export function mountGroupsFlows(el, {flows = null, groups = [], Plot = null, width = 720} = {}) {
  if (!el) return;
  const doc = el.ownerDocument;
  const fit = Math.max(280, Math.min(width, el.clientWidth || width));
  el.replaceChildren();
  el.classList.add("groups-flows");
  el.append(
    sankeySection(doc, groups, flows, Plot, fit),
    participationSection(doc, groups, Plot, fit),
    combinationSection(doc, groups, flows, Plot, fit),
    languageSection(doc, groups, Plot, fit),
  );
}
