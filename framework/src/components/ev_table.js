// Publication table and "New in the last 2 weeks" callout for the Evidence map (EV-TABLE).
// Plain DOM; the filtering, sorting and paging rules live in ev_table_model.js.
import "./shared/topics.js";
import {loadJson} from "./atlas.js";
import {
  DEFAULT_DIRS,
  authorLine,
  dateLabel,
  escapeHtml,
  filterRows,
  normaliseRows,
  pageInfo,
  pageRows,
  recentRows,
  sortRows,
  toCsv
} from "./ev_table_model.js";

const SORT_OPTIONS = [
  ["pub_date", "Published"],
  ["year", "Year"],
  ["cited_by_count", "Citations"],
  ["title", "Title"],
  ["journal", "Journal"]
];
const COLUMN_COUNT = 6;

// Abstracts are a large file, so they load once, on the first "Abstract" expand, and are shared.
let abstractsPromise = null;

function loadAbstracts() {
  if (!abstractsPromise) {
    abstractsPromise = loadJson("work_text/abstracts.json")
      .then((payload) => (payload && payload.abstracts && typeof payload.abstracts === "object" ? payload.abstracts : {}))
      .catch(() => {
        abstractsPromise = null;
        return null;
      });
  }
  return abstractsPromise;
}

function topicApi() {
  return typeof window !== "undefined" ? window.AtlasTopics || null : null;
}

function topicChips(row) {
  const tags = [...row.domain_tags, ...row.facet_tags];
  const api = topicApi();
  if (!api) return tags.map((tag) => escapeHtml(tag)).join(" ");
  return api.sortTags(tags).map((tag) => api.chip(tag)).join(" ");
}

function linkLinks(row) {
  const links = [];
  const title = row.title || "this work";
  if (row.doi) links.push(`<a href="${escapeHtml(row.doi)}" aria-label="${escapeHtml(`DOI for ${title}`)}">DOI</a>`);
  if (row.is_oa && row.oa_url) {
    links.push(`<a href="${escapeHtml(row.oa_url)}" aria-label="${escapeHtml(`Open access copy of ${title}`)}">Open access copy</a>`);
  }
  if (/^W\d+$/.test(row.work_id)) {
    links.push(`<a href="https://openalex.org/${row.work_id}" aria-label="${escapeHtml(`OpenAlex record for ${title}`)}">OpenAlex record</a>`);
  }
  return links.length ? `<div class="ev-links">${links.join("")}</div>` : "";
}

function abstractHtml(row, title) {
  if (!row.has_abstract) return `<p class="ev-no-abstract">No abstract available</p>`;
  return `<details class="ev-abstract" data-id="${escapeHtml(row.work_id)}">`
    + `<summary>Abstract<span class="ev-sr-only"> for ${escapeHtml(title)}</span></summary>`
    + `<p class="ev-abstract-text">Loading abstract…</p></details>`;
}

function rowHtml(row, isNew) {
  const title = row.title || "Untitled work";
  const badge = isNew ? ` <span class="ev-badge">New</span>` : "";
  const journal = row.journal ? escapeHtml(row.journal) : "";
  return `<tr>`
    + `<td>${escapeHtml(dateLabel(row))}</td>`
    + `<td><span class="ev-title">${escapeHtml(title)}</span>${badge}`
    + `<div class="ev-authors">${escapeHtml(authorLine(row))}</div>${abstractHtml(row, title)}</td>`
    + `<td>${journal}</td>`
    + `<td><div class="topic-chips">${topicChips(row)}</div></td>`
    + `<td class="num">${row.cited_by_count.toLocaleString("en-US")}</td>`
    + `<td>${linkLinks(row)}</td>`
    + `</tr>`;
}

const DEFAULT_HINT = "Select heatmap cells or topic names to narrow this table.";

function shellHtml(hint = DEFAULT_HINT) {
  const sortOptions = SORT_OPTIONS.map(([key, label]) => `<option value="${key}">${label}</option>`).join("");
  const header = (key, label, cls = "") => `<th scope="col"${cls ? ` class="${cls}"` : ""}>`
    + `<button type="button" class="ev-sort" data-sort="${key}">${label}</button></th>`;
  return (hint ? `<p class="ev-hint">${escapeHtml(hint)}</p>` : "")
    + `<div class="ev-table-tools">`
    + `<label class="ev-field ev-field-search"><span>Search</span>`
    + `<input type="search" data-role="q" autocomplete="off" placeholder="Title, author or journal"></label>`
    + `<label class="ev-field"><span>Minimum citations</span>`
    + `<input type="number" min="0" step="1" inputmode="numeric" data-role="min"></label>`
    + `<label class="ev-check"><input type="checkbox" data-role="oa"> Open access only</label>`
    + `<label class="ev-check"><input type="checkbox" data-role="recent"> New (last 2 weeks) only</label>`
    + `<label class="ev-field"><span>Sort by</span><select data-role="sort">${sortOptions}</select></label>`
    + `<button type="button" class="ev-btn" data-role="dir">Descending</button>`
    + `<button type="button" class="ev-btn" data-role="csv">Download CSV</button>`
    + `</div>`
    + `<p class="ev-status" data-role="status" aria-live="polite">Loading works…</p>`
    + `<div class="ev-table-scroll"><table class="ev-works">`
    + `<caption>Published works with a California author</caption>`
    + `<thead><tr>${header("pub_date", "Published")}${header("title", "Title")}${header("journal", "Journal")}`
    + `<th scope="col">Topics</th>${header("cited_by_count", "Citations", "num")}<th scope="col">Links</th></tr></thead>`
    + `<tbody data-role="rows"></tbody></table></div>`
    + `<nav class="ev-pager" aria-label="Works pages"><button type="button" class="ev-btn" data-role="prev">Previous</button>`
    + `<span data-role="range" aria-live="off"></span>`
    + `<button type="button" class="ev-btn" data-role="next">Next</button></nav>`;
}

// Mounts the table into container. Resolves once the rows are loaded (never rejects; a load
// failure is shown inside the table). update(ids) limits the table to those work_ids; null shows all.
// hint: the line above the controls (default: the Evidence map heatmap hint; "" for none).
export function mountWorksTable(container, {today = new Date(), hint = DEFAULT_HINT} = {}) {
  container.classList.add("ev-table-root");
  container.innerHTML = shellHtml(hint);
  const q = (role) => container.querySelector(`[data-role="${role}"]`);
  const el = {
    tools: container.querySelector(".ev-table-tools"),
    q: q("q"),
    min: q("min"),
    oa: q("oa"),
    recent: q("recent"),
    sort: q("sort"),
    dir: q("dir"),
    csv: q("csv"),
    status: q("status"),
    rows: q("rows"),
    prev: q("prev"),
    next: q("next"),
    range: q("range")
  };
  const state = {loaded: false, rows: [], ids: null, sortKey: "pub_date", sortDir: DEFAULT_DIRS.pub_date, page: 1};
  const openIds = new Set();

  const filters = () => ({
    q: el.q.value,
    minCites: el.min.value,
    oaOnly: el.oa.checked,
    recentOnly: el.recent.checked
  });

  const visibleRows = () => {
    const base = state.ids ? state.rows.filter((row) => state.ids.has(row.work_id)) : state.rows;
    return sortRows(filterRows(base, filters(), today), state.sortKey, state.sortDir);
  };

  function fillAbstract(details) {
    const target = details.querySelector(".ev-abstract-text");
    const id = details.dataset.id;
    target.textContent = "Loading abstract…";
    loadAbstracts().then((abstracts) => {
      if (!details.open || !details.isConnected) return;
      if (abstracts === null) {
        target.textContent = "Abstract unavailable right now.";
        return;
      }
      const text = Object.prototype.hasOwnProperty.call(abstracts, id) ? abstracts[id] : "";
      target.textContent = typeof text === "string" && text.trim() ? text.trim() : "No abstract available";
    });
  }

  function syncSortControls() {
    el.sort.value = state.sortKey;
    el.dir.textContent = state.sortDir === "asc" ? "Ascending" : "Descending";
    container.querySelectorAll("th[scope='col'] .ev-sort").forEach((button) => {
      const active = button.dataset.sort === state.sortKey;
      button.parentElement.setAttribute("aria-sort", active ? (state.sortDir === "asc" ? "ascending" : "descending") : "none");
    });
  }

  function render() {
    if (!state.loaded) return;
    const all = visibleRows();
    const info = pageInfo(all.length, state.page);
    state.page = info.page;
    const items = pageRows(all, info.page);
    const recentIds = new Set(recentRows(all, today).map((row) => row.work_id));
    el.rows.innerHTML = items.length
      ? items.map((row) => rowHtml(row, recentIds.has(row.work_id))).join("")
      : `<tr><td class="ev-empty" colspan="${COLUMN_COUNT}">No works match these filters.</td></tr>`;
    el.rows.querySelectorAll("details.ev-abstract").forEach((details) => {
      details.addEventListener("toggle", () => {
        if (details.open) {
          openIds.add(details.dataset.id);
          fillAbstract(details);
        } else {
          openIds.delete(details.dataset.id);
        }
      });
      if (openIds.has(details.dataset.id)) details.open = true;
    });
    el.range.textContent = info.total ? `Showing ${info.start}–${info.end} of ${info.total}` : "Showing 0 of 0";
    el.status.textContent = info.total
      ? `${info.total} ${info.total === 1 ? "work matches" : "works match"} the current filters.`
      : "";
    el.prev.disabled = info.page <= 1;
    el.next.disabled = info.page >= info.pages;
    syncSortControls();
  }

  function resetAndRender() {
    state.page = 1;
    render();
  }

  function setSort(key) {
    if (state.sortKey === key) {
      state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
    } else {
      state.sortKey = key;
      state.sortDir = DEFAULT_DIRS[key];
    }
    resetAndRender();
  }

  function downloadCsv() {
    const doc = container.ownerDocument;
    const blob = new Blob(["\ufeff", toCsv(visibleRows())], {type: "text/csv;charset=utf-8"});
    const url = URL.createObjectURL(blob);
    const link = doc.createElement("a");
    link.href = url;
    link.download = "ca-plastics-works.csv";
    doc.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  el.tools.addEventListener("input", resetAndRender);
  el.tools.addEventListener("change", resetAndRender);
  el.sort.addEventListener("change", () => {
    state.sortKey = el.sort.value;
    state.sortDir = DEFAULT_DIRS[state.sortKey];
    resetAndRender();
  });
  el.dir.addEventListener("click", () => {
    state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
    resetAndRender();
  });
  el.csv.addEventListener("click", downloadCsv);
  el.prev.addEventListener("click", () => {
    state.page -= 1;
    render();
  });
  el.next.addEventListener("click", () => {
    state.page += 1;
    render();
  });
  container.querySelectorAll("th .ev-sort").forEach((button) => {
    button.addEventListener("click", () => setSort(button.dataset.sort));
  });

  const ready = loadJson("works_detail.json")
    .then((payload) => {
      // The page lists plastic-related works only.
      state.rows = normaliseRows(payload).filter((row) => row.plastic_related === true);
      state.loaded = true;
      el.status.textContent = "";
      render();
    })
    .catch(() => {
      el.status.textContent = "The works list is unavailable right now.";
      el.rows.innerHTML = "";
    });

  return {
    ready,
    update(workIds) {
      state.ids = workIds === null || workIds === undefined ? null : new Set(Array.from(workIds, String));
      resetAndRender();
    }
  };
}

// "New in the last 2 weeks" callout. rows are normalised works (see normaliseRows). The container is
// hidden when no work is recent.
export function renderRecentCallout(container, rows, today = new Date()) {
  const recent = sortRows(recentRows(rows || [], today), "pub_date", "desc");
  if (!recent.length) {
    container.hidden = true;
    container.innerHTML = "";
    return;
  }
  const items = recent.map((row) => {
    const title = escapeHtml(row.title || "Untitled work");
    const link = row.doi ? `<a href="${escapeHtml(row.doi)}">${title}</a>` : `<strong>${title}</strong>`;
    const meta = [dateLabel(row), row.journal].filter(Boolean).map((text) => escapeHtml(text)).join(" · ");
    return `<li>${link} <span class="ev-recent-meta">${meta}</span></li>`;
  });
  const count = recent.length;
  container.classList.add("ev-recent");
  container.innerHTML = `<h2 class="ev-recent-title">New in the last 2 weeks</h2>`
    + `<p class="ev-recent-note">${count} ${count === 1 ? "work was" : "works were"} published in the last 14 days.</p>`
    + `<ul class="ev-recent-list">${items.join("")}</ul>`;
  container.hidden = false;
}

