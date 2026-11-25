# Buttondown: weekly email digest (MAIL-1)

Checked on 2026-11-17 against the public Buttondown API docs (introduction, authentication,
formatting, rate limits, create email, publish email, idempotency keys). No live call has been
made. The digest script (`scripts/build_weekly_digest.py`) sends only with `--send`, and the
scheduled workflow (`.github/workflows/weekly_digest.yml`) runs only when the repository secret
`BUTTONDOWN_API_KEY` exists.

## Endpoints used

| Step | Request | Body and headers |
|---|---|---|
| 1. Draft | `POST https://api.buttondown.com/v1/emails` | JSON `subject`, `body`, `template: "naked"`; header `X-Idempotency-Key: atlas-digest-<week ending>` |
| 2. Publish | `POST https://api.buttondown.com/v1/emails/{id}/publish` | JSON `{}`; publishes and sends now (no `publish_date`) |

- Auth: header `Authorization: Token <key>` (the word Token, then a space). The key comes only
  from the environment variable `BUTTONDOWN_API_KEY`. The script never prints it, and errors are
  scrubbed of it.
- The idempotency key means a repeated run for the same week reuses the draft rather than
  making a second one. Publishing a sent email again fails, which is the intended guard.
- Rate limit: 600 requests a minute for all endpoints. A digest makes two requests.
- If publish fails after the draft is created, the error names the draft id. Publish it from the
  Buttondown app or fix the cause and re-run.

## Body format (verified from the create-email docs)

- The body is HTML or Markdown. Buttondown detects the format from tags. The digest also starts
  with `<!-- buttondown-editor-mode: fancy -->`, which states HTML explicitly.
- A body that starts with `---` is rejected (`body_contains_frontmatter`). The digest never does.
- `template: "naked"` uses the body as the whole email with no Buttondown wrapper.
- `email_type` defaults to public, so the digest is also published in the public web archive.

## Not verified

- **Unsubscribe placeholder.** The digest uses `{{ unsubscribe_url }}`. This merge tag was not
  found in the Buttondown docs pages read. Verify it before the first live send (owner step 4).
- **Plain text.** The API takes one `body` and the docs read define no separate text part.
  `digest.txt` is a preview copy only. Whether Buttondown derives a text part from the HTML is
  not known.
- **Buttondown tracking.** The digest adds no tracking pixel. Whether Buttondown adds open or
  click tracking of its own is not verified.

## Owner steps

1. Create the Buttondown account and newsletter. Set the newsletter name to `Plastiverse · California`.
2. In Buttondown, create an API key (API, then Keys). Add it as the repository secret
   `BUTTONDOWN_API_KEY` (GitHub: Settings, Secrets and variables, Actions).
3. Confirm the PLAT-1 move is live before the first send. Links point to
   `https://plastiverse.live/california` (`config/notifications.yml`, `digest.site_url`).
4. Check the unsubscribe link and layout. In Buttondown, create a draft, paste the HTML from
   `scratch/digest/digest.html` into fancy mode, send a test to yourself, and click Unsubscribe.
5. Decide whether the digest should stay in the public archive (default: yes).
6. To preview a week: `py -3.14 scripts/build_weekly_digest.py --out scratch/digest` (files only)
   or `--dry-run` (prints the requests with the key shown as a placeholder).
7. The first scheduled run is Monday 14:00 UTC. To run it early, use Actions, Weekly digest,
   Run workflow, with an empty `week_ending` for the most recent Sunday.

## Known data limits

- Awards are not in the digest. `site/data/california/grants.json` has no `first_seen`; `start` is the award
  start, not the date the Atlas added it.
- Experts are not in the digest. "New expert" has no agreed definition yet.
- Backfill: 1,397 plastic-related works share `first_seen` 2026-11-11. Any week that includes
  that date looks far larger than the real weekly additions (the week ending 2026-11-15 shows
  1,565). The owner should decide whether to set a floor before the first live week.
