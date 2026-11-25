import { keyedHash, randomHex, randomToken, sha256Hex, signSessionId, verifySignedSessionId } from "./crypto";
import { type Env, requireSecret } from "./env";
import { REGIONS, type Region, institutionName, isRegion, matchInstitution } from "./eligibility";
import { SESSION_COOKIE, SESSION_MAX_AGE_S, clearSessionCookie, json, readCookie, redirect, sessionCookie } from "./http";
import { chooseSender } from "./mail";
import { EMAIL_LIMIT, IP_LIMIT, withinRateLimit } from "./rate_limit";
import { verifyTurnstile } from "./turnstile";

const MINUTE_MS = 60 * 1000;
const LINK_TTL_MS = 30 * MINUTE_MS;
const SESSION_TTL_MS = SESSION_MAX_AGE_S * 1000;
// One answer whether or not the address qualifies (no account enumeration).
const GENERIC_START_MESSAGE =
  "If this address belongs to an eligible institution, a sign-in link has been sent. The link expires in 30 minutes.";
const EMAIL_RE = /^[^\s@]{1,64}@[^\s@]{1,253}\.[^\s@]{2,}$/;

export interface Ctx {
  now: number;
}

interface AmbassadorRow {
  id: string;
  email: string;
  region: string;
  institution_id: string;
  display_name: string | null;
  public_credit: number;
  consent_at: number | null;
  status: string;
}

function maskEmail(email: string): string {
  const at = email.indexOf("@");
  return `${email.slice(0, 1)}***${email.slice(at)}`;
}

async function audit(db: D1Database, now: number, action: string, subject: string | null, detail: object): Promise<void> {
  await db
    .prepare("INSERT INTO audit_log (at, action, subject, detail) VALUES (?1, ?2, ?3, ?4)")
    .bind(now, action, subject, JSON.stringify(detail))
    .run();
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

  const signingKey = requireSecret(env.SESSION_SIGNING_KEY, "SESSION_SIGNING_KEY");
  const emailHash = await keyedHash(signingKey, "email", email);
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
    "SELECT email, email_hash, region, institution_id FROM magic_links " +
      "WHERE token_hash = ?1 AND used_at IS NULL AND expires_at > ?2",
  )
    .bind(tokenHash, ctx.now)
    .first<{ email: string | null; email_hash: string; region: string; institution_id: string }>();
  if (!link || !link.email) return failure();

  // Claim atomically: only one request can change used_at from NULL.
  const claimed = await env.DB.prepare(
    "UPDATE magic_links SET used_at = ?1, email = NULL WHERE token_hash = ?2 AND used_at IS NULL AND expires_at > ?1",
  )
    .bind(ctx.now, tokenHash)
    .run();
  if (claimed.meta.changes !== 1) return failure();

  const ambassadorId = randomHex(16);
  await env.DB.prepare(
    "INSERT INTO ambassadors (id, email_hash, email, region, institution_id, created_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6) " +
      "ON CONFLICT (email_hash) DO NOTHING",
  )
    .bind(ambassadorId, link.email_hash, link.email, link.region, link.institution_id, ctx.now)
    .run();
  const row = await env.DB.prepare("SELECT id, status FROM ambassadors WHERE email_hash = ?1")
    .bind(link.email_hash)
    .first<{ id: string; status: string }>();
  if (!row || row.status !== "active") return failure();

  const signingKey = requireSecret(env.SESSION_SIGNING_KEY, "SESSION_SIGNING_KEY");
  const sessionId = randomToken(32);
  await env.DB.prepare("INSERT INTO sessions (id_hash, ambassador_id, created_at, expires_at) VALUES (?1, ?2, ?3, ?4)")
    .bind(await sha256Hex(sessionId), row.id, ctx.now, ctx.now + SESSION_TTL_MS)
    .run();
  await audit(env.DB, ctx.now, "auth.verify", link.email_hash, { region: link.region });
  return redirect(env.WORKSPACE_URL, { "Set-Cookie": sessionCookie(await signSessionId(signingKey, sessionId)) });
}

/** Resolves the signed session cookie to an active ambassador, or null. */
export async function currentAmbassador(request: Request, env: Env, now: number): Promise<AmbassadorRow | null> {
  const cookie = readCookie(request, SESSION_COOKIE);
  if (!cookie || !env.SESSION_SIGNING_KEY) return null;
  const sessionId = await verifySignedSessionId(env.SESSION_SIGNING_KEY, cookie);
  if (!sessionId) return null;
  return env.DB.prepare(
    "SELECT a.id, a.email, a.region, a.institution_id, a.display_name, a.public_credit, a.consent_at, a.status " +
      "FROM sessions s JOIN ambassadors a ON a.id = s.ambassador_id " +
      "WHERE s.id_hash = ?1 AND s.expires_at > ?2 AND a.status = 'active'",
  )
    .bind(await sha256Hex(sessionId), now)
    .first<AmbassadorRow>();
}

/** GET /me: the profile, with the email masked. */
export async function handleMe(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const a = await currentAmbassador(request, env, ctx.now);
  if (!a) return json({ ok: false, error: "not_signed_in" }, 401);
  const region = a.region as Region;
  return json({
    ok: true,
    ambassador: {
      id: a.id,
      email_masked: maskEmail(a.email),
      region: a.region,
      institution: { id: a.institution_id, name: institutionName(region, a.institution_id) },
      display_name: a.display_name,
      public_credit: a.public_credit === 1,
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
