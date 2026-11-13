// Pure helpers for the Funding visualizations (ported from the classic grants page, site/grants.html).
// No DOM access. Input rows are the awards that match the Funding filter form (state.grantsFiltered in
// funding.js). viewRows() returns new objects, so the input rows are never changed.
// The optional topic helper T is the shared AtlasTopics object (components/shared/topics.js).

export const UNTAGGED = "__untagged__";
export const HEAT_START = 2012;
export const DEFAULT_SECTOR_LABELS = {
  academia: "Academia", nonprofit: "Nonprofit & research institute", jpa: "Joint powers / regional agency",
  government: "Government", industry: "Industry", individual: "Individual (fellowship)", unknown: "Unknown"
};
export const SECTOR_ORDER = ["academia", "nonprofit", "jpa", "government", "industry", "individual", "unknown"];
export const SECTOR_SHORT = {nonprofit: "Nonprofit & institute", jpa: "Joint powers / regional", individual: "Individual fellowship"};
export const SECTOR_COLORS = {
  academia: "#2f5d8a", nonprofit: "#5f8fb8", jpa: "#86a3bd", government: "#55616b", industry: "#8b959d", individual: "#a9b4bd", unknown: "#c3cbd1"
};
export const FUNDER_COLOR = "#3d4f5c";
export const AGENCY_COLORS = {
  NSF: "#2c5f9e", NIH: "#b84f7e", NOAA: "#1f9393", EPA: "#8d9b22", "CA Ocean Protection Council": "#c97b17",
  NIST: "#7a5aa6", USDA: "#5e8c3a", "CA State Water Board": "#a64b3c", "California Sea Grant": "#3a8fbf", "US Department of State": "#7d8790"
};
export const AGENCY_OTHER = "#a9b3ba";
export const UNTAGGED_COLOR = "#8a9499";
export const FALLBACK_COLOR = "#8b959d";

const isMatrixTag = (tag) => String(tag).startsWith("matrix:");

export function sectorLabelsFor(extra) {
  return Object.assign({}, DEFAULT_SECTOR_LABELS, extra || {});
}

export function agencyColor(agency) {
  return AGENCY_COLORS[agency] || AGENCY_OTHER;
}

export function topicKeys(T) {
  return T ? Object.keys(T.TOPICS) : [];
}

export function topicLabel(key, T) {
  if (key === UNTAGGED) return "Untagged";
  return T ? T.label(key) : String(key);
}

// An award has a usable amount only when it is a positive finite number (as in the classic page).
export function hasAmount(row) {
  return typeof row.amount === "number" && isFinite(row.amount) && row.amount > 0;
}

// Topics of one award without matrix tags, sorted; untagged awards get the single UNTAGGED topic.
export function topicsOf(row, T) {
  const tags = (row.domain_tags || []).filter((tag) => !isMatrixTag(tag));
  const sorted = T ? T.sortTags(tags) : [...new Set(tags)].sort();
  return sorted.length ? sorted : [UNTAGGED];
}

export function orgKeyOf(name) {
  const key = String(name || "").toLowerCase().replace(/[.,'’"]/g, "").replace(/\s+/g, " ").trim();
  return key || "(unknown)";
}

function titleCaseOrg(text) {
  const small = new Set(["of", "and", "the", "at", "for", "in", "on"]);
  return text.toLowerCase().split(" ").map((w, i) => (i > 0 && small.has(w) ? w : w.charAt(0).toUpperCase() + w.slice(1))).join(" ");
}

// Display name for one organisation: the most common spelling that is not all capitals, else a title-cased form.
function pickOrgName(counts) {
  const all = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  const mixed = all.find(([name]) => name !== name.toUpperCase());
  if (mixed) return mixed[0];
  return all.length ? titleCaseOrg(all[0][0]) : "Unknown organisation";
}

// Derived view rows: funder agency, sector, fiscal year, organisation key and name, topics, reported amount.
export function viewRows(rows, T) {
  const variants = new Map();
  const out = rows.map((row) => {
    const raw = String(row.org || "").replace(/\s+/g, " ").trim();
    const orgKey = orgKeyOf(raw);
    if (!variants.has(orgKey)) variants.set(orgKey, new Map());
    if (raw) variants.get(orgKey).set(raw, (variants.get(orgKey).get(raw) || 0) + 1);
    return {
      grant_key: row.grant_key,
      title: row.title || "",
      org: raw,
      orgKey,
      orgName: "",
      org_state: row.org_state || "",
      agency: row.funder_agency || row.funder || "Unknown funder",
      sector: row.sector || "unknown",
      program: row.program || "",
      fy: row.fiscal_year == null ? null : Number(row.fiscal_year),
      start: row.start || "",
      end: row.end || "",
      amount: hasAmount(row) ? row.amount : null,
      amountBasis: row.amount_basis || "",
      currency: row.currency || "USD",
      url: row.url || "",
      caLed: row.ca_led === true,
      topics: topicsOf(row, T)
    };
  });
  const names = new Map([...variants].map(([key, counts]) => [key, pickOrgName(counts)]));
  out.forEach((row) => {
    row.orgName = names.get(row.orgKey);
  });
  return out;
}

// Sectors and topics present in the rows, in canonical order; unknown values follow in sorted order.
export function sectorsInRows(vrows) {
  const seen = new Set(vrows.map((r) => r.sector));
  const extra = [...seen].filter((s) => !SECTOR_ORDER.includes(s)).sort();
  return [...SECTOR_ORDER, ...extra].filter((s) => seen.has(s));
}

export function topicsInRows(vrows, T) {
  const known = topicKeys(T);
  const seen = new Set(vrows.flatMap((r) => r.topics));
  const extra = [...seen].filter((t) => t !== UNTAGGED && !known.includes(t)).sort();
  return [...known, ...extra, UNTAGGED].filter((t) => seen.has(t));
}

// Tile metrics for the summary row.
export function tileMetrics(vrows) {
  const agencies = new Set(), orgs = new Set(), sectors = new Set();
  let ca = 0, amount = 0, withAmt = 0;
  vrows.forEach((r) => {
    agencies.add(r.agency);
    orgs.add(r.orgKey);
    sectors.add(r.sector);
    if (r.caLed) ca += 1;
    if (r.amount !== null) {
      amount += r.amount;
      withAmt += 1;
    }
  });
  return {
    awards: vrows.length,
    funders: agencies.size,
    orgs: orgs.size,
    sectors: sectors.size,
    caShare: vrows.length ? ca / vrows.length : 0,
    amount,
    withAmt,
    noAmt: vrows.length - withAmt
  };
}

// ---- Sankey -----------------------------------------------------------------------------------

// Columns: 0 funder agency, 1 sector, 2 organisation (only when opts.orgs), last column topic.
// opts.mode "awards" (default) or "amount"; opts.topN organisations kept per sector (the rest become
// "Other <sector>"); opts.sectorLabels; opts.T for topic labels. Each award adds its weight to every node
// it passes through; an award with k topics splits its weight k ways, so flows into and out of a middle
// node always balance.
export function buildSankey(vrows, opts = {}) {
  const mode = opts.mode === "amount" ? "amount" : "awards";
  const topN = Math.max(1, opts.topN || 6);
  const withOrgs = opts.orgs !== false;
  const labels = opts.sectorLabels || DEFAULT_SECTOR_LABELS;
  const T = opts.T || null;
  const used = [];
  let excluded = 0;
  vrows.forEach((r) => {
    if (mode === "amount" && r.amount === null) excluded += 1;
    else used.push(r);
  });
  const weight = (r) => (mode === "amount" ? r.amount : 1);
  const bySector = new Map();
  used.forEach((r) => {
    if (!bySector.has(r.sector)) bySector.set(r.sector, new Map());
    const m = bySector.get(r.sector);
    m.set(r.orgKey, (m.get(r.orgKey) || 0) + weight(r));
  });
  const keep = new Map();
  bySector.forEach((m, sector) => {
    const ranked = [...m.entries()].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(b[0]));
    keep.set(sector, new Set(ranked.slice(0, topN).map((e) => e[0])));
  });
  const nodes = new Map();
  const links = new Map();
  const lastCol = withOrgs ? 3 : 2;
  const node = (id, col, type, key, name, extra) => {
    if (!nodes.has(id)) {
      nodes.set(id, Object.assign({id, col, type, key, name, value: 0, awardsW: 0, amountW: 0, keys: new Set()}, extra || {}));
    }
    return nodes.get(id);
  };
  const touch = (n, key, share, awardShare, amountShare) => {
    n.value += share;
    n.awardsW += awardShare;
    n.amountW += amountShare;
    n.keys.add(key);
  };
  const link = (a, b, share, awardShare, amountShare) => {
    const id = `${a.id}>${b.id}`;
    if (!links.has(id)) links.set(id, {id, source: a.id, target: b.id, value: 0, awardsW: 0, amountW: 0});
    const l = links.get(id);
    l.value += share;
    l.awardsW += awardShare;
    l.amountW += amountShare;
  };
  used.forEach((r) => {
    const w = weight(r);
    const amt = r.amount ?? 0;
    const agency = node(`a:${r.agency}`, 0, "agency", r.agency, r.agency);
    const sector = node(`s:${r.sector}`, 1, "sector", r.sector, labels[r.sector] || r.sector);
    touch(agency, r.grant_key, w, 1, amt);
    touch(sector, r.grant_key, w, 1, amt);
    link(agency, sector, w, 1, amt);
    let from = sector;
    if (withOrgs) {
      const isTop = keep.get(r.sector).has(r.orgKey);
      const org = isTop
        ? node(`o:${r.sector}:${r.orgKey}`, 2, "org", r.orgKey, r.orgName, {sector: r.sector})
        : node(`o:other:${r.sector}`, 2, "other", r.sector, `Other ${(SECTOR_SHORT[r.sector] || labels[r.sector] || r.sector).toLowerCase()}`, {sector: r.sector});
      touch(org, r.grant_key, w, 1, amt);
      link(sector, org, w, 1, amt);
      from = org;
    }
    const k = r.topics.length;
    r.topics.forEach((t) => {
      const topic = node(`t:${t}`, lastCol, "topic", t, topicLabel(t, T));
      touch(topic, r.grant_key, w / k, 1 / k, amt / k);
      link(from, topic, w / k, 1 / k, amt / k);
    });
  });
  let total = 0;
  nodes.forEach((n) => {
    if (n.col === 0) total += n.value;
  });
  const nodeList = [...nodes.values()].map(({keys, ...rest}) => ({...rest, count: keys.size}));
  return {
    nodes: nodeList,
    links: [...links.values()],
    total,
    excluded,
    mode,
    withOrgs,
    ncols: lastCol + 1,
    awardCount: used.length
  };
}

const sectorIndex = (s) => {
  const i = SECTOR_ORDER.indexOf(s);
  return i < 0 ? 99 : i;
};

// Column order: untagged topics last; organisations grouped by sector, "Other" last in its sector.
function nodeOrder(a, b) {
  if (a.type === "topic" || b.type === "topic") {
    const au = a.key === UNTAGGED ? 1 : 0, bu = b.key === UNTAGGED ? 1 : 0;
    return au - bu || b.value - a.value || a.name.localeCompare(b.name);
  }
  if (a.type === "org" || a.type === "other") {
    const ao = a.type === "other" ? 1 : 0, bo = b.type === "other" ? 1 : 0;
    return sectorIndex(a.sector) - sectorIndex(b.sector) || ao - bo || b.value - a.value || a.name.localeCompare(b.name);
  }
  return b.value - a.value || a.name.localeCompare(b.name);
}

// Positions every node and link on one shared scale. Returns copies; the graph is not changed.
// o: {width, height, marginLeft, marginRight, marginTop, gap, nodeWidth, minNodeHeight}.
export function layoutSankey(graph, o) {
  const W = o.width, gap = o.gap == null ? 2 : o.gap, nw = o.nodeWidth || 12;
  const ml = o.marginLeft == null ? 130 : o.marginLeft, mr = o.marginRight == null ? 170 : o.marginRight, mt = o.marginTop == null ? 26 : o.marginTop;
  const minH = o.minNodeHeight == null ? 5 : o.minNodeHeight;
  const nodes = graph.nodes.map((n) => ({...n}));
  const cols = [];
  for (let c = 0; c < graph.ncols; c++) cols.push(nodes.filter((n) => n.col === c));
  cols.forEach((list) => list.sort(nodeOrder));
  const inner = Math.max(40, o.height - mt - 8);
  let scale = Infinity;
  cols.forEach((list) => {
    const sum = list.reduce((s, n) => s + n.value, 0);
    if (sum > 0) scale = Math.min(scale, (inner - gap * Math.max(0, list.length - 1)) / sum);
  });
  if (!Number.isFinite(scale)) scale = 0;
  // Grow the canvas when minimum node heights make a column taller than the requested height.
  let usedMax = 0;
  cols.forEach((list) => {
    const h = list.reduce((s, n) => s + Math.max(n.value * scale, minH), 0) + gap * Math.max(0, list.length - 1);
    usedMax = Math.max(usedMax, h);
  });
  const H = Math.max(o.height, usedMax + mt + 8);
  const span = graph.ncols > 1 ? (W - ml - mr - nw) / (graph.ncols - 1) : 0;
  const byId = new Map();
  cols.forEach((list, c) => {
    let y = mt;
    list.forEach((n) => {
      n.x = ml + c * span;
      n.w = nw;
      n.h = Math.max(n.value * scale, minH);
      n.y = y;
      y += n.h + gap;
      byId.set(n.id, n);
    });
  });
  const links = graph.links.map((l) => ({...l, s: byId.get(l.source), t: byId.get(l.target), width: l.value * scale}));
  // Link ends stack along each node in the order of the node at the other end.
  nodes.forEach((n) => {
    const out = links.filter((l) => l.s === n).sort((a, b) => a.t.y - b.t.y || a.id.localeCompare(b.id));
    const inn = links.filter((l) => l.t === n).sort((a, b) => a.s.y - b.s.y || a.id.localeCompare(b.id));
    let oy = n.y;
    out.forEach((l) => {
      l.y0 = oy + l.width / 2;
      oy += l.width;
    });
    let iy = n.y;
    inn.forEach((l) => {
      l.y1 = iy + l.width / 2;
      iy += l.width;
    });
  });
  links.forEach((l) => {
    const x0 = l.s.x + l.s.w, x1 = l.t.x, xm = (x0 + x1) / 2;
    l.d = `M${x0.toFixed(1)},${l.y0.toFixed(2)}C${xm.toFixed(1)},${l.y0.toFixed(2)} ${xm.toFixed(1)},${l.y1.toFixed(2)} ${x1.toFixed(1)},${l.y1.toFixed(2)}`;
  });
  return {nodes, links, width: W, height: H, scale, marginLeft: ml};
}

// ---- Year, heat, matrix and organisation views ------------------------------------------------

// Funder agencies in legend order: known agencies first (fixed order), then the rest alphabetically.
export function agencyOrder(vrows) {
  const counts = new Map();
  vrows.forEach((r) => counts.set(r.agency, (counts.get(r.agency) || 0) + 1));
  const known = Object.keys(AGENCY_COLORS);
  const extra = [...counts.keys()].filter((a) => !known.includes(a)).sort();
  return known.filter((a) => counts.has(a)).concat(extra);
}

// Awards per fiscal year, split by funder agency. Every year between the first and last is present
// (zero years included). Undated awards are counted separately.
export function yearCounts(vrows, order) {
  const years = new Map();
  let undated = 0;
  vrows.forEach((r) => {
    if (r.fy === null) {
      undated += 1;
      return;
    }
    if (!years.has(r.fy)) years.set(r.fy, new Map());
    const m = years.get(r.fy);
    m.set(r.agency, (m.get(r.agency) || 0) + 1);
  });
  if (!years.size) return {years: [], undated, max: 0};
  const lo = Math.min(...years.keys()), hi = Math.max(...years.keys());
  const out = [];
  let max = 0;
  for (let y = lo; y <= hi; y++) {
    const m = years.get(y) || new Map();
    const segs = order.filter((a) => m.get(a)).map((a) => ({agency: a, n: m.get(a)}));
    const total = segs.reduce((s, x) => s + x.n, 0);
    max = Math.max(max, total);
    out.push({year: y, total, segs});
  }
  return {years: out, undated, max};
}

// Topic by fiscal year. Years before HEAT_START share one "pre" column. An award counts once per topic.
export function buildHeat(vrows, T) {
  const dated = vrows.filter((r) => r.fy !== null);
  if (!dated.length) return {cols: [], rows: [], max: 0};
  const hi = Math.max(...dated.map((r) => r.fy));
  const lo = Math.max(HEAT_START, Math.min(...dated.map((r) => r.fy)));
  const cols = [];
  if (dated.some((r) => r.fy < HEAT_START)) cols.push("pre");
  for (let y = lo; y <= hi; y++) cols.push(y);
  const colOf = (r) => cols.indexOf(r.fy < HEAT_START ? "pre" : r.fy);
  const rows = topicsInRows(dated, T).map((t) => {
    const counts = cols.map(() => 0);
    dated.forEach((r) => {
      if (r.topics.includes(t)) counts[colOf(r)] += 1;
    });
    return {key: t, label: topicLabel(t, T), counts, total: counts.reduce((a, b) => a + b, 0)};
  });
  return {cols, rows, max: Math.max(0, ...rows.flatMap((r) => r.counts))};
}

// Recipient sector by topic. An award counts once per topic it carries.
export function buildSectorTopic(vrows, T) {
  const sectors = sectorsInRows(vrows);
  const topics = topicsInRows(vrows, T);
  const grid = sectors.map((s) => topics.map((t) => vrows.filter((r) => r.sector === s && r.topics.includes(t)).length));
  return {sectors, topics, grid, max: Math.max(0, ...grid.flat())};
}

// Organisations ranked by number of awards (ties by name).
export function topOrgs(vrows, n) {
  const m = new Map();
  vrows.forEach((r) => {
    if (!m.has(r.orgKey)) m.set(r.orgKey, {key: r.orgKey, name: r.orgName, sector: r.sector, n: 0});
    m.get(r.orgKey).n += 1;
  });
  return [...m.values()].sort((a, b) => b.n - a.n || a.name.localeCompare(b.name)).slice(0, n);
}

// Cell colour on a white-to-blue ramp (count 0 is a neutral grey).
export function heatFill(count, max) {
  if (!count) return "#f3f5f6";
  const t = max > 0 ? Math.min(1, count / max) : 0;
  const a = [0xe6, 0xee, 0xf6], b = [0x0b, 0x4f, 0x9c];
  const c = a.map((v, i) => Math.round(v + (b[i] - v) * t));
  return `#${c.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

// Higher-contrast of white and black text on a hex fill (at least 4.58:1 on any fill).
export function inkFor(hex) {
  const n = parseInt(hex.slice(1), 16);
  const lin = (v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  const L = 0.2126 * lin((n >> 16) & 255) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255);
  return 1.05 / (L + 0.05) >= (L + 0.05) / 0.05 ? "#ffffff" : "#000000";
}

// Rounds an axis maximum up to 1, 2, 5 or 10 times a power of ten.
export function niceMax(max) {
  if (max <= 5) return Math.max(1, max);
  const pow = Math.pow(10, Math.floor(Math.log10(max)));
  const f = max / pow;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pow;
}

// Colour for a topic (hatched topics use their CSS fill). Untagged awards use a neutral grey.
export function topicFill(key, T, css = false) {
  if (key === UNTAGGED || !T) return UNTAGGED_COLOR;
  return css ? T.cssFill(key) : T.svgFill(key);
}
