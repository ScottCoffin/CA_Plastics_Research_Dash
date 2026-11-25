export interface Env {
  DB: D1Database;
  SITE_ORIGIN: string;
  ALLOWED_ORIGIN: string;
  WORKSPACE_URL: string;
  PUBLIC_API_URL: string;
  /** Public site origin (slice 2c): the only host the reminder pass fetches case files from. */
  PUBLIC_SITE_URL: string;
  MAIL_FROM: string;
  /** ORCID iD of the owner account (non-secret, wrangler.toml). The account with this iD is the owner. */
  OWNER_ORCID: string;
  /** "resend" (production) or "outbox" (local dev and tests only). */
  MAIL_MODE?: string;
  // Secrets (Worker secrets; never in wrangler.toml).
  RESEND_API_KEY?: string;
  TURNSTILE_SECRET?: string;
  SESSION_SIGNING_KEY?: string;
  /** Keys email lookups (slice 2a). Separate from SESSION_SIGNING_KEY so either can rotate alone. */
  EMAIL_HASH_KEY?: string;
  ORCID_CLIENT_ID?: string;
  ORCID_CLIENT_SECRET?: string;
  /** Bearer token for GET /export/approved (the PR job). Unset means the export refuses every request. */
  EXPORT_TOKEN?: string;
}

/** Fail closed: a missing secret is a server error, never a silent fallback. */
export function requireSecret(value: string | undefined, name: keyof Env): string {
  if (!value) throw new Error(`missing secret ${String(name)}`);
  return value;
}
