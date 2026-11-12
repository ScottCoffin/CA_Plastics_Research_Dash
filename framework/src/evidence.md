---
title: Evidence map
---

# Evidence map

Filter the atlas's distinct works by topic, sector, work type, open access, California leadership, plastic relevance and year, then open the works behind any count.

<link rel="stylesheet" href="./components/evidence.css">

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
        <button id="evidence-show-works" type="button" disabled>Show works</button>
      </div>
      <section id="evidence-strip" class="ev-strip" aria-labelledby="evidence-strip-heading" hidden>
        <h3 id="evidence-strip-heading">Related resources</h3>
        <ul id="evidence-strip-list" class="ev-strip-list"></ul>
        <p id="evidence-strip-note" class="data-note"></p>
      </section>
      <section class="ev-view" aria-labelledby="ev-v1-heading"><h3 id="ev-v1-heading">Evidence matrix</h3><p class="ev-placeholder">Coming with EM-8.</p></section>
      <section class="ev-view" aria-labelledby="ev-v2-heading"><h3 id="ev-v2-heading">Sampled-location atlas</h3><p class="ev-placeholder">Coming with EM-9.</p></section>
      <section class="ev-view" aria-labelledby="ev-v3-heading"><h3 id="ev-v3-heading">Pipeline flow</h3><p class="ev-placeholder">Coming with EM-6.</p></section>
      <section class="ev-view" aria-labelledby="ev-v4-heading"><h3 id="ev-v4-heading">Trend panel</h3><p class="ev-placeholder">Coming with EM-7.</p></section>
      <section class="ev-view" aria-labelledby="ev-v5-heading"><h3 id="ev-v5-heading">Review overlay</h3><p class="ev-placeholder">Coming with EM-10.</p></section>
    </div>
  </div>
  <dialog id="evidence-drawer" class="ev-drawer" role="dialog" aria-modal="true" aria-labelledby="evidence-drawer-title">
    <div class="ev-drawer-body">
      <header class="ev-drawer-head"><h3 id="evidence-drawer-title">Works</h3><button id="evidence-drawer-close" type="button">Close</button></header>
      <p id="evidence-drawer-count" class="result-count" aria-live="polite"></p>
      <ol id="evidence-drawer-list" class="ev-drawer-list"></ol>
      <nav class="ev-pager" aria-label="Work pages"><button id="evidence-drawer-prev" type="button">Previous</button><span id="evidence-drawer-page"></span><button id="evidence-drawer-next" type="button">Next</button></nav>
    </div>
  </dialog>
</div>

```js
import {mountEvidence} from "./components/evidence.js";
mountEvidence();
```
