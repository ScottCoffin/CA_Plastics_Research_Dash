import { SELF, env } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { seedAmbassador, emailHashOf } from "./helpers";

// Case answers and consensus, submissions and their validation, and the export feed (AMB-1 slice 2b). Local D1 in
// workerd; no network.

const API = "https://api.plastiverse.live";
const CASE = "amb-0123456789ab";
const OTHER_CASE = "amb-ba9876543210";
const EXPORT_TOKEN = "test-export-token-0123456789abcdef";

function req(method: string, path: string, body?: unknown, cookie?: string, headers: Record<string, string> = {}): Promise<Response> {
  const all: Record<string, string> = { ...headers };
  if (body !== undefined) all["Content-Type"] = "application/json";
  if (cookie) all.Cookie = cookie;
  return SELF.fetch(`${API}${path}`, { method, headers: all, body: body === undefined ? undefined : JSON.stringify(body) });
}

function answer(cookie: string, caseId: string, answerValue: string, correctValue?: string): Promise<Response> {
  const body: Record<string, unknown> = { region: "norway", case_id: caseId, answer: answerValue };
  if (correctValue !== undefined) body.correct_value = correctValue;
  return req("POST", "/cases/answer", body, cookie);
}

async function members(n: number): Promise<{ id: string; cookie: string }[]> {
  const out: { id: string; cookie: string }[] = [];
  for (let i = 0; i < n; i++) out.push(await seedAmbassador({ region: "norway", email: `m${i}@niva.no` }));
  return out;
}

function submission(extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    region: "norway",
    stream: "knowledge",
    kind: "funder",
    payload: { name: "Fund for the fjords", url: "https://fund.example/programme" },
    ...extra,
  };
}

describe("case answers and consensus", () => {
  it("one answer is not consensus; the caller sees only their own answer", async () => {
    const [a, b] = await members(2);
    const res = await answer(a.cookie, CASE, "disagree", "Oslo");
    expect(res.status).toBe(200);
    expect(((await res.json()) as { consensus: unknown }).consensus).toBeNull();
    const mine = (await (await req("GET", "/cases/answers?region=norway", undefined, b.cookie)).json()) as { answers: unknown[] };
    expect(mine.answers).toHaveLength(0);
    const own = (await (await req("GET", "/cases/answers?region=norway", undefined, a.cookie)).json()) as {
      answers: { case_id: string; answer: string; correct_value: string; consensus: unknown }[];
    };
    expect(own.answers).toEqual([
      expect.objectContaining({ case_id: CASE, answer: "disagree", correct_value: "Oslo", consensus: null }),
    ]);
  });

  it("two agreeing answers are consensus, visible to the ambassadors who answered", async () => {
    const [a, b, c] = await members(3);
    await answer(a.cookie, CASE, "agree");
    const second = await answer(b.cookie, CASE, "agree");
    expect(((await second.json()) as { consensus: unknown }).consensus).toEqual({ answer: "agree", correct_value: null });
    // A third ambassador who has not answered sees their own answer only, with the consensus attached.
    const third = await answer(c.cookie, CASE, "unsure");
    expect(((await third.json()) as { consensus: unknown }).consensus).toEqual({ answer: "agree", correct_value: null });
    const list = (await (await req("GET", "/cases/answers?region=norway", undefined, c.cookie)).json()) as {
      answers: { case_id: string; consensus: unknown }[];
    };
    expect(list.answers).toEqual([expect.objectContaining({ case_id: CASE, consensus: { answer: "agree", correct_value: null } })]);
  });

  it("two disagreeing answers with the same value are consensus; different values are not", async () => {
    const [a, b, c, d] = await members(4);
    await answer(a.cookie, CASE, "disagree", "Bergen");
    await answer(b.cookie, CASE, "disagree", "Bergen");
    expect(((await (await answer(c.cookie, CASE, "unsure")).json()) as { consensus: unknown }).consensus).toEqual({
      answer: "disagree",
      correct_value: "Bergen",
    });
    await answer(d.cookie, OTHER_CASE, "disagree", "Bergen");
    const split = await answer(a.cookie, OTHER_CASE, "disagree", "Oslo");
    expect(((await split.json()) as { consensus: unknown }).consensus).toBeNull();
    const lone = await answer(b.cookie, OTHER_CASE, "agree");
    expect(((await lone.json()) as { consensus: unknown }).consensus).toBeNull();
  });

  it("'unsure' never forms consensus", async () => {
    const [a, b] = await members(2);
    await answer(a.cookie, CASE, "unsure");
    const res = await answer(b.cookie, CASE, "unsure");
    expect(((await res.json()) as { consensus: unknown }).consensus).toBeNull();
  });

  it("re-answering replaces the earlier answer (one row per ambassador and case)", async () => {
    const [a] = await members(1);
    await answer(a.cookie, CASE, "agree");
    await answer(a.cookie, CASE, "disagree", "Trondheim");
    const count = await env.DB.prepare("SELECT COUNT(*) AS n, MAX(answer) AS answer FROM case_answers WHERE ambassador_id = ?1")
      .bind(a.id)
      .first<{ n: number; answer: string }>();
    expect(count).toEqual({ n: 1, answer: "disagree" });
  });

  it("validates the case id, region, answer and correct value", async () => {
    const [a] = await members(1);
    expect((await req("POST", "/cases/answer", { region: "norway", case_id: "CASE-1", answer: "agree" }, a.cookie)).status).toBe(400);
    expect((await req("POST", "/cases/answer", { region: "atlantis", case_id: CASE, answer: "agree" }, a.cookie)).status).toBe(400);
    expect((await req("POST", "/cases/answer", { region: "norway", case_id: CASE, answer: "maybe" }, a.cookie)).status).toBe(400);
    expect((await answer(a.cookie, CASE, "disagree")).status).toBe(400);
    expect((await answer(a.cookie, CASE, "agree", "Oslo")).status).toBe(400);
    expect((await answer(a.cookie, CASE, "disagree", "<script>x</script>")).status).toBe(400);
  });

  it("refuses an ambassador who is not a member of the region, and anonymous callers", async () => {
    const outsider = await seedAmbassador({ region: "california", email: "c@berkeley.edu" });
    expect((await answer(outsider.cookie, CASE, "agree")).status).toBe(403);
    expect((await req("POST", "/cases/answer", { region: "norway", case_id: CASE, answer: "agree" })).status).toBe(401);
    expect((await req("GET", "/cases/answers?region=norway")).status).toBe(401);
  });

  it("ignores suspended ambassadors' answers when counting consensus", async () => {
    const [a, b, c] = await members(3);
    await answer(a.cookie, CASE, "agree");
    await env.DB.prepare("UPDATE ambassadors SET status = 'suspended' WHERE id = ?1").bind(a.id).run();
    await answer(b.cookie, CASE, "agree");
    const res = await answer(c.cookie, CASE, "unsure");
    expect(((await res.json()) as { consensus: unknown }).consensus).toBeNull();
  });
});

describe("submissions", () => {
  it("accepts a valid knowledge submission as pending and lists it for the submitter", async () => {
    const [a] = await members(1);
    const res = await req("POST", "/submissions", submission(), a.cookie);
    expect(res.status).toBe(201);
    const body = (await res.json()) as { id: number; status: string };
    expect(body.status).toBe("pending");
    const mine = (await (await req("GET", "/submissions/mine", undefined, a.cookie)).json()) as {
      submissions: { id: number; status: string; payload: unknown }[];
    };
    expect(mine.submissions).toEqual([
      expect.objectContaining({ id: body.id, status: "pending", payload: { name: "Fund for the fjords", url: "https://fund.example/programme" } }),
    ]);
  });

  it("accepts a confirm (stream B) item", async () => {
    const [a] = await members(1);
    const res = await req(
      "POST",
      "/submissions",
      { region: "norway", stream: "confirm", kind: "correct", payload: { item_id: "norway:funder:3", url: "https://fund.example/new" } },
      a.cookie,
    );
    expect(res.status).toBe(201);
  });

  it("refuses unknown keys, wrong types, http URLs, HTML, over-length text and missing required fields", async () => {
    const [a] = await members(1);
    const cases: [string, Record<string, unknown>, string | null][] = [
      ["unknown key", { payload: { name: "x", url: "https://a.example/", extra: "y" } }, "extra"],
      ["plain http url", { payload: { name: "x", url: "http://a.example/" } }, "url"],
      ["javascript url", { payload: { name: "x", url: "javascript:alert(1)" } }, "url"],
      ["url with credentials", { payload: { name: "x", url: "https://user:pw@a.example/" } }, "url"],
      ["html in name", { payload: { name: "<script>x</script>", url: "https://a.example/" } }, "name"],
      ["html in note", { payload: { name: "x", url: "https://a.example/", note: "<img src=x>" } }, "note"],
      ["name too long", { payload: { name: "n".repeat(201), url: "https://a.example/" } }, "name"],
      ["number value", { payload: { name: 5, url: "https://a.example/" } }, "name"],
      ["missing url", { payload: { name: "x" } }, "url"],
      ["array payload", { payload: ["x"] }, "payload"],
      ["control character", { payload: { name: "a\u0007b", url: "https://a.example/" } }, "name"],
    ];
    for (const [label, change, field] of cases) {
      const res = await req("POST", "/submissions", submission(change), a.cookie);
      expect(res.status, label).toBe(400);
      const body = (await res.json()) as { error: string; field?: string };
      expect(body.error, label).toBe("invalid_payload");
      if (field) expect(body.field, label).toBe(field);
    }
  });

  it("refuses a stream and kind that do not match, and unknown kinds", async () => {
    const [a] = await members(1);
    expect((await req("POST", "/submissions", submission({ stream: "confirm" }), a.cookie)).status).toBe(400);
    expect((await req("POST", "/submissions", submission({ kind: "toString" }), a.cookie)).status).toBe(400);
    expect((await req("POST", "/submissions", submission({ kind: "nonsense" }), a.cookie)).status).toBe(400);
  });

  it("refuses non-members and anonymous callers", async () => {
    const outsider = await seedAmbassador({ region: "california", email: "c@berkeley.edu" });
    expect((await req("POST", "/submissions", submission(), outsider.cookie)).status).toBe(403);
    expect((await req("POST", "/submissions", submission())).status).toBe(401);
  });

  it("stores only the fields of the kind, and rate-limits per account", async () => {
    const [a] = await members(1);
    await req("POST", "/submissions", submission({ payload: { name: "Fund", url: "https://fund.example/", note: "ok" } }), a.cookie);
    const row = await env.DB.prepare("SELECT payload FROM submissions WHERE ambassador_id = ?1").bind(a.id).first<{ payload: string }>();
    expect(JSON.parse(row?.payload ?? "{}")).toEqual({ name: "Fund", url: "https://fund.example/", note: "ok" });
    let last = 0;
    for (let i = 0; i < 40; i++) {
      last = (await req("POST", "/submissions", submission(), a.cookie)).status;
      if (last === 429) break;
    }
    expect(last).toBe(429);
  });
});

describe("export feed", () => {
  it("refuses a missing, wrong or unconfigured token with 401", async () => {
    expect((await req("GET", "/export/approved")).status).toBe(401);
    expect((await req("GET", "/export/approved", undefined, undefined, { Authorization: "Bearer wrong-token" })).status).toBe(401);
    expect((await req("GET", "/export/approved", undefined, undefined, { Authorization: "Basic abc" })).status).toBe(401);
    expect((await req("POST", "/export/approved", undefined, undefined, { Authorization: `Bearer ${EXPORT_TOKEN}` })).status).toBe(405);
  });

  it("returns approved submissions and consensus answers with the right token, and no email or hash", async () => {
    // The test environment has no EXPORT_TOKEN binding by default; set it for this test only.
    (env as unknown as Record<string, string>).EXPORT_TOKEN = EXPORT_TOKEN;
    try {
      const [a, b, c] = await members(3);
      const email = "m0@niva.no";
      const sub = await req("POST", "/submissions", submission(), a.cookie);
      const { id } = (await sub.json()) as { id: number };
      await env.DB.prepare("UPDATE submissions SET status = 'approved', decided_at = ?1, decided_by = ?2 WHERE id = ?3")
        .bind(Date.now(), c.id, id)
        .run();
      await answer(a.cookie, CASE, "agree");
      await answer(b.cookie, CASE, "agree");
      await answer(c.cookie, OTHER_CASE, "unsure");

      const res = await req("GET", "/export/approved?since=0", undefined, undefined, { Authorization: `Bearer ${EXPORT_TOKEN}` });
      expect(res.status).toBe(200);
      const text = await res.text();
      const body = JSON.parse(text) as {
        submissions: { id: number; payload: unknown }[];
        case_answers: { case_id: string; answer: string }[];
      };
      expect(body.submissions).toHaveLength(1);
      expect(body.submissions[0].payload).toEqual({ name: "Fund for the fjords", url: "https://fund.example/programme" });
      expect(body.case_answers).toEqual([expect.objectContaining({ region: "norway", case_id: CASE, answer: "agree" })]);
      expect(text).not.toContain(email);
      expect(text).not.toContain(await emailHashOf(email));
      expect(text).not.toMatch(/"email|email_hash|ambassador_id|orcid/);
      expect(text).not.toContain("@");
    } finally {
      delete (env as unknown as Record<string, string>).EXPORT_TOKEN;
    }
  });

  it("validates since", async () => {
    (env as unknown as Record<string, string>).EXPORT_TOKEN = EXPORT_TOKEN;
    try {
      const headers = { Authorization: `Bearer ${EXPORT_TOKEN}` };
      expect((await req("GET", "/export/approved?since=yesterday", undefined, undefined, headers)).status).toBe(400);
      expect((await req("GET", "/export/approved?since=-5", undefined, undefined, headers)).status).toBe(400);
    } finally {
      delete (env as unknown as Record<string, string>).EXPORT_TOKEN;
    }
  });
});
