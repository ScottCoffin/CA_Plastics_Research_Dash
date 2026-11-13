// Pure helpers for the Experts page (AT-5d). Ported from the classic site's Experts script
// (site/index.html: filteredAuthors, authorSummary, expertComparator, expertMetricsHtml,
// profileHtml, drawerStatsHtml, renderVirtualRows, openDrawer, the CSV export and the hash
// read/write). No DOM access at module load; the Node runtime test imports this file.
// Topic helpers come from the global AtlasTopics (components/shared/topics.js).
import {classicUrl, escapeHtml} from "./atlas.js";

export const SORT_KEYS = ["ca_works", "cited_by", "h_index", "plastic_citations", "plastic_works", "m_quotient", "rising"];
export const SORT_FIELDS = Object.freeze({cited_by: "cited_by_count", h_index: "h_index", plastic_citations: "plastic_citations", plastic_works: "plastic_works_count", m_quotient: "m_quotient", rising: "rising_score"});
// Owner request 2026-11-12: experts default to plastics citations.
export const DEFAULT_SORT = "plastic_citations";
const OA_VALUES = ["", "oa", "closed"];
const GITHUB_REPO = "https://github.com/ScottCoffin/CA_Plastics_Research_Dash";
export const EMPTY_MATCH_TEXT = "No experts match these filters.";
export const RISING_TITLE = "Rising citation momentum: trend in this expert's share of all Atlas experts' plastics citations over the last 5 complete years (percentile among experts with at least 10 plastics citations in that window).";
export const CSV_HEADER = ["author_id", "name", "work_count", "ca_works_count", "first_year", "last_year", "ca_basis", "domain_tags", "institution_ids", "cited_by_count", "h_index", "plastic_works_count", "plastic_citations", "plastic_citation_share_pct", "topic_counts"];

function topics() {
  const api = globalThis.AtlasTopics;
  if (!api) throw new Error("AtlasTopics is not loaded (shared/topics.js)");
  return api;
}

// ---- Hash state -----------------------------------------------------------------------------

export function defaultFilters() {
  return {search: "", institutionType: "", institution: "", tag: "", yearFrom: "", yearTo: "", caBasis: "", oa: "", early: false, sort: DEFAULT_SORT, collab: false};
}

// Clears the filter selections; the sort order and the collaborator flag are kept (classic reset).
export function resetFilters(filters) {
  return {...filters, search: "", institutionType: "", institution: "", tag: "", yearFrom: "", yearTo: "", caBasis: "", oa: "", early: false};
}

// Accepts "#<params>" and the legacy "#experts?<params>" (and bare "#experts").
export function parseExpertHash(hash) {
  let raw = String(hash ?? "").replace(/^#/, "");
  if (raw === "experts") raw = "";
  else if (raw.startsWith("experts?")) raw = raw.slice("experts?".length);
  const params = new URLSearchParams(raw);
  const pick = (name) => params.get(name) || "";
  const filters = {
    search: pick("search"),
    institutionType: pick("institution_type"),
    institution: pick("institution"),
    tag: pick("tag"),
    yearFrom: pick("year_from"),
    yearTo: pick("year_to"),
    caBasis: pick("ca_basis"),
    oa: OA_VALUES.includes(pick("oa")) ? pick("oa") : "",
    early: params.get("early") === "1",
    sort: SORT_KEYS.includes(pick("sort")) ? pick("sort") : DEFAULT_SORT,
    collab: params.get("collab") === "1"
  };
  // Deep link #author=<id> opens that researcher's drawer once the data is loaded.
  const author = /^[A-Za-z0-9]{1,40}$/.test(pick("author")) ? pick("author") : "";
  return {filters, author};
}

export function formatExpertQuery(filters) {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.institutionType) params.set("institution_type", filters.institutionType);
  if (filters.institution) params.set("institution", filters.institution);
  if (filters.tag) params.set("tag", filters.tag);
  if (filters.yearFrom) params.set("year_from", filters.yearFrom);
  if (filters.yearTo) params.set("year_to", filters.yearTo);
  if (filters.caBasis) params.set("ca_basis", filters.caBasis);
  if (filters.oa) params.set("oa", filters.oa);
  if (filters.early) params.set("early", "1");
  if (filters.sort && filters.sort !== DEFAULT_SORT) params.set("sort", filters.sort);
  if (filters.collab) params.set("collab", "1");
  return params.toString();
}

// "#<params>", or "" when every filter is at its default (the caller then drops the hash).
export function formatExpertHash(filters) {
  const query = formatExpertQuery(filters);
  return query ? `#${query}` : "";
}

// ---- Summaries and filtering ----------------------------------------------------------------

export function metricValue(value) {
  return value === null || value === undefined || value === "" || !Number.isFinite(Number(value)) ? null : Number(value);
}

export function workBasis(work) {
  if (work.ca_basis) return String(work.ca_basis);
  const led = Boolean(work.ca_led);
  const sampled = Boolean(work.ca_sampled || work.ca_setting === "sampled");
  if (led && sampled) return "both";
  if (led) return "ca-led";
  if (sampled) return "ca-sampled";
  if (work.ca_any_author) return "ca-affiliated";
  return "none";
}

export function primaryAffiliationText(author) {
  const primary = (author.primary_affiliations || []).map((item) => (typeof item === "string" ? item : item && item.name)).filter(Boolean);
  return primary.join(", ");
}

export function buildLookups(index, institutionList) {
  return {
    worksById: new Map(((index && index.works) || []).map((work) => [work.work_id, work])),
    institutionsById: new Map((institutionList || []).map((institution) => [institution.inst_id, institution]))
  };
}

// Per-author view model: works, tags, institutions and CA basis derived from the index lookups.
export function summarizeAuthor(author, worksById, institutionsById) {
  const works = (author.work_ids || []).map((id) => worksById.get(id)).filter(Boolean);
  const tags = [...new Set(works.flatMap((work) => [...(work.domain_tags || []), ...(work.facet_tags || [])]))].sort();
  const institutionIds = [...new Set(works.flatMap((work) => work.institution_ids || []).concat(author.institution_ids || []))];
  const institutionRows = institutionIds.map((id) => institutionsById.get(id)).filter(Boolean);
  const types = [...new Set(institutionRows.map((institution) => institution.atlas_type || "other"))];
  const caInstitutions = institutionRows.filter((institution) => institution.ca_flag);
  const bases = new Set(works.map(workBasis));
  const basis = bases.has("both") || (bases.has("ca-led") && bases.has("ca-sampled")) ? "both" : bases.has("ca-led") ? "ca-led" : bases.has("ca-sampled") ? "ca-sampled" : bases.has("ca-affiliated") ? "ca-affiliated" : "none";
  const years = works.map((work) => Number(work.year)).filter(Number.isFinite);
  const latest = years.length ? Math.max(...years) : null;
  const recentCount = latest === null ? 0 : works.filter((work) => Number(work.year) >= latest - 4).length;
  const topicWeights = topics().weights(works).filter(([tag]) => !topics().isMatrix(tag));
  const matrixWeights = topics().weights(works.map((work) => ({domain_tags: (work.facet_tags || []).filter(topics().isMatrix)}))).filter(([tag]) => topics().isMatrix(tag));
  return {...author, works, tags, topicWeights, matrixWeights, institutionRows, types, caInstitutions, basis, recentCount, latest};
}

export function buildAuthorSearchIndex(MiniSearchCtor, summaries) {
  const index = new MiniSearchCtor({idField: "author_id", fields: ["name", "author_id", "affiliation"], storeFields: []});
  index.addAll(summaries.map((author) => ({author_id: author.author_id, name: author.name || "", affiliation: primaryAffiliationText(author)})));
  return index;
}

// Ranked search (fuzzy, prefix, all words must match) returns the matching author ids.
export function searchAuthorIds(index, query) {
  return new Set(index.search(query, {prefix: true, fuzzy: 0.2, combineWith: "AND"}).map((hit) => hit.id));
}

export function expertComparator(sortKey) {
  const base = (a, b) => (b.ca_works_count || 0) - (a.ca_works_count || 0) || (b.work_count || 0) - (a.work_count || 0) || String(a.name).localeCompare(String(b.name));
  const field = Object.hasOwn(SORT_FIELDS, sortKey) ? SORT_FIELDS[sortKey] : undefined;
  if (!field) return base;
  // Null metrics sort last in either case; ties fall back to the CA-works order.
  return (a, b) => {
    const x = metricValue(a[field]);
    const y = metricValue(b[field]);
    if (x === null && y === null) return base(a, b);
    if (x === null) return 1;
    if (y === null) return -1;
    return y - x || base(a, b);
  };
}

// `rankedIds` is the MiniSearch id set for a non-empty query, or null (substring fallback).
export function filterAuthors(summaries, filters, rankedIds = null) {
  const search = filters.search.trim().toLowerCase();
  return summaries.filter((author) => {
    const haystack = `${author.name} ${author.author_id}`.toLowerCase();
    const idMatch = String(author.author_id).toLowerCase() === search;
    if (search && !idMatch && !(rankedIds ? rankedIds.has(author.author_id) : haystack.includes(search))) return false;
    if (filters.institutionType && !author.types.includes(filters.institutionType)) return false;
    if (filters.institution && !author.institutionRows.some((institution) => institution.inst_id === filters.institution)) return false;
    if (filters.tag && !author.tags.includes(filters.tag)) return false;
    if (filters.yearFrom && !author.works.some((work) => Number(work.year) >= Number(filters.yearFrom))) return false;
    if (filters.yearTo && !author.works.some((work) => Number(work.year) <= Number(filters.yearTo))) return false;
    if (filters.caBasis && author.basis !== filters.caBasis) return false;
    if (filters.oa === "oa" && !author.works.some((work) => work.is_oa)) return false;
    if (filters.oa === "closed" && !author.works.every((work) => !work.is_oa)) return false;
    if (filters.early && !author.early_career) return false;
    return true;
  }).sort(expertComparator(filters.sort));
}

export function virtualWindow({scrollTop, clientHeight, rowHeight, count, overscan}) {
  const start = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const end = Math.min(count, Math.ceil((scrollTop + clientHeight) / rowHeight) + overscan);
  return {start, end};
}

// Narrow screens wrap the metrics and affiliation lines more, so their slots are taller.
export function rowHeightForWidth(width) {
  return width < 640 ? 264 : 232;
}

// "N of M experts": N matching the filters, M in the whole index.
export function expertCountText(count, total) {
  return `${countFormat.format(count)} of ${countFormat.format(total)} expert${total === 1 ? "" : "s"}`;
}

// ---- Row and drawer markup ------------------------------------------------------------------

const countFormat = new Intl.NumberFormat("en-US");
function metricNumber(value) {
  const number = metricValue(value);
  return number === null ? "—" : countFormat.format(number);
}

export function plasticShare(author) {
  const total = metricValue(author.cited_by_count);
  const plastic = metricValue(author.plastic_citations);
  return total && plastic !== null ? Math.round((plastic / total) * 100) : null;
}

export function mQuotientTitle(author) {
  return author.first_pub_year ? `m-quotient: h-index divided by years since first publication (${author.first_pub_year}).` : "m-quotient: h-index divided by years since first publication (first year unavailable).";
}

export function expertPageUrl(authorId) {
  return classicUrl(`expert.html#author=${encodeURIComponent(authorId)}`);
}

// Metric line; the active sort key is bold. Plastics citations carry their basis in a tooltip.
export function expertMetricsHtml(author, sortKey) {
  const share = plasticShare(author);
  const corpusOnly = author.plastic_basis === "atlas_corpus";
  const basisTitle = corpusOnly ? "Plastics citations are counted only over this author's works in the Atlas California corpus, not their whole OpenAlex record." : "Plastics citations are counted across this author's whole OpenAlex record (works classified as plastics-related).";
  const part = (key, text, title = "") => { const body = sortKey === key ? `<strong>${escapeHtml(text)}</strong>` : escapeHtml(text); return title ? `<span title="${escapeHtml(title)}">${body}</span>` : body; };
  return [part("h_index", `h ${metricNumber(author.h_index)}`), part("cited_by", `${metricNumber(author.cited_by_count)} citations`), part("plastic_citations", `${metricNumber(author.plastic_citations)} on plastics (${share === null ? "—" : `${share}%`})`, basisTitle), part("plastic_works", `${metricNumber(author.plastic_works_count)} plastics works`), part("m_quotient", `m ${author.m_quotient ?? "—"}`, mQuotientTitle(author)), ...(author.rising_pct === null || author.rising_pct === undefined ? [] : [part("rising", `rising: ${author.rising_pct}th percentile`, RISING_TITLE)])].join(" · ") + (corpusOnly ? ` <span class="basis-note" title="${escapeHtml(basisTitle)}">(CA corpus only)</span>` : "");
}

export function expertTopicsHtml(author) {
  if (!author.topicsHtml) {
    const chips = [...author.topicWeights, ...author.matrixWeights].map(([tag, count]) => topics().chip(tag, count));
    author.topicsHtml = chips.length
      ? `<div class="expert-topics" aria-label="Research topics with work counts">${chips.join("")}<button class="topic-more" type="button" data-author-id="${escapeHtml(author.author_id)}" hidden>+0 more</button></div>`
      : '<p class="card-meta">No topic tags yet</p>';
  }
  return author.topicsHtml;
}

export function expertRowHtml(author, index, rowHeight, sortKey) {
  const years = author.first_year && author.last_year ? `${author.first_year}–${author.last_year}` : "Year unavailable";
  const primary = primaryAffiliationText(author);
  const affiliation = primary || (author.caInstitutions.length ? author.caInstitutions.map((institution) => institution.name).join(", ") : "No California affiliation");
  const meta = `${affiliation} · ${years} · ${author.recentCount} in recent 5 years · ${author.basis}`;
  const orcid = author.orcid ? ` · <a href="${escapeHtml(author.orcid)}" target="_blank" rel="noreferrer">ORCID</a>` : "";
  return `<div class="virtual-row" role="listitem" style="transform:translateY(${index * rowHeight}px);height:${rowHeight}px"><div class="card expert-card"><div class="card-header"><h3><button class="expert-link" type="button" data-author-id="${escapeHtml(author.author_id)}">${escapeHtml(author.name || "Unnamed author")}</button></h3><span class="expert-card-actions"><a class="expert-page-link" href="${escapeHtml(expertPageUrl(author.author_id))}" title="Open the full profile page">Full profile</a><span class="chip">${escapeHtml(author.ca_works_count || 0)} tagged works</span></span></div>${expertTopicsHtml(author)}<p class="expert-metrics">${expertMetricsHtml(author, sortKey)}${orcid}</p><p class="card-meta expert-affil" title="${escapeHtml(meta)}">${escapeHtml(meta)}</p></div></div>`;
}

export function profileIssueUrl(name, authorId) {
  const title = `Profile issue: ${name || "Researcher"} (${authorId})`;
  return `${GITHUB_REPO}/issues/new?title=${encodeURIComponent(title)}`;
}

// Returns only http(s) URLs (escaped by the caller), or "" for anything else.
export function safeHttpUrl(value) {
  try {
    const url = new URL(String(value ?? "").trim());
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

// Expert drawer profile from data/authors/<id>.json: owner-approved photo, ORCID bio, keywords and links.
// Returns "" when there is nothing to show. name labels the photo alt text.
export function profileHtml(profile, name = "") {
  if (!profile || typeof profile !== "object") return "";
  const parts = [];
  const photo = profile.photo || {};
  const thumb = safeHttpUrl(photo.thumb_url);
  if (thumb) {
    const source = safeHttpUrl(photo.source_url);
    const credit = photo.credit ? `Photo: ${escapeHtml(photo.credit)}` : "Photo";
    const licence = source ? `<a href="${escapeHtml(source)}" target="_blank" rel="noreferrer">${escapeHtml(photo.license || "Licence")}</a>` : escapeHtml(photo.license || "");
    parts.push(`<figure class="drawer-photo"><img src="${escapeHtml(thumb)}" alt="Photo of ${escapeHtml(name || "researcher")}" loading="lazy" width="96"><figcaption>${credit}${licence ? ` · ${licence}` : ""}</figcaption></figure>`);
  }
  const bio = String(profile.bio || "").trim();
  if (bio) parts.push(`<p class="drawer-bio">${escapeHtml(bio)}<span class="detail-meta"> (from ORCID)</span></p>`);
  const keywords = (Array.isArray(profile.keywords) ? profile.keywords : []).filter((keyword) => String(keyword ?? "").trim());
  if (keywords.length) parts.push(`<div class="kw-chips">${keywords.map((keyword) => `<span class="kw-chip">${escapeHtml(String(keyword).trim())}</span>`).join("")}</div>`);
  const links = (Array.isArray(profile.links) ? profile.links : []).map((link) => ({label: String(link?.label ?? "").trim(), url: safeHttpUrl(link?.url)})).filter((link) => link.url);
  if (links.length) parts.push(`<ul class="drawer-links">${links.map((link) => `<li><a href="${escapeHtml(link.url)}" target="_blank" rel="noreferrer">${escapeHtml(link.label || link.url)}</a></li>`).join("")}</ul>`);
  return parts.join("");
}

// Summary tiles for the drawer. Missing or null values render as an em dash.
// coauthorCount is null when the works carry no author_ids, so that tile is omitted.
export function drawerStatsHtml(author, works, coauthorCount) {
  const share = plasticShare(author);
  const corpusOnly = author.plastic_basis === "atlas_corpus";
  const years = works.map((work) => Number(work.year)).filter(Number.isFinite);
  const latest = years.length ? Math.max(...years) : null;
  const recent = latest === null ? null : works.filter((work) => Number(work.year) >= latest - 4).length;
  const first = metricValue(author.first_year);
  const last = metricValue(author.last_year);
  const activeYears = first === null && last === null ? "—" : `${first ?? "—"}–${last ?? "—"}`;
  const plasticNote = [`${share === null ? "—" : share}% of total`, corpusOnly ? "(CA corpus only)" : ""].filter(Boolean).join(" ");
  const tiles = [
    ["h-index", metricNumber(author.h_index)],
    ["Total citations", metricNumber(author.cited_by_count)],
    ["Plastics citations", metricNumber(author.plastic_citations), plasticNote],
    ["Plastics works", metricNumber(author.plastic_works_count)],
    ["CA-affiliated works", metricNumber(author.ca_works_count)],
    ["m-quotient", author.m_quotient === null || author.m_quotient === undefined ? "—" : String(author.m_quotient), author.first_pub_year ? `first paper ${author.first_pub_year}` : ""],
    ["Rising (percentile)", author.rising_pct === null || author.rising_pct === undefined ? "—" : `${author.rising_pct}th`],
    ["Years active", activeYears],
    ["Recent works (last 5 years)", metricNumber(recent)]
  ];
  if (coauthorCount !== null) tiles.push(["Distinct co-authors", metricNumber(coauthorCount)]);
  const tileHtml = ([label, value, note = ""]) => `<div class="drawer-stat"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}${note ? `<span class="drawer-stat-note">${escapeHtml(note)}</span>` : ""}</dd></div>`;
  return `<dl class="drawer-stats" aria-label="Summary metrics">${tiles.map(tileHtml).join("")}</dl>`;
}

// Affiliations are the author's own (owner 2026-11-12): OpenAlex affiliation history with years,
// else the institutions on this author's own authorships, never co-authors'.
export function historyFromAuthor(author, works, institutionsById) {
  if (Array.isArray(author.affiliation_history) && author.affiliation_history.length) {
    return author.affiliation_history.map((item) => ({name: item.name || item.id, years: item.years || []}));
  }
  return [...new Set(works.flatMap((work) => work.author_institution_ids || []).concat(author.institution_ids || []))]
    .map((id) => ({name: institutionsById.get(id)?.name || id, years: []}));
}

// Id -> name from works' byline entries (authors: [{id, name}]). Entries without an id or name are skipped.
export function bylineNames(works) {
  const names = new Map();
  (Array.isArray(works) ? works : []).forEach((work) => {
    (Array.isArray(work?.authors) ? work.authors : []).forEach((author) => {
      const id = String(author?.id ?? "").trim();
      const name = String(author?.name ?? "").trim();
      if (id && name && !names.has(id)) names.set(id, name);
    });
  });
  return names;
}

// Byline under a work title (plain text): names in byline order (at most 10), the profiled author in bold,
// then "et al. (N authors)" using author_count. Returns "" when the work has no authors list (old snapshots).
const BYLINE_SHOWN = 10;
const DRAWER_OTHERS_SHOWN = 12;
export function workAuthorsHtml(work, authorId) {
  const raw = Array.isArray(work?.authors) ? work.authors : [];
  const named = raw.map((author) => ({id: String(author?.id ?? "").trim(), name: String(author?.name ?? "").trim()})).filter((author) => author.name);
  if (!named.length) return "";
  const shown = named.slice(0, BYLINE_SHOWN);
  const declared = Number.isInteger(work.author_count) && work.author_count > 0 ? work.author_count : 0;
  const total = declared > 0 ? Math.max(declared, named.length) : raw.length;
  const parts = shown.map(({id, name}) => (id && id === String(authorId) ? `<strong>${escapeHtml(name)}</strong>` : escapeHtml(name)));
  if (total > shown.length) parts.push(`et al. (${total} authors)`);
  return `<p class="work-authors">${parts.join(", ")}</p>`;
}

// Frequent co-authors: shared-work counts per co-author. CA experts are named from expertsById; other
// co-authors are named from the works' byline entries and left out when no name is recorded.
export function coauthorSummary(works, authorId, expertsById) {
  const coauthorIds = [...new Set(works.flatMap((work) => (work.author_ids || []).filter((id) => id !== authorId)))];
  const coauthorCount = works.some((work) => Array.isArray(work.author_ids)) ? coauthorIds.length : null;
  const sharedCounts = new Map();
  works.forEach((work) => new Set(work.author_ids || []).forEach((id) => { if (id !== authorId) sharedCounts.set(id, (sharedCounts.get(id) || 0) + 1); }));
  const namedCoauthors = [...sharedCounts.entries()].filter(([id]) => expertsById.has(id)).sort((a, b) => b[1] - a[1] || String(expertsById.get(a[0]).name).localeCompare(String(expertsById.get(b[0]).name)));
  const names = bylineNames(works);
  const otherCoauthors = [...sharedCounts.entries()]
    .filter(([id]) => !expertsById.has(id) && names.has(id))
    .map(([id, shared]) => ({author_id: id, name: names.get(id), shared}))
    .sort((a, b) => b.shared - a.shared || a.name.localeCompare(b.name));
  return {coauthorCount, namedCoauthors, otherCoauthors};
}

export function workDatasetsHtml(work) {
  const datasets = Array.isArray(work?.datasets) ? work.datasets : [];
  if (!datasets.length) return "";
  const labels = { "DataCite-relation": "DataCite relation", "DAS-match": "Data availability statement" };
  const items = datasets.map((dataset) => {
    const doi = escapeHtml(dataset.doi);
    const relation = dataset.relation ? ` · relation: ${escapeHtml(dataset.relation)}` : "";
    const evidence = labels[dataset.evidence_type] || "Unrecognized evidence";
    return `<li><a href="https://doi.org/${doi}" target="_blank" rel="noreferrer">${doi}</a> <span class="chip">Evidence: ${escapeHtml(evidence)}</span>${relation}</li>`;
  }).join("");
  return `<div class="work-datasets"><p><strong>Datasets</strong></p><ul>${items}</ul></div>`;
}

// Inner HTML of the researcher drawer. author is the summary merged with detail.author;
// ctx.histogramSvg(rows, opts) is optional (null when the expert_page helpers are missing).
export function drawerContentHtml({author, works, authorId, profile, expertsById, institutionsById, histogramSvg = null}) {
  const drawerTopics = topics().weights(works, {matrices: true});
  const history = historyFromAuthor(author, works, institutionsById);
  const historyHtml = history.map((item) => { const years = item.years.length ? ` <span class="detail-meta">(${item.years.length > 1 ? `${Math.min(...item.years)}–${Math.max(...item.years)}` : item.years[0]})</span>` : ""; return `<li>${escapeHtml(item.name)}${years}</li>`; }).join("");
  const primaryText = primaryAffiliationText(author);
  const histogram = histogramSvg && Array.isArray(author.citations_by_year) && author.citations_by_year.length ? `<h3>Citations per year</h3><div class="drawer-histogram">${histogramSvg(author.citations_by_year, {width: 420, height: 180})}</div>` : "";
  const {coauthorCount, namedCoauthors, otherCoauthors} = coauthorSummary(works, authorId, expertsById);
  const otherHtml = otherCoauthors.length
    ? `<p class="detail-meta">Other co-authors (not on the California expert list)</p><ul class="coauthor-list">${otherCoauthors.slice(0, DRAWER_OTHERS_SHOWN).map((c) => `<li><span>${escapeHtml(c.name)}</span> <span class="detail-meta">${c.shared} shared ${c.shared === 1 ? "work" : "works"}</span></li>`).join("")}</ul>${otherCoauthors.length > DRAWER_OTHERS_SHOWN ? `<p class="detail-meta">Plus ${otherCoauthors.length - DRAWER_OTHERS_SHOWN} more co-authors.</p>` : ""}`
    : "";
  const worksHtml = works.map((work) => {
    const links = [work.doi ? `<a href="${escapeHtml(work.doi)}" target="_blank" rel="noreferrer">DOI</a>` : "", work.oa_url ? `<a href="${escapeHtml(work.oa_url)}" target="_blank" rel="noreferrer">Open access</a>` : ""].filter(Boolean).join("");
    const tags = [...(work.domain_tags || []), ...(work.facet_tags || [])];
    const affiliations = (work.institution_ids || []).map((id) => institutionsById.get(id)?.name || id).join(", ") || "not recorded";
    return `<li class="work-detail"><strong>${escapeHtml(work.title || "Untitled work")}</strong>${workAuthorsHtml(work, authorId)}<p>${escapeHtml(work.year || "Year unavailable")} · ${escapeHtml(work.journal || "Journal unavailable")} · ${escapeHtml(workBasis(work))}</p><p>Affiliations: ${escapeHtml(affiliations)}</p>${tags.length ? `<div class="topic-chips">${topics().sortTags(tags).map((tag) => topics().chip(tag)).join("")}</div>` : ""}<details class="work-abstract"><summary>Abstract</summary>${String(work.abstract || "").trim() ? `<p>${escapeHtml(String(work.abstract).trim())}</p>` : '<p class="detail-meta">No abstract available</p>'}</details>${workDatasetsHtml(work)}${links ? `<div class="work-links">${links}</div>` : ""}</li>`;
  }).join("");
  return `${primaryText ? `<p class="drawer-primary"><span class="detail-meta">Primary affiliation:</span> <strong>${escapeHtml(primaryText)}</strong></p>` : ""}<p class="detail-meta">${escapeHtml(author.author_id)} · ${escapeHtml(author.work_count || works.length)} works · ${escapeHtml(author.ca_works_count || 0)} CA-connected works</p><p class="drawer-actions"><a class="button-link" href="${escapeHtml(expertPageUrl(author.author_id || authorId))}">Open full profile page</a>${author.orcid ? ` <a href="${escapeHtml(author.orcid)}" target="_blank" rel="noreferrer">ORCID profile</a>` : ""}</p>${profileHtml(profile, author.name)}${drawerStatsHtml(author, works, coauthorCount)}${histogram}<h3>Topics</h3>${drawerTopics.length ? `<div class="topic-chips">${drawerTopics.map(([tag, count]) => topics().chip(tag, count)).join("")}</div>` : '<p class="detail-meta">No topic tags yet.</p>'}<details class="drawer-section"><summary>Affiliation history <span class="drawer-section-count">(${history.length} ${history.length === 1 ? "institution" : "institutions"})</span></summary><div class="drawer-section-body">${history.length ? `<ul class="affiliation-list">${historyHtml}</ul>` : '<p class="detail-meta">No institution affiliations in this snapshot.</p>'}</div></details><details class="drawer-section"><summary>Frequent co-authors <span class="drawer-section-count">(${namedCoauthors.length} CA experts${otherCoauthors.length ? `, ${otherCoauthors.length} others` : ""})</span></summary><div class="drawer-section-body">${namedCoauthors.length ? `<ul class="coauthor-list">${namedCoauthors.map(([id, count]) => `<li><button type="button" class="coauthor-link" data-author-id="${escapeHtml(id)}">${escapeHtml(expertsById.get(id).name || id)}</button> <span class="detail-meta">${count} shared ${count === 1 ? "work" : "works"}</span></li>`).join("")}</ul>` : '<p class="detail-meta">No co-authors on the California expert list.</p>'}${otherHtml}</div></details><h3>Works</h3>${works.length ? '<div class="abstract-controls" role="group" aria-label="Abstract display"><button type="button" id="abstracts-expand">Expand all abstracts</button><button type="button" id="abstracts-collapse">Collapse all</button></div>' : ""}<ul class="works-list">${works.length ? worksHtml : '<li class="empty">No works are available for this researcher.</li>'}</ul><p><a href="${GITHUB_REPO}/issues/new?title=Atlas%20data%20correction%20${encodeURIComponent(author.name || authorId)}" target="_blank" rel="noreferrer">Report an error about this profile</a></p>`;
}

// ---- CSV export -----------------------------------------------------------------------------

export function csvRow(author) {
  return [author.author_id, author.name, author.work_count, author.ca_works_count, author.first_year, author.last_year, author.basis, (author.tags || []).join(";"), (author.institution_ids || []).join(";"), author.cited_by_count, author.h_index, author.plastic_works_count, author.plastic_citations, plasticShare(author), author.topicWeights.map(([tag, count]) => `${tag}:${count}`).join(";")];
}

// Every cell is quoted with embedded quotes doubled; null and undefined become empty cells.
export function csvText(authors) {
  return [CSV_HEADER, ...authors.map(csvRow)].map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\n");
}
