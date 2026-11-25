import { SELF, env } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import worker from "../src/index";
import { seedAmbassador } from "./helpers";

// Roles, moderation decisions, leads, suspension and the nightly cleanup (AMB-1 slice 2b). Everything runs against the
// local D1 in workerd; no network. OWNER_ORCID is the wrangler.toml placeholder.

const API = "https://api.plastiverse.live";
const OWNER_ORCID = "0000-0000-0000-0000";
const DAY = 24 * 60 * 60 * 1000;

function req(method: string, path: string, body?: unknown, cookie?: string): Promise<Response> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (cookie) headers.Cookie = cookie;
  return SELF.fetch(`${API}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
}

async function insertSubmission(ambassadorId: string, region = "norway"): Promise<number> {
  const row = await env.DB.prepare(
    "INSERT INTO submissions (ambassador_id, region, stream, kind, payload, status, created_at) " +
      "VALUES (?1, ?2, 'knowledge', 'funder', '{\"name\":\"Fund\",\"url\":\"https://fund.example/\"}', 'pending', ?3) RETURNING id",
  )
    .bind(ambassadorId, region, Date.now())
    .first<{ id: number }>();
  return row?.id ?? 0;
}

async function insertProposal(ambassadorId: string): Promise<number> {
  const row = await env.DB.prepare(
    "INSERT INTO proposals (ambassador_id, kind, payload, status, created_at) " +
      "VALUES (?1, 'institution', '{\"name\":\"New Lab\"}', 'pending', ?2) RETURNING id",
  )
    .bind(ambassadorId, Date.now())
    .first<{ id: number }>();
  return row?.id ?? 0;
}

describe("moderator roles", () => {
  it("refuses an ordinary ambassador on every moderation route", async () => {
    const amb = await seedAmbassador({ region: "norway", email: "amb@niva.no" });
    const other = await seedAmbassador({ region: "norway", email: "other@niva.no" });
    const id = await insertSubmission(other.id);
    expect((await req("GET", "/moderation/queue?region=norway", undefined, amb.cookie)).status).toBe(403);
    expect((await req("POST", "/moderation/decide", { type: "submission", id, decision: "approve" }, amb.cookie)).status).toBe(403);
    expect((await req("POST", "/moderation/leads", { ambassador_id: other.id, region: "norway" }, amb.cookie)).status).toBe(403);
    expect((await req("POST", "/moderation/suspend", { ambassador_id: other.id }, amb.cookie)).status).toBe(403);
  });

  it("answers 401 without a session", async () => {
    expect((await req("GET", "/moderation/queue?region=norway")).status).toBe(401);
    expect((await req("POST", "/moderation/suspend", { ambassador_id: "x" })).status).toBe(401);
  });

  it("lets the owner and a lead see the queue for every region", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID, email: "owner@example.org" });
    const lead = await seedAmbassador({ role: "lead", region: "belgium", email: "lead@ugent.be" });
    const author = await seedAmbassador({ region: "california", email: "author@berkeley.edu" });
    await insertSubmission(author.id, "california");
    await insertProposal(author.id);

    for (const cookie of [owner.cookie, lead.cookie]) {
      const all = await req("GET", "/moderation/queue", undefined, cookie);
      expect(all.status).toBe(200);
      const body = (await all.json()) as { submissions: unknown[]; proposals: unknown[] };
      expect(body.submissions).toHaveLength(1);
      expect(body.proposals).toHaveLength(1);
      const cal = await req("GET", "/moderation/queue?region=california", undefined, cookie);
      expect(((await cal.json()) as { submissions: unknown[] }).submissions).toHaveLength(1);
    }
  });

  it("does not expose emails in the queue", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID, email: "owner@example.org" });
    const author = await seedAmbassador({ region: "california", email: "private-author@berkeley.edu" });
    await insertSubmission(author.id, "california");
    const text = await (await req("GET", "/moderation/queue", undefined, owner.cookie)).text();
    expect(text).not.toContain("private-author");
    expect(text).not.toContain("@");
  });

  it("refuses an invalid region filter", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    expect((await req("GET", "/moderation/queue?region=atlantis", undefined, owner.cookie)).status).toBe(400);
  });
});

describe("decisions", () => {
  it("lets the owner approve a submission and audits it; a second decision is refused", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const author = await seedAmbassador({ region: "norway", email: "a@niva.no" });
    const id = await insertSubmission(author.id);

    const res = await req("POST", "/moderation/decide", { type: "submission", id, decision: "approve", note: "Looks right" }, owner.cookie);
    expect(res.status).toBe(200);
    const row = await env.DB.prepare("SELECT status, decided_by, decision_note FROM submissions WHERE id = ?1")
      .bind(id)
      .first<{ status: string; decided_by: string; decision_note: string }>();
    expect(row).toEqual({ status: "approved", decided_by: owner.id, decision_note: "Looks right" });
    const audit = await env.DB.prepare("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'moderation.decide' AND subject = ?1")
      .bind(owner.id)
      .first<{ n: number }>();
    expect(audit?.n).toBe(1);

    const again = await req("POST", "/moderation/decide", { type: "submission", id, decision: "reject" }, owner.cookie);
    expect(again.status).toBe(409);
  });

  it("refuses a lead deciding their own item, and allows a lead to decide someone else's", async () => {
    const lead = await seedAmbassador({ role: "lead", region: "norway", email: "lead@niva.no" });
    const other = await seedAmbassador({ region: "norway", email: "other@niva.no" });
    const own = await insertSubmission(lead.id);
    const theirs = await insertSubmission(other.id);
    const self = await req("POST", "/moderation/decide", { type: "submission", id: own, decision: "approve" }, lead.cookie);
    expect(self.status).toBe(403);
    expect(((await self.json()) as { error: string }).error).toBe("self_decision");
    const ok = await req("POST", "/moderation/decide", { type: "submission", id: theirs, decision: "reject" }, lead.cookie);
    expect(ok.status).toBe(200);
  });

  it("refuses an owner deciding their own proposal", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID, status: "active" });
    const id = await insertProposal(owner.id);
    const res = await req("POST", "/moderation/decide", { type: "proposal", id, decision: "approve" }, owner.cookie);
    expect(res.status).toBe(403);
  });

  it("records a proposal decision without activating the applicant", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const applicant = await seedAmbassador({ status: "pending", email: undefined, created_at: Date.now() });
    const id = await insertProposal(applicant.id);
    const res = await req("POST", "/moderation/decide", { type: "proposal", id, decision: "approve" }, owner.cookie);
    expect(res.status).toBe(200);
    const proposal = await env.DB.prepare("SELECT status, decided_by FROM proposals WHERE id = ?1")
      .bind(id)
      .first<{ status: string; decided_by: string }>();
    expect(proposal).toEqual({ status: "approved", decided_by: owner.id });
    const applicantRow = await env.DB.prepare("SELECT status FROM ambassadors WHERE id = ?1")
      .bind(applicant.id)
      .first<{ status: string }>();
    expect(applicantRow?.status).toBe("pending");
  });

  it("validates the decision body", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    expect((await req("POST", "/moderation/decide", { type: "other", id: 1, decision: "approve" }, owner.cookie)).status).toBe(400);
    expect((await req("POST", "/moderation/decide", { type: "submission", id: "1", decision: "approve" }, owner.cookie)).status).toBe(400);
    expect((await req("POST", "/moderation/decide", { type: "submission", id: 1, decision: "maybe" }, owner.cookie)).status).toBe(400);
    expect((await req("POST", "/moderation/decide", { type: "submission", id: 999, decision: "approve" }, owner.cookie)).status).toBe(404);
    expect(
      (await req("POST", "/moderation/decide", { type: "submission", id: 1, decision: "approve", note: "<b>x</b>" }, owner.cookie)).status,
    ).toBe(400);
  });
});

describe("leads", () => {
  it("lets the owner promote an active region member to lead, and audits it", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const member = await seedAmbassador({ region: "belgium", email: "m@ugent.be" });
    const res = await req("POST", "/moderation/leads", { ambassador_id: member.id, region: "belgium" }, owner.cookie);
    expect(res.status).toBe(200);
    const row = await env.DB.prepare("SELECT role FROM ambassadors WHERE id = ?1").bind(member.id).first<{ role: string }>();
    expect(row?.role).toBe("lead");
    const link = await env.DB.prepare("SELECT promoted_by FROM region_leads WHERE ambassador_id = ?1 AND region = 'belgium'")
      .bind(member.id)
      .first<{ promoted_by: string }>();
    expect(link?.promoted_by).toBe(owner.id);
    const audit = await env.DB.prepare("SELECT COUNT(*) AS n FROM audit_log WHERE action = 'moderation.lead' AND subject = ?1")
      .bind(member.id)
      .first<{ n: number }>();
    expect(audit?.n).toBe(1);
  });

  it("lets a lead promote a further lead, but not promote someone outside the region", async () => {
    const lead = await seedAmbassador({ role: "lead", region: "norway", email: "l@niva.no" });
    const member = await seedAmbassador({ region: "norway", email: "m@ntnu.no" });
    const outsider = await seedAmbassador({ region: "california", email: "c@berkeley.edu" });
    expect((await req("POST", "/moderation/leads", { ambassador_id: outsider.id, region: "norway" }, lead.cookie)).status).toBe(409);
    const ok = await req("POST", "/moderation/leads", { ambassador_id: member.id, region: "norway" }, lead.cookie);
    expect(ok.status).toBe(200);
  });

  it("refuses self-promotion, the owner account, pending accounts and bad regions", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const pending = await seedAmbassador({ status: "pending", region: undefined });
    expect((await req("POST", "/moderation/leads", { ambassador_id: owner.id, region: "norway" }, owner.cookie)).status).toBe(403);
    expect((await req("POST", "/moderation/leads", { ambassador_id: pending.id, region: "norway" }, owner.cookie)).status).toBe(409);
    expect((await req("POST", "/moderation/leads", { ambassador_id: pending.id, region: "mars" }, owner.cookie)).status).toBe(400);
  });
});

describe("suspension", () => {
  it("lets only the owner suspend, ends the sessions, and refuses the owner account", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const lead = await seedAmbassador({ role: "lead", region: "norway", email: "l@niva.no" });
    const victim = await seedAmbassador({ region: "norway", email: "v@niva.no" });

    expect((await req("POST", "/moderation/suspend", { ambassador_id: victim.id }, lead.cookie)).status).toBe(403);
    expect((await req("GET", "/me", undefined, victim.cookie)).status).toBe(200);

    const res = await req("POST", "/moderation/suspend", { ambassador_id: victim.id }, owner.cookie);
    expect(res.status).toBe(200);
    const row = await env.DB.prepare("SELECT status FROM ambassadors WHERE id = ?1").bind(victim.id).first<{ status: string }>();
    expect(row?.status).toBe("suspended");
    const sessions = await env.DB.prepare("SELECT COUNT(*) AS n FROM sessions WHERE ambassador_id = ?1")
      .bind(victim.id)
      .first<{ n: number }>();
    expect(sessions?.n).toBe(0);
    expect((await req("GET", "/me", undefined, victim.cookie)).status).toBe(401);

    expect((await req("POST", "/moderation/suspend", { ambassador_id: owner.id }, owner.cookie)).status).toBe(409);
    expect((await req("POST", "/moderation/suspend", { ambassador_id: "missing" }, owner.cookie)).status).toBe(404);
  });

  it("hides a suspended account's pending items from the queue", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const victim = await seedAmbassador({ region: "norway", email: "v@niva.no" });
    await insertSubmission(victim.id);
    await req("POST", "/moderation/suspend", { ambassador_id: victim.id }, owner.cookie);
    const body = (await (await req("GET", "/moderation/queue?region=norway", undefined, owner.cookie)).json()) as {
      submissions: unknown[];
    };
    expect(body.submissions).toHaveLength(0);
  });
});

describe("scheduled cleanup", () => {
  it("removes only expired rows and stale pending sign-ups", async () => {
    const now = Date.now();
    const old = now - 8 * DAY;
    // Expired: orcid state, signup session, magic link, and a stale pending sign-up with a child proposal.
    await env.DB.prepare("INSERT INTO orcid_states (state_hash, nonce_hash, created_at, expires_at) VALUES ('s-old','n-old',?1,?2)")
      .bind(old, now - 1)
      .run();
    await env.DB.prepare("INSERT INTO orcid_states (state_hash, nonce_hash, created_at, expires_at) VALUES ('s-new','n-new',?1,?2)")
      .bind(now, now + 60_000)
      .run();
    const stalePending = await seedAmbassador({ status: "pending", created_at: old });
    const freshPending = await seedAmbassador({ status: "pending", created_at: now - DAY });
    const active = await seedAmbassador({ region: "norway", email: "a@niva.no", created_at: old });
    await env.DB.prepare("INSERT INTO signup_sessions (id_hash, ambassador_id, created_at, expires_at) VALUES ('ss-old', ?1, ?2, ?3)")
      .bind(freshPending.id, old, now - 1)
      .run();
    await env.DB.prepare("INSERT INTO signup_sessions (id_hash, ambassador_id, created_at, expires_at) VALUES ('ss-new', ?1, ?2, ?3)")
      .bind(freshPending.id, now, now + 60_000)
      .run();
    await env.DB.prepare(
      "INSERT INTO magic_links (token_hash, email_hash, region, institution_id, created_at, expires_at) VALUES ('ml-old','h',?1,'I1',?2,?3)",
    )
      .bind("norway", old, now - 1)
      .run();
    await env.DB.prepare(
      "INSERT INTO magic_links (token_hash, email_hash, region, institution_id, created_at, expires_at) VALUES ('ml-new','h',?1,'I1',?2,?3)",
    )
      .bind("norway", now, now + 60_000)
      .run();
    await insertProposal(stalePending.id);

    await worker.scheduled({ cron: "17 3 * * *", scheduledTime: now } as unknown as ScheduledController, env);

    const count = async (sql: string, ...binds: unknown[]): Promise<number> =>
      (await env.DB.prepare(sql).bind(...binds).first<{ n: number }>())?.n ?? 0;
    expect(await count("SELECT COUNT(*) AS n FROM orcid_states WHERE state_hash = 's-old'")).toBe(0);
    expect(await count("SELECT COUNT(*) AS n FROM orcid_states WHERE state_hash = 's-new'")).toBe(1);
    expect(await count("SELECT COUNT(*) AS n FROM signup_sessions WHERE id_hash = 'ss-old'")).toBe(0);
    expect(await count("SELECT COUNT(*) AS n FROM signup_sessions WHERE id_hash = 'ss-new'")).toBe(1);
    expect(await count("SELECT COUNT(*) AS n FROM magic_links WHERE token_hash = 'ml-old'")).toBe(0);
    expect(await count("SELECT COUNT(*) AS n FROM magic_links WHERE token_hash = 'ml-new'")).toBe(1);
    expect(await count("SELECT COUNT(*) AS n FROM ambassadors WHERE id = ?1", stalePending.id)).toBe(0);
    expect(await count("SELECT COUNT(*) AS n FROM proposals WHERE ambassador_id = ?1", stalePending.id)).toBe(0);
    expect(await count("SELECT COUNT(*) AS n FROM ambassadors WHERE id = ?1", freshPending.id)).toBe(1);
    expect(await count("SELECT COUNT(*) AS n FROM ambassadors WHERE id = ?1", active.id)).toBe(1);
  });
});
