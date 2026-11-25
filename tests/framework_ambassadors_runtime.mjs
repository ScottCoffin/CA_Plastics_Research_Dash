// Runtime check for the ambassadors page helpers (framework/src/components/ambassadors.js, world_map.js), run by
// tests/test_ambassadors_page.py. Pure functions only, on the real data files: no network, no DOM.
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {dirname, join} from "node:path";
import {fileURLToPath} from "node:url";
import {
  EMAIL_ADDRESS,
  checkEligibility,
  countryRegion,
  domainWithin,
  emailDomain,
  institutionHasDomain,
  institutionPool,
  isFreeMail,
  placeView,
  regionForPlace,
  suggestInstitutions,
} from "../framework/src/components/ambassadors.js";
import {
  FRAME_WIDTH,
  ISLAND_ISO,
  ISLAND_MIN_EXTENT_KM,
  MIN_EXTENT_KM,
  boxOf,
  foldName,
  frameExtent,
  frameXY,
  minKmFor,
  minimumBox,
  placeExtent,
  placeRows,
  searchPlaces,
} from "../framework/src/components/world_map.js";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..");
const read = (rel) => JSON.parse(readFileSync(join(root, rel), "utf-8"));
const close = (a, b, eps = 1e-6) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);
const km = ([w, s, e, n]) => {
  const midLat = (s + n) / 2;
  return {ew: (e - w) * 111.32 * Math.cos((midLat * Math.PI) / 180), ns: (n - s) * 111.32};
};

// ---- data: the real region index and institution lists -----------------------------------------
const index = read("site/data/global/ambassador_regions.json");
const regions = index.regions.map((r) => ({
  ...r,
  institutions: read(`site/data/${r.slug}/ambassador_institutions.json`).institutions,
}));
const bySlug = Object.fromEntries(regions.map((r) => [r.slug, r]));
assert.equal(index.schema, "amb-regions-v1");
assert.deepEqual(regions.map((r) => r.slug).sort(), ["belgium", "california", "norway"]);
assert.ok(regions.every((r) => r.status === "open_to_ambassadors"), "no proposed or fake regions");

// ---- email domains and free mail -----------------------------------------------------------
assert.equal(emailDomain("someone@niva.no"), "niva.no");
assert.equal(emailDomain("  Someone@NIVA.NO "), "niva.no");
assert.equal(emailDomain("someone@"), null);
assert.equal(emailDomain("no at sign"), null);
assert.equal(emailDomain("a@b"), null, "a domain needs a dot and a suffix");
assert.ok(domainWithin("mail.niva.no", "niva.no"), "subdomains match");
assert.ok(domainWithin("niva.no", "niva.no"));
assert.ok(!domainWithin("evilniva.no", "niva.no"), "a suffix that is not a label does not match");
assert.ok(!domainWithin("niva.no.example.com", "niva.no"));
assert.ok(isFreeMail("gmail.com"));
assert.ok(isFreeMail("mail.gmail.com"), "free mail subdomains are refused too");
assert.ok(isFreeMail("proton.me"));
assert.ok(!isFreeMail("notgmail.com"));
assert.ok(!isFreeMail("niva.no"));
assert.ok(institutionHasDomain({domains: ["niva.no"]}, "sub.niva.no"));
assert.ok(!institutionHasDomain({domains: ["niva.no"]}, "niva.com"));
assert.equal(EMAIL_ADDRESS, "theplastiverse@gmail.com");

// ---- eligibility -----------------------------------------------------------------------------
const niva = checkEligibility("someone@niva.no", regions, null);
assert.equal(niva.state, "eligible");
assert.equal(niva.region.slug, "norway");
assert.equal(niva.institution.name, "Norwegian Institute for Water Research");

const nivaInNorway = checkEligibility("someone@niva.no", regions, "norway");
assert.equal(nivaInNorway.state, "eligible", "the place's region is Norway");

const nivaInCalifornia = checkEligibility("someone@niva.no", regions, "california");
assert.equal(nivaInCalifornia.state, "other_region", "NIVA is listed for Norway, not California");
assert.equal(nivaInCalifornia.region.slug, "norway");

assert.equal(checkEligibility("someone@gmail.com", regions, "norway").state, "free_mail", "free mail is refused");
assert.equal(checkEligibility("someone@", regions).state, "invalid");
assert.equal(checkEligibility("   ", regions).state, "empty");
assert.equal(checkEligibility("someone@unknown-example.org", regions, "norway").state, "not_eligible");

const byName = checkEligibility("Norwegian Institute for Water Research", regions, "norway");
assert.equal(byName.state, "eligible", "an exact name is eligible");
assert.equal(byName.institution.name, "Norwegian Institute for Water Research");
assert.equal(checkEligibility("Norwegian Institute for Water Research", regions, "belgium").state, "other_region");
assert.equal(checkEligibility("Ghent University", regions, "belgium").state, "eligible");
assert.equal(checkEligibility("zzz nothing like this", regions, "norway").state, "not_eligible");
assert.equal(checkEligibility("University of California", regions, "california").state, "choose",
  "a shared name with several matches asks the user to choose");

// Acronyms and aliases (owner requirement): NIVA, NTNU, VLIZ, UC Davis and the full name all match.
for (const [text, region, slug] of [
  ["NIVA", null, "norway"],
  ["niva", "norway", "norway"],
  ["NTNU", null, "norway"],
  ["VLIZ", null, "belgium"],
  ["UC Davis", "california", "california"],
  ["Norwegian Institute for Water Research", null, "norway"],
]) {
  const hit = checkEligibility(text, regions, region);
  assert.equal(hit.state, "eligible", text);
  assert.equal(hit.region.slug, slug, text);
}
assert.equal(checkEligibility("VLIZ", regions, "norway").state, "other_region", "VLIZ is listed for Belgium");
assert.equal(checkEligibility("NIV", regions, null).state === "eligible", false, "an acronym is whole-word only");
assert.equal(checkEligibility("UC Davis", regions, null).institution.name, "University of California, Davis");

// ---- type-ahead ------------------------------------------------------------------------------
const pool = institutionPool(regions);
const byDomain = suggestInstitutions("niva.no", pool, 3);
assert.equal(byDomain[0].institution.name, "Norwegian Institute for Water Research", "a domain finds its institution");
assert.deepEqual(suggestInstitutions("n", pool), [], "one letter is not enough");
assert.deepEqual(suggestInstitutions("someone@niva.no", pool), [], "an email gets no list");
const nordic = suggestInstitutions("norwegian", institutionPool(regions, "norway"), 20);
assert.ok(nordic.length > 0 && nordic.every((e) => e.region.slug === "norway"), "the list stays in the chosen region");
assert.ok(nordic.every((e, i, a) => i === 0 || a[i - 1].score <= e.score), "best matches first");

// ---- places and regions ----------------------------------------------------------------------
const placesPayload = read("site/data/global/places.json");
const rows = placeRows(placesPayload);
assert.ok(rows.length > 30000, "the whole place index is loaded");
const first = (q) => searchPlaces(rows, q, 3);
assert.equal(first("Palau")[0].kind, "country");
assert.equal(first("Palau")[0].iso, "PW");
assert.equal(first("Bergen")[0].name, "Bergen");
assert.equal(first("Bergen")[0].iso, "NO", "the larger Bergen (Norway) ranks first");
assert.equal(first("Oakland")[0].name, "Oakland");
assert.equal(foldName("Ålesund"), "alesund");

const californiaAdmin = rows.find((r) => r.kind === "admin1" && r.name === "California" && r.iso === "US");
const oakland = rows.find((r) => r.kind === "city" && r.name === "Oakland" && r.iso === "US");
const bergen = rows.find((r) => r.kind === "city" && r.name === "Bergen" && r.iso === "NO");
const palau = rows.find((r) => r.kind === "country" && r.iso === "PW");
const texas = rows.find((r) => r.kind === "admin1" && r.name === "Texas" && r.iso === "US");
const us = rows.find((r) => r.kind === "country" && r.iso === "US");
assert.equal(regionForPlace(californiaAdmin, regions)?.slug, "california");
assert.equal(regionForPlace(oakland, regions)?.slug, "california", "a city takes its state's region");
assert.equal(regionForPlace(bergen, regions)?.slug, "norway");
assert.equal(regionForPlace(texas, regions), null, "another state is not California");
assert.equal(regionForPlace(us, regions), null, "the whole country is not the state region");
assert.equal(regionForPlace(palau, regions), null, "Palau is not open");
assert.equal(regionForPlace(null, regions), null);
assert.equal(countryRegion("NO", regions)?.slug, "norway");
assert.equal(countryRegion("US", regions), null, "the US is open only through California");
assert.equal(bySlug.california.subdivision_names[0], "California");

// ---- island states: the 120 km minimum box, other places 300 km -------------------------------
assert.equal(MIN_EXTENT_KM, 300);
assert.equal(ISLAND_MIN_EXTENT_KM, 120);
assert.equal(minKmFor("PW"), 120);
assert.equal(minKmFor("WS"), 120, "Samoa is an island state");
assert.equal(minKmFor("NO"), 300);
assert.ok(ISLAND_ISO.has("TV") && ISLAND_ISO.has("FJ"));
const pointBox = minimumBox([134.5, 7.5, 134.5, 7.5], minKmFor("PW"));
const pk = km(pointBox);
close(pk.ns, 120, 0.5);
close(pk.ew, 120, 0.5);
const wideBox = minimumBox([0, 0, 10, 0.5], minKmFor("NO"));
close(km(wideBox).ew, 1113.2, 1, "a box wider than the minimum keeps its own width");
const nearly = minimumBox([5, 60, 5.01, 60.01], minKmFor("NO"));
close(km(nearly).ns, 300, 0.5);
assert.deepEqual(boxOf([3, 4]), [3, 4, 3, 4]);
assert.equal(frameExtent([0, 0, 0, 0]).length, 4);
// Palau's place box (its country box) projects inside the frame, and the 120 km rule applies to its extent.
const [px0, py0, px1, py1] = placeExtent(palau.geom, "PW");
assert.ok(px0 >= 0 && px1 <= FRAME_WIDTH && py0 >= 0, "Palau's extent is inside the Natural Earth frame");
assert.ok(px1 - px0 > 0 && py1 - py0 > 0);
close(frameXY(0, 0)[0], FRAME_WIDTH / 2, 1e-6, "the equator and prime meridian sit in the frame centre");

// ---- the view of a place --------------------------------------------------------------------
const FULL = [0, 7.3, 1000, 434.7];
const aspect = FULL[2] / FULL[3];
const view = placeView(palau.geom, "PW", aspect, FULL);
assert.ok(view[2] >= 120 && view[2] <= FULL[2], "a place view is at least 120 units wide");
close(view[2] / view[3], aspect, 1e-6);
const inside = (v) => v[0] >= FULL[0] - 1e-6 && v[1] >= FULL[1] - 1e-6 && v[0] + v[2] <= FULL[0] + FULL[2] + 1e-6 && v[1] + v[3] <= FULL[1] + FULL[3] + 1e-6;
assert.ok(inside(view), "the view stays inside the map");
const fraction = (placeExtent(palau.geom, "PW")[2] - placeExtent(palau.geom, "PW")[0]) / view[2];
assert.ok(fraction > 0.05, `Palau fills a useful share of the view (${fraction.toFixed(3)})`);
const bergenView = placeView(bergen.geom, "NO", aspect, FULL);
assert.ok(inside(bergenView));

console.log("ambassadors helpers: ok");
