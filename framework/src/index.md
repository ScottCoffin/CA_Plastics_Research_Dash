---
title: Overview
---

# CA Plastics Research Atlas

A transparent starting point for finding plastic-related research connected to California.

```js
import {loadJson, aboutViewModel} from "./components/atlas.js";
const metadata = await loadJson("build_metadata.json");
const snapshot = aboutViewModel(metadata, null);
```

<p class="atlas-notice">${snapshot.refreshText}</p>

<dl class="atlas-stats">${snapshot.stats.filter((s) => s.label !== "Schema").map(({label, value}) => html`<div><dt>${label}</dt><dd>${value}</dd></div>`)}</dl>

<div class="atlas-cards">
  <a class="card" href="./experts"><h2>Experts</h2><p>California researchers working on plastics, with topics and metrics.</p></a>
  <a class="card" href="./institutions"><h2>Institutions</h2><p>Universities, agencies and other organisations, with a map and tiers.</p></a>
  <a class="card" href="./monitoring"><h2>Monitoring</h2><p>Public plastic monitoring samples from California waters.</p></a>
  <a class="card" href="./funding"><h2>Funding</h2><p>Grants and awards for plastics research, and open funding calls.</p></a>
  <a class="card" href="./about"><h2>About</h2><p>Sources, definitions, limitations and corrections.</p></a>
</div>
