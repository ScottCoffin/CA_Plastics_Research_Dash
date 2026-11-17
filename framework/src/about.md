---
title: About
---

<header class="atlas-page-head">
<p class="atlas-page-head__eyebrow"><svg class="icon" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><use href="#i-info"></use></svg> Reference</p>
<h1>About the Atlas</h1>
<p class="atlas-page-head__lead">What the Atlas collects, where it comes from, how works are screened and classified, and how to cite, reuse or correct it.</p>
</header>

<link rel="stylesheet" href="./components/about.css">

```js
import {loadJson, aboutViewModel, releaseDoi, classicUrl} from "./components/atlas.js";
import {injectIconSprite} from "./components/shared/icons.js";
import {mountAboutFlow} from "./components/about_flow.js";
injectIconSprite();
const [metadata, release, releaseFlow] = await Promise.all([
  loadJson("build_metadata.json"),
  loadJson("release.json", {optional: true}),
  loadJson("methods_flow.json", {optional: true})
]);
const snapshot = aboutViewModel(metadata, null);
const doi = releaseDoi(release);
mountAboutFlow(document.getElementById("about-flow"), metadata, releaseFlow);
```

<p class="atlas-notice" id="about-freshness">${snapshot.refreshDisplay ? html`Last refresh: <time datetime=${snapshot.refreshIso}>${snapshot.refreshDisplay}</time>` : snapshot.refreshText}</p>

<dl class="atlas-stats" id="about-stats">${snapshot.stats.map(({label, value, note}) => html`<div><dt>${label}</dt><dd>${value}</dd>${note ? html`<dd class="stat-note">${note}</dd>` : ""}</div>`)}</dl>

<section class="about-section" aria-labelledby="what-the-atlas-is">

## What the Atlas is

<p class="about-lede">A living evidence map of plastics and microplastics research connected to California. Every morning an automated pipeline collects new scholarly records and funding data and rebuilds the site, so the map grows as the field publishes. A work is included when at least one author is affiliated with California and plastic is central to it. Included works are journal articles and reviews, conference papers and abstracts, preprints, theses and dissertations, book chapters, reports and datasets. Around those works the Atlas maps the researchers and institutions involved, public monitoring observations from California waters, and plastic-related grants.</p>
</section>

```js
// NOTIFY-AB: the feed address with a copy button. Without the Clipboard API (or when it refuses),
// the address is selected so a reader can copy it from the keyboard.
const FEED_URL = "https://plastiverse.live/feed.xml";

async function copyFeedUrl(event) {
  const panel = event.currentTarget.closest(".get-updates__feed");
  const status = panel.querySelector(".get-updates__status");
  try {
    await navigator.clipboard.writeText(FEED_URL);
    status.dataset.state = "copied";
    status.textContent = "Copied";
  } catch {
    const range = document.createRange();
    range.selectNodeContents(panel.querySelector(".get-updates__address"));
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    status.dataset.state = "fallback";
    status.textContent = "Copying is not available here. The address is selected: press Ctrl+C or Cmd+C to copy it.";
  }
}

const feedAddress = html`<div class="get-updates__feed">
  <div class="get-updates__row">
    <code class="get-updates__address">${FEED_URL}</code>
    <button type="button" class="atlas-btn atlas-btn--primary get-updates__copy" onclick=${copyFeedUrl}>Copy feed link</button>
  </div>
  <p class="get-updates__status" role="status"></p>
</div>`;
```

<section class="about-section get-updates" aria-labelledby="get-updates">

## Get updates

<p class="about-lede">Every morning the pipeline adds any new California plastics papers and awards it finds. Follow the feed, get phone alerts, or both.</p>

<div class="about-grid">
<article class="about-card" style="--c: var(--atlas-task-water)">
<h3>Feed</h3>
<p>The newest papers and awards come as an Atom feed. Copy the address into a feed reader such as Feedly, Inoreader, NetNewsWire or Thunderbird. In Slack or Microsoft Teams, add an RSS app and paste the same address.</p>
${feedAddress}
</article>
<article class="about-card" style="--c: var(--atlas-task-people)">
<h3>Phone alerts</h3>
<p>When the daily update finds new papers, ntfy sends your phone one short alert that lists their titles. Days with nothing new send nothing.</p>
<ol class="get-updates__steps">
<li>Install the free ntfy app for Android or iOS.</li>
<li>In the app, add the topic <code>plastiverse-california</code>.</li>
</ol>
<div class="get-updates__actions">
<a class="atlas-btn atlas-btn--secondary" href="https://ntfy.sh" target="_blank" rel="noreferrer">Get the ntfy app</a>
<a class="atlas-btn atlas-btn--secondary" href="https://ntfy.sh/plastiverse-california" target="_blank" rel="noreferrer">Open the topic in a browser</a>
</div>
</article>
</div>

<p class="about-soon">A weekly email digest is coming soon.</p>
</section>

<section class="about-section" aria-labelledby="how-works-are-screened">

## How works are screened

<p>Each box is a stage of the pipeline; the box beside it counts what left at that stage. Nothing is deleted silently: every removal is either a rule in the public code or a recorded review decision.</p>
<div id="about-flow" class="about-flow-host"></div>
</section>

<section class="about-section" aria-labelledby="where-the-data-come-from">

## Where the data come from

<div class="about-grid">
<article class="about-card" style="--c: var(--atlas-task-water)">
<h3>OpenAlex</h3>
<p><a href="https://openalex.org/" target="_blank" rel="noreferrer">OpenAlex</a> is a free, open index of the world's research, run by the nonprofit OurResearch. It describes several hundred million scholarly works, the authors who wrote them, their institutions and their topics, and releases the data under CC0. The Atlas sends it a reviewed plastics search of titles and abstracts, limited to authors at California institutions, and reads back each work's authors, affiliations, citations and open-access status.</p>
</article>
<article class="about-card" style="--c: var(--atlas-task-people)">
<h3>ROR, ORCID and repositories</h3>
<p>The <a href="https://ror.org/" target="_blank" rel="noreferrer">Research Organization Registry (ROR)</a> gives each institution a stable identity and location, which is how affiliations are tied to California. <a href="https://orcid.org/" target="_blank" rel="noreferrer">ORCID</a> profiles add researchers' employment histories, works and public biographies. The University of California's eScholarship repository adds theses and campus deposits, and DataCite adds datasets and posters. Europe PMC is used as an independent check on what the search misses.</p>
</article>
<article class="about-card" style="--c: var(--atlas-task-money)">
<h3>Funding databases</h3>
<p>Awards come from NIH RePORTER, the NSF award search, USAspending.gov, California Sea Grant, Ocean Protection Council approvals and State Water Board grant records. Each source reports amounts on its own basis (for example, total cost for one fiscal year versus the estimated total for the whole award), so the Atlas never adds amounts across sources.</p>
</article>
<article class="about-card" style="--c: var(--atlas-task-evidence)">
<h3>Monitoring and policy</h3>
<p>Monitoring observations are published only from sources whose licence allows reuse, each with its own citation; the first is the San Francisco Bay microplastics study (5 Gyres Institute and the San Francisco Estuary Institute). Policy pages link to the Department of Toxic Substances Control and the Ocean Protection Council; those documents are paraphrased and linked, never copied.</p>
</article>
</div>
</section>

<section class="about-section" aria-labelledby="how-works-are-classified">

## How works are classified

<ol class="about-steps">
<li style="--c: var(--atlas-task-water)"><h3>1. Search</h3><p>A versioned list of terms is searched in titles and abstracts. The terms include microplastic, nanoplastic, plastic debris, marine litter, resin pellets and plastic recycling. Some terms count only in context: “microfiber” must appear near textiles, laundry or wastewater. Exclusions remove materials-science uses such as “plastic deformation” and “crystal plasticity”. The query was tuned against more than 350 works labelled by hand.</p></li>
<li style="--c: var(--atlas-task-people)"><h3>2. California test</h3><p>A work needs at least one California author. That is decided by a registered California institution, by the raw affiliation text when the registry has no match, by the author's recent California record, or by a University of California repository deposit. Each author link records which of these applied.</p></li>
<li style="--c: var(--atlas-task-money)"><h3>3. Relevance</h3><p>Keyword rules mark works where plastic is central. Works the rules cannot decide confidently are read by a language model (Claude Haiku). The maintainer's own review decisions always override the rules and the model. Chemicals in plastics form a separate, flagged tier.</p></li>
<li style="--c: var(--atlas-task-evidence)"><h3>4. Topics and study type</h3><p>Keyword rules assign topics: occurrence and monitoring, fate and transport, soil and agriculture, analytical methods, toxicity, wastewater, human exposure, air, risk assessment, the plastisphere and plastic-associated chemicals. They also assign study types. These tags are provisional screening labels, not validated classifications.</p></li>
<li style="--c: var(--atlas-task-water)"><h3>5. People and networks</h3><p>An expert is an author with at least one published California-affiliated work. Profiles that share a name and institution are merged. Career metrics come from OpenAlex. The collaboration network links experts who co-author, and clusters them with the Louvain method.</p></li>
<li style="--c: var(--atlas-task-money)"><h3>6. Funding relevance</h3><p>An award is plastic-related when its title says so or its abstract contains strong plastics terms. Weaker abstract mentions are read by a language model; the maintainer's decisions override it, and unreviewed mentions stay excluded.</p></li>
</ol>
</section>

<section class="about-section" aria-labelledby="definitions-limits-and-reuse">

## Definitions, limits and reuse

<div class="about-grid">
<article class="about-card" style="--c: var(--atlas-task-water)">
<h3>Definitions</h3>
<p><strong>Plastic-related:</strong> work about plastic debris or particles, plastic litter, microfibers, tire-wear particles, plastics recycling and alternatives, or plastic-pollution policy. Chemicals in plastics are a separately flagged tier.</p>
<p><strong>CA-led:</strong> the first author's affiliation resolves to a California institution. <strong>CA-sampled:</strong> samples were collected or monitoring was deployed on California land or in state waters. A California affiliation does not by itself mean sampling happened in California.</p>
<p>California state waters use a three-nautical-mile polygon derived from NOAA's offshore maritime-limit line and clipped through the CDFW dataset. It is not a legal depiction of maritime limits. More terms are in the <a href="./glossary">Glossary</a>.</p>
</article>
<article class="about-card about-limitations-card" style="--c: var(--atlas-vermilion)">
<h3>Limitations</h3>
<p>Plastic-related and topic labels are provisional, rule-based screening metadata. A held-out gold set is being labelled, so no validated precision or recall is available yet. Provisional labels are not a pollution leaderboard; confirm the linked source work before drawing conclusions.</p>
<p>OpenAlex coverage and affiliation records may be incomplete or incorrect, and author profiles can split one person's works or combine different people. An institution's location does not identify where a study sampled.</p>
<p>The refresh time is when the site's data were last rebuilt, not when each source record was last updated.</p>
</article>
<article class="about-card about-citation-card" style="--c: var(--atlas-task-money)">
<h3 id="how-to-cite">How to cite</h3>
${doi
  ? html`<p>Coffin, S. (${String(release.date || "").slice(0, 4)}). <cite>CA Plastics Research Atlas</cite> (${String(release.version || "")}) [Data set and software]. Zenodo. <a href="https://doi.org/${doi}" target="_blank" rel="noreferrer">https://doi.org/${doi}</a></p>`
  : html`<p>Coffin, S. <cite>CA Plastics Research Atlas</cite> [Data set and software]. Zenodo.</p>`}
<p>To cite every version at once, use the concept DOI <a href="https://doi.org/10.5281/zenodo.24124016" target="_blank" rel="noreferrer">10.5281/zenodo.24124016</a>, which always resolves to the latest release. Each release holds the methods card, Parquet files and checksums.</p>
</article>
<article class="about-card" style="--c: var(--atlas-task-evidence)">
<h3>Licence</h3>
<p>Data produced by the Atlas (the files behind these pages, the feed and the release snapshots) are shared under the <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noreferrer">Creative Commons Attribution 4.0 licence (CC BY 4.0)</a>: you may reuse them, including commercially, if you credit the Atlas. The code is under the <a href="https://opensource.org/license/mit" target="_blank" rel="noreferrer">MIT licence</a>. Third-party material keeps its own terms: bibliographic metadata comes from OpenAlex (CC0), and each monitoring observation carries its source's licence and citation.</p>
</article>
<article class="about-card" style="--c: var(--atlas-task-people)">
<h3>Corrections and source work</h3>
<p>For a correction or profile-removal request, <a href="mailto:theplastiverse@gmail.com?subject=Atlas%20data%20correction" rel="external">email theplastiverse@gmail.com</a>. Include the OpenAlex ID, DOI or source URL when available, the field in question, and the proposed correction. Requests are acknowledged and acted on within 5 to 10 business days; a removed person or work is also excluded at the next ingest. The project does not alter the upstream OpenAlex record.</p>
</article>
<article class="about-card" style="--c: var(--atlas-task-water)">
<h3>Methods and pipeline health</h3>
<p><a href="https://doi.org/10.5281/zenodo.24124016" target="_blank" rel="noreferrer">Methods, data files and checksums are in each archived release</a> (concept DOI 10.5281/zenodo.24124016).</p>
${html`<p>Pipeline health: <a href="${classicUrl("status.html")}">run status and drift alarms</a>. <a href="${classicUrl("feed.xml")}" type="application/atom+xml">Subscribe (Atom feed)</a>.</p>`}
</article>
</div>
</section>

<p class="about-credit">Created by <a href="https://scottcoff.in" target="_blank" rel="noreferrer">Scott Coffin</a>.</p>
