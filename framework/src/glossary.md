---
title: Glossary
---

# Glossary

<p class="panel-intro">Plain-language meanings of the terms used on the Experts, Institutions and Monitoring pages. Each entry names where its wording comes from.</p>

<dl class="glossary">

<dt id="access-tiers"><strong>Access tiers A–D</strong></dt>
<dd>
<p>Each monitoring source is placed in one tier that describes how its data can be reached and what kind of evidence it is. Tier A: the source page identifies public data or a download. Tier B: a documented program or dataset whose export, subset or licence still needs review. Tier C: reporting or future sources with no confirmed public observation endpoint. Tier D: evidence taken from literature or reports rather than from a data source. Tiers describe access and evidence, not data quality.</p>
<p><small>Source: the Atlas's monitoring source registry rules.</small></p>
</dd>

<dt id="tier"><strong>Tier (institutions)</strong></dt>
<dd>
<p>A group of California institutions whose rank ranges overlap, so their order cannot be reliably told apart. Tier 1 starts with the leading institution. Each next institution joins the current tier while its lower rank bound is at most the tier leader's upper rank bound; otherwise it starts a new tier and becomes the leader. Within a tier, institutions are sorted by fractional works. Tiers are not a quality grade.</p>
<p><small>Source: Methods (institution counts and stability).</small></p>
</dd>

<dt id="fractional-works"><strong>Fractional works</strong></dt>
<dd>
<p>A credit count in which each work counts as 1, split across the institutions of its authors. The work's weight is split equally among its distinct authors. Each author's share is then split equally among that author's distinct institutions on the work. For example, if 2 of 5 authors are affiliated only with institution A, institution A receives 0.4. Authors with no listed institution go to an <code>unaffiliated</code> bucket, so each work's weights sum to 1.</p>
<p><small>Source: Methods (institution counts and stability).</small></p>
</dd>

<dt id="bootstrap-interval"><strong>Bootstrap interval</strong></dt>
<dd>
<p>The range of values an institution's fractional works and rank could plausibly take if the set of works were slightly different. It is made by resampling the works with replacement 1,000 times (fixed random seed) and taking the 95% percentile range of the results. If the interval would exclude the point estimate, it is widened to include it and flagged. An institution whose rank interval overlaps the neighbour above or below is marked "not distinguishable" from that neighbour.</p>
<p><small>Source: Methods (institution counts and stability).</small></p>
</dd>

<dt id="rank-range"><strong>Rank range</strong></dt>
<dd>
<p>The bootstrap interval for an institution's position among the top 200 California institutions by fractional works. It is shown as "rank 3" when the lower and upper bounds are the same, and as "ranks 3–7" otherwise. Rankings use California institutions only; collaborators outside California keep their shares but are not ranked.</p>
<p><small>Source: Methods (institution counts and stability).</small></p>
</dd>

<dt id="rising-percentile"><strong>Rising percentile and its population</strong></dt>
<dd>
<p>Rising citation momentum measures whether an expert's share of all Atlas experts' plastics citations is growing. It is the slope of that share over the last 5 complete years, in percentage points per year, so growth in the field as a whole does not count as rising. The rising percentile is the expert's rank within that population. Its population is the scored experts: those with at least 10 plastics citations in the 5-year window. Experts below that threshold have no rising percentile.</p>
<p><small>Source: the Atlas's expert metrics method. Wording to be confirmed.</small></p>
</dd>

<dt id="m-quotient"><strong>m-quotient</strong></dt>
<dd>
<p>An h-index adjusted for career length: the h-index divided by the number of years since the first publication year (at least 1 year). The first year is the earliest year with at least 2 works, so isolated early works that are probably misattributed are skipped. A higher value means more citation impact per year of career. It is shown on the Experts page as "m-quotient (h per career year)".</p>
<p><small>Source: the Atlas's expert metrics method. Wording to be confirmed.</small></p>
</dd>

<dt id="current-affiliation"><strong>Current affiliation</strong></dt>
<dd>
<p>The expert's latest OpenAlex affiliations, the institutions listed on their most recent affiliation record. "In California now" means at least one of them is in the Atlas's California institution registry. "Outside California now" means none of them is. "Unknown" means OpenAlex lists no latest affiliation for the expert. The "last California affiliation" year is the latest year OpenAlex lists the expert at a California institution. Where the expert lives or where their work was done is not checked.</p>
<p><small>Source: the Atlas's expert metrics method and California institution registry.</small></p>
</dd>

<dt id="ca-led"><strong>CA-led</strong></dt>
<dd>
<p>The first author's affiliation resolves to a California institution.</p>
<p><small>Source: About, Definitions.</small></p>
</dd>

<dt id="ca-sampled"><strong>CA-sampled</strong></dt>
<dd>
<p>Sample collection or deployed monitoring took place in California land or state waters. A California affiliation does not by itself mean that sampling happened in California.</p>
<p><small>Source: About, Definitions.</small></p>
</dd>

<dt id="state-waters"><strong>California state waters</strong></dt>
<dd>
<p>The area used to decide whether a sample was taken in state waters. It is a three-nautical-mile polygon derived from NOAA's offshore maritime-limit line and clipped through the CDFW dataset. It is not a legal depiction of maritime limits.</p>
<p><small>Source: About, Definitions.</small></p>
</dd>

<dt id="matrix"><strong>Matrix</strong></dt>
<dd>
<p>The kind of material a monitoring sample was taken from, such as surface water, sediment, stormwater or organism tissue. Concentrations measured in different matrices are not directly comparable. On the Experts page, a “domain or matrix tag” is a different, provisional topic tag taken from work titles and abstracts.</p>
<p><small>Source: standard usage in environmental monitoring. Wording to be confirmed.</small></p>
</dd>

<dt id="plastic-related"><strong>Plastic-related</strong></dt>
<dd>
<p>A work about plastic debris or particles, plastic litter, microfibers, tire-wear particles, or plastic-pollution policy. Chemicals in plastics are a separately flagged Tier 2 scope. Plastic-related and topic labels are provisional, rule-based screening metadata; a held-out gold set and evaluation are later work, so no validated precision or recall is available yet.</p>
<p><small>Source: About, Definitions and Limitations.</small></p>
</dd>

<dt id="licences"><strong>Licences</strong></dt>
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

</dl>
