// Pure view model for the Evidence map publication table (EV-TABLE). No DOM access, no imports,
// so Node tests can run it directly. Dates are calendar days in UTC.

export const PAGE_SIZE = 25;
export const SORT_KEYS = ["pub_date", "year", "cited_by_count", "title", "journal"];
export const DEFAULT_DIRS = {pub_date: "desc", year: "desc", cited_by_count: "desc", title: "asc", journal: "asc"};

const DAY_MS = 86400000;
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const CSV_HEADER = [
  "work_id", "title", "authors", "journal", "publication_date", "year",
  "citations", "doi", "open_access", "open_access_url", "topics"
];

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[c]);
}

// Only http(s) links are kept; anything else (javascript:, mailto:, junk) becomes "".
export function safeHttpUrl(value) {
  const text = typeof value === "string" ? value.trim() : "";
  if (!text) return "";
  try {
    const url = new URL(text);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : "";
  } catch (_error) {
    return "";
  }
}

// Day number (days since 1970-01-01 UTC) for a YYYY-MM-DD string, or null when it is not a real date.
function parseIsoDay(value) {
  if (typeof value !== "string" || !ISO_DAY.test(value)) return null;
  const [year, month, day] = value.split("-").map(Number);
  const ms = Date.UTC(year, month - 1, day);
  const date = new Date(ms);
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
  return Math.floor(ms / DAY_MS);
}

function dayNumberOf(date) {
  if (!(date instanceof Date) || Number.isNaN(date.getTime())) return null;
  return Math.floor(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()) / DAY_MS);
}

function textOf(value) {
  return typeof value === "string" ? value.trim() : "";
}

function stringList(value) {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.map(textOf).filter(Boolean))];
}

function allTags(row) {
  return [...(row.domain_tags || []), ...(row.facet_tags || [])];
}

// One works_detail.json entry in the shape the table expects, or null when it has no work_id.
export function normaliseRow(raw) {
  if (!raw || typeof raw !== "object") return null;
  const workId = textOf(raw.work_id);
  if (!workId) return null;
  const pubDate = parseIsoDay(raw.pub_date) === null ? "" : raw.pub_date;
  const yearNumber = Number(raw.year);
  const year = Number.isInteger(yearNumber) && yearNumber > 0 ? yearNumber : pubDate ? Number(pubDate.slice(0, 4)) : null;
  const authors = stringList(raw.authors);
  const authorCount = Number(raw.author_count);
  const citations = Number(raw.cited_by_count);
  return {
    work_id: workId,
    title: textOf(raw.title),
    year,
    pub_date: pubDate,
    first_seen: textOf(raw.first_seen),
    doi: safeHttpUrl(raw.doi),
    journal: textOf(raw.journal),
    type: textOf(raw.type),
    cited_by_count: Number.isFinite(citations) && citations > 0 ? Math.floor(citations) : 0,
    is_oa: raw.is_oa === true,
    oa_url: safeHttpUrl(raw.oa_url),
    plastic_related: raw.plastic_related === true ? true : raw.plastic_related === false ? false : null,
    ca_led: raw.ca_led === true,
    domain_tags: stringList(raw.domain_tags),
    facet_tags: stringList(raw.facet_tags),
    authors,
    author_count: Number.isInteger(authorCount) && authorCount >= authors.length ? authorCount : authors.length,
    has_abstract: raw.has_abstract === true
  };
}

// Accepts the works_detail.json object (or a bare array); drops malformed and duplicate rows.
export function normaliseRows(payload) {
  const list = Array.isArray(payload) ? payload : payload && Array.isArray(payload.works) ? payload.works : [];
  const seen = new Set();
  const rows = [];
  for (const raw of list) {
    const row = normaliseRow(raw);
    if (row && !seen.has(row.work_id)) {
      seen.add(row.work_id);
      rows.push(row);
    }
  }
  return rows;
}

// Sorted, de-duplicated topic and matrix tags carried by any row.
export function tagsPresent(rows) {
  const tags = new Set();
  for (const row of rows || []) allTags(row).forEach((tag) => tags.add(tag));
  return [...tags].sort();
}

// True when pub_date falls within the last `days` calendar days before `today`, inclusive.
// Future dates and rows without a valid pub_date are not recent.
export function isRecent(row, today = new Date(), days = 14) {
  const pubDay = parseIsoDay(row && row.pub_date);
  const todayDay = dayNumberOf(today);
  if (pubDay === null || todayDay === null) return false;
  const age = todayDay - pubDay;
  return age >= 0 && age <= days;
}

export function recentRows(rows, today = new Date()) {
  return (rows || []).filter((row) => isRecent(row, today));
}

// filters: {q, tag, minCites, oaOnly, recentOnly}. q matches every whitespace-separated term
// against title, authors and journal. Blank or non-numeric minCites means no minimum.
export function filterRows(rows, filters = {}, today = new Date()) {
  const {q = "", tag = "", minCites = null, oaOnly = false, recentOnly = false} = filters || {};
  const terms = String(q ?? "").trim().toLowerCase().split(/\s+/).filter(Boolean);
  const min = minCites === null || minCites === undefined || String(minCites).trim() === "" ? NaN : Number(minCites);
  const hasMin = Number.isFinite(min);
  return (rows || []).filter((row) => {
    if (terms.length) {
      const haystack = [row.title, (row.authors || []).join(" "), row.journal].join(" ").toLowerCase();
      if (!terms.every((term) => haystack.includes(term))) return false;
    }
    if (tag && !allTags(row).includes(tag)) return false;
    if (hasMin && row.cited_by_count < min) return false;
    if (oaOnly && !row.is_oa) return false;
    if (recentOnly && !isRecent(row, today)) return false;
    return true;
  });
}

// Missing values always sort last, whatever the direction.
function compareValues(a, b, key, sign) {
  const va = sortValue(a, key);
  const vb = sortValue(b, key);
  if (va === null || vb === null) return (va === null) - (vb === null);
  const result = typeof va === "number" ? va - vb : va.localeCompare(vb, "en");
  return result * sign;
}

function sortValue(row, key) {
  if (key === "year") return Number.isInteger(row.year) ? row.year : null;
  if (key === "cited_by_count") return Number.isFinite(row.cited_by_count) ? row.cited_by_count : null;
  const text = textOf(row[key]);
  return text ? text : null;
}

function compareRows(a, b, key, sign) {
  if (key !== "pub_date") return compareValues(a, b, key, sign);
  // Dated rows come first in both directions; undated rows are ordered by year, then last.
  const dayA = parseIsoDay(a.pub_date);
  const dayB = parseIsoDay(b.pub_date);
  if (dayA !== null && dayB !== null) return (dayA - dayB) * sign;
  if (dayA !== null || dayB !== null) return dayA !== null ? -1 : 1;
  return compareValues(a, b, "year", sign);
}

// Returns a new array. key defaults to pub_date; dir defaults to that key's default direction.
export function sortRows(rows, key = "pub_date", dir) {
  const sortKey = SORT_KEYS.includes(key) ? key : "pub_date";
  const direction = dir === "asc" || dir === "desc" ? dir : DEFAULT_DIRS[sortKey];
  const sign = direction === "asc" ? 1 : -1;
  return [...(rows || [])].sort((a, b) => {
    const primary = compareRows(a, b, sortKey, sign);
    if (primary) return primary;
    return a.title.localeCompare(b.title, "en") || a.work_id.localeCompare(b.work_id, "en");
  });
}

// Paging state for `total` rows. page is 1-based and clamped; start and end are 1-based (0 when empty).
export function pageInfo(total, page = 1, size = PAGE_SIZE) {
  const count = Math.max(0, Math.floor(Number(total)) || 0);
  const perPage = Math.max(1, Math.floor(Number(size)) || PAGE_SIZE);
  const pages = Math.max(1, Math.ceil(count / perPage));
  const current = Math.min(pages, Math.max(1, Math.floor(Number(page)) || 1));
  const start = count === 0 ? 0 : (current - 1) * perPage + 1;
  const end = Math.min(count, current * perPage);
  return {page: current, pages, size: perPage, total: count, start, end};
}

export function pageRows(rows, page = 1, size = PAGE_SIZE) {
  const list = rows || [];
  const info = pageInfo(list.length, page, size);
  if (info.total === 0) return [];
  return list.slice((info.page - 1) * info.size, info.page * info.size);
}

// "A, B, C et al. (27 authors)" when the byline is longer than max; otherwise the full list.
export function authorLine(row, max = 6) {
  const names = Array.isArray(row && row.authors) ? row.authors : [];
  if (!names.length) return "";
  const total = Math.max(names.length, Number(row.author_count) || 0);
  const limit = Math.max(1, Math.floor(max));
  if (total <= limit && names.length <= limit) return names.join(", ");
  return `${names.slice(0, limit).join(", ")} et al. (${total} authors)`;
}

// "12 Nov 2026" when the full date is known, otherwise the year, otherwise a plain note.
export function dateLabel(row) {
  if (parseIsoDay(row && row.pub_date) !== null) {
    const [year, month, day] = row.pub_date.split("-").map(Number);
    return `${day} ${MONTHS[month - 1]} ${year}`;
  }
  return row && row.year ? String(row.year) : "Date not listed";
}

// Text cells that spreadsheet programs would read as formulas get a leading apostrophe.
function csvCell(value) {
  let text = value === null || value === undefined ? "" : String(value);
  if (typeof value === "string" && /^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv(rows) {
  const lines = [CSV_HEADER.join(",")];
  for (const row of rows || []) {
    const cells = [
      row.work_id,
      row.title,
      (row.authors || []).join("; "),
      row.journal,
      row.pub_date,
      row.year,
      row.cited_by_count,
      row.doi,
      row.is_oa ? "yes" : "no",
      row.oa_url,
      allTags(row).join("; ")
    ];
    lines.push(cells.map(csvCell).join(","));
  }
  return `${lines.join("\r\n")}\r\n`;
}
