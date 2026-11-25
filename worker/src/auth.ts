import { keyedHash, randomHex, randomToken, sha256Hex, signSessionId, verifySignedSessionId } from "./crypto";
import { type Env, requireSecret } from "./env";
import { REGIONS, type Region, institutionDisplayName, institutionName, isRegion, matchInstitution } from "./eligibility";
import type { Fetch } from "./outbound";
import { SESSION_COOKIE, SESSION_MAX_AGE_S, clearSessionCookie, json, readCookie, redirect, sessionCookie } from "./http";
import { chooseSender } from "./mail";
import { EMAIL_LIMIT, IP_LIMIT, withinRateLimit } from "./rate_limit";
import { verifyTurnstile } from "./turnstile";

const MINUTE_MS = 60 * 1000;
export const LINK_TTL_MS = 30 * MINUTE_MS;
const SESSION_TTL_MS = SESSION_MAX_AGE_S * 1000;
// One answer whether or not the address qualifies (no account enumeration).
const GENERIC_START_MESSAGE =
  "If this address belongs to an eligible institution, a sign-in link has been sent. The link expires in 30 minutes.";
export const EMAIL_RE = /^[^\s@]{1,64}@[^\s@]{1,253}\.[^\s@]{2,}$/;

export interface Ctx {
  now: number;
  /** Outbound HTTP (ORCID, OpenAlex). Injected so tests can answer without the network. */
  fetch: Fetch;
}

/** The ambassador columns a session needs. email, region and institution_id are null while pending. */
export interface AmbassadorRow {
  id: string;
  email: string | null;
  region: string | null;
  institution_id: string | null;
  display_name: string | null;
  credit_public: number;
  consent_at: number | null;
  orcid: string | null;
  author_id: string | null;
  status: string;
}

export interface MagicLinkRow {
  email: string | null;
  email_hash: string;
  region: string;
  institution_id: string;
  ambassador_id: string | null;
}

export function maskEmail(email: string): string {
  const at = email.indexOf("@");
  return `${email.slice(0, 1)}***${email.slice(at)}`;
}

export async function audit(db: D1Database, now: number, action: string, subject: string | null, detail: object): Promise<void> {
  await db
    .prepare("INSERT INTO audit_log (at, action, subject, detail) VALUES (?1, ?2, ?3, ?4)")
    .bind(now, action, subject, JSON.stringify(detail))
    .run();
}

/** Stores a session row (hash only) and returns the signed cookie value. */
export async function createSession(env: Env, ambassadorId: string, now: number): Promise<string> {
  const signingKey = requireSecret(env.SESSION_SIGNING_KEY, "SESSION_SIGNING_KEY");
  const sessionId = randomToken(32);
  await env.DB.prepare("INSERT INTO sessions (id_hash, ambassador_id, created_at, expires_at) VALUES (?1, ?2, ?3, ?4)")
    .bind(await sha256Hex(sessionId), ambassadorId, now, now + SESSION_TTL_MS)
    .run();
  return signSessionId(signingKey, sessionId);
}

/** POST /auth/start {email, region, turnstileToken} */
export async function handleStart(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  let body: { email?: unknown; region?: unknown; turnstileToken?: unknown };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return json({ ok: false, error: "invalid_request" }, 400);
  }
  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  if (!email || email.length > 254 || !EMAIL_RE.test(email)) {
    return json({ ok: false, error: "invalid_email" }, 400);
  }
  if (!isRegion(body.region)) return json({ ok: false, error: "invalid_region", regions: REGIONS }, 400);
  const region: Region = body.region;
  const turnstileToken = typeof body.turnstileToken === "string" ? body.turnstileToken.slice(0, 2048) : "";

  const ip = request.headers.get("CF-Connecting-IP");
  if (!(await verifyTurnstile(env.TURNSTILE_SECRET, turnstileToken, ip))) {
    return json({ ok: false, error: "bot_check_failed" }, 403);
  }

  const emailHash = await keyedHash(requireSecret(env.EMAIL_HASH_KEY, "EMAIL_HASH_KEY"), "email", email);
  // Limits count every request, eligible or not, so they reveal nothing about the address.
  const emailOk = await withinRateLimit(env.DB, "email", emailHash, EMAIL_LIMIT.limit, EMAIL_LIMIT.windowMs, ctx.now);
  const ipKey = await sha256Hex(ip ?? "unknown");
  const ipOk = await withinRateLimit(env.DB, "ip", ipKey, IP_LIMIT.limit, IP_LIMIT.windowMs, ctx.now);
  if (!emailOk || !ipOk) return json({ ok: false, error: "rate_limited" }, 429);

  const match = matchInstitution(region, email.slice(email.indexOf("@") + 1));
  let outcome = "not_eligible";
  if (match) {
    try {
      const token = randomToken(32);
      await env.DB.prepare(
        "INSERT INTO magic_links (token_hash, email_hash, email, region, institution_id, created_at, expires_at) " +
          "VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
      )
        .bind(await sha256Hex(token), emailHash, email, region, match.institutionId, ctx.now, ctx.now + LINK_TTL_MS)
        .run();
      const link = `${env.PUBLIC_API_URL}/auth/verify?token=${token}`;
      await chooseSender(env).send({
        to: email,
        subject: "Your Plastiverse ambassador sign-in link",
        text:
          `Sign in to the Plastiverse ambassador workspace (valid 30 minutes, one use):\n\n${link}\n\n` +
          "If you did not ask for this, ignore this message.",
      });
      outcome = "sent";
    } catch (err) {
      // Same response either way; the failure is logged (class only), never shown to the caller.
      console.error("sign-in send failed", err instanceof Error ? err.name : "unknown");
      outcome = "send_failed";
    }
  }
  await audit(env.DB, ctx.now, "auth.start", emailHash, { region, outcome });
  return json({ ok: true, message: GENERIC_START_MESSAGE });
}

/**
 * Activates an ORCID sign-up once its institutional email is proven: the pending ambassador gets the email and
 * its hash, claimed institutions and pending regions become active, and the signup session ends.
 * Returns false when the ambassador cannot take this email (already in use, or not pending).
 */
async function activatePendingAmbassador(env: Env, link: MagicLinkRow & { email: string }, now: number): Promise<boolean> {
  const id = link.ambassador_id as string;
  const pending = await env.DB.prepare("SELECT status FROM ambassadors WHERE id = ?1").bind(id).first<{ status: string }>();
  if (!pending || pending.status !== "pending") return false;
  const taken = await env.DB.prepare("SELECT id FROM ambassadors WHERE email_hash = ?1 AND id <> ?2")
    .bind(link.email_hash, id)
    .first();
  if (taken) return false;
  try {
    // One atomic batch. The first statement only applies while pending; the others are idempotent.
    await env.DB.batch([
      env.DB.prepare(
        "UPDATE ambassadors SET status = 'active', email = ?1, email_hash = ?2, region = ?3, institution_id = ?4 " +
          "WHERE id = ?5 AND status = 'pending'",
      ).bind(link.email, link.email_hash, link.region, link.institution_id, id),
      env.DB.prepare("UPDATE ambassador_institutions SET claimed_at = ?1 WHERE ambassador_id = ?2 AND eligible = 1").bind(now, id),
      env.DB.prepare(
        "UPDATE ambassador_regions SET status = 'active', joined_at = ?1 WHERE ambassador_id = ?2 AND status = 'pending_email'",
      ).bind(now, id),
      env.DB.prepare("DELETE FROM signup_sessions WHERE ambassador_id = ?1").bind(id),
    ]);
  } catch (err) {
    console.error("signup activation failed", err instanceof Error ? err.name : "unknown");
    return false;
  }
  const after = await env.DB.prepare("SELECT status FROM ambassadors WHERE id = ?1").bind(id).first<{ status: string }>();
  return after?.status === "active";
}

/** GET /auth/verify?token= : single-use link, then a session cookie and a redirect to the workspace. */
export async function handleVerify(url: URL, env: Env, ctx: Ctx): Promise<Response> {
  const failure = (): Response => {
    const target = new URL(env.WORKSPACE_URL);
    target.searchParams.set("signin", "failed");
    return redirect(target.toString());
  };
  const token = url.searchParams.get("token") ?? "";
  if (!/^[A-Za-z0-9_-]{43}$/.test(token)) return failure();

  const tokenHash = await sha256Hex(token);
  const link = await env.DB.prepare(
    "SELECT email, email_hash, region, institution_id, ambassador_id FROM magic_links " +
      "WHERE token_hash = ?1 AND used_at IS NULL AND expires_at > ?2",
  )
    .bind(tokenHash, ctx.now)
    .first<MagicLinkRow>();
  if (!link || !link.email) return failure();

  // Claim atomically: only one request can change used_at from NULL.
  const claimed = await env.DB.prepare(
    "UPDATE magic_links SET used_at = ?1, email = NULL WHERE token_hash = ?2 AND used_at IS NULL AND expires_at > ?1",
  )
    .bind(ctx.now, tokenHash)
    .run();
  if (claimed.meta.changes !== 1) return failure();

  let ambassadorId: string;
  if (link.ambassador_id) {
    // ORCID-first sign-up (slice 2a): the link belongs to a pending ambassador.
    const ok = await activatePendingAmbassador(env, { ...link, email: link.email }, ctx.now);
    if (!ok) return failure();
    ambassadorId = link.ambassador_id;
    await audit(env.DB, ctx.now, "signup.email_confirmed", link.email_hash, { region: link.region });
  } else {
    // Slice-1 email-first route, kept for compatibility (the UI uses ORCID-first).
    await env.DB.prepare(
      "INSERT INTO ambassadors (id, email_hash, email, region, institution_id, created_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6) " +
        "ON CONFLICT (email_hash) DO NOTHING",
    )
      .bind(randomHex(16), link.email_hash, link.email, link.region, link.institution_id, ctx.now)
      .run();
    const row = await env.DB.prepare("SELECT id, status FROM ambassadors WHERE email_hash = ?1")
      .bind(link.email_hash)
      .first<{ id: string; status: string }>();
    if (!row || row.status !== "active") return failure();
    ambassadorId = row.id;
    await env.DB.prepare(
      "INSERT OR IGNORE INTO ambassador_regions (ambassador_id, region, status, joined_at) VALUES (?1, ?2, 'active', ?3)",
    )
      .bind(ambassadorId, link.region, ctx.now)
      .run();
    await audit(env.DB, ctx.now, "auth.verify", link.email_hash, { region: link.region });
  }

  const cookie = await createSession(env, ambassadorId, ctx.now);
  return redirect(env.WORKSPACE_URL, { "Set-Cookie": sessionCookie(cookie) });
}

/** Resolves the signed session cookie to an active ambassador, or null. */
export async function currentAmbassador(request: Request, env: Env, now: number): Promise<AmbassadorRow | null> {
  const cookie = readCookie(request, SESSION_COOKIE);
  if (!cookie || !env.SESSION_SIGNING_KEY) return null;
  const sessionId = await verifySignedSessionId(env.SESSION_SIGNING_KEY, cookie);
  if (!sessionId) return null;
  return env.DB.prepare(
    "SELECT a.id, a.email, a.region, a.institution_id, a.display_name, a.credit_public, a.consent_at, a.orcid, a.author_id, a.status " +
      "FROM sessions s JOIN ambassadors a ON a.id = s.ambassador_id " +
      "WHERE s.id_hash = ?1 AND s.expires_at > ?2 AND a.status = 'active'",
  )
    .bind(await sha256Hex(sessionId), now)
    .first<AmbassadorRow>();
}

/** GET /me: the profile (email masked), ORCID link, claimed institutions and regions. */
export async function handleMe(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const a = await currentAmbassador(request, env, ctx.now);
  if (!a) return json({ ok: false, error: "not_signed_in" }, 401);
  const institutions = await env.DB.prepare(
    "SELECT institution_id, source, eligible FROM ambassador_institutions " +
      "WHERE ambassador_id = ?1 AND claimed_at IS NOT NULL ORDER BY eligible DESC, institution_id",
  )
    .bind(a.id)
    .all<{ institution_id: string; source: string; eligible: number }>();
  const regions = await env.DB.prepare(
    "SELECT region, status, joined_at FROM ambassador_regions WHERE ambassador_id = ?1 ORDER BY region",
  )
    .bind(a.id)
    .all<{ region: string; status: string; joined_at: number }>();
  const homeRegion = a.region && isRegion(a.region) ? a.region : null;
  return json({
    ok: true,
    ambassador: {
      id: a.id,
      orcid: a.orcid,
      author_id: a.author_id,
      email_masked: a.email ? maskEmail(a.email) : null,
      region: a.region,
      institution:
        a.institution_id === null
          ? null
          : { id: a.institution_id, name: homeRegion ? institutionName(homeRegion, a.institution_id) : null },
      institutions: institutions.results.map((r) => ({
        id: r.institution_id,
        name: institutionDisplayName(r.institution_id),
        source: r.source,
        eligible: r.eligible === 1,
      })),
      regions: regions.results.map((r) => ({ region: r.region, status: r.status, joined_at: r.joined_at })),
      display_name: a.display_name,
      public_credit: a.credit_public === 1,
      consent_given: a.consent_at !== null,
      needs_profile: a.display_name === null || a.consent_at === null,
    },
  });
}

/** POST /auth/signout: idempotent. Deletes the server-side session and clears the cookie. */
export async function handleSignout(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const cookie = readCookie(request, SESSION_COOKIE);
  if (cookie && env.SESSION_SIGNING_KEY) {
    const sessionId = await verifySignedSessionId(env.SESSION_SIGNING_KEY, cookie);
    if (sessionId) {
      await env.DB.prepare("DELETE FROM sessions WHERE id_hash = ?1").bind(await sha256Hex(sessionId)).run();
    }
  }
  await audit(env.DB, ctx.now, "auth.signout", null, {});
  return json({ ok: true }, 200, { "Set-Cookie": clearSessionCookie() });
}
