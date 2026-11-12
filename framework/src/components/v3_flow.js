// V-3 pipeline flow diagram (EM-6, Add-on A2 §5): one box per ROSES stage, numbered steps and
// arrows between boxes. Rendered as nested ordered lists so screen readers get the sequence.
// Helpers that need no DOM live in v3_flow_model.js.
import {loadJson} from "./atlas.js";
import {UNAVAILABLE, footerText, stageRows} from "./v3_flow_model.js";

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function buildStage(row) {
  const item = el("li", `v3-stage ${row.performed ? "v3-stage--performed" : "v3-stage--off"}`);
  item.append(el("h3", "v3-stage-name", row.stage), el("p", "v3-status", row.status));
  if (row.steps.length) {
    const steps = el("ol", "v3-steps");
    for (const step of row.steps) {
      const li = el("li", "v3-step");
      li.append(el("span", "v3-step-label", step.label), el("span", "v3-step-value", step.value));
      steps.append(li);
    }
    item.append(steps);
  }
  if (row.note) item.append(el("p", "v3-note", row.note));
  return item;
}

export function renderV3Flow(container, data) {
  const rows = stageRows(data);
  if (!rows.length) throw new Error("methods_flow.json has no stages");
  const figure = el("div", "v3-flow");
  figure.append(el("ol", "v3-stages"), el("p", "v3-footer", footerText(data)));
  figure.querySelector(".v3-stages").append(...rows.map(buildStage));
  container.replaceChildren(figure);
}

export async function mountV3Flow(container) {
  if (!container) return;
  try {
    const data = await loadJson("methods_flow.json");
    renderV3Flow(container, data);
  } catch {
    container.replaceChildren(el("p", "v3-unavailable", UNAVAILABLE));
  }
}
