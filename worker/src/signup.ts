import { EMAIL_RE, type Ctx, LINK_TTL_MS, audit, createSession, currentAmbassador } from "./auth";
import { buildChecklist, type ChecklistItem } from "./checklist";
import { type Env, requireSecret } from "./env";
import { DOMAIN_RE, REGIONS, type Region, isFreeMail, isRegion, isTrustedDomain, matchClaimedInstitution } from "./eligibility";
import { keyedHash, randomHex, randomToken, sha256Hex, signSessionId, verifySignedSessionId } from "./crypto";
import {
  ORCID_NONCE_COOKIE,
  ORCID_NONCE_MAX_AGE_S,
  SIGNUP_COOKIE,
  SIGNUP_MAX_AGE_S,
  hostCookie,
  json,
  readCookie,
  redirect,
  sessionCookie,
} from "./http";
import { chooseSender } from "./mail";
import { fetchAuthorByOrcid } from "./openalex";
import { type Employment, exchangeOrcidCode, fetchEmployments, orcidAuthorizeUrl } from "./orcid";
import { EMAIL_LIMIT, IP_LIMIT, withinRateLimit } from "./rate_limit";
import { verifyTurnstile } from "./turnstile";

/** Current contribution terms (docs/AMBASSADOR_TERMS.md). Consent must cite this version. */
export const TERMS_VERSION = "v1";
const ORCID_STATE_TTL_MS = 10 * 60 * 1000;
const SIGNUP_TTL_MS = SIGNUP_MAX_AGE_S * 1000;
const TOKEN_RE = /^[A-Za-z0-9_-]{43}$/;
const MAX_PROPOSALS = 10;

interface SignupRow {
  id: string;
  orcid: string;
  checklist_json: string | null;
  status: string;
}

function err(error: string, status: number): Response {
  return json({ ok: false, error }, status);
}

export function orcidRedirectUri(env: Env): string {
  return `${env.PUBLIC_API_URL}/orcid/callback`;
}

function workspaceUrl(env: Env, params: Record<string, string>): string {
  const target = new URL(env.WORKSPACE_URL);
  for (const [k, v] of Object.entries(params)) target.searchParams.set(k, v);
  return target.toString();
}

async function createSignupSession(env: Env, ambassadorId: string, now: number): Promise<string> {
  const signingKey = requireSecret(env.SESSION_SIGNING_KEY, "SESSION_SIGNING_KEY");
  const id = randomToken(32);
  await env.DB.prepare("INSERT INTO signup_sessions (id_hash, ambassador_id, created_at, expires_at) VALUES (?1, ?2, ?3, ?4)")
    .bind(await sha256Hex(id), ambassadorId, now, now + SIGNUP_TTL_MS)
    .run();
  return signSessionId(signingKey, id);
}

/** Resolves the signup cookie to a pending ambassador (ORCID verified, email not yet proven), or null. */
async function currentSignup(request: Request, env: Env, now: number): Promise<SignupRow | null> {
  const cookie = readCookie(request, SIGNUP_COOKIE);
  if (!cookie || !env.SESSION_SIGNING_KEY) return null;
  const id = await verifySignedSessionId(env.SESSION_SIGNING_KEY, cookie);
  if (!id) return null;
  return env.DB.prepare(
    "SELECT a.id, a.orcid, a.checklist_json, a.status FROM signup_sessions s JOIN ambassadors a ON a.id = s.ambassador_id " +
      "WHERE s.id_hash = ?1 AND s.expires_at > ?2 AND a.status = 'pending' AND a.review_state IS NULL",
  )
    .bind(await sha256Hex(id), now)
    .first<SignupRow>();
}

/** GET /orcid/start: state and a browser-binding nonce, both stored only as hashes; then redirect to ORCID. */
export async function handleOrcidStart(env: Env, ctx: Ctx): Promise<Response> {
  const clientId = requireSecret(env.ORCID_CLIENT_ID, "ORCID_CLIENT_ID");
  const state = randomToken(32);
  const nonce = randomToken(32);
  await env.DB.prepare("DELETE FROM orcid_states WHERE expires_at < ?1").bind(ctx.now).run();
  await env.DB.prepare("INSERT INTO orcid_states (state_hash, nonce_hash, created_at, expires_at) VALUES (?1, ?2, ?3, ?4)")
    .bind(await sha256Hex(state), await sha256Hex(nonce), ctx.now, ctx.now + ORCID_STATE_TTL_MS)
    .run();
  return redirect(orcidAuthorizeUrl(clientId, orcidRedirectUri(env), state), {
    "Set-Cookie": hostCookie(ORCID_NONCE_COOKIE, nonce, ORCID_NONCE_MAX_AGE_S),
  });
}

/**
 * GET /orcid/callback?code&state: checks the state and the nonce cookie (one conditional DELETE, so each state
 * works once), exchanges the code, and opens a signup session for the verified iD. An active ambassador with
 * this iD gets a normal session instead (ORCID sign-in for a returning ambassador).
 */
export async function handleOrcidCallback(url: URL, request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const fail = (): Response => {
    const res = redirect(workspaceUrl(env, { signin: "failed" }));
    res.headers.append("Set-Cookie", hostCookie(ORCID_NONCE_COOKIE, "", 0));
    return res;
  };
  const state = url.searchParams.get("state") ?? "";
  const code = url.searchParams.get("code") ?? "";
  const nonce = readCookie(request, ORCID_NONCE_COOKIE) ?? "";
  if (url.searchParams.has("error") || !TOKEN_RE.test(state) || !TOKEN_RE.test(nonce) || !code || code.length > 512) {
    return fail();
  }
  const claimed = await env.DB.prepare(
    "DELETE FROM orcid_states WHERE state_hash = ?1 AND nonce_hash = ?2 AND expires_at > ?3",
  )
    .bind(await sha256Hex(state), await sha256Hex(nonce), ctx.now)
    .run();
  if (claimed.meta.changes !== 1) return fail();

  let orcid: string;
  try {
    orcid = await exchangeOrcidCode(
      ctx.fetch,
      requireSecret(env.ORCID_CLIENT_ID, "ORCID_CLIENT_ID"),
      requireSecret(env.ORCID_CLIENT_SECRET, "ORCID_CLIENT_SECRET"),
      code,
      orcidRedirectUri(env),
    );
  } catch (e) {
    console.error("orcid exchange failed", e instanceof Error ? e.name : "unknown");
    return fail();
  }

  await env.DB.prepare("INSERT INTO ambassadors (id, orcid, status, created_at) VALUES (?1, ?2, 'pending', ?3) ON CONFLICT (orcid) DO NOTHING")
    .bind(randomHex(16), orcid, ctx.now)
    .run();
  const row = await env.DB.prepare("SELECT id, status, review_state FROM ambassadors WHERE orcid = ?1")
    .bind(orcid)
    .first<{ id: string; status: string; review_state: string | null }>();
  if (!row || row.status === "suspended") return fail();
  await audit(env.DB, ctx.now, "signup.orcid", await sha256Hex(orcid), { status: row.status });

  if (row.status === "active") {
    const res = redirect(workspaceUrl(env, { signin: "orcid" }));
    res.headers.append("Set-Cookie", await sessionSetCookie(env, row.id, ctx.now));
    return res;
  }
  if (row.review_state === "pending_review") {
    // Unlisted institution waiting for a moderator: no session and no signup cookie (owner 2026-11-26).
    const res = redirect(workspaceUrl(env, { signup: "pending_review" }));
    res.headers.append("Set-Cookie", hostCookie(ORCID_NONCE_COOKIE, "", 0));
    return res;
  }
  const res = redirect(workspaceUrl(env, { signup: "orcid" }));
  res.headers.append("Set-Cookie", hostCookie(SIGNUP_COOKIE, await createSignupSession(env, row.id, ctx.now), SIGNUP_MAX_AGE_S));
  res.headers.append("Set-Cookie", hostCookie(ORCID_NONCE_COOKIE, "", 0));
  return res;
}

async function sessionSetCookie(env: Env, ambassadorId: string, now: number): Promise<string> {
  return sessionCookie(await createSession(env, ambassadorId, now));
}

/**
 * GET /signup/profile: the author lookup. Fetches the OpenAlex author (by ORCID) and the public ORCID employments,
 * stores the checklist snapshot the claims are checked against, and returns it. No author record gives an empty
 * checklist and the proposal path.
 */
export async function handleSignupLookup(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const s = await currentSignup(request, env, ctx.now);
  if (!s) return err("not_signed_in", 401);
  let author: Awaited<ReturnType<typeof fetchAuthorByOrcid>>;
  try {
    author = await fetchAuthorByOrcid(ctx.fetch, s.orcid);
  } catch (e) {
    console.error("openalex lookup failed", e instanceof Error ? e.name : "unknown");
    return err("lookup_failed", 502);
  }
  let employments: Employment[] = [];
  let employmentsChecked = true;
  try {
    employments = await fetchEmployments(ctx.fetch, s.orcid);
  } catch (e) {
    employmentsChecked = false;
    console.error("orcid employments failed", e instanceof Error ? e.name : "unknown");
  }
  const checklist = buildChecklist(author, employments);
  await env.DB.prepare("UPDATE ambassadors SET author_id = ?1, checklist_json = ?2 WHERE id = ?3")
    .bind(author?.id ?? null, JSON.stringify(checklist), s.id)
    .run();
  return json({
    ok: true,
    orcid: s.orcid,
    author: author ? { id: author.id, display_name: author.name } : null,
    employments_checked: employmentsChecked,
    institutions: checklist,
    regions: REGIONS,
    proposals_open: true,
    message:
      checklist.length === 0
        ? "No institutions were found on the linked record. Propose your institutions or regions; moderation will review them."
        : undefined,
  });
}

function stringList(value: unknown, max: number): string[] | null {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.length > max) return null;
  if (!value.every((v) => typeof v === "string" && v.length > 0 && v.length <= 200)) return null;
  return [...new Set(value as string[])];
}

export interface ParsedProposal {
  kind: string;
  /** Stored JSON. For a domain-bearing institution the domain is the normalised (lowercase) one. */
  payload: string;
  /** Set only for an institution with a domain (unlisted-institution path, owner 2026-11-26). */
  region: Region | null;
  domain: string | null;
}

/**
 * Proposals: plain string fields only, bounded in size. An institution whose payload carries a domain must also name
 * its region, and the domain must be valid and trusted for that region (eligibility.isTrustedDomain). Returns the
 * first problem as an error code.
 */
function parseProposals(value: unknown): ParsedProposal[] | { error: string } {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.length > MAX_PROPOSALS) return { error: "invalid_proposal" };
  const out: ParsedProposal[] = [];
  for (const item of value as unknown[]) {
    if (!item || typeof item !== "object") return { error: "invalid_proposal" };
    const { kind, payload, region } = item as { kind?: unknown; payload?: unknown; region?: unknown };
    if (kind !== "institution" && kind !== "region") return { error: "invalid_proposal" };
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) return { error: "invalid_proposal" };
    const fields = { ...(payload as Record<string, unknown>) };
    const entries = Object.entries(fields);
    if (entries.length === 0 || entries.length > 10) return { error: "invalid_proposal" };
    if (!entries.every(([k, v]) => k.length <= 40 && typeof v === "string" && v.length <= 300)) return { error: "invalid_proposal" };
    let domain: string | null = null;
    let proposedRegion: Region | null = null;
    if (kind === "institution" && fields.domain !== undefined) {
      if (typeof fields.domain !== "string") return { error: "invalid_domain" };
      domain = fields.domain.trim().toLowerCase();
      if (!isRegion(region)) return { error: "invalid_region" };
      if (!DOMAIN_RE.test(domain)) return { error: "invalid_domain" };
      if (!isTrustedDomain(region, domain)) return { error: "untrusted_domain" };
      proposedRegion = region;
      fields.domain = domain;
    }
    const json = JSON.stringify(fields);
    if (json.length > 2000) return { error: "invalid_proposal" };
    out.push({ kind, payload: json, region: proposedRegion, domain });
  }
  return out;
}

/**
 * POST /signup/claims {institutions, regions, proposals}. Institutions must be on the checklist. Either one claimed
 * institution is eligible (status pending_email, and every region must be tied to a claimed eligible institution),
 * or only proposals are sent (status proposals_only). A new call replaces the earlier pending claims and proposals.
 */
export async function handleSignupClaims(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const s = await currentSignup(request, env, ctx.now);
  if (!s) return err("not_signed_in", 401);
  let body: { institutions?: unknown; regions?: unknown; proposals?: unknown };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return err("invalid_request", 400);
  }
  const institutionIds = stringList(body.institutions, 100);
  const regionIds = stringList(body.regions, REGIONS.length);
  const parsed = parseProposals(body.proposals);
  if (!institutionIds || !regionIds) return err("invalid_request", 400);
  if (!Array.isArray(parsed)) return err(parsed.error, 400);
  const proposals = parsed;
  if (!s.checklist_json) return err("lookup_required", 409);

  const checklist = JSON.parse(s.checklist_json) as ChecklistItem[];
  const byId = new Map(checklist.map((item) => [item.id, item]));
  const picked: ChecklistItem[] = [];
  for (const id of institutionIds) {
    const item = byId.get(id);
    if (!item) return err("unknown_institution", 400);
    picked.push(item);
  }
  const eligible = picked.filter((item) => item.eligible);
  // Without an eligible institution sign-up cannot continue, but proposals still go to moderation (section 13.6).
  if (eligible.length === 0 && proposals.length === 0) return err("no_eligible_institution", 400);
  const tied = new Set(eligible.flatMap((item) => item.regions));
  for (const region of regionIds) {
    if (!isRegion(region) || !tied.has(region)) return err("region_not_tied", 400);
  }
  if (eligible.length > 0 && regionIds.length === 0) return err("region_required", 400);
  // Unlisted institution (owner 2026-11-26): with no eligible institution and exactly one domain-bearing institution
  // proposal, the email step confirms that domain (pending_email_proposal). Regions must be empty on that path.
  const domainProposals = proposals.filter((p) => p.domain !== null);
  const status =
    eligible.length > 0 ? "pending_email" : domainProposals.length === 1 ? "pending_email_proposal" : "proposals_only";
  const awaitingEmail = status === "pending_email_proposal" ? domainProposals[0] : null;

  await env.DB.batch([
    env.DB.prepare("DELETE FROM ambassador_institutions WHERE ambassador_id = ?1").bind(s.id),
    env.DB.prepare("DELETE FROM ambassador_regions WHERE ambassador_id = ?1 AND status = 'pending_email'").bind(s.id),
    env.DB.prepare("DELETE FROM proposals WHERE ambassador_id = ?1 AND status = 'pending'").bind(s.id),
    ...picked.map((item) =>
      env.DB.prepare(
        "INSERT INTO ambassador_institutions (ambassador_id, institution_id, source, eligible, claimed_at) VALUES (?1, ?2, ?3, ?4, NULL)",
      ).bind(s.id, item.id, item.source, item.eligible ? 1 : 0),
    ),
    ...regionIds.map((region) =>
      env.DB.prepare("INSERT INTO ambassador_regions (ambassador_id, region, status, joined_at) VALUES (?1, ?2, 'pending_email', ?3)")
        .bind(s.id, region, ctx.now),
    ),
    ...proposals.map((p) =>
      env.DB.prepare(
        "INSERT INTO proposals (ambassador_id, kind, payload, status, created_at, proposed_region, proposed_domain, awaiting_email) " +
          "VALUES (?1, ?2, ?3, 'pending', ?4, ?5, ?6, ?7)",
      ).bind(s.id, p.kind, p.payload, ctx.now, p.region, p.domain, p === awaitingEmail ? 1 : 0),
    ),
  ]);
  await audit(env.DB, ctx.now, "signup.claims", await sha256Hex(s.orcid), {
    institutions: picked.length,
    regions: regionIds.length,
    proposals: proposals.length,
  });
  return json({
    ok: true,
    status,
    institutions: picked.length,
    eligible: eligible.length,
    regions: regionIds,
    proposals: proposals.length,
  });
}

/**
 * POST /signup/email {email, turnstileToken}: one institutional email. Its domain must match a claimed eligible
 * institution. Sends a single-use link (30 minutes); the link activates the sign-up.
 */
export async function handleSignupEmail(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const s = await currentSignup(request, env, ctx.now);
  if (!s) return err("not_signed_in", 401);
  let body: { email?: unknown; turnstileToken?: unknown };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return err("invalid_request", 400);
  }
  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  if (!email || email.length > 254 || !EMAIL_RE.test(email)) return err("invalid_email", 400);
  const turnstileToken = typeof body.turnstileToken === "string" ? body.turnstileToken.slice(0, 2048) : "";
  const ip = request.headers.get("CF-Connecting-IP");
  if (!(await verifyTurnstile(env.TURNSTILE_SECRET, turnstileToken, ip))) return err("bot_check_failed", 403);

  const emailHash = await keyedHash(requireSecret(env.EMAIL_HASH_KEY, "EMAIL_HASH_KEY"), "email", email);
  const emailOk = await withinRateLimit(env.DB, "email", emailHash, EMAIL_LIMIT.limit, EMAIL_LIMIT.windowMs, ctx.now);
  const ipOk = await withinRateLimit(env.DB, "ip", await sha256Hex(ip ?? "unknown"), IP_LIMIT.limit, IP_LIMIT.windowMs, ctx.now);
  if (!emailOk || !ipOk) return err("rate_limited", 429);

  // Unlisted institution (owner 2026-11-26): the address must sit under the proposed domain, and that domain is trusted.
  const awaiting = await env.DB.prepare(
    "SELECT id, proposed_region, proposed_domain FROM proposals " +
      "WHERE ambassador_id = ?1 AND awaiting_email = 1 AND status = 'pending' AND kind = 'institution'",
  )
    .bind(s.id)
    .first<{ id: number; proposed_region: string | null; proposed_domain: string | null }>();

  const domain = email.slice(email.indexOf("@") + 1);
  let region: string;
  let institutionId: string;
  let proposalId: number | null = null;
  if (awaiting) {
    const proposed = awaiting.proposed_domain ?? "";
    if (!isRegion(awaiting.proposed_region) || !proposed) return err("domain_not_proposed", 400);
    if (domain !== proposed && !domain.endsWith(`.${proposed}`)) return err("domain_not_proposed", 400);
    if (!isTrustedDomain(awaiting.proposed_region, domain)) return err("untrusted_domain", 400);
    region = awaiting.proposed_region;
    institutionId = `add:${proposed}`;
    proposalId = awaiting.id;
  } else {
    const claimed = await env.DB.prepare("SELECT institution_id FROM ambassador_institutions WHERE ambassador_id = ?1 AND eligible = 1")
      .bind(s.id)
      .all<{ institution_id: string }>();
    const pendingRegions = await env.DB.prepare("SELECT region FROM ambassador_regions WHERE ambassador_id = ?1 AND status = 'pending_email'")
      .bind(s.id)
      .all<{ region: string }>();
    if (claimed.results.length === 0 || pendingRegions.results.length === 0) return err("claims_required", 409);

    const match = matchClaimedInstitution(
      claimed.results.map((r) => r.institution_id),
      domain,
    );
    if (!match) return err("domain_not_claimed", 400);
    const wanted = pendingRegions.results.map((r) => r.region);
    region = match.regions.find((r) => wanted.includes(r)) ?? match.regions[0];
    institutionId = match.institutionId;
  }

  try {
    const token = randomToken(32);
    await env.DB.prepare(
      "INSERT INTO magic_links (token_hash, email_hash, email, region, institution_id, created_at, expires_at, ambassador_id, proposal_id) " +
        "VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9)",
    )
      .bind(await sha256Hex(token), emailHash, email, region, institutionId, ctx.now, ctx.now + LINK_TTL_MS, s.id, proposalId)
      .run();
    const link = `${env.PUBLIC_API_URL}/auth/verify?token=${token}`;
    await chooseSender(env).send({
      to: email,
      subject: "Confirm your Plastiverse ambassador sign-up",
      text:
        "Confirm your institutional email for the Plastiverse ambassador sign-up (valid 30 minutes, one use):\n\n" +
        `${link}\n\n` +
        (proposalId === null
          ? ""
          : "Your institution proposal is then reviewed by a moderator. You get a sign-in link only after approval.\n\n") +
        "If you did not ask for this, ignore this message.",
    });
  } catch (e) {
    console.error("signup email failed", e instanceof Error ? e.name : "unknown");
    return err("mail_failed", 502);
  }
  await audit(env.DB, ctx.now, "signup.email_sent", emailHash, { region, proposal: proposalId !== null });
  return json({ ok: true, message: "A confirmation link has been sent to your institutional address. It expires in 30 minutes." });
}

/** POST /signup/profile {display_name, credit_public (default true), accept_terms_version}: after email proof. */
export async function handleProfileSave(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const a = await currentAmbassador(request, env, ctx.now);
  if (!a) return err("not_signed_in", 401);
  let body: { display_name?: unknown; credit_public?: unknown; accept_terms_version?: unknown };
  try {
    body = (await request.json()) as typeof body;
  } catch {
    return err("invalid_request", 400);
  }
  const name = typeof body.display_name === "string" ? body.display_name.trim() : "";
  if (name.length < 1 || name.length > 80) return err("invalid_display_name", 400);
  const credit = body.credit_public === undefined ? true : body.credit_public;
  if (typeof credit !== "boolean") return err("invalid_credit", 400);
  if (body.accept_terms_version !== TERMS_VERSION) return err("terms_version_required", 400);
  await env.DB.prepare(
    "UPDATE ambassadors SET display_name = ?1, credit_public = ?2, consent_at = ?3, terms_version = ?4 WHERE id = ?5 AND status = 'active'",
  )
    .bind(name, credit ? 1 : 0, ctx.now, TERMS_VERSION, a.id)
    .run();
  await audit(env.DB, ctx.now, "signup.profile", null, { credit_public: credit, terms: TERMS_VERSION });
  return json({ ok: true });
}
