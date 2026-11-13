// Policy page: the curated DTSC microplastics regulatory timeline (Add-on A2 §7 Part B, EM-18).
// Reference information with outbound links only; it makes no statement about implementation,
// enforcement or effectiveness. The date text is reformatted from date_iso (UXD-7 prose style);
// the machine value is kept in <time datetime>. date_as_stated is the fallback when date_iso is unusable.
import {escapeHtml, loadJson} from "./atlas.js";

// Hardcoded so the caveat is shown even when the data file cannot be loaded.
export const CAVEAT = "Listing does not by itself create requirements; Priority Product designation is a separate rulemaking.";

const KIND_LABELS = {
  workshop: "Workshop",
  proposal: "Proposal",
  background: "Background document",
  finalized: "Finalized",
  effective: "Effective",
  work_plan: "Work plan"
};

// Only https links are shown (the YAML validator enforces this too).
export function isHttps(url) {
  if (typeof url !== "string") return false;
  try {
    return new URL(url).protocol === "https:";
  } catch {
    return false;
  }
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// Prose date from an ISO-style value: "2025-11-12" -> "12 Nov 2025", "2025-11" -> "Nov 2025",
// "2025" -> "2025". Returns null for anything else so the caller can fall back to date_as_stated.
export function formatDate(dateIso) {
  const m = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/.exec(String(dateIso ?? ""));
  if (!m) return null;
  const [, year, month, day] = m;
  if (month === undefined) return year;
  const monthNumber = Number(month);
  if (monthNumber < 1 || monthNumber > 12) return null;
  const label = MONTHS[monthNumber - 1];
  if (day === undefined) return `${label} ${year}`;
  const dayNumber = Number(day);
  // Day 0 of the following month is the last day of this one.
  const daysInMonth = new Date(Date.UTC(Number(year), monthNumber, 0)).getUTCDate();
  if (dayNumber < 1 || dayNumber > daysInMonth) return null;
  return `${dayNumber} ${label} ${year}`;
}

// Sort key: a month-only date sorts as the first day of that month (same rule as the validator).
function sortKey(dateIso) {
  const value = String(dateIso ?? "");
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : `${value}-01`;
}

// Newest-first view model. Entries without a date or event text are dropped.
export function timelineItems(data) {
  const entries = data && Array.isArray(data.entries) ? data.entries : [];
  return entries
    .filter((e) => e && typeof e === "object" && typeof e.date_as_stated === "string" && typeof e.event === "string")
    .map((e) => ({
      id: String(e.id ?? ""),
      dateAsStated: e.date_as_stated,
      dateIso: String(e.date_iso ?? ""),
      event: e.event,
      sourceLabel: typeof e.source_label === "string" ? e.source_label : "Source",
      sourceUrl: isHttps(e.source_url) ? e.source_url : null,
      kind: typeof e.kind === "string" ? e.kind : "",
      kindLabel: KIND_LABELS[e.kind] || (typeof e.kind === "string" ? e.kind : "")
    }))
    .sort((a, b) => (sortKey(a.dateIso) < sortKey(b.dateIso) ? 1 : sortKey(a.dateIso) > sortKey(b.dateIso) ? -1 : 0));
}

export function caveatHtml(detail = "") {
  const detailHtml = detail ? `<p class="pol-caveat-detail">${escapeHtml(detail)}</p>` : "";
  return `<div class="pol-caveat" role="note"><p class="pol-caveat-main"><strong>${escapeHtml(CAVEAT)}</strong></p>${detailHtml}</div>`;
}

function itemHtml(item) {
  const source = item.sourceUrl
    ? `<a href="${escapeHtml(item.sourceUrl)}" target="_blank" rel="noreferrer">${escapeHtml(item.sourceLabel)}</a>`
    : `<span class="pol-source-text">${escapeHtml(item.sourceLabel)}</span>`;
  const kind = item.kindLabel ? `<span class="pol-kind">${escapeHtml(item.kindLabel)}</span> ` : "";
  const prose = formatDate(item.dateIso);
  const dateHtml = prose
    ? `<time datetime="${escapeHtml(item.dateIso)}">${escapeHtml(prose)}</time>`
    : escapeHtml(item.dateAsStated);
  return `<li class="pol-item"><p class="pol-date">${dateHtml}</p>` +
    `<p class="pol-event">${escapeHtml(item.event)}</p>` +
    `<p class="pol-meta">${kind}${source}</p></li>`;
}

export function renderTimeline(data) {
  const items = timelineItems(data);
  const detail = data && typeof data.caveat_detail === "string" ? data.caveat_detail : "";
  const list = items.length
    ? `<ol class="pol-list" aria-label="DTSC microplastics timeline, newest first">${items.map(itemHtml).join("")}</ol>`
    : `<p class="data-note" role="status">No timeline entries are available.</p>`;
  return caveatHtml(detail) + list;
}

export async function mountPolicy(root = document.getElementById("policy-timeline")) {
  if (!root) return;
  // The caveat is rendered first, so it is visible whatever happens to the data request.
  root.innerHTML = caveatHtml() + `<p class="data-note" role="status">Loading the timeline…</p>`;
  let data;
  try {
    data = await loadJson("dtsc_timeline.json");
  } catch {
    root.innerHTML = caveatHtml() + `<p class="data-note" role="status">The timeline could not be loaded. Check the DTSC pages directly.</p>`;
    return;
  }
  root.innerHTML = renderTimeline(data);
}
