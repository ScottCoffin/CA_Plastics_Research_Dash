# Region pages (REG-1): Norway and Belgium

Owner request 2026-11-25: collaborators in Norway and Belgium want to help, so both get a region page now, in the
global Plastiverse Live theme, built from the global corpus. Anything local that a local expert has not confirmed
is shown as a clearly marked placeholder. One shared component renders every region; the front end never branches
on the region (docs/PLATFORM_ARCHITECTURE.md section 4).

## Files

| File | Written by | Purpose |
|---|---|---|
| `regions/_registry.yml` | hand | entries `norway` (NO) and `belgium` (BE): tier A, status `planned`, predicate `country_codes`, `site_data_dir` |
| `regions/<slug>/region.yml` | hand, then local experts | display name, languages, local search terms, and the placeholder sections below; each item has a `status` |
| `site/data/<slug>/region.json` | `scripts/build_region_pages.py [--check]` | the page payload (schema below) |
| `framework/src/<slug>/index.md` | hand (thin) | mounts the shared component with the slug |
| `framework/src/components/region_page.{js,css}` | hand | the shared region page |

## `region.json` (schema `region-v1`)

```
schema_version  "region-v1"
generated_at, slug, name, iso, status ("in_preparation"), screening_status ("unscreened_query_hit")
what_this_is_and_is_not  {is, is_not}      plain language; says the figures are unscreened query hits
stats            {works_total, first_year, last_complete_year, works_with_pmid}
works_by_year    [{year, count, partial}]  same series as countries.json for the ISO code
top_topics       [{id, name, count}]       10
top_institutions [{id, name, ror, type, works}]   15, from authorships with that country
top_researchers  [{id, name, works}]       15, by works with an authorship in the country (public OpenAlex names;
                                           owner green-lit global author names 2026-11-25); no emails or contacts
partner_countries [{iso, name, works}]     10 countries most often co-authoring
sections         [{id, title, status, summary, items: [{name, url, kind, status, note}], needs}]
                 from region.yml; status is "placeholder" | "draft" | "confirmed"; `needs` says what a local
                 expert should confirm
ambassadors      {status: "recruiting", url: "/ambassadors"}
```

Section ids, in page order: `funding`, `monitoring`, `policy`, `research_networks`, `local_terms`, `geography`.

## Placeholder rule

Every candidate source starts as `status: to_confirm` and renders with a visible "To be confirmed by a local
expert" badge and a link to the ambassadors page. Nothing local is presented as verified until a collaborator
changes its status in `region.yml` (AMB-1 designs how confirmations flow back).
