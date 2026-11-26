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
 * ids or ORCID iDs. Ambassador names appear only where the ambassador kept public credit. `institutions` lists approved
 * institution proposals (region, name, url, domain, institution_type, decided_at) and never the applicant.
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
      "WHERE s.status = 'approved' AND s.decided_at >= ?1 " +
      "AND NOT (s.kind = 'group_tag' AND json_extract(s.payload, '$.second_tag_for') IS NOT NULL) ORDER BY s.decided_at, s.id",
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

  // Approved institution proposals with their allowlist fields (AMB-1 proposals-to-allowlist, part 1). Rows approved
  // before migration 0005 have no region and are not exported. Only the public name and URL from the payload appear.
  const institutionRows = await env.DB.prepare(
    "SELECT p.id, p.region, p.domain, p.institution_type, p.payload, p.decided_at FROM proposals p " +
      "WHERE p.kind = 'institution' AND p.status = 'approved' AND p.decided_at >= ?1 " +
      "AND p.region IS NOT NULL AND p.domain IS NOT NULL AND p.institution_type IS NOT NULL ORDER BY p.decided_at, p.id",
  )
    .bind(since)
    .all<{ id: number; region: string; domain: string; institution_type: string; payload: string; decided_at: number }>();

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
    institutions: institutionRows.results.map((p) => {
      const payload = JSON.parse(p.payload) as { name?: unknown; url?: unknown };
      return {
        id: p.id,
        region: p.region,
        name: typeof payload.name === "string" ? payload.name : null,
        url: typeof payload.url === "string" ? payload.url : null,
        domain: p.domain,
        institution_type: p.institution_type,
        decided_at: p.decided_at,
      };
    }),
  });
}
