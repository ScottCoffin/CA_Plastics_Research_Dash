import type { Env } from "./env";
import { requireSecret } from "./env";

export interface OutgoingMail {
  to: string;
  subject: string;
  text: string;
  /** Optional minimal HTML body (no tracking pixels, no external images). */
  html?: string;
  /** Optional extra headers, e.g. RFC 8058 List-Unsubscribe on non-essential mail. */
  headers?: Record<string, string>;
}

export interface EmailSender {
  send(mail: OutgoingMail): Promise<void>;
}

/** Production sender: Resend HTTP API (free tier, plastiverse.live sender with SPF/DKIM). */
export class ResendSender implements EmailSender {
  constructor(
    private readonly apiKey: string,
    private readonly from: string,
    private readonly fetchImpl: typeof fetch = (...args) => fetch(...args),
  ) {}

  async send(mail: OutgoingMail): Promise<void> {
    const response = await this.fetchImpl("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${this.apiKey}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        from: this.from,
        to: [mail.to],
        subject: mail.subject,
        text: mail.text,
        ...(mail.html !== undefined ? { html: mail.html } : {}),
        ...(mail.headers !== undefined ? { headers: mail.headers } : {}),
      }),
    });
    if (!response.ok) throw new Error(`resend responded ${response.status}`);
  }
}

/** Local dev and tests: stores the message in D1 table `outbox`. Never used in production. */
export class OutboxSender implements EmailSender {
  constructor(private readonly db: D1Database) {}

  async send(mail: OutgoingMail): Promise<void> {
    await this.db
      .prepare("INSERT INTO outbox (created_at, to_address, subject, body, headers) VALUES (?1, ?2, ?3, ?4, ?5)")
      .bind(Date.now(), mail.to, mail.subject, mail.text, mail.headers ? JSON.stringify(mail.headers) : null)
      .run();
  }
}

export function chooseSender(env: Env): EmailSender {
  if (env.MAIL_MODE === "outbox") return new OutboxSender(env.DB);
  return new ResendSender(requireSecret(env.RESEND_API_KEY, "RESEND_API_KEY"), env.MAIL_FROM);
}
