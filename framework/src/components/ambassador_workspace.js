// Ambassador workspace (AMB-1 front end slice 2b; docs/AMBASSADORS_SPEC.md sections 4 and "Front end slice 2b").
// ambassador_signup.js mounts it after sign-in (showAccount) inside #amb-signup-body. Stream A reviews classifier
// cases one per screen and saves each answer at once; stream B confirms the region page's placeholders through
// reviewed submissions. Worker calls go through api() from ambassador_signup.js (credentials included); the case
// and region files are same-origin public JSON. Pure helpers are exported for
// tests/framework_ambassador_workspace_runtime.mjs and touch no DOM at import time. Nothing personal is kept in the
// browser: no browser storage of personal data, and none in the URL.
import {escapeHtml, globalDataUrl, regionFileUrl, siteRoot} from "./atlas.js";
import {REGION_NAMES, api, errorText} from "./ambassador_signup.js";
import {REGION_SCHEMA, safeUrl} from "./region_page.js";
import {badgeHTML} from "./ambassador_badge.js";
import {placeRows} from "./world_map.js";
import {placeView} from "./ambassadors.js";
import {mountKnowledge, mySubmissions} from "./ambassador_knowledge.js";
import {mountGroups, mountGroupSuggest} from "./ambassador_groups.js";
import {mountSettings} from "./ambassador_settings.js";
import {mountInvite} from "./ambassador_invite.js";

export const CASES_SCHEMA = "amb-cases-v1";
/** Time estimates from the design notes: 30 seconds per case, 2 minutes per placeholder. */
export const CASE_MINUTES = 0.5;
export const ITEM_MINUTES = 2;
export const ANSWERS = ["agree", "disagree", "unsure"];
export const CONFIRM_KINDS = ["confirm", "correct", "not_relevant"];
export const CASE_KIND_LABELS = {
  all: "All case types",
  institution_in_region: "Institution in the region",
  institution_type: "Institution type",
  local_language_relevance: "Local-language work",
  local_terms: "Local search terms",
};
const ANSWER_LABELS = {agree: "Agree", disagree: "Disagree", unsure: "Unsure"};
const TYPE_LABELS = {
  education: "University or school",
  government: "Government",
  nonprofit: "Non-profit",
  facility: "Research institute or facility",
  company: "Company",
  healthcare: "Healthcare",
  archive: "Archive",
  other: "Other",
};
const WORKSPACE_ERRORS = {
  invalid_case_id: "This case could not be saved. Reload the page and try again.",
  invalid_answer: "Choose Agree, Disagree or Unsure.",
  correct_value_required: "Choose or type the correct value first.",
  correct_value_not_allowed: "A correct value is only for a Disagree answer.",
  not_region_member: "This region is not open to your account at the moment.",
  invalid_region: "This region is not open for tasks yet.",
  invalid_kind: "That kind of change is not known. Reload the page and try again.",
  stream_kind_mismatch: "That kind of change belongs to another task. Reload the page and try again.",
  invalid_payload: "Check the note, name and web address: plain text, no < or > characters, and https web addresses only.",
};
/** Same rule as the Worker's isHttpsUrl: https only, no credentials. */
export function httpsAddress(text) {
  try {
    const url = new URL(text);
    return url.protocol === "https:" && url.username === "" && url.password === "" && url.hostname !== "";
  } catch {
    return false;
  }
}

/** Plain plain-language sentence for a Worker error code; shares the sign-up map for codes it does not know. */
export function workspaceErrorText(code) {
  return Object.prototype.hasOwnProperty.call(WORKSPACE_ERRORS, code) ? WORKSPACE_ERRORS[code] : errorText(code);
}

/** Trimmed text with whitespace collapsed, or null when it is too long or has characters the Worker refuses. */
export function cleanText(value, max) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  if (text.length > max || /[<>\u0000-\u001f\u007f]/.test(text)) return null;
  return text;
}

/** Active regions (slugs) of the signed-in ambassador, in the order the Worker returns them. */
export function activeRegions(ambassador) {
  return (ambassador?.regions || []).filter((r) => r.status === "active").map((r) => r.region);
}

/** "about N minutes" for a number of minutes; "nothing left" for zero. */
export function estimateText(minutes) {
  if (!(minutes > 0)) return "nothing left";
  const n = Math.max(1, Math.ceil(minutes));
  return `about ${n} minute${n === 1 ? "" : "s"}`;
}

export function filterCases(cases, kind) {
  return kind && kind !== "all" ? cases.filter((c) => c.kind === kind) : cases.slice();
}

/** Screens reached from the mailed links: the settings link (`#notifications`) and the reminder's next-task link
 *  (`?region=<slug>&case=<case_id>`). Returns {region, caseId, screen}, each null when absent or malformed. */
export function deepLinkFrom(search, hash) {
  const params = new URLSearchParams(search || "");
  const region = params.get("region");
  const caseId = params.get("case");
  return {
    region: region && /^[a-z0-9_-]{1,40}$/.test(region) ? region : null,
    caseId: caseId && /^amb-[0-9a-f]{12}$/.test(caseId) ? caseId : null,
    screen: hash === "#notifications" ? "settings" : null,
  };
}

/** Counts for a stream: answered cases, total cases, and what is left. `answers` is a Map by case_id. */
export function caseProgress(cases, answers) {
  const answered = cases.filter((c) => answers.has(c.case_id)).length;
  return {answered, total: cases.length, remaining: cases.length - answered};
}

export function progressText({answered, total}) {
  return `${answered} of ${total} answered`;
}

/**
 * Progress across the task streams. Each stream is {done, total, minutes} where minutes is the time one remaining
 * item takes. Returns each stream's counts, share and minutes left, and the region's overall count, share and minutes.
 */
export function progressSummary(streams) {
  const share = (done, total) => (total ? Math.round((done / total) * 100) : 0);
  const rows = (streams || []).map(({done, total, minutes}) => {
    const all = Math.max(0, Number(total) || 0);
    const got = Math.min(Math.max(0, Number(done) || 0), all);
    const remaining = all - got;
    return {done: got, total: all, remaining, percent: share(got, all), minutes: remaining * minutes};
  });
  const done = rows.reduce((sum, r) => sum + r.done, 0);
  const total = rows.reduce((sum, r) => sum + r.total, 0);
  const minutes = rows.reduce((sum, r) => sum + r.minutes, 0);
  return {streams: rows, done, total, remaining: total - done, percent: share(done, total), minutes};
}

/** "Time left: about N minutes", or "Nothing left to do" when no minutes are left. */
export function timeLeftText(minutes) {
  return minutes > 0 ? `Time left: ${estimateText(minutes)}` : "Nothing left to do";
}

/** Index of the first case without an answer, or -1 when every case is answered. */
export function firstUnanswered(cases, answers) {
  return cases.findIndex((c) => !answers.has(c.case_id));
}

/** The choices for a fixed-value case type, or null when the correct value is typed. */
export function caseChoices(item) {
  if (item.kind === "institution_in_region") {
    return [
      {value: "in region", label: "In the region"},
      {value: "not in region", label: "Not in the region"},
    ];
  }
  if (item.kind === "institution_type") {
    return (item.options || [])
      .filter((value) => value !== "unsure")
      .map((value) => ({value, label: TYPE_LABELS[value] || value}));
  }
  return null;
}

/** The terms the search admitted a case on: quoted place names in affiliation signals, or the local term itself. */
export function admittingTerms(item) {
  const evidence = item.evidence || {};
  if (item.kind === "local_terms") return evidence.term ? [String(evidence.term)] : [];
  const terms = [];
  for (const signal of Array.isArray(evidence.signals) ? evidence.signals : []) {
    const match = /^affiliation mentions "(.+)"$/.exec(String(signal));
    if (match) terms.push(match[1]);
  }
  return [...new Set(terms)];
}

const escapeRegExp = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/**
 * Escaped HTML with each admitting term wrapped in <mark>. Text is escaped first, segment by segment, so a term
 * or a case field can never inject markup. Matching ignores case; longer terms win over shorter ones.
 */
export function highlightHtml(text, terms) {
  const plain = String(text ?? "");
  const clean = [...new Set((terms || []).map((t) => String(t).trim()).filter((t) => t.length > 0))].sort(
    (a, b) => b.length - a.length,
  );
  if (clean.length === 0) return escapeHtml(plain);
  const parts = plain.split(new RegExp(`(${clean.map(escapeRegExp).join("|")})`, "giu"));
  // split() with one capture group puts the matches at the odd indexes.
  return parts.map((part, i) => (i % 2 === 1 ? `<mark>${escapeHtml(part)}</mark>` : escapeHtml(part))).join("");
}

/** The POST /cases/answer body, or null when the answer is not valid. Disagree needs a correct value. */
export function answerBody({region, caseId, answer, correctValue}) {
  if (!ANSWERS.includes(answer) || typeof caseId !== "string" || !caseId) return null;
  if (answer !== "disagree") return {region, case_id: caseId, answer};
  const value = cleanText(correctValue, 200);
  if (!value) return null;
  return {region, case_id: caseId, answer, correct_value: value};
}

/** The POST /submissions body for stream B, or null when the fields do not fit the kind. */
export function submissionBody({region, kind, itemId, name, url, note}) {
  if (!CONFIRM_KINDS.includes(kind) || typeof itemId !== "string" || !itemId) return null;
  const cleanNote = cleanText(note, 1000);
  const payload = {item_id: itemId};
  if (cleanNote === null) return null;
  if (kind === "correct") {
    const cleanName = cleanText(name, 200);
    const cleanUrl = cleanText(url, 500);
    if (cleanName === null || cleanUrl === null) return null;
    if (cleanUrl && !httpsAddress(cleanUrl)) return null;
    if (!cleanName && !cleanUrl && !cleanNote) return null;
    if (cleanName) payload.name = cleanName;
    if (cleanUrl) payload.url = cleanUrl;
  }
  if (cleanNote) payload.note = cleanNote;
  return {region, stream: "confirm", kind, payload};
}

/** Items still to confirm in region.json (to_confirm or draft), flattened in page order, each with its item_id. */
export function itemsToConfirm(sections) {
  return (sections || []).flatMap((section) =>
    (section.items || [])
      .filter((item) => item.item_id && (item.status === "to_confirm" || item.status === "draft"))
      .map((item) => ({
        item_id: item.item_id,
        section_id: section.id,
        section_title: section.title,
        name: item.name,
        url: item.url || "",
        status: item.status,
        note: item.note || "",
      })),
  );
}

/** The newest confirm submission per item_id for one region (the Worker lists newest first). */
export function latestSubmissionByItem(submissions, region) {
  const byItem = new Map();
  for (const row of submissions || []) {
    const itemId = row?.payload?.item_id;
    if (row.region !== region || row.stream !== "confirm" || typeof itemId !== "string") continue;
    if (!byItem.has(itemId)) byItem.set(itemId, row);
  }
  return byItem;
}

/** The plain review label for a submission status. */
export function reviewText(status) {
  if (status === "pending") return "Sent for review";
  if (status === "approved") return "Accepted";
  if (status === "rejected") return "Not accepted";
  return "";
}

/** The text state of a stream B choice, from the person's latest submission for the item ("" when none). */
export function choiceText(row) {
  const said = {confirm: "Confirmed.", correct: "Correction sent.", not_relevant: "Marked not relevant."}[row?.kind];
  if (!said) return "";
  if (row.status === "pending") return `${said} Waiting for review.`;
  if (row.status === "approved") return `${said} Accepted.`;
  if (row.status === "rejected") return `${said} Not accepted.`;
  return said;
}

// ---- DOM ----------------------------------------------------------------------------------------------------
const esc = (value) => escapeHtml(value);
const regionName = (slug) => REGION_NAMES[slug] || slug;
// A check mark shown inside the button the person chose (colour is never the only cue).
const CHECK = '<svg class="ws-check" width="12" height="10" viewBox="0 0 12 10" aria-hidden="true" focusable="false"><path d="M1 5l3.2 3.2L11 1.5" fill="none" stroke="currentColor" stroke-width="2"/></svg>';
const chosenMark = (on) => (on ? CHECK : "");

let state = null;
let wrap = null;

// The map data for the region header: the shared world outline, the place index and the region list. Loaded once.
let geoPromise = null;
export function loadGeo() {
  if (!geoPromise) {
    const fetchJson = (url) => fetch(url, {cache: "no-cache"}).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    geoPromise = Promise.all([
      fetchJson(new URL("assets/world/world.json", siteRoot())),
      fetchJson(globalDataUrl("places.json")),
      fetchJson(globalDataUrl("ambassador_regions.json")),
    ]).then(([world, places, index]) => ({world, rows: placeRows(places), regions: index?.regions || []}));
  }
  return geoPromise;
}

/** The place a region is zoomed to: its subdivision (California) or its country. Null when none matches. */
export function regionPlace(region, rows) {
  const iso = (region.country_codes || [])[0];
  if (!iso) return null;
  if ((region.subdivision_names || []).length) {
    const sub = rows.find((r) => r.kind === "admin1" && r.iso === iso && region.subdivision_names.includes(r.name));
    if (sub) return sub;
  }
  return rows.find((r) => r.kind === "country" && r.iso === iso) || null;
}

/** The shared world_map.js frame [x, y, w, h]; a zoomed view keeps its aspect ratio, so the map box can reserve it. */
export function mapFrame(world) {
  const [top, bottom] = world.crop;
  return [0, top, world.w, bottom - top];
}

/** The region's map: the world outline with the region highlighted and the view zoomed to it (shared world_map.js frame). */
export function regionMapHTML(geo, slug) {
  const region = geo.regions.find((r) => r.slug === slug);
  const world = geo.world;
  if (!region || !world) return "";
  const frame = mapFrame(world);
  const place = regionPlace(region, geo.rows);
  const view = place ? placeView(place.geom, place.iso, frame[2] / frame[3], frame, 120) : frame;
  // A subdivided region (California) highlights its outline only; its country is drawn plain.
  const subdivided = (region.subdivision_names || []).length > 0;
  const onCountries = new Set(subdivided ? [] : region.country_codes || []);
  const paths = world.countries
    .map((c) => `<path class="c${onCountries.has(c.iso_a2) ? " open" : ""}" d="${c.d}"/>`)
    .join("");
  const outline = subdivided && world.ca ? `<path class="ca open" d="${world.ca}"/>` : "";
  return `<svg class="amb-map" viewBox="${view.map((n) => n.toFixed(1)).join(" ")}" preserveAspectRatio="xMidYMid meet" focusable="false" aria-hidden="true"><path class="sea" d="${world.sphere}"/>${paths}${outline}</svg>`;
}

/** Mounts the workspace (the signed-in dashboard) into `root`, the sign-up body, for a signed-in ambassador. */
export function mountWorkspace(root, ambassador, {focus = true, announce = null} = {}) {
  const regions = activeRegions(ambassador);
  const deep = deepLinkFrom(location.search, location.hash);
  if (deep.region || deep.caseId || deep.screen) {
    // The links carry no personal data; drop them from the address bar once read.
    const url = new URL(location.href);
    url.search = "";
    url.hash = "";
    history.replaceState(history.state, "", url.href);
  }
  state = {
    root,
    ambassador,
    pendingCase: deep.caseId,
    name: ambassador.display_name || "",
    regions,
    region: deep.region && regions.includes(deep.region) ? deep.region : regions[0] || "",
    screen: deep.screen || "home",
    loading: regions.length > 0,
    loadError: "",
    busy: false,
    cases: [],
    answers: new Map(),
    filter: "all",
    index: 0,
    disagreeOpen: null,
    note: null,
    sections: null,
    items: [],
    editOpen: null,
    submissions: [],
    geo: null,
  };
  root.innerHTML = '<div class="ws" data-ws><p class="sr" role="status" aria-live="polite" data-ws-live></p><header class="ws-top" data-ws-head></header><div data-ws-main></div></div>';
  wrap = root.querySelector("[data-ws]");
  wrap.addEventListener("click", onClick);
  wrap.addEventListener("change", onChange);
  if (announce) announce(`Signed in as ${ambassador.display_name}.`);
  render({focus: focus ? "title" : null});
  if (!regions.length) return undefined;
  // Focus stays on the dashboard heading; the region data loads behind it.
  return loadRegion(state.region, false);
}

const mainEl = () => wrap.querySelector("[data-ws-main]");
const headEl = () => wrap.querySelector("[data-ws-head]");
function say(text) {
  const live = wrap.querySelector("[data-ws-live]");
  if (live) live.textContent = text;
}

// focus: "title" moves focus to the dashboard heading (on mount); "heading" to the heading of the current screen.
function render({focus = null} = {}) {
  const host = mainEl();
  if (!host) return;
  headEl().innerHTML = headerHTML();
  wrap.classList.toggle("is-dash", state.screen === "home" && state.regions.length > 0);
  if (isModuleScreen(state.screen) && (!state.loading || state.screen !== "C")) mountModule(host);
  else if (state.loading) host.innerHTML = loadingHTML();
  else if (state.screen === "A") host.innerHTML = streamAHTML();
  else if (state.screen === "B") host.innerHTML = streamBHTML();
  else host.innerHTML = homeHTML();
  if (focus === "title") headEl().querySelector("h1")?.focus();
  else if (focus === "heading") host.querySelector("h2")?.focus();
}

// Screens drawn by their own modules. Each renders its back link and h2 synchronously and keeps its own state.
const MODULE_SCREENS = new Set(["C", "D", "settings", "invite"]);
// Stream E (suggest a missing group) is drawn by its own module too.
const isModuleScreen = (screen) => MODULE_SCREENS.has(screen) || screen === "E";
function mountModule(main) {
  // A fresh element per mount, so a module's listeners leave with its screen.
  main.innerHTML = "<div data-ws-module></div>";
  const host = main.firstElementChild;
  const ctx = {api, errorText: workspaceErrorText, say};
  if (state.screen === "settings") return mountSettings(host, ctx);
  if (state.screen === "invite") return mountInvite(host, {...ctx, ambassador: state.ambassador});
  if (state.screen === "D") return mountGroups(host, {
    ...ctx,
    region: state.region,
    regionName: regionName(state.region),
    submissions: state.submissions,
    onSubmitted: (row) => state.submissions.unshift(row),
  });
  if (state.screen === "E") return mountGroupSuggest(host, {
    ...ctx,
    region: state.region,
    regionName: regionName(state.region),
    submissions: state.submissions,
    onSubmitted: (row) => state.submissions.unshift(row),
  });
  return mountKnowledge(host, {
    ...ctx,
    region: state.region,
    regionName: regionName(state.region),
    submissions: state.submissions,
    onSubmitted: (row) => state.submissions.unshift(row),
  });
}

const crumb = '<p class="ws-crumb"><button type="button" class="link-btn" data-ws-action="home">Back to your tasks</button></p>';

function loadingHTML() {
  return `<h2 tabindex="-1">Your tasks</h2><p class="status">Loading your tasks for ${esc(regionName(state.region))}.</p>`;
}

/** The dashboard header: greeting with the display name, the region's badge, the region switcher and sign out. */
function headerHTML() {
  const switcher =
    state.regions.length > 1
      ? `<div class="ws-chips" role="group" aria-label="Choose a region">${state.regions
          .map(
            (slug) =>
              `<button type="button" class="ws-chip" data-ws-action="region" data-region="${esc(slug)}" aria-pressed="${slug === state.region}">${esc(regionName(slug))}</button>`,
          )
          .join("")}</div>`
      : "";
  const badge = state.region ? badgeHTML(regionName(state.region)) : "";
  return `<div class="ws-hello"><h1 tabindex="-1">Welcome back${state.name ? `, ${esc(state.name)}` : ""}</h1>${badge}</div>
    <div class="ws-top-end">${switcher}<button type="button" class="link-btn" data-action="signout">Sign out</button></div>`;
}

/** One task stream as a card: name, progress, time left, and Start, Continue or Review. */
function streamCard(stream, name, {done, total, time, label, empty = ""}) {
  const action = total > 0 && done >= total ? "Review" : done > 0 ? "Continue" : "Start";
  const meter = total
    ? `<progress value="${done}" max="${total}" aria-label="${esc(name)}: ${done} of ${total} ${esc(label)}"></progress>`
    : "";
  return `<li class="ws-card"><div class="ws-card-main">
      <h4 class="ws-card-name">${esc(name)}</h4>
      <p class="ws-card-status">${total ? `${done} of ${total} ${esc(label)} · ${esc(time)}` : esc(empty || "Nothing to show yet")}</p>
      ${meter}
    </div>
    ${total ? `<button type="button" class="btn solid" data-ws-action="open" data-stream="${stream}">${action}<span class="sr"> ${esc(name)}</span></button>` : ""}</li>`;
}

/** A card with no progress bar: name, one status line and an action button. */
function plainCard(stream, name, status, action) {
  return `<li class="ws-card"><div class="ws-card-main"><h4 class="ws-card-name">${esc(name)}</h4><p class="ws-card-status">${esc(status)}</p></div>
    <button type="button" class="btn${stream === "C" ? " solid" : ""}" data-ws-action="open" data-stream="${stream}">${esc(action)}<span class="sr"> ${esc(name)}</span></button></li>`;
}

/** The local-knowledge card's status: what was sent for this region and how much is approved. */
export function knowledgeStatus(rows) {
  if (!rows.length) return "Groups, policies, datasets and more · about 5 minutes each";
  const approved = rows.filter((row) => row.status === "approved").length;
  return `${rows.length} sent for review · ${approved} approved`;
}

function homeHTML() {
  if (!state.regions.length) {
    return `<section class="ws-empty" aria-labelledby="ws-empty-h"><h2 id="ws-empty-h">No region is open to your account yet</h2>
      <p class="hint">When a region is linked to your author record, its tasks appear here. To ask for a region, write to the Atlas team at the address in the page footer.</p></section>`;
  }
  const progress = caseProgress(state.cases, state.answers);
  const latest = latestSubmissionByItem(state.submissions, state.region);
  const sentCount = state.items.filter((item) => latest.has(item.item_id)).length;
  const summary = progressSummary([
    {done: progress.answered, total: progress.total, minutes: CASE_MINUTES},
    {done: sentCount, total: state.items.length, minutes: ITEM_MINUTES},
  ]);
  const [caseRow, itemRow] = summary.streams;
  const errors = state.loadError ? `<p class="ws-error">${esc(state.loadError)}</p>` : "";
  const figure = state.geo ? mapFigureHTML(state.geo, state.region) : "";
  // Tasks come first (the next step on a phone); on wide screens the right column holds the map and the progress.
  return `<div class="ws-dash">
    <section class="ws-tasks" aria-labelledby="ws-tasks-h">
      <h2 id="ws-tasks-h">Your tasks</h2>
      ${errors}
      <ul class="ws-cards">
        ${streamCard("A", "Check classifier cases", {
          done: caseRow.done,
          total: caseRow.total,
          time: caseRow.remaining > 0 ? estimateText(caseRow.minutes) : "all answered",
          label: "cases answered",
          empty: "No cases yet",
        })}
        ${streamCard("B", "Confirm the region page", {
          done: itemRow.done,
          total: itemRow.total,
          time: itemRow.remaining > 0 ? estimateText(itemRow.minutes) : "all sent",
          label: "items sent for review",
          empty: "Nothing to confirm",
        })}
        ${plainCard("C", "Add local knowledge", knowledgeStatus(mySubmissions(state.submissions, state.region)), "Add an item")}
        ${plainCard("D", "Tag local groups", "Check assigned organisations' public pages and tag them", "Open tasks")}
        ${plainCard("E", "Suggest a missing group", "Add an organisation that is missing from the list", "Suggest a group")}
      </ul>
      <h3 class="ws-more-h">More</h3>
      <ul class="ws-cards">
        ${plainCard("invite", "Invite your co-authors", "A ready-made message with your personal invitation link", "Invite")}
        ${plainCard("settings", "Notification settings", "Reminders and news we send you", "Open settings")}
      </ul>
    </section>
    <div class="ws-side">
      <section class="ws-regionhead" aria-labelledby="ws-region-h">
        <h2 id="ws-region-h" tabindex="-1">${esc(regionName(state.region))}</h2>
        <p class="hint">Your tasks for this region. Each answer is saved as soon as you give it.</p>
        ${figure}
      </section>
      <section class="ws-progress" aria-labelledby="ws-progress-h">
        <h3 id="ws-progress-h">Progress</h3>
        <p class="ws-progress-all">${summary.done} of ${summary.total} done for this region (${summary.percent}%)</p>
        ${summary.total ? `<progress value="${summary.done}" max="${summary.total}" aria-label="Region progress: ${summary.done} of ${summary.total} done"></progress>` : ""}
        <p class="ws-progress-time">${esc(timeLeftText(summary.minutes))}</p>
        <ul class="ws-progress-streams">
          ${progressStreamHTML("Check classifier cases", caseRow, "cases answered", "No cases yet")}
          ${progressStreamHTML("Confirm the region page", itemRow, "items sent for review", "Nothing to confirm")}
        </ul>
      </section>
    </div>
  </div>`;
}

/** One stream's line in the progress summary: name, count and share as text, with a bar. */
function progressStreamHTML(name, row, label, empty = "Nothing to show yet") {
  // Same empty wording as the matching task card.
  const text = row.total ? `${row.done} of ${row.total} ${label} (${row.percent}%)` : empty;
  const bar = row.total
    ? `<progress value="${row.done}" max="${row.total}" aria-label="${esc(name)}: ${row.done} of ${row.total} ${esc(label)}"></progress>`
    : "";
  return `<li class="ws-progress-stream"><p class="ws-progress-line"><span>${esc(name)}</span><span>${esc(text)}</span></p>${bar}</li>`;
}

/** The map box at the frame's aspect ratio, so the map takes its height before the SVG is drawn. */
function mapFigureHTML(geo, slug) {
  const world = geo.world;
  const svg = regionMapHTML(geo, slug);
  if (!svg || !world) return "";
  const [, , w, h] = mapFrame(world);
  return `<figure class="ws-map" style="aspect-ratio: ${w} / ${h}">${svg}<figcaption class="sr">Map of ${esc(regionName(slug))}, highlighted.</figcaption></figure>`;
}

function evidenceRows(item) {
  const e = item.evidence || {};
  const terms = admittingTerms(item);
  const rows = [];
  if (e.institution_name) rows.push(["Institution", highlightHtml(e.institution_name, terms)]);
  if (e.title) rows.push(["Title", highlightHtml(e.title, terms)]);
  if (e.term) rows.push(["Term", highlightHtml(e.term, terms)]);
  if (e.note) rows.push(["Note", highlightHtml(e.note, terms)]);
  if (e.language) rows.push(["Language", esc(e.language)]);
  if (e.works !== undefined) rows.push(["Works in the region", esc(e.works)]);
  if (Array.isArray(e.affiliation_examples) && e.affiliation_examples.length) {
    rows.push(["Affiliation as written", e.affiliation_examples.map((x) => highlightHtml(x, terms)).join("; ")]);
  }
  if (Array.isArray(e.signals) && e.signals.length) {
    rows.push(["Why it was flagged", e.signals.map((x) => highlightHtml(x, terms)).join("; ")]);
  }
  return rows;
}

const machineLabel = (item) => TYPE_LABELS[item.current_value] || item.current_value;

function streamAHTML() {
  const progress = caseProgress(state.cases, state.answers);
  const shown = filterCases(state.cases, state.filter);
  const filter = `<div class="field"><label for="ws-filter">Case type</label><select id="ws-filter" data-ws-filter>${Object.entries(
    CASE_KIND_LABELS,
  )
    .filter(([kind]) => kind === "all" || state.cases.some((c) => c.kind === kind))
    .map(([kind, label]) => `<option value="${esc(kind)}"${kind === state.filter ? " selected" : ""}>${esc(label)}</option>`)
    .join("")}</select></div>`;
  const top = `${crumb}<h2 tabindex="-1" class="ws-stream-title">Check classifier cases</h2>
    <div class="ws-progress"><p>${esc(progressText(progress))}. ${esc(
      progress.remaining > 0 ? `${estimateText(progress.remaining * CASE_MINUTES)} left.` : "All answered.",
    )}</p><progress max="${progress.total || 1}" value="${progress.answered}" aria-label="Cases answered">${progress.answered}</progress></div>`;
  if (state.loadError && !state.cases.length) return `${top}<p class="ws-error">${esc(state.loadError)}</p>`;
  if (!state.cases.length) return `${top}<p class="hint">There are no cases for this region yet.</p>`;
  if (!shown.length) return `${top}${filter}<p class="hint">No cases of this type.</p>`;
  state.index = Math.min(Math.max(0, state.index), shown.length - 1);
  const item = shown[state.index];
  const saved = state.answers.get(item.case_id) || null;
  const choices = caseChoices(item);
  const editing = state.disagreeOpen === item.case_id || saved?.answer === "disagree";
  const valueField = choices
    ? `<div class="field"><label for="ws-correct-value">Correct value</label><select id="ws-correct-value"><option value="">Choose a value</option>${choices
        .map((c) => `<option value="${esc(c.value)}"${saved?.correct_value === c.value ? " selected" : ""}>${esc(c.label)}</option>`)
        .join("")}</select></div>`
    : `<div class="field"><label for="ws-correct-value">Correct value</label><input id="ws-correct-value" type="text" maxlength="200" value="${esc(
        saved?.correct_value || "",
      )}" aria-describedby="ws-correct-hint"><p class="hint" id="ws-correct-hint">Plain text, up to 200 characters.</p></div>`;
  const buttons = ANSWERS.map(
    (answer) =>
      `<button type="button" class="ws-answer" data-ws-action="answer" data-answer="${answer}" aria-pressed="${saved?.answer === answer}">${chosenMark(saved?.answer === answer)}${ANSWER_LABELS[answer]}</button>`,
  ).join("");
  const rows = evidenceRows(item)
    .map(([label, html]) => `<div><dt>${esc(label)}</dt><dd>${html}</dd></div>`)
    .join("");
  let yours = "You have not answered this case yet.";
  if (saved) {
    const value = saved.answer === "disagree" && saved.correct_value ? ` The correct value is ${esc(TYPE_LABELS[saved.correct_value] || saved.correct_value)}.` : "";
    yours = `Your answer: ${ANSWER_LABELS[saved.answer]}.${value}${saved.consensus ? " Two ambassadors agree on this case." : ""}`;
  }
  const note = state.note && state.note.caseId === item.case_id ? `<p class="ws-saved">${esc(state.note.text)}</p>` : "";
  return `${top}${filter}
    <section class="ws-case" aria-label="Case ${state.index + 1} of ${shown.length}">
      <p class="ws-count">Case ${state.index + 1} of ${shown.length}</p>
      <h2 tabindex="-1">${esc(item.question)}</h2>
      <dl class="ws-evidence">${rows}</dl>
      <p class="ws-machine">The classifier says: <strong>${esc(machineLabel(item))}</strong></p>
      <div class="ws-answers" role="group" aria-label="Your answer">${buttons}</div>
      ${editing ? `<div class="ws-correct">${valueField}<button type="button" class="btn solid" data-ws-action="save-disagree">Save the correct value</button></div>` : ""}
      ${note}
      <p class="ws-yours">${yours}</p>
      <nav class="ws-nav" aria-label="Move between cases">
        <button type="button" class="btn" data-ws-action="prev"${state.index === 0 ? " disabled" : ""}>Previous case</button>
        <button type="button" class="btn" data-ws-action="next"${state.index >= shown.length - 1 ? " disabled" : ""}>Next case</button>
      </nav>
    </section>`;
}

function streamBHTML() {
  if (!state.sections) {
    return `${crumb}<h2 tabindex="-1">Confirm the region page</h2><p class="ws-error">The region page could not be read just now. Try again in a few minutes.</p>`;
  }
  const latest = latestSubmissionByItem(state.submissions, state.region);
  const sectionsHTML = state.sections
    .map((section) => {
      const rows = state.items
        .map((item, index) => ({item, index}))
        .filter(({item}) => item.section_id === section.id)
        .map(({item, index}) => {
          const chosen = latest.get(item.item_id);
          const state = choiceText(chosen);
          const pressed = (kind) => `aria-pressed="${chosen?.kind === kind}"`;
          const link = safeUrl(item.url);
          const name = link ? `<a class="link" href="${esc(link)}" rel="noopener">${esc(item.name)}</a>` : esc(item.name);
          const open = state.editOpen === index;
          return `<li class="ws-item" data-item-row="${index}">
            <p class="ws-item-name">${name}</p>
            <p class="hint">${item.status === "draft" ? "Draft" : "To be confirmed"}</p>
            ${state ? `<p class="ws-state">${esc(state)}</p>` : ""}
            ${item.note ? `<p class="hint">${esc(item.note)}</p>` : ""}
            <div class="ws-item-actions">
              <button type="button" class="btn" data-ws-action="item-confirm" data-index="${index}" ${pressed("confirm")}>${chosenMark(chosen?.kind === "confirm")}Confirm</button>
              <button type="button" class="btn" data-ws-action="item-not-relevant" data-index="${index}" ${pressed("not_relevant")}>${chosenMark(chosen?.kind === "not_relevant")}Not relevant</button>
              <button type="button" class="btn" data-ws-action="item-edit" data-index="${index}" aria-expanded="${open}" aria-controls="ws-edit-${index}" ${pressed("correct")}>${chosenMark(chosen?.kind === "correct")}Correct or add a note</button>
            </div>
            <div class="ws-edit" id="ws-edit-${index}"${open ? "" : " hidden"}>
              <div class="field"><label for="ws-name-${index}">New name</label><input id="ws-name-${index}" type="text" maxlength="200" aria-describedby="ws-name-hint-${index}"><p class="hint" id="ws-name-hint-${index}">Leave blank to keep: ${esc(item.name)}</p></div>
              <div class="field"><label for="ws-url-${index}">New web address (https)</label><input id="ws-url-${index}" type="url" maxlength="500"></div>
              <div class="field"><label for="ws-note-${index}">Note (optional)</label><textarea id="ws-note-${index}" rows="3" maxlength="1000"></textarea></div>
              <div class="ws-item-actions"><button type="button" class="btn solid" data-ws-action="item-correct" data-index="${index}">Send the correction</button></div>
            </div>
          </li>`;
        })
        .join("");
      return rows ? `<section class="ws-section"><h3>${esc(section.title)}</h3><ul class="ws-items">${rows}</ul></section>` : "";
    })
    .join("");
  const count = state.items.length
    ? `${state.items.length} to confirm, ${estimateText(state.items.length * ITEM_MINUTES)}.`
    : "Nothing left to confirm on this page.";
  return `${crumb}<h2 tabindex="-1">Confirm the region page</h2>
    <p class="hint">${esc(count)} Confirm what is right, correct a name or web address, or mark an item not relevant. Each answer is sent for review before it changes the public page.</p>
    ${sectionsHTML}`;
}

// ---- data ---------------------------------------------------------------------------------------------------
async function readJson(url) {
  try {
    const response = await fetch(url, {cache: "no-cache"});
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

async function loadRegion(slug, focus) {
  const current = state;
  const [cases, regionFile, answers, mine, geo] = await Promise.all([
    readJson(regionFileUrl(slug, "ambassador_cases.json")),
    readJson(regionFileUrl(slug, "region.json")),
    api(`/cases/answers?region=${encodeURIComponent(slug)}`),
    api("/submissions/mine"),
    loadGeo(),
  ]);
  if (current !== state) return undefined;
  state.geo = geo;
  const errors = [];
  const caseList = cases && cases.schema === CASES_SCHEMA && Array.isArray(cases.cases) ? cases.cases : null;
  if (!caseList) errors.push("The cases for this region could not be read just now. Try again in a few minutes.");
  state.cases = caseList || [];
  if (answers.ok) {
    state.answers = new Map((answers.data.answers || []).map((a) => [a.case_id, a]));
  } else {
    state.answers = new Map();
    errors.push(`Your earlier answers could not be loaded (${workspaceErrorText(answers.error)}), so the progress may be wrong.`);
  }
  state.sections = regionFile && regionFile.schema_version === REGION_SCHEMA && Array.isArray(regionFile.sections) ? regionFile.sections : null;
  state.items = itemsToConfirm(state.sections || []);
  state.submissions = mine.ok && Array.isArray(mine.data.submissions) ? mine.data.submissions : [];
  state.loadError = errors.join(" ");
  state.loading = false;
  state.index = Math.max(0, firstUnanswered(filterCases(state.cases, state.filter), state.answers));
  if (state.pendingCase) {
    const at = state.cases.findIndex((item) => item.case_id === state.pendingCase);
    state.pendingCase = null;
    if (at >= 0) {
      Object.assign(state, {screen: "A", filter: "all", index: at});
      focus = true;
    }
  }
  // Settings and invitations do not use the region data; re-drawing them would reset what the person is doing.
  if (state.screen === "settings" || state.screen === "invite") return undefined;
  render({focus: focus ? "heading" : null});
  return undefined;
}

// ---- actions ------------------------------------------------------------------------------------------------
async function guarded(task) {
  if (state.busy) return;
  const current = state;
  state.busy = true;
  try {
    await task(current);
  } finally {
    if (current === state) state.busy = false;
  }
}

function currentCase() {
  return filterCases(state.cases, state.filter)[state.index] || null;
}

async function postAnswer(body, focus) {
  await guarded(async (current) => {
    const response = await api("/cases/answer", {method: "POST", body});
    if (current !== state) return;
    if (!response.ok) {
      say(workspaceErrorText(response.error));
      return;
    }
    state.answers.set(body.case_id, {
      case_id: body.case_id,
      answer: body.answer,
      correct_value: body.correct_value ?? null,
      consensus: response.data.consensus ?? null,
    });
    state.disagreeOpen = null;
    state.note = {caseId: body.case_id, text: "Saved."};
    say("Saved.");
    render({focus});
  });
}

async function sendItem(index, kind) {
  const item = state.items[index];
  if (!item) return;
  const body = submissionBody({
    region: state.region,
    kind,
    itemId: item.item_id,
    name: wrap.querySelector(`#ws-name-${index}`)?.value || "",
    url: wrap.querySelector(`#ws-url-${index}`)?.value || "",
    note: wrap.querySelector(`#ws-note-${index}`)?.value || "",
  });
  if (!body) {
    say("Check the note, name and web address: plain text, no < or > characters, and https web addresses only.");
    return;
  }
  await guarded(async (current) => {
    const response = await api("/submissions", {method: "POST", body});
    if (current !== state) return;
    if (!response.ok) {
      say(workspaceErrorText(response.error));
      return;
    }
    state.submissions.unshift({
      id: response.data.id,
      region: state.region,
      stream: "confirm",
      kind,
      payload: body.payload,
      status: "pending",
      created_at: Date.now(),
      decided_at: null,
      decision_note: null,
    });
    state.editOpen = null;
    say("Sent for review.");
    render({focus: `[data-ws-action="item-confirm"][data-index="${index}"]`});
  });
}

function onClick(event) {
  const control = event.target.closest("[data-ws-action]");
  if (!control || !wrap.contains(control)) return;
  const action = control.dataset.wsAction;
  if (action === "region") return chooseRegion(control.dataset.region);
  if (action === "open") {
    state.screen = control.dataset.stream;
    state.disagreeOpen = null;
    if (state.screen === "A") {
      state.index = Math.max(0, firstUnanswered(filterCases(state.cases, state.filter), state.answers));
    }
    state.note = null;
    return render({focus: "heading"});
  }
  if (action === "home") {
    state.screen = "home";
    state.editOpen = null;
    return render({focus: "heading"});
  }
  if (action === "answer") return answerFromButton(control.dataset.answer);
  if (action === "save-disagree") return saveDisagree();
  if (action === "prev" || action === "next") {
    state.index += action === "next" ? 1 : -1;
    state.disagreeOpen = null;
    state.note = null;
    return render({focus: "heading"});
  }
  if (action === "item-confirm") return sendItem(Number(control.dataset.index), "confirm");
  if (action === "item-not-relevant") return sendItem(Number(control.dataset.index), "not_relevant");
  if (action === "item-correct") return sendItem(Number(control.dataset.index), "correct");
  if (action === "item-edit") {
    const index = Number(control.dataset.index);
    state.editOpen = state.editOpen === index ? null : index;
    render({focus: `[data-ws-action="item-edit"][data-index="${index}"]`});
    if (state.editOpen === index) wrap.querySelector(`#ws-name-${index}`)?.focus();
    return undefined;
  }
  return undefined;
}

function onChange(event) {
  if (!event.target.matches("[data-ws-filter]")) return;
  state.filter = event.target.value;
  state.disagreeOpen = null;
  state.note = null;
  state.index = Math.max(0, firstUnanswered(filterCases(state.cases, state.filter), state.answers));
  render({focus: "#ws-filter"});
}

function answerFromButton(answer) {
  const item = currentCase();
  if (!item) return undefined;
  if (answer === "disagree") {
    state.disagreeOpen = item.case_id;
    return render({focus: "#ws-correct-value"});
  }
  state.disagreeOpen = null;
  const body = answerBody({region: state.region, caseId: item.case_id, answer});
  return postAnswer(body, `[data-ws-action="answer"][data-answer="${answer}"]`);
}

function saveDisagree() {
  const item = currentCase();
  if (!item) return undefined;
  const value = wrap.querySelector("#ws-correct-value")?.value || "";
  const body = answerBody({region: state.region, caseId: item.case_id, answer: "disagree", correctValue: value});
  if (!body) {
    say(value ? "Remove any < or > characters from the correct value and try again." : workspaceErrorText("correct_value_required"));
    return undefined;
  }
  return postAnswer(body, '[data-ws-action="answer"][data-answer="disagree"]');
}

function chooseRegion(slug) {
  if (!slug || slug === state.region || !state.regions.includes(slug)) return;
  Object.assign(state, {
    region: slug,
    screen: "home",
    loading: true,
    loadError: "",
    cases: [],
    answers: new Map(),
    index: 0,
    disagreeOpen: null,
    note: null,
    sections: null,
    items: [],
    editOpen: null,
  });
  render({focus: "heading"});
  loadRegion(slug, true);
}
