"""Build the weekly email digest of new California plastics papers; --send publishes it (MAIL-1).

The digest covers one Monday-to-Sunday week (UTC) of works whose ``first_seen`` falls inside it.
The default week is the most recent Sunday. Sending needs the repository secret
BUTTONDOWN_API_KEY; without it, or when the week has no new works, the script logs why and
exits 0 without a request.

    py -3.14 scripts/build_weekly_digest.py --out scratch/digest          # preview files
    py -3.14 scripts/build_weekly_digest.py --dry-run                     # print the request
    py -3.14 scripts/build_weekly_digest.py --week-ending 2026-11-15 --send
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from atlas.build.digest import (
    API_KEY_ENV,
    BUTTONDOWN_API,
    DEFAULT_ABSTRACTS,
    DEFAULT_CONFIG,
    DEFAULT_WORKS,
    EDITOR_MODE,
    Digest,
    DigestError,
    build_digest,
    email_payload,
    idempotency_key,
    last_sunday,
    load_abstracts,
    load_settings,
    load_works,
    parse_week_ending,
    render_html,
    render_text,
    send_digest,
    subject_line,
)


def _week_ending_arg(text: str):
    try:
        return parse_week_ending(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{exc} (got {text!r})") from None


def dry_run_text(digest: Digest, subject: str, html_body: str) -> str:
    """The two requests --send would make, with the key shown only as a placeholder."""
    shown = dict(email_payload(subject, html_body))
    shown["body"] = f"{EDITOR_MODE} [{len(html_body):,} characters of HTML]"
    note = (
        "no works this week: --send would skip"
        if digest.total == 0
        else f"{digest.total} works, {len(digest.cards)} listed"
    )
    lines = [
        f"POST {BUTTONDOWN_API}/emails",
        f"Authorization: Token <{API_KEY_ENV}>",
        "Content-Type: application/json",
        f"X-Idempotency-Key: {idempotency_key(digest.week_end)}",
        json.dumps(shown, ensure_ascii=True, indent=2),
        f"then POST {BUTTONDOWN_API}/emails/<id>/publish (same Authorization header, body {{}})",
        f"Dry run: nothing was sent ({note}).",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None, *, opener=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--week-ending",
        type=_week_ending_arg,
        default=None,
        help="Sunday that ends the week (YYYY-MM-DD). Default: the most recent Sunday (UTC).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="directory for preview files digest.html and digest.txt",
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--send", action="store_true", help="publish the digest to subscribers via Buttondown"
    )
    modes.add_argument(
        "--dry-run", action="store_true", help="print the requests --send would make; send nothing"
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--works", type=Path, default=DEFAULT_WORKS)
    parser.add_argument("--abstracts", type=Path, default=DEFAULT_ABSTRACTS)
    args = parser.parse_args(argv)

    try:
        settings = load_settings(args.config)
        works = load_works(args.works)
    except DigestError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    try:
        abstracts = load_abstracts(args.abstracts)
    except DigestError as exc:
        print(f"WARNING: digest without abstracts; {exc}", file=sys.stderr)
        abstracts = {}

    week_ending = args.week_ending or last_sunday(datetime.now(UTC).date())
    digest = build_digest(
        works,
        abstracts,
        week_ending=week_ending,
        max_works=settings.max_works,
        site_url=settings.site_url,
        max_age_days=settings.max_age_days,
    )
    subject = subject_line(settings, digest)
    print(
        f"Week {digest.week_start} to {digest.week_end} (UTC): {digest.total} new "
        f"plastic-related works; {len(digest.cards)} listed."
    )
    print(f"Subject: {subject}")
    html_body = render_html(digest, settings)

    if args.out is not None:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "digest.html").write_text(html_body, encoding="utf-8")
        (args.out / "digest.txt").write_text(render_text(digest, settings), encoding="utf-8")
        print(f"Wrote {args.out / 'digest.html'} and {args.out / 'digest.txt'}")

    if args.dry_run:
        print(dry_run_text(digest, subject, html_body))
        return 0
    if not args.send:
        return 0
    if digest.total == 0:
        print("No new plastic-related works this week; digest not sent.")
        return 0
    api_key = os.environ.get(API_KEY_ENV, "").strip()
    if not api_key:
        print(f"{API_KEY_ENV} is not set; digest not sent (no-op).")
        return 0
    try:
        email_id = send_digest(
            api_key=api_key,
            subject=subject,
            html_body=html_body,
            idempotency=idempotency_key(week_ending),
            opener=opener,
        )
    except DigestError as exc:
        # The key never reaches an error message, but scrub it anyway.
        message = str(exc).replace(api_key, "[key removed]")
        print(f"ERROR: digest not sent: {message}", file=sys.stderr)
        return 1
    print(f"Sent digest email {email_id}: {digest.total} new works, {len(digest.cards)} listed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
