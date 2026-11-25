import { env } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import type { Fetch } from "../src/outbound";
import { runReminders } from "../src/reminders";
import { SITE, seedAmbassador } from "./helpers";

const DAY = 24 * 60 * 60 * 1000;
const NOW = Date.UTC(2026, 10, 25);
const CASE_FILE_URL = `${SITE}/data/norway/ambassador_cases.json`;

/** A public case file (amb-cases-v1) with n cases; ids are amb-<12 hex>. */
function caseFile(n: number): unknown {
  return {
    schema: "amb-cases-v1",
    region: "norway",
    cases: Array.from({ length: n }, (_, i) => ({
      case_id: `amb-${(i + 1).toString(16).padStart(12, "0")}`,
      kind: "institution",
      question: "Is this right?",
      evidence: [],
      current_value: null,
      options: [],
    })),
  };
}

const caseId = (i: number): string => `amb-${i.toString(16).padStart(12, "0")}`;

/** A fake public site: serves the given files and records every URL requested. */
function fakeSite(files: Record<string, unknown>): { urls: string[]; fetchImpl: Fetch } {
  const urls: string[] = [];
  const fetchImpl: Fetch = async (input) => {
    urls.push(input);
    const body = files[input];
    if (body === undefined) return new Response("not found", { status: 404 });
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  };
  return { urls, fetchImpl };
}

async function seedNorway(email: string, createdDaysAgo = 30): Promise<string> {
  const { id } = await seedAmbassador({ region: "norway", email, created_at: NOW - createdDaysAgo * DAY });
  // The home region (ambassadors.region) is what reminders use; seedAmbassador only writes the membership row.
  await env.DB.prepare("UPDATE ambassadors SET region = 'norway' WHERE id = ?1").bind(id).run();
  return id;
}

async function outboxReminders(): Promise<{ subject: string; body: string; headers: string | null }[]> {
  const rows = await env.DB.prepare("SELECT subject, body, headers FROM outbox WHERE subject LIKE '%open task%' ORDER BY id").all<{
    subject: string;
    body: string;
    headers: string | null;
  }>();
  return rows.results;
}

async function ambassadorRow(id: string): Promise<{ reminders_unanswered: number; last_reminder_at: number | null }> {
  const row = await env.DB.prepare("SELECT reminders_unanswered, last_reminder_at FROM ambassadors WHERE id = ?1")
    .bind(id)
    .first<{ reminders_unanswered: number; last_reminder_at: number | null }>();
  if (!row) throw new Error("no ambassador");
  return row;
}

describe("fortnightly reminder", () => {
  it("is sent when tasks are open and opted in, with the time estimate, progress and List-Unsubscribe headers", async () => {
    await seedNorway("a@niva.no");
    const site = fakeSite({ [CASE_FILE_URL]: caseFile(12) });
    const counts = await runReminders(env, NOW, site.fetchImpl);
    expect(counts).toMatchObject({ scanned: 1, sent: 1, no_open_tasks: 0, paused: 0 });

    const [mail] = await outboxReminders();
    expect(mail.subject).toBe("12 open tasks in Norway");
    expect(mail.body).toContain("about 12 minutes");
    expect(mail.body).toContain("Region progress: 0 of 12 Norway cases have a confirmed answer.");
    expect(mail.body).toContain(`${SITE}/ambassadors/?region=norway&case=${caseId(1)}`);
    expect(mail.body).toContain("#notifications");
    const headers = JSON.parse(mail.headers ?? "{}") as Record<string, string>;
    expect(headers["List-Unsubscribe-Post"]).toBe("List-Unsubscribe=One-Click");
    expect(headers["List-Unsubscribe"]).toMatch(/^<https:\/\/api\.plastiverse\.live\/unsubscribe\?t=[A-Za-z0-9_-]{43}>$/);
  });

  it("is not sent when nothing is open (every case answered)", async () => {
    const id = await seedNorway("b@niva.no");
    for (const i of [1, 2]) {
      await env.DB.prepare(
        "INSERT INTO case_answers (ambassador_id, region, case_id, answer, correct_value, answered_at) VALUES (?1, 'norway', ?2, 'agree', NULL, ?3)",
      )
        .bind(id, caseId(i), NOW - DAY)
        .run();
    }
    const counts = await runReminders(env, NOW, fakeSite({ [CASE_FILE_URL]: caseFile(2) }).fetchImpl);
    expect(counts).toMatchObject({ sent: 0, no_open_tasks: 1 });
    expect(await outboxReminders()).toHaveLength(0);
  });

  it("is not sent within 14 days of the last reminder, and is sent once 14 days have passed", async () => {
    const id = await seedNorway("c@niva.no");
    const site = fakeSite({ [CASE_FILE_URL]: caseFile(3) });
    expect((await runReminders(env, NOW, site.fetchImpl)).sent).toBe(1);
    expect((await runReminders(env, NOW + DAY, site.fetchImpl)).sent).toBe(0);
    expect((await runReminders(env, NOW + 13 * DAY, site.fetchImpl)).sent).toBe(0);
    expect((await runReminders(env, NOW + 14 * DAY, site.fetchImpl)).sent).toBe(1);
    expect((await ambassadorRow(id)).reminders_unanswered).toBe(2);
    expect(await outboxReminders()).toHaveLength(2);
  });

  it("is not sent to an ambassador who opted out", async () => {
    const id = await seedNorway("d@niva.no");
    await env.DB.prepare("INSERT INTO notification_prefs (ambassador_id, reminders, product_news, updated_at) VALUES (?1, 0, 0, ?2)")
      .bind(id, NOW)
      .run();
    const counts = await runReminders(env, NOW, fakeSite({ [CASE_FILE_URL]: caseFile(3) }).fetchImpl);
    expect(counts.scanned).toBe(0);
    expect(await outboxReminders()).toHaveLength(0);
  });

  it("pauses after three unanswered reminders, and an answer restarts the count", async () => {
    const id = await seedNorway("e@niva.no", 120);
    const site = fakeSite({ [CASE_FILE_URL]: caseFile(4) });
    for (const day of [0, 14, 28]) expect((await runReminders(env, NOW + day * DAY, site.fetchImpl)).sent).toBe(1);
    expect((await ambassadorRow(id)).reminders_unanswered).toBe(3);

    expect((await runReminders(env, NOW + 42 * DAY, site.fetchImpl)).sent).toBe(0);
    expect(await outboxReminders()).toHaveLength(3);

    // The ambassador answers one case after the last reminder: the pause ends at the next due date.
    await env.DB.prepare(
      "INSERT INTO case_answers (ambassador_id, region, case_id, answer, correct_value, answered_at) VALUES (?1, 'norway', ?2, 'unsure', NULL, ?3)",
    )
      .bind(id, caseId(1), NOW + 43 * DAY)
      .run();
    const counts = await runReminders(env, NOW + 56 * DAY, site.fetchImpl);
    expect(counts.sent).toBe(1);
    expect((await ambassadorRow(id)).reminders_unanswered).toBe(1);
    const latest = (await outboxReminders()).at(-1);
    expect(latest?.body).toContain("about 3 minutes");
  });

  it("counts stream A cases only: pending stream B submissions do not add tasks", async () => {
    const id = await seedNorway("f@niva.no");
    await env.DB.prepare(
      "INSERT INTO submissions (ambassador_id, region, stream, kind, payload, status, created_at) VALUES (?1, 'norway', 'knowledge', 'paper', '{}', 'pending', ?2)",
    )
      .bind(id, NOW)
      .run();
    await runReminders(env, NOW, fakeSite({ [CASE_FILE_URL]: caseFile(2) }).fetchImpl);
    expect((await outboxReminders())[0].subject).toBe("2 open tasks in Norway");
  });

  it("reads only PUBLIC_SITE_URL data, once per region per run, and sends nothing if the file is unavailable", async () => {
    await seedNorway("g@niva.no");
    await seedNorway("h@niva.no");
    const site = fakeSite({ [CASE_FILE_URL]: caseFile(2) });
    await runReminders(env, NOW, site.fetchImpl);
    expect(site.urls).toEqual([CASE_FILE_URL]);
    expect(site.urls.every((url) => url.startsWith(`${env.PUBLIC_SITE_URL}/data/`))).toBe(true);

    await env.DB.prepare("DELETE FROM outbox").run();
    await env.DB.prepare("UPDATE ambassadors SET last_reminder_at = NULL").run();
    const missing = await runReminders(env, NOW, fakeSite({}).fetchImpl);
    expect(missing).toMatchObject({ sent: 0, fetch_failed: 2 });
    expect(await outboxReminders()).toHaveLength(0);
  });
});
