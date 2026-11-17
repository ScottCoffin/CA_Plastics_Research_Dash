---
title: Overview
---

<link rel="stylesheet" href="./components/overview.css">

<div class="atlas-overview">
<section class="overview-hero" aria-labelledby="overview-title">
<div class="overview-hero__grid">
<div class="overview-hero__copy">
<h1 class="overview-title" id="overview-title">California plastics research, in four parts.</h1>
<p class="overview-lead">Who studies plastics in California, what is monitored, what is funded, and what has been published. Rebuilt from open sources every day.</p>
<ul class="overview-doors" aria-label="Start here">
<li><a class="overview-door" data-plane="people" href="./experts" style="--c: var(--atlas-task-people)"><span class="overview-door__swatch" aria-hidden="true"></span><strong class="overview-door__task">Find a researcher</strong><small class="overview-door__count" data-count-group><span data-count="authors" data-suffix=" authors"></span></small></a></li>
<li><a class="overview-door" data-plane="water" href="./monitoring" style="--c: var(--atlas-task-water)"><span class="overview-door__swatch" aria-hidden="true"></span><strong class="overview-door__task">Check monitoring data</strong><small class="overview-door__count" data-count-group><span data-count="monitoring_samples" data-suffix=" samples"></span></small></a></li>
<li><a class="overview-door" data-plane="money" href="./funding" style="--c: var(--atlas-task-money)"><span class="overview-door__swatch" aria-hidden="true"></span><strong class="overview-door__task">See funding</strong><small class="overview-door__count" data-count-group><span data-count="awards" data-suffix=" awards"></span></small></a></li>
<li><a class="overview-door" data-plane="evidence" href="./evidence" style="--c: var(--atlas-task-evidence)"><span class="overview-door__swatch" aria-hidden="true"></span><strong class="overview-door__task">Explore the evidence</strong><small class="overview-door__count" data-count-group><span data-count="plastic_works" data-suffix=" works"></span></small></a></li>
</ul>
<form class="overview-search" action="./search" method="get" role="search" data-atlas-site-search>
<label class="visually-hidden" for="overview-q">Search the whole Atlas</label>
<p class="overview-caps" aria-hidden="true">Or search the whole Atlas</p>
<div class="overview-search__field"><input id="overview-q" type="search" name="q" placeholder="Experts, institutions, topics, funders" autocomplete="off"><button type="submit">Search</button></div>
</form>
</div>
<figure class="overview-figure" id="overview-figure" aria-label="California drawn from four planes: researchers, monitoring, funding and evidence">
<svg viewBox="-470 -575 1010 1090" role="group" aria-labelledby="overview-fig-title">
<title id="overview-fig-title">California in four colour planes, one for each part of the Atlas</title>
<defs>
<clipPath id="overview-ca"><path d="M469,474L492,458L469,407L486,379L488,336L523,299L501,280L478,221L0,-221L0,-553L-375,-553L-379,-528L-361,-490L-376,-416L-369,-427L-363,-425L-392,-381L-343,-313L-331,-212L-278,-160L-252,-121L-266,-137L-269,-110L-225,-90L-213,-128L-189,-115L-150,-127L-158,-115L-149,-121L-143,-122L-132,-116L-129,-111L-150,-112L-210,-112L-181,-51L-211,-67L-214,-90L-224,-59L-208,-13L-160,18L-157,31L-176,46L-169,77L-79,173L-78,196L-57,206L-57,269L-40,283L39,286L77,321L132,329L141,360L167,360L221,405L256,494L469,474Z"/></clipPath>
</defs>
<g class="overview-piece" data-plane="water"><g clip-path="url(#overview-ca)"><a href="./monitoring" tabindex="-1" aria-hidden="true"><polygon class="overview-plane" data-plane="water" points="-470,-575 560,-575 560,-150 -470,-150"/></a></g></g>
<g class="overview-piece" data-plane="people"><g clip-path="url(#overview-ca)"><a href="./experts" tabindex="-1" aria-hidden="true"><polygon class="overview-plane" data-plane="people" points="-470,-150 70,-150 -70,205 -470,205"/></a></g><path d="M-330,70 A62,62 0 0 0 -206,70 Z" style="fill: var(--atlas-vermilion)" aria-hidden="true"/></g>
<g class="overview-piece" data-plane="money"><g clip-path="url(#overview-ca)"><a href="./funding" tabindex="-1" aria-hidden="true"><polygon class="overview-plane" data-plane="money" points="70,-150 560,-150 560,250 -70,205"/></a></g></g>
<g class="overview-piece" data-plane="evidence"><g clip-path="url(#overview-ca)"><a href="./evidence" tabindex="-1" aria-hidden="true"><polygon class="overview-plane" data-plane="evidence" points="-470,205 -70,205 560,250 560,520 -470,520"/></a></g></g>
</svg>
<figcaption class="overview-caps">32.5° to 42° N</figcaption>
</figure>
</div>
</section>
<section class="overview-band" id="people" aria-labelledby="people-h" style="--c: var(--atlas-task-people)">
<div class="overview-band__grid">
<div class="overview-band__swatch" aria-hidden="true"><svg viewBox="0 0 300 220" preserveAspectRatio="xMidYMid slice" focusable="false"><rect x="150" y="0" width="150" height="220" style="fill: var(--atlas-indigo)"/><path d="M95,80 A55,55 0 0 0 205,80 Z" style="fill: var(--atlas-page)"/><circle cx="150" cy="190" r="70" style="fill: var(--atlas-gold)"/></svg></div>
<div>
<h2 class="overview-band__title" id="people-h">Find a researcher</h2>
<p class="overview-band__text">Search California-affiliated authors by topic, institution and output, and see who publishes with whom. Profiles are built from OpenAlex and ROR records.</p>
<ul class="overview-facts">
<li data-count-group><b data-count="authors"></b><span>authors</span></li>
<li data-count-group><b data-count="network_experts"></b><span>experts in the network, <span data-count="network_links"></span> links</span></li>
<li data-count-group><b data-count="california_institutions"></b><span>California institutions</span></li>
</ul>
<div class="overview-go"><a href="./experts">Experts</a><a href="./network">Collaboration network</a><a href="./institutions">Institutions</a></div>
</div>
</div>
</section>
<section class="overview-band" id="water" aria-labelledby="water-h" style="--c: var(--atlas-task-water)">
<div class="overview-band__grid">
<div class="overview-band__swatch" aria-hidden="true"><svg viewBox="0 0 300 220" preserveAspectRatio="xMidYMid slice" focusable="false"><rect y="120" width="300" height="100" style="fill: var(--atlas-page)"/><path d="M60,120 A90,90 0 0 1 240,120 Z" style="fill: var(--atlas-vermilion)"/><rect x="0" y="160" width="300" height="20" style="fill: var(--atlas-indigo)"/></svg></div>
<div>
<h2 class="overview-band__title" id="water-h">Check monitoring data</h2>
<p class="overview-band__text">Browse public plastic samples from California waters on a map, with each source's licence and citation. Samples describe individual sites; they do not establish statewide coverage.</p>
<ul class="overview-facts">
<li data-count-group><b data-count="monitoring_samples"></b><span>sample observations</span></li>
<li data-count-group><b data-count="monitoring_sources"></b><span>verified sources</span></li>
</ul>
<div class="overview-go"><a href="./monitoring">Monitoring map</a></div>
</div>
</div>
</section>
<section class="overview-band" id="money" aria-labelledby="money-h" style="--c: var(--atlas-task-money)">
<div class="overview-band__grid">
<div class="overview-band__swatch" aria-hidden="true"><svg viewBox="0 0 300 220" preserveAspectRatio="xMidYMid slice" focusable="false"><rect x="40" y="40" width="90" height="90" style="fill: var(--atlas-ink)"/><circle cx="200" cy="85" r="45" style="fill: var(--atlas-page)"/><polygon points="90,220 170,130 250,220" style="fill: var(--atlas-vermilion)"/></svg></div>
<div>
<h2 class="overview-band__title" id="money-h">See funding</h2>
<p class="overview-band__text">Browse plastic-related grants and awards connected to California, and open funding calls, drawn from public grant databases.</p>
<ul class="overview-facts">
<li data-count-group><b data-count="awards"></b><span>plastic-related awards</span></li>
</ul>
<div class="overview-go"><a href="./funding">Funding</a></div>
</div>
</div>
</section>
<section class="overview-band" id="evidence" aria-labelledby="evidence-h" style="--c: var(--atlas-task-evidence); --c-arrow: var(--atlas-gold)">
<div class="overview-band__grid">
<div class="overview-band__swatch" aria-hidden="true"><svg viewBox="0 0 300 220" preserveAspectRatio="xMidYMid slice" focusable="false"><rect x="30" y="30" width="70" height="70" style="fill: var(--atlas-page)"/><rect x="115" y="30" width="70" height="70" style="fill: var(--atlas-gold)"/><rect x="200" y="30" width="70" height="70" style="fill: var(--atlas-page)"/><rect x="30" y="115" width="70" height="70" style="fill: var(--atlas-indigo)"/><rect x="115" y="115" width="70" height="70" style="fill: var(--atlas-page)"/><rect x="200" y="115" width="70" height="70" style="fill: var(--atlas-vermilion)"/></svg></div>
<div>
<h2 class="overview-band__title" id="evidence-h">Explore the evidence</h2>
<p class="overview-band__text">Filter published plastic-related works by topic, year and sector, see trends and a topic heatmap, and follow the DTSC microplastics regulatory timeline. Topic tags come from keyword rules and are provisional.</p>
<ul class="overview-facts">
<li data-count-group><b data-count="plastic_works"></b><span>plastic-related works</span></li>
</ul>
<div class="overview-go"><a href="./evidence">Evidence map</a><a href="./policy">Policy</a><a href="./resources">Related resources</a></div>
</div>
</div>
</section>
<section class="overview-engine" aria-labelledby="overview-engine-title">
<div class="overview-engine__head">
<p class="overview-caps">Behind the pages</p>
<h2 class="overview-engine__title" id="overview-engine-title">A living evidence map of California plastics research</h2>
<p class="overview-engine__lead">The Atlas is rebuilt every morning from open catalogues. It tracks plastics and microplastics research with at least one California-affiliated author: journal articles and reviews, conference papers and abstracts, preprints, theses and dissertations, book chapters, reports and datasets. It also tracks the researchers, institutions, monitoring data and funding around that work.</p>
<p class="overview-engine__types" data-count-group hidden><span data-count="type_summary"></span></p>
</div>
<ol class="overview-pipeline">
<li class="overview-pipe" style="--c: var(--atlas-task-water)">
<span class="overview-pipe__n" aria-hidden="true">1</span>
<h3>Gather</h3>
<p>A reviewed search of titles and abstracts runs against <a href="https://openalex.org/" target="_blank" rel="noreferrer">OpenAlex</a>, an open index of scholarly works, authors and institutions. Records found through researchers' ORCID profiles, the University of California's eScholarship repository and DataCite are added, and recall is checked against Europe PMC.</p>
<p class="overview-pipe__also">Funding: NIH RePORTER, NSF awards, USAspending.gov, California Sea Grant, the Ocean Protection Council and State Water Board grants. Monitoring: rights-cleared sample datasets.</p>
</li>
<li class="overview-pipe" style="--c: var(--atlas-task-people)">
<span class="overview-pipe__n" aria-hidden="true">2</span>
<h3>Screen</h3>
<p>A work stays only if an author is tied to California: by a registered California institution, by the affiliation text itself, or by the author's recent California record. Keyword rules then decide whether plastic is central to the work. Uncertain cases get a second, language-model read, and the maintainer's review decisions override both.</p>
</li>
<li class="overview-pipe" style="--c: var(--atlas-task-money)">
<span class="overview-pipe__n" aria-hidden="true">3</span>
<h3>Classify and link</h3>
<p>Keyword rules tag each work with topics (such as monitoring, toxicity, wastewater or human health) and a study type; these tags are provisional. Authors are matched to institutions through the ROR registry, duplicate profiles are merged, and co-authorship becomes the collaboration network.</p>
</li>
<li class="overview-pipe" style="--c: var(--atlas-task-evidence)">
<span class="overview-pipe__n" aria-hidden="true">4</span>
<h3>Publish</h3>
<p>The build writes plain JSON and Parquet files and redeploys this static site. Nothing in your browser queries a server. Releases are archived on Zenodo with a citable DOI, and the <a href="./about#how-works-are-screened">About page</a> shows the full screening flow.</p>
</li>
</ol>
</section>
<section class="overview-clock" aria-labelledby="overview-clock-title">
<div class="overview-clock__inner">
<h2 class="overview-clock__title" id="overview-clock-title">How the Atlas stays current</h2>
<p class="overview-clock__text">Scheduled GitHub Actions jobs run in a two-hour window each morning, UTC (about 2 to 4 a.m. in California in winter). Times below are drawn to scale.</p>
<div class="overview-chart" tabindex="0" role="region" aria-label="Scheduled jobs, drawn to scale"><div class="overview-chart__frame" id="overview-chart"></div></div>
<div class="overview-notes">
<div><h3>Static by design</h3><p>No server or database. Data ship as versioned JSON and Parquet files beside the pages.</p></div>
<div><h3>Open methods</h3><p>Code, queries and decisions are public on GitHub. <a href="./about">Read the methods</a>. Terms are defined in the <a href="./glossary">glossary</a>.</p></div>
<div><h3>Every number has a source</h3><p>Counts on this page come from the latest Atlas snapshot.</p><p class="stat-note" data-stat-note="Authors" hidden></p><p class="stat-note" data-stat-note="California institutions" hidden></p><p class="overview-refresh" id="overview-refresh" aria-live="polite">Loading snapshot refresh time…</p></div>
</div>
</div>
</section>
</div>

```js
import {loadJson, aboutViewModel, formatCount} from "./components/atlas.js";
const metadata = await loadJson("build_metadata.json");
const snapshot = aboutViewModel(metadata, null);

// VD-25b: live counts. A data-count placeholder reads one value: the About stats for authors and
// California institutions, metadata.counts for the rest. A group with any missing value is hidden
// (never "Unavailable"). Visible groups reserve their height in CSS, so filling them does not shift the page.
const statRows = new Map(snapshot.stats.map((row) => [row.label, row]));
const metadataCounts = metadata?.counts ?? {};
const countText = (text) => (text && text !== "Unavailable" ? text : null);
const counts = new Map([
  ["authors", countText(statRows.get("Authors")?.value)],
  ["california_institutions", countText(statRows.get("California institutions")?.value)],
  ...["awards", "monitoring_samples", "monitoring_sources", "network_experts", "network_links", "plastic_works"]
    .map((key) => [key, countText(formatCount(metadataCounts[key]))]),
  ["type_summary", typeSummary(metadata?.flow?.by_type)],
]);

// Living output mix, e.g. "Now: 1,398 articles · 109 reviews · …". Hidden until the export carries flow.by_type.
function typeSummary(byType) {
  const names = {article: "articles", review: "reviews", "conference-paper": "conference papers", preprint: "preprints",
    "book-chapter": "book chapters", "conference-abstract": "conference abstracts", dataset: "datasets",
    dissertation: "theses and dissertations", report: "reports", book: "books"};
  const rows = Object.entries(byType ?? {}).filter(([type, n]) => names[type] && n > 0).sort((a, b) => b[1] - a[1]);
  return rows.length ? `Now: ${rows.map(([type, n]) => `${formatCount(n)} ${names[type]}`).join(" · ")}.` : null;
}
for (const group of document.querySelectorAll("[data-count-group]")) {
  const pieces = [...group.querySelectorAll("[data-count]")];
  const values = pieces.map((node) => counts.get(node.dataset.count) ?? null);
  const ready = values.every(Boolean);
  group.hidden = !ready;
  if (ready) pieces.forEach((node, i) => { node.textContent = `${values[i]}${node.dataset.suffix ?? ""}`; });
}
for (const note of document.querySelectorAll("[data-stat-note]")) {
  const row = statRows.get(note.dataset.statNote);
  const shown = Boolean(countText(row?.value));
  note.textContent = shown ? row.note : "";
  note.hidden = !shown;
}

const refreshHost = document.querySelector("#overview-refresh");
if (snapshot.refreshDisplay && snapshot.refreshIso) {
  refreshHost.replaceChildren(html`Last refresh: <time datetime=${snapshot.refreshIso}>${snapshot.refreshDisplay}</time>`);
} else {
  refreshHost.textContent = snapshot.refreshText;
}
```

```js
(() => {
  // Row and plane light each other (the signature interaction); focus lights the same pair.
  const figure = document.getElementById("overview-figure");
  const doors = [...document.querySelectorAll(".overview-door")];
  const planes = [...document.querySelectorAll(".overview-plane")];
  const light = (key) => {
    figure.classList.toggle("has-lit", Boolean(key));
    planes.forEach((p) => p.classList.toggle("is-lit", p.dataset.plane === key));
    doors.forEach((d) => d.classList.toggle("is-lit", d.dataset.plane === key));
  };
  for (const el of [...doors, ...planes]) {
    el.addEventListener("mouseenter", () => light(el.dataset.plane));
    el.addEventListener("mouseleave", () => light(null));
    el.addEventListener("focus", () => light(el.dataset.plane));
    el.addEventListener("blur", () => light(null));
  }
})();
```

```js
(async () => {
  // VD-30: on every load (owner 2026-11-17) the four planes travel in from their own edges and spring into place
  // (a sampled spring on the Web Animations API, no library). The markup is the finished map; transforms
  // exist only while the intro runs.
  const figure = document.getElementById("overview-figure");
  const svg = figure?.querySelector("svg");
  const hero = figure?.closest(".overview-hero");
  const pieces = [...(figure?.querySelectorAll(".overview-piece") ?? [])];
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!svg || pieces.length !== 4 || reduced || !figure.getClientRects().length) return;

  // Each plane starts just outside the viewport on its own side: water from above, people from the left,
  // money from the right, evidence from below. Distances come from each plane's box at rest, in CSS px.
  const EDGE = 16;
  const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
  const unit = svg.getScreenCTM().a; // CSS px per SVG user unit (the viewBox scales uniformly)
  const outside = {
    water: (r) => [0, -(r.bottom + EDGE)],
    people: (r) => [-(r.right + EDGE), 0],
    money: (r) => [vw - r.left + EDGE, 0],
    evidence: (r) => [0, vh - r.top + EDGE],
  };
  const tilt = {water: -8, people: 7, money: -7, evidence: 8};
  const plan = pieces.map((piece) => {
    const [x, y] = outside[piece.dataset.plane](piece.getBoundingClientRect());
    return {piece, x: x / unit, y: y / unit, tilt: tilt[piece.dataset.plane]};
  });

  // Park every plane off the page before the first animation frame, so the finished map never flashes. Each plane
  // pivots on its own centre (fill-box), and rest() removes every trace of the intro.
  const rest = () => {
    for (const {piece} of plan) {
      piece.style.transform = "";
      piece.style.transformOrigin = "";
      piece.style.transformBox = "";
    }
    hero?.classList.remove("is-map-intro");
  };
  hero?.classList.add("is-map-intro");
  for (const {piece, x, y, tilt: deg} of plan) {
    piece.style.transformBox = "fill-box";
    piece.style.transformOrigin = "50% 50%";
    piece.style.transform = `translate(${x}px, ${y}px) rotate(${deg}deg)`;
  }

  // A press or a key during the intro finishes it at once.
  const ac = new AbortController();
  let controls = null;
  let cancelled = false;
  const finishNow = () => {
    if (controls) controls.forEach((control) => control.complete());
    else { cancelled = true; rest(); }
  };
  window.addEventListener("pointerdown", finishNow, {once: true, signal: ac.signal});
  window.addEventListener("keydown", finishNow, {once: true, signal: ac.signal});

  // The spring is sampled here and played with the browser's Web Animations API: no library download,
  // so the intro starts at once. Underdamped spring (damping ratio 0.55, natural frequency 10 rad/s):
  // about 12% overshoot, settled within 1.1 s. Pieces start 120 ms apart.
  const ZETA = 0.55, OMEGA = 10, DURATION = 1100, STEPS = 66, GAP = 120;
  const wd = OMEGA * Math.sqrt(1 - ZETA * ZETA);
  const remaining = (t) => Math.exp(-ZETA * OMEGA * t) * (Math.cos(wd * t) + (ZETA * OMEGA / wd) * Math.sin(wd * t));
  if (cancelled || typeof Element.prototype.animate !== "function") {
    ac.abort();
    rest();
    return;
  }
  controls = plan.map(({piece, x, y, tilt: deg}, i) => {
    const frames = [];
    for (let s = 0; s <= STEPS; s++) {
      const k = s === STEPS ? 0 : remaining((s / STEPS) * (DURATION / 1000));
      frames.push({transform: `translate(${x * k}px, ${y * k}px) rotate(${deg * k}deg)`});
    }
    return piece.animate(frames, {duration: DURATION, delay: i * GAP, easing: "linear", fill: "both"});
  });
  controls.forEach((animation) => { animation.complete = () => animation.finish(); });
  await Promise.allSettled(controls.map((animation) => animation.finished));
  controls.forEach((animation) => animation.cancel());
  ac.abort();
  rest();
})();
```

```js
(() => {
  // Schedule chart: 09:30 to 12:00 UTC on one linear scale, drawn to scale from the job times.
  const host = document.getElementById("overview-chart");
  const W = 1000, H = 260, L = 20, R = 20, t0 = 9 * 60 + 30, t1 = 12 * 60;
  const x = (m) => L + ((m - t0) / (t1 - t0)) * (W - L - R);
  const axisY = 150;
  const jobs = [
    {m: 9 * 60 + 42, label: "Keepalive", sub: "monthly, 1st", shape: "sq", c: "var(--atlas-line)", up: true},
    {m: 10 * 60 + 15, label: "Build and deploy", sub: "daily 10:15", shape: "sq", c: "var(--atlas-vermilion)", up: true, dx: -6},
    {m: 10 * 60 + 17, label: "Daily ingest from OpenAlex", sub: "daily 10:17", shape: "dot", c: "var(--atlas-gold)", up: false},
    {m: 10 * 60 + 31, label: "Source watch", sub: "Mondays 10:31", shape: "tri", c: "var(--atlas-map-water)", up: true, dx: 70},
    {m: 11 * 60 + 47, label: "Watchdog", sub: "daily 11:47", shape: "dot", c: "var(--atlas-on-brand)", up: false},
  ];
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="overview-chart-title"><title id="overview-chart-title">Scheduled jobs between 09:30 and 12:00 UTC</title>`;
  s += `<line x1="${L}" x2="${W - R}" y1="${axisY}" y2="${axisY}" style="stroke: var(--atlas-on-brand)" stroke-width="2"/>`;
  for (let m = t0; m <= t1; m += 15) {
    const major = m % 30 === 0;
    s += `<line x1="${x(m)}" x2="${x(m)}" y1="${axisY}" y2="${axisY + (major ? 12 : 6)}" style="stroke: var(--atlas-on-brand)"/>`;
    if (major) {
      const hh = String(Math.floor(m / 60)).padStart(2, "0"), mm = String(m % 60).padStart(2, "0");
      s += `<text x="${x(m)}" y="${axisY + 32}" text-anchor="middle" font-size="14" style="font-variant-numeric:tabular-nums">${hh}:${mm}</text>`;
    }
  }
  for (const j of jobs) {
    const cx = x(j.m), ly = j.up ? 40 : 238, my = axisY;
    const tx = cx + (j.dx || 0);
    s += `<line x1="${cx}" x2="${cx}" y1="${my}" y2="${j.up ? ly + 14 : ly - 34}" stroke-width="1.5" style="stroke: ${j.c}"/>`;
    if (j.shape === "sq") s += `<rect x="${cx - 8}" y="${my - 8}" width="16" height="16" style="fill: ${j.c}"/>`;
    else if (j.shape === "tri") s += `<polygon points="${cx},${my - 10} ${cx + 10},${my + 8} ${cx - 10},${my + 8}" style="fill: ${j.c}"/>`;
    else s += `<circle cx="${cx}" cy="${my}" r="9" style="fill: ${j.c}"/>`;
    const anchor = j.m > 11 * 60 ? "end" : "start";
    const ax = anchor === "end" ? cx + 4 : tx;
    s += `<text x="${ax}" y="${j.up ? ly - 6 : ly - 14}" font-size="16" font-weight="700" text-anchor="${anchor}">${j.label}</text>`;
    s += `<text x="${ax}" y="${j.up ? ly + 12 : ly + 4}" font-size="13" text-anchor="${anchor}" fill-opacity=".75">${j.sub}</text>`;
  }
  s += `</svg>`;
  host.innerHTML = s;
})();
```
