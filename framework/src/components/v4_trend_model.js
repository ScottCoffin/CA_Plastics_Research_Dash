// Pure helpers for the Evidence Map trend panel (V-4, EM-7). Nothing here touches the DOM, so
// Node tests can import this module directly.

// Earliest publication year drawn in the trend panel; earlier years are not shown.
export const FIRST_YEAR = 2000;

// Inclusive list of integer years.
export function yearRange(from, to) {
  const out = [];
  for (let y = from; y <= to; y++) out.push(y);
  return out;
}

// countsFn(sel) -> number of corpus works matching sel (for example {year: ["2019"], topic: ["air"]}).
// Returns {years, series: [{topic, values}], totals}: values and totals are aligned with years.
// A work tagged with several topics is counted in each, so topic values can sum above totals.
export function seriesByTopic(countsFn, years, topics) {
  const series = topics.map((topic) => ({
    topic,
    values: years.map((year) => Number(countsFn({year: [String(year)], topic: [topic]})) || 0)
  }));
  const totals = years.map((year) => Number(countsFn({year: [String(year)]})) || 0);
  return {years: years.slice(), series, totals};
}

// Same shape as seriesByTopic, computed from work rows ({year, domain_tags}) already filtered by
// the page's selection, so the panel follows the filters.
export function seriesFromRows(rows, years, topics) {
  const index = new Map(years.map((year, i) => [year, i]));
  const totals = years.map(() => 0);
  const byTopic = new Map(topics.map((topic) => [topic, years.map(() => 0)]));
  for (const row of rows || []) {
    const i = index.get(Number(row && row.year));
    if (i === undefined) continue;
    totals[i] += 1;
    for (const tag of new Set(row.domain_tags || [])) {
      const values = byTopic.get(tag);
      if (values) values[i] += 1;
    }
  }
  return {years: years.slice(), series: topics.map((topic) => ({topic, values: byTopic.get(topic)})), totals};
}

// CA share per year: corpus works / global works, for years with a positive global count.
// corpusByYear and globalByYear are objects keyed by year (string or number).
// Returns [{year, corpus, global, share}] sorted by year; share is a fraction (0..1+).
export function caShare(corpusByYear, globalByYear) {
  const rows = [];
  for (const key of Object.keys(globalByYear || {})) {
    const year = Number(key);
    const global = Number(globalByYear[key]);
    if (!Number.isInteger(year) || !(global > 0)) continue;
    const corpus = Number((corpusByYear || {})[key]) || 0;
    rows.push({year, corpus, global, share: corpus / global});
  }
  return rows.sort((a, b) => a.year - b.year);
}

// True when a calendar year overlaps the 12 months ending at refDate. That is the year before
// refDate's year onward, because the previous year always overlaps the 12-month span. Such years are
// drawn lighter: their indexing is still settling.
export function isRecent(year, refDate) {
  if (!(refDate instanceof Date) || Number.isNaN(refDate.getTime())) return false;
  const start = new Date(refDate.getTime());
  start.setUTCFullYear(start.getUTCFullYear() - 1);
  return Number(year) >= start.getUTCFullYear();
}

// Reference date for "last 12 months": the global file's fetched_at when valid, else today.
export function refDateFor(globalPayload, today) {
  const fetched = globalPayload && new Date(globalPayload.fetched_at);
  if (fetched && !Number.isNaN(fetched.getTime())) return fetched;
  return today instanceof Date ? today : new Date();
}

// A round upper bound for a chart axis (1, 2, 5 or 10 times a power of ten).
export function niceMax(value) {
  const v = Number(value);
  if (!(v > 0)) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(v));
  for (const step of [1, 2, 5, 10]) {
    if (step * magnitude >= v) return step * magnitude;
  }
  return 10 * magnitude;
}

// Escape text for HTML or SVG markup.
export function escapeHtml(text) {
  return String(text == null ? "" : text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
