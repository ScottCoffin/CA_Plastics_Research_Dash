// The Ambassador badge (AMB-1): one SVG component, drawn into every [data-amb] element, so every page shows the
// same seal. A seal carries the Plastiverse Live sun mark and the label "Ambassador · <region>".
// Accessible name: "Plastiverse Live ambassador for <region>" (role img). Styles: ambassadors.css (.amb).
//
// Seal outline: the Lucide "badge" icon, ISC licence (lucide-static 0.460.0, https://lucide.dev).
// Sun mark: the Plastiverse Live mark. Nothing is fetched at run time.

const SEAL_BODY = "M3.85 8.62a4 4 0 0 1 4.78-4.77 4 4 0 0 1 6.74 0 4 4 0 0 1 4.78 4.78 4 4 0 0 1 0 6.74 4 4 0 0 1-4.77 4.78 4 4 0 0 1-6.75 0 4 4 0 0 1-4.78-4.77 4 4 0 0 1 0-6.76Z";
const escapeText = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

// The badge markup for one region name ("Norway", "California").
export function badgeHTML(region, {large = false} = {}) {
  const name = escapeText(region);
  return `<span class="amb${large ? " lg" : ""}" role="img" aria-label="Plastiverse Live ambassador for ${name}">` +
    '<svg class="seal" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
    `<path class="seal-body" d="${SEAL_BODY}"/>` +
    '<g class="seal-sun" transform="translate(12 12) scale(.36) translate(-14 -14)"><circle cx="14" cy="14" r="6"/><path d="M2 14H26M14 2V26"/></g>' +
    '</svg>' +
    `<span class="amb-label"><span class="amb-word">Ambassador</span><span class="amb-sep" aria-hidden="true"> · </span><span class="amb-reg">${name}</span></span>` +
    "</span>";
}

// Fill every [data-amb="<region name>"] element under root with the badge. data-big makes the large variant.
export function mountBadges(root = document) {
  root.querySelectorAll("[data-amb]").forEach((el) => {
    el.outerHTML = badgeHTML(el.getAttribute("data-amb"), {large: el.hasAttribute("data-big")});
  });
}
