---
title: Evidence map
---

<link rel="stylesheet" href="../components/evidence.css">
<link rel="stylesheet" href="../components/v3_flow.css">
<link rel="stylesheet" href="../components/v4_trend.css">
<link rel="stylesheet" href="../components/ev_heatmap.css">
<link rel="stylesheet" href="../components/ev_table.css">

<header class="atlas-page-head">
  <p class="atlas-page-head__eyebrow"><svg class="icon" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><use href="#i-grid"></use></svg> Data</p>
  <h1 id="evidence-map">Evidence map</h1>
  <p class="atlas-page-head__lead">Explore Belgium-linked works with filters and a heatmap. Selections show matching publications below. Works found by the Atlas search; not yet reviewed for relevance.</p>
</header>

<details class="atlas-disclosure ev-how-to">
  <summary>How to use this page</summary>
  <div class="atlas-disclosure__body">
    <p>Filter the Belgium works found by the Atlas search by words in the title, year range, topic, sector, work type, open access, and journal. Works found by the Atlas search; not yet reviewed for relevance. The publication table can sort by journal and by citation count.</p>
    <p>The heatmap follows the filters, and selecting heatmap cells narrows the publication table below. Click a topic, matrix, or period heading to select that whole row or column.</p>
  </div>
</details>

<div class="atlas-callout atlas-callout--dev ev-dev-callout" role="note">
  <p class="ev-notice">In development: a map of sampled locations and a review overlay will be added here. Topic and matrix tags come from keyword rules and are provisional.</p>
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
      <section class="ev-view atlas-chart" aria-labelledby="ev-heatmap-heading" hidden><div class="atlas-chart__head"><div><div class="atlas-help-row"><h2 id="ev-heatmap-heading" tabindex="-1">Evidence heatmap</h2><button type="button" class="atlas-help" data-atlas-tip-align="end" aria-label="About this chart: Each cell counts works for one topic and one matrix or five-year period; works can carry several tags, so cells overlap. Click a cell or a heading to select it, and the publication table lists only the selected works." data-atlas-tip="Each cell counts works for one topic and one matrix or five-year period; works can carry several tags, so cells overlap. Click a cell or a heading to select it, and the publication table lists only the selected works." aria-expanded="false"><svg class="atlas-help__icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="9.5"/><path d="M12 11v5.5M12 7.5h.01"/></svg></button></div><p class="atlas-chart__source">Source: works in the Atlas by topic and matrix or five-year period, following the filters.</p></div><div class="atlas-segmented" role="group" aria-label="Chart or table view: Evidence heatmap"><button type="button" data-view="chart" aria-pressed="true">Chart</button><button type="button" data-view="table" aria-pressed="false">Table</button></div></div><div class="atlas-chart__body"><div id="ev-heatmap"></div></div></section>
    </div>
  </div>
  <div class="atlas-callout atlas-callout--info ev-info-callout" role="note">
    <p class="data-note ev-aux-note">The topic <strong>Plastic-associated chemicals</strong> (such as BPA, phthalates and 6PPD) is auxiliary. The Atlas searches for plastics terms, so it covers these chemical studies far less completely than studies of plastic particles and debris.</p>
  </div>
  <section id="ev-recent" class="ev-recent atlas-callout atlas-callout--new" aria-label="New in the last 2 weeks" hidden></section>
  <section class="ev-view atlas-chart" aria-labelledby="ev-table-heading" data-kind="table"><div class="atlas-chart__head"><h2 id="ev-table-heading" tabindex="-1">Publications</h2></div><div class="atlas-chart__body"><div id="ev-table-selection" class="ev-table-selection ev-table-root" role="status" aria-live="polite" hidden></div><div id="ev-table"><p class="result-count">Loading publications…</p></div></div></section>
</div>

```js
import {mountEvidence} from "../components/evidence.js";
import {injectIconSprite} from "../components/shared/icons.js";
import {initTooltips} from "../components/shared/tooltip.js";
injectIconSprite();
initTooltips(document);
requestAnimationFrame(() => {
  requestAnimationFrame(() => {
    mountEvidence().catch((error) => console.error("Failed to initialize the Evidence map.", error));
  });
});
```
