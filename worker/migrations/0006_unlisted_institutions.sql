-- AMB-1 unlisted institutions (owner decision 2026-11-26, QUESTIONS AMB-UNLISTED-EMAIL): a person whose ORCID or
-- OpenAlex record links no eligible institution proposes an institution with its email domain. A trusted public-sector
-- address (region trusted_email_suffixes) confirms the email; a moderator then approves or rejects. LOCAL ONLY until
-- the owner applies it. Times are Unix milliseconds (INTEGER).
--
-- ADDITIVE ONLY: no table is rebuilt (the live D1 holds real accounts). Every change is an ADD COLUMN or CREATE INDEX.
--
-- Privacy: no new personal data. proposed_domain and confirmed_domain are registrable hosts, not addresses. The confirmed
-- email itself is kept in ambassadors.email, as for every other sign-up (never exported).
--
-- review_state marks an ambassador waiting for a moderator. Their status stays 'pending' (signup-session and cleanup
-- rules already key on it); review_state = 'pending_review' is what blocks sign-in and exempts them from cleanup.

-- 1. Ambassadors: the waiting-for-moderator marker (NULL for everyone else).
ALTER TABLE ambassadors ADD COLUMN review_state TEXT CHECK (review_state IS NULL OR review_state = 'pending_review');

-- 2. Magic links: a confirmation link for an unlisted-institution proposal carries its proposal id.
ALTER TABLE magic_links ADD COLUMN proposal_id INTEGER;

-- 3. Proposals: the proposed region and domain (set at claim time), the awaiting-email flag the email step uses, and the
--    confirmation (set when the link is used). region, domain and institution_type stay the moderator's allowlist fields.
ALTER TABLE proposals ADD COLUMN proposed_region TEXT;
ALTER TABLE proposals ADD COLUMN proposed_domain TEXT;
ALTER TABLE proposals ADD COLUMN awaiting_email INTEGER NOT NULL DEFAULT 0 CHECK (awaiting_email IN (0, 1));
ALTER TABLE proposals ADD COLUMN email_confirmed_at INTEGER;
ALTER TABLE proposals ADD COLUMN confirmed_domain TEXT;

-- 4. Lookups by the email step (awaiting proposal of a sign-up) and by the moderation queue (confirmed proposals).
CREATE INDEX proposals_awaiting_email ON proposals (ambassador_id, awaiting_email);
CREATE INDEX ambassadors_review_state ON ambassadors (review_state);
