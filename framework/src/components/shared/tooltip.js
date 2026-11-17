// VD-24 shared tooltips, placed by VD-29. A tip is one bubble, .atlas-tip, that this module appends to
// document.body (or to the full-screen element) and places with fixed viewport coordinates, so no ancestor's
// overflow can clip it. The bubble keeps 8 px from its trigger and 8 px inside the viewport edges, and flips
// above/below (or to a side) when there is no room. Styles are in framework/src/design/components.css.
//
// The bubble opens on mouse hover (fine pointers only), on keyboard focus (:focus-visible) and on a click or
// tap on a help button (.atlas-help, through aria-expanded). Esc dismisses it without moving focus (WCAG 1.4.13),
// and the pointer can move onto the bubble to read it: it closes only after the pointer leaves both.

const EDGE = 8; // px kept between the bubble and the viewport edges
const GAP = 8; // px between the trigger and the bubble
const HOVER_GRACE_MS = 150; // lets the pointer cross the gap from the trigger onto the bubble

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

let bubble = null; // the one .atlas-tip element, created on first use
let shown = null; // the trigger the bubble currently describes
let hovered = null; // the trigger under the pointer
let focused = null; // the trigger with keyboard focus
let dismissed = false; // Esc was pressed; cleared by the next focus, pointer entry or click
let hideTimer = 0;
let installed = false;

const canHover = () => window.matchMedia("(hover: hover)").matches;

function ensureBubble() {
  if (!bubble) {
    bubble = document.createElement("div");
    bubble.className = "atlas-tip";
    bubble.setAttribute("aria-hidden", "true");
    bubble.hidden = true;
  }
  return bubble;
}

function hide() {
  shown = null;
  if (bubble) bubble.hidden = true;
}

// Keyboard focus wins, then the pointer, then a help button that a click or tap has opened.
function wanted() {
  if (dismissed) return null;
  const open = document.querySelector('.atlas-help[aria-expanded="true"]');
  return [focused, hovered, open].find((tip) => tip && tip.isConnected) || null;
}

function viewport() {
  return {width: document.documentElement.clientWidth, height: document.documentElement.clientHeight};
}

// Start position for a box of size px along an axis of limit px, kept EDGE px inside both ends.
const keepInside = (start, size, limit) => Math.min(Math.max(start, EDGE), Math.max(EDGE, limit - EDGE - size));

// Shows nothing for a trigger scrolled or hidden out of the viewport (a zero-size box is hidden too).
function onScreen(tip) {
  const r = tip.getBoundingClientRect();
  const view = viewport();
  return r.width > 0 && r.height > 0 && r.bottom > 0 && r.right > 0 && r.top < view.height && r.left < view.width;
}

// Sets the bubble's fixed left and top from the trigger's box and the bubble's measured size.
function place(tip) {
  const node = ensureBubble();
  const box = node.getBoundingClientRect();
  const r = tip.getBoundingClientRect();
  const view = viewport();
  const pos = tip.getAttribute("data-atlas-tip-pos");
  const align = tip.getAttribute("data-atlas-tip-align");
  let left;
  let top;
  if (pos === "left" || pos === "right") {
    // Beside the trigger: the requested side, or the other side when the requested one has no room.
    const leftStart = r.left - GAP - box.width;
    const rightStart = r.right + GAP;
    const fitsLeft = leftStart >= EDGE;
    const fitsRight = rightStart + box.width <= view.width - EDGE;
    const useLeft = pos === "left" ? (fitsLeft || !fitsRight) : (!fitsRight && fitsLeft);
    left = keepInside(useLeft ? leftStart : rightStart, box.width, view.width);
    top = keepInside(r.top + (r.height - box.height) / 2, box.height, view.height);
  } else {
    // Above by default; below when requested or when there is no room above. Centred on the trigger, or on
    // its start or end edge for data-atlas-tip-align.
    const aboveStart = r.top - GAP - box.height;
    const belowStart = r.bottom + GAP;
    const fitsAbove = aboveStart >= EDGE;
    const fitsBelow = belowStart + box.height <= view.height - EDGE;
    const useBelow = pos === "below" ? (fitsBelow || !fitsAbove) : (!fitsAbove && fitsBelow);
    top = keepInside(useBelow ? belowStart : aboveStart, box.height, view.height);
    let anchor = r.left + (r.width - box.width) / 2;
    if (align === "start") anchor = r.left;
    if (align === "end") anchor = r.right - box.width;
    left = keepInside(anchor, box.width, view.width);
  }
  node.style.left = `${left}px`;
  node.style.top = `${top}px`;
}

// Brings the bubble in line with the wanted trigger: shows and places it, or hides it.
function refresh() {
  const tip = wanted();
  const text = tip ? tip.getAttribute("data-atlas-tip") : "";
  if (!tip || !text || !onScreen(tip)) {
    hide();
    return;
  }
  const node = ensureBubble();
  // In native full screen only the full-screen element and its descendants are drawn, so the bubble moves into it.
  const host = document.fullscreenElement || document.body;
  if (node.parentElement !== host) host.append(node);
  node.textContent = text;
  node.hidden = false;
  shown = tip;
  place(tip);
}

function endHover() {
  if (hovered && hovered.matches(":hover")) return;
  if (bubble && bubble.matches(":hover")) return;
  hovered = null;
  refresh();
}

// Call once per page; repeat calls are harmless. Sets aria-expanded on the help buttons under root and
// installs document-level listeners once, so help buttons rendered later also respond to taps and keys.
export function initTooltips(root = document) {
  for (const button of root.querySelectorAll(".atlas-help")) {
    if (!button.hasAttribute("aria-expanded")) button.setAttribute("aria-expanded", "false");
  }
  if (installed) {
    refresh();
    return;
  }
  installed = true;

  document.addEventListener("click", (event) => {
    // A click on the bubble (the pointer can reach it) leaves an open help button open.
    if (bubble && bubble.contains(event.target)) return;
    const help = within(event.target, ".atlas-help");
    for (const open of document.querySelectorAll('.atlas-help[aria-expanded="true"]')) {
      if (open !== help) open.setAttribute("aria-expanded", "false");
    }
    if (help) help.setAttribute("aria-expanded", String(help.getAttribute("aria-expanded") !== "true"));
    dismissed = false;
    refresh();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    for (const open of document.querySelectorAll('.atlas-help[aria-expanded="true"]')) {
      open.setAttribute("aria-expanded", "false");
    }
    dismissed = true;
    refresh();
  });

  document.addEventListener("focusin", (event) => {
    const tip = within(event.target, "[data-atlas-tip]");
    focused = tip && event.target.matches(":focus-visible") ? tip : null;
    dismissed = false;
    refresh();
  });

  document.addEventListener("focusout", () => {
    focused = null;
    refresh();
  });

  document.addEventListener("mouseover", (event) => {
    if (!canHover()) return;
    if (bubble && !bubble.hidden && bubble.contains(event.target)) {
      clearTimeout(hideTimer);
      return;
    }
    const tip = within(event.target, "[data-atlas-tip]");
    if (!tip) return;
    clearTimeout(hideTimer);
    if (tip === hovered) return;
    hovered = tip;
    dismissed = false;
    refresh();
  });

  document.addEventListener("mouseout", (event) => {
    if (!canHover()) return;
    const inside = (node) => (hovered && hovered.contains(node))
      || (bubble && !bubble.hidden && bubble.contains(node));
    if (!inside(event.target) || inside(event.relatedTarget)) return;
    clearTimeout(hideTimer);
    hideTimer = window.setTimeout(endHover, HOVER_GRACE_MS);
  });

  // Scrolling (in any container, hence the capture phase) and resizing move the trigger under a fixed bubble.
  document.addEventListener("scroll", () => { if (shown) refresh(); }, {capture: true, passive: true});
  window.addEventListener("resize", () => refresh());
  document.addEventListener("fullscreenchange", () => refresh());
}
