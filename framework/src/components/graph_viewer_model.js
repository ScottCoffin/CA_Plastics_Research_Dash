// Pure helpers for the global graph viewer (BQ-V.3, components/graph_viewer.js). No DOM, no npm
// imports, so tests/framework_graph_viewer_runtime.mjs can load this file under Node.
// Data: site/data/global/graphs/ (docs/NETWORK_BUILD.md §16 and §16b). Node rows follow the JSON
// `nodes.fields`; edge rows are [source, target, weight] with node indices.
import {OTHER, SECONDARY_ALL_PAIRS} from "./shared/palette.js";

export const GRAPHS = Object.freeze(["institutions", "authors"]);
export const PHONE_MAX_WIDTH = 860;
export const NODE_SIZE = Object.freeze({min: 2.5, max: 16});
export const LABEL_COUNT = Object.freeze({desktop: 40, phone: 20});
export const SEARCH_LIMIT = 8;
export const TABLE_LIMIT = 200;
export const ZOOM_TO_NODE = 0.25;

export function graphName(value, fallback = "institutions") {
  return GRAPHS.includes(value) ? value : fallback;
}

// phone: "auto" (or undefined) uses the viewport width; true/false (or the strings) force the choice.
export function usePhone(option, width) {
  if (option === true || option === "true") return true;
  if (option === false || option === "false") return false;
  return Number(width) <= PHONE_MAX_WIDTH;
}

// Manifest key for a graph: "institutions" or "institutions_phone" (graphs_manifest.json `graphs`).
export function graphFileKey(name, phone) {
  return phone ? `${graphName(name)}_phone` : graphName(name);
}

// Layout: float32 little-endian x, y pairs in node order (node i at bytes 8i to 8i+7).
export function decodeLayout(buffer, count) {
  const n = Number(count);
  if (!Number.isInteger(n) || n < 0) throw new Error("layout needs a node count");
  if (!buffer || buffer.byteLength < n * 8) throw new Error("layout file is shorter than its node count");
  const view = new DataView(buffer);
  const out = new Float32Array(n * 2);
  for (let i = 0; i < n; i += 1) {
    out[2 * i] = view.getFloat32(8 * i, true);
    out[2 * i + 1] = view.getFloat32(8 * i + 4, true);
  }
  return out;
}

const FIELD_MAP = {display_name: "name", country_code: "country"};

// Rows -> node objects. Fields may be missing for one graph (type, ror); they become null.
export function nodesFromRows(json) {
  const fields = json?.nodes?.fields;
  const rows = json?.nodes?.rows;
  if (!Array.isArray(fields) || !Array.isArray(rows)) throw new Error("graph file has no nodes.fields or nodes.rows");
  const seen = new Set();
  return rows.map((row, index) => {
    if (!Array.isArray(row) || row.length !== fields.length) throw new Error(`node row ${index} does not match fields`);
    const node = {index, id: null, name: "", country: null, type: null, ror: null, works: 0, community: null};
    fields.forEach((field, i) => {
      const key = FIELD_MAP[field] ?? field;
      node[key] = row[i];
    });
    node.id = String(node.id);
    node.name = node.name ? String(node.name) : node.id;
    node.works = Number(node.works) || 0;
    node.country = node.country ?? null;
    node.type = node.type ?? null;
    node.ror = node.ror ?? null;
    node.community = node.community ?? null;
    if (seen.has(node.id)) throw new Error(`duplicate node id ${node.id}`);
    seen.add(node.id);
    return node;
  });
}

export function edgesFromRows(json, count) {
  const rows = json?.edges?.rows;
  if (!Array.isArray(rows)) throw new Error("graph file has no edges.rows");
  return rows.map((row, index) => {
    const [source, target, weight] = row;
    if (!Number.isInteger(source) || !Number.isInteger(target) || source < 0 || target < 0 ||
        source >= count || target >= count || source === target) {
      throw new Error(`edge row ${index} points outside the node list`);
    }
    return {source, target, weight: Number(weight) || 1};
  });
}

function compareKeys(a, b) {
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b));
}

// Colour for the top groups by node count (ties: key order); every other group, and an unknown
// value, takes the shared grey. Returns the Map used by colourOf, the legend rows and the other count.
export function colourGroups(keys, palette = SECONDARY_ALL_PAIRS) {
  const counts = new Map();
  for (const key of keys) {
    if (key === null || key === undefined || key === "") continue;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  const ranked = [...counts].sort((a, b) => (b[1] - a[1]) || compareKeys(a[0], b[0]));
  const colours = new Map();
  const legend = ranked.slice(0, palette.length).map(([key, count], i) => {
    colours.set(key, palette[i]);
    return {key, colour: palette[i], count};
  });
  const otherCount = ranked.slice(palette.length).reduce((sum, [, count]) => sum + count, 0);
  return {colours, legend, otherCount, otherColour: OTHER};
}

export function colourOf(colours, key) {
  return (key !== null && key !== undefined && colours.get(key)) || OTHER;
}

// Node area scales with works (square root), so a node with twice the works is not twice as wide.
export function nodeSize(works, maxWorks) {
  const {min, max} = NODE_SIZE;
  if (!(maxWorks > 0) || !(works > 0)) return min;
  return min + (max - min) * Math.sqrt(Math.min(1, works / maxWorks));
}

export function maxWorks(nodes) {
  return nodes.reduce((best, node) => Math.max(best, node.works), 0);
}

// Labels only for the top-N nodes by works (ties: the canonical index order). Returns a Set of indices.
export function labelIndices(nodes, count) {
  const order = nodes.map((node) => node.index).sort((a, b) => (nodes[b].works - nodes[a].works) || (a - b));
  return new Set(order.slice(0, Math.max(0, count)));
}

export function buildAdjacency(edges, count) {
  const adjacency = Array.from({length: count}, () => []);
  for (const {source, target, weight} of edges) {
    adjacency[source].push({index: target, weight});
    adjacency[target].push({index: source, weight});
  }
  return adjacency;
}

// The strongest neighbours by shared works (ties: lower node index).
export function topNeighbours(adjacency, index, limit = 10) {
  return [...(adjacency[index] ?? [])]
    .sort((a, b) => (b.weight - a.weight) || (a.index - b.index))
    .slice(0, limit);
}

export function foldText(value) {
  return String(value ?? "").normalize("NFD").replace(/\p{M}+/gu, "").toLowerCase().trim();
}

// Type-ahead: names that start with the query come first, then names that contain it; more works first.
export function matchNodes(nodes, query, limit = Infinity) {
  const q = foldText(query);
  if (!q) return [];
  const starts = [];
  const inside = [];
  for (const node of nodes) {
    const name = foldText(node.name);
    if (name.startsWith(q)) starts.push(node);
    else if (name.includes(q)) inside.push(node);
  }
  const byWorks = (a, b) => (b.works - a.works) || (a.index - b.index);
  return [...starts.sort(byWorks), ...inside.sort(byWorks)].slice(0, limit);
}

// Table sort. Works and links sort numerically; name and country sort as text. Ties keep the canonical order.
export function sortNodes(nodes, key = "works", direction = "desc") {
  const sign = direction === "asc" ? 1 : -1;
  return [...nodes].sort((a, b) => {
    let diff;
    if (key === "name") diff = foldText(a.name).localeCompare(foldText(b.name));
    else if (key === "country") diff = String(a.country ?? "").localeCompare(String(b.country ?? ""));
    else if (key === "community") diff = (Number(a.community) || 0) - (Number(b.community) || 0);
    else if (key === "links") diff = (a.links ?? 0) - (b.links ?? 0);
    else diff = a.works - b.works;
    return (sign * diff) || (a.index - b.index);
  });
}

// URL state: #g=<graph>&n=<nodeId>&z=<camera ratio>&x=<camera x>&y=<camera y>. Smaller z is closer.
// A host page can prefix the keys (hashPrefix, e.g. "gv." gives #gv.g=...) so other keys in the same
// hash (explore's scope= and view=) coexist with the viewer's.
const NODE_ID = /^[A-Za-z0-9]{1,24}$/;
const HASH_PREFIX = /^[A-Za-z0-9_.-]{0,16}$/;
export const GRAPH_HASH_KEYS = Object.freeze(["g", "n", "z", "x", "y"]);

export function hashPrefixOk(prefix) {
  return typeof prefix === "string" && HASH_PREFIX.test(prefix);
}

export function parseGraphHash(hash, prefix = "") {
  const params = new URLSearchParams(String(hash ?? "").replace(/^#/, ""));
  const out = {};
  if (GRAPHS.includes(params.get(`${prefix}g`))) out.graph = params.get(`${prefix}g`);
  if (NODE_ID.test(params.get(`${prefix}n`) ?? "")) out.node = params.get(`${prefix}n`);
  const num = (key, test) => {
    const raw = params.get(`${prefix}${key}`);
    if (raw === null || raw.trim() === "") return undefined;
    const value = Number(raw);
    return Number.isFinite(value) && test(value) ? value : undefined;
  };
  const z = num("z", (v) => v > 0 && v <= 1000);
  const x = num("x", () => true);
  const y = num("y", () => true);
  if (z !== undefined) out.zoom = z;
  if (x !== undefined) out.x = x;
  if (y !== undefined) out.y = y;
  return out;
}

const round = (value, digits) => String(Number(Number(value).toFixed(digits)));

// Returns the whole hash: the viewer's keys are replaced (or dropped when state is empty) and every
// other key in `current` is kept, so a page can keep its own state beside the viewer's.
export function formatGraphHash(state = {}, prefix = "", current = "") {
  const params = new URLSearchParams(String(current ?? "").replace(/^#/, ""));
  for (const key of GRAPH_HASH_KEYS) params.delete(`${prefix}${key}`);
  if (GRAPHS.includes(state.graph)) params.set(`${prefix}g`, state.graph);
  if (state.node && NODE_ID.test(String(state.node))) params.set(`${prefix}n`, String(state.node));
  if (Number.isFinite(state.zoom) && state.zoom > 0) params.set(`${prefix}z`, round(state.zoom, 4));
  if (Number.isFinite(state.x)) params.set(`${prefix}x`, round(state.x, 5));
  if (Number.isFinite(state.y)) params.set(`${prefix}y`, round(state.y, 5));
  const text = params.toString();
  return text ? `#${text}` : "";
}

// The manifest's plain-language note: a string, or an {is, is_not} object.
export function noteText(value) {
  if (typeof value === "string") return value;
  if (value && typeof value === "object") {
    return [value.is, value.is_not].filter(Boolean).join(" ");
  }
  return "";
}

export function formatWorks(value) {
  const n = Math.round(Number(value) || 0);
  return `${n.toLocaleString("en-US")} ${n === 1 ? "work" : "works"}`;
}

export function openAlexUrl(id) {
  return NODE_ID.test(String(id ?? "")) ? `https://openalex.org/${id}` : null;
}

// Download rows for one graph from site/data/global/graphs/exports/manifest.json (GEXF and GraphML).
// Only files whose `graph` matches are listed; the file name must be a plain name (no folders).
const FORMAT_LABEL = Object.freeze({gexf: "GEXF", graphml: "GraphML"});
export function exportFiles(manifest, name) {
  if (!GRAPHS.includes(name)) return [];
  const files = Array.isArray(manifest?.files) ? manifest.files : [];
  return files
    .filter((f) => f && f.graph === name && /^[A-Za-z0-9_.-]+$/.test(String(f.file ?? "")) && FORMAT_LABEL[f.format])
    .map((f) => ({file: f.file, format: f.format, label: FORMAT_LABEL[f.format], bytes: Number(f.bytes) || 0}))
    .sort((a, b) => Object.keys(FORMAT_LABEL).indexOf(a.format) - Object.keys(FORMAT_LABEL).indexOf(b.format));
}
