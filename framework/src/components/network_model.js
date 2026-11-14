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

// ---- sigma.js graph helpers -------------------------------------------------------------------
// Colour and size modes for the WebGL graph. Groups are the colour keys: a cluster number, a
// main topic (first tag) or a main sector (first sector). Only the largest groups get a colour.
export const OTHER_GROUP = "__other__";
export const EDGE_COLOUR = "#7d8a90";

function firstTag(list) {
  if (!Array.isArray(list) || !list.length) return null;
  const value = list[0];
  return value === null || value === undefined || String(value) === "" ? null : String(value);
}

// The group a node belongs to in the chosen colour mode, or null when it has none.
export function nodeGroup(node, colourMode) {
  if (colourMode === "topic") return firstTag(node.topics);
  if (colourMode === "sector") return firstTag(node.sectors);
  return node.community === undefined || node.community === null ? null : String(node.community);
}

// Experts per group, largest first; ties by key (numbers in numeric order).
export function groupCounts(nodes, colourMode) {
  const counts = new Map();
  for (const node of nodes || []) {
    const key = nodeGroup(node, colourMode);
    if (key !== null) counts.set(key, (counts.get(key) || 0) + 1);
  }
  return new Map(
    [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], undefined, {numeric: true}))
  );
}

// Colour per group for the largest groups, in palette order. Topics use their own colour when
// topicColour returns one. Groups beyond the palette are absent and draw in the other colour.
export function colourGroups(nodes, colourMode, topicColour = () => null) {
  const out = new Map();
  [...groupCounts(nodes, colourMode).keys()].slice(0, COMMUNITY_COLOURS.length).forEach((key, i) => {
    const own = colourMode === "topic" ? topicColour(key) : null;
    out.set(key, own || COMMUNITY_COLOURS[i]);
  });
  return out;
}

// Legend rows in colour order, plus one "other" row when some experts have no coloured group.
export function legendGroups(nodes, colourMode, colours, topicLabel = (tag) => String(tag)) {
  const counts = groupCounts(nodes, colourMode);
  const noun = colourMode === "topic" ? "topics" : colourMode === "sector" ? "sectors" : "clusters";
  const labelOf = (key, rank) => {
    if (colourMode === "topic") return topicLabel(key);
    if (colourMode === "sector") return sectorLabel(key);
    return `Cluster ${rank}`;
  };
  const items = [...colours.keys()].map((key, i) => ({
    key,
    colour: colours.get(key),
    count: counts.get(key) || 0,
    label: labelOf(key, i + 1)
  }));
  const otherCount = (nodes || []).length - items.reduce((sum, item) => sum + item.count, 0);
  if (otherCount > 0) {
    items.push({key: OTHER_GROUP, colour: OTHER_COLOUR, count: otherCount, label: `Other ${noun}`});
  }
  return items;
}

// Colour for one node, given the colour map from colourGroups.
export function nodeColour(node, colourMode, colours) {
  const key = nodeGroup(node, colourMode);
  return key !== null && colours.has(key) ? colours.get(key) : OTHER_COLOUR;
}

// The number a node is sized by: plastic-related works or collaborators.
export function sizeValue(node, sizeMode) {
  return sizeMode === "collaborators" ? Number(node.degree) || 0 : Number(node.plastic_works) || 0;
}

// Sigma node size in pixels: area grows with the value, from 3 px (none) to 14 px (the largest).
export function sigmaNodeSize(value, maxValue) {
  const share = maxValue > 0 ? Math.sqrt(Math.max(0, Number(value) || 0) / maxValue) : 0;
  return 3 + 11 * share;
}

// Plain node and edge rows for the graph: only the experts that pass the node filters and are not
// in a hidden legend group, and only the links with a shown weight between two kept experts.
// options: {colours, hiddenGroups: Set, positions: Map(id -> {x, y})} override the defaults.
export function graphAttributes(nodes, edges, state, colourMode, sizeMode, options = {}) {
  const colours = options.colours || colourGroups(nodes, colourMode);
  const hidden = options.hiddenGroups || new Set();
  const positions = options.positions || new Map();
  const matching = matchingNodeIds(nodes, state);
  const weights = shownEdgeWeights(edges || [], matching, state);
  const maxValue = Math.max(1, ...(nodes || []).map((node) => sizeValue(node, sizeMode)));
  const nodeRows = [];
  const kept = new Set();
  for (const node of nodes || []) {
    if (!matching.has(node.id)) continue;
    const group = nodeGroup(node, colourMode);
    const key = group !== null && colours.has(group) ? group : OTHER_GROUP;
    if (hidden.has(key)) continue;
    const at = positions.get(node.id) || {x: Number(node.x) || 0, y: Number(node.y) || 0};
    kept.add(node.id);
    nodeRows.push({
      key: node.id,
      label: node.name,
      x: at.x,
      y: at.y,
      size: sigmaNodeSize(sizeValue(node, sizeMode), maxValue),
      color: key === OTHER_GROUP ? OTHER_COLOUR : colours.get(key),
      group: key
    });
  }
  const edgeRows = [];
  (edges || []).forEach((edge, i) => {
    const weight = weights[i];
    if (!(weight > 0) || !kept.has(edge.source) || !kept.has(edge.target)) return;
    edgeRows.push({
      key: `e${i}`,
      source: edge.source,
      target: edge.target,
      size: 0.6 * edgeStroke(weight),
      color: EDGE_COLOUR,
      weight
    });
  });
  return {nodes: nodeRows, edges: edgeRows};
}

// The co-authors joined to `id` by a shown link, most shared works first (then by id).
export function topCoauthors(edges, weights, id, n = 8) {
  const rows = [];
  (edges || []).forEach((edge, i) => {
    const weight = weights[i];
    if (!(weight > 0)) return;
    if (edge.source === id) rows.push({id: edge.target, weight});
    else if (edge.target === id) rows.push({id: edge.source, weight});
  });
  return rows
    .sort((a, b) => b.weight - a.weight || String(a.id).localeCompare(String(b.id)))
    .slice(0, Math.max(0, n));
}
