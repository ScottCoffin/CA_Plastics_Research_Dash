# Ambassador Worker (AMB-1 slice 1, local only)

Cloudflare Worker with D1 for ambassador magic-link sign-in. Spec: `docs/AMBASSADORS_SPEC.md` (sections 2, 3, 5, 6, 10, 11
and "Backend slice 1 (local)"). This folder is its own npm package; nothing here is deployed.

## Local development (no network, no real email)

Prerequisites: Node.js 20+ and npm. Run from `worker/`.

```bash
npm ci                                   # exact versions from package-lock.json
npx wrangler d1 migrations apply DB --local
npm test                                 # vitest in workerd with a local D1 (fakes Turnstile; blocks other fetches)
npx tsc --noEmit                         # typecheck
npx wrangler dev                         # optional: local server
```

For `wrangler dev`, create `worker/.dev.vars` (gitignored) with fake values only, for example:

```
MAIL_MODE=outbox
TURNSTILE_SECRET=1x0000000000000000000000000000000AA
SESSION_SIGNING_KEY=local-dev-only-signing-key-change-me
```

`MAIL_MODE=outbox` writes sign-in links to the local D1 table `outbox` instead of sending them. Turnstile's published
test secret always passes; it is for local use only.

## Configuration

- `wrangler.toml` holds names, the D1 binding (placeholder `database_id = "LOCAL-ONLY"`) and non-secret vars.
- Secrets (never in the repo): `RESEND_API_KEY`, `TURNSTILE_SECRET`, `SESSION_SIGNING_KEY`. ORCID secrets come in slice 2.
- The allowlists are bundled from `site/data/<region>/ambassador_institutions.json` at build time.

## Deploy (owner-approved only)

Do not run these without the owner's explicit approval for each step:

1. Create the D1 database and put its real id in `wrangler.toml` (owner-approved only).
2. `npx wrangler d1 migrations apply DB --remote` (owner-approved only).
3. `npx wrangler secret put RESEND_API_KEY`, `TURNSTILE_SECRET`, `SESSION_SIGNING_KEY` (owner-approved only).
4. Route the Worker under `plastiverse.live/api/*` so that cookies are same-site (owner-approved only).
5. `npx wrangler deploy` (owner-approved only).

## Tests from the repo root

`py -3.14 -m pytest -q tests/test_ambassador_worker.py` runs `npm test` here when `worker/node_modules` exists; it
skips otherwise.
