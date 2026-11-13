// Evidence map shell (Add-on A2 §5, EM-5b): shared filter state in the URL hash, A1 bit-set facets
// (AT-4 engine) and distinct works only. The page lists plastic-related works only (selectionFor adds
// that facet). Every view below the filters follows them (owner 2026-11-12): trend panel, heatmap and
// publication table get the matching rows on each change; heatmap cells narrow the publication table
// (owner 2026-11-13); the pipeline flow is static. Related resources moved to their own page.
// Pure helpers live in evidence_model.js; this file owns the DOM.
import "./shared/facets.js";
import "./shared/topics.js";
import {dataUrl, formatCount, loadJson} from "./atlas.js";
import {mountV3Flow} from "./v3_flow.js";
import {mountV4Trend} from "./v4_trend.js";
import {mountHeatmap} from "./ev_heatmap.js";
import {mountWorksTable, renderRecentCallout} from "./ev_table.js";
import {normaliseRows} from "./ev_table_model.js";
import {emptyState, formatHash, parseHash, sanitizeState, selectionFor} from "./evidence_model.js";

const $ = (id) => document.getElementById(id);

// Facets shown as checkbox groups. Plastic relevance is not a choice here: the page always applies it.
// The institution facet stays valid in the hash but has no UI.
const FACET_UI = [
  {key: "topic", label: "Topic", name: (label) => window.AtlasTopics.label(label)},
  {key: "ca_led", label: "Led from California", names: {yes: "Yes", no: "No"}},
  {key: "sector", label: "Sector"},
  {key: "type", label: "Work type"},
  {key: "oa", label: "Open access", names: {open: "Open access", closed: "Closed access"}}
];

const app = {
  index: null,
  known: null,
  yearLabels: [],
  state: emptyState(),
  rows: [],
  current: null,
  detail: null,
  views: [],
  // Work ids that match the page filters, and the heatmap selection (null when nothing is selected).
  lastIds: [],
  heatIds: null,
  table: null
};

function optionName(ui, label) {
  if (ui.name) return ui.name(label);
  return ui.names?.[label] ?? label;
}

function buildFilterGroups(container, index) {
  for (const ui of FACET_UI) {
    const labels = (index.facets[ui.key] || []).map((item) => item.label);
    // A facet with no options in the bundle gets no group, so the intro never lists a missing filter.
    if (!labels.length) continue;
    const fieldset = document.createElement("fieldset");
    fieldset.className = "ev-group";
    const legend = document.createElement("legend");
    legend.textContent = ui.label;
    fieldset.append(legend);
    labels.sort((a, b) => optionName(ui, a).localeCompare(optionName(ui, b)));
    for (const label of labels) {
      const row = document.createElement("label");
      row.className = "ev-option";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = label;
      const name = document.createElement("span");
      name.className = "ev-option-name";
      name.textContent = optionName(ui, label);
      const count = document.createElement("span");
      count.className = "ev-count";
      row.append(input, name, count);
      fieldset.append(row);
      app.rows.push({facet: ui.key, label, row, input, count});
    }
    container.append(fieldset);
  }
}

// Writes the form's controls back into a state object; hidden facets keep their hash values.
function readControls() {
  const facets = {};
  for (const key of Object.keys(app.state.facets)) {
    if (!FACET_UI.some((ui) => ui.key === key)) facets[key] = app.state.facets[key];
  }
  for (const row of app.rows) {
    if (row.input.checked) (facets[row.facet] = facets[row.facet] || []).push(row.label);
  }
  return {
    facets,
    yearFrom: Number($("evidence-year-from").value),
    yearTo: Number($("evidence-year-to").value),
    q: $("evidence-search").value
  };
}

function syncControls() {
  for (const row of app.rows) row.input.checked = (app.state.facets[row.facet] || []).includes(row.label);
  $("evidence-year-from").value = app.state.yearFrom ?? "";
  $("evidence-year-to").value = app.state.yearTo ?? "";
  $("evidence-search").value = app.state.q;
}

// The one place state changes: sanitize, mirror into the hash, then redraw.
function setState(next, {sync = false} = {}) {
  app.state = sanitizeState(next, app.known);
  if (sync) syncControls();
  history.replaceState(null, "", `${location.pathname}${location.search}${formatHash(app.state)}`);
  render();
}

function render() {
  const {sel, impossible} = selectionFor(app.state, app.yearLabels);
  const extra = app.state.q ? app.index.searchBits(app.state.q) : undefined;
  const result = impossible ? {total: 0, counts: {}} : app.index.counts(sel, extra);
  for (const row of app.rows) {
    const count = result.counts[`${row.facet}|${row.label}`] ?? 0;
    row.count.textContent = formatCount(count);
    row.row.classList.toggle("ev-zero", count === 0);
  }
  app.current = {sel, impossible, extra};
  $("evidence-count").textContent = `${formatCount(result.total)} distinct works match`;
  notifyViews();
}

// Pushes the matching rows to every reactive view. Views mount asynchronously, so a view that
// mounts later gets the current rows from notifyViews() once it registers.
function notifyViews() {
  if (!app.current || !app.detail) return;
  const {sel, impossible, extra} = app.current;
  const ids = impossible ? [] : app.index.selectedIds(sel, extra);
  const rows = ids.map((id) => app.detail.get(id)).filter(Boolean);
  const filtered = formatHash(app.state) !== "";
  app.lastIds = ids;
  for (const view of app.views) {
    try {
      view({ids, rows, filtered});
    } catch (error) {
      console.error(error);
    }
  }
}

// The publication table shows the page-filtered works, narrowed to the heatmap selection when one exists.
function applyTable() {
  if (!app.table) return;
  const ids = app.heatIds ? app.lastIds.filter((id) => app.heatIds.has(id)) : app.lastIds;
  app.table.update(ids);
}

let detailPromise = null;
function loadDetail() {
  if (!detailPromise) {
    detailPromise = loadJson("works_detail.json")
      .then((payload) => new Map(normaliseRows(payload).map((row) => [row.work_id, row])))
      .catch((error) => {
        detailPromise = null;
        throw error;
      });
  }
  return detailPromise;
}

function bindFilters() {
  const form = $("evidence-filters");
  let timer = 0;
  form.addEventListener("submit", (event) => event.preventDefault());
  form.addEventListener("change", () => setState(readControls()));
  form.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => setState(readControls()), 150);
  });
  $("evidence-reset").addEventListener("click", () => setState(emptyState(), {sync: true}));
  window.addEventListener("hashchange", () => setState(parseHash(location.hash), {sync: true}));
}

// A view section stays hidden until its container has content, so a failed view leaves no empty heading.
function settleSection(container, mounted) {
  const section = container.closest("section");
  section.hidden = true;
  return mounted.then(
    () => {
      section.hidden = !container.hasChildNodes();
    },
    () => {
      section.hidden = true;
    }
  );
}

function showStatus(text) {
  $("evidence-status").textContent = text;
}

function showFailed() {
  const retry = document.createElement("button");
  retry.type = "button";
  retry.textContent = "Retry";
  retry.addEventListener("click", () => loadBundle());
  $("evidence-status").replaceChildren("Could not load the evidence data. ", retry);
}

let bound = false;

// Loads the bundle and wires the controls once. A failed load shows a retry button; a retry re-runs this.
async function loadBundle() {
  showStatus("Loading the evidence bundle…");
  let index;
  try {
    index = await window.AtlasFacets.BitmaskIndex.load(dataUrl("bundle/"));
  } catch {
    showFailed();
    return;
  }
  app.index = index;
  app.known = Object.fromEntries(
    Object.keys(index.facets).map((key) => [key, new Set(index.facets[key].map((item) => item.label))])
  );
  app.yearLabels = (index.facets.year || []).map((item) => item.label);
  if (!bound) {
    buildFilterGroups($("evidence-groups"), index);
    bindFilters();
    bound = true;
  }
  app.state = sanitizeState(parseHash(location.hash), app.known);
  setState(app.state, {sync: true});
  showStatus(`Loaded ${formatCount(index.N)} works.`);
  await mountViews(index);
}

let viewsMounted = false;
// Trend panel, heatmap, publication table and the "new in the last 2 weeks" callout.
async function mountViews(index) {
  if (viewsMounted) return;
  viewsMounted = true;
  const trendPromise = mountV4Trend($("ev-v4"), index);
  settleSection($("ev-v4"), trendPromise);
  let detail;
  try {
    detail = await loadDetail();
  } catch {
    $("ev-table").textContent = "Could not load the publication details.";
    return;
  }
  app.detail = detail;
  const plasticWorks = [...detail.values()].filter((row) => row.plastic_related === true);
  renderRecentCallout($("ev-recent"), plasticWorks, new Date());
  const heatmap = mountHeatmap($("ev-heatmap"), {
    onSelect: (ids) => {
      app.heatIds = ids ? new Set(ids) : null;
      applyTable();
    }
  });
  $("ev-heatmap").closest("section").hidden = false;
  app.table = mountWorksTable($("ev-table"));
  app.views.push(({rows}) => heatmap.update(rows), () => applyTable());
  notifyViews();
  try {
    const trend = await trendPromise;
    if (trend && typeof trend.update === "function") {
      app.views.push(({rows, filtered}) => trend.update(rows, {filtered}));
      if (formatHash(app.state) !== "") notifyViews();
    }
  } catch {
    // settleSection already hid the trend section.
  }
}

export async function mountEvidence() {
  // V-3 (EM-6) needs only the methods card export, so it renders independently of the bundle.
  mountV3Flow($("ev-v3"));
  await loadBundle();
}
