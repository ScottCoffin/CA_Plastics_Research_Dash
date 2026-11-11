# Expert outreach: bios, photos and consent (spec, 2026-11-11)

Owner request: elicit expert bios, photos and consent by email, which also introduces
experts to the Atlas. Owner decisions (2026-11-11): contacts live in a local ignored
file; invitations go out as a mail-merge from the owner's own account; experts submit
through a Google/Microsoft Form the owner owns.

## Non-negotiable guardrails

1. **No contact data in the repository.** The repo and site are public. Emails, consent
   logs and form exports live only under `data/private/` (gitignored), and no public
   payload or log may contain an email (S10.2 privacy scan).
2. **Nothing is sent automatically.** The pipeline writes a mail-merge CSV and a template
   for owner review; the owner sends from their own account in small batches.
3. **Legitimate sources only.** Corresponding-author emails published for scholarly
   correspondence (affiliation strings, article XML), and emails the person made public
   (ORCID). No scraping of directories that disallow it in `robots.txt` (UC Davis Aggie
   Experts, UCSF Profiles), and no guessing addresses from name patterns.
4. **Identity, purpose and opt-out in every message:** who is writing, why the recipient
   is listed (their CA plastics research), what the Atlas shows about them, a link to
   their profile, and a one-line opt-out that the owner honours permanently
   (`data/private/outreach_optout.csv`, checked before every batch; it also feeds the
   GOV-B suppression route when the person asks for removal from the Atlas).
5. **One invitation and at most one reminder per person;** never contact people who opted
   out or are suppressed.

## Contact discovery (measured 2026-11-11, counts only)

| Source | Coverage of 2,426 experts | Match to the right person |
|---|---|---|
| OpenAlex raw affiliation strings ("Electronic address: ...") | 207 (8.5%) | the email sits on that author's authorship: high |
| ORCID public email (`/v3.0/{orcid}/email`) | ~11% of the 1,605 with an ORCID (about 175) | authoritative |
| Europe PMC full-text XML (`<email>` in `<corresp>`/contrib) for OA biomedical/environmental papers | not yet measured | high when the contrib links the email |
| CORE full text (owner key) | not yet measured | medium; needs name-to-email matching on the first page |

Expected combined coverage is about 20-30%. A contact row records the source, the work it
came from, a match confidence, and the date seen; the newest high-confidence address wins.

## Flow

1. `scripts/build_outreach_contacts.py` writes `data/private/outreach_contacts.csv`
   (author_id, name, email, source, evidence work, confidence, last_seen), skipping
   opt-outs and suppressed authors. It prints counts only.
2. `scripts/build_outreach_mailmerge.py --batch N` writes
   `data/private/mailmerge_<date>.csv` (first name, name, email, profile URL, top topics,
   California works count) and `docs/outreach_template.md` (owner-approved text; no
   personal data). Batches are prioritised by plastics works and recency.
3. The owner sends with Outlook/Gmail mail-merge and logs the batch in
   `data/private/outreach_log.csv`.
4. Form (owner's Google/Microsoft Form): name, ORCID/OpenAlex ID (pre-filled link),
   bio up to 600 characters, photo upload, a licence statement ("I own this photo and
   license it to the Atlas under CC BY 4.0"), consent to publish, and an opt-out box.
5. `scripts/import_expert_profiles.py <form export>` validates responses and writes only
   public fields to `curation/expert_profiles.csv` (author_id, bio, photo filename,
   licence, credit, consent date, owner_approved). Photos are resized to small WebP
   thumbnails in `site/assets/experts/`. Emails never leave `data/private/`.
6. The owner approves each profile (`owner_approved`); the export shows approved bios
   and photos in the drawer; everyone else gets an initials avatar plus ORCID/Wikidata
   material from S9.5.

## Template outline (owner approves the final wording)

Subject: Your California plastics research in the CA Plastics Research Atlas.
Body: who the owner is and the independent nature of the project (disclaimer); "you are
listed because of N California-affiliated plastics publications"; a link to their
profile; an invitation to add a short bio and photo (form link) and to correct anything
(correction route); a one-line opt-out ("reply 'no thanks' and you will not hear from
us again"); the owner's name and contact.

Tracked as TODO S9.6; depends on S9.5's drawer support for bios and photos.
