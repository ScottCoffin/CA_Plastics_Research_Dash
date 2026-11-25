// The public ambassadors landing page (AMB-1 slice 1, no sign-in yet). The markup is static in ambassadors.md;
// this module fills the world map, the place search, the region panel and table, and the "Can I join?" checker
// from real data only: site/data/global/ambassador_regions.json (scripts/build_ambassador_regions.py), each region's
// site/data/<slug>/ambassador_institutions.json, places.json and assets/world/world.json. The pure helpers are
// exported for the node runtime test (tests/framework_ambassadors_runtime.mjs).
import {globalDataUrl, regionFileUrl, siteRoot} from "./atlas.js";
import {
  KIND_LABEL, attachMapGestures, boundaryPaths, clampView, foldName, mountPlaceSearch, placeExtent, placeRows,
} from "./world_map.js";
import {mountBadges} from "./ambassador_badge.js";

export const EMAIL_ADDRESS = "theplastiverse@gmail.com";

// ---- eligibility (pure) ----------------------------------------------------------------------
// Free-mail services are never accepted for sign-in (owner rule, AMB-1 section 2). A domain counts when it is the
// base domain or one of its subdomains, so "mail.niva.no" matches "niva.no" and "evilniva.no" does not.
export const FREE_MAIL = [
  "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "msn.com", "yahoo.com", "yahoo.co.uk",
  "icloud.com", "me.com", "mac.com", "aol.com", "proton.me", "protonmail.com", "pm.me", "gmx.de", "gmx.net", "gmx.com",
  "web.de", "mail.com", "yandex.ru", "zoho.com", "hey.com", "tutanota.com", "qq.com", "163.com", "126.com", "sina.com",
];
export function emailDomain(text) {
  const match = /^[^\s@]+@([a-z0-9.-]+\.[a-z]{2,})$/i.exec(String(text ?? "").trim());
  return match ? match[1].toLowerCase() : null;
}
export function domainWithin(domain, base) {
  return domain === base || domain.endsWith("." + base);
}
export function isFreeMail(domain) {
  return FREE_MAIL.some((base) => domainWithin(domain, base));
}
export function institutionHasDomain(institution, domain) {
  return (institution.domains || []).some((base) => domainWithin(domain, String(base).toLowerCase()));
}
// Every institution of the given regions, as {region, institution} pairs. slug limits the pool to one region.
export function institutionPool(regions, slug = null) {
  return regions
    .filter((r) => !slug || r.slug === slug)
    .flatMap((region) => (region.institutions || []).map((institution) => ({region, institution})));
}
// How well a name matches the typed text: 0 exact, 1 starts with it, 2 a word starts with it, 3 inside it; -1 no match.
function nameScore(name, q) {
  const n = foldName(name);
  if (n === q) return 0;
  if (n.startsWith(q)) return 1;
  if (n.split(/[\s,.()'-]+/).some((word) => word.startsWith(q))) return 2;
  return n.includes(q) ? 3 : -1;
}
// How well one institution matches the folded text: its name or an alias (as nameScore), or its acronym only when
// the whole text is the acronym ("NIVA", "ntnu"; acronyms never match inside other words). -1 when it does not.
export function institutionScore(institution, q) {
  if ((institution.acronyms || []).some((a) => foldName(a) === q)) return 0;
  let best = nameScore(institution.name, q);
  for (const alias of institution.aliases || []) {
    const s = nameScore(alias, q);
    if (s >= 0 && (best < 0 || s < best)) best = s;
  }
  return best;
}
// Type-ahead over institution names, acronyms, aliases and, when the text looks like a domain, their domains.
// Best matches first.
export function suggestInstitutions(query, pool, limit = 8) {
  const q = foldName(query);
  if (q.length < 2 || q.includes("@")) return [];
  const withDomain = q.includes(".");
  return pool
    .map((entry) => {
      let score = institutionScore(entry.institution, q);
      if (withDomain) {
        const domains = (entry.institution.domains || []).map((d) => String(d).toLowerCase());
        if (domains.some((d) => d.startsWith(q))) score = score < 0 ? 1 : Math.min(score, 1);
        else if (domains.some((d) => d.includes(q))) score = score < 0 ? 3 : Math.min(score, 3);
      }
      return {...entry, score};
    })
    .filter((entry) => entry.score >= 0)
    .sort((a, b) => a.score - b.score || a.institution.name.localeCompare(b.institution.name))
    .slice(0, limit);
}
// The eligibility check. regionSlug is the region of the chosen place (or null when none is chosen).
// States: empty; invalid (a malformed email); free_mail; eligible (institution and region); other_region (the
// institution is listed for a different region); choose (several names match); not_eligible.
export function checkEligibility(query, regions, regionSlug = null) {
  const text = String(query ?? "").trim();
  if (!text) return {state: "empty"};
  if (text.includes("@")) {
    const domain = emailDomain(text);
    if (!domain) return {state: "invalid"};
    if (isFreeMail(domain)) return {state: "free_mail"};
    const hits = institutionPool(regions).filter(({institution}) => institutionHasDomain(institution, domain));
    if (!hits.length) return {state: "not_eligible", region: regionSlug};
    const here = regionSlug ? hits.find((h) => h.region.slug === regionSlug) : hits[0];
    if (here) return {state: "eligible", region: here.region, institution: here.institution};
    return {state: "other_region", region: hits[0].region, institution: hits[0].institution, placeRegion: regionSlug};
  }
  const here = suggestInstitutions(text, institutionPool(regions, regionSlug), 8);
  if (here.length === 1 || (here.length && here[0].score === 0)) {
    return {state: "eligible", region: here[0].region, institution: here[0].institution};
  }
  if (here.length > 1) return {state: "choose", options: here};
  const elsewhere = regionSlug ? suggestInstitutions(text, institutionPool(regions), 8) : [];
  if (elsewhere.length === 1 || (elsewhere.length && elsewhere[0].score === 0)) {
    return {state: "other_region", region: elsewhere[0].region, institution: elsewhere[0].institution, placeRegion: regionSlug};
  }
  return {state: "not_eligible", region: regionSlug};
}

// ---- places and regions (pure) ---------------------------------------------------------------
// The region a place belongs to, or null. A region with subdivision_names (California) takes the places of those
// subdivisions (the admin-1 row, or a city whose parent starts with the subdivision name); otherwise every place in
// its countries belongs to it.
export function regionForPlace(place, regions) {
  if (!place) return null;
  for (const region of regions) {
    if (!(region.country_codes || []).includes(place.iso)) continue;
    if (!(region.subdivision_names || []).length) return region;
    const top = place.kind === "admin1" ? place.name : String(place.parent || "").split(",")[0].trim();
    if (region.subdivision_names.includes(top)) return region;
  }
  return null;
}
// The region whose whole country is one region (no subdivision list), for a country code, or null.
export function countryRegion(iso, regions) {
  return regions.find((r) => !(r.subdivision_names || []).length && (r.country_codes || []).includes(iso)) || null;
}
// The view (frame units) that shows a place: its zoom extent with a little room, at least minWidth units wide, kept
// inside the frame. aspect is the map's width over height.
export function placeView(geom, iso, aspect, frame, minWidth = 120) {
  const [x0, y0, x1, y1] = placeExtent(geom, iso);
  const w = Math.min(Math.max((x1 - x0) * 1.3, minWidth), frame[2]);
  const h = w / aspect;
  return clampView([(x0 + x1) / 2 - w / 2, (y0 + y1) / 2 - h / 2, w, h], frame);
}

// ---- page -----------------------------------------------------------------------------------
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]));
const fmt = (n) => Number(n).toLocaleString("en-GB");
const STATUS_OPEN = "Open to ambassadors";

function mapMarkup(world, regions, placeByIso) {
  const [top, bottom] = world.crop;
  const height = bottom - top;
  const open = new Set(regions.filter((r) => !(r.subdivision_names || []).length).flatMap((r) => r.country_codes));
  const caOpen = regions.some((r) => (r.subdivision_names || []).includes("California"));
  const paths = world.countries.map((c) =>
    `<path class="c${open.has(c.iso_a2) ? " open" : ""}" data-iso="${esc(c.iso_a2)}" d="${c.d}"/>`).join("");
  // world.json carries California's outline (ca) for the US; it is drawn over the US when California is open.
  const ca = caOpen ? `<path class="ca open" data-region="california" d="${world.ca}"/>` : "";
  const dots = (world.small || []).map((m) => {
    const name = placeByIso.get(m.iso)?.name || m.iso;
    const on = open.has(m.iso);
    return `<g class="sm${on ? " open" : ""}" data-iso="${esc(m.iso)}" tabindex="0" role="button" aria-label="${esc(name)}${on ? ", open to ambassadors" : ", not open yet"}. Select to see the place.">` +
      `<circle class="sm-hit" cx="${m.x}" cy="${m.y}" r="8"/><circle class="sm-dot" cx="${m.x}" cy="${m.y}" r="3"/></g>`;
  }).join("");
  const bounds = boundaryPaths(world);
  return `<div class="amb-mapbox">
    <svg class="amb-map" id="amb-map" tabindex="0" viewBox="0 ${top} ${world.w} ${height}" preserveAspectRatio="xMidYMid meet" role="group" aria-label="World map of ambassador regions. Select a shape or dot to open its panel; the table below lists the same regions.">
      <path class="sea" d="${world.sphere}"/>${paths}${ca}<path class="pg" d="${bounds.pacific}"/><path class="bd" d="${bounds.disputed}"/>${dots}<path class="zoom-box" d="" style="display:none"/>
    </svg>
    <div class="map-zoom" role="group" aria-label="Map zoom">
      <button type="button" class="btn" id="amb-zoom-in" aria-label="Zoom in" title="Zoom in">+</button>
      <button type="button" class="btn" id="amb-zoom-out" aria-label="Zoom out" title="Zoom out">&minus;</button>
      <button type="button" class="btn" id="amb-zoom-reset" aria-label="Reset map view" title="Reset map view">Reset</button>
    </div>
    <div class="map-hint" id="amb-hint" aria-live="polite"></div>
  </div>`;
}

function regionPanelHTML(region) {
  const count = region.institutions.length;
  return `<h3>${esc(region.name)}</h3>
    <p class="status"><span class="sw st-open" aria-hidden="true"></span>${STATUS_OPEN}</p>
    <dl class="kv">
      <dt>Eligible institutions</dt><dd>${fmt(count)} listed. An institution is listed when at least three plastics works have an author there.</dd>
      <dt>Ambassadors</dt><dd>None confirmed yet.</dd>
    </dl>
    <p class="actions"><a class="btn solid" href="#can-i-join" data-check="${esc(region.slug)}">Check if you can join ${esc(region.name)}</a></p>
    <p><a class="link" href="${esc(region.page)}">Open the ${esc(region.name)} page</a></p>`;
}

function placePanelHTML(place, subRegions) {
  const inside = subRegions.length
    ? `<p>Open inside ${esc(place.name)}: ${subRegions.map((r) => `<button type="button" class="link-btn" data-region="${esc(r.slug)}">${esc(r.name)}</button>`).join(", ")}.</p>`
    : "";
  return `<h3>${esc(place.name)}</h3>
    <p class="status">No ambassador region is open here yet.</p>${inside}
    <p>Tell us which region you know: email <span class="addr">${EMAIL_ADDRESS}</span> (text, no link needed).</p>`;
}

const RESULT = {
  empty: ["", "Type your work email or your institution's name."],
  invalid: ["Not a complete email address", "Check the address, or type your institution's name instead."],
  free_mail: ["Free email services cannot be used to join",
    `Gmail, Outlook, Proton and similar services cannot be accepted. Use your institution's work address, or email ${EMAIL_ADDRESS}.`],
  choose: ["Several institutions match", "Choose one from the list below."],
};

function resultHTML(result, place, regions) {
  const placeName = place ? place.name : "";
  switch (result.state) {
    case "eligible":
      return `<b>Eligible: ${esc(result.institution.name)}</b>Your institution is listed for ${esc(result.region.name)}. Sign-in opens soon; you will sign in with your work email address.`;
    case "other_region":
      return `<b>Not eligible for ${esc(placeName || result.placeRegion || "this place")} yet</b>${esc(result.institution.name)} is listed for ${esc(result.region.name)}. Choose ${esc(result.region.name)} on the map to join there.`;
    case "not_eligible": {
      const where = result.region ? regions.find((r) => r.slug === result.region)?.name : "";
      return `<b>Not on the list yet</b>Your institution is not among the institutions tagged for plastics research${where ? " in " + esc(where) : ""}. Email <span class="addr">${EMAIL_ADDRESS}</span> with your institution's name and the place you know.`;
    }
    default: {
      const [head, body] = RESULT[result.state] || RESULT.empty;
      return head ? `<b>${esc(head)}</b>${esc(body)}` : esc(body);
    }
  }
}

export async function mountAmbassadors(root) {
  const [regionsResponse, placesResponse, worldResponse] = await Promise.all([
    fetch(globalDataUrl("ambassador_regions.json"), {cache: "no-cache"}),
    fetch(globalDataUrl("places.json"), {cache: "no-cache"}).catch(() => null),
    fetch(new URL("assets/world/world.json", siteRoot()), {cache: "no-cache"}).catch(() => null),
  ]);
  if (!regionsResponse.ok) throw new Error(`ambassador_regions.json returned HTTP ${regionsResponse.status}`);
  const index = await regionsResponse.json();
  const REGIONS = await Promise.all((index.regions || []).map(async (region) => {
    const response = await fetch(regionFileUrl(region.slug, "ambassador_institutions.json"), {cache: "no-cache"}).catch(() => null);
    const file = response?.ok ? await response.json().catch(() => null) : null;
    return {...region, institutions: file?.institutions || []};
  }));
  const PLACE_ROWS = placeRows(placesResponse?.ok ? await placesResponse.json().catch(() => null) : null);
  const WORLD = worldResponse?.ok ? await worldResponse.json().catch(() => null) : null;
  const $ = (s) => root.querySelector(s);
  const countries = PLACE_ROWS.filter((r) => r.kind === "country");
  const placeByIso = new Map(countries.map((r) => [r.iso, r]));
  const placeFor = (region) => {
    const iso = region.country_codes[0];
    if (region.subdivision_names?.length) {
      return PLACE_ROWS.find((r) => r.kind === "admin1" && r.iso === iso && region.subdivision_names.includes(r.name)) || placeByIso.get(iso);
    }
    return placeByIso.get(iso);
  };

  // ---- map -------------------------------------------------------------------------------------
  const mapHost = $("#amb-map-host");
  if (!WORLD) {
    mapHost.innerHTML = `<p class="status" role="status">The map could not load. The table below lists the same regions.</p>`;
  } else {
    mapHost.innerHTML = mapMarkup(WORLD, REGIONS, placeByIso);
  }
  const svg = $("#amb-map");
  const FULL = WORLD ? [0, WORLD.crop[0], WORLD.w, WORLD.crop[1] - WORLD.crop[0]] : null;
  let vb = FULL ? FULL.slice() : null;
  const drag = {moved: false};
  const aspect = () => FULL[2] / FULL[3];
  // Dots keep a constant size on screen, and each hit area is at least 24 CSS px across (WCAG 2.5.8).
  const sizeMarkers = () => {
    const scale = svg.getBoundingClientRect().width / vb[2];
    if (!scale) return;
    svg.querySelectorAll(".sm-dot").forEach((d) => d.setAttribute("r", (4.5 / scale).toFixed(3)));
    svg.querySelectorAll(".sm-hit").forEach((d) => d.setAttribute("r", (13 / scale).toFixed(3)));
  };
  const showView = (next) => {
    vb = next;
    svg.setAttribute("viewBox", vb.join(" "));
    sizeMarkers();
  };
  let gestures = null;
  if (svg) {
    gestures = attachMapGestures(svg, {
      frame: FULL,
      view: () => vb,
      apply: showView,
      reset: () => showView(FULL.slice()),
      hint: $("#amb-hint"),
      drag,
    });
    sizeMarkers();
    addEventListener("resize", () => { if (root.isConnected) sizeMarkers(); });
    svg.addEventListener("click", (e) => {
      if (drag.moved) return;
      const target = e.target.closest?.("[data-region], [data-iso]");
      if (!target) return;
      if (target.dataset.region) chooseRegion(REGIONS.find((r) => r.slug === target.dataset.region));
      else chooseIso(target.dataset.iso);
    });
    svg.addEventListener("keydown", (e) => {
      const dot = e.target.closest?.(".sm");
      if (dot && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); chooseIso(dot.dataset.iso); }
    });
    $("#amb-zoom-in").addEventListener("click", () => gestures.zoomBy(1.6));
    $("#amb-zoom-out").addEventListener("click", () => gestures.zoomBy(1 / 1.6));
    $("#amb-zoom-reset").addEventListener("click", () => showView(FULL.slice()));
  }
  mountBadges(root);
  // The dashed outline of the zoom extent of the chosen place (it shows where Palau or Bergen sits when the place has no outline).
  const zoomBox = svg?.querySelector(".zoom-box");
  function showZoomBox(place) {
    if (!zoomBox) return;
    if (!place) { zoomBox.style.display = "none"; return; }
    const [x0, y0, x1, y1] = placeExtent(place.geom, place.iso);
    zoomBox.setAttribute("d", `M${x0} ${y0}H${x1}V${y1}H${x0}Z`);
    zoomBox.style.display = "";
  }
  const paintSelection = (region) => {
    svg?.querySelectorAll(".sel").forEach((el) => el.classList.remove("sel"));
    if (!region || !svg) return;
    if (region.subdivision_names?.length) svg.querySelector(`[data-region="${region.slug}"]`)?.classList.add("sel");
    else region.country_codes.forEach((iso) => svg.querySelectorAll(`[data-iso="${iso}"]`).forEach((el) => el.classList.add("sel")));
  };

  // ---- selection: panel, zoom, status ----------------------------------------------------------
  const panel = $("#amb-panel");
  const status = $("#amb-search-status");
  let selectedPlace = null;
  function choose(place, region) {
    selectedPlace = place;
    paintSelection(region);
    if (place && FULL) showView(placeView(place.geom, place.iso, aspect(), FULL));
    showZoomBox(place);
    panel.innerHTML = region
      ? regionPanelHTML(region)
      : placePanelHTML(place, REGIONS.filter((r) => (r.country_codes || []).includes(place.iso) && r.subdivision_names?.length));
    if (status) status.textContent = `Showing ${place.name}${region ? ", open to ambassadors" : ", not open yet"}.`;
  }
  function chooseRegion(region) {
    if (!region) return;
    choose(placeFor(region), region);
  }
  function chooseIso(iso) {
    const region = countryRegion(iso, REGIONS);
    if (region) return chooseRegion(region);
    const place = placeByIso.get(iso);
    if (place) choose(place, null);
  }
  panel.addEventListener("click", (e) => {
    const check = e.target.closest("[data-check]");
    if (check) {
      e.preventDefault();
      setCheckPlace(placeFor(REGIONS.find((r) => r.slug === check.dataset.check)));
      $("#can-i-join").scrollIntoView({block: "start"});
      $("#amb-check-q").focus({preventScroll: true});
      return;
    }
    const region = e.target.closest("[data-region]");
    if (region) chooseRegion(REGIONS.find((r) => r.slug === region.dataset.region));
  });

  // ---- place search ----------------------------------------------------------------------------
  const placeSub = (r) => (r.kind === "country" ? "Country" : `${KIND_LABEL[r.kind]}, ${r.parent}`);
  mountPlaceSearch($("#amb-search"), {
    id: "amb-q",
    rows: PLACE_ROWS,
    sub: placeSub,
    placeholder: "Try Palau, Koror, Bergen or Alameda County",
    onPick: (r) => {
      const region = regionForPlace(r, REGIONS);
      choose(r, region);
    },
  });

  // ---- table alternative -----------------------------------------------------------------------
  $("#amb-table-body").innerHTML = REGIONS.map((r) =>
    `<tr><th scope="row">${esc(r.name)}</th><td>${STATUS_OPEN}</td><td>None confirmed yet</td><td><a class="link" href="#can-i-join" data-check="${esc(r.slug)}">Check if you can join</a></td></tr>`).join("");
  const toggle = $("#amb-table-toggle");
  toggle.addEventListener("click", () => {
    const wrap = $("#amb-table-wrap");
    wrap.hidden = !wrap.hidden;
    toggle.setAttribute("aria-expanded", String(!wrap.hidden));
  });
  $("#amb-table-body").addEventListener("click", (e) => {
    const check = e.target.closest("[data-check]");
    if (check) { e.preventDefault(); setCheckPlace(placeFor(REGIONS.find((r) => r.slug === check.dataset.check))); $("#can-i-join").scrollIntoView({block: "start"}); }
  });

  // ---- can I join? -----------------------------------------------------------------------------
  let checkPlace = null;
  const placeInput = mountPlaceSearch($("#amb-check-place"), {
    id: "amb-check-place-search",
    rows: PLACE_ROWS,
    sub: placeSub,
    placeholder: "Any place",
    onPick: (r) => setCheckPlace(r),
  });
  function setCheckPlace(place) {
    checkPlace = place || null;
    placeInput.value = checkPlace ? checkPlace.name : "";
    runCheck();
  }
  const q = $("#amb-check-q"), list = $("#amb-check-list"), result = $("#amb-check-result");
  let options = [], active = -1;
  const checkRegion = () => regionForPlace(checkPlace, REGIONS);
  function paintOptions() {
    list.innerHTML = options.map((o, i) =>
      `<div role="option" id="amb-check-o${i}" data-i="${i}" aria-selected="${i === active}">${esc(o.institution.name)}<small>${esc(o.institution.type)}, ${esc(o.region.name)}</small></div>`).join("");
    list.hidden = !options.length;
    q.setAttribute("aria-expanded", String(!!options.length));
    q.setAttribute("aria-activedescendant", active >= 0 ? `amb-check-o${active}` : "");
  }
  function pickOption(i) {
    if (!options[i]) return;
    q.value = options[i].institution.name;
    options = []; active = -1; paintOptions();
    runCheck();
  }
  q.addEventListener("input", () => {
    options = q.value.includes("@") ? [] : suggestInstitutions(q.value, institutionPool(REGIONS, checkRegion()?.slug ?? null));
    active = options.length ? 0 : -1;
    paintOptions();
  });
  q.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!options.length) return;
      e.preventDefault();
      active = (active + (e.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
      paintOptions();
    } else if (e.key === "Enter" && active >= 0 && options.length) {
      e.preventDefault();
      pickOption(active);
    } else if (e.key === "Escape") {
      options = []; paintOptions();
    }
  });
  list.addEventListener("mousedown", (e) => {
    const o = e.target.closest("[data-i]");
    if (o) { e.preventDefault(); pickOption(+o.dataset.i); }
  });
  function runCheck() {
    if (checkPlace && !checkRegion()) {
      result.innerHTML = `<b>No ambassador region is open for ${esc(checkPlace.name)} yet</b>Email <span class="addr">${EMAIL_ADDRESS}</span> and tell us about this place.`;
      result.dataset.state = "no";
      result.hidden = false;
      return;
    }
    const state = checkEligibility(q.value, REGIONS, checkRegion()?.slug ?? null);
    if (state.state === "choose") {
      options = state.options;
      active = 0;
      paintOptions();
    }
    result.innerHTML = resultHTML(state, checkPlace, REGIONS);
    result.dataset.state = state.state === "eligible" ? "yes" : state.state === "empty" ? "" : "no";
    result.hidden = state.state === "empty" && !checkPlace;
  }
  $("#amb-check-form").addEventListener("submit", (e) => {
    e.preventDefault();
    options = []; paintOptions();
    runCheck();
  });
}
