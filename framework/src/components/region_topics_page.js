// Reuse the California topics renderer. This region-only adapter localizes its scope text after
// rendering so GP-1 keeps the California renderer bundle byte-for-byte unchanged.
import {renderTopics} from "./topics_page.js";

export async function mountRegionTopics(root, {series, bursts, Plot}) {
  try {
    const [payload, burstPayload] = await Promise.all([series(), bursts().catch(() => null)]);
    renderTopics(root, payload, burstPayload, {Plot});
    const region = String(payload.region_name || payload.scope || "regional");
    const replacements = [
      ["plastic-related California works", `unscreened ${region} works`],
      ["plastic-related works", `unscreened ${region} works`],
      ["plastic-related California", `unscreened ${region}`],
      ["plastic-related", "unscreened"],
      ["rising screen", "trend screen"],
    ];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      let value = walker.currentNode.nodeValue;
      for (const [from, to] of replacements) value = value.replaceAll(from, to);
      walker.currentNode.nodeValue = value;
    }
    root.querySelectorAll("[aria-label]").forEach((node) => {
      let value = node.getAttribute("aria-label");
      for (const [from, to] of replacements) value = value.replaceAll(from, to);
      node.setAttribute("aria-label", value);
    });
    root.querySelectorAll(".tp-scroll[role='region']").forEach((node, index) => {
      const caption = node.querySelector("table caption")?.textContent?.trim();
      node.setAttribute("aria-label", caption || `${region} topic data table ${index + 1}`);
    });
  } catch (error) {
    root.replaceChildren(Object.assign(document.createElement("p"), {
      className: "tp-status", textContent: "The topic data could not be loaded.",
    }));
    console.error("topics:", error);
  }
}
