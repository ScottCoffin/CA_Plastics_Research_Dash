import { audit, currentAmbassador, type AmbassadorRow, type Ctx } from "./auth";
import type { Env } from "./env";
import { REGIONS, isRegion } from "./eligibility";
import { json } from "./http";
import { withinRateLimit } from "./rate_limit";

const HOUR_MS = 60 * 60 * 1000;
/** Per-account limit on moderation writes (decisions, promotions, suspensions). */
export const MODERATION_LIMIT = { limit: 200, windowMs: HOUR_MS };
const QUEUE_LIMIT = 200;
/** Control characters (except tab and newline) and angle brackets: no HTML in plain text fields. */
const UNSAFE_TEXT = /[<>\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/;

export type Role = "owner" | "lead" | "ambassador";

export function err(error: string, status: number, extra: Record<string, unknown> = {}): Response {
  return json({ ok: false, error, ...extra }, status);
}

/** A JSON object body, or null when the body is not a JSON object. */
export async function readBody(request: Request): Promise<Record<string, unknown> | null> {
  try {
    const body = (await request.json()) as unknown;
    if (!body || typeof body !== "object" || Array.isArray(body)) return null;
    return body as Record<string, unknown>;
  } catch {
    return null;
  }
}

/** Trimmed plain text of 1..max characters with no HTML and no control characters, or null. */
export function plainText(value: unknown, max: number): string | null {
  if (typeof value !== "string") return null;
  const text = value.trim();
  if (text.length === 0 || text.length > max || UNSAFE_TEXT.test(text)) return null;
  return text;
}

/**
 * The owner is the account whose ORCID equals OWNER_ORCID. A lead is an ambassador with role 'lead'. Everyone else is
 * an ambassador. The owner is never read from the database, so a stored role cannot grant it.
 */
export async function roleOf(db: D1Database, env: Env, a: AmbassadorRow): Promise<Role> {
  if (a.orcid && env.OWNER_ORCID && a.orcid === env.OWNER_ORCID) return "owner";
  const row = await db.prepare("SELECT role FROM ambassadors WHERE id = ?1").bind(a.id).first<{ role: string }>();
  return row?.role === "lead" ? "lead" : "ambassador";
}

export function isOwnerAccount(a: AmbassadorRow, env: Env): boolean {
  return Boolean(a.orcid && env.OWNER_ORCID && a.orcid === env.OWNER_ORCID);
}

/** Owners and leads moderate. Returns the caller and role, or an error response. */
export async function moderator(
  request: Request,
  env: Env,
  ctx: Ctx,
): Promise<{ a: AmbassadorRow; role: "owner" | "lead" } | { error: Response }> {
  const a = await currentAmbassador(request, env, ctx.now);
  if (!a) return { error: err("not_signed_in", 401) };
  const role = await roleOf(env.DB, env, a);
  if (role === "ambassador") return { error: err("forbidden", 403) };
  return { a, role };
}

/** Per-account fixed-window limit (keyed by the random ambassador id, never by email). */
export async function accountWithinLimit(
  db: D1Database,
  scope: string,
  ambassadorId: string,
  limit: number,
  windowMs: number,
  now: number,
): Promise<boolean> {
  return withinRateLimit(db, `account:${scope}`, ambassadorId, limit, windowMs, now);
}

/** GET /moderation/queue?region= : pending submissions and proposals. Owner and leads see every region. */
export async function handleQueue(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const m = await moderator(request, env, ctx);
  if ("error" in m) return m.error;
  const regionParam = new URL(request.url).searchParams.get("region");
  if (regionParam !== null && !isRegion(regionParam)) return err("invalid_region", 400, { regions: REGIONS });
  const region = regionParam;

  // Suspended accounts' pending items are hidden. A proposal has no region of its own: it is listed under a region
  // when its applicant holds that region, and only in the unfiltered queue otherwise.
  const submissions = await env.DB.prepare(
    "SELECT s.id, s.region, s.stream, s.kind, s.payload, s.created_at, s.ambassador_id, a.display_name " +
      "FROM submissions s JOIN ambassadors a ON a.id = s.ambassador_id " +
      "WHERE s.status = 'pending' AND a.status <> 'suspended' AND (?1 IS NULL OR s.region = ?1) " +
      "ORDER BY s.created_at, s.id LIMIT ?2",
  )
    .bind(region, QUEUE_LIMIT)
    .all<{
      id: number;
      region: string;
      stream: string;
      kind: string;
      payload: string;
      created_at: number;
      ambassador_id: string;
      display_name: string | null;
    }>();
  const proposals = await env.DB.prepare(
    "SELECT p.id, p.kind, p.payload, p.created_at, p.ambassador_id, a.display_name " +
      "FROM proposals p JOIN ambassadors a ON a.id = p.ambassador_id " +
      "WHERE p.status = 'pending' AND a.status <> 'suspended' " +
      "AND (?1 IS NULL OR EXISTS (SELECT 1 FROM ambassador_regions r WHERE r.ambassador_id = p.ambassador_id AND r.region = ?1)) " +
      "ORDER BY p.created_at, p.id LIMIT ?2",
  )
    .bind(region, QUEUE_LIMIT)
    .all<{ id: number; kind: string; payload: string; created_at: number; ambassador_id: string; display_name: string | null }>();

  return json({
    ok: true,
    region,
    submissions: submissions.results.map((s) => ({
      type: "submission",
      id: s.id,
      region: s.region,
      stream: s.stream,
      kind: s.kind,
      payload: JSON.parse(s.payload) as unknown,
      created_at: s.created_at,
      submitter: { display_name: s.display_name },
      own: s.ambassador_id === m.a.id,
    })),
    proposals: proposals.results.map((p) => ({
      type: "proposal",
      id: p.id,
      kind: p.kind,
      payload: JSON.parse(p.payload) as unknown,
      created_at: p.created_at,
      submitter: { display_name: p.display_name },
      own: p.ambassador_id === m.a.id,
    })),
  });
}

/**
 * POST /moderation/decide {type: submission|proposal, id, decision: approve|reject, note?}. The decision is recorded
 * and audited. Approving a proposal does not activate anyone: activation is a later slice.
 */
export async function handleDecide(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const m = await moderator(request, env, ctx);
  if ("error" in m) return m.error;
  const body = await readBody(request);
  if (!body) return err("invalid_request", 400);
  const type = body.type;
  if (type !== "submission" && type !== "proposal") return err("invalid_type", 400);
  const id = body.id;
  if (typeof id !== "number" || !Number.isSafeInteger(id) || id < 1) return err("invalid_id", 400);
  const decision = body.decision;
  if (decision !== "approve" && decision !== "reject") return err("invalid_decision", 400);
  let note: string | null = null;
  if (body.note !== undefined && body.note !== null) {
    note = plainText(body.note, 1000);
    if (note === null) return err("invalid_note", 400);
  }
  if (!(await accountWithinLimit(env.DB, "moderate", m.a.id, MODERATION_LIMIT.limit, MODERATION_LIMIT.windowMs, ctx.now))) {
    return err("rate_limited", 429);
  }

  // The table name comes from this fixed mapping, never from the request.
  const table = type === "submission" ? "submissions" : "proposals";
  const item = await env.DB.prepare(`SELECT ambassador_id, status FROM ${table} WHERE id = ?1`)
    .bind(id)
    .first<{ ambassador_id: string; status: string }>();
  if (!item) return err("not_found", 404);
  if (item.ambassador_id === m.a.id) return err("self_decision", 403);
  if (item.status !== "pending") return err("already_decided", 409);

  const status = decision === "approve" ? "approved" : "rejected";
  const changed = await env.DB.prepare(
    `UPDATE ${table} SET status = ?1, decided_at = ?2, decided_by = ?3, decision_note = ?4 WHERE id = ?5 AND status = 'pending'`,
  )
    .bind(status, ctx.now, m.a.id, note, id)
    .run();
  if (changed.meta.changes !== 1) return err("already_decided", 409);
  await audit(env.DB, ctx.now, "moderation.decide", m.a.id, { type, id, decision, by: m.role });
  return json({ ok: true, type, id, status });
}

/**
 * POST /moderation/leads {ambassador_id, region}: owner or lead promotes an active ambassador of that region to lead.
 * Idempotent for an existing lead of that region.
 */
export async function handlePromoteLead(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const m = await moderator(request, env, ctx);
  if ("error" in m) return m.error;
  const body = await readBody(request);
  if (!body) return err("invalid_request", 400);
  if (typeof body.ambassador_id !== "string" || body.ambassador_id.length === 0 || body.ambassador_id.length > 64) {
    return err("invalid_ambassador", 400);
  }
  if (!isRegion(body.region)) return err("invalid_region", 400, { regions: REGIONS });
  const region = body.region;
  if (!(await accountWithinLimit(env.DB, "moderate", m.a.id, MODERATION_LIMIT.limit, MODERATION_LIMIT.windowMs, ctx.now))) {
    return err("rate_limited", 429);
  }

  const target = await env.DB.prepare("SELECT id, orcid, status, role FROM ambassadors WHERE id = ?1")
    .bind(body.ambassador_id)
    .first<{ id: string; orcid: string | null; status: string; role: string }>();
  if (!target) return err("not_found", 404);
  if (target.id === m.a.id) return err("self_promotion", 403);
  if (target.orcid && target.orcid === env.OWNER_ORCID) return err("is_owner", 409);
  if (target.status !== "active") return err("not_active", 409);
  const member = await env.DB.prepare(
    "SELECT 1 AS ok FROM ambassador_regions WHERE ambassador_id = ?1 AND region = ?2 AND status = 'active'",
  )
    .bind(target.id, region)
    .first();
  if (!member) return err("not_region_member", 409);

  await env.DB.batch([
    env.DB.prepare(
      "INSERT OR IGNORE INTO region_leads (ambassador_id, region, promoted_by, promoted_at) VALUES (?1, ?2, ?3, ?4)",
    ).bind(target.id, region, m.a.id, ctx.now),
    env.DB.prepare("UPDATE ambassadors SET role = 'lead' WHERE id = ?1 AND role = 'ambassador'").bind(target.id),
  ]);
  await audit(env.DB, ctx.now, "moderation.lead", target.id, { region, by: m.role });
  return json({ ok: true, ambassador_id: target.id, region, role: "lead" });
}

/** POST /moderation/suspend {ambassador_id}: owner only. Sets status suspended and ends their sessions. */
export async function handleSuspend(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const a = await currentAmbassador(request, env, ctx.now);
  if (!a) return err("not_signed_in", 401);
  if (!isOwnerAccount(a, env)) return err("forbidden", 403);
  const body = await readBody(request);
  if (!body) return err("invalid_request", 400);
  if (typeof body.ambassador_id !== "string" || body.ambassador_id.length === 0 || body.ambassador_id.length > 64) {
    return err("invalid_ambassador", 400);
  }
  if (!(await accountWithinLimit(env.DB, "moderate", a.id, MODERATION_LIMIT.limit, MODERATION_LIMIT.windowMs, ctx.now))) {
    return err("rate_limited", 429);
  }
  const target = await env.DB.prepare("SELECT id, orcid FROM ambassadors WHERE id = ?1")
    .bind(body.ambassador_id)
    .first<{ id: string; orcid: string | null }>();
  if (!target) return err("not_found", 404);
  if (target.id === a.id || (target.orcid && target.orcid === env.OWNER_ORCID)) return err("cannot_suspend_owner", 409);

  await env.DB.batch([
    env.DB.prepare("UPDATE ambassadors SET status = 'suspended' WHERE id = ?1").bind(target.id),
    env.DB.prepare("DELETE FROM sessions WHERE ambassador_id = ?1").bind(target.id),
    env.DB.prepare("DELETE FROM signup_sessions WHERE ambassador_id = ?1").bind(target.id),
  ]);
  await audit(env.DB, ctx.now, "moderation.suspend", target.id, { by: "owner" });
  return json({ ok: true, ambassador_id: target.id, status: "suspended" });
}
