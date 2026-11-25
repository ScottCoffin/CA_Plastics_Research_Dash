-- AMB-1 slice 1: ambassador sign-in (LOCAL ONLY). Times are Unix milliseconds (INTEGER).
-- Privacy: tokens and session ids are stored only as SHA-256 hashes (magic links and sessions are
-- high-entropy random values, so a plain hash suffices). Email addresses are keyed HMAC-SHA256 hashes
-- for lookups. Plain email is kept in two places only, for sign-in and notices: ambassadors.email
-- and, transiently, magic_links.email (cleared when the link is used). Never exported.

CREATE TABLE ambassadors (
  id TEXT PRIMARY KEY,                       -- random 16 bytes, hex
  email_hash TEXT NOT NULL UNIQUE,           -- HMAC-SHA256(SESSION_SIGNING_KEY, "email:" + normalised address)
  email TEXT NOT NULL,                       -- PRIVATE: sign-in and notices only; never exported or published
  region TEXT NOT NULL,                      -- california | norway | belgium
  institution_id TEXT NOT NULL,              -- OpenAlex institution id from ambassador_institutions.json
  display_name TEXT,                         -- set at first-sign-in profile (slice 2)
  public_credit INTEGER NOT NULL DEFAULT 0 CHECK (public_credit IN (0, 1)),
  consent_at INTEGER,                        -- contribution terms accepted (slice 2)
  created_at INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended'))
);
CREATE INDEX ambassadors_region ON ambassadors (region, institution_id);

CREATE TABLE magic_links (
  token_hash TEXT PRIMARY KEY,               -- SHA-256 of the 32-byte random token; the token itself is never stored
  email_hash TEXT NOT NULL,
  email TEXT,                                -- PRIVATE, transient: cleared when the link is used
  region TEXT NOT NULL,
  institution_id TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,               -- created_at + 30 minutes
  used_at INTEGER                            -- single use: set once, by a conditional UPDATE
);
CREATE INDEX magic_links_email_hash ON magic_links (email_hash, created_at);
CREATE INDEX magic_links_expires_at ON magic_links (expires_at);

CREATE TABLE sessions (
  id_hash TEXT PRIMARY KEY,                  -- SHA-256 of the session id carried in the signed cookie
  ambassador_id TEXT NOT NULL REFERENCES ambassadors (id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL                -- created_at + 30 days
);
CREATE INDEX sessions_ambassador_id ON sessions (ambassador_id);
CREATE INDEX sessions_expires_at ON sessions (expires_at);

CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at INTEGER NOT NULL,
  action TEXT NOT NULL,                      -- e.g. auth.start, auth.verify, auth.signout
  subject TEXT,                              -- email hash or ambassador id, never plain email
  detail TEXT                                -- short JSON, no plain email
);
CREATE INDEX audit_log_at ON audit_log (at);

-- Fixed-window counters: bucket = "<scope>:<key>:<window index>".
CREATE TABLE rate_limits (
  bucket TEXT PRIMARY KEY,
  count INTEGER NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE INDEX rate_limits_expires_at ON rate_limits (expires_at);

-- LOCAL DEV AND TESTS ONLY (MAIL_MODE = "outbox"). Holds sent messages instead of Resend.
-- Production never writes here; this table is not a mail archive.
CREATE TABLE outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at INTEGER NOT NULL,
  to_address TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL
);
