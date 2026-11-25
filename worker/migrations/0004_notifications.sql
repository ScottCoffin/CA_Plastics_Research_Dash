-- AMB-1 slice 2c: notifications, one-click unsubscribe, welcome mail, invitations, fortnightly reminders (LOCAL ONLY).
-- Times are Unix milliseconds (INTEGER).
--
-- Privacy: unsubscribe and invitation tokens are stored only as SHA-256 hashes. No email address is added to any
-- new table. Invitations record a count of sign-ups and never the invitee's identity. Co-authors' addresses are never
-- stored: the ambassador sends the invitation from their own mail program (mailto, no recipient).

-- 1. Activity and reminder state on the ambassador. last_seen_at is set on sign-in. welcome_sent_at marks the one
--    welcome mail. reminders_unanswered counts reminders with no answer since (paused at 3). last_reminder_at anchors
--    the fortnight.
ALTER TABLE ambassadors ADD COLUMN last_seen_at INTEGER;
ALTER TABLE ambassadors ADD COLUMN welcome_sent_at INTEGER;
ALTER TABLE ambassadors ADD COLUMN reminders_unanswered INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ambassadors ADD COLUMN last_reminder_at INTEGER;

-- 2. Notification preferences. No row means the defaults: reminders on, product news off.
CREATE TABLE notification_prefs (
  ambassador_id TEXT PRIMARY KEY REFERENCES ambassadors (id) ON DELETE CASCADE,
  reminders INTEGER NOT NULL DEFAULT 1 CHECK (reminders IN (0, 1)),
  product_news INTEGER NOT NULL DEFAULT 0 CHECK (product_news IN (0, 1)),
  updated_at INTEGER NOT NULL
);

-- 3. One-click unsubscribe tokens. Each non-essential mail carries its own token (a new row), so links in older mail
--    keep working. Only the hash is stored; the token is shown in the mail and never again.
CREATE TABLE unsubscribe_tokens (
  token_hash TEXT PRIMARY KEY,
  ambassador_id TEXT NOT NULL REFERENCES ambassadors (id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL
);
CREATE INDEX unsubscribe_tokens_ambassador_id ON unsubscribe_tokens (ambassador_id);

-- 4. Personal invitation links. Rate limit: 50 per ambassador in 30 days (counted from created_at).
--    signups counts sign-ups that arrived with the link; nothing else is recorded.
CREATE TABLE invitations (
  token_hash TEXT PRIMARY KEY,               -- SHA-256 of the 32-byte random token
  ambassador_id TEXT NOT NULL REFERENCES ambassadors (id) ON DELETE CASCADE,
  created_at INTEGER NOT NULL,
  signups INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX invitations_ambassador_created ON invitations (ambassador_id, created_at);

-- 5. A magic link may carry the invitation token hash (sent by the public page as `invite` on POST /auth/start).
ALTER TABLE magic_links ADD COLUMN invite_hash TEXT;

-- 6. LOCAL DEV AND TESTS ONLY: the outbox keeps the mail headers so tests can check List-Unsubscribe.
ALTER TABLE outbox ADD COLUMN headers TEXT;
