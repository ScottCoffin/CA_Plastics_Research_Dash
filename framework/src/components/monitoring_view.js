// Pure view helpers for the Monitoring page (AT-5c). Ported unchanged from the classic site's
// <script id="monitoring-view-helpers"> (site/index.html); the Node runtime test imports this file.
// No DOM access at module load.

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
