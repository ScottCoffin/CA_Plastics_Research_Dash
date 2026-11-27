// Runtime checks for the Community groups flows, participation and language views. The helpers live in
// framework/src/components/groups_flows.js. Run with --dump-fixture to print the fixture (groups, vocab and the
// flows.json blocks mirrored from src/atlas/groups/build.py build_flows); tests/test_groups_flows.py compares that
// mirror with the real builder.
import assert from "node:assert/strict";
import {
  EMPTY_MESSAGE, SMALL_CELL, contrastRatio, inkFor,
} from "../framework/src/components/groups_composition.js";
import {GROUP_TAXONOMY} from "../framework/src/components/ambassador_groups.js";
import {
  PARTICIPATION_ORDER, combinationPanels, combinationRows, flowConservation, flowRows, languageName,
  languagePanel, languageRegionCounts, mountGroupsFlows, participationFacets, participationLabel, stageBars, styleFor,
} from "../framework/src/components/groups_flows.js";
import {CHROME, SECONDARY, SEQ, rampFill} from "../framework/src/components/shared/palette.js";

const SECTORS = ["ngo_civil_society", "community_informal", "foundation", "academia_research", "government"];
const CENTRALITY = ["primary", "substantial", "incidental", "none"];
const ACTIVITIES = ["advocacy_campaigning", "cleanup_removal", "research_monitoring", "waste_management_recycling", "education_awareness"];
const PARTICIPATION_VALUES = PARTICIPATION_ORDER.filter((value) => value !== "not_set");
const REGIONS = ["Northern America", "Eastern Africa", "Eastern Asia"];
const LANGUAGES = [["en"], ["en", "es"], ["fr"], [], ["zh", "en"]];
const TAGGED = ["ambassador_tagged", "reviewed", "group_confirmed"];

// 30 tagged groups and 3 roster rows that are not tagged. Each tagged group has a sector, a centrality and one or
// more activities (the first is the principal one). Every third or fourth group adds a second or third activity.
const tagged = Array.from({length: 30}, (_, i) => {
  const activities = [ACTIVITIES[i % 5]];
  if (i % 3 === 0) activities.push(ACTIVITIES[(i + 2) % 5]);
  if (i % 4 === 0) activities.push(ACTIVITIES[(i + 3) % 5]);
  const unique = [...new Set(activities)];
  const researching = unique.includes("research_monitoring");
  return {
    group_id: `cg_${String(i).padStart(16, "0")}`,
    name: `Group ${i}`,
    status: TAGGED[i % 3],
    layer: i % 3 === 0 ? "adjacent" : "core",
    sector: SECTORS[i % 5],
    plastics_centrality: CENTRALITY[i % 4],
    primary_activities: unique,
    participation_in_science: researching ? PARTICIPATION_VALUES[i % PARTICIPATION_VALUES.length] : null,
    region: REGIONS[i % 3],
    website_languages: LANGUAGES[i % 5],
  };
});
const untagged = [0, 1, 2].map((i) => ({
  group_id: `cg_u${i}`, name: `Roster ${i}`, status: "unlabelled", layer: "untagged", sector: null,
  plastics_centrality: null, primary_activities: [], participation_in_science: null, region: "Western Africa",
  website_languages: [],
}));
const groups = [...untagged, ...tagged];

const VOCAB = Object.freeze({
  sector: GROUP_TAXONOMY.sector,
  plastics_centrality: GROUP_TAXONOMY.plastics_centrality,
  primary_activities: GROUP_TAXONOMY.primary_activities,
  participation_in_science: PARTICIPATION_VALUES,
});

const compareLists = (a, b) => {
  for (let i = 0; i < Math.min(a.length, b.length); i += 1) {
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  }
  return a.length - b.length;
};
const pos = (kind, value) => VOCAB[kind].indexOf(value);

/** Mirror of build_flows in src/atlas/groups/build.py, for the same records. */
function mirrorFlows(records) {
  const taggedRecords = records.filter((r) => TAGGED.includes(r.status));
  const first = new Map();
  const second = new Map();
  for (const r of taggedRecords) {
    const fk = JSON.stringify([r.sector, r.plastics_centrality]);
    first.set(fk, (first.get(fk) || 0) + 1);
    const sk = JSON.stringify([r.plastics_centrality, r.primary_activities[0]]);
    second.set(sk, (second.get(sk) || 0) + 1);
  }
  const nodes = [];
  for (const [stage, kind, pick] of [
    ["sector", "sector", (r) => r.sector],
    ["centrality", "plastics_centrality", (r) => r.plastics_centrality],
    ["activity", "primary_activities", (r) => r.primary_activities[0]],
  ]) {
    const values = [...new Set(taggedRecords.map(pick))].sort((a, b) => pos(kind, a) - pos(kind, b));
    for (const value of values) nodes.push({id: `${stage}:${value}`, stage, label: value});
  }
  const firstLinks = [...first].map(([k, n]) => ({s: JSON.parse(k)[0], c: JSON.parse(k)[1], n}))
    .sort((a, b) => pos("sector", a.s) - pos("sector", b.s) || pos("plastics_centrality", a.c) - pos("plastics_centrality", b.c))
    .map(({s, c, n}) => ({source: `sector:${s}`, target: `centrality:${c}`, value: n}));
  const secondLinks = [...second].map(([k, n]) => ({c: JSON.parse(k)[0], a: JSON.parse(k)[1], n}))
    .sort((a, b) => pos("plastics_centrality", a.c) - pos("plastics_centrality", b.c) || pos("primary_activities", a.a) - pos("primary_activities", b.a))
    .map(({c, a, n}) => ({source: `centrality:${c}`, target: `activity:${a}`, value: n}));
  const researching = taggedRecords.filter((r) => r.primary_activities.includes("research_monitoring"));
  const counts = Object.fromEntries([...PARTICIPATION_VALUES, "not_set"].map((v) => [v, 0]));
  for (const r of researching) counts[r.participation_in_science || "not_set"] += 1;
  const combos = new Map();
  for (const r of taggedRecords) {
    const key = JSON.stringify([...new Set(r.primary_activities)].sort((a, b) => pos("primary_activities", a) - pos("primary_activities", b)));
    combos.set(key, (combos.get(key) || 0) + 1);
  }
  const all = [...combos].map(([k, n]) => ({activities: JSON.parse(k), groups: n}));
  const kept = all.filter((c) => c.groups >= 3).sort((a, b) => b.groups - a.groups || compareLists(a.activities, b.activities));
  const rest = all.filter((c) => c.groups < 3);
  return {
    sankey: {stages: ["sector", "centrality", "activity"], nodes, links: [...firstLinks, ...secondLinks]},
    participation: {
      research_monitoring_n: researching.length,
      with_f5_value_n: researching.filter((r) => r.participation_in_science).length,
      counts,
    },
    activity_combinations: {
      min_group_size: 3,
      ordering: "by frequency of tag combinations",
      combinations: kept,
      other: {combinations: rest.length, groups: rest.reduce((sum, c) => sum + c.groups, 0)},
    },
  };
}

const flows = mirrorFlows(groups);
const cases = [];
const check = (name, fn) => cases.push([name, fn]);

check("fixture: 30 tagged groups and 3 untagged rows", () => {
  assert.equal(tagged.length, 30);
  assert.equal(groups.length, 33);
});

// ---- conservation ----
check("each stage total equals the tagged total", () => {
  const stages = stageBars(flows);
  assert.deepEqual(stages.map((s) => s.total), [30, 30, 30]);
  assert.equal(flowConservation(stages, 30).ok, true);
});

check("a broken link breaks conservation", () => {
  const broken = structuredClone(flows);
  broken.sankey.links[0].value += 1;
  assert.equal(flowConservation(stageBars(broken), 30).ok, false);
});

check("flow rows give one row per link, and sector links sum to the tagged total", () => {
  const rows = flowRows(flows);
  assert.equal(rows.length, flows.sankey.links.length);
  assert.ok(rows.every((r) => r.from && r.to), "every link has both ends named");
  const fromSectors = flows.sankey.links.filter((l) => l.source.startsWith("sector:")).reduce((s, l) => s + l.value, 0);
  assert.equal(fromSectors, 30);
});

// ---- ordering: taxonomy order, never by size ----
check("nodes follow taxonomy order even when a later node is larger", () => {
  const sized = {
    sankey: {
      stages: ["sector", "centrality", "activity"],
      nodes: [
        {id: "sector:foundation", stage: "sector", label: "foundation"},
        {id: "sector:ngo_civil_society", stage: "sector", label: "ngo_civil_society"},
        {id: "centrality:primary", stage: "centrality", label: "primary"},
      ],
      links: [
        {source: "sector:foundation", target: "centrality:primary", value: 9},
        {source: "sector:ngo_civil_society", target: "centrality:primary", value: 1},
      ],
    },
  };
  const [sectorBar] = stageBars(sized);
  assert.deepEqual(sectorBar.segments.map((s) => s.value), ["ngo_civil_society", "foundation"]);
  assert.equal(sectorBar.total, 10);
});

check("fixture sector bar follows the taxonomy", () => {
  const [sectorBar] = stageBars(flows);
  const observed = GROUP_TAXONOMY.sector.filter((s) => SECTORS.includes(s));
  assert.deepEqual(sectorBar.segments.map((s) => s.value), observed);
});

// ---- small cells ----
check("segments under the small-cell size are muted and keep their count", () => {
  const segment = stageBars({
    sankey: {
      nodes: [{id: "sector:foundation", stage: "sector", label: "foundation"}, {id: "sector:government", stage: "sector", label: "government"}],
      links: [
        {source: "sector:foundation", target: "centrality:primary", value: 2},
        {source: "sector:government", target: "centrality:primary", value: 7},
      ],
    },
  })[0].segments;
  const foundation = segment.find((s) => s.value === "foundation");
  const government = segment.find((s) => s.value === "government");
  assert.equal(foundation.small, true);
  assert.equal(foundation.fill, CHROME.sunken);
  assert.equal(foundation.text, "2");
  assert.equal(government.small, false);
  assert.equal(government.text, "7");
  assert.equal(SMALL_CELL, 5);
});

check("every palette fill has ink at 4.5:1 or better", () => {
  for (let i = 0; i < SECONDARY.length; i += 1) {
    const style = styleFor(10, i);
    assert.ok(contrastRatio(style.fill, style.ink) >= 4.5, `${style.fill} on ${style.ink}`);
  }
  const muted = styleFor(1, 0);
  assert.ok(contrastRatio(muted.fill, muted.ink) >= 4.5);
  for (let t = 0; t <= 1; t += 0.05) {
    const fill = rampFill(t);
    assert.ok(contrastRatio(fill, inkFor(fill)) >= 4.5, `ramp ${t.toFixed(2)} ${fill}`);
  }
});

// ---- activity combinations ----
check("combinations under 3 groups are collapsed into other combinations", () => {
  const block = {
    activity_combinations: {
      min_group_size: 3,
      ordering: "by frequency of tag combinations",
      combinations: [
        {activities: ["advocacy_campaigning"], groups: 5},
        {activities: ["cleanup_removal"], groups: 2},
        {activities: ["education_awareness"], groups: 1},
      ],
      other: {combinations: 0, groups: 0},
    },
  };
  const combos = combinationRows(block);
  assert.equal(combos.combinationCount, 1);
  assert.equal(combos.rows[0].n, 5);
  const other = combos.rows.at(-1);
  assert.equal(other.label, "Other combinations");
  assert.equal(other.n, 3);
  assert.equal(combos.other.combinations, 2);
  assert.equal(other.small, true);
});

check("combination bars are ranked by frequency and add up to the tagged total", () => {
  const combos = combinationRows(flows);
  const ranked = combos.rows.filter((r) => r.key !== "other");
  const ns = ranked.map((r) => r.n);
  assert.deepEqual(ns, [...ns].sort((x, y) => y - x));
  assert.equal(combos.rows.reduce((s, r) => s + r.n, 0), 30);
  assert.ok(ranked.every((r) => r.n >= 3));
  assert.equal(combos.rows.at(-1).key, "other");
});

check("dot key marks exactly the activities in each combination; other has no dots", () => {
  const combos = combinationRows(flows);
  const {dot, columns} = combinationPanels(combos.rows);
  combos.rows.forEach((row, index) => {
    const cells = dot.dots.filter((c) => c.row === index);
    if (row.key === "other") {
      assert.equal(cells.length, 0);
      return;
    }
    assert.equal(cells.length, columns.length);
    assert.equal(cells.filter((c) => c.on).length, row.activities.length);
  });
});

check("the dot key and the bars share one y domain, height and margins", () => {
  const combos = combinationRows(flows);
  const n = combos.rows.length;
  const {dot, bar} = combinationPanels(combos.rows);
  assert.deepEqual(dot.yDomain, bar.yDomain);
  assert.deepEqual(dot.yDomain, [n - 0.5, -0.5]);
  assert.equal(dot.height, bar.height);
  assert.equal(dot.marginTop, bar.marginTop);
  assert.equal(dot.marginBottom, bar.marginBottom);
  // Each bar and each dot row sits on an integer row index inside the shared domain.
  assert.deepEqual(bar.bars.map((b) => b.row), combos.rows.map((_, i) => i));
  assert.ok(dot.dots.every((d) => Number.isInteger(d.row) && d.row >= 0 && d.row < n));
});

check("the joining line spans only the filled dots of its row, and the bars carry full names", () => {
  const combos = combinationRows(flows);
  const {dot, bar} = combinationPanels(combos.rows);
  for (const join of dot.joins) {
    const filled = dot.dots.filter((d) => d.row === join.row && d.on).map((d) => d.col);
    assert.ok(filled.length >= 2);
    assert.equal(join.x1, Math.min(...filled));
    assert.equal(join.x2, Math.max(...filled));
  }
  combos.rows.forEach((row, i) => {
    assert.ok(bar.bars[i].tip.startsWith(row.label), row.label);
  });
});

// ---- participation ----
check("participation facets: one per sector, rows add up to each sector and the total", () => {
  const facets = participationFacets(groups);
  const researching = tagged.filter((g) => g.primary_activities.includes("research_monitoring"));
  assert.equal(facets.total, researching.length);
  assert.equal(facets.facets.reduce((s, f) => s + f.total, 0), facets.total);
  for (const facet of facets.facets) {
    assert.equal(facet.rows.reduce((s, r) => s + r.n, 0), facet.total);
    assert.deepEqual(facet.rows.map((r) => r.value), PARTICIPATION_ORDER);
  }
  assert.equal(facets.withValue, researching.length);
});

check("participation: groups without a value count as not recorded", () => {
  const facets = participationFacets([
    {status: "reviewed", sector: "foundation", primary_activities: ["research_monitoring"], participation_in_science: null},
    {status: "reviewed", sector: "foundation", primary_activities: ["research_monitoring"], participation_in_science: "collegial"},
    {status: "reviewed", sector: "foundation", primary_activities: ["advocacy_campaigning"], participation_in_science: "collegial"},
  ]);
  assert.equal(facets.total, 2);
  assert.equal(facets.withValue, 1);
  const notSet = facets.facets[0].rows.find((r) => r.value === "not_set");
  assert.equal(notSet.n, 1);
  assert.equal(notSet.label, "Not recorded");
  assert.equal(participationLabel("co_created"), "Co-created");
});

// ---- languages ----
check("language rows are the regions with a tagged group; columns are the languages", () => {
  const counts = languageRegionCounts(groups);
  const panel = languagePanel(counts);
  const expectedRegions = [...new Set(tagged.map((g) => g.region))];
  assert.deepEqual([...panel.rows].sort(), [...expectedRegions].sort());
  assert.ok(!panel.rows.includes("Western Africa"));
  assert.deepEqual(panel.columns.map((c) => c.code), counts.languages.map((l) => l.code));
  for (const region of panel.rows) {
    for (const column of panel.columns) {
      const cells = panel.cells.filter((c) => c.row === region && c.column === column.code);
      assert.equal(cells.length, 1, `${region} / ${column.code}`);
      const expected = tagged.filter((g) => g.region === region && g.website_languages.includes(column.code)).length;
      assert.equal(cells[0].n, expected, `${region} / ${column.code}`);
    }
  }
});

check("languages count each tagged group once, by region", () => {
  const counts = languageRegionCounts(groups);
  assert.equal(counts.total, 30);
  for (const lang of counts.languages) {
    const expected = tagged.filter((g) => g.website_languages.includes(lang.code)).length;
    assert.equal(lang.n, expected, lang.code);
    const cellSum = counts.cells.filter((c) => c.language === lang.code).reduce((s, c) => s + c.n, 0);
    assert.equal(cellSum, expected, lang.code);
  }
  assert.equal(counts.noLanguage, tagged.filter((g) => g.website_languages.length === 0).length);
  assert.ok(!counts.regions.includes("Western Africa"), "untagged regions are left out");
});

check("language names come from the English display names, or the code", () => {
  assert.equal(languageName("en"), "English");
  assert.equal(languageName("zz-not-a-code!"), "zz-not-a-code!");
});

// ---- empty states ----
check("every view is empty without tagged groups", () => {
  assert.equal(EMPTY_MESSAGE, "No groups are tagged yet. These charts fill in as volunteers tag groups.");
  assert.equal(flowConservation(stageBars({}), 0).ok, true);
  assert.equal(stageBars(null)[0].total, 0);
  assert.equal(participationFacets([]).total, 0);
  assert.equal(combinationRows({}).rows.length, 0);
  assert.equal(languageRegionCounts([]).total, 0);
  const untaggedOnly = untagged.map((g) => ({...g}));
  assert.equal(languageRegionCounts(untaggedOnly).total, 0);
});

check("mount without an element does nothing", () => {
  mountGroupsFlows(null, {flows, groups});
});

if (process.argv.includes("--dump-fixture")) {
  process.stdout.write(JSON.stringify({groups, vocab: VOCAB, flows}));
} else {
  for (const [name, fn] of cases) {
    try {
      fn();
    } catch (error) {
      console.error(`FAILED: ${name}`);
      throw error;
    }
  }
  console.log(`${cases.length} groups flows runtime checks passed`);
}
