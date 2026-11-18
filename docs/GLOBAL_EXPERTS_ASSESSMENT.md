# Global expert profiles at $0: assessment (2026-11-18)

Owner request (2026-11-18): bring the California expert profiles (all their features and data) to the
global scope eventually, and evaluate first what it takes, keeping the site at $0.
Audience: the owner. Status: assessment only. Nothing has been built.

## Short answer

Yes, it can run at $0, but not as a copy of the California pipeline. California works because it is
small: 2,649 experts, 25 MB of per-expert files committed to git, and owner review of edge cases. The global
scale is about 100 to 200 times larger, so five things must change.

1. **Ingest once, partition locally (PLAT-4) comes first.** The global works pull lists every author on
   every plastics work for about 7,000 OpenAlex credits once (USD 0.70), then 10 to 20 credits a day.
   Every per-expert number we can compute locally from those works is free.
2. **Only career metrics need extra calls.** They come from batch `/authors` calls: 100 authors per list
   call at USD 0.0001, so about 4,000 credits per full refresh. California's per-author plastics query
   calls are not needed globally: the global corpus already is each author's whole plastics record.
3. **Per-expert files live on Cloudflare R2, not GitHub Pages or git.** Pages caps a site at 1 GB, and git
   should not carry hundreds of thousands of changing files. R2's free tier (10 GB of storage, 1 M writes and
   10 M reads a month, free egress) fits if the files are sharded so that a full monthly rewrite is thousands
   of writes, not hundreds of thousands.
4. **Profiles come in tiers.** Every author gets a light record. A full profile goes to authors above a
   threshold the owner sets (for example 3 or more plastics works). Static SEO pages go only to the top N
   that fit the Pages budget.
5. **No paid automation.** California uses the Claude API (Haiku) to screen works the rules cannot decide,
   and owner review for photos and author merges. Globally that becomes rules plus measured precision, the
   OpenAlex author records as they are, and a correction or opt-out link. Owner review stays for curated
   regions.

## Scale (estimates until PLAT-4 measures them)

| Quantity | California today | Global estimate | Basis |
|---|---|---|---|
| Plastics works | 1,918 published (2,036 in the corpus) | 134,801 | OpenAlex count under the active query, 2026-11-18 |
| Distinct authors on those works | 9,148 (all authors on CA works) | about 300,000 to 500,000 | California has 4.5 distinct authors per work; authors repeat more across a larger corpus |
| Authors with 3 or more plastics works | n/a | about 50,000 to 100,000 | heavy-tailed authorship; to be measured |
| Per-expert JSON | 7.3 KB mean, 5.1 KB median, 25 MB total | 2 to 4 GB for every author; 0.4 to 0.8 GB above the threshold | California file sizes times the counts above |

The global ingest (PLAT-4) yields the exact author list and works-per-author distribution at no extra cost.
Every number above is replaced by a measurement before any design choice depends on it.

## Feature by feature

| California profile feature | California source | Global source | Cost | Verdict |
|---|---|---|---|---|
| Name, affiliations, ORCID, works list with DOIs | Works corpus + `/authors` | Global corpus + batch `/authors` | ~4,000 credits/refresh | Yes |
| Career metrics (citations, h-index, i10, works count) | `/authors` list calls | Same, batched | Included above | Yes |
| Plastics citations per year, plastics works count | Per-author query calls (10 credits/page) | Computed locally from the global corpus | 0 | Yes, cheaper than California |
| Primary and own affiliation history | Author record + works | Same | Included | Yes |
| m-quotient, rising score | Works-by-year per author (1 credit/author) | Approximate from `/authors` `counts_by_year` (last 10 years), or exact for experts above the threshold (1 credit each, one-off) | 0, or 50k to 100k credits spread over 1 to 2 weeks | Yes with a threshold |
| Topics, expertise sentence | Corpus labels | Same rules on the global corpus | 0 | Yes; precision of the global query must be measured first |
| Co-authors, co-author institutions, network | Local | Local; network served per country or community slice | 0 | Yes |
| Funding badge | US federal and California sources matched to people | OpenAlex funder and award acknowledgements on the works themselves; regional grant adapters (CORDIS, UKRI, NIH, NSF) later for curated regions | 0 | Partly: "funded by" from acknowledgements, not grant-to-person matching |
| Data steward badge (datasets) | DataCite by ORCID | Same (free API) | 0 credits; hours of polite requests, spread across days | Yes, for authors with ORCID |
| ORCID bio, keywords, links | ORCID public API | Same, about 40% of authors have ORCID; 30-day cache | 0; about 6 hours of requests at 8/s for 160,000 records, spread over days | Yes |
| Photos | Wikidata, shown only after owner approval | Wikidata licensed images shown automatically with credit, or no photos outside curated regions | 0 | Owner decision |
| Research network badges (Land to Sea) | Curated YAML | Curated, curated regions only | 0 | Regional only |
| Expert search | One `search_index.json` | Sharded index on R2 (per country and by name prefix) | 0 | Yes |
| Static SEO page per expert | 2,614 pages on Pages | Top N only (about 20,000 pages, about 150 MB, inside the 1 GB Pages cap); the rest render client-side | 0 | Yes for the top N |

## Free-tier budgets (checked 2026-11-18 against provider pages)

| Resource | Free limit | Global experts would use | Fits? |
|---|---|---|---|
| OpenAlex free key | USD 1/day; list call USD 0.0001; search call USD 0.001; single lookup free; quarterly snapshot free | Backfill USD 0.70 once; daily works 10 to 20 credits; author refresh 4,000 credits/month (about 130/day); existing California and landing jobs | Yes; stays far below 10,000 credits a day. The free alternate key covers bursts |
| GitHub Pages | 1 GB site, 100 GB/month soft bandwidth, 10-minute deploy | California about 70 MB + top-N SEO pages about 150 MB | Yes, with top N only |
| Git repository | 1 GB recommended | Must not hold global per-expert files or global normalized tables | Yes, if those go to R2 and the Actions cache |
| GitHub Actions (public repo) | Free; 6 hours per job; 20 concurrent jobs; 10 GB cache per repo | Daily global rebuild estimated 20 to 40 minutes; ORCID and DataCite batches spread across days | Yes |
| Cloudflare R2 | 10 GB-month storage; 1 M Class A (writes, lists) and 10 M Class B (reads) a month; egress free | 0.5 to 4 GB stored; daily changed shards plus one monthly full rewrite in sharded files (about 16,000 objects); reads = profile views | Yes, only if sharded and written incrementally. Rewriting 400,000 single files monthly would exceed the 1 M writes |

Not verified: the size of the OpenAlex snapshot, and the RAM and disk of the public-repo Linux runner.
Both matter only if we switch the backfill to the snapshot or build the full global network in one job.

## Proposed plan (tasks, in order)

- **GX-0 (prerequisite): PLAT-3 region abstraction and PLAT-4 global ingest.** One OpenAlex query with no
  geographic filter, partitioned locally. This gives exact author counts, works per author and all
  co-author links.
- **GX-1 Measure and decide.**
  - Works-per-author distribution.
  - A labelled precision sample of the global query: the owner labels about 200 works in a Streamlit review app.
  - The owner then chooses the full-profile threshold and the top N for SEO pages.
- **GX-2 Author records.** Batch `/authors` refresh, monthly and incremental (about 4,000 credits).
  - Local plastics metrics.
  - Optional exact career start for experts above the threshold.
- **GX-3 Publish to R2.** Sharded per-expert files, a manifest of shard hashes, and writes only for changed
  shards. A sharded search index. The owner adds an R2 write token as a repository secret.
- **GX-4 One expert page for every scope.** Make `california/expert.html` region-agnostic: it reads a
  California file or an R2 shard. California keeps its extra badges. `/explore` gets an Experts list that
  opens it.
- **GX-5 SEO pages for the top N, inside the Pages budget.** Person JSON-LD, sitemap shards and the opt-out list.
- **GX-6 Free enrichment.** ORCID bios and links, DataCite datasets and OpenAlex funder acknowledgements,
  each cached and spread across days. Photos as the owner decides.
- **GX-7 Collaboration network slices.** Per country and per community, built locally.

## What the owner needs to decide (before GX-1)

1. Full-profile threshold: 3 or more plastics works (default), or another rule (for example 2 or more in the
   last 5 years).
2. SEO pages: top 20,000 experts by plastics works (default), or none outside curated regions.
3. Photos outside curated regions: none (default), or licensed Wikidata images shown automatically with credit.
4. Outside curated regions, accept OpenAlex author records as they are, without manual merges, with a
   visible "report an error" link and the existing opt-out (default yes).
5. An R2 write token (owner action, about 10 minutes) when GX-3 starts.

## Risks

- **Global query precision is unknown.** Recent samples include off-topic titles. Expert topics and
  rankings inherit the noise until GX-1 measures it and the rules are tightened.
- **OpenAlex author disambiguation.** Split and merged authors are more visible at scale. California fixes
  them by hand (`curation/author_attach.csv`); the global set cannot.
- **Living people at scale.** Opt-out and suppression must apply to every surface the same day. Emails are
  never published (existing rule).
- **Free tiers can change.** OpenAlex moved to paid plans in 2026. Keep every job budget-guarded and cached
  so that a lost tier degrades freshness, not the site.
