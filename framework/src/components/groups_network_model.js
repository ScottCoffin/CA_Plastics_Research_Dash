// Pure helpers for the community groups network view (CG-11 part B, components/groups_network.js).
// No DOM and no npm imports, so tests/framework_groups_network_runtime.mjs can load this file under Node.
// Data: site/data/global/groups/groups_graph.json (schema cg-graph-v1). Edges keep their edge_type all the way
// through: assignment (group to facet), affiliation (group to group or external, quoted) and co_occurrence
// (activity to activity). The edge types are never merged into one kind of link.
import {groupLabel} from "./group_labels.js";

export const GRAPH_SCHEMA = "cg-graph-v1";
export const MODES = Object.freeze(["assignments", "co_occurrence"]);
export const STATUS_LABELS = Object.freeze({
  not_tagged: "Not yet tagged",
  ambassador_tagged: "Volunteer-tagged",
  reviewed: "Reviewed",
  group_confirmed: "Confirmed by group",
  cannot_determine: "Could not be tagged from public pages"
});
/** Plain sector name (group_labels.js); a missing sector reads as "Other". */
export const sectorLabel = (value) => groupLabel("sector", value) || "Other";
export const EDGE_LABELS = Object.freeze({
  assignment: "Tag",
  affiliation: "Stated affiliation",
  co_occurrence: "Tags used together"
});

const DEFAULT_STATE = Object.freeze({mode: "assignments", affiliations: false, externals: true, adjacent: true, status: "", query: "", ego: ""});
const EDGE_TYPES = ["assignment", "affiliation", "co_occurrence"];

// Accent- and case-folded key so that "Sao Paulo" finds "São Paulo".
export const searchKey = (value) => String(value ?? "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("en");

// URL hash state. Every key starts with "net" so the groups page keys (q, group, tree, ...) are left alone.
// Defaults are left out of the hash.
export function netHashState(hash = "") {
  const params = new URLSearchParams(String(hash).replace(/^#/, ""));
  const status = params.get("net_status") ?? "";
  return {
    mode: params.get("net") === "co_occurrence" ? "co_occurrence" : "assignments",
    affiliations: params.get("net_aff") === "1",
    externals: params.get("net_ext") !== "0",
    adjacent: params.get("net_adj") !== "0",
    status: Object.hasOwn(STATUS_LABELS, status) ? status : "",
    query: params.get("net_q") || "",
    ego: params.get("net_ego") || ""
  };
}

// Returns the full hash: net keys rewritten from state, every other key in currentHash kept as it was.
export function formatNetHash(state = {}, currentHash = "") {
  const value = {...DEFAULT_STATE, ...state};
  const params = new URLSearchParams(String(currentHash).replace(/^#/, ""));
  for (const key of ["net", "net_aff", "net_ext", "net_adj", "net_status", "net_q", "net_ego"]) params.delete(key);
  if (value.mode === "co_occurrence") params.set("net", "co_occurrence");
  if (value.affiliations) params.set("net_aff", "1");
  if (!value.externals) params.set("net_ext", "0");
  if (!value.adjacent) params.set("net_adj", "0");
  if (value.status) params.set("net_status", value.status);
  if (value.query) params.set("net_q", value.query);
  if (value.ego) params.set("net_ego", value.ego);
  const serialised = params.toString();
  return serialised ? `#${serialised}` : "";
}

// Deterministic fallback layout (golden-angle spiral) used when the payload has no x and y.
export function fallbackPosition(index) {
  const angle = index * 2.399963229728653;
  const radius = 10 * Math.sqrt(index + 1);
  return {x: Number((radius * Math.cos(angle)).toFixed(3)), y: Number((radius * Math.sin(angle)).toFixed(3))};
}

const finite = (value) => Number.isFinite(value);

// Checks the payload and returns clean nodes and edges. Edges with a missing endpoint, an unknown edge_type
// or a stated affiliation without a quote are dropped (T-GRAPH). Positions come from the payload or the fallback.
export function prepareGraph(json) {
  const empty = {nodes: [], edges: [], caution: "", denominatorNote: "", valid: false};
  if (!json || typeof json !== "object") return empty;
  const rawNodes = Array.isArray(json.nodes) ? json.nodes : [];
  const ids = [...new Set(rawNodes.map((node) => String(node?.id ?? "")).filter(Boolean))].sort();
  const position = new Map(ids.map((id, index) => [id, index]));
  const nodes = rawNodes
    .filter((node) => node && position.has(String(node.id)))
    .map((node) => {
      const id = String(node.id);
      const fallback = fallbackPosition(position.get(id));
      return {
        id,
        type: String(node.type ?? ""),
        label: String(node.label ?? id),
        degree: finite(Number(node.degree)) ? Number(node.degree) : 0,
        layer: node.layer === "adjacent" ? "adjacent" : node.layer === "core" ? "core" : "",
        sector: String(node.sector ?? ""),
        status: String(node.status ?? ""),
        x: finite(node.x) ? node.x : fallback.x,
        y: finite(node.y) ? node.y : fallback.y
      };
    });
  const known = new Set(nodes.map((node) => node.id));
  const edges = [];
  (Array.isArray(json.edges) ? json.edges : []).forEach((edge, index) => {
    const source = String(edge?.source ?? "");
    const target = String(edge?.target ?? "");
    if (!known.has(source) || !known.has(target)) return;
    const type = edge.edge_type;
    if (!EDGE_TYPES.includes(type)) return;
    if (type === "affiliation" && !String(edge.quote ?? "").trim()) return;
    edges.push({
      key: `e${index}`,
      edge_type: type,
      source,
      target,
      facet: String(edge.facet ?? ""),
      relation: String(edge.relation ?? ""),
      directed: Boolean(edge.directed),
      url: /^https?:\/\//.test(String(edge.url ?? "")) ? String(edge.url) : "",
      quote: String(edge.quote ?? ""),
      weight: finite(Number(edge.weight)) ? Number(edge.weight) : 1
    });
  });
  return {
    nodes,
    edges,
    caution: String(json.caution ?? ""),
    denominatorNote: String(json.denominator_note ?? ""),
    valid: json.schema === GRAPH_SCHEMA
  };
}

export const isEmptyGraph = (graph) => !graph || graph.nodes.length === 0;

const isGroup = (node) => node.type === "group";
const isExternal = (node) => node.type === "external";

// The edge types a mode draws. Stated affiliations only join the default assignments view.
function edgeTypesFor(state) {
  if (state.mode === "co_occurrence") return ["co_occurrence"];
  return state.affiliations ? ["assignment", "affiliation"] : ["assignment"];
}

function neighbourIds(edges, id) {
  const out = new Set();
  for (const edge of edges) {
    if (edge.source === id) out.add(edge.target);
    else if (edge.target === id) out.add(edge.source);
  }
  return out;
}

// The network for the current state. Returns {nodes, edges, counts}. A node is shown only when it has at least
// one visible edge, so untagged groups never appear. Each edge keeps its edge_type.
export function viewFor(graph, state = {}) {
  const current = {...DEFAULT_STATE, ...state};
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const allowed = new Set(edgeTypesFor(current));
  const hidden = (node) => {
    if (!node) return true;
    if (isGroup(node)) {
      if (node.layer === "adjacent" && !current.adjacent) return true;
      if (current.status && node.status !== current.status) return true;
    }
    return isExternal(node) && !current.externals;
  };
  let edges = graph.edges.filter((edge) => allowed.has(edge.edge_type)
    && !hidden(byId.get(edge.source)) && !hidden(byId.get(edge.target)));
  const needle = searchKey(current.query.trim());
  if (needle) {
    const matches = new Set(
      [...new Set(edges.flatMap((edge) => [edge.source, edge.target]))]
        .filter((id) => searchKey(byId.get(id)?.label).includes(needle))
    );
    const keep = new Set([...matches, ...[...matches].flatMap((id) => [...neighbourIds(edges, id)])]);
    edges = edges.filter((edge) => keep.has(edge.source) && keep.has(edge.target));
  }
  if (current.ego && edges.some((edge) => edge.source === current.ego || edge.target === current.ego)) {
    const keep = new Set([current.ego, ...neighbourIds(edges, current.ego)]);
    edges = edges.filter((edge) => keep.has(edge.source) && keep.has(edge.target));
  }
  const shown = new Set(edges.flatMap((edge) => [edge.source, edge.target]));
  const nodes = graph.nodes.filter((node) => shown.has(node.id));
  return {nodes, edges, counts: {nodes: nodes.length, edges: edges.length}};
}

// Node size by the number of tags (the legend says this is not importance). Falls back to the view degree.
export function nodeSize(node, viewDegree = 0) {
  const degree = Number.isFinite(node?.degree) && node.degree > 0 ? node.degree : viewDegree;
  return Math.min(16, 4 + 2 * Math.sqrt(Math.max(0, degree)));
}

export function degreeMap(edges) {
  const out = new Map();
  for (const edge of edges) {
    out.set(edge.source, (out.get(edge.source) ?? 0) + 1);
    out.set(edge.target, (out.get(edge.target) ?? 0) + 1);
  }
  return out;
}

// Distinct sector values in sorted order; the index picks a colour token in the component.
export function sectorsOf(graph) {
  return [...new Set(graph.nodes.filter(isGroup).map((node) => node.sector).filter(Boolean))].sort();
}

// Ego neighbourhood of a view: the node and its direct neighbours, with the edges between them.
export function egoView(view, id) {
  const keep = new Set([id, ...neighbourIds(view.edges, id)]);
  const edges = view.edges.filter((edge) => keep.has(edge.source) && keep.has(edge.target));
  const nodes = view.nodes.filter((node) => keep.has(node.id));
  return {nodes, edges, counts: {nodes: nodes.length, edges: edges.length}};
}

export function linkLabel(edge) {
  if (!edge) return "";
  if (edge.edge_type === "affiliation") return edge.relation ? edge.relation.replace(/_/g, " ") : EDGE_LABELS.affiliation;
  return EDGE_LABELS[edge.edge_type] ?? "Link";
}
