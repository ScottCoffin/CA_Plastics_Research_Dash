// Pure, DOM-free helpers for the Evidence map shell (Add-on A2 §5, EM-5b). Nothing here touches
// document or window at module top level, so tests/framework_evidence_runtime.mjs can import it.
// State shape: {facets: {facet: [label, ...]}, yearFrom: number|null, yearTo: number|null, q: string}.

// "plastic" is not a state key: the page always lists plastic-related works only (see selectionFor),
// so a hash that carries plastic=... is ignored.
export const FACET_KEYS = ["topic", "ca_led", "sector", "type", "oa", "institution"];
export const PLASTIC_ONLY = {plastic: ["yes"]};
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
export function selectionFor(state, yearLabels = []) {
  const clean = normalizeState(state);
  const sel = {plastic: [...PLASTIC_ONLY.plastic]};
  for (const [key, labels] of Object.entries(clean.facets)) sel[key] = labels;
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
