import { type Region, institutionDisplayName, institutionIdForRor, regionsForInstitution } from "./eligibility";
import type { Employment } from "./orcid";
import type { AffiliationYears, OpenAlexAuthor } from "./openalex";

export interface ChecklistItem {
  /** OpenAlex institution id (I<digits>), or an unmapped key: ror:<url> or name:<organisation name>. */
  id: string;
  name: string;
  source: "openalex_history" | "orcid_employment";
  country: string | null;
  type: string | null;
  years: AffiliationYears | null;
  /** On a region's allowlist. Only eligible items can make regions available. */
  eligible: boolean;
  regions: Region[];
}

const MAX_ITEMS = 200;

function mergeYears(a: AffiliationYears | null, b: AffiliationYears | null): AffiliationYears | null {
  if (!a) return b;
  if (!b) return a;
  const from = a.from === null ? b.from : b.from === null ? a.from : Math.min(a.from, b.from);
  const to = a.to === null ? b.to : b.to === null ? a.to : Math.max(a.to, b.to);
  return { from, to };
}

/**
 * The institution checklist (section 13): every institution on the author's OpenAlex record (current or past),
 * plus public ORCID employments. An institution listed twice is shown once, with the union of its years.
 */
export function buildChecklist(author: OpenAlexAuthor | null, employments: Employment[]): ChecklistItem[] {
  const byId = new Map<string, ChecklistItem>();
  const add = (item: Omit<ChecklistItem, "eligible" | "regions" | "name"> & { name: string }): void => {
    const regions = regionsForInstitution(item.id);
    const existing = byId.get(item.id);
    if (existing) {
      existing.years = mergeYears(existing.years, item.years);
      return;
    }
    byId.set(item.id, {
      ...item,
      name: institutionDisplayName(item.id) ?? item.name,
      eligible: regions.length > 0,
      regions,
    });
  };

  for (const inst of author?.institutions ?? []) {
    add({ id: inst.id, name: inst.name, source: "openalex_history", country: inst.country, type: inst.type, years: inst.years });
  }
  for (const emp of employments) {
    const mapped = emp.ror ? institutionIdForRor(emp.ror) : null;
    const id = mapped ?? (emp.ror ? `ror:${emp.ror}` : `name:${emp.orgName}`);
    add({
      id,
      name: emp.orgName,
      source: "orcid_employment",
      country: emp.country,
      type: null,
      years: { from: emp.startYear, to: emp.endYear },
    });
  }

  return [...byId.values()]
    .sort((a, b) => Number(b.eligible) - Number(a.eligible) || a.name.localeCompare(b.name))
    .slice(0, MAX_ITEMS);
}
