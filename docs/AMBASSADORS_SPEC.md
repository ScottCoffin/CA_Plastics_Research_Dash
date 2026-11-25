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
