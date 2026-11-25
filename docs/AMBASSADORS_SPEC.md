# Local ambassadors (AMB-1) — product and technical spec

Status: approved direction 2026-11-25. Owner decisions (QUESTIONS AMB-*): backend Cloudflare Workers + D1; email via Resend; moderation by the owner plus per-region leads; research institutes (ROR `facility`) are eligible.

## 1. Owner requirements (2026-11-25, paraphrased)

1. Entry is granted on email confirmation from a verified email domain of a verified institution in the
   ambassador's region: government, academia or non-profit.
2. The institution must already be tagged as producing plastics research in that region.
3. After verifying, the ambassador gets an easy interface to ground-truth region-specific classifier
   ambiguities and to add community groups, volunteer organisations, local policies, and the other
   region-specific information the Atlas needs.

## 2. Who can join (eligibility)

- **Eligible institutions, per region:** institutions with at least `min_works` plastics works in the region's
  corpus (California: the curated corpus; other regions: the global partition, authorship institution with the
  region's country code), whose type is `education`, `government` or `nonprofit`; `facility` (research
  institutes such as NIVA or VLIZ) is eligible (owner 2026-11-25); `company`, `healthcare`, `archive`
  and `other` do not. Default `min_works` = 3.
- **Domains:** from the ROR record (`domains`) and the OpenAlex `homepage_url` host, reduced to the registrable
  domain (e.g. `niva.no`); subdomains are accepted (`bio.uio.no` -> `uio.no`). Free-mail and generic domains are
  always refused (gmail, outlook, proton, ...). Owner overrides in `regions/<slug>/ambassador_domains.csv`
  (add, remove, note).
- **Published allowlist:** `site/data/<slug>/ambassador_institutions.json` (institution name, type, works, domains)
  so applicants can see in advance whether their institution qualifies. Institutions only; no people.
- **Not eligible yet?** The page offers the current email route (theplastiverse@gmail.com) for a manual review.

## 3. Sign-in flow (magic link, no passwords)

1. The applicant picks a region and enters an institutional email; bot check (Cloudflare Turnstile).
2. The backend checks the domain against the region allowlist and sends a one-time link (valid 30 minutes).
3. Clicking it signs them in: a signed session (30 days, renewable), bound to region and institution.
4. First sign-in asks for a display name, an optional public credit ("Ambassador: Name, Institution"),
   and consent to the contribution terms (licence of contributions: CC BY-NC 4.0, matching the data licence).
- Stored: email (for sign-in and notices only), salted hash for lookups, institution id, region, consent and dates.
  Never published; deleted on request. Emails never enter the repository (owner rule: `data/private/` only).

## 4. The ambassador workspace

One region dashboard with three task streams. Review tasks follow the owner's review rule: one case per screen,
one-click decisions saved at once, the admitting search terms highlighted, progress shown.

**A. Ground-truth classifier ambiguities (region-specific).** Each case shows the evidence and the current
machine decision; the ambassador clicks agree, disagree (with the correct value) or unsure.
- Is this institution in the region? (raw-affiliation place-name collisions; e.g. "Bergen" NL vs NO,
  "Georgia" US vs country; the CA basis and region predicates)
- Is this institution's type right? (university / government / non-profit / research institute / company)
- Is this local-language work about plastics? (non-English titles and abstracts the English rules handle poorly)
- Is this place name a sampling location in the region? (gazetteer hits for the S5.2 toponym extractor)
- Low-confidence plastic-relevance decisions for works with an author in the region (like H2, but local)
- Are these two author records the same person? (local name variants; merges are applied by the owner)
- Local search terms: is this term used locally for plastic pollution, and with what meaning?
Cases come from a per-region queue file built by the pipeline; each answer is stored with source `ambassador`,
the ambassador id and time, and feeds the gold sets with its own agreement statistics (never mixed silently
with owner labels).

**B. Confirm the region page's placeholders.** Every `to_confirm` item in `regions/<slug>/region.yml`
(funders, monitoring programmes, policies, research networks, local terms, geography): confirm, correct the
name or URL, mark "not relevant", or add a note.

**C. Add local knowledge** (structured forms, each with name, URL, short description, contact route if public,
licence where data is involved):
- Community groups and coalitions; volunteer organisations (beach and river clean-ups, citizen science)
- Local and regional policies, plans and targets (with dates), and upcoming decisions
- Funders and programmes; monitoring datasets and data portals (with licence)
- Research networks and labs; local events and conferences; local media and outreach channels
- Missing institutions and researchers (institutions only are published; researchers only with public profiles)
- Indigenous and community knowledge holders: only organisations that publish their own contact route, and
  only with their consent
- Corrections to anything on the region page

## 5. Moderation and publication

- Every submission lands in a moderation queue. Approvers: the owner for every region, plus a region lead the
  owner promotes from that region's ambassadors (owner 2026-11-25); the owner still reviews every pull request. Approved items flow into the repository by a scheduled job that opens a pull request updating
  `regions/<slug>/region.yml` and the curation CSVs, so every change is reviewable and versioned.
- Classifier answers do not change public pages directly: they become labels, and the pipeline applies them
  under the usual override precedence (owner > ambassador consensus > model).
- Two ambassadors agreeing counts as consensus for label use; a single answer is kept and shown to the
  owner as a suggestion.
- Abuse: rate limits per account, Turnstile on sign-in, the owner can suspend an account or a domain.

## 6. Architecture

- **Static site (unchanged):** region allowlists, task-queue files (case ids and the public evidence only) and the
  workspace UI are part of the Framework build.
- **Backend** (owner 2026-11-25): Cloudflare Workers + D1 (the owner already uses Cloudflare for DNS and R2)
  for sign-in, sessions, submissions, moderation and the export endpoint the scheduled GitHub job reads.
- **Email** (owner 2026-11-25): Resend (free tier) from a
  `plastiverse.live` sender with SPF/DKIM.
- **Secrets** (owner-held): Worker session-signing key, email API key, Turnstile secret, a GitHub token scoped to
  opening pull requests on this repository, a Worker API token for the export job.

## 7. Build order

1. Data (no backend): eligibility builder and published allowlists per region; per-region case queues for
   stream A; the placeholder list for stream B. Tests.
2. Design (Impeccable, global theme): landing and eligibility checker, sign-in, workspace dashboard, the
   one-case-per-screen reviewer, the add-knowledge forms, moderation view. Owner review.
3. Backend (after the owner decisions and secrets): Worker + D1 schema, magic link, sessions, submissions,
   moderation, export; local tests with Miniflare/wrangler dev.
4. Pull-request job and the pipeline consumers (labels with source `ambassador`; region.yml updates).
5. Pilot with the Norway and Belgium collaborators.

## Ambassador data (AMB-1 step 1)

Built by `py -3.14 scripts/build_ambassador_data.py` (`--slug S` for one region; `--check` validates the committed
files and fails when they are stale against the ignored inputs, SKIP for the staleness check when they are absent).
Code: `src/atlas/build/ambassadors.py`. Offline; nothing is fetched. No people are published: the institution file
has institution names, types, counts and domains only; the case files carry titles, institution names, place names
and short affiliation strings (never abstracts, emails or author names).

Eligibility (section 2): an institution is listed when it has at least 3 plastics works in the region's corpus with an
author at it and its OpenAlex type is `education`, `government`, `nonprofit` or `facility`. California uses the
curated corpus (authorships whose `ca_basis` is in the registry's `ca_basis_values`) and the registry type
(`openalex_type`). Other regions use the global partition (authorship institutions whose `country_code` is the
region's ISO code) and the type on the raw OpenAlex record.

Domains come from a domain cache under `data/interim/ambassador_domains/` (ignored; one JSON per institution with fetch dates). It is filled only by `--fetch-domains`, the one network mode: the OpenAlex institution record (`homepage_url`, `ror`; batches of up to 100 ids; a plain filter, about 1 credit per call; capped at 20 credits per run; logged to `data/logs/api_usage.jsonl`) and the ROR v2 record (`domains` and website links; one request per second; generic User-Agent; no key). A local ROR dump under `data/raw` is also read when present. Precedence (owner rule): ROR domains first, then the OpenAlex homepage host, then ROR website links; the first group with a usable domain is used. Each host is reduced to its registrable domain: the last
two labels, or the last three under a two-level suffix (`ca.gov`, `ac.uk`, `gov.uk`, `co.uk`, `org.uk`, `edu.au`,
`gov.au`). Subdomains are accepted (`bio.uio.no` gives `uio.no`). Free-mail and generic domains (gmail, outlook,
hotmail, live, yahoo, gmx and the other names in `FREE_MAIL_DOMAINS`) are always refused, including as overrides.
Owner overrides are in `regions/<slug>/ambassador_domains.csv` (columns `institution_id`, `domain`, `action`
add or remove, `note`), applied in file order; an invalid row stops the build. An institution with no known domain
is listed with `domains: []` and `needs_domain: true`.

Case queues (section 4.A, stream A): `institution_in_region` (raw-affiliation-only matches in California; place-name
mentions or author-country-only signals elsewhere; capped at 200, affiliation evidence first),
`institution_type` (region institutions with at least 3 works whose type is missing or `other`, or a company with
at least 10 works; capped at 100), `local_language_relevance` (non-English works with a region author; title only;
capped at 200) and `local_terms` (one per `local_search_terms` entry in `regions/<slug>/region.yml`). Case ids are
`amb-` plus the first 12 hex digits of a SHA-256 of region, kind and entity key, so answers survive rebuilds.
Selection is deterministic (sorted by the rules above; no sampling).

Files (per region folder, committed): `ambassador_institutions.json` (schema `amb-v1`) and `ambassador_cases.json`
(schema `amb-cases-v1`). Override files were created with headers only.

## 8. Landing map, search and region proposals (owner 2026-11-25, second round)

**World map.** The ambassadors landing opens on a world map in the **Natural Earth projection** (d3
`geoNaturalEarth1`; owner decision, it also becomes the projection of the shared global map). Regions with at least
one verified ambassador are drawn in one colour, open regions (no ambassador yet) in another, and proposed regions
awaiting more members in a third, with a legend and a table alternative. Geometry: Natural Earth admin-0 at 1:50m
(includes small island states such as Palau, Nauru and Tuvalu; public domain); every country smaller than a few
pixels at world scale also gets a centroid marker so it can be seen, focused and clicked.

**Search and zoom.** One search field with autocomplete over countries, first-level subdivisions (states,
provinces, counties where Natural Earth admin-1 has them) and populated places (GeoNames cities with population at
least 15,000, CC BY 4.0, credited). Typing ranks matches by type and population and shows the parent ("Koror,
Palau"; "Bergen, Vestland, Norway"); choosing one zooms the map to it. Zoom uses the feature's bounds with a
minimum box (about 300 km), so tiny countries and cities are zoomed in properly; points zoom to their
surroundings. The same search and minimum-box rule fix `/explore`, which today cannot zoom to Palau.

**Proposing a region.** A verified ambassador can propose the region they speak for at any granularity:
- one country; a state, province or county; a city or metropolitan area (place plus radius, or admin units);
- a group of countries or subdivisions (e.g. Pacific Island countries, small West African states).
They build it on the map or by search (add and remove units), name it, and see which eligible institutions and
how many plastics works fall inside. The region's predicate is generated from the chosen units (country codes,
subdivision codes, place names), the same predicate shape as `regions/_registry.yml`.

**Auto-approval.** A proposal from a verified ambassador whose institution lies inside the proposed region is
approved automatically and appears on the map at once (status `active-ambassador`); the owner and region leads see
it in the moderation log and can edit or retire it. Proposals that do not contain the proposer's institution
wait for moderation. Approved regions reach the repository registry by the usual pull request.

**Refining granularity.** Regions form a tree. When a sub-unit of a larger region gains its own verified ambassador
(an ambassador whose institution lies in that sub-unit, e.g. Samoa inside "Pacific Island countries"), the sub-unit
is offered as its own child region; it splits out automatically once it has an ambassador and at least 50 plastics
works (the Tier B threshold), otherwise it stays in the group. The parent keeps the remaining units and links to
its children; nothing is deleted, so earlier contributions stay attached to the units they were about. A city
region inside a state region works the same way (child of the state).

## 9. Time estimates on tasks (owner 2026-11-25)

Every task and stream shows how long it should take, from a per-kind estimate refined by the median time
ambassadors actually take (shown once 20 answers exist): ground-truth case about 30 seconds; confirm a
placeholder about 2 minutes; add a community group or organisation about 5 minutes; add a policy with dates about
8 minutes; propose a region about 5 minutes. The dashboard sums them ("about 15 minutes for the next 30 cases")
and lets ambassadors pick a session length (5, 15 or 30 minutes) that selects the next tasks to fit.
