/**
 * Mail templates (AMB-1 slice 2c). One module for every message the Worker writes except the sign-in link (auth.ts).
 * Each template returns plain text and a minimal HTML body: no tracking pixels, no external images, no scripts.
 * Every non-essential mail carries a link to notification settings and a one-click unsubscribe link (RFC 8058 headers).
 */

export interface MailLinks {
  /** Notification settings in the workspace (signed in). */
  settingsUrl: string;
  /** One-click unsubscribe from reminders (GET shows a confirmation page, POST turns reminders off). */
  unsubscribeUrl: string;
}

export interface RenderedMail {
  subject: string;
  text: string;
  html: string;
}

const REGION_NAMES: Record<string, string> = { california: "California", norway: "Norway", belgium: "Belgium" };

/** Display name of a region slug (falls back to the slug). */
export function regionName(region: string): string {
  return REGION_NAMES[region] ?? region;
}

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** RFC 8058 one-click unsubscribe headers. Only for non-essential mail (never the sign-in link). */
export function listUnsubscribeHeaders(unsubscribeUrl: string): Record<string, string> {
  return {
    "List-Unsubscribe": `<${unsubscribeUrl}>`,
    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
  };
}

/** Footer lines shared by every non-essential mail. */
function footer(links: MailLinks): string {
  return (
    `Notification settings: ${links.settingsUrl}\n` +
    `Unsubscribe from reminders (one click): ${links.unsubscribeUrl}`
  );
}

/** Minimal HTML from the plain text: paragraphs split on blank lines, URLs become links, everything escaped. */
function toHtml(text: string): string {
  const paragraphs = text.split("\n\n").map((paragraph) => {
    const escaped = escapeHtml(paragraph).replace(/https:\/\/[^\s<]+/g, (url) => `<a href="${url}">${url}</a>`);
    return `<p>${escaped.replace(/\n/g, "<br>")}</p>`;
  });
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Plastiverse</title></head><body>${paragraphs.join("")}</body></html>`;
}

function render(subject: string, bodyText: string, links: MailLinks): RenderedMail {
  const text = `${bodyText}\n\n${footer(links)}\n`;
  return { subject, text, html: toHtml(text) };
}

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

/** 1. Welcome and thanks, sent once when an ambassador first joins. */
export function welcomeMail(input: { regionName: string; workspaceUrl: string; links: MailLinks }): RenderedMail {
  const body =
    `Thank you for joining the Plastiverse ambassador programme for ${input.regionName}.\n\n` +
    "What happens next: open the workspace to see the review tasks for your region. Each task takes a few minutes. " +
    "An answer counts once a second ambassador gives the same answer.\n\n" +
    `Workspace: ${input.workspaceUrl}\n\n` +
    "Bring colleagues: the workspace lists your co-authors. Each invitation opens in your own email program, " +
    "and the Atlas never stores their addresses.";
  return render("Welcome to the Plastiverse ambassador workspace", body, input.links);
}

/** 3. Fortnightly reminder: only when tasks are open and reminders are on. */
export function reminderMail(input: {
  regionName: string;
  open: number;
  minutes: number;
  confirmed: number;
  total: number;
  nextUrl: string;
  links: MailLinks;
}): RenderedMail {
  const subject = `${plural(input.open, "open task")} in ${input.regionName}`;
  const body =
    `You have ${plural(input.open, "open task")} in the ${input.regionName} workspace, about ${plural(input.minutes, "minute")} in total.\n\n` +
    `Region progress: ${input.confirmed} of ${input.total} ${input.regionName} cases have a confirmed answer.\n\n` +
    `Next task: ${input.nextUrl}\n\n` +
    "You get one reminder every two weeks while tasks are open. After three reminders without an answer, " +
    "reminders pause until you sign in again.";
  return render(subject, body, input.links);
}

/**
 * Invitation text for the ambassador's own email program (mailto, no recipient). The Atlas sends nothing and stores
 * no address: the ambassador adds the co-author's address.
 */
export function invitationText(inviteUrl: string): { subject: string; body: string } {
  return {
    subject: "Join me in the Plastiverse ambassador programme",
    body:
      "I am an ambassador for the Plastiverse Atlas of plastics research. Your research is in its corpus, " +
      "and I think you would be a good ambassador too. Joining takes a few minutes with your institutional email:\n\n" +
      `${inviteUrl}\n\n` +
      "The link is a personal invitation from me.",
  };
}

/** mailto: href with subject and body, no recipient. */
export function mailtoHref(subject: string, body: string): string {
  return `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}
