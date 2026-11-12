// Institutions page logic (AT-5e). Lift-and-shift of the classic Institutions tab in site/index.html
// (institutionMetrics, topic bars and chips, cards and tiers views, the institution map, controls,
// comparators and hash state). Markup lives in src/institutions.md; the tiers helpers in inst_tiers.js;
// shared map code in svg_map.js. Nothing touches the DOM until mountInstitutions() runs.
import "./shared/topics.js";
import {loadJson, escapeHtml, classicUrl} from "./atlas.js";
import {monitoringView} from "./monitoring_view.js";
import {monitoringMap, attachMapInteractions, ensureCaBasemap, caBasemapFeatures, caBasemapState} from "./svg_map.js";
import {instTiers} from "./inst_tiers.js";

const $ = (id) => document.getElementById(id);
// AtlasTopics is set by shared/topics.js (imported above); read it at call time, as experts_model.js does.
const topics = () => globalThis.AtlasTopics;
const countFormat = new Intl.NumberFormat("en-US");
const TIERS_PATH = "bundle/inst_tiers.json";
const LEGACY_TAB = "institutions";

// Page state (classic: the institution* variables and the institution fields of the shared state object).
const state = {
  data: null, // {index, institutions}
  worksByInst: new Map(), // inst_id -> plastic-related works
  includeCollaborators: false,
  instView: "tiers", // inst_view hash parameter: "tiers" (default) or "list"
  institutionViewType: "", // atlas_type chip; "" means all types
  institutionSort: "tagged",
  institutionPrimaryTopic: "",
};
// Tiers payload: idle | loading | ready | failed (classic tiersStatus / tiersRows).
const tiers = {status: "idle", rows: []};
// Institution map state (classic institutionMap* variables).
const map = {
  points: [],
  view: null, // null means the statewide view
  selection: null, // {ids} for the selected marker or cluster
  rendered: [],
  frame: 0,
  lacking: 0, // qualifying institutions without coordinates
  container: null,
};

// Pure helpers (DOM-free; exported for tests/test_framework_institutions.py via the runtime check).
export function taggedWork(work) {
  return work && work.plastic_related === true;
}

export function buildInstitutionWorksIndex(index) {
  const worksByInst = new Map();
  ((index && index.works) || []).forEach((work) => {
    if (!taggedWork(work)) return;
    new Set(work.institution_ids || []).forEach((id) => {
      if (!worksByInst.has(id)) worksByInst.set(id, []);
      worksByInst.get(id).push(work);
    });
  });
  return worksByInst;
}

export function metricValue(value) {
  return value === null || value === undefined || value === "" || !Number.isFinite(Number(value)) ? null : Number(value);
}

export function metricNumber(value) {
  const number = metricValue(value);
  return number === null ? "—" : countFormat.format(number);
}

export function institutionMetrics(institution, worksByInst) {
  const works = worksByInst.get(institution.inst_id) || [];
  const years = works.map((work) => Number(work.year)).filter(Number.isFinite);
  const latestYear = years.length ? Math.max(...years) : null;
  const firstYear = years.length ? Math.min(...years) : null;
  const byYear = new Map();
  years.forEach((year) => byYear.set(year, (byYear.get(year) || 0) + 1));
  const trendYears = firstYear === null ? [] : Array.from({ length: latestYear - firstYear + 1 }, (_, index) => firstYear + index);
  const series = trendYears.map((year) => byYear.get(year) || 0);
  const recentCutoff = latestYear === null ? null : latestYear - 4;
  return { institution, works, taggedCount: works.length, recentCount: recentCutoff === null ? 0 : years.filter((year) => year >= recentCutoff).length, trendYears, series, topics: topics().weights(works) };
}

export function primaryTopic(metric) {
  const entry = metric.topics.find(([tag]) => !topics().isMatrix(tag));
  return entry ? entry[0] : "";
}

export function topicShare(metric, tag) {
  const entry = metric.topics.find(([name]) => name === tag);
  return { count: entry ? entry[1] : 0, share: metric.taggedCount ? (entry ? entry[1] : 0) / metric.taggedCount : 0 };
}

export function institutionComparator(sortKey) {
  const byName = (a, b) => String(a.institution.name).localeCompare(String(b.institution.name));
  if (sortKey === "name") return byName;
  if (sortKey === "recent") return (a, b) => b.recentCount - a.recentCount || b.taggedCount - a.taggedCount || byName(a, b);
  if (sortKey.startsWith("share:")) {
    const tag = sortKey.slice(6);
    return (a, b) => { const x = topicShare(a, tag); const y = topicShare(b, tag); return y.share - x.share || y.count - x.count || b.taggedCount - a.taggedCount || byName(a, b); };
  }
  return (a, b) => b.taggedCount - a.taggedCount || b.recentCount - a.recentCount || byName(a, b);
}

// Framework-relative URL (the Experts page sits next to this one under app/).
function appUrl(path) {
  return new URL(path, document.baseURI).href;
}

// Hash parameters. The legacy "#institutions?..." prefix is accepted; links are written without it.
function hashParams() {
  let raw = window.location.hash.replace(/^#/, "");
  if (raw === LEGACY_TAB) raw = "";
  else if (raw.startsWith(`${LEGACY_TAB}?`)) raw = raw.slice(LEGACY_TAB.length + 1);
  return new URLSearchParams(raw);
}

function readHash() {
  const params = hashParams();
  state.instView = instTiers.viewFromParams(params);
  state.includeCollaborators = params.get("collab") === "1";
}

function writeHash() {
  const params = new URLSearchParams();
  if (state.includeCollaborators) params.set("collab", "1");
  instTiers.applyViewParam(params, state.instView);
  const query = params.toString();
  const next = query ? `#${query}` : "";
  if (window.location.hash !== next) window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${next}`);
}

// Topic bar, chips and links (HTML builders, as in the classic page).
// 100%-stacked bar of topic counts; hue fills only, 2px white gaps come from the segment strokes.
function topicBar(entries, name) {
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  if (!total) return '<p class="topic-bar-note">No topic tags yet</p>';
  let x = 0;
  const share = (count) => Math.round((count / total) * 100);
  const segments = entries.map(([tag, count]) => {
    const width = (count / total) * 1000;
    const rect = `<rect x="${x.toFixed(2)}" y="0" width="${width.toFixed(2)}" height="14" fill="${topics().svgFill ? topics().svgFill(tag) : topics().color(tag)}"><title>${escapeHtml(topics().label(tag))}: ${count} work${count === 1 ? "" : "s"} (${share(count)}%)</title></rect>`;
    x += width;
    return rect;
  }).join("");
  const summary = entries.slice(0, 5).map(([tag, count]) => `${topics().label(tag)} ${share(count)}%`).join(", ");
  return `<svg class="topic-bar" viewBox="0 0 1000 14" preserveAspectRatio="none" role="img" aria-label="${escapeHtml(`Topic mix of ${name}: ${summary}${entries.length > 5 ? ", and others" : ""}`)}">${segments}</svg>`;
}

function topicChipList(entries, limit) {
  const shown = entries.slice(0, limit).map(([tag, count]) => topics().chip(tag, count)).join("");
  const rest = entries.length - limit;
  return shown ? `<div class="topic-chips" aria-label="Top topics with work counts">${shown}${rest > 0 ? `<span class="topic-chip matrix">+${rest} more</span>` : ""}</div>` : "";
}

function topExpertsHtml(institution) {
  const experts = institution.top_experts || [];
  if (!experts.length) return "";
  const items = experts.map((expert) => {
    const name = expert.in_atlas_index ? `<a class="expert-name" href="${escapeHtml(appUrl(`experts#author=${encodeURIComponent(expert.author_id)}`))}">${escapeHtml(expert.name || expert.author_id)}</a>` : `<span class="expert-name">${escapeHtml(expert.name || expert.author_id)}</span>`;
    return `<li>${name}<span class="detail-meta">${expert.works} ${expert.works === 1 ? "work" : "works"}</span>${expert.topic ? topics().chip(expert.topic) : ""}</li>`;
  }).join("");
  return `<div class="top-experts"><h3>Top experts</h3><ul>${items}</ul><a href="${escapeHtml(classicUrl(`sem.html#inst=${encodeURIComponent(institution.inst_id)}&section=experts`))}">All experts at this institution</a></div>`;
}

function collaboratorLine(institution) {
  if (institution.ca_flag) return "";
  const n = Number(institution.work_count) || 0;
  return `<p class="collab-line"><span class="collab-badge">Collaborator outside California</span> Appears through ${n} ${n === 1 ? "work" : "works"} co-authored with California researchers.</p>`;
}

function publicationsLink(institutionId) {
  return `<a class="button-link institution-publications-link" href="${escapeHtml(classicUrl(`sem.html#inst=${encodeURIComponent(institutionId)}`))}">View publications</a>`;
}

function sparkline(metric) {
  const values = metric.series;
  if (!values.length) return '<span class="data-note">No yearly trend</span>';
  const max = Math.max(...values, 1);
  const width = 120;
  const height = 28;
  const points = values.map((value, index) => `${values.length === 1 ? width / 2 : (index / (values.length - 1)) * width},${height - (value / max) * (height - 4) - 2}`).join(" ");
  const label = `${metric.institution.name}: ${values.join(", ")} tagged works by year`;
  return `<svg class="sparkline" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(label)}"><polyline points="${points}"></polyline>${values.map((value, index) => { const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width; const y = height - (value / max) * (height - 4) - 2; return `<circle cx="${x}" cy="${y}" r="2.2"></circle>`; }).join("")}</svg>`;
}

function institutionExpertLink(institutionId) {
  return `<button class="institution-expert-link" type="button" data-institution-id="${escapeHtml(institutionId)}">View experts</button>`;
}

// Classic openInstitutionExperts switched tabs; the Experts page is its own Framework page now.
function openInstitutionExperts(institutionId) {
  window.location.assign(appUrl(`experts#institution=${encodeURIComponent(institutionId)}`));
}

function primaryTopicLine(metric) {
  const tag = primaryTopic(metric);
  const note = state.institutionSort.startsWith("share:") ? (() => { const t = state.institutionSort.slice(6); const v = topicShare(metric, t); return ` <span class="basis-note">${escapeHtml(topics().label(t))}: ${Math.round(v.share * 100)}% of works</span>`; })() : "";
  return `<p class="primary-topic-line">Primary topic: ${tag ? topics().chip(tag, topicShare(metric, tag).count) : '<span class="basis-note">not yet tagged</span>'}${note}</p>`;
}

// Map: drawing, details and clusters (classic drawInstitutionMap and friends).
function institutionMapCurrentView() {
  return map.view || monitoringMap.viewBox("statewide");
}

function scheduleInstitutionMapDraw() {
  if (map.frame) return;
  map.frame = window.requestAnimationFrame(() => { map.frame = 0; drawInstitutionMap(); });
}

function institutionClusterKey(cluster) {
  return cluster.items.map((metric) => metric.institution.inst_id).sort()[0];
}

function drawInstitutionMap() {
  if (!state.data) return;
  ensureCaBasemap(() => drawInstitutionMap());
  const container = $("institution-map");
  if (!map.points.length) {
    container.innerHTML = '<p class="empty">No California institutions with coordinates match this filter.</p>';
    map.rendered = [];
    return;
  }
  const view = institutionMapCurrentView();
  const clusters = monitoringMap.clusterPoints(map.points, view);
  map.rendered = clusters;
  const selected = new Set(map.selection ? map.selection.ids : []);
  const focused = document.activeElement && container.contains(document.activeElement) ? document.activeElement.getAttribute("data-cluster-key") : null;
  const maxWeight = Math.max(1, ...clusters.map((cluster) => cluster.weight));
  const fontSize = view.width * 0.022;
  const markers = clusters.map((cluster, index) => {
    const clustered = cluster.items.length > 1;
    const radius = view.width * (0.014 + 0.03 * Math.sqrt(cluster.weight / maxWeight));
    const label = clustered ? `${cluster.items.length} institutions, ${cluster.weight} plastic-related works` : `${cluster.items[0].institution.name}, ${cluster.weight} plastic-related works`;
    const isSelected = cluster.items.some((metric) => selected.has(metric.institution.inst_id));
    const halo = isSelected ? `<circle class="marker-halo" cx="${cluster.x}" cy="${cluster.y}" r="${radius * 1.4}"/>` : "";
    return `<g class="monitoring-marker institution-marker${clustered ? " cluster" : ""}${isSelected ? " selected" : ""}" role="button" tabindex="0" aria-pressed="${isSelected}" aria-label="${escapeHtml(`${label}. Select for details.`)}" data-cluster-index="${index}" data-cluster-key="${escapeHtml(institutionClusterKey(cluster))}"><title>${escapeHtml(label)}</title><circle class="marker-body" cx="${cluster.x}" cy="${cluster.y}" r="${radius}"/>${halo}${clustered ? `<text x="${cluster.x}" y="${cluster.y}" font-size="${fontSize}" text-anchor="middle" dominant-baseline="central">${cluster.items.length}</text>` : ""}</g>`;
  }).join("");
  const basemapFeatures = caBasemapFeatures();
  const basemap = basemapFeatures
    ? `<path class="map-state-waters" fill-rule="evenodd" d="${basemapFeatures.state_waters}"/><path class="map-land" fill-rule="evenodd" d="${basemapFeatures.land}"/>`
    : "";
  container.innerHTML = `<svg class="monitoring-map-svg" viewBox="${view.x} ${view.y} ${view.width} ${view.height}" preserveAspectRatio="xMidYMid meet" role="group" aria-label="${escapeHtml(`California institution map: ${map.points.length} institutions, ${clusters.length} markers`)}"><rect class="map-sea" x="${view.x}" y="${view.y}" width="${view.width}" height="${view.height}"/>${basemap}${monitoringMap.placeLabels(view, clusters.map((cluster) => ({ x: cluster.x, y: cluster.y, r: view.width * (0.014 + 0.03 * Math.sqrt(cluster.weight / maxWeight)) })))}<g class="monitoring-markers">${markers}</g></svg>`;
  if (focused !== null) {
    const marker = [...container.querySelectorAll("[data-cluster-key]")].find((item) => item.getAttribute("data-cluster-key") === focused);
    (marker || container).focus({ preventScroll: true });
  }
  const basemapNote = caBasemapState() === "failed" ? " Basemap unavailable; markers only." : basemapFeatures ? "" : " Basemap loading.";
  $("institution-map-note").textContent = `${state.includeCollaborators ? "The map shows California institutions only; out-of-state collaborators have no California location. " : ""}${map.points.length} California institution${map.points.length === 1 ? "" : "s"} mapped${map.lacking ? `; ${map.lacking} qualifying institution${map.lacking === 1 ? "" : "s"} lack coordinates` : ""}. Zoom ${monitoringMap.zoomScale(view).toFixed(1)}x; nearby institutions are grouped into numbered clusters that split as you zoom in.${basemapNote}`;
}

function renderInstitutionMapDetails() {
  const panel = $("institution-map-details");
  const ids = map.selection ? map.selection.ids : [];
  const byId = new Map(map.points.map((point) => [point.item.institution.inst_id, point.item]));
  const metrics = ids.map((id) => byId.get(id)).filter(Boolean).sort((a, b) => b.taggedCount - a.taggedCount);
  if (!metrics.length) { panel.innerHTML = ""; return; }
  const shown = metrics.slice(0, 5);
  const blocks = shown.map((metric) => {
    const institution = metric.institution;
    const years = metric.works.length ? `${metric.trendYears[0]}–${metric.trendYears[metric.trendYears.length - 1]}` : (institution.years || []).length ? `${Math.min(...institution.years)}–${Math.max(...institution.years)}` : "—";
    const stat = (name, value) => `<div><dt>${name}</dt><dd>${escapeHtml(value)}</dd></div>`;
    return `<section class="map-inst"><h4>${escapeHtml(institution.name)}</h4><div><span class="chip">${escapeHtml(institution.atlas_type || "other")}</span></div><dl class="map-inst-stats">${stat("Works", metricNumber(institution.work_count))}${stat("Plastic-related works", metricNumber(metric.taggedCount))}${stat("Authors", metricNumber(institution.author_count))}${stat("Years active", years)}${stat("Recent 5 years", metricNumber(metric.recentCount))}</dl>${topicBar(metric.topics, institution.name)}${topicChipList(metric.topics, 3)}${topExpertsHtml(institution)}<div class="institution-actions"><button class="institution-expert-link" type="button" data-institution-id="${escapeHtml(institution.inst_id)}">Show experts</button>${publicationsLink(institution.inst_id)}</div></section>`;
  }).join("");
  panel.innerHTML = `<div class="map-details-card"><div class="map-details-head"><h3>${metrics.length} institution${metrics.length === 1 ? "" : "s"} selected</h3><div class="map-details-actions">${metrics.length > 1 ? "<button type=\"button\" data-map-fit>Zoom to these</button>" : ""}<button type="button" data-map-close>Close</button></div></div>${blocks}${metrics.length > shown.length ? `<p class="data-note">Showing the ${shown.length} largest of ${metrics.length} institutions; zoom in to separate the rest.</p>` : ""}</div>`;
}

function selectInstitutionCluster(index) {
  const cluster = map.rendered[index];
  if (!cluster) return;
  map.selection = { ids: cluster.items.map((metric) => metric.institution.inst_id) };
  renderInstitutionMapDetails();
  drawInstitutionMap();
}

function clusterMap(metrics) {
  const located = metrics.filter((metric) => metric.institution.ca_flag && monitoringView.coordinates({ lat: metric.institution.lat, lon: metric.institution.lon }) !== null);
  map.points = located.map((metric) => {
    const [x, y] = monitoringMap.project(Number(metric.institution.lon), Number(metric.institution.lat));
    return { x, y, weight: metric.taggedCount, item: metric };
  });
  map.lacking = metrics.filter((metric) => metric.institution.ca_flag).length - located.length;
  if (map.selection) {
    const available = new Set(map.points.map((point) => point.item.institution.inst_id));
    const ids = map.selection.ids.filter((id) => available.has(id));
    map.selection = ids.length ? { ids } : null;
  }
  renderInstitutionMapDetails();
  drawInstitutionMap();
}

// Controls, comparators and the tiers view.
function setupInstitutionControls(all) {
  const topicTags = topics().sortTags([...new Set(all.flatMap((metric) => metric.topics.map(([tag]) => tag)).filter((tag) => !topics().isMatrix(tag)))]);
  const sortSelect = $("institution-sort");
  const filterSelect = $("institution-topic-filter");
  const signature = topicTags.join("|");
  if (sortSelect.dataset.signature !== signature) {
    sortSelect.dataset.signature = signature;
    sortSelect.innerHTML = '<option value="tagged">Tagged works (most first)</option><option value="recent">Recent 5-year works</option><option value="name">Name (A to Z)</option>' + topicTags.map((tag) => `<option value="share:${escapeHtml(tag)}">Share of topic: ${escapeHtml(topics().label(tag))}</option>`).join("");
    filterSelect.innerHTML = '<option value="">All primary topics</option>' + topicTags.map((tag) => `<option value="${escapeHtml(tag)}">${escapeHtml(topics().label(tag))}</option>`).join("");
  }
  if (![...sortSelect.options].some((option) => option.value === state.institutionSort)) state.institutionSort = "tagged";
  if (![...filterSelect.options].some((option) => option.value === state.institutionPrimaryTopic)) state.institutionPrimaryTopic = "";
  sortSelect.value = state.institutionSort;
  filterSelect.value = state.institutionPrimaryTopic;
}

function ensureInstitutionTiers() {
  if (tiers.status !== "idle") return;
  tiers.status = "loading";
  loadJson(TIERS_PATH)
    .then((payload) => { if (!payload || !Array.isArray(payload.tiers) || !payload.tiers.length) throw new Error("no tiers"); tiers.rows = payload.tiers; tiers.status = "ready"; })
    .catch(() => { tiers.status = "failed"; })
    .then(() => { if (tiers.status === "ready") renderInstitutions(); });
}

function renderInstitutionTiers() {
  const root = $("institutions-root");
  const on = tiers.status === "ready" && state.instView !== "list";
  $("institution-view-field").hidden = tiers.status !== "ready";
  $("institution-tiers").hidden = !on;
  $("institution-list").hidden = on;
  root.querySelectorAll("[data-inst-view]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.instView === (on ? "tiers" : "list"))));
  if (!on) return;
  $("institution-tier-groups").innerHTML = instTiers.tiersHtml(tiers.rows, state.institutionViewType);
  const groups = instTiers.groupTiers(tiers.rows, state.institutionViewType);
  $("institution-count").textContent = `${groups.reduce((n, g) => n + g.rows.length, 0)} California institutions in ${groups.length} tiers, sorted by fractional works within each tier`;
}

function institutionCardHtml(metric) {
  const institution = metric.institution;
  return `<article class="card institution-card" data-institution-id="${escapeHtml(institution.inst_id)}"><div class="card-header"><h2>${escapeHtml(institution.name)}</h2><span class="chip">${escapeHtml(institution.atlas_type || "other")}</span></div>${collaboratorLine(institution)}${primaryTopicLine(metric)}<p class="institution-stats"><span>${metric.taggedCount} tagged works all time</span><span>${metric.recentCount} in recent 5 years</span><span>${metric.works.length ? `${metric.trendYears[0]}–${metric.trendYears[metric.trendYears.length - 1]}` : "Year unavailable"}</span></p><div class="institution-topics">${topicBar(metric.topics, institution.name)}${topicChipList(metric.topics, 5)}</div>${sparkline(metric)}${topExpertsHtml(institution)}<div class="institution-actions">${institution.ca_flag ? institutionExpertLink(institution.inst_id) : ""}${publicationsLink(institution.inst_id)}</div></article>`;
}

function renderInstitutions() {
  if (!state.data) return;
  ensureInstitutionTiers();
  const all = (state.data.institutions.institutions || []).filter((institution) => state.includeCollaborators || institution.ca_flag).map((institution) => institutionMetrics(institution, state.worksByInst)).filter((metric) => metric.taggedCount > 0);
  $("institution-collab").checked = state.includeCollaborators;
  const types = [...new Set(all.map((metric) => metric.institution.atlas_type || "other"))].sort();
  const selected = state.institutionViewType;
  setupInstitutionControls(all);
  const topicFilter = state.institutionPrimaryTopic;
  const filtered = all.filter((metric) => (!selected || (metric.institution.atlas_type || "other") === selected) && (!topicFilter || primaryTopic(metric) === topicFilter)).sort(institutionComparator(state.institutionSort));
  $("institution-type-chips").innerHTML = [`<button class="chip-button institution-type-chip" type="button" data-institution-type="" aria-pressed="${selected === ""}">All types</button>`, ...types.map((type) => `<button class="chip-button institution-type-chip" type="button" data-institution-type="${escapeHtml(type)}" aria-pressed="${selected === type}">${escapeHtml(type)}</button>`)].join("");
  const sortLabel = $("institution-sort").selectedOptions[0]?.textContent || "";
  const topicNote = topicFilter ? `; primary topic: ${topics().label(topicFilter)}` : "";
  $("institution-count").textContent = `${filtered.length} of ${all.length} ${state.includeCollaborators ? "" : "California "}qualifying institution${all.length === 1 ? "" : "s"} shown${topicNote}; sorted by ${sortLabel.toLowerCase()}`;
  $("institution-list").innerHTML = filtered.length ? filtered.map(institutionCardHtml).join("") : '<p class="empty">No qualifying institutions match this type filter.</p>';
  $("institution-type-chips").querySelectorAll(".institution-type-chip").forEach((button) => button.addEventListener("click", () => { state.institutionViewType = button.dataset.institutionType; renderInstitutions(); }));
  $("institution-list").querySelectorAll(".institution-expert-link").forEach((button) => button.addEventListener("click", () => openInstitutionExperts(button.dataset.institutionId)));
  clusterMap(filtered);
  renderInstitutionTiers();
}

function bindEvents() {
  const root = $("institutions-root");
  // Delegated clicks: view switch and tier names (classic document-level listener, scoped to this page).
  root.addEventListener("click", (event) => {
    const view = event.target.closest("[data-inst-view]");
    if (view) { state.instView = view.dataset.instView; writeHash(); renderInstitutions(); return; }
    const name = event.target.closest("#institution-tier-groups .tier-name");
    if (name) openInstitutionExperts(name.dataset.institutionId);
  });
  $("institution-sort").addEventListener("change", (event) => { state.institutionSort = event.target.value; renderInstitutions(); });
  $("institution-topic-filter").addEventListener("change", (event) => { state.institutionPrimaryTopic = event.target.value; renderInstitutions(); });
  $("institution-collab").addEventListener("change", (event) => {
    state.includeCollaborators = event.target.checked;
    writeHash();
    if (state.data) renderInstitutions();
  });
  const mapContainer = $("institution-map");
  map.container = mapContainer;
  attachMapInteractions(mapContainer, { getView: institutionMapCurrentView, setView: (view) => { map.view = view; scheduleInstitutionMapDraw(); }, select: selectInstitutionCluster });
  $("institution-zoom-in").addEventListener("click", () => { map.view = monitoringMap.zoomView(institutionMapCurrentView(), 1.5); scheduleInstitutionMapDraw(); });
  $("institution-zoom-out").addEventListener("click", () => { map.view = monitoringMap.zoomView(institutionMapCurrentView(), 1 / 1.5); scheduleInstitutionMapDraw(); });
  $("institution-zoom-reset").addEventListener("click", () => { map.view = null; scheduleInstitutionMapDraw(); });
  $("institution-map-details").addEventListener("click", (event) => {
    const expertButton = event.target.closest(".institution-expert-link");
    if (expertButton) { openInstitutionExperts(expertButton.dataset.institutionId); return; }
    if (event.target.closest("[data-map-fit]")) {
      const byId = new Map(map.points.map((point) => [point.item.institution.inst_id, point]));
      const points = (map.selection ? map.selection.ids : []).map((id) => byId.get(id)).filter(Boolean).map((point) => [point.x, point.y]);
      const fitted = monitoringMap.fitView(points, institutionMapCurrentView());
      if (fitted) { map.view = fitted; drawInstitutionMap(); }
    }
    if (event.target.closest("[data-map-close]")) {
      map.selection = null;
      renderInstitutionMapDetails();
      drawInstitutionMap();
      map.container.focus({ preventScroll: true });
    }
  });
  window.addEventListener("hashchange", () => { readHash(); if (state.data) renderInstitutions(); });
}

// Entry point for src/institutions.md. Reads the hash, binds the page, then loads the S3.1 payloads.
export async function mountInstitutions() {
  readHash();
  bindEvents();
  try {
    const [index, institutions] = await Promise.all([loadJson("index.json"), loadJson("institutions.json")]);
    if (!index || !Array.isArray(index.authors) || !Array.isArray(index.works)) throw new Error("index.json does not match the S3.1 contract");
    state.data = {index, institutions};
    state.worksByInst = buildInstitutionWorksIndex(index);
    renderInstitutions();
  } catch (error) {
    $("institution-count").textContent = "Institution data unavailable.";
    $("institution-list").innerHTML = `<p class="empty">${escapeHtml(error.message)}<br>Run the site through a web server and rebuild the S3.1 data export.</p>`;
  }
}
