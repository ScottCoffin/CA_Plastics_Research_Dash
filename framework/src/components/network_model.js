// Pure helpers for the collaboration network page. No DOM access.
// Edges carry yearly co-authored-work counts (years: {"2019": 1, ...}); the year range and the
// minimum-works filter act on those counts. Nodes stay visible when they match the node filters
// (topic, sector, institution, now in California); matching nodes with no shown link are dimmed.

export const MIN_WORKS_MAX = 10;
export const VIEW_SIZE = 1000;
export const COMMUNITY_COLOURS = [
  "#0072B2",
  "#D55E00",
  "#009E73",
  "#CC79A7",
  "#E69F00",
  "#56B4E9",
  "#7A4E9B",
  "#8C6D1F"
];
export const OTHER_COLOUR = "#b9c3c8";

const SECTOR_LABELS = {
  UC: "University of California",
  CSU: "California State University",
  other: "Other institution",
  private: "Private",
  "nonprofit/NGO": "Nonprofit or NGO",
  JPA: "Joint powers authority",
  federal: "Federal agency",
  "state-agency": "State agency",
  company: "Company",
  utility: "Utility",
  "local-agency": "Local agency"
};

export function sectorLabel(value) {
  return Object.prototype.hasOwnProperty.call(SECTOR_LABELS, value) ? SECTOR_LABELS[value] : String(value);
}

function safeDecode(text) {
  try {
    return decodeURIComponent(text);
  } catch {
    return text;
  }
}

function yearValue(value) {
  const year = Number(value);
  return Number.isInteger(year) && year >= 1900 && year <= 2100 ? year : null;
}

export function emptyNetworkState() {
  return {topic: "", sector: "", institution: "", yearFrom: null, yearTo: null, minWorks: 1, currentOnly: false};
}

// Clamps and tidies a state object: years become integers or null (swapped when reversed),
// the minimum is 1-10, and the institution text is trimmed.
export function normalizeNetworkState(state) {
  const source = state && typeof state === "object" ? state : {};
  let yearFrom = yearValue(source.yearFrom);
  let yearTo = yearValue(source.yearTo);
  if (yearFrom !== null && yearTo !== null && yearFrom > yearTo) [yearFrom, yearTo] = [yearTo, yearFrom];
  const minWorks = Math.round(Number(source.minWorks));
  return {
    topic: typeof source.topic === "string" ? source.topic.trim() : "",
    sector: typeof source.sector === "string" ? source.sector.trim() : "",
    institution: typeof source.institution === "string" ? source.institution.trim() : "",
    yearFrom,
    yearTo,
    minWorks: Number.isFinite(minWorks) ? Math.min(MIN_WORKS_MAX, Math.max(1, minWorks)) : 1,
    currentOnly: source.currentOnly === true
  };
}

// Reads "#topic=air&sector=UC&inst=Davis&year_from=2015&year_to=2024&min=3&now=ca".
// Unknown keys are ignored; values are percent-decoded individually.
export function parseNetworkHash(hash) {
  const state = emptyNetworkState();
  const body = String(hash ?? "").replace(/^#/, "");
  for (const part of body.split("&")) {
    const eq = part.indexOf("=");
    if (eq < 1) continue;
    const key = safeDecode(part.slice(0, eq));
    const value = safeDecode(part.slice(eq + 1));
    if (key === "topic") state.topic = value;
    else if (key === "sector") state.sector = value;
    else if (key === "inst") state.institution = value;
    else if (key === "year_from") state.yearFrom = Number(value);
    else if (key === "year_to") state.yearTo = Number(value);
    else if (key === "min") state.minWorks = Number(value);
    else if (key === "now") state.currentOnly = value === "ca";
  }
  return normalizeNetworkState(state);
}

// Inverse of parseNetworkHash. Returns "" when no filter is set.
export function formatNetworkHash(state) {
  const clean = normalizeNetworkState(state);
  const parts = [];
  if (clean.topic) parts.push(`topic=${encodeURIComponent(clean.topic)}`);
  if (clean.sector) parts.push(`sector=${encodeURIComponent(clean.sector)}`);
  if (clean.institution) parts.push(`inst=${encodeURIComponent(clean.institution)}`);
  if (clean.yearFrom !== null) parts.push(`year_from=${clean.yearFrom}`);
  if (clean.yearTo !== null) parts.push(`year_to=${clean.yearTo}`);
  if (clean.minWorks > 1) parts.push(`min=${clean.minWorks}`);
  if (clean.currentOnly) parts.push("now=ca");
  return parts.length ? `#${parts.join("&")}` : "";
}

// Earliest and latest years that carry any co-authored work in the edge list.
export function yearBounds(edges) {
  let min = null;
  let max = null;
  for (const edge of edges || []) {
    for (const [key, count] of Object.entries(edge.years || {})) {
      const year = Number(key);
      if (!Number.isInteger(year) || !(Number(count) > 0)) continue;
      min = min === null ? year : Math.min(min, year);
      max = max === null ? year : Math.max(max, year);
    }
  }
  return {min, max};
}

// Co-authored works on an edge. Without a year range this is the stored total; with one it is the
// sum of the yearly counts inside the range (both ends inclusive).
export function edgeWeight(edge, yearFrom = null, yearTo = null) {
  const total = Number(edge?.weight) || 0;
  if (yearFrom === null && yearTo === null) return total;
  let sum = 0;
  for (const [key, count] of Object.entries(edge?.years || {})) {
    const year = Number(key);
    if ((yearFrom === null || year >= yearFrom) && (yearTo === null || year <= yearTo)) {
      sum += Number(count) || 0;
    }
  }
  return sum;
}

// Ids of the nodes that pass the node-level filters (topic, sector, institution text, now in CA).
export function matchingNodeIds(nodes, state) {
  const s = normalizeNetworkState(state);
  const needle = s.institution.toLowerCase();
  const ids = new Set();
  for (const node of nodes || []) {
    if (s.topic && !(node.topics || []).includes(s.topic)) continue;
    if (s.sector && !(node.sectors || []).includes(s.sector)) continue;
    if (needle) {
      const names = [...(node.institutions || []), ...(node.primary_affiliations || [])];
      if (!names.some((name) => String(name).toLowerCase().includes(needle))) continue;
    }
    if (s.currentOnly && node.current_in_ca !== true) continue;
    ids.add(node.id);
  }
  return ids;
}

// Per-edge weight to draw, aligned with the edges array. 0 means the edge is hidden: an endpoint
// is filtered out, the range weight is 0, or the weight is below the minimum.
export function shownEdgeWeights(edges, matching, state) {
  const s = normalizeNetworkState(state);
  return (edges || []).map((edge) => {
    if (!matching.has(edge.source) || !matching.has(edge.target)) return 0;
    const weight = edgeWeight(edge, s.yearFrom, s.yearTo);
    return weight > 0 && weight >= s.minWorks ? weight : 0;
  });
}

// Ids that have at least one shown link.
export function connectedIds(edges, weights) {
  const ids = new Set();
  edges.forEach((edge, i) => {
    if (weights[i] > 0) {
      ids.add(edge.source);
      ids.add(edge.target);
    }
  });
  return ids;
}

// Ids joined to `id` by a shown link.
export function neighbourIds(edges, weights, id) {
  const ids = new Set();
  edges.forEach((edge, i) => {
    if (!(weights[i] > 0)) return;
    if (edge.source === id) ids.add(edge.target);
    else if (edge.target === id) ids.add(edge.source);
  });
  return ids;
}

export function networkSummary(matching, weights) {
  return {experts: matching.size, links: weights.filter((w) => w > 0).length};
}

export function tagOptions(nodes, field = "topics") {
  const tags = new Set();
  for (const node of nodes || []) for (const tag of node[field] || []) tags.add(String(tag));
  return [...tags].sort((a, b) => a.localeCompare(b));
}

export function sectorOptions(nodes) {
  return tagOptions(nodes, "sectors");
}

// Matching nodes, most collaborators first (the node's total co-author count), then by name.
export function sortByCollaborators(nodes, matching) {
  return (nodes || [])
    .filter((node) => matching.has(node.id))
    .sort((a, b) => (Number(b.degree) || 0) - (Number(a.degree) || 0) || String(a.name).localeCompare(String(b.name)));
}

// Eight largest communities get the palette, in size order (Map insertion order). Others are absent.
export function communityColourMap(nodes) {
  const sizes = new Map();
  for (const node of nodes || []) sizes.set(node.community, (sizes.get(node.community) || 0) + 1);
  const ranked = [...sizes.entries()]
    .sort((a, b) => b[1] - a[1] || a[0] - b[0])
    .slice(0, COMMUNITY_COLOURS.length)
    .map(([community]) => community);
  return new Map(ranked.map((community, i) => [community, COMMUNITY_COLOURS[i]]));
}

// Area scales with works: radius 4 (no works) to 16 (the most works).
export function nodeRadius(works, maxWorks) {
  const share = maxWorks > 0 ? Math.sqrt(Math.max(0, Number(works) || 0) / maxWorks) : 0;
  return 4 + 12 * share;
}

// Stroke width proportional to shared works, capped so heavy pairs stay readable.
export function edgeStroke(weight) {
  return Math.min(8, 1.2 * weight);
}

// Maps the precomputed layout onto a square view, keeping its aspect ratio and centring it.
export function layoutToView(nodes, size = VIEW_SIZE, pad = 40) {
  const out = new Map();
  const points = (nodes || []).filter((node) => Number.isFinite(node.x) && Number.isFinite(node.y));
  if (!points.length) return out;
  const xs = points.map((node) => node.x);
  const ys = points.map((node) => node.y);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  const spanX = Math.max(...xs) - minX;
  const spanY = Math.max(...ys) - minY;
  const scale = (size - 2 * pad) / (Math.max(spanX, spanY) || 1);
  const offX = (size - spanX * scale) / 2;
  const offY = (size - spanY * scale) / 2;
  for (const node of points) {
    out.set(node.id, {x: offX + (node.x - minX) * scale, y: offY + (node.y - minY) * scale});
  }
  return out;
}
