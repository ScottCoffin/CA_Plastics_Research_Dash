// Plain-language labels for community group taxonomy values (AMB-GROUPS-UX). Keys come from config/groups_taxonomy.yml;
// the labels are what volunteers and readers see. A value without a label falls back to its key with underscores
// replaced and the first letter capitalised. Pure module: no DOM and no imports, so Node tests can load it.

export const GROUP_LABELS = Object.freeze({
  entity_type: Object.freeze({
    organisation: "Organisation", network_coalition: "Network or coalition", programme_project: "Programme or project",
    campaign: "Campaign", informal_group: "Informal group", chapter_branch: "Chapter or branch", other: "Other",
  }),
  sector: Object.freeze({
    ngo_civil_society: "NGO or civil society", community_informal: "Community or informal group", foundation: "Foundation",
    academia_research: "Academia or research", private_sector: "Private sector", government: "Government",
    joint_power_authority: "Joint powers authority", igo: "Intergovernmental body", other: "Other",
  }),
  plastics_centrality: Object.freeze({
    primary: "Primary focus", substantial: "Substantial part of their work", incidental: "Incidental (a passing mention)",
    none: "None", cannot_determine: "Cannot determine",
  }),
  primary_activities: Object.freeze({
    advocacy_campaigning: "Advocacy and campaigns", policy_governance: "Policy and governance",
    research_monitoring: "Research and monitoring", education_awareness: "Education and awareness",
    cleanup_removal: "Clean-ups and litter removal", waste_management_recycling: "Waste management and recycling",
    reuse_refill_alternatives: "Reuse, refill and alternatives", business_innovation: "Business and innovation",
    community_organising_justice: "Community organising and justice", coalition_building_capacity: "Coalition building and capacity",
    funding_grantmaking: "Funding and grant-making", legal_action: "Legal action", other: "Other",
  }),
  geographic_scope: Object.freeze({
    local: "Local", subnational: "State or province", national: "National", regional_multi_country: "Regional (several countries)",
    global: "Global",
  }),
  legal_form: Object.freeze({
    registered_nonprofit: "Registered nonprofit", unincorporated: "Unincorporated", company: "Company", public_body: "Public body",
    university: "University", unknown: "Unknown",
  }),
  participation_in_science: Object.freeze({
    contractual: "Contractual", contributory: "Contributory", collaborative: "Collaborative", co_created: "Co-created",
    collegial: "Collegial", not_applicable: "Not applicable",
  }),
  constituency: Object.freeze({
    frontline_fenceline: "Frontline and fenceline communities", indigenous: "Indigenous peoples", youth: "Youth",
    waste_workers: "Waste workers", coastal_fishing: "Coastal and fishing communities", faith: "Faith communities",
    consumers: "Consumers", industry: "Industry", other: "Other",
  }),
  relation: Object.freeze({
    member_of: "Member of", partner_of: "Partner of", fiscal_sponsor: "Fiscal sponsor", parent_of: "Parent body of",
    funded_by: "Funded by",
  }),
  cannot_determine_reason: Object.freeze({
    no_web_presence: "No web presence", dead_link: "Dead link", language_barrier: "Language barrier",
    insufficient_information: "Insufficient information", not_an_organisation: "Not an organisation",
    conflict_of_interest: "Conflict of interest",
  }),
});

/** Key with underscores replaced by spaces and the first letter capitalised, e.g. "joint_thing" -> "Joint thing". */
export const niceLabel = (value) => String(value).replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());

/** Plain label for a taxonomy value of one facet kind. Empty input gives "". */
export function groupLabel(kind, value) {
  if (value === undefined || value === null || value === "") return "";
  const key = String(value);
  const labels = GROUP_LABELS[kind];
  return labels && Object.hasOwn(labels, key) ? labels[key] : niceLabel(key);
}
