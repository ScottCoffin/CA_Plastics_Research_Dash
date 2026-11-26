// Runtime checks for the ORCID-first sign-up (AMB-1 slice 2a). The pure helpers live in
// framework/src/components/ambassador_signup.js; the DOM flow is checked in a browser (mocked API).
import assert from "node:assert/strict";
import {
  pageMode,
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
  REGIONS_EVENT,
  signupRegionState,
  checkUnlisted,
  displayName,
  domainHasTrustedSuffix,
  routeFromSearch,
  stripQuery,
  suffixHintText,
  trustedSuffixesFor,
  unlistedPayload,
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

const CA_SUFFIXES = ["ca.gov", "ca.us", "edu", "gov"];

check("pending_review is its own route and is cleaned from the URL like the others", () => {
  assert.equal(routeFromSearch("?signup=pending_review"), "pending_review");
  assert.equal(routeFromSearch("?signup=orcid"), "signup");
  assert.equal(stripQuery("https://plastiverse.live/ambassadors?signup=pending_review#x"), "https://plastiverse.live/ambassadors#x");
});

check("trusted suffix matching: exact suffix, subdomains and the suffix itself; look-alikes do not match", () => {
  assert.equal(domainHasTrustedSuffix("oehha.ca.gov", CA_SUFFIXES), true);
  assert.equal(domainHasTrustedSuffix("ca.gov", CA_SUFFIXES), true);
  assert.equal(domainHasTrustedSuffix("mail.Berkeley.EDU", CA_SUFFIXES), true);
  assert.equal(domainHasTrustedSuffix("evilca.gov", ["ca.gov"]), false, "look-alike must not match ca.gov");
  assert.equal(domainHasTrustedSuffix("evil-ca.gov", ["ca.gov"]), false);
  assert.equal(domainHasTrustedSuffix("evilca.gov", CA_SUFFIXES), true, "it is a .gov domain, so the gov suffix applies");
  assert.equal(domainHasTrustedSuffix("ca.gov.evil.com", CA_SUFFIXES), false);
  assert.equal(domainHasTrustedSuffix("notgov", CA_SUFFIXES), false);
  assert.equal(domainHasTrustedSuffix("edu", CA_SUFFIXES), false, "a bare suffix is not a domain");
  assert.equal(domainHasTrustedSuffix("gmail.com", CA_SUFFIXES), false);
  assert.equal(domainHasTrustedSuffix("oehha.ca.gov", []), false, "no suffixes, no match");
  assert.equal(domainHasTrustedSuffix("", CA_SUFFIXES), false);
});

check("trusted suffixes come from the region file; missing or bad entries give none", () => {
  assert.deepEqual(trustedSuffixesFor({trusted_email_suffixes: ["CA.gov", "edu", 3, ""]}), ["ca.gov", "edu"]);
  assert.deepEqual(trustedSuffixesFor({institutions: []}), []);
  assert.deepEqual(trustedSuffixesFor(null), []);
});

check("suffix hint is built from the region's suffixes", () => {
  assert.equal(suffixHintText("california", CA_SUFFIXES), "Addresses ending in .ca.gov, .ca.us, .edu or .gov can be confirmed for California.");
  assert.equal(suffixHintText("norway", []), "Email addresses cannot confirm an institution for Norway yet.");
  assert.equal(suffixHintText("california", ["gov"]), "Addresses ending in .gov can be confirmed for California.");
});

check("unlisted check: name, https website, region and a domain under a trusted suffix", () => {
  const good = {name: "OEHHA", url: "https://oehha.ca.gov", region: "california", domain: "OEHHA.ca.gov"};
  assert.deepEqual(checkUnlisted(good, CA_SUFFIXES), []);
  const fields = (values, suffixes = CA_SUFFIXES) => checkUnlisted({...good, ...values}, suffixes).map((e) => e.field);
  assert.deepEqual(fields({name: " "}), ["unl-name"]);
  assert.deepEqual(fields({url: "http://oehha.ca.gov"}), ["unl-url"], "website must be https");
  assert.deepEqual(fields({region: "constructor"}, []), ["unl-region", "unl-domain"]);
  assert.deepEqual(fields({domain: "evilca.gov"}, ["ca.gov"]), ["unl-domain"]);
  assert.deepEqual(fields({domain: ""}), ["unl-domain"]);
  assert.deepEqual(fields({domain: "oehha.ca.gov"}, []), ["unl-domain"], "a region with no suffixes refuses every domain");
  assert.equal(checkUnlisted({...good, url: ""}, CA_SUFFIXES).length, 0, "website is optional");
});

check("unlisted proposal payload: name, optional url, lowercase domain; claims carry the region", () => {
  assert.deepEqual(unlistedPayload({name: " OEHHA ", url: "", domain: "OEHHA.ca.gov"}), {name: "OEHHA", domain: "oehha.ca.gov"});
  const body = claimsBody({
    ticked: [],
    regions: [],
    proposals: [],
    unlisted: {name: "OEHHA", url: "https://oehha.ca.gov", region: "california", domain: "oehha.ca.gov"},
  });
  assert.deepEqual(body.proposals, [
    {kind: "institution", region: "california", payload: {name: "OEHHA", url: "https://oehha.ca.gov", domain: "oehha.ca.gov"}},
  ]);
  assert.deepEqual(claimsBody({ticked: [], regions: [], proposals: [{name: "Lab", url: ""}]}).proposals, [
    {kind: "institution", payload: {name: "Lab"}},
  ]);
});

check("names: an approved proposal with no name shows its domain; unknown errors stay plain text", () => {
  assert.equal(displayName({name: null, domain: "oehha.ca.gov"}), "oehha.ca.gov");
  assert.equal(displayName({name: "OEHHA"}), "OEHHA");
  assert.equal(errorText("domain_not_proposed"), "That address is not at the domain of the institution you proposed.");
  assert.equal(errorText("invalid_domain").includes("invalid_domain"), false);
  assert.equal(errorText("untrusted_domain").includes("untrusted_domain"), false);
});

check("page mode: a signed-in ambassador with a profile is the dashboard; everyone else sees the public page", () => {
  const me = (ambassador) => ({ok: true, status: 200, data: {ambassador}});
  assert.equal(pageMode(me({display_name: "A", needs_profile: false, regions: []})), "dashboard");
  assert.equal(pageMode(me({display_name: "A", needs_profile: false, regions: [{region: "california", status: "active"}]})), "dashboard");
  assert.equal(pageMode(me({display_name: "A", needs_profile: true})), "public");
  assert.equal(pageMode({ok: false, status: 401, error: "not_signed_in"}), "public");
  assert.equal(pageMode({ok: false, status: 0, error: "network"}), "public");
  assert.equal(pageMode(null), "public");
  assert.equal(pageMode({ok: true, data: {}}), "public");
});

check("map highlight: suggested from the ticked eligible institutions and the unlisted region; chosen from the ticks", () => {
  assert.equal(REGIONS_EVENT, "amb:regions");
  const checklist = [
    {id: "n1", eligible: true, regions: ["norway"]},
    {id: "c1", eligible: true, regions: ["california"]},
    {id: "x", eligible: false, regions: ["belgium"]},
  ];
  // Ticked: a Norway and a California institution. Only Norway is ticked on the Regions step.
  assert.deepEqual(signupRegionState({checklist, ticked: ["n1", "c1", "x"], regions: ["norway"]}), {
    suggested: ["california", "norway"], chosen: ["norway"],
  });
  // An ineligible tick never suggests its region; an unticked institution suggests nothing.
  assert.deepEqual(signupRegionState({checklist, ticked: ["x"], regions: ["belgium"]}), {suggested: [], chosen: []});
  assert.deepEqual(signupRegionState({checklist, ticked: ["c1"], regions: ["norway"]}), {
    suggested: ["california"], chosen: [],
  }, "a chosen region that is not suggested is dropped");
  // The unlisted proposal's region is suggested even with no eligible institution; there is no regions step, so nothing is chosen.
  const unlisted = {name: "OEHHA", region: "california", domain: "oehha.ca.gov"};
  assert.deepEqual(signupRegionState({checklist, ticked: [], regions: [], unlisted}), {suggested: ["california"], chosen: []});
  assert.deepEqual(signupRegionState({checklist, ticked: ["n1"], regions: ["norway"], unlisted}), {
    suggested: ["california", "norway"], chosen: ["norway"],
  });
  // Nothing ticked and no proposal: nothing is highlighted; a missing checklist is safe.
  assert.deepEqual(signupRegionState({checklist: null, ticked: [], regions: null}), {suggested: [], chosen: []});
});

console.log(`${passed} ambassador sign-up runtime checks passed`);
