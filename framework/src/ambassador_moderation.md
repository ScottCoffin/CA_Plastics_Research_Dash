---
title: Moderation · Plastiverse Live
sidebar: false
header: false
footer: false
toc: false
pager: false
head: '<meta name="robots" content="noindex, nofollow">'
---

<!-- AMB-1 slice 2c: the moderation page for the owner and region leads. Unlisted (not in the navigation, sitemap or
     llms.txt) and noindex. The markup is static here; components/ambassador_moderation.js reads /me and
     /moderation/queue and draws one item per screen. Styles: components/ambassadors.css and ambassador_moderation.css. -->

<link rel="stylesheet" href="./components/ambassadors.css">
<link rel="stylesheet" href="./components/ambassador_moderation.css">

<div class="am">
<a class="skip" href="#main">Skip to the content</a>
<header class="top">
  <a class="brand" href="./" aria-label="Plastiverse Live home"><svg width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><circle cx="13" cy="13" r="5"/><line x1="2.6" y1="13" x2="23.4" y2="13"/><line x1="13" y1="2.6" x2="13" y2="23.4"/></svg><span class="wm">PLASTI<b>VERSE</b> LIVE</span></a>
  <nav class="nav" aria-label="Main">
    <a href="./explore">Explore the data</a>
    <a href="./ambassadors">Ambassadors</a>
  </nav>
</header>

<main id="main" tabindex="-1">

<section class="hero">
  <h1>Moderation</h1>
  <p class="lede">Review ambassador submissions and proposals one at a time. Each decision is saved as soon as you make it.</p>
</section>

<section class="sec mod" id="mod-root" aria-label="Moderation queue">
  <p class="sr" id="mod-status" role="status" aria-live="polite"></p>
  <div id="mod-body"><p class="status">Loading the queue.</p></div>
</section>

</main>

<footer class="foot">
  <p><b>Plastiverse Live</b> · <a href="./ambassador_terms">Contribution terms</a> · <a href="./explore">Explore the data</a> · Email <span class="addr">theplastiverse@gmail.com</span></p>
</footer>
</div>

```js
import {mountModeration} from "./components/ambassador_moderation.js";
mountModeration(document.querySelector(".am")).catch((error) => console.error("moderation:", error));
```
