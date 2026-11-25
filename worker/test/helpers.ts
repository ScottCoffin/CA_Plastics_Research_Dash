import { SELF, env } from "cloudflare:test";
import { afterEach, beforeEach } from "vitest";

const TABLES = [
  "audit_log",
  "outbox",
  "sessions",
  "signup_sessions",
  "orcid_states",
  "proposals",
  "magic_links",
  "ambassador_regions",
  "ambassador_institutions",
  "ambassadors",
  "rate_limits",
];

export const SITE = "https://plastiverse.live";
const API = "https://api.plastiverse.live";
const TURNSTILE_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

export interface FakeNetwork {
  turnstileTokens: string[];
  turnstileSuccess: boolean;
  /** ORCID iD the fake OAuth exchange verifies (null: token endpoint refuses). */
  orcidId: string | null;
  /** Bodies of token exchanges, to check the redirect URI and secret were sent. */
  orcidTokenForms: URLSearchParams[];
  /** OpenAlex author answer: HTTP status and body (status 404 means no author). */
  openalex: { status: number; body: unknown };
  /** ORCID public employments answer. */
  employments: { status: number; body: unknown };
  /** User-Agent values seen on OpenAlex calls. */
  openalexUserAgents: string[];
}

/**
 * Replaces globalThis.fetch for each test. Turnstile siteverify is answered locally; any other
 * outbound request throws, so no test can reach Cloudflare, Resend or the internet.
 */
export const network: FakeNetwork = freshNetwork();
const realFetch = globalThis.fetch;

function freshNetwork(): FakeNetwork {
  return {
    turnstileTokens: [],
    turnstileSuccess: true,
    orcidId: "0000-0002-1825-0097",
    orcidTokenForms: [],
    openalex: { status: 404, body: {} },
    employments: { status: 200, body: { "affiliation-group": [] } },
    openalexUserAgents: [],
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

beforeEach(async () => {
  // Each test starts from an empty local D1 (the migrations stay applied).
  for (const table of TABLES) await env.DB.prepare(`DELETE FROM ${table}`).run();
  Object.assign(network, freshNetwork());
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url === TURNSTILE_URL) {
      const form = init?.body as FormData;
      network.turnstileTokens.push(String(form.get("response")));
      return json({ success: network.turnstileSuccess });
    }
    if (url === "https://orcid.org/oauth/token") {
      network.orcidTokenForms.push(new URLSearchParams(String(init?.body)));
      if (network.orcidId === null) return json({ error: "invalid_grant" }, 400);
      return json({ orcid: network.orcidId, name: "Test Person", access_token: "not-stored" });
    }
    if (url.startsWith("https://pub.orcid.org/v3.0/") && url.endsWith("/employments")) {
      return json(network.employments.body, network.employments.status);
    }
    if (url.startsWith("https://api.openalex.org/authors/orcid:")) {
      const headers = new Headers(init?.headers);
      network.openalexUserAgents.push(headers.get("User-Agent") ?? "");
      return json(network.openalex.body, network.openalex.status);
    }
    throw new Error(`network disabled in tests: ${url}`);
  }) as typeof fetch;
});

afterEach(() => {
  globalThis.fetch = realFetch;
});

export function startSignIn(
  email: string,
  region = "norway",
  options: { turnstileToken?: string | null; origin?: string; ip?: string } = {},
): Promise<Response> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (options.origin !== undefined) headers.Origin = options.origin;
  if (options.ip !== undefined) headers["CF-Connecting-IP"] = options.ip;
  const body: Record<string, unknown> = { email, region };
  if (options.turnstileToken !== null) body.turnstileToken = options.turnstileToken ?? "good-token";
  return SELF.fetch(`${SITE}/auth/start`, { method: "POST", headers, body: JSON.stringify(body) });
}

/** The newest sign-in link token sent to the local outbox (dev and test sender). */
export async function latestToken(): Promise<string> {
  const row = await env.DB.prepare("SELECT body FROM outbox ORDER BY id DESC LIMIT 1").first<{ body: string }>();
  const match = row?.body.match(/token=([A-Za-z0-9_-]{43})/);
  if (!match) throw new Error("no sign-in link in outbox");
  return match[1];
}

export async function outboxCount(): Promise<number> {
  const row = await env.DB.prepare("SELECT COUNT(*) AS n FROM outbox").first<{ n: number }>();
  return row?.n ?? 0;
}

export function verify(token: string): Promise<Response> {
  return SELF.fetch(`${SITE}/auth/verify?token=${token}`, { redirect: "manual" });
}

/** Cookie pair ("name=value") from a Set-Cookie header, for replaying in later requests. */
export function sessionPair(res: Response): string {
  const setCookie = res.headers.get("Set-Cookie") ?? "";
  const pair = setCookie.split(";")[0];
  if (!pair.startsWith("__Host-plastiverse_session=")) throw new Error("no session cookie");
  return pair;
}

/** Request to the Worker through SELF (never the real network). `path` starts with "/". */
export function api(path: string, init?: RequestInit): Promise<Response> {
  return SELF.fetch(`${SITE}${path}`, init);
}

export function me(cookie?: string, origin?: string): Promise<Response> {
  const headers: Record<string, string> = {};
  if (cookie) headers.Cookie = cookie;
  if (origin) headers.Origin = origin;
  return SELF.fetch(`${SITE}/me`, { headers });
}

/** Full sign-in for an address: start, read the link from the outbox, verify. Returns the session cookie. */
export async function signIn(email: string, region = "norway"): Promise<string> {
  const start = await startSignIn(email, region);
  if (start.status !== 200) throw new Error(`start failed ${start.status}`);
  const res = await verify(await latestToken());
  if (res.status !== 302 || !res.headers.get("Set-Cookie")) throw new Error("verify failed");
  return sessionPair(res);
}
