-- CG-6a (Add-on A4): 30-day leases on BFFP community groups, claimed in batches by ambassadors (BFFP §5.2).
-- Additive only. Times are Unix milliseconds (INTEGER). One holder per group: group_id is the primary key.
CREATE TABLE group_leases (
  group_id TEXT PRIMARY KEY,                 -- cg_<16 hex>, from the published roster
  ambassador_id TEXT NOT NULL REFERENCES ambassadors (id) ON DELETE CASCADE,
  region TEXT NOT NULL,                      -- region the batch was claimed for (validated in code)
  leased_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  renewals INTEGER NOT NULL DEFAULT 0        -- renewal is allowed once (renewals < 1)
);
CREATE INDEX group_leases_ambassador_id ON group_leases (ambassador_id);
