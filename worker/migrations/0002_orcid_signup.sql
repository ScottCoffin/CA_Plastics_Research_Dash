-- AMB-1 slice 2a: ORCID-first sign-up (LOCAL ONLY). Times are Unix milliseconds (INTEGER).
--
-- MIGRATION NOTE (owner action before any remote apply):
--   1. Email lookups now use EMAIL_HASH_KEY (a dedicated secret), not SESSION_SIGNING_KEY. Rows created by
--      slice 1 hold email_hash values keyed with SESSION_SIGNING_KEY, so they will not match new lookups.
--      Slice 1 was never deployed (no production data): reset the local D1 instead of re-hashing.
--   2. ambassadors is rebuilt (email, email_hash, region and institution_id become nullable because an ORCID
--      sign-up creates the pending row before any email is confirmed). sessions is rebuilt in the same step so
--      that dropping the old parent table does not cascade-delete live sessions.
--   3. ORCID secrets are new: ORCID_CLIENT_ID and ORCID_CLIENT_SECRET (Worker secrets), plus EMAIL_HASH_KEY.
--
-- Privacy: unchanged from slice 1. Tokens, session ids and OAuth states are stored only as SHA-256 hashes.
-- Plain email stays in ambassadors.email and, transiently, magic_links.email. The ORCID access token is never
-- stored. Email and ORCID lookups use keyed hashes.

-- 1. Rebuild ambassadors with the sign-up columns.
CREATE TABLE ambassadors_v2 (
  id TEXT PRIMARY KEY,                       -- random 16 bytes, hex
  orcid TEXT UNIQUE,                         -- public ORCID iD (verified by ORCID OAuth /authenticate)
  author_id TEXT,                            -- OpenAlex author id (A<digits>) linked at lookup time
  checklist_json TEXT,                       -- pending only: the institution checklist shown at sign-up
  email_hash TEXT UNIQUE,                    -- HMAC-SHA256(EMAIL_HASH_KEY, "email:" + normalised address); set on email proof
  email TEXT,                                -- PRIVATE: sign-in and notices only; never exported or published
  region TEXT,                               -- home region of the confirmed email (set on email proof)
  institution_id TEXT,                       -- home institution of the confirmed email (set on email proof)
  display_name TEXT,                         -- set at the first-visit profile
  credit_public INTEGER NOT NULL DEFAULT 1 CHECK (credit_public IN (0, 1)),  -- credit ON by default (owner)
  consent_at INTEGER,                        -- contribution terms accepted
  terms_version TEXT,                        -- e.g. v1 (docs/AMBASSADOR_TERMS.md)
  created_at INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('pending', 'active', 'suspended'))
);

INSERT INTO ambassadors_v2 (id, email_hash, email, region, institution_id, display_name, credit_public, consent_at, created_at, status)
  SELECT id, email_hash, email, region, institution_id, display_name, public_credit, consent_at, created_at, status
  FROM ambassadors;

-- 2. Rebuild sessions against the new parent (copy first, drop the child, then the old parent).
CREATE TABLE sessions_v2 (
  id_hash TEXT PRIMARY KEY,                  -- SHA-256 of the session id carried in the signed cookie
  ambassador_id TEXT NOT NULL REFERENCES ambassadors_v2 (id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);
INSERT INTO sessions_v2 SELECT id_hash, ambassador_id, created_at, expires_at FROM sessions;
DROP TABLE sessions;
DROP TABLE ambassadors;
ALTER TABLE ambassadors_v2 RENAME TO ambassadors;
ALTER TABLE sessions_v2 RENAME TO sessions;
CREATE INDEX ambassadors_region ON ambassadors (region, institution_id);
CREATE INDEX sessions_ambassador_id ON sessions (ambassador_id);
CREATE INDEX sessions_expires_at ON sessions (expires_at);

-- 3. Magic links can now belong to a pending ORCID sign-up (ambassador_id set) or to the slice-1 email route (NULL).
ALTER TABLE magic_links ADD COLUMN ambassador_id TEXT REFERENCES ambassadors (id) ON DELETE CASCADE;

-- 4. Claimed institutions. eligible = on a region allowlist. claimed_at is set when the confirmed email makes them active.
CREATE TABLE ambassador_institutions (
  ambassador_id TEXT NOT NULL REFERENCES ambassadors (id) ON DELETE CASCADE,
  institution_id TEXT NOT NULL,              -- OpenAlex institution id (I<digits>) or an unmapped ror:/name: key
  source TEXT NOT NULL CHECK (source IN ('openalex_history', 'orcid_employment', 'proposed')),
  eligible INTEGER NOT NULL CHECK (eligible IN (0, 1)),
  claimed_at INTEGER,                        -- NULL until the email proof activates the claim
  PRIMARY KEY (ambassador_id, institution_id)
);

-- 5. Regions joined. pending_email until the email proof; then active.
CREATE TABLE ambassador_regions (
  ambassador_id TEXT NOT NULL REFERENCES ambassadors (id) ON DELETE CASCADE,
  region TEXT NOT NULL,                      -- california | norway | belgium (validated in code)
  status TEXT NOT NULL CHECK (status IN ('active', 'pending_email')),
  joined_at INTEGER NOT NULL,
  PRIMARY KEY (ambassador_id, region)
);

-- 6. Proposals (institutions or regions not on the record). They go to moderation and do not block sign-up.
CREATE TABLE proposals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ambassador_id TEXT NOT NULL REFERENCES ambassadors (id) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('institution', 'region')),
  payload TEXT NOT NULL,                     -- short JSON of plain strings chosen by the applicant
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  created_at INTEGER NOT NULL
);
CREATE INDEX proposals_ambassador_id ON proposals (ambassador_id);

-- 7. ORCID OAuth state, single use. The nonce cookie (browser binding) is stored only as its hash.
CREATE TABLE orcid_states (
  state_hash TEXT PRIMARY KEY,               -- SHA-256 of the state parameter
  nonce_hash TEXT NOT NULL,                  -- SHA-256 of the nonce cookie set by /orcid/start
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL                -- created_at + 10 minutes
);
CREATE INDEX orcid_states_expires_at ON orcid_states (expires_at);

-- 8. Short-lived signup session after ORCID sign-in and before the email proof (cookie __Host-plastiverse_signup).
CREATE TABLE signup_sessions (
  id_hash TEXT PRIMARY KEY,                  -- SHA-256 of the session id carried in the signed cookie
  ambassador_id TEXT NOT NULL REFERENCES ambassadors (id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL                -- created_at + 60 minutes
);
CREATE INDEX signup_sessions_ambassador_id ON signup_sessions (ambassador_id);
CREATE INDEX signup_sessions_expires_at ON signup_sessions (expires_at);
