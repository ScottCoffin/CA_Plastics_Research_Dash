import { env } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { sha256Hex } from "../src/crypto";
import { SITE, api, latestToken, seedAmbassador, verify } from "./helpers";

interface InviteResponse {
  ok: boolean;
  url: string;
  mailto: string;
}

async function createInvitation(cookie: string): Promise<InviteResponse> {
  const res = await api("/invitations", { method: "POST", headers: { Cookie: cookie } });
  expect(res.status).toBe(200);
  return (await res.json()) as InviteResponse;
}

function tokenOf(url: string): string {
  const match = url.match(/\/invite\?t=([A-Za-z0-9_-]{43})$/);
  if (!match) throw new Error(`no invitation token in ${url}`);
  return match[1];
}

async function invitationCount(): Promise<number> {
  return (await env.DB.prepare("SELECT COUNT(*) AS n FROM invitations").first<{ n: number }>())?.n ?? 0;
}

describe("POST /invitations", () => {
  it("requires a session", async () => {
    expect((await api("/invitations", { method: "POST" })).status).toBe(401);
    expect(await invitationCount()).toBe(0);
  });

  it("returns a personal link and a mailto with subject and body, and no recipient address", async () => {
    const { cookie } = await seedAmbassador({ region: "norway", email: "inviter@niva.no" });
    const invite = await createInvitation(cookie);
    expect(invite.ok).toBe(true);
    expect(invite.url.startsWith("https://api.plastiverse.live/invite?t=")).toBe(true);
    expect(invite.mailto.startsWith("mailto:?subject=")).toBe(true);
    expect(invite.mailto).not.toMatch(/mailto:[^?]/);
    const decoded = decodeURIComponent(invite.mailto);
    expect(decoded).toContain("&body=");
    expect(decoded).toContain(invite.url);
    expect(decoded).not.toContain("inviter@niva.no");
    expect(decoded).not.toMatch(/@/);
  });

  it("stores only the hash of the token, never the token or any address", async () => {
    const { cookie } = await seedAmbassador({ region: "norway", email: "hash@niva.no" });
    const invite = await createInvitation(cookie);
    const token = tokenOf(invite.url);
    const rows = await env.DB.prepare("SELECT token_hash, ambassador_id FROM invitations").all<{ token_hash: string; ambassador_id: string }>();
    expect(rows.results).toHaveLength(1);
    expect(rows.results[0].token_hash).toBe(await sha256Hex(token));
    expect(rows.results[0].token_hash).not.toContain(token);
    const dump = JSON.stringify(rows.results);
    expect(dump).not.toContain("hash@niva.no");
  });

  it("is rate limited to 50 invitations per ambassador in 30 days", async () => {
    const { cookie } = await seedAmbassador({ region: "norway", email: "busy@niva.no" });
    for (let i = 0; i < 50; i++) await createInvitation(cookie);
    const blocked = await api("/invitations", { method: "POST", headers: { Cookie: cookie } });
    expect(blocked.status).toBe(429);
    expect(await invitationCount()).toBe(50);
  });

  it("the limit is per ambassador: another ambassador can still invite", async () => {
    const busy = await seedAmbassador({ region: "norway", email: "busy2@niva.no" });
    const other = await seedAmbassador({ region: "norway", email: "other@niva.no" });
    for (let i = 0; i < 50; i++) {
      await env.DB.prepare("INSERT INTO invitations (token_hash, ambassador_id, created_at) VALUES (?1, ?2, ?3)")
        .bind(`seed-${i}`, busy.id, Date.now())
        .run();
    }
    expect((await api("/invitations", { method: "POST", headers: { Cookie: busy.cookie } })).status).toBe(429);
    expect((await api("/invitations", { method: "POST", headers: { Cookie: other.cookie } })).status).toBe(200);
  });
});

describe("GET /invite", () => {
  it("redirects to the public ambassadors page with ?invited=1 and records nothing", async () => {
    const before = await invitationCount();
    const res = await api("/invite?t=" + "A".repeat(43), { redirect: "manual" });
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toBe(`${SITE}/ambassadors?invited=1`);
    expect(res.headers.get("Set-Cookie")).toBeNull();
    expect(await invitationCount()).toBe(before);
  });
});

describe("sign-ups that arrive with an invitation", () => {
  it("count once per new ambassador and never record who signed up", async () => {
    const inviter = await seedAmbassador({ region: "norway", email: "lead@niva.no" });
    const invite = await createInvitation(inviter.cookie);
    const token = tokenOf(invite.url);

    const start = await api("/auth/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "invitee@niva.no", region: "norway", turnstileToken: "good-token", invite: token }),
    });
    expect(start.status).toBe(200);
    const verified = await verify(await latestToken());
    expect(verified.status).toBe(302);
    const count = await env.DB.prepare("SELECT signups FROM invitations").first<{ signups: number }>();
    expect(count?.signups).toBe(1);

    // The same invitee signing in again is not a new join, so the count stays at 1.
    await api("/auth/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "invitee@niva.no", region: "norway", turnstileToken: "good-token", invite: token }),
    });
    await verify(await latestToken());
    expect((await env.DB.prepare("SELECT signups FROM invitations").first<{ signups: number }>())?.signups).toBe(1);

    const dump = JSON.stringify(await env.DB.prepare("SELECT * FROM invitations").all());
    expect(dump).not.toContain("invitee");
  });

  it("a malformed invitation token is ignored and sign-in still works", async () => {
    const start = await api("/auth/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "plain@niva.no", region: "norway", turnstileToken: "good-token", invite: "not-a-token" }),
    });
    expect(start.status).toBe(200);
    const link = await env.DB.prepare("SELECT invite_hash FROM magic_links").first<{ invite_hash: string | null }>();
    expect(link?.invite_hash).toBeNull();
  });
});
