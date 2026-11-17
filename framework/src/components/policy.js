// Policy page: the curated DTSC microplastics regulatory timeline (Add-on A2 §7 Part B, EM-18)
// and the OPC Solutions track (Part A, EM-17). Reference information with outbound links only; it
// makes no statement about implementation, enforcement or effectiveness. The date text is
// reformatted from date_iso (UXD-7 prose style); the machine value is kept in <time datetime>.
// date_as_stated is the fallback when date_iso is unusable.
import {escapeHtml, loadJson} from "./atlas.js";

// Hardcoded so the caveat is shown even when the data file cannot be loaded.
export const CAVEAT = "Listing does not by itself create requirements; Priority Product designation is a separate rulemaking.";

const KIND_LABELS = {
  workshop: "Workshop",
  proposal: "Proposal",
  background: "Background document",
  finalized: "Finalized",
  effective: "Effective",
  work_plan: "Work plan"
};

// Only https links are shown (the YAML validator enforces this too).
export function isHttps(url) {
  if (typeof url !== "string") return false;
  try {
    return new URL(url).protocol === "https:";
  } catch {
    return false;
  }
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Prose date from an ISO-style value: "2025-11-12" -> "12 Nov 2025", "2025-11" -> "Nov 2025",
// "2025" -> "2025". Returns null for anything else so the caller can fall back to date_as_stated.
export function formatDate(dateIso) {
  const m = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/.exec(String(dateIso ?? ""));
  if (!m) return null;
  const [, year, month, day] = m;
  if (month === undefined) return year;
  const monthNumber = Number(month);
  if (monthNumber < 1 || monthNumber > 12) return null;
  const label = MONTHS[monthNumber - 1];
  if (day === undefined) return `${label} ${year}`;
  const dayNumber = Number(day);
  // Day 0 of the following month is the last day of this one.
  const daysInMonth = new Date(Date.UTC(Number(year), monthNumber, 0)).getUTCDate();
  if (dayNumber < 1 || dayNumber > daysInMonth) return null;
  return `${dayNumber} ${label} ${year}`;
}

// Sort key: a month-only date sorts as the first day of that month (same rule as the validator).
function sortKey(dateIso) {
  const value = String(dateIso ?? "");
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : `${value}-01`;
}

// Newest-first view model. Entries without a date or event text are dropped.
export function timelineItems(data) {
  const entries = data && Array.isArray(data.entries) ? data.entries : [];
  return entries
    .filter((e) => e && typeof e === "object" && typeof e.date_as_stated === "string" && typeof e.event === "string")
    .map((e) => ({
      id: String(e.id ?? ""),
      dateAsStated: e.date_as_stated,
      dateIso: String(e.date_iso ?? ""),
      event: e.event,
      sourceLabel: typeof e.source_label === "string" ? e.source_label : "Source",
      sourceUrl: isHttps(e.source_url) ? e.source_url : null,
      kind: typeof e.kind === "string" ? e.kind : "",
      kindLabel: KIND_LABELS[e.kind] || (typeof e.kind === "string" ? e.kind : "")
    }))
    .sort((a, b) => (sortKey(a.dateIso) < sortKey(b.dateIso) ? 1 : sortKey(a.dateIso) > sortKey(b.dateIso) ? -1 : 0));
}

export function caveatHtml(detail = "") {
  const detailHtml = detail ? `<p class="pol-caveat-detail">${escapeHtml(detail)}</p>` : "";
  return `<div class="pol-caveat" role="note"><p class="pol-caveat-main"><strong>${escapeHtml(CAVEAT)}</strong></p>${detailHtml}</div>`;
}

function itemHtml(item) {
  const source = item.sourceUrl
    ? `<a href="${escapeHtml(item.sourceUrl)}" target="_blank" rel="noreferrer">${escapeHtml(item.sourceLabel)}</a>`
    : `<span class="pol-source-text">${escapeHtml(item.sourceLabel)}</span>`;
  const kind = item.kindLabel ? `<span class="pol-kind">${escapeHtml(item.kindLabel)}</span> ` : "";
  const prose = formatDate(item.dateIso);
  const dateHtml = prose
    ? `<time datetime="${escapeHtml(item.dateIso)}">${escapeHtml(prose)}</time>`
    : escapeHtml(item.dateAsStated);
  return `<li class="pol-item"><p class="pol-date">${dateHtml}</p>` +
    `<p class="pol-event">${escapeHtml(item.event)}</p>` +
    `<p class="pol-meta">${kind}${source}</p></li>`;
}

export function renderTimeline(data) {
  const items = timelineItems(data);
  const detail = data && typeof data.caveat_detail === "string" ? data.caveat_detail : "";
  const list = items.length
    ? `<ol class="pol-list" aria-label="DTSC microplastics timeline, newest first">${items.map(itemHtml).join("")}</ol>`
    : `<p class="data-note" role="status">No timeline entries are available.</p>`;
  return caveatHtml(detail) + list;
}

export async function mountPolicy(root = document.getElementById("policy-timeline")) {
  if (!root) return;
  // The caveat is rendered first, so it is visible whatever happens to the data request.
  root.innerHTML = caveatHtml() + `<p class="data-note" role="status">Loading the timeline…</p>`;
  let data;
  try {
    data = await loadJson("dtsc_timeline.json");
  } catch {
    root.innerHTML = caveatHtml() + `<p class="data-note" role="status">The timeline could not be loaded. Check the DTSC pages directly.</p>`;
    return;
  }
  root.innerHTML = renderTimeline(data);
}

// OPC Solutions track: the 22 recommended early actions in the Ocean Protection Council's
// Statewide Microplastics Strategy. The summaries are the Atlas's own paraphrases, and the
// Global Plastic Laws links are a draft mapping until it has been reviewed.
// Hardcoded like CAVEAT, so the disclaimer and the source link show even if the data cannot load.
export const OPC_DISCLAIMER = "The Global Plastic Laws Database is an educational and research resource and should not be regarded as fully comprehensive or completely up to date for legal purposes.";
export const OPC_STRATEGY = {
  label: "Ocean Protection Council, Statewide Microplastics Strategy (2022)",
  url: "https://opc.ca.gov/water-quality/plastics/",
  adopted: "23 February 2022"
};

// The Atlas cell for an action: a keyword search on the Evidence page, or a topic filter.
export function atlasHref(atlas) {
  if (!atlas || typeof atlas !== "object") return null;
  const q = typeof atlas.q === "string" ? atlas.q.trim() : "";
  if (q) return `./evidence#q=${encodeURIComponent(q)}`;
  const topic = typeof atlas.topic === "string" ? atlas.topic.trim() : "";
  return topic ? `./evidence#topic=${encodeURIComponent(topic)}` : null;
}

// Objectives in curated order, each with its actions as view models. Topic links need an https
// base URL, and only slugs that gpl.topics defines are shown. The California search needs https too.
export function opcGroups(data) {
  const gpl = data && typeof data.gpl === "object" && data.gpl ? data.gpl : {};
  const topics = gpl.topics && typeof gpl.topics === "object" ? gpl.topics : {};
  const base = isHttps(gpl.base_url) ? String(gpl.base_url).replace(/\/+$/, "") : null;
  const californiaHref = isHttps(gpl.california_search_url) ? gpl.california_search_url : null;
  const isObject = (value) => Boolean(value) && typeof value === "object";
  const actions = data && Array.isArray(data.actions) ? data.actions.filter(isObject) : [];
  const objectives = data && Array.isArray(data.objectives) ? data.objectives.filter(isObject) : [];
  return objectives.map((objective) => ({
    id: String(objective.id ?? ""),
    name: typeof objective.name === "string" ? objective.name : "",
    actions: actions.filter((a) => a.objective === objective.id).map((a) => ({
      code: String(a.code ?? ""),
      summary: typeof a.summary === "string" ? a.summary : "",
      group: typeof a.group === "string" ? a.group : "",
      deadline: typeof a.deadline_as_stated === "string" ? a.deadline_as_stated : "",
      topics: (Array.isArray(a.gpl_topics) ? a.gpl_topics : [])
        .filter((slug) => typeof slug === "string" && Object.hasOwn(topics, slug))
        .map((slug) => ({
          slug,
          name: String(topics[slug]),
          href: base ? `${base}/topic/${encodeURIComponent(slug)}` : null
        })),
      californiaHref,
      atlasHref: atlasHref(a.atlas)
    }))
  }));
}

function srSuffix(code) {
  return `<span class="opc-sr"> for ${escapeHtml(code)}</span>`;
}

function opcCardHtml(action) {
  const topics = action.topics.length
    ? action.topics.map((topic) => (topic.href
      ? `<a href="${escapeHtml(topic.href)}" target="_blank" rel="noreferrer">${escapeHtml(topic.name)}</a>`
      : escapeHtml(topic.name))).join(", ")
    : `<span class="opc-none">No matching topic</span>`;
  const california = action.californiaHref
    ? `<a href="${escapeHtml(action.californiaHref)}" target="_blank" rel="noreferrer">California laws${srSuffix(action.code)}</a>`
    : "";
  const atlas = action.atlasHref
    ? `<a href="${escapeHtml(action.atlasHref)}">In the Atlas${srSuffix(action.code)}</a>`
    : "";
  return `<li class="opc-card">` +
    `<p class="opc-head"><code>${escapeHtml(action.code)}</code> <span class="opc-group">${escapeHtml(action.group)}</span></p>` +
    `<p class="opc-summary">${escapeHtml(action.summary)}</p>` +
    `<p><span class="opc-label">Strategy deadline</span> ${escapeHtml(action.deadline)}</p>` +
    `<p><span class="opc-label">Global Plastic Laws topic</span> ${topics}</p>` +
    `<p class="opc-links">${california}${california && atlas ? " " : ""}${atlas}</p>` +
    `</li>`;
}

// Introduction and disclaimer. Rendered from constants, so it needs no data.
export function opcFrameHtml() {
  return `<p class="opc-intro">The Ocean Protection Council's Statewide Microplastics Strategy, adopted ${escapeHtml(OPC_STRATEGY.adopted)}, lists 22 recommended early actions (Chapter 2A). The summaries are the Atlas's own paraphrases, not the Council's wording. Deadlines are quoted as the Strategy states them. <a href="${escapeHtml(OPC_STRATEGY.url)}" target="_blank" rel="noreferrer">Read the Strategy on the Ocean Protection Council site</a>.</p>` +
    `<div class="atlas-callout atlas-callout--info opc-disclaimer" role="note"><p>${escapeHtml(OPC_DISCLAIMER)}</p></div>`;
}

// The draft badge is shown unless the mapping is marked owner_reviewed, so a missing status stays draft.
export function opcBodyHtml(data) {
  const groups = opcGroups(data);
  if (!groups.some((group) => group.actions.length)) {
    return `<p class="data-note" role="status">No early actions are available.</p>`;
  }
  const badge = data.mapping_status !== "owner_reviewed"
    ? `<p class="opc-draft"><span class="atlas-badge opc-badge">Draft mapping, not yet reviewed</span> The Global Plastic Laws links are the Atlas's draft mapping and may change.</p>`
    : "";
  const chips = groups.map((group) => `<button type="button" class="opc-chip" aria-pressed="true" data-objective-chip="${escapeHtml(group.id)}">${escapeHtml(group.name)}</button>`).join("");
  const sections = groups.map((group) => `<section class="opc-objective" data-objective-section="${escapeHtml(group.id)}" aria-labelledby="opc-objective-${escapeHtml(group.id)}"><h3 id="opc-objective-${escapeHtml(group.id)}">${escapeHtml(group.name)}</h3><ul class="opc-grid">${group.actions.map(opcCardHtml).join("")}</ul></section>`).join("");
  return badge +
    `<div class="opc-filter" role="group" aria-label="Show objectives">${chips}</div>` +
    `<p class="data-note" data-objective-empty role="status" hidden>No objectives are selected. Choose one to see its actions.</p>` +
    sections;
}

// Toggle chips show or hide an objective's actions. Each chip starts pressed (shown).
function bindObjectiveFilter(root) {
  const chips = [...root.querySelectorAll("[data-objective-chip]")];
  const sections = [...root.querySelectorAll("[data-objective-section]")];
  const empty = root.querySelector("[data-objective-empty]");
  const apply = () => {
    const pressed = new Set(chips
      .filter((chip) => chip.getAttribute("aria-pressed") === "true")
      .map((chip) => chip.dataset.objectiveChip));
    for (const section of sections) section.hidden = !pressed.has(section.dataset.objectiveSection);
    if (empty) empty.hidden = pressed.size > 0;
  };
  for (const chip of chips) {
    chip.addEventListener("click", () => {
      chip.setAttribute("aria-pressed", chip.getAttribute("aria-pressed") === "true" ? "false" : "true");
      apply();
    });
  }
}

export async function mountOpcActions(root = document.getElementById("policy-opc")) {
  if (!root) return;
  // The introduction and disclaimer come first, so they show whatever happens to the data request.
  root.innerHTML = opcFrameHtml() + `<p class="data-note" role="status">Loading the early actions…</p>`;
  let data;
  try {
    data = await loadJson("opc_actions.json");
  } catch {
    root.innerHTML = opcFrameHtml() + `<p class="data-note" role="status">The early actions could not be loaded. Check the Ocean Protection Council pages directly.</p>`;
    return;
  }
  root.innerHTML = opcFrameHtml() + opcBodyHtml(data);
  bindObjectiveFilter(root);
}
