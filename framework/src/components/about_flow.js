// Living screening flow for the About page (owner request 2026-11-17).
// Reads build_metadata.json `flow` (written by every daily export) and falls back to the archived
// release flow in methods_flow.json. Every number shown comes from one of those two files.

const fmt = (n) => (Number.isFinite(n) ? n.toLocaleString("en-US") : "–");
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);

// Rows: {label, value, out: {label, value} | null, c: task colour token}.
export function liveFlowRows(flow) {
  if (!flow || !Number.isFinite(flow.published)) return null;
  const rows = [];
  if (Number.isFinite(flow.records_retrieved)) {
    rows.push({label: "Records retrieved", note: "OpenAlex search plus ORCID, eScholarship and curated additions", value: flow.records_retrieved,
      out: {label: "Duplicate records merged", value: flow.duplicates_collapsed}, c: "--atlas-task-water"});
  }
  rows.push({label: "Unique works screened", value: flow.unique_works,
    out: {label: "No California-affiliated author", value: flow.no_ca_authorship}, c: "--atlas-task-water"});
  rows.push({label: "With a California author", value: flow.unique_works - flow.no_ca_authorship,
    out: {label: "Removed by curation decisions", value: flow.removed_by_curation}, c: "--atlas-task-people"});
  rows.push({label: "Published in the Atlas", value: flow.published,
    out: {label: "Not plastic-related (kept, but not on the Evidence map)", value: flow.not_plastic_related}, c: "--atlas-task-money"});
  rows.push({label: "Plastic-related works", note: "shown on the Evidence map", value: flow.plastic_related, out: null, c: "--atlas-task-evidence"});
  return rows;
}

export function releaseFlowRows(data) {
  const steps = (data?.stages ?? []).flatMap((stage) => stage.steps ?? []).filter((s) => Number.isFinite(s.value));
  if (!steps.length) return null;
  const colours = ["--atlas-task-water", "--atlas-task-water", "--atlas-task-people", "--atlas-task-money", "--atlas-task-evidence", "--atlas-task-evidence"];
  return steps.map((step, i) => ({
    label: step.label,
    value: step.value,
    out: i < steps.length - 1 ? {label: "Not carried forward", value: step.value - steps[i + 1].value} : null,
    c: colours[Math.min(i, colours.length - 1)]
  }));
}

export function renderFlow(container, rows, caption) {
  if (!rows) {
    container.innerHTML = `<p class="about-flow__empty">Screening counts are unavailable in this snapshot.</p>`;
    return;
  }
  const items = rows.map((row, i) => `
    <li class="about-flow__row" style="--c: var(${row.c}); --i: ${i}">
      <div class="about-flow__box">
        <span class="about-flow__value">${fmt(row.value)}</span>
        <span class="about-flow__label">${esc(row.label)}</span>
        ${row.note ? `<span class="about-flow__note">${esc(row.note)}</span>` : ""}
      </div>
      ${row.out && Number.isFinite(row.out.value) ? `<div class="about-flow__out"><span class="about-flow__value">${fmt(row.out.value)}</span><span class="about-flow__label">${esc(row.out.label)}</span></div>` : ""}
    </li>`).join("");
  container.innerHTML = `<ol class="about-flow" aria-label="Screening flow, from records retrieved to plastic-related works">${items}</ol><p class="about-flow__caption">${caption}</p>`;
}

export function mountAboutFlow(container, metadata, releaseFlow) {
  const live = liveFlowRows(metadata?.flow);
  if (live) {
    renderFlow(container, live, "Counts from today’s build. They change as new work is published and as review decisions are recorded. Laid out after the PRISMA and ROSES flow diagrams used for systematic maps.");
  } else {
    const version = releaseFlow?.release_version ? ` ${esc(releaseFlow.release_version)}` : "";
    renderFlow(container, releaseFlowRows(releaseFlow), `Counts from the archived release${version}; the daily build will replace them with live counts. Laid out after the ROSES flow diagram for systematic maps (CC BY 4.0).`);
  }
}
