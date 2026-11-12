// Pure helpers for the full-page expert profile (site/expert.html).
// Browsers read window.AtlasExpert; Node tests read module.exports. No DOM access here.
(function (global) {
  "use strict";

  const PLOT = { all: "#9db9cb", plastic: "#b43c0c", ink: "#17324d", muted: "#4f6272", grid: "#d5e2e6" };

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }
  // Only http(s) URLs are returned (callers escape them again for attributes); anything else is "".
  function safeHttpUrl(value) {
    try {
      const url = new URL(String(value ?? "").trim());
      return ["http:", "https:"].includes(url.protocol) ? url.href : "";
    } catch {
      return "";
    }
  }
  // Author id from "#author=<id>" (preferred) or "?author=<id>". Empty string when absent.
  function parseAuthorParam(hash, search) {
    const fromHash = new URLSearchParams(String(hash || "").replace(/^#/, "")).get("author");
    const fromQuery = new URLSearchParams(String(search || "").replace(/^\?/, "")).get("author");
    return String(fromHash || fromQuery || "").trim();
  }
  function isValidAuthorId(raw) {
    return /^[A-Za-z0-9]{1,40}$/.test(String(raw || ""));
  }

  function toYear(value) {
    const y = Number.parseInt(value, 10);
    return Number.isInteger(y) ? y : null;
  }
  function workYear(work) {
    const y = Number(work.year);
    return Number.isInteger(y) && y > 0 ? y : null;
  }
  function compareText(a, b) {
    return String(a || "").localeCompare(String(b || ""), "en", { sensitivity: "base" });
  }
  function finiteOr(value, fallback) {
    const n = Number(value);
    return value === null || value === undefined || value === "" || !Number.isFinite(n) ? fallback : n;
  }

  // Filters compose with AND. tags: a Set (or array) of topic/matrix tags; a work must carry every tag
  // in domain_tags or facet_tags. Year bounds drop works without a valid year. q matches title and journal.
  function filterWorks(works, filters = {}) {
    const terms = String(filters.q || "").toLowerCase().split(/\s+/).filter(Boolean);
    const from = toYear(filters.yearFrom);
    const to = toYear(filters.yearTo);
    const tags = filters.tags ? [...filters.tags] : [];
    return (Array.isArray(works) ? works : []).filter((work) => {
      if (filters.plasticOnly && work.plastic_related !== true) return false;
      if (from !== null || to !== null) {
        const year = workYear(work);
        if (year === null) return false;
        if (from !== null && year < from) return false;
        if (to !== null && year > to) return false;
      }
      if (tags.length) {
        const have = new Set([...(work.domain_tags || []), ...(work.facet_tags || [])]);
        if (!tags.every((tag) => have.has(tag))) return false;
      }
      if (terms.length) {
        const haystack = [work.title, work.journal].join(" ").toLowerCase();
        if (!terms.every((term) => haystack.includes(term))) return false;
      }
      return true;
    });
  }

  // Stable sort. key: "year" (newest first, default), "citations" (most first), "title" (A to Z).
  // Works without a year sort last in the year order.
  function sortWorks(works, key) {
    const byYear = (a, b) => {
      const ya = workYear(a);
      const yb = workYear(b);
      if (ya === null && yb === null) return 0;
      if (ya === null) return 1;
      if (yb === null) return -1;
      return yb - ya;
    };
    const comparers = {
      year: byYear,
      citations: (a, b) => finiteOr(b.cited_by_count, 0) - finiteOr(a.cited_by_count, 0) || byYear(a, b),
      title: (a, b) => compareText(a.title, b.title) || byYear(a, b)
    };
    const compare = comparers[key] || comparers.year;
    return [...(Array.isArray(works) ? works : [])].sort(compare);
  }

  // "M-quotient" tooltip text. The value itself is shown separately by the page.
  function mQuotientText(author) {
    const first = toYear(author && author.first_pub_year);
    const when = first === null ? "first year unknown" : `first year ${first}`;
    return `h-index divided by years since first publication (${when})`;
  }

  // Share of total citations that are plastics-related, as a whole percentage, or null.
  function plasticShare(author) {
    const total = finiteOr(author && author.cited_by_count, null);
    const plastic = finiteOr(author && author.plastic_citations, null);
    return total && plastic !== null ? Math.round((100 * plastic) / total) : null;
  }

  // "2018, 2020–2022": ascending years with consecutive runs joined by an en dash.
  function yearRangesText(years) {
    const sorted = [...new Set((Array.isArray(years) ? years : []).map(toYear).filter((y) => y !== null))].sort((a, b) => a - b);
    const parts = [];
    let start = null;
    let prev = null;
    sorted.forEach((y) => {
      if (start === null) {
        start = y;
      } else if (y !== prev + 1) {
        parts.push(start === prev ? `${start}` : `${start}–${prev}`);
        start = y;
      }
      prev = y;
    });
    if (start !== null) parts.push(start === prev ? `${start}` : `${start}–${prev}`);
    return parts.join(", ");
  }

  // Co-author shared-work counts for one author, most shared first. The author themself is excluded.
  function coauthorCounts(works, selfId) {
    const counts = new Map();
    (Array.isArray(works) ? works : []).forEach((work) => {
      const ids = new Set(Array.isArray(work.author_ids) ? work.author_ids : []);
      ids.forEach((id) => {
        if (id && id !== selfId) counts.set(id, (counts.get(id) || 0) + 1);
      });
    });
    return [...counts.entries()]
      .map(([author_id, shared]) => ({ author_id, shared }))
      .sort((a, b) => b.shared - a.shared || compareText(a.author_id, b.author_id));
  }

  // Profile block from data/authors/<id>.json: photo credit, ORCID bio, keywords and links.
  // Returns "" when there is nothing to show. Only http(s) URLs are linked.
  function profileHtml(profile, name = "") {
    if (!profile || typeof profile !== "object") return "";
    const parts = [];
    const photo = profile.photo || {};
    const thumb = safeHttpUrl(photo.thumb_url);
    if (thumb) {
      const source = safeHttpUrl(photo.source_url);
      const credit = photo.credit ? `Photo: ${escapeHtml(photo.credit)}` : "Photo";
      const licence = source ? `<a href="${escapeHtml(source)}" target="_blank" rel="noreferrer">${escapeHtml(photo.license || "Licence")}</a>` : escapeHtml(photo.license || "");
      parts.push(`<figure class="expert-photo"><img src="${escapeHtml(thumb)}" alt="Photo of ${escapeHtml(name || "researcher")}" loading="lazy" width="120"><figcaption>${credit}${licence ? ` · ${licence}` : ""}</figcaption></figure>`);
    }
    const bio = String(profile.bio || "").trim();
    if (bio) parts.push(`<p class="expert-bio">${escapeHtml(bio)} <span class="muted">(from ORCID)</span></p>`);
    const keywords = (Array.isArray(profile.keywords) ? profile.keywords : []).map((k) => String(k ?? "").trim()).filter(Boolean);
    if (keywords.length) parts.push(`<ul class="kw-chips" aria-label="Keywords">${keywords.map((k) => `<li class="kw-chip">${escapeHtml(k)}</li>`).join("")}</ul>`);
    const links = (Array.isArray(profile.links) ? profile.links : [])
      .map((link) => ({ label: String(link?.label ?? "").trim(), url: safeHttpUrl(link?.url) }))
      .filter((link) => link.url);
    if (links.length) parts.push(`<ul class="expert-links">${links.map((link) => `<li><a href="${escapeHtml(link.url)}" target="_blank" rel="noreferrer">${escapeHtml(link.label || link.url)}</a></li>`).join("")}</ul>`);
    return parts.join("");
  }

  // Ascending, validated rows: year (int), all (count), plastic (count or null when unknown).
  function citationSeries(rows) {
    return (Array.isArray(rows) ? rows : [])
      .map((row) => ({
        year: toYear(row && row.year),
        all: Math.max(0, finiteOr(row && row.all, 0)),
        plastic: row && row.plastic !== null && row.plastic !== undefined ? finiteOr(row.plastic, null) : null
      }))
      .filter((row) => row.year !== null)
      .sort((a, b) => a.year - b.year);
  }

  // Round a positive peak up to 1, 2, 5 or 10 times a power of ten, so the y axis ends on a tidy value.
  function niceCeil(value) {
    if (!(value > 0)) return 1;
    const power = 10 ** Math.floor(Math.log10(value));
    const f = value / power;
    const mult = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
    return mult * power;
  }

  // Overlaid bars: a full-width bar for all citations and a narrower inner bar for plastics-related
  // citations. With no known plastics values, only the all-citation bars are drawn. Returns "" for no rows.
  function citationHistogramSvg(rows, opts = {}) {
    const series = citationSeries(rows);
    if (!series.length) return "";
    const width = Number(opts.width) > 0 ? Number(opts.width) : 640;
    const height = Number(opts.height) > 0 ? Number(opts.height) : 260;
    const label = opts.label || "Citations received per year";
    const hasPlastic = series.some((row) => row.plastic !== null);
    const left = 56;
    const right = 12;
    const top = 36;
    const bottom = 44;
    const plotW = width - left - right;
    const plotH = height - top - bottom;
    const peak = Math.max(0, ...series.map((row) => Math.max(row.all, row.plastic || 0)));
    const yMax = niceCeil(peak);
    const yOf = (value) => top + plotH * (1 - value / yMax);
    const baseline = yOf(0);
    const band = plotW / series.length;
    const barW = Math.max(2, band * 0.7);
    const every = Math.ceil(series.length / 12);
    const parts = [];
    [...new Set([0, 1, 2, 3, 4].map((i) => Math.round((yMax * i) / 4)))].forEach((tick) => {
      const y = yOf(tick);
      parts.push(`<line x1="${left}" x2="${width - right}" y1="${y}" y2="${y}" stroke="${PLOT.grid}"/>`);
      parts.push(`<text x="${left - 6}" y="${y + 4}" text-anchor="end" font-size="11" fill="${PLOT.muted}">${tick}</text>`);
    });
    series.forEach((row, i) => {
      const x = left + band * i + (band - barW) / 2;
      const tip = `${row.year}: ${row.all} ${row.all === 1 ? "citation" : "citations"}${row.plastic !== null ? `, ${row.plastic} plastics-related` : ""}`;
      parts.push(`<rect x="${x.toFixed(2)}" y="${yOf(row.all).toFixed(2)}" width="${barW.toFixed(2)}" height="${(baseline - yOf(row.all)).toFixed(2)}" fill="${PLOT.all}"><title>${escapeHtml(tip)}</title></rect>`);
      if (row.plastic !== null && row.plastic > 0) {
        const pw = barW * 0.5;
        parts.push(`<rect x="${(x + (barW - pw) / 2).toFixed(2)}" y="${yOf(row.plastic).toFixed(2)}" width="${pw.toFixed(2)}" height="${(baseline - yOf(row.plastic)).toFixed(2)}" fill="${PLOT.plastic}"/>`);
      }
      if (i % every === 0) parts.push(`<text x="${(x + barW / 2).toFixed(2)}" y="${height - bottom + 16}" text-anchor="middle" font-size="11" fill="${PLOT.muted}">${row.year}</text>`);
    });
    const legend = [`<rect x="${left}" y="10" width="12" height="12" fill="${PLOT.all}"/><text x="${left + 18}" y="20" font-size="12" fill="${PLOT.ink}">All citations</text>`];
    if (hasPlastic) legend.push(`<rect x="${left + 130}" y="10" width="12" height="12" fill="${PLOT.plastic}"/><text x="${left + 148}" y="20" font-size="12" fill="${PLOT.ink}">Plastics-related (Atlas plastics query)</text>`);
    const yTitle = `<text transform="rotate(-90)" x="${-(top + plotH / 2)}" y="14" text-anchor="middle" font-size="12" fill="${PLOT.muted}">Citations</text>`;
    const xTitle = `<text x="${left + plotW / 2}" y="${height - 6}" text-anchor="middle" font-size="12" fill="${PLOT.muted}">Year</text>`;
    return `<svg viewBox="0 0 ${width} ${height}" width="100%" role="img" aria-label="${escapeHtml(label)}" class="cit-chart"><title>${escapeHtml(label)}</title>${legend.join("")}${parts.join("")}${yTitle}${xTitle}</svg>`;
  }

  const api = {
    escapeHtml,
    safeHttpUrl,
    parseAuthorParam,
    isValidAuthorId,
    filterWorks,
    sortWorks,
    mQuotientText,
    plasticShare,
    yearRangesText,
    coauthorCounts,
    profileHtml,
    citationSeries,
    citationHistogramSvg
  };
  global.AtlasExpert = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
