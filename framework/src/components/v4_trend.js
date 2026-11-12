// V-4 trend panel for the Evidence Map (EM-7): works per year by topic, and the California share
// of global output under the same query version. Hand-built SVG; no chart library.
// Inputs: idx is the AT-4 BitmaskIndex (window.AtlasFacets) that the Evidence Map page loads.
import "./shared/topics.js";
import {dataUrl} from "./atlas.js";
import {
  FIRST_YEAR,
  caShare,
  escapeHtml,
  isRecent,
  niceMax,
  refDateFor,
  seriesByTopic,
  yearRange
} from "./v4_trend_model.js";

const W = 720;
const H = 300;
const M = {top: 14, right: 12, bottom: 36, left: 52};
const PLOT_W = W - M.left - M.right;
const PLOT_H = H - M.top - M.bottom;

async function loadGlobal() {
  try {
    const response = await fetch(dataUrl("trend_global.json"));
    if (!response.ok) return null;
    const payload = await response.json();
    return payload && payload.by_year ? payload : null;
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

function xFor(index, count) {
  return M.left + (index + 0.5) * (PLOT_W / count);
}

function yearTicks(years) {
  return years.map((year, i) => ({year, i})).filter(({year, i}) => year % 5 === 0 || i === years.length - 1);
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
  if (!inRange.length) return '<p class="v4-note">No overlapping years with a global count.</p>';
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
  return svg(`California share of global works per year under query ${version}`, grid + line + dots + ticks);
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

function dataTable(data, rows, globalByYear, version) {
  const api = window.AtlasTopics;
  const head = [
    "<th scope=\"col\">Year</th>",
    '<th scope="col">Works</th>',
    ...data.series.map((s) => `<th scope="col">${escapeHtml(api.label(s.topic))}</th>`),
    ...(globalByYear ? ['<th scope="col">Global works</th>', '<th scope="col">CA share</th>'] : [])
  ].join("");
  const body = data.years
    .map((year, i) => {
      const row = rows.find((r) => r.year === year);
      const cells = [
        `<th scope="row">${year}</th>`,
        `<td>${data.totals[i]}</td>`,
        ...data.series.map((s) => `<td>${s.values[i]}</td>`),
        ...(globalByYear
          ? [`<td>${globalByYear[year] ?? ""}</td>`, `<td>${row ? pct(row.share * 100) : ""}</td>`]
          : [])
      ];
      return `<tr>${cells.join("")}</tr>`;
    })
    .join("");
  return `<table class="v4-sr-only"><caption>Works per year by topic${globalByYear ? `, and CA share under query ${escapeHtml(version)}` : ""}</caption>` +
    `<thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

export async function mountV4Trend(container, idx) {
  if (!container) throw new Error("mountV4Trend needs a container element");
  container.classList.add("v4-trend");
  container.innerHTML = '<p class="v4-status" role="status">Loading the trend panel…</p>';
  const globalPayload = await loadGlobal();
  const today = new Date();
  const refDate = refDateFor(globalPayload, today);
  const years = yearRange(FIRST_YEAR, today.getUTCFullYear());
  const topics = topicKeys(idx);
  const data = seriesByTopic(countsFor(idx), years, topics);
  const corpusByYear = Object.fromEntries(years.map((year, i) => [year, data.totals[i]]));
  const globalByYear = globalPayload ? globalPayload.by_year : null;
  const rows = globalByYear ? caShare(corpusByYear, globalByYear) : [];
  const version = globalPayload ? String(globalPayload.query_version || "") : "";
  const globalSection = globalPayload
    ? `<h3 class="v4-heading">California share of global output</h3>` +
      shareChart(rows, years, version, refDate) +
      `<p class="v4-note">Under query ${escapeHtml(version)}: California-connected works as a share of all OpenAlex works ` +
      `matching the same query, by publication year. Global counts fetched ${escapeHtml(globalPayload.fetched_at)}.</p>`
    : '<p class="v4-note v4-unavailable">Global comparison unavailable.</p>';
  container.innerHTML =
    `<h3 class="v4-heading">Works per year by topic</h3>` +
    barChart(data, refDate) +
    legend(topics) +
    `<p class="v4-note">A work with several topic tags is counted under each. Works before ${FIRST_YEAR} are not shown.</p>` +
    globalSection +
    dataTable(data, rows, globalByYear, version);
}
