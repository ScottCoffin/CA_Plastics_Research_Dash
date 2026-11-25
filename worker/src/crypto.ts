const encoder = new TextEncoder();

export function b64url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/** 32 random bytes by default, base64url (43 characters). */
export function randomToken(bytes = 32): string {
  return b64url(crypto.getRandomValues(new Uint8Array(bytes)));
}

export function randomHex(bytes = 16): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(bytes)), (b) => b.toString(16).padStart(2, "0")).join("");
}

function hex(bytes: ArrayBuffer): string {
  return Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, "0")).join("");
}

export async function sha256Hex(value: string): Promise<string> {
  return hex(await crypto.subtle.digest("SHA-256", encoder.encode(value)));
}

async function hmacKey(secret: string): Promise<CryptoKey> {
  return crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, [
    "sign",
    "verify",
  ]);
}

/** Keyed hash with a purpose prefix, so one key cannot be replayed across purposes. */
export async function keyedHash(secret: string, purpose: string, value: string): Promise<string> {
  const key = await hmacKey(secret);
  return hex(await crypto.subtle.sign("HMAC", key, encoder.encode(`${purpose}:${value}`)));
}

/** Session cookie value: "<session id>.<HMAC(session id)>". */
export async function signSessionId(secret: string, sessionId: string): Promise<string> {
  const key = await hmacKey(secret);
  const sig = await crypto.subtle.sign("HMAC", key, encoder.encode(`session:${sessionId}`));
  return `${sessionId}.${b64url(new Uint8Array(sig))}`;
}

/** Returns the session id when the signature is valid (constant-time check), otherwise null. */
export async function verifySignedSessionId(secret: string, signed: string): Promise<string | null> {
  const dot = signed.lastIndexOf(".");
  if (dot <= 0) return null;
  const sessionId = signed.slice(0, dot);
  const sig = signed.slice(dot + 1);
  if (!/^[A-Za-z0-9_-]{43}$/.test(sessionId) || !/^[A-Za-z0-9_-]{43}$/.test(sig)) return null;
  const key = await hmacKey(secret);
  const raw = Uint8Array.from(atob(sig.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (sig.length % 4)) % 4)), (c) =>
    c.charCodeAt(0),
  );
  const ok = await crypto.subtle.verify("HMAC", key, raw, encoder.encode(`session:${sessionId}`));
  return ok ? sessionId : null;
}
