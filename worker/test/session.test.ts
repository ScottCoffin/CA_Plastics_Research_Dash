import { env } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { api, latestToken, me, signIn, startSignIn, verify } from "./helpers";

const WORKSPACE = "https://plastiverse.live/ambassadors/";

describe("GET /auth/verify (single-use, expiring links)", () => {
  it("signs in once, redirects to the workspace and sets the session cookie", async () => {
    await startSignIn("once@niva.no", "norway");
    const res = await verify(await latestToken());
    expect(res.status).toBe(302);
    expect(res.headers.get("Location")).toBe(WORKSPACE);
    expect(res.headers.get("Set-Cookie")).toContain("__Host-plastiverse_session=");
  });

  it("refuses a second use of the same link", async () => {
    await startSignIn("single@niva.no", "norway");
    const token = await latestToken();
    const first = await verify(token);
    expect(first.headers.get("Set-Cookie")).not.toBeNull();
    const second = await verify(token);
    expect(second.status).toBe(302);
    expect(second.headers.get("Location")).toBe(`${WORKSPACE}?signin=failed`);
    expect(second.headers.get("Set-Cookie")).toBeNull();
  });

  it("refuses an expired link", async () => {
    await startSignIn("late@niva.no", "norway");
    const token = await latestToken();
    await env.DB.prepare("UPDATE magic_links SET expires_at = 0").run();
    const res = await verify(token);
    expect(res.headers.get("Location")).toBe(`${WORKSPACE}?signin=failed`);
    expect(res.headers.get("Set-Cookie")).toBeNull();
  });

  it("refuses an unknown or malformed token without leaking which", async () => {
    const res = await verify("x".repeat(43));
    expect(res.headers.get("Location")).toBe(`${WORKSPACE}?signin=failed`);
    const malformed = await verify("short");
    expect(malformed.headers.get("Location")).toBe(`${WORKSPACE}?signin=failed`);
  });

  it("creates one ambassador per address, even across sign-ins", async () => {
    await signIn("repeat@niva.no", "norway");
    await signIn("repeat@niva.no", "norway");
    const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM ambassadors").first<{ n: number }>();
    expect(row?.n).toBe(1);
  });
});

describe("session cookie", () => {
  it("has HttpOnly, Secure, SameSite=Lax, Path=/, a 30-day Max-Age and the __Host- prefix", async () => {
    await startSignIn("flags@niva.no", "norway");
    const res = await verify(await latestToken());
    const cookie = res.headers.get("Set-Cookie") ?? "";
    expect(cookie).toMatch(/^__Host-plastiverse_session=[A-Za-z0-9_-]{43}\.[A-Za-z0-9_-]{43};/);
    expect(cookie).toContain("Path=/");
    expect(cookie).toContain("Max-Age=2592000");
    expect(cookie).toContain("HttpOnly");
    expect(cookie).toContain("Secure");
    expect(cookie).toContain("SameSite=Lax");
    expect(cookie).not.toContain("Domain=");
  });

  it("is accepted by /me, which returns a masked email only", async () => {
    const cookie = await signIn("profile@niva.no", "norway");
    const res = await me(cookie);
    expect(res.status).toBe(200);
    const text = await res.text();
    expect(text).toContain('"email_masked":"p***@niva.no"');
    expect(text).not.toContain("profile@niva.no");
    expect(JSON.parse(text).ambassador.needs_profile).toBe(true);
  });

  it("rejects a tampered signature", async () => {
    const cookie = await signIn("tamper@niva.no", "norway");
    const value = cookie.split("=")[1];
    const last = value.slice(-1) === "A" ? "B" : "A";
    const forged = `__Host-plastiverse_session=${value.slice(0, -1)}${last}`;
    expect((await me(forged)).status).toBe(401);
  });

  it("rejects a cookie with a different session id under the old signature", async () => {
    const cookie = await signIn("swap@niva.no", "norway");
    const [, sig] = cookie.split("=")[1].split(".");
    const forged = `__Host-plastiverse_session=${"A".repeat(43)}.${sig}`;
    expect((await me(forged)).status).toBe(401);
  });

  it("rejects a cookie signed with another key", async () => {
    const { signSessionId } = await import("../src/crypto");
    const foreign = await signSessionId("some-other-key", "A".repeat(43));
    expect((await me(`__Host-plastiverse_session=${foreign}`)).status).toBe(401);
  });

  it("stops working when the server-side session expires", async () => {
    const cookie = await signIn("expiry@niva.no", "norway");
    await env.DB.prepare("UPDATE sessions SET expires_at = 0").run();
    expect((await me(cookie)).status).toBe(401);
  });

  it("stores only hashes of session ids", async () => {
    const cookie = await signIn("hashes@niva.no", "norway");
    const sessionId = cookie.split("=")[1].split(".")[0];
    const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM sessions WHERE id_hash = ?1")
      .bind(sessionId)
      .first<{ n: number }>();
    expect(row?.n).toBe(0);
  });
});

describe("POST /auth/signout", () => {
  it("deletes the session and clears the cookie", async () => {
    const cookie = await signIn("leave@niva.no", "norway");
    expect((await me(cookie)).status).toBe(200);
    const out = await api(`/auth/signout`, { method: "POST", headers: { Cookie: cookie } });
    expect(out.status).toBe(200);
    expect(out.headers.get("Set-Cookie")).toContain("Max-Age=0");
    expect((await me(cookie)).status).toBe(401);
  });

  it("is idempotent without a session", async () => {
    const out = await api(`/auth/signout`, { method: "POST" });
    expect(out.status).toBe(200);
  });
});

describe("GET /me without a session", () => {
  it("returns 401", async () => {
    const res = await me();
    expect(res.status).toBe(401);
  });
});
