import type { Fetch } from "./outbound";

// ORCID public iD: 4 groups of 4 characters, last character may be X (ISO 7064 check digit).
export const ORCID_RE = /^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$/;
const ORCID_HEADERS = { Accept: "application/json" };

export interface Employment {
  orgName: string;
  /** Normalised ROR URL (https://ror.org/<id>) when the public record gives one. */
  ror: string | null;
  country: string | null;
  startYear: number | null;
  endYear: number | null;
}

/** ORCID OAuth authorize URL (scope /authenticate proves the iD). */
export function orcidAuthorizeUrl(clientId: string, redirectUri: string, state: string): string {
  const url = new URL("https://orcid.org/oauth/authorize");
  url.searchParams.set("client_id", clientId);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", "/authenticate");
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("state", state);
  return url.toString();
}

/** Exchanges the authorization code. The access token is discarded; only the verified iD is kept. */
export async function exchangeOrcidCode(
  fetchImpl: Fetch,
  clientId: string,
  clientSecret: string,
  code: string,
  redirectUri: string,
): Promise<string> {
  const form = new URLSearchParams({
    client_id: clientId,
    client_secret: clientSecret,
    grant_type: "authorization_code",
    code,
    redirect_uri: redirectUri,
  });
  const res = await fetchImpl("https://orcid.org/oauth/token", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });
  if (!res.ok) throw new Error(`orcid token responded ${res.status}`);
  const data = (await res.json()) as { orcid?: unknown };
  if (typeof data.orcid !== "string" || !ORCID_RE.test(data.orcid)) throw new Error("orcid token without iD");
  return data.orcid;
}

function yearOf(value: unknown): number | null {
  const raw = (value as { year?: { value?: unknown } } | null | undefined)?.year?.value;
  const n = Number(raw);
  return Number.isInteger(n) && n >= 1900 && n <= 2100 ? n : null;
}

/** Short ROR URL form (https://ror.org/<id>) or null. */
export function normaliseRor(value: string): string | null {
  const match = value.trim().match(/(?:ror\.org\/)?(0[a-hj-km-np-tv-z0-9]{6}\d{2})$/i);
  return match ? `https://ror.org/${match[1].toLowerCase()}` : null;
}

/**
 * Public employments (pub.orcid.org v3.0, JSON). A 404 is "no employments". Any other failure throws, so the
 * caller can say the list is unavailable instead of showing an empty one.
 */
export async function fetchEmployments(fetchImpl: Fetch, orcid: string): Promise<Employment[]> {
  const res = await fetchImpl(`https://pub.orcid.org/v3.0/${orcid}/employments`, { headers: ORCID_HEADERS });
  if (res.status === 404) return [];
  if (!res.ok) throw new Error(`orcid employments responded ${res.status}`);
  const data = (await res.json()) as {
    "affiliation-group"?: { summaries?: { "employment-summary"?: Record<string, unknown> }[] }[];
  };
  const out: Employment[] = [];
  for (const group of data["affiliation-group"] ?? []) {
    for (const summary of group.summaries ?? []) {
      const e = summary["employment-summary"] as
        | {
            organization?: {
              name?: unknown;
              address?: { country?: unknown };
              "disambiguated-organization"?: {
                "disambiguated-organization-identifier"?: unknown;
                "disambiguation-source"?: unknown;
              } | null;
            };
            "start-date"?: unknown;
            "end-date"?: unknown;
          }
        | undefined;
      const org = e?.organization;
      if (!org || typeof org.name !== "string" || org.name.trim() === "") continue;
      const disamb = org["disambiguated-organization"];
      const ror =
        disamb?.["disambiguation-source"] === "ROR" && typeof disamb["disambiguated-organization-identifier"] === "string"
          ? normaliseRor(disamb["disambiguated-organization-identifier"])
          : null;
      const country = typeof org.address?.country === "string" ? org.address.country : null;
      out.push({
        orgName: org.name.trim().slice(0, 200),
        ror,
        country,
        startYear: yearOf(e?.["start-date"]),
        endYear: yearOf(e?.["end-date"]),
      });
    }
  }
  return out.slice(0, 100);
}
