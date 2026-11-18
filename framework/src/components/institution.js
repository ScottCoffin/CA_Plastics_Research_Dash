// Institution detail page (INST-PAGE), reached as institution#inst=<id>[&section=experts|publications|topics].
// DOM only: every calculation lives in institution_model.js. The publications list is the shared
// works table (ev_table.js), limited to this institution's works and to the chosen topic.
import "./shared/topics.js";
import {loadJson, escapeHtml, classicUrl} from "./atlas.js";
import {mountWorksTable} from "./ev_table.js";
import {safeHttpUrl} from "./ev_table_model.js";
import {institutionTypeLabel} from "./shared/labels.js";
import {icon} from "./shared/icons.js";
import {
  LEAD_AUTHOR_LIMIT,
  barChartLayout,
  collaborators,
  contributorSummary,
  labelStep,
  leadAuthors,
  mostCited,
  networksForInstitution,
  openAlexUrl,
  parseInstitutionHash,
  plasticWorks,
  rorUrl,
  searchInstitutions,
  summaryStats,
  topJournals,
  topicWeights,
  workIds,
  worksPerYear,
  worksWithTag,
} from "./institution_model.js";

const topics = () => globalThis.AtlasTopics;
const countFormat = new Intl.NumberFormat("en-US");
const fmt = (value) => (Number.isFinite(value) ? countFormat.format(value) : "—");
const plural = (count, word) => `${fmt(count)} ${word}${count === 1 ? "" : "s"}`;
const percent = (share) => (share === null || share === undefined ? "—" : `${Math.round(share * 100)}%`);
const appUrl = (path) => new URL(path, document.baseURI).href;
const root = () => document.getElementById("institution-root");
const pick = (selector) => root().querySelector(selector);

// loadedId and payload describe the institution currently drawn; token drops stale async results.
const state = {
  institutions: null, // array from institutions.json
  byId: new Map(),
  token: 0,
  loadedId: "",
  payload: null,
  instId: "",
  section: "",
  works: [],
  experts: [],
  filterTag: "",
  leadsExpanded: false,
  table: null,
  networksRequest: null, // promise for research_networks.json, shared by every render
};

async function loadInstitutionList() {
  if (state.institutions) return state.institutions;
  const payload = await loadJson("institutions.json");
  const list = payload && Array.isArray(payload.institutions) ? payload.institutions : null;
  if (!list) throw new Error("institutions.json does not match the expected shape");
  state.byId = new Map(list.map((institution) => [String(institution.inst_id), institution]));
  state.institutions = list;
  return list;
}

// Loaded once per page session. A missing file resolves to null (no networks card); a failed
// request clears the cache so that Retry can try again.
function loadNetworks() {
  if (!state.networksRequest) {
    state.networksRequest = loadJson("research_networks.json", {optional: true}).catch(() => {
      state.networksRequest = null;
      return null;
    });
  }
  return state.networksRequest;
}

function nameOf(id) {
  const known = state.byId.get(id);
  return known && known.name ? known.name : id;
}

function renderFailed(error) {
  root().innerHTML = `<div class="inst-state" role="alert"><p>${escapeHtml(error.message || "Institution data is unavailable")}. Run the site through a web server and rebuild the data export.</p>`
    + `<button type="button" id="institution-retry" class="inst-button">Retry</button></div>`;
}

function searchPageHtml(notice) {
  return `<h1>Institutions</h1>`
    + `<p class="panel-intro">Search for an institution to see its plastic-related work, lead authors, topics and publications.</p>`
    + (notice ? noticeHtml(notice) : "")
    + `<div class="inst-field"><label for="institution-search">Search institutions</label>`
    + `<input id="institution-search" type="search" autocomplete="off" placeholder="Name, city or type"></div>`
    + `<p id="institution-search-count" class="result-count" role="status" aria-live="polite"></p>`
    + `<ul id="institution-search-results" class="inst-search-results"></ul>`
    + `<p class="data-note"><a href="${escapeHtml(appUrl("institutions"))}">Open the institutions leaderboard</a></p>`;
}

function renderSearchResults(query) {
  const {total, shown} = searchInstitutions(state.institutions || [], query);
  const count = pick("#institution-search-count");
  const list = pick("#institution-search-results");
  if (!count || !list) return;
  count.textContent = total
    ? `${fmt(total)} institution${total === 1 ? "" : "s"} found${total > shown.length ? `; showing the first ${shown.length}. Type more words to narrow the list.` : "."}`
    : "No institution matches this search.";
  list.innerHTML = shown.map((institution) => {
    const details = [institutionTypeLabel(institution.atlas_type), institution.city].filter(Boolean).join(", ");
    return `<li><a href="${escapeHtml(appUrl(`institution#inst=${encodeURIComponent(institution.inst_id)}`))}">${escapeHtml(institution.name || institution.inst_id)}</a>`
      + (details ? ` <span class="detail-meta">${escapeHtml(details)}</span>` : "")
      + `</li>`;
  }).join("");
}

async function showSearch(token, notice) {
  try {
    await loadInstitutionList();
  } catch (error) {
    if (token === state.token) renderFailed(error);
    return;
  }
  if (token !== state.token) return;
  root().innerHTML = searchPageHtml(notice);
  renderSearchResults("");
}

// Shared callout (design/components.css): an info icon beside one message.
function noticeHtml(message) {
  return `<div class="atlas-callout atlas-callout--info" role="status">${icon("info").outerHTML}<p>${escapeHtml(message)}</p></div>`;
}

function headerHtml(institution) {
  const name = institution.name || institution.inst_id;
  const ror = rorUrl(institution.ror);
  const openAlex = openAlexUrl(institution.inst_id);
  const location = [institution.city, institution.region].filter(Boolean).join(", ");
  const scope = institution.ca_flag
    ? `<span class="atlas-badge atlas-badge--good">California</span>`
    : `<span class="atlas-badge atlas-badge--accent">Collaborator outside California</span>`;
  const links = [
    ror ? `<a class="atlas-pill" href="${escapeHtml(ror)}">ROR record</a>` : "",
    openAlex ? `<a class="atlas-pill" href="${escapeHtml(openAlex)}">OpenAlex record</a>` : "",
  ].join("");
  return `<p class="inst-back"><a href="${escapeHtml(appUrl("institutions"))}">← All institutions</a></p>`
    + `<header class="atlas-page-head inst-page-head"><span class="motif" aria-hidden="true"></span>`
    + `<p class="atlas-page-head__eyebrow">${icon("building").outerHTML}Institution</p>`
    + `<h1>${escapeHtml(name)}</h1>`
    + `<p class="atlas-page-head__lead">Plastic-related works, lead authors, topics and publications for this institution.</p>`
    + `<div class="atlas-page-head__meta"><span class="atlas-badge">${escapeHtml(institutionTypeLabel(institution.atlas_type || "other"))}</span>${scope}`
    + (location ? `<span class="atlas-pill">${escapeHtml(location)}</span>` : "")
    + links
    + `</div></header>`;
}

function tilesHtml(stats) {
  const tiles = [
    ["Plastic-related works", fmt(stats.plasticWorks), ""],
    ["Authors", fmt(stats.experts), ""],
    ["Citations to these works", fmt(stats.citations), ""],
    ["Open access", percent(stats.oaShare), "share of works"],
    ["California-led", percent(stats.caLedShare), "share of works"],
    ["Active years", stats.firstYear === null ? "—" : `${stats.firstYear}–${stats.lastYear}`, ""],
    ["Works in the last 5 full years", fmt(stats.recentWorks), `${stats.recentFrom}–${stats.recentTo}`],
  ];
  return `<dl class="atlas-kpis inst-tiles">${tiles.map(([label, value, note]) => `<div class="atlas-kpi"><dt class="atlas-kpi__label">${escapeHtml(label)}</dt>`
    + `<dd class="atlas-kpi__value">${escapeHtml(value)}${note ? ` <span class="atlas-kpi__note">${escapeHtml(note)}</span>` : ""}</dd></div>`).join("")}</dl>`;
}

function yearsHtml(works) {
  const series = worksPerYear(works);
  if (!series.length) return `<p class="empty">No plastic-related works with a publication year yet.</p>`;
  const layout = barChartLayout(series);
  const step = labelStep(series.length);
  const summary = series.map((entry) => `${entry.year}: ${entry.count}`).join(", ");
  const bars = layout.bars.map((bar) => `<rect class="inst-bar" x="${bar.x.toFixed(2)}" y="${bar.y.toFixed(2)}" width="${bar.width.toFixed(2)}" height="${bar.height.toFixed(2)}"><title>${bar.year}: ${escapeHtml(plural(bar.count, "work"))}</title></rect>`).join("");
  const labels = layout.bars
    .filter((_, index) => index % step === 0)
    .map((bar) => `<text x="${(bar.x + bar.width / 2).toFixed(2)}" y="${layout.height - 6}" text-anchor="middle">${bar.year}</text>`)
    .join("");
  const rows = series.map((entry) => `<tr><th scope="row">${entry.year}</th><td>${fmt(entry.count)}</td></tr>`).join("");
  return `<figure class="inst-chart">`
    + `<svg class="inst-bars" viewBox="0 0 ${layout.width} ${layout.height}" role="img" aria-label="${escapeHtml(`Plastic-related works per year. ${summary}.`)}">`
    + `<line class="inst-axis" x1="0" x2="${layout.width}" y1="${layout.baseline}" y2="${layout.baseline}"/>${bars}${labels}</svg>`
    + `<table class="inst-sr-only"><caption>Plastic-related works per year</caption><thead><tr><th scope="col">Year</th><th scope="col">Works</th></tr></thead><tbody>${rows}</tbody></table>`
    + `</figure>`;
}

function topicChip(entry, matrix) {
  const api = topics();
  const active = state.filterTag === entry.tag;
  const dot = matrix ? "" : `<span class="topic-dot" aria-hidden="true" style="background:${escapeHtml(api.color(entry.tag))}"></span>`;
  return `<button type="button" class="inst-topic-chip${matrix ? " matrix" : ""}" data-topic="${escapeHtml(entry.tag)}" aria-pressed="${active}" style="font-size:${entry.fontRem}rem">`
    + `${dot}<span>${escapeHtml(api.label(entry.tag))}</span> <span class="inst-topic-count">${fmt(entry.count)}</span></button>`;
}

function renderTopics() {
  const container = pick("#inst-topics");
  if (!container) return;
  const {topics: topicList, matrices} = topicWeights(state.works);
  const topicHtml = topicList.length
    ? `<div class="inst-topic-cloud" role="group" aria-label="Topic tags, sized by number of works">${topicList.map((entry) => topicChip(entry, false)).join("")}</div>`
    : `<p class="empty">No topic tags yet.</p>`;
  const matrixHtml = matrices.length
    ? `<h3 class="inst-subhead">Sampled matrix</h3><div class="inst-topic-cloud" role="group" aria-label="Sampled matrix tags">${matrices.map((entry) => topicChip(entry, true)).join("")}</div>`
    : "";
  const selected = state.filterTag
    ? `<p class="inst-filter-note" aria-live="polite">Publication list filtered to ${escapeHtml(topics().label(state.filterTag))}: ${plural(worksWithTag(state.works, state.filterTag).length, "work")}.</p>`
    : `<p class="inst-filter-note" aria-live="polite">Select a topic to filter the publication list.</p>`;
  container.innerHTML = `<p class="data-note">Bigger tags have more works. A work can carry several tags, so the counts add up to more than the number of works.</p>`
    + topicHtml + matrixHtml
    + `<div class="inst-filter-row">${selected}<button type="button" class="inst-button" data-topic-clear${state.filterTag ? "" : " disabled"}>Clear</button></div>`;
}

function updateTable() {
  const subset = worksWithTag(state.works, state.filterTag);
  if (state.table) state.table.update(workIds(subset));
  const note = pick("#inst-publications-note");
  if (note) {
    note.textContent = state.filterTag
      ? `Showing ${plural(subset.length, "work")} tagged ${topics().label(state.filterTag)}.`
      : `Showing all ${plural(state.works.length, "plastic-related work")} for this institution.`;
  }
}

function leadsHtml() {
  const rows = leadAuthors(state.experts, state.works);
  if (!rows.length) return `<p class="empty">No authors are listed for this institution yet.</p>`;
  const expanded = state.leadsExpanded;
  const shown = expanded ? rows : rows.slice(0, LEAD_AUTHOR_LIMIT);
  const api = topics();
  const body = shown.map((row) => {
    const name = row.inAtlas
      ? `<a href="${escapeHtml(appUrl(`authors#author=${encodeURIComponent(row.author_id)}`))}">${escapeHtml(row.name)}</a>`
      : escapeHtml(row.name);
    const years = row.firstYear === null || row.lastYear === null ? "—" : `${row.firstYear}–${row.lastYear}`;
    const chips = row.topTopics.map((entry) => api.chip(entry.tag, entry.count)).join(" ");
    return `<tr><th scope="row">${name}</th><td class="num">${fmt(row.worksHere)}</td><td class="num">${fmt(row.firstHere)}</td>`
      + `<td class="num">${fmt(row.lastHere)}</td><td>${years}</td><td><div class="topic-chips">${chips || "—"}</div></td></tr>`;
  }).join("");
  const toggle = rows.length > LEAD_AUTHOR_LIMIT
    ? `<p><button type="button" class="inst-button" data-leads-toggle aria-expanded="${expanded}">${expanded ? "Show fewer" : `Show all ${fmt(rows.length)}`}</button></p>`
    : "";
  return `<div class="inst-table-scroll"><table class="inst-table"><caption>Authors ranked by works at this institution</caption>`
    + `<thead><tr><th scope="col">Name</th><th scope="col" class="num">Works here</th><th scope="col" class="num">First author</th>`
    + `<th scope="col" class="num">Last author</th><th scope="col">Active years</th><th scope="col">Top topics</th></tr></thead>`
    + `<tbody>${body}</tbody></table></div>${toggle}`;
}

function renderLeads() {
  const container = pick("#inst-leads");
  if (container) container.innerHTML = leadsHtml();
}

function listHtml(items, empty) {
  return items.length ? `<ol class="inst-list">${items.join("")}</ol>` : `<p class="empty">${escapeHtml(empty)}</p>`;
}

function collaboratorsHtml() {
  return listHtml(
    collaborators(state.works, state.instId, nameOf).map((entry) => `<li><a href="${escapeHtml(appUrl(`institution#inst=${encodeURIComponent(entry.inst_id)}`))}">${escapeHtml(entry.name)}</a> <span class="detail-meta">${plural(entry.works, "shared work")}</span></li>`),
    "No other institutions appear on these works."
  );
}

function journalsHtml() {
  return listHtml(
    topJournals(state.works).map((entry) => `<li>${escapeHtml(entry.journal)} <span class="detail-meta">${plural(entry.count, "work")}</span></li>`),
    "No journal names are recorded for these works."
  );
}

function citedHtml() {
  return listHtml(
    mostCited(state.works).map((work) => {
      const title = escapeHtml(work.title || "Untitled work");
      const doi = safeHttpUrl(work.doi);
      const heading = doi ? `<a href="${escapeHtml(doi)}">${title}</a>` : title;
      const meta = [work.year, work.journal, plural(Number(work.cited_by_count) || 0, "citation")].filter((part) => part !== undefined && part !== null && part !== "").map((part) => escapeHtml(part)).join(" · ");
      return `<li>${heading} <span class="detail-meta">${meta}</span></li>`;
    }),
    "No works are recorded for this institution."
  );
}

function sectionHtml(id, heading, body, intro = "") {
  return `<section class="inst-section atlas-card" id="section-${id}" aria-labelledby="heading-${id}"><h2 id="heading-${id}" tabindex="-1">${heading}</h2>${intro}${body}</section>`;
}

function disclosureHtml(network) {
  return network.disclosure ? `<p class="inst-network-disclosure">Disclosure: ${escapeHtml(network.disclosure)}</p>` : "";
}

function networkNameHtml(network) {
  return network.url
    ? `<a href="${escapeHtml(network.url)}">${escapeHtml(network.name)}</a>`
    : escapeHtml(network.name);
}

// Host institutions named from the institution list (linked to their pages). A host outside the
// list falls back to the steward's name, unlinked.
function hostLinksHtml(network) {
  const known = network.host_institution_ids.filter((id) => state.byId.has(id));
  if (!known.length) return network.steward ? escapeHtml(network.steward) : "";
  return known
    .map((id) => `<a href="${escapeHtml(appUrl(`institution#inst=${encodeURIComponent(id)}`))}">${escapeHtml(nameOf(id))}</a>`)
    .join(" and ");
}

function linkListHtml(label, items) {
  return `<p class="inst-network-label">${escapeHtml(label)}</p><ul class="inst-network-people">${items.join("")}</ul>`;
}

// A consortium this institution hosts: logo, name, steward, description, focus areas, contributors.
function hostedNetworkHtml(network) {
  const logo = network.logo
    ? `<img class="inst-network-logo" src="${escapeHtml(classicUrl(network.logo.path))}" alt="" width="64" height="64" loading="lazy">`
    : "";
  const steward = network.steward
    ? `<p class="inst-network-steward">Hosted by ${network.steward_source
      ? `<a href="${escapeHtml(network.steward_source)}">${escapeHtml(network.steward)}</a>`
      : escapeHtml(network.steward)}</p>`
    : "";
  const description = network.description
    ? `<p class="inst-network-description">“${escapeHtml(network.description)}”${network.description_source ? ` (<a href="${escapeHtml(network.description_source)}">source</a>)` : ""}</p>`
    : "";
  const focus = network.focus_areas.length
    ? `<p class="inst-network-label">Focus areas</p><ul class="inst-network-focus">${network.focus_areas.map((area) => `<li class="inst-chip">${escapeHtml(area)}</li>`).join("")}</ul>`
    : "";
  const people = network.atlas_contributors.length
    ? linkListHtml("Contributors with Atlas author profiles", network.atlas_contributors.map((person) =>
      `<li><a href="${escapeHtml(appUrl(`authors#author=${encodeURIComponent(person.author_id)}`))}">${escapeHtml(person.name)}</a></li>`))
    : "";
  const summary = contributorSummary(network);
  const related = network.related_links.length
    ? linkListHtml("Related links", network.related_links.map((link) =>
      `<li><a href="${escapeHtml(link.url)}">${escapeHtml(link.label)}</a></li>`))
    : "";
  return `<article class="inst-network"><div class="inst-network-head">${logo}`
    + `<div class="inst-network-title"><h3>${networkNameHtml(network)}</h3>${steward}</div></div>`
    + description + focus + people
    + (summary ? `<p class="data-note">${escapeHtml(summary)}</p>` : "")
    + related + disclosureHtml(network) + `</article>`;
}

// A network whose researchers are listed contributors: one pointer sentence and its disclosure.
function memberNetworkHtml(network) {
  const hosts = hostLinksHtml(network);
  return `<p class="inst-network-pointer">Researchers here are listed contributors to the ${networkNameHtml(network)}${hosts ? `, hosted by ${hosts}` : ""}.</p>`
    + disclosureHtml(network);
}

function networksSectionHtml(found) {
  if (!found.hosted.length && !found.member.length) return "";
  return sectionHtml("networks", "Research networks",
    found.hosted.map(hostedNetworkHtml).join("") + found.member.map(memberNetworkHtml).join(""));
}

function renderInstitution(payload, known, networks) {
  const institution = {...(known || {}), ...(payload.institution || {}), inst_id: state.instId};
  state.works = plasticWorks(payload.works);
  state.experts = Array.isArray(payload.experts) ? payload.experts : [];
  state.filterTag = "";
  state.leadsExpanded = false;
  const stats = summaryStats(payload);
  root().innerHTML = headerHtml(institution)
    + networksSectionHtml(networksForInstitution(networks, state.instId))
    + sectionHtml("summary", "Summary", tilesHtml(stats))
    + sectionHtml("years", "Plastic-related works per year", yearsHtml(state.works))
    + sectionHtml("topics", "Topics", `<div id="inst-topics"></div>`)
    + sectionHtml("experts", "Lead authors", `<div id="inst-leads"></div>`)
    + sectionHtml("collaborators", "Collaborating institutions", collaboratorsHtml(), `<p class="data-note">Other institutions on the same plastic-related works.</p>`)
    + sectionHtml("journals", "Top journals", journalsHtml())
    + sectionHtml("cited", "Most-cited works", citedHtml())
    + sectionHtml("publications", "Publications", `<p id="inst-publications-note" class="inst-filter-note" aria-live="polite"></p><div id="inst-publications"></div>`,
      `<p class="data-note">Plastic-related works with a California author. Use the topic tags above to narrow the list.</p>`);
  renderTopics();
  renderLeads();
  state.table = mountWorksTable(pick("#inst-publications"), {
    hint: "Select a topic above to narrow this list."
  });
  updateTable();
}

function renderUnavailable(known) {
  root().innerHTML = headerHtml(known)
    + noticeHtml("Detailed data for this institution is not in the current export. Search for another institution, or return to the leaderboard.");
}

function scrollToSection() {
  if (!state.section) return;
  const target = pick(`#section-${state.section} h2`);
  if (!target) return;
  target.scrollIntoView({block: "start"});
  target.focus({preventScroll: true});
}

async function render() {
  const token = ++state.token;
  const {instId, section} = parseInstitutionHash(window.location.hash);
  state.section = section;
  state.instId = instId;
  if (!instId) {
    state.loadedId = "";
    state.payload = null;
    await showSearch(token, "");
    return;
  }
  if (state.loadedId === instId && state.payload) {
    scrollToSection();
    return;
  }
  state.loadedId = "";
  state.payload = null;
  root().innerHTML = `<p class="result-count" role="status" aria-live="polite">Loading institution…</p>`;
  try {
    // The networks card is decided before the first paint, so the page never shifts after mounting.
    const [, payload, networks] = await Promise.all([
      loadInstitutionList(),
      loadJson(`institution_works/${encodeURIComponent(instId)}.json`, {optional: true}),
      loadNetworks(),
    ]);
    if (token !== state.token) return;
    const known = state.byId.get(instId) || null;
    if (!payload) {
      if (known) renderUnavailable(known);
      else await showSearch(token, "We could not find that institution. Search below for another one.");
      return;
    }
    state.payload = payload;
    state.loadedId = instId;
    renderInstitution(payload, known, networks);
    scrollToSection();
  } catch (error) {
    if (token === state.token) renderFailed(error);
  }
}

function toggleTopic(tag) {
  state.filterTag = state.filterTag === tag ? "" : tag;
  renderTopics();
  updateTable();
  const button = [...root().querySelectorAll("[data-topic]")].find((item) => item.dataset.topic === tag);
  if (button) button.focus();
}

function onClick(event) {
  const topic = event.target.closest("[data-topic]");
  if (topic) {
    toggleTopic(topic.dataset.topic);
    return;
  }
  if (event.target.closest("[data-topic-clear]")) {
    state.filterTag = "";
    renderTopics();
    updateTable();
    const heading = pick("#heading-topics");
    if (heading) heading.focus();
    return;
  }
  if (event.target.closest("[data-leads-toggle]")) {
    state.leadsExpanded = !state.leadsExpanded;
    renderLeads();
    const toggle = pick("[data-leads-toggle]");
    if (toggle) toggle.focus();
    return;
  }
  if (event.target.closest("#institution-retry")) render();
}

function onInput(event) {
  if (event.target.id === "institution-search") renderSearchResults(event.target.value);
}

// Entry point for src/institution.md.
export async function mountInstitution() {
  const api = topics();
  if (api && typeof api.injectCss === "function") api.injectCss();
  root().addEventListener("click", onClick);
  root().addEventListener("input", onInput);
  window.addEventListener("hashchange", () => { render(); });
  await render();
}
