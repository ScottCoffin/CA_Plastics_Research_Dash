import { env } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { latestToken, network, outboxCount, startSignIn } from "./helpers";

async function body(res: Response): Promise<unknown> {
  return res.json();
}

describe("POST /auth/start eligibility", () => {
  it("sends a link to an eligible institution domain (niva.no, norway)", async () => {
    const res = await startSignIn("first.last@niva.no", "norway");
    expect(res.status).toBe(200);
    expect(res.headers.get("Cache-Control")).toBe("no-store");
    expect(await outboxCount()).toBe(1);
    const sent = await env.DB.prepare("SELECT to_address, subject FROM outbox").first<{ to_address: string }>();
    expect(sent?.to_address).toBe("first.last@niva.no");
    expect(network.turnstileTokens).toEqual(["good-token"]);
  });

  it("accepts a subdomain of an allowed registrable domain (bio.uio.no -> uio.no)", async () => {
    const res = await startSignIn("student@bio.uio.no", "norway");
    expect(res.status).toBe(200);
    expect(await outboxCount()).toBe(1);
    const link = await env.DB.prepare("SELECT institution_id FROM magic_links").first<{ institution_id: string }>();
    expect(link?.institution_id).toMatch(/^I\d+$/);
  });

  it("refuses free-mail with the same response shape and sends nothing", async () => {
    const eligible = await (await startSignIn("someone@niva.no", "norway")).json();
    const res = await startSignIn("someone@gmail.com", "norway");
    expect(res.status).toBe(200);
    expect(await body(res)).toEqual(eligible);
    expect(await outboxCount()).toBe(1); // only the eligible one above
  });

  it("refuses a subdomain of free-mail (x.gmail.com)", async () => {
    const res = await startSignIn("someone@mail.gmail.com", "norway");
    expect(res.status).toBe(200);
    expect(await outboxCount()).toBe(0);
  });

  it("gives an unknown domain the same status and body as an eligible one", async () => {
    const eligible = await startSignIn("a@niva.no", "norway");
    const unknown = await startSignIn("nobody@not-a-real-institution.example", "norway");
    expect(unknown.status).toBe(eligible.status);
    expect(await body(unknown)).toEqual(await body(eligible));
    expect(await outboxCount()).toBe(1);
  });

  it("refuses an eligible domain under the wrong region with the same shape", async () => {
    const res = await startSignIn("someone@niva.no", "california");
    expect(res.status).toBe(200);
    expect(await outboxCount()).toBe(0);
  });

  it("stores only the hash of the token, never the token itself", async () => {
    await startSignIn("hash.check@niva.no", "norway");
    const token = await latestToken();
    const row = await env.DB.prepare("SELECT token_hash FROM magic_links").first<{ token_hash: string }>();
    expect(row?.token_hash).toMatch(/^[0-9a-f]{64}$/);
    expect(row?.token_hash).not.toBe(token);
  });

  it("returns 403 when the Turnstile check fails, and sends nothing", async () => {
    network.turnstileSuccess = false;
    const res = await startSignIn("bot@niva.no", "norway");
    expect(res.status).toBe(403);
    expect(await body(res)).toEqual({ ok: false, error: "bot_check_failed" });
    expect(await outboxCount()).toBe(0);
  });

  it("treats a missing Turnstile token as a failed bot check without calling Turnstile", async () => {
    const res = await startSignIn("bot@niva.no", "norway", { turnstileToken: null });
    expect(res.status).toBe(403);
    expect(network.turnstileTokens).toEqual([]);
  });

  it("rejects malformed requests with 400", async () => {
    expect((await startSignIn("not-an-email", "norway")).status).toBe(400);
    expect((await startSignIn("a@niva.no", "atlantis")).status).toBe(400);
  });
});

describe("POST /auth/start rate limits", () => {
  it("limits five requests per address per hour, counting ineligible addresses too", async () => {
    const statuses: number[] = [];
    for (let i = 0; i < 6; i++) {
      statuses.push((await startSignIn("loop@not-a-real-institution.example", "norway", { ip: "10.0.0.9" })).status);
    }
    expect(statuses).toEqual([200, 200, 200, 200, 200, 429]);
    const limited = await startSignIn("loop@not-a-real-institution.example", "norway", { ip: "10.0.0.9" });
    expect(await body(limited)).toEqual({ ok: false, error: "rate_limited" });
  });

  it("limits thirty requests per client IP across addresses", async () => {
    let last = 0;
    for (let i = 0; i < 31; i++) {
      last = (await startSignIn(`user${i}@not-a-real-institution.example`, "norway", { ip: "10.0.0.77" })).status;
    }
    expect(last).toBe(429);
  });
});
