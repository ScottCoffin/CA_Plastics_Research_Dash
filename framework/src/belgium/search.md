---
title: Search
head: '<meta name="robots" content="noindex, nofollow">'
---

<header class="atlas-page-head">
  <p class="atlas-page-head__eyebrow">Search</p>
  <h1>Search the Atlas</h1>
  <p class="atlas-page-head__lead">Search Belgium authors, institutions, and topic tags in the regional research export.</p>
</header>

<form class="site-search-page__form" action="./search" method="get" role="search" aria-label="Search Belgium research" data-atlas-search-page>
  <label for="site-search-page-input">Search for a name, place, topic or term</label>
  <div class="site-search-page__field">
    <input id="site-search-page-input" name="q" type="search" autocomplete="off" placeholder="e.g. microplastics, author, institution">
    <button type="submit">Search</button>
  </div>
</form>

<p class="site-search-page__status" role="status" aria-live="polite" data-atlas-search-status>Search Belgium authors, institutions, and topics.</p>

<div class="site-search-page__results" data-atlas-search-results></div>

<noscript>

Search results need JavaScript. Browse [Authors](./authors) and [Institutions](./institutions) without search.

</noscript>
