---
title: Graph viewer (development)
sidebar: false
header: false
footer: false
toc: false
pager: false
head: '<meta name="robots" content="noindex, nofollow">'
---

<link rel="stylesheet" href="./components/graph_viewer.css">

<main class="dev-graph" id="main">
<h1>Graph viewer (development)</h1>
<p>Unlisted test page for the global graph viewer (BQ-V.3). Not linked from the site; not in the sitemap or llms.txt. Query: <code>?graph=institutions|authors&amp;phone=auto|true|false</code>.</p>
<div id="dev-graph"></div>
</main>

```js
import {mountGraph} from "./components/graph_viewer.js";
const params = new URLSearchParams(window.location.search);
mountGraph(document.querySelector("#dev-graph"), {
  graph: params.get("graph") ?? "institutions",
  phone: params.get("phone") ?? "auto"
});
```
