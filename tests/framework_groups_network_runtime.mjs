// Focused, DOM-free checks for the CG-11 network model (groups_network_model.js). The fixture is synthetic:
// the published groups_graph.json has no tagged groups yet, so this test never reads site/data.
import assert from "node:assert/strict";
import {
  degreeMap,
  egoView,
  formatNetHash,
  isEmptyGraph,
  linkLabel,
  netHashState,
  nodeSize,
  prepareGraph,
  sectorLabel,
  sectorsOf,
  searchKey,
  viewFor
} from "../framework/src/components/groups_network_model.js";

const fixture = {
  schema: "cg-graph-v1",
  caution: "The view reflects tagged groups only.",
  denominator_note: "Denominator note for the test.",
  edge_types: {},
  nodes: [
    {id: "group:g1", type: "group", label: "Alpha Group", degree: 3, layer: "core", sector: "ngo_civil_society", status: "reviewed"},
    {id: "group:g2", type: "group", label: "Beta Group", degree: 2, layer: "adjacent", sector: "government", status: "not_tagged"},
    {id: "group:g3", type: "group", label: "Untagged Group", degree: 0, layer: "core", sector: "other", status: "not_tagged"},
    {id: "activity:a1", type: "activity", label: "Advocacy", degree: 2},
    {id: "activity:a2", type: "activity", label: "Cleanup", degree: 2},
    {id: "activity:a3", type: "activity", label: "Research", degree: 1},
    {id: "theme:t1", type: "theme", label: "Policy", degree: 1},
    {id: "place:p1", type: "place", label: "São Paulo", degree: 1},
    {id: "external:x1", type: "external", label: "Outside Org", degree: 1}
  ],
  edges: [
    {edge_type: "assignment", source: "group:g1", target: "activity:a1", facet: "activity"},
    {edge_type: "assignment", source: "group:g1", target: "activity:a2", facet: "activity"},
    {edge_type: "assignment", source: "group:g1", target: "place:p1", facet: "place"},
    {edge_type: "assignment", source: "group:g2", target: "activity:a1", facet: "activity"},
    {edge_type: "assignment", source: "group:g2", target: "theme:t1", facet: "theme"},
    {edge_type: "affiliation", source: "group:g1", target: "group:g2", relation: "member_of", directed: true, url: "https://example.org/a", quote: "Alpha is a member of Beta."},
    {edge_type: "affiliation", source: "group:g1", target: "external:x1", relation: "partner", quote: ""},
    {edge_type: "affiliation", source: "group:g2", target: "external:x1", relation: "partner", quote: "Beta works with Outside Org."},
    {edge_type: "co_occurrence", source: "activity:a1", target: "activity:a2", weight: 1},
    {edge_type: "co_occurrence", source: "activity:a1", target: "activity:a3", weight: 4},
    {edge_type: "assignment", source: "group:g1", target: "missing:node", facet: "activity"}
  ]
};

const graph = prepareGraph(fixture);
assert.equal(graph.valid, true);
assert.equal(isEmptyGraph(graph), false);
assert.equal(graph.edges.length, 9, "missing endpoint and quote-less affiliation are dropped");
assert.ok(graph.nodes.every((node) => Number.isFinite(node.x) && Number.isFinite(node.y)), "fallback positions fill x and y");
assert.equal(graph.caution, fixture.caution);
assert.equal(graph.denominatorNote, fixture.denominator_note);
assert.deepEqual(prepareGraph({schema: "other", nodes: [], edges: []}).nodes, []);
assert.equal(isEmptyGraph(prepareGraph(null)), true);
assert.equal(isEmptyGraph(prepareGraph({schema: "cg-graph-v1", nodes: [], edges: []})), true);
assert.deepEqual(prepareGraph(fixture).nodes.map((n) => n.id), graph.nodes.map((n) => n.id));

// Default view: group and facet links only, untagged groups never appear, every edge keeps its type.
const base = viewFor(graph, {});
assert.ok(base.edges.every((edge) => edge.edge_type === "assignment"));
assert.equal(base.nodes.some((node) => node.id === "group:g3"), false, "untagged group is not drawn");
assert.equal(base.nodes.some((node) => node.id === "external:x1"), false, "no external without an affiliation");
assert.deepEqual(base.counts, {nodes: base.nodes.length, edges: base.edges.length});
assert.equal(base.counts.edges, 5);

// Stated affiliations join the assignment view with their own edge type; quote-less ones were already dropped.
const withAff = viewFor(graph, {affiliations: true});
assert.ok(withAff.edges.some((edge) => edge.edge_type === "affiliation" && edge.relation === "member_of"));
assert.ok(withAff.edges.some((edge) => edge.edge_type === "assignment"));
assert.equal(withAff.edges.filter((edge) => edge.edge_type === "affiliation").every((edge) => edge.quote.length > 0), true);
assert.equal(withAff.nodes.some((node) => node.id === "external:x1"), true);
assert.equal(viewFor(graph, {affiliations: true, externals: false}).nodes.some((node) => node.id === "external:x1"), false);

// Co-occurrence mode: activity nodes only, co_occurrence edges only.
const co = viewFor(graph, {mode: "co_occurrence", affiliations: true});
assert.ok(co.edges.length === 2 && co.edges.every((edge) => edge.edge_type === "co_occurrence"));
assert.ok(co.nodes.every((node) => node.type === "activity"));
assert.equal(co.counts.edges, 2);

// Filters: adjacent layer, status, and search (accent and case folded).
assert.equal(viewFor(graph, {adjacent: false}).nodes.some((node) => node.id === "group:g2"), false);
assert.equal(viewFor(graph, {status: "reviewed"}).nodes.some((node) => node.id === "group:g2"), false);
assert.equal(viewFor(graph, {status: "reviewed"}).nodes.some((node) => node.id === "group:g1"), true);
assert.equal(searchKey("São Paulo"), "sao paulo");
const found = viewFor(graph, {query: "SAO PAULO"});
assert.ok(found.nodes.some((node) => node.id === "place:p1"));
assert.ok(found.nodes.some((node) => node.id === "group:g1"), "a match keeps its neighbours");
assert.equal(viewFor(graph, {query: "nothing matches this"}).counts.nodes, 0, "no match gives an empty view");

// Ego network: the node and its direct neighbours, with the edges between them.
const full = viewFor(graph, {affiliations: true});
const ego = egoView(full, "group:g1");
assert.ok(ego.nodes.every((node) => node.id === "group:g1" || full.edges.some((edge) => edge.source === "group:g1" && edge.target === node.id || edge.target === "group:g1" && edge.source === node.id)));
assert.equal(ego.nodes.some((node) => node.id === "activity:a3"), false);
assert.equal(viewFor(graph, {ego: "group:g1", affiliations: true}).nodes.some((node) => node.id === "activity:a3"), false);

// Hash state: net keys only, other keys kept, defaults omitted.
const state = {mode: "co_occurrence", affiliations: true, externals: false, adjacent: false, status: "reviewed", query: "x", ego: "group:g1"};
const hash = formatNetHash(state, "#group=abc&tree=function&q=roster");
assert.match(hash, /group=abc/);
assert.match(hash, /tree=function/);
assert.match(hash, /q=roster/);
assert.deepEqual(netHashState(hash), state);
assert.equal(formatNetHash({}, "#group=abc&net=co_occurrence&net_aff=1"), "#group=abc");
assert.deepEqual(netHashState("#net_status=bogus"), {mode: "assignments", affiliations: false, externals: true, adjacent: true, status: "", query: "", ego: ""});
assert.equal(netHashState("#net_ext=0").externals, false);

// Sizes, degrees, sectors and labels.
assert.ok(nodeSize({degree: 9}) > nodeSize({degree: 1}));
assert.ok(nodeSize({degree: 0}, 0) >= 4);
assert.ok(nodeSize({degree: 1000}) <= 16);
assert.equal(degreeMap(base.edges).get("activity:a1"), 2);
assert.deepEqual(sectorsOf(graph), ["government", "ngo_civil_society", "other"]);
assert.equal(sectorLabel("ngo_civil_society"), "NGO or civil society");
assert.equal(sectorLabel("unknown_sector"), "Unknown sector");
assert.equal(linkLabel(withAff.edges.find((edge) => edge.edge_type === "affiliation")), "member of");
assert.equal(linkLabel(co.edges[0]), "Tags used together");

console.log("groups network runtime assertions passed");
