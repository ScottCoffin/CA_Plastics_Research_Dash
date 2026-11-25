import { type Ctx, handleMe, handleSignout, handleStart, handleVerify } from "./auth";
import type { Env } from "./env";
import { json } from "./http";
import { type Fetch, liveFetch } from "./outbound";
import {
  handleOrcidCallback,
  handleOrcidStart,
  handleProfileSave,
  handleSignupClaims,
  handleSignupEmail,
  handleSignupLookup,
} from "./signup";

const ALLOWED_METHODS = "GET, POST, OPTIONS";

function corsHeaders(origin: string): Record<string, string> {
  return {
    "Access-Control-Allow-Origin": origin,
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Methods": ALLOWED_METHODS,
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "600",
    Vary: "Origin",
  };
}

/**
 * JSON API. CORS: only ALLOWED_ORIGIN may call, with credentials. Any other Origin header is refused
 * with 403 before routing, so a foreign site cannot start sign-in or read /me.
 * `fetchImpl` carries the outbound calls to ORCID and OpenAlex (tests pass a fake; production uses fetch).
 */
export async function handle(
  request: Request,
  env: Env,
  now: number = Date.now(),
  fetchImpl: Fetch = liveFetch,
): Promise<Response> {
  const origin = request.headers.get("Origin");
  if (origin !== null && origin !== env.ALLOWED_ORIGIN) return json({ ok: false, error: "origin_not_allowed" }, 403);
  const withCors = (res: Response): Response => {
    if (origin !== null) for (const [k, v] of Object.entries(corsHeaders(origin))) res.headers.set(k, v);
    return res;
  };

  if (request.method === "OPTIONS") return withCors(new Response(null, { status: 204 }));

  const url = new URL(request.url);
  const ctx: Ctx = { now, fetch: fetchImpl };
  const methodNotAllowed = (): Response => withCors(json({ ok: false, error: "method_not_allowed" }, 405));
  try {
    switch (url.pathname) {
      case "/auth/start":
        if (request.method !== "POST") return methodNotAllowed();
        return withCors(await handleStart(request, env, ctx));
      case "/auth/verify":
        // Opened from the email link: a top-level GET with no Origin header, so CORS does not apply.
        if (request.method !== "GET") return json({ ok: false, error: "method_not_allowed" }, 405);
        return handleVerify(url, env, ctx);
      case "/orcid/start":
        // Top-level navigation from the site; redirects to ORCID. No CORS.
        if (request.method !== "GET") return json({ ok: false, error: "method_not_allowed" }, 405);
        return handleOrcidStart(env, ctx);
      case "/orcid/callback":
        // Top-level redirect back from ORCID. No CORS.
        if (request.method !== "GET") return json({ ok: false, error: "method_not_allowed" }, 405);
        return handleOrcidCallback(url, request, env, ctx);
      case "/signup/profile":
        if (request.method === "GET") return withCors(await handleSignupLookup(request, env, ctx));
        if (request.method === "POST") return withCors(await handleProfileSave(request, env, ctx));
        return methodNotAllowed();
      case "/signup/claims":
        if (request.method !== "POST") return methodNotAllowed();
        return withCors(await handleSignupClaims(request, env, ctx));
      case "/signup/email":
        if (request.method !== "POST") return methodNotAllowed();
        return withCors(await handleSignupEmail(request, env, ctx));
      case "/me":
        if (request.method !== "GET") return methodNotAllowed();
        return withCors(await handleMe(request, env, ctx));
      case "/auth/signout":
        if (request.method !== "POST") return methodNotAllowed();
        return withCors(await handleSignout(request, env, ctx));
      default:
        return withCors(json({ ok: false, error: "not_found" }, 404));
    }
  } catch (err) {
    // Log the error class only; never echo secrets, emails or tokens.
    console.error("request failed", err instanceof Error ? err.name : "unknown");
    return withCors(json({ ok: false, error: "internal" }, 500));
  }
}

export default {
  fetch(request: Request, env: Env): Promise<Response> {
    return handle(request, env);
  },
} satisfies ExportedHandler<Env>;
