// Runtime checks for the ORCID-first sign-up (AMB-1 slice 2a). The pure helpers live in
// framework/src/components/ambassador_signup.js; the DOM flow is checked in a browser (mocked API).
import assert from "node:assert/strict";
import {
  allowedDomains,
  apiUrl,
  checkEmail,
  checkInstitutions,
  checkProfile,
  checkProposal,
  checkRegions,
  claimsBody,
  domainMatches,
  eligibleTicked,
  errorText,
  keepSelected,
  profileBody,
  regionsFor,
  routeFromSearch,
  stripQuery,
  yearsText,
} from "../framework/src/components/ambassador_signup.js";

let passed = 0;
const check = (name, fn) => {
  fn();
  passed += 1;
  console.log(`ok - ${name}`);
};

const CHECKLIST = [
  {id: "I1", name: "Univ A", source: "openalex_history", eligible: true, regions: ["norway", "belgium"], years: {from: 2015, to: null}},
  {id: "I2", name: "Lab B", source: "openalex_history", eligible: true, regions: ["california"], years: null},
  {id: "I3", name: "Firm C", source: "orcid_employment", eligible: false, regions: [], years: {from: 2020, to: 2021}},
];

check("query state router reads only the three known values", () => {
  assert.equal(routeFromSearch("?signup=orcid"), "signup");
  assert.equal(routeFromSearch("?signin=orcid"), "signin");
  assert.equal(routeFromSearch("?signin=failed"), "failed");
  assert.equal(routeFromSearch("?signup=other"), null);
  assert.equal(routeFromSearch("?foo=1"), null);
  assert.equal(routeFromSearch(""), null);
  assert.equal(routeFromSearch(undefined), null);
});

check("the query is removed and the hash kept", () => {
  assert.equal(stripQuery("https://plastiverse.live/ambassadors/?signup=orcid#regions"), "https://plastiverse.live/ambassadors/#regions");
  assert.equal(stripQuery("https://plastiverse.live/ambassadors?signin=failed"), "https://plastiverse.live/ambassadors");
});

check("one API base for every Worker call", () => {
  assert.equal(apiUrl("/signup/profile"), "https://api.plastiverse.live/signup/profile");
  assert.equal(apiUrl("/orcid/start"), "https://api.plastiverse.live/orcid/start");
});

check("error map turns codes into plain sentences and never shows raw codes", () => {
  assert.match(errorText("not_signed_in"), /Sign up with ORCID again/);
  assert.match(errorText("rate_limited"), /too many attempts/);
  assert.match(errorText("domain_not_claimed"), /not at the domain/);
  for (const code of ["network", "bot_check_failed", "mail_failed", "not_signed_in", "unknown_code", "http_500"]) {
    const text = errorText(code);
    assert.ok(text.length > 20, code);
    assert.doesNotMatch(text, /_|http_|\d{3}/, code);
  }
  assert.equal(errorText("some_new_code"), errorText("internal_unknown"));
});

check("eligible ticks only: ineligible ids are ignored", () => {
  const picked = eligibleTicked(CHECKLIST, ["I1", "I3"]);
  assert.deepEqual(picked.map((i) => i.id), ["I1"]);
});

check("regions come only from ticked eligible institutions, sorted, none preselected", () => {
  assert.deepEqual(regionsFor(CHECKLIST, []), []);
  assert.deepEqual(regionsFor(CHECKLIST, ["I3"]), []);
  assert.deepEqual(regionsFor(CHECKLIST, ["I1"]), ["belgium", "norway"]);
  assert.deepEqual(regionsFor(CHECKLIST, ["I1", "I2"]), ["belgium", "california", "norway"]);
});

check("a region choice is kept only while it is still offered", () => {
  assert.deepEqual(keepSelected(["norway", "california"], ["norway", "belgium"]), ["norway"]);
  assert.deepEqual(keepSelected([], ["norway"]), []);
});

check("institution step: needs an eligible tick or a proposal", () => {
  assert.equal(checkInstitutions({ticked: [], proposals: [], checklist: CHECKLIST}).length, 1);
  assert.equal(checkInstitutions({ticked: ["I3"], proposals: [], checklist: CHECKLIST}).length, 1);
  assert.equal(checkInstitutions({ticked: ["I1"], proposals: [], checklist: CHECKLIST}).length, 0);
  assert.equal(checkInstitutions({ticked: [], proposals: [{name: "X"}], checklist: CHECKLIST}).length, 0);
});

check("region step: required when an eligible institution is ticked, not otherwise", () => {
  assert.equal(checkRegions({regions: [], eligibleCount: 1})[0].field, "signup-regions");
  assert.equal(checkRegions({regions: [], eligibleCount: 0}).length, 0);
  assert.equal(checkRegions({regions: ["norway"], eligibleCount: 1}).length, 0);
});

check("proposal validation: name required, optional https URL", () => {
  assert.equal(checkProposal({name: "  ", url: ""})[0].field, "prop-name");
  assert.equal(checkProposal({name: "Institute", url: ""}).length, 0);
  assert.equal(checkProposal({name: "Institute", url: "https://example.org/x"}).length, 0);
  assert.equal(checkProposal({name: "Institute", url: "example.org"})[0].field, "prop-url");
  assert.equal(checkProposal({name: "a".repeat(201), url: ""})[0].field, "prop-name");
});

check("email validation and domain matching (subdomains match, look-alikes do not)", () => {
  assert.equal(checkEmail("me@uio.no", ["uio.no"]).length, 0);
  assert.equal(checkEmail("me@bio.uio.no", ["uio.no"]).length, 0);
  assert.equal(checkEmail("me@eviluio.no", ["uio.no"]).length, 1);
  assert.equal(checkEmail("me@gmail.com", ["uio.no"]).length, 1);
  assert.equal(checkEmail("not-an-email", []).length, 1);
  // With no domain list the server decides, so only the format is checked here.
  assert.equal(checkEmail("me@gmail.com", []).length, 0);
  assert.equal(domainMatches("bio.uio.no", "uio.no"), true);
  assert.equal(domainMatches("uio.no.evil.com", "uio.no"), false);
});

check("allowed domains come from the ticked institutions only", () => {
  const files = {
    norway: {institutions: [{id: "I1", domains: ["UiO.no", "uio.no"]}, {id: "I9", domains: ["other.no"]}]},
    california: {institutions: [{id: "I2", domains: ["lab.edu"]}]},
  };
  assert.deepEqual(allowedDomains(files, ["I1"]), ["uio.no"]);
  assert.deepEqual(allowedDomains(files, ["I1", "I2"]), ["lab.edu", "uio.no"]);
  assert.deepEqual(allowedDomains({norway: null}, ["I1"]), []);
});

check("claims body sends the full selection and every proposal as kind institution", () => {
  const body = claimsBody({
    ticked: ["I1"],
    regions: ["norway"],
    proposals: [{name: " New Institute ", url: " https://new.example "}, {name: "Other", url: ""}],
  });
  assert.deepEqual(body, {
    institutions: ["I1"],
    regions: ["norway"],
    proposals: [
      {kind: "institution", payload: {name: "New Institute", url: "https://new.example"}},
      {kind: "institution", payload: {name: "Other"}},
    ],
  });
});

check("profile body: trimmed name, credit boolean, terms v1", () => {
  assert.deepEqual(profileBody({name: " Ada ", creditPublic: true}), {display_name: "Ada", credit_public: true, accept_terms_version: "v1"});
  assert.equal(profileBody({name: "Ada", creditPublic: false}).credit_public, false);
  assert.equal(checkProfile({name: "", accepted: true})[0].field, "profile-name");
  assert.equal(checkProfile({name: "Ada", accepted: false})[0].field, "profile-terms");
  assert.equal(checkProfile({name: "Ada", accepted: true}).length, 0);
});

check("years text reads from, to and open-ended ranges", () => {
  assert.equal(yearsText({from: 2015, to: null}), "since 2015");
  assert.equal(yearsText({from: 2020, to: 2021}), "2020 to 2021");
  assert.equal(yearsText({from: 2019, to: 2019}), "2019");
  assert.equal(yearsText(null), "");
});

console.log(`${passed} ambassador sign-up runtime checks passed`);
