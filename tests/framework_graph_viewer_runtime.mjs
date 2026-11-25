// Runtime checks for the global graph viewer (BQ-V.3). The pure helpers live in
// framework/src/components/graph_viewer_model.js; the DOM component is checked in a browser.
import assert from "node:assert/strict";
import {
  buildAdjacency,
  colourGroups,
  colourOf,
  decodeLayout,
  edgesFromRows,
  exportFiles,
  formatGraphHash,
  formatWorks,
  graphFileKey,
  graphName,
  hashPrefixOk,
  labelIndices,
  matchNodes,
  nodeSize,
  nodesFromRows,
  noteText,
  openAlexUrl,
  parseGraphHash,
  sortNodes,
  topNeighbours,
  usePhone
} from "../framework/src/components/graph_viewer_model.js";
import {OTHER, SECONDARY_ALL_PAIRS} from "../framework/src/components/shared/palette.js";

let passed = 0;
const check = (name, fn) => {
  fn();
  passed += 1;
  console.log(`ok - ${name}`);
};

check("graph names and file keys", () => {
  assert.equal(graphName("authors"), "authors");
  assert.equal(graphName("nope"), "institutions");
  assert.equal(graphFileKey("institutions", false), "institutions");
  assert.equal(graphFileKey("authors", true), "authors_phone");
});

check("phone choice: width <= 860 or forced", () => {
  assert.equal(usePhone("auto", 860), true);
  assert.equal(usePhone(undefined, 861), false);
  assert.equal(usePhone("auto", 390), true);
  assert.equal(usePhone(false, 390), false);
  assert.equal(usePhone("true", 1440), true);
  assert.equal(usePhone(true, 1440), true);
});

check("layout decodes float32 little-endian x, y pairs in node order", () => {
  const buffer = new ArrayBuffer(16);
  const view = new DataView(buffer);
  [[1.5, -2.25], [0.125, 3]].forEach(([x, y], i) => {
    view.setFloat32(8 * i, x, true);
    view.setFloat32(8 * i + 4, y, true);
  });
  const out = decodeLayout(buffer, 2);
  assert.equal(out.length, 4);
  assert.deepEqual([...out], [1.5, -2.25, 0.125, 3]);
});

check("layout rejects a file shorter than its node count", () => {
  assert.throws(() => decodeLayout(new ArrayBuffer(8), 2), /shorter/);
  assert.throws(() => decodeLayout(null, 1), /shorter/);
});

const instJson = {
  nodes: {
    fields: ["id", "display_name", "ror", "country_code", "type", "works", "community"],
    rows: [
      ["I1", "Alpha University", "https://ror.org/a", "US", "education", 40, 0],
      ["I2", "Beta Institute", null, "FR", "government", 10, 1],
      ["I3", "Gamma Lab", null, null, null, 25, 0],
      ["I4", "Delta", null, "US", "facility", 5, null]
    ]
  },
  edges: {rows: [[0, 1, 3], [0, 2, 7], [2, 3, 1]]}
};

check("rows become node objects keyed by field names", () => {
  const nodes = nodesFromRows(instJson);
  assert.equal(nodes.length, 4);
  assert.deepEqual(
    {id: nodes[0].id, name: nodes[0].name, country: nodes[0].country, works: nodes[0].works, community: nodes[0].community, index: nodes[0].index},
    {id: "I1", name: "Alpha University", country: "US", works: 40, community: 0, index: 0}
  );
  assert.equal(nodes[2].country, null);
  assert.equal(nodes[1].ror, null);
  assert.equal(nodes[3].community, null);
});

check("author rows (no ror or type) load with null for missing fields", () => {
  const nodes = nodesFromRows({
    nodes: {fields: ["id", "display_name", "country_code", "works", "community"], rows: [["A1", "Ana Ruiz", "NL", 9, 2]]},
    edges: {rows: []}
  });
  assert.equal(nodes[0].name, "Ana Ruiz");
  assert.equal(nodes[0].type, null);
  assert.equal(nodes[0].ror, null);
  assert.equal(nodes[0].country, "NL");
});

check("bad rows and duplicate ids are rejected", () => {
  assert.throws(() => nodesFromRows({nodes: {fields: ["id"], rows: [["a", "b"]]}}), /does not match/);
  assert.throws(() => nodesFromRows({nodes: {fields: ["id"], rows: [["a"], ["a"]]}}), /duplicate/);
});

check("edges map to indices and reject out-of-range endpoints", () => {
  const edges = edgesFromRows(instJson, 4);
  assert.deepEqual(edges[1], {source: 0, target: 2, weight: 7});
  assert.throws(() => edgesFromRows({edges: {rows: [[0, 9, 1]]}}, 4), /outside/);
  assert.throws(() => edgesFromRows({edges: {rows: [[1, 1, 1]]}}, 4), /outside/);
});

check("colours: top six groups by node count, the rest and unknowns grey", () => {
  const keys = [0, 0, 0, 1, 1, 2, 3, 4, 5, 6, 7, null, undefined];
  const out = colourGroups(keys);
  assert.equal(out.legend.length, SECONDARY_ALL_PAIRS.length);
  assert.equal(out.legend[0].key, 0);
  assert.equal(out.legend[0].count, 3);
  assert.equal(colourOf(out.colours, 0), SECONDARY_ALL_PAIRS[0]);
  assert.equal(colourOf(out.colours, 6), OTHER);
  assert.equal(out.otherCount, 2);
  assert.equal(colourOf(out.colours, null), OTHER);
  assert.equal(colourOf(out.colours, "missing"), OTHER);
});

check("colour ties keep key order and string keys sort as text", () => {
  const out = colourGroups(["b", "a", "b", "a"]);
  assert.deepEqual(out.legend.map((row) => row.key), ["a", "b"]);
  assert.equal(out.legend[0].colour, SECONDARY_ALL_PAIRS[0]);
  assert.equal(out.otherCount, 0);
});

check("node size scales with the square root of works", () => {
  assert.equal(nodeSize(0, 100), 2.5);
  assert.equal(nodeSize(100, 100), 16);
  const half = nodeSize(25, 100);
  assert.ok(Math.abs(half - (2.5 + 13.5 * 0.5)) < 1e-9);
  assert.equal(nodeSize(5, 0), 2.5);
});

check("labels go to the top-N nodes by works, ties by index", () => {
  const nodes = nodesFromRows(instJson);
  assert.deepEqual([...labelIndices(nodes, 2)].sort(), [0, 2]);
  assert.deepEqual([...labelIndices(nodes, 0)], []);
  assert.equal(labelIndices(nodes, 99).size, 4);
});

check("adjacency and neighbours sort by weight then index", () => {
  const nodes = nodesFromRows(instJson);
  const adjacency = buildAdjacency(edgesFromRows(instJson, nodes.length), nodes.length);
  assert.deepEqual(topNeighbours(adjacency, 0, 10).map((n) => n.index), [2, 1]);
  assert.deepEqual(topNeighbours(adjacency, 0, 1), [{index: 2, weight: 7}]);
  assert.deepEqual(topNeighbours(adjacency, 3, 10), [{index: 2, weight: 1}]);
});

check("search folds diacritics, puts name starts first, and caps results", () => {
  const nodes = nodesFromRows({
    nodes: {
      fields: ["id", "display_name", "works"],
      rows: [["A1", "Anna Müller", 3], ["A2", "Hans Mueller-Lang", 9], ["A3", "Anna Schmidt", 5], ["A4", "Lena Muller", 1]]
    },
    edges: {rows: []}
  });
  assert.deepEqual(matchNodes(nodes, "muller").map((n) => n.id), ["A1", "A4"]);
  assert.deepEqual(matchNodes(nodes, "mueller").map((n) => n.id), ["A2"]);
  assert.deepEqual(matchNodes(nodes, "anna").map((n) => n.id), ["A3", "A1"]);
  assert.deepEqual(matchNodes(nodes, "a").map((n) => n.id), ["A3", "A1", "A2", "A4"]);
  assert.deepEqual(matchNodes(nodes, "   "), []);
  assert.equal(matchNodes(nodes, "a", 2).length, 2);
});

check("table sort is numeric for works and textual for name", () => {
  const nodes = nodesFromRows(instJson);
  assert.deepEqual(sortNodes(nodes, "works", "desc").map((n) => n.id), ["I1", "I3", "I2", "I4"]);
  assert.deepEqual(sortNodes(nodes, "works", "asc").map((n) => n.id), ["I4", "I2", "I3", "I1"]);
  assert.deepEqual(sortNodes(nodes, "name", "asc").map((n) => n.name)[0], "Alpha University");
  assert.equal(sortNodes(nodes, "community", "asc").at(-1).id, "I2");
});

check("hash parses the documented keys and rejects bad values", () => {
  assert.deepEqual(
    parseGraphHash("#g=authors&n=A5023220319&z=0.25&x=0.4&y=0.61"),
    {graph: "authors", node: "A5023220319", zoom: 0.25, x: 0.4, y: 0.61}
  );
  assert.deepEqual(parseGraphHash("#g=other&n=<script>&z=-1&x=abc"), {});
  assert.deepEqual(parseGraphHash("#n=I12&z=5000"), {node: "I12"});
  assert.deepEqual(parseGraphHash(""), {});
});

check("hash serialises with rounding and round-trips", () => {
  const hash = formatGraphHash({graph: "institutions", node: "I19820366", zoom: 0.123456789, x: 0.5, y: 0.25});
  assert.equal(hash, "#g=institutions&n=I19820366&z=0.1235&x=0.5&y=0.25");
  assert.deepEqual(parseGraphHash(hash), {graph: "institutions", node: "I19820366", zoom: 0.1235, x: 0.5, y: 0.25});
  assert.equal(formatGraphHash({graph: "x", node: "a b"}), "");
  assert.equal(formatGraphHash({}), "");
});

check("manifest note reads a string or an is / is_not object", () => {
  assert.equal(noteText("plain"), "plain");
  assert.equal(noteText({is: "A graph.", is_not: "Not a measure."}), "A graph. Not a measure.");
  assert.equal(noteText(null), "");
});

check("works wording and OpenAlex links", () => {
  assert.equal(formatWorks(1), "1 work");
  assert.equal(formatWorks(2970), "2,970 works");
  assert.equal(openAlexUrl("A5023220319"), "https://openalex.org/A5023220319");
  assert.equal(openAlexUrl("../x"), null);
});

check("hash prefix keeps the viewer keys apart from the page's own keys", () => {
  assert.equal(hashPrefixOk("gv."), true);
  assert.equal(hashPrefixOk(""), true);
  assert.equal(hashPrefixOk("gv.<x>"), false);
  const page = "#scope=cont%3AEurope&view=network&gv.g=authors&gv.n=A5023220319&gv.z=0.25";
  assert.deepEqual(parseGraphHash(page, "gv."), {graph: "authors", node: "A5023220319", zoom: 0.25});
  assert.deepEqual(parseGraphHash(page), {});
  // Writing replaces only the viewer's keys and keeps scope= and view=.
  const written = formatGraphHash({graph: "institutions", node: "I19820366", zoom: 0.5, x: 0.1, y: 0.2}, "gv.", page);
  assert.equal(written, "#scope=cont%3AEurope&view=network&gv.g=institutions&gv.n=I19820366&gv.z=0.5&gv.x=0.1&gv.y=0.2");
  assert.deepEqual(parseGraphHash(written, "gv."), {graph: "institutions", node: "I19820366", zoom: 0.5, x: 0.1, y: 0.2});
  // An empty state drops only the viewer's keys; with no prefix the viewer keys are the bare names.
  assert.equal(formatGraphHash({}, "gv.", page), "#scope=cont%3AEurope&view=network");
  assert.equal(formatGraphHash({graph: "authors"}, "", "#scope=world&g=institutions"), "#scope=world&g=authors");
});

check("export rows: only the graph's GEXF and GraphML files, plain names, GEXF first", () => {
  const manifest = {files: [
    {file: "authors.graphml.gz", format: "graphml", graph: "authors", bytes: 1114768},
    {file: "institutions.graphml.gz", format: "graphml", graph: "institutions", bytes: 1159056},
    {file: "institutions.gexf.gz", format: "gexf", graph: "institutions", bytes: 1327908},
    {file: "../evil.gexf", format: "gexf", graph: "institutions", bytes: 1},
    {file: "california_network.gexf", format: "gexf"}
  ]};
  assert.deepEqual(exportFiles(manifest, "institutions"), [
    {file: "institutions.gexf.gz", format: "gexf", label: "GEXF", bytes: 1327908},
    {file: "institutions.graphml.gz", format: "graphml", label: "GraphML", bytes: 1159056}
  ]);
  assert.deepEqual(exportFiles(manifest, "other"), []);
  assert.deepEqual(exportFiles(null, "authors"), []);
});

console.log(`framework graph viewer runtime: ${passed} checks passed`);
