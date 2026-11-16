---
title: Evidence map
---

<link rel="stylesheet" href="./components/evidence.css">
<link rel="stylesheet" href="./components/v3_flow.css">
<link rel="stylesheet" href="./components/v4_trend.css">
<link rel="stylesheet" href="./components/ev_heatmap.css">
<link rel="stylesheet" href="./components/ev_table.css">

<header class="atlas-page-head">
  <p class="atlas-page-head__eyebrow">Data</p>
</header>

# Evidence map

<p class="atlas-page-head__lead">Explore the Atlas's plastic-related works with filters, trends, and a heatmap. Selections show matching publications below.</p>

<details class="atlas-disclosure ev-how-to">
  <summary>How to use this page</summary>
  <div class="atlas-disclosure__body">
    <p>Filter the Atlas's distinct works by words in the title, year range, topic, sector, work type, open access, and California leadership. The page lists plastic-related works only.</p>
    <p>The trend charts and heatmap follow the filters, and selecting heatmap cells narrows the publication table below. Click a topic, matrix, or period heading to select that whole row or column.</p>
  </div>
</details>

<div class="atlas-callout atlas-callout--dev ev-dev-callout" role="note">
  <p class="ev-notice">In development: a map of sampled locations and a review overlay will be added here. Topic and matrix tags come from keyword rules and are provisional.</p>
</div>

<div class="atlas-callout atlas-callout--info ev-info-callout" role="note">
  <p class="data-note ev-aux-note">The topic <strong>Plastic-associated chemicals</strong> (such as BPA, phthalates and 6PPD) is auxiliary. The Atlas searches for plastics terms, so it covers these chemical studies far less completely than studies of plastic particles and debris. <a href="./glossary#plastic-associated-chemicals">More about this topic</a>.</p>
</div>

<div id="evidence-root">
  <p id="evidence-status" class="result-count" role="status" aria-live="polite">Loading the evidence bundle…</p>
  <div class="ev-layout">
    <form id="evidence-filters" class="ev-filters" aria-label="Filter distinct works">
      <div class="ev-field"><label for="evidence-search">Search titles</label><input id="evidence-search" type="search" autocomplete="off" placeholder="Words in the title"></div>
      <div class="ev-years">
        <div class="ev-field"><label for="evidence-year-from">Year from</label><input id="evidence-year-from" type="number" inputmode="numeric" min="1900" max="2100" step="1"></div>
        <div class="ev-field"><label for="evidence-year-to">Year to</label><input id="evidence-year-to" type="number" inputmode="numeric" min="1900" max="2100" step="1"></div>
      </div>
      <div id="evidence-groups" class="ev-groups"></div>
      <div class="ev-actions"><button id="evidence-reset" type="button">Reset filters</button></div>
    </form>
    <div class="ev-main">
      <div class="ev-summary">
        <p id="evidence-count" class="ev-count-line" aria-live="polite"></p>
      </div>
      <div class="atlas-callout atlas-callout--caution ev-volume-callout" role="note"><p class="data-note volume-caption">Counts show how much has been published, not the strength or quality of the evidence.</p></div>
      <section class="ev-view atlas-chart" aria-labelledby="ev-v4-heading" hidden><div class="atlas-chart__head"><h2 id="ev-v4-heading">Trends</h2></div><div class="atlas-chart__body"><div id="ev-v4"></div></div></section>
      <section class="ev-view atlas-chart" aria-labelledby="ev-heatmap-heading" hidden><div class="atlas-chart__head"><h2 id="ev-heatmap-heading" tabindex="-1">Evidence heatmap</h2></div><div class="atlas-chart__body"><div id="ev-heatmap"></div></div></section>
    </div>
  </div>
  <section id="ev-recent" class="ev-recent atlas-callout atlas-callout--new" aria-label="New in the last 2 weeks" hidden></section>
  <section class="ev-view atlas-chart" aria-labelledby="ev-table-heading"><div class="atlas-chart__head"><h2 id="ev-table-heading" tabindex="-1">Publications</h2></div><div class="atlas-chart__body"><div id="ev-table-selection" class="ev-table-selection ev-table-root" role="status" aria-live="polite" hidden></div><div id="ev-table"><p class="result-count">Loading publications…</p></div></div></section>
  <details class="ev-view ev-flow-box"><summary id="ev-v3-heading">How works were selected (pipeline flow)</summary><div id="ev-v3"></div></details>
</div>

```js
import {mountEvidence} from "./components/evidence.js";
mountEvidence();
```
