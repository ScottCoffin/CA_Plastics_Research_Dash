// Funding visualizations for the Framework Funding page, ported from the classic grants page
// (site/grants.html). mountFundingViz(container) builds the chart cards once and returns {update(rows),
// onSelect(handler)}; update() redraws every view from the awards that match the page's filter form. The
// views follow the filter form and do not set filters themselves. The Sankey alone has a local drill-down:
// clicking a block (or pressing Enter on it) narrows only the Sankey and its table to the flows through that
// block. The two heatmaps select cells (several cells combine as a union within one heatmap, and the two
// heatmaps combine as an intersection); onSelect hands the page the awards the selection leaves, and only
// the page's awards table follows it.
// Every chart is an Atlas chart card with a Chart/Table control; the table pane is that chart's table
// alternative. The pure markup builders are exported so Node tests can check them.
import {escapeHtml} from "./atlas.js";
import {CHROME} from "./shared/palette.js";
import {helpButtonHtml} from "./shared/tooltip.js";
import {
  DEFAULT_SECTOR_LABELS, FALLBACK_COLOR, FUNDER_COLOR, HEAT_START, SECTOR_COLORS, UNTAGGED, agencyColor, agencyOrder,
  buildHeat, buildSankey, buildSectorTopic, filterByHeatSelection, focusOfNode, heatCellKey, heatFill, inkFor,
  layoutSankey, liveSectorTopicKeys, liveTopicYearKeys, niceMax, pruneHeatSelection, sectorLabelsFor, tileMetrics,
  toggleHeatCell, topOrgs, topicFill, viewRows, yearCounts
} from "./funding_viz_model.js";

const esc = escapeHtml;
const fmtInt = (n) => Math.round(n).toLocaleString("en-US");
const fmtShare = (n) => (Math.abs(n - Math.round(n)) < 0.05 ? fmtInt(n) : n.toFixed(1));
export const fmtUsd = (n) => {
  if (n == null || !isFinite(n)) return "n/a";
  const a = Math.abs(n);
  if (a >= 1e9) return `$${(n / 1e9).toFixed(2)} B`;
  if (a >= 1e6) return `$${(n / 1e6).toFixed(1)} M`;
  if (a >= 1e3) return `$${Math.round(n / 1e3).toLocaleString("en-US")} K`;
  return `$${Math.round(n)}`;
};
const fmtUsdFull = (n) => (n == null ? "" : `$${Math.round(n).toLocaleString("en-US")}`);
const AMOUNT_CAVEAT = "source bases differ";

// Atlas icon as a sprite reference. Pure markup, so the Node tests can build the static frame.
const iconHtml = (name) => `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-${name}"></use></svg>`;

// Static frames. A loading tile reserves the stat-tile height before the awards arrive.
const LOADING_TILE = '<div class="atlas-kpi atlas-kpi--loading" aria-hidden="true"><dt class="atlas-kpi__label">&nbsp;</dt><dd class="atlas-kpi__value">&nbsp;</dd></div>';

const HEAT_INTRO = "Awards per cell. An award with several topics counts once in each of its topics.";
// Host element of each heatmap's grid, by its cell kind.
const HEAT_HOST = {"topic-year": "heat", "sector-topic": "matrix"};

// The selection line above a heatmap: "N cells selected · Clear". paintHeats() keeps its text and button in step.
function heatSelectionHtml(kind) {
  return `<div class="fv-heat-selection" data-heat-selection="${kind}"><p class="fv-heat-status">`
    + '<span class="fv-heat-count" role="status" aria-live="polite">No cells selected.</span>'
    + '<span class="fv-heat-sep" aria-hidden="true" hidden> · </span>'
    + `<button type="button" class="fv-heat-clear" data-heat="${kind}" hidden>Clear</button></p></div>`;
}

// One chart card: title, source line, the Chart/Table control, then a Chart pane and a Table pane.
// setView() shows one pane; the table pane starts hidden. Each [data-fv] host is filled by update().
function chartCard({id, title, source, intro, extra = "", chart, table, help = ""}) {
  const heading = help ? `<div class="atlas-help-row"><h2 id="${id}">${title}</h2>${help}</div>` : `<h2 id="${id}">${title}</h2>`;
  return `<section class="atlas-chart" aria-labelledby="${id}">`
    + `<div class="atlas-chart__head"><div>${heading}<p class="atlas-chart__source">${source}</p></div>`
    + `<div class="atlas-segmented" role="group" aria-label="Chart or table view: ${title}">`
    + '<button type="button" data-view="chart" aria-pressed="true">Chart</button>'
    + '<button type="button" data-view="table" aria-pressed="false">Table</button></div></div>'
    + `<div class="atlas-chart__body"><p class="fv-intro">${intro}</p>${extra}`
    + `<div data-fv-pane="chart">${chart}</div><div data-fv-pane="table" hidden>${table}</div></div>`
    + "</section>";
}

const VIZ_SKELETON = '<section class="fv-tiles" data-fv-section="tiles" aria-labelledby="fv-tiles-h">'
  + '<h2 id="fv-tiles-h" class="fv-sr-only">Summary of the filtered awards</h2>'
  + `<dl class="atlas-kpis" data-fv="tiles">${LOADING_TILE.repeat(5)}</dl></section>`
  + chartCard({
    id: "fv-sankey-h",
    title: "Funder, sector, organisation and topic",
    help: helpButtonHtml("Ribbons show how awards flow from funder to sector, organisation and topic; ribbon width counts awards unless you choose reported amounts, which follow each source's own basis and are not comparable. Click a block to show only the flows through it.", {align: "start"}),
    source: "Source: the awards in the filtered list.",
    intro: "Each ribbon is a group of awards. Hover over a ribbon or a block to see its totals. Click a block (or press Enter on it) to show only the flows that pass through it; click it again to show all flows. The filters above change this view.",
    extra: `<div class="atlas-callout atlas-callout--caution">${iconHtml("alert")}<p><strong>Read amounts with care.</strong> Amounts follow each source's own basis, are not comparable or additive across sources, and some awards have no amount. Ribbon width therefore defaults to the number of awards.</p></div>`
      + '<div class="fv-controls">'
      + '<fieldset class="fv-fieldset"><legend>Ribbon width</legend>'
      + '<label><input type="radio" name="fv-width" value="awards" checked> Number of awards</label>'
      + '<label><input type="radio" name="fv-width" value="amount"> Reported amount (USD, not comparable across sources)</label>'
      + "</fieldset>"
      + '<label><input type="checkbox" class="fv-orgs" checked> Show recipient organisations</label>'
      + '<label class="fv-topn">Organisations per sector <input type="range" class="fv-topn-input" min="3" max="15" value="6"> <output class="fv-topn-out">6</output></label>'
      + "</div>",
    chart: '<p class="fv-note" data-fv="amount-note" hidden></p>'
      + '<div class="fv-focus-bar" data-fv="sankey-focus"><p class="fv-focus-text" role="status" aria-live="polite"></p><button type="button" class="fv-focus-clear" hidden>Show all flows</button></div>'
      + '<div class="fv-sankey-wrap" data-fv="sankey" role="region" aria-label="Sankey diagram, scrollable" tabindex="0"></div>'
      + '<p class="fv-note">Awards with several topics split their weight equally across those topics (an award with two topics adds one half to each). Awards with no topic go to "Untagged". Within each sector the organisation column shows the largest recipients, and the rest are grouped as "Other" with the sector name.</p>',
    table: '<div class="fv-scroll" data-fv="sankey-table" role="region" aria-label="Sankey values as a table, scrollable" tabindex="0"></div>'
  })
  + chartCard({
    id: "fv-year-h",
    title: "Awards per fiscal year, by funder agency",
    source: "Source: the awards in the filtered list, by fiscal year.",
    intro: "Count of awards in each fiscal year, stacked by funder agency.",
    chart: '<ul class="fv-legend" data-fv="year-legend" aria-label="Funder agencies"></ul><div class="fv-scroll" data-fv="year-chart"></div>',
    table: '<div class="fv-scroll" data-fv="year-table" role="region" aria-label="Awards per fiscal year as a table, scrollable" tabindex="0"></div>'
  })
  + chartCard({
    id: "fv-org-h",
    title: "Top recipient organisations",
    source: "Source: the awards in the filtered list, by recipient organisation.",
    intro: "Number of awards for the twelve organisations with the most awards in the filtered list.",
    chart: '<div data-fv="orgs"></div>',
    table: '<div data-fv="orgs-table"></div>'
  })
  + chartCard({
    id: "fv-heat-h",
    title: "Topic by fiscal year",
    source: "Source: the awards in the filtered list, by topic and fiscal year.",
    intro: `${HEAT_INTRO} Click cells to show only their awards in the awards table below.`,
    extra: heatSelectionHtml("topic-year"),
    chart: '<div data-fv="heat"></div>',
    table: '<div data-fv="heat-table"></div>'
  })
  + chartCard({
    id: "fv-matrix-h",
    title: "Recipient sector by topic",
    source: "Source: the awards in the filtered list, by recipient sector and topic.",
    intro: `${HEAT_INTRO} Click cells to show only their awards in the awards table below.`,
    extra: heatSelectionHtml("sector-topic"),
    chart: '<div data-fv="matrix"></div>',
    table: '<div data-fv="matrix-table"></div>'
  });

// Exposed for the Node and pytest contract checks on the static frame.
export {VIZ_SKELETON};

function region(html, label) {
  return `<div class="fv-scroll" role="region" aria-label="${esc(label)}" tabindex="0">${html}</div>`;
}

function emptyText(text) {
  return `<p class="fv-empty">${esc(text)}</p>`;
}

// ---- Markup builders (pure) -------------------------------------------------------------------

// Stat tiles: the <dl class="atlas-kpis"> host is already in the page; these are its children.
export function tilesHtml(m) {
  const tile = (icon, title, value, note) => `<div class="atlas-kpi"><dt class="atlas-kpi__label">${iconHtml(icon)}${title}</dt>`
    + `<dd class="atlas-kpi__value">${value}</dd>${note ? `<dd class="atlas-kpi__note">${note}</dd>` : ""}</div>`;
  return tile("coins", "Awards", fmtInt(m.awards))
    + tile("scale", "Funder agencies", fmtInt(m.funders))
    + tile("building", "Recipient organisations", fmtInt(m.orgs))
    + tile("grid", "Sectors", fmtInt(m.sectors))
    + tile("home", "California-led", m.awards ? `${Math.round(m.caShare * 100)}%` : "n/a", "share of awards led from California");
}

function kindLabel(n) {
  if (n.type === "agency") return "Funder agency";
  if (n.type === "sector") return "Sector";
  if (n.type === "topic") return "Topic";
  return "Recipient organisation";
}

function valueText(value, amount) {
  return amount ? `${fmtUsd(value)} reported (${AMOUNT_CAVEAT})` : `${fmtShare(value)} awards`;
}

function nodeFill(n, T) {
  if (n.type === "agency") return FUNDER_COLOR;
  if (n.type === "sector") return SECTOR_COLORS[n.key] || FALLBACK_COLOR;
  if (n.type === "topic") return topicFill(n.key, T);
  return SECTOR_COLORS[n.sector] || FALLBACK_COLOR;
}

function linkFill(l, T) {
  const t = l.t;
  if (t.type === "topic") return topicFill(t.key, T);
  if (t.type === "sector") return SECTOR_COLORS[t.key] || FALLBACK_COLOR;
  return SECTOR_COLORS[t.sector] || FALLBACK_COLOR;
}

// SVG Sankey with a title per ribbon and per block. Each block is a button (Enter or click toggles the
// drill-down); focusId marks the block that is drilled into. The caller puts it in a horizontally
// scrolling box.
export function sankeySvg(graph, width, {T = null, amount = false, focusId = null} = {}) {
  const count = Math.max(...Array.from({length: graph.ncols}, (_, c) => graph.nodes.filter((n) => n.col === c).length));
  const height = Math.min(1000, Math.max(420, count * 24 + 40));
  const L = layoutSankey(graph, {width, height, marginLeft: 120, marginRight: 190});
  const heads = graph.withOrgs
    ? ["Funder agency", "Recipient sector", "Recipient organisation", "Topic"]
    : ["Funder agency", "Recipient sector", "Topic"];
  const parts = [
    `<svg class="fv-sankey-svg" width="${L.width}" height="${L.height}" viewBox="0 0 ${L.width} ${L.height}" role="group" aria-labelledby="fv-sankey-title">`,
    `<title id="fv-sankey-title">Sankey diagram of funder agencies, recipient sectors, organisations and topics</title>`
  ];
  heads.forEach((h, i) => {
    const x = L.nodes.find((n) => n.col === i);
    if (x) parts.push(`<text class="fv-col-head" x="${i === 0 ? x.x + x.w : x.x}" y="14" text-anchor="${i === 0 ? "end" : "start"}">${esc(h)}</text>`);
  });
  parts.push("<g>");
  L.links.forEach((l) => {
    const text = `${l.s.name} to ${l.t.name}: ${valueText(l.value, amount)}`;
    parts.push(`<path class="fv-link" d="${l.d}" stroke="${linkFill(l, T)}" stroke-width="${Math.max(l.width, 0.6).toFixed(2)}"><title>${esc(text)}</title></path>`);
  });
  parts.push("</g><g>");
  const total = graph.total || 1;
  const lastBottom = new Map();
  L.nodes.slice().sort((a, b) => a.col - b.col || a.y - b.y).forEach((n) => {
    const first = n.col === 0, last = n.col === graph.ncols - 1;
    const cy = n.y + n.h / 2;
    const prev = lastBottom.has(n.col) ? lastBottom.get(n.col) : -1e9;
    let labelMarkup = "", visibleLabel = "";
    if (cy - 7 >= prev) {
      const maxc = first ? 17 : last ? 24 : 26;
      const name = n.name.length > maxc ? `${n.name.slice(0, maxc - 1)}…` : n.name;
      visibleLabel = name;
      labelMarkup = `<text class="fv-label" x="${first ? n.x - 6 : n.x + n.w + 6}" y="${(cy + 4).toFixed(1)}" text-anchor="${first ? "end" : "start"}">${esc(name)}</text>`;
      lastBottom.set(n.col, cy + 7);
    }
    const share = ((n.value / total) * 100).toFixed(1);
    const text = `${n.name} (${kindLabel(n)}): ${fmtInt(n.count)} awards, ${share}% of ${amount ? "reported amount" : "award weight"}`
      + (n.amountW ? `; ${fmtUsd(n.amountW)} reported (${AMOUNT_CAVEAT})` : "");
    const focused = n.id === focusId;
    const action = focused ? "Selected. Press Enter to show all flows." : "Press Enter to show only flows through this block.";
    const ariaLabel = `${visibleLabel ? `${visibleLabel}. ` : ""}${text}. ${action}`;
    parts.push(`<g class="fv-node${focused ? " is-focus" : ""}" data-id="${esc(n.id)}" tabindex="0" role="button" `
      + `aria-pressed="${focused ? "true" : "false"}" aria-label="${esc(ariaLabel)}"><title>${esc(text)}</title>`
      + `<rect x="${n.x}" y="${n.y.toFixed(2)}" width="${n.w}" height="${n.h.toFixed(2)}" fill="${nodeFill(n, T)}"></rect>${labelMarkup}</g>`);
  });
  parts.push("</g></svg>");
  return parts.join("");
}

// Table alternative to the Sankey: one row per ribbon.
export function sankeyTableHtml(graph, amount = false) {
  const nameOf = new Map(graph.nodes.map((n) => [n.id, n]));
  const total = graph.total || 1;
  const rows = graph.links.slice().sort((a, b) => a.source.localeCompare(b.source) || b.value - a.value).map((l) => {
    const a = nameOf.get(l.source), b = nameOf.get(l.target);
    return `<tr><td class="fv-name">${esc(a.name)} <span class="fv-muted">(${kindLabel(a)})</span></td>`
      + `<td class="fv-name">${esc(b.name)} <span class="fv-muted">(${kindLabel(b)})</span></td>`
      + `<td class="num">${amount ? fmtUsdFull(l.value) : fmtShare(l.value)}</td>`
      + `<td class="num">${((l.value / total) * 100).toFixed(1)}%</td></tr>`;
  }).join("");
  return `<table class="fv-sankey-table"><caption class="fv-sr-only">Sankey ribbons: from, to, ${amount ? "reported amount" : "awards"} and share</caption>`
    + `<thead><tr><th scope="col">From</th><th scope="col">To</th><th scope="col" class="num">${amount ? "Reported amount (USD)" : "Awards (split across topics)"}</th><th scope="col" class="num">Share</th></tr></thead>`
    + `<tbody>${rows}</tbody></table>`;
}

// Stacked bars per fiscal year. width is the drawing width in CSS pixels.
export function yearChartSvg(yc, width) {
  const n = yc.years.length;
  const W = width, H = 260, ml = 38, mr = 8, mt = 8, mb = 28;
  const pw = W - ml - mr, ph = H - mt - mb, top = niceMax(yc.max);
  const bw = pw / n;
  const y = (v) => mt + ph - (v / top) * ph;
  const parts = [`<svg class="fv-year-svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="fv-year-title">`,
    `<title id="fv-year-title">Stacked bar chart of awards per fiscal year by funder agency</title><g class="fv-axis">`];
  [0, top / 2, top].forEach((t) => {
    parts.push(`<line x1="${ml}" x2="${W - mr}" y1="${y(t)}" y2="${y(t)}" stroke="${CHROME.grid}"></line>`
      + `<text x="${ml - 5}" y="${y(t) + 4}" text-anchor="end">${fmtShare(t)}</text>`);
  });
  const step = Math.max(1, Math.ceil((n * 30) / pw));
  yc.years.forEach((yr, i) => {
    if (i % step === 0) parts.push(`<text x="${ml + bw * i + bw / 2}" y="${H - 10}" text-anchor="middle">${yr.year}</text>`);
  });
  parts.push("</g>");
  yc.years.forEach((yr, i) => {
    let acc = 0;
    yr.segs.forEach((s) => {
      const y0 = y(acc + s.n), h = y(acc) - y0;
      parts.push(`<rect x="${(ml + bw * i + bw * 0.12).toFixed(1)}" y="${y0.toFixed(1)}" width="${(bw * 0.76).toFixed(1)}" height="${Math.max(h, 0).toFixed(1)}" fill="${agencyColor(s.agency)}" stroke="${CHROME.surface}" stroke-width="2"><title>${yr.year}, ${esc(s.agency)}: ${s.n} awards</title></rect>`);
      acc += s.n;
    });
  });
  parts.push("</svg>");
  return parts.join("");
}

export function yearTableHtml(yc, present) {
  const head = present.map((a) => `<th scope="col" class="num">${esc(a)}</th>`).join("");
  const body = yc.years.map((yr) => `<tr><th scope="row">${yr.year}</th>${present.map((a) => {
    const s = yr.segs.find((x) => x.agency === a);
    return `<td class="num">${s ? s.n : 0}</td>`;
  }).join("")}<td class="num">${yr.total}</td></tr>`).join("");
  return `<table><caption class="fv-sr-only">Awards per fiscal year and funder agency</caption>`
    + `<thead><tr><th scope="col">Fiscal year</th>${head}<th scope="col" class="num">Total</th></tr></thead><tbody>${body}</tbody></table>`;
}

export function orgListHtml(list, labels) {
  if (!list.length) return emptyText("No awards match the current filters.");
  const max = list[0].n;
  return `<ol class="fv-orgs-list">${list.map((o) => `<li><span class="fv-org-name">${esc(o.name)}</span>`
    + `<span class="atlas-badge atlas-badge--muted">${esc(labels[o.sector] || o.sector)}</span>`
    + `<span class="fv-bar" aria-hidden="true"><span style="width:${((o.n / max) * 100).toFixed(1)}%"></span></span>`
    + `<span class="fv-count">${o.n} ${o.n === 1 ? "award" : "awards"}</span></li>`).join("")}</ol>`;
}

// Table alternative to the organisation bars: one row per organisation, in the same order.
export function orgTableHtml(list, labels) {
  if (!list.length) return emptyText("No awards match the current filters.");
  const body = list.map((o) => `<tr><th scope="row">${esc(o.name)}</th><td>${esc(labels[o.sector] || o.sector)}</td><td class="num">${o.n}</td></tr>`).join("");
  return region(`<table><caption class="fv-sr-only">Top recipient organisations by number of awards</caption>`
    + `<thead><tr><th scope="col">Recipient organisation</th><th scope="col">Sector</th><th scope="col" class="num">Awards</th></tr></thead><tbody>${body}</tbody></table>`,
  "Top recipient organisations as a table, scrollable");
}

function dotHtml(key, T) {
  return `<span class="fv-dot" aria-hidden="true" style="background:${topicFill(key, T, true)}"></span>`;
}

// A heatmap cell is coloured by its count. The plain variant (the table pane) keeps the same numbers
// without the fill, so the table reads the same with or without colour. A chart cell is a button: a click
// selects it (aria-pressed, a check mark and a 2 px ink outline). A cell with no awards is disabled.
function heatCell(n, max, {plain = false, kind = "", row = "", col = "", label = "", pressed = false} = {}) {
  if (plain) return `<td class="num">${n}</td>`;
  const fill = heatFill(n, max);
  const style = `background:${fill};color:${inkFor(fill)}`;
  const name = `${label}: ${n ? `${n} ${n === 1 ? "award" : "awards"}` : "no awards"}. Visible count: ${n}.`;
  if (!n) return `<td><button type="button" class="fv-cell" style="${style}" disabled aria-label="${esc(name)}">${n}</button></td>`;
  return `<td><button type="button" class="fv-cell" data-heat="${kind}" data-row="${esc(row)}" data-col="${esc(col)}" `
    + `aria-pressed="${pressed ? "true" : "false"}" style="${style}" aria-label="${esc(name)}">`
    + `<span class="fv-check" aria-hidden="true">${pressed ? "✓ " : ""}</span>${n}</button></td>`;
}

export function heatTableHtml(h, T, {plain = false, selected = new Set()} = {}) {
  if (!h.rows.length) return emptyText("No dated awards match the current filters.");
  const colName = (c) => (c === "pre" ? `Before ${HEAT_START}` : String(c));
  const head = h.cols.map((c) => `<th scope="col">${esc(colName(c))}</th>`).join("");
  const body = h.rows.map((r) => {
    const cells = r.counts.map((n, i) => heatCell(n, h.max, {
      plain, kind: "topic-year", row: r.key, col: h.cols[i], label: `${r.label}, ${colName(h.cols[i])}`,
      pressed: selected.has(heatCellKey(r.key, h.cols[i]))
    })).join("");
    return `<tr><th scope="row">${dotHtml(r.key, T)}${esc(r.label)}</th>${cells}</tr>`;
  }).join("");
  return region(`<table class="fv-matrix"><caption class="fv-sr-only">Awards per topic and fiscal year</caption>`
    + `<thead><tr><th scope="col">Topic</th>${head}</tr></thead><tbody>${body}</tbody></table>`,
  plain ? "Topic by fiscal year table, scrollable" : "Topic by fiscal year heatmap, scrollable");
}

export function matrixTableHtml(m, labels, T, {plain = false, selected = new Set()} = {}) {
  if (!m.sectors.length) return emptyText("No awards match the current filters.");
  const topicName = (t) => (t === UNTAGGED ? "Untagged" : T ? T.label(t) : t);
  const head = m.topics.map((t) => `<th scope="col">${dotHtml(t, T)}${esc(topicName(t))}</th>`).join("");
  const body = m.sectors.map((s, i) => {
    const cells = m.grid[i].map((n, j) => heatCell(n, m.max, {
      plain, kind: "sector-topic", row: s, col: m.topics[j], label: `${labels[s] || s}, ${topicName(m.topics[j])}`,
      pressed: selected.has(heatCellKey(s, m.topics[j]))
    })).join("");
    return `<tr><th scope="row">${esc(labels[s] || s)}</th>${cells}</tr>`;
  }).join("");
  return region(`<table class="fv-matrix"><caption class="fv-sr-only">Awards per recipient sector and topic</caption>`
    + `<thead><tr><th scope="col">Recipient sector</th>${head}</tr></thead><tbody>${body}</tbody></table>`,
  plain ? "Recipient sector by topic table, scrollable" : "Recipient sector by topic heatmap, scrollable");
}

// ---- Mount ------------------------------------------------------------------------------------

// Mounts the visualizations into container once. update(rows, sectorLabels) redraws every view.
export function mountFundingViz(container) {
  if (!container) throw new Error("mountFundingViz needs a container element");
  const T = globalThis.AtlasTopics || null;
  container.classList.add("fv-root");
  container.innerHTML = VIZ_SKELETON;
  const host = (name) => container.querySelector(`[data-fv="${name}"]`);
  // raw: the awards as passed to update() (vrows is the same list in the same order, as viewRows keeps it).
  // heat: the selected cells of each heatmap. onSelect: the page's handler for the awards the selection leaves.
  const state = {
    vrows: [], raw: [], labels: DEFAULT_SECTOR_LABELS, mode: "awards", orgs: true, topN: 6, width: 0, focus: null, graph: null,
    heat: {"topic-year": new Set(), "sector-topic": new Set()}, onSelect: null
  };

  function renderSankey() {
    const amount = state.mode === "amount";
    const opts = {mode: state.mode, topN: state.topN, orgs: state.orgs, sectorLabels: state.labels, T};
    let graph = buildSankey(state.vrows, {...opts, focus: state.focus});
    const block = state.focus ? graph.nodes.find((n) => n.id === state.focus.id) : null;
    if (state.focus && !block) {
      // The drill-down block has gone (a filter, the organisation cap or the amount mode removed it).
      state.focus = null;
      graph = buildSankey(state.vrows, opts);
    }
    if (block) state.focus = focusOfNode(block);
    state.graph = graph;
    const note = host("amount-note");
    note.hidden = !amount;
    note.innerHTML = amount
      ? `<strong>Showing reported amounts (USD), which are not comparable across sources.</strong> ${fmtInt(graph.excluded)} of ${fmtInt(state.vrows.length)} filtered awards have no reported amount and are excluded from this view.`
      : "";
    container.querySelector(".fv-topn").hidden = !state.orgs;
    const wrap = host("sankey");
    const table = host("sankey-table");
    const bar = host("sankey-focus");
    // The status line stays in the page (a live region that starts hidden is often not announced);
    // only the clear button is hidden when nothing is drilled into.
    bar.querySelector(".fv-focus-clear").hidden = !block;
    bar.querySelector(".fv-focus-text").innerHTML = block
      ? `Showing only flows through ${esc(block.name)} (${kindLabel(block).toLowerCase()}).`
      : "";
    if (!graph.nodes.length) {
      wrap.innerHTML = emptyText(amount ? "No awards with a reported amount match the current filters." : "No awards match the current filters.");
      table.innerHTML = "";
      return;
    }
    wrap.innerHTML = sankeySvg(graph, Math.max(760, wrap.clientWidth || 800), {T, amount, focusId: block ? block.id : null});
    table.innerHTML = sankeyTableHtml(graph, amount);
  }

  function renderYears() {
    const order = agencyOrder(state.vrows);
    const yc = yearCounts(state.vrows, order);
    const present = order.filter((a) => yc.years.some((y) => y.segs.some((s) => s.agency === a)));
    host("year-legend").innerHTML = present.map((a) => `<li><i style="background:${agencyColor(a)}"></i>${esc(a)}</li>`).join("");
    const chart = host("year-chart");
    const table = host("year-table");
    if (!yc.years.length) {
      chart.innerHTML = emptyText("No dated awards match the current filters.");
      table.innerHTML = "";
      return;
    }
    const width = Math.max(Math.min(chart.clientWidth || 560, 900), 300);
    const undated = yc.undated
      ? `<p class="fv-note">${fmtInt(yc.undated)} filtered ${yc.undated === 1 ? "award has" : "awards have"} no fiscal year and ${yc.undated === 1 ? "is" : "are"} not shown here.</p>`
      : "";
    chart.innerHTML = yearChartSvg(yc, width) + undated;
    table.innerHTML = yearTableHtml(yc, present);
  }

  // Both heatmaps count the awards that match the page filters; their selections narrow only the awards table.
  // A selected cell that is empty (or gone) after a filter change is dropped; the other cells stay selected.
  function renderHeats() {
    const heat = buildHeat(state.vrows, T);
    const matrix = buildSectorTopic(state.vrows, T);
    state.heat["topic-year"] = pruneHeatSelection(state.heat["topic-year"], liveTopicYearKeys(heat));
    state.heat["sector-topic"] = pruneHeatSelection(state.heat["sector-topic"], liveSectorTopicKeys(matrix));
    host("heat").innerHTML = heatTableHtml(heat, T, {selected: state.heat["topic-year"]});
    host("heat-table").innerHTML = heatTableHtml(heat, T, {plain: true});
    host("matrix").innerHTML = matrixTableHtml(matrix, state.labels, T, {selected: state.heat["sector-topic"]});
    host("matrix-table").innerHTML = matrixTableHtml(matrix, state.labels, T, {plain: true});
    paintHeats();
  }

  // Keeps the pressed cells, the selection line and its Clear button in step with state.heat. It edits the
  // markup in place, so keyboard focus stays on the cell that was pressed.
  function paintHeats() {
    for (const kind of Object.keys(state.heat)) {
      const selected = state.heat[kind];
      container.querySelectorAll(`button.fv-cell[data-heat="${kind}"]`).forEach((button) => {
        const pressed = selected.has(heatCellKey(button.dataset.row, button.dataset.col));
        button.setAttribute("aria-pressed", String(pressed));
        button.querySelector(".fv-check").textContent = pressed ? "✓ " : "";
      });
      const bar = container.querySelector(`[data-heat-selection="${kind}"]`);
      const count = selected.size;
      bar.querySelector(".fv-heat-count").textContent = count ? `${count} ${count === 1 ? "cell" : "cells"} selected` : "No cells selected.";
      bar.querySelector(".fv-heat-sep").hidden = !count;
      bar.querySelector(".fv-heat-clear").hidden = !count;
    }
  }

  // Tells the page which awards the heatmap selections leave (null when no cell is selected). The page's
  // awards table shows those awards; the charts above keep following the page filters only.
  function publish() {
    if (!state.onSelect) return;
    const heat = {topicYear: state.heat["topic-year"], sectorTopic: state.heat["sector-topic"]};
    if (!heat.topicYear.size && !heat.sectorTopic.size) {
      state.onSelect(null);
      return;
    }
    const kept = new Set(filterByHeatSelection(state.vrows, heat));
    state.onSelect(state.raw.filter((_, i) => kept.has(state.vrows[i])));
  }

  function setHeat(kind, next) {
    state.heat[kind] = next;
    paintHeats();
    publish();
  }

  function renderAll() {
    host("tiles").innerHTML = tilesHtml(tileMetrics(state.vrows));
    renderSankey();
    renderYears();
    const orgs = topOrgs(state.vrows, 12);
    host("orgs").innerHTML = orgListHtml(orgs, state.labels);
    host("orgs-table").innerHTML = orgTableHtml(orgs, state.labels);
    renderHeats();
    state.width = container.clientWidth;
  }

  // Chart/Table control: the card shows one pane. A hidden pane has no width to draw into, so the views
  // are redrawn when the chart pane comes back.
  function setView(button) {
    const card = button.closest(".atlas-chart");
    const view = button.dataset.view;
    card.querySelectorAll("button[data-view]").forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
    card.querySelectorAll("[data-fv-pane]").forEach((pane) => {
      pane.hidden = pane.dataset.fvPane !== view;
    });
    if (view === "chart" && state.vrows.length) renderAll();
  }

  container.addEventListener("change", (event) => {
    const target = event.target;
    if (target.name === "fv-width") {
      state.mode = target.value === "amount" ? "amount" : "awards";
      renderSankey();
    } else if (target.classList.contains("fv-orgs")) {
      state.orgs = target.checked;
      renderSankey();
    }
  });
  container.addEventListener("input", (event) => {
    const target = event.target;
    if (!target.classList.contains("fv-topn-input")) return;
    state.topN = Number(target.value);
    container.querySelector(".fv-topn-out").textContent = target.value;
    renderSankey();
  });
  // Sankey drill-down. A block toggles the focus on itself (a click, or Enter or Space on its keyboard focus).
  // The Sankey redraws, and keyboard focus returns to the same block, or to the Sankey box if it has gone.
  const cssEscape = (value) => (typeof CSS !== "undefined" && CSS.escape ? CSS.escape(value) : String(value).replace(/["\\]/g, "\\$&"));
  function restoreFocus(id) {
    const wrap = host("sankey");
    const el = id == null ? null : wrap.querySelector(`.fv-node[data-id="${cssEscape(id)}"]`);
    (el || wrap).focus({preventScroll: true});
  }
  function toggleFocus(id) {
    const node = state.graph && state.graph.nodes.find((n) => n.id === id);
    if (!node) return;
    state.focus = state.focus && state.focus.id === id ? null : focusOfNode(node);
    renderSankey();
    restoreFocus(id);
  }
  function clearFocus() {
    if (!state.focus) return;
    state.focus = null;
    renderSankey();
    restoreFocus(null);
  }
  container.addEventListener("click", (event) => {
    const target = event.target;
    const view = target.closest("button[data-view]");
    if (view) {
      setView(view);
      return;
    }
    if (target.closest(".fv-focus-clear")) {
      clearFocus();
      return;
    }
    const cell = target.closest("button.fv-cell[data-heat]");
    if (cell) {
      if (!cell.disabled) setHeat(cell.dataset.heat, toggleHeatCell(state.heat[cell.dataset.heat], heatCellKey(cell.dataset.row, cell.dataset.col)));
      return;
    }
    const clear = target.closest("button.fv-heat-clear");
    if (clear) {
      if (state.heat[clear.dataset.heat].size) setHeat(clear.dataset.heat, new Set());
      // The Clear button hides once nothing is selected, so keyboard focus moves to that heatmap's table.
      const region = host(HEAT_HOST[clear.dataset.heat]).firstElementChild;
      if (region) region.focus({preventScroll: true});
      return;
    }
    const node = target.closest(".fv-node");
    if (node) toggleFocus(node.getAttribute("data-id"));
  });
  container.addEventListener("keydown", (event) => {
    const wrap = host("sankey");
    if (!wrap.contains(event.target)) return;
    const node = event.target.closest(".fv-node");
    if (node && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      toggleFocus(node.getAttribute("data-id"));
    } else if (event.key === "Escape") {
      clearFocus();
    }
  });

  // The Sankey and year chart size themselves from the container width, so redraw when it changes.
  if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(() => {
      if (container.clientWidth !== state.width && state.vrows.length) renderAll();
    }).observe(container);
  }

  return {
    update(rows, sectorLabels) {
      state.raw = Array.isArray(rows) ? rows : [];
      state.vrows = viewRows(state.raw, T);
      state.labels = sectorLabelsFor(sectorLabels);
      renderAll();
      publish();
    },
    // handler(rows) runs on every heatmap selection change and on every update(). rows are the awards the
    // selection leaves, in the order given to update(); null means no cell is selected.
    onSelect(handler) {
      state.onSelect = typeof handler === "function" ? handler : null;
    },
    // Empties both heatmap selections (the page's "Reset all filters").
    clearSelection() {
      for (const kind of Object.keys(state.heat)) if (state.heat[kind].size) setHeat(kind, new Set());
    }
  };
}
