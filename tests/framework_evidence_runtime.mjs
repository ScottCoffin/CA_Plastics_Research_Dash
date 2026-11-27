// Runtime checks for the Framework Evidence map shell helpers (EM-5b).
// The pure helpers live in framework/src/components/evidence_model.js; the selection check runs
// the shared AT-4 engine (site/assets/facets.js) over a tiny synthetic bundle.
import assert from "node:assert/strict";
import {createRequire} from "node:module";
import {fileURLToPath} from "node:url";
import {
  JOURNAL_FACET,
  andBits,
  emptyState,
  formatHash,
  journalBits,
  journalOptions,
  matchesJournalQuery,
  parseHash,
  safeHttpUrl,
  sanitizeState,
  selectionFor,
  stripEntries,
  tallyJournals
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

// The plastic filter is not a hash key: a hash that carries it is ignored and never written back.
{
  assert.deepEqual(parseHash("#plastic=no"), emptyState());
  assert.deepEqual(parseHash("#plastic=yes&topic=air"), {facets: {topic: ["air"]}, yearFrom: null, yearTo: null, q: ""});
  assert.equal(formatHash({...emptyState(), facets: {plastic: ["yes"]}}), "");
  assert.equal(formatHash({...emptyState(), facets: {plastic: ["no"], topic: ["air"]}}), "#topic=air");
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

// Related links are rendered only for https URLs.
{
  assert.equal(safeHttpUrl("https://example.org/x"), "https://example.org/x");
  assert.equal(safeHttpUrl("javascript:alert(1)"), null);
  assert.equal(safeHttpUrl("http://example.org"), null);
}

// Year ranges map onto the bundle's year labels; a range with no labels is impossible.
// Every selection carries the plastic-related constraint.
{
  const years = ["2014", "2015", "2020"];
  assert.deepEqual(selectionFor({...emptyState(), yearFrom: 2015}, years), {sel: {plastic: ["yes"], year: ["2015", "2020"]}, impossible: false});
  assert.deepEqual(selectionFor({...emptyState(), yearTo: 2014}, years), {sel: {plastic: ["yes"], year: ["2014"]}, impossible: false});
  assert.equal(selectionFor({...emptyState(), yearFrom: 2030}, years).impossible, true);
  assert.deepEqual(selectionFor(emptyState(), years), {sel: {plastic: ["yes"]}, impossible: false});
  // GP-8: a region without relevance review keeps no plastic facet.
  assert.deepEqual(selectionFor(emptyState(), years, {plastic: null}), {sel: {}, impossible: false});
}

// A plastic facet in the state never widens or changes the selection.
{
  const state = {...emptyState(), facets: {plastic: ["no"], topic: ["air"]}};
  assert.deepEqual(selectionFor(state, []), {sel: {plastic: ["yes"], topic: ["air"]}, impossible: false});
}

// The shared AT-4 engine over a synthetic bundle: works W0..W3 (bit i = work i).
// topic air = {0,1}, sea = {2,3}; year 2015 = {0,2}, year 2020 = {1,3}; plastic yes = {0,1,2}.
{
  const words = [0b0011, 0b1100, 0b0101, 0b1010, 0b0111];
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
    year: [{label: "2015", id: 2, count: 2}, {label: "2020", id: 3, count: 2}],
    plastic: [{label: "yes", id: 4, count: 3}]
  };
  const works = {schema: "at4.v1", work_ids: ["W0", "W1", "W2", "W3"], titles: ["a", "b", "c", "d"], years: [2015, 2020, 2015, 2020]};
  const index = new BitmaskIndex(facets, buffer, works);

  // Year range plus topic, with the plastic constraint applied through selectionFor.
  const {sel, impossible} = selectionFor({...emptyState(), facets: {topic: ["air"]}, yearFrom: 2020, yearTo: 2020}, ["2015", "2020"]);
  assert.equal(impossible, false);
  assert.equal(index.counts(sel).total, 1);
  assert.deepEqual(index.selectedIds(sel), ["W1"]);

  // Plastic-only: W3 is not plastic-related, so it is excluded from every count.
  const plasticOnly = selectionFor(emptyState(), ["2015", "2020"]);
  assert.equal(index.counts(plasticOnly.sel).total, 3);
  assert.deepEqual(index.selectedIds(plasticOnly.sel), ["W0", "W1", "W2"]);
  const sea = selectionFor({...emptyState(), facets: {topic: ["sea"]}}, ["2015", "2020"]);
  assert.deepEqual(index.selectedIds(sea.sel), ["W2"]);
  assert.equal(index.counts(sea.sel).total, 1);

  // The engine's own counts (no plastic facet) still see all four works.
  const all = index.counts({topic: ["air"]});
  assert.equal(all.total, 2);
  assert.equal(all.counts["year|2015"], 1);
  assert.equal(all.counts["year|2020"], 1);
  assert.equal(all.counts["topic|sea"], 2);
}

// VD-34 journal filter: the hash keeps journal names (commas and ampersands survive), and the
// journal labels are sanitized like the other facets.
{
  const state = {...emptyState(), facets: {journal: ["Water, Air, & Soil Pollution", "Chemosphere"], topic: ["air"]}};
  const hash = formatHash(state);
  assert.ok(hash.startsWith("#topic=air&journal="), hash);
  assert.ok(hash.includes("Water%2C%20Air%2C%20%26%20Soil%20Pollution,Chemosphere"), hash);
  assert.deepEqual(parseHash(hash), state);
  const known = {journal: new Set(["Chemosphere"]), topic: new Set(["air"])};
  assert.deepEqual(sanitizeState(state, known).facets, {journal: ["Chemosphere"], topic: ["air"]});
  // A journal the page does not list (or no journal list at all) is dropped, like any unknown label.
  assert.deepEqual(sanitizeState(state, {topic: new Set(["air"])}).facets, {topic: ["air"]});
}

// journalOptions: distinct trimmed names, blank names skipped, most works first, then by name.
{
  const rows = [
    {journal: "Chemosphere"},
    {journal: " Water Research "},
    {journal: "Chemosphere"},
    {journal: ""},
    {journal: "Aquatic Toxicology"},
    {journal: "Water Research"},
    {journal: null},
    null
  ];
  assert.deepEqual(journalOptions(rows), [
    {label: "Chemosphere", count: 2},
    {label: "Water Research", count: 2},
    {label: "Aquatic Toxicology", count: 1}
  ]);
  assert.deepEqual(journalOptions(null), []);
}

// The journal search is case-insensitive and every term must match.
{
  assert.equal(matchesJournalQuery("Water Research", "water"), true);
  assert.equal(matchesJournalQuery("Water Research", "WATER  res"), true);
  assert.equal(matchesJournalQuery("Water Research", "water chemo"), false);
  assert.equal(matchesJournalQuery("Water Research", ""), true);
  assert.equal(matchesJournalQuery("Water Research", "   "), true);
}

// The journal bit-set uses the AT-4 layout; journal counts ignore the journal filter itself.
{
  const words = [0b1111];
  const header = Buffer.alloc(16);
  header.write("BMF1", 0, "latin1");
  header.writeUInt32LE(1, 4);
  header.writeUInt32LE(4, 8);
  header.writeUInt32LE(1, 12);
  const body = Buffer.alloc(4);
  body.writeUInt32LE(words[0], 0);
  const index = new BitmaskIndex(
    {topic: [{label: "air", id: 0, count: 4}]},
    Buffer.concat([header, body]),
    {schema: "at4.v1", work_ids: ["W0", "W1", "W2", "W3"], titles: ["a", "b", "c", "d"], years: [2015, 2015, 2020, 2020]}
  );
  const journalOf = new Map([["W0", "Chemosphere"], ["W1", "Water Research"], ["W2", "Chemosphere"], ["W3", ""]]);
  const chemo = journalBits(index.workIds, journalOf, ["Chemosphere"], index.W);
  assert.deepEqual(index.selectedIds({}, chemo), ["W0", "W2"]);
  assert.equal(index.counts({}, chemo).total, 2);
  assert.equal(index.counts({}, chemo).counts["topic|air"], 2);
  // Two journals are an OR; with a text bit-set the two are ANDed.
  const both = journalBits(index.workIds, journalOf, ["Chemosphere", "Water Research"], index.W);
  assert.deepEqual(index.selectedIds({}, both), ["W0", "W1", "W2"]);
  const titleBits = new Uint32Array([0b0101]);
  assert.deepEqual(index.selectedIds({}, andBits(titleBits, both)), ["W0", "W2"]);
  assert.equal(andBits(undefined, undefined), undefined);
  assert.equal(andBits(titleBits, undefined), titleBits);
  assert.deepEqual(Array.from(andBits(titleBits, chemo)), [0b0101]);
  // Plastic-only selections never carry the journal key into the engine's selection.
  const selection = selectionFor({...emptyState(), facets: {journal: ["Chemosphere"]}}, []);
  assert.deepEqual(selection.sel, {plastic: ["yes"]});
  assert.equal(JOURNAL_FACET, "journal");
  // The tally counts each work once under its journal; works without a journal are not counted.
  const tally = tallyJournals(index.selectedIds({}, undefined), journalOf);
  assert.equal(tally.get("Chemosphere"), 2);
  assert.equal(tally.get("Water Research"), 1);
  assert.equal(tally.has(""), false);
}

console.log("framework_evidence_runtime: all checks passed");
