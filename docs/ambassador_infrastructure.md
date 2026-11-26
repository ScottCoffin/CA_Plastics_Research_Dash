# Ambassador infrastructure: interface for the groups layer (CG-5)

Answers the five questions of the groups spec (`docs/BFFP.md` §5.5) from the repository as of
2026-11-26, and defines what the groups layer (Add-on A4) reuses and what it adds. The full design
of the ambassador programme is `docs/AMBASSADORS_SPEC.md`; the code is `worker/`.
Conflict notes are in `.agent/DECISIONS.md` (A4-C2, A4-C3, A4-C4).

## 1. Where ambassador records are kept, and who administers them

- A Cloudflare Worker at `https://api.plastiverse.live` with a D1 database (`plastiverse-ambassadors`).
  Migrations `worker/migrations/0001`..`0006`; tables include `ambassadors`, `ambassador_regions`,
  `ambassador_institutions`, `sessions`, `submissions`, `case_answers`, `proposals`, `region_leads`,
  `notification_prefs`, `invitations` and `audit_log`.
- Sign-up is ORCID first, then one institutional email confirmed by a one-time link (Turnstile on the
  form). Region membership comes from the institutions an ambassador claims; unlisted institutions go
  through moderation.
- Administration: the owner (owner moderator by ORCID iD) and promoted region leads, on the unlisted
  page `/ambassador_moderation` (approve or reject with a note, promote leads, owner-only suspension).
- Personal data (email, ORCID, names) stays in D1. The public repository never holds it.

## 2. Assignment and submission today

- There is no assignment engine. Ambassadors work through three task streams on their dashboard
  (`/ambassadors` when signed in): check classifier cases (answers with consensus), confirm the
  region page (confirm, correct, not relevant), and add local knowledge (11 kinds).
- Submissions: `POST /submissions {region, stream, kind, payload}` with a per-kind field allow-list and
  length limits (`worker/src/submissions.ts`); every submission waits in the moderation queue.
- Gap for the groups layer: batches, leases, one holder per entry, the conflict-of-interest return,
  and the tagging form with facets and evidence (CG-6).

## 3. Export and vocabularies

- Export: `GET /export/approved` (bearer token `AMB_EXPORT_TOKEN`, server to server) lists approved
  items since a watermark. The daily GitHub job `scripts/ambassador_export_pr.py` turns them into a
  pull request (region files, `curation/ambassador_labels.csv`, institution additions) that the owner
  reviews. Every payload is validated again on the way in.
- Vocabularies: the Worker enforces per-kind allowed keys, https-only URLs and plain text, not
  controlled values. For the groups layer the controlled vocabularies (F1-F14) and the evidence rules
  (V1-V14) are enforced twice: in the Worker on submit, and in the ingest validator (CG-4), which is
  the enforcement point the spec requires (§7.1).

## 4. Authentication and data protection

- Sessions are signed `__Host-` cookies; CORS credentials are limited to `https://plastiverse.live`.
  Magic links last 30 minutes; no account enumeration; per-account rate limits.
- Email addresses are stored only for sign-in and mail; a dedicated hash key is used for lookups;
  co-author invitations never take or store an address. Mail carries one-click unsubscribe.
- The ambassador `id` is an opaque random identifier. It is the spec's `ambassador_id`; it never
  appears in a published file (V9). Public credit follows the contribution terms v1: on by default,
  switchable to "Confirmed by a local ambassador" (A4-C4).

## 5. Region scheme and languages

- Regions are `regions/_registry.yml` (today `california`, `norway`, `belgium`), each with an
  eligible-institution list and optional trusted email suffixes. New regions are added there.
  Groups map country (ISO 3166-1) to an ambassador region where one exists; other countries use the
  UN M49 sub-region as a display level and wait in the unassigned pool; missing countries are
  `region_unknown` (A4-C3).
- Languages: the Worker does not record ambassador languages yet. CG-6 adds an optional list of
  ISO 639-1 codes on the profile so assignments can follow website language (A4-Q6).

## Adapter for the groups layer

| Spec need (§5.5) | Reuse | Add (CG-6 unless noted) |
|---|---|---|
| Roster entries delivered as assignments | Dashboard task cards, region membership, sessions | D1 tables for roster entries, batches and leases (additive migration); "Tag local groups" stream |
| Submissions as rows meeting the CSV contract (§8.3) | `POST /submissions`, moderation queue, export job | A `group_tag` kind with facet and evidence fields; the export job writes the §8.3 CSV and `affiliations.csv` into ignored `data/interim/bffp/submissions/` for ingest |
| Opaque `ambassador_id` per submission | Ambassador `id` | Nothing |
| Review and double tagging (§7) | Moderation page, region leads, audit log | Second-tagger assignment, agreement statistics (CG-7) |
| Suggest a group | Add local knowledge | The group kinds move to the A4 record (QUESTIONS AMB-KNOWLEDGE-EXTRAS) |

Every schema change is an additive D1 migration, and every Worker deploy waits for the owner's
go-ahead, as for earlier slices.
