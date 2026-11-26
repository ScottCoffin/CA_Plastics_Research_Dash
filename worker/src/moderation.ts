import { audit, currentAmbassador, type AmbassadorRow, type Ctx } from "./auth";
import type { Env } from "./env";
import { DOMAIN_RE, REGIONS, isRegion, type Region } from "./eligibility";
import { queueWelcome } from "./notifications";
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
      "AND NOT (s.kind = 'group_tag' AND json_extract(s.payload, '$.second_tag_for') IS NOT NULL) " +
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
    "SELECT p.id, p.kind, p.payload, p.created_at, p.ambassador_id, a.display_name, p.proposed_region, p.proposed_domain, " +
      "p.email_confirmed_at, p.confirmed_domain " +
      "FROM proposals p JOIN ambassadors a ON a.id = p.ambassador_id " +
      "WHERE p.status = 'pending' AND a.status <> 'suspended' " +
      "AND (?1 IS NULL OR p.proposed_region = ?1 " +
      "OR EXISTS (SELECT 1 FROM ambassador_regions r WHERE r.ambassador_id = p.ambassador_id AND r.region = ?1)) " +
      "ORDER BY p.created_at, p.id LIMIT ?2",
  )
    .bind(region, QUEUE_LIMIT)
    .all<{
      id: number;
      kind: string;
      payload: string;
      created_at: number;
      ambassador_id: string;
      display_name: string | null;
      proposed_region: string | null;
      proposed_domain: string | null;
      email_confirmed_at: number | null;
      confirmed_domain: string | null;
    }>();

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
      // Unlisted institutions (owner 2026-11-26): prefill the approval form from the proposal.
      email_confirmed: p.email_confirmed_at !== null,
      confirmed_domain: p.confirmed_domain,
      proposed_region: p.proposed_region,
      proposed_domain: p.proposed_domain,
    })),
  });
}

/** Institution types an approved proposal may carry onto a region's eligible list (the 3-work rule is unchanged). */
export const INSTITUTION_TYPES = ["education", "government", "nonprofit", "facility"] as const;
export type InstitutionType = (typeof INSTITUTION_TYPES)[number];
/**
 * Free-mail providers, mirrored from FREE_MAIL in eligibility.ts (not exported there). A domain or any subdomain of
 * one of these can never be an institution. Keep the two lists in step.
 */
const FREE_MAIL_HOSTS = [
  "gmail.com", "googlemail.com", "outlook.com", "outlook.fr", "hotmail.com", "hotmail.co.uk", "live.com",
  "live.co.uk", "msn.com", "yahoo.com", "yahoo.co.uk", "yahoo.fr", "ymail.com", "aol.com", "icloud.com",
  "me.com", "mac.com", "proton.me", "protonmail.com", "pm.me", "gmx.com", "gmx.net", "gmx.de", "web.de",
  "mail.com", "zoho.com", "yandex.com", "yandex.ru", "qq.com", "163.com", "126.com", "hey.com", "fastmail.com",
  "tutanota.com", "tuta.io", "mailbox.org", "seznam.cz", "wp.pl", "orange.fr", "free.fr", "laposte.net",
];

export interface AllowlistFields {
  region: Region;
  domain: string;
  institution_type: InstitutionType;
}

/** True when the domain or one of its parent domains is free-mail (suffix match, as eligibility.ts does). */
export function isFreeMailDomain(domain: string): boolean {
  const labels = domain.split(".");
  for (let i = 0; i < labels.length - 1; i++) {
    if (FREE_MAIL_HOSTS.includes(labels.slice(i).join("."))) return true;
  }
  return false;
}

/**
 * The region, domain and type an approval of an institution proposal must carry. Returns the first problem as an
 * error code (allowlist_fields_required when any field is absent, otherwise the specific check that failed).
 */
export function parseAllowlistFields(body: Record<string, unknown>): AllowlistFields | { error: string } {
  if (body.region === undefined || body.domain === undefined || body.institution_type === undefined) {
    return { error: "allowlist_fields_required" };
  }
  if (!isRegion(body.region)) return { error: "invalid_region" };
  if (typeof body.domain !== "string" || !DOMAIN_RE.test(body.domain.trim())) return { error: "invalid_domain" };
  const domain = body.domain.trim();
  if (isFreeMailDomain(domain)) return { error: "free_mail_domain" };
  if (!(INSTITUTION_TYPES as readonly unknown[]).includes(body.institution_type)) return { error: "invalid_institution_type" };
  return { region: body.region, domain, institution_type: body.institution_type as InstitutionType };
}

/**
 * Unlisted institution approved (owner 2026-11-26): the ambassador with review_state 'pending_review' becomes active in the approved region
 * with the claimed institution add:<domain> (source 'proposed', eligible), the region row becomes active, and the
 * welcome mail (with the workspace link) is queued once. The guarded first UPDATE makes this idempotent.
 */
async function activateUnlisted(env: Env, ambassadorId: string, fields: AllowlistFields, now: number): Promise<void> {
  const institutionId = `add:${fields.domain}`;
  const flipped = await env.DB.prepare(
    "UPDATE ambassadors SET status = 'active', region = ?1, institution_id = ?2, review_state = NULL " +
      "WHERE id = ?3 AND status = 'pending' AND review_state = 'pending_review'",
  )
    .bind(fields.region, institutionId, ambassadorId)
    .run();
  if (flipped.meta.changes !== 1) return;
  await env.DB.batch([
    env.DB.prepare(
      "INSERT INTO ambassador_institutions (ambassador_id, institution_id, source, eligible, claimed_at) VALUES (?1, ?2, 'proposed', 1, ?3) " +
        "ON CONFLICT (ambassador_id, institution_id) DO UPDATE SET eligible = 1, claimed_at = excluded.claimed_at",
    ).bind(ambassadorId, institutionId, now),
    env.DB.prepare(
      "INSERT INTO ambassador_regions (ambassador_id, region, status, joined_at) VALUES (?1, ?2, 'active', ?3) " +
        "ON CONFLICT (ambassador_id, region) DO UPDATE SET status = 'active', joined_at = excluded.joined_at",
    ).bind(ambassadorId, fields.region, now),
  ]);
  await queueWelcome(env, ambassadorId, now);
}

/**
 * POST /moderation/decide {type: submission|proposal, id, decision: approve|reject, note?}. The decision is recorded
 * and audited. Approving an institution proposal also needs {region, domain, institution_type} (ignored otherwise): the
 * approved row then joins that region's eligible list at the next build (GET /export/approved). An approval of an
 * email-confirmed (unlisted) institution also activates the proposer and queues the welcome mail; a rejection of one
 * returns the proposer to 'pending' with the decision note kept on the proposal.
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
  const item = await env.DB.prepare(
    `SELECT ambassador_id, status, kind, ${type === "proposal" ? "email_confirmed_at" : "NULL"} AS email_confirmed_at, ` +
      `${type === "submission" ? "json_extract(payload, '$.second_tag_for')" : "NULL"} AS second_tag_for FROM ${table} WHERE id = ?1`,
  )
    .bind(id)
    .first<{ ambassador_id: string; status: string; kind: string; email_confirmed_at: number | null; second_tag_for: number | null }>();
  if (!item) return err("not_found", 404);
  if (type === "submission" && item.kind === "group_tag" && item.second_tag_for !== null) {
    return err("blind_second_tag", 409);
  }
  if (item.ambassador_id === m.a.id) return err("self_decision", 403);
  if (item.status !== "pending") return err("already_decided", 409);

  // An approved institution proposal joins its region's eligible list, so its region, domain and type are required.
  let allowlist: AllowlistFields | null = null;
  if (type === "proposal" && decision === "approve" && item.kind === "institution") {
    const parsed = parseAllowlistFields(body);
    if ("error" in parsed) return err(parsed.error, 400);
    allowlist = parsed;
  }

  const status = decision === "approve" ? "approved" : "rejected";
  const changed = allowlist
    ? await env.DB.prepare(
        "UPDATE proposals SET status = ?1, decided_at = ?2, decided_by = ?3, decision_note = ?4, " +
          "region = ?5, domain = ?6, institution_type = ?7 WHERE id = ?8 AND status = 'pending'",
      )
        .bind(status, ctx.now, m.a.id, note, allowlist.region, allowlist.domain, allowlist.institution_type, id)
        .run()
    : await env.DB.prepare(
        `UPDATE ${table} SET status = ?1, decided_at = ?2, decided_by = ?3, decision_note = ?4 WHERE id = ?5 AND status = 'pending'`,
      )
        .bind(status, ctx.now, m.a.id, note, id)
        .run();
  if (changed.meta.changes !== 1) return err("already_decided", 409);
  // Unlisted institution with a confirmed email (owner 2026-11-26): approval activates the proposer, rejection returns
  // them to 'pending' (no session either way). The proposal row keeps the decision note.
  if (type === "proposal" && item.email_confirmed_at !== null) {
    if (allowlist) await activateUnlisted(env, item.ambassador_id, allowlist, ctx.now);
    else if (decision === "reject") {
      await env.DB.prepare(
        "UPDATE ambassadors SET email = NULL, email_hash = NULL, review_state = NULL WHERE id = ?1 AND review_state = 'pending_review'",
      )
        .bind(item.ambassador_id)
        .run();
    }
  }
  await audit(env.DB, ctx.now, "moderation.decide", m.a.id, {
    type,
    id,
    decision,
    by: m.role,
    ...(allowlist ? { region: allowlist.region, institution_type: allowlist.institution_type } : {}),
  });
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
