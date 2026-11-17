---
title: Overview
---

<link rel="stylesheet" href="./components/overview.css">

<div class="atlas-overview">
  <section class="atlas-hero" aria-labelledby="atlas-overview-title">
    <div class="atlas-hero__motif" aria-hidden="true"></div>
    <div class="atlas-hero__content">
      <h1 class="atlas-hero__title" id="atlas-overview-title">CA Plastics Research Atlas</h1>
      <p class="atlas-hero__lead">A transparent starting point for finding plastic-related research connected to California.</p>
      <form class="atlas-hero__search" data-atlas-site-search action="./search" method="get" role="search">
        <label class="atlas-search">
          <span class="visually-hidden">Search the Atlas</span>
          <span class="atlas-search__icon" data-atlas-icon="search"></span>
          <input class="atlas-input" type="search" name="q" placeholder="Search experts, institutions, topics, funders…" autocomplete="off">
        </label>
        <button class="atlas-btn atlas-btn--primary" type="submit">Search</button>
      </form>
      <p class="atlas-hero__fresh" id="overview-refresh" aria-live="polite">Loading snapshot refresh time…</p>
    </div>
  </section>
  <div class="overview-body">
<section class="overview-stats overview-band overview-band--sunken" aria-label="Atlas snapshot statistics">
      <dl class="atlas-kpis" id="overview-stats" aria-busy="true">
        <div class="atlas-kpi atlas-kpi--loading" aria-hidden="true">
          <dt class="atlas-kpi__label">Authors</dt><dd class="atlas-kpi__value">&nbsp;</dd><dd class="stat-note">&nbsp;</dd>
        </div>
        <div class="atlas-kpi atlas-kpi--loading" aria-hidden="true">
          <dt class="atlas-kpi__label">Works</dt><dd class="atlas-kpi__value">&nbsp;</dd><dd class="stat-note">&nbsp;</dd>
        </div>
        <div class="atlas-kpi atlas-kpi--loading" aria-hidden="true">
          <dt class="atlas-kpi__label">Institutions</dt><dd class="atlas-kpi__value">&nbsp;</dd><dd class="stat-note">&nbsp;</dd>
        </div>
        <div class="atlas-kpi atlas-kpi--loading" aria-hidden="true">
          <dt class="atlas-kpi__label">California institutions</dt><dd class="atlas-kpi__value">&nbsp;</dd><dd class="stat-note">&nbsp;</dd>
        </div>
      </dl>
    </section>
<section class="overview-section overview-band overview-band--surface" id="start-here" aria-labelledby="start-here-title">
      <div class="overview-section__head">
        <h2 id="start-here-title">Start here</h2>
      </div>
      <ul class="atlas-task-list">
        <li><a href="./experts"><span class="atlas-task atlas-task--experts">
            <span class="tile-icon" data-atlas-icon="person"></span>
            <span class="atlas-task__body"><span class="atlas-task__title">Find a California researcher</span></span>
            <span class="atlas-task__arrow" data-atlas-icon="arrow"></span>
          </span></a>
        </li>
        <li><a href="./funding"><span class="atlas-task atlas-task--funding">
            <span class="tile-icon" data-atlas-icon="coins"></span>
            <span class="atlas-task__body"><span class="atlas-task__title">See plastics research funding</span></span>
            <span class="atlas-task__arrow" data-atlas-icon="arrow"></span>
          </span></a>
        </li>
        <li><a href="./monitoring"><span class="atlas-task atlas-task--monitoring">
            <span class="tile-icon" data-atlas-icon="drop"></span>
            <span class="atlas-task__body"><span class="atlas-task__title">Check monitoring data</span></span>
            <span class="atlas-task__arrow" data-atlas-icon="arrow"></span>
          </span></a>
        </li>
      </ul>
    </section>
<section class="overview-section overview-band overview-band--sunken" aria-labelledby="explore-atlas-title">
      <div class="overview-section__head">
        <p class="atlas-eyebrow">Browse by collection</p>
        <h2 id="explore-atlas-title">Explore the Atlas</h2>
      </div>
      <div class="atlas-entry-grid">
        <a class="atlas-entry" href="./experts">
          <span class="atlas-entry__icon" data-atlas-icon="person"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Experts</span><span class="atlas-entry__text">California researchers, topics and metrics.</span><span class="atlas-entry__meta" data-overview-count-group hidden><span data-overview-count="Authors" data-overview-suffix="authors"></span></span></span>
        </a>
        <a class="atlas-entry" href="./network">
          <span class="atlas-entry__icon" data-atlas-icon="network"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Collaboration network</span><span class="atlas-entry__text">How researchers connect through shared work.</span><span class="atlas-entry__meta" data-overview-count-group hidden><span data-overview-count="Network experts" data-overview-suffix="experts"></span><span class="atlas-entry__meta-separator" aria-hidden="true">·</span><span data-overview-count="Network links" data-overview-suffix="links"></span></span></span>
        </a>
        <a class="atlas-entry" href="./institutions">
          <span class="atlas-entry__icon" data-atlas-icon="building"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Institutions</span><span class="atlas-entry__text">California institutions and research connections.</span><span class="atlas-entry__meta" data-overview-count-group hidden><span data-overview-count="Institutions" data-overview-suffix="institutions"></span><span class="atlas-entry__meta-separator" aria-hidden="true">·</span><span data-overview-count="California institutions" data-overview-suffix="California institutions"></span></span></span>
        </a>
        <a class="atlas-entry" href="./monitoring">
          <span class="atlas-entry__icon" data-atlas-icon="drop"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Monitoring</span><span class="atlas-entry__text">Public samples from California waters.</span><span class="atlas-entry__meta" data-overview-count-group hidden><span data-overview-count="Monitoring samples" data-overview-suffix="samples"></span><span class="atlas-entry__meta-separator" aria-hidden="true">·</span><span data-overview-count="Monitoring sources" data-overview-suffix="sources"></span></span></span>
        </a>
        <a class="atlas-entry" href="./funding">
          <span class="atlas-entry__icon" data-atlas-icon="coins"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Funding</span><span class="atlas-entry__text">Grants, awards and open calls.</span><span class="atlas-entry__meta" data-overview-count-group hidden><span data-overview-count="Awards" data-overview-suffix="plastic-related awards"></span></span></span>
        </a>
        <a class="atlas-entry" href="./evidence">
          <span class="atlas-entry__icon" data-atlas-icon="grid"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Evidence map</span><span class="atlas-entry__text">Filter works by topic, year, sector.</span><span class="atlas-entry__meta" data-overview-count-group hidden><span data-overview-count="Plastic-related works" data-overview-suffix="plastic-related works"></span></span></span>
        </a>
        <a class="atlas-entry" href="./policy">
          <span class="atlas-entry__icon" data-atlas-icon="scale"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Policy</span><span class="atlas-entry__text">Follow the DTSC microplastics timeline.</span></span>
        </a>
        <a class="atlas-entry" href="./resources">
          <span class="atlas-entry__icon" data-atlas-icon="link"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Related resources</span><span class="atlas-entry__text">Outside databases and tools on plastics.</span></span>
        </a>
      </div>
    </section>
<section class="overview-section overview-band overview-band--surface" aria-labelledby="how-it-works">
      <div class="overview-section__head">
        <h2 id="how-it-works">How it works</h2>
      </div>
      <ol class="overview-steps">
        <li class="overview-step">
          <span class="overview-step__icon" data-atlas-icon="download"></span>
          <h3>Daily ingest</h3>
          <p class="overview-step__when">GitHub Actions, daily at 10:17 UTC</p>
          <p class="overview-step__text">Fetches new plastic-related works from OpenAlex, normalises authors and institutions, applies relevance labels and reviewed overrides, rebuilds expert metrics, the collaboration network and the search index.</p>
        </li>
        <li class="overview-step">
          <span class="overview-step__icon" data-atlas-icon="tools"></span>
          <h3>Build and deploy</h3>
          <p class="overview-step__when">Daily at 10:15 UTC and on every change</p>
          <p class="overview-step__text">Rebuilds open funding calls, the status page and the feed, builds this Observable Framework site and publishes it on GitHub Pages.</p>
        </li>
        <li class="overview-step">
          <span class="overview-step__icon" data-atlas-icon="search"></span>
          <h3>Weekly source watch</h3>
          <p class="overview-step__when">Mondays at 10:31 UTC</p>
          <p class="overview-step__text">Checks CEDEN for new microplastics monitoring data and verifies outside links.</p>
        </li>
        <li class="overview-step">
          <span class="overview-step__icon" data-atlas-icon="alert"></span>
          <h3>Watchdog</h3>
          <p class="overview-step__when">Daily at 11:47 UTC, plus a monthly keepalive</p>
          <p class="overview-step__text">Flags scheduled jobs that fail or stall.</p>
        </li>
        <li class="overview-step overview-step--note">
          <span class="overview-step__icon" data-atlas-icon="book"></span>
          <h3>Static by design</h3>
          <p class="overview-step__text">No server or database; data ship as versioned JSON and Parquet files; code and methods are open on GitHub. <a href="./about">Read the methods</a></p>
        </li>
      </ol>
    </section>
  </div>
</div>

```js
import {icon} from "./components/shared/icons.js";
for (const host of document.querySelectorAll("[data-atlas-icon]")) {
  host.replaceChildren(icon(host.dataset.atlasIcon));
}
```

```js
import {loadJson, aboutViewModel, formatCount} from "./components/atlas.js";
const metadata = await loadJson("build_metadata.json");
const snapshot = aboutViewModel(metadata, null);

// VD-13: entry-card counts beyond the About stats. Each reads one key of build_metadata.json
// counts, formatted as the Atlas formats every count; a missing key reads "Unavailable", which
// keeps its card group hidden.
const metadataCounts = metadata?.counts ?? {};
const cardCounts = new Map(
  [
    ["Awards", "awards"],
    ["Monitoring samples", "monitoring_samples"],
    ["Monitoring sources", "monitoring_sources"],
    ["Network experts", "network_experts"],
    ["Network links", "network_links"],
    ["Plastic-related works", "plastic_works"],
  ].map(([label, key]) => [label, formatCount(metadataCounts[key])]),
);

const statIcons = new Map([
  ["Authors", "person"],
  ["Works", "book"],
  ["Institutions", "network"],
  ["California institutions", "building"],
]);
const statLabels = [...statIcons.keys()];
const stats = new Map(snapshot.stats.map(({label, value, note}) => [label, {value, note}]));
const statsHost = document.querySelector("#overview-stats");
const statTiles = statLabels.map((label) => {
  const stat = stats.get(label);
  const tile = document.createElement("div");
  tile.className = "atlas-kpi";
  const labelNode = document.createElement("dt");
  labelNode.className = "atlas-kpi__label";
  labelNode.append(icon(statIcons.get(label)), document.createTextNode(label));
  const valueNode = document.createElement("dd");
  valueNode.className = "atlas-kpi__value";
  valueNode.textContent = stat?.value ?? "Unavailable";
  const noteNode = document.createElement("dd");
  noteNode.className = "atlas-kpi__note stat-note";
  noteNode.textContent = stat?.note ?? "Definition unavailable.";
  tile.append(labelNode, valueNode, noteNode);
  return tile;
});
statsHost.replaceChildren(...statTiles);
statsHost.setAttribute("aria-busy", "false");

for (const group of document.querySelectorAll("[data-overview-count-group]")) {
  const counts = [...group.querySelectorAll("[data-overview-count]")];
  const entries = counts.map((node) => ({node, value: cardCounts.get(node.dataset.overviewCount) ?? stats.get(node.dataset.overviewCount)?.value}));
  if (!entries.length || entries.some(({value}) => !value || value === "Unavailable")) continue;
  for (const {node, value} of entries) {
    node.textContent = `${value} ${node.dataset.overviewSuffix}`;
  }
  group.hidden = false;
}

const refreshHost = document.querySelector("#overview-refresh");
if (snapshot.refreshDisplay && snapshot.refreshIso) {
  refreshHost.replaceChildren(html`Last refresh: <time datetime=${snapshot.refreshIso}>${snapshot.refreshDisplay}</time>`);
} else {
  refreshHost.textContent = snapshot.refreshText;
}
```
