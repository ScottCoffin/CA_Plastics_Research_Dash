---
title: Topics
---

<header class="atlas-page-head">
<p class="atlas-page-head__eyebrow"><svg class="icon" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><use href="#i-info"></use></svg> Data</p>
<h1>Topic evolution in California</h1>
<p class="atlas-page-head__lead">How the rule-based topic labels on California plastics research change by year, which topics tend to appear together, and which show a rising share.</p>
</header>

<link rel="stylesheet" href="../components/topics_page.css">

## What this is and is not

- These are **rule-based, provisional labels**. No topic label has been checked against human-labelled gold data yet, so every accuracy state below reads "experimental" or "insufficient data" until that check exists.
- The figures are **counts and shares of plastic-related California works** by publication year. A share shows how much of the year's plastic-related output carries a topic. It is **not a measure of importance**.
- A **rising flag** is a statistical screen: a trend test with volume, label-source and leave-one-institution-out checks. It has **no correction for multiple testing** across topics, so a flag is a prompt for review, not a confirmed finding.
- Lenses are shown separately. A lens is counted only when the work itself uses the frame, with a quoted excerpt.

Accuracy states: **validated** needs a per-topic F1 score from gold labels (none exist yet); **insufficient data** means fewer than 10 works in complete years, or no labels yet; **experimental** is everything else.

<section class="atlas-notice" aria-label="Status">
<div id="topics-root" class="tp">
<p class="tp-status">Loading the topic series.</p>
</div>
</section>

```js
import {loadJson} from "../components/atlas.js";
import {mountTopics} from "../components/topics_page.js";
const root = document.getElementById("topics-root");
await mountTopics(root, {
  series: () => loadJson("topics_timeseries.json"),
  bursts: () => loadJson("topic_bursts.json"),
  Plot,
});
```

The [About page](./about) states the same limits, and the [Glossary](./glossary) defines the terms.
