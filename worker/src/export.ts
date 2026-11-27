import type { Ctx } from "./auth";
import type { Env } from "./env";
import { REGIONS, type Region } from "./eligibility";
import { keyedHash, sha256Hex } from "./crypto";
import { exportPairs, exportReviews } from "./group_qa";
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
 * `group_pairs` (CG-7b) lists blind agreement pairs whose primary tag is approved: the Tier-1 values of the primary
 * (value_a) and of the first usable second tag (value_b). `group_reviews` lists reviewer checks per Tier-1 facet with
 * the original and reviewed values and the reason code. Neither carries an ambassador id, a name or the pair basis.
 * AMB-ROSTER-QC: each `same_as` answer in an approved group_tag gains `rater` (a keyed hash of the ambassador and the
 * unordered pair: the same ambassador gives the same token for one pair, and tokens cannot be linked across pairs) and
 * `by_moderator` (the tagger is the owner or a lead). Without SESSION_SIGNING_KEY the answers are left out.
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
    "SELECT s.id, s.region, s.stream, s.kind, s.payload, s.decided_at, s.ambassador_id, a.role, a.orcid, " +
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
      ambassador_id: string;
      role: string;
      orcid: string | null;
      credit_name: string | null;
    }>();

  const submissions = [];
  for (const s of approved.results) {
    const payload = JSON.parse(s.payload) as Record<string, unknown>;
    if (s.kind === "group_tag" && Array.isArray(payload.same_as)) {
      payload.same_as = await raterAnswers(env, payload, s.ambassador_id, s.role === "lead" || (s.orcid !== null && s.orcid === env.OWNER_ORCID));
      if ((payload.same_as as unknown[]).length === 0) delete payload.same_as;
    }
    submissions.push({
      id: s.id,
      region: s.region,
      stream: s.stream,
      kind: s.kind,
      payload,
      decided_at: s.decided_at,
      credit_name: s.credit_name,
    });
  }

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
    submissions,
    case_answers: caseRows,
    group_pairs: await exportPairs(env.DB, since),
    group_reviews: await exportReviews(env.DB, since),
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

/** The duplicate answers with an unlinkable per-pair rater token; none when the signing key is unset (fail closed). */
async function raterAnswers(
  env: Env,
  payload: Record<string, unknown>,
  ambassadorId: string,
  byModerator: boolean,
): Promise<Record<string, unknown>[]> {
  if (!env.SESSION_SIGNING_KEY || typeof payload.group_id !== "string") return [];
  const out: Record<string, unknown>[] = [];
  for (const item of payload.same_as as Record<string, unknown>[]) {
    if (typeof item.group_id !== "string") continue;
    const pair = [payload.group_id, item.group_id].sort().join("|");
    const rater = (await keyedHash(env.SESSION_SIGNING_KEY, "roster-qc-rater", `${ambassadorId}|${pair}`)).slice(0, 16);
    out.push({ group_id: item.group_id, answer: item.answer, rater, by_moderator: byModerator });
  }
  return out;
}
