import { SELF, env } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { isFreeMailDomain, parseAllowlistFields } from "../src/moderation";
import { seedAmbassador } from "./helpers";

// Approved institution proposals join a region's eligible list (AMB-1 proposals-to-allowlist, part 1). Runs against the
// local D1 in workerd; no network. OWNER_ORCID comes from wrangler.toml through the test env.

const API = "https://api.plastiverse.live";
const OWNER_ORCID = env.OWNER_ORCID;
const EXPORT_TOKEN = "test-export-token-allowlist-0123456789";

function req(method: string, path: string, body?: unknown, cookie?: string, headers: Record<string, string> = {}): Promise<Response> {
  const all: Record<string, string> = { ...headers };
  if (body !== undefined) all["Content-Type"] = "application/json";
  if (cookie) all.Cookie = cookie;
  return SELF.fetch(`${API}${path}`, { method, headers: all, body: body === undefined ? undefined : JSON.stringify(body) });
}

async function insertProposal(ambassadorId: string, kind: "institution" | "region", payload: object): Promise<number> {
  const row = await env.DB.prepare(
    "INSERT INTO proposals (ambassador_id, kind, payload, status, created_at) VALUES (?1, ?2, ?3, 'pending', ?4) RETURNING id",
  )
    .bind(ambassadorId, kind, JSON.stringify(payload), Date.now())
    .first<{ id: number }>();
  return row?.id ?? 0;
}

const OEHHA = { name: "OEHHA", url: "https://oehha.ca.gov/" };

function approveBody(id: number, fields: Record<string, unknown> = {}): Record<string, unknown> {
  return { type: "proposal", id, decision: "approve", ...fields };
}

const GOOD = { region: "california", domain: "oehha.ca.gov", institution_type: "government" };

describe("approving an institution proposal needs its allowlist fields", () => {
  it("refuses an approval with no region, domain or type, and leaves the proposal pending", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const applicant = await seedAmbassador({ region: "california", email: "a@berkeley.edu" });
    const id = await insertProposal(applicant.id, "institution", OEHHA);
    const res = await req("POST", "/moderation/decide", approveBody(id), owner.cookie);
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ ok: false, error: "allowlist_fields_required" });
    const row = await env.DB.prepare("SELECT status, region FROM proposals WHERE id = ?1").bind(id).first<{ status: string; region: string | null }>();
    expect(row).toEqual({ status: "pending", region: null });
  });

  it("refuses an approval that is missing any one of the three fields", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const applicant = await seedAmbassador({ region: "california", email: "a@berkeley.edu" });
    const id = await insertProposal(applicant.id, "institution", OEHHA);
    for (const missing of ["region", "domain", "institution_type"] as const) {
      const fields: Record<string, unknown> = { ...GOOD };
      delete fields[missing];
      const res = await req("POST", "/moderation/decide", approveBody(id, fields), owner.cookie);
      expect(((await res.json()) as { error: string }).error, missing).toBe("allowlist_fields_required");
      expect(res.status, missing).toBe(400);
    }
  });

  it("refuses an unknown region", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const applicant = await seedAmbassador({ region: "california", email: "a@berkeley.edu" });
    const id = await insertProposal(applicant.id, "institution", OEHHA);
    const res = await req("POST", "/moderation/decide", approveBody(id, { ...GOOD, region: "mars" }), owner.cookie);
    expect(((await res.json()) as { error: string }).error).toBe("invalid_region");
  });

  it("refuses a domain that is not a lowercase registrable host", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const applicant = await seedAmbassador({ region: "california", email: "a@berkeley.edu" });
    const id = await insertProposal(applicant.id, "institution", OEHHA);
    for (const domain of ["localhost", "OEHHA.ca.gov", "https://oehha.ca.gov", "oehha.ca.gov/path", "oehha.c", "a b.gov", "x.y.z.1"]) {
      const res = await req("POST", "/moderation/decide", approveBody(id, { ...GOOD, domain }), owner.cookie);
      expect(((await res.json()) as { error: string }).error, domain).toBe("invalid_domain");
      expect(res.status, domain).toBe(400);
    }
  });

  it("refuses a free-mail domain and any subdomain of one", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const applicant = await seedAmbassador({ region: "california", email: "a@berkeley.edu" });
    const id = await insertProposal(applicant.id, "institution", OEHHA);
    for (const domain of ["gmail.com", "mail.gmail.com", "outlook.com"]) {
      const res = await req("POST", "/moderation/decide", approveBody(id, { ...GOOD, domain }), owner.cookie);
      expect(((await res.json()) as { error: string }).error, domain).toBe("free_mail_domain");
    }
  });

  it("refuses an institution type outside the four eligible types", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const applicant = await seedAmbassador({ region: "california", email: "a@berkeley.edu" });
    const id = await insertProposal(applicant.id, "institution", OEHHA);
    const res = await req("POST", "/moderation/decide", approveBody(id, { ...GOOD, institution_type: "company" }), owner.cookie);
    expect(((await res.json()) as { error: string }).error).toBe("invalid_institution_type");
  });

  it("stores the region, domain and type on approval, and audits the region and type", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const applicant = await seedAmbassador({ region: "california", email: "a@berkeley.edu" });
    const id = await insertProposal(applicant.id, "institution", OEHHA);
    const res = await req("POST", "/moderation/decide", approveBody(id, GOOD), owner.cookie);
    expect(res.status).toBe(200);
    const row = await env.DB.prepare("SELECT status, region, domain, institution_type, decided_by FROM proposals WHERE id = ?1")
      .bind(id)
      .first();
    expect(row).toEqual({ status: "approved", region: "california", domain: "oehha.ca.gov", institution_type: "government", decided_by: owner.id });
    const audit = await env.DB.prepare("SELECT detail FROM audit_log WHERE action = 'moderation.decide' AND subject = ?1")
      .bind(owner.id)
      .first<{ detail: string }>();
    expect(JSON.parse(audit?.detail ?? "{}")).toMatchObject({ type: "proposal", id, decision: "approve", region: "california" });
  });

  it("needs no fields to reject, and stores none", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const applicant = await seedAmbassador({ region: "california", email: "a@berkeley.edu" });
    const id = await insertProposal(applicant.id, "institution", OEHHA);
    const res = await req("POST", "/moderation/decide", { type: "proposal", id, decision: "reject" }, owner.cookie);
    expect(res.status).toBe(200);
    const row = await env.DB.prepare("SELECT status, region, domain, institution_type FROM proposals WHERE id = ?1").bind(id).first();
    expect(row).toEqual({ status: "rejected", region: null, domain: null, institution_type: null });
  });

  it("does not require the fields for a region proposal", async () => {
    const owner = await seedAmbassador({ orcid: OWNER_ORCID });
    const applicant = await seedAmbassador({ region: "california", email: "a@berkeley.edu" });
    const id = await insertProposal(applicant.id, "region", { name: "Ontario" });
    const res = await req("POST", "/moderation/decide", approveBody(id), owner.cookie);
    expect(res.status).toBe(200);
  });
});

describe("the free-mail and domain helpers", () => {
  it("recognises free-mail registrable names and their subdomains only", () => {
    expect(isFreeMailDomain("gmail.com")).toBe(true);
    expect(isFreeMailDomain("x.gmail.com")).toBe(true);
    expect(isFreeMailDomain("oehha.ca.gov")).toBe(false);
    expect(isFreeMailDomain("notgmail.com")).toBe(false);
  });

  it("returns the fields when all are present and valid, and the first problem otherwise", () => {
    expect(parseAllowlistFields({ ...GOOD })).toEqual({ region: "california", domain: "oehha.ca.gov", institution_type: "government" });
    expect(parseAllowlistFields({ domain: "oehha.ca.gov" })).toEqual({ error: "allowlist_fields_required" });
    expect(parseAllowlistFields({ ...GOOD, domain: "gmail.com" })).toEqual({ error: "free_mail_domain" });
  });
});

describe("export carries approved institutions without personal data", () => {
  it("lists the approved institution with its fields, keeps the old keys, and omits the applicant", async () => {
    (env as unknown as Record<string, string>).EXPORT_TOKEN = EXPORT_TOKEN;
    try {
      const headers = { Authorization: `Bearer ${EXPORT_TOKEN}` };
      const owner = await seedAmbassador({ orcid: OWNER_ORCID });
      const applicant = await seedAmbassador({ region: "california", email: "private-applicant@berkeley.edu" });
      const id = await insertProposal(applicant.id, "institution", OEHHA);
      // A pending proposal and a rejected one must not appear.
      await insertProposal(applicant.id, "institution", { name: "Pending Lab" });
      const rejected = await insertProposal(applicant.id, "institution", { name: "Rejected Lab" });
      await req("POST", "/moderation/decide", { type: "proposal", id: rejected, decision: "reject" }, owner.cookie);
      expect((await req("POST", "/moderation/decide", approveBody(id, GOOD), owner.cookie)).status).toBe(200);

      const res = await req("GET", "/export/approved?since=0", undefined, undefined, headers);
      expect(res.status).toBe(200);
      const text = await res.text();
      const body = JSON.parse(text) as Record<string, unknown>;
      expect(Object.keys(body).sort()).toEqual(["case_answers", "generated_at", "group_pairs", "group_reviews", "institutions", "ok", "since", "submissions"]);
      expect(body.institutions).toEqual([
        {
          id,
          region: "california",
          name: "OEHHA",
          url: "https://oehha.ca.gov/",
          domain: "oehha.ca.gov",
          institution_type: "government",
          decided_at: expect.any(Number),
        },
      ]);
      expect(text).not.toContain("private-applicant");
      expect(text).not.toContain("@");
      expect(text).not.toContain(applicant.id);
      expect(text).not.toMatch(/"email|email_hash|ambassador_id|orcid|decided_by/);
    } finally {
      delete (env as unknown as Record<string, string>).EXPORT_TOKEN;
    }
  });

  it("filters institutions by since and sets url to null when the payload has none", async () => {
    (env as unknown as Record<string, string>).EXPORT_TOKEN = EXPORT_TOKEN;
    try {
      const headers = { Authorization: `Bearer ${EXPORT_TOKEN}` };
      const owner = await seedAmbassador({ orcid: OWNER_ORCID });
      const applicant = await seedAmbassador({ region: "norway", email: "n@niva.no" });
      const id = await insertProposal(applicant.id, "institution", { name: "NIVA" });
      await req("POST", "/moderation/decide", approveBody(id, { region: "norway", domain: "niva.no", institution_type: "nonprofit" }), owner.cookie);
      const later = Date.now() + 60_000;
      const none = (await (await req("GET", `/export/approved?since=${later}`, undefined, undefined, headers)).json()) as {
        institutions: unknown[];
      };
      expect(none.institutions).toEqual([]);
      const all = (await (await req("GET", "/export/approved?since=0", undefined, undefined, headers)).json()) as {
        institutions: { url: string | null }[];
      };
      expect(all.institutions).toHaveLength(1);
      expect(all.institutions[0].url).toBeNull();
    } finally {
      delete (env as unknown as Record<string, string>).EXPORT_TOKEN;
    }
  });

  it("never exports an approved institution from before the allowlist columns (no region)", async () => {
    (env as unknown as Record<string, string>).EXPORT_TOKEN = EXPORT_TOKEN;
    try {
      const headers = { Authorization: `Bearer ${EXPORT_TOKEN}` };
      const applicant = await seedAmbassador({ region: "norway", email: "old@niva.no" });
      const id = await insertProposal(applicant.id, "institution", { name: "Old Lab" });
      await env.DB.prepare("UPDATE proposals SET status = 'approved', decided_at = ?1 WHERE id = ?2").bind(Date.now(), id).run();
      const body = (await (await req("GET", "/export/approved?since=0", undefined, undefined, headers)).json()) as {
        institutions: unknown[];
      };
      expect(body.institutions).toEqual([]);
    } finally {
      delete (env as unknown as Record<string, string>).EXPORT_TOKEN;
    }
  });
});
