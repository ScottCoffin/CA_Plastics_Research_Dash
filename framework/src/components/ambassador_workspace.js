// Ambassador workspace (AMB-1 front end slice 2b; docs/AMBASSADORS_SPEC.md sections 4 and "Front end slice 2b").
// ambassador_signup.js mounts it after sign-in (showAccount) inside #amb-signup-body. Stream A reviews classifier
// cases one per screen and saves each answer at once; stream B confirms the region page's placeholders through
// reviewed submissions. Worker calls go through api() from ambassador_signup.js (credentials included); the case
// and region files are same-origin public JSON. Pure helpers are exported for
// tests/framework_ambassador_workspace_runtime.mjs and touch no DOM at import time. Nothing personal is kept in the
// browser: no browser storage of personal data, and none in the URL.
import {escapeHtml, regionFileUrl} from "./atlas.js";
import {REGION_NAMES, api, errorText} from "./ambassador_signup.js";
import {REGION_SCHEMA, safeUrl} from "./region_page.js";

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

/** Counts for a stream: answered cases, total cases, and what is left. `answers` is a Map by case_id. */
export function caseProgress(cases, answers) {
  const answered = cases.filter((c) => answers.has(c.case_id)).length;
  return {answered, total: cases.length, remaining: cases.length - answered};
}

export function progressText({answered, total}) {
  return `${answered} of ${total} answered`;
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

// ---- DOM ----------------------------------------------------------------------------------------------------
const esc = (value) => escapeHtml(value);
const regionName = (slug) => REGION_NAMES[slug] || slug;

let state = null;
let wrap = null;

/** Mounts the workspace into `root` (the sign-up body) for a signed-in ambassador with active regions. */
export function mountWorkspace(root, ambassador, {focus = true, announce = null} = {}) {
  const regions = activeRegions(ambassador);
  state = {
    root,
    regions,
    region: regions[0] || "",
    screen: "home",
    loading: true,
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
  };
  root.innerHTML = '<div class="ws" data-ws><p class="sr" role="status" aria-live="polite" data-ws-live></p><div data-ws-main></div></div>';
  wrap = root.querySelector("[data-ws]");
  wrap.addEventListener("click", onClick);
  wrap.addEventListener("change", onChange);
  if (announce) announce(`Signed in as ${ambassador.display_name}.`);
  render({focus: focus ? "heading" : null});
  return loadRegion(state.region, focus);
}

const mainEl = () => wrap.querySelector("[data-ws-main]");
function say(text) {
  const live = wrap.querySelector("[data-ws-live]");
  if (live) live.textContent = text;
}

function render({focus = null} = {}) {
  const host = mainEl();
  if (!host) return;
  if (state.loading) host.innerHTML = loadingHTML();
  else if (state.screen === "A") host.innerHTML = streamAHTML();
  else if (state.screen === "B") host.innerHTML = streamBHTML();
  else host.innerHTML = homeHTML();
  if (focus === "heading") host.querySelector("h2")?.focus();
  else if (focus) host.querySelector(focus)?.focus();
}

const crumb = '<p class="ws-crumb"><button type="button" class="link-btn" data-ws-action="home">Back to your tasks</button></p>';

function loadingHTML() {
  return `<h2 tabindex="-1">Your workspace</h2><p class="status">Loading your tasks for ${esc(regionName(state.region))}.</p>`;
}

function streamButton(stream, name, count, time) {
  return `<button type="button" class="ws-stream" data-ws-action="open" data-stream="${stream}">
    <span class="ws-stream-name">${esc(name)}</span><span class="ws-stream-count">${esc(count)}</span><span class="ws-stream-time">${esc(time)}</span></button>`;
}

function homeHTML() {
  const progress = caseProgress(state.cases, state.answers);
  const toConfirm = state.items.length;
  const switcher =
    state.regions.length > 1
      ? `<div class="ws-chips" role="group" aria-label="Choose a region">${state.regions
          .map(
            (slug) =>
              `<button type="button" class="ws-chip" data-ws-action="region" data-region="${esc(slug)}" aria-pressed="${slug === state.region}">${esc(regionName(slug))}</button>`,
          )
          .join("")}</div>`
      : "";
  const caseCount = progress.total ? progressText(progress) : "No cases yet";
  const caseTime = progress.remaining > 0 ? estimateText(progress.remaining * CASE_MINUTES) : "all answered";
  const itemCount = toConfirm ? `${toConfirm} to confirm` : "Nothing to confirm";
  const itemTime = toConfirm ? estimateText(toConfirm * ITEM_MINUTES) : "all confirmed";
  return `<p class="ws-region">Ambassador workspace</p>
    <h2 tabindex="-1">${esc(regionName(state.region))}</h2>
    <p class="hint">Your tasks for this region. Each answer is saved as soon as you give it.</p>
    ${switcher}
    ${state.loadError ? `<p class="ws-error">${esc(state.loadError)}</p>` : ""}
    <ul class="ws-streams">
      <li>${streamButton("A", "Check classifier cases", caseCount, caseTime)}</li>
      <li>${streamButton("B", "Confirm the region page", itemCount, itemTime)}</li>
      <li><div class="ws-stream is-soon" aria-disabled="true"><span class="ws-stream-name">Add local knowledge</span><span class="ws-stream-count">Coming next</span></div></li>
      <li><div class="ws-stream is-soon" aria-disabled="true"><span class="ws-stream-name">Settings</span><span class="ws-stream-count">Coming next</span></div></li>
    </ul>
    <p class="actions"><button type="button" class="link-btn" data-action="signout">Sign out</button></p>`;
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
      `<button type="button" class="ws-answer" data-ws-action="answer" data-answer="${answer}" aria-pressed="${saved?.answer === answer}">${ANSWER_LABELS[answer]}</button>`,
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
          const review = reviewText(latest.get(item.item_id)?.status);
          const link = safeUrl(item.url);
          const name = link ? `<a class="link" href="${esc(link)}" rel="noopener">${esc(item.name)}</a>` : esc(item.name);
          const open = state.editOpen === index;
          return `<li class="ws-item" data-item-row="${index}">
            <p class="ws-item-name">${name}</p>
            <p class="hint">${item.status === "draft" ? "Draft" : "To be confirmed"}${review ? `. ${esc(review)}` : ""}</p>
            ${item.note ? `<p class="hint">${esc(item.note)}</p>` : ""}
            <div class="ws-item-actions">
              <button type="button" class="btn" data-ws-action="item-confirm" data-index="${index}">Confirm</button>
              <button type="button" class="btn" data-ws-action="item-not-relevant" data-index="${index}">Not relevant</button>
              <button type="button" class="btn" data-ws-action="item-edit" data-index="${index}" aria-expanded="${open}" aria-controls="ws-edit-${index}">Correct or add a note</button>
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
  const [cases, regionFile, answers, mine] = await Promise.all([
    readJson(regionFileUrl(slug, "ambassador_cases.json")),
    readJson(regionFileUrl(slug, "region.json")),
    api(`/cases/answers?region=${encodeURIComponent(slug)}`),
    api("/submissions/mine"),
  ]);
  if (current !== state) return undefined;
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
