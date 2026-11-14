// Shared runtime helpers for the Framework pages (AT-5).
// Data: pages fetch the site's committed payloads (site/data) at runtime. Every page sits at the
// top level of src/. Since the owner's switch (2026-11-13) the deploy puts the app at the site
// root (scripts/assemble_site.py), so data is ./data/; the side-by-side layout (app under /app/,
// used by scripts/serve_framework_preview.py without --assembled) keeps ../data/.

// Resolved lazily so Node tests can import this module (and modules that import it).
function pageBase() {
  return typeof document !== "undefined" ? document.baseURI : "http://localhost/app/";
}

// The folder that holds data/, assets/ and the classic pages, as an absolute URL.
export function siteRoot(base = pageBase()) {
  const url = new URL(base);
  return new URL(/\/app\/[^/]*$/.test(url.pathname) ? "../" : "./", url);
}

export function dataUrl(path) {
  return new URL(String(path).replace(/^\/+/, ""), new URL("data/", siteRoot())).href;
}

export function classicUrl(path = "") {
  return new URL(String(path).replace(/^\/+/, ""), siteRoot()).href;
}

export async function loadJson(path, {optional = false} = {}) {
  const response = await fetch(dataUrl(path), {cache: "no-cache"});
  if (!response.ok) {
    if (optional) return null;
    throw new Error(`${path} returned HTTP ${response.status}`);
  }
  return response.json();
}

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[c]);
}

export function formatCount(value) {
  return Number.isSafeInteger(value) && value >= 0 ? new Intl.NumberFormat("en-US").format(value) : "Unavailable";
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

// UX-14: "12 Nov 2026, 17:09 UTC" for prose; null when the value is not a timestamp.
export function formatRefresh(value) {
  const date = new Date(String(value ?? ""));
  if (!/^\d{4}-\d{2}-\d{2}T/.test(String(value ?? "")) || Number.isNaN(date.getTime())) return null;
  const pad = (n) => String(n).padStart(2, "0");
  return `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}, ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())} UTC`;
}

// Same view model as the classic About tab (site/index.html aboutViewModel).
export function aboutViewModel(metadata, index) {
  const current = metadata && typeof metadata === "object" ? metadata : {};
  const indexData = index && typeof index === "object" ? index : {};
  const counts = current.counts && typeof current.counts === "object" ? current.counts : {};
  const generatedAt = typeof current.generated_at === "string" ? current.generated_at.trim() : "";
  const isFixture = generatedAt === "fixture";
  const refreshDisplay = isFixture ? null : formatRefresh(generatedAt);
  const refreshIso = refreshDisplay ? new Date(generatedAt).toISOString() : null;
  const refreshText = isFixture
    ? "Example data loaded — sample data, not a current refresh."
    : refreshDisplay
      ? `Last refresh: ${refreshDisplay}`
      : generatedAt
        ? `Last refresh (UTC): ${generatedAt}`
        : "Refresh time unavailable";
  // UX-6: each count carries its definition, so pages with different filters can be compared.
  const stats = [
    ["Authors", counts.authors, "California-affiliated authors with at least one published work."],
    ["Works", counts.works, "Distinct published works with a California author."],
    ["Institutions", counts.institutions, "Every institution on those works, including out-of-state co-authors."],
    ["California institutions", counts.ca_institutions, "California institutions with any published work. The Institutions page lists only those with a plastic-related work, so it shows fewer."]
  ];
  // UX-14: "Labeled works" is shown only when it differs from Works (every published work carries a label row).
  if (counts.labeled_works !== counts.works) stats.push(["Labeled works", counts.labeled_works, "Published works with a topic and relevance label."]);
  const rows = stats.map(([label, value, note]) => ({label, value: formatCount(value), note}));
  rows.push({label: "Schema", value: current.schema_version || indexData.schema_version || "Unavailable"});
  return {isFixture, refreshText, refreshDisplay, refreshIso, stats: rows};
}

// A DOI is shown only when it looks like a DOI (same rule as the classic About tab).
export function releaseDoi(release) {
  return release && typeof release.doi === "string" && /^10\.\d+\/[\w./-]+$/.test(release.doi) ? release.doi : null;
}

// Placeholder for views not yet ported: links to the matching classic-site tab.
export function classicLink(tab, label) {
  const a = document.createElement("a");
  a.href = classicUrl(`index.html#${tab}`);
  a.textContent = label;
  return a;
}
