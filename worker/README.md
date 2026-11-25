# Ambassador Worker (AMB-1 slices 1 and 2a, local only)

Cloudflare Worker with D1 for ambassador sign-in: ORCID-first sign-up (slice 2a) and the email-first magic link
(slice 1, kept for compatibility). Spec: `docs/AMBASSADORS_SPEC.md` (sections 2, 3, 12, 13, "Backend slice 1 (local)"
and "Backend slice 2a (ORCID-first sign-up, local only)"). This folder is its own npm package; nothing here is deployed.

## Local development (no network, no real email)

Prerequisites: Node.js 20+ and npm. Run from `worker/`.

```bash
npm ci                                   # exact versions from package-lock.json
npx wrangler d1 migrations apply DB --local
npm test                                 # vitest in workerd with a local D1 (fakes Turnstile, ORCID, OpenAlex; blocks other fetches)
npx tsc --noEmit                         # typecheck
npx wrangler dev                         # optional: local server
```

For `wrangler dev`, create `worker/.dev.vars` (gitignored) with fake values only, for example:

```
MAIL_MODE=outbox
TURNSTILE_SECRET=1x0000000000000000000000000000000AA
SESSION_SIGNING_KEY=local-dev-only-signing-key-change-me
EMAIL_HASH_KEY=local-dev-only-email-key-change-me
ORCID_CLIENT_ID=APP-LOCAL-ONLY
ORCID_CLIENT_SECRET=local-dev-only-orcid-secret
```

`MAIL_MODE=outbox` writes sign-in links to the local D1 table `outbox` instead of sending them. Turnstile's published
test secret always passes; it is for local use only. Local `wrangler dev` cannot complete a real ORCID login with fake
client values; the tests cover the flow with a fake ORCID.

## Configuration

- `wrangler.toml` holds names, the D1 binding (placeholder `database_id = "LOCAL-ONLY"`) and non-secret vars.
  `PUBLIC_API_URL` is the API host `https://api.plastiverse.live` (QUESTIONS AMB-API-HOST).
- Secrets (never in the repo): `RESEND_API_KEY`, `TURNSTILE_SECRET`, `SESSION_SIGNING_KEY`, `EMAIL_HASH_KEY`,
  `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET`. Email lookups use `EMAIL_HASH_KEY` only (separate from the session key).
- The ORCID redirect URI to register with ORCID: `https://api.plastiverse.live/orcid/callback`.
- The allowlists are bundled from `site/data/<region>/ambassador_institutions.json` at build time.
- Migrations: `0001_init.sql` (slice 1), `0002_orcid_signup.sql` (slice 2a). Read the migration note in 0002 before any
  remote apply: slice-1 local rows were keyed with `SESSION_SIGNING_KEY` and must be reset, not re-hashed.

## Routes

- `POST /auth/start`, `GET /auth/verify`, `GET /me`, `POST /auth/signout`: slice 1 (see the spec).
- `GET /orcid/start`, `GET /orcid/callback`: ORCID OAuth (`/authenticate`), state and nonce hashed, single use.
- `GET /signup/profile` (signup cookie): OpenAlex author and ORCID employments, returns the institution checklist.
- `POST /signup/claims` (signup cookie): claims from the checklist, regions tied to claimed eligible institutions, proposals.
- `POST /signup/email` (signup cookie): one institutional email (Turnstile, rate limits), single-use link.
- `POST /signup/profile` (session cookie): display name, credit (default on), terms `v1`.

Outbound calls (ORCID token, ORCID employments, OpenAlex) go through `src/outbound.ts`; `handle()` takes the fetch as
an argument, and the production default is the global `fetch`.

## Deploy (owner-approved only)

Do not run these without the owner's explicit approval for each step:

1. Create the D1 database and put its real id in `wrangler.toml` (owner-approved only).
2. `npx wrangler d1 migrations apply DB --remote` (owner-approved only).
3. `npx wrangler secret put RESEND_API_KEY`, `TURNSTILE_SECRET`, `SESSION_SIGNING_KEY`, `EMAIL_HASH_KEY`,
   `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET` (owner-approved only).
4. Route the Worker under `api.plastiverse.live` (owner-approved only) and register the ORCID redirect URI above.
5. `npx wrangler deploy` (owner-approved only).

## Tests from the repo root

`py -3.14 -m pytest -q tests/test_ambassador_worker.py` runs `npm test` here when `worker/node_modules` exists; it
skips otherwise.
