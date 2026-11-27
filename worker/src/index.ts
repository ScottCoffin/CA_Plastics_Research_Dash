import { type Ctx, handleMe, handleSignout, handleStart, handleVerify } from "./auth";
import { runCleanup } from "./cleanup";
import { handleCoauthors } from "./coauthors";
import type { Env } from "./env";
import { handleExport } from "./export";
import { handleCreateInvitation, handleInvite } from "./invitations";
import { json } from "./http";
import { handleGetNotifications, handleSetNotifications, handleUnsubscribe, handleUnsubscribePage } from "./notifications";
import { handlePromoteLead, handleQueue, handleDecide, handleSuspend } from "./moderation";
import { type Fetch, liveFetch } from "./outbound";
import { runReminders } from "./reminders";
import {
  handleOrcidCallback,
  handleOrcidStart,
  handleProfileSave,
  handleSignupClaims,
  handleSignupEmail,
  handleSignupLookup,
} from "./signup";
import { handleReview, handleReviewQueue } from "./group_qa";
import { handleGroupBatch } from "./groups";
import { handleCaseAnswer, handleCaseAnswers, handleMySubmissions, handleSubmit } from "./submissions";

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
      case "/cases/answer":
        if (request.method !== "POST") return methodNotAllowed();
        return withCors(await handleCaseAnswer(request, env, ctx));
      case "/cases/answers":
        if (request.method !== "GET") return methodNotAllowed();
        return withCors(await handleCaseAnswers(request, env, ctx));
      case "/submissions":
        if (request.method !== "POST") return methodNotAllowed();
        return withCors(await handleSubmit(request, env, ctx));
      case "/submissions/mine":
        if (request.method !== "GET") return methodNotAllowed();
        return withCors(await handleMySubmissions(request, env, ctx));
      case "/groups/batch":
        if (request.method !== "GET") return methodNotAllowed();
        return withCors(await handleGroupBatch(request, env, ctx));
      case "/groups/reviews":
        if (request.method === "GET") return withCors(await handleReviewQueue(request, env, ctx));
        if (request.method === "POST") return withCors(await handleReview(request, env, ctx));
        return methodNotAllowed();
      case "/moderation/queue":
        if (request.method !== "GET") return methodNotAllowed();
        return withCors(await handleQueue(request, env, ctx));
      case "/moderation/decide":
        if (request.method !== "POST") return methodNotAllowed();
        return withCors(await handleDecide(request, env, ctx));
      case "/moderation/leads":
        if (request.method !== "POST") return methodNotAllowed();
        return withCors(await handlePromoteLead(request, env, ctx));
      case "/moderation/suspend":
        if (request.method !== "POST") return methodNotAllowed();
        return withCors(await handleSuspend(request, env, ctx));
      case "/me/notifications":
        if (request.method === "GET") return withCors(await handleGetNotifications(request, env, ctx));
        if (request.method === "POST") return withCors(await handleSetNotifications(request, env, ctx));
        return methodNotAllowed();
      case "/me/coauthors":
        if (request.method !== "GET") return methodNotAllowed();
        return withCors(await handleCoauthors(request, env, ctx));
      case "/invitations":
        if (request.method !== "POST") return methodNotAllowed();
        return withCors(await handleCreateInvitation(request, env, ctx));
      case "/invite":
        // Personal invitation link opened by the invitee (top-level GET). Records nothing. No CORS.
        if (request.method !== "GET") return json({ ok: false, error: "method_not_allowed" }, 405);
        return handleInvite(env);
      case "/unsubscribe":
        // Mail links and one-click POST from mail clients (no Origin, no CORS). The GET only shows a page.
        if (request.method === "GET") return handleUnsubscribePage(url, env);
        if (request.method === "POST") return handleUnsubscribe(url, env, ctx.now);
        return json({ ok: false, error: "method_not_allowed" }, 405);
      case "/export/approved":
        // Read-only feed for the PR job (bearer token, server-to-server). No CORS.
        if (request.method !== "GET") return json({ ok: false, error: "method_not_allowed" }, 405);
        return handleExport(request, env, ctx);
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
  /**
   * Cron "17 3 * * *": expired sign-up state and stale pending sign-ups (cleanup), then the fortnightly reminder pass.
   * Logs counts only.
   */
  async scheduled(_controller: ScheduledController, env: Env): Promise<void> {
    const counts = await runCleanup(env.DB, Date.now());
    console.log("cleanup", JSON.stringify(counts));
    const reminders = await runReminders(env, Date.now(), liveFetch);
    console.log("reminders", JSON.stringify(reminders));
  },
} satisfies ExportedHandler<Env>;
