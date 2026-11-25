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

## 10. Owner round 3 (2026-11-25): institution search, boundaries, map controls, badges, emails

**Institution entry.** Regions have many institutions, so every institution choice (sign-in eligibility check,
"Your institution" in a proposal) is a text field with type-ahead matching over the region's eligible institutions
(name, acronym, alternate names and email domain; e.g. "NIVA", "Norwegian Institute for Water Research",
"niva.no" all match), showing the type and city. No long drop-down lists.

**Boundaries.** The global map draws disputed boundaries from Natural Earth (`ne_50m_admin_0_boundary_lines_disputed_areas`,
dashed, with a legend line "Disputed boundary, as drawn by Natural Earth") and the Pacific grouping lines from
Natural Earth (`ne_10m_admin_0_pacific_groupings`) that box small Pacific island states. Natural Earth is public
domain; its point of view on disputed areas is the default Natural Earth view, stated in the map credit.

**Map controls.** Zoom and pan live in the map itself: wheel or trackpad zoom, drag to pan, pinch on touch,
double-click to zoom in, keyboard (+, -, arrows, 0) when the map has focus, and a small on-map control group (zoom in,
zoom out, reset) overlaid in a corner of the map frame, never outside it. Zoom is limited to sensible bounds. Gestures are cooperative so the page never gets stuck (lead, 2026-11-25): the wheel zooms only with Ctrl/Cmd held or after the map is activated by a click, tap or keyboard focus (Escape or leaving deactivates); otherwise the page scrolls and a short hint explains how to zoom; on touch, one finger scrolls the page and two fingers pan and pinch. `/explore` implements this first (`wheelZooms`, `nextActive`, `dragMode` in explore.js).

**Propose-a-region view.** The proposal map opens centred and zoomed on the place selected on the previous
page (the landing search or map selection). Selected units keep a visible, high-contrast boundary line drawn on top
of the selection fill (line colour from the ink token, at least 3:1 against the fill and the surrounding map).

**Ambassador badges.** An ambassador links their author record (search their name among the region's authors,
pick the matching OpenAlex author; ORCID shown when known); a moderator confirms the link unless name and institution
match exactly. The confirmed author then shows an "Ambassador" badge (with region) next to their name wherever the
Atlas shows that author: region pages (top researchers), author profile pages, author lists and search results,
and the network view's details panel. The become-an-ambassador page shows the badge and explains it. The badge is
opt-out (an ambassador can hide it) and is removed when the ambassador leaves.

**Emails** (all through Resend from a plastiverse.live address; every message has a link to notification settings
and one-click unsubscribe for non-essential mail; sign-in links are the only mail that cannot be switched off):
1. *Welcome and thanks*, sent when an ambassador first joins: thanks them, says what happens next, links the
   workspace, and invites them to bring colleagues.
2. *Invite your co-authors*: the workspace lists their co-authors from the corpus (name, institution, whether the
   institution is eligible and in which region). One click opens a ready-made invitation in the ambassador's own
   email program (subject and body pre-filled, with a personal invitation link). The Atlas never shows or stores
   co-authors' email addresses; the ambassador adds the address. Invitations sent are not tracked beyond the
   invitation link's sign-ups.
3. *Fortnightly reminder*: every 14 days, only if the ambassador has open tasks and has not opted out: how many
   tasks are open with the time estimate ("about 12 minutes"), the region's progress, and a link straight to the
   next task. No reminder when nothing is open; reminders pause after three unanswered ones until the ambassador
   returns.

## 11. Owner round 4 (2026-11-25): badge, consistent region choice, ORCID, workspace map, monitoring data

**Badge.** A real badge, not a text chip: a vector seal (a rosette or shield shape from an open icon set such as
Lucide, ISC licence, credited) carrying the Plastiverse Live sun mark and the words "Ambassador" and the region,
in brand colours (coral, butter, ink), legible at 16 px inline and 64 px on profiles; an accessible name
("Plastiverse Live ambassador for Norway"). Stored as one SVG component, so every page draws the same badge.
A raster variant made with Codex image generation is optional (Codex is not installed on the current machine).

**One way to choose a place.** Every place choice (eligibility check, sign-in, proposals) uses the same control as
the landing page: the place search with type-ahead and a map, pre-filled with the place chosen earlier. No radio
buttons or bare drop-downs for regions. The eligibility checker puts the place field and the institution field on
one aligned row (same height and baseline) on desktop, stacked on phones.

**ORCID.** "Connect your ORCID" uses ORCID's own sign-in (ORCID OAuth, `/authenticate` scope, so the iD is proven,
not typed). The Atlas then cross-references the iD against its author records (the ORCID on OpenAlex authors and
`curation/orcid_author_ids.csv`): an exact match links the author record automatically and the badge appears without
moderation; no match leaves the manual author search as fallback. ORCID needs a free public API client registered by
the owner (redirect URI on the Worker).

**Workspace map.** The ambassador's workspace opens with a map zoomed to their region (the same map component),
showing the region outline, eligible institutions as points, and open tasks by place where tasks have one.

**Share monitoring data.** A flow for sharing a monitoring dataset as an individual or on behalf of a group or
organisation: who shares (person, or organisation with the sharer's role and a confirmation that they may share
it), dataset description (name, sampling period, place on the map, matrices such as water, sediment, biota, air,
size range, methods, QA notes), access (public link, DOI or repository; or a file upload stored privately until
reviewed), licence (CC0, CC BY 4.0, ODC-BY, other, not sure) and permission for the Atlas to publish summaries or rows
under that licence. Datasets enter the same moderation queue and follow the monitoring licence rules
(`config/monitoring_publication.yml`): nothing is published until its licence is cleared.

**Proposal map size.** The propose-a-region map is the page's main element: full content width and at least 60% of
the viewport height on desktop, with the unit list and summary beside it on very wide screens or below it otherwise.

## 12. Owner answers to the design questions (2026-11-25)

Recorded from `.impeccable/surfaces/impeccable-sketches-ambassadors-html.md`:
- **Visible institutions:** an ambassador sees their own region's allowlist, plus the allowlists of any region they
  belonged to before, judged from their linked author record's institution history.
- **Single answers:** shown to the ambassador only after consensus (two agreeing ambassadors); before that, no
  "pending suggestion" state is shown.
- **After saving a case:** stay on the saved case (no auto-advance).
- **Leads:** the owner (Scott Coffin) approves leads; leads can promote further leads; leads can see every
  region's queues.
- **City radius:** chosen by the proposer.
- **Proposed regions:** appear on the public map only once approved.
- **Island zoom:** island states use a smaller minimum box (about 120 km).
- **Place index threshold:** no exceptions (Koror is not added); the search states the rule plainly ("cities and
  towns over 15,000 people; smaller places by their state or county").
- **Geometry:** real admin-1 boundaries (Natural Earth admin-1 or GADM) before the pilot.
- **Lead and owner task estimates:** best guesses for now (moderation item about 1 minute, region-tree decision
  about 3 minutes, lead promotion about 2 minutes).
- **/explore:** adopts the same place search (countries, subdivisions, cities) and minimum-box rule.
- **Data:** real data only on deployment; sample names replaced by real corpus data before the pilot.
- **Badge:** "Ambassador · <region>" only (no institution). A linked author still pending review appears on public
  pages without the badge.
- **Email sender:** ambassadors@plastiverse.live (confirmed). Stream A counts as a task in reminders.
- **Co-authors outside the allowlist:** get the email route, not an error.
- **Natural Earth credit wording:** confirmed.
- **Map gestures:** acceptable; the "how to zoom" hint persists until the map is clicked (all maps, including
  /explore).
- **Share monitoring data:** the publication choice is forced (no preselection); the place is chosen at region
  granularity.
- **Public credit (owner, after explanation):** on by default; ambassadors can opt out ("Confirmed by a local
  ambassador"). The first-visit screen and the terms say so plainly.
- **Contribution terms:** the agent drafts them for owner review: docs/AMBASSADOR_TERMS.md (CC BY-NC 4.0, right to
  share, names shown by default with opt-out, no personal data about others, review, withdrawal).
- **Split rule (owner, after explanation):** a sub-unit splits into its own region automatically when it has its own
  verified ambassador AND at least 50 plastics works; the group's existing ambassadors stay with the group and the
  new ambassador leads the child; below 50 works the sub-unit stays in the group.

## Backend slice 1 (local)

Status: built and tested locally in `worker/` (AMB-1 backend, slice 1). Not deployed; no Cloudflare or Resend
calls, no real email. Slice 2 (ORCID, submissions, moderation, proposals, emails, reminders, PR export) follows.

**Routes** (JSON; `Cache-Control: no-store`):

- `POST /auth/start` `{email, region, turnstileToken}`: validates the request (400), checks Turnstile (403
  `bot_check_failed`), applies rate limits (429 `rate_limited`), then, when the email's domain is on the region's
  allowlist, stores a single-use link and sends it. Always returns `200 {ok: true, message}` with the same text
  otherwise.
- `GET /auth/verify?token=`: consumes the link, finds or creates the ambassador, sets the session cookie and
  redirects (302) to the workspace URL. Any failure redirects to the same URL with `?signin=failed`.
- `GET /me`: the signed-in profile (401 `not_signed_in` otherwise). The email is returned masked only.
- `POST /auth/signout`: deletes the server-side session and clears the cookie (idempotent).

**Eligibility.** The Worker bundles the three `amb-v1` files (`site/data/<region>/ambassador_institutions.json`, with
the owner overrides already applied). A domain matches when it, or a parent domain, is on the region's allowlist
(`bio.uio.no` matches `uio.no`). Free-mail and its subdomains are always refused. A matching email under another
region is refused.

**Schema** (`worker/migrations/0001_init.sql`): `ambassadors` (id, email_hash, email, region, institution_id,
display_name, public_credit, consent_at, created_at, status), `magic_links` (token_hash, email_hash, email transient,
region, institution_id, created_at, expires_at, used_at), `sessions` (id_hash, ambassador_id, created_at, expires_at),
`audit_log`, `rate_limits` (fixed windows) and `outbox` (local and test mail only). Indexes cover lookups and expiry.

**Security notes**

- Tokens and session ids are 32 random bytes; the database stores only their SHA-256 hashes. Links expire after
  30 minutes and are single use (one conditional `UPDATE` claims them).
- Email addresses are looked up by a keyed HMAC (purpose-prefixed, keyed with `SESSION_SIGNING_KEY`). Plain email is
  kept for sign-in and notices only, never exported. `magic_links.email` is cleared when the link is used.
- Session cookie: `__Host-plastiverse_session`, HttpOnly, Secure, SameSite=Lax, Path=/, 30 days. The value is
  `<session id>.<HMAC-SHA256>`; the signature is checked in constant time, and the server-side row must be unexpired.
- No account enumeration: the `/auth/start` response is the same for eligible, ineligible, free-mail and unknown
  addresses. Rate limits count every request, eligible or not. A send failure is logged (error class only) and
  answered the same way.
- Rate limits: 5 requests per address per hour; 30 per client IP (`CF-Connecting-IP`) per hour.
- Turnstile fails closed: a missing secret, a network error or a non-success answer is a bot-check failure.
- CORS: only `ALLOWED_ORIGIN` may call, with credentials. Any other `Origin` header gets 403 before routing.
- Secrets are Worker secrets only. A missing secret stops the request (fail closed); the outbox sender is for local
  use (`MAIL_MODE=outbox`) and is never the production default.

**Open for the owner (slice 1):** the route must sit under `plastiverse.live/api/*` so the session cookie is
same-site with the site; the workspace path (`/ambassadors/`) is provisional; and the email hash key shares
`SESSION_SIGNING_KEY`, so rotating that key also changes the email lookup keys (a dedicated key is planned for slice 2).

**Slice 2 scope:** ORCID sign-in and linking, the first-sign-in profile and consent, submissions and moderation queue
(owner and region leads), region proposals, the Resend notices and reminders, a scheduled export endpoint for the PR job,
and a CI job for `worker/` tests.

## 13. ORCID-first sign-up (owner 2026-11-25; replaces the email-first entry of sections 3 and 11)

1. **Verify ORCID.** "Sign up with ORCID" uses ORCID OAuth (`/authenticate`), so the iD is proven.
2. **Find the author record.** The iD is cross-referenced to the Atlas author records (OpenAlex author ORCID,
   `curation/orcid_author_ids.csv`, and the global partition). One match links it; several are shown to choose from;
   none offers the name search, then moderator review.
3. **Claim institutions.** A checklist of every institution on the linked record's affiliation history (OpenAlex
   authorships, plus ORCID employments when the public record lists them), each marked eligible or not (on a
   region's allowlist: education, government, non-profit or research institute, at least 3 plastics works there).
   The ambassador ticks the ones to claim. **Any listed affiliation counts, current or past** (owner).
4. **Choose regions.** The regions tied to the claimed eligible institutions (the region whose predicate contains
   the institution: country, subdivision, registry region) are listed; the ambassador opts into one or more.
5. **Prove one institution.** Confirm ONE email address at the domain of any claimed eligible institution (magic
   link, section 3). Once confirmed, all ticked institutions and opted-in regions are active (owner: ORCID plus one
   institutional email).
6. **Propose something else.** Institutions or regions not on the record can be proposed (institution search over
   OpenAlex/ROR or free text; region via the propose-a-region flow); these go to moderation and do not block the
   rest of sign-up.
7. Then the first-visit screen (display name, credit default on with opt-out, terms v1).

Back end: the Worker stores the ORCID iD (public identifier), the linked author id, claimed institutions with their
source (openalex_history, orcid_employment, proposed), regions joined, and the confirmed email's domain; regions
an ambassador serves can grow later by claiming more institutions.
