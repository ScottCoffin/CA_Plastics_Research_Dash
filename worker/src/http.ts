export const SESSION_COOKIE = "__Host-plastiverse_session";
export const SESSION_MAX_AGE_S = 30 * 24 * 60 * 60;

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
