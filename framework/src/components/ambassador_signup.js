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
};
const GENERIC_ERROR = "Something went wrong on our side. Try again in a few minutes.";

/** Maps an API error code to a plain sentence. Raw codes and stack traces are never shown. */
export function errorText(code) {
  return Object.prototype.hasOwnProperty.call(ERROR_TEXT, code) ? ERROR_TEXT[code] : GENERIC_ERROR;
}

export function apiUrl(path) {
  return `${API_BASE}${path}`;
}

/** Query state on page load: "signup" (ORCID returned, step flow), "signin" (ORCID sign-in), "failed", or null. */
export function routeFromSearch(search) {
  const params = new URLSearchParams(search || "");
  if (params.get("signup") === "orcid") return "signup";
  if (params.get("signin") === "failed") return "failed";
  if (params.get("signin") === "orcid") return "signin";
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

export function yearsText(years) {
  if (!years) return "";
  const {from = null, to = null} = years;
  if (from === null && to === null) return "";
  if (to === null) return `since ${from}`;
  if (from === null) return `until ${to}`;
  return from === to ? `${from}` : `${from} to ${to}`;
}

// ---- validation (pure). Each problem is {field, message}; field is the id of the element to focus. -----------
export function checkInstitutions({ticked, proposals, checklist}) {
  if (eligibleTicked(checklist, ticked).length === 0 && (proposals || []).length === 0) {
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
export function claimsBody({ticked, regions, proposals}) {
  return {
    institutions: [...(ticked || [])],
    regions: [...(regions || [])],
    // Each claims call replaces the earlier proposals, so every call sends the full list.
    proposals: (proposals || []).map((p) => ({
      kind: "institution",
      payload: p.url ? {name: p.name.trim(), url: p.url.trim()} : {name: p.name.trim()},
    })),
  };
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

function freshFlow() {
  return {step: 1, profile: null, ticked: [], regions: [], proposals: [], proposalOpen: false, domains: [], token: "", widgetId: null};
}

const $ = (selector) => body.querySelector(selector);
const checkedValues = (name) => [...body.querySelectorAll(`input[name="${name}"]:checked`)].map((input) => input.value);

function setStatus(text) {
  if (statusEl) statusEl.textContent = text;
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
      `<span>${esc(item.name)}${years ? ` (${esc(years)})` : ""}<small>Eligible for ${esc(regions)}</small></span></label></li>`;
  }).join("");
}

function proposalsHTML() {
  return flow.proposals.map((p, i) => `<li>${esc(p.name)}${p.url ? ` <small>${esc(p.url)}</small>` : ""}
    <button type="button" class="link-btn" data-action="remove-proposal" data-index="${i}" aria-label="Remove the proposal for ${esc(p.name)}">Remove</button></li>`).join("");
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
      `<li><span>${esc(item.name)}</span><small class="hint"> Not yet on a region's list of eligible institutions, so it cannot be claimed here.</small></li>`).join("")}</ul>`
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

async function loadDomains(ticked, checklist) {
  const slugs = new Set();
  for (const item of eligibleTicked(checklist, ticked)) for (const region of item.regions || []) slugs.add(region);
  const files = {};
  await Promise.all([...slugs].map(async (slug) => {
    const response = await fetch(regionFileUrl(slug, "ambassador_institutions.json"), {cache: "no-cache"}).catch(() => null);
    files[slug] = response?.ok ? await response.json().catch(() => null) : null;
  }));
  return allowedDomains(files, ticked);
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
  flow.domains = await loadDomains(flow.ticked, flow.profile.institutions);
  const domains = flow.domains.length
    ? `Use your address at one of these domains: ${esc(flow.domains.join(", "))}.`
    : "The institutions you ticked do not list a domain yet. Email the address in the contribution terms for help.";
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
  show(`<p class="step-n">Email sent</p><h2 tabindex="-1">Check your inbox</h2>
    <p>We sent a confirmation link to your institutional address. It works once and expires in 30 minutes. Open it in this browser to finish signing up.</p>
    <p class="hint">Nothing else is needed on this page.</p>`);
  setStatus("Check your inbox for the confirmation link.");
}

function showMessage(title, text, actions = "") {
  show(`<h2 tabindex="-1">${esc(title)}</h2><p>${esc(text)}</p>${actions ? `<div class="btns">${actions}</div>` : ""}`);
  setStatus(title);
}

const orcidLink = (label) => `<a class="btn solid" href="${apiUrl("/orcid/start")}">${esc(label)}</a>`;
const retryButton = '<button type="button" class="btn" data-action="retry">Try again</button>';

function showFailed() {
  showMessage("We could not sign you in", "Nothing was changed. Try signing in with ORCID again.", orcidLink("Sign in with ORCID"));
}

function showProposalsSent() {
  show(`<h2 tabindex="-1">Your proposals are with moderation</h2>
    <p>Thank you. Moderation reviews each proposal; it does not block anything else. To confirm an email you need at least one eligible institution on your record. You can sign up again when one is listed.</p>
    <p><a class="link" href="./ambassadors">Back to the ambassador page</a></p>`);
  setStatus("Your proposals were sent to moderation.");
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

function showSignedIn(ambassador) {
  const names = (ambassador.regions || []).map((r) => regionLabel(r.region));
  show(`<h2 tabindex="-1">Signed in as ${esc(ambassador.display_name)}</h2>
    <p>${names.length ? `Regions: ${esc(names.join(", "))}.` : "No region is linked yet."}</p>
    <p class="actions"><button type="button" class="link-btn" data-action="signout">Sign out</button></p>`);
  setStatus(`Signed in as ${ambassador.display_name}.`);
}

/** Shows the right screen for a signed-in ambassador: the first-visit profile when it is missing, else the panel. */
function showAccount(ambassador, focus = true) {
  if (ambassador.needs_profile) {
    showFirstVisit();
    if (!focus) body.querySelector("h2")?.blur();
    return;
  }
  if (activeRegions(ambassador).length) {
    panel.hidden = false;
    return mountWorkspace(body, ambassador, {focus, announce: setStatus});
  }
  showSignedIn(ambassador);
  if (!focus) body.querySelector("h2")?.blur();
}

async function startSignup() {
  const response = await api("/signup/profile");
  if (!response.ok) {
    const again = response.error === "not_signed_in" ? orcidLink("Sign up with ORCID") : retryButton;
    return showMessage("We could not start your sign-up", errorText(response.error), again);
  }
  flow = freshFlow();
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
  setBusy(form, true);
  const response = await api("/signup/claims", {method: "POST", body: claimsBody({ticked: flow.ticked, regions: flow.regions, proposals: flow.proposals})});
  setBusy(form, false);
  if (!response.ok) return showErrors([{field: "signup-regions", message: errorText(response.error)}]);
  if (response.data.status === "pending_email") return renderStep(4);
  return showProposalsSent();
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
  if (!response.ok) return showErrors([{field: "signup-email", message: errorText(response.error)}]);
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
    const errors = checkInstitutions({ticked: flow.ticked, proposals: flow.proposals, checklist: flow.profile.institutions});
    if (errors.length) return showErrors(errors);
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
    return renderStep(flow.step - 1);
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
    return showMessage("You have signed out", "Your session has ended on this device.", orcidLink("Sign in with ORCID"));
  }
  return undefined;
}

/** Mounts the sign-up. Call once after the page markup is in the DOM. */
export async function mountSignup(root) {
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
  });
  panel.addEventListener("input", syncSubmit);

  const route = routeFromSearch(location.search);
  if (route) history.replaceState(history.state, "", stripQuery(location.href));
  if (route === "failed") return showFailed();
  if (route === "signup") return startSignup();
  const me = await api("/me");
  if (me.ok) return showAccount(me.data.ambassador, route !== null);
  if (route === "signin") return showFailed();
  return undefined;
}
