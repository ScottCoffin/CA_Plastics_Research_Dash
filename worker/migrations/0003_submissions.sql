-- AMB-1 slice 2b: submissions, moderation roles, case answers (LOCAL ONLY). Times are Unix milliseconds (INTEGER).
--
-- Privacy: no email or email hash is added here. Exports (GET /export/approved) carry no ambassador email, and
-- ambassador ids are not exported. Owner identity is not stored: the account whose ORCID equals OWNER_ORCID
-- (wrangler.toml [vars]) is the owner, so the role column only records leads and ordinary ambassadors.

-- 1. Roles. 'owner' is accepted by the CHECK for completeness, but the code derives the owner from OWNER_ORCID.
ALTER TABLE ambassadors ADD COLUMN role TEXT NOT NULL DEFAULT 'ambassador' CHECK (role IN ('ambassador', 'lead', 'owner'));

-- 2. Decision record for proposals (0002 created the table without one). Set only by a moderation decision.
ALTER TABLE proposals ADD COLUMN decided_at INTEGER;
ALTER TABLE proposals ADD COLUMN decided_by TEXT;     -- ambassador id of the moderator (owner or lead)
ALTER TABLE proposals ADD COLUMN decision_note TEXT;

-- 3. Region leads promoted by the owner or another lead. A lead can see every region's queues (owner answer);
--    the region records where the promotion was made and whose region the lead was promoted from.
CREATE TABLE region_leads (
  ambassador_id TEXT NOT NULL REFERENCES ambassadors (id) ON DELETE CASCADE,
  region TEXT NOT NULL,                      -- california | norway | belgium (validated in code)
  promoted_by TEXT NOT NULL,                 -- ambassador id of the owner or lead who promoted
  promoted_at INTEGER NOT NULL,
  PRIMARY KEY (ambassador_id, region)
);

-- 4. Stream B and C submissions. payload is a short JSON object of plain strings, validated per kind in code.
CREATE TABLE submissions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ambassador_id TEXT NOT NULL REFERENCES ambassadors (id) ON DELETE CASCADE,
  region TEXT NOT NULL,
  stream TEXT NOT NULL CHECK (stream IN ('confirm', 'knowledge')),
  kind TEXT NOT NULL,
  payload TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  created_at INTEGER NOT NULL,
  decided_at INTEGER,
  decided_by TEXT,                           -- ambassador id of the moderator (owner or lead)
  decision_note TEXT
);
CREATE INDEX submissions_ambassador_id ON submissions (ambassador_id);
CREATE INDEX submissions_status_region ON submissions (status, region);

-- 5. Stream A answers: one row per (ambassador, case). A re-answer replaces the row.
--    correct_value is set only for 'disagree' (the value the ambassador gives instead).
CREATE TABLE case_answers (
  ambassador_id TEXT NOT NULL REFERENCES ambassadors (id) ON DELETE CASCADE,
  region TEXT NOT NULL,
  case_id TEXT NOT NULL,                     -- amb-<12 hex>, from the pipeline's per-region queue
  answer TEXT NOT NULL CHECK (answer IN ('agree', 'disagree', 'unsure')),
  correct_value TEXT,
  answered_at INTEGER NOT NULL,
  PRIMARY KEY (ambassador_id, region, case_id)
);
CREATE INDEX case_answers_case ON case_answers (region, case_id);
