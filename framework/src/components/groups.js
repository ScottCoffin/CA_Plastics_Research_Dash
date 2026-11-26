// Community groups page (CG-13, Add-on A4; docs/BFFP.md §9.2-§9.3). The page is /groups (framework/src/groups.md).
// It renders the coverage panel, the roster table with its filters, and the group card from
// site/data/global/groups/groups.json and coverage.json. Pure helpers are exported for the Node runtime test
// (tests/framework_groups_runtime.mjs). Every value is escaped before it reaches innerHTML.
import {escapeHtml} from "./atlas.js";
import {groupsTreeHtml, mountGroupsTree, treeHashState} from "./groups_tree.js";

export const CONTACT_EMAIL = "theplastiverse@gmail.com";
export const PAGE_SIZE = 50;
export const SORT_KEYS = ["name", "country"];
export const STANDING_NOTE = "Tags were entered by volunteers from public sources and have not been verified by the group unless marked Confirmed.";
export const STATUS_OPTIONS = [
  {value: "not_tagged", label: "Not yet tagged"},
  {value: "volunteer", label: "Volunteer-tagged"},
  {value: "reviewed", label: "Reviewed"},
  {value: "confirmed", label: "Confirmed by group"},
  {value: "cannot", label: "Could not be tagged from public pages"},
];
export const DEFAULT_STATE = Object.freeze({q: "", region: "", country: "", status: "", sort: "name", dir: "asc", page: 1, group: ""});

const TAGGED_STATUSES = new Set(["ambassador_tagged", "reviewed", "group_confirmed"]);
const CENTRALITY_LABELS = {
  primary: "Primary plastics focus",
  substantial: "Substantial plastics focus",
  incidental: "Incidental plastics focus",
  none: "No stated plastics focus",
};
const countryNames = typeof Intl.DisplayNames === "function" ? new Intl.DisplayNames(["en"], {type: "region"}) : null;

const list = (value) => (Array.isArray(value) ? value : []);
const text = (value) => String(value ?? "").trim();
const searchKey = (value) => text(value).normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const formatInt = (value) => Number(value || 0).toLocaleString("en-US");

// Badge key for a raw roster status. "unlabelled" and "assigned" both read as not yet tagged.
export function statusKey(status) {
  if (status === "ambassador_tagged") return "volunteer";
  if (status === "reviewed") return "reviewed";
  if (status === "group_confirmed") return "confirmed";
  if (status === "cannot_determine") return "cannot";
  return "not_tagged";
}

export function statusLabel(status) {
  return STATUS_OPTIONS.find((option) => option.value === statusKey(status)).label;
}

export function isTagged(group) {
  return TAGGED_STATUSES.has(group?.status);
}

export function countryName(code) {
  const value = text(code).toUpperCase();
  if (!/^[A-Z]{2}$/.test(value)) return "";
  try {
    return countryNames?.of(value) || value;
  } catch {
    return value;
  }
}

export function regionLabel(region) {
  const value = text(region);
  return !value || value === "region_unknown" ? "Region not known" : value;
}

export function countryLabel(group) {
  return countryName(group?.country) || "Country not stated";
}

// Only http(s) links are rendered (no javascript: targets).
export function safeUrl(url) {
  const value = typeof url === "string" ? url.trim() : "";
  return /^https?:\/\/[^\s"<>]+$/i.test(value) ? value : null;
}

export function provenanceLine(group) {
  return group?.bffp_listed && group.bffp_listed_asof ? `Listed as a BFFP member as of ${group.bffp_listed_asof}` : "";
}

// Name search (accents ignored), region, country and status filters. Empty filters match everything.
export function filterGroups(groups, filters = {}) {
  const q = searchKey(filters.q);
  return list(groups).filter((group) =>
    (!q || searchKey(group.name).includes(q)) &&
    (!filters.region || (text(group.region) || "region_unknown") === filters.region) &&
    (!filters.country || text(group.country).toUpperCase() === filters.country) &&
    (!filters.without_tags || !isTagged(group)) &&
    (!filters.status || statusKey(group.status) === filters.status));
}

// Only name and country sort (no score ordering, rule 6). Blank values sort last in both directions.
export function sortGroups(groups, key = "name", dir = "asc") {
  const sortKey = SORT_KEYS.includes(key) ? key : "name";
  const sign = dir === "desc" ? -1 : 1;
  const valueOf = (group) => (sortKey === "country" ? countryName(group.country) : text(group.name));
  return [...list(groups)].sort((a, b) => {
    const va = valueOf(a);
    const vb = valueOf(b);
    if ((!va || !vb) && va !== vb) return va ? -1 : 1;
    const byValue = sign * va.localeCompare(vb, "en", {sensitivity: "base"});
    if (byValue) return byValue;
    return text(a.name).localeCompare(text(b.name), "en") || text(a.group_id).localeCompare(text(b.group_id));
  });
}

// Page arithmetic for the table: the page is clamped to 1..pages.
export function pageOf(total, page = 1, size = PAGE_SIZE) {
  const count = Math.max(0, Math.floor(Number(total)) || 0);
  const pages = Math.max(1, Math.ceil(count / size));
  const current = Math.min(pages, Math.max(1, Math.floor(Number(page)) || 1));
  const start = count ? (current - 1) * size : 0;
  return {page: current, pages, start, end: Math.min(count, start + size), total: count};
}

// URL hash state. Defaults are left out of the hash, so the plain page has an empty hash.
export function parseHash(hash = "") {
  const params = new URLSearchParams(String(hash).replace(/^#/, ""));
  const state = {...DEFAULT_STATE};
  for (const key of ["q", "region", "country", "group"]) if (params.has(key)) state[key] = params.get(key);
  if (params.get("without_tags") === "1") state.without_tags = true;
  if (STATUS_OPTIONS.some((option) => option.value === params.get("status"))) state.status = params.get("status");
  if (SORT_KEYS.includes(params.get("sort"))) state.sort = params.get("sort");
  if (params.get("dir") === "desc") state.dir = "desc";
  const page = Number.parseInt(params.get("page"), 10);
  if (Number.isInteger(page) && page > 1) state.page = page;
  return state;
}

export function formatHash(state = {}) {
  const value = {...DEFAULT_STATE, ...state};
  const params = new URLSearchParams();
  for (const key of ["q", "region", "country", "status", "group"]) if (value[key]) params.set(key, value[key]);
  if (value.without_tags) params.set("without_tags", "1");
  if (value.sort !== DEFAULT_STATE.sort) params.set("sort", value.sort);
  if (value.dir !== DEFAULT_STATE.dir) params.set("dir", value.dir);
  if (value.page > 1) params.set("page", String(value.page));
  const serialised = params.toString();
  return serialised ? `#${serialised}` : "";
}

function coverageRow(key, label, roster, tagged) {
  const rosterCount = Math.max(0, Number(roster) || 0);
  const taggedCount = Math.max(0, Number(tagged) || 0);
  return {key, label, roster: rosterCount, tagged: taggedCount, percent: rosterCount ? Math.round((taggedCount / rosterCount) * 1000) / 10 : null};
}

// The first row is the whole roster; then one row per M49 region, largest first.
export function coverageRows(coverage) {
  const byRegion = coverage && typeof coverage.by_region === "object" && coverage.by_region ? coverage.by_region : {};
  const regions = Object.entries(byRegion)
    .map(([region, value]) => coverageRow(region, regionLabel(region), value?.roster, value?.tagged))
    .sort((a, b) => b.roster - a.roster || a.label.localeCompare(b.label, "en"));
  const roster = Number(coverage?.roster_total) || regions.reduce((sum, row) => sum + row.roster, 0);
  const tagged = Number(coverage?.tagged_total) || regions.reduce((sum, row) => sum + row.tagged, 0);
  return [coverageRow("all", "All regions", roster, tagged), ...regions];
}

export function centralityLabel(value) {
  const key = text(value);
  return key ? CENTRALITY_LABELS[key] || key.replace(/_/g, " ") : "";
}

export function badgeHtml(status) {
  const key = statusKey(status);
  return `<span class="gv-badge gv-badge--${key}">${escapeHtml(statusLabel(status))}</span>`;
}

function sortMark(sort, dir, key) {
  if (sort !== key) return "";
  return ` <span aria-hidden="true">${dir === "desc" ? "▼" : "▲"}</span>`;
}

function sortAria(sort, dir, key) {
  if (sort !== key) return "none";
  return dir === "desc" ? "descending" : "ascending";
}

export function rowHtml(group) {
  const name = escapeHtml(group.name || "Unnamed group");
  const site = safeUrl(group.url);
  const websiteCell = site
    ? `<a href="${escapeHtml(site)}" rel="noopener nofollow">Website<span class="gv-sr"> of ${name}</span></a>`
    : "No website listed";
  const helpCell = isTagged(group)
    ? ""
    : `<a href="./ambassadors">Help tag this group<span class="gv-sr"> ${name}</span></a>`;
  return `<tr>
    <th scope="row"><button type="button" class="gv-name" data-group="${escapeHtml(group.group_id)}" aria-haspopup="dialog">${name}</button></th>
    <td>${escapeHtml(regionLabel(group.region))}</td>
    <td>${escapeHtml(countryLabel(group))}</td>
    <td>${badgeHtml(group.status)}</td>
    <td>${websiteCell}</td>
    <td>${helpCell}</td>
  </tr>`;
}

export function coverageHtml(coverage) {
  const note = text(coverage?.denominator_note);
  const bars = coverageRows(coverage).map((row) => {
    const value = row.roster
      ? `${formatInt(row.tagged)} of ${formatInt(row.roster)} tagged (${row.percent.toFixed(1)}%)`
      : "No groups on the roster";
    const width = row.percent == null ? 0 : Math.min(100, row.percent);
    return `<li class="gv-bar"><span class="gv-bar-label">${escapeHtml(row.label)}</span>` +
      `<span class="gv-track" aria-hidden="true"><span class="gv-fill" style="width: ${width}%"></span></span>` +
      `<span class="gv-bar-value">${escapeHtml(value)}</span></li>`;
  }).join("");
  return `<section class="gv-panel" aria-labelledby="gv-cov-title">
    <h2 id="gv-cov-title">Tagging coverage</h2>
    ${note ? `<p class="gv-caption">${escapeHtml(note)}</p>` : ""}
    <ul class="gv-bars">${bars}</ul>
  </section>`;
}

function fact(label, value) {
  return value ? `<div class="gv-fact"><dt>${escapeHtml(label)}</dt><dd>${value}</dd></div>` : "";
}

function quoteHtml(evidence) {
  const quote = text(evidence?.quote);
  if (!quote) return "";
  const source = safeUrl(evidence.url);
  const accessed = text(evidence.accessed_at);
  const link = source ? `<a href="${escapeHtml(source)}" rel="noopener nofollow">Source</a>` : "";
  const meta = [link, accessed ? `accessed ${escapeHtml(accessed)}` : ""].filter(Boolean).join(", ");
  return `<blockquote>${escapeHtml(quote)}</blockquote>${meta ? `<p class="gv-meta">${meta}</p>` : ""}`;
}

// Group card (§9.2): only the fields that exist are shown; null or empty tag fields are omitted.
export function cardHtml(group) {
  const site = safeUrl(group?.url);
  const places = list(group?.places).map((code) => countryName(code) || text(code)).filter(Boolean);
  const activities = list(group?.primary_activities).map(text).filter(Boolean);
  const languages = list(group?.website_languages).map(text).filter(Boolean);
  const evidence = list(group?.evidence).map(quoteHtml).filter(Boolean);
  const affiliations = list(group?.stated_affiliations).map((item) => {
    const target = text(item?.target_name) || text(item?.target_group_id);
    const relation = text(item?.relation).replace(/_/g, " ");
    const quote = quoteHtml(item?.evidence);
    return target ? `<li><b>${escapeHtml(relation || "Affiliated with")}</b>: ${escapeHtml(target)}${quote}</li>` : "";
  }).filter(Boolean);
  const provenance = provenanceLine(group);
  const facts = [
    fact("Website", site ? `<a href="${escapeHtml(site)}" rel="noopener nofollow">${escapeHtml(site)}</a>` : ""),
    fact("Country", escapeHtml(countryName(group?.country))),
    fact("Places", places.length ? escapeHtml(places.join(", ")) : ""),
    fact("Status", badgeHtml(group?.status)),
    fact("Entity type", escapeHtml(text(group?.entity_type).replace(/_/g, " "))),
    fact("Sector", escapeHtml(text(group?.sector).replace(/_/g, " "))),
    fact("Plastics focus", escapeHtml(centralityLabel(group?.plastics_centrality))),
    fact("Activities", activities.length ? `<ol class="gv-list">${activities.map((a) => `<li>${escapeHtml(a)}</li>`).join("")}</ol>` : ""),
    fact("Website languages", languages.length ? escapeHtml(languages.join(", ")) : ""),
  ].join("");
  return `<div class="gv-card-body">
    <div class="gv-card-head">
      <h2 id="gv-card-title">${escapeHtml(group?.name || "Unnamed group")}</h2>
      <button type="button" class="gv-btn" data-close>Close</button>
    </div>
    <dl class="gv-facts">${facts}</dl>
    ${evidence.length ? `<h3>Evidence</h3><div class="gv-evidence">${evidence.join("")}</div>` : ""}
    ${affiliations.length ? `<h3>Stated affiliations</h3><ul class="gv-affiliations">${affiliations.join("")}</ul>` : ""}
    ${provenance ? `<p class="gv-provenance">${escapeHtml(provenance)}</p>` : ""}
    <p class="gv-standing">${escapeHtml(STANDING_NOTE)}</p>
    <p class="gv-correct"><b>Suggest a correction.</b> Write to ${escapeHtml(CONTACT_EMAIL)} with the group name and what should change.</p>
    <div class="gv-card-foot"><button type="button" class="gv-btn" data-close>Close</button></div>
  </div>`;
}

function controlsHtml(groups, state) {
  const regions = [...new Set(groups.map((g) => text(g.region) || "region_unknown"))]
    .map((value) => ({value, label: regionLabel(value)}))
    .sort((a, b) => a.label.localeCompare(b.label, "en"));
  const countries = [...new Set(groups.map((g) => text(g.country).toUpperCase()).filter(Boolean))]
    .map((value) => ({value, label: countryName(value) || value}))
    .sort((a, b) => a.label.localeCompare(b.label, "en"));
  const options = (items, selected, all) => [`<option value="">${all}</option>`]
    .concat(items.map((item) => `<option value="${escapeHtml(item.value)}"${item.value === selected ? " selected" : ""}>${escapeHtml(item.label)}</option>`))
    .join("");
  return `<div class="gv-controls" role="search">
    <div class="gv-field gv-field--search"><label for="gv-q">Search by group name</label>
      <input id="gv-q" type="search" autocomplete="off" value="${escapeHtml(state.q)}"></div>
    <div class="gv-field"><label for="gv-region">Region</label>
      <select id="gv-region">${options(regions, state.region, "All regions")}</select></div>
    <div class="gv-field"><label for="gv-country">Country</label>
      <select id="gv-country">${options(countries, state.country, "All countries")}</select></div>
    <div class="gv-field"><label for="gv-status">Status</label>
      <select id="gv-status">${options(STATUS_OPTIONS, state.status, "All statuses")}</select></div>
    <div class="gv-field"><button type="button" class="gv-btn" data-action="clear">Clear filters</button></div>
  </div>`;
}

function resultsHtml(groups, state) {
  const filtered = sortGroups(filterGroups(groups, state), state.sort, state.dir);
  const pg = pageOf(filtered.length, state.page);
  const rows = filtered.slice(pg.start, pg.end).map(rowHtml).join("");
  const caption = pg.total
    ? `Showing ${formatInt(pg.start + 1)} to ${formatInt(pg.end)} of ${formatInt(pg.total)} groups that match the filters.`
    : "No groups match these filters.";
  const head = (key, label) => `<th scope="col" aria-sort="${sortAria(state.sort, state.dir, key)}">` +
    `<button type="button" class="gv-sort" data-sort="${key}">${label}${sortMark(state.sort, state.dir, key)}</button></th>`;
  return `<p class="gv-results-caption" id="gv-count" tabindex="-1">${escapeHtml(caption)}</p>
    <div class="gv-table-wrap" role="region" aria-labelledby="gv-count" tabindex="0">
    <table class="gv-table">
      <caption class="gv-sr">Community groups on the BFFP roster, with tagging status. Select a group name to open its card.</caption>
      <thead><tr>${head("name", "Group")}<th scope="col">Region</th>${head("country", "Country")}<th scope="col">Status</th><th scope="col">Website</th><th scope="col">Tagging</th></tr></thead>
      <tbody>${rows || `<tr><td colspan="6">No groups match these filters.</td></tr>`}</tbody>
    </table>
    </div>
    ${pg.pages > 1 ? `<nav class="gv-pager" aria-label="Table pages">
      <button type="button" class="gv-btn" data-page-target="${pg.page - 1}"${pg.page <= 1 ? " disabled" : ""}>Previous</button>
      <span id="gv-page-status" tabindex="-1">Page ${pg.page} of ${pg.pages}</span>
      <button type="button" class="gv-btn" data-page-target="${pg.page + 1}"${pg.page >= pg.pages ? " disabled" : ""}>Next</button>
    </nav>` : ""}`;
}

// Mounts the page into root. load() resolves to {groups, coverage, tree}; tree may be unavailable.
export async function mountGroups(root, load) {
  root.innerHTML = '<p class="gv-status">Loading the roster…</p>';
  let data;
  try {
    data = await load();
  } catch {
    root.innerHTML = '<p class="gv-status">The roster could not be loaded. Try again later.</p>';
    return;
  }
  const groups = list(data?.groups);
  const byId = new Map(groups.map((group) => [group.group_id, group]));
  let state = {...DEFAULT_STATE, ...parseHash(location.hash)};
  root.innerHTML = `${coverageHtml(data?.coverage ?? {})}
    ${groupsTreeHtml(data?.tree, treeHashState(location.hash), treeHashState(location.hash).query)}
    <section class="gv-panel" aria-labelledby="gv-table-title">
      <h2 id="gv-table-title">Roster</h2>
      <p class="gv-tree-filter-note" id="gv-tree-filter-note"${state.without_tags ? "" : " hidden"} aria-live="polite">Showing only groups without tags, including groups that could not be tagged from public pages. <button type="button" class="gv-name" data-action="clear">Clear this filter</button></p>
      ${controlsHtml(groups, state)}
      <div id="gv-results"></div>
    </section>
    <dialog id="gv-card" class="gv-card" aria-labelledby="gv-card-title"></dialog>`;
  const results = root.querySelector("#gv-results");
  const dialog = root.querySelector("#gv-card");

  const syncHash = () => {
    const params = new URLSearchParams(formatHash(state).replace(/^#/, ""));
    const current = new URLSearchParams(location.hash.replace(/^#/, ""));
    for (const key of ["tree", "tree_all", "tree_open", "tree_closed", "tree_find"]) if (current.has(key)) params.set(key, current.get(key));
    const value = params.toString();
    history.replaceState(null, "", `${location.pathname}${location.search}${value ? `#${value}` : ""}`);
  };
  const syncControls = () => {
    root.querySelector("#gv-q").value = state.q;
    root.querySelector("#gv-region").value = state.region;
    root.querySelector("#gv-country").value = state.country;
    root.querySelector("#gv-status").value = state.status;
  };
  const renderResults = () => {
    const pg = pageOf(filterGroups(groups, state).length, state.page);
    state.page = pg.page;
    results.innerHTML = resultsHtml(groups, state);
    const note = root.querySelector("#gv-tree-filter-note");
    if (note) note.hidden = !state.without_tags;
  };
  const setState = (patch) => {
    state = {...state, ...patch};
    renderResults();
    syncHash();
  };
  const showCard = (id) => {
    const group = byId.get(id);
    if (!group) return false;
    dialog.innerHTML = cardHtml(group);
    if (!dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
    return true;
  };
  const refocus = (selector) => root.querySelector(selector)?.focus();

  mountGroupsTree(root, data?.tree, {
    onGroup: (id) => {
      if (showCard(id)) { state = {...state, group: id}; syncHash(); }
    },
    onRoster: (filters) => {
      state = {...state, region: "", country: "", ...filters, q: "", status: "", without_tags: true, page: 1, group: ""};
      syncControls();
      renderResults();
      syncHash();
      const result = root.querySelector("#gv-count");
      result?.focus({preventScroll: true});
      result?.scrollIntoView({behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start"});
    },
  });

  root.addEventListener("input", (event) => {
    if (event.target.id === "gv-q") setState({q: event.target.value, page: 1, without_tags: false});
  });
  root.addEventListener("change", (event) => {
    const field = {"gv-region": "region", "gv-country": "country", "gv-status": "status"}[event.target.id];
    if (field) setState({[field]: event.target.value, page: 1, without_tags: false});
  });
  root.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button || !root.contains(button)) return;
    if (button.dataset.group) {
      if (showCard(button.dataset.group)) {
        state = {...state, group: button.dataset.group};
        syncHash();
      }
    } else if (button.dataset.sort) {
      const key = button.dataset.sort;
      const dir = state.sort === key && state.dir === "asc" ? "desc" : "asc";
      setState({sort: key, dir, page: 1});
      refocus(`[data-sort="${key}"]`);
    } else if (button.dataset.pageTarget) {
      setState({page: Number(button.dataset.pageTarget)});
      refocus("#gv-page-status");
    } else if (button.dataset.action === "clear") {
      state = {...DEFAULT_STATE, sort: state.sort, dir: state.dir, without_tags: false};
      syncControls();
      renderResults();
      syncHash();
    }
  });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog || event.target.closest("[data-close]")) dialog.close();
  });
  dialog.addEventListener("close", () => {
    if (state.group) {
      state = {...state, group: ""};
      syncHash();
    }
  });
  window.addEventListener("hashchange", () => {
    state = {...DEFAULT_STATE, ...parseHash(location.hash)};
    syncControls();
    renderResults();
    if (state.group && byId.has(state.group)) showCard(state.group);
    else if (dialog.open) dialog.close();
  });

  renderResults();
  if (state.group) showCard(state.group);
  syncHash();
}
