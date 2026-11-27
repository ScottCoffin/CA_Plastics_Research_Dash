---
title: Topics
---

<header class="atlas-page-head">
<p class="atlas-page-head__eyebrow"><svg class="icon" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><use href="#i-info"></use></svg> Data</p>
<h1>Topic evolution in Belgium</h1>
<p class="atlas-page-head__lead">Yearly counts and shares for provisional topic tags on unscreened Belgium works. These are OpenAlex query hits, not a screened or ranked set of Belgian research.</p>
</header>

<link rel="stylesheet" href="../components/topics_page.css">

## What this is and is not

- Topic tags are **provisional domain labels**. Regional relevance has not been screened and no regional tag has been validated against human-labelled gold data.
- Figures are **counts and shares of unscreened Belgium works** by publication year. They are not a measure of importance.
- A rule-only rising-share screen uses a volume threshold and leave-one-institution-out checks. Owner/model sensitivity variants and gold-label accuracy are unavailable. Flags have no correction for multiple testing and are prompts for review, not confirmed findings.
- Analytic lenses are not computed for this region.

Accuracy states are indicative only: no Belgium gold labels are available. Fewer than 10 works in complete years is marked insufficient data; other tags are experimental.

<section class="atlas-notice" aria-label="Status">
<div id="topics-root" class="tp">
<p class="tp-status">Loading the topic series.</p>
</div>
</section>

```js
import {loadJson} from "../components/atlas.js";
import {mountRegionTopics} from "../components/region_topics_page.js";
const root = document.getElementById("topics-root");
await mountRegionTopics(root, {
  series: () => loadJson("topics_timeseries.json"),
  bursts: () => loadJson("topic_bursts.json"),
  Plot,
});
```

Browse [Belgium authors](./authors), [institutions](./institutions), or [works and evidence](./evidence). Use [regional search](./search) to find a topic or author.
