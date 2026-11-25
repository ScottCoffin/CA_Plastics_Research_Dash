// BQ-4.4: renders topics_timeseries.json (bq4-v1) and topic_bursts.json (bq4-v1) on /california/topics.
// Every label and figure comes from the payloads. Text is set with textContent, never innerHTML.
// Accuracy states and rising flags are text, never colour alone. Charts (Observable Plot, passed in
// by the page) sit beside a table with the same numbers.

import "./shared/topics.js";

// Display names: the shared topic labels (Occurrence & monitoring, ...) when the payload carries only the id.
export function displayLabel(id, fallback) {
  const shared = globalThis.AtlasTopics?.label?.(id);
  if (shared && shared !== id) return shared;
  return fallback || id;
}

export function withDisplayLabels(series) {
  const tags = (series.tags || []).map((tag) => ({...tag, label: displayLabel(tag.tag, tag.label)}));
  const co = series.cooccurrence;
  const cooccurrence = co && Array.isArray(co.pairs)
    ? {...co, pairs: co.pairs.map((p) => ({...p, label_a: displayLabel(p.a, p.label_a), label_b: displayLabel(p.b, p.label_b)}))}
    : co;
  return {...series, tags, cooccurrence};
}

export const ACCURACY_TEXT = {
  validated: "validated",
  experimental: "experimental",
  "insufficient data": "insufficient data",
};

function el(tag, attrs = {}, text = "") {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text) node.textContent = text;
  return node;
}

function share(value) {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "not available";
}

function number(value, digits = 2) {
  return typeof value === "number" ? value.toFixed(digits) : "not available";
}

export function accuracyText(state) {
  return `Accuracy: ${ACCURACY_TEXT[state] || "insufficient data"}`;
}

export function risingText(flag) {
  return flag ? "Flagged as rising (statistical screen)" : "Not flagged as rising";
}

export function pairStatusText(status) {
  return status === "sufficient" ? "sufficient" : "insufficient data";
}

// Charts start at the first complete year with at least this many plastic-related works; earlier
// years have so few works that one paper swings the share to 100%. The table keeps every year.
export const MIN_CHART_WORKS = 20;

export function chartStartYear(series) {
  const first = (series.plastic_related_by_year || []).find((row) => !row.partial && row.count >= MIN_CHART_WORKS);
  return first ? first.year : null;
}

// Complete years only, for charts. Partial years stay in the table, marked as partial.
export function completeRows(tag, startYear = null) {
  return (tag.by_year || []).filter(
    (row) => !row.partial && typeof row.share === "number" && (startYear == null || row.year >= startYear),
  );
}

function flaggedTags(bursts) {
  const flags = new Map((bursts?.tags || []).map((t) => [t.tag, t]));
  return flags;
}

function renderStatus(root, series) {
  const status = el("p", {class: "tp-status", id: "topics-status"});
  status.textContent = `${series.notice} Complete years run to ${series.last_complete_year}.`;
  root.append(status);
}

function renderSmallMultiples(root, series, bursts, Plot) {
  const section = el("section", {class: "tp-block", "aria-labelledby": "topics-share"});
  section.append(el("h2", {id: "topics-share"}, "Share of plastic-related works by year"));
  section.append(el("p", {}, "Each panel is one topic. The share is the works with that topic divided by all plastic-related California works in the same year. Partial years are left out of the charts and shown in the table."));
  const start = chartStartYear(series);
  if (start != null) {
    section.append(el("p", {class: "tp-muted"}, `Charts start in ${start}, the first complete year with at least ${MIN_CHART_WORKS} plastic-related California works; earlier years are in the table.`));
  }
  const grid = el("div", {class: "tp-grid"});
  const flags = flaggedTags(bursts);
  for (const tag of series.tags) {
    const rows = completeRows(tag, start);
    const panel = el("article", {class: "tp-panel", "data-tag": tag.tag});
    panel.append(el("h3", {}, tag.label));
    const badges = el("p", {class: "tp-badges"});
    badges.append(el("span", {class: "tp-badge"}, accuracyText(tag.accuracy_state)));
    const flag = flags.get(tag.tag);
    if (flag) badges.append(el("span", {class: "tp-badge"}, risingText(flag.flag)));
    panel.append(badges);
    if (rows.length && !Plot) {
      panel.append(el("p", {class: "tp-muted"}, "Chart unavailable; the table below has the same figures."));
    } else if (rows.length) {
      const chart = Plot.plot({
        width: 320,
        height: 130,
        marginLeft: 44,
        x: {label: null, tickFormat: "d"},
        y: {label: null, grid: true, percent: true, zero: true},
        marks: [Plot.lineY(rows, {x: "year", y: "share", stroke: "currentColor"}), Plot.dot(rows, {x: "year", y: "share", fill: "currentColor", r: 2})],
      });
      chart.setAttribute("role", "img");
      chart.setAttribute("aria-label", `${tag.label}: share of plastic-related works by year, ${rows[0].year} to ${rows[rows.length - 1].year}`);
      panel.append(chart);
    } else {
      panel.append(el("p", {class: "tp-muted"}, "No complete-year works for this topic yet."));
    }
    grid.append(panel);
  }
  section.append(grid);
  root.append(section);
}

function renderShareTable(root, series) {
  const section = el("section", {class: "tp-block", "aria-labelledby": "topics-table"});
  section.append(el("h2", {id: "topics-table"}, "Table: share by year"));
  section.append(el("p", {}, "The same figures as the charts, as a table. Share is blank where the year has no plastic-related works."));
  const years = (series.plastic_related_by_year || []).map((row) => row.year);
  const yearSet = new Set();
  for (const tag of series.tags) for (const row of tag.by_year || []) yearSet.add(row.year);
  const allYears = [...yearSet].sort((a, b) => a - b);
  const partial = new Set(series.tags.flatMap((tag) => (tag.by_year || []).filter((row) => row.partial).map((row) => row.year)));
  const wrap = el("div", {class: "tp-scroll"});
  const table = el("table", {class: "tp-table"});
  table.append(el("caption", {}, "Share of plastic-related California works by topic and year"));
  const head = el("tr");
  head.append(el("th", {scope: "col"}, "Topic"));
  for (const year of allYears) head.append(el("th", {scope: "col"}, partial.has(year) ? `${year} (partial)` : String(year)));
  const thead = el("thead");
  thead.append(head);
  table.append(thead);
  const body = el("tbody");
  for (const tag of series.tags) {
    const row = el("tr");
    row.append(el("th", {scope: "row"}, tag.label));
    const byYear = new Map((tag.by_year || []).map((r) => [r.year, r]));
    for (const year of allYears) row.append(el("td", {}, share(byYear.get(year)?.share)));
    body.append(row);
  }
  table.append(body);
  wrap.append(table);
  section.append(wrap);
  if (years.length === 0) section.append(el("p", {class: "tp-muted"}, "No yearly totals are available."));
  root.append(section);
}

function renderTopicList(root, series, bursts) {
  const section = el("section", {class: "tp-block", "aria-labelledby": "topics-list"});
  section.append(el("h2", {id: "topics-list"}, "Topics: accuracy and rising screen"));
  const flags = flaggedTags(bursts);
  const wrap = el("div", {class: "tp-scroll"});
  const table = el("table", {class: "tp-table"});
  table.append(el("caption", {}, "Each topic with its accuracy state and rising screen result"));
  const head = el("tr");
  for (const name of ["Topic", "Accuracy state", "Works in complete years", "Rising screen", "Works, all label sources", "Works, rule labels only"]) {
    head.append(el("th", {scope: "col"}, name));
  }
  const thead = el("thead");
  thead.append(head);
  table.append(thead);
  const body = el("tbody");
  for (const tag of series.tags) {
    const flag = flags.get(tag.tag);
    const row = el("tr");
    row.append(el("th", {scope: "row"}, tag.label));
    row.append(el("td", {}, ACCURACY_TEXT[tag.accuracy_state] || "insufficient data"));
    row.append(el("td", {}, String(tag.complete_works)));
    row.append(el("td", {}, flag ? risingText(flag.flag) : "not computed"));
    row.append(el("td", {}, String(tag.label_source_totals?.all_sources ?? "not available")));
    row.append(el("td", {}, String(tag.label_source_totals?.rule_only ?? "not available")));
    body.append(row);
  }
  table.append(body);
  wrap.append(table);
  section.append(wrap);
  if (bursts?.statistical_screen) section.append(el("p", {class: "tp-note"}, bursts.statistical_screen));
  root.append(section);
}

// Co-occurrence table: click a header to sort. Insufficient pairs stay in the table, greyed and labelled.
export function sortPairs(pairs, key, direction) {
  const sign = direction === "asc" ? 1 : -1;
  return [...pairs].sort((x, y) => {
    const a = x[key] ?? -Infinity;
    const b = y[key] ?? -Infinity;
    if (a === b) return `${x.label_a}${x.label_b}`.localeCompare(`${y.label_a}${y.label_b}`);
    return a < b ? -sign : sign;
  });
}

function renderPairs(root, series) {
  const section = el("section", {class: "tp-block", "aria-labelledby": "topics-pairs"});
  section.append(el("h2", {id: "topics-pairs"}, "Topics that appear together"));
  const co = series.cooccurrence;
  section.append(el("p", {}, `Counts of works carrying both topics, in complete years (${co.window_years.from ?? "earliest"} to ${co.window_years.to}). Pairs with fewer than ${co.min_pair_n} shared works are shown greyed, labelled "insufficient data".`));
  const columns = [
    ["label", "Pair"],
    ["n_ab", "Works with both"],
    ["jaccard", "Jaccard"],
    ["lift", "Lift"],
    ["phi", "Phi"],
    ["status", "Status"],
  ];
  const wrap = el("div", {class: "tp-scroll"});
  const table = el("table", {class: "tp-table tp-sortable"});
  table.append(el("caption", {}, "Topic pairs in complete years, all label sources"));
  const head = el("tr");
  const state = {key: "n_ab", direction: "desc"};
  const headers = {};
  for (const [key, name] of columns) {
    const th = el("th", {scope: "col", "data-key": key});
    const button = el("button", {type: "button", class: "tp-sort"}, name);
    th.append(button);
    headers[key] = th;
    head.append(th);
    button.addEventListener("click", () => {
      state.direction = state.key === key && state.direction === "desc" ? "asc" : "desc";
      state.key = key;
      paint();
    });
  }
  const thead = el("thead");
  thead.append(head);
  table.append(thead);
  const body = el("tbody");
  table.append(body);
  wrap.append(table);
  section.append(wrap);

  const pairs = co.pairs.map((p) => ({...p, label: `${p.label_a} and ${p.label_b}`}));
  function paint() {
    for (const [key, th] of Object.entries(headers)) {
      th.setAttribute("aria-sort", key === state.key ? (state.direction === "asc" ? "ascending" : "descending") : "none");
    }
    body.replaceChildren();
    for (const pair of sortPairs(pairs, state.key, state.direction)) {
      const insufficient = pair.status !== "sufficient";
      const row = el("tr", {class: insufficient ? "tp-muted" : ""});
      row.append(el("th", {scope: "row"}, pair.label));
      row.append(el("td", {}, String(pair.n_ab)));
      row.append(el("td", {}, number(pair.jaccard)));
      row.append(el("td", {}, number(pair.lift)));
      row.append(el("td", {}, number(pair.phi)));
      row.append(el("td", {}, pairStatusText(pair.status)));
      body.append(row);
    }
  }
  paint();
  root.append(section);
}

function renderLens(root, series) {
  const section = el("section", {class: "tp-block", "aria-labelledby": "topics-lens"});
  section.append(el("h2", {id: "topics-lens"}, "Analytic lenses"));
  const lens = series.lens || {};
  section.append(el("p", {class: "tp-note"}, lens.caption || ""));
  section.append(el("p", {}, `Lens status: ${lens.message || lens.status || "not available"}.`));
  const rows = lens.series || [];
  if (rows.length) {
    const table = el("table", {class: "tp-table"});
    table.append(el("caption", {}, "Lens works by year"));
    const head = el("tr");
    for (const name of ["Year", "Works"]) head.append(el("th", {scope: "col"}, name));
    const thead = el("thead");
  thead.append(head);
  table.append(thead);
    const body = el("tbody");
    for (const row of rows) {
      const tr = el("tr");
      tr.append(el("th", {scope: "row"}, String(row.year)));
      tr.append(el("td", {}, String(row.count)));
      body.append(tr);
    }
    table.append(body);
    const lensWrap = el("div", {class: "tp-scroll"});
    lensWrap.append(table);
    section.append(lensWrap);
  }
  root.append(section);
}

export function renderTopics(root, rawSeries, bursts, {Plot = null} = {}) {
  const series = withDisplayLabels(rawSeries);
  root.replaceChildren();
  root.setAttribute("data-topics-schema", series.schema || "");
  renderStatus(root, series);
  renderSmallMultiples(root, series, bursts, Plot);
  renderShareTable(root, series);
  renderTopicList(root, series, bursts);
  renderPairs(root, series);
  renderLens(root, series);
  return root;
}

export async function mountTopics(root, {series, bursts, Plot}) {
  try {
    const [seriesPayload, burstPayload] = await Promise.all([
      series(),
      bursts().catch(() => null),
    ]);
    renderTopics(root, seriesPayload, burstPayload, {Plot});
  } catch (error) {
    root.replaceChildren(el("p", {class: "tp-status"}, "The topic data could not be loaded."));
    console.error("topics:", error);
  }
}
