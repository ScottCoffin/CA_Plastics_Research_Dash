// Region pages (REG-1, docs/REGION_PAGES.md): one shared component renders every region from
// data/<slug>/region.json (schema region-v1). The front end never branches on the region. The page
// markup is static in framework/src/<slug>/index.md (header and root div); this module fills the
// root. Pure helpers are exported for the Node runtime test (tests/test_region_page.py).
import {escapeHtml, formatCount, pageUrl, regionFileUrl, regionSlug, siteRoot} from "./atlas.js";

export const REGION_SCHEMA = "region-v1";
// Contract order of the six local sections (docs/REGION_PAGES.md).
export const SECTION_ORDER = ["funding", "monitoring", "policy", "research_networks", "local_terms", "geography"];
export const PLACEHOLDER_BADGE = "To be confirmed by a local researcher";
export const CONFIRMED_BADGE = "Confirmed by a local researcher";
export const STATUS_LINE = "In preparation with local collaborators";
// Region authors with at least this many region works have a profile page (region author files, GP-2).
const REGION_PROFILE_MIN_WORKS = 2;
const PARTIAL_NOTE = "Partial year: counts run to the date of the last fetch.";

const list = (value) => (Array.isArray(value) ? value : []);
const textOf = (value) => (Array.isArray(value) ? value.join(" ") : String(value ?? "")).trim();

// Text is rendered as written. Public wording is enforced on the data (scripts/check_public_text.py
// checks region.json), not rewritten here: a silent swap could alter real names.
export function publicText(value) {
  return String(value ?? "");
}

// Only http(s) links are rendered (region.yml is hand-written; no javascript: or relative targets).
export function safeUrl(url) {
  const value = typeof url === "string" ? url.trim() : "";
  return /^https?:\/\/[^\s"<>]+$/i.test(value) ? value : null;
}

// OpenAlex author ids ("A123...") link to the public author page; anything else gets no link.
export function openalexAuthorUrl(id) {
  const value = String(id ?? "").trim();
  if (/^https:\/\/openalex\.org\/A\d+$/.test(value)) return value;
  return /^A\d+$/.test(value) ? `https://openalex.org/${value}` : null;
}

// Badge for an item or section: only a confirmed status is shown as confirmed.
export function badgeText(status) {
  return status === "confirmed" ? CONFIRMED_BADGE : PLACEHOLDER_BADGE;
}

// works_by_year -> complete years (ascending) and the partial year, if any (same shape as countries.json).
export function yearSeries(entries) {
  const rows = [];
  let partial = null;
  for (const entry of list(entries)) {
    const year = Number(entry?.year);
    const count = Number(entry?.count);
    if (!Number.isInteger(year) || !Number.isFinite(count)) continue;
    if (entry.partial) partial = {year, count, partial: true};
    else rows.push({year, count});
  }
  rows.sort((a, b) => a.year - b.year);
  return {rows, partial};
}

// Validated view model for a region-v1 payload, or null when the schema does not match.
export function normalizeRegion(payload) {
  if (payload?.schema_version !== REGION_SCHEMA || typeof payload.name !== "string") return null;
  const stats = payload.stats && typeof payload.stats === "object" ? payload.stats : {};
  const sections = list(payload.sections)
    .filter((section) => SECTION_ORDER.includes(section?.id))
    .sort((a, b) => SECTION_ORDER.indexOf(a.id) - SECTION_ORDER.indexOf(b.id));
  const scope = payload.what_this_is_and_is_not && typeof payload.what_this_is_and_is_not === "object"
    ? payload.what_this_is_and_is_not : {};
  return {
    name: publicText(payload.name),
    is: publicText(textOf(scope.is)),
    isNot: publicText(textOf(scope.is_not)),
    worksTotal: Number(stats.works_total) || 0,
    firstYear: stats.first_year ?? null,
    lastCompleteYear: stats.last_complete_year ?? null,
    worksWithPmid: Number(stats.works_with_pmid) || 0,
    years: yearSeries(payload.works_by_year),
    topics: list(payload.top_topics),
    institutions: list(payload.top_institutions),
    researchers: list(payload.top_researchers),
    partners: list(payload.partner_countries),
    sections,
  };
}

// Bar widths are percentages of the largest count (0 to 100, rounded).
export function barPercent(count, max) {
  return max > 0 ? Math.round((Math.max(0, count) / max) * 100) : 0;
}

// ---- markup ----------------------------------------------------------------------------------

const VIEW_TOGGLE = (group, chart, table, chartLabel = "Chart", tableLabel = "Table") =>
  `<div class="rg-view" data-view-group="${group}">` +
  `<div class="rg-toggle" role="group" aria-label="Show as">` +
  `<button type="button" data-view="chart" aria-pressed="true">${chartLabel}</button>` +
  `<button type="button" data-view="table" aria-pressed="false">${tableLabel}</button></div>` +
  `<div data-panel="chart">${chart}</div><div data-panel="table" hidden>${table}</div></div>`;

function tableHtml(caption, head, rows) {
  const body = rows.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("");
  return `<div class="rg-table-wrap" role="region" aria-label="${escapeHtml(caption)}" tabindex="0">` +
    `<table><caption class="rg-sr">${escapeHtml(caption)}</caption>` +
    `<thead><tr>${head.map((h) => `<th scope="col">${escapeHtml(h)}</th>`).join("")}</tr></thead>` +
    `<tbody>${body}</tbody></table></div>`;
}

// Works per year as an SVG column chart; the partial year is hatched. viewBox keeps 320 px legible.
export function worksChartSvg(series, name) {
  const all = [...series.rows, ...(series.partial ? [series.partial] : [])];
  if (!all.length) return `<p class="rg-state">No yearly counts yet.</p>`;
  const W = 360, H = 220, L = 36, R = 6, T = 12, B = 26;
  const plotW = W - L - R, plotH = H - T - B;
  const max = Math.max(1, ...all.map((d) => d.count));
  const slot = plotW / all.length;
  const barW = Math.max(2, slot * 0.72);
  const step = Math.max(1, Math.ceil(all.length / 6));
  const bars = all.map((d, i) => {
    const h = (plotH * d.count) / max;
    const x = L + i * slot + (slot - barW) / 2;
    const title = `${d.year}: ${formatCount(d.count)}${d.partial ? " (partial year)" : ""}`;
    return `<rect class="rg-bar${d.partial ? " rg-bar-partial" : ""}" x="${x.toFixed(1)}" y="${(T + plotH - h).toFixed(1)}" ` +
      `width="${barW.toFixed(1)}" height="${h.toFixed(1)}"><title>${escapeHtml(title)}</title></rect>`;
  });
  const labels = all.map((d, i) => (i % step === 0 || i === all.length - 1
    ? `<text class="rg-axis" x="${(L + i * slot + slot / 2).toFixed(1)}" y="${H - 8}" text-anchor="middle">${d.year}</text>` : ""));
  const first = all[0].year, last = all[all.length - 1].year;
  return `<svg class="rg-chart" viewBox="0 0 ${W} ${H}" role="img" ` +
    `aria-label="${escapeHtml(`Works per year for ${name}, ${first} to ${last}. Table alternative follows.`)}">` +
    `<defs><pattern id="rg-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">` +
    `<rect class="rg-hatch-bg" width="6" height="6"/><line class="rg-hatch-line" x1="0" y1="0" x2="0" y2="6"/></pattern></defs>` +
    `<line class="rg-axis-line" x1="${L}" x2="${W - R}" y1="${T + plotH}" y2="${T + plotH}"/>` +
    `<text class="rg-axis" x="${L - 6}" y="${T + plotH}" text-anchor="end">0</text>` +
    `<text class="rg-axis" x="${L - 6}" y="${T + 8}" text-anchor="end">${formatCount(max)}</text>` +
    bars.join("") + labels.join("") + `</svg>`;
}

function barListHtml(rows, nameOf, countOf) {
  const max = Math.max(0, ...rows.map(countOf));
  return `<ol class="rg-bars">` + rows.map((row) => {
    const count = countOf(row);
    return `<li><span class="rg-bar-label">${escapeHtml(nameOf(row))}</span>` +
      `<span class="rg-bar-track" aria-hidden="true"><span class="rg-bar-fill" style="width:${barPercent(count, max)}%"></span></span>` +
      `<span class="rg-bar-value">${escapeHtml(formatCount(count))}</span></li>`;
  }).join("") + `</ol>`;
}

function sectionHtml(section, ambassadorsHref) {
  const id = String(section.id);
  const title = escapeHtml(publicText(section.title || id));
  const items = list(section.items);
  const itemsHtml = items.length
    ? `<ul class="rg-items">` + items.map((item) => {
      const url = safeUrl(item?.url);
      const name = escapeHtml(publicText(item?.name || "Untitled"));
      const label = url ? `<a href="${escapeHtml(url)}" rel="noreferrer">${name}</a>` : name;
      const note = item?.note ? `<p class="rg-note">${escapeHtml(publicText(item.note))}</p>` : "";
      const kind = item?.kind ? `<p class="rg-kind">${escapeHtml(publicText(item.kind))}</p>` : "";
      return `<li class="rg-item"><p class="rg-item-name">${label}</p>${kind}` +
        `<p><span class="rg-badge${item?.status === "confirmed" ? " rg-badge-ok" : ""}">${badgeText(item?.status)}</span></p>${note}</li>`;
    }).join("") + `</ul>`
    : `<p class="rg-state">No candidates listed yet.</p>`;
  const needs = section.needs ? `<p class="rg-needs"><b>To confirm:</b> ${escapeHtml(publicText(section.needs))}</p>` : "";
  return `<section class="rg-block rg-section" id="${escapeHtml(id)}" aria-labelledby="rg-sec-${escapeHtml(id)}">` +
    `<h2 id="rg-sec-${escapeHtml(id)}">${title}</h2>` +
    `<p><span class="rg-badge${section.status === "confirmed" ? " rg-badge-ok" : ""}">${badgeText(section.status)}</span></p>` +
    (section.summary ? `<p class="rg-lede">${escapeHtml(publicText(section.summary))}</p>` : "") +
    itemsHtml + needs +
    `<p><a class="rg-link" href="${ambassadorsHref}">Help confirm this section</a></p></section>`;
}

// The whole page body for one region (the static header and footer live in the Framework page).
// knownIds: the inst_ids in the region's institutions.json (GP-5). A listed institution links to its
// institution page when it is there; otherwise it keeps its ROR link. null means no institution pages.
export function renderRegion(model, ambassadorsHref, knownIds = null) {
  const years = model.years;
  const lastYear = years.partial ? years.partial.year : model.lastCompleteYear;
  const yearRows = [...years.rows, ...(years.partial ? [years.partial] : [])];
  const topics = model.topics.slice(0, 10);
  const institutions = model.institutions.slice(0, 15);
  const researchers = model.researchers.slice(0, 15);
  const partners = model.partners.slice(0, 10);
  const yearTable = tableHtml(`Works per year, ${model.name}`, ["Year", "Works", "Note"],
    yearRows.map((d) => [String(d.year), formatCount(d.count), d.partial ? "Partial year" : ""]));
  const topicTable = tableHtml(`Top topics, ${model.name}`, ["Topic", "Works"],
    topics.map((t) => [publicText(t.name || t.id || ""), formatCount(t.count)]));
  const emptyNote = model.worksTotal === 0
    ? `<p class="rg-state" role="status">No works for this region in the current search yet.</p>` : "";
  const instList = (institutions.length ? `<ol class="rg-list">` + institutions.map((i) => {
    const ror = safeUrl(i.ror);
    const name = escapeHtml(publicText(i.name || "Unnamed institution"));
    const id = String(i.id ?? "");
    const page = knownIds && knownIds.has(id) ? `./institution#inst=${encodeURIComponent(id)}` : "";
    const link = page ? `<a href="${escapeHtml(page)}">${name}</a>` : ror ? `<a href="${escapeHtml(ror)}" rel="noreferrer">${name}</a>` : name;
    return `<li><span class="rg-list-name">${link}</span>` +
      `<span class="rg-list-meta">${escapeHtml(publicText(i.type || ""))}</span>` +
      `<span class="rg-list-count">${escapeHtml(formatCount(i.works))} works</span></li>`;
  }).join("") + `</ol>` : `<p class="rg-state">No institutions listed yet.</p>`)
    + (knownIds ? `<p class="rg-state"><a href="./institutions">See all institutions</a></p>` : "");
  const researcherList = researchers.length ? `<ol class="rg-list">` + researchers.map((r) => {
    const url = openalexAuthorUrl(r.id);
    const name = escapeHtml(publicText(r.name || "Unnamed author"));
    // Region authors with an author file (two or more region works, GP-2) link to the region profile.
    const profile = regionSlug() !== "california" && Number(r.works) >= REGION_PROFILE_MIN_WORKS && r.id
      ? pageUrl(`expert.html#author=${encodeURIComponent(r.id)}`) : "";
    const link = profile ? `<a href="${escapeHtml(profile)}">${name}</a>` : url ? `<a href="${escapeHtml(url)}" rel="noreferrer">${name}</a>` : name;
    return `<li><span class="rg-list-name">${link}</span>` +
      `<span class="rg-list-count">${escapeHtml(formatCount(r.works))} works</span></li>`;
  }).join("") + `</ol>` : `<p class="rg-state">No researchers listed yet.</p>`;
  const partnerList = partners.length ? `<ol class="rg-list">` + partners.map((p) =>
    `<li><span class="rg-list-name">${escapeHtml(publicText(p.name || p.iso || ""))}</span>` +
    `<span class="rg-list-count">${escapeHtml(formatCount(p.works))} works</span></li>`).join("") + `</ol>`
    : `<p class="rg-state">No partner countries listed yet.</p>`;
  // Reference regions with a collaboration network (GP-3) link to it from the researchers list.
  const networkLink = regionSlug() === "california" ? "" : `<p class="rg-state"><a href="./network">Collaboration network</a> · <a href="./evidence">Works and evidence map</a></p>`;
  const scopeNote = [model.is, model.isNot].filter(Boolean).map((t) => `<p>${escapeHtml(t)}</p>`).join("");
  const partialNote = years.partial ? `<p class="rg-note">${escapeHtml(PARTIAL_NOTE)} (${years.partial.year} so far.)</p>` : "";

  return `<section class="rg-hero" aria-labelledby="rg-title">` +
    `<p class="rg-eyebrow">Regional atlas</p>` +
    `<h1 id="rg-title">${escapeHtml(model.name)}</h1>` +
    `<p class="rg-status"><span class="rg-pill">${STATUS_LINE}</span></p>` +
    (model.is ? `<p class="rg-lede">${escapeHtml(model.is)}</p>` : "") +
    `<p><a class="rg-cta" href="${ambassadorsHref}">Help build this page</a></p></section>` +
    emptyNote +
    `<section class="rg-stats" aria-label="Summary"><dl class="rg-stat-grid">` +
    `<div class="rg-stat"><dt>Works</dt><dd>${escapeHtml(formatCount(model.worksTotal))}</dd></div>` +
    `<div class="rg-stat"><dt>First year</dt><dd>${escapeHtml(model.firstYear ?? "Unavailable")}</dd></div>` +
    `<div class="rg-stat"><dt>With a PubMed ID</dt><dd>${escapeHtml(formatCount(model.worksWithPmid))}</dd></div>` +
    `</dl><p class="rg-note">Latest year in the series: ${escapeHtml(lastYear ?? "Unavailable")}.</p></section>` +
    `<section class="rg-block" aria-labelledby="rg-years-h"><h2 id="rg-years-h">Works per year</h2>` +
    VIEW_TOGGLE("years", worksChartSvg(years, model.name), yearTable) + partialNote + `</section>` +
    `<section class="rg-block" aria-labelledby="rg-topics-h"><h2 id="rg-topics-h">Top topics</h2>` +
    VIEW_TOGGLE("topics", topics.length ? barListHtml(topics, (t) => publicText(t.name || t.id || ""), (t) => Number(t.count) || 0) : `<p class="rg-state">No topics yet.</p>`, topicTable) +
    `</section>` +
    `<section class="rg-block" aria-labelledby="rg-inst-h"><h2 id="rg-inst-h">Top institutions</h2>${instList}</section>` +
    `<section class="rg-block" aria-labelledby="rg-res-h"><h2 id="rg-res-h">Top researchers</h2>` +
    `<p class="rg-note">Public names from OpenAlex, ranked by works with an author in this region. Each name links to the OpenAlex author page.</p>${researcherList}${networkLink}</section>` +
    `<section class="rg-block" aria-labelledby="rg-part-h"><h2 id="rg-part-h">Partner countries</h2>` +
    `<p class="rg-note">Countries most often on the same works.</p>${partnerList}</section>` +
    `<div class="rg-local" aria-label="Local sections">` +
    list(model.sections).map((s) => sectionHtml(s, ambassadorsHref)).join("") + `</div>` +
    `<section class="rg-block rg-scope" aria-labelledby="rg-scope-h"><h2 id="rg-scope-h">About these figures</h2>` +
    `<p><b>Figures are unscreened search hits from OpenAlex.</b></p>${scopeNote}</section>`;
}

const LOADING = `<p class="rg-state" role="status">Loading the region…</p>`;
const FAILED = `<p class="rg-state rg-state-error" role="alert">The region data could not be loaded. Reload the page to try again.</p>`;

// Delegated handler for the Chart/Table toggles (one group per chart).
export function onToggle(event) {
  const button = event.target.closest?.("[data-view]");
  const group = button?.closest("[data-view-group]");
  if (!group) return;
  for (const b of group.querySelectorAll(":scope > .rg-toggle [data-view]")) b.setAttribute("aria-pressed", String(b === button));
  for (const panel of group.querySelectorAll(":scope > [data-panel]")) panel.hidden = panel.dataset.panel !== button.dataset.view;
}

// The inst_ids of the region's institution pages, or null when the region has no institutions.json.
async function regionInstitutionIds(slug) {
  try {
    const response = await fetch(regionFileUrl(slug, "institutions.json"), {cache: "no-cache"});
    if (!response.ok) return null;
    const payload = await response.json();
    return new Set(list(payload?.institutions).map((row) => String(row.inst_id ?? "")));
  } catch {
    return null;
  }
}

export async function mountRegion(root, slug) {
  root.innerHTML = LOADING;
  root.onclick = onToggle;
  let model = null;
  try {
    const response = await fetch(regionFileUrl(slug, "region.json"), {cache: "no-cache"});
    if (!response.ok) throw new Error(`region.json returned HTTP ${response.status}`);
    model = normalizeRegion(await response.json());
    if (!model) throw new Error("region.json does not match region-v1");
  } catch (error) {
    console.error("region:", error);
    root.innerHTML = FAILED;
    return;
  }
  const ambassadorsHref = new URL("ambassadors", siteRoot()).href;
  root.innerHTML = renderRegion(model, ambassadorsHref, await regionInstitutionIds(slug));
}
