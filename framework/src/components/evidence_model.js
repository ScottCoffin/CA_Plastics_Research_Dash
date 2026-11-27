// Pure, DOM-free helpers for the Evidence map shell (Add-on A2 §5, EM-5b). Nothing here touches
// document or window at module top level, so tests/framework_evidence_runtime.mjs can import it.
// State shape: {facets: {facet: [label, ...]}, yearFrom: number|null, yearTo: number|null, q: string}.

// "plastic" is not a state key: the page always lists plastic-related works only (see selectionFor),
// so a hash that carries plastic=... is ignored.
export const FACET_KEYS = ["topic", "ca_led", "sector", "type", "oa", "institution", "journal"];
export const PLASTIC_ONLY = {plastic: ["yes"]};
// VD-34: the journal filter is not an AT-4 bundle facet. It is applied as a bit-set over the bundle's
// works (journalBits), so selectionFor leaves it out of the selection.
export const JOURNAL_FACET = "journal";
export const LINKOUT_NOTE = "External resource; the Atlas links to it and does not copy its data.";

export function emptyState() {
  return {facets: {}, yearFrom: null, yearTo: null, q: ""};
}

// A usable year is a four-digit integer; anything else means "no bound".
function yearValue(value) {
  return Number.isInteger(value) && value >= 1000 && value <= 9999 ? value : null;
}

function safeDecode(text) {
  try {
    return decodeURIComponent(text);
  } catch {
    return text;
  }
}

// Returns a clean copy: known keys only, no empty or duplicate labels, valid years, trimmed q.
export function normalizeState(state) {
  const source = state && typeof state === "object" ? state : {};
  const facets = {};
  for (const key of FACET_KEYS) {
    const labels = Array.isArray(source.facets?.[key]) ? source.facets[key] : [];
    const unique = [...new Set(labels.map((label) => String(label)).filter((label) => label !== ""))];
    if (unique.length) facets[key] = unique;
  }
  return {
    facets,
    yearFrom: yearValue(source.yearFrom),
    yearTo: yearValue(source.yearTo),
    q: typeof source.q === "string" ? source.q.trim() : ""
  };
}

// Reads "#topic=a,b&ca_led=yes&year_from=2015&year_to=2024&q=text". Labels are encoded
// individually, so a literal comma is always a separator. Unknown keys are ignored.
export function parseHash(hash) {
  const state = emptyState();
  const body = String(hash ?? "").replace(/^#/, "");
  for (const part of body.split("&")) {
    const eq = part.indexOf("=");
    if (eq < 1) continue;
    const key = safeDecode(part.slice(0, eq));
    const raw = part.slice(eq + 1);
    if (key === "year_from") state.yearFrom = Number(safeDecode(raw));
    else if (key === "year_to") state.yearTo = Number(safeDecode(raw));
    else if (key === "q") state.q = safeDecode(raw);
    else if (FACET_KEYS.includes(key)) state.facets[key] = raw.split(",").map(safeDecode);
  }
  return normalizeState(state);
}

// Inverse of parseHash. Returns "" for an empty state, otherwise "#..." with keys in fixed order.
export function formatHash(state) {
  const clean = normalizeState(state);
  const parts = [];
  for (const key of FACET_KEYS) {
    if (clean.facets[key]) parts.push(`${key}=${clean.facets[key].map((label) => encodeURIComponent(label)).join(",")}`);
  }
  if (clean.yearFrom !== null) parts.push(`year_from=${clean.yearFrom}`);
  if (clean.yearTo !== null) parts.push(`year_to=${clean.yearTo}`);
  if (clean.q) parts.push(`q=${encodeURIComponent(clean.q)}`);
  return parts.length ? `#${parts.join("&")}` : "";
}

// Drops labels that the bundle does not define. known: {facet: Set of labels}.
export function sanitizeState(state, known) {
  const clean = normalizeState(state);
  for (const key of Object.keys(clean.facets)) {
    const allowed = known?.[key];
    const labels = clean.facets[key].filter((label) => allowed?.has(label));
    if (labels.length) clean.facets[key] = labels;
    else delete clean.facets[key];
  }
  return clean;
}

function inYearRange(year, from, to) {
  return Number.isFinite(year) && (from === null || year >= from) && (to === null || year <= to);
}

// Converts the state into an index selection {sel, impossible}. yearLabels are the bundle's
// year labels (strings). A year range that matches no label cannot be expressed as a selection
// (an empty list means "no constraint" to the engine), so it is flagged as impossible instead.
// The plastic-related facet is always applied, so every count, view and list excludes other works.
// `plastic` is the relevance labels to keep. Regions without relevance review pass null (no plastic facet).
export function selectionFor(state, yearLabels = [], {plastic = PLASTIC_ONLY.plastic} = {}) {
  const clean = normalizeState(state);
  const sel = plastic ? {plastic: [...plastic]} : {};
  for (const [key, labels] of Object.entries(clean.facets)) {
    if (key !== JOURNAL_FACET) sel[key] = labels;
  }
  let impossible = false;
  if (clean.yearFrom !== null || clean.yearTo !== null) {
    const years = yearLabels.filter((label) => inYearRange(Number(label), clean.yearFrom, clean.yearTo));
    if (years.length) sel.year = years;
    else impossible = true;
  }
  return {sel, impossible};
}

// Related-resources rule: entries whose topics intersect the selected topics; when none match
// (or no topic is selected), the entries flagged default. Duplicate ids are shown once.
export function stripEntries(entries, selectedTopics = []) {
  const seen = new Set();
  const unique = [];
  for (const entry of Array.isArray(entries) ? entries : []) {
    if (!entry || typeof entry !== "object" || !entry.id || seen.has(entry.id)) continue;
    seen.add(entry.id);
    unique.push(entry);
  }
  const topics = new Set(selectedTopics || []);
  const matched = unique.filter((entry) => Array.isArray(entry.topics) && entry.topics.some((tag) => topics.has(tag)));
  if (matched.length) return matched;
  return unique.filter((entry) => entry.default === true);
}

// Only https links are rendered as links (root_url comes from a curated JSON file).
export function safeHttpUrl(url) {
  return typeof url === "string" && /^https:\/\/\S+$/.test(url) ? url : null;
}

// VD-34 journal filter. Options are the distinct journal names in rows (blank names skipped), most works
// first, then by name: [{label, count}].
export function journalOptions(rows) {
  const counts = new Map();
  for (const row of rows || []) {
    const name = typeof row?.journal === "string" ? row.journal.trim() : "";
    if (name) counts.set(name, (counts.get(name) || 0) + 1);
  }
  return [...counts]
    .map(([label, count]) => ({label, count}))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "en"));
}

// Case-insensitive search over the journal options: every whitespace-separated term must appear.
export function matchesJournalQuery(label, query) {
  const terms = String(query ?? "").trim().toLowerCase().split(/\s+/).filter(Boolean);
  const text = String(label).toLowerCase();
  return terms.every((term) => text.includes(term));
}

// Bit-set in the AT-4 layout (bit i = work i of workIds) for the works whose journal is one of labels.
// journalOf: Map of work_id -> journal name; words: the index's word count (index.W).
export function journalBits(workIds, journalOf, labels, words) {
  const wanted = new Set(labels || []);
  const out = new Uint32Array(words);
  workIds.forEach((id, i) => {
    if (wanted.has(journalOf.get(id))) out[i >>> 5] |= (1 << (i & 31)) >>> 0;
  });
  return out;
}

// Works per journal name for the ids given (a Map). Works without a journal are not counted.
export function tallyJournals(ids, journalOf) {
  const counts = new Map();
  for (const id of ids) {
    const name = journalOf.get(id);
    if (name) counts.set(name, (counts.get(name) || 0) + 1);
  }
  return counts;
}

// AND of two optional bit-sets; undefined means no constraint.
export function andBits(a, b) {
  if (!a) return b || undefined;
  if (!b) return a;
  const out = new Uint32Array(a.length);
  for (let i = 0; i < a.length; i++) out[i] = a[i] & b[i];
  return out;
}
