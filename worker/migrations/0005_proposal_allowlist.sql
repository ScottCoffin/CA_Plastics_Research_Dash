-- AMB-1 proposals-to-allowlist, part 1: an approved institution proposal joins its region's eligible list (LOCAL ONLY).
-- Times are Unix milliseconds (INTEGER).
--
-- Set only by an approving moderation decision on an institution proposal (POST /moderation/decide). Existing approved
-- proposals from before this migration keep NULL here and are never exported as institutions.
-- Privacy: no email, ambassador id or ORCID iD is added. The domain is a public registrable host (for example
-- oehha.ca.gov), not an address. GET /export/approved reads these columns and nothing personal.

ALTER TABLE proposals ADD COLUMN region TEXT;             -- california | norway | belgium (validated in code)
ALTER TABLE proposals ADD COLUMN domain TEXT;             -- lowercase registrable host, e.g. oehha.ca.gov (validated in code)
ALTER TABLE proposals ADD COLUMN institution_type TEXT CHECK (institution_type IN ('education', 'government', 'nonprofit', 'facility'));
