// Community groups coverage and map (CG-12 part 1) for /groups. Three blocks inside the container the page gives:
// progress by region (one compact bar per region, a region table and a weekly cumulative line), a world map of the
// groups on the list by country, and a California panel of principal activities. Only aggregate counts are drawn: no
// individual group is named by the progress or map blocks. Pure helpers and string builders are exported for the node
// runtime test (tests/framework_groups_coverage_runtime.mjs); the DOM work is mountGroupsCoverage, which needs no DOM
// at import.
import {boundaryPaths} from "./world_map.js";

// ---- constants -------------------------------------------------------------------------------
// Counts below this are drawn muted with the number still visible (rule 7). None is hidden.
export const SMALL_CELL = 5;
// Regions shown before the "Show all" toggle.
export const REGION_LIMIT = 12;
// The catch-all bucket for groups with no recorded region. It is always the last row.
export const UNKNOWN_REGION = "region_unknown";
// Bar segments in stacking order. "tagged" (volunteer-tagged, reviewed, confirmed) is the progress that counts.
export const STATUS_ORDER = ["unlabelled", "assigned", "ambassador_tagged", "reviewed", "group_confirmed", "cannot_determine"];
export const STATUS_LABEL = {
  unlabelled: "Not yet tagged",
  assigned: "Assigned to a volunteer",
  ambassador_tagged: "Volunteer-tagged",
  reviewed: "Reviewed",
  group_confirmed: "Confirmed as a group",
  cannot_determine: "Could not be tagged",
};
export const TAGGED_STATUSES = ["ambassador_tagged", "reviewed", "group_confirmed"];
export const NO_WEEKLY_TEXT = "Tagging has not started yet.";
export const BAND_LABEL = [
  "No groups tagged yet",
  "Under a quarter tagged",
  "A quarter to under half tagged",
  "Half to under three quarters tagged",
  "Three quarters or more tagged",
];
export const CA_CODE = "US-CA";
// The neutrality note of the ambassadors map (framework/src/ambassadors.md), reused as it is.
export const MAP_CREDIT = "Map: Natural Earth 1:50m (public domain). Boundaries: Natural Earth disputed boundary lines, shown as Natural Earth's default view, and Pacific groupings (10m). Country positions are approximate; the map makes no claim about borders.";

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const fmt = (n) => Number(n || 0).toLocaleString("en-GB");

// ---- words and counts (pure) -----------------------------------------------------------------
// The count and its noun: "1 group", "706 groups". The noun is singular only for exactly one.
export function plural(n, one, many = `${one}s`) {
  return `${fmt(n)} ${Number(n) === 1 ? one : many}`;
}
export function isSmallCell(n, threshold = SMALL_CELL) {
  return Number(n) < threshold;
}
export function statusLabel(key) {
  return STATUS_LABEL[key] || String(key);
}
export function isTagged(group) {
  return TAGGED_STATUSES.includes(group?.status);
}
// Every status count of one region or country row, zero where the payload has none.
export function statusCounts(status = {}) {
  return Object.fromEntries(STATUS_ORDER.map((key) => [key, Number(status?.[key]) || 0]));
}
// The full status breakdown of one row as text (the bar's tooltip).
export function breakdownText(counts) {
  return STATUS_ORDER.map((key) => `${statusLabel(key)}: ${fmt(counts[key])}`).join("; ");
}

// ---- regions (pure) --------------------------------------------------------------------------
// One row per UN sub-region, largest first. The unknown-region bucket is labelled in plain words and always last.
export function regionRows(coverage) {
  return Object.entries(coverage?.by_region || {})
    .map(([name, row]) => ({
      region: name,
      label: name === UNKNOWN_REGION ? "Region not recorded" : name,
      roster: Number(row?.roster) || 0,
      tagged: Number(row?.tagged) || 0,
      counts: statusCounts(row?.status),
    }))
    .sort((a, b) => (a.region === UNKNOWN_REGION) - (b.region === UNKNOWN_REGION)
      || b.roster - a.roster || a.label.localeCompare(b.label));
}
// The rows shown by default (the first `limit`) and the rows behind the "Show all" toggle.
export function regionView(rows, limit = REGION_LIMIT) {
  return {shown: rows.slice(0, limit), hidden: rows.slice(limit), regionCount: rows.filter((r) => r.region !== UNKNOWN_REGION).length};
}
// The toggle's text for its current state.
export function toggleLabel(expanded, regionCount) {
  return expanded ? "Show fewer regions" : `Show all ${plural(regionCount, "region")}`;
}
// The stacked segments of one bar, as fractions of scaleMax (the largest region, so bars compare across rows).
export function stackSegments(counts, scaleMax) {
  let start = 0;
  return STATUS_ORDER.map((status) => {
    const n = counts[status] || 0;
    const segment = {
      status, label: statusLabel(status), n, small: isSmallCell(n),
      from: scaleMax ? start / scaleMax : 0, to: scaleMax ? (start + n) / scaleMax : 0,
    };
    start += n;
    return segment;
  });
}
// Weekly cumulative points from coverage.weekly_tagged. Accepts {week|date, cumulative|tagged}; empty when none.
export function weeklyPoints(list) {
  return (Array.isArray(list) ? list : [])
    .map((row) => ({
      week: String(row?.week ?? row?.date ?? ""),
      cumulative: Number(row?.cumulative ?? row?.tagged ?? NaN),
    }))
    .filter((p) => p.week && Number.isFinite(p.cumulative));
}

// ---- size and share (pure) -------------------------------------------------------------------
// Circle radius so that area is proportional to the roster size (radius ∝ √n), with a visible minimum.
export function sizeRadius(roster, maxRoster, maxRadius = 18) {
  if (!(roster > 0) || !(maxRoster > 0)) return 0;
  return Math.max(2.5, maxRadius * Math.sqrt(roster / maxRoster));
}
// Round down to 1, 2 or 5 times a power of ten, so legend values read as round numbers.
export function niceCount(x) {
  if (!(x >= 1)) return 0;
  const e = 10 ** Math.floor(Math.log10(x));
  const f = x / e;
  return (f >= 5 ? 5 : f >= 2 ? 2 : 1) * e;
}
// Up to three reference sizes for the size legend, largest first, without repeats.
export function legendSizes(maxRoster) {
  return [...new Set([niceCount(maxRoster), niceCount(maxRoster / 4), niceCount(maxRoster / 16)])].filter((v) => v > 0);
}
export function tagShare(tagged, roster) {
  return roster > 0 ? Math.min(1, (Number(tagged) || 0) / roster) : 0;
}
// Colour band of a share: 0 none tagged (outline only), then quarters.
export function shareBand(share) {
  if (!(share > 0)) return 0;
  if (share < 0.25) return 1;
  if (share < 0.5) return 2;
  if (share < 0.75) return 3;
  return 4;
}
export function formatShare(share) {
  return `${Math.round((Number(share) || 0) * 100)}%`;
}

// ---- countries (pure) ------------------------------------------------------------------------
// The centre of the bounding box of a country's largest sub-polygon, in the world.json frame. A country path is
// absolute M (start a sub-polygon) and L (line to) with Z; the largest sub-polygon by area is the mainland, so a
// country with overseas parts (France, Norway) is placed on its main territory. Returns null for an empty path.
export function countryAnchor(d) {
  const parts = String(d || "").split("M").slice(1).map((seg) => {
    const nums = (seg.match(/-?\d+(?:\.\d+)?/g) || []).map(Number);
    const pts = [];
    for (let i = 0; i + 1 < nums.length; i += 2) pts.push([nums[i], nums[i + 1]]);
    return pts;
  }).filter((pts) => pts.length >= 3);
  let best = null;
  for (const pts of parts) {
    let twice = 0;
    for (let i = 0; i < pts.length; i++) {
      const [x1, y1] = pts[i];
      const [x2, y2] = pts[(i + 1) % pts.length];
      twice += x1 * y2 - x2 * y1;
    }
    const area = Math.abs(twice) / 2;
    if (!best || area > best.area) best = {area, pts};
  }
  if (!best) return null;
  const xs = best.pts.map((p) => p[0]);
  const ys = best.pts.map((p) => p[1]);
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
}
// ISO2 -> [x, y] in the world frame: the path anchor for countries in world.json, else the world.small point.
export function countryAnchors(world) {
  const anchors = new Map();
  for (const c of world?.countries || []) {
    if (anchors.has(c.iso_a2)) continue;
    const at = countryAnchor(c.d);
    if (at) anchors.set(c.iso_a2, at);
  }
  for (const m of world?.small || []) {
    if (!anchors.has(m.iso) && Number.isFinite(m.x) && Number.isFinite(m.y)) anchors.set(m.iso, [m.x, m.y]);
  }
  return anchors;
}
export function countryName(iso, world) {
  const named = (world?.countries || []).find((c) => c.iso_a2 === iso);
  if (named?.name) return named.name;
  try {
    return new Intl.DisplayNames(["en"], {type: "region"}).of(iso) || iso;
  } catch {
    return iso;
  }
}
// One row per country on the list, largest first, with its anchor (null when the map cannot place it).
export function countryRows(coverage, world) {
  const anchors = countryAnchors(world);
  return Object.entries(coverage?.by_country || {})
    .map(([iso, row]) => {
      const roster = Number(row?.roster) || 0;
      const tagged = Number(row?.tagged) || 0;
      const share = tagShare(tagged, roster);
      return {
        iso, name: countryName(iso, world), roster, tagged, share,
        band: shareBand(share), small: isSmallCell(roster), anchor: anchors.get(iso) || null,
      };
    })
    .sort((a, b) => b.roster - a.roster || a.name.localeCompare(b.name));
}

// ---- California (pure) -----------------------------------------------------------------------
export function activityLabel(raw) {
  const text = String(raw ?? "").replace(/_/g, " ").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "Not stated";
}
// Tagged groups whose places include California (US-CA).
export function californiaGroups(groups) {
  return (groups || []).filter((g) => isTagged(g) && (g.places || []).includes(CA_CODE));
}
// Principal activities of the given groups with a count each, most common first.
export function activityRows(groups) {
  const counts = new Map();
  for (const group of groups) {
    for (const activity of new Set((group.primary_activities || []).map(String))) {
      counts.set(activity, (counts.get(activity) || 0) + 1);
    }
  }
  return [...counts]
    .map(([activity, n]) => ({activity, label: activityLabel(activity), n, small: isSmallCell(n)}))
    .sort((a, b) => b.n - a.n || a.label.localeCompare(b.label));
}

// ---- markup (pure string builders; no DOM access) --------------------------------------------
function regionRowHTML(row, scaleMax, extra) {
  const bar = stackSegments(row.counts, scaleMax).filter((s) => s.n > 0).map((s) =>
    `<span class="gc-seg seg-${s.status}${s.small ? " is-small" : ""}" style="width:${((s.to - s.from) * 100).toFixed(2)}%" title="${esc(`${s.label}: ${fmt(s.n)}`)}"></span>`).join("");
  return `<li class="gc-row${extra ? " gc-extra" : ""}"${extra ? " hidden" : ""}>` +
    `<span class="gc-row-name">${esc(row.label)}</span>` +
    `<span class="gc-bar" aria-hidden="true" title="${esc(breakdownText(row.counts))}">${bar}</span>` +
    `<span class="gc-row-count">${esc(plural(row.roster, "group"))} · ${fmt(row.tagged)} tagged</span></li>`;
}
// The region table: every region with every status count, below the bars.
function regionTableHTML(rows) {
  const head = STATUS_ORDER.map((key) => `<th scope="col">${esc(statusLabel(key))}</th>`).join("");
  const body = rows.map((r) => `<tr><th scope="row">${esc(r.label)}</th><td>${fmt(r.roster)}</td><td>${fmt(r.tagged)}</td>` +
    STATUS_ORDER.map((key) => `<td>${fmt(r.counts[key])}</td>`).join("") + "</tr>").join("");
  return `<details class="gc-details gc-region-table"><summary>Show as a table</summary><div class="gc-scroll" tabindex="0" role="region" aria-label="Table of groups"><table>
    <caption>Groups by region and status</caption>
    <thead><tr><th scope="col">Region</th><th scope="col">Groups</th><th scope="col">Tagged</th>${head}</tr></thead>
    <tbody>${body}</tbody></table></div></details>`;
}
function coverageHTML(coverage, rows, points) {
  const scaleMax = Math.max(0, ...rows.map((r) => r.roster));
  const view = regionView(rows);
  const legend = STATUS_ORDER.map((key) => `<li><span class="gc-sw seg-${key}" aria-hidden="true"></span>${esc(statusLabel(key))}</li>`).join("");
  const shown = view.shown.map((row) => regionRowHTML(row, scaleMax, false)).join("");
  const more = view.hidden.map((row) => regionRowHTML(row, scaleMax, true)).join("");
  const toggle = view.hidden.length
    ? `<button type="button" class="gc-toggle" aria-expanded="false" aria-controls="gc-regions" data-gc-toggle>${esc(toggleLabel(false, view.regionCount))}</button>`
    : "";
  return `<div class="gc-block gc-cov">
    <h3>Progress by region</h3>
    <p class="gc-caption">${esc(coverage?.denominator_note || "")}</p>
    <ul class="gc-legend" aria-label="Bar colours">${legend}</ul>
    <ul class="gc-rows" id="gc-regions">${shown}${more}</ul>
    ${toggle}
    ${regionTableHTML(rows)}
    <div class="gc-weekly" data-weekly>${weeklyHTML(points)}</div>
  </div>`;
}
// The weekly line is drawn by mountGroupsCoverage; the table and the empty sentence are plain HTML.
function weeklyHTML(points) {
  if (!points.length) return `<p class="gc-empty">${NO_WEEKLY_TEXT}</p>`;
  return `<p class="gc-caption">Groups tagged each week, cumulative.</p>${weeklyTableHTML(points)}`;
}
function weeklyTableHTML(points) {
  if (!points.length) return "";
  const body = points.map((p) => `<tr><td>${esc(p.week)}</td><td>${fmt(p.cumulative)}</td></tr>`).join("");
  return `<details class="gc-details"><summary>Show weekly counts as a table</summary><table><thead><tr><th scope="col">Week</th><th scope="col">Groups tagged (cumulative)</th></tr></thead><tbody>${body}</tbody></table></details>`;
}
function mapHTML(rows, world) {
  const [top, bottom] = world?.crop || [0, 520];
  const height = bottom - top;
  const placed = rows.filter((r) => r.anchor && r.roster > 0);
  const maxRoster = Math.max(0, ...rows.map((r) => r.roster));
  const bounds = boundaryPaths(world);
  const countries = (world?.countries || []).map((c) => `<path class="gm-land" d="${c.d}"/>`).join("");
  const dots = [...placed].sort((a, b) => b.roster - a.roster).map((r) => {
    const radius = sizeRadius(r.roster, maxRoster).toFixed(2);
    const note = `${r.name}: ${plural(r.roster, "group")} on the list, ${fmt(r.tagged)} tagged (${formatShare(r.share)})${r.small ? `. Fewer than ${SMALL_CELL} groups, so muted` : ""}`;
    return `<circle class="gm-dot band-${r.band}${r.small ? " is-small" : ""}" data-iso="${esc(r.iso)}" cx="${r.anchor[0].toFixed(1)}" cy="${r.anchor[1].toFixed(1)}" r="${radius}"><title>${esc(note)}</title></circle>`;
  }).join("");
  const sizes = legendSizes(maxRoster);
  const sizeSvg = sizes.map((v, i) => {
    const r = sizeRadius(v, maxRoster);
    const cx = 30 + i * 80;
    return `<g><circle class="gm-legend-dot" cx="${cx}" cy="${40 - r}" r="${r.toFixed(2)}"/><text x="${cx + 26}" y="44" class="gm-legend-text">${fmt(v)}</text></g>`;
  }).join("");
  const bandSvg = BAND_LABEL.map((label, i) => `<li><span class="gc-sw band-${i}" aria-hidden="true"></span>${esc(label)}</li>`).join("");
  const summary = `World map of ${plural(placed.length, "country", "countries")} with groups on the list. Circle area shows the number of groups; colour shows the share tagged. The table below lists every country.`;
  return `<div class="gm-mapbox">
    <svg class="gm-map" viewBox="0 ${top} ${world?.w || 1000} ${height}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="${esc(summary)}">
      <path class="gm-sea" d="${esc(world?.sphere || "")}"/>${countries}<path class="gm-pg" d="${esc(bounds.pacific)}"/><path class="gm-bd" d="${esc(bounds.disputed)}"/>${dots}
    </svg>
  </div>
  <div class="gm-key">
    <svg class="gm-sizes" width="260" height="50" viewBox="0 0 260 50" aria-hidden="true">${sizeSvg}</svg>
    <p class="gm-key-text">Circle area: number of groups on the list.</p>
    <ul class="gc-legend" aria-label="Colour key">${bandSvg}</ul>
    <p class="gm-key-text">Muted circles: fewer than ${SMALL_CELL} groups; the count is in the tooltip and the table.</p>
    <p class="credit">${esc(MAP_CREDIT)}</p>
  </div>
  ${mapTableHTML(rows)}`;
}
function mapTableHTML(rows) {
  const body = rows.map((r) => `<tr><td>${esc(r.name)}</td><td>${fmt(r.roster)}</td><td>${fmt(r.tagged)}</td><td>${formatShare(r.share)}</td></tr>`).join("");
  const empty = `<tr><td colspan="4">No countries on the list yet.</td></tr>`;
  return `<details class="gc-details gm-table"><summary>Show as a table</summary><table>
    <caption>Groups on the list by country</caption>
    <thead><tr><th scope="col">Country</th><th scope="col">Groups on the list</th><th scope="col">Tagged</th><th scope="col">Share tagged</th></tr></thead>
    <tbody>${body || empty}</tbody></table></details>`;
}
function californiaHTML(groups) {
  const cagroups = californiaGroups(groups);
  const head = `<h3>California</h3>`;
  if (!cagroups.length) return `<div class="gc-block gc-ca">${head}<p class="gc-empty">No California groups are tagged yet.</p></div>`;
  const rows = activityRows(cagroups);
  const max = Math.max(...rows.map((r) => r.n));
  const body = rows.map((r) => `<li class="gc-row"><div class="gc-row-head"><span class="gc-row-name">${esc(r.label)}</span><span class="gc-row-count">${fmt(r.n)}${r.small ? " (small count)" : ""}</span></div>` +
    `<div class="gc-bar" aria-hidden="true"><span class="gc-seg seg-ambassador_tagged${r.small ? " is-small" : ""}" style="width:${((r.n / max) * 100).toFixed(2)}%"></span></div></li>`).join("");
  const count = plural(cagroups.length, "tagged California group", "tagged California groups");
  return `<div class="gc-block gc-ca">${head}<p class="gc-caption">${count}; each bar counts the groups listing that activity as a principal activity.</p><ul class="gc-rows">${body}</ul></div>`;
}

// The whole content of the container as one HTML string, from the three data payloads.
export function coverageMarkup({coverage, groups, world}) {
  const rows = regionRows(coverage);
  const points = weeklyPoints(coverage?.weekly_tagged);
  const cov = coverageHTML(coverage, rows, points);
  const list = Array.isArray(groups) ? groups : (groups?.groups || []);
  const map = `<div class="gc-block gc-map"><h3>Where the groups are</h3>${mapHTML(countryRows(coverage, world), world)}</div>`;
  return `${cov}${map}${californiaHTML(list)}`;
}

// ---- DOM ---------------------------------------------------------------------------------------
// Fills el with the three blocks, wires the region toggle and draws the weekly line with Plot (Framework's global)
// when there are points.
export function mountGroupsCoverage(el, {coverage, groups, world, Plot = null} = {}) {
  if (!el) return;
  el.classList.add("gc");
  el.innerHTML = coverageMarkup({coverage, groups, world});
  const toggle = el.querySelector("[data-gc-toggle]");
  if (toggle) {
    const regionCount = regionView(regionRows(coverage)).regionCount;
    toggle.addEventListener("click", () => {
      const expanded = toggle.getAttribute("aria-expanded") !== "true";
      toggle.setAttribute("aria-expanded", String(expanded));
      toggle.textContent = toggleLabel(expanded, regionCount);
      el.querySelectorAll(".gc-extra").forEach((row) => { row.hidden = !expanded; });
    });
  }
  const points = weeklyPoints(coverage?.weekly_tagged);
  const host = el.querySelector("[data-weekly]");
  if (points.length && Plot && host) {
    const date = (p) => new Date(p.week);
    host.prepend(Plot.plot({
      height: 220, marginLeft: 48, ariaLabel: "Groups tagged each week, cumulative",
      x: {type: "utc", label: null}, y: {label: "Groups tagged", grid: true, zero: true},
      marks: [
        Plot.lineY(points, {x: date, y: "cumulative", curve: "step-after", stroke: "currentColor", strokeWidth: 2}),
        Plot.dot(points, {x: date, y: "cumulative", fill: "currentColor", r: 3}),
      ],
    }));
  }
}
