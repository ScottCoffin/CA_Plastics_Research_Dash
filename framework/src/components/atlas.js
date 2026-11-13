// Shared runtime helpers for the Framework pages (AT-5).
// Data: pages fetch the classic site's committed payloads at runtime. The Framework build
// is deployed at <site>/app/, and every page sits at the top level of src/, so the data
// directory is always ../data/ relative to the page URL.

// Resolved lazily so Node tests can import this module (and modules that import it).
function pageBase() {
  return typeof document !== "undefined" ? document.baseURI : "http://localhost/app/";
}

export function dataUrl(path) {
  return new URL(String(path).replace(/^\/+/, ""), new URL("../data/", pageBase())).href;
}

export function classicUrl(path = "") {
  return new URL(String(path).replace(/^\/+/, ""), new URL("../", pageBase())).href;
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

// Same view model as the classic About tab (site/index.html aboutViewModel).
export function aboutViewModel(metadata, index) {
  const current = metadata && typeof metadata === "object" ? metadata : {};
  const indexData = index && typeof index === "object" ? index : {};
  const counts = current.counts && typeof current.counts === "object" ? current.counts : {};
  const generatedAt = typeof current.generated_at === "string" ? current.generated_at.trim() : "";
  const isFixture = generatedAt === "fixture";
  const refreshText = isFixture
    ? "Example data loaded — sample data, not a current refresh."
    : generatedAt
      ? `Last refresh (UTC): ${generatedAt}`
      : "Refresh time unavailable";
  // UX-6: each count carries its definition, so pages with different filters can be compared.
  const stats = [
    ["Authors", counts.authors, "California-affiliated authors with at least one published work."],
    ["Works", counts.works, "Distinct published works with a California author."],
    ["Institutions", counts.institutions, "Every institution on those works, including out-of-state co-authors."],
    ["California institutions", counts.ca_institutions, "California institutions with any published work. The Institutions page lists only those with a plastic-related work, so it shows fewer."],
    ["Labeled works", counts.labeled_works, ""]
  ].map(([label, value, note]) => ({label, value: formatCount(value), note}));
  stats.push({label: "Schema", value: current.schema_version || indexData.schema_version || "Unavailable"});
  return {isFixture, refreshText, stats};
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
