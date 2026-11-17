---
title: Funding
---

<link rel="stylesheet" href="./components/funding.css">
<link rel="stylesheet" href="./components/funding_viz.css">

<div id="funding-root">
<header class="atlas-page-head funding-page-head">
<span class="motif" aria-hidden="true"></span>
<p class="atlas-page-head__eyebrow"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-coins"></use></svg>Data</p>
<h1>Funding</h1>
<p class="atlas-page-head__lead">Public awards from federal, state and other funders, as each source reports them. Use the filters to narrow the list, click heatmap cells to narrow it further, or switch any chart to its table.</p>
</header>

<div id="grants-basis-caution" class="atlas-callout atlas-callout--caution">
<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-alert"></use></svg>
<p>Awards as reported by each source (NIH RePORTER, NSF Awards, USAspending.gov, California Sea Grant, Ocean Protection Council). Amounts follow each source's own basis and are not comparable or additive across sources or fiscal years. Pass-through awards appear once, on their lowest-level record. Plastic relevance and topic tags are provisional rule-based labels. This is not a complete record of public funding.</p>
</div>

<div class="atlas-callout atlas-callout--info" role="note">
<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-info"></use></svg>
<p class="data-note volume-caption">Award counts show volume, not strength: more awards do not mean larger or better research programmes.</p>
</div>

<section class="atlas-filters" aria-labelledby="grants-filters-heading">
<div class="atlas-filters__head">
<h2 id="grants-filters-heading">Filters</h2>
<span id="grants-filter-count" class="atlas-filters__count" aria-live="polite">0 on</span>
<button id="grants-reset" class="atlas-btn atlas-btn--ghost" type="button">Clear all</button>
</div>
<form id="grants-filters" class="atlas-filters__body" aria-label="Filter awards">
<div class="atlas-filters__grid grants-primary-filters">
<div class="atlas-field grants-field"><label class="atlas-label" for="grants-search">Search awards</label><div class="atlas-search"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-search"></use></svg><input id="grants-search" class="atlas-input" type="search" autocomplete="off" placeholder="Title, recipient, PI, program, funder"></div></div>
<div class="atlas-field grants-field"><label class="atlas-label" for="grants-agency">Funder agency</label><select id="grants-agency" class="atlas-select"></select></div>
<div class="atlas-field grants-field"><label class="atlas-label" for="grants-tag">Topic tag</label><select id="grants-tag" class="atlas-select"></select></div>
<div class="atlas-field grants-field"><label class="atlas-label" for="grants-year-from">Fiscal year from</label><input id="grants-year-from" class="atlas-input" type="number" inputmode="numeric" min="1900" max="2100" step="1"></div>
<div class="atlas-field grants-field"><label class="atlas-label" for="grants-year-to">Fiscal year to</label><input id="grants-year-to" class="atlas-input" type="number" inputmode="numeric" min="1900" max="2100" step="1"></div>
</div>
<details id="grants-more-filters" class="atlas-filters__more">
<summary>More filters <span>(9)</span></summary>
<div class="atlas-filters__grid grants-more-grid">
<div class="atlas-field grants-field"><label class="atlas-label" for="grants-sector">Recipient sector</label><select id="grants-sector" class="atlas-select"></select></div>
<div class="atlas-field grants-field"><label class="atlas-label" for="grants-funder-type">Funder type</label><select id="grants-funder-type" class="atlas-select"><option value="">All funder types</option><option value="federal">Federal</option><option value="state">State</option><option value="other">Other</option></select></div>
<div class="atlas-field grants-field"><label class="atlas-label" for="grants-funder">Funder</label><select id="grants-funder" class="atlas-select"></select></div>
<div class="atlas-field grants-field"><label class="atlas-label" for="grants-program">Program</label><select id="grants-program" class="atlas-select"></select></div>
<div class="atlas-field grants-field"><label class="atlas-label" for="grants-amount-min">Amount at least (USD)</label><input id="grants-amount-min" class="atlas-input" type="number" inputmode="numeric" min="0" step="1000"></div>
<div class="atlas-field grants-field"><label class="atlas-label" for="grants-amount-max">Amount at most (USD)</label><input id="grants-amount-max" class="atlas-input" type="number" inputmode="numeric" min="0" step="1000"></div>
<div class="atlas-field grants-field"><label class="atlas-label" for="grants-institution-type">Recipient institution type</label><select id="grants-institution-type" class="atlas-select"></select></div>
<div class="atlas-field grants-field"><label class="atlas-label" for="grants-ca-led">Led from California</label><select id="grants-ca-led" class="atlas-select"><option value="">Any</option><option value="yes">Yes</option><option value="no">No</option><option value="unknown">Unknown</option></select></div>
<div class="atlas-field grants-field grants-check"><input id="grants-plastic" class="atlas-check" type="checkbox" checked><label for="grants-plastic">Provisional plastic relevance only (true or unknown)</label></div>
</div>
</details>
</form>
<div id="grants-chips" class="atlas-active-filters" aria-label="Active filters" aria-live="polite"></div>
</section>

<div class="atlas-result-line">
<p id="grants-status" role="status" aria-live="polite"></p>
<button id="grants-csv" class="atlas-btn atlas-btn--secondary" type="button"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false"><use href="#i-download"></use></svg> Download filtered CSV</button>
</div>

<div id="grants-viz" class="grants-viz"></div>

<section class="grants-list" aria-label="Award list">
<div id="grants-table" class="grants-table-wrap" tabindex="0" role="region" aria-label="Awards table, scrollable"></div>
<nav class="grants-pager" aria-label="Award table pages"><button id="grants-prev" class="atlas-btn atlas-btn--secondary" type="button">Previous</button><span id="grants-page"></span><button id="grants-next" class="atlas-btn atlas-btn--secondary" type="button">Next</button><label for="grants-page-size">Rows per page (default 50) <select id="grants-page-size" class="atlas-select"><option value="25">25</option><option value="50" selected>50</option><option value="100">100</option></select></label></nav>
</section>

<section aria-labelledby="grants-basis-heading" class="grants-basis"><h2 id="grants-basis-heading">Amount basis by source</h2><div id="grants-basis"></div></section>

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
import {initTooltips} from "./components/shared/tooltip.js";
initTooltips(document);
mountFunding();
```
