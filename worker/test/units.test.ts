import { describe, expect, it } from "vitest";
import { requireSecret } from "../src/env";
import { institutionName, matchInstitution } from "../src/eligibility";
import { ResendSender, chooseSender } from "../src/mail";
import { randomToken } from "../src/crypto";

describe("eligibility allowlists", () => {
  it("matches a registrable domain and its subdomains", () => {
    expect(matchInstitution("norway", "niva.no")?.domain).toBe("niva.no");
    expect(matchInstitution("norway", "bio.uio.no")?.domain).toBe("uio.no");
    expect(matchInstitution("norway", "NIVA.NO")?.domain).toBe("niva.no");
  });

  it("does not match a sibling that merely ends with the same letters", () => {
    expect(matchInstitution("norway", "notniva.no")).toBeNull();
    expect(matchInstitution("norway", "niva.no.attacker.example")).toBeNull();
  });

  it("refuses free-mail even when it appears inside a longer name", () => {
    expect(matchInstitution("norway", "gmail.com")).toBeNull();
    expect(matchInstitution("california", "ucdavis.edu.gmail.com")).toBeNull();
  });

  it("resolves institution names from the bundled allowlist", () => {
    const hit = matchInstitution("norway", "niva.no");
    expect(hit && institutionName("norway", hit.institutionId)).toBe(hit?.institutionName);
    expect(institutionName("norway", "I-does-not-exist")).toBeNull();
  });
});

describe("secrets and mail", () => {
  it("fails closed when a secret is missing", () => {
    expect(() => requireSecret(undefined, "RESEND_API_KEY")).toThrow(/RESEND_API_KEY/);
    expect(() => requireSecret("", "SESSION_SIGNING_KEY")).toThrow();
  });

  it("uses Resend with a bearer key when not in outbox mode", async () => {
    const calls: { url: string; auth: string | null; body: unknown }[] = [];
    const fake = (async (url: string, init: RequestInit) => {
      calls.push({
        url,
        auth: new Headers(init.headers).get("Authorization"),
        body: JSON.parse(String(init.body)),
      });
      return new Response("{}", { status: 200 });
    }) as typeof fetch;
    await new ResendSender("re_test_key", "Plastiverse <auth@plastiverse.live>", fake).send({
      to: "x@niva.no",
      subject: "s",
      text: "t",
    });
    expect(calls[0].url).toBe("https://api.resend.com/emails");
    expect(calls[0].auth).toBe("Bearer re_test_key");
    expect(calls[0].body).toMatchObject({ to: ["x@niva.no"], from: "Plastiverse <auth@plastiverse.live>" });
  });

  it("throws (so the caller logs and answers generically) when Resend refuses", async () => {
    const fake = (async () => new Response("no", { status: 500 })) as typeof fetch;
    await expect(new ResendSender("k", "f", fake).send({ to: "a@b.no", subject: "s", text: "t" })).rejects.toThrow(
      /500/,
    );
  });

  it("chooses Resend by default and refuses to start without its key", () => {
    expect(() => chooseSender({ MAIL_MODE: "resend" } as never)).toThrow(/RESEND_API_KEY/);
  });
});

describe("tokens", () => {
  it("produces 43-character url-safe random tokens", () => {
    const a = randomToken();
    expect(a).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(randomToken()).not.toBe(a);
  });
});
