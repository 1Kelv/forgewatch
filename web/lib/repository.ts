export const FREQUENCIES = ["manual", "daily", "weekly"] as const;
export type Frequency = (typeof FREQUENCIES)[number];

export const FREQUENCY_LABELS: Record<Frequency, string> = {
  manual: "Manual only",
  daily: "Every day",
  weekly: "Every week",
};

const REPOSITORY_PART = /^[A-Za-z0-9_.-]+$/;
const BRANCH = /^[A-Za-z0-9._/-]+$/;

export function parseGitHubRepository(value: string): string {
  const raw = value.trim().replace(/\/+$/, "").replace(/\.git$/i, "");
  let path = raw;
  if (/^https?:\/\//i.test(raw)) {
    const url = new URL(raw);
    if (url.protocol !== "https:" || url.hostname.toLowerCase() !== "github.com") {
      throw new Error("Enter a GitHub repository URL from github.com.");
    }
    path = url.pathname.replace(/^\//, "");
  }
  const parts = path.split("/");
  if (parts.length !== 2 || !parts.every((part) => REPOSITORY_PART.test(part))) {
    throw new Error("Use a repository URL such as https://github.com/owner/repository.");
  }
  return `${parts[0]}/${parts[1]}`;
}

export function validateBranch(value: string): string {
  const branch = value.trim();
  if (!branch || branch.length > 255 || !BRANCH.test(branch) || branch.includes("..")) {
    throw new Error("Enter a valid Git branch name.");
  }
  return branch;
}

export function nextScanAt(frequency: Frequency, from = new Date()): Date | null {
  if (frequency === "manual") return null;
  const nextCron = new Date(
    Date.UTC(from.getUTCFullYear(), from.getUTCMonth(), from.getUTCDate(), 3, 17),
  );
  if (nextCron.getTime() <= from.getTime()) nextCron.setUTCDate(nextCron.getUTCDate() + 1);
  if (frequency === "weekly") nextCron.setUTCDate(nextCron.getUTCDate() + 6);
  return nextCron;
}
