// Funding visualizations for the Framework Funding page, ported from the classic grants page
// (site/grants.html). mountFundingViz(container) builds the controls once and returns {update(rows)};
// update() redraws every view from the awards that match the page's filter form. The views are
// read-only: they follow the filter form and do not set filters themselves. Each chart has a table
// alternative. The pure markup builders are exported so Node tests can check them.
import {escapeHtml} from "./atlas.js";
import {
  DEFAULT_SECTOR_LABELS, FALLBACK_COLOR, FUNDER_COLOR, HEAT_START, SECTOR_COLORS, UNTAGGED, agencyColor, agencyOrder,
  buildHeat, buildSankey, buildSectorTopic, heatFill, inkFor, layoutSankey, niceMax, sectorLabelsFor, tileMetrics,
  topOrgs, topicFill, viewRows, yearCounts
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

// Static controls and section frames. Each [data-fv] host is filled by update().
const SKELETON = `
<div class="fv-section" data-fv-section="tiles">
  <h3 id="fv-tiles-h">Summary of the filtered awards</h3>
  <div data-fv="tiles"></div>
</div>
<section class="fv-section" aria-labelledby="fv-sankey-h">
  <h3 id="fv-sankey-h">Funder, sector, organisation and topic</h3>
  <p class="fv-intro">Each ribbon is a group of awards. Hover over a ribbon or a block to see its totals. The filters above change this view.</p>
  <p class="fv-caveat"><strong>Read amounts with care.</strong> Amounts follow each source's own basis, are not comparable or additive across sources, and some awards have no amount. Ribbon width therefore defaults to the number of awards.</p>
  <div class="fv-controls">
    <fieldset class="fv-fieldset"><legend>Ribbon width</legend>
      <label><input type="radio" name="fv-width" value="awards" checked> Number of awards</label>
      <label><input type="radio" name="fv-width" value="amount"> Reported amount (USD, not comparable across sources)</label>
    </fieldset>
    <label><input type="checkbox" class="fv-orgs" checked> Show recipient organisations</label>
    <label class="fv-topn">Organisations per sector <input type="range" class="fv-topn-input" min="3" max="15" value="6"> <output class="fv-topn-out">6</output></label>
  </div>
  <p class="fv-note" data-fv="amount-note" hidden></p>
  <div class="fv-sankey-wrap" data-fv="sankey" role="region" aria-label="Sankey diagram, scrollable" tabindex="0"></div>
  <p class="fv-note">Awards with several topics split their weight equally across those topics (an award with two topics adds one half to each). Awards with no topic go to "Untagged". Within each sector the organisation column shows the largest recipients, and the rest are grouped as "Other" with the sector name.</p>
  <details class="fv-details"><summary>View the Sankey as a table</summary><div class="fv-scroll" data-fv="sankey-table" role="region" aria-label="Sankey values as a table, scrollable" tabindex="0"></div></details>
</section>
<section class="fv-section" aria-labelledby="fv-year-h">
  <h3 id="fv-year-h">Awards per fiscal year, by funder agency</h3>
  <p class="fv-intro">Count of awards in each fiscal year, stacked by funder agency.</p>
  <ul class="fv-legend" data-fv="year-legend" aria-label="Funder agencies"></ul>
  <div class="fv-scroll" data-fv="year-chart"></div>
  <details class="fv-details"><summary>View as a table</summary><div class="fv-scroll" data-fv="year-table" role="region" aria-label="Awards per fiscal year as a table, scrollable" tabindex="0"></div></details>
</section>
<section class="fv-section" aria-labelledby="fv-org-h">
  <h3 id="fv-org-h">Top recipient organisations</h3>
  <p class="fv-intro">Number of awards for the twelve organisations with the most awards in the filtered list.</p>
  <div data-fv="orgs"></div>
</section>
<section class="fv-section" aria-labelledby="fv-heat-h">
  <h3 id="fv-heat-h">Topic by fiscal year</h3>
  <p class="fv-intro">Awards per cell. An award with several topics counts once in each of its topics.</p>
  <div data-fv="heat"></div>
</section>
<section class="fv-section" aria-labelledby="fv-matrix-h">
  <h3 id="fv-matrix-h">Recipient sector by topic</h3>
  <p class="fv-intro">Awards per cell. An award with several topics counts once in each of its topics.</p>
  <div data-fv="matrix"></div>
</section>`;

function region(html, label) {
  return `<div class="fv-scroll" role="region" aria-label="${esc(label)}" tabindex="0">${html}</div>`;
}

function emptyText(text) {
  return `<p class="fv-empty">${esc(text)}</p>`;
}

// ---- Markup builders (pure) -------------------------------------------------------------------

export function tilesHtml(m) {
  const tile = (title, value, note) => `<div class="fv-metric"><dt>${title}</dt><dd>${value}${note ? `<small>${note}</small>` : ""}</dd></div>`;
  return `<dl class="fv-metrics">${tile("Awards", fmtInt(m.awards))}${tile("Funder agencies", fmtInt(m.funders))}`
    + `${tile("Recipient organisations", fmtInt(m.orgs))}${tile("Sectors", fmtInt(m.sectors))}`
    + `${tile("California-led", m.awards ? `${Math.round(m.caShare * 100)}%` : "n/a", "share of awards led from California")}</dl>`;
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

// SVG Sankey with a title per ribbon and per block. The caller puts it in a horizontally scrolling box.
export function sankeySvg(graph, width, {T = null, amount = false} = {}) {
  const count = Math.max(...Array.from({length: graph.ncols}, (_, c) => graph.nodes.filter((n) => n.col === c).length));
  const height = Math.min(1000, Math.max(420, count * 24 + 40));
  const L = layoutSankey(graph, {width, height, marginLeft: 120, marginRight: 190});
  const heads = graph.withOrgs
    ? ["Funder agency", "Recipient sector", "Recipient organisation", "Topic"]
    : ["Funder agency", "Recipient sector", "Topic"];
  const parts = [
    `<svg class="fv-sankey-svg" width="${L.width}" height="${L.height}" viewBox="0 0 ${L.width} ${L.height}" role="img" aria-labelledby="fv-sankey-title">`,
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
    let label = "";
    if (cy - 7 >= prev) {
      const maxc = first ? 17 : last ? 24 : 26;
      const name = n.name.length > maxc ? `${n.name.slice(0, maxc - 1)}…` : n.name;
      label = `<text class="fv-label" x="${first ? n.x - 6 : n.x + n.w + 6}" y="${(cy + 4).toFixed(1)}" text-anchor="${first ? "end" : "start"}">${esc(name)}</text>`;
      lastBottom.set(n.col, cy + 7);
    }
    const share = ((n.value / total) * 100).toFixed(1);
    const text = `${n.name} (${kindLabel(n)}): ${fmtInt(n.count)} awards, ${share}% of ${amount ? "reported amount" : "award weight"}`
      + (n.amountW ? `; ${fmtUsd(n.amountW)} reported (${AMOUNT_CAVEAT})` : "");
    parts.push(`<g class="fv-node"><title>${esc(text)}</title><rect x="${n.x}" y="${n.y.toFixed(2)}" width="${n.w}" height="${n.h.toFixed(2)}" fill="${nodeFill(n, T)}"></rect>${label}</g>`);
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
    return `<tr><td>${esc(a.name)} <span class="fv-muted">(${kindLabel(a)})</span></td>`
      + `<td>${esc(b.name)} <span class="fv-muted">(${kindLabel(b)})</span></td>`
      + `<td class="num">${amount ? fmtUsdFull(l.value) : fmtShare(l.value)}</td>`
      + `<td class="num">${((l.value / total) * 100).toFixed(1)}%</td></tr>`;
  }).join("");
  return `<table><caption class="fv-sr-only">Sankey ribbons: from, to, ${amount ? "reported amount" : "awards"} and share</caption>`
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
    parts.push(`<line x1="${ml}" x2="${W - mr}" y1="${y(t)}" y2="${y(t)}" stroke="#c8d8dc"></line>`
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
      parts.push(`<rect x="${(ml + bw * i + bw * 0.12).toFixed(1)}" y="${y0.toFixed(1)}" width="${(bw * 0.76).toFixed(1)}" height="${Math.max(h, 0).toFixed(1)}" fill="${agencyColor(s.agency)}" stroke="#fff" stroke-width="2"><title>${yr.year}, ${esc(s.agency)}: ${s.n} awards</title></rect>`);
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
    + `<span class="fv-badge">${esc(labels[o.sector] || o.sector)}</span>`
    + `<span class="fv-bar" aria-hidden="true"><span style="width:${((o.n / max) * 100).toFixed(1)}%"></span></span>`
    + `<span class="fv-count">${o.n} ${o.n === 1 ? "award" : "awards"}</span></li>`).join("")}</ol>`;
}

function dotHtml(key, T) {
  return `<span class="fv-dot" aria-hidden="true" style="background:${topicFill(key, T, true)}"></span>`;
}

export function heatTableHtml(h, T) {
  if (!h.rows.length) return emptyText("No dated awards match the current filters.");
  const colName = (c) => (c === "pre" ? `Before ${HEAT_START}` : String(c));
  const head = h.cols.map((c) => `<th scope="col">${esc(colName(c))}</th>`).join("");
  const body = h.rows.map((r) => `<tr><th scope="row">${dotHtml(r.key, T)}${esc(r.label)}</th>${r.counts.map((n) => {
    const fill = heatFill(n, h.max);
    return `<td class="fv-cell" style="background:${fill};color:${inkFor(fill)}">${n}</td>`;
  }).join("")}</tr>`).join("");
  return region(`<table class="fv-matrix"><caption class="fv-sr-only">Awards per topic and fiscal year</caption>`
    + `<thead><tr><th scope="col">Topic</th>${head}</tr></thead><tbody>${body}</tbody></table>`, "Topic by fiscal year table, scrollable");
}

export function matrixTableHtml(m, labels, T) {
  if (!m.sectors.length) return emptyText("No awards match the current filters.");
  const head = m.topics.map((t) => `<th scope="col">${dotHtml(t, T)}${esc(t === UNTAGGED ? "Untagged" : T ? T.label(t) : t)}</th>`).join("");
  const body = m.sectors.map((s, i) => `<tr><th scope="row">${esc(labels[s] || s)}</th>${m.grid[i].map((n) => {
    const fill = heatFill(n, m.max);
    return `<td class="fv-cell" style="background:${fill};color:${inkFor(fill)}">${n}</td>`;
  }).join("")}</tr>`).join("");
  return region(`<table class="fv-matrix"><caption class="fv-sr-only">Awards per recipient sector and topic</caption>`
    + `<thead><tr><th scope="col">Recipient sector</th>${head}</tr></thead><tbody>${body}</tbody></table>`, "Recipient sector by topic table, scrollable");
}

// ---- Mount ------------------------------------------------------------------------------------

// Mounts the visualizations into container once. update(rows, sectorLabels) redraws every view.
export function mountFundingViz(container) {
  if (!container) throw new Error("mountFundingViz needs a container element");
  const T = globalThis.AtlasTopics || null;
  container.classList.add("fv-root");
  container.innerHTML = SKELETON;
  const host = (name) => container.querySelector(`[data-fv="${name}"]`);
  const state = {vrows: [], labels: DEFAULT_SECTOR_LABELS, mode: "awards", orgs: true, topN: 6, width: 0};

  function renderSankey() {
    const amount = state.mode === "amount";
    const graph = buildSankey(state.vrows, {mode: state.mode, topN: state.topN, orgs: state.orgs, sectorLabels: state.labels, T});
    const note = host("amount-note");
    note.hidden = !amount;
    note.innerHTML = amount
      ? `<strong>Showing reported amounts (USD), which are not comparable across sources.</strong> ${fmtInt(graph.excluded)} of ${fmtInt(state.vrows.length)} filtered awards have no reported amount and are excluded from this view.`
      : "";
    container.querySelector(".fv-topn").hidden = !state.orgs;
    const wrap = host("sankey");
    const table = host("sankey-table");
    if (!graph.nodes.length) {
      wrap.innerHTML = emptyText(amount ? "No awards with a reported amount match the current filters." : "No awards match the current filters.");
      table.innerHTML = "";
      return;
    }
    wrap.innerHTML = sankeySvg(graph, Math.max(760, wrap.clientWidth || 800), {T, amount});
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

  function renderAll() {
    host("tiles").innerHTML = tilesHtml(tileMetrics(state.vrows));
    renderSankey();
    renderYears();
    host("orgs").innerHTML = orgListHtml(topOrgs(state.vrows, 12), state.labels);
    host("heat").innerHTML = heatTableHtml(buildHeat(state.vrows, T), T);
    host("matrix").innerHTML = matrixTableHtml(buildSectorTopic(state.vrows, T), state.labels, T);
    state.width = container.clientWidth;
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
  // The Sankey and year chart size themselves from the container width, so redraw when it changes.
  if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(() => {
      if (container.clientWidth !== state.width && state.vrows.length) renderAll();
    }).observe(container);
  }

  return {
    update(rows, sectorLabels) {
      state.vrows = viewRows(Array.isArray(rows) ? rows : [], T);
      state.labels = sectorLabelsFor(sectorLabels);
      renderAll();
    }
  };
}
