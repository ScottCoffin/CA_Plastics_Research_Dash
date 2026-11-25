---
title: Data quality · Plastiverse Live
sidebar: false
header: false
footer: false
toc: false
pager: false
head: |
  <style>
    @font-face { font-family: "Schibsted Grotesk"; font-style: normal; font-weight: 400 700; font-display: swap; src: url("./assets/fonts/SchibstedGrotesk-Variable-latin.woff2") format("woff2"); unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD, U+2192; }
    @font-face { font-family: "Martian Mono"; font-style: normal; font-weight: 400; font-display: swap; src: url("./assets/fonts/MartianMono-Regular-latin.woff2") format("woff2"); unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD, U+2192; }
  </style>
  <link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNiAyNiI+PHJlY3Qgd2lkdGg9IjI2IiBoZWlnaHQ9IjI2IiByeD0iNSIgZmlsbD0iIzE3MjYzZCIvPjxjaXJjbGUgY3g9IjEzIiBjeT0iMTMiIHI9IjUiIGZpbGw9IiNmZmY0OWEiLz48ZyBzdHJva2U9IiNmZmY0OWEiIHN0cm9rZS13aWR0aD0iMS42IiBzdHJva2UtbGluZWNhcD0icm91bmQiPjxsaW5lIHgxPSIyMC42MCIgeTE9IjEzLjAwIiB4Mj0iMjMuNDAiIHkyPSIxMy4wMCIvPjxsaW5lIHgxPSIxOS40NyIgeTE9IjE1LjY4IiB4Mj0iMjMuMTYiIHkyPSIxNy4yMSIvPjxsaW5lIHgxPSIxOC4zNyIgeTE9IjE4LjM3IiB4Mj0iMjAuMzUiIHkyPSIyMC4zNSIvPjxsaW5lIHgxPSIxNS42OCIgeTE9IjE5LjQ3IiB4Mj0iMTcuMjEiIHkyPSIyMy4xNiIvPjxsaW5lIHgxPSIxMy4wMCIgeTE9IjIwLjYwIiB4Mj0iMTMuMDAiIHkyPSIyMy40MCIvPjxsaW5lIHgxPSIxMC4zMiIgeTE9IjE5LjQ3IiB4Mj0iOC43OSIgeTI9IjIzLjE2Ii8+PGxpbmUgeDE9IjcuNjMiIHkxPSIxOC4zNyIgeDI9IjUuNjUiIHkyPSIyMC4zNSIvPjxsaW5lIHgxPSI2LjUzIiB5MT0iMTUuNjgiIHgyPSIyLjg0IiB5Mj0iMTcuMjEiLz48bGluZSB4MT0iNS40MCIgeTE9IjEzLjAwIiB4Mj0iMi42MCIgeTI9IjEzLjAwIi8+PGxpbmUgeDE9IjYuNTMiIHkxPSIxMC4zMiIgeDI9IjIuODQiIHkyPSI4Ljc5Ii8+PGxpbmUgeDE9IjcuNjMiIHkxPSI3LjYzIiB4Mj0iNS42NSIgeTI9IjUuNjUiLz48bGluZSB4MT0iMTAuMzIiIHkxPSI2LjUzIiB4Mj0iOC43OSIgeTI9IjIuODQiLz48bGluZSB4MT0iMTMuMDAiIHkxPSI1LjQwIiB4Mj0iMTMuMDAiIHkyPSIyLjYwIi8+PGxpbmUgeDE9IjE1LjY4IiB5MT0iNi41MyIgeDI9IjE3LjIxIiB5Mj0iMi44NCIvPjxsaW5lIHgxPSIxOC4zNyIgeTE9IjcuNjMiIHgyPSIyMC4zNSIgeTI9IjUuNjUiLz48bGluZSB4MT0iMTkuNDciIHkxPSIxMC4zMiIgeDI9IjIzLjE2IiB5Mj0iOC43OSIvPjwvZz48L3N2Zz4=">
  <meta name="theme-color" content="#000000">
---

<!-- BQ-1.4: /quality, the global quality page. Chrome and tokens: components/explore.css (scoped to .gx).
     Blocks: components/quality.css. Data: data/global/quality.json, rendered by components/quality.js. -->

<link rel="stylesheet" href="./components/explore.css">
<link rel="stylesheet" href="./components/quality.css">

<div class="gx">
<a class="skip" href="#main">Skip to the content</a>
<header class="top">
  <a class="brand" href="./" aria-label="Plastiverse Live home"><svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="5"/><g><line x1="20.60" y1="13.00" x2="23.40" y2="13.00"/><line x1="20.02" y1="15.91" x2="23.72" y2="17.44"/><line x1="18.37" y1="18.37" x2="20.35" y2="20.35"/><line x1="15.91" y1="20.02" x2="17.44" y2="23.72"/><line x1="13.00" y1="20.60" x2="13.00" y2="23.40"/><line x1="10.09" y1="20.02" x2="8.56" y2="23.72"/><line x1="7.63" y1="18.37" x2="5.65" y2="20.35"/><line x1="5.98" y1="15.91" x2="2.28" y2="17.44"/><line x1="5.40" y1="13.00" x2="2.60" y2="13.00"/><line x1="5.98" y1="10.09" x2="2.28" y2="8.56"/><line x1="7.63" y1="7.63" x2="5.65" y2="5.65"/><line x1="10.09" y1="5.98" x2="8.56" y2="2.28"/><line x1="13.00" y1="5.40" x2="13.00" y2="2.60"/><line x1="15.91" y1="5.98" x2="17.44" y2="2.28"/><line x1="18.37" y1="7.63" x2="20.35" y2="5.65"/><line x1="20.02" y1="10.09" x2="23.72" y2="8.56"/></g></svg><span class="wm" aria-hidden="true">PLASTIVERSE <b>LIVE</b></span></a>
  <nav class="nav" aria-label="Main">
    <a href="./explore">Explore the data</a>
    <a href="./quality" aria-current="page">Data quality</a>
    <a href="./california/about#how-works-are-screened">Methods</a>
    <a href="./california/about">About</a>
  </nav>
</header>
<main id="main" tabindex="-1">
<div class="wrap">
<div class="head">
  <h1>How accurate is the global search?</h1>
  <p class="statement">Global works are unscreened query hits. A labelled sample will show how many are plastics research and how many relevant works the search misses.</p>
</div>
</div>

<div id="quality-root" class="qx">
<p class="qx-status">No validated estimate yet. The labelled sample is still being built.</p>
</div>

<section class="qx" aria-labelledby="quality-method">
<h2 id="quality-method">How it is measured</h2>
<p>A random sample of global works from the frozen query frame is labelled by hand against a written guide. Strata are defined by language block, theme group and relevance-score band. Each labelled work is weighted by its selection chance, so the sample stands for the whole frame. Until the sample is complete and analysed, no precision, recall or interval is published.</p>
<p>The <a href="./california/quality">California quality page</a> reports the matching checks for the California corpus, and the <a href="./california/about">About page</a> describes the limits of the labels.</p>
</section>
</main>

<footer class="foot">
  <div><b>Plastiverse Live</b><br>Created by <a href="https://scottcoff.in" rel="noreferrer">Scott Coffin</a>. Not a State product.</div>
  <div><b>Read more</b><br><a href="./california/about">About</a> · <a href="./california/glossary">Glossary</a> · <a href="./explore">Explore the data</a></div>
</footer>
</div>

```js
import {mountQuality} from "./components/quality.js";
const root = document.getElementById("quality-root");
await mountQuality(root, async () => {
  const response = await fetch("./data/global/quality.json", {cache: "no-cache"});
  if (!response.ok) throw new Error("quality.json returned HTTP " + response.status);
  return response.json();
});
```
