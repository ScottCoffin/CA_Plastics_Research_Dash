const SITEVERIFY = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

/**
 * Cloudflare Turnstile server-side check. Fails closed: a missing secret, a network error or any
 * non-success answer returns false.
 */
export async function verifyTurnstile(
  secret: string | undefined,
  token: string,
  remoteIp: string | null,
): Promise<boolean> {
  if (!secret || !token) return false;
  const form = new FormData();
  form.set("secret", secret);
  form.set("response", token);
  if (remoteIp) form.set("remoteip", remoteIp);
  try {
    const response = await fetch(SITEVERIFY, { method: "POST", body: form });
    if (!response.ok) return false;
    const data = (await response.json()) as { success?: unknown };
    return data.success === true;
  } catch {
    return false;
  }
}
