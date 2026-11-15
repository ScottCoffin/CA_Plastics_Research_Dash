---
title: Overview
---

<link rel="stylesheet" href="./components/overview.css">

<div class="atlas-overview">
  <section class="atlas-hero" aria-labelledby="atlas-overview-title">
    <div class="atlas-hero__motif" aria-hidden="true"></div>
    <div class="atlas-hero__content">
      <p class="atlas-hero__eyebrow">California · 32.5° to 42° N · Plastics research since 1950</p>
      <h1 class="atlas-hero__title" id="atlas-overview-title">CA Plastics Research Atlas</h1>
      <p class="atlas-hero__lead">A transparent starting point for finding plastic-related research connected to California.</p>
      <form class="atlas-hero__search" data-atlas-expert-search action="./experts" method="get">
        <label class="atlas-search">
          <span class="visually-hidden">Search experts</span>
          <span class="atlas-search__icon" data-atlas-icon="search"></span>
          <input class="atlas-input" type="search" name="search" placeholder="Search California researchers" autocomplete="off">
        </label>
        <button class="atlas-btn atlas-btn--primary" type="submit">Search experts</button>
      </form>
      <p class="atlas-hero__fresh" id="overview-refresh" aria-live="polite">Loading snapshot refresh time…</p>
    </div>
  </section>
  <div class="overview-body">
<section class="overview-stats" aria-label="Atlas snapshot statistics">
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
<section class="overview-section" id="start-here" aria-labelledby="start-here-title">
      <div class="overview-section__head">
        <p class="atlas-eyebrow">Quick routes</p>
        <h2 id="start-here-title">Start here</h2>
      </div>
      <ul class="atlas-task-list">
        <li><a href="./experts"><span class="atlas-task">
            <span class="tile-icon" data-atlas-icon="person"></span>
            <span class="atlas-task__body"><span class="atlas-task__title">Find a California researcher</span><span class="atlas-task__text">Search people and their research topics.</span></span>
            <span class="atlas-task__arrow" data-atlas-icon="arrow"></span>
          </span></a>
        </li>
        <li><a href="./funding"><span class="atlas-task">
            <span class="tile-icon" data-atlas-icon="coins"></span>
            <span class="atlas-task__body"><span class="atlas-task__title">See who is funded for plastics research</span><span class="atlas-task__text">Browse grants, awards, and open calls.</span></span>
            <span class="atlas-task__arrow" data-atlas-icon="arrow"></span>
          </span></a>
        </li>
        <li><a href="./monitoring"><span class="atlas-task">
            <span class="tile-icon" data-atlas-icon="drop"></span>
            <span class="atlas-task__body"><span class="atlas-task__title">Check plastic monitoring data</span><span class="atlas-task__text">Explore public samples from California waters.</span></span>
            <span class="atlas-task__arrow" data-atlas-icon="arrow"></span>
          </span></a>
        </li>
      </ul>
    </section>
<section class="overview-section" aria-labelledby="explore-atlas-title">
      <div class="overview-section__head">
        <p class="atlas-eyebrow">Browse by collection</p>
        <h2 id="explore-atlas-title">Explore the Atlas</h2>
      </div>
      <div class="atlas-entry-grid">
        <a class="atlas-entry" href="./experts">
          <span class="atlas-entry__icon" data-atlas-icon="person"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Experts</span><span class="atlas-entry__text">California researchers working on plastics, with topics and metrics.</span><span class="atlas-entry__meta" data-overview-count-group hidden><span data-overview-count="Authors" data-overview-suffix="authors"></span></span></span>
        </a>
        <a class="atlas-entry" href="./network">
          <span class="atlas-entry__icon" data-atlas-icon="network"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Collaboration network</span><span class="atlas-entry__text">See how researchers connect through shared work.</span></span>
        </a>
        <a class="atlas-entry" href="./institutions">
          <span class="atlas-entry__icon" data-atlas-icon="building"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Institutions</span><span class="atlas-entry__text">Explore California institutions and their research connections.</span><span class="atlas-entry__meta" data-overview-count-group hidden><span data-overview-count="Institutions" data-overview-suffix="institutions"></span><span class="atlas-entry__meta-separator" aria-hidden="true">·</span><span data-overview-count="California institutions" data-overview-suffix="California institutions"></span></span></span>
        </a>
        <a class="atlas-entry" href="./monitoring">
          <span class="atlas-entry__icon" data-atlas-icon="drop"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Monitoring</span><span class="atlas-entry__text">Browse public plastic monitoring samples from California waters.</span></span>
        </a>
        <a class="atlas-entry" href="./funding">
          <span class="atlas-entry__icon" data-atlas-icon="coins"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Funding</span><span class="atlas-entry__text">Explore grants, awards, and open funding calls.</span></span>
        </a>
        <a class="atlas-entry" href="./evidence">
          <span class="atlas-entry__icon" data-atlas-icon="grid"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Evidence map</span><span class="atlas-entry__text">Filter the published works snapshot by topic, year, and sector.</span><span class="atlas-entry__meta" data-overview-count-group hidden><span data-overview-count="Works" data-overview-suffix="works in snapshot"></span></span></span>
        </a>
        <a class="atlas-entry" href="./policy">
          <span class="atlas-entry__icon" data-atlas-icon="scale"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Policy</span><span class="atlas-entry__text">Follow the DTSC microplastics regulatory timeline.</span></span>
        </a>
        <a class="atlas-entry" href="./resources">
          <span class="atlas-entry__icon" data-atlas-icon="link"></span>
          <span class="atlas-entry__body"><span class="atlas-entry__title">Related resources</span><span class="atlas-entry__text">Find outside databases and tools on plastics.</span></span>
        </a>
      </div>
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
import {loadJson, aboutViewModel} from "./components/atlas.js";
const metadata = await loadJson("build_metadata.json");
const snapshot = aboutViewModel(metadata, null);

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
  const entries = counts.map((node) => ({node, value: stats.get(node.dataset.overviewCount)?.value}));
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
