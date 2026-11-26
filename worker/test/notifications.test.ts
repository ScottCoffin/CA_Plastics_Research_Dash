import { env } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { sha256Hex } from "../src/crypto";
import { escapeHtml, listUnsubscribeHeaders, welcomeMail } from "../src/templates";
import { api, seedAmbassador, signIn } from "./helpers";

interface Sent {
  to_address: string;
  subject: string;
  body: string;
  headers: string | null;
}

async function sentWithSubject(prefix: string): Promise<Sent[]> {
  const rows = await env.DB.prepare("SELECT to_address, subject, body, headers FROM outbox WHERE subject LIKE ?1 ORDER BY id")
    .bind(`${prefix}%`)
    .all<Sent>();
  return rows.results;
}

/** The one-click unsubscribe token from a mail body. */
function unsubscribeToken(body: string): string {
  const match = body.match(/unsubscribe\?t=([A-Za-z0-9_-]{43})/);
  if (!match) throw new Error("no unsubscribe link in mail");
  return match[1];
}

describe("welcome mail", () => {
  it("is queued once, when the ambassador first joins", async () => {
    await signIn("first.last@niva.no", "norway");
    expect(await sentWithSubject("Welcome")).toHaveLength(1);
    await signIn("first.last@niva.no", "norway");
    expect(await sentWithSubject("Welcome")).toHaveLength(1);
    const row = await env.DB.prepare("SELECT welcome_sent_at FROM ambassadors").first<{ welcome_sent_at: number | null }>();
    expect(row?.welcome_sent_at).not.toBeNull();
  });

  it("carries the settings link, one-click unsubscribe and List-Unsubscribe headers; sign-in mail has none", async () => {
    await signIn("first.last@niva.no", "norway");
    const [welcome] = await sentWithSubject("Welcome");
    expect(welcome.body).toContain("#notifications");
    const token = unsubscribeToken(welcome.body);
    const headers = JSON.parse(welcome.headers ?? "{}") as Record<string, string>;
    expect(headers["List-Unsubscribe"]).toBe(`<https://api.plastiverse.live/unsubscribe?t=${token}>`);
    expect(headers["List-Unsubscribe-Post"]).toBe("List-Unsubscribe=One-Click");

    const signInMail = await env.DB.prepare("SELECT headers FROM outbox WHERE subject LIKE 'Your Plastiverse%'").first<{ headers: string | null }>();
    expect(signInMail?.headers).toBeNull();
  });

  it("templates: HTML escapes text and uses no images, scripts or tracking", () => {
    const links = { settingsUrl: "https://plastiverse.live/ambassadors#notifications", unsubscribeUrl: "https://api.plastiverse.live/unsubscribe?t=x" };
    const mail = welcomeMail({ regionName: "Norway", workspaceUrl: "https://plastiverse.live/ambassadors", links });
    expect(mail.html).not.toMatch(/<img|<script|<iframe|src=/i);
    expect(escapeHtml(`<a href="x">&'`)).toBe("&lt;a href=&quot;x&quot;&gt;&amp;&#39;");
    expect(listUnsubscribeHeaders(links.unsubscribeUrl)["List-Unsubscribe"]).toBe(`<${links.unsubscribeUrl}>`);
  });
});

describe("one-click unsubscribe", () => {
  it("GET shows a confirmation page and changes nothing; POST turns reminders off", async () => {
    await signIn("first.last@niva.no", "norway");
    const [welcome] = await sentWithSubject("Welcome");
    const token = unsubscribeToken(welcome.body);

    const page = await api(`/unsubscribe?t=${token}`);
    expect(page.status).toBe(200);
    expect(page.headers.get("Content-Type")).toContain("text/html");
    expect(await page.text()).toContain('method="post"');
    expect(await env.DB.prepare("SELECT COUNT(*) AS n FROM notification_prefs").first<{ n: number }>()).toEqual({ n: 0 });

    const post = await api(`/unsubscribe?t=${token}`, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: "List-Unsubscribe=One-Click" });
    expect(post.status).toBe(200);

    const row = await env.DB.prepare("SELECT reminders FROM notification_prefs").first<{ reminders: number }>();
    expect(row?.reminders).toBe(0);
  });

  it("stores the unsubscribe token only as a hash, and a repeated POST is harmless", async () => {
    await signIn("first.last@niva.no", "norway");
    const [welcome] = await sentWithSubject("Welcome");
    const token = unsubscribeToken(welcome.body);
    const stored = await env.DB.prepare("SELECT token_hash FROM unsubscribe_tokens").all<{ token_hash: string }>();
    expect(stored.results.map((r) => r.token_hash)).toEqual([await sha256Hex(token)]);
    expect(stored.results[0].token_hash).not.toBe(token);
    for (let i = 0; i < 2; i++) {
      expect((await api(`/unsubscribe?t=${token}`, { method: "POST" })).status).toBe(200);
    }
  });

  it("refuses unknown or malformed tokens on GET and POST", async () => {
    const bogus = "A".repeat(43);
    expect((await api(`/unsubscribe?t=${bogus}`)).status).toBe(404);
    expect((await api(`/unsubscribe?t=${bogus}`, { method: "POST" })).status).toBe(404);
    expect((await api("/unsubscribe?t=short", { method: "POST" })).status).toBe(404);
    expect((await api("/unsubscribe")).status).toBe(404);
  });
});

describe("notification settings (session)", () => {
  it("defaults to reminders on and product news off, and both can be changed", async () => {
    const { cookie } = await seedAmbassador({ region: "norway", email: "a@niva.no" });
    const first = await (await api("/me/notifications", { headers: { Cookie: cookie } })).json();
    expect(first).toEqual({ ok: true, notifications: { reminders: true, product_news: false } });

    const set = await api("/me/notifications", {
      method: "POST",
      headers: { Cookie: cookie, "Content-Type": "application/json" },
      body: JSON.stringify({ product_news: true, reminders: false }),
    });
    expect(set.status).toBe(200);
    expect(await set.json()).toEqual({ ok: true, notifications: { reminders: false, product_news: true } });
    expect(await (await api("/me/notifications", { headers: { Cookie: cookie } })).json()).toEqual({
      ok: true,
      notifications: { reminders: false, product_news: true },
    });
  });

  it("rejects non-boolean values and empty bodies; requires a session", async () => {
    const { cookie } = await seedAmbassador({ region: "norway", email: "b@niva.no" });
    const post = (body: string) =>
      api("/me/notifications", { method: "POST", headers: { Cookie: cookie, "Content-Type": "application/json" }, body });
    expect((await post(JSON.stringify({ reminders: "no" }))).status).toBe(400);
    expect((await post("{}")).status).toBe(400);
    expect((await post("not json")).status).toBe(400);
    expect((await api("/me/notifications")).status).toBe(401);
  });

  it("a sign-in resets the unanswered-reminder counter and records last_seen_at", async () => {
    await seedAmbassador({ region: "norway", email: "first.last@niva.no", created_at: Date.now() - 90 * 86400000 });
    await env.DB.prepare("UPDATE ambassadors SET reminders_unanswered = 3").run();
    await signIn("first.last@niva.no", "norway");
    const row = await env.DB.prepare("SELECT reminders_unanswered, last_seen_at FROM ambassadors").first<{
      reminders_unanswered: number;
      last_seen_at: number | null;
    }>();
    expect(row?.reminders_unanswered).toBe(0);
    expect(row?.last_seen_at).not.toBeNull();
  });
});
