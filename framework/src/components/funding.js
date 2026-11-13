// Funding view for the Framework shell (AT-5b). A lift-and-shift of the classic site's Funding tab
// (site/index.html: loadOpenCalls..showFunding and the funding event bindings). Markup, labels,
// filters, sorting, paging, charts and the CSV export follow the classic code. The differences:
// - data is fetched with dataUrl() from the classic site's data/ folder;
// - the page hash has no "funding?" tab prefix (legacy "#funding?..." hashes are still read);
// - nothing touches the DOM at module top level, so Node tests can import the pure helpers.
// funding.md imports components/shared/topics.js (AtlasTopics) before this module runs.
import {dataUrl, escapeHtml} from "./atlas.js";
import {mountFundingViz} from "./funding_viz.js";

const $ = (id) => document.getElementById(id);

const GRANT_FUNDER_ORDER = ["federal", "state", "other"];
const GRANT_FUNDER_COLORS = {federal: "#2f6f8f", state: "#2f8f6f", other: "#b8862b"};
const GRANT_FUNDER_LABELS = {federal: "Federal", state: "State", other: "Other"};
const GRANT_SOURCE_LABELS = {nih_reporter: "NIH RePORTER", nsf_awards: "NSF Awards", usaspending: "USAspending.gov", ca_sea_grant: "California Sea Grant", opc_council: "Ocean Protection Council"};
export const GRANT_FILTERS = [
  {key: "q", id: "grants-search"}, {key: "sc", id: "grants-sector"}, {key: "fa", id: "grants-agency"},
  {key: "ft", id: "grants-funder-type"}, {key: "fn", id: "grants-funder"}, {key: "pg", id: "grants-program"},
  {key: "yf", id: "grants-year-from"}, {key: "yt", id: "grants-year-to"}, {key: "amin", id: "grants-amount-min"},
  {key: "amax", id: "grants-amount-max"}, {key: "it", id: "grants-institution-type"}, {key: "tg", id: "grants-tag"},
  {key: "ca", id: "grants-ca-led"}
];
export const GRANT_CSV_COLUMNS = ["grant_key", "source", "title", "pi_names", "org", "org_state", "institution_type", "start", "end", "fiscal_year", "amount", "currency", "amount_basis", "funder", "funder_type", "program", "funder_chain", "url", "plastic_related", "domain_tags", "ca_led", "sector", "sector_detail", "funder_agency"];
const USD_FORMAT = new Intl.NumberFormat("en-US", {style: "currency", currency: "USD", maximumFractionDigits: 0});
export const GRANT_COLUMNS = [
  {key: "title", label: "Award"}, {key: "org", label: "Recipient"}, {key: "sector", label: "Sector"},
  {key: "agency", label: "Funder agency"}, {key: "program", label: "Program"}, {key: "fy", label: "Fiscal year / start", num: true},
  {key: "end", label: "End"}, {key: "amount", label: "Amount", num: true}, {key: "ca", label: "CA-led"}, {key: "plastic", label: "Plastic-related"}
];

// Mutable view state (the classic page kept these as top-level let variables).
const state = {
  openCallsRequest: null,
  grantsRequest: null,
  grantsData: null,
  grantsFiltered: [],
  grantsPage: 0,
  grantsPageSize: 50,
  grantsReady: false,
  viz: null,
  grantsSort: {key: null, dir: "asc"},
  grantsSearchTimer: 0,
  listening: false
};

// ---- Open calls -------------------------------------------------------------------------------

function loadOpenCalls() {
  if (!state.openCallsRequest) {
    state.openCallsRequest = fetch(dataUrl("open_calls.json"), {cache: "no-cache"})
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .catch((error) => {
        state.openCallsRequest = null;
        throw error;
      });
  }
  return state.openCallsRequest;
}

export function openCallsHtml(payload) {
  const calls = Array.isArray(payload.calls) ? payload.calls : [];
  return calls.length
    ? `<ul class="open-calls-list" aria-label="Open plastic-related funding calls">${calls.map((call) => {
        const title = call.url ? `<a href="${escapeHtml(call.url)}" target="_blank" rel="noreferrer">${escapeHtml(call.title)}</a>` : escapeHtml(call.title);
        return `<li>${title}<br><small>${escapeHtml(call.agency)} · Deadline: ${escapeHtml(call.deadline)} · Status: ${escapeHtml(call.status)}</small></li>`;
      }).join("")}</ul>`
    : '<p class="empty">No open plastic-related calls right now</p>';
}

function renderOpenCalls(payload) {
  const calls = Array.isArray(payload.calls) ? payload.calls : [];
  $("open-calls-status").textContent = `${calls.length} open ${calls.length === 1 ? "call" : "calls"} in the latest snapshot`;
  $("open-calls").innerHTML = openCallsHtml(payload);
}

function showOpenCalls() {
  $("open-calls-status").textContent = "Loading open calls…";
  loadOpenCalls()
    .then(renderOpenCalls)
    .catch(() => {
      $("open-calls-status").textContent = "";
      $("open-calls").innerHTML = '<p class="empty">Open calls could not be loaded right now.</p>';
    });
}

// ---- Pure grant helpers (exported for tests) --------------------------------------------------

export function grantTri(value) {
  return value === true ? 1 : value === false ? 0 : null;
}

export function grantSectorLabel(row, sectorLabels = {}) {
  return (sectorLabels && sectorLabels[row.sector]) || row.sector || "Unknown";
}

// Adds the search haystack (_q) and the sortable values (_s) to each row, as the classic page did.
export function prepareGrantRows(rows, sectorLabels = {}) {
  rows.forEach((row) => {
    row._q = [row.title, row.org, (row.pi_names || []).join(" "), row.program, row.funder, row.funder_agency].filter(Boolean).join(" \n ").toLowerCase();
    row._s = {
      title: (row.title || "").toLowerCase(), org: (row.org || "").toLowerCase(), sector: grantSectorLabel(row, sectorLabels).toLowerCase(),
      agency: (row.funder_agency || row.funder || "").toLowerCase(), program: (row.program || "").toLowerCase(),
      fy: row.fiscal_year ?? null, end: row.end || "", amount: row.amount ?? null, ca: grantTri(row.ca_led), plastic: grantTri(row.plastic_related)
    };
  });
  return rows;
}

// Sorts in place. Empty values always sort last; ties fall back to newest fiscal year, then title.
export function sortGrantRows(rows, sort = {key: null, dir: "asc"}) {
  const key = sort.key;
  const mult = sort.dir === "desc" ? -1 : 1;
  const tie = (a, b) => {
    const fa = a._s.fy, fb = b._s.fy;
    if (fa !== fb) { if (fa === null) return 1; if (fb === null) return -1; return fb - fa; }
    return a._s.title < b._s.title ? -1 : a._s.title > b._s.title ? 1 : 0;
  };
  rows.sort((a, b) => {
    if (key) {
      const va = a._s[key], vb = b._s[key];
      const na = va === null || va === "", nb = vb === null || vb === "";
      if (na !== nb) return na ? 1 : -1;
      if (!na && va !== vb) return (va < vb ? -1 : 1) * mult;
    }
    return tie(a, b);
  });
  return rows;
}

export function formatGrantAmount(row) {
  if (row.amount === null) return "Not reported";
  if (row.currency && row.currency !== "USD") return `${row.amount.toLocaleString("en-US")} ${escapeHtml(row.currency)}`;
  return USD_FORMAT.format(row.amount);
}

export function grantCaLedState(row) {
  return row.ca_led === true ? "yes" : row.ca_led === false ? "no" : "unknown";
}

// filters: {q (lower-case), sector, agency, funderType, funder, program, yearFrom, yearTo,
// amountMin, amountMax, institutionType, tag, caLed, plastic}; numeric bounds are null when unset.
export function grantMatches(row, filters) {
  if (filters.plastic && row.plastic_related === false) return false;
  if (filters.sector && row.sector !== filters.sector) return false;
  if (filters.agency && row.funder_agency !== filters.agency) return false;
  if (filters.q && !row._q.includes(filters.q)) return false;
  if (filters.funderType && row.funder_type !== filters.funderType) return false;
  if (filters.funder && row.funder !== filters.funder) return false;
  if (filters.program && row.program !== filters.program) return false;
  if (filters.yearFrom !== null && (row.fiscal_year === null || row.fiscal_year < filters.yearFrom)) return false;
  if (filters.yearTo !== null && (row.fiscal_year === null || row.fiscal_year > filters.yearTo)) return false;
  if (filters.amountMin !== null && (row.amount === null || row.amount < filters.amountMin)) return false;
  if (filters.amountMax !== null && (row.amount === null || row.amount > filters.amountMax)) return false;
  if (filters.institutionType && row.institution_type !== filters.institutionType) return false;
  if (filters.tag && !row.domain_tags.includes(filters.tag)) return false;
  if (filters.caLed && grantCaLedState(row) !== filters.caLed) return false;
  return true;
}

// ---- Page hash --------------------------------------------------------------------------------

// Accepts "#<params>" and the legacy classic "#funding?<params>" form.
export function fundingParamsFromHash(hash) {
  const text = String(hash || "").replace(/^#/, "");
  const legacy = /^funding(\?|$)/.exec(text);
  return new URLSearchParams(legacy ? text.slice(legacy[0].length) : text);
}

export function fundingFromParams(params) {
  const controls = {};
  GRANT_FILTERS.forEach(({key, id}) => {
    controls[id] = params.get(key) || "";
  });
  const sortKey = params.get("sort");
  const sort = GRANT_COLUMNS.some((column) => column.key === sortKey)
    ? {key: sortKey, dir: params.get("dir") === "desc" ? "desc" : "asc"}
    : {key: null, dir: "asc"};
  return {controls, plastic: params.get("pl") !== "0", sort};
}

export function fundingToParams({controls, plastic, sort}) {
  const params = new URLSearchParams();
  GRANT_FILTERS.forEach(({key, id}) => {
    if (controls[id]) params.set(key, controls[id]);
  });
  if (!plastic) params.set("pl", "0");
  if (sort.key) {
    params.set("sort", sort.key);
    params.set("dir", sort.dir);
  }
  return params;
}

export function fundingHashFor(params) {
  const text = params.toString();
  return text ? `#${text}` : "";
}

function readFundingHash() {
  const {controls, plastic, sort} = fundingFromParams(fundingParamsFromHash(window.location.hash));
  Object.entries(controls).forEach(([id, value]) => {
    $(id).value = value;
  });
  $("grants-plastic").checked = plastic;
  state.grantsSort = sort;
}

function writeFundingHash() {
  const controls = {};
  GRANT_FILTERS.forEach(({id}) => {
    controls[id] = $(id).value;
  });
  const next = fundingHashFor(fundingToParams({controls, plastic: $("grants-plastic").checked, sort: state.grantsSort}));
  if (window.location.hash !== next) window.history.replaceState(null, "", next || window.location.pathname + window.location.search);
}

// ---- Awards: loading and filter controls ------------------------------------------------------

function loadGrants() {
  if (!state.grantsRequest) {
    state.grantsRequest = fetch(dataUrl("grants.json"), {cache: "no-cache"})
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .catch((error) => {
        state.grantsRequest = null;
        throw error;
      });
  }
  return state.grantsRequest;
}

function sectorLabelsOf() {
  return (state.grantsData && state.grantsData.sector_labels) || {};
}

function grantUniqueSorted(values) {
  return [...new Set(values.filter((value) => value !== null && value !== undefined && value !== ""))].sort((a, b) => String(a).localeCompare(String(b)));
}

function fillGrantSelect(id, values, allLabel, labelFor = (value) => value) {
  $(id).innerHTML = `<option value="">${escapeHtml(allLabel)}</option>` + values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(labelFor(value))}</option>`).join("");
}

function populateGrantFilters(payload) {
  const rows = payload.rows;
  prepareGrantRows(rows, payload.sector_labels || {});
  const countBy = (getter) => {
    const m = new Map();
    rows.forEach((row) => {
      const v = getter(row);
      if (v) m.set(v, (m.get(v) || 0) + 1);
    });
    return m;
  };
  const fillCounted = (id, counts, allLabel, labelFor, order) => {
    const entries = [...counts.entries()].sort(order);
    $(id).innerHTML = `<option value="">${escapeHtml(allLabel)}</option>` + entries.map(([value, n]) => `<option value="${escapeHtml(value)}" data-label="${escapeHtml(labelFor(value))}">${escapeHtml(labelFor(value))} (${n})</option>`).join("");
  };
  const sectorLabels = payload.sector_labels || {};
  fillCounted("grants-sector", countBy((row) => row.sector), "All sectors", (v) => sectorLabels[v] || v, (a, b) => (sectorLabels[a[0]] || a[0]).localeCompare(sectorLabels[b[0]] || b[0]));
  fillCounted("grants-agency", countBy((row) => row.funder_agency), "All funder agencies", (v) => v, (a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  fillGrantSelect("grants-funder", grantUniqueSorted(rows.map((row) => row.funder)), "All funders");
  fillGrantSelect("grants-program", grantUniqueSorted(rows.map((row) => row.program)), "All programs");
  fillGrantSelect("grants-institution-type", grantUniqueSorted(rows.map((row) => row.institution_type)), "All institution types");
  fillGrantSelect("grants-tag", grantUniqueSorted(rows.flatMap((row) => row.domain_tags)), "All topic tags", (tag) => AtlasTopics.label(tag));
  const years = rows.map((row) => row.fiscal_year).filter((year) => year !== null);
  if (years.length) {
    ["grants-year-from", "grants-year-to"].forEach((id) => {
      $(id).min = String(Math.min(...years));
      $(id).max = String(Math.max(...years));
    });
  }
  // Per-source subtotals only: each source uses its own amount basis, so the figures are never summed across sources.
  const subtotalRows = Object.entries(payload.sources).map(([name, info]) => {
    const amounts = rows.filter((row) => row.source === name && row.amount !== null);
    const subtotal = amounts.reduce((sum, row) => sum + row.amount, 0);
    return `<tr><th scope="row">${escapeHtml(GRANT_SOURCE_LABELS[name] || name)} (${escapeHtml(GRANT_FUNDER_LABELS[info.funder_type] || info.funder_type)})</th>`
      + `<td class="num">${amounts.length}</td><td class="num">${amounts.length ? USD_FORMAT.format(subtotal) : "None reported"}</td>`
      + `<td>${escapeHtml(info.amount_basis)}</td></tr>`;
  });
  $("grants-basis").innerHTML = `<table class="grants-subtotals"><caption>Per-source subtotals, as reported. These are not a total: sources use different amount bases and cannot be added.</caption>`
    + `<thead><tr><th scope="col">Source</th><th scope="col" class="num">Awards with an amount</th><th scope="col" class="num">Reported amount (USD)</th><th scope="col">Amount basis</th></tr></thead>`
    + `<tbody>${subtotalRows.join("")}</tbody></table><p class="data-note">${escapeHtml(payload.caveat)}</p>`;
}

function readGrantFilterValues() {
  const number = (id) => (($(id).value === "") ? null : Number($(id).value));
  return {
    q: $("grants-search").value.trim().toLowerCase(),
    sector: $("grants-sector").value,
    agency: $("grants-agency").value,
    funderType: $("grants-funder-type").value,
    funder: $("grants-funder").value,
    program: $("grants-program").value,
    yearFrom: number("grants-year-from"),
    yearTo: number("grants-year-to"),
    amountMin: number("grants-amount-min"),
    amountMax: number("grants-amount-max"),
    institutionType: $("grants-institution-type").value,
    tag: $("grants-tag").value,
    caLed: $("grants-ca-led").value,
    plastic: $("grants-plastic").checked
  };
}

// ---- Awards: table ----------------------------------------------------------------------------

export function grantFlagBadge(value) {
  const text = value === true ? "Yes" : value === false ? "No" : "Unknown";
  return `<span class="grants-badge${value === true ? " yes" : ""}">${text}</span>`;
}

export function grantRowHtml(row, sectorLabels = {}) {
  const title = row.url
    ? `<a href="${escapeHtml(row.url)}" target="_blank" rel="noreferrer">${escapeHtml(row.title)}</a>`
    : escapeHtml(row.title);
  const people = row.pi_names.length ? `<br><small>${escapeHtml(row.pi_names.join("; "))}</small>` : "";
  const tags = row.domain_tags.length ? `<div class="topic-chips">${AtlasTopics.sortTags([...row.domain_tags]).map((tag) => AtlasTopics.chip(tag)).join("")}</div>` : "";
  const detail = row.sector_detail ? ` title="${escapeHtml(row.sector_detail)}"` : "";
  return `<tr><th scope="row">${title}${people}${tags}</th>`
    + `<td>${escapeHtml(row.org || "Recipient not reported")}<br><small>${escapeHtml(row.institution_type)}${row.org_state ? ` · ${escapeHtml(row.org_state)}` : ""}</small></td>`
    + `<td><span class="grants-badge"${detail}>${escapeHtml(grantSectorLabel(row, sectorLabels))}</span></td>`
    + `<td>${escapeHtml(row.funder_agency || row.funder || "Not reported")}</td>`
    + `<td>${escapeHtml(row.program || "Not reported")}</td>`
    + `<td>${row.fiscal_year ?? "unknown"}<br><small>${escapeHtml(row.start || "start not reported")}</small></td>`
    + `<td>${escapeHtml(row.end || "not reported")}</td>`
    + `<td class="num"><span title="${escapeHtml(row.amount_basis)}">${formatGrantAmount(row)}</span></td>`
    + `<td>${grantFlagBadge(row.ca_led)}</td>`
    + `<td>${grantFlagBadge(row.plastic_related)}</td></tr>`;
}

export function grantsHeadHtml(sort = {key: null, dir: "asc"}) {
  return "<tr>" + GRANT_COLUMNS.map((column) => {
    const active = sort.key === column.key;
    const aria = active ? (sort.dir === "desc" ? "descending" : "ascending") : "none";
    const arrow = active ? (sort.dir === "desc" ? "▼" : "▲") : "⇅";
    return `<th scope="col" aria-sort="${aria}"${column.num ? ' class="num"' : ""}><button type="button" class="grants-sort" data-sort="${column.key}">${column.label}<span class="grants-arrow" aria-hidden="true">${arrow}</span></button></th>`;
  }).join("") + "</tr>";
}

function renderGrantsTable(rows) {
  const pages = Math.max(1, Math.ceil(rows.length / state.grantsPageSize));
  state.grantsPage = Math.min(state.grantsPage, pages - 1);
  const slice = rows.slice(state.grantsPage * state.grantsPageSize, (state.grantsPage + 1) * state.grantsPageSize);
  const labels = sectorLabelsOf();
  const body = slice.length ? slice.map((row) => grantRowHtml(row, labels)).join("") : `<tr><td colspan="${GRANT_COLUMNS.length}" class="empty">No awards match these filters. Try resetting one of the selections.</td></tr>`;
  $("grants-table").innerHTML = `<table class="grants-table"><caption class="grants-sr-only">Awards matching the filters; column headers sort the table</caption><thead>${grantsHeadHtml(state.grantsSort)}</thead><tbody>${body}</tbody></table>`;
  $("grants-page").textContent = rows.length ? `Page ${state.grantsPage + 1} of ${pages}` : "";
  $("grants-prev").disabled = state.grantsPage === 0;
  $("grants-next").disabled = state.grantsPage >= pages - 1;
}

function renderGrantChips() {
  const chips = [];
  GRANT_FILTERS.forEach(({id}) => {
    const control = $(id);
    if (!control.value) return;
    const field = document.querySelector(`label[for="${id}"]`).textContent;
    const option = control.tagName === "SELECT" ? control.selectedOptions[0] : null;
    const text = option ? (option.dataset.label || option.textContent) : control.value;
    chips.push(`<li><button type="button" data-clear="${id}" aria-label="Remove filter ${escapeHtml(field)}: ${escapeHtml(text)}">${escapeHtml(field)}: ${escapeHtml(text)} ✕</button></li>`);
  });
  if (!$("grants-plastic").checked) chips.push('<li><button type="button" data-clear="grants-plastic" aria-label="Remove filter: including non-plastic awards">Including non-plastic awards ✕</button></li>');
  if (chips.length) chips.push('<li><button type="button" data-clear="all">Reset all filters and sort</button></li>');
  $("grants-chips").innerHTML = chips.join("");
}

function resetGrantFilters() {
  GRANT_FILTERS.forEach(({id}) => {
    $(id).value = "";
  });
  $("grants-plastic").checked = true;
  state.grantsSort = {key: null, dir: "asc"};
  state.grantsPage = 0;
  renderFunding();
}

// ---- Awards: CSV export -----------------------------------------------------------------------

export function grantCsvCell(value) {
  let text = Array.isArray(value) ? value.join(" | ") : value === null || value === undefined ? "" : String(value);
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

// CSV of the given rows (defaults to the rows matching the current filters), BOM-prefixed as in the classic file.
export function buildGrantsCsv(rows = state.grantsFiltered) {
  const lines = [GRANT_CSV_COLUMNS.join(",")];
  rows.forEach((row) => {
    const cells = GRANT_CSV_COLUMNS.map((column) => grantCsvCell(column === "funder_chain" ? row.funder_chain.join(" > ") : row[column]));
    lines.push(cells.join(","));
  });
  return `\uFEFF${lines.join("\r\n")}\r\n`;
}

function downloadGrantsCsv() {
  const blob = new Blob([buildGrantsCsv()], {type: "text/csv;charset=utf-8"});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "ca_plastics_awards_filtered.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 0);
}

// ---- Awards: render and bind ------------------------------------------------------------------

function renderFunding() {
  const filters = readGrantFilterValues();
  state.grantsFiltered = sortGrantRows(state.grantsData.rows.filter((row) => grantMatches(row, filters)), state.grantsSort);
  const withAmount = state.grantsFiltered.filter((row) => row.amount !== null);
  $("grants-status").textContent = `${state.grantsFiltered.length} of ${state.grantsData.rows.length} awards match. ${withAmount.length} report an amount.`;
  state.viz.update(state.grantsFiltered, sectorLabelsOf());
  renderGrantsTable(state.grantsFiltered);
  renderGrantChips();
  writeFundingHash();
}

function bindFundingControls() {
  document.querySelectorAll("#grants-filters input, #grants-filters select").forEach((control) => {
    const isText = control.type === "search";
    control.addEventListener(control.type === "number" || isText ? "input" : "change", () => {
      const run = () => {
        state.grantsPage = 0;
        renderFunding();
      };
      if (isText) {
        window.clearTimeout(state.grantsSearchTimer);
        state.grantsSearchTimer = window.setTimeout(run, 150);
      } else run();
    });
  });
  $("grants-filters").addEventListener("submit", (event) => event.preventDefault());
  $("grants-reset").addEventListener("click", resetGrantFilters);
  $("grants-chips").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-clear]");
    if (!button) return;
    if (button.dataset.clear === "all") return resetGrantFilters();
    const control = $(button.dataset.clear);
    if (control.type === "checkbox") control.checked = true;
    else control.value = "";
    state.grantsPage = 0;
    renderFunding();
  });
  $("grants-table").addEventListener("click", (event) => {
    const button = event.target.closest("button.grants-sort");
    if (!button) return;
    const key = button.dataset.sort;
    state.grantsSort = state.grantsSort.key === key && state.grantsSort.dir === "asc" ? {key, dir: "desc"} : {key, dir: "asc"};
    state.grantsPage = 0;
    renderFunding();
    const next = $("grants-table").querySelector(`button[data-sort="${key}"]`);
    if (next) next.focus();
  });
  $("grants-page-size").addEventListener("change", () => {
    state.grantsPageSize = Number($("grants-page-size").value) || 50;
    state.grantsPage = 0;
    renderGrantsTable(state.grantsFiltered);
  });
  $("grants-prev").addEventListener("click", () => {
    state.grantsPage = Math.max(0, state.grantsPage - 1);
    renderGrantsTable(state.grantsFiltered);
  });
  $("grants-next").addEventListener("click", () => {
    state.grantsPage += 1;
    renderGrantsTable(state.grantsFiltered);
  });
  $("grants-csv").addEventListener("click", downloadGrantsCsv);
}

function showFunding() {
  // Narrow screens start with the filter panel collapsed so the table stays in view.
  const filterPanel = $("grants-filter-panel");
  if (filterPanel && !filterPanel.dataset.sized) {
    filterPanel.dataset.sized = "1";
    if (window.matchMedia("(max-width: 700px)").matches) filterPanel.open = false;
  }
  if (state.grantsReady) {
    readFundingHash();
    renderFunding();
    return;
  }
  $("grants-status").textContent = "Loading awards…";
  loadGrants()
    .then((payload) => {
      state.grantsData = payload;
      populateGrantFilters(payload);
      bindFundingControls();
      state.grantsReady = true;
      readFundingHash();
      renderFunding();
    })
    .catch(() => {
      $("grants-status").textContent = "";
      $("grants-table").innerHTML = '<p class="empty">Awards could not be loaded right now.</p>';
    });
}

// Mounts the whole Funding view: open calls, then awards (same order as the classic selectTab).
// Call once from the page's js block, after the panel markup has been rendered.
export function mountFunding() {
  // The charts follow the filter form: update() runs on every change to the awards (renderFunding).
  if (!state.viz) state.viz = mountFundingViz($("grants-viz"));
  showOpenCalls();
  showFunding();
  if (!state.listening) {
    state.listening = true;
    window.addEventListener("hashchange", () => {
      if (state.grantsReady) showFunding();
    });
  }
}
