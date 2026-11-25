import type { Ctx } from "./auth";
import type { Env } from "./env";
import { REGIONS, type Region } from "./eligibility";
import { sha256Hex } from "./crypto";
import { json } from "./http";
import { consensusByCase } from "./submissions";

/**
 * Constant-time comparison. Both values are hashed first, so the compare is over fixed-length digests and the
 * length of the presented token does not leak.
 */
export async function tokenMatches(presented: string, expected: string): Promise<boolean> {
  const a = await sha256Hex(presented);
  const b = await sha256Hex(expected);
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

/**
 * GET /export/approved?since=<ms>: read-only feed for the PR job. Bearer EXPORT_TOKEN. Returns approved submissions
 * and consensus case answers whose latest change is at or after `since`. Never returns emails, email hashes, ambassador
 * ids or ORCID iDs. Ambassador names appear only where the ambassador kept public credit.
 * Unset EXPORT_TOKEN refuses every request (fail closed).
 */
export async function handleExport(request: Request, env: Env, ctx: Ctx): Promise<Response> {
  const header = request.headers.get("Authorization") ?? "";
  const presented = header.startsWith("Bearer ") ? header.slice("Bearer ".length).trim() : "";
  if (!env.EXPORT_TOKEN || presented === "" || !(await tokenMatches(presented, env.EXPORT_TOKEN))) {
    return json({ ok: false, error: "unauthorized" }, 401, { "WWW-Authenticate": "Bearer" });
  }

  const sinceParam = new URL(request.url).searchParams.get("since") ?? "0";
  if (!/^\d{1,16}$/.test(sinceParam)) return json({ ok: false, error: "invalid_since" }, 400);
  const since = Number(sinceParam);
  if (!Number.isSafeInteger(since)) return json({ ok: false, error: "invalid_since" }, 400);

  const approved = await env.DB.prepare(
    "SELECT s.id, s.region, s.stream, s.kind, s.payload, s.decided_at, " +
      "CASE WHEN a.credit_public = 1 THEN a.display_name ELSE NULL END AS credit_name " +
      "FROM submissions s JOIN ambassadors a ON a.id = s.ambassador_id " +
      "WHERE s.status = 'approved' AND s.decided_at >= ?1 ORDER BY s.decided_at, s.id",
  )
    .bind(since)
    .all<{
      id: number;
      region: string;
      stream: string;
      kind: string;
      payload: string;
      decided_at: number;
      credit_name: string | null;
    }>();

  // Consensus per case (not 'unsure'). Only cases whose latest agreeing answer is at or after `since` are exported.
  const caseRows: { region: string; case_id: string; answer: string; correct_value: string | null; answered_at: number }[] = [];
  for (const region of REGIONS as readonly Region[]) {
    const latest = await env.DB.prepare(
      "SELECT ca.case_id, MAX(ca.answered_at) AS at FROM case_answers ca JOIN ambassadors a ON a.id = ca.ambassador_id " +
        "WHERE ca.region = ?1 AND ca.answer <> 'unsure' AND a.status = 'active' GROUP BY ca.case_id",
    )
      .bind(region)
      .all<{ case_id: string; at: number }>();
    const changed = new Map(latest.results.filter((r) => r.at >= since).map((r) => [r.case_id, r.at]));
    if (changed.size === 0) continue;
    const consensus = await consensusByCase(env.DB, region);
    for (const [caseId, at] of changed) {
      const agreed = consensus.get(caseId);
      if (agreed) caseRows.push({ region, case_id: caseId, answer: agreed.answer, correct_value: agreed.correct_value, answered_at: at });
    }
  }

  return json({
    ok: true,
    generated_at: ctx.now,
    since,
    submissions: approved.results.map((s) => ({
      id: s.id,
      region: s.region,
      stream: s.stream,
      kind: s.kind,
      payload: JSON.parse(s.payload) as unknown,
      decided_at: s.decided_at,
      credit_name: s.credit_name,
    })),
    case_answers: caseRows,
  });
}
