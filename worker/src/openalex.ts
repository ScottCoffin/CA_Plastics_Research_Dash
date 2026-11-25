import type { Fetch } from "./outbound";

export interface AffiliationYears {
  from: number | null;
  to: number | null;
}

export interface OpenAlexInstitution {
  /** Short OpenAlex institution id (I<digits>). */
  id: string;
  name: string;
  country: string | null;
  type: string | null;
  years: AffiliationYears | null;
}

export interface OpenAlexAuthor {
  /** Short OpenAlex author id (A<digits>). */
  id: string;
  name: string;
  /** Authorship affiliations (with years), then last-known institutions (no years). Current or past all count. */
  institutions: OpenAlexInstitution[];
}

const USER_AGENT = "PlastiverseLive-Ambassadors";

const AUTHOR_ID = /^(?:https?:\/\/openalex\.org\/)?(A\d+)$/;
const INSTITUTION_ID = /^(?:https?:\/\/openalex\.org\/)?(I\d+)$/;

/** Short OpenAlex id (A<digits> or I<digits>) from a short or openalex.org URL form, or null. */
function shortId(value: unknown, prefix: "I" | "A"): string | null {
  if (typeof value !== "string") return null;
  const match = value.match(prefix === "A" ? AUTHOR_ID : INSTITUTION_ID);
  return match ? match[1] : null;
}

function text(value: unknown, max = 200): string {
  return typeof value === "string" ? value.slice(0, max) : "";
}

interface RawInstitution {
  id?: unknown;
  display_name?: unknown;
  country_code?: unknown;
  type?: unknown;
}

function toInstitution(raw: RawInstitution | undefined, years: AffiliationYears | null): OpenAlexInstitution | null {
  const id = shortId(raw?.id, "I");
  if (!id) return null;
  return {
    id,
    name: text(raw?.display_name) || id,
    country: typeof raw?.country_code === "string" ? raw.country_code : null,
    type: typeof raw?.type === "string" ? raw.type : null,
    years,
  };
}

/**
 * OpenAlex singleton lookup by ORCID (no key; polite User-Agent). Returns null when OpenAlex has no author for the
 * iD (404). Any other failure throws.
 */
export async function fetchAuthorByOrcid(fetchImpl: Fetch, orcid: string): Promise<OpenAlexAuthor | null> {
  const res = await fetchImpl(`https://api.openalex.org/authors/orcid:${orcid}`, {
    headers: { Accept: "application/json", "User-Agent": USER_AGENT },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`openalex responded ${res.status}`);
  const data = (await res.json()) as {
    id?: unknown;
    display_name?: unknown;
    affiliations?: { institution?: RawInstitution; years?: unknown }[];
    last_known_institutions?: RawInstitution[];
  };
  const id = shortId(data.id, "A");
  if (!id) return null;
  const institutions: OpenAlexInstitution[] = [];
  for (const aff of data.affiliations ?? []) {
    const years = Array.isArray(aff.years)
      ? aff.years.filter((y): y is number => Number.isInteger(y))
      : [];
    const range = years.length > 0 ? { from: Math.min(...years), to: Math.max(...years) } : null;
    const inst = toInstitution(aff.institution, range);
    if (inst) institutions.push(inst);
  }
  for (const raw of data.last_known_institutions ?? []) {
    const inst = toInstitution(raw, null);
    if (inst) institutions.push(inst);
  }
  return { id, name: text(data.display_name) || id, institutions: institutions.slice(0, 200) };
}
