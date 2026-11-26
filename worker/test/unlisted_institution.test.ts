import { SELF, env } from "cloudflare:test";
import { describe, expect, it, vi } from "vitest";
import { runCleanup } from "../src/cleanup";
import { isTrustedDomain, trustedSuffixes } from "../src/eligibility";
import { latestToken, seedAmbassador } from "./helpers";

// Unlisted institutions (AMB-1, owner decision 2026-11-26, QUESTIONS AMB-UNLISTED-EMAIL). A person whose ORCID and
// OpenAlex records link no eligible institution proposes an institution with its email domain. A trusted public-sector
// address confirms it; until a moderator approves, the person has no session and no workspace.

// The California allowlist carries trusted_email_suffixes once the pipeline publishes it. The mock states the contract
// value so these tests do not depend on the generated file.
vi.mock("../../site/data/california/ambassador_institutions.json", async (importOriginal) => {
  const original = (await importOriginal()) as { default: Record<string, unknown> };
  return { default: { ...original.default, trusted_email_suffixes: ["ca.gov", "ca.us", "edu", "gov"] } };
});

const API = "https://api.plastiverse.live";
const WORKSPACE = "https://plastiverse.live/ambassadors";
const SIGNUP = "__Host-plastiverse_signup";
const NONCE = "__Host-plastiverse_orcid";
const SESSION = "__Host-plastiverse_session";
const OWNER_ORCID = env.OWNER_ORCID;
const OEHHA = "oehha.ca.gov";
const CONFIRM_SUBJECT = "Confirm your Plastiverse ambassador sign-up";

function pair(res: Response, name: string): string {
  const raw = res.headers.getSetCookie().find((c) => c.startsWith(`${name}=`));
  if (!raw) throw new Error(`no ${name} cookie`);
  return raw.split(";")[0];
}

function setsCookie(res: Response, name: string): boolean {
  return res.headers.getSetCookie().some((c) => c.startsWith(`${name}=`));
}

function send(method: string, path: string, body?: unknown, cookie?: string): Promise<Response> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (cookie) headers.Cookie = cookie;
  return SELF.fetch(`${API}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
}

async function orcidSignUp(): Promise<string> {
  const start = await SELF.fetch(`${API}/orcid/start`, { redirect: "manual" });
  const state = new URL(start.headers.get("Location") ?? "https://invalid.example/").searchParams.get("state") ?? "";
  const url = new URL(`${API}/orcid/callback`);
  url.searchParams.set("code", "test-code");
  url.searchParams.set("state", state);
  const res = await SELF.fetch(url, { redirect: "manual", headers: { Cookie: pair(start, NONCE) } });
  if (res.status !== 302) throw new Error(`callback ${res.status}`);
  return pair(res, SIGNUP);
}

function proposal(domain: string, region = "california"): Record<string, unknown> {
  return { kind: "institution", region, payload: { name: "Public Office", domain } };
}

/** ORCID sign-up, profile lookup (no OpenAlex author, no employments: no eligible institution) and the claim. */
async function claimUnlisted(proposals: unknown[], regions: string[] = []): Promise<Response> {
  const signup = await orcidSignUp();
  expect((await send("GET", "/signup/profile", undefined, signup)).status).toBe(200);
  return send("POST", "/signup/claims", { institutions: [], regions, proposals }, signup);
}

async function signupCookieFor(domain: string): Promise<string> {
  const signup = await orcidSignUp();
  expect((await send("GET", "/signup/profile", undefined, signup)).status).toBe(200);
  const claim = await send("POST", "/signup/claims", { institutions: [], regions: [], proposals: [proposal(domain)] }, signup);
  expect(((await claim.json()) as { status: string }).status).toBe("pending_email_proposal");
  return signup;
}

/** The full path up to the confirmation link being used. Returns the verify response. */
async function confirmEmail(email: string, domain = OEHHA): Promise<Response> {
  const signup = await signupCookieFor(domain);
  const res = await send("POST", "/signup/email", { email, turnstileToken: "good-token" }, signup);
  expect(res.status).toBe(200);
  return SELF.fetch(`${API}/auth/verify?token=${await latestToken()}`, { redirect: "manual" });
}

async function proposalRow(): Promise<Record<string, unknown>> {
  const row = await env.DB.prepare(
    "SELECT id, status, email_confirmed_at, confirmed_domain, decision_note, proposed_region, proposed_domain FROM proposals",
  ).first<Record<string, unknown>>();
  if (!row) throw new Error("no proposal");
  return row;
}

async function proposalId(): Promise<number> {
  return (await proposalRow()).id as number;
}

describe("unlisted institution: claims validation", () => {
  it("refuses an untrusted or free-mail domain", async () => {
    for (const domain of ["acme.com", "gmail.com", "mail.yahoo.com"]) {
      const res = await claimUnlisted([proposal(domain)]);
      expect(res.status).toBe(400);
      expect(((await res.json()) as { error: string }).error).toBe("untrusted_domain");
    }
  });

  it("refuses a malformed domain and a proposal without a region", async () => {
    const bad = await claimUnlisted([proposal("not a domain")]);
    expect(((await bad.json()) as { error: string }).error).toBe("invalid_domain");
    const noRegion = await claimUnlisted([{ kind: "institution", payload: { name: "X", domain: OEHHA } }]);
    expect(((await noRegion.json()) as { error: string }).error).toBe("invalid_region");
  });

  it("accepts a trusted domain as pending_email_proposal and stores the proposal", async () => {
    const res = await claimUnlisted([proposal(OEHHA)]);
    expect(res.status).toBe(200);
    expect(((await res.json()) as { status: string }).status).toBe("pending_email_proposal");
    const row = await proposalRow();
    expect(row.proposed_region).toBe("california");
    expect(row.proposed_domain).toBe(OEHHA);
  });

  it("treats a host under a trusted suffix as trusted (gmail.com.ca.gov sits under ca.gov)", async () => {
    const res = await claimUnlisted([proposal("gmail.com.ca.gov")]);
    expect(((await res.json()) as { status: string }).status).toBe("pending_email_proposal");
  });

  it("rejects regions on the unlisted path (the proposal names its region)", async () => {
    const res = await claimUnlisted([proposal(OEHHA)], ["california"]);
    expect(res.status).toBe(400);
    expect(((await res.json()) as { error: string }).error).toBe("region_not_tied");
  });

  it("keeps proposals_only when two domain proposals are sent", async () => {
    const res = await claimUnlisted([proposal(OEHHA), proposal("cdph.ca.gov")]);
    expect(((await res.json()) as { status: string }).status).toBe("proposals_only");
  });
});

describe("unlisted institution: trusted domain rule", () => {
  it("matches a suffix or a subdomain of one, and nothing else", () => {
    expect(trustedSuffixes("california")).toEqual(["ca.gov", "ca.us", "edu", "gov"]);
    expect(isTrustedDomain("california", "ca.gov")).toBe(true);
    expect(isTrustedDomain("california", "oehha.ca.gov")).toBe(true);
    expect(isTrustedDomain("california", "a.berkeley.edu")).toBe(true);
    expect(isTrustedDomain("california", "ca.gov.example.com")).toBe(false);
    // "gov" is itself a trusted suffix, so any .gov host counts; the boundary is at the label, not the substring.
    expect(isTrustedDomain("california", "notca.gov")).toBe(true);
    expect(isTrustedDomain("california", "ca.gov.au")).toBe(false);
    expect(isTrustedDomain("california", "gmail.com")).toBe(false);
    expect(isTrustedDomain("california", "gov")).toBe(false);
  });
});

describe("unlisted institution: email confirmation", () => {
  it("accepts the proposal domain and its subdomains, refuses other domains", async () => {
    const signup = await signupCookieFor(OEHHA);
    const email = (address: string) => send("POST", "/signup/email", { email: address, turnstileToken: "good-token" }, signup);
    expect((await email("ana@oehha.ca.gov")).status).toBe(200);
    expect((await email("ana@lab.oehha.ca.gov")).status).toBe(200);
    const other = await email("ana@cdph.ca.gov");
    expect(other.status).toBe(400);
    expect(((await other.json()) as { error: string }).error).toBe("domain_not_proposed");
    const free = await email("ana@gmail.com");
    expect(((await free.json()) as { error: string }).error).toBe("domain_not_proposed");
    const linked = await env.DB.prepare("SELECT COUNT(*) AS n FROM magic_links WHERE proposal_id IS NOT NULL").first<{ n: number }>();
    expect(linked?.n).toBe(2);
  });
});

describe("unlisted institution: verify, ORCID and queue", () => {
  it("verify sets pending_review, creates no session and redirects to the pending notice", async () => {
    const res = await confirmEmail("ana@oehha.ca.gov");
    expect(res.status).toBe(302);
    const target = new URL(res.headers.get("Location") ?? "https://invalid.example/");
    expect(`${target.origin}${target.pathname}`).toBe(WORKSPACE);
    expect(target.searchParams.get("signup")).toBe("pending_review");
    expect(setsCookie(res, SESSION)).toBe(false);
    const ambassador = await env.DB.prepare("SELECT status, review_state, email FROM ambassadors").first<{
      status: string;
      review_state: string | null;
      email: string;
    }>();
    expect(ambassador?.status).toBe("pending");
    expect(ambassador?.review_state).toBe("pending_review");
    expect(ambassador?.email).toBe("ana@oehha.ca.gov");
    const row = await proposalRow();
    expect(row.email_confirmed_at).not.toBeNull();
    expect(row.confirmed_domain).toBe("oehha.ca.gov");
    const sessions = await env.DB.prepare("SELECT COUNT(*) AS n FROM sessions").first<{ n: number }>();
    expect(sessions?.n).toBe(0);
  });

  it("the signup cookie stops working once the email is confirmed", async () => {
    const signup = await signupCookieFor(OEHHA);
    expect((await send("POST", "/signup/email", { email: "ana@oehha.ca.gov", turnstileToken: "good-token" }, signup)).status).toBe(200);
    expect((await SELF.fetch(`${API}/auth/verify?token=${await latestToken()}`, { redirect: "manual" })).status).toBe(302);
    const after = await send("POST", "/signup/email", { email: "ana@oehha.ca.gov", turnstileToken: "good-token" }, signup);
    expect(after.status).toBe(401);
  });

  it("a reused confirmation link is refused", async () => {
    const link = await confirmEmail("ana@oehha.ca.gov");
    expect(link.status).toBe(302);
    const again = await SELF.fetch(`${API}/auth/verify?token=${await latestToken()}`, { redirect: "manual" });
    expect(new URL(again.headers.get("Location") ?? "https://invalid.example/").searchParams.get("signin")).toBe("failed");
  });

  it("an ORCID sign-in for a pending_review ambassador redirects without a session", async () => {
    await confirmEmail("ana@oehha.ca.gov");
    const start = await SELF.fetch(`${API}/orcid/start`, { redirect: "manual" });
    const state = new URL(start.headers.get("Location") ?? "https://invalid.example/").searchParams.get("state") ?? "";
    const url = new URL(`${API}/orcid/callback`);
    url.searchParams.set("code", "test-code");
    url.searchParams.set("state", state);
    const res = await SELF.fetch(url, { redirect: "manual", headers: { Cookie: pair(start, NONCE) } });
    expect(res.status).toBe(302);
    expect(new URL(res.headers.get("Location") ?? "https://invalid.example/").searchParams.get("signup")).toBe("pending_review");
    expect(setsCookie(res, SESSION)).toBe(false);
    expect(setsCookie(res, SIGNUP)).toBe(false);
  });

  it("the moderation queue shows the confirmed email and the prefill fields", async () => {
    await confirmEmail("ana@oehha.ca.gov");
    const owner = await seedAmbassador({ orcid: env.OWNER_ORCID, status: "active" });
    const res = await send("GET", "/moderation/queue", undefined, owner.cookie);
    expect(res.status).toBe(200);
    const body = (await res.json()) as { proposals: Record<string, unknown>[] };
    expect(body.proposals).toHaveLength(1);
    expect(body.proposals[0]).toMatchObject({
      email_confirmed: true,
      confirmed_domain: OEHHA,
      proposed_region: "california",
      proposed_domain: OEHHA,
    });
  });
});

describe("unlisted institution: moderation decisions", () => {
  it("approval activates the proposer, records the claimed institution and queues the welcome mail", async () => {
    await confirmEmail("ana@oehha.ca.gov");
    const owner = await seedAmbassador({ orcid: env.OWNER_ORCID, status: "active" });
    const id = await proposalId();
    const res = await send(
      "POST",
      "/moderation/decide",
      { type: "proposal", id, decision: "approve", region: "california", domain: OEHHA, institution_type: "government" },
      owner.cookie,
    );
    expect(res.status).toBe(200);

    const ambassador = await env.DB.prepare(
      "SELECT status, region, institution_id, welcome_sent_at FROM ambassadors WHERE status = 'active'",
    ).first<{ status: string; region: string; institution_id: string; welcome_sent_at: number | null }>();
    expect(ambassador).toMatchObject({ status: "active", region: "california", institution_id: `add:${OEHHA}` });
    expect(ambassador?.welcome_sent_at).not.toBeNull();

    const claimed = await env.DB.prepare(
      "SELECT source, eligible, claimed_at FROM ambassador_institutions WHERE institution_id = ?1",
    )
      .bind(`add:${OEHHA}`)
      .first<{ source: string; eligible: number; claimed_at: number | null }>();
    expect(claimed).toMatchObject({ source: "proposed", eligible: 1 });
    expect(claimed?.claimed_at).not.toBeNull();

    const region = await env.DB.prepare("SELECT status FROM ambassador_regions WHERE region = 'california'").first<{ status: string }>();
    expect(region?.status).toBe("active");

    const mail = await env.DB.prepare("SELECT subject, body FROM outbox WHERE to_address = ?1 ORDER BY id").bind("ana@oehha.ca.gov").all<{
      subject: string;
      body: string;
    }>();
    // Confirmation mail first, then the welcome mail (with the workspace link).
    expect(mail.results.length).toBe(2);
    expect(mail.results[0].subject).toBe(CONFIRM_SUBJECT);
    expect(mail.results[1].subject).not.toBe(CONFIRM_SUBJECT);
    expect(mail.results[1].body).toContain(WORKSPACE);
    const sessions = await env.DB.prepare("SELECT COUNT(*) AS n FROM sessions WHERE ambassador_id <> ?1").bind(owner.id).first<{ n: number }>();
    expect(sessions?.n).toBe(0);
  });

  it("rejection leaves the account inactive, keeps the note and deletes nothing", async () => {
    await confirmEmail("ana@oehha.ca.gov");
    const owner = await seedAmbassador({ orcid: env.OWNER_ORCID, status: "active" });
    const id = await proposalId();
    const res = await send(
      "POST",
      "/moderation/decide",
      { type: "proposal", id, decision: "reject", note: "Not a public body we list" },
      owner.cookie,
    );
    expect(res.status).toBe(200);
    const ambassador = await env.DB.prepare("SELECT status, email, review_state FROM ambassadors WHERE status <> 'active'").first<{
      status: string;
      email: string | null;
      review_state: string | null;
    }>();
    expect(ambassador).toMatchObject({ status: "pending", email: null, review_state: null });
    const row = await proposalRow();
    expect(row.status).toBe("rejected");
    expect(row.decision_note).toBe("Not a public body we list");
    const activeRegions = await env.DB.prepare("SELECT COUNT(*) AS n FROM ambassador_regions WHERE region = 'california'").first<{ n: number }>();
    expect(activeRegions?.n).toBe(0);
    const mail = await env.DB.prepare("SELECT COUNT(*) AS n FROM outbox WHERE to_address = ?1").bind("ana@oehha.ca.gov").first<{ n: number }>();
    expect(mail?.n).toBe(1);
  });

  it("the nightly cleanup keeps pending_review ambassadors", async () => {
    await env.DB.prepare(
      "INSERT INTO ambassadors (id, orcid, email, email_hash, status, review_state, created_at) " +
        "VALUES ('review1', '0000-0003-0000-0001', 'ana@oehha.ca.gov', 'hash-review', 'pending', 'pending_review', 0)",
    ).run();
    await env.DB.prepare("INSERT INTO ambassadors (id, orcid, status, created_at) VALUES ('stale1', '0000-0003-0000-0002', 'pending', 0)").run();
    const counts = await runCleanup(env.DB, Date.now());
    expect(counts.pending_ambassadors).toBe(1);
    const kept = await env.DB.prepare("SELECT status, review_state FROM ambassadors WHERE id = 'review1'").first<{
      status: string;
      review_state: string | null;
    }>();
    expect(kept).toMatchObject({ status: "pending", review_state: "pending_review" });
  });
});
