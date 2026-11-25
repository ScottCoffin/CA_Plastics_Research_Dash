// Institution detail page: pure helpers with no DOM access (INST-PAGE). institution.js renders these;
// tests/framework_institution_runtime.mjs checks them in Node. Inputs are the per-institution payload
// (site/data/california/institution_works/<inst_id>.json) and the institution list (site/data/california/institutions.json).
// Only plastic-related works count toward every statistic, chart and topic size (plastic_related === true).

export const SECTION_IDS = ["experts", "publications", "topics"];
const INST_ID_PATTERN = /^[A-Za-z0-9._-]{1,64}$/;
const TOPIC_REM = {min: 0.85, max: 1.7};
const MATRIX_REM = {min: 0.8, max: 1.1};
const RECENT_YEAR_COUNT = 5;
export const LEAD_AUTHOR_LIMIT = 15;
export const COLLABORATOR_LIMIT = 10;
export const JOURNAL_LIMIT = 8;
export const CITED_LIMIT = 5;
export const SEARCH_LIMIT = 50;

export function isSafeInstId(value) {
  return typeof value === "string" && INST_ID_PATTERN.test(value);
}

// "#inst=<id>&section=experts|publications|topics". Unknown or unsafe values are dropped.
export function parseInstitutionHash(hash) {
  const params = new URLSearchParams(String(hash || "").replace(/^#/, ""));
  const instId = params.get("inst") || "";
  const section = params.get("section") || "";
  return {
    instId: isSafeInstId(instId) ? instId : "",
    section: SECTION_IDS.includes(section) ? section : "",
  };
}

export function isMatrixTag(tag) {
  return String(tag || "").startsWith("matrix:");
}

export function plasticWorks(works) {
  return (Array.isArray(works) ? works : []).filter((work) => work && work.plastic_related === true);
}

export function yearOf(work) {
  const year = Number(work && work.year);
  return Number.isInteger(year) ? year : null;
}

// One entry per calendar year from the first to the last plastic-related work (gaps are zero).
export function worksPerYear(works) {
  const years = works.map(yearOf).filter((year) => year !== null);
  if (!years.length) return [];
  const first = Math.min(...years);
  const last = Math.max(...years);
  const counts = new Map();
  years.forEach((year) => counts.set(year, (counts.get(year) || 0) + 1));
  return Array.from({length: last - first + 1}, (_, index) => ({year: first + index, count: counts.get(first + index) || 0}));
}

// The last complete calendar years: the year before `today`, and the four before it.
export function recentWindow(today = new Date()) {
  const to = today.getFullYear() - 1;
  return {from: to - RECENT_YEAR_COUNT + 1, to};
}

export function summaryStats(payload, today = new Date()) {
  const experts = Array.isArray(payload && payload.experts) ? payload.experts : [];
  const works = plasticWorks(payload && payload.works);
  const years = works.map(yearOf).filter((year) => year !== null);
  const window = recentWindow(today);
  const share = (count) => (works.length ? count / works.length : null);
  return {
    plasticWorks: works.length,
    experts: experts.length,
    citations: works.reduce((sum, work) => sum + Math.max(0, Number(work.cited_by_count) || 0), 0),
    oaShare: share(works.filter((work) => work.is_oa === true).length),
    caLedShare: share(works.filter((work) => work.ca_led === true).length),
    firstYear: years.length ? Math.min(...years) : null,
    lastYear: years.length ? Math.max(...years) : null,
    recentWorks: works.filter((work) => {
      const year = yearOf(work);
      return year !== null && year >= window.from && year <= window.to;
    }).length,
    recentFrom: window.from,
    recentTo: window.to,
  };
}

// Font size in rem, scaled by sqrt(count / largest) so that area, not width, tracks the count.
export function fontSizeRem(count, largest, bounds = TOPIC_REM) {
  if (!(largest > 0) || !(count > 0)) return bounds.min;
  const size = bounds.min + (bounds.max - bounds.min) * Math.sqrt(count / largest);
  return Math.round(size * 1000) / 1000;
}

function tagsOf(work) {
  return [...(Array.isArray(work.domain_tags) ? work.domain_tags : []), ...(Array.isArray(work.facet_tags) ? work.facet_tags : [])];
}

function countTags(works, matrix) {
  const counts = new Map();
  works.forEach((work) => {
    const domain = Array.isArray(work.domain_tags) ? work.domain_tags : [];
    const facets = Array.isArray(work.facet_tags) ? work.facet_tags : [];
    const tags = matrix
      ? [...facets, ...domain].filter(isMatrixTag)
      : domain.filter((tag) => !isMatrixTag(tag));
    new Set(tags).forEach((tag) => counts.set(tag, (counts.get(tag) || 0) + 1));
  });
  return [...counts.entries()]
    .map(([tag, count]) => ({tag, count}))
    .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag));
}

function sized(entries, total, bounds) {
  const largest = entries.length ? entries[0].count : 0;
  return entries.map((entry) => ({
    ...entry,
    share: total ? entry.count / total : 0,
    fontRem: fontSizeRem(entry.count, largest, bounds),
  }));
}

// Topic chips (domain tags) and matrix chips (matrix:* facets), each with a count, share and font size.
export function topicWeights(works) {
  const total = works.length;
  return {
    topics: sized(countTags(works, false), total, TOPIC_REM),
    matrices: sized(countTags(works, true), total, MATRIX_REM),
  };
}

// Works carrying a tag, as a domain or facet tag. An empty tag returns every work.
export function worksWithTag(works, tag) {
  return tag ? works.filter((work) => tagsOf(work).includes(tag)) : works;
}

export function workIds(works) {
  return works.map((work) => String(work.work_id || "")).filter(Boolean);
}

function topTopicsOf(topics, limit) {
  return (Array.isArray(topics) ? topics : [])
    .filter((entry) => Array.isArray(entry) && !isMatrixTag(entry[0]))
    .map(([tag, count]) => ({tag: String(tag), count: Number(count) || 0}))
    .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag))
    .slice(0, limit);
}

// Experts ranked by works at this institution, then plastic citations, then name. First and last
// author counts come from the author order of this institution's plastic-related works. A
// single-author work counts as first author only.
export function leadAuthors(experts, works) {
  const firstCounts = new Map();
  const lastCounts = new Map();
  works.forEach((work) => {
    const ids = Array.isArray(work.author_ids) ? work.author_ids.map(String) : [];
    if (!ids.length) return;
    firstCounts.set(ids[0], (firstCounts.get(ids[0]) || 0) + 1);
    if (ids.length > 1) lastCounts.set(ids[ids.length - 1], (lastCounts.get(ids[ids.length - 1]) || 0) + 1);
  });
  return (Array.isArray(experts) ? experts : [])
    .map((expert) => ({
      author_id: String(expert.author_id || ""),
      name: String(expert.name || expert.author_id || ""),
      inAtlas: expert.in_atlas_index === true,
      worksHere: Number(expert.works_at_institution) || 0,
      plasticCitations: Number(expert.plastic_citations) || 0,
      firstHere: firstCounts.get(String(expert.author_id)) || 0,
      lastHere: lastCounts.get(String(expert.author_id)) || 0,
      firstYear: Number.isInteger(expert.first_year) ? expert.first_year : null,
      lastYear: Number.isInteger(expert.last_year) ? expert.last_year : null,
      topTopics: topTopicsOf(expert.topics, 3),
    }))
    .sort((a, b) => b.worksHere - a.worksHere || b.plasticCitations - a.plasticCitations || a.name.localeCompare(b.name));
}

// Other institutions that appear on this institution's plastic-related works.
export function collaborators(works, instId, nameOf = (id) => id, limit = COLLABORATOR_LIMIT) {
  const counts = new Map();
  works.forEach((work) => {
    const ids = new Set((Array.isArray(work.institution_ids) ? work.institution_ids : []).map(String));
    ids.forEach((id) => {
      if (id !== instId) counts.set(id, (counts.get(id) || 0) + 1);
    });
  });
  return [...counts.entries()]
    .map(([id, count]) => ({inst_id: id, name: String(nameOf(id) || id), works: count}))
    .sort((a, b) => b.works - a.works || a.name.localeCompare(b.name))
    .slice(0, limit);
}

export function topJournals(works, limit = JOURNAL_LIMIT) {
  const counts = new Map();
  works.forEach((work) => {
    const journal = String(work.journal || "").trim();
    if (journal) counts.set(journal, (counts.get(journal) || 0) + 1);
  });
  return [...counts.entries()]
    .map(([journal, count]) => ({journal, count}))
    .sort((a, b) => b.count - a.count || a.journal.localeCompare(b.journal))
    .slice(0, limit);
}

export function mostCited(works, limit = CITED_LIMIT) {
  return [...works]
    .sort((a, b) => (Number(b.cited_by_count) || 0) - (Number(a.cited_by_count) || 0) || String(a.title || "").localeCompare(String(b.title || "")))
    .slice(0, limit);
}

// Bar geometry for the per-year chart in a width x height viewBox. The baseline sits above the labels.
export function barChartLayout(series, width = 600, height = 200, top = 12, bottom = 26) {
  const largest = Math.max(1, ...series.map((entry) => entry.count));
  const plot = height - top - bottom;
  const slot = series.length ? width / series.length : 0;
  const barWidth = Math.max(2, slot * 0.7);
  return {
    width,
    height,
    baseline: top + plot,
    largest,
    bars: series.map((entry, index) => {
      const barHeight = (entry.count / largest) * plot;
      return {
        year: entry.year,
        count: entry.count,
        x: index * slot + (slot - barWidth) / 2,
        y: top + plot - barHeight,
        width: barWidth,
        height: barHeight,
      };
    }),
  };
}

// Label every nth year so that about twelve labels fit.
export function labelStep(count) {
  return Math.max(1, Math.ceil(count / 12));
}

// Safe outbound links. Only ROR ids (with or without the ror.org prefix) and OpenAlex institution ids.
export function rorUrl(ror) {
  const match = /^(?:https:\/\/ror\.org\/)?(0[a-z0-9]{8})$/i.exec(String(ror || "").trim());
  return match ? `https://ror.org/${match[1].toLowerCase()}` : "";
}

export function openAlexUrl(instId) {
  return /^I\d+$/.test(String(instId || "")) ? `https://openalex.org/${instId}` : "";
}

// Institution search for the no-id page: every term must appear in name, city, region or type.
export function searchInstitutions(list, query, limit = SEARCH_LIMIT) {
  const terms = String(query || "").trim().toLowerCase().split(/\s+/).filter(Boolean);
  const matches = (Array.isArray(list) ? list : [])
    .filter((institution) => institution && isSafeInstId(institution.inst_id))
    .filter((institution) => {
      if (!terms.length) return true;
      const text = [institution.name, institution.city, institution.region, institution.atlas_type].join(" ").toLowerCase();
      return terms.every((term) => text.includes(term));
    })
    .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")));
  return {total: matches.length, shown: matches.slice(0, limit)};
}

// Research networks (site/data/california/research_networks.json). Each entry is cleaned here before the page
// uses it: unsafe links are emptied, and entries without an id or a name are dropped.
export const NETWORK_SCHEMA_VERSION = "net1.v1";
const ASSET_PATH_PATTERN = /^assets\/[A-Za-z0-9._\/-]+\.(?:png|jpe?g|svg|webp)$/i;
const AUTHOR_ID_PATTERN = /^[A-Za-z0-9]{1,32}$/;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Only absolute https URLs with a host survive; anything else becomes "".
export function httpsUrl(value) {
  const text = typeof value === "string" ? value.trim() : "";
  if (!text) return "";
  try {
    const url = new URL(text);
    return url.protocol === "https:" && url.hostname !== "" ? url.href : "";
  } catch {
    return "";
  }
}

function trimmed(value) {
  return typeof value === "string" ? value.trim() : "";
}

function instIdList(value) {
  return Array.isArray(value) ? value.map(trimmed).filter(isSafeInstId) : [];
}

function cleanNetwork(raw) {
  if (!raw || typeof raw !== "object") return null;
  const id = trimmed(raw.id);
  const name = trimmed(raw.name);
  if (!id || !name) return null;
  const logoPath = trimmed(raw.logo && raw.logo.path);
  const count = raw.listed_contributor_count;
  return {
    id,
    name,
    url: httpsUrl(raw.url),
    steward: trimmed(raw.steward),
    steward_source: httpsUrl(raw.steward_source),
    description: trimmed(raw.description),
    description_source: httpsUrl(raw.description_source),
    focus_areas: Array.isArray(raw.focus_areas) ? raw.focus_areas.map(trimmed).filter(Boolean) : [],
    related_links: Array.isArray(raw.related_links)
      ? raw.related_links
        .map((link) => ({label: trimmed(link && link.label), url: httpsUrl(link && link.url)}))
        .filter((link) => link.label && link.url)
      : [],
    host_institution_ids: instIdList(raw.host_institution_ids),
    member_institution_ids: instIdList(raw.member_institution_ids),
    listed_contributor_count: Number.isInteger(count) && count >= 0 ? count : null,
    roster_as_of: trimmed(raw.roster_as_of),
    atlas_contributors: Array.isArray(raw.atlas_contributors)
      ? raw.atlas_contributors
        .map((person) => ({author_id: trimmed(person && person.author_id), name: trimmed(person && person.name)}))
        .filter((person) => AUTHOR_ID_PATTERN.test(person.author_id) && person.name)
      : [],
    logo: ASSET_PATH_PATTERN.test(logoPath) && !logoPath.includes("..")
      ? {path: logoPath, alt: trimmed(raw.logo.alt)}
      : null,
    disclosure: trimmed(raw.disclosure) || null,
  };
}

// Networks for one institution: "hosted" when it hosts the consortium, "member" when its researchers
// are listed contributors. A network it hosts is shown only once, as hosted.
export function networksForInstitution(payload, instId) {
  const id = String(instId || "");
  const empty = {hosted: [], member: []};
  if (!isSafeInstId(id) || !payload || payload.schema_version !== NETWORK_SCHEMA_VERSION || !Array.isArray(payload.networks)) return empty;
  const networks = payload.networks.map(cleanNetwork).filter(Boolean);
  return {
    hosted: networks.filter((network) => network.host_institution_ids.includes(id)),
    member: networks.filter((network) => !network.host_institution_ids.includes(id) && network.member_institution_ids.includes(id)),
  };
}

// "2026-10-29" -> "29 Oct 2026". Invalid dates give "". UTC arithmetic, English month names.
export function formatRosterDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value ?? ""));
  if (!match) return "";
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return "";
  return `${day} ${MONTHS[month - 1]} ${year}`;
}

// One sentence on how many contributors the consortium lists and how many have Atlas profiles.
export function contributorSummary(network) {
  const listed = network ? network.listed_contributor_count : null;
  const atlasCount = network && Array.isArray(network.atlas_contributors) ? network.atlas_contributors.length : 0;
  const hasListed = Number.isInteger(listed) && listed >= 0;
  if (!hasListed && !atlasCount) return "";
  const date = formatRosterDate(network.roster_as_of);
  const lead = hasListed
    ? `The consortium lists ${listed} contributor${listed === 1 ? "" : "s"}`
    : "The consortium lists its contributors";
  const updated = date ? ` (page updated ${date})` : "";
  const atlas = atlasCount === 0
    ? "none have Atlas author profiles"
    : `${atlasCount} ${atlasCount === 1 ? "has an Atlas author profile" : "have Atlas author profiles"}`;
  return `${lead}${updated}; ${atlas}.`;
}
