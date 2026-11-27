// Evidence map shell (Add-on A2 §5, EM-5b): shared filter state in the URL hash, A1 bit-set facets
// (AT-4 engine) and distinct works only. The page lists plastic-related works only (selectionFor adds
// that facet). Every view below the filters follows them (owner 2026-11-12): trend panel, heatmap and
// publication table get the matching rows on each change; heatmap cells narrow the publication table
// (owner 2026-11-13); the pipeline flow is static. Related resources moved to their own page.
// Pure helpers live in evidence_model.js; this file owns the DOM.
import "./shared/facets.js";
import "./shared/topics.js";
import {regionDataUrl, formatCount, loadJson, regionSlug} from "./atlas.js";
import {mountV3Flow} from "./v3_flow.js";
import {mountV4Trend} from "./v4_trend.js";
import {mountHeatmap} from "./ev_heatmap.js";
import {labelSummary} from "./ev_heatmap_model.js";
import {mountWorksTable, renderRecentCallout} from "./ev_table.js";
import {attachJournalMetrics, normaliseRows} from "./ev_table_model.js";
import {
  JOURNAL_FACET,
  andBits,
  emptyState,
  formatHash,
  journalBits,
  journalOptions,
  matchesJournalQuery,
  parseHash,
  sanitizeState,
  selectionFor,
  tallyJournals
} from "./evidence_model.js";
import {sectorLabel, workTypeLabel} from "./shared/labels.js";

const $ = (id) => document.getElementById(id);

// Facets shown as checkbox groups. Plastic relevance is not a choice here: the page always applies it.
// The institution facet stays valid in the hash but has no UI.
const FACET_UI = [
  {key: "topic", label: "Topic", name: (label) => window.AtlasTopics.label(label)},
  {key: "ca_led", label: "Led from California", names: {yes: "Yes", no: "No"}},
  {key: "sector", label: "Sector", name: sectorLabel},
  {key: "type", label: "Work type", name: workTypeLabel},
  {key: "oa", label: "Open access", names: {open: "Open access", closed: "Closed access"}}
];
// Keys the form owns: readControls rebuilds them from the controls and keeps every other key from the state.
const CONTROLLED = new Set([...FACET_UI.map((ui) => ui.key), JOURNAL_FACET]);

// GP-8: a region page (any registry slug but California) lists the works of its region. Those works have no
// relevance review, so they are listed as unscreened query hits (plastic_related null), and California-only
// views and facets are left out.
const isRegion = () => regionSlug() !== "california";
function listedWork(row) {
  return isRegion() ? row.plastic_related !== false : row.plastic_related === true;
}

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
  // Works in the heatmap selection that the table shows, and one label per selected cell.
  heatCount: null,
  heatLabels: [],
  // Distinct works that match the page filters (before the heatmap selection).
  total: 0,
  // VD-34: work_id -> journal name (from works_detail), for the journal filter and its counts.
  journalOf: new Map(),
  table: null,
  heatmap: null
};

function optionName(ui, label) {
  if (ui.name) return ui.name(label);
  return ui.names?.[label] ?? label;
}

function buildFilterGroups(container, index) {
  for (const ui of FACET_UI) {
    if (ui.key === "ca_led" && isRegion()) continue;
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
      if (ui.key === "topic") {
        const dot = document.createElement("span");
        dot.className = "topic-dot";
        dot.setAttribute("aria-hidden", "true");
        dot.style.background = window.AtlasTopics.cssFill(label);
        if (window.AtlasTopics.pattern(label) === "hatch") dot.classList.add("hatch");
        if (window.AtlasTopics.isAuxiliary(label)) dot.classList.add("auxiliary");
        name.prepend(dot);
      }
      const count = document.createElement("span");
      count.className = "ev-count";
      row.append(input, name, count);
      fieldset.append(row);
      app.rows.push({facet: ui.key, label, row, input, count});
    }
    container.append(fieldset);
  }
}

// VD-34: the journal checklist, most works first, with a search box that only hides options. Each option is an
// app.rows entry (facet "journal"), so readControls, syncControls and the counts treat it like any other facet.
function buildJournalGroup(container, options) {
  const fieldset = document.createElement("fieldset");
  fieldset.className = "ev-group ev-journal-group";
  const legend = document.createElement("legend");
  legend.textContent = "Journal";
  const search = document.createElement("input");
  search.type = "search";
  search.className = "ev-journal-search";
  search.autocomplete = "off";
  search.placeholder = "Search journals";
  search.setAttribute("aria-label", "Search journals");
  search.dataset.role = "journal-search";
  const list = document.createElement("div");
  list.className = "ev-journal-list";
  list.setAttribute("role", "group");
  list.setAttribute("aria-label", "Journals, most works first");
  for (const {label, count} of options) {
    const row = document.createElement("label");
    row.className = "ev-option";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = label;
    const name = document.createElement("span");
    name.className = "ev-option-name";
    name.textContent = label;
    const countEl = document.createElement("span");
    countEl.className = "ev-count";
    countEl.textContent = formatCount(count);
    row.append(input, name, countEl);
    list.append(row);
    app.rows.push({facet: JOURNAL_FACET, label, row, input, count: countEl});
  }
  fieldset.append(legend, search, list);
  container.append(fieldset);
  search.addEventListener("input", filterJournalOptions);
}

// Writes the form's controls back into a state object; hidden facets keep their hash values.
function readControls() {
  const facets = {};
  for (const key of Object.keys(app.state.facets)) {
    if (!CONTROLLED.has(key)) facets[key] = app.state.facets[key];
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
  filterJournalOptions();
}

// Works whose journal is ticked, as a bit-set over the bundle's works (undefined when no journal is ticked).
function journalFilterBits() {
  const labels = app.state.facets[JOURNAL_FACET];
  return labels && labels.length ? journalBits(app.index.workIds, app.journalOf, labels, app.index.W) : undefined;
}

// Shows the journal options that match the search text. A ticked journal always stays visible.
function filterJournalOptions() {
  const search = $("evidence-groups").querySelector("[data-role='journal-search']");
  if (!search) return;
  for (const row of app.rows) {
    if (row.facet === JOURNAL_FACET) {
      row.row.hidden = !row.input.checked && !matchesJournalQuery(row.label, search.value);
    }
  }
}

// The one place state changes: sanitize, mirror into the hash, then redraw.
function setState(next, {sync = false} = {}) {
  app.state = sanitizeState(next, app.known);
  if (sync) syncControls();
  history.replaceState(null, "", `${location.pathname}${location.search}${formatHash(app.state)}`);
  render();
}

function render() {
  // A region has no relevance review, so its works are not filtered by the plastic facet.
  const {sel, impossible} = selectionFor(app.state, app.yearLabels, {plastic: isRegion() ? null : undefined});
  const text = app.state.q ? app.index.searchBits(app.state.q) : undefined;
  // The journal filter is a bit-set over the bundle's works, so every count and list below respects it.
  const extra = andBits(text, journalFilterBits());
  const result = impossible ? {total: 0, counts: {}} : app.index.counts(sel, extra);
  // A journal's count ignores the journal filter itself, as a facet's count ignores its own facet.
  const journals = impossible ? new Map() : tallyJournals(app.index.selectedIds(sel, text), app.journalOf);
  for (const row of app.rows) {
    const count =
      row.facet === JOURNAL_FACET
        ? (journals.get(row.label) ?? 0)
        : (result.counts[`${row.facet}|${row.label}`] ?? 0);
    row.count.textContent = formatCount(count);
    row.row.classList.toggle("ev-zero", count === 0);
  }
  app.current = {sel, impossible, extra};
  app.total = result.total;
  renderHeadline();
  notifyViews();
}

// The headline names the heatmap selection too, once one exists.
function renderHeadline() {
  const base = `${formatCount(app.total)} distinct works match`;
  $("evidence-count").textContent =
    app.heatCount === null
      ? base
      : `${base} · ${formatCount(app.heatCount)} in the heatmap selection (listed under Publications)`;
}

// Banner above the publication table: says what the table is narrowed to, and clears it.
function renderSelectionBanner() {
  const banner = $("ev-table-selection");
  banner.hidden = app.heatIds === null;
  if (app.heatIds === null) return;
  const works = app.heatCount === 1 ? "work" : "works";
  banner.querySelector(".ev-table-selection-text").textContent =
    `Showing ${formatCount(app.heatCount)} ${works} from your heatmap selection: ${labelSummary(app.heatLabels)}.`;
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
// The headline and the banner follow the same selected works.
function applyTable() {
  const ids = app.heatIds ? app.lastIds.filter((id) => app.heatIds.has(id)) : app.lastIds;
  app.heatCount = app.heatIds ? ids.length : null;
  if (app.table) app.table.update(ids);
  renderHeadline();
  renderSelectionBanner();
}

// VD-34: journal_metrics.json is optional. Without it the 2-yr mean citedness column is blank; the page still works.
function loadJournalMetrics() {
  // A region export has no journal metrics (no journal names in the partition), so it does not request the file.
  if (isRegion()) return Promise.resolve(null);
  return loadJson("journal_metrics.json", {optional: true}).catch(() => null);
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
  form.addEventListener("input", (event) => {
    // The journal search only hides options; it is not part of the filter state.
    if (event.target.dataset?.role === "journal-search") return;
    clearTimeout(timer);
    timer = setTimeout(() => setState(readControls()), 150);
  });
  $("evidence-reset").addEventListener("click", () => {
    const search = $("evidence-groups").querySelector("[data-role='journal-search']");
    if (search) search.value = "";
    setState(emptyState(), {sync: true});
  });
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
  let detail = null;
  try {
    // The works detail names each work's journal. Without it the journal filter is left out, not the page.
    [index, detail] = await Promise.all([
      window.AtlasFacets.BitmaskIndex.load(regionDataUrl("bundle/")),
      loadDetail().catch(() => null)
    ]);
  } catch {
    showFailed();
    return;
  }
  app.index = index;
  app.known = Object.fromEntries(
    Object.keys(index.facets).map((key) => [key, new Set(index.facets[key].map((item) => item.label))])
  );
  app.yearLabels = (index.facets.year || []).map((item) => item.label);
  // VD-34: journal options come from the plastic-related rows, most works first. The filter's labels must be
  // known before the hash is read, so a shared link with journal=... keeps its journals.
  const plasticRows = detail ? [...detail.values()].filter(listedWork) : [];
  const journals = journalOptions(plasticRows);
  app.journalOf = detail ? new Map([...detail].map(([id, row]) => [id, row.journal])) : new Map();
  app.known[JOURNAL_FACET] = new Set(journals.map((item) => item.label));
  if (!bound) {
    buildFilterGroups($("evidence-groups"), index);
    if (journals.length) buildJournalGroup($("evidence-groups"), journals);
    bindFilters();
    bound = true;
  }
  app.state = sanitizeState(parseHash(location.hash), app.known);
  setState(app.state, {sync: true});
  showStatus(`Loaded ${formatCount(index.N)} works.`);
  await mountViews(index);
}

// The banner's text is filled by applyTable; its one button clears the heatmap selection.
function mountSelectionBanner(heatmap) {
  const banner = $("ev-table-selection");
  const text = document.createElement("span");
  text.className = "ev-table-selection-text";
  const clear = document.createElement("button");
  clear.type = "button";
  clear.textContent = "Clear heatmap selection";
  clear.addEventListener("click", () => {
    heatmap.clear();
    // The banner hides on clear, so keep keyboard focus on the heatmap heading instead.
    $("ev-heatmap-heading").focus({preventScroll: true});
  });
  banner.replaceChildren(text, clear);
}

let viewsMounted = false;
// Trend panel, heatmap, publication table and the "new in the last 2 weeks" callout.
async function mountViews(index) {
  if (viewsMounted) return;
  viewsMounted = true;
  let detail;
  let journals;
  try {
    [detail, journals] = await Promise.all([loadDetail(), loadJournalMetrics()]);
  } catch {
    $("ev-table").textContent = "Could not load the publication details.";
    if (isRegion()) return;
    const trendPromise = mountV4Trend($("ev-v4"), index);
    settleSection($("ev-v4"), trendPromise);
    return;
  }
  app.detail = detail;
  const plasticWorks = [...detail.values()].filter(listedWork);
  // The trend's California share is not meaningful for a region, so a region page keeps the panel hidden.
  const trendPromise = isRegion() ? Promise.resolve(null) : mountV4Trend($("ev-v4"), index, plasticWorks);
  if (!isRegion()) settleSection($("ev-v4"), trendPromise);
  renderRecentCallout($("ev-recent"), plasticWorks, new Date());
  app.heatmap = mountHeatmap($("ev-heatmap"), {
    onSelect: (ids) => {
      app.heatIds = ids ? new Set(ids) : null;
      app.heatLabels = app.heatIds && app.heatmap ? app.heatmap.describe() : [];
      applyTable();
    }
  });
  mountSelectionBanner(app.heatmap);
  $("ev-heatmap").closest("section").hidden = false;
  app.table = mountWorksTable($("ev-table"), {
    initialRows: attachJournalMetrics(plasticWorks, journals),
    metricsColumn: !isRegion()
  });
  app.views.push(({rows}) => app.heatmap.update(rows), () => applyTable());
  notifyViews();
  try {
    const trend = await trendPromise;
    if (trend && typeof trend.update === "function") {
      app.views.push(({rows, filtered}) => trend.update(rows, {filtered}));
      if (formatHash(app.state) !== "") {
        trend.update(app.lastIds.map((id) => app.detail.get(id)).filter(Boolean), {filtered: true});
      }
    }
  } catch {
    // settleSection already hid the trend section.
  }
}

// Chart/Table controls on the chart cards. A click sets data-view on the card and moves aria-pressed; evidence.css
// shows the matching pane. The mode lives on the card, not in the pane, because the chart panes are rebuilt on
// every filter change and would otherwise reset to the chart.
function wireChartViews() {
  for (const group of document.querySelectorAll("#evidence-root .atlas-chart > .atlas-chart__head .atlas-segmented")) {
    group.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-view]");
      if (!button || !group.contains(button)) return;
      group.closest(".atlas-chart").dataset.view = button.dataset.view;
      for (const other of group.querySelectorAll("button[data-view]")) {
        other.setAttribute("aria-pressed", String(other === button));
      }
    });
  }
}

export async function mountEvidence() {
  wireChartViews();
  // V-3 (EM-6) needs only the methods card export, so it renders independently of the bundle.
  // The pipeline flow is the California methods card; a region page has no flow section.
  if (!isRegion()) mountV3Flow($("ev-v3"));
  await loadBundle();
}
