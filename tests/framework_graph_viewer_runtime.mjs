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
  manifestNoteFor,
  manifestPathFor,
  matchNodes,
  maxWorks,
  nodeSize,
  nodesFromRows,
  noteText,
  openAlexUrl,
  parseGraphHash,
  sizeValue,
  sortNodes,
  formatWorksFilter,
  normaliseWorksFilter,
  parseWorksFilter,
  topNeighbours,
  topSteps,
  usePhone,
  visibleWorks,
  worksFilterDefaults
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
  const linked = nodes.map((n, i) => ({...n, links: [1, 3, 0, 2][i]}));
  assert.deepEqual(sortNodes(linked, "links", "desc").map((n) => n.id), ["I2", "I4", "I1", "I3"]);
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

const worksJson = {
  graph: "works",
  nodes: {
    fields: ["id", "title", "year", "cited_by_count", "embedding_quality", "community"],
    rows: [
      ["W1", "Microplastics in soil", 2019, 120, "ok", 0],
      ["W2", "Plastique en mer", 2011, 4, "low", 1],
      ["W3", "Plastic litter on beaches", 2015, 40, "ok", 0]
    ]
  },
  edges: {fields: ["source", "target", "weight"], rows: [[0, 1, 0.912], [0, 2, 0.8]]}
};

check("works: graph name, file keys and the works manifest path", () => {
  assert.equal(graphName("works"), "works");
  assert.equal(graphFileKey("works", true), "works_phone");
  assert.equal(graphFileKey("works", false), "works");
  assert.equal(manifestPathFor("works"), "graphs/works_manifest.json");
  assert.equal(manifestPathFor("authors"), "graphs/graphs_manifest.json");
  assert.equal(manifestPathFor("institutions"), "graphs/graphs_manifest.json");
});

check("manifest note for each graph reads its own manifest field", () => {
  assert.equal(manifestNoteFor("works", {what_this_is: "Works note."}), "Works note.");
  assert.equal(manifestNoteFor("authors", {author_graph: {what_this_is_and_is_not: {is: "A.", is_not: "B."}}}), "A. B.");
  assert.equal(manifestNoteFor("institutions", {what_this_is_and_is_not: "Inst note."}), "Inst note.");
  assert.equal(manifestNoteFor("works", null), "");
});

check("works rows load as nodes: title becomes the name, quality and year are kept", () => {
  const nodes = nodesFromRows(worksJson);
  assert.equal(nodes[1].id, "W2");
  assert.equal(nodes[1].name, "Plastique en mer");
  assert.equal(nodes[1].embedding_quality, "low");
  assert.equal(nodes[1].year, 2011);
  assert.equal(nodes[1].cited_by_count, 4);
  const edges = edgesFromRows(worksJson, nodes.length);
  assert.deepEqual(edges[0], {source: 0, target: 1, weight: 0.912});
});

check("works dots size by links, other graphs by works", () => {
  const nodes = nodesFromRows(worksJson);
  const adjacency = buildAdjacency(edgesFromRows(worksJson, nodes.length), nodes.length);
  nodes.forEach((node) => { node.links = adjacency[node.index].length; });
  assert.equal(sizeValue(nodes[0], "works"), 2);
  assert.equal(sizeValue(nodes[1], "works"), 1);
  assert.equal(sizeValue(nodes[0], "institutions"), 0);
  assert.equal(maxWorks(nodes, "works"), 2);
  assert.equal(maxWorks(nodes), 0);
  assert.deepEqual([...labelIndices(nodes, 1, "works")], [0]);
});

check("works table sorts by citations and by year", () => {
  const nodes = nodesFromRows(worksJson);
  assert.deepEqual(sortNodes(nodes, "cited", "desc").map((n) => n.id), ["W1", "W3", "W2"]);
  assert.deepEqual(sortNodes(nodes, "year", "asc").map((n) => n.id), ["W2", "W3", "W1"]);
});

check("works hash selects the works graph and keeps the page's keys", () => {
  assert.deepEqual(parseGraphHash("#gv.g=works&gv.n=W1", "gv."), {graph: "works", node: "W1"});
  assert.deepEqual(parseGraphHash("#g=works"), {graph: "works"});
});

// Works view controls. Defaults come from the data; null years are ignored when the range is set.
const yearNodes = [
  {index: 0, year: 2019}, {index: 1, year: null}, {index: 2, year: 2011}, {index: 3, year: 2015}
];

check("works filter defaults: the data's top count and year range, null years ignored", () => {
  assert.deepEqual(worksFilterDefaults(yearNodes), {top: 4, yearMin: 2011, yearMax: 2019});
  assert.deepEqual(worksFilterDefaults([{index: 0, year: null}]), {top: 1, yearMin: null, yearMax: null});
  assert.deepEqual(topSteps(15000), [500, 1000, 2000, 5000, 10000, 15000]);
  assert.deepEqual(topSteps(5000), [500, 1000, 2000, 5000]);
  assert.deepEqual(topSteps(3000), [500, 1000, 2000, 3000]);
  assert.deepEqual(topSteps(0), []);
});

const worksDefaults = {top: 15000, yearMin: 2000, yearMax: 2020};

check("works filter clamps top to the nearest step and years to the data range", () => {
  assert.equal(normaliseWorksFilter({top: 1234}, worksDefaults).top, 1000);
  assert.equal(normaliseWorksFilter({top: 100}, worksDefaults).top, 500);
  assert.equal(normaliseWorksFilter({top: 99999}, worksDefaults).top, 15000);
  assert.equal(normaliseWorksFilter({top: "abc"}, worksDefaults).top, 15000);
  assert.deepEqual(normaliseWorksFilter({yearMin: 1990, yearMax: 2100}, worksDefaults), {top: 15000, yearMin: 2000, yearMax: 2020});
  assert.equal(normaliseWorksFilter({yearMin: 2010.4}, worksDefaults).yearMin, 2010);
  assert.equal(normaliseWorksFilter({yearMin: null}, worksDefaults).yearMin, 2000);
});

check("works filter hash round trip keeps other keys and leaves out defaults", () => {
  const state = {top: 2000, yearMin: 2005, yearMax: 2010};
  const hash = formatWorksFilter(state, "gv.", "#g=works&gv.n=W1", worksDefaults);
  assert.equal(hash, "#g=works&gv.n=W1&gv.top=2000&gv.y0=2005&gv.y1=2010");
  assert.deepEqual(parseWorksFilter(hash, "gv.", worksDefaults), state);
  assert.equal(formatWorksFilter(worksDefaults, "gv.", "#g=works&gv.n=W1", worksDefaults), "#g=works&gv.n=W1");
  assert.equal(formatWorksFilter(worksDefaults, "gv.", "#gv.top=2000&gv.y0=2005", worksDefaults), "");
  assert.equal(formatWorksFilter({top: 2000, yearMin: null, yearMax: 2010}, "", ""), "#top=2000&y1=2010");
  assert.deepEqual(parseWorksFilter("#top=1&y0=abc", "", worksDefaults), {top: 500, yearMin: 2000, yearMax: 2020});
});

// 1200 works: every 7th has no year; the others run 2000 to 2009 (index order is citation order).
const gridNodes = Array.from({length: 1200}, (_, i) => ({index: i, id: `W${i}`, year: i % 7 === 0 ? null : 2000 + (i % 10)}));
const indices = (set) => [...set].sort((a, b) => a - b);
const expectedWorks = (top, from, to) => gridNodes
  .filter((n) => n.index < top && n.year !== null && n.year >= from && n.year <= to)
  .map((n) => n.index);

check("visible works: top only (null years shown on the full range), years only, both", () => {
  const full = worksFilterDefaults(gridNodes);
  assert.deepEqual([full.top, full.yearMin, full.yearMax], [1200, 2000, 2009]);
  const topOnly = visibleWorks(gridNodes, {top: 1000, yearMin: 2000, yearMax: 2009});
  assert.equal(topOnly.size, 1000);
  assert.ok(topOnly.has(0) && topOnly.has(999) && !topOnly.has(1000));
  assert.deepEqual(indices(visibleWorks(gridNodes, {top: 1200, yearMin: 2003, yearMax: 2004})), expectedWorks(1200, 2003, 2004));
  assert.deepEqual(indices(visibleWorks(gridNodes, {top: 500, yearMin: 2003, yearMax: 2004})), expectedWorks(500, 2003, 2004));
});

check("visible works: null-year works are hidden once the year range is narrowed", () => {
  const full = visibleWorks(gridNodes, {top: 1200, yearMin: 2000, yearMax: 2009});
  assert.equal(full.size, 1200);
  assert.ok(full.has(0));
  const narrowed = visibleWorks(gridNodes, {top: 1200, yearMin: 2000, yearMax: 2008});
  assert.ok(!narrowed.has(0));
  assert.ok([...narrowed].every((i) => gridNodes[i].year !== null));
});

console.log(`framework graph viewer runtime: ${passed} checks passed`);
