export const SESSION_COOKIE = "__Host-plastiverse_session";
export const SESSION_MAX_AGE_S = 30 * 24 * 60 * 60;
// Short-lived sign-up cookies (slice 2a). Both use __Host- names: Secure, Path=/, no Domain.
export const SIGNUP_COOKIE = "__Host-plastiverse_signup";
export const SIGNUP_MAX_AGE_S = 60 * 60;
export const ORCID_NONCE_COOKIE = "__Host-plastiverse_orcid";
export const ORCID_NONCE_MAX_AGE_S = 10 * 60;

export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
      ...headers,
    },
  });
}

export function redirect(location: string, headers: Record<string, string> = {}): Response {
  return new Response(null, {
    status: 302,
    headers: { Location: location, "Cache-Control": "no-store", ...headers },
  });
}

// The __Host- prefix forces Secure, Path=/ and no Domain attribute.
export function sessionCookie(value: string): string {
  return `${SESSION_COOKIE}=${value}; Path=/; Max-Age=${SESSION_MAX_AGE_S}; HttpOnly; Secure; SameSite=Lax`;
}

/** Host-only, Secure, HttpOnly cookie (the __Host- prefix forces Path=/ and no Domain). */
export function hostCookie(name: string, value: string, maxAgeS: number): string {
  return `${name}=${value}; Path=/; Max-Age=${maxAgeS}; HttpOnly; Secure; SameSite=Lax`;
}

export function clearSessionCookie(): string {
  return `${SESSION_COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax`;
}

export function readCookie(request: Request, name: string): string | null {
  const header = request.headers.get("Cookie");
  if (!header) return null;
  for (const part of header.split(";")) {
    const eq = part.indexOf("=");
    if (eq > 0 && part.slice(0, eq).trim() === name) return part.slice(eq + 1).trim();
  }
  return null;
}
