import { isRegion } from "./eligibility";
import type { Env } from "./env";
import { chooseSender } from "./mail";
import { type Fetch } from "./outbound";
import { mintLinks } from "./notifications";
import { consensusByCase } from "./submissions";
import { listUnsubscribeHeaders, regionName, reminderMail } from "./templates";

const DAY_MS = 24 * 60 * 60 * 1000;
/** One reminder per fortnight, measured from the last reminder (or the welcome, or the sign-up). */
export const REMINDER_INTERVAL_MS = 14 * DAY_MS;
/** Reminders pause after this many reminders with no answer, until the ambassador signs in or answers. */
export const REMINDER_PAUSE_AFTER = 3;
/** Candidates examined per run; at most one mail per candidate, so this also caps mails per run. */
export const REMINDER_BATCH_LIMIT = 200;
/** A case without a `minutes` field counts as one minute (owner: "about N minutes"). */
const DEFAULT_CASE_MINUTES = 1;
const MAX_CASE_MINUTES = 120;
const CASE_ID_RE = /^amb-[0-9a-f]{12}$/;

export interface ReminderCounts {
  scanned: number;
  sent: number;
  no_open_tasks: number;
  paused: number;
  fetch_failed: number;
  send_failed: number;
}

interface PublicCase {
  case_id: string;
  minutes: number;
}

interface Candidate {
  id: string;
  email: string;
  region: string;
  unanswered: number;
  answers_since: number;
  anchor: number;
}

function caseMinutes(value: unknown): number {
  return typeof value === "number" && Number.isInteger(value) && value >= 1 && value <= MAX_CASE_MINUTES
    ? value
    : DEFAULT_CASE_MINUTES;
}

/**
 * Reads the public per-region case file (amb-cases-v1) through the injected fetch. Only
 * `${PUBLIC_SITE_URL}/data/<region>/ambassador_cases.json` is ever requested. Returns null on any failure.
 */
export async function loadCaseFile(env: Env, region: string, fetchImpl: Fetch): Promise<PublicCase[] | null> {
  if (!isRegion(region)) return null;
  try {
    const res = await fetchImpl(`${env.PUBLIC_SITE_URL}/data/${region}/ambassador_cases.json`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    const payload = (await res.json()) as { schema?: unknown; cases?: unknown };
    if (payload.schema !== "amb-cases-v1" || !Array.isArray(payload.cases)) return null;
    const out: PublicCase[] = [];
    for (const item of payload.cases) {
      if (typeof item !== "object" || item === null) continue;
      const record = item as { case_id?: unknown; minutes?: unknown };
      if (typeof record.case_id === "string" && CASE_ID_RE.test(record.case_id)) {
        out.push({ case_id: record.case_id, minutes: caseMinutes(record.minutes) });
      }
    }
    return out;
  } catch (err) {
    console.error("case file read failed", err instanceof Error ? err.name : "unknown");
    return null;
  }
}

/**
 * Fortnightly reminder pass (daily cron, extended from the cleanup). Sends to active ambassadors who opted in, have
 * open stream A tasks in their home region, were last reminded (or joined) at least 14 days ago, and have fewer than
 * three unanswered reminders. Stream B items are not counted. Logs counts only, never addresses.
 */
export async function runReminders(env: Env, now: number, fetchImpl: Fetch): Promise<ReminderCounts> {
  const counts: ReminderCounts = { scanned: 0, sent: 0, no_open_tasks: 0, paused: 0, fetch_failed: 0, send_failed: 0 };
  const dueBefore = now - REMINDER_INTERVAL_MS;
  const anchor = "COALESCE(a.last_reminder_at, a.welcome_sent_at, a.created_at)";
  const answersSince =
    "(SELECT COUNT(*) FROM case_answers c WHERE c.ambassador_id = a.id AND c.answered_at > COALESCE(a.last_reminder_at, 0))";
  const { results } = await env.DB.prepare(
    "SELECT a.id, a.email, a.region, a.reminders_unanswered AS unanswered, " +
      `${answersSince} AS answers_since, ${anchor} AS anchor ` +
      "FROM ambassadors a LEFT JOIN notification_prefs p ON p.ambassador_id = a.id " +
      "WHERE a.status = 'active' AND a.email IS NOT NULL AND a.region IS NOT NULL " +
      "AND COALESCE(p.reminders, 1) = 1 " +
      `AND ${anchor} <= ?1 ` +
      `AND (a.reminders_unanswered < ?2 OR ${answersSince} > 0) ` +
      `ORDER BY ${anchor} LIMIT ?3`,
  )
    .bind(dueBefore, REMINDER_PAUSE_AFTER, REMINDER_BATCH_LIMIT)
    .all<Candidate>();

  const caseCache = new Map<string, Promise<PublicCase[] | null>>();
  const consensusCache = new Map<string, ReturnType<typeof consensusByCase>>();
  const casesFor = (region: string): Promise<PublicCase[] | null> => {
    let cached = caseCache.get(region);
    if (!cached) {
      cached = loadCaseFile(env, region, fetchImpl);
      caseCache.set(region, cached);
    }
    return cached;
  };

  for (const candidate of results) {
    counts.scanned += 1;
    if (!isRegion(candidate.region)) continue;
    let unanswered = candidate.unanswered;
    if (candidate.answers_since > 0 && unanswered > 0) {
      // The ambassador answered since the last reminder: the counter restarts.
      unanswered = 0;
      await env.DB.prepare("UPDATE ambassadors SET reminders_unanswered = 0 WHERE id = ?1").bind(candidate.id).run();
    }
    if (unanswered >= REMINDER_PAUSE_AFTER) {
      counts.paused += 1;
      continue;
    }

    const cases = await casesFor(candidate.region);
    if (cases === null) {
      counts.fetch_failed += 1;
      continue;
    }
    const answered = await env.DB.prepare("SELECT case_id FROM case_answers WHERE ambassador_id = ?1 AND region = ?2")
      .bind(candidate.id, candidate.region)
      .all<{ case_id: string }>();
    const answeredIds = new Set(answered.results.map((r) => r.case_id));
    const open = cases.filter((c) => !answeredIds.has(c.case_id));
    if (open.length === 0) {
      counts.no_open_tasks += 1;
      continue;
    }

    let consensus = consensusCache.get(candidate.region);
    if (!consensus) {
      consensus = consensusByCase(env.DB, candidate.region);
      consensusCache.set(candidate.region, consensus);
    }
    const agreed = await consensus;
    const confirmed = cases.filter((c) => agreed.has(c.case_id)).length;
    const minutes = open.reduce((sum, c) => sum + c.minutes, 0);
    try {
      const links = await mintLinks(env, candidate.id, now);
      const mail = reminderMail({
        regionName: regionName(candidate.region),
        open: open.length,
        minutes,
        confirmed,
        total: cases.length,
        nextUrl: `${env.WORKSPACE_URL}?region=${candidate.region}&case=${encodeURIComponent(open[0].case_id)}`,
        links,
      });
      await chooseSender(env).send({
        to: candidate.email,
        subject: mail.subject,
        text: mail.text,
        html: mail.html,
        headers: listUnsubscribeHeaders(links.unsubscribeUrl),
      });
      await env.DB.prepare("UPDATE ambassadors SET last_reminder_at = ?1, reminders_unanswered = ?2 WHERE id = ?3")
        .bind(now, unanswered + 1, candidate.id)
        .run();
      counts.sent += 1;
    } catch (err) {
      console.error("reminder send failed", err instanceof Error ? err.name : "unknown");
      counts.send_failed += 1;
    }
  }
  return counts;
}
