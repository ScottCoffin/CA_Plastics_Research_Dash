import { SELF, env } from "cloudflare:test";
import { describe, expect, it } from "vitest";
import { keyedHash, sha256Hex } from "../src/crypto";
import norway from "../../site/data/norway/ambassador_institutions.json";
import { latestToken, network, outboxCount } from "./helpers";

// ORCID-first sign-up (AMB-1 slice 2a). ORCID, OpenAlex and Turnstile are answered by the fake network in
// helpers.ts; any other outbound request throws.

const API = "https://api.plastiverse.live";
const WORKSPACE = "https://plastiverse.live/ambassadors";
const SIGNUP = "__Host-plastiverse_signup";
const NONCE = "__Host-plastiverse_orcid";
const SESSION = "__Host-plastiverse_session";
const ORCID = "0000-0002-1825-0097";
const OTHER_ORCID = "0000-0001-5109-3700";

// Real allowlist ids (norway amb-v1): NIVA (nonprofit, niva.no), NTNU (education, ntnu.no).
const NIVA = "I2802939387";
const NTNU = "I204778367";
const UNLISTED = "I9000000001";

const AUTHOR = {
  id: "https://openalex.org/A5000000001",
  display_name: "Ana Test",
  affiliations: [
    {
      institution: { id: `https://openalex.org/${NIVA}`, display_name: "NIVA", country_code: "NO", type: "nonprofit" },
      years: [2019, 2020, 2021],
    },
    {
      institution: { id: `https://openalex.org/${NTNU}`, display_name: "NTNU", country_code: "NO", type: "education" },
      years: [2009, 2012],
    },
    {
      institution: { id: `https://openalex.org/${UNLISTED}`, display_name: "Unlisted Lab", country_code: "US", type: "company" },
      years: [2022],
    },
  ],
  last_known_institutions: [
    { id: `https://openalex.org/${NIVA}`, display_name: "NIVA", country_code: "NO", type: "nonprofit" },
  ],
};

// ORCID employments answer with one organisation. A null ror means no disambiguated organisation.
function employmentAt(ror: string | null, orgName = "Some Institute") {
  return {
    "affiliation-group": [
      {
        summaries: [
          {
            "employment-summary": {
              organization: {
                name: orgName,
                address: { country: "US" },
                "disambiguated-organization": ror
                  ? { "disambiguated-organization-identifier": ror, "disambiguation-source": "ROR" }
                  : null,
              },
              "start-date": { year: { value: "2015" } },
              "end-date": null,
            },
          },
        ],
      },
    ],
  };
}

// Not on any allowlist (checked by the unmapped-ROR test below).
const ROR_EMPLOYMENT = employmentAt("https://ror.org/03yrm5c26");
// The first norway allowlist entry (it carries a ROR URL).
const LISTED_WITH_ROR = norway.institutions.find((inst) => inst.ror);

function pair(res: Response, name: string): string {
  const raw = res.headers.getSetCookie().find((c) => c.startsWith(`${name}=`));
  if (!raw) throw new Error(`no ${name} cookie`);
  return raw.split(";")[0];
}

function hasCookie(res: Response, name: string): boolean {
  return res.headers.getSetCookie().some((c) => c.startsWith(`${name}=`));
}

function location(res: Response): URL {
  return new URL(res.headers.get("Location") ?? "https://invalid.example/");
}

async function startOrcid(): Promise<{ state: string; nonce: string }> {
  const res = await SELF.fetch(`${API}/orcid/start`, { redirect: "manual" });
  if (res.status !== 302) throw new Error(`orcid start ${res.status}`);
  return { state: location(res).searchParams.get("state") ?? "", nonce: pair(res, NONCE) };
}

function callback(state: string, cookie?: string): Promise<Response> {
  const url = new URL(`${API}/orcid/callback`);
  url.searchParams.set("code", "test-code");
  url.searchParams.set("state", state);
  return SELF.fetch(url, { redirect: "manual", headers: cookie ? { Cookie: cookie } : {} });
}

/** ORCID sign-up up to the signup cookie. */
async function orcidSignUp(): Promise<string> {
  const { state, nonce } = await startOrcid();
  const res = await callback(state, nonce);
  if (res.status !== 302) throw new Error(`callback ${res.status}`);
  return pair(res, SIGNUP);
}

function send(method: string, path: string, body?: unknown, cookie?: string): Promise<Response> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (cookie) headers.Cookie = cookie;
  return SELF.fetch(`${API}${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
}

function claim(signup: string, institutions: string[], regions: string[], proposals: unknown[] = []): Promise<Response> {
  return send("POST", "/signup/claims", { institutions, regions, proposals }, signup);
}

function emailProof(signup: string, email: string, turnstileToken = "good-token"): Promise<Response> {
  return send("POST", "/signup/email", { email, turnstileToken }, signup);
}

async function verifyLatestLink(): Promise<Response> {
  return SELF.fetch(`${API}/auth/verify?token=${await latestToken()}`, { redirect: "manual" });
}

/** The whole flow for one institutional address. Returns the session cookie pair. */
async function fullSignUp(email = "ana.test@niva.no", institutions = [NIVA], regions = ["norway"]): Promise<string> {
  network.openalex = { status: 200, body: AUTHOR };
  const signup = await orcidSignUp();
  expect((await send("GET", "/signup/profile", undefined, signup)).status).toBe(200);
  expect((await claim(signup, institutions, regions)).status).toBe(200);
  expect((await emailProof(signup, email)).status).toBe(200);
  const res = await verifyLatestLink();
  expect(res.status).toBe(302);
  return pair(res, SESSION);
}

describe("ORCID start and callback", () => {
  it("redirects to ORCID /authenticate with the registered redirect URI, storing only the state hash", async () => {
    const res = await SELF.fetch(`${API}/orcid/start`, { redirect: "manual" });
    expect(res.status).toBe(302);
    const to = location(res);
    expect(`${to.origin}${to.pathname}`).toBe("https://orcid.org/oauth/authorize");
    expect(to.searchParams.get("scope")).toBe("/authenticate");
    expect(to.searchParams.get("response_type")).toBe("code");
    expect(to.searchParams.get("client_id")).toBe("APP-TEST-0000000000");
    expect(to.searchParams.get("redirect_uri")).toBe("https://api.plastiverse.live/orcid/callback");
    const state = to.searchParams.get("state") ?? "";
    expect(state).toMatch(/^[A-Za-z0-9_-]{43}$/);
    const row = await env.DB.prepare("SELECT state_hash FROM orcid_states").first<{ state_hash: string }>();
    expect(row?.state_hash).toBe(await sha256Hex(state));
    expect(res.headers.get("Set-Cookie")).toContain("HttpOnly; Secure; SameSite=Lax");
  });

  it("exchanges the code with the client secret and the same redirect URI, then opens a pending signup", async () => {
    const { state, nonce } = await startOrcid();
    const res = await callback(state, nonce);
    expect(location(res).searchParams.get("signup")).toBe("orcid");
    expect(location(res).origin + location(res).pathname).toBe(WORKSPACE);
    const form = network.orcidTokenForms[0];
    expect(form.get("client_secret")).toBe("test-orcid-client-secret");
    expect(form.get("redirect_uri")).toBe("https://api.plastiverse.live/orcid/callback");
    expect(form.get("grant_type")).toBe("authorization_code");
    const row = await env.DB.prepare("SELECT orcid, status, email FROM ambassadors").first<{ orcid: string; status: string; email: string | null }>();
    expect(row).toEqual({ orcid: ORCID, status: "pending", email: null });
  });

  it("refuses a state that does not match (no signup cookie, no token exchange)", async () => {
    const { nonce } = await startOrcid();
    const res = await callback("A".repeat(43), nonce);
    expect(location(res).searchParams.get("signin")).toBe("failed");
    expect(hasCookie(res, SIGNUP)).toBe(false);
    expect(network.orcidTokenForms).toHaveLength(0);
  });

  it("refuses a callback without the browser nonce cookie", async () => {
    const { state } = await startOrcid();
    const res = await callback(state);
    expect(location(res).searchParams.get("signin")).toBe("failed");
    expect(network.orcidTokenForms).toHaveLength(0);
  });

  it("accepts each state once", async () => {
    const { state, nonce } = await startOrcid();
    expect(location(await callback(state, nonce)).searchParams.get("signup")).toBe("orcid");
    expect(location(await callback(state, nonce)).searchParams.get("signin")).toBe("failed");
  });

  it("refuses when ORCID does not verify the code", async () => {
    network.orcidId = null;
    const { state, nonce } = await startOrcid();
    const res = await callback(state, nonce);
    expect(location(res).searchParams.get("signin")).toBe("failed");
    expect(hasCookie(res, SIGNUP)).toBe(false);
  });
});

describe("author lookup and claims", () => {
  it("lists the affiliation history with eligibility, regions and years (past affiliations count)", async () => {
    network.openalex = { status: 200, body: AUTHOR };
    const signup = await orcidSignUp();
    const res = await send("GET", "/signup/profile", undefined, signup);
    expect(res.status).toBe(200);
    const body = (await res.json()) as {
      author: { id: string } | null;
      institutions: { id: string; eligible: boolean; regions: string[]; years: unknown; source: string }[];
    };
    expect(body.author?.id).toBe("A5000000001");
    expect(network.openalexUserAgents[0]).toBe("PlastiverseLive-Ambassadors");
    const byId = new Map(body.institutions.map((i) => [i.id, i]));
    expect(byId.get(NIVA)).toMatchObject({ eligible: true, regions: ["norway"], years: { from: 2019, to: 2021 }, source: "openalex_history" });
    expect(byId.get(NTNU)).toMatchObject({ eligible: true, regions: ["norway"], years: { from: 2009, to: 2012 } });
    expect(byId.get(UNLISTED)).toMatchObject({ eligible: false, regions: [] });
  });

  it("shows an ORCID employment with an unmapped ROR as ineligible, and tolerates an employments outage", async () => {
    network.employments = { status: 200, body: ROR_EMPLOYMENT };
    const signup = await orcidSignUp();
    const body = (await (await send("GET", "/signup/profile", undefined, signup)).json()) as {
      author: unknown;
      institutions: { id: string; eligible: boolean; source: string }[];
    };
    expect(body.author).toBeNull();
    expect(body.institutions).toEqual([
      expect.objectContaining({ id: "ror:https://ror.org/03yrm5c26", eligible: false, source: "orcid_employment" }),
    ]);
    network.employments = { status: 500, body: {} };
    const again = await send("GET", "/signup/profile", undefined, signup);
    expect(again.status).toBe(200);
    expect(await again.json()).toMatchObject({ employments_checked: false });
  });

  it("maps an ORCID employment through its ROR to an eligible allowlisted institution", async () => {
    expect(LISTED_WITH_ROR?.ror).toMatch(/^https:\/\/ror\.org\/0[a-z0-9]{8}$/);
    network.employments = { status: 200, body: employmentAt(LISTED_WITH_ROR!.ror, LISTED_WITH_ROR!.name) };
    const signup = await orcidSignUp();
    const body = (await (await send("GET", "/signup/profile", undefined, signup)).json()) as {
      institutions: { id: string; name: string; eligible: boolean; regions: string[]; source: string }[];
    };
    expect(body.institutions).toEqual([
      expect.objectContaining({
        id: LISTED_WITH_ROR!.id,
        name: LISTED_WITH_ROR!.name,
        eligible: true,
        regions: expect.arrayContaining(["norway"]),
        source: "orcid_employment",
      }),
    ]);
  });

  it("an employment without a ROR is never matched to an allowlisted institution by name", async () => {
    // Every current allowlist entry carries a ror, so a null-ror entry cannot be bundled; this checks
    // the no-ROR path that a null-ror entry would take (matching by organisation name is not done).
    network.employments = { status: 200, body: employmentAt(null, LISTED_WITH_ROR!.name) };
    const signup = await orcidSignUp();
    const body = (await (await send("GET", "/signup/profile", undefined, signup)).json()) as {
      institutions: { id: string; eligible: boolean; source: string }[];
    };
    expect(body.institutions).toEqual([
      expect.objectContaining({ id: `name:${LISTED_WITH_ROR!.name}`, eligible: false, source: "orcid_employment" }),
    ]);
  });

  it("with no OpenAlex author: empty checklist, proposal path, proposals stored pending and replaced", async () => {
    const signup = await orcidSignUp();
    const body = (await (await send("GET", "/signup/profile", undefined, signup)).json()) as {
      author: unknown;
      institutions: unknown[];
      message?: string;
    };
    expect(body.author).toBeNull();
    expect(body.institutions).toEqual([]);
    expect(body.message).toContain("Propose");

    const first = await claim(signup, [], [], [{ kind: "institution", payload: { name: "First lab" } }]);
    expect(await first.json()).toMatchObject({ ok: true, status: "proposals_only" });
    await claim(signup, [], [], [{ kind: "region", payload: { name: "Second region" } }]);
    const rows = await env.DB.prepare("SELECT kind, payload, status FROM proposals").all<{ kind: string; payload: string; status: string }>();
    expect(rows.results).toHaveLength(1);
    expect(rows.results[0]).toMatchObject({ kind: "region", status: "pending" });
    expect(rows.results[0].payload).toContain("Second region");

    // Proposals do not make an email step possible.
    expect((await emailProof(signup, "ana.test@niva.no")).status).toBe(409);
    expect(await outboxCount()).toBe(0);
  });

  it("refuses an institution that is not on the checklist", async () => {
    network.openalex = { status: 200, body: AUTHOR };
    const signup = await orcidSignUp();
    await send("GET", "/signup/profile", undefined, signup);
    const res = await claim(signup, ["I1"], ["norway"]);
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ ok: false, error: "unknown_institution" });
  });

  it("refuses claims when only ineligible institutions are ticked and no proposal is made", async () => {
    network.openalex = { status: 200, body: AUTHOR };
    const signup = await orcidSignUp();
    await send("GET", "/signup/profile", undefined, signup);
    const res = await claim(signup, [UNLISTED], []);
    expect(await res.json()).toEqual({ ok: false, error: "no_eligible_institution" });
  });

  it("refuses a region that no claimed eligible institution ties to", async () => {
    network.openalex = { status: 200, body: AUTHOR };
    const signup = await orcidSignUp();
    await send("GET", "/signup/profile", undefined, signup);
    const res = await claim(signup, [NIVA], ["california"]);
    expect(await res.json()).toEqual({ ok: false, error: "region_not_tied" });
  });

  it("requires the lookup before claims (409)", async () => {
    const signup = await orcidSignUp();
    expect((await claim(signup, [NIVA], ["norway"])).status).toBe(409);
  });

  it("returns 502 and stores nothing when OpenAlex fails", async () => {
    network.openalex = { status: 500, body: {} };
    const signup = await orcidSignUp();
    const res = await send("GET", "/signup/profile", undefined, signup);
    expect(res.status).toBe(502);
    expect(await res.json()).toEqual({ ok: false, error: "lookup_failed" });
    const row = await env.DB.prepare("SELECT checklist_json FROM ambassadors").first<{ checklist_json: string | null }>();
    expect(row?.checklist_json).toBeNull();
  });
});

describe("email proof, activation and profile", () => {
  it("full happy path: ORCID, checklist, claims, one institutional email, verify, then profile and consent", async () => {
    network.openalex = { status: 200, body: AUTHOR };
    const signup = await orcidSignUp();
    await send("GET", "/signup/profile", undefined, signup);
    expect(await (await claim(signup, [NIVA, NTNU], ["norway"])).json()).toMatchObject({ ok: true, status: "pending_email", eligible: 2 });
    expect((await emailProof(signup, "Ana.Test@niva.no ")).status).toBe(200);
    expect(await outboxCount()).toBe(1);

    const verified = await verifyLatestLink();
    expect(verified.status).toBe(302);
    expect(location(verified).searchParams.get("signin")).toBeNull();
    const session = pair(verified, SESSION);

    const me = (await (await send("GET", "/me", undefined, session)).json()) as {
      ambassador: {
        orcid: string;
        author_id: string;
        email_masked: string;
        regions: { region: string; status: string }[];
        institutions: { id: string; eligible: boolean }[];
        needs_profile: boolean;
        public_credit: boolean;
      };
    };
    expect(me.ambassador).toMatchObject({
      orcid: ORCID,
      author_id: "A5000000001",
      email_masked: "a***@niva.no",
      regions: [{ region: "norway", status: "active" }],
      needs_profile: true,
    });
    expect(me.ambassador.institutions.map((i) => i.id).sort()).toEqual([NIVA, NTNU].sort());
    expect(me.ambassador.public_credit).toBe(true);

    const saved = await send("POST", "/signup/profile", { display_name: "Ana Test", accept_terms_version: "v1" }, session);
    expect(saved.status).toBe(200);
    const after = (await (await send("GET", "/me", undefined, session)).json()) as {
      ambassador: { consent_given: boolean; needs_profile: boolean; public_credit: boolean; display_name: string };
    };
    expect(after.ambassador).toMatchObject({ consent_given: true, needs_profile: false, public_credit: true, display_name: "Ana Test" });
  });

  it("stores hashes only: email keyed, link token and session id hashed, link email cleared, signup session ended", async () => {
    const session = await fullSignUp();
    const ambassador = await env.DB.prepare("SELECT email_hash, email, status FROM ambassadors").first<{
      email_hash: string;
      email: string;
      status: string;
    }>();
    expect(ambassador?.email_hash).toBe(await keyedHash(env.EMAIL_HASH_KEY as string, "email", "ana.test@niva.no"));
    expect(ambassador?.email).toBe("ana.test@niva.no");
    expect(ambassador?.status).toBe("active");
    const link = await env.DB.prepare("SELECT token_hash, email, used_at FROM magic_links").first<{
      token_hash: string;
      email: string | null;
      used_at: number | null;
    }>();
    expect(link?.email).toBeNull();
    expect(link?.used_at).not.toBeNull();
    expect(link?.token_hash).toMatch(/^[0-9a-f]{64}$/);
    const sessionId = session.slice(session.indexOf("=") + 1);
    const idOnly = sessionId.slice(0, sessionId.lastIndexOf("."));
    const stored = await env.DB.prepare("SELECT id_hash FROM sessions").first<{ id_hash: string }>();
    expect(stored?.id_hash).toBe(await sha256Hex(idOnly));
    expect(stored?.id_hash).not.toBe(idOnly);
    expect((await env.DB.prepare("SELECT COUNT(*) AS n FROM signup_sessions").first<{ n: number }>())?.n).toBe(0);
  });

  it("refuses an email at a domain that was not claimed, and sends nothing", async () => {
    network.openalex = { status: 200, body: AUTHOR };
    const signup = await orcidSignUp();
    await send("GET", "/signup/profile", undefined, signup);
    expect((await claim(signup, [NIVA], ["norway"])).status).toBe(200);
    const res = await emailProof(signup, "ana@ntnu.no");
    expect(res.status).toBe(400);
    expect(await res.json()).toEqual({ ok: false, error: "domain_not_claimed" });
    expect(await outboxCount()).toBe(0);
  });

  it("a past affiliation can be the confirmed institution", async () => {
    network.openalex = { status: 200, body: AUTHOR };
    const session = await fullSignUp("ana@ntnu.no", [NTNU], ["norway"]);
    const me = (await (await send("GET", "/me", undefined, session)).json()) as {
      ambassador: { institutions: { id: string; source: string }[] };
    };
    expect(me.ambassador.institutions).toEqual([expect.objectContaining({ id: NTNU, source: "openalex_history" })]);
  });

  it("the confirmation link works once", async () => {
    await fullSignUp();
    const again = await verifyLatestLink();
    expect(location(again).searchParams.get("signin")).toBe("failed");
  });

  it("refuses the email step when the bot check fails, and sends nothing", async () => {
    network.openalex = { status: 200, body: AUTHOR };
    network.turnstileSuccess = false;
    const signup = await orcidSignUp();
    await send("GET", "/signup/profile", undefined, signup);
    await claim(signup, [NIVA], ["norway"]);
    const res = await emailProof(signup, "ana.test@niva.no");
    expect(res.status).toBe(403);
    expect(await outboxCount()).toBe(0);
  });

  it("an address already used by another ambassador does not activate a second account", async () => {
    await fullSignUp();
    network.orcidId = OTHER_ORCID;
    network.openalex = { status: 200, body: AUTHOR };
    const second = await orcidSignUp();
    await send("GET", "/signup/profile", undefined, second);
    await claim(second, [NIVA], ["norway"]);
    expect((await emailProof(second, "ana.test@niva.no")).status).toBe(200);
    const res = await verifyLatestLink();
    expect(location(res).searchParams.get("signin")).toBe("failed");
    expect(hasCookie(res, SESSION)).toBe(false);
  });

  it("profile and consent: terms v1 required, credit on by default, opt-out honoured", async () => {
    const session = await fullSignUp();
    const wrongTerms = await send("POST", "/signup/profile", { display_name: "Ana", accept_terms_version: "v2" }, session);
    expect(await wrongTerms.json()).toEqual({ ok: false, error: "terms_version_required" });
    const blankName = await send("POST", "/signup/profile", { display_name: "  ", accept_terms_version: "v1" }, session);
    expect(blankName.status).toBe(400);
    const optOut = await send("POST", "/signup/profile", { display_name: "Ana", credit_public: false, accept_terms_version: "v1" }, session);
    expect(optOut.status).toBe(200);
    const me = (await (await send("GET", "/me", undefined, session)).json()) as { ambassador: { public_credit: boolean } };
    expect(me.ambassador.public_credit).toBe(false);
    const row = await env.DB.prepare("SELECT terms_version FROM ambassadors").first<{ terms_version: string }>();
    expect(row?.terms_version).toBe("v1");
  });

  it("the profile is refused before the email proof (signup cookie is not a session)", async () => {
    const signup = await orcidSignUp();
    const res = await send("POST", "/signup/profile", { display_name: "Ana", accept_terms_version: "v1" }, signup);
    expect(res.status).toBe(401);
  });
});
