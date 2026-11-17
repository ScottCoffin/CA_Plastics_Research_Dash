// VD-24 shared tooltips. The styles are in framework/src/design/components.css: hover and keyboard focus
// on any [data-atlas-tip] element are pure CSS. This module adds the part CSS cannot do: a tap opens a
// help button (.atlas-help) through aria-expanded, Esc and a tap outside close it, and Esc dismisses a
// tip that keyboard focus is showing without moving focus (WCAG 1.4.13).

const DISMISSED = "atlas-tip--dismissed";
const HELP_ICON = '<svg class="atlas-help__icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
  + '<circle cx="12" cy="12" r="9.5"/><path d="M12 11v5.5M12 7.5h.01"/></svg>';

const escapeAttr = (value) => String(value).replace(/[&<>"']/g, (char) => (
  {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[char]
));

// The Element that target is, or is inside, when it matches selector (null otherwise).
const within = (target, selector) => (target instanceof Element ? target.closest(selector) : null);

// Markup for a help button beside a heading or label. text is a one or two sentence explanation, shown on
// hover, on keyboard focus and on tap. subject completes the accessible name: "About <subject>: <text>".
// align ("start" or "end") anchors the bubble to the button's left or right edge, for a button near a viewport edge.
export function helpButtonHtml(text, {subject = "this chart", align = ""} = {}) {
  const alignAttr = align ? ` data-atlas-tip-align="${escapeAttr(align)}"` : "";
  return `<button type="button" class="atlas-help"${alignAttr} aria-label="${escapeAttr(`About ${subject}: ${text}`)}"`
    + ` data-atlas-tip="${escapeAttr(text)}" aria-expanded="false">${HELP_ICON}</button>`;
}

let installed = false;

// Call once per page; repeat calls are harmless. Sets aria-expanded on the help buttons under root and
// installs document-level listeners once, so help buttons rendered later also respond to taps and keys.
export function initTooltips(root = document) {
  for (const button of root.querySelectorAll(".atlas-help")) {
    if (!button.hasAttribute("aria-expanded")) button.setAttribute("aria-expanded", "false");
  }
  if (installed) return;
  installed = true;
  const openHelp = () => document.querySelectorAll('.atlas-help[aria-expanded="true"]');

  document.addEventListener("click", (event) => {
    const help = within(event.target, ".atlas-help");
    for (const open of openHelp()) {
      if (open !== help) open.setAttribute("aria-expanded", "false");
    }
    if (help) help.setAttribute("aria-expanded", String(help.getAttribute("aria-expanded") !== "true"));
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    for (const open of openHelp()) open.setAttribute("aria-expanded", "false");
    within(event.target, "[data-atlas-tip]")?.classList.add(DISMISSED);
  });

  document.addEventListener("focusout", (event) => {
    within(event.target, `.${DISMISSED}`)?.classList.remove(DISMISSED);
  });

  document.addEventListener("mouseout", (event) => {
    const tip = within(event.target, `.${DISMISSED}`);
    if (tip && !tip.contains(event.relatedTarget)) tip.classList.remove(DISMISSED);
  });
}
