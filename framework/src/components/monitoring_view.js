// Pure view helpers for the Monitoring page (AT-5c). Ported unchanged from the classic site's
// <script id="monitoring-view-helpers"> (site/index.html); the Node runtime test imports this file.
// No DOM access at module load.

// Presentation helpers for the Monitoring usability pass (UX-9). They sit above the ported
// monitoringView block on purpose: tests/test_framework_monitoring.py compares all code after the
// ported object's export line with the classic helper block, so new code must not follow it.

// Plain-language glosses for licence ids. Summaries for orientation only; the source record governs.
export const licenceGlosses = Object.freeze({
  "CC-BY-4.0": "Creative Commons Attribution 4.0: reuse, including commercial, with credit to the source",
  "ODC-BY": "Open Data Commons Attribution: reuse with credit",
  "CC0-1.0": "Public-domain dedication: reuse with no conditions; credit is requested, not required",
  "fair-use-factual-values": "Factual values reported in a publication, shown under fair use; reuse terms for the underlying dataset are not recorded (check the source)"
});
export const licenceGlossFallback = "Reuse terms not recorded; check the source";

export function licenceGloss(id) {
  const key = typeof id === "string" ? id.trim() : "";
  return Object.hasOwn(licenceGlosses, key) ? licenceGlosses[key] : licenceGlossFallback;
}

// Full dates (with an optional time) show as YYYY-MM-DD. Partial dates (YYYY or YYYY-MM) stay as
// recorded because the day is unknown. Missing or invalid dates read "Unknown date".
export function formatSampleDate(sample) {
  if (monitoringView.year(sample) === null) return "Unknown date";
  const value = sample.date.trim();
  return /^\d{4}-\d{2}-\d{2}/.test(value) ? value.slice(0, 10) : value;
}

// The single non-empty value of `key` shared by every row, or null when rows disagree or none has one.
// Callers put a shared unit in the column header; otherwise each cell keeps its own unit inline.
export function sharedUnit(rows, key) {
  const values = new Set(rows.map((row) => (typeof row[key] === "string" ? row[key].trim() : "")));
  if (values.size !== 1) return null;
  const [unit] = values;
  return unit || null;
}

const csvHeaderLabel = (label, unit) => (unit ? `${label} (${unit})` : label);
const valueText = (value) => (value === null || value === undefined ? "" : String(value));

function csvField(value) {
  const text = valueText(value);
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function measureColumns(rows, label, valueKey, unitKey) {
  const unit = sharedUnit(rows, unitKey);
  const columns = [{ header: csvHeaderLabel(label, unit), value: (row) => valueText(row[valueKey]) }];
  if (!unit && rows.some((row) => row[unitKey])) columns.push({ header: `${label} unit`, value: (row) => row[unitKey] || "" });
  return columns;
}

// CSV of the observation rows the page is showing (all filtered rows, not only the current page).
// Leading '#' lines carry citations, licence ids and the download date; then a header row and data
// rows in RFC 4180 form (CRLF line endings, quoted fields). `downloadedOn` is a YYYY-MM-DD string.
export function samplesCsv(rows, datasets, downloadedOn) {
  const byId = new Map((datasets || []).map((dataset) => [dataset.id, dataset]));
  const sources = [...new Set(rows.map((row) => row.dataset_id))].map((id) => byId.get(id)).filter(Boolean);
  const citations = [...new Set(sources.map((dataset) => dataset.citation).filter(Boolean))];
  const licences = [...new Set(sources.map((dataset) => (dataset.publication_license && dataset.publication_license.id) || ""))];
  const licenceLines = (licences.length ? licences : [""]).map((id) => `Licence ${id || "not recorded"}: ${licenceGloss(id)}`);
  const columns = [
    { header: "Date", value: formatSampleDate },
    { header: "Matrix", value: (row) => monitoringView.matrix(row) || "Unknown matrix" },
    { header: "Region", value: (row) => monitoringView.region(row) },
    { header: "Method", value: (row) => valueText(row.method) },
    { header: "Particle count", value: (row) => valueText(row.particle_count) },
    ...measureColumns(rows, "Concentration", "concentration_value", "concentration_unit"),
    ...measureColumns(rows, "Deposition rate", "deposition_rate_value", "deposition_rate_unit"),
    { header: "Citation", value: (row) => valueText(row.citation || (byId.get(row.dataset_id) || {}).citation || "Citation unavailable") },
    { header: "Dataset ID", value: (row) => valueText(row.dataset_id) },
    { header: "Licence", value: (row) => (byId.get(row.dataset_id) && byId.get(row.dataset_id).publication_license && byId.get(row.dataset_id).publication_license.id) || "not recorded" }
  ];
  const comment = (text) => `# ${String(text).replace(/[\r\n]+/g, " ")}`;
  const lines = [
    comment("Monitoring observations exported from the CA Plastics Research Atlas (filtered view; every row matching the current filters)."),
    ...(citations.length ? citations : ["Citation unavailable"]).map((text) => comment(`Source citation: ${text}`)),
    ...licenceLines.map(comment),
    comment("Empty cells mean the value was not recorded; they are not evidence of a data gap."),
    comment(`Downloaded from the CA Plastics Research Atlas on ${downloadedOn}.`),
    columns.map((column) => csvField(column.header)).join(","),
    ...rows.map((row) => columns.map((column) => csvField(column.value(row))).join(","))
  ];
  return `${lines.join("\r\n")}\r\n`;
}

export const monitoringView = Object.freeze({
  unknownMatrix: "__unknown__",
  unknownYear: "__unknown__",
  matrix(sample) {
    const value = sample && typeof sample.matrix === "string" ? sample.matrix.trim() : "";
    return value || null;
  },
  year(sample) {
    const value = sample && typeof sample.date === "string" ? sample.date.trim() : "";
    if (/^\d{4}(?:-(?:0[1-9]|1[0-2]))?$/.test(value)) return value.slice(0, 4);
    const parts = /^(\d{4})-(\d{2})-(\d{2})(?:T.*)?$/.exec(value);
    if (!parts || !Number.isFinite(Date.parse(value))) return null;
    const [year, month, day] = parts.slice(1).map(Number);
    const calendarDate = new Date(0);
    calendarDate.setUTCHours(0, 0, 0, 0);
    calendarDate.setUTCFullYear(year, month - 1, day);
    if (calendarDate.getUTCFullYear() !== year || calendarDate.getUTCMonth() !== month - 1 || calendarDate.getUTCDate() !== day) return null;
    return value.slice(0, 4);
  },
  coordinates(sample) {
    if (!sample || typeof sample !== "object") return null;
    const rawLat = sample.lat;
    const rawLon = sample.lon;
    if ([rawLat, rawLon].some((value) => value === null || value === undefined || !["number", "string"].includes(typeof value) || (typeof value === "string" && !value.trim()))) return null;
    const lat = Number(rawLat);
    const lon = Number(rawLon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
    return [lat, lon];
  },
  region(sample) {
    if (sample.in_ca_land === true) return "land";
    if (sample.in_ca_state_waters === true) return "state_waters";
    if (sample.in_ca_land === false && sample.in_ca_state_waters === false) return "outside";
    return "unknown";
  },
  displayValue(value, fallback) {
    return value === null || value === undefined ? fallback : String(value);
  },
  filterOptions(samples) {
    const matrices = samples.map((sample) => monitoringView.matrix(sample));
    const years = samples.map((sample) => monitoringView.year(sample));
    return {
      matrices: [...new Set(matrices.filter(Boolean))].sort(),
      years: [...new Set(years.filter(Boolean))].sort(),
      hasUnknownMatrix: matrices.includes(null),
      hasUnknownYear: years.includes(null)
    };
  },
  locatedSamples(samples) {
    return samples.map((row) => ({ row, coordinates: monitoringView.coordinates(row) })).filter((item) => item.coordinates !== null);
  },
  filterSamples(samples, allowedDatasetIds, filters) {
    return samples.filter((sample) => {
      if (!allowedDatasetIds.has(sample.dataset_id)) return false;
      const matrix = monitoringView.matrix(sample);
      if (filters.matrix === monitoringView.unknownMatrix && matrix !== null) return false;
      if (filters.matrix && filters.matrix !== monitoringView.unknownMatrix && matrix !== filters.matrix) return false;
      const year = monitoringView.year(sample);
      if (filters.year === monitoringView.unknownYear && year !== null) return false;
      if (filters.year && filters.year !== monitoringView.unknownYear && year !== filters.year) return false;
      if (filters.region && monitoringView.region(sample) !== filters.region) return false;
      if (filters.contributor && String(sample.contributor_in_ca) !== filters.contributor) return false;
      return true;
    });
  }
});
