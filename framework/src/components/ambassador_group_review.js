// Group tag checks on the moderation page (CG-7c). The owner and region leads check sampled community-group tags
// against the evidence: one tag per screen, every field starts as "Agree" so an all-agree check is one click, and
// "Edit" reveals the value picker and a reason. The static markup is in ambassador_moderation.md (section #grv-root).
// This module reads GET /groups/reviews and the published roster once, and saves each check with POST /groups/reviews.
// Submitted text is written with textContent only, and links are built only for http(s) URLs. Pure helpers are
// exported for tests/framework_ambassador_group_review_runtime.mjs; nothing touches the DOM at import time.
import {REGION_NAMES, api, apiUrl, errorText} from "./ambassador_signup.js";
import {globalDataUrl} from "./atlas.js";
import {groupLabel} from "./group_labels.js";

/** The five fields a check covers, in screen order. The Worker requires all five. */
export const TAG_FACETS = ["entity_type", "sector", "plastics_centrality", "primary_activities", "geographic_scope"];
/** Allowed values per field. Mirrors GROUP_TAXONOMY in ambassador_groups.js (tests/test_ambassador_group_review.py keeps them equal). */
export const FACET_VALUES = {
  entity_type: ["organisation", "network_coalition", "programme_project", "campaign", "informal_group", "chapter_branch", "other"],
  sector: ["ngo_civil_society", "community_informal", "foundation", "academia_research", "private_sector", "government", "joint_power_authority", "igo", "other"],
  plastics_centrality: ["primary", "substantial", "incidental", "none", "cannot_determine"],
  primary_activities: ["advocacy_campaigning", "policy_governance", "research_monitoring", "education_awareness", "cleanup_removal", "waste_management_recycling", "reuse_refill_alternatives", "business_innovation", "community_organising_justice", "coalition_building_capacity", "funding_grantmaking", "legal_action", "other"],
  geographic_scope: ["local", "subnational", "national", "regional_multi_country", "global"],
};
export const FACET_LABELS = {
  entity_type: "Organisation type", sector: "Sector", plastics_centrality: "How central are plastics?",
  primary_activities: "Main activities (choose 1 to 5)", geographic_scope: "Geographic scope",
};
/** How the field is named inside a sentence. */
const FACET_NAMES = {
  entity_type: "the organisation type", sector: "the sector", plastics_centrality: "how central plastics are",
  primary_activities: "the main activities", geographic_scope: "the geographic scope",
};
export const MAX_ACTIVITIES = 5;
/** Reasons for an edit. The keys must equal REVIEW_REASON in worker/src/groups_taxonomy.ts (checked by pytest). */
export const REVIEW_REASONS = Object.freeze({
  evidence_contradicts: {label: "The evidence says something else", tip: "The page says something different from the tag."},
  better_evidence_found: {label: "I found better evidence on the group's own site", tip: "Another page on the group's own site settles it."},
  guide_rule: {label: "The labelling guide gives a different value", tip: "The labelling guide points to a different value."},
  activity_order: {label: "The main activity should be listed first", tip: "The activities are right, but the main one is not first."},
  slip: {label: "A slip (the wrong option was picked)", tip: "The wrong option was picked by mistake."},
  other: {label: "Other", tip: "None of the reasons above fits."},
});
export const NOT_MODERATOR_TEXT = "This page is for the owner and region leads.";
const SIGN_IN_TEXT = "Group tag checks are for the owner and region leads. Sign in with ORCID to check tags.";
/** Errors after which the tag can no longer be checked here: show the sentence and go on to the next tag. */
export const ADVANCE_CODES = ["not_found", "not_selected", "not_approved", "already_reviewed"];
const HTTP_ONLY = ["http:", "https:"];

const ERROR_TEXT = {
  invalid_review: "A choice in this check is not valid. Look at the fields and try again.",
  not_signed_in: "Your sign-in has ended. Sign in with ORCID to check tags.",
  forbidden: NOT_MODERATOR_TEXT,
  self_review: "You cannot check a tag that you tagged yourself.",
  not_found: "This tag is no longer waiting for a check. Moving on to the next one.",
  not_selected: "This tag is no longer in the check list. Moving on to the next one.",
  not_approved: "This tag is not approved yet, so it cannot be checked. Moving on to the next one.",
  already_reviewed: "Someone has already checked this tag. Moving on to the next one.",
  rate_limited: "There have been too many checks this hour. Wait a while and try again.",
};

/** A check's error code as a plain sentence. Unknown codes use the shared generic text. */
export function reviewErrorText(code) {
  return Object.hasOwn(ERROR_TEXT, code) ? ERROR_TEXT[code] : errorText(code);
}

/** "Tag 2 of 7" for a 1-based position. */
export function progressText(position, total) {
  return `Tag ${position} of ${total}`;
}

/** The plain label of a reason code, or "" when the code is unknown. */
export function reasonLabel(code) {
  return Object.hasOwn(REVIEW_REASONS, code) ? REVIEW_REASONS[code].label : "";
}

/** Every field starts as Agree. */
export function initialChoices() {
  return Object.fromEntries(TAG_FACETS.map((facet) => [facet, {outcome: "agree"}]));
}

/** The request body for POST /groups/reviews. An edit carries `value` and `reason_code`; an agree carries nothing else. */
export function reviewBody(submissionId, choices) {
  const facets = {};
  for (const facet of TAG_FACETS) {
    const choice = choices?.[facet] || {outcome: "agree"};
    facets[facet] = choice.outcome === "edit"
      ? {outcome: "edit", value: Array.isArray(choice.value) ? [...choice.value] : choice.value, reason_code: choice.reason}
      : {outcome: "agree"};
  }
  return {submission_id: submissionId, facets};
}

/** The tagged value of a field. Activities are always an array (empty when the tag has none). */
function originalValue(payload, facet) {
  const value = payload?.[facet];
  if (facet === "primary_activities") return Array.isArray(value) ? value : [];
  return value ?? null;
}

/**
 * The first sentence that stops the check from being saved, or null. Checks: a value from the list, activities
 * (1 to 5, distinct), a value that differs from the tag (order counts for activities), no "cannot determine" for
 * plastics, and a reason for every edit.
 */
export function reviewProblem(payload, choices) {
  for (const facet of TAG_FACETS) {
    const choice = choices?.[facet];
    if (!choice || choice.outcome !== "edit") continue;
    const name = FACET_NAMES[facet];
    const value = choice.value;
    const original = originalValue(payload, facet);
    if (facet === "primary_activities") {
      if (!Array.isArray(value) || value.length < 1 || value.length > MAX_ACTIVITIES) {
        return `Choose 1 to ${MAX_ACTIVITIES} main activities.`;
      }
      if (new Set(value).size !== value.length || value.some((v) => !FACET_VALUES[facet].includes(v))) {
        return "Choose each main activity from the list, once.";
      }
      if (JSON.stringify(value) === JSON.stringify(original)) {
        return "Change the main activities or their order, or choose Agree.";
      }
    } else {
      if (!FACET_VALUES[facet].includes(value)) return `Choose a value for ${name}.`;
      if (facet === "plastics_centrality" && value === "cannot_determine") {
        return "Plastics cannot be marked as cannot determine here. Choose another value.";
      }
      if (value === original) return `Change the value for ${name}, or choose Agree.`;
    }
    if (!Object.hasOwn(REVIEW_REASONS, choice.reason)) return `Choose a reason for the change to ${name}.`;
  }
  return null;
}

/** An http or https address, or null. Only these become links. */
export function safeHttpUrl(value) {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  try {
    return HTTP_ONLY.includes(new URL(trimmed).protocol) && !/[\s<>"]/.test(trimmed) ? trimmed : null;
  } catch {
    return null;
  }
}

/**
 * The evidence for one field: {quote, notStated, url, accessedAt}, or null when none is recorded. Every tag carries its
 * own activities evidence, so no field borrows another field's quote.
 */
export function facetEvidence(payload, facet) {
  const entries = Array.isArray(payload?.evidence) ? payload.evidence : [];
  const find = (name) => entries.find((entry) => entry && entry.facet === name);
  const entry = find(facet);
  if (!entry) return null;
  const quote = typeof entry.quote === "string" ? entry.quote.trim() : "";
  return {
    quote: quote || null,
    notStated: entry.not_stated === true,
    url: safeHttpUrl(entry.url),
    accessedAt: typeof entry.accessed_at === "string" ? entry.accessed_at : null,
  };
}

/** A field's tagged value as plain text, using the display labels. Activities are joined; the first one is marked main. */
export function facetValueText(facet, value) {
  if (facet === "primary_activities") {
    const list = Array.isArray(value) ? value : [];
    return list.map((v, i) => `${groupLabel(facet, v)}${i === 0 ? " (main)" : ""}`).join(", ");
  }
  return groupLabel(facet, value);
}

/** Index of the published roster by group id: {name, url}. A missing or unreadable roster gives an empty index. */
export function rosterIndex(roster) {
  const index = new Map();
  const records = Array.isArray(roster?.records) ? roster.records : [];
  for (const record of records) {
    if (record && record.group_id !== undefined && record.group_id !== null) {
      index.set(String(record.group_id), {
        name: typeof record.name === "string" ? record.name.trim() : "",
        url: safeHttpUrl(record.url),
      });
    }
  }
  return index;
}

/** Name and website for a group. The name falls back to the group id; the website is null when the roster has none. */
export function groupDisplay(index, groupId) {
  const record = index?.get(String(groupId));
  return {name: record?.name || String(groupId ?? ""), url: record?.url || null};
}

const isAllAgree = (choices) => TAG_FACETS.every((facet) => choices[facet]?.outcome === "agree");

// ---- DOM ----------------------------------------------------------------------------------------------------------

let root = null;
let body = null;
let statusEl = null;
let state = null; // {region, reviews, index, notice}
let shell = null; // {select, count, host} once the region picker is on the page
let view = null; // the tag on screen: {review, choices, save, result}
let rosterCache = null;
let rosterMap = rosterIndex(null);

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  node.append(...children);
  return node;
}

function setStatus(text) {
  if (statusEl) statusEl.textContent = text;
}

function setResult(text, isError = false) {
  if (!view) return;
  view.result.textContent = text;
  view.result.className = isError ? "hint mod-result grv-result is-error" : "hint mod-result grv-result";
}

function setBusy(busy) {
  if (!view) return;
  view.save.disabled = busy;
  for (const input of view.inputs) input.disabled = busy;
}

/** The roster, fetched once. A failed fetch is cached as an empty roster, so names fall back to the group id. */
function loadRoster() {
  if (!rosterCache) {
    rosterCache = fetch(globalDataUrl("groups/roster.json"), {cache: "no-cache"})
      .then((response) => (response.ok ? response.json() : null))
      .then((roster) => (rosterMap = rosterIndex(roster)))
      .catch(() => (rosterMap = rosterIndex(null)));
  }
  return rosterCache;
}

function reviewsUrl(region) {
  return region ? `/groups/reviews?region=${encodeURIComponent(region)}` : "/groups/reviews";
}

function showSignIn() {
  shell = null;
  view = null;
  body.replaceChildren(
    el("p", {}, [SIGN_IN_TEXT]),
    el("div", {class: "btns"}, [el("a", {class: "btn solid", href: apiUrl("/orcid/start")}, ["Sign in with ORCID"])]),
  );
  setStatus(SIGN_IN_TEXT);
}

function showNotModerator() {
  shell = null;
  view = null;
  body.replaceChildren(el("p", {tabindex: "-1"}, [NOT_MODERATOR_TEXT]));
  body.querySelector("p").focus();
  setStatus(NOT_MODERATOR_TEXT);
}

function showFailure(text) {
  shell = null;
  view = null;
  const retry = el("button", {type: "button", class: "btn"}, ["Try again"]);
  retry.addEventListener("click", () => loadReviews(state?.region || ""));
  body.replaceChildren(el("p", {class: "hint"}, [text]), el("div", {class: "btns"}, [retry]));
  setStatus(text);
}

/** The region picker, the count line and the tag area. Built once; later loads only fill the tag area. */
function buildShell() {
  const select = el("select", {id: "grv-region", class: "mod-select"}, [
    el("option", {value: ""}, ["All regions"]),
    ...Object.entries(REGION_NAMES).map(([slug, label]) => el("option", {value: slug}, [label])),
  ]);
  select.addEventListener("change", (event) => loadReviews(event.target.value));
  const count = el("p", {class: "mod-count", role: "status", "aria-live": "polite"});
  const host = el("div", {class: "grv-queue"});
  body.replaceChildren(
    el("h2", {class: "grv-title"}, ["Group tag checks"]),
    el("p", {class: "hint"}, ["Check each sampled group tag against its evidence. Agree, or edit a field and give a reason. Each check is saved as soon as you press the button."]),
    el("div", {class: "field"}, [el("label", {for: "grv-region"}, ["Region"]), select]),
    count,
    host,
  );
  shell = {select, count, host};
}

/** Loads the checks for a region ("" for all) and shows the first tag. */
async function loadReviews(region) {
  const [response] = await Promise.all([api(reviewsUrl(region)), loadRoster()]);
  if (!response.ok) {
    if (response.error === "not_signed_in") return showSignIn();
    if (response.status === 403 || response.error === "forbidden") return showNotModerator();
    return showFailure(reviewErrorText(response.error));
  }
  state = {
    region,
    reviews: Array.isArray(response.data?.reviews) ? response.data.reviews : [],
    index: 0,
    notice: "",
  };
  if (!shell) buildShell();
  shell.select.value = region;
  return renderQueue();
}

function renderQueue() {
  const total = state.reviews.length;
  // The empty state says it once, in the tag area.
  shell.count.textContent = total ? `${total} ${total === 1 ? "tag" : "tags"} in this view.` : "";
  if (total === 0) {
    const where = state.region ? ` in ${REGION_NAMES[state.region] || state.region}` : "";
    shell.host.replaceChildren(el("p", {}, [`No group tags are waiting for a check${where}.`]));
    view = null;
    setStatus("No group tags are waiting for a check.");
    return;
  }
  if (state.index >= total) {
    const refresh = el("button", {type: "button", class: "btn"}, ["Refresh the checks"]);
    refresh.addEventListener("click", () => loadReviews(state.region));
    shell.host.replaceChildren(el("p", {}, ["That was the last tag in this view."]), el("div", {class: "btns"}, [refresh]));
    view = null;
    setStatus("No more tags in this view.");
    return;
  }
  renderReview(state.reviews[state.index]);
}

/** One tag on screen: the group, then a row per field with its evidence and the Agree / Edit choice. */
function renderReview(review) {
  const payload = review.payload || {};
  const group = groupDisplay(rosterMap, payload.group_id);
  const choices = initialChoices();
  const inputs = [];
  const result = el("p", {class: "hint mod-result grv-result", role: "status", "aria-live": "polite"}, [state.notice]);
  state.notice = "";
  const save = el("button", {type: "button", class: "btn solid"}, ["Save check: all agree"]);
  const heading = el("h3", {tabindex: "-1", class: "grv-heading"}, [group.name]);
  view = {review, choices, save, result, inputs};

  const rows = TAG_FACETS.map((facet) => facetRow(facet, payload, choices, inputs));
  save.addEventListener("click", () => saveCheck(review));
  const article = el("article", {class: "grv-tag", "aria-label": "Group tag check"}, [
    el("p", {class: "grv-progress"}, [progressText(state.index + 1, state.reviews.length)]),
    heading,
    group.url
      ? el("p", {class: "grv-site"}, [el("a", {href: group.url, target: "_blank", rel: "noopener noreferrer nofollow"}, ["Group website (opens in a new tab)"])])
      : el("p", {class: "hint"}, ["The roster has no website for this group."]),
    ...rows,
    el("div", {class: "btns"}, [save]),
    result,
  ]);
  shell.host.replaceChildren(article);
  setStatus(`${progressText(state.index + 1, state.reviews.length)}. ${group.name}.`);
  updateSaveLabel();
  heading.focus();
}

function updateSaveLabel() {
  if (!view) return;
  view.save.textContent = isAllAgree(view.choices) ? "Save check: all agree" : "Save check";
}

function evidenceParagraph(facet, payload) {
  const evidence = facetEvidence(payload, facet);
  const children = [];
  if (!evidence) {
    children.push("No evidence is recorded for this field.");
  } else {
    if (evidence.quote) children.push(`"${evidence.quote}"`);
    else if (evidence.notStated) children.push("Not stated on the page");
    else children.push("No quote was recorded.");
    if (evidence.accessedAt) children.push(` Page read ${evidence.accessedAt}.`);
    if (evidence.url) {
      children.push(" ", el("a", {href: evidence.url, target: "_blank", rel: "noopener noreferrer nofollow"}, ["Source page (opens in a new tab)"]));
    }
  }
  return el("p", {class: "grv-evidence"}, children);
}

/** One field: the tagged value, its evidence, Agree / Edit, and the picker and reason when Edit is chosen. */
function facetRow(facet, payload, choices, inputs) {
  const name = `grv-${facet}`;
  const original = originalValue(payload, facet);
  const agree = el("input", {type: "radio", name, value: "agree", checked: true});
  const edit = el("input", {type: "radio", name, value: "edit"});
  const reason = el("select", {id: `grv-reason-${facet}`, class: "mod-select"}, [
    el("option", {value: ""}, ["Choose a reason"]),
    ...Object.keys(REVIEW_REASONS).map((code) => el("option", {value: code}, [REVIEW_REASONS[code].label])),
  ]);
  const tip = el("p", {class: "hint grv-tip"});
  const panel = el("div", {class: "grv-edit", hidden: true});
  const picker = facet === "primary_activities" ? null : el("select", {id: `grv-value-${facet}`, class: "mod-select"}, [
    el("option", {value: ""}, ["Choose a value"]),
    ...FACET_VALUES[facet].map((value) => el("option", {value}, [groupLabel(facet, value)])),
  ]);
  const order = [...originalValue(payload, facet)];
  const boxes = [];

  const read = () => ({
    value: picker ? (picker.value || null) : [...order],
    reason: reason.value || undefined,
  });
  const sync = () => {
    panel.hidden = !edit.checked;
    choices[facet] = edit.checked ? {outcome: "edit", ...read()} : {outcome: "agree"};
    tip.textContent = reason.value ? REVIEW_REASONS[reason.value].tip : "";
    reason.title = tip.textContent;
    updateSaveLabel();
  };
  const warn = (text) => setResult(text, true);

  if (picker) {
    picker.addEventListener("change", sync);
    panel.append(el("label", {for: picker.id}, ["Corrected value"]), picker);
  } else {
    const list = el("div", {class: "grv-activities", role: "group", "aria-label": FACET_LABELS[facet]});
    for (const value of FACET_VALUES[facet]) {
      const box = el("input", {type: "checkbox", value, checked: original.includes(value)});
      boxes.push(box);
      box.addEventListener("change", () => {
        if (box.checked) {
          if (order.length >= MAX_ACTIVITIES) {
            box.checked = false;
            return warn(`Choose up to ${MAX_ACTIVITIES} main activities.`);
          }
          order.push(value);
        } else {
          const at = order.indexOf(value);
          if (at >= 0) order.splice(at, 1);
        }
        return sync();
      });
      list.append(el("label", {}, [box, ` ${groupLabel(facet, value)}`]));
    }
    panel.append(
      el("p", {class: "hint", id: `grv-value-hint-${facet}`}, ["Tick up to 5. The first one you tick is the main activity, so tick in the order you want."]),
      list,
    );
    inputs.push(...boxes);
  }
  if (picker) inputs.push(picker);
  panel.append(el("label", {for: reason.id}, ["Reason for the change"]), reason, tip);
  reason.addEventListener("change", sync);
  agree.addEventListener("change", sync);
  edit.addEventListener("change", sync);
  inputs.push(agree, edit, reason);

  return el("fieldset", {class: "grv-facet"}, [
    el("legend", {}, [FACET_LABELS[facet]]),
    el("p", {class: "grv-tagged"}, [`Tagged as: ${facetValueText(facet, original) || "Not given"}`]),
    evidenceParagraph(facet, payload),
    el("div", {class: "grv-choice"}, [
      el("label", {class: "grv-option"}, [agree, " Agree"]),
      el("label", {class: "grv-option"}, [edit, " Edit"]),
    ]),
    panel,
  ]);
}

async function saveCheck(review) {
  if (!view || view.review !== review) return;
  const problem = reviewProblem(review.payload, view.choices);
  if (problem) return setResult(problem, true);
  const current = view;
  setBusy(true);
  setResult("Saving your check.");
  const response = await api("/groups/reviews", {method: "POST", body: reviewBody(review.submission_id, view.choices)});
  if (view !== current) return undefined; // the page moved on while the request ran
  if (response.ok) {
    state.index += 1;
    state.notice = "Check saved.";
    return renderQueue();
  }
  if (response.error === "not_signed_in") return showSignIn();
  if (response.status === 403 || response.error === "forbidden") return showNotModerator();
  if (ADVANCE_CODES.includes(response.error) || response.status === 404) {
    state.index += 1;
    state.notice = reviewErrorText(response.error);
    return renderQueue();
  }
  setResult(reviewErrorText(response.error), true);
  setBusy(false);
  return undefined;
}

/** Mounts the group tag checks in `rootEl` (the #grv-root section). Nothing is read until this runs. */
export async function mountGroupReview(rootEl) {
  root = rootEl;
  body = root.querySelector("#grv-body");
  statusEl = root.querySelector("#grv-status");
  if (!body) return undefined;
  return loadReviews("");
}
