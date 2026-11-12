// Evidence map shell (Add-on A2 §5, EM-5b): shared filter state in the URL hash, A1 bit-set facets
// (AT-4 engine), distinct works only, a shared works drawer and a related-resources strip. The
// views V-3 and V-4 mount here; the other views are not built yet and have no sections in evidence.md.
// Pure helpers live in evidence_model.js; this file owns the DOM.
import "./shared/facets.js";
import "./shared/topics.js";
import {dataUrl, formatCount, loadJson} from "./atlas.js";
import {mountV3Flow} from "./v3_flow.js";
import {mountV4Trend} from "./v4_trend.js";
import {
  DRAWER_PAGE_SIZE,
  LINKOUT_NOTE,
  emptyState,
  formatHash,
  openAlexUrl,
  pageWorks,
  parseHash,
  safeHttpUrl,
  sanitizeState,
  selectionFor,
  sortWorksNewestFirst,
  stripEntries,
  worksMetaMap
} from "./evidence_model.js";

const $ = (id) => document.getElementById(id);

// Facets shown as checkbox groups. The institution facet stays valid in the hash but has no UI.
const FACET_UI = [
  {key: "topic", label: "Topic", name: (label) => window.AtlasTopics.label(label)},
  {key: "ca_led", label: "Led from California", names: {yes: "Yes", no: "No"}},
  {key: "sector", label: "Sector"},
  {key: "type", label: "Work type"},
  {key: "oa", label: "Open access", names: {open: "Open access", closed: "Closed access"}},
  {key: "plastic", label: "Plastic-related", names: {yes: "Yes", no: "No"}}
];

const app = {
  index: null,
  known: null,
  yearLabels: [],
  state: emptyState(),
  rows: [],
  current: null,
  linkouts: null,
  drawer: null,
  opener: null
};

let worksPromise = null;

// Titles and years for the drawer, built once from the bundle's works index.
function loadWorks() {
  if (!worksPromise) {
    worksPromise = fetch(dataUrl("bundle/works_index.json"))
      .then((response) => {
        if (!response.ok) throw new Error(`works_index.json returned HTTP ${response.status}`);
        return response.json();
      })
      .then(worksMetaMap)
      .catch((error) => {
        worksPromise = null;
        throw error;
      });
  }
  return worksPromise;
}

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
  renderStrip();
}

function renderStrip() {
  const section = $("evidence-strip");
  const entries = app.linkouts ? stripEntries(app.linkouts, app.state.facets.topic || []) : [];
  section.hidden = entries.length === 0;
  if (!entries.length) return;
  const list = $("evidence-strip-list");
  list.replaceChildren();
  for (const entry of entries) {
    const item = document.createElement("li");
    item.className = "ev-strip-item";
    const url = safeHttpUrl(entry.root_url);
    const name = document.createElement(url ? "a" : "span");
    if (url) {
      name.href = url;
      name.target = "_blank";
      name.rel = "noreferrer";
    }
    name.textContent = String(entry.name || entry.id);
    item.append(name);
    if (entry.steward) {
      const steward = document.createElement("span");
      steward.className = "ev-strip-steward";
      steward.textContent = ` ${entry.steward}`;
      item.append(steward);
    }
    if (entry.description) {
      const description = document.createElement("p");
      description.className = "ev-strip-description";
      description.textContent = String(entry.description);
      item.append(description);
    }
    list.append(item);
  }
  $("evidence-strip-note").textContent = LINKOUT_NOTE;
}

function renderDrawer() {
  const drawer = app.drawer;
  const page = pageWorks(drawer.sorted, drawer.page, DRAWER_PAGE_SIZE);
  drawer.page = page.page;
  const list = $("evidence-drawer-list");
  list.replaceChildren();
  for (const id of page.items) {
    const info = drawer.meta.get(id) || {title: "", year: null};
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = openAlexUrl(id);
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = info.title || id;
    item.append(link);
    if (info.year !== null) {
      const year = document.createElement("span");
      year.className = "ev-year";
      year.textContent = ` (${info.year})`;
      item.append(year);
    }
    list.append(item);
  }
  $("evidence-drawer-count").textContent = `${formatCount(page.total)} works, newest first`;
  $("evidence-drawer-page").textContent = `Page ${page.page + 1} of ${page.pages}`;
  $("evidence-drawer-prev").disabled = page.page === 0;
  $("evidence-drawer-next").disabled = page.page >= page.pages - 1;
}

// Shared works drawer. Matrix cells (EM-8) reuse it: pass a title and the work ids to list.
export async function openWorksDrawer(title, workIds, opener = document.activeElement) {
  const dialog = $("evidence-drawer");
  if (!dialog) throw new Error("evidence drawer markup is missing");
  const meta = await loadWorks();
  app.drawer = {meta, sorted: sortWorksNewestFirst(workIds, meta), page: 0};
  app.opener = opener instanceof HTMLElement ? opener : null;
  $("evidence-drawer-title").textContent = title;
  renderDrawer();
  if (!dialog.open) dialog.showModal();
  $("evidence-drawer-close").focus();
}

function bindDrawer() {
  const dialog = $("evidence-drawer");
  const step = (delta) => {
    app.drawer.page += delta;
    renderDrawer();
  };
  $("evidence-drawer-prev").addEventListener("click", () => step(-1));
  $("evidence-drawer-next").addEventListener("click", () => step(1));
  $("evidence-drawer-close").addEventListener("click", () => dialog.close());
  // A click on the dialog box itself (padding is zero) is a click on the backdrop.
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("close", () => app.opener?.focus());
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
  $("evidence-show-works").addEventListener("click", (event) => {
    const {sel, impossible, extra} = app.current;
    const ids = impossible ? [] : app.index.selectedIds(sel, extra);
    openWorksDrawer("Matching works", ids, event.currentTarget).catch((error) => {
      $("evidence-status").textContent = `Could not list the works: ${error.message}`;
    });
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

let linkoutsPromise = null;
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
    bindDrawer();
    bound = true;
  }
  app.state = sanitizeState(parseHash(location.hash), app.known);
  $("evidence-show-works").disabled = false;
  setState(app.state, {sync: true});
  showStatus(`Loaded ${formatCount(index.N)} works.`);
  app.linkouts = await linkoutsPromise;
  renderStrip();
  // V-4 (EM-7): whole-corpus trends from the same bit-set index (not filtered by the selection).
  settleSection($("ev-v4"), mountV4Trend($("ev-v4"), index));
}

export async function mountEvidence() {
  // V-3 (EM-6) needs only the methods card export, so it renders independently of the bundle.
  settleSection($("ev-v3"), mountV3Flow($("ev-v3")));
  linkoutsPromise = loadJson("linkouts.json", {optional: true})
    .then((data) => (Array.isArray(data?.entries) ? data.entries : null))
    .catch(() => null);
  await loadBundle();
}
