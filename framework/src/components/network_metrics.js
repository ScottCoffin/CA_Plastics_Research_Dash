// Collaboration-structure panel on the California network page (BQ-3.4; A3 section 7, Module 3).
// It reads site/data/network_metrics.json (schema bq3-v1, aggregates only) once the panel nears the
// viewport. The chart view draws four headline measures as small multiples, with Authors and
// Institutions side by side and 2026 marked as a partial year. The table view lists every measure for
// every period, one table per graph. The panel reads no author or institution id or name, so it cannot
// name or rank anyone.
import {escapeHtml, formatCount, formatRefresh, loadJson} from "./atlas.js";

const SCHEMA = "bq3-v1";
const NOT_AVAILABLE = "Not available";
const TICKS = [0, 0.5, 1];

const ALL_YEARS = {key: "all", label: "All years"};
const PERIODS = [
  {key: "2011-2015", label: "2011–2015", axis: ["2011–15"]},
  {key: "2016-2020", label: "2016–2020", axis: ["2016–20"]},
  {key: "2021-2025", label: "2021–2025", axis: ["2021–25"]},
  {key: "2026", label: "2026 (partial year)", axis: ["2026", "partial"], partial: true},
];
const TABLE_PERIODS = [ALL_YEARS, ...PERIODS];

const GRAPHS = [
  {key: "authors", label: "Authors", noun: "author", mark: "circle", series: "nm-series--authors"},
  {key: "institutions", label: "Institutions", noun: "institution", mark: "square", series: "nm-series--institutions"},
];

// Definitions shown in the disclosure, in order. The text itself comes from the payload's definitions.
const DEFINITION_KEYS = [
  ["windows", "Periods"],
  ["author_graph", "Authors graph"],
  ["institution_graph", "Institutions graph"],
  ["edge_weight", "Link strength"],
  ["nodes", "Members in the graph"],
  ["edges", "Links"],
  ["components", "Groups"],
  ["components_with_edges", "Groups with two or more members"],
  ["giant_component", "Largest connected group"],
  ["density", "Density"],
  ["average_clustering", "Average clustering"],
  ["isolates", "Members with no link"],
  ["degree", "Partners per member"],
  ["communities", "Clusters"],
  ["modularity", "Modularity"],
  ["cross_institution", "Links across institutions"],
  ["cross_sector", "Links across sectors"],
  ["out_of_region", "Links with one end outside California"],
  ["rounding", "Rounding"],
];

// Chart geometry in SVG user units (the svg scales to its column width).
const VIEW = {width: 360, height: 200};
const PLOT = {left: 46, right: 348, top: 22, bottom: 150};
const STEP = (PLOT.right - PLOT.left) / PERIODS.length;
const xAt = (index) => PLOT.left + STEP * (index + 0.5);
const yAt = (value) => PLOT.bottom - value * (PLOT.bottom - PLOT.top);

const HEADLINES = [
  {
    title: "Largest connected group",
    note: "Share of members who belong to it",
    kind: "share",
    read: (record) => record.giant_component_share,
  },
  {
    title: "Members with no link",
    note: "Share of members who share no work with another member",
    kind: "share",
    read: (record) => record.isolate_share,
  },
  {
    title: "Links reaching outside California",
    note: "Share of links with one end outside California",
    kind: "share",
    read: (record) => (record.out_of_region || {}).fraction,
  },
  {
    title: "Modularity",
    note: "How cleanly the links split into clusters, from 0 to 1",
    kind: "index",
    read: (record) => record.modularity,
  },
];

const DEGREE_ROWS = [
  ["min", "minimum"],
  ["p25", "25th percentile"],
  ["median", "median"],
  ["p75", "75th percentile"],
  ["p90", "90th percentile"],
  ["max", "maximum"],
];

// Formatters: every number shown on the panel goes through one of these, never raw from the payload.
const isNumber = (value) => typeof value === "number" && Number.isFinite(value);
const countText = (value) => (Number.isSafeInteger(value) && value >= 0 ? formatCount(value) : NOT_AVAILABLE);
const percentText = (value) => (isNumber(value) ? `${(value * 100).toFixed(1)}%` : NOT_AVAILABLE);
const decimalText = (digits) => (value) => (isNumber(value) ? value.toFixed(digits) : NOT_AVAILABLE);
const quantileText = (value) => {
  if (!isNumber(value)) return NOT_AVAILABLE;
  return Number.isInteger(value) ? formatCount(value) : value.toFixed(1);
};

// A share with the number of links it was judged on. The count shows how much the share rests on.
function fractionText(part) {
  if (!part || !isNumber(part.fraction)) return NOT_AVAILABLE;
  return `${percentText(part.fraction)} <span class="nm-n">of ${countText(part.edges_considered)} links</span>`;
}

// Table rows: [label, cell(window record) -> HTML].
const TABLE_ROWS = [
  ["Plastic-related works", (record) => countText(record.works)],
  ["Members in the graph", (record) => countText(record.nodes)],
  ["Links between members", (record) => countText(record.edges)],
  ["Groups, including single members", (record) => countText(record.components)],
  ["Groups with two or more members", (record) => countText(record.components_with_edges)],
  ["Members in the largest group", (record) => countText(record.giant_component_nodes)],
  ["Share of members in the largest group", (record) => percentText(record.giant_component_share)],
  ["Density", (record) => decimalText(4)(record.density)],
  ["Average clustering", (record) => decimalText(2)(record.average_clustering)],
  ["Members with no link", (record) => countText(record.isolates)],
  ["Share of members with no link", (record) => percentText(record.isolate_share)],
  ...DEGREE_ROWS.map(([key, text]) => [
    `Partners per member: ${text}`,
    (record) => quantileText((record.degree || {})[key]),
  ]),
  ["Clusters (Louvain method)", (record) => countText(record.communities)],
  ["Modularity", (record) => decimalText(2)(record.modularity)],
  ["Share of links across institutions", (record) => fractionText(record.cross_institution)],
  ["Share of links across sectors", (record) => fractionText(record.cross_sector)],
  ["Share of links with one end outside California", (record) => fractionText(record.out_of_region)],
];

function windowRecord(graph, key) {
  return ((graph && graph.windows) || []).find((record) => record.window === key) || {};
}

function marker(graph, [x, y], partial) {
  const classes = `nm-point ${graph.series}${partial ? " nm-point--partial" : ""}`;
  return graph.mark === "square"
    ? `<rect class="${classes}" x="${x - 3.5}" y="${y - 3.5}" width="7" height="7"/>`
    : `<circle class="${classes}" cx="${x}" cy="${y}" r="3.5"/>`;
}

const KEY_MARKUP = [
  ...GRAPHS.map((graph) => (
    `<li><svg class="nm-key__mark ${graph.series}" viewBox="0 0 28 12" aria-hidden="true" focusable="false">`
    + `<line class="nm-line" x1="2" y1="6" x2="26" y2="6"/>${marker(graph, [14, 6], false)}</svg>`
    + `${graph.label} (${graph.mark === "square" ? "squares" : "circles"})</li>`
  )),
  '<li><svg class="nm-key__mark" viewBox="0 0 28 12" aria-hidden="true" focusable="false">'
    + '<line class="nm-line nm-line--partial" x1="2" y1="6" x2="26" y2="6"/>'
    + '<circle class="nm-point nm-point--partial" cx="14" cy="6" r="3.5"/></svg>'
    + "Dashed line and hollow marker: 2026, a partial year</li>",
];

function periodLabel(period, index) {
  const x = xAt(index);
  const [first, second] = period.axis;
  const secondLine = second ? `<tspan x="${x}" dy="13">${escapeHtml(second)}</tspan>` : "";
  return `<text class="nm-tick" x="${x}" y="${PLOT.bottom + 17}" text-anchor="middle">`
    + `<tspan x="${x}">${escapeHtml(first)}</tspan>${secondLine}</text>`;
}

function seriesMarkup(graph, values) {
  const points = values.map((value, index) => (value === null ? null : [xAt(index), yAt(value)]));
  const solid = points.slice(0, 3).filter(Boolean);
  let markup = "";
  if (solid.length > 1) {
    markup += `<polyline class="nm-line ${graph.series}" points="${solid.map((p) => p.join(",")).join(" ")}"/>`;
  }
  // The segment into 2026 is dashed, because that year is still running.
  if (points[2] && points[3]) {
    markup += `<line class="nm-line nm-line--partial ${graph.series}" x1="${points[2][0]}" y1="${points[2][1]}" `
      + `x2="${points[3][0]}" y2="${points[3][1]}"/>`;
  }
  points.forEach((point, index) => {
    if (point) markup += marker(graph, point, Boolean(PERIODS[index].partial));
  });
  return markup;
}

function headlineFigure(headline, graphs) {
  const shown = (value) => (headline.kind === "share" ? percentText(value) : decimalText(2)(value));
  const tickText = (tick) => (headline.kind === "share" ? `${tick * 100}%` : tick.toFixed(1));
  const series = GRAPHS.map((graph) => ({
    graph,
    values: PERIODS.map((period) => {
      const value = headline.read(windowRecord(graphs[graph.key], period.key));
      return isNumber(value) ? value : null;
    }),
  }));

  const summary = series
    .map(({graph, values}) => (
      `${graph.label}: ${PERIODS.map((period, index) => `${period.label} ${shown(values[index])}`).join(", ")}`
    ))
    .join(". ");

  const band = `<rect class="nm-partial-band" x="${PLOT.left + STEP * 3}" y="${PLOT.top - 6}" `
    + `width="${STEP}" height="${PLOT.bottom - PLOT.top + 6}"/>`;
  const grid = TICKS.map((tick) => {
    const y = yAt(tick);
    const cls = tick === 0 ? "nm-axis" : "nm-grid-line";
    return `<line class="${cls}" x1="${PLOT.left}" x2="${PLOT.right}" y1="${y}" y2="${y}"/>`
      + `<text class="nm-tick" x="${PLOT.left - 6}" y="${y + 4}" text-anchor="end">${tickText(tick)}</text>`;
  }).join("");

  // Value labels: the higher of the two series sits above its point and the lower one below. A lower label
  // that would fall on the axis moves to the right of its point instead; network_metrics.css gives labels a halo.
  const labels = PERIODS.map((_, index) => series.map((entry, k) => {
    const value = entry.values[index];
    if (value === null) return "";
    const other = series[1 - k].values[index];
    const higher = other === null || (k === 0 ? value >= other : value > other);
    const x = xAt(index);
    const y = yAt(value);
    let place = `x="${x}" y="${y - 8}" text-anchor="middle"`;
    if (!higher) {
      place = y + 15 > PLOT.bottom - 4
        ? `x="${x + 7}" y="${y + 4}" text-anchor="start"`
        : `x="${x}" y="${y + 15}" text-anchor="middle"`;
    }
    return `<text class="nm-value ${entry.graph.series}" ${place}>${shown(value)}</text>`;
  }).join("")).join("");

  const lines = series.map((entry) => seriesMarkup(entry.graph, entry.values)).join("");
  const xLabels = PERIODS.map((period, index) => periodLabel(period, index)).join("");
  const description = `${headline.title}, by period. ${summary}.`;

  return `<figure class="nm-mult"><figcaption><strong>${escapeHtml(headline.title)}</strong>`
    + `<span>${escapeHtml(headline.note)}</span></figcaption>`
    + `<svg class="nm-svg" viewBox="0 0 ${VIEW.width} ${VIEW.height}" role="img" `
    + `aria-label="${escapeHtml(description)}" focusable="false">`
    + band + grid + lines + labels + xLabels
    + "</svg></figure>";
}

function chartMarkup(graphs) {
  const key = `<ul class="nm-key" aria-label="Chart key">${KEY_MARKUP.join("")}</ul>`;
  return `${key}<div class="nm-mults">${HEADLINES.map((headline) => headlineFigure(headline, graphs)).join("")}</div>`;
}

function tableMarkup(graph, payloadGraph) {
  const captionId = `nm-caption-${graph.key}`;
  const head = TABLE_PERIODS.map((period) => `<th scope="col">${escapeHtml(period.label)}</th>`).join("");
  const rows = TABLE_ROWS.map(([label, cell]) => (
    `<tr><th scope="row">${escapeHtml(label)}</th>`
    + TABLE_PERIODS.map((period) => `<td class="r">${cell(windowRecord(payloadGraph, period.key))}</td>`).join("")
    + "</tr>"
  )).join("");
  return `<div class="atlas-table-wrap nm-table-wrap" role="region" tabindex="0" aria-labelledby="${captionId}">`
    + `<table class="atlas-table nm-table"><caption id="${captionId}">${escapeHtml(graph.label)}: measures for each period. `
    + `Totals and shares only, and no ${graph.noun} is named.</caption>`
    + `<thead><tr><th scope="col">Measure</th>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

function notesMarkup(payload) {
  const definitions = payload.definitions || {};
  const items = DEFINITION_KEYS
    .filter(([key]) => typeof definitions[key] === "string")
    .map(([key, label]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(definitions[key])}</dd>`)
    .join("");
  return `<p>${escapeHtml(payload.ascertainment_note || "")}</p>`
    + `<h3 class="nm-defs-heading">Definitions</h3><dl class="nm-defs">${items}</dl>`;
}

function statusText(payload) {
  const built = formatRefresh(payload.source && payload.source.index_build_timestamp);
  return `${built ? `Works index built ${built}. ` : ""}The 2026 period is partial: the year is still running.`;
}

function checkPayload(payload) {
  const graphs = payload && payload.graphs;
  if (!payload || payload.schema_version !== SCHEMA || !graphs || !graphs.authors || !graphs.institutions) {
    throw new Error("network_metrics.json does not match the bq3-v1 schema");
  }
  return graphs;
}

function renderPanel(panel, payload) {
  const graphs = checkPayload(payload);
  panel.querySelector("#nm-chart").innerHTML = chartMarkup(graphs);
  panel.querySelector("#nm-table").innerHTML = GRAPHS
    .map((graph) => tableMarkup(graph, graphs[graph.key]))
    .join("");
  panel.querySelector("#nm-notes-body").innerHTML = notesMarkup(payload);
  panel.querySelector("#nm-status").textContent = statusText(payload);
}

async function loadPanel(panel) {
  try {
    renderPanel(panel, await loadJson("network_metrics.json"));
  } catch (error) {
    console.error("Failed to load the collaboration measures.", error);
    panel.querySelector("#nm-status").textContent = "The collaboration measures could not be loaded.";
  }
}

// Chart/Table toggle: a click sets data-view on the card and moves aria-pressed. network_metrics.css shows the pane.
function wireViewToggle(card) {
  const group = card.querySelector(".atlas-segmented");
  group.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-view]");
    if (!button || !group.contains(button)) return;
    card.dataset.view = button.dataset.view;
    for (const other of group.querySelectorAll("button[data-view]")) {
      other.setAttribute("aria-pressed", String(other === button));
    }
  });
}

export function mountNetworkMetrics(root = document) {
  const panel = root.querySelector("#network-metrics");
  if (!panel || panel.dataset.mounted === "true") return;
  panel.dataset.mounted = "true";
  wireViewToggle(panel.querySelector(".nm-card"));

  // Lazy load: fetch the payload once, when the panel is about to scroll into view.
  if (typeof IntersectionObserver !== "function") {
    loadPanel(panel);
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    if (!entries.some((entry) => entry.isIntersecting)) return;
    observer.disconnect();
    loadPanel(panel);
  }, {rootMargin: "600px 0px"});
  observer.observe(panel);
}
