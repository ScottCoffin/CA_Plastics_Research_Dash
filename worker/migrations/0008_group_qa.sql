-- CG-7b (Add-on A4, BFFP §7.2-7.3): deliberate blind second tags, reviewer sampling and the reason-coded audit.
-- Additive only. Times are Unix milliseconds (INTEGER). Nothing here is exported with an ambassador id.
--
-- A usable primary tag is a group_tag submission with no second_tag_for, status ambassador_tagged and
-- not_an_organisation not true. Selection runs in the same D1 batch as the tag insert (submissions.ts).

-- 1. One random position per consecutive block. kind 'sample': scope = region, blocks of 10 usable primary tags
--    (exactly 10% per region). kind 'review': scope = ambassador id, blocks of 5 after the first 25 (exactly 20%).
--    INSERT OR IGNORE keeps the first draw, so concurrent tags read the same pick.
CREATE TABLE group_qa_blocks (
  kind TEXT NOT NULL CHECK (kind IN ('sample', 'review')),
  scope TEXT NOT NULL,
  block_no INTEGER NOT NULL,
  pick INTEGER NOT NULL,
  PRIMARY KEY (kind, scope, block_no)
);

-- 2. Primary tags selected for a deliberate blind second tag, with the current two-hour hold of the second tagger
--    (a different active ambassador of the same region). One sample per group.
CREATE TABLE group_tag_samples (
  primary_id INTEGER PRIMARY KEY REFERENCES submissions (id) ON DELETE CASCADE,
  group_id TEXT NOT NULL UNIQUE,
  region TEXT NOT NULL,
  selected_at INTEGER NOT NULL,
  assigned_to TEXT REFERENCES ambassadors (id) ON DELETE SET NULL,
  hold_until INTEGER
);
CREATE INDEX group_tag_samples_region ON group_tag_samples (region);
CREATE INDEX group_tag_samples_assigned_to ON group_tag_samples (assigned_to);

-- 3. Audit of agreement pairs: the first usable second tag of each usable primary. basis 'sample' when the second
--    tagger held the sample assignment, 'overlap' otherwise (two ambassadors happened to tag the same group).
--    Both tags stay in submissions; neither row is ever deleted by moderation.
CREATE TABLE group_tag_pairs (
  primary_id INTEGER PRIMARY KEY REFERENCES submissions (id) ON DELETE CASCADE,
  second_id INTEGER NOT NULL UNIQUE REFERENCES submissions (id) ON DELETE CASCADE,
  basis TEXT NOT NULL CHECK (basis IN ('sample', 'overlap')),
  paired_at INTEGER NOT NULL
);

-- 4. Primary tags selected for a reviewer check: each ambassador's first 25 usable primary tags, then 20%.
CREATE TABLE group_review_picks (
  submission_id INTEGER PRIMARY KEY REFERENCES submissions (id) ON DELETE CASCADE,
  basis TEXT NOT NULL CHECK (basis IN ('first_25', 'random_20')),
  selected_at INTEGER NOT NULL
);

-- 5. Reviewer checks, one row per Tier-1 facet: the ambassador's value, the reviewed value and, for an edit, a
--    reason code (config/groups_taxonomy.yml review_reason). The first complete review of a tag wins.
CREATE TABLE group_tag_reviews (
  submission_id INTEGER NOT NULL REFERENCES submissions (id) ON DELETE CASCADE,
  facet TEXT NOT NULL,
  outcome TEXT NOT NULL CHECK (outcome IN ('agree', 'edit')),
  original_value TEXT NOT NULL,
  reviewed_value TEXT NOT NULL,
  reason_code TEXT,
  reviewer_id TEXT REFERENCES ambassadors (id) ON DELETE SET NULL,
  reviewed_at INTEGER NOT NULL,
  PRIMARY KEY (submission_id, facet),
  CHECK ((outcome = 'agree' AND reason_code IS NULL AND reviewed_value = original_value)
      OR (outcome = 'edit' AND reason_code IS NOT NULL AND reviewed_value <> original_value))
);
CREATE INDEX group_tag_reviews_reviewed_at ON group_tag_reviews (reviewed_at);
