---
title: Glossary
---

<header class="atlas-page-head">
<p class="atlas-page-head__eyebrow"><svg class="icon" viewBox="0 0 24 24" focusable="false" aria-hidden="true"><use href="#i-book"></use></svg> Reference</p>
<h1>Glossary</h1>
<p class="atlas-page-head__lead">Plain-language meanings of the terms used on the Authors, Institutions and Monitoring pages. Each entry names where its wording comes from.</p>
</header>

<link rel="stylesheet" href="../components/glossary.css">

<dl class="glossary">

<dt id="author"><a class="glossary-term-link" href="#author"><strong>Author</strong></a></dt>
<dd>
<p>A person listed on one or more works in the corpus, as identified by OpenAlex author IDs; profiles may split or merge people.</p>
<p><small>Source: OpenAlex author records, with the Atlas's same-name, same-institution merges.</small></p>
</dd>

<dt id="access-tiers"><a class="glossary-term-link" href="#access-tiers"><strong>Access tiers A–D</strong></a></dt>
<dd>
<p>Each monitoring source is placed in one tier that describes how its data can be reached and what kind of evidence it is. Tier A: the source page identifies public data or a download. Tier B: a documented program or dataset whose export, subset or licence still needs review. Tier C: reporting or future sources with no confirmed public observation endpoint. Tier D: evidence taken from literature or reports rather than from a data source. Tiers describe access and evidence, not data quality.</p>
<p><small>Source: the Atlas's monitoring source registry rules.</small></p>
</dd>

<dt id="tier"><a class="glossary-term-link" href="#tier"><strong>Tier (institutions)</strong></a></dt>
<dd>
<p>A group of California institutions whose rank ranges overlap, so their order cannot be reliably told apart. Tier 1 starts with the leading institution. Each next institution joins the current tier while its lower rank bound is at most the tier leader's upper rank bound; otherwise it starts a new tier and becomes the leader. Within a tier, institutions are sorted by fractional works. Tiers are not a quality grade.</p>
<p><small>Source: Methods (institution counts and stability).</small></p>
</dd>

<dt id="fractional-works"><a class="glossary-term-link" href="#fractional-works"><strong>Fractional works</strong></a></dt>
<dd>
<p>A credit count in which each work counts as 1, split across the institutions of its authors. The work's weight is split equally among its distinct authors. Each author's share is then split equally among that author's distinct institutions on the work. For example, if 2 of 5 authors are affiliated only with institution A, institution A receives 0.4. Authors with no listed institution go to an <code>unaffiliated</code> bucket, so each work's weights sum to 1.</p>
<p><small>Source: Methods (institution counts and stability).</small></p>
</dd>

<dt id="bootstrap-interval"><a class="glossary-term-link" href="#bootstrap-interval"><strong>Bootstrap interval</strong></a></dt>
<dd>
<p>The range of values an institution's fractional works and rank could plausibly take if the set of works were slightly different. It is made by resampling the works with replacement 1,000 times (fixed random seed) and taking the 95% percentile range of the results. If the interval would exclude the point estimate, it is widened to include it and flagged. An institution whose rank interval overlaps the neighbour above or below is marked "not distinguishable" from that neighbour.</p>
<p><small>Source: Methods (institution counts and stability).</small></p>
</dd>

<dt id="rank-range"><a class="glossary-term-link" href="#rank-range"><strong>Rank range</strong></a></dt>
<dd>
<p>The bootstrap interval for an institution's position among the top 200 California institutions by fractional works. It is shown as "rank 3" when the lower and upper bounds are the same, and as "ranks 3–7" otherwise. Rankings use California institutions only; collaborators outside California keep their shares but are not ranked.</p>
<p><small>Source: Methods (institution counts and stability).</small></p>
</dd>

<dt id="rising-percentile"><a class="glossary-term-link" href="#rising-percentile"><strong>Rising percentile and its population</strong></a></dt>
<dd>
<p>Rising citation momentum measures whether an author's share of all Atlas authors' plastics citations is growing. It is the slope of that share over the last 5 complete years, in percentage points per year, so growth in the field as a whole does not count as rising. The rising percentile is the author's rank within that population. Its population is the scored authors: those with at least 10 plastics citations in the 5-year window. Authors below that threshold have no rising percentile.</p>
<p><small>Source: the Atlas's author metrics method. Wording to be confirmed.</small></p>
</dd>

<dt id="m-quotient"><a class="glossary-term-link" href="#m-quotient"><strong>m-quotient</strong></a></dt>
<dd>
<p>An h-index adjusted for career length: the h-index divided by the number of years since the first publication year (at least 1 year). The first year is the earliest year with at least 2 works, so isolated early works that are probably misattributed are skipped. A higher value means more citation impact per year of career. It is shown on the Authors page as "m-quotient (h per career year)".</p>
<p><small>Source: the Atlas's author metrics method. Wording to be confirmed.</small></p>
</dd>

<dt id="current-affiliation"><a class="glossary-term-link" href="#current-affiliation"><strong>Current affiliation</strong></a></dt>
<dd>
<p>The author's latest OpenAlex affiliations, the institutions listed on their most recent affiliation record. "In California now" means at least one of them is in the Atlas's California institution registry. "Outside California now" means none of them is. "Unknown" means OpenAlex lists no latest affiliation for the author. The "last California affiliation" year is the latest year OpenAlex lists the author at a California institution. Where the author lives or where their work was done is not checked.</p>
<p><small>Source: the Atlas's author metrics method and California institution registry.</small></p>
</dd>

<dt id="ca-led"><a class="glossary-term-link" href="#ca-led"><strong>CA-led</strong></a></dt>
<dd>
<p>The first author's affiliation resolves to a California institution.</p>
<p><small>Source: About, Definitions.</small></p>
</dd>

<dt id="ca-sampled"><a class="glossary-term-link" href="#ca-sampled"><strong>CA-sampled</strong></a></dt>
<dd>
<p>Sample collection or deployed monitoring took place in California land or state waters. A California affiliation does not by itself mean that sampling happened in California.</p>
<p><small>Source: About, Definitions.</small></p>
</dd>

<dt id="state-waters"><a class="glossary-term-link" href="#state-waters"><strong>California state waters</strong></a></dt>
<dd>
<p>The area used to decide whether a sample was taken in state waters. It is a three-nautical-mile polygon derived from NOAA's offshore maritime-limit line and clipped through the CDFW dataset. It is not a legal depiction of maritime limits.</p>
<p><small>Source: About, Definitions.</small></p>
</dd>

<dt id="matrix"><a class="glossary-term-link" href="#matrix"><strong>Matrix</strong></a></dt>
<dd>
<p>The kind of material a monitoring sample was taken from, such as surface water, sediment, stormwater or organism tissue. Concentrations measured in different matrices are not directly comparable. On the Authors page, a “domain or matrix tag” is a different, provisional topic tag taken from work titles and abstracts.</p>
<p><small>Source: standard usage in environmental monitoring. Wording to be confirmed.</small></p>
</dd>

<dt id="plastic-related"><a class="glossary-term-link" href="#plastic-related"><strong>Plastic-related</strong></a></dt>
<dd>
<p>A work about plastic debris or particles, plastic litter, microfibers, tire-wear particles, or plastic-pollution policy. Studies of chemicals associated with plastics are kept as an auxiliary topic (see <a href="#plastic-associated-chemicals">Plastic-associated chemicals</a>). Plastic-related and topic labels are provisional, rule-based screening metadata; a held-out gold set and evaluation are later work, so no validated precision or recall is available yet.</p>
<p><small>Source: About, Definitions and Limitations.</small></p>
</dd>

<dt id="plastic-associated-chemicals"><a class="glossary-term-link" href="#plastic-associated-chemicals"><strong>Plastic-associated chemicals (auxiliary topic)</strong></a></dt>
<dd>
<p>Studies of chemicals that come from or travel with plastics, such as bisphenol A (BPA), phthalates, plastic additives and the tire chemical 6PPD, that the search found through those chemical names rather than through plastics terms. They stay in the Atlas and carry this topic tag, shown with a dashed, grey-hatched chip. They are auxiliary: the Atlas searches for plastics terms, so its coverage of these chemical studies (much of it exposure and health research) is far less complete than its coverage of studies of plastic particles and debris. Do not read their counts as the size of California research on these chemicals.</p>
<p><small>Source: owner scope decision, 13 November 2026; the search's chemicals-in-plastics terms.</small></p>
</dd>

<dt id="licences"><a class="glossary-term-link" href="#licences"><strong>Licences</strong></a></dt>
<dd>
<p>The reuse terms recorded for each monitoring source or sample. Plain-language glosses used on the Monitoring page:</p>
<ul>
<li><strong>CC-BY-4.0</strong>: Creative Commons Attribution 4.0. Reuse, including commercial, with credit to the source.</li>
<li><strong>ODC-BY</strong>: Open Data Commons Attribution. Reuse with credit.</li>
<li><strong>CC0-1.0</strong>: Public-domain dedication. Reuse with no conditions; credit is requested, not required.</li>
<li><strong>fair-use-factual-values</strong>: Factual values reported in a publication, shown under fair use. Reuse terms for the underlying dataset are not recorded; check the source.</li>
<li><strong>Not recorded</strong>: reuse terms are not recorded; check the source.</li>
</ul>
<p><small>Source: the Monitoring page's licence notes. These are summaries; check the licence text before relying on them for reuse decisions.</small></p>
</dd>

<dt id="two-year-mean-citedness"><a class="glossary-term-link" href="#two-year-mean-citedness"><strong>2-yr mean citedness</strong></a></dt>
<dd>
<p>The average number of citations received this year by a journal's works from the two previous years. OpenAlex publishes it for each source as the two-year mean citedness. It is the open analogue of the impact factor. Clarivate's Journal Impact Factor is proprietary and is not used here. The Evidence map labels the column "2-yr mean citedness (OpenAlex)". It describes a journal as a whole, not any one paper, and it counts citations rather than quality. A blank value means OpenAlex has no figure for that journal, or its OpenAlex record is a different venue, so no figure is shown.</p>
<p><small>Source: OpenAlex source summary statistics, refreshed by the Atlas's data pipeline.</small></p>
</dd>

<dt id="corporate-imperialism"><a class="glossary-term-link" href="#corporate-imperialism"><strong>Corporate imperialism</strong></a></dt>
<dd>
<p>A neoliberal trend in which companies expand across national borders, shaping how goods are produced and consumed and influencing government policy.</p>
<p><small>Source: <a href="https://doi.org/10.1016/j.marpol.2024.106078">Peryman et al. 2024</a>.</small></p>
</dd>

<dt id="deficit-model-of-knowledge"><a class="glossary-term-link" href="#deficit-model-of-knowledge"><strong>Deficit model of knowledge</strong></a></dt>
<dd>
<p>A view that treats specialists as the authority and blames poor public decisions mainly on a shortage of information.</p>
<p><small>Source: <a href="https://www.ncbi.nlm.nih.gov/books/NBK582037/">Foellmer et al. 2022</a>.</small></p>
</dd>

<dt id="descriptive-vs-prescriptive-norms"><a class="glossary-term-link" href="#descriptive-vs-prescriptive-norms"><strong>Descriptive vs prescriptive norms</strong></a></dt>
<dd>
<p>Descriptive norms are what people commonly do and accept. Prescriptive norms are what people judge to be the acceptable or right thing to do.</p>
<p><small>Source: <a href="https://www.ncbi.nlm.nih.gov/books/NBK582037/">Foellmer et al. 2022</a>.</small></p>
</dd>

<dt id="environmental-justice"><a class="glossary-term-link" href="#environmental-justice"><strong>Environmental justice</strong></a></dt>
<dd>
<p>In the US Environmental Protection Agency's definition, no group, whatever its race, colour, national origin or income, should bear environmental harms unfairly, and everyone should be able to take a real part in environmental decisions.</p>
<p><small>Source: <a href="https://19january2017snapshot.epa.gov/environmentaljustice/learn-about-environmental-justice_.html">US EPA, archived page (2017 snapshot)</a>.</small></p>
</dd>

<dt id="extended-producer-responsibility"><a class="glossary-term-link" href="#extended-producer-responsibility"><strong>Extended producer responsibility (EPR)</strong></a></dt>
<dd>
<p>A policy approach that makes producers responsible, financially, physically or both, for their products after they have been used or discarded.</p>
<p><small>Source: <a href="https://doi.org/10.1787/9789264256385-en">OECD 2016</a>, Extended Producer Responsibility: Updated Guidance for Efficient Waste Management.</small></p>
</dd>

<dt id="garbage-patch"><a class="glossary-term-link" href="#garbage-patch"><strong>Garbage patch</strong></a></dt>
<dd>
<p>An area of ocean where rotating currents, called gyres, gather floating debris. It is not a solid island of trash, because much of the debris is spread through the water below the surface.</p>
<p><small>Source: <a href="https://marinedebris.noaa.gov/info/patch.html">NOAA Marine Debris Program</a>.</small></p>
</dd>

<dt id="mnps"><a class="glossary-term-link" href="#mnps"><strong>MNPs (micro- and nanoplastics)</strong></a></dt>
<dd>
<p>Plastic particles in the micrometre and nanometre size ranges. Where the line between micro-, nano- and larger plastics falls depends on the source, so see the size note under <a href="#nanoplastic-size-conventions">Nanoplastic size conventions</a>.</p>
<p><small>Source: the Atlas's own usage; the size note is linked above.</small></p>
</dd>

<dt id="nanoplastic-size-conventions"><a class="glossary-term-link" href="#nanoplastic-size-conventions"><strong>Nanoplastic size conventions</strong></a></dt>
<dd>
<p>Environmental and toxicology studies often treat particles smaller than 1 µm as nanoplastics. Nanomaterials research often uses a much smaller limit, below 100 nm.</p>
<p><small>Source: <a href="https://doi.org/10.1016/j.jhazmat.2026.144102">Ortiz-Balsero et al. 2026</a>.</small></p>
</dd>

<dt id="safe-and-sustainable-by-design"><a class="glossary-term-link" href="#safe-and-sustainable-by-design"><strong>Safe and sustainable by design (SSbD)</strong></a></dt>
<dd>
<p>An optional European Union approach to developing chemicals and materials that are safe and sustainable over their full life cycle, including a way to assess them.</p>
<p><small>Source: <a href="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022H2510">Commission Recommendation (EU) 2022/2510 of 8 December 2022</a>.</small></p>
</dd>

<dt id="scalar-mismatch"><a class="glossary-term-link" href="#scalar-mismatch"><strong>Scalar mismatch</strong></a></dt>
<dd>
<p>The condition in which a problem and the responses to it operate at different sizes or levels.</p>
<p><small>Source: <a href="https://www.ncbi.nlm.nih.gov/books/NBK582037/">Foellmer et al. 2022</a>.</small></p>
</dd>

<dt id="scoping-review"><a class="glossary-term-link" href="#scoping-review"><strong>Scoping review</strong></a></dt>
<dd>
<p>A review design that maps how much research exists on a topic and what kinds of studies it contains, usually without pooling the results statistically.</p>
<p><small>Source: the Atlas's plain-language definition.</small></p>
</dd>

<dt id="slow-violence"><a class="glossary-term-link" href="#slow-violence"><strong>Slow violence</strong></a></dt>
<dd>
<p>Environmental harm that builds up over years and across distances, and that is easy to overlook because it is seldom seen as violence.</p>
<p><small>Source: Nixon 2011, <em>Slow Violence and the Environmentalism of the Poor</em>, Harvard University Press, p. 2.</small></p>
</dd>

<dt id="systematic-evidence-map"><a class="glossary-term-link" href="#systematic-evidence-map"><strong>Systematic evidence map</strong></a></dt>
<dd>
<p>A review design that charts the research on a topic in a structured set of categories, showing where evidence is dense and where it is missing, without pooling the results.</p>
<p><small>Source: <a href="https://doi.org/10.1002/cl2.1402">Campbell et al. 2024</a>, a review protocol on methods for evidence and gap maps.</small></p>
</dd>

<dt id="umbrella-review"><a class="glossary-term-link" href="#umbrella-review"><strong>Umbrella review</strong></a></dt>
<dd>
<p>A review design that gathers and compares the findings of existing systematic reviews on a topic, rather than those of individual studies.</p>
<p><small>Source: the Atlas's plain-language definition.</small></p>
</dd>

<dt id="waste-as-a-dynamic-social-construction"><a class="glossary-term-link" href="#waste-as-a-dynamic-social-construction"><strong>Waste as a dynamic social construction</strong></a></dt>
<dd>
<p>The view that how people perceive waste, and how waste is defined, varies with social and cultural context.</p>
<p><small>Source: <a href="https://www.ncbi.nlm.nih.gov/books/NBK582037/">Foellmer et al. 2022</a>.</small></p>
</dd>

<dt id="waste-colonialism"><a class="glossary-term-link" href="#waste-colonialism"><strong>Waste colonialism</strong></a></dt>
<dd>
<p>In its first sense, the movement of waste from higher-income to lower-income countries, with the Basel Convention (1989) and the Bamako Convention (1991) as its starting points. In a second sense, the term is also applied to how plastic pollution science itself is carried out.</p>
<p>See also <a href="https://discardstudies.com/">Discard Studies</a>.</p>
<p><small>Source: <a href="https://doi.org/10.1016/j.marpol.2024.106078">Peryman et al. 2024</a> (working definition); <a href="https://www.basel.int/">Basel Convention</a>.</small></p>
</dd>

<dt id="waste-trade"><a class="glossary-term-link" href="#waste-trade"><strong>Waste trade</strong></a></dt>
<dd>
<p>Trade in waste across national borders, including plastic scrap. The Basel Convention's plastic waste amendments extend its controls on transboundary movement to more kinds of plastic waste.</p>
<p><small>Source: <a href="https://www.basel.int/">Basel Convention</a>.</small></p>
</dd>

</dl>

```js
import {injectIconSprite} from "../components/shared/icons.js";
injectIconSprite();
```
