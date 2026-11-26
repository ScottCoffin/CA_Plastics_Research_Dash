// ORCID-first sign-up on /ambassadors (AMB-1 front end slice 2a; docs/AMBASSADORS_SPEC.md section 13).
// The static markup is in ambassadors.md (#amb-signup). This module reads the query state, calls the Worker and
// draws the steps. Pure helpers are exported for tests/framework_ambassador_signup_runtime.mjs and stay free of DOM
// access at import time. Nothing personal is stored: no email in localStorage, and the query string is removed
// from the URL after it is read.
import {regionFileUrl} from "./atlas.js";
import {activeRegions, mountWorkspace} from "./ambassador_workspace.js";

/** The one API base. Every Worker call goes through apiUrl() and api() below. */
export const API_BASE = "https://api.plastiverse.live";
/** Turnstile site key (public). While it is PENDING-OWNER no Turnstile script loads and email is disabled. */
export const TURNSTILE_SITE_KEY = "0x4AAAAAAGSpAKBkj-_OosMX";
export const TURNSTILE_SCRIPT = "https://challenges.cloudflare.com/turnstile/v0/api.js";
/** Contribution terms version. Must match worker/src/signup.ts TERMS_VERSION. */
export const TERMS_VERSION = "v1";
export const STEP_COUNT = 4;
export const MAX_PROPOSALS = 10;
export const PROPOSE_REGION_HREF = "mailto:theplastiverse@gmail.com?subject=Propose%20a%20region";
export const REGION_NAMES = {belgium: "Belgium", california: "California", norway: "Norway"};

const PENDING = "PENDING-OWNER";
const EMAIL_RE = /^[^\s@]{1,64}@[^\s@]{1,253}\.[^\s@]{2,}$/;
const URL_RE = /^https?:\/\/\S+$/i;
const HTTPS_URL_RE = /^https:\/\/\S+$/i;
const DOMAIN_RE = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$/;

const ERROR_TEXT = {
  network: "We could not reach the sign-up service. Check your connection and try again.",
  not_signed_in: "Your sign-up has ended. Sign up with ORCID again to start.",
  lookup_failed: "We could not read your author record just now. Try again in a few minutes.",
  lookup_required: "We need to read your author record first. Reload this page and start again.",
  invalid_request: "Some answers were not in the expected form. Check the step and try again.",
  invalid_proposal: "A proposal could not be sent. Check its name and web address.",
  unknown_institution: "One of the institutions is no longer on your list. Reload this page and start again.",
  no_eligible_institution: "Tick at least one eligible institution, or propose one.",
  region_not_tied: "One of the regions is not tied to an institution you ticked. Choose the regions again.",
  region_required: "Choose at least one region.",
  invalid_email: "Enter a complete email address.",
  bot_check_failed: "The check did not pass. Complete it again and send the link.",
  rate_limited: "There have been too many attempts. Wait a while and try again.",
  claims_required: "Save your institutions and regions first, then confirm the email.",
  domain_not_claimed: "That address is not at the domain of an institution you ticked.",
  mail_failed: "We could not send the email just now. Try again in a few minutes.",
  invalid_display_name: "Enter a display name of up to 80 characters.",
  invalid_credit: "Choose whether to show your name, then try again.",
  terms_version_required: "Agree to the contribution terms to continue.",
  untrusted_domain: "That email domain cannot confirm an institution for this region. Use the domain shown in the hint.",
  invalid_domain: "Enter a work email domain such as oehha.ca.gov, without the @ or a web address.",
  invalid_region: "Choose the region for the institution you are proposing.",
  domain_not_proposed: "That address is not at the domain of the institution you proposed.",
};
const GENERIC_ERROR = "Something went wrong on our side. Try again in a few minutes.";

/** Maps an API error code to a plain sentence. Raw codes and stack traces are never shown. */
export function errorText(code) {
  return Object.prototype.hasOwnProperty.call(ERROR_TEXT, code) ? ERROR_TEXT[code] : GENERIC_ERROR;
}

export function apiUrl(path) {
  return `${API_BASE}${path}`;
}

/** Query state on page load: "signup" (ORCID returned, step flow), "signin" (ORCID sign-in), "failed",
 *  "pending_review" (email confirmed, waiting for a moderator), or null. */
export function routeFromSearch(search) {
  const params = new URLSearchParams(search || "");
  if (params.get("signup") === "orcid") return "signup";
  if (params.get("signin") === "failed") return "failed";
  if (params.get("signin") === "orcid") return "signin";
  // Set by the emailed link (or ORCID sign-in) for a sign-up waiting on moderation. No session is kept.
  if (params.get("signup") === "pending_review") return "pending_review";
  return null;
}

/** The same URL with the query string removed (the hash is kept). */
export function stripQuery(href) {
  const url = new URL(href);
  url.search = "";
  return url.href;
}

/** Eligible institutions that are ticked. Ticks on ineligible items are ignored. */
export function eligibleTicked(checklist, ticked) {
  const picked = new Set(ticked || []);
  return (checklist || []).filter((item) => item.eligible && picked.has(item.id));
}

/** Regions tied to the ticked eligible institutions, in alphabetical order. Nothing is preselected. */
export function regionsFor(checklist, ticked) {
  const set = new Set();
  for (const item of eligibleTicked(checklist, ticked)) for (const region of item.regions || []) set.add(region);
  return [...set].sort();
}

/** Keeps only the selected regions that are still offered (going back and changing institutions). */
export function keepSelected(selected, available) {
  return (selected || []).filter((region) => available.includes(region));
}

/** The event the page root carries for the map (ambassadors.js listens; the same string there). */
export const REGIONS_EVENT = "amb:regions";
/**
 * The regions the map shows during sign-up. suggested: the regions of the ticked eligible institutions plus the region
 * of an unlisted institution proposal. chosen: the ticked regions that are suggested (never more than suggested).
 */
export function signupRegionState({checklist, ticked, regions, unlisted = null}) {
  const suggested = [...new Set([...regionsFor(checklist, ticked), ...(unlisted?.region ? [unlisted.region] : [])])].sort();
  return {suggested, chosen: keepSelected(regions, suggested).sort()};
}

/** Email domains accepted for the ticked institutions, from each region's allowlist file. */
export function allowedDomains(files, ticked) {
  const out = new Set();
  const picked = new Set(ticked || []);
  for (const file of Object.values(files || {})) {
    for (const institution of file?.institutions || []) {
      if (!picked.has(institution.id)) continue;
      for (const domain of institution.domains || []) out.add(String(domain).toLowerCase());
    }
  }
  return [...out].sort();
}

/** The name to show for a checklist item. An approved proposal may have no name yet: its domain is shown instead. */
export function displayName(item) {
  return item?.name || item?.domain || "Institution awaiting details";
}

export function yearsText(years) {
  if (!years) return "";
  const {from = null, to = null} = years;
  if (from === null && to === null) return "";
  if (to === null) return `since ${from}`;
  if (from === null) return `until ${to}`;
  return from === to ? `${from}` : `${from} to ${to}`;
}

// ---- validation (pure). Each problem is {field, message}; field is the id of the element to focus. -----------
export function checkInstitutions({ticked, proposals, checklist, unlisted = null}) {
  if (eligibleTicked(checklist, ticked).length === 0 && (proposals || []).length === 0 && !unlisted) {
    return [{field: "signup-institutions", message: "Tick at least one eligible institution, or propose one."}];
  }
  return [];
}

export function checkRegions({regions, eligibleCount}) {
  if (eligibleCount > 0 && (regions || []).length === 0) {
    return [{field: "signup-regions", message: "Choose at least one region."}];
  }
  return [];
}

export function checkProposal({name, url}) {
  const errors = [];
  const trimmedName = String(name || "").trim();
  const trimmedUrl = String(url || "").trim();
  if (!trimmedName) errors.push({field: "prop-name", message: "Enter the institution's name."});
  else if (trimmedName.length > 200) errors.push({field: "prop-name", message: "The name is too long. Use 200 characters at most."});
  if (trimmedUrl && (trimmedUrl.length > 300 || !URL_RE.test(trimmedUrl))) {
    errors.push({field: "prop-url", message: "Enter a web address starting with https://, or leave it empty."});
  }
  return errors;
}

export function emailDomain(email) {
  const at = String(email || "").lastIndexOf("@");
  return at < 0 ? "" : String(email).slice(at + 1).toLowerCase();
}

export function domainMatches(domain, base) {
  return domain === base || domain.endsWith(`.${base}`);
}

/** The trusted email suffixes of a region's allowlist file, lower case. Missing means none. */
export function trustedSuffixesFor(file) {
  const values = Array.isArray(file?.trusted_email_suffixes) ? file.trusted_email_suffixes : [];
  return values.filter((value) => typeof value === "string" && value).map((value) => value.toLowerCase());
}

/**
 * True when the domain is a suffix itself or ends in ".<suffix>" (subdomains included). A look-alike such as
 * evilca.gov does not match ca.gov, and a bare label such as "edu" is not a domain.
 */
export function domainHasTrustedSuffix(domain, suffixes) {
  const value = String(domain || "").trim().toLowerCase();
  if (!DOMAIN_RE.test(value)) return false;
  return (suffixes || []).some((suffix) => value === suffix || value.endsWith(`.${suffix}`));
}

/** The hint under the work email field, built from the region's suffixes. */
export function suffixHintText(region, suffixes) {
  const label = regionLabel(region);
  if (!suffixes || suffixes.length === 0) return `Email addresses cannot confirm an institution for ${label} yet.`;
  const list = suffixes.map((suffix) => `.${suffix}`);
  const text = list.length === 1 ? list[0] : `${list.slice(0, -1).join(", ")} or ${list[list.length - 1]}`;
  return `Addresses ending in ${text} can be confirmed for ${label}.`;
}

/** The proposal payload for an unlisted institution: name, optional https web address, and the email domain. */
export function unlistedPayload({name, url, domain}) {
  const payload = {name: String(name || "").trim()};
  const web = String(url || "").trim();
  if (web) payload.url = web;
  payload.domain = String(domain || "").trim().toLowerCase();
  return payload;
}

/** Checks the unlisted-institution form. `suffixes` are the trusted suffixes of the chosen region. */
export function checkUnlisted({name, url, region, domain}, suffixes) {
  const errors = [];
  const trimmedName = String(name || "").trim();
  const web = String(url || "").trim();
  if (!trimmedName) errors.push({field: "unl-name", message: "Enter the institution's name."});
  else if (trimmedName.length > 200) errors.push({field: "unl-name", message: "The name is too long. Use 200 characters at most."});
  if (web && (web.length > 300 || !HTTPS_URL_RE.test(web))) {
    errors.push({field: "unl-url", message: "Enter a web address starting with https://, or leave it empty."});
  }
  if (!Object.prototype.hasOwnProperty.call(REGION_NAMES, region)) errors.push({field: "unl-region", message: "Choose a region."});
  const host = String(domain || "").trim().toLowerCase();
  if (!host) {
    errors.push({field: "unl-domain", message: "Enter the email domain your institution uses, such as oehha.ca.gov."});
  } else if (!domainHasTrustedSuffix(host, suffixes)) {
    errors.push({field: "unl-domain", message: `${suffixHintText(region, suffixes)} Check the work email domain.`});
  }
  return errors;
}

/** Email format, then the domain check when the ticked institutions list domains. The server decides the rest. */
export function checkEmail(email, allowed) {
  const value = String(email || "").trim().toLowerCase();
  if (value.length > 254 || !EMAIL_RE.test(value)) {
    return [{field: "signup-email", message: "Enter a complete email address, such as name@institution.edu."}];
  }
  if (allowed && allowed.length > 0 && !allowed.some((base) => domainMatches(emailDomain(value), base))) {
    return [{field: "signup-email", message: "That address is not at one of the domains listed above."}];
  }
  return [];
}

export function checkProfile({name, accepted}) {
  const errors = [];
  const trimmed = String(name || "").trim();
  if (trimmed.length < 1 || trimmed.length > 80) {
    errors.push({field: "profile-name", message: "Enter a display name of up to 80 characters."});
  }
  if (!accepted) errors.push({field: "profile-terms", message: "Tick the box to agree to the contribution terms."});
  return errors;
}

// ---- request bodies (pure) ---------------------------------------------------------------------------------
export function claimsBody({ticked, regions, proposals, unlisted = null}) {
  // Each claims call replaces the earlier proposals, so every call sends the full list.
  const items = (proposals || []).map((p) => ({
    kind: "institution",
    payload: p.url ? {name: p.name.trim(), url: p.url.trim()} : {name: p.name.trim()},
  }));
  // An unlisted institution carries its region and work email domain (the Worker checks the domain's suffix).
  if (unlisted) items.push({kind: "institution", region: unlisted.region, payload: unlistedPayload(unlisted)});
  return {institutions: [...(ticked || [])], regions: [...(regions || [])], proposals: items};
}

export function profileBody({name, creditPublic}) {
  return {display_name: String(name || "").trim(), credit_public: Boolean(creditPublic), accept_terms_version: TERMS_VERSION};
}

// ---- DOM ----------------------------------------------------------------------------------------------------
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const regionLabel = (slug) => REGION_NAMES[slug] || slug;

/** One API helper for the Worker. Always sends credentials; always parses the JSON body; never throws. */
// Exported for ambassador_workspace.js, which calls the Worker through this same helper (credentials included).
export async function api(path, {method = "GET", body} = {}) {
  let response;
  try {
    response = await fetch(apiUrl(path), {
      method,
      credentials: "include",
      cache: "no-store",
      headers: body === undefined ? {} : {"Content-Type": "application/json"},
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    return {ok: false, status: 0, error: "network"};
  }
  const data = await response.json().catch(() => null);
  if (response.ok && data && data.ok !== false) return {ok: true, status: response.status, data};
  return {ok: false, status: response.status, error: (data && data.error) || `http_${response.status}`};
}

let panel = null;
let body = null;
let statusEl = null;
let flow = freshFlow();
let turnstileLoading = null;
let pageRoot = null;

/**
 * The page mode after GET /me: "dashboard" for a signed-in ambassador whose profile is complete, else "public"
 * (the recruiting page, as today). A failed or missing /me is public too.
 */
export function pageMode(me) {
  const ambassador = me && me.ok && me.data ? me.data.ambassador : null;
  return ambassador && !ambassador.needs_profile ? "dashboard" : "public";
}

const DASHBOARD_TITLE = "Your ambassador dashboard · Plastiverse Live";
let publicTitle = null;

/** Sets data-mode on the page root (the CSS hides the recruiting sections in dashboard and checking modes). */
export function setPageMode(mode) {
  if (!pageRoot) return;
  pageRoot.dataset.mode = mode;
  if (publicTitle === null) publicTitle = document.title;
  document.title = mode === "dashboard" ? DASHBOARD_TITLE : publicTitle;
}

function freshFlow() {
  return {
    step: 1, profile: null, ticked: [], regions: [], proposals: [], proposalOpen: false, domains: [], token: "", widgetId: null,
    unlisted: null, proposalOnly: false, suffixes: {},
  };
}

const $ = (selector) => body.querySelector(selector);
const checkedValues = (name) => [...body.querySelectorAll(`input[name="${name}"]:checked`)].map((input) => input.value);

function setStatus(text) {
  if (statusEl) statusEl.textContent = text;
}

/** Tells the map which regions to highlight. Nothing is sent to the Worker. */
function emitRegions(detail) {
  pageRoot?.dispatchEvent(new CustomEvent(REGIONS_EVENT, {bubbles: true, detail}));
}
function publishRegions() {
  emitRegions(flow.profile
    ? signupRegionState({checklist: flow.profile.institutions, ticked: flow.ticked, regions: flow.regions, unlisted: flow.unlisted})
    : {suggested: [], chosen: []});
}
/** The sign-up has ended or was cancelled: the map drops its highlight. */
function clearRegions() {
  emitRegions({suggested: [], chosen: []});
}

function show(html, focus = true) {
  body.innerHTML = html;
  panel.hidden = false;
  const heading = body.querySelector("h2");
  if (focus && heading) heading.focus();
}

function showLanding(message = "") {
  panel.hidden = true;
  body.innerHTML = "";
  flow = freshFlow();
  setStatus(message);
  clearRegions();
}

function showErrors(errors) {
  const host = $("[data-errors-host]");
  if (!host) return;
  host.innerHTML = errors.length === 0 ? "" : `<div class="err-sum" data-errors tabindex="-1">
    <p>${errors.length === 1 ? "Please check this point" : "Please check these points"}</p>
    <ul>${errors.map((e) => `<li><a href="#${esc(e.field)}" data-focus="${esc(e.field)}">${esc(e.message)}</a></li>`).join("")}</ul>
  </div>`;
  const summary = host.querySelector("[data-errors]");
  if (summary) summary.focus();
  setStatus(errors[0] ? errors[0].message : "");
}

function setBusy(form, busy) {
  const submit = form?.querySelector('[type="submit"]');
  if (submit) submit.disabled = busy;
}

function stepHead(n, title) {
  return `<p class="step-n">Step ${n} of ${STEP_COUNT}</p><h2 tabindex="-1">${esc(title)}</h2><div data-errors-host></div>`;
}

const STEP_TITLES = {1: "Your record", 2: "Institutions", 3: "Regions", 4: "Confirm one institutional email"};

function renderStep(n) {
  flow.step = n;
  setStatus(`Step ${n} of ${STEP_COUNT}: ${STEP_TITLES[n]}.`);
  publishRegions();
  if (n === 1) return stepRecord();
  if (n === 2) return stepInstitutions();
  if (n === 3) return stepRegions();
  return stepEmail();
}

function backButton() {
  return '<button type="button" class="btn" data-action="back">Back</button>';
}

function stepRecord() {
  const p = flow.profile;
  const record = p.author
    ? `<dl class="kv"><dt>Author record</dt><dd>${esc(p.author.display_name)}</dd>` +
      `<dt>ORCID iD</dt><dd><span class="addr">${esc(p.orcid)}</span></dd>` +
      `<dt>Institutions on the record</dt><dd>${p.institutions.length}</dd></dl>`
    : "<p>We could not find your author record. You can still continue: propose your institutions and regions, and moderation will review them.</p>";
  const employments = p.employments_checked === false
    ? "<p class=\"hint\">Public ORCID employments could not be checked just now. You can propose any missing institution in the next step.</p>"
    : "";
  show(`${stepHead(1, STEP_TITLES[1])}
    <form data-form="record" novalidate>
      ${record}${employments}
      <div class="btns">${backButton()}<button type="submit" class="btn solid">Continue</button></div>
    </form>`);
}

function ticksHTML(items) {
  return items.map((item) => {
    const regions = (item.regions || []).map(regionLabel).join(", ");
    const years = yearsText(item.years);
    return `<li><label class="check"><input type="checkbox" name="institution" value="${esc(item.id)}"${flow.ticked.includes(item.id) ? " checked" : ""}>` +
      `<span>${esc(displayName(item))}${years ? ` (${esc(years)})` : ""}<small>Eligible for ${esc(regions)}</small></span></label></li>`;
  }).join("");
}

function proposalsHTML() {
  return flow.proposals.map((p, i) => `<li>${esc(p.name)}${p.url ? ` <small>${esc(p.url)}</small>` : ""}
    <button type="button" class="link-btn" data-action="remove-proposal" data-index="${i}" aria-label="Remove the proposal for ${esc(p.name)}">Remove</button></li>`).join("");
}

/** "My institution isn't listed": always shown; highlighted when no eligible institution exists. */
function unlistedHTML(noEligible) {
  const u = flow.unlisted;
  const summary = u
    ? `<p>Proposed: <strong>${esc(u.name)}</strong>, email domain <span class="addr">${esc(u.domain)}</span>, ${esc(regionLabel(u.region))}.
        <button type="button" class="link-btn" data-action="remove-unlisted" aria-label="Remove the institution ${esc(u.name)}">Remove</button></p>`
    : `<div class="field"><label for="unl-name">Institution name</label><input id="unl-name" type="text" maxlength="200" autocomplete="organization"></div>
        <div class="field"><label for="unl-url">Website (optional)</label><input id="unl-url" type="url" maxlength="300" placeholder="https://" autocomplete="url"></div>
        <div class="field"><label for="unl-region">Region</label><select id="unl-region" class="mod-select">
          <option value="">Choose a region</option>${Object.keys(REGION_NAMES).map((slug) => `<option value="${esc(slug)}">${esc(regionLabel(slug))}</option>`).join("")}
        </select></div>
        <div class="field"><label for="unl-domain">Work email domain</label><input id="unl-domain" type="text" maxlength="253" placeholder="oehha.ca.gov" autocomplete="off" spellcheck="false" aria-describedby="unl-domain-hint">
          <p class="hint" id="unl-domain-hint">Choose a region to see which email domains can confirm it.</p></div>
        <div class="btns"><button type="button" class="btn" data-action="add-unlisted">Add this institution</button></div>`;
  return `<fieldset id="signup-unlisted" class="unlisted${noEligible ? " is-key" : ""}" tabindex="-1" data-unlisted-area>
    <legend>My institution isn't listed</legend>
    <p class="hint">${noEligible ? "None of your institutions is on the eligible list yet. " : ""}Add your institution and a work email domain. We send a link to that address; a moderator then reviews the request.</p>
    ${summary}
  </fieldset>`;
}

function updateUnlistedHint() {
  const hint = $("#unl-domain-hint");
  const region = $("#unl-region")?.value || "";
  if (hint) hint.textContent = region ? suffixHintText(region, flow.suffixes[region] || []) : "Choose a region to see which email domains can confirm it.";
}

function stepInstitutions() {
  const items = flow.profile.institutions || [];
  const eligible = items.filter((item) => item.eligible);
  const ineligible = items.filter((item) => !item.eligible);
  const message = items.length === 0 && flow.profile.message ? `<p>${esc(flow.profile.message)}</p>` : "";
  const eligibleBlock = eligible.length
    ? `<fieldset id="signup-institutions" tabindex="-1"><legend>Institutions you can claim</legend><p class="hint">Tick each institution you work or worked at. Any listed affiliation counts, current or past.</p><ul class="plain">${ticksHTML(eligible)}</ul></fieldset>`
    : "";
  const ineligibleBlock = ineligible.length
    ? `<h3>Not eligible yet</h3><ul class="plain">${ineligible.map((item) =>
      `<li><span>${esc(displayName(item))}</span><small class="hint"> Not yet on a region's list of eligible institutions, so it cannot be claimed here.</small></li>`).join("")}</ul>`
    : "";
  show(`${stepHead(2, STEP_TITLES[2])}
    ${message}${eligibleBlock}${ineligibleBlock}
    <div class="proposal" data-proposal-area>
      <button type="button" class="btn" data-action="toggle-proposal" aria-expanded="${flow.proposalOpen ? "true" : "false"}" aria-controls="signup-proposal">Propose another institution</button>
      <div id="signup-proposal" class="sub" ${flow.proposalOpen ? "" : "hidden"}>
        <div class="field"><label for="prop-name">Institution name</label><input id="prop-name" type="text" maxlength="200" autocomplete="off"></div>
        <div class="field"><label for="prop-url">Web address (optional)</label><input id="prop-url" type="url" maxlength="300" placeholder="https://" autocomplete="off"></div>
        <div class="btns"><button type="button" class="btn" data-action="add-proposal">Add this proposal</button></div>
      </div>
      <ul class="plain" aria-label="Proposed institutions">${proposalsHTML()}</ul>
    </div>
    ${unlistedHTML(eligibleTicked(items, flow.ticked).length === 0)}
    <form data-form="institutions" novalidate>
      <div class="btns">${backButton()}<button type="submit" class="btn solid">Continue</button></div>
    </form>`, true);
}

function stepRegions() {
  const available = regionsFor(flow.profile.institutions, flow.ticked);
  flow.regions = keepSelected(flow.regions, available);
  const hasEligible = eligibleTicked(flow.profile.institutions, flow.ticked).length > 0;
  const choice = available.length
    ? `<fieldset id="signup-regions" tabindex="-1"><legend>Regions you want to join</legend>
        <p class="hint">Regions tied to the institutions you ticked. Choose one or more; nothing is chosen for you.</p>
        ${available.map((region) => `<label class="check"><input type="checkbox" name="region" value="${esc(region)}"${flow.regions.includes(region) ? " checked" : ""}><span>${esc(regionLabel(region))}</span></label>`).join("")}
      </fieldset>`
    : `<p>${hasEligible ? "" : "No institution is ticked, so there are no regions to choose. Continue to send your proposals to moderation."}</p>`;
  show(`${stepHead(3, STEP_TITLES[3])}
    ${choice}
    <p class="hint">Not on this list? <a class="link" href="${PROPOSE_REGION_HREF}">Propose a region</a>.</p>
    <form data-form="regions" novalidate>
      <div class="btns">${backButton()}<button type="submit" class="btn solid">Continue</button></div>
    </form>`);
}

/** The allowlist file of each region (same-origin, no credentials). A missing file maps to null. */
async function loadRegionFiles(slugs) {
  const files = {};
  await Promise.all([...slugs].map(async (slug) => {
    const response = await fetch(regionFileUrl(slug, "ambassador_institutions.json"), {cache: "no-cache"}).catch(() => null);
    files[slug] = response?.ok ? await response.json().catch(() => null) : null;
  }));
  return files;
}

async function loadDomains(ticked, checklist) {
  const slugs = new Set();
  for (const item of eligibleTicked(checklist, ticked)) for (const region of item.regions || []) slugs.add(region);
  return allowedDomains(await loadRegionFiles(slugs), ticked);
}

function loadTurnstile() {
  if (window.turnstile) return Promise.resolve();
  if (!turnstileLoading) {
    turnstileLoading = new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = TURNSTILE_SCRIPT;
      script.async = true;
      script.onload = resolve;
      script.onerror = () => reject(new Error("turnstile"));
      document.head.append(script);
    });
  }
  return turnstileLoading;
}

function syncSubmit() {
  const submit = $("#signup-send");
  if (submit) submit.disabled = TURNSTILE_SITE_KEY === PENDING || !flow.token;
}

async function mountTurnstile() {
  if (TURNSTILE_SITE_KEY === PENDING) return;
  const host = $("#signup-turnstile");
  if (!host) return;
  try {
    await loadTurnstile();
    if (!$("#signup-turnstile")) return;
    flow.widgetId = window.turnstile.render(host, {
      sitekey: TURNSTILE_SITE_KEY,
      callback: (token) => {
        flow.token = token;
        syncSubmit();
      },
      "expired-callback": () => {
        flow.token = "";
        syncSubmit();
      },
      "error-callback": () => {
        flow.token = "";
        syncSubmit();
      },
    });
  } catch {
    setStatus("The check could not load. Reload this page to try again.");
  }
}

async function stepEmail() {
  const onlyUnlisted = flow.proposalOnly && flow.unlisted;
  flow.domains = onlyUnlisted ? [flow.unlisted.domain] : await loadDomains(flow.ticked, flow.profile.institutions);
  let domains = flow.domains.length
    ? `Use your address at one of these domains: ${esc(flow.domains.join(", "))}.`
    : "The institutions you ticked do not list a domain yet. Email the address in the contribution terms for help.";
  if (onlyUnlisted) domains = `Your address must be at ${esc(flow.unlisted.domain)} or one of its subdomains.`;
  const captcha = TURNSTILE_SITE_KEY === PENDING
    ? '<p class="status" id="signup-captcha">Email confirmation opens soon.</p>'
    : '<div id="signup-turnstile" class="turnstile"></div>';
  show(`${stepHead(4, STEP_TITLES[4])}
    <p>We send one link to this address. It works once and expires after 30 minutes. Your address is not stored in this browser.</p>
    <form data-form="email" novalidate>
      <div class="field">
        <label for="signup-email">Institutional email address</label>
        <input id="signup-email" name="email" type="email" autocomplete="email" inputmode="email" spellcheck="false" aria-describedby="signup-email-hint">
        <p class="hint" id="signup-email-hint">${domains} Free email services cannot be used.</p>
      </div>
      ${captcha}
      <div class="btns">${backButton()}<button type="submit" class="btn solid" id="signup-send" disabled>Send confirmation link</button></div>
    </form>`);
  await mountTurnstile();
  syncSubmit();
}

function showInbox() {
  clearRegions();
  show(`<p class="step-n">Email sent</p><h2 tabindex="-1">Check your inbox</h2>
    <p>We sent a confirmation link to your institutional address. It works once and expires in 30 minutes. Open it in this browser to finish signing up.</p>
    <p class="hint">Nothing else is needed on this page.</p>`);
  setStatus("Check your inbox for the confirmation link.");
}

function showMessage(title, text, actions = "") {
  clearRegions();
  show(`<h2 tabindex="-1">${esc(title)}</h2><p>${esc(text)}</p>${actions ? `<div class="btns">${actions}</div>` : ""}`);
  setStatus(title);
}

const orcidLink = (label) => `<a class="btn solid" href="${apiUrl("/orcid/start")}">${esc(label)}</a>`;
const retryButton = '<button type="button" class="btn" data-action="retry">Try again</button>';

function showFailed() {
  showMessage("We could not sign you in", "Nothing was changed. Try signing in with ORCID again.", orcidLink("Sign in with ORCID"));
}

function showProposalsSent() {
  clearRegions();
  show(`<h2 tabindex="-1">Your proposals are with moderation</h2>
    <p>Thank you. Moderation reviews each proposal; it does not block anything else. To confirm an email you need at least one eligible institution on your record. You can sign up again when one is listed.</p>
    <p><a class="link" href="./ambassadors">Back to the ambassador page</a></p>`);
  setStatus("Your proposals were sent to moderation.");
}

/** Email confirmed for an unlisted institution: no session exists yet, so nothing else is loaded. */
function showPendingReview() {
  clearRegions();
  show(`<h2 tabindex="-1">Your sign-up is with moderation</h2>
    <p>Thanks, your email is confirmed. A moderator will review your institution and you'll get an email when your account is active.</p>
    <p><a class="link" href="./ambassadors">Back to the ambassador page</a></p>`);
  setStatus("Your email is confirmed. A moderator will review your institution.");
}

function showFirstVisit() {
  show(`<h2 tabindex="-1">Set up your ambassador profile</h2>
    <p>A few details before your workspace opens.</p>
    <form data-form="profile" novalidate>
      <div data-errors-host></div>
      <div class="field">
        <label for="profile-name">Display name</label>
        <input id="profile-name" name="display_name" type="text" maxlength="80" autocomplete="name" aria-describedby="profile-name-hint">
        <p class="hint" id="profile-name-hint">How your name appears on Atlas pages you contribute to. Up to 80 characters.</p>
      </div>
      <div class="group">
        <label class="check"><input id="profile-credit" name="credit" type="checkbox" checked aria-describedby="profile-credit-hint"><span>Show my name as a contributor</span></label>
        <p class="hint" id="profile-credit-hint">On by default. Untick it and your contributions are marked "Confirmed by a local ambassador" instead of your name.</p>
      </div>
      <div class="group">
        <label class="check"><input id="profile-terms" name="terms" type="checkbox" aria-describedby="profile-terms-hint"><span>I agree to the contribution terms (version ${TERMS_VERSION}).</span></label>
        <p class="hint" id="profile-terms-hint"><a class="link" href="./ambassador_terms">Read the contribution terms</a>. They explain the licence, the public credit and how to withdraw.</p>
      </div>
      <div class="btns"><button type="submit" class="btn solid">Save and continue</button></div>
    </form>`);
}

/** Shows the right screen for a signed-in ambassador: the first-visit profile when it is missing, else the dashboard. */
function showAccount(ambassador, focus = true) {
  clearRegions();
  if (ambassador.needs_profile) {
    showFirstVisit();
    if (!focus) body.querySelector("h2")?.blur();
    return;
  }
  panel.hidden = false;
  return mountWorkspace(body, ambassador, {focus, announce: setStatus});
}

async function startSignup() {
  const [response, files] = await Promise.all([api("/signup/profile"), loadRegionFiles(Object.keys(REGION_NAMES))]);
  if (!response.ok) {
    const again = response.error === "not_signed_in" ? orcidLink("Sign up with ORCID") : retryButton;
    return showMessage("We could not start your sign-up", errorText(response.error), again);
  }
  flow = freshFlow();
  for (const slug of Object.keys(REGION_NAMES)) flow.suffixes[slug] = trustedSuffixesFor(files[slug]);
  flow.profile = response.data;
  renderStep(1);
}

/** Reads the ticks and regions on screen into the flow, so going back or re-rendering keeps them. */
function captureStep() {
  if (!body) return;
  if (flow.step === 2 && $('[data-form="institutions"]')) flow.ticked = checkedValues("institution");
  if (flow.step === 3 && $('[data-form="regions"]')) flow.regions = checkedValues("region");
}

function addProposal() {
  captureStep();
  const name = $("#prop-name")?.value ?? "";
  const url = $("#prop-url")?.value ?? "";
  const errors = checkProposal({name, url});
  if (flow.proposals.length >= MAX_PROPOSALS) {
    errors.push({field: "prop-name", message: `You can propose up to ${MAX_PROPOSALS} institutions.`});
  }
  if (errors.length) return showErrors(errors);
  flow.proposals.push({name: name.trim(), url: url.trim()});
  flow.proposalOpen = true;
  renderStep(2);
  setStatus(`Proposal added: ${name.trim()}. It is sent when you continue.`);
  $("#prop-name")?.focus();
  return undefined;
}

async function submitRegions(form) {
  captureStep();
  const eligibleCount = eligibleTicked(flow.profile.institutions, flow.ticked).length;
  const errors = checkRegions({regions: flow.regions, eligibleCount});
  if (errors.length) return showErrors(errors);
  return sendClaims(form, "signup-regions");
}

/** Saves the ticks, regions and proposals. Moves on to the email step, or to moderation when nothing needs an email. */
async function sendClaims(form, field) {
  setBusy(form, true);
  const response = await api("/signup/claims", {
    method: "POST",
    body: claimsBody({ticked: flow.ticked, regions: flow.regions, proposals: flow.proposals, unlisted: flow.unlisted}),
  });
  setBusy(form, false);
  if (!response.ok) {
    // Errors about the unlisted institution point at its fields; they are on the same step when it was sent.
    const unlistedField = {invalid_domain: "unl-domain", untrusted_domain: "unl-domain", invalid_region: "unl-region"}[response.error];
    return showErrors([{field: unlistedField && flow.unlisted ? unlistedField : field, message: errorText(response.error)}]);
  }
  if (response.data.status === "pending_email_proposal") {
    flow.proposalOnly = true;
    return renderStep(4);
  }
  if (response.data.status === "pending_email") {
    flow.proposalOnly = false;
    return renderStep(4);
  }
  return showProposalsSent();
}

function addUnlisted() {
  captureStep();
  const values = {
    name: $("#unl-name")?.value ?? "",
    url: $("#unl-url")?.value ?? "",
    region: $("#unl-region")?.value ?? "",
    domain: $("#unl-domain")?.value ?? "",
  };
  const errors = checkUnlisted(values, flow.suffixes[values.region] || []);
  if (errors.length) return showErrors(errors);
  flow.unlisted = {name: values.name.trim(), url: values.url.trim(), region: values.region, domain: values.domain.trim().toLowerCase()};
  renderStep(2);
  setStatus(`Institution proposal added: ${flow.unlisted.name}. It is sent when you continue.`);
  return undefined;
}

async function submitEmail(form) {
  const email = String(form.elements.email.value || "").trim().toLowerCase();
  const errors = checkEmail(email, flow.domains);
  if (errors.length) return showErrors(errors);
  setBusy(form, true);
  const response = await api("/signup/email", {method: "POST", body: {email, turnstileToken: flow.token}});
  setBusy(form, false);
  // Turnstile tokens are single use: reset the widget after every attempt.
  flow.token = "";
  if (flow.widgetId !== null && window.turnstile) window.turnstile.reset(flow.widgetId);
  syncSubmit();
  if (!response.ok) {
    const message = response.error === "domain_not_proposed" && flow.unlisted
      ? `Use an address at ${flow.unlisted.domain}, the institution you proposed.`
      : errorText(response.error);
    return showErrors([{field: "signup-email", message}]);
  }
  return showInbox();
}

async function submitProfile(form) {
  const name = form.elements.display_name.value;
  const errors = checkProfile({name, accepted: form.elements.terms.checked});
  if (errors.length) return showErrors(errors);
  setBusy(form, true);
  const saved = await api("/signup/profile", {method: "POST", body: profileBody({name, creditPublic: form.elements.credit.checked})});
  setBusy(form, false);
  if (!saved.ok) return showErrors([{field: "profile-name", message: errorText(saved.error)}]);
  const me = await api("/me");
  if (!me.ok) return showMessage("Your profile is saved", errorText(me.error), retryButton);
  return showAccount(me.data.ambassador);
}

function onSubmit(form) {
  const kind = form.dataset.form;
  if (kind === "record") return renderStep(2);
  if (kind === "institutions") {
    captureStep();
    const errors = checkInstitutions({ticked: flow.ticked, proposals: flow.proposals, checklist: flow.profile.institutions, unlisted: flow.unlisted});
    if (errors.length) return showErrors(errors);
    // With no eligible institution ticked, the unlisted institution's region is used, so the regions step is skipped.
    if (flow.unlisted && eligibleTicked(flow.profile.institutions, flow.ticked).length === 0) {
      flow.regions = [];
      return sendClaims(form, "signup-institutions");
    }
    return renderStep(3);
  }
  if (kind === "regions") return submitRegions(form);
  if (kind === "email") return submitEmail(form);
  if (kind === "profile") return submitProfile(form);
  return undefined;
}

async function onAction(action, el) {
  if (action === "back") {
    captureStep();
    if (flow.step <= 1) return showLanding();
    if (flow.step === 4 && flow.proposalOnly) return renderStep(2);
    return renderStep(flow.step - 1);
  }
  if (action === "add-unlisted") return addUnlisted();
  if (action === "remove-unlisted") {
    captureStep();
    flow.unlisted = null;
    renderStep(2);
    return setStatus("Institution proposal removed.");
  }
  if (action === "toggle-proposal") {
    captureStep();
    flow.proposalOpen = !flow.proposalOpen;
    renderStep(2);
    return $("#prop-name")?.focus();
  }
  if (action === "add-proposal") return addProposal();
  if (action === "remove-proposal") {
    captureStep();
    flow.proposals.splice(Number(el.dataset.index), 1);
    renderStep(2);
    return setStatus("Proposal removed.");
  }
  if (action === "retry") return startSignup();
  if (action === "signout") {
    // A visible message, not only the status line: the panel is hidden when the landing page shows.
    const response = await api("/auth/signout", {method: "POST"});
    if (!response.ok) return showMessage("We could not sign you out", errorText(response.error));
    setPageMode("public");
    return showMessage("You have signed out", "Your session has ended on this device.", orcidLink("Sign in with ORCID"));
  }
  return undefined;
}

/** Mounts the sign-up. Call once after the page markup is in the DOM. The page stays in its checking mode until /me answers. */
export async function mountSignup(root) {
  pageRoot = root;
  let modeSet = false;
  const report = (mode) => {
    modeSet = true;
    setPageMode(mode);
  };
  try {
    return await mountSignupFlow(root, report);
  } finally {
    if (!modeSet) setPageMode("public");
  }
}

async function mountSignupFlow(root, report) {
  panel = root.querySelector("#amb-signup");
  body = root.querySelector("#amb-signup-body");
  statusEl = root.querySelector("#amb-signup-status");
  if (!panel || !body) return;
  root.querySelectorAll("[data-orcid-start]").forEach((link) => {
    link.href = apiUrl("/orcid/start");
  });

  panel.addEventListener("submit", (event) => {
    event.preventDefault();
    if (event.target.dataset?.form) onSubmit(event.target);
  });
  panel.addEventListener("click", (event) => {
    const focusTarget = event.target.closest("[data-focus]");
    if (focusTarget) {
      event.preventDefault();
      document.getElementById(focusTarget.dataset.focus)?.focus();
      return;
    }
    const action = event.target.closest("[data-action]");
    if (action) onAction(action.dataset.action, action);
  });
  panel.addEventListener("keydown", (event) => {
    // Enter in the proposal fields adds the proposal instead of submitting the step form.
    if (event.key === "Enter" && event.target.closest("[data-proposal-area]")) {
      event.preventDefault();
      addProposal();
    }
    if (event.key === "Enter" && event.target.closest("[data-unlisted-area]") && event.target.tagName === "INPUT") {
      event.preventDefault();
      addUnlisted();
    }
  });
  panel.addEventListener("input", syncSubmit);
  panel.addEventListener("change", (event) => {
    if (event.target.id === "unl-region") updateUnlistedHint();
    // Ticks and regions update the map as they change, not only when the step is drawn.
    if (event.target.name === "institution") {
      flow.ticked = checkedValues("institution");
      publishRegions();
    }
    if (event.target.name === "region") {
      flow.regions = checkedValues("region");
      publishRegions();
    }
  });

  const route = routeFromSearch(location.search);
  if (route) history.replaceState(history.state, "", stripQuery(location.href));
  if (route && route !== "signin") report("public");
  if (route === "failed") return showFailed();
  if (route === "pending_review") return showPendingReview();
  if (route === "signup") return startSignup();
  const me = await api("/me");
  report(pageMode(me));
  if (me.ok) return showAccount(me.data.ambassador, route !== null);
  if (route === "signin") return showFailed();
  return undefined;
}
