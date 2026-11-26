const DAY_MS = 24 * 60 * 60 * 1000;
/** A pending sign-up with no confirmed email is removed after this long. */
export const STALE_PENDING_MS = 7 * DAY_MS;

export interface CleanupCounts {
  orcid_states: number;
  signup_sessions: number;
  magic_links: number;
  pending_ambassadors: number;
}

/**
 * Nightly cleanup (cron "17 3 * * *"). Deletes only expired ORCID states, sign-up sessions and magic links, and
 * pending ambassadors older than 7 days that never proved an email. Active and suspended accounts are never touched, and
 * neither are ambassadors with review_state 'pending_review' (an unlisted institution waiting for a moderator; owner
 * 2026-11-26).
 * Returns counts only (no identifiers, no emails) for the log.
 */
export async function runCleanup(db: D1Database, now: number): Promise<CleanupCounts> {
  const staleSet =
    "SELECT id FROM ambassadors WHERE status = 'pending' AND email_hash IS NULL AND review_state IS NULL AND created_at < ?1";
  const staleCutoff = now - STALE_PENDING_MS;
  const results = await db.batch([
    db.prepare("DELETE FROM orcid_states WHERE expires_at < ?1").bind(now),
    db.prepare("DELETE FROM signup_sessions WHERE expires_at < ?1").bind(now),
    db.prepare("DELETE FROM magic_links WHERE expires_at < ?1").bind(now),
    // Children of the stale pending sign-ups first, then the sign-ups themselves (one atomic batch).
    db.prepare(`DELETE FROM proposals WHERE ambassador_id IN (${staleSet})`).bind(staleCutoff),
    db.prepare(`DELETE FROM ambassador_institutions WHERE ambassador_id IN (${staleSet})`).bind(staleCutoff),
    db.prepare(`DELETE FROM ambassador_regions WHERE ambassador_id IN (${staleSet})`).bind(staleCutoff),
    db.prepare(`DELETE FROM signup_sessions WHERE ambassador_id IN (${staleSet})`).bind(staleCutoff),
    db.prepare(`DELETE FROM magic_links WHERE ambassador_id IN (${staleSet})`).bind(staleCutoff),
    db.prepare("DELETE FROM ambassadors WHERE status = 'pending' AND email_hash IS NULL AND review_state IS NULL AND created_at < ?1").bind(staleCutoff),
  ]);
  return {
    orcid_states: results[0].meta.changes ?? 0,
    signup_sessions: results[1].meta.changes ?? 0,
    magic_links: results[2].meta.changes ?? 0,
    pending_ambassadors: results[8].meta.changes ?? 0,
  };
}
