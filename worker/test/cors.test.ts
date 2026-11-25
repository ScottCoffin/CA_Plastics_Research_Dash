import { describe, expect, it } from "vitest";
import { api, me, outboxCount, startSignIn } from "./helpers";

const ALLOWED = "https://plastiverse.live";
const OTHER = "https://evil.example";

describe("CORS (only the site origin)", () => {
  it("answers the preflight for the site origin with credentials allowed", async () => {
    const res = await api(`/me`, { method: "OPTIONS", headers: { Origin: ALLOWED } });
    expect(res.status).toBe(204);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe(ALLOWED);
    expect(res.headers.get("Access-Control-Allow-Credentials")).toBe("true");
    expect(res.headers.get("Vary")).toBe("Origin");
  });

  it("refuses the preflight from another origin", async () => {
    const res = await api(`/me`, { method: "OPTIONS", headers: { Origin: OTHER } });
    expect(res.status).toBe(403);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBeNull();
  });

  it("refuses GET /me from another origin, with no CORS header", async () => {
    const res = await me(undefined, OTHER);
    expect(res.status).toBe(403);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBeNull();
  });

  it("refuses POST /auth/start from another origin and sends nothing", async () => {
    const res = await startSignIn("cross@niva.no", "norway", { origin: OTHER });
    expect(res.status).toBe(403);
    expect(await outboxCount()).toBe(0);
  });

  it("echoes the site origin on allowed responses", async () => {
    const res = await me(undefined, ALLOWED);
    expect(res.status).toBe(401);
    expect(res.headers.get("Access-Control-Allow-Origin")).toBe(ALLOWED);
  });

  it("allows requests without an Origin header (same-site and non-browser)", async () => {
    expect((await me()).status).toBe(401);
  });
});

describe("method and route handling", () => {
  it("returns 405 for the wrong method and 404 for unknown paths", async () => {
    expect((await api(`/auth/start`)).status).toBe(405);
    expect((await api(`/nope`)).status).toBe(404);
  });
});
