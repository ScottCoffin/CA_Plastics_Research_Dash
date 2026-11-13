---
title: Evidence map
---

# Evidence map

Filter the atlas's distinct works by words in the title, year range, topic, sector, work type, open access and California leadership. The page lists plastic-related works only. The trend charts and the heatmap follow the filters, and selecting heatmap cells narrows the publication table below.

<p class="ev-notice">In development: a map of sampled locations and a review overlay will be added here. Topic and matrix tags come from keyword rules and are provisional.</p>

<link rel="stylesheet" href="./components/evidence.css">
<link rel="stylesheet" href="./components/v3_flow.css">
<link rel="stylesheet" href="./components/v4_trend.css">
<link rel="stylesheet" href="./components/ev_heatmap.css">
<link rel="stylesheet" href="./components/ev_table.css">

<div id="evidence-root">
  <p id="evidence-status" class="result-count" role="status" aria-live="polite">Loading the evidence bundle…</p>
  <section id="ev-recent" class="ev-recent" aria-label="New in the last 2 weeks" hidden></section>
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
      <p class="data-note volume-caption">Counts show how much has been published, not the strength or quality of the evidence.</p>
      <section class="ev-view" aria-labelledby="ev-v4-heading" hidden><h2 id="ev-v4-heading">Trends</h2><div id="ev-v4"></div></section>
      <section class="ev-view" aria-labelledby="ev-heatmap-heading" hidden><h2 id="ev-heatmap-heading">Evidence heatmap</h2><div id="ev-heatmap"></div></section>
    </div>
  </div>
  <section class="ev-view" aria-labelledby="ev-table-heading"><h2 id="ev-table-heading">Publications</h2><div id="ev-table"><p class="result-count">Loading publications…</p></div></section>
  <details class="ev-view ev-flow-box"><summary id="ev-v3-heading">How works were selected (pipeline flow)</summary><div id="ev-v3"></div></details>
</div>

```js
import {mountEvidence} from "./components/evidence.js";
mountEvidence();
```
