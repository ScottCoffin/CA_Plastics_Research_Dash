// Runtime check for the community groups page helpers (framework/src/components/groups.js), run by
// tests/test_groups_page.py. Pure functions only, no DOM: inline fixtures plus the real roster when it is built.
import assert from "node:assert/strict";
import {existsSync, readFileSync} from "node:fs";
import {dirname, join} from "node:path";
import {fileURLToPath} from "node:url";
import {
  CONTACT_EMAIL,
  DEFAULT_STATE,
  PAGE_SIZE,
  STANDING_NOTE,
  cardHtml,
  countryName,
  coverageHtml,
  coverageRows,
  filterGroups,
  formatHash,
  isTagged,
  parseHash,
  pageOf,
  provenanceLine,
  rowHtml,
  safeUrl,
  sortGroups,
  statusKey,
  statusLabel,
} from "../framework/src/components/groups.js";

const here = dirname(fileURLToPath(import.meta.url));

const group = (overrides) => ({
  group_id: "cg_test_0001",
  name: "Alpha Clean Coast",
  country: "PH",
  places: [],
  region: "South-eastern Asia",
  status: "unlabelled",
  url: "https://alpha.example.org",
  bffp_listed: true,
  bffp_listed_asof: "2026-11-26",
  primary_activities: [],
  website_languages: [],
  evidence: [],
  stated_affiliations: [],
  entity_type: null,
  sector: null,
  plastics_centrality: null,
  ...overrides,
});

const fixtures = [
  group({group_id: "cg_a", name: "Alpha Clean Coast", status: "unlabelled"}),
  group({group_id: "cg_b", name: "Bravo Waters", country: "US", region: "Northern America", status: "ambassador_tagged", plastics_centrality: "primary", primary_activities: ["Beach cleanup"]}),
  group({group_id: "cg_c", name: "Émile Réseau", country: "FR", region: "Western Europe", status: "reviewed"}),
  group({group_id: "cg_d", name: "Delta Group", country: null, region: "region_unknown", status: "group_confirmed", url: null}),
  group({group_id: "cg_e", name: "Echo Lab", country: "PH", region: "South-eastern Asia", status: "assigned"}),
  group({group_id: "cg_f", name: "Foxtrot Trust", country: "US", region: "Northern America", status: "cannot_determine"}),
];

// Status keys and labels: the four public badge labels plus one for cannot_determine.
assert.equal(statusKey("unlabelled"), "not_tagged");
assert.equal(statusKey("assigned"), "not_tagged");
assert.equal(statusLabel("unlabelled"), "Not yet tagged");
assert.equal(statusLabel("ambassador_tagged"), "Volunteer-tagged");
assert.equal(statusLabel("reviewed"), "Reviewed");
assert.equal(statusLabel("group_confirmed"), "Confirmed by group");
assert.equal(statusLabel("cannot_determine"), "Could not be tagged from public pages");
assert.equal(isTagged(fixtures[0]), false);
assert.equal(isTagged(fixtures[1]), true);
assert.equal(isTagged(fixtures[4]), false, "assigned is not yet tagged");

// Country names come from Intl; unknown or missing codes give an empty string.
assert.equal(countryName("PH"), "Philippines");
assert.equal(countryName(null), "");
assert.equal(countryName("ph"), "Philippines");

// Filters: accent-insensitive name search, region, country and status (status filter uses the badge key).
assert.deepEqual(filterGroups(fixtures, {q: "reseau"}).map((g) => g.group_id), ["cg_c"]);
assert.deepEqual(filterGroups(fixtures, {q: "  BRAVO "}).map((g) => g.group_id), ["cg_b"]);
assert.equal(filterGroups(fixtures, {}).length, fixtures.length);
assert.deepEqual(filterGroups(fixtures, {region: "region_unknown"}).map((g) => g.group_id), ["cg_d"]);
assert.deepEqual(filterGroups(fixtures, {country: "US"}).map((g) => g.group_id), ["cg_b", "cg_f"]);
assert.deepEqual(filterGroups(fixtures, {status: "not_tagged"}).map((g) => g.group_id), ["cg_a", "cg_e"]);
assert.deepEqual(filterGroups(fixtures, {status: "confirmed", country: "PH"}), []);

// Sorting: name or country only; blanks last in both directions; no score key exists.
assert.deepEqual(sortGroups(fixtures, "name", "asc").map((g) => g.name), [
  "Alpha Clean Coast", "Bravo Waters", "Delta Group", "Echo Lab", "Émile Réseau", "Foxtrot Trust",
].sort((a, b) => a.localeCompare(b, "en")));
assert.deepEqual(sortGroups(fixtures, "name", "desc").map((g) => g.name)[0], "Foxtrot Trust");
const byCountry = sortGroups(fixtures, "country", "asc").map((g) => g.group_id);
assert.equal(byCountry[byCountry.length - 1], "cg_d", "blank country sorts last");
const byCountryDesc = sortGroups(fixtures, "country", "desc").map((g) => g.group_id);
assert.equal(byCountryDesc[byCountryDesc.length - 1], "cg_d", "blank country stays last when descending");
assert.equal(sortGroups(fixtures, "score", "asc")[0].name, "Alpha Clean Coast", "unknown keys fall back to name");

// Paging: 50 per page, clamped to the last page.
assert.equal(PAGE_SIZE, 50);
assert.deepEqual(pageOf(2708, 1), {page: 1, pages: 55, start: 0, end: 50, total: 2708});
assert.deepEqual(pageOf(2708, 55), {page: 55, pages: 55, start: 2700, end: 2708, total: 2708});
assert.equal(pageOf(2708, 999).page, 55, "page beyond the end clamps");
assert.equal(pageOf(2708, -4).page, 1, "page below 1 clamps");
assert.deepEqual(pageOf(0, 1), {page: 1, pages: 1, start: 0, end: 0, total: 0});

// URL hash: defaults are omitted, values round-trip, unknown values fall back to defaults.
assert.equal(formatHash(DEFAULT_STATE), "");
const state = {q: "bravo waters", region: "Northern America", country: "US", status: "volunteer", sort: "country", dir: "desc", page: 3, group: "cg_b"};
const hash = formatHash(state);
assert.match(hash, /^#/);
assert.deepEqual(parseHash(hash), {...DEFAULT_STATE, ...state});
assert.deepEqual(parseHash("#status=bogus&sort=score&dir=sideways&page=0"), DEFAULT_STATE);
assert.deepEqual(parseHash(""), DEFAULT_STATE);
assert.equal(formatHash({sort: "name", dir: "asc", page: 1}), "");

// Coverage: the first row is the whole roster, then one row per region, largest first.
const coverage = {
  roster_total: 4,
  tagged_total: 1,
  denominator_note: "Based on 1 of 4 roster organisations tagged (25.0%). Tagged groups are not a random sample.",
  by_region: {
    "Northern America": {roster: 3, tagged: 1, status: {}},
    region_unknown: {roster: 1, tagged: 0, status: {}},
  },
};
const rows = coverageRows(coverage);
assert.equal(rows[0].label, "All regions");
assert.equal(rows[0].roster, 4);
assert.equal(rows[0].percent, 25);
assert.equal(rows[1].label, "Northern America");
assert.equal(rows[1].percent, 33.3);
assert.equal(rows[2].label, "Region not known");
assert.equal(rows[2].percent, 0);
const empty = coverageRows({by_region: {"Caribbean": {roster: 0, tagged: 0}}});
assert.equal(empty[1].percent, null, "a region with no roster has no percentage");
const coverageMarkup = coverageHtml(coverage);
assert.ok(coverageMarkup.includes("Based on 1 of 4 roster organisations tagged"), "denominator note is shown");
assert.ok(coverageMarkup.includes("1 of 3 tagged (33.3%)"), "bar values are shown as text");

// Provenance and links.
assert.equal(provenanceLine(fixtures[0]), "Listed as a BFFP member as of 2026-11-26");
assert.equal(provenanceLine(group({bffp_listed: false})), "");
assert.equal(safeUrl("javascript:alert(1)"), null);
assert.equal(safeUrl("https://alpha.example.org/x"), "https://alpha.example.org/x");
assert.equal(safeUrl(null), null);

// Table rows: untagged rows link to the ambassadors page (no trailing slash); tagged rows do not.
const untaggedRow = rowHtml(fixtures[0]);
assert.ok(untaggedRow.includes('href="./ambassadors"'), "help link points at ./ambassadors");
assert.ok(!untaggedRow.includes("./ambassadors/"), "no trailing slash on the help link");
assert.ok(untaggedRow.includes("Help tag this group"));
assert.ok(!rowHtml(fixtures[1]).includes("Help tag this group"), "tagged rows carry no help link");
assert.ok(untaggedRow.includes('rel="noopener nofollow"'), "website links are noopener nofollow");
assert.ok(rowHtml(fixtures[3]).includes("No website listed"), "missing website is stated, not linked");
const escapedRow = rowHtml(group({name: "<img src=x onerror=alert(1)>"}));
assert.ok(!escapedRow.includes("<img"), "names are escaped");
assert.ok(escapedRow.includes("&lt;img"));

// Group card: null tag fields are omitted; provenance and standing note are present; correction uses the public address.
const card = cardHtml(fixtures[1]);
assert.ok(card.includes("Plastics focus"), "fields that exist are shown");
assert.ok(!card.includes("Entity type"), "null entity_type is omitted");
assert.ok(!card.includes("Sector"), "null sector is omitted");
assert.ok(!card.includes("Stated affiliations"), "empty affiliations are omitted");
assert.ok(!card.includes("Evidence<"), "empty evidence is omitted");
assert.ok(!card.includes("Places"), "empty places are omitted");
assert.ok(card.includes("Beach cleanup"), "activities are listed");
assert.ok(card.includes("Listed as a BFFP member as of 2026-11-26"));
assert.ok(card.includes(STANDING_NOTE), "standing note is verbatim");
assert.ok(card.includes("Suggest a correction"));
assert.ok(card.includes(CONTACT_EMAIL));
// Correction link: the mailto subject carries the encoded group name and id; the methods link targets the section.
const subject = encodeURIComponent(`Group correction: ${fixtures[1].name} (${fixtures[1].group_id})`);
assert.ok(card.includes(`mailto:${CONTACT_EMAIL}?subject=${subject}`), "mailto subject names the group");
assert.ok(card.includes(`href="#gv-methods" data-close`), "methods link closes the card and points at the section");
const hostile = cardHtml(group({group_id: "cg_x<&>", name: "<script>alert(1)</script>"}));
assert.ok(!hostile.includes("<script>"), "group name is escaped in the card");
assert.ok(hostile.includes("&lt;script&gt;"), "escaped name is shown as text");
assert.ok(hostile.includes(`mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent("Group correction: <script>alert(1)</script> (cg_x<&>)")}`), "subject is percent-encoded and the href is escaped");
const withEvidence = cardHtml(group({
  evidence: [{quote: "We clean the coast monthly.", url: "https://alpha.example.org/about", accessed_at: "2026-11-20"}],
  stated_affiliations: [{relation: "member_of", target_name: "Beta Network", evidence: {quote: "Member of Beta Network.", url: "https://alpha.example.org/", accessed_at: "2026-11-20"}}],
  plastics_centrality: "substantial",
}));
assert.ok(withEvidence.includes("We clean the coast monthly."));
assert.ok(withEvidence.includes("accessed 2026-11-20"));
assert.ok(withEvidence.includes("Member of"), "relation is shown in plain words");
assert.ok(withEvidence.includes("Beta Network"));
assert.ok(withEvidence.includes("Substantial plastics focus"));
const labelled = cardHtml(group({sector: "joint_power_authority", entity_type: "chapter_branch", primary_activities: ["cleanup_removal"]}));
assert.ok(labelled.includes("Joint powers authority") && labelled.includes("Chapter or branch"), "sector and entity type use plain labels");
assert.ok(labelled.includes("Clean-ups and litter removal"), "activities use plain labels");
assert.ok(!labelled.includes("cleanup_removal") && !labelled.includes("joint_power_authority"), "no raw keys in the card");
assert.ok(!withEvidence.includes("cg-v2") && !withEvidence.includes("org_status"), "no internal field names in the card");

// The real roster, when it has been built: every group is listed once and the filters partition it.
const rosterPath = join(here, "..", "site", "data", "global", "groups", "groups.json");
if (existsSync(rosterPath)) {
  const roster = JSON.parse(readFileSync(rosterPath, "utf8")).groups;
  assert.equal(new Set(roster.map((g) => g.group_id)).size, roster.length, "group ids are unique");
  const statusCounts = ["not_tagged", "volunteer", "reviewed", "confirmed", "cannot"].map((s) => filterGroups(roster, {status: s}).length);
  assert.equal(statusCounts.reduce((a, b) => a + b, 0), roster.length, "status filters partition the roster");
  assert.equal(sortGroups(roster, "country").length, roster.length);
  assert.equal(filterGroups(roster, {status: "volunteer"}).every(isTagged), true);
}

console.log("framework_groups_runtime: all assertions passed");
