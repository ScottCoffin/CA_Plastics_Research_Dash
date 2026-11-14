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
  // Expert id from the page address (pure; the page passes in the address query and fragment).
  // "#author=<id>" wins; otherwise "?author=<id>" or "?id=<id>" are used. A full OpenAlex author URL
  // (openalex.org/A... with a scheme) is reduced to its last segment. status: "ok" (id is "A" plus digits,
  // returned upper-case), "missing" (no id given) or "malformed" (an id was given but is not an OpenAlex
  // author id). raw is the text that was tried, trimmed; empty when missing.
  function parseExpertId(search, hash) {
    const fromHash = new URLSearchParams(String(hash || "").replace(/^#/, "")).get("author");
    const query = new URLSearchParams(String(search || "").replace(/^\?/, ""));
    const raw = [fromHash, query.get("author"), query.get("id")]
      .map((value) => String(value ?? "").trim())
      .find((value) => value !== "") || "";
    if (!raw) return { id: "", status: "missing", raw: "" };
    const tail = raw.replace(/\/+$/, "").split("/").pop();
    const match = /^A(\d+)$/i.exec(tail);
    return match ? { id: `A${match[1]}`, status: "ok", raw } : { id: "", status: "malformed", raw };
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

  // Font size and padding (rem) for a topic tag: scaled by its count relative to the largest count
  // (sqrt scale, 0.8rem to 1.6rem). Missing or zero counts and max give the smallest size.
  function tagScale(count, max) {
    const c = Number(count);
    const m = Number(max);
    const ratio = Number.isFinite(c) && Number.isFinite(m) && m > 0 ? Math.min(1, Math.max(0, c / m)) : 0;
    const s = Math.sqrt(ratio);
    const r = (x) => Math.round(x * 100) / 100;
    return { fontRem: r(0.8 + 0.8 * s), padYRem: r(0.2 + 0.15 * s), padXRem: r(0.6 + 0.4 * s) };
  }

  // Id -> name from the byline entries (works[].authors). Entries without an id or name are skipped.
  function bylineNames(works) {
    const names = new Map();
    (Array.isArray(works) ? works : []).forEach((work) => {
      (Array.isArray(work && work.authors) ? work.authors : []).forEach((author) => {
        const id = String(author?.id ?? "").trim();
        const name = String(author?.name ?? "").trim();
        if (id && name && !names.has(id)) names.set(id, name);
      });
    });
    return names;
  }

  // Co-author rows for the list: {author_id, shared, name, expert}. names: Map from bylineNames.
  // expertNames: Map of CA expert id to name, or null when the expert list is unavailable. A co-author
  // with no name in either source is dropped, so the caller's "Plus N more" count is over named rows only.
  function coauthorEntries(counts, names, expertNames) {
    const hasExperts = Boolean(expertNames) && typeof expertNames.has === "function";
    return (Array.isArray(counts) ? counts : [])
      .map(({ author_id: id, shared }) => {
        const expert = hasExperts && expertNames.has(id);
        const name = (expert && expertNames.get(id)) || (names && names.get(id)) || "";
        return { author_id: id, shared, name: String(name).trim(), expert: Boolean(expert) };
      })
      .filter((entry) => entry.name);
  }

  // Byline under a publication title. Names in byline order (at most 10); the profiled expert (selfId) in
  // bold; CA experts (ids in expertNames, a Map) link to their profile; then "et al. (N authors)" when there
  // are more. Returns "" when the work has no authors list (old snapshots).
  const BYLINE_SHOWN = 10;
  function authorLineHtml(work, selfId, expertNames) {
    const raw = Array.isArray(work && work.authors) ? work.authors : [];
    const named = raw
      .map((author) => ({ id: String(author?.id ?? "").trim(), name: String(author?.name ?? "").trim() }))
      .filter((author) => author.name);
    if (!named.length) return "";
    const shown = named.slice(0, BYLINE_SHOWN);
    const declared = Number.isInteger(work.author_count) && work.author_count > 0 ? work.author_count : 0;
    const total = declared > 0 ? Math.max(declared, named.length) : raw.length;
    const self = String(selfId || "");
    const hasExperts = Boolean(expertNames) && typeof expertNames.has === "function";
    const parts = shown.map(({ id, name }) => {
      if (self && id === self) return `<strong>${escapeHtml(name)}</strong>`;
      if (hasExperts && id && expertNames.has(id)) return `<a href="expert.html#author=${encodeURIComponent(id)}">${escapeHtml(name)}</a>`;
      return escapeHtml(name);
    });
    if (total > shown.length) parts.push(`et al. (${total} authors)`);
    return `<p class="pub-authors">${parts.join(", ")}</p>`;
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

  // ---- Funding, data stewardship and co-author institutions ------------------------------------
  // Inputs come from data/expert_badges.json (grants, datasets, method) and data/institutions.json.
  const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
  const RECENT_START_YEARS = 5;
  const TOP_INSTITUTIONS = 8;
  const TOPIC_SUMMARY_SHOWN = 2;

  // Local calendar date as ISO "YYYY-MM-DD" (pass new Date()).
  function isoDate(date) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  }
  function isoDateOrEmpty(value) {
    const text = String(value ?? "").trim();
    return ISO_DATE_RE.test(text) ? text : "";
  }
  function stringList(value) {
    return (Array.isArray(value) ? value : []).map((v) => String(v ?? "").trim()).filter(Boolean);
  }
  // "Source: ...." sentence from a method note in the badges file; "" when there is no note.
  function sourceNote(text) {
    const note = String(text ?? "").trim();
    if (!note) return "";
    const sentence = note.charAt(0).toUpperCase() + note.slice(1);
    return `Source: ${sentence}${sentence.endsWith(".") ? "" : "."}`;
  }
  function countNoun(n, singular, plural) {
    return `${n} ${n === 1 ? singular : plural}`;
  }

  // Grants split on the given ISO date. Active: end date on or after today, or no end date and a start
  // date within the last five years. Grants without a valid date are past. Each list is newest start first.
  function fundingStatus(grants, today) {
    const day = isoDateOrEmpty(today);
    const cutoff = day ? `${Number(day.slice(0, 4)) - RECENT_START_YEARS}${day.slice(4)}` : "";
    const active = [];
    const past = [];
    (Array.isArray(grants) ? grants : []).forEach((grant) => {
      if (!grant || typeof grant !== "object") return;
      const start = isoDateOrEmpty(grant.start);
      const end = isoDateOrEmpty(grant.end);
      const isActive = day !== "" && (end !== "" ? end >= day : start !== "" && start >= cutoff);
      (isActive ? active : past).push(grant);
    });
    const newestFirst = (a, b) => compareText(isoDateOrEmpty(b.start), isoDateOrEmpty(a.start)) || compareText(a.title, b.title);
    return { active: active.sort(newestFirst), past: past.sort(newestFirst) };
  }

  // Header badges. Each one carries the source of its count in the title attribute.
  function expertBadgesHtml({ activeGrants = 0, datasetCount = 0, method = {} } = {}) {
    const badges = [];
    if (activeGrants > 0) {
      const title = `${sourceNote(method.funding)} Active: end date today or later, or no end date and a start within five years.`.trim();
      badges.push(`<li class="expert-badge" title="${escapeHtml(title)}">Active funding</li>`);
    }
    if (datasetCount > 0) {
      const title = sourceNote(method.datasets);
      badges.push(`<li class="expert-badge" title="${escapeHtml(title)}">Data steward · ${escapeHtml(countNoun(datasetCount, "dataset", "datasets"))}</li>`);
    }
    return badges.join("");
  }

  // Grant list for the Funding section: source note, then active grants before past ones.
  function grantItemHtml(grant, active) {
    const title = String(grant.title || "").trim() || "Untitled grant";
    const url = safeHttpUrl(grant.url);
    const titleHtml = url
      ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(title)}</a>`
      : escapeHtml(title);
    const facts = [grant.funder, grant.org]
      .map((v) => String(v ?? "").trim())
      .filter(Boolean)
      .map((v) => `<span>${escapeHtml(v)}</span>`);
    const years = grantYearsText(grant);
    facts.push(`<span>${escapeHtml(years)}</span>`);
    const tag = active ? ' <span class="badge active">Active</span>' : "";
    const note = grant.match === "pi_name"
      ? "<p class=\"grant-note\">Matched by the principal investigator's name; check the award.</p>"
      : "";
    return `<li class="grant"><h3>${titleHtml}${tag}</h3><p class="grant-meta">${facts.join(' <span aria-hidden="true">·</span> ')}</p>${note}</li>`;
  }
  function grantYearsText(grant) {
    const start = isoDateOrEmpty(grant.start).slice(0, 4);
    const end = isoDateOrEmpty(grant.end).slice(0, 4);
    if (start && end) return start === end ? start : `${start}–${end}`;
    if (start) return `From ${start}`;
    if (end) return `Until ${end}`;
    return "Dates not recorded";
  }
  function fundingHtml(funding, method = {}) {
    const note = sourceNote(method.funding);
    const items = [
      ...funding.active.map((g) => grantItemHtml(g, true)),
      ...funding.past.map((g) => grantItemHtml(g, false))
    ];
    return `${note ? `<p class="panel-intro">${escapeHtml(note)}</p>` : ""}<ul class="grant-list">${items.join("")}</ul>`;
  }

  // Dataset list. doiUrl(doi) returns the link for a DOI (or "" when there is none); the page supplies it.
  function datasetsHtml(datasets, doiUrl) {
    const items = (Array.isArray(datasets?.items) ? datasets.items : []).filter((d) => d && typeof d === "object");
    const count = Number(datasets?.count) > 0 ? Number(datasets.count) : items.length;
    const rows = items.map((d) => {
      const title = String(d.title || "").trim() || "Untitled dataset";
      const link = typeof doiUrl === "function" ? safeHttpUrl(doiUrl(d.doi)) : "";
      const titleHtml = link
        ? `<a href="${escapeHtml(link)}" target="_blank" rel="noreferrer">${escapeHtml(title)}</a>`
        : escapeHtml(title);
      const facts = [String(d.publisher ?? "").trim(), toYear(d.year) === null ? "" : String(toYear(d.year))]
        .filter(Boolean)
        .map((v) => `<span>${escapeHtml(v)}</span>`);
      return `<li class="dataset"><h3>${titleHtml}</h3>${facts.length ? `<p class="grant-meta">${facts.join(' <span aria-hidden="true">·</span> ')}</p>` : ""}</li>`;
    });
    const lead = `<p class="panel-intro">${escapeHtml(countNoun(count, "plastic-related dataset", "plastic-related datasets"))} in DataCite</p>`;
    return `${lead}<ul class="dataset-list">${rows.join("")}</ul>`;
  }

  // Co-author institutions. work.institution_ids lists every institution on the work; work.author_institution_ids
  // lists only this expert's own institutions on it (not aligned with author_ids). Co-author institutions are
  // therefore the work's institutions minus the expert's own ones. Works that list other author ids but not
  // selfId are skipped. institutionsById is a Map or plain object from data/institutions.json (inst_id -> record).
  function coauthorInstitutionSummary(works, selfId, institutionsById) {
    const lookup = (id) => {
      if (!institutionsById) return undefined;
      if (typeof institutionsById.get === "function") return institutionsById.get(id);
      return Object.hasOwn(institutionsById, id) ? institutionsById[id] : undefined;
    };
    const hasRecords = Boolean(institutionsById) && (typeof institutionsById.size === "number"
      ? institutionsById.size > 0
      : Object.keys(institutionsById).length > 0);
    const tally = new Map();
    (Array.isArray(works) ? works : []).forEach((work) => {
      if (!work || typeof work !== "object") return;
      if (selfId && Array.isArray(work.author_ids) && !work.author_ids.includes(selfId)) return;
      const own = new Set(stringList(work.author_institution_ids));
      stringList(work.institution_ids)
        .filter((id) => !own.has(id))
        .forEach((id) => tally.set(id, (tally.get(id) || 0) + 1));
    });
    const rows = [...tally.entries()]
      .map(([inst_id, shared]) => {
        const inst = lookup(inst_id);
        const known = Boolean(inst) && typeof inst === "object";
        return { inst_id, name: String((known && inst.name) || inst_id).trim(), works: shared, ca: known && inst.ca_flag === true };
      })
      .sort((a, b) => b.works - a.works || compareText(a.name, b.name) || compareText(a.inst_id, b.inst_id));
    const count = rows.length;
    const caCount = rows.filter((row) => row.ca).length;
    return {
      count,
      caShare: count > 0 && hasRecords ? caCount / count : null,
      top: rows.slice(0, TOP_INSTITUTIONS).map(({ inst_id, name, works: n, ca }) => ({ inst_id, name, works: n, ca }))
    };
  }

  // Summary sentence plus a list. Names link to the institution's SEM page only when they are California
  // institutions, as elsewhere on the page. Returns "" when there are no co-author institutions.
  const INST_LINK_ID_RE = /^[A-Za-z0-9_-]{1,60}$/;
  function coauthorInstitutionsHtml(summary) {
    if (!summary || summary.count === 0) return "";
    const pct = summary.caShare === null || summary.caShare === undefined ? null : Math.round(100 * summary.caShare);
    const lead = `${escapeHtml(`Co-authors came from ${countNoun(summary.count, "institution", "institutions")}`)}${pct === null ? "." : `; ${pct}% in California.`}`;
    const items = summary.top.map((row) => {
      const label = escapeHtml(row.name || row.inst_id);
      const name = row.ca && INST_LINK_ID_RE.test(row.inst_id)
        ? `<a href="sem.html#inst=${encodeURIComponent(row.inst_id)}">${label}</a>`
        : label;
      return `<li>${name} <span class="shared">· ${escapeHtml(countNoun(row.works, "work", "works"))}</span></li>`;
    });
    return `<p class="panel-intro">${lead}</p><ul class="coauthor-list">${items.join("")}</ul>`;
  }

  // Expertise statement from the top two topics and top two matrices (settings) among plastic-related works.
  // Template only, no generated prose. labelOf(tag) gives the visible label (AtlasTopics.label on the page).
  // Returns "" when there are fewer than three plastic-related works.
  function expertiseStatement(works, labelOf) {
    const label = typeof labelOf === "function" ? labelOf : (tag) => String(tag);
    const plastic = (Array.isArray(works) ? works : []).filter((w) => w && w.plastic_related === true);
    const n = plastic.length;
    if (n < 3) return "";
    const topicCounts = new Map();
    const settingCounts = new Map();
    plastic.forEach((work) => {
      new Set([...stringList(work.domain_tags), ...stringList(work.facet_tags)]).forEach((tag) => {
        const bucket = tag.startsWith("matrix:") ? settingCounts : topicCounts;
        bucket.set(tag, (bucket.get(tag) || 0) + 1);
      });
    });
    const top = (counts) => [...counts.entries()]
      .sort((a, b) => b[1] - a[1] || compareText(a[0], b[0]))
      .slice(0, TOPIC_SUMMARY_SHOWN);
    const parts = [];
    const topics = top(topicCounts);
    if (topics.length) {
      const named = topics.map(([tag, count]) => `${label(tag)} (${count} of ${countNoun(n, "work", "works")})`);
      parts.push(`Top topics in plastic-related work: ${named.join(" and ")}.`);
    }
    const settings = top(settingCounts).map(([tag]) => {
      const text = String(label(tag));
      return text.charAt(0).toLowerCase() + text.slice(1);
    });
    if (settings.length) {
      parts.push(`${settings.length > 1 ? "Most common settings" : "Most common setting"}: ${settings.join(", ")}.`);
    }
    return parts.join(" ");
  }

  const api = {
    escapeHtml,
    safeHttpUrl,
    parseAuthorParam,
    isValidAuthorId,
    parseExpertId,
    filterWorks,
    sortWorks,
    mQuotientText,
    plasticShare,
    yearRangesText,
    coauthorCounts,
    tagScale,
    bylineNames,
    coauthorEntries,
    authorLineHtml,
    profileHtml,
    citationSeries,
    citationHistogramSvg,
    isoDate,
    fundingStatus,
    expertBadgesHtml,
    fundingHtml,
    datasetsHtml,
    coauthorInstitutionSummary,
    coauthorInstitutionsHtml,
    expertiseStatement
  };
  global.AtlasExpert = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
