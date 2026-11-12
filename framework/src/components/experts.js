// Experts page (AT-5d): DOM wiring for the classic site's Experts tab. Pure helpers live in
// experts_model.js. Browsers read the vendored globals window.AtlasTopics, window.MiniSearch and
// window.AtlasExpert, which the side-effect imports below install.
import "./shared/vendor/minisearch-7.2.0.js";
import "./shared/topics.js";
import "./shared/expert_page.js";
import {dataUrl, escapeHtml} from "./atlas.js";
import {
  EMPTY_MATCH_HTML,
  buildAuthorSearchIndex,
  buildLookups,
  csvText,
  defaultFilters,
  drawerContentHtml,
  expertCountText,
  expertRowHtml,
  filterAuthors,
  formatExpertHash,
  parseExpertHash,
  profileIssueUrl,
  resetFilters,
  rowHeightForWidth,
  searchAuthorIds,
  summarizeAuthor,
  virtualWindow
} from "./experts_model.js";

const $ = (id) => document.getElementById(id);
const FILTER_IDS = ["expert-search", "institution-type-filter", "institution-filter", "tag-filter", "year-from", "year-to", "ca-basis-filter", "oa-filter", "expert-sort", "early-filter"];
const OVERSCAN = 4;

const state = {
  data: null,
  filters: defaultFilters(),
  pendingAuthor: "",
  lastFilterSignature: "",
  drawerPrevious: null,
  lookups: null,
  summaries: null,
  rankSearch: null,
  filteredAuthors: [],
  rowHeight: 232
};
let controller = null;

function summaries() {
  if (!state.summaries) {
    state.lookups = buildLookups(state.data.index, state.data.institutions);
    state.summaries = state.data.index.authors.map((author) => summarizeAuthor(author, state.lookups.worksById, state.lookups.institutionsById));
  }
  return state.summaries;
}

// One MiniSearch index per loaded payload; null when MiniSearch is missing (substring fallback).
function rankedIdsFor(query) {
  if (!query || typeof window.MiniSearch !== "function") return null;
  const list = summaries();
  if (!state.rankSearch || state.rankSearch.source !== list) {
    state.rankSearch = {source: list, index: buildAuthorSearchIndex(window.MiniSearch, list), query: null, ids: null};
  }
  const memo = state.rankSearch;
  if (memo.query !== query) {
    memo.query = query;
    memo.ids = searchAuthorIds(memo.index, query);
  }
  return memo.ids;
}

function currentAuthors() {
  const query = state.filters.search.trim();
  return filterAuthors(summaries(), state.filters, rankedIdsFor(query));
}

function populateFilters() {
  const tags = new Set();
  state.data.index.works.forEach((work) => [...(work.domain_tags || []), ...(work.facet_tags || [])].forEach((tag) => tags.add(tag)));
  const types = new Set();
  const institutions = new Map();
  (state.data.institutions || []).forEach((institution) => {
    types.add(institution.atlas_type || "other");
    institutions.set(institution.inst_id, institution);
  });
  const topics = window.AtlasTopics;
  $("institution-type-filter").innerHTML = '<option value="">All institution types</option>' + [...types].sort().map((type) => `<option value="${escapeHtml(type)}">${escapeHtml(type)}</option>`).join("");
  $("institution-filter").innerHTML = '<option value="">All institutions</option>' + [...institutions.values()].sort((a, b) => String(a.name).localeCompare(String(b.name))).map((institution) => `<option value="${escapeHtml(institution.inst_id)}">${escapeHtml(institution.name)}</option>`).join("");
  const sortedTags = topics.sortTags([...tags]);
  const tagOption = (tag) => `<option value="${escapeHtml(tag)}">${escapeHtml(topics.label(tag))}</option>`;
  $("tag-filter").innerHTML = '<option value="">All tags</option>' + `<optgroup label="Research topics">${sortedTags.filter((tag) => !topics.isMatrix(tag)).map(tagOption).join("")}</optgroup><optgroup label="Matrices">${sortedTags.filter(topics.isMatrix).map(tagOption).join("")}</optgroup>`;
}

function applyControls() {
  const f = state.filters;
  $("expert-search").value = f.search;
  $("institution-type-filter").value = f.institutionType;
  $("institution-filter").value = f.institution;
  $("tag-filter").value = f.tag;
  $("year-from").value = f.yearFrom;
  $("year-to").value = f.yearTo;
  $("ca-basis-filter").value = f.caBasis;
  $("oa-filter").value = f.oa;
  $("expert-sort").value = f.sort;
  $("early-filter").checked = f.early;
}

function readHash() {
  const {filters, author} = parseExpertHash(window.location.hash);
  state.filters = filters;
  state.pendingAuthor = author;
}

function writeHash() {
  const hash = formatExpertHash(state.filters);
  if (window.location.hash !== hash) window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}${hash}`);
}

function updateRowHeight() {
  const height = rowHeightForWidth(window.innerWidth);
  const changed = height !== state.rowHeight;
  state.rowHeight = height;
  return changed;
}

function renderExperts() {
  const authors = currentAuthors();
  state.filteredAuthors = authors;
  updateRowHeight();
  $("expert-count").textContent = expertCountText(authors.length);
  $("expert-spacer").style.height = `${Math.max(authors.length * state.rowHeight, authors.length ? 1 : 0)}px`;
  renderVirtualRows();
  if (!authors.length) $("expert-rows").innerHTML = EMPTY_MATCH_HTML;
}

function updateViews() {
  applyControls();
  renderExperts();
}

function renderVirtualRows() {
  const list = $("expert-list");
  const rows = $("expert-rows");
  if (!state.filteredAuthors.length) {
    rows.innerHTML = "";
    return;
  }
  const {start, end} = virtualWindow({scrollTop: list.scrollTop, clientHeight: list.clientHeight, rowHeight: state.rowHeight, count: state.filteredAuthors.length, overscan: OVERSCAN});
  rows.innerHTML = state.filteredAuthors.slice(start, end).map((author, offset) => expertRowHtml(author, start + offset, state.rowHeight, state.filters.sort)).join("");
  fitExpertTopics(rows);
  rows.querySelectorAll(".expert-link, .topic-more").forEach((button) => button.addEventListener("click", () => openDrawer(button.dataset.authorId)));
}

// Shows at most two lines of chips; whatever does not fit collapses into a "+N more" button.
function fitExpertTopics(root) {
  root.querySelectorAll(".expert-topics").forEach((box) => {
    const chips = [...box.querySelectorAll(".topic-chip")];
    const more = box.querySelector(".topic-more");
    if (!more || !chips.length) return;
    const overflows = (element) => element.offsetTop + element.offsetHeight > box.clientHeight + 1;
    if (!overflows(chips[chips.length - 1])) return;
    more.hidden = false;
    let hidden = 0;
    while (hidden < chips.length - 1) {
      hidden += 1;
      chips[chips.length - hidden].hidden = true;
      more.textContent = `+${hidden} more`;
      if (!overflows(more)) break;
    }
    more.title = chips.slice(chips.length - hidden).map((chip) => chip.textContent.trim()).join(", ");
  });
}

async function openDrawer(authorId) {
  state.drawerPrevious = document.activeElement;
  $("researcher-drawer").hidden = false;
  $("drawer-backdrop").hidden = false;
  $("drawer-issue-link").href = profileIssueUrl(authorId, authorId);
  $("drawer-content").innerHTML = '<p class="detail-meta">Loading researcher details…</p>';
  $("drawer-close").focus();
  try {
    const response = await fetch(dataUrl(`authors/${encodeURIComponent(authorId)}.json`), {cache: "no-cache"});
    if (!response.ok) throw new Error(`author detail returned HTTP ${response.status}`);
    const detail = await response.json();
    const all = summaries();
    const summary = all.find((item) => item.author_id === authorId) || {};
    const author = {...summary, ...(detail.author || {})};
    const works = detail.works || [];
    const expertsById = new Map(all.map((item) => [item.author_id, item]));
    $("drawer-title").textContent = author.name || "Researcher";
    $("drawer-issue-link").href = profileIssueUrl(author.name, author.author_id || authorId);
    $("drawer-content").innerHTML = drawerContentHtml({author, works, authorId, profile: detail.profile, expertsById, institutionsById: state.lookups.institutionsById, histogramSvg: histogramSvg()});
    const setAbstracts = (open) => $("drawer-content").querySelectorAll("details.work-abstract").forEach((node) => { node.open = open; });
    const expandButton = $("abstracts-expand");
    const collapseButton = $("abstracts-collapse");
    if (expandButton) expandButton.addEventListener("click", () => setAbstracts(true));
    if (collapseButton) collapseButton.addEventListener("click", () => setAbstracts(false));
    $("drawer-content").querySelectorAll(".coauthor-link").forEach((button) => button.addEventListener("click", () => openDrawer(button.dataset.authorId)));
  } catch (error) {
    $("drawer-content").innerHTML = `<p class="empty">${escapeHtml(error.message)}</p>`;
  }
}

function histogramSvg() {
  const helpers = window.AtlasExpert;
  return helpers ? (rows, opts) => helpers.citationHistogramSvg(rows, opts) : null;
}

function openPendingAuthor() {
  const authorId = state.pendingAuthor;
  state.pendingAuthor = "";
  if (authorId && state.data) openDrawer(authorId);
}

function closeDrawer() {
  $("researcher-drawer").hidden = true;
  $("drawer-backdrop").hidden = true;
  if (state.drawerPrevious && typeof state.drawerPrevious.focus === "function") state.drawerPrevious.focus();
}

function onFilterChange() {
  state.filters = {
    ...state.filters,
    search: $("expert-search").value.trim(),
    institutionType: $("institution-type-filter").value,
    institution: $("institution-filter").value,
    tag: $("tag-filter").value,
    yearFrom: $("year-from").value,
    yearTo: $("year-to").value,
    caBasis: $("ca-basis-filter").value,
    oa: $("oa-filter").value,
    sort: $("expert-sort").value,
    early: $("early-filter").checked
  };
  // "change" fires on blur after "input" already rendered; re-rendering then replaced the
  // rows between mousedown and mouseup, so the first click on an expert was lost.
  const f = state.filters;
  const signature = JSON.stringify([f.search, f.institutionType, f.institution, f.tag, f.yearFrom, f.yearTo, f.caBasis, f.oa, f.early, f.sort]);
  if (signature === state.lastFilterSignature) return;
  state.lastFilterSignature = signature;
  writeHash();
  renderExperts();
}

function exportCsv() {
  if (!state.data) return;
  const blob = new Blob([csvText(currentAuthors())], {type: "text/csv;charset=utf-8"});
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "ca-plastics-atlas-experts.csv";
  link.click();
  URL.revokeObjectURL(url);
}

async function loadData() {
  try {
    const [index, institutions] = await Promise.all(["index.json", "institutions.json"].map(async (path) => {
      const response = await fetch(dataUrl(path), {cache: "no-cache"});
      if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
      return response.json();
    }));
    if (!index || !Array.isArray(index.authors) || !Array.isArray(index.works)) throw new Error("index.json does not match the S3.1 contract");
    state.data = {index, institutions: (institutions && institutions.institutions) || []};
    state.summaries = null;
    state.rankSearch = null;
    populateFilters();
    updateViews();
    openPendingAuthor();
  } catch (error) {
    $("expert-count").textContent = "The static data could not be loaded.";
    $("expert-list").innerHTML = `<p class="empty">${escapeHtml(error.message)}<br>Run the site through a web server and rebuild the S3.1 data export.</p>`;
  }
}

function bindEvents(signal) {
  FILTER_IDS.forEach((id) => {
    $(id).addEventListener("input", onFilterChange, {signal});
    $(id).addEventListener("change", onFilterChange, {signal});
  });
  $("reset-filters").addEventListener("click", () => {
    state.filters = resetFilters(state.filters);
    writeHash();
    updateViews();
    $("expert-search").focus();
  });
  $("rising-preset").addEventListener("click", () => {
    state.filters = {...state.filters, early: true, sort: "rising"};
    $("early-filter").checked = true;
    $("expert-sort").value = "rising";
    state.lastFilterSignature = "";
    writeHash();
    renderExperts();
  }, {signal});
  $("export-csv").addEventListener("click", exportCsv, {signal});
  $("drawer-close").addEventListener("click", closeDrawer, {signal});
  $("drawer-backdrop").addEventListener("click", closeDrawer, {signal});
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !$("researcher-drawer").hidden) closeDrawer();
  }, {signal});
  window.addEventListener("hashchange", () => {
    readHash();
    if (state.data) {
      updateViews();
      openPendingAuthor();
    }
  }, {signal});
  let resizeFrame = 0;
  window.addEventListener("resize", () => {
    if (resizeFrame) return;
    resizeFrame = window.requestAnimationFrame(() => {
      resizeFrame = 0;
      if (!state.data) return;
      if (updateRowHeight()) renderExperts();
      else renderVirtualRows();
    });
  }, {signal});
  $("expert-list").addEventListener("scroll", () => window.requestAnimationFrame(renderVirtualRows), {passive: true, signal});
}

// Called once from experts.md. Re-running (Framework re-renders the page) aborts the previous listeners.
export function mountExperts() {
  if (controller) controller.abort();
  controller = new AbortController();
  state.data = null;
  state.summaries = null;
  state.rankSearch = null;
  state.lastFilterSignature = "";
  readHash();
  bindEvents(controller.signal);
  loadData();
}
