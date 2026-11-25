import { randomToken, sha256Hex } from "./crypto";
import type { Env } from "./env";
import { type Ctx, currentAmbassador } from "./auth";
import { json } from "./http";
import { chooseSender } from "./mail";
import { type MailLinks, escapeHtml, listUnsubscribeHeaders, regionName, welcomeMail } from "./templates";

const TOKEN_RE = /^[A-Za-z0-9_-]{43}$/;

export interface Prefs {
  reminders: boolean;
  product_news: boolean;
}

/** Defaults when no row exists: reminders on, product news off. */
export const DEFAULT_PREFS: Prefs = { reminders: true, product_news: false };

export async function readPrefs(db: D1Database, ambassadorId: string): Promise<Prefs> {
  const row = await db
    .prepare("SELECT reminders, product_news FROM notification_prefs WHERE ambassador_id = ?1")
    .bind(ambassadorId)
    .first<{ reminders: number; product_news: number }>();
  if (!row) return { ...DEFAULT_PREFS };
  return { reminders: row.reminders === 1, product_news: row.product_news === 1 };
}

/**
 * Issues a fresh unsubscribe token for one mail. Only its SHA-256 hash is stored; older links keep working because
 * each mail gets its own row. Returns the links every non-essential mail must carry.
 */
export async function mintLinks(env: Env, ambassadorId: string, now: number): Promise<MailLinks> {
  const token = randomToken(32);
  await env.DB.prepare("INSERT INTO unsubscribe_tokens (token_hash, ambassador_id, created_at) VALUES (?1, ?2, ?3)")
    .bind(await sha256Hex(token), ambassadorId, now)
    .run();
  return {
    settingsUrl: `${env.WORKSPACE_URL}#notifications`,
    unsubscribeUrl: `${env.PUBLIC_API_URL}/unsubscribe?t=${token}`,
  };
}

/**
 * Called on every sign-in (auth.ts /auth/verify). Records last_seen_at and resets the unanswered-reminder counter,
 * so reminders resume when the ambassador returns.
 */
export async function markSignedIn(db: D1Database, ambassadorId: string, now: number): Promise<void> {
  await db
    .prepare("UPDATE ambassadors SET last_seen_at = ?1, reminders_unanswered = 0 WHERE id = ?2")
    .bind(now, ambassadorId)
    .run();
}

/**
 * Welcome mail, once per ambassador (welcome_sent_at is claimed by a conditional UPDATE). Returns true when this call
 * is the first join, so the caller can count an invitation sign-up. A failed send releases the claim so the next
 * sign-in retries it.
 */
export async function queueWelcome(env: Env, ambassadorId: string, now: number): Promise<boolean> {
  const claim = await env.DB.prepare(
    "UPDATE ambassadors SET welcome_sent_at = ?1 WHERE id = ?2 AND status = 'active' AND welcome_sent_at IS NULL",
  )
    .bind(now, ambassadorId)
    .run();
  if (claim.meta.changes !== 1) return false;
  const row = await env.DB.prepare("SELECT email, region FROM ambassadors WHERE id = ?1 AND status = 'active'")
    .bind(ambassadorId)
    .first<{ email: string | null; region: string | null }>();
  if (!row?.email || !row.region) return true;
  try {
    const links = await mintLinks(env, ambassadorId, now);
    const mail = welcomeMail({
      regionName: regionName(row.region),
      workspaceUrl: env.WORKSPACE_URL,
      links,
    });
    await chooseSender(env).send({
      to: row.email,
      subject: mail.subject,
      text: mail.text,
      html: mail.html,
      headers: listUnsubscribeHeaders(links.unsubscribeUrl),
    });
  } catch (err) {
    console.error("welcome send failed", err instanceof Error ? err.name : "unknown");
    await env.DB.prepare("UPDATE ambassadors SET welcome_sent_at = NULL WHERE id = ?1").bind(ambassadorId).run();
  }
  return true;
}

/** Looks up an unsubscribe token (hash only). Returns the ambassador id or null. */
async function ambassadorForUnsubscribe(db: D1Database, token: string | null): Promise<string | null> {
  if (!token || !TOKEN_RE.test(token)) return null;
  const row = await db
    .prepare("SELECT t.ambassador_id FROM unsubscribe_tokens t JOIN ambassadors a ON a.id = t.ambassador_id WHERE t.token_hash = ?1")
    .bind(await sha256Hex(token))
    .first<{ ambassador_id: string }>();
  return row?.ambassador_id ?? null;
}

function htmlPage(status: number, title: string, bodyHtml: string): Response {
  return new Response(
    `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${escapeHtml(title)}</title></head>` +
      `<body><main><h1>${escapeHtml(title)}</h1>${bodyHtml}</main></body></html>`,
    {
      status,
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; form-action 'self'",
      },
    },
  );
}

/** GET /unsubscribe?t=: a confirmation page only. It changes nothing (mail scanners may open links). */
export async function handleUnsubscribePage(url: URL, env: Env): Promise<Response> {
  const token = url.searchParams.get("t");
  if ((await ambassadorForUnsubscribe(env.DB, token)) === null) {
    return htmlPage(404, "This link is not valid", "<p>The unsubscribe link is not valid. Sign in to change notification settings.</p>");
  }
  return htmlPage(
    200,
    "Turn off reminders?",
    `<p>You will stop receiving reminders about open tasks in the Plastiverse ambassador workspace.</p>` +
      `<form method="post" action="/unsubscribe?t=${encodeURIComponent(token ?? "")}">` +
      `<button type="submit">Turn off reminders</button></form>`,
  );
}

/** POST /unsubscribe?t= (RFC 8058 one-click, or the confirmation form): turns reminders off. */
export async function handleUnsubscribe(url: URL, env: Env, now: number): Promise<Response> {
  const ambassadorId = await ambassadorForUnsubscribe(env.DB, url.searchParams.get("t"));
  if (ambassadorId === null) {
    return htmlPage(404, "This link is not valid", "<p>The unsubscribe link is not valid.</p>");
  }
  await env.DB.prepare(
    "INSERT INTO notification_prefs (ambassador_id, reminders, product_news, updated_at) VALUES (?1, 0, 0, ?2) " +
      "ON CONFLICT (ambassador_id) DO UPDATE SET reminders = 0, updated_at = excluded.updated_at",
  )
    .bind(ambassadorId, now)
    .run();
  return htmlPage(
    200,
    "You are unsubscribed",
    "<p>You will no longer receive reminders. You can turn them back on in the workspace notification settings.</p>",
  );
}

/** GET /me/notifications (session). */
export async function handleGetNotifications(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const a = await currentAmbassador(request, env, ctx.now);
  if (!a) return json({ ok: false, error: "not_signed_in" }, 401);
  return json({ ok: true, notifications: await readPrefs(env.DB, a.id) });
}

/** POST /me/notifications (session) {reminders?: boolean, product_news?: boolean}. Booleans only, at least one key. */
export async function handleSetNotifications(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const a = await currentAmbassador(request, env, ctx.now);
  if (!a) return json({ ok: false, error: "not_signed_in" }, 401);
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return json({ ok: false, error: "invalid_request" }, 400);
  }
  if (typeof body !== "object" || body === null || Array.isArray(body)) return json({ ok: false, error: "invalid_request" }, 400);
  const input = body as Record<string, unknown>;
  const keys = ["reminders", "product_news"] as const;
  const given = keys.filter((k) => k in input);
  if (given.length === 0) return json({ ok: false, error: "invalid_request" }, 400);
  for (const k of given) {
    if (typeof input[k] !== "boolean") return json({ ok: false, error: "invalid_value", field: k }, 400);
  }
  const next: Prefs = { ...(await readPrefs(env.DB, a.id)) };
  for (const k of given) next[k] = input[k] as boolean;
  await env.DB.prepare(
    "INSERT INTO notification_prefs (ambassador_id, reminders, product_news, updated_at) VALUES (?1, ?2, ?3, ?4) " +
      "ON CONFLICT (ambassador_id) DO UPDATE SET reminders = excluded.reminders, " +
      "product_news = excluded.product_news, updated_at = excluded.updated_at",
  )
    .bind(a.id, next.reminders ? 1 : 0, next.product_news ? 1 : 0, ctx.now)
    .run();
  return json({ ok: true, notifications: next });
}
