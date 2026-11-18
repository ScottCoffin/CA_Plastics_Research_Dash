---
title: Search
head: '<meta name="robots" content="noindex, nofollow">'
---

<header class="atlas-page-head">
  <p class="atlas-page-head__eyebrow">Search</p>
  <h1>Search the Atlas</h1>
  <p class="atlas-page-head__lead">Find authors, institutions, research topics, funders, glossary terms and related resources in one place.</p>
</header>

<form class="site-search-page__form" action="./search" method="get" role="search" data-atlas-search-page>
  <label for="site-search-page-input">Search for a name, place, topic or term</label>
  <div class="site-search-page__field">
    <input id="site-search-page-input" name="q" type="search" autocomplete="off" placeholder="e.g. Rochman, UC Davis, microfiber, NSF">
    <button type="submit">Search</button>
  </div>
</form>

<p class="site-search-page__status" role="status" aria-live="polite" data-atlas-search-status>Type a name, institution, topic, funder or glossary term to search the Atlas.</p>

<div class="site-search-page__results" data-atlas-search-results></div>

<noscript>

Search results need JavaScript. You can still browse the [Authors](./authors), [Institutions](./institutions), [Funding](./funding) and [Glossary](./glossary) pages.

</noscript>
