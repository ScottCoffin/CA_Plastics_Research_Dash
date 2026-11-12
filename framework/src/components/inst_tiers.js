// Pure tiers helpers for the Institutions page (AT-5e). Lift-and-shift of <script id="inst-tiers-helpers">
// in site/index.html; the code is unchanged (a drift test in tests/test_framework_institutions.py
// compares them). No DOM access at module load, so Node tests can import this file.
export const instTiers = Object.freeze({
  esc(v) { return String(v ?? "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c])); },
  fmt(n) { return Number(n || 0).toFixed(1); },
  viewFromParams(params) { return params.get("inst_view") === "list" ? "list" : "tiers"; },
  applyViewParam(params, view) { if (view === "list") params.set("inst_view", "list"); },
  // Groups rows by tier (optionally one atlas_type), sorts each tier by fractional works, and computes a shared bar scale.
  groupTiers(rows, type) {
    const by = new Map();
    (rows || []).filter((r) => !type || (r.atlas_type || "other") === type).forEach((r) => { if (!by.has(r.tier)) by.set(r.tier, []); by.get(r.tier).push(r); });
    return [...by.keys()].sort((a, b) => a - b).map((tier) => {
      const list = by.get(tier).slice().sort((a, b) => b.works_frac - a.works_frac || String(a.name).localeCompare(String(b.name)));
      const fr = list.map((r) => r.works_frac);
      return { tier, rows: list, fracMin: Math.min(...fr), fracMax: Math.max(...fr), scaleMin: Math.min(...list.map((r) => r.frac_lo)), scaleMax: Math.max(...list.map((r) => r.frac_hi)) };
    });
  },
  summary(g) { return `Tier ${g.tier} · ${g.rows.length} institution${g.rows.length === 1 ? "" : "s"} · fractional works ${this.fmt(g.fracMin)}–${this.fmt(g.fracMax)}`; },
  rankText(r) { return r.rank_lo === r.rank_hi ? `rank ${r.rank_lo}` : `ranks ${r.rank_lo}–${r.rank_hi}`; },
  rangeSvg(r, lo, hi) {
    const w = 120, span = hi > lo ? hi - lo : 1, x = (v) => Math.max(0, Math.min(w, ((v - lo) / span) * w)).toFixed(1);
    const label = `${this.fmt(r.works_frac)} fractional works, 95% range ${this.fmt(r.frac_lo)} to ${this.fmt(r.frac_hi)}`;
    return `<svg class="tier-bar" viewBox="0 0 ${w} 12" width="${w}" height="12" role="img" aria-label="${this.esc(label)}"><line class="tier-bar-axis" x1="0" x2="${w}" y1="6" y2="6"/><line class="tier-bar-range" x1="${x(r.frac_lo)}" x2="${x(r.frac_hi)}" y1="6" y2="6"/><circle class="tier-bar-dot" cx="${x(r.works_frac)}" cy="6" r="3.5"/></svg>`;
  },
  rowHtml(r, g) {
    const e = this.esc;
    return `<li class="tier-row"><button class="tier-name" type="button" data-institution-id="${e(r.inst_id)}" title="View experts at ${e(r.name)}">${e(r.name)}</button><span class="chip">${e(r.atlas_type || "other")}</span><span class="tier-full">${r.works_full} works (full count)</span><span class="tier-frac">${this.fmt(r.works_frac)} (${this.fmt(r.frac_lo)}–${this.fmt(r.frac_hi)}) ${this.rangeSvg(r, g.scaleMin, g.scaleMax)}</span><span class="tier-rank">${this.rankText(r)}</span></li>`;
  },
  tiersHtml(rows, type) {
    const groups = this.groupTiers(rows, type);
    if (!groups.length) return '<p class="empty">No ranked institutions match this type filter.</p>';
    return groups.map((g) => `<details class="tier-group"${g.tier <= 2 ? " open" : ""}><summary>${this.summary(g)}</summary><ul class="tier-list">${g.rows.map((r) => this.rowHtml(r, g)).join("")}</ul></details>`).join("");
  }
});
