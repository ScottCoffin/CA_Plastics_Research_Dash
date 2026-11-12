// Runtime checks for the Framework Funding view's pure helpers (AT-5b).
// The helpers are the classic Funding tab's logic, lifted into framework/src/components/funding.js.
import assert from "node:assert/strict";
import {
  buildGrantsCsv,
  fundingFromParams,
  fundingHashFor,
  fundingParamsFromHash,
  fundingToParams,
  formatGrantAmount,
  grantCsvCell,
  grantMatches,
  prepareGrantRows,
  sortGrantRows,
  svgBarChartInstitutions
} from "../framework/src/components/funding.js";

const base = {
  pi_names: [], domain_tags: [], funder_chain: [], org_state: "", sector_detail: "", start: "", end: "",
  amount_basis: "", funder: "", funder_agency: "", program: "", url: "", currency: "USD", org: "", institution_type: "university"
};
const rows = () => [
  {...base, grant_key: "a", source: "nsf_awards", title: "Beta study", org: "UC Davis", pi_names: ["Ann Lee"],
    program: "P1", funder: "NSF", funder_agency: "NSF", funder_type: "federal", sector: "university",
    fiscal_year: 2022, end: "2024-12-31", amount: 50000, url: "https://example.org/1", ca_led: true,
    plastic_related: true, domain_tags: ["air"], funder_chain: ["NSF", "UC"]},
  {...base, grant_key: "b", source: "usaspending", title: 'Alpha, "quoted"', funder: "CA", funder_agency: "",
    funder_type: "state", sector: "government", fiscal_year: null, amount: null, ca_led: false, plastic_related: null,
    institution_type: "state agency"},
  {...base, grant_key: "c", source: "ca_sea_grant", title: "=cmd", funder: "Sea Grant", funder_agency: "Sea Grant",
    funder_type: "other", sector: "university", fiscal_year: 2019, amount: 1000, currency: "EUR", plastic_related: false,
    ca_led: "maybe"}
];
const labels = {university: "University", government: "Government"};
const defaults = {
  q: "", sector: "", agency: "", funderType: "", funder: "", program: "", yearFrom: null, yearTo: null,
  amountMin: null, amountMax: null, institutionType: "", tag: "", caLed: "", plastic: true
};
const ids = (list) => list.map((row) => row.grant_key);

// Search haystack and sortable values.
{
  const prepared = prepareGrantRows(rows(), labels);
  assert.match(prepared[0]._q, /ann lee/);
  assert.equal(prepared[0]._s.sector, "university");
  assert.equal(prepared[1]._s.sector, "government");
  assert.equal(prepared[2]._s.ca, null);
  assert.equal(prepared[0]._s.ca, 1);
}

// Filters.
{
  const prepared = prepareGrantRows(rows(), labels);
  const match = (filters) => ids(prepared.filter((row) => grantMatches(row, {...defaults, ...filters})));
  assert.deepEqual(match({}), ["a", "b", "c"].filter((k) => k !== "c"), "plastic-only default drops plastic_related false");
  assert.deepEqual(match({plastic: false}), ["a", "b", "c"]);
  assert.deepEqual(match({q: "ann lee"}), ["a"]);
  assert.deepEqual(match({q: "alpha, \"quoted\""}), ["b"]);
  assert.deepEqual(match({sector: "government", plastic: false}), ["b"]);
  assert.deepEqual(match({yearFrom: 2020, plastic: false}), ["a"], "undated rows fail a year bound");
  assert.deepEqual(match({amountMin: 1, plastic: false}), ["a", "c"], "null amounts fail an amount bound");
  assert.deepEqual(match({caLed: "unknown", plastic: false}), ["c"], "non-boolean ca_led counts as unknown");
  assert.deepEqual(match({tag: "air"}), ["a"]);
  assert.deepEqual(match({funderType: "other", plastic: false}), ["c"]);
}

// Sort: empty values last; default order is newest fiscal year first, then title.
{
  const prepared = prepareGrantRows(rows(), labels);
  assert.deepEqual(ids(sortGrantRows([...prepared], {key: null, dir: "asc"})), ["a", "c", "b"]);
  assert.deepEqual(ids(sortGrantRows([...prepared], {key: "amount", dir: "asc"})), ["c", "a", "b"]);
  assert.deepEqual(ids(sortGrantRows([...prepared], {key: "amount", dir: "desc"})), ["a", "c", "b"]);
  assert.deepEqual(ids(sortGrantRows([...prepared], {key: "sector", dir: "asc"})), ["b", "a", "c"]);
}

// Amount formatting.
{
  assert.equal(formatGrantAmount({amount: null, currency: "USD"}), "Not reported");
  assert.equal(formatGrantAmount({amount: 50000, currency: "USD"}), "$50,000");
  assert.equal(formatGrantAmount({amount: 1000, currency: "EUR"}), "1,000 EUR");
}

// CSV escaping, formula guard and BOM.
{
  assert.equal(grantCsvCell('Alpha, "quoted"'), '"Alpha, ""quoted"""');
  assert.equal(grantCsvCell("=cmd"), "'=cmd");
  assert.equal(grantCsvCell(["a", "b"]), "a | b");
  assert.equal(grantCsvCell(null), "");
  const prepared = prepareGrantRows(rows(), labels);
  const csv = buildGrantsCsv(sortGrantRows([...prepared], {key: null, dir: "asc"}));
  assert.equal(csv.charCodeAt(0), 0xfeff);
  const lines = csv.slice(1).split("\r\n");
  assert.equal(lines[0].split(",")[0], "grant_key");
  assert.equal(lines[1].split(",")[0], "a");
  assert.ok(lines[1].includes("NSF > UC"), "funder chain joined with ' > '");
  assert.ok(lines[2].includes(",'=cmd,"));
  assert.ok(lines[3].includes('"Alpha, ""quoted"""'));
  assert.equal(lines[lines.length - 1], "", "CSV ends with CRLF");
}

// Hash: round trip with the new prefix-free form and the legacy "#funding?" form.
{
  const current = "#q=ann&sc=university&yf=2020&pl=0&sort=amount&dir=desc";
  const legacy = "#funding?q=ann&sc=university&yf=2020&pl=0&sort=amount&dir=desc";
  const roundTrip = (hash) => fundingHashFor(fundingToParams(fundingFromParams(fundingParamsFromHash(hash))));
  assert.equal(roundTrip(current), current);
  assert.equal(roundTrip(legacy), current);
  assert.equal(roundTrip("#funding"), "");
  assert.equal(roundTrip(""), "");
  const parsed = fundingFromParams(fundingParamsFromHash(legacy));
  assert.equal(parsed.controls.grants_search, undefined);
  assert.equal(parsed.controls["grants-search"], "ann");
  assert.equal(parsed.controls["grants-year-from"], "2020");
  assert.equal(parsed.plastic, false);
  assert.deepEqual(parsed.sort, {key: "amount", dir: "desc"});
  assert.deepEqual(fundingFromParams(fundingParamsFromHash("#sort=bogus&dir=desc")).sort, {key: null, dir: "asc"});
  assert.equal(fundingFromParams(fundingParamsFromHash("")).plastic, true);
}

// Chart helper smoke check.
{
  const prepared = prepareGrantRows(rows(), labels);
  const svg = svgBarChartInstitutions(prepared);
  assert.match(svg, /^<svg /);
  assert.match(svg, /university: 2/);
}

console.log("framework funding runtime checks passed");
