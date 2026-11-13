---
title: Funding
---

<link rel="stylesheet" href="./components/funding.css">

<div id="funding-root">
  <h1>Funding</h1>
  <p class="viz-link"><a class="btn-link" id="funding-grants-link" style="display:inline-block;padding:0.55rem 1rem;border-radius:0.4rem;background:var(--brand-dark);color:#fff;font-weight:700;text-decoration:none">Open the funding visualizations &rarr;</a> <span class="data-note">Interactive Sankey, charts and a filterable award table.</span></p>
  <section aria-labelledby="grants-heading" class="grants">
    <h2 id="grants-heading">Awards</h2>
    <p class="data-note">Awards as reported by each source (NIH RePORTER, NSF Awards, USAspending.gov, California Sea Grant, Ocean Protection Council). Amounts follow each source's own basis and are not comparable or additive across sources or fiscal years. Pass-through awards appear once, on their lowest-level record. Plastic relevance and topic tags are provisional rule-based labels. This is not a complete record of public funding.</p>
    <details id="grants-filter-panel" class="facet grants-filter-panel" open><summary><span class="grants-filter-summary">Filters</span></summary>
    <form id="grants-filters" class="grants-filters" aria-label="Filter awards">
      <div class="grants-field"><label for="grants-search">Search awards</label><input id="grants-search" type="search" autocomplete="off" placeholder="Title, recipient, PI, program, funder"></div>
      <div class="grants-field"><label for="grants-sector">Recipient sector</label><select id="grants-sector"></select></div>
      <div class="grants-field"><label for="grants-agency">Funder agency</label><select id="grants-agency"></select></div>
      <div class="grants-field"><label for="grants-funder-type">Funder type</label><select id="grants-funder-type"><option value="">All funder types</option><option value="federal">Federal</option><option value="state">State</option><option value="other">Other</option></select></div>
      <div class="grants-field"><label for="grants-funder">Funder</label><select id="grants-funder"></select></div>
      <div class="grants-field"><label for="grants-program">Program</label><select id="grants-program"></select></div>
      <div class="grants-field"><label for="grants-year-from">Fiscal year from</label><input id="grants-year-from" type="number" inputmode="numeric" min="1900" max="2100" step="1"></div>
      <div class="grants-field"><label for="grants-year-to">Fiscal year to</label><input id="grants-year-to" type="number" inputmode="numeric" min="1900" max="2100" step="1"></div>
      <div class="grants-field"><label for="grants-amount-min">Amount at least (USD)</label><input id="grants-amount-min" type="number" inputmode="numeric" min="0" step="1000"></div>
      <div class="grants-field"><label for="grants-amount-max">Amount at most (USD)</label><input id="grants-amount-max" type="number" inputmode="numeric" min="0" step="1000"></div>
      <div class="grants-field"><label for="grants-institution-type">Recipient institution type</label><select id="grants-institution-type"></select></div>
      <div class="grants-field"><label for="grants-tag">Topic tag</label><select id="grants-tag"></select></div>
      <div class="grants-field"><label for="grants-ca-led">Led from California</label><select id="grants-ca-led"><option value="">Any</option><option value="yes">Yes</option><option value="no">No</option><option value="unknown">Unknown</option></select></div>
      <div class="grants-field grants-check"><input id="grants-plastic" type="checkbox" checked><label for="grants-plastic">Provisional plastic relevance only (true or unknown)</label></div>
      <div class="grants-actions"><button id="grants-reset" type="button">Reset filters</button><button id="grants-csv" type="button">Download filtered CSV</button></div>
    </form>
    </details>
    <ul id="grants-chips" class="grants-chips" aria-label="Active filters"></ul>
    <p id="grants-status" class="result-count" role="status" aria-live="polite"></p>
    <div class="grants-charts">
      <figure class="grants-chart"><figcaption>Awards by fiscal year and funder type (count)</figcaption><div id="grants-chart-year"></div></figure>
      <figure class="grants-chart"><figcaption>Awards by recipient institution type (count)</figcaption><div id="grants-chart-institution"></div></figure>
    </div>
    <div id="grants-table" class="grants-table-wrap" tabindex="0" role="region" aria-label="Awards table, scrollable"></div>
    <nav class="grants-pager" aria-label="Award table pages"><button id="grants-prev" type="button">Previous</button><span id="grants-page"></span><button id="grants-next" type="button">Next</button><label for="grants-page-size">Rows per page (default 50) <select id="grants-page-size"><option value="25">25</option><option value="50" selected>50</option><option value="100">100</option></select></label></nav>
    <section aria-labelledby="grants-basis-heading" class="grants-basis"><h3 id="grants-basis-heading">Amount basis by source</h3><div id="grants-basis"></div></section>
  </section>
  <section aria-labelledby="open-calls-heading" class="open-calls">
    <h2 id="open-calls-heading">Open funding calls</h2>
    <p class="data-note">Source: California Grants Portal (public domain), refreshed daily; calls are opportunities, not awards. <a href="https://data.ca.gov/dataset/california-grants-portal" target="_blank" rel="noreferrer">Dataset</a></p>
    <p id="open-calls-status" class="result-count" role="status" aria-live="polite"></p>
    <div id="open-calls"></div>
  </section>
</div>

```js
import "./components/shared/topics.js";
import {mountFunding} from "./components/funding.js";
mountFunding();
```
