// Pure view model for the V-3 pipeline flow (EM-6, Add-on A2 §5). No DOM access, so Node tests
// can import it. The counts come from site/data/methods_flow.json, which is built from AT-10.

export const UNAVAILABLE = "Pipeline counts are unavailable.";

export function formatCount(value) {
  return Number.isSafeInteger(value) && value >= 0
    ? new Intl.NumberFormat("en-US").format(value)
    : "Unavailable";
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

// One row per stage, in file order. Malformed stages are skipped rather than rendered.
export function stageRows(data) {
  if (!isObject(data) || !Array.isArray(data.stages)) return [];
  return data.stages.filter((stage) => isObject(stage) && typeof stage.stage === "string").map((stage) => {
    const performed = stage.status === "performed";
    const steps = (Array.isArray(stage.steps) ? stage.steps : []).filter(isObject).map((step) => ({
      label: String(step.label ?? ""),
      value: formatCount(step.value),
      raw: step.value
    }));
    return {
      stage: stage.stage,
      status: performed ? "performed" : "not performed",
      performed,
      steps,
      note: typeof stage.note === "string" && stage.note ? stage.note : null
    };
  });
}

// Footer sentence: the release version when the release date matches, else the release date.
export function footerText(data) {
  const source = isObject(data) && data.release_version
    ? data.release_version
    : isObject(data) && data.release_date ? data.release_date : "current";
  return `Flow follows the ROSES template for systematic maps (CC BY 4.0). Counts from the ${source} methods card.`;
}
