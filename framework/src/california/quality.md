---
title: Quality
---

<header class="atlas-page-head">
<p class="atlas-page-head__eyebrow"><svg class="icon" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><use href="#i-info"></use></svg> Reference</p>
<h1>Quality of the California atlas</h1>
<p class="atlas-page-head__lead">How accurate the California labels are, how we will measure it, and where the checking stands.</p>
</header>

<link rel="stylesheet" href="../components/quality.css">

<section class="atlas-notice" aria-label="Status">
<div id="quality-root" class="qx">
<p class="qx-status">No validated estimate yet. The labelled sample is still being built.</p>
</div>
</section>

## What is measured

- **Precision**: of the works the atlas shows as plastics research, the share a human labeller confirms.
- **Recall**: of the works a human labeller confirms as plastics research, the share the atlas shows.
- **Residual relevant works**: an upper bound on relevant works the atlas leaves out of the low-scoring band.
- **Language coverage**: how the estimates change across languages and abstract presence.

## How it is measured

A random sample of California works is labelled by hand, one work at a time, against a written guide. The
labels are compared with the atlas's displayed labels. Works are drawn with a design, not by convenience, so
each labelled work stands for others like it. Results are weighted by the chance each work was selected.
Intervals resample author groups, so one prolific group cannot dominate them. Leak-test works are labelled
for checks only and are never used to tune the labels.

## Current status

The status line above is read from the published data file and is updated with each build. Until the labelled
sample is complete and analysed, the atlas publishes no precision, recall or other figure, and no interval.
Interim counts are shown only as progress, so they cannot be mistaken for results.

## What this is and is not

This page describes how the labels will be checked. It is not yet an evaluation. Labels are provisional,
rule-based screening metadata until the checks are published. Do not use the labels as a pollution ranking.
The [About page](./about) states the same limit, and the [Glossary](./glossary) defines the terms.

```js
import {loadJson} from "../components/atlas.js";
import {mountQuality} from "../components/quality.js";
const root = document.getElementById("quality-root");
await mountQuality(root, () => loadJson("quality.json"));
```
