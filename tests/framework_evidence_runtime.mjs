// Runtime checks for the Framework Evidence map shell helpers (EM-5b).
// The pure helpers live in framework/src/components/evidence_model.js; the selection check runs
// the shared AT-4 engine (site/assets/facets.js) over a tiny synthetic bundle.
import assert from "node:assert/strict";
import {createRequire} from "node:module";
import {fileURLToPath} from "node:url";
import {
  emptyState,
  formatHash,
  pageWorks,
  parseHash,
  safeHttpUrl,
  sanitizeState,
  selectionFor,
  sortWorksNewestFirst,
  stripEntries,
  worksMetaMap
} from "../framework/src/components/evidence_model.js";

const require = createRequire(import.meta.url);
const {BitmaskIndex} = require(fileURLToPath(new URL("../site/assets/facets.js", import.meta.url)));

// Hash round trip.
{
  assert.equal(formatHash(emptyState()), "");
  assert.deepEqual(parseHash(""), emptyState());
  assert.deepEqual(parseHash("#"), emptyState());

  const full = {
    facets: {topic: ["air", "fate_transport_and_sorption"], ca_led: ["yes"], institution: ["I138285227"]},
    yearFrom: 2015, yearTo: 2024, q: "lead paint"
  };
  const hash = formatHash(full);
  assert.equal(hash, "#topic=air,fate_transport_and_sorption&ca_led=yes&institution=I138285227&year_from=2015&year_to=2024&q=lead%20paint");
  assert.deepEqual(parseHash(hash), full);
  assert.deepEqual(parseHash(hash).facets.topic, ["air", "fate_transport_and_sorption"]);

  const years = {...emptyState(), yearFrom: 2010};
  assert.equal(formatHash(years), "#year_from=2010");
  assert.deepEqual(parseHash("#year_from=2010"), years);
  assert.equal(parseHash("#year_from=soon").yearFrom, null);

  // Labels with commas, ampersands and percent signs survive because each label is encoded.
  const tricky = {facets: {sector: ["a,b", "c&d=e", "100%"]}, yearFrom: null, yearTo: null, q: "a&b"};
  assert.deepEqual(parseHash(formatHash(tricky)), tricky);

  // Unknown keys and empty or duplicate labels are dropped.
  assert.deepEqual(parseHash("#bogus=1&topic=air,,air"), {facets: {topic: ["air"]}, yearFrom: null, yearTo: null, q: ""});
}

// sanitizeState keeps only labels the bundle defines.
{
  const known = {topic: new Set(["air"])};
  assert.deepEqual(sanitizeState({facets: {topic: ["air", "nope"], sector: ["x"]}}, known).facets, {topic: ["air"]});
}

// stripEntries.
{
  const entries = [
    {id: "a", name: "A", topics: ["air"], default: false},
    {id: "b", name: "B", topics: ["sea"], default: true},
    {id: "c", name: "C", topics: ["air", "sea"], default: false},
    {id: "a", name: "A again", topics: ["air"], default: false},
    {id: "d", name: "D", topics: [], default: true},
    null
  ];
  assert.deepEqual(stripEntries(entries, ["air"]).map((e) => e.id), ["a", "c"]);
  assert.deepEqual(stripEntries(entries, ["air", "sea"]).map((e) => e.id), ["a", "b", "c"]);
  // No topic matches: fall back to the defaults.
  assert.deepEqual(stripEntries(entries, ["fire"]).map((e) => e.id), ["b", "d"]);
  // No topic selected: defaults too.
  assert.deepEqual(stripEntries(entries, []).map((e) => e.id), ["b", "d"]);
  assert.deepEqual(stripEntries(entries).map((e) => e.id), ["b", "d"]);
  assert.deepEqual(stripEntries(null, ["air"]), []);
}

// Drawer helpers: sorting, paging and the works map.
{
  const works = {
    work_ids: ["W1", "W2", "W3", "W4"],
    titles: ["one", "two", "three", "four"],
    years: [2010, null, 2020, 2010]
  };
  const meta = worksMetaMap(works);
  assert.deepEqual(meta.get("W3"), {title: "three", year: 2020});
  assert.deepEqual(meta.get("W2"), {title: "two", year: null});
  assert.deepEqual(sortWorksNewestFirst(["W1", "W2", "W3", "W4"], meta), ["W3", "W1", "W4", "W2"]);

  const many = Array.from({length: 120}, (_, i) => `W${i}`);
  const page = pageWorks(many, 2);
  assert.equal(page.pages, 3);
  assert.equal(page.page, 2);
  assert.equal(page.items.length, 20);
  assert.equal(page.items[0], "W100");
  assert.equal(pageWorks(many, 9).page, 2);
  assert.equal(pageWorks(many, -1).page, 0);
  assert.equal(pageWorks([], 0).pages, 1);
  assert.throws(() => worksMetaMap({work_ids: ["W1"], titles: [], years: [2000]}));
}

// Related links are rendered only for https URLs.
{
  assert.equal(safeHttpUrl("https://example.org/x"), "https://example.org/x");
  assert.equal(safeHttpUrl("javascript:alert(1)"), null);
  assert.equal(safeHttpUrl("http://example.org"), null);
}

// Year ranges map onto the bundle's year labels; a range with no labels is impossible.
{
  const years = ["2014", "2015", "2020"];
  assert.deepEqual(selectionFor({...emptyState(), yearFrom: 2015}, years), {sel: {year: ["2015", "2020"]}, impossible: false});
  assert.deepEqual(selectionFor({...emptyState(), yearTo: 2014}, years), {sel: {year: ["2014"]}, impossible: false});
  assert.equal(selectionFor({...emptyState(), yearFrom: 2030}, years).impossible, true);
  assert.deepEqual(selectionFor(emptyState(), years), {sel: {}, impossible: false});
}

// The shared AT-4 engine over a synthetic bundle: works W0..W3 (bit i = work i).
// topic air = {0,1}, sea = {2,3}; year 2015 = {0,2}, year 2020 = {1,3}.
{
  const words = [0b0011, 0b1100, 0b0101, 0b1010];
  const header = Buffer.alloc(16);
  header.write("BMF1", 0, "latin1");
  header.writeUInt32LE(1, 4);
  header.writeUInt32LE(4, 8);
  header.writeUInt32LE(words.length, 12);
  const body = Buffer.alloc(words.length * 4);
  words.forEach((w, i) => body.writeUInt32LE(w >>> 0, i * 4));
  const buffer = Buffer.concat([header, body]);
  const facets = {
    topic: [{label: "air", id: 0, count: 2}, {label: "sea", id: 1, count: 2}],
    year: [{label: "2015", id: 2, count: 2}, {label: "2020", id: 3, count: 2}]
  };
  const works = {schema: "at4.v1", work_ids: ["W0", "W1", "W2", "W3"], titles: ["a", "b", "c", "d"], years: [2015, 2020, 2015, 2020]};
  const index = new BitmaskIndex(facets, buffer, works);

  const {sel, impossible} = selectionFor({...emptyState(), facets: {topic: ["air"]}, yearFrom: 2020, yearTo: 2020}, ["2015", "2020"]);
  assert.equal(impossible, false);
  assert.equal(index.counts(sel).total, 1);
  assert.deepEqual(index.selectedIds(sel), ["W1"]);

  const all = index.counts({topic: ["air"]});
  assert.equal(all.total, 2);
  assert.equal(all.counts["year|2015"], 1);
  assert.equal(all.counts["year|2020"], 1);
  assert.equal(all.counts["topic|sea"], 2);
}

// The shell's hash format is the one parseHash reads back.
assert.equal(formatHash({...emptyState(), facets: {plastic: ["yes"]}}), "#plastic=yes");

console.log("framework_evidence_runtime: all checks passed");
