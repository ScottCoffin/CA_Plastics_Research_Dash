# Ambassador Worker (AMB-1 slices 1, 2a and 2b, local only)

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

- `wrangler.toml` holds names, the D1 binding (the production database id, created 2026-11-25) and non-secret vars.
  `PUBLIC_API_URL` is the API host `https://api.plastiverse.live` (QUESTIONS AMB-API-HOST).
- Secrets (never in the repo): `RESEND_API_KEY`, `TURNSTILE_SECRET`, `SESSION_SIGNING_KEY`, `EMAIL_HASH_KEY`,
  `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET`. Email lookups use `EMAIL_HASH_KEY` only (separate from the session key).
- The ORCID redirect URI to register with ORCID: `https://api.plastiverse.live/orcid/callback`.
- The allowlists are bundled from `site/data/<region>/ambassador_institutions.json` at build time.
- `OWNER_ORCID` (wrangler.toml `[vars]`) is a placeholder; the account with that ORCID iD is the owner. The owner sets the
  real iD before deploy (owner action).
- Secret `EXPORT_TOKEN` (owner-approved `wrangler secret put` only): the bearer token for `/export/approved`. Unset, the export refuses every request.
- `PUBLIC_SITE_URL` (wrangler.toml `[vars]`, `https://plastiverse.live`): the only host the reminder pass reads case files from.
- Migrations: `0001_init.sql` (slice 1), `0002_orcid_signup.sql` (slice 2a), `0003_submissions.sql` (slice 2b),
  `0004_notifications.sql` (slice 2c). Read the migration note in 0002 before any
  remote apply: slice-1 local rows were keyed with `SESSION_SIGNING_KEY` and must be reset, not re-hashed.

## Routes

- `POST /auth/start`, `GET /auth/verify`, `GET /me`, `POST /auth/signout`: slice 1 (see the spec).
- `GET /orcid/start`, `GET /orcid/callback`: ORCID OAuth (`/authenticate`), state and nonce hashed, single use.
- `GET /signup/profile` (signup cookie): OpenAlex author and ORCID employments, returns the institution checklist.
- `POST /signup/claims` (signup cookie): claims from the checklist, regions tied to claimed eligible institutions, proposals.
- `POST /signup/email` (signup cookie): one institutional email (Turnstile, rate limits), single-use link.
- `POST /signup/profile` (session cookie): display name, credit (default on), terms `v1`.
- `POST /cases/answer` (session, active member of the region): `{region, case_id, answer: agree|disagree|unsure,
  correct_value?}` (`correct_value` required for `disagree` only). One answer per ambassador and case; a re-answer replaces it.
  Returns the case's consensus (null until two active ambassadors agree).
- `GET /cases/answers?region=`: the caller's own answers, each with its consensus. Other people's single answers are never returned.
- `POST /submissions` (session, member): `{region, stream: confirm|knowledge, kind, payload}`, status `pending`.
  Payload keys are allowed per kind (`src/submissions.ts`, `KINDS`); https URLs only; no HTML; length limits.
- `GET /submissions/mine` (session): the caller's submissions with status and decision note.
- `GET /moderation/queue?region=` (owner or lead): pending submissions and proposals. Owner and leads see every region.
- `POST /moderation/decide` (owner or lead): `{type: submission|proposal, id, decision: approve|reject, note?}`. A
  moderator cannot decide their own item. Audited. Approving a proposal records the decision only (no activation).
- `POST /moderation/leads` (owner or lead): `{ambassador_id, region}` promotes an active member of that region to lead.
- `POST /moderation/suspend` (owner only): `{ambassador_id}` sets `suspended` and deletes their sessions.
- `GET /export/approved?since=<ms>` (bearer `EXPORT_TOKEN`, read-only): approved submissions and consensus case answers.
  No emails, email hashes, ambassador ids or ORCID iDs.
- Slice 2c (local): `GET /me/notifications` and `POST /me/notifications` (session) `{reminders?, product_news?}`
  (reminders on and product news off by default); `GET /unsubscribe?t=` (confirmation page, changes nothing) and
  `POST /unsubscribe?t=` (RFC 8058 one-click, turns reminders off); `POST /invitations` (session; returns `url` and a
  `mailto:` href with no recipient; 50 per 30 days); `GET /invite?t=` (records nothing, redirects to
  `SITE_ORIGIN/ambassadors/?invited=1`). `POST /auth/start` accepts an optional `invite` token, counted once when that
  sign-up joins. Welcome mail once per ambassador (on `/auth/verify`). Mail templates: `src/templates.ts`.
- Scheduled (cron `17 3 * * *`), after the cleanup: the fortnightly reminder pass (`src/reminders.ts`). A reminder goes to an
  active opted-in ambassador with open stream A tasks in the home region, 14 days after the last reminder (or the welcome,
  or the sign-up). It pauses after three unanswered reminders until sign-in or an answer. Batch: 200 candidates per run.
  Logs counts only.
- Scheduled (cron `17 3 * * *`): deletes expired ORCID states, sign-up sessions and magic links, and pending sign-ups
  older than 7 days with no email proof. Logs counts only.

Outbound calls (ORCID token, ORCID employments, OpenAlex) go through `src/outbound.ts`; `handle()` takes the fetch as
an argument, and the production default is the global `fetch`.

## Deploy (owner-approved only)

Do not run these without the owner's explicit approval for each step:

1. Create the D1 database and put its real id in `wrangler.toml` (owner-approved only).
2. `npx wrangler d1 migrations apply DB --remote` (owner-approved only).
3. `npx wrangler secret put RESEND_API_KEY`, `TURNSTILE_SECRET`, `SESSION_SIGNING_KEY`, `EMAIL_HASH_KEY`,
   `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET`, `EXPORT_TOKEN` (owner-approved only). Set `OWNER_ORCID` in `wrangler.toml` first.
4. Route the Worker under `api.plastiverse.live` (owner-approved only) and register the ORCID redirect URI above.
5. `npx wrangler deploy` (owner-approved only).

## Tests from the repo root

`py -3.14 -m pytest -q tests/test_ambassador_worker.py` runs `npm test` here when `worker/node_modules` exists; it
skips otherwise.
