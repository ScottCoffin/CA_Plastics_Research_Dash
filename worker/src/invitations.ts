import { randomToken, sha256Hex } from "./crypto";
import { type Ctx, currentAmbassador } from "./auth";
import type { Env } from "./env";
import { json, redirect } from "./http";
import { invitationText, mailtoHref } from "./templates";

const DAY_MS = 24 * 60 * 60 * 1000;
/** Owner limit: at most 50 invitation links per ambassador in any 30 days. */
export const INVITE_LIMIT = 50;
export const INVITE_WINDOW_MS = 30 * DAY_MS;
const TOKEN_RE = /^[A-Za-z0-9_-]{43}$/;

/**
 * POST /invitations (session): a personal invitation link and a mailto: href with the subject and body pre-filled.
 * No recipient address is accepted, returned or stored. Only the token's hash is stored.
 */
export async function handleCreateInvitation(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const a = await currentAmbassador(request, env, ctx.now);
  if (!a) return json({ ok: false, error: "not_signed_in" }, 401);
  const recent = await env.DB.prepare(
    "SELECT COUNT(*) AS n FROM invitations WHERE ambassador_id = ?1 AND created_at > ?2",
  )
    .bind(a.id, ctx.now - INVITE_WINDOW_MS)
    .first<{ n: number }>();
  if ((recent?.n ?? 0) >= INVITE_LIMIT) return json({ ok: false, error: "rate_limited" }, 429);

  const token = randomToken(32);
  await env.DB.prepare("INSERT INTO invitations (token_hash, ambassador_id, created_at, signups) VALUES (?1, ?2, ?3, 0)")
    .bind(await sha256Hex(token), a.id, ctx.now)
    .run();
  const url = `${env.PUBLIC_API_URL}/invite?t=${token}`;
  const text = invitationText(url);
  return json({ ok: true, url, mailto: mailtoHref(text.subject, text.body) });
}

/**
 * GET /invite?t=: records nothing (no lookup, no cookie, no log of the token) and redirects to the public ambassadors
 * page with ?invited=1.
 */
export function handleInvite(env: Env): Response {
  return redirect(`${env.SITE_ORIGIN}/ambassadors?invited=1`);
}

/** Counts one sign-up that arrived with an invitation (a count only). Never records who signed up. */
export async function countInvitationSignup(db: D1Database, inviteHash: string | null, newAmbassadorId: string): Promise<void> {
  if (!inviteHash) return;
  await db
    .prepare("UPDATE invitations SET signups = signups + 1 WHERE token_hash = ?1 AND ambassador_id <> ?2")
    .bind(inviteHash, newAmbassadorId)
    .run();
}

/** Hash of an invitation token from a request body, or null when the value is not a well-formed token. */
export async function inviteHashOf(value: unknown): Promise<string | null> {
  return typeof value === "string" && TOKEN_RE.test(value) ? sha256Hex(value) : null;
}
