import california from "../../site/data/california/ambassador_institutions.json";
import norway from "../../site/data/norway/ambassador_institutions.json";
import belgium from "../../site/data/belgium/ambassador_institutions.json";

// Bundled at build time (slice 1). The three amb-v1 files are the published allowlists; owner
// overrides are already applied in them (regions/<slug>/ambassador_domains.csv).

export const REGIONS = ["california", "norway", "belgium"] as const;
export type Region = (typeof REGIONS)[number];

interface AllowlistFile {
  schema: string;
  region: string;
  institutions: {
    id: string;
    name: string;
    type: string;
    works: number;
    domains: string[];
    needs_domain?: boolean;
    /** Short ROR URL (https://ror.org/<id>), or null when unknown. ORCID employments match through it. */
    ror: string | null;
  }[];
}

export interface InstitutionMatch {
  institutionId: string;
  institutionName: string;
  domain: string;
}

// Mirrors FREE_MAIL_DOMAINS in src/atlas/build/ambassadors.py (the build refuses these as well).
// Only the registrable names are listed; subdomains of them are refused by suffix match.
const FREE_MAIL = new Set([
  "gmail.com", "googlemail.com", "outlook.com", "outlook.fr", "hotmail.com", "hotmail.co.uk", "live.com",
  "live.co.uk", "msn.com", "yahoo.com", "yahoo.co.uk", "yahoo.fr", "ymail.com", "aol.com", "icloud.com",
  "me.com", "mac.com", "proton.me", "protonmail.com", "pm.me", "gmx.com", "gmx.net", "gmx.de", "web.de",
  "mail.com", "zoho.com", "yandex.com", "yandex.ru", "qq.com", "163.com", "126.com", "hey.com", "fastmail.com",
  "tutanota.com", "tuta.io", "mailbox.org", "seznam.cz", "wp.pl", "orange.fr", "free.fr", "laposte.net",
]);

const ALLOWLISTS: Record<Region, Map<string, { id: string; name: string }>> = {
  california: buildAllowlist(california as AllowlistFile),
  norway: buildAllowlist(norway as AllowlistFile),
  belgium: buildAllowlist(belgium as AllowlistFile),
};

const NAMES: Record<Region, Map<string, string>> = {
  california: institutionNames(california as AllowlistFile),
  norway: institutionNames(norway as AllowlistFile),
  belgium: institutionNames(belgium as AllowlistFile),
};

function buildAllowlist(file: AllowlistFile): Map<string, { id: string; name: string }> {
  const map = new Map<string, { id: string; name: string }>();
  // The files list institutions by works (descending), so the first owner of a shared domain wins.
  for (const inst of file.institutions) {
    if (inst.needs_domain) continue;
    for (const domain of inst.domains) {
      if (!map.has(domain)) map.set(domain, { id: inst.id, name: inst.name });
    }
  }
  return map;
}

function institutionNames(file: AllowlistFile): Map<string, string> {
  return new Map(file.institutions.map((inst) => [inst.id, inst.name]));
}

const ALL_FILES: [Region, AllowlistFile][] = [
  ["california", california as AllowlistFile],
  ["norway", norway as AllowlistFile],
  ["belgium", belgium as AllowlistFile],
];

// Institution id -> the regions whose allowlist lists it (region membership). Eligible = at least one region.
const MEMBERSHIP = new Map<string, Region[]>();
// Institution id -> its own allowlist domains (union over regions), for claimed-institution matching.
const OWN_DOMAINS = new Map<string, string[]>();
// Institution id -> display name (first region that lists it).
const DISPLAY_NAMES = new Map<string, string>();
// ROR URL -> institution id, from allowlist `ror` fields when present.
const ROR_TO_INSTITUTION = new Map<string, string>();

for (const [region, file] of ALL_FILES) {
  for (const inst of file.institutions) {
    const regions = MEMBERSHIP.get(inst.id) ?? [];
    if (!regions.includes(region)) regions.push(region);
    MEMBERSHIP.set(inst.id, regions);
    if (!DISPLAY_NAMES.has(inst.id)) DISPLAY_NAMES.set(inst.id, inst.name);
    if (!inst.needs_domain) {
      const own = OWN_DOMAINS.get(inst.id) ?? [];
      for (const domain of inst.domains) if (!own.includes(domain)) own.push(domain);
      OWN_DOMAINS.set(inst.id, own);
    }
    if (inst.ror && !ROR_TO_INSTITUTION.has(inst.ror)) ROR_TO_INSTITUTION.set(inst.ror, inst.id);
  }
}

/** Regions whose allowlist lists this OpenAlex institution id (empty when not eligible anywhere). */
export function regionsForInstitution(institutionId: string): Region[] {
  return [...(MEMBERSHIP.get(institutionId) ?? [])];
}

/** Display name from the bundled allowlists, or null when the institution is not listed. */
export function institutionDisplayName(institutionId: string): string | null {
  return DISPLAY_NAMES.get(institutionId) ?? null;
}

/** Allowlist institution id for a ROR URL (only when an allowlist carries its ror field), or null. */
export function institutionIdForRor(ror: string): string | null {
  return ROR_TO_INSTITUTION.get(ror) ?? null;
}

/**
 * Matches an email domain against the domains of the claimed institutions only (sign-up, section 13).
 * Free-mail is refused first. Returns the claimed institution whose domain (or a parent of it) matches.
 */
export function matchClaimedInstitution(
  claimedIds: readonly string[],
  emailDomain: string,
): { institutionId: string; regions: Region[]; domain: string } | null {
  const names = suffixes(emailDomain.toLowerCase());
  if (names.some((name) => FREE_MAIL.has(name))) return null;
  for (const id of claimedIds) {
    const owned = OWN_DOMAINS.get(id) ?? [];
    const domain = names.find((name) => owned.includes(name));
    if (domain) return { institutionId: id, regions: regionsForInstitution(id), domain };
  }
  return null;
}

export function isRegion(value: unknown): value is Region {
  return typeof value === "string" && (REGIONS as readonly string[]).includes(value);
}

/** Institution name for a region's institution id (from the bundled allowlist), or null. */
export function institutionName(region: Region, institutionId: string): string | null {
  return NAMES[region].get(institutionId) ?? null;
}

/** Domain suffixes from most to least specific: bio.uio.no -> bio.uio.no, uio.no, no. */
function suffixes(domain: string): string[] {
  const labels = domain.split(".");
  const out: string[] = [];
  for (let i = 0; i < labels.length; i++) out.push(labels.slice(i).join("."));
  return out;
}

/**
 * Matches an email domain against a region's allowlist. Subdomains of an allowed registrable domain
 * are accepted. Free-mail (and any subdomain of it) is refused first. Returns null when not eligible.
 */
export function matchInstitution(region: Region, emailDomain: string): InstitutionMatch | null {
  const domain = emailDomain.toLowerCase();
  const names = suffixes(domain);
  if (names.some((name) => FREE_MAIL.has(name))) return null;
  for (const name of names) {
    const hit = ALLOWLISTS[region].get(name);
    if (hit) return { institutionId: hit.id, institutionName: hit.name, domain: name };
  }
  return null;
}
