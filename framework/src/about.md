---
title: About
---

# About this snapshot

The Atlas is a static, client-side site. It reads generated JSON and does not query OpenAlex from your browser.

```js
import {loadJson, aboutViewModel, releaseDoi, classicUrl} from "./components/atlas.js";
const [metadata, release] = await Promise.all([
  loadJson("build_metadata.json"),
  loadJson("release.json", {optional: true})
]);
const snapshot = aboutViewModel(metadata, null);
const doi = releaseDoi(release);
```

<p class="atlas-notice" id="about-freshness">${snapshot.refreshDisplay ? html`Last refresh: <time datetime=${snapshot.refreshIso}>${snapshot.refreshDisplay}</time>` : snapshot.refreshText}</p>

${doi
  ? html`<p>Latest archived release: ${String(release.version || "")} (${String(release.date || "")}), DOI <a href="https://doi.org/${doi}" target="_blank" rel="noreferrer">${doi}</a>. Methods card, Parquet files and checksums are in the release archive.</p>`
  : html`<p>Archived releases: <a href="https://doi.org/10.5281/zenodo.24124016" target="_blank" rel="noreferrer">Zenodo DOI 10.5281/zenodo.24124016</a> (always resolves to the latest release).</p>`}

<dl class="atlas-stats" id="about-stats">${snapshot.stats.map(({label, value, note}) => html`<div><dt>${label}</dt><dd>${value}</dd>${note ? html`<dd class="stat-note">${note}</dd>` : ""}</div>`)}</dl>

<p class="atlas-notice"><strong>Interpretation note:</strong> provisional labels are screening metadata, not a validated pollution leaderboard. Confirm the linked source work before drawing conclusions.</p>

<div class="atlas-cards">
<section class="card">

## Sources and snapshot

OpenAlex supplies the work and affiliation metadata. The published list comes from a reviewed plastics search of titles and abstracts. Simple keyword counts, such as a bare search for “plastic”, are used only to decide what to review first; they are not the published list.

The refresh time is when this site’s data were last rebuilt, not when each source record was last updated. If a page says “Example data loaded”, it is showing built-in sample data, not a current refresh.

</section>
<section class="card">

## Definitions

**Plastic-related:** work about plastic debris or particles, plastic litter, microfibers, tire-wear particles, or plastic-pollution policy. Chemicals in plastics are a separately flagged Tier 2 scope.

**CA-led:** the first author’s affiliation resolves to a California institution. **CA-sampled:** sample collection or deployed monitoring took place in California land or state waters. A California affiliation does not by itself mean sampling happened in California.

California state waters use a three-nautical-mile polygon derived from NOAA’s offshore maritime-limit line and clipped through the CDFW dataset. It is not a legal depiction of maritime limits.

More terms used across the Atlas are defined in the <a href="./glossary">Glossary</a>.

</section>
<section class="card">

## Limitations

Plastic-related and topic labels are provisional, rule-based screening metadata. A held-out gold set and evaluation are later roadmap work, so no validated precision or recall is available yet.

OpenAlex coverage and affiliation records may be incomplete or incorrect, and author profiles can split one person’s works or combine different people. Institution location does not identify a study’s sampling location.

</section>
<section class="card">

## How to cite

${doi
  ? html`<p>Coffin, S. (${String(release.date || "").slice(0, 4)}). <cite>CA Plastics Research Atlas</cite> (${String(release.version || "")}) [Data set and software]. Zenodo. <a href="https://doi.org/${doi}" target="_blank" rel="noreferrer">https://doi.org/${doi}</a></p>`
  : html`<p>Coffin, S. <cite>CA Plastics Research Atlas</cite> [Data set and software]. Zenodo.</p>`}

To cite every version at once, use the concept DOI <a href="https://doi.org/10.5281/zenodo.24124016" target="_blank" rel="noreferrer">10.5281/zenodo.24124016</a>, which always resolves to the latest release.

</section>
<section class="card">

## Licence

Data produced by the Atlas (the files behind these pages, the feed and the release snapshots) are shared under the <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">Creative Commons Attribution 4.0 licence (CC BY 4.0)</a>: you may reuse them, including commercially, if you credit the Atlas. The code is under the <a href="https://github.com/ScottCoffin/CA_Plastics_Research_Dash/blob/main/LICENSE" target="_blank" rel="noreferrer">MIT licence</a>. Third-party material keeps its own terms: bibliographic metadata comes from OpenAlex (CC0), and each monitoring observation carries its source’s licence and citation. Details: <a href="https://github.com/ScottCoffin/CA_Plastics_Research_Dash/blob/main/LICENSE-DATA.md" target="_blank" rel="noreferrer">data licence</a>.

</section>
<section class="card">

## Corrections and source work

For a correction or profile-removal request, <a href="https://github.com/ScottCoffin/CA_Plastics_Research_Dash/issues/new?title=Atlas%20data%20correction" target="_blank" rel="noreferrer">open a data-correction issue</a>. Include the OpenAlex ID, DOI or source URL when available, the field in question, and the proposed correction. If you cannot use GitHub, a contact address will be listed here soon. Requests are acknowledged and acted on within 5 to 10 business days; a removed person or work is also excluded at the next ingest. Changes are reviewed for a later snapshot; the project does not alter the upstream OpenAlex record.

</section>
</div>

<p class="atlas-notice"><strong>Disclaimer:</strong> Independent project; not an official OEHHA or State product.</p>

<!-- EM-14: owner affiliation disclosure; owner approved naming roles (GOV-B, 2026-11-10) -->
<p class="atlas-notice"><strong>Disclosure:</strong> the Atlas owner, Scott Coffin, is a co-founder of Plastiverse, which hosts this site at plastiverse.live. The Atlas is an independent research tool and is not an official product of any agency.</p>

Full methods: <a href="https://github.com/ScottCoffin/CA_Plastics_Research_Dash/blob/main/docs/METHODS.md" target="_blank" rel="noreferrer">docs/METHODS.md</a>. Data schema: <a href="https://github.com/ScottCoffin/CA_Plastics_Research_Dash/blob/main/docs/SITE_DATA.md" target="_blank" rel="noreferrer">site data description</a>. Upstream catalogue: <a href="https://openalex.org/" target="_blank" rel="noreferrer">OpenAlex</a>.

Pipeline health: <a href=${classicUrl("status.html")}>run status and drift alarms</a>. <a href=${classicUrl("feed.xml")} type="application/atom+xml">Subscribe (Atom feed)</a>.
