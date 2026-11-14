// Runtime checks for the collaboration network model (S9.4 web view).
// The pure helpers live in framework/src/components/network_model.js.
import assert from "node:assert/strict";
import {
  COMMUNITY_COLOURS,
  communityColourMap,
  connectedIds,
  edgeStroke,
  edgeWeight,
  emptyNetworkState,
  formatNetworkHash,
  colourGroups,
  graphAttributes,
  groupCounts,
  layoutToView,
  legendGroups,
  matchingNodeIds,
  neighbourIds,
  networkSummary,
  nodeColour,
  nodeGroup,
  nodeRadius,
  normalizeNetworkState,
  OTHER_COLOUR,
  OTHER_GROUP,
  parseNetworkHash,
  sectorLabel,
  sectorOptions,
  shownEdgeWeights,
  sigmaNodeSize,
  sortByCollaborators,
  tagOptions,
  topCoauthors,
  yearBounds
} from "../framework/src/components/network_model.js";

// Hash round trip: every filter survives format then parse, and unknown keys are ignored.
{
  const state = normalizeNetworkState({
    topic: "air",
    sector: "UC",
    institution: "Davis & co",
    yearFrom: 2015,
    yearTo: 2024,
    minWorks: 3,
    currentOnly: true
  });
  const hash = formatNetworkHash(state);
  assert.equal(hash, "#topic=air&sector=UC&inst=Davis%20%26%20co&year_from=2015&year_to=2024&min=3&now=ca");
  assert.deepEqual(parseNetworkHash(hash), state);
  assert.equal(formatNetworkHash(emptyNetworkState()), "");
  assert.deepEqual(parseNetworkHash(""), emptyNetworkState());
  assert.deepEqual(
    parseNetworkHash("#min=99&year_from=2024&year_to=2010&bogus=1"),
    normalizeNetworkState({minWorks: 10, yearFrom: 2010, yearTo: 2024})
  );
  assert.deepEqual(parseNetworkHash("#inst=%E0%A4%A&min=abc"), normalizeNetworkState({institution: "%E0%A4%A"}));
}

// Year-range edge weights: sum of the yearly counts inside the range, both ends inclusive.
{
  const edge = {source: "a", target: "b", weight: 5, years: {"2019": 1, "2020": 4}};
  assert.equal(edgeWeight(edge), 5);
  assert.equal(edgeWeight(edge, 2019, 2019), 1);
  assert.equal(edgeWeight(edge, 2019, 2020), 5);
  assert.equal(edgeWeight(edge, 2020, null), 4);
  assert.equal(edgeWeight(edge, null, 2018), 0);
  assert.deepEqual(yearBounds([edge, {years: {"2024": 2}}]), {min: 2019, max: 2024});
  assert.deepEqual(yearBounds([]), {min: null, max: null});
}

// Fixture: a-b (5 works), a-c (2 works, 2024 only), b-c (1 work, 2010); d is isolated.
const nodes = [
  {id: "a", name: "Ann", community: 0, degree: 2, plastic_works: 9, topics: ["air"], sectors: ["UC"],
    institutions: ["UC Davis"], primary_affiliations: ["UC Davis"], current_in_ca: true, x: -1, y: 0},
  {id: "b", name: "Ben", community: 0, degree: 2, plastic_works: 4, topics: [], sectors: ["CSU"],
    institutions: ["Cal Poly"], primary_affiliations: ["Cal Poly"], current_in_ca: false, x: 0, y: 1},
  {id: "c", name: "Cy", community: 1, degree: 2, plastic_works: 1, topics: ["air"], sectors: ["UC"],
    institutions: ["UCLA"], primary_affiliations: ["UCLA"], current_in_ca: true, x: 1, y: -1},
  {id: "d", name: "Dee", community: 2, degree: 0, plastic_works: 2, topics: [], sectors: ["private"],
    institutions: ["Acme Corp"], primary_affiliations: [], current_in_ca: false, x: 0.5, y: 0.5}
];
const edges = [
  {source: "a", target: "b", weight: 5, years: {"2019": 1, "2020": 4}},
  {source: "a", target: "c", weight: 2, years: {"2024": 2}},
  {source: "b", target: "c", weight: 1, years: {"2010": 1}}
];
const everyone = new Set(["a", "b", "c", "d"]);

// Node filters: topic, sector, institution text (case-insensitive), now in California.
{
  const ids = (state) => [...matchingNodeIds(nodes, normalizeNetworkState(state))].sort();
  assert.deepEqual(ids({}), ["a", "b", "c", "d"]);
  assert.deepEqual(ids({topic: "air"}), ["a", "c"]);
  assert.deepEqual(ids({sector: "UC"}), ["a", "c"]);
  assert.deepEqual(ids({institution: "uc"}), ["a", "c"]);
  assert.deepEqual(ids({institution: "ACME"}), ["d"]);
  assert.deepEqual(ids({currentOnly: true}), ["a", "c"]);
  assert.deepEqual(ids({topic: "air", sector: "UC", currentOnly: true}), ["a", "c"]);
  assert.deepEqual(ids({topic: "air", sector: "CSU"}), []);
}

// Edge filters: endpoint visibility, range weight, minimum works, zero-weight edges hidden.
{
  assert.deepEqual(shownEdgeWeights(edges, everyone, {}), [5, 2, 1]);
  assert.deepEqual(shownEdgeWeights(edges, everyone, {minWorks: 2}), [5, 2, 0]);
  assert.deepEqual(shownEdgeWeights(edges, everyone, {yearFrom: 2019, yearTo: 2020}), [5, 0, 0]);
  assert.deepEqual(shownEdgeWeights(edges, everyone, {yearFrom: 2019, yearTo: 2024, minWorks: 3}), [5, 0, 0]);
  assert.deepEqual(shownEdgeWeights(edges, new Set(["a", "c"]), {}), [0, 2, 0]);
  assert.deepEqual(shownEdgeWeights(edges, everyone, {yearFrom: 2025}), [0, 0, 0]);
}

// Neighbour lookup, connected nodes, dimmed nodes and summary counts use only shown links.
{
  assert.deepEqual([...neighbourIds(edges, [5, 2, 1], "a")].sort(), ["b", "c"]);
  assert.deepEqual([...neighbourIds(edges, [5, 0, 0], "a")], ["b"]);
  assert.deepEqual([...neighbourIds(edges, [0, 0, 0], "a")], []);
  assert.deepEqual([...connectedIds(edges, [5, 0, 0])].sort(), ["a", "b"]);
  const weights = shownEdgeWeights(edges, everyone, {yearFrom: 2019, yearTo: 2020});
  const dimmed = [...everyone].filter((id) => !connectedIds(edges, weights).has(id)).sort();
  assert.deepEqual(dimmed, ["c", "d"]);
  assert.deepEqual(networkSummary(everyone, [5, 0, 0]), {experts: 4, links: 1});
}

// Table order: most collaborators first, then name; only matching experts.
{
  assert.deepEqual(sortByCollaborators(nodes, everyone).map((n) => n.id), ["a", "b", "c", "d"]);
  assert.deepEqual(sortByCollaborators(nodes, new Set(["a", "c", "d"])).map((n) => n.id), ["a", "c", "d"]);
}

// Option lists, labels and community colours.
{
  assert.deepEqual(tagOptions(nodes), ["air"]);
  assert.deepEqual(sectorOptions(nodes), ["CSU", "private", "UC"]);
  assert.equal(sectorLabel("UC"), "University of California");
  assert.equal(sectorLabel("mystery"), "mystery");
  const colours = communityColourMap(nodes);
  assert.deepEqual([...colours.keys()], [0, 1, 2]);
  assert.equal(colours.get(0), COMMUNITY_COLOURS[0]);
  assert.equal(colours.get(2), COMMUNITY_COLOURS[2]);
  assert.equal(colours.get(9), undefined);
}

// Sizes: radius grows with the square root of works; stroke grows with weight, capped.
{
  assert.equal(nodeRadius(0, 16), 4);
  assert.equal(nodeRadius(16, 16), 16);
  assert.equal(nodeRadius(4, 16), 10);
  assert.equal(edgeStroke(1), 1.2);
  assert.equal(edgeStroke(100), 8);
}

// Layout: every node lands inside the view with its padding.
{
  const view = layoutToView(nodes);
  assert.equal(view.size, 4);
  for (const point of view.values()) {
    assert.ok(point.x >= 40 && point.x <= 960, `x ${point.x}`);
    assert.ok(point.y >= 40 && point.y <= 960, `y ${point.y}`);
  }
  assert.deepEqual(layoutToView([]), new Map());
}

// sigma graph helpers: groups by colour mode, legend rows, colours, sizes.
{
  assert.equal(nodeGroup(nodes[0], "cluster"), "0");
  assert.equal(nodeGroup(nodes[1], "topic"), null);
  assert.equal(nodeGroup(nodes[0], "sector"), "UC");
  assert.deepEqual([...groupCounts(nodes, "cluster")], [["0", 2], ["1", 1], ["2", 1]]);
  assert.deepEqual([...groupCounts(nodes, "topic")], [["air", 2]]);
  const clusterColours = colourGroups(nodes, "cluster");
  assert.deepEqual([...clusterColours.keys()], ["0", "1", "2"]);
  assert.equal(clusterColours.get("0"), COMMUNITY_COLOURS[0]);
  assert.equal(colourGroups(nodes, "topic", () => "#123456").get("air"), "#123456");
  assert.equal(colourGroups(nodes, "topic").get("air"), COMMUNITY_COLOURS[0]);
  const clusterLegend = legendGroups(nodes, "cluster", clusterColours);
  assert.deepEqual(
    clusterLegend.map((g) => [g.key, g.count, g.label]),
    [["0", 2, "Cluster 1"], ["1", 1, "Cluster 2"], ["2", 1, "Cluster 3"]]
  );
  const topicColours = colourGroups(nodes, "topic");
  const topicLegend = legendGroups(nodes, "topic", topicColours, (tag) => `Topic ${tag}`);
  assert.deepEqual(
    topicLegend.map((g) => [g.key, g.count, g.label]),
    [["air", 2, "Topic air"], [OTHER_GROUP, 2, "Other topics"]]
  );
  assert.deepEqual(
    legendGroups(nodes, "sector", colourGroups(nodes, "sector")).map((g) => g.label),
    ["University of California", "California State University", "Private"]
  );
  assert.equal(nodeColour(nodes[3], "cluster", clusterColours), COMMUNITY_COLOURS[2]);
  assert.equal(nodeColour(nodes[1], "topic", topicColours), OTHER_COLOUR);
  assert.equal(sigmaNodeSize(0, 9), 3);
  assert.equal(sigmaNodeSize(9, 9), 14);
  assert.ok(Math.abs(sigmaNodeSize(4, 9) - 10.3333) < 1e-3);
}

// Graph rows: filters, hidden legend groups, saved positions, colour fallback.
{
  const all = graphAttributes(nodes, edges, {}, "cluster", "works");
  assert.deepEqual(all.nodes.map((n) => n.key), ["a", "b", "c", "d"]);
  assert.deepEqual(
    all.edges.map((e) => [e.key, e.source, e.target, e.weight]),
    [["e0", "a", "b", 5], ["e1", "a", "c", 2], ["e2", "b", "c", 1]]
  );
  assert.equal(all.nodes[0].label, "Ann");
  assert.equal(all.nodes[0].color, COMMUNITY_COLOURS[0]);
  assert.equal(all.nodes[0].size, 14);
  assert.equal(all.nodes[0].x, -1);
  const noCluster1 = graphAttributes(nodes, edges, {}, "cluster", "works", {hiddenGroups: new Set(["1"])});
  assert.deepEqual(noCluster1.nodes.map((n) => n.key), ["a", "b", "d"]);
  assert.deepEqual(noCluster1.edges.map((e) => e.key), ["e0"]);
  const minTwo = graphAttributes(nodes, edges, {minWorks: 2}, "cluster", "works");
  assert.deepEqual(minTwo.edges.map((e) => e.key), ["e0", "e1"]);
  const current = graphAttributes(nodes, edges, {currentOnly: true}, "cluster", "collaborators", {
    positions: new Map([["a", {x: 5, y: 6}]])
  });
  assert.deepEqual(current.nodes.map((n) => n.key), ["a", "c"]);
  assert.deepEqual([current.nodes[0].x, current.nodes[0].y], [5, 6]);
  assert.deepEqual(current.edges.map((e) => e.key), ["e1"]);
  assert.equal(current.nodes[0].size, 14);
  const byTopic = graphAttributes(nodes, edges, {}, "topic", "works", {colours: new Map([["air", "#111111"]])});
  assert.deepEqual(
    byTopic.nodes.map((n) => [n.key, n.color]),
    [["a", "#111111"], ["b", OTHER_COLOUR], ["c", "#111111"], ["d", OTHER_COLOUR]]
  );
  const noOther = graphAttributes(nodes, edges, {}, "topic", "works", {
    colours: new Map([["air", "#111111"]]),
    hiddenGroups: new Set([OTHER_GROUP])
  });
  assert.deepEqual(noOther.nodes.map((n) => n.key), ["a", "c"]);
  assert.deepEqual(noOther.edges.map((e) => e.key), ["e1"]);
  assert.deepEqual(graphAttributes([], [], {}, "cluster", "works").nodes, []);
}

// Co-authors: shown links only, most shared works first.
{
  assert.deepEqual(topCoauthors(edges, [5, 2, 1], "a", 8), [{id: "b", weight: 5}, {id: "c", weight: 2}]);
  assert.deepEqual(topCoauthors(edges, [5, 0, 1], "a", 8), [{id: "b", weight: 5}]);
  assert.deepEqual(topCoauthors(edges, [5, 2, 1], "a", 1), [{id: "b", weight: 5}]);
  assert.deepEqual(topCoauthors(edges, [5, 2, 1], "c", 8).map((r) => r.id), ["a", "b"]);
  assert.deepEqual(topCoauthors(edges, [5, 2, 1], "d", 8), []);
}

console.log("framework_network_runtime: all checks passed");
