// V-4 trend panel for the Evidence Map (EM-7): works per year by topic, and the California share of
// matching records (C/A) from site/data/global/denominators.json (BQ-2.4). Published plastic-related works (D)
// sit beside the share and are never divided. Hand-built SVG; no chart library.
// Inputs: idx is the AT-4 BitmaskIndex (window.AtlasFacets) that the Evidence Map page loads.
import "./shared/topics.js";
import {globalDataUrl} from "./atlas.js";
import {
  FIRST_YEAR,
  countsByYear,
  denominatorShare,
  escapeHtml,
  isRecent,
  niceMax,
  readDenominators,
  refDateFor,
  seriesByTopic,
  seriesFromRows,
  yearRange
} from "./v4_trend_model.js";

const W = 720;
const H = 300;
const M = {top: 14, right: 12, bottom: 36, left: 52};
const PLOT_W = W - M.left - M.right;
const PLOT_H = H - M.top - M.bottom;

async function loadDenominators() {
  try {
    const response = await fetch(globalDataUrl("denominators.json"));
    if (!response.ok) return null;
    return readDenominators(await response.json());
  } catch (_error) {
    return null;
  }
}

// Counts that treat labels absent from the index as zero works (the AT-4 engine throws on them).
function countsFor(idx) {
  return (sel) => {
    for (const [facet, labels] of Object.entries(sel)) {
      const known = idx.ids && idx.ids[facet];
      if (!known || !labels.every((label) => known.has(label))) return 0;
    }
    return idx.counts(sel).total;
  };
}

function topicKeys(idx) {
  const topics = window.AtlasTopics.TOPICS;
  return Object.keys(topics)
    .filter((key) => idx.ids && idx.ids.topic && idx.ids.topic.has(key))
    .sort((a, b) => topics[a].order - topics[b].order);
}

function pct(value) {
  return `${Number(value.toPrecision(2))}%`;
}

function count(value) {
  return value == null ? "" : Number(value).toLocaleString("en-US");
}

function xFor(index, count) {
  return M.left + (index + 0.5) * (PLOT_W / count);
}

// VD-18: label every even year. The former every-5-years rule plus a forced last year put 2025
// and 2026 side by side; "recent" bars keep their lighter fill (still being indexed).
function yearTicks(years) {
  return years.map((year, i) => ({year, i})).filter(({year}) => year % 2 === 0);
}

function barChart(data, refDate) {
  const api = window.AtlasTopics;
  const {years, series, totals} = data;
  const max = niceMax(Math.max(0, ...totals));
  const band = PLOT_W / years.length;
  const barWidth = Math.max(1, band * 0.78);
  const y = (value) => M.top + PLOT_H - (value / max) * PLOT_H;
  const bars = [];
  years.forEach((year, i) => {
    const recent = isRecent(year, refDate);
    let base = 0;
    for (const {topic, values} of series) {
      const value = values[i];
      if (!value) continue;
      const top = y(base + value);
      const height = y(base) - top;
      const label = escapeHtml(`${year} ${api.label(topic)}: ${value}`);
      bars.push(
        `<rect class="v4-bar${recent ? " v4-recent" : ""}" x="${(xFor(i, years.length) - barWidth / 2).toFixed(1)}" ` +
          `y="${top.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${height.toFixed(1)}" ` +
          `fill="${api.color(topic)}"><title>${label}</title></rect>`
      );
      base += value;
    }
  });
  const grid = [0, max / 2, max]
    .map((v) => `<line class="v4-grid" x1="${M.left}" x2="${W - M.right}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/>` +
      `<text class="v4-tick" x="${M.left - 6}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end">${v.toLocaleString("en-US")}</text>`)
    .join("");
  const ticks = yearTicks(years)
    .map(({year, i}) => `<text class="v4-tick" x="${xFor(i, years.length).toFixed(1)}" y="${H - 14}" text-anchor="middle">${year}</text>`)
    .join("");
  return svg("Works per year by topic, stacked", grid + bars.join("") + ticks);
}

function shareChart(rows, years, version, refDate) {
  const inRange = rows.filter((row) => years.includes(row.year));
  if (!inRange.length) return '<p class="v4-note">No complete years with a share to draw.</p>';
  const max = niceMax(Math.max(...inRange.map((row) => row.share * 100)));
  const y = (value) => M.top + PLOT_H - (value / max) * PLOT_H;
  const points = inRange.map((row) => ({
    row,
    x: xFor(years.indexOf(row.year), years.length),
    y: y(row.share * 100),
    recent: isRecent(row.year, refDate)
  }));
  const line = `<polyline class="v4-line" fill="none" points="${points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")}"/>`;
  const dots = points
    .map((p) => `<circle class="v4-dot${p.recent ? " v4-recent" : ""}" cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3.5">` +
      `<title>${escapeHtml(`${p.row.year}: ${pct(p.row.share * 100)} (${p.row.corpus} of ${p.row.global})`)}</title></circle>`)
    .join("");
  const grid = [0, max / 2, max]
    .map((v) => `<line class="v4-grid" x1="${M.left}" x2="${W - M.right}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/>` +
      `<text class="v4-tick" x="${M.left - 6}" y="${(y(v) + 4).toFixed(1)}" text-anchor="end">${pct(v)}</text>`)
    .join("");
  const ticks = yearTicks(years)
    .map(({year, i}) => `<text class="v4-tick" x="${xFor(i, years.length).toFixed(1)}" y="${H - 14}" text-anchor="middle">${year}</text>`)
    .join("");
  return svg(`California share of matching records per year under query ${version}`, grid + line + dots + ticks);
}

function svg(label, body) {
  return `<svg class="v4-svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="${escapeHtml(label)}" focusable="false">${body}</svg>`;
}

function legend(topics) {
  const api = window.AtlasTopics;
  const items = topics.map(
    (topic) => `<li><span class="v4-swatch" style="background:${api.color(topic)}"></span>${escapeHtml(api.label(topic))}</li>`
  );
  items.push('<li><span class="v4-swatch v4-swatch-recent"></span>Last 12 months: still being indexed</li>');
  return `<ul class="v4-legend">${items.join("")}</ul>`;
}

// Table alternative: the bar counts, plus the share columns when denominators.json loaded.
// Share and denominator columns cover complete years only; a blank cell is an incomplete year.
function dataTable(data, shareRows, denoms, version) {
  const api = window.AtlasTopics;
  const counts = denoms
    ? {C: countsByYear(denoms, "C"), A: countsByYear(denoms, "A"), D: countsByYear(denoms, "D")}
    : null;
  const shareByYear = new Map(shareRows.map((row) => [row.year, row]));
  const head = [
    "<th scope=\"col\">Year</th>",
    '<th scope="col">Works</th>',
    ...data.series.map((s) => `<th scope="col">${escapeHtml(api.label(s.topic))}</th>`),
    ...(counts
      ? [
          '<th scope="col">California records (C)</th>',
          '<th scope="col">Matching records (A)</th>',
          '<th scope="col">California share (C/A)</th>',
          '<th scope="col">Published plastic-related works (D, not divided)</th>'
        ]
      : [])
  ].join("");
  const body = data.years
    .map((year, i) => {
      const row = shareByYear.get(year);
      const cells = [
        `<th scope="row">${year}</th>`,
        `<td>${data.totals[i]}</td>`,
        ...data.series.map((s) => `<td>${s.values[i]}</td>`),
        ...(counts
          ? [
              `<td>${count(counts.C[year])}</td>`,
              `<td>${count(counts.A[year])}</td>`,
              `<td>${row ? pct(row.share * 100) : ""}</td>`,
              `<td>${count(counts.D[year])}</td>`
            ]
          : [])
      ];
      return `<tr>${cells.join("")}</tr>`;
    })
    .join("");
  return `<div class="atlas-table-wrap" role="region" aria-label="Works per year table, scrollable" tabindex="0">` +
    `<table class="atlas-table"><caption>Works per year by topic${counts ? `, and California share of matching records under query ${escapeHtml(version)} (complete years)` : ""}</caption>` +
    `<thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

// Renders the whole corpus first; update(rows) redraws from the rows that match the page filters.
// The share comes from denominators.json and is never filtered, so the note says so when filters are on.
export async function mountV4Trend(container, idx, initialRows = null) {
  if (!container) throw new Error("mountV4Trend needs a container element");
  container.classList.add("v4-trend");
  container.innerHTML = '<p class="v4-status" role="status">Loading the trend panel…</p>';
  const denoms = await loadDenominators();
  const today = new Date();
  const refDate = refDateFor(denoms && {fetched_at: denoms.generated_at}, today);
  const years = yearRange(FIRST_YEAR, today.getUTCFullYear());
  const topics = topicKeys(idx);
  const version = denoms ? String(denoms.version.query_version || "") : "";
  const shareRows = denoms ? denominatorShare(denoms, "C", "A") : [];

  function shareSection() {
    if (!denoms) return '<p class="v4-note v4-unavailable">Share comparison unavailable.</p>';
    const latest = shareRows.filter((row) => years.includes(row.year)).at(-1);
    const dCounts = countsByYear(denoms, "D");
    const latestNote = latest
      ? `In ${latest.year}, ${latest.corpus.toLocaleString("en-US")} of ${latest.global.toLocaleString("en-US")} matching records ` +
        `have a California author (${pct(latest.share * 100)}). Published plastic-related works in California that year: ` +
        `${count(dCounts[latest.year])}, shown beside the share and not divided.`
      : "";
    const what = denoms.what_this_is_and_is_not || {};
    return (
      '<h3 class="v4-heading">California share of matching records</h3>' +
      shareChart(shareRows, years, version, refDate) +
      `<p class="v4-note">Under query ${escapeHtml(version)}, by publication year, complete years only. The share is not filtered.</p>` +
      (latestNote ? `<p class="v4-note">${escapeHtml(latestNote)}</p>` : "") +
      `<div class="v4-what"><h4 class="v4-heading">What this is and is not</h4>` +
      `<p class="v4-note"><strong>This is:</strong> ${escapeHtml(what.is || "")}</p>` +
      `<p class="v4-note"><strong>This is not:</strong> ${escapeHtml(what.is_not || "")}</p></div>`
    );
  }

  function draw(data, filtered) {
    // Two panes: the chart, and the same numbers in a table. The card's Chart/Table control shows one of them.
    container.innerHTML =
      '<div data-pane="chart">' +
      `<h3 class="v4-heading">Works per year by topic${filtered ? " (filtered)" : ""}</h3>` +
      barChart(data, refDate) +
      legend(topics) +
      `<p class="v4-note">A work with several topic tags is counted under each. Works before ${FIRST_YEAR} are not shown.</p>` +
      shareSection() +
      "</div>" +
      `<div data-pane="table">${dataTable(data, shareRows, denoms, version)}</div>`;
  }

  const initialData = initialRows === null ? seriesByTopic(countsFor(idx), years, topics) : seriesFromRows(initialRows, years, topics);
  draw(initialData, false);
  return {
    update(rows, {filtered = true} = {}) {
      draw(seriesFromRows(rows, years, topics), filtered);
    }
  };
}
