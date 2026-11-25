/**
 * Fixed-window counter in D1. Returns true while the count is within `limit` for the window.
 * Expired buckets are pruned on each call (the table stays small).
 */
export async function withinRateLimit(
  db: D1Database,
  scope: string,
  key: string,
  limit: number,
  windowMs: number,
  now: number,
): Promise<boolean> {
  const windowIndex = Math.floor(now / windowMs);
  const bucket = `${scope}:${key}:${windowIndex}`;
  const expiresAt = (windowIndex + 1) * windowMs;
  await db.prepare("DELETE FROM rate_limits WHERE expires_at < ?1").bind(now).run();
  const row = await db
    .prepare(
      "INSERT INTO rate_limits (bucket, count, expires_at) VALUES (?1, 1, ?2) " +
        "ON CONFLICT (bucket) DO UPDATE SET count = count + 1 RETURNING count",
    )
    .bind(bucket, expiresAt)
    .first<{ count: number }>();
  return row !== null && row.count <= limit;
}

export const EMAIL_LIMIT = { limit: 5, windowMs: 60 * 60 * 1000 };
export const IP_LIMIT = { limit: 30, windowMs: 60 * 60 * 1000 };
